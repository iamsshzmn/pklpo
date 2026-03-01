"""
DAG: features_calc_short

Назначение:
- Расчёт только features_calc_short индикаторов (24 фичи) с инкрементальным обновлением.
- Глобальный freshness gate на старт DAG.
- Параллелизм по символам с ограничением для CPU-bound операций.

Параметры запуска (через dag_run.conf):
- symbols: list[str] (optional, None = все символы)
- timeframes: list[str] (default: ["1m", "5m", "15m", "30m", "1H", "4H", "1D"])
- max_concurrent_symbols: int (default: 3)
"""

import asyncio
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from airflow import DAG
from airflow.operators.python import PythonOperator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from src.features.core import compute_features
from src.features.infrastructure.db_operations import fetch_latest_ts, fetch_ohlcv_df
from src.features.infrastructure.persistence.inserter import insert_indicators
from src.features.presets.features_calc_short_v1 import FEATURES_CALC_SHORT_SPECS
from src.utils.session_utils import get_db_session


def get_or_create_event_loop():
    """Получает существующий event loop или создает новый.

    В Airflow каждая попытка задачи выполняется в отдельном процессе,
    поэтому глобальный loop может быть недоступен. Создаем loop внутри функции.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def get_dag_env() -> dict[str, str]:
    """Получает переменные окружения из Airflow Connections/Variables.

    Источник истины для секретов - только Airflow Connection 'pklpo_db'.
    Остальные параметры (не секреты) - из Variables с безопасными дефолтами.
    """
    from airflow.hooks.base import BaseHook
    from airflow.models import Variable

    env = {}

    # DATABASE_URL ТОЛЬКО из Airflow Connection (источник истины для секретов)
    try:
        conn = BaseHook.get_connection("pklpo_db")
        if not conn:
            raise RuntimeError("Airflow connection 'pklpo_db' is not configured")

        uri = conn.get_uri()
        # Конвертируем postgres:// в postgresql+asyncpg://
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql+asyncpg://", 1)
        env["DATABASE_URL"] = uri
    except Exception as e:
        raise RuntimeError(
            "DATABASE_URL не настроен. Установите Airflow Connection 'pklpo_db' "
            "(Conn Id: pklpo_db, Type: Postgres). "
            "Никаких дефолтов с паролями в коде!"
        ) from e

    # Остальные переменные (не секреты) из Variables с безопасными дефолтами
    env["DATABASE_SSL"] = Variable.get("pklpo_database_ssl", default_var="disable")

    return env


def setup_env(env: dict[str, str | None]) -> None:
    """Устанавливает переменные окружения и создаёт необходимые директории."""
    for key, value in env.items():
        if value is not None:
            os.environ[key] = value

    # Ensure writable dirs exist
    Path("/tmp/pklpo").mkdir(parents=True, exist_ok=True)
    Path("/tmp/pklpo/data").mkdir(parents=True, exist_ok=True)


# Константа для единообразия
OHLCV_TIMESTAMP_COLUMN = "timestamp"  # в миллисекундах


def _timeframe_to_seconds(timeframe: str) -> int:
    """Конвертирует таймфрейм в секунды."""
    multipliers = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1H": 3600,
        "4H": 14400,
        "12H": 43200,
        "1D": 86400,
        "1W": 604800,
        "1M": 2592000,
    }
    return multipliers.get(timeframe, 60)


def _get_limit_for_timeframe(timeframe: str) -> int:
    """Возвращает лимит баров в зависимости от таймфрейма."""
    limits = {
        "1m": 15000,
        "5m": 10000,
        "15m": 5000,
        "30m": 4000,
        "1H": 3000,
        "4H": 2000,
        "12H": 1500,
        "1D": 1000,
        "1W": 500,
        "1M": 300,
    }
    return limits.get(timeframe, 5000)


def _get_timeout_for_timeframe(timeframe: str) -> int:
    """Возвращает таймаут в секундах для таймфрейма.

    Args:
        timeframe: Таймфрейм (например, "1m", "5m", "1D")

    Returns:
        Таймаут в секундах
    """
    timeouts = {
        "1m": 600,  # 10 мин для 1m (много баров)
        "5m": 450,  # 7.5 мин
        "15m": 300,  # 5 мин
        "30m": 300,  # 5 мин
        "1H": 240,  # 4 мин
        "4H": 180,  # 3 мин
        "12H": 150,  # 2.5 мин
        "1D": 120,  # 2 мин для 1D (мало баров)
        "1W": 90,  # 1.5 мин
        "1M": 60,  # 1 мин
    }
    return timeouts.get(timeframe, 300)  # дефолт 5 мин


def _get_expected_closed_bar_ts(timeframe: str, now_utc: datetime) -> int:
    """Вычисляет timestamp последнего закрытого бара для таймфрейма.

    Args:
        timeframe: Таймфрейм (например, "1m", "5m", "1H")
        now_utc: Текущее время в UTC

    Returns:
        Timestamp последнего закрытого бара в миллисекундах
    """
    tf_seconds = _timeframe_to_seconds(timeframe)
    now_ts = int(now_utc.timestamp())
    # Округляем вниз до начала текущего периода, затем вычитаем один период
    current_period_start = (now_ts // tf_seconds) * tf_seconds
    expected_closed_bar_ts = current_period_start - tf_seconds
    return expected_closed_bar_ts * 1000  # конвертируем в миллисекунды


async def check_has_work_to_do(
    session: AsyncSession,
    timeframes: list[str],
    is_manual_run: bool = False,
    max_lag_fast: int = 240,
    max_lag_slow: int = 1200,
) -> bool:
    """Проверяет есть ли работа: сравнивает indicators vs ohlcv.

    Возвращает True если нужно выполнить DAG (есть работа),
    False если можно пропустить (данные свежие и синхронизированы).
    Выполняется ОДИН РАЗ на старт, не на каждый символ.

    Args:
        session: Асинхронная сессия БД
        timeframes: Список таймфреймов для проверки
        is_manual_run: Флаг ручного запуска (всегда True для выполнения)
        max_lag_fast: Максимальный lag для fast ТФ (1m, 5m) в секундах
        max_lag_slow: Максимальный lag для slow ТФ (15m+) в секундах

    Returns:
        True если нужно выполнить DAG, False если пропустить
    """
    if is_manual_run:
        return True  # Ручной запуск всегда выполняем

    now_utc = datetime.now(UTC)

    # Пропускаем DAG только если ВСЕ таймфреймы свежие и синхронизированы
    all_fresh = True

    for timeframe in timeframes:
        # Определяем порог lag в зависимости от таймфрейма
        is_fast = timeframe in ("1m", "5m")
        max_lag_seconds = max_lag_fast if is_fast else max_lag_slow

        # 1. Проверка свежести OHLCV
        expected_closed_bar_ts_ms = _get_expected_closed_bar_ts(timeframe, now_utc)

        res_ohlcv = await session.execute(
            text("SELECT MAX(timestamp) FROM swap_ohlcv_p WHERE timeframe = :tf"),
            {"tf": timeframe},
        )
        ohlcv_max_ts_ms = res_ohlcv.scalar()

        if not ohlcv_max_ts_ms:
            # Нет данных, нужно рассчитать
            print(f"[gate] {timeframe}: нет данных OHLCV, есть работа")
            return True  # Выполнять DAG

        # Вычисляем lag: разница между ожидаемым закрытым баром и фактическим
        ohlcv_lag_ms = expected_closed_bar_ts_ms - ohlcv_max_ts_ms
        ohlcv_lag_sec = ohlcv_lag_ms / 1000

        if ohlcv_lag_sec >= max_lag_seconds:
            print(
                f"[gate] {timeframe}: OHLCV отстают "
                f"(lag {ohlcv_lag_sec:.0f}s >= {max_lag_seconds}s), есть работа"
            )
            all_fresh = False
            continue

        # 2. Проверка feature lag (НОВОЕ)
        res_indicators = await session.execute(
            text(
                """
                SELECT MAX(timestamp)
                FROM indicators
                WHERE timeframe = :tf
            """
            ),
            {"tf": timeframe},
        )
        indicators_max_ts_ms = res_indicators.scalar()

        if not indicators_max_ts_ms:
            # Нет индикаторов, есть работа
            print(f"[gate] {timeframe}: нет данных indicators, есть работа")
            all_fresh = False
            continue

        # Вычисляем feature lag tolerance
        if is_fast:
            feature_lag_tolerance_seconds = 300
        else:
            # slow TF: tolerance = 1 * timeframe_seconds
            feature_lag_tolerance_seconds = _timeframe_to_seconds(timeframe)

        # Сравниваем: если indicators отстают от ohlcv больше чем на допуск — есть работа
        feature_lag_ms = ohlcv_max_ts_ms - indicators_max_ts_ms
        feature_lag_sec = feature_lag_ms / 1000

        if feature_lag_sec > feature_lag_tolerance_seconds:
            print(
                f"[gate] {timeframe}: feature lag {feature_lag_sec:.0f}s > "
                f"tolerance {feature_lag_tolerance_seconds}s, есть работа"
            )
            all_fresh = False
        else:
            print(
                f"[gate] {timeframe}: свежий и синхронизирован "
                f"(feature lag {feature_lag_sec:.0f}s <= {feature_lag_tolerance_seconds}s)"
            )

    # Пропускаем DAG только если ВСЕ таймфреймы свежие и синхронизированы
    if all_fresh:
        print("[gate] Все таймфреймы свежие и синхронизированы, пропускаем DAG")
        return False  # Пропустить DAG

    return True  # Выполнять DAG


async def get_last_calculated_ts(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
) -> int | None:
    """Получает последний рассчитанный timestamp для (symbol, timeframe).

    Возвращает timestamp в СЕКУНДАХ (как fetch_latest_ts).

    Args:
        session: Асинхронная сессия БД
        symbol: Символ инструмента
        timeframe: Таймфрейм

    Returns:
        Последний timestamp в секундах или None
    """
    return await fetch_latest_ts(session, symbol, timeframe)


async def check_has_new_ohlcv(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    last_feature_ts: int | None,  # в секундах
) -> tuple[bool, int | None]:
    """Проверяет есть ли новые OHLCV данные относительно watermark.

    ВАЖНО: swap_ohlcv_p.timestamp в МИЛЛИСЕКУНДАХ (int).

    Args:
        session: Асинхронная сессия БД
        symbol: Символ инструмента
        timeframe: Таймфрейм
        last_feature_ts: Последний timestamp фичи в секундах

    Returns:
        (has_new, latest_ohlcv_ts_seconds): есть ли новые данные и последний timestamp
    """
    res = await session.execute(
        text(
            f"""
            SELECT MAX({OHLCV_TIMESTAMP_COLUMN})
            FROM swap_ohlcv_p
            WHERE symbol = :symbol AND timeframe = :tf
        """
        ),
        {"symbol": symbol, "tf": timeframe},
    )
    latest_ohlcv_ts_ms = res.scalar()

    if not latest_ohlcv_ts_ms:
        return (False, None)

    # Конвертируем миллисекунды в секунды
    latest_ohlcv_ts_seconds = latest_ohlcv_ts_ms // 1000

    if last_feature_ts is None:
        # Первый расчёт - есть данные
        return (True, latest_ohlcv_ts_seconds)

    # Есть новые данные если latest OHLCV > last feature
    has_new = latest_ohlcv_ts_seconds > last_feature_ts
    return (has_new, latest_ohlcv_ts_seconds)


async def get_ohlcv_window(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    from_ts: int | None,  # в секундах (как fetch_latest_ts)
    warmup_bars: int = 500,
) -> pd.DataFrame:
    """Загружает OHLCV окно с warmup для расчёта индикаторов.

    from_ts в секундах (как fetch_latest_ts возвращает).
    Возвращает DataFrame с колонкой 'timestamp' в МИЛЛИСЕКУНДАХ (для compute_features).

    Лимит зависит от таймфрейма: для старших ТФ меньше баров.

    Args:
        session: Асинхронная сессия БД
        symbol: Символ инструмента
        timeframe: Таймфрейм
        from_ts: Timestamp начала окна в секундах (None = последние N баров)
        warmup_bars: Количество баров для warmup

    Returns:
        DataFrame с колонками timestamp (ms), open, high, low, close, volume
    """
    # Если from_ts есть, вычитаем warmup
    if from_ts:
        timeframe_seconds = _timeframe_to_seconds(timeframe)
        warmup_ts = from_ts - (warmup_bars * timeframe_seconds)
    else:
        # Первый расчёт: берём последние N баров (limit)
        warmup_ts = None

    # Лимит зависит от таймфрейма
    limit = _get_limit_for_timeframe(timeframe)

    # Используем существующую функцию
    df = await fetch_ohlcv_df(
        session,
        symbol=symbol,
        timeframe=timeframe,
        since_ts=warmup_ts,  # в секундах
        limit=limit,
    )

    if df is None or len(df) == 0:
        return pd.DataFrame()

    # fetch_ohlcv_df возвращает 'ts' в секундах
    # compute_features ожидает 'timestamp' в миллисекундах
    # Создаём timestamp_ms, НЕ переименовываем ts (чтобы не было конфликта)
    df = df.copy()
    df["timestamp"] = df["ts"] * 1000  # конвертация в миллисекунды

    # Возвращаем только нужные колонки для compute_features
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


async def save_features_batch(
    session: AsyncSession,
    df_features: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> int:
    """Сохраняет рассчитанные фичи в БД батчами.

    Использует существующую функцию insert_indicators, которая делает UPSERT.
    Принимает session как параметр (не создаёт новую, НЕ коммитит).

    ВАЖНО: Коммит делается в process_symbol_features после всех таймфреймов.

    Args:
        session: Асинхронная сессия БД
        df_features: DataFrame с рассчитанными фичами
        symbol: Символ инструмента
        timeframe: Таймфрейм

    Returns:
        Количество сохранённых строк
    """
    # Подготовка данных: добавляем symbol и timeframe
    df_features = df_features.copy()
    df_features["symbol"] = symbol
    df_features["timeframe"] = timeframe

    # Убеждаемся, что timestamp в миллисекундах (как ожидает insert_indicators)
    if "timestamp" not in df_features.columns:
        if "ts" in df_features.columns:
            df_features["timestamp"] = df_features["ts"] * 1000
        else:
            raise ValueError("DataFrame must have 'timestamp' or 'ts' column")

    # Сохранение (insert_indicators сам обрабатывает батчи внутри)
    # ВАЖНО: insert_indicators НЕ коммитит сам, коммит делаем вручную ПОСЛЕ всех таймфреймов
    rows_saved = await insert_indicators(
        session=session,
        ind_df=df_features,
        symbol=symbol,
        timeframe=timeframe,
    )

    return rows_saved


async def process_symbol_features(
    session: AsyncSession,
    symbol: str,
    timeframes: list[str],
    specs: list[str],
) -> dict[str, Any]:
    """Обрабатывает один символ для всех таймфреймов.

    Принимает session как параметр (не создаёт новую).
    Таймаут определяется автоматически по таймфрейму.

    Args:
        session: Асинхронная сессия БД
        symbol: Символ инструмента
        timeframes: Список таймфреймов
        specs: Список спецификаций индикаторов

    Returns:
        Словарь с результатами обработки
    """
    symbol_start = time.time()
    results: dict[str, Any] = {}
    errors: list[str] = []

    for timeframe in timeframes:
        tf_start = time.time()
        timeout = _get_timeout_for_timeframe(timeframe)
        try:
            # Получение watermark (в секундах)
            last_feature_ts = await get_last_calculated_ts(session, symbol, timeframe)

            # Быстрая проверка: есть ли новые OHLCV данные?
            has_new, latest_ohlcv_ts = await check_has_new_ohlcv(
                session, symbol, timeframe, last_feature_ts
            )

            if not has_new:
                tf_duration = time.time() - tf_start
                print(f"[{symbol}/{timeframe}] Пропуск: нет новых OHLCV данных")
                results[timeframe] = {
                    "status": "skipped",
                    "reason": "no_new_ohlcv",
                    "compute_time_seconds": round(tf_duration, 2),
                }
                continue

            # Загрузка OHLCV окна (с warmup)
            df_ohlcv = await get_ohlcv_window(
                session, symbol, timeframe, last_feature_ts, warmup_bars=500
            )

            if len(df_ohlcv) == 0:
                tf_duration = time.time() - tf_start
                print(f"[{symbol}/{timeframe}] Нет данных после загрузки")
                results[timeframe] = {
                    "status": "skipped",
                    "reason": "no_data",
                    "compute_time_seconds": round(tf_duration, 2),
                }
                continue

            # Расчёт индикаторов (синхронная функция, но в async контексте)
            # Таймаут определяется по таймфрейму
            df_features = await asyncio.wait_for(
                asyncio.to_thread(
                    compute_features,
                    df_ohlcv,
                    specs=specs,
                    volatility_normalize=False,  # features_calc_short не нужна нормализация
                    debug=False,
                ),
                timeout=timeout,
            )

            # Сохранение в БД (батчевый upsert, БЕЗ коммита)
            rows_saved = await save_features_batch(
                session, df_features, symbol, timeframe
            )

            tf_duration = time.time() - tf_start

            results[timeframe] = {
                "rows_processed": len(df_ohlcv),
                "rows_saved": rows_saved,
                "status": "ok",
                "bars_loaded": len(df_ohlcv),  # ОБЯЗАТЕЛЬНО
                "compute_time_seconds": round(tf_duration, 2),  # ОБЯЗАТЕЛЬНО
            }

        except TimeoutError:
            tf_duration = time.time() - tf_start
            error_msg = f"{symbol}/{timeframe}: timeout ({timeout}s)"
            errors.append(error_msg)
            print(f"⏱️ {error_msg}")
            results[timeframe] = {
                "status": "error",
                "error": "timeout",
                "compute_time_seconds": round(tf_duration, 2),  # ОБЯЗАТЕЛЬНО
            }
        except Exception as e:
            tf_duration = time.time() - tf_start
            error_msg = f"{symbol}/{timeframe}: {e!s}"
            errors.append(error_msg)
            print(f"❌ {error_msg}")
            results[timeframe] = {
                "status": "error",
                "error": str(e),
                "compute_time_seconds": round(tf_duration, 2),  # ОБЯЗАТЕЛЬНО
            }

    # Коммит ОДИН РАЗ на символ после всех таймфреймов
    # ТОЛЬКО если нет ошибок (атомарность символа)
    has_saved_data = any(
        isinstance(r, dict)
        and isinstance(r.get("rows_saved"), int)
        and r.get("rows_saved", 0) > 0
        for r in results.values()
    )

    if has_saved_data and len(errors) == 0:
        await session.commit()
        print(f"[{symbol}] Коммит после обработки всех таймфреймов")
    elif errors:
        await session.rollback()
        print(f"[{symbol}] Rollback из-за ошибок ({len(errors)}): {errors}")
    else:
        print(f"[{symbol}] Нет данных для коммита (все ТФ пропущены)")

    symbol_duration = time.time() - symbol_start

    return {
        "symbol": symbol,
        "results": results,
        "errors": errors,
        "success": len(errors) == 0,
        "total_duration_seconds": round(symbol_duration, 2),
        "timeframes_processed": len(
            [
                r
                for r in results.values()
                if isinstance(r, dict) and r.get("status") == "ok"
            ]
        ),
        "timeframes_failed": len(
            [
                r
                for r in results.values()
                if isinstance(r, dict) and r.get("status") == "error"
            ]
        ),
    }


async def process_all_symbols(
    engine: AsyncEngine,  # ОДИН engine/pool на весь ран
    symbols: list[str] | None,
    timeframes: list[str],
    specs: list[str],
    max_concurrent_symbols: int = 3,  # Уменьшено: compute_features CPU-bound
) -> dict[str, Any]:
    """Обрабатывает все символы с ограничением параллелизма.

    ВАЖНО: AsyncSession не потокобезопасна!
    Используем ОДИН engine/pool, но ОТДЕЛЬНУЮ сессию на каждый символ.

    Args:
        engine: Асинхронный engine БД (один на весь ран)
        symbols: Список символов (None = все)
        timeframes: Список таймфреймов
        specs: Список спецификаций индикаторов
        max_concurrent_symbols: Максимальное количество параллельных символов

    Returns:
        Словарь со статистикой обработки
    """
    # Получение списка символов (нужна временная сессия)
    async with AsyncSession(engine) as temp_session:
        if not symbols:
            res = await temp_session.execute(
                text("SELECT DISTINCT symbol FROM swap_ohlcv_p ORDER BY symbol")
            )
            symbols = [row[0] for row in res.fetchall()]

    # Семафор для ограничения параллелизма
    # compute_features CPU-bound, поэтому ограничиваем до 2-4
    semaphore = asyncio.Semaphore(max_concurrent_symbols)

    async def process_with_semaphore(symbol: str):
        """Обрабатывает один символ в отдельной сессии."""
        async with semaphore:
            # Каждый символ получает свою сессию из общего пула
            async with AsyncSession(engine) as symbol_session:
                return await process_symbol_features(
                    symbol_session, symbol, timeframes, specs
                )

    # Параллельная обработка
    tasks = [process_with_semaphore(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Агрегация статистики
    total_symbols = len(symbols)
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    failed = total_symbols - successful

    return {
        "total_symbols": total_symbols,
        "successful": successful,
        "failed": failed,
        "results": results,
    }


def features_calc_short_run_task(**context):
    """Основная задача расчёта features_calc_short features."""
    # Настройка окружения
    env = get_dag_env()
    setup_env(env)

    # Получение конфигурации
    dag_run = context.get("dag_run")
    conf = (dag_run.conf or {}) if dag_run else {}

    # Параметры
    symbols = conf.get("symbols")  # None = все
    timeframes = conf.get("timeframes", ["1m", "5m", "15m", "30m", "1H", "4H", "1D"])
    max_concurrent_symbols = conf.get(
        "max_concurrent_symbols", 3
    )  # Уменьшено для CPU-bound

    # Проверка ручного запуска
    is_manual_run = dag_run and dag_run.run_type == "manual"

    loop = get_or_create_event_loop()
    start_time = time.time()

    async def _run_async():
        """Внутренняя async функция с ОДНИМ engine/pool на весь ран."""
        # Получаем engine из существующей функции или создаём свой
        # Используем DATABASE_URL из окружения
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL не установлен")

        # Создаём engine один раз на весь ран
        engine = create_async_engine(database_url, pool_pre_ping=True)

        try:
            # ГЛОБАЛЬНЫЙ freshness gate (один раз на старт DAG)
            # Нужна временная сессия для проверки
            async with get_db_session() as temp_session:
                if not is_manual_run:
                    has_work = await check_has_work_to_do(
                        temp_session,
                        timeframes,
                        is_manual_run=is_manual_run,
                        max_lag_fast=240,
                        max_lag_slow=1200,
                    )
                    if not has_work:
                        print(
                            "[features_calc_short] Пропуск: все таймфреймы свежие "
                            "и синхронизированы"
                        )
                        return {
                            "skipped": True,
                            "reason": "ohlcv_fresh_and_synced",
                            "message": (
                                "Все таймфреймы свежие и синхронизированы, "
                                "расчёт не требуется"
                            ),
                        }

            # Запуск расчёта (передаём engine, не session)
            stats = await process_all_symbols(
                engine=engine,
                symbols=symbols,
                timeframes=timeframes,
                specs=FEATURES_CALC_SHORT_SPECS,
                max_concurrent_symbols=max_concurrent_symbols,
            )

            # Агрегация статистики
            rows_saved_total = sum(
                r.get("results", {}).get(tf, {}).get("rows_saved", 0)
                for r in stats["results"]
                if isinstance(r, dict)
                for tf in timeframes
            )

            # Агрегация метрик времени
            total_compute_time = sum(
                r.get("total_duration_seconds", 0)
                for r in stats["results"]
                if isinstance(r, dict)
            )

            avg_compute_time = (
                total_compute_time / stats["total_symbols"]
                if stats["total_symbols"] > 0
                else 0
            )

            symbols_with_work = sum(
                1
                for r in stats["results"]
                if isinstance(r, dict) and r.get("timeframes_processed", 0) > 0
            )

            return {
                "total_symbols": stats["total_symbols"],
                "successful": stats["successful"],
                "failed": stats["failed"],
                "rows_saved_total": rows_saved_total,
                "symbols_with_work": symbols_with_work,
                "total_compute_time_seconds": round(total_compute_time, 2),
                "avg_compute_time_per_symbol_seconds": round(avg_compute_time, 2),
            }
        finally:
            # Закрываем engine в конце
            await engine.dispose()

    # Запуск async функции
    result = loop.run_until_complete(_run_async())

    # Добавляем duration (если result - словарь)
    if isinstance(result, dict):
        duration = time.time() - start_time
        result["duration_seconds"] = round(duration, 2)

    return result


def features_calc_short_validate_task(**context):
    """Проверка наличия записей после расчёта."""
    env = get_dag_env()
    setup_env(env)

    loop = get_or_create_event_loop()

    async def validate():
        async with get_db_session() as session:
            # Проверка для fast ТФ (1m, 5m)
            for tf in ["1m", "5m"]:
                res = await session.execute(
                    text(
                        """
                        SELECT MAX(timestamp)
                        FROM indicators
                        WHERE timeframe = :tf
                    """
                    ),
                    {"tf": tf},
                )
                max_ts = res.scalar()
                if max_ts:
                    lag_sec = (
                        datetime.now(UTC).timestamp() * 1000 - max_ts
                    ) / 1000
                    print(f"Lag for {tf}: {lag_sec:.0f}s")

    loop.run_until_complete(validate())


default_args = {
    "owner": "features_calc_short",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

dag = DAG(
    dag_id="features_calc_short",
    start_date=datetime(2025, 1, 1),
    schedule="*/15 * * * *",  # Каждые 15 минут
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
)

features_calc_short_run = PythonOperator(
    task_id="features_calc_short_run",
    python_callable=features_calc_short_run_task,
    dag=dag,
)

features_calc_short_validate = PythonOperator(
    task_id="features_calc_short_validate",
    python_callable=features_calc_short_validate_task,
    dag=dag,
)

features_calc_short_run >> features_calc_short_validate
