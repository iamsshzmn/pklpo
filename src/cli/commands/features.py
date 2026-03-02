"""
Features CLI command for pipeline integration.

This module provides the CLI interface for the features stage of the pipeline,
integrating with the features module to calculate technical indicators.
"""

import asyncio
import hashlib
import json
import os
import time
import uuid
from datetime import datetime

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

from src.features import compute_features
from src.features.infrastructure.database import (
    insert_indicators as infra_insert_indicators,
)
from src.features.observability.logging import get_features_logger, log_features_summary
from src.features.specs import FEATURE_SPECS
from src.utils.session_utils import get_db_session

logger = get_features_logger()


def register(subparsers):
    """Register features command with CLI parser."""
    p = subparsers.add_parser("features", help="Расчёт технических индикаторов")
    p.add_argument("--symbols", nargs="+", help="Символы для обработки")
    p.add_argument(
        "--timeframes",
        nargs="+",
        default=["1m", "5m", "15m", "1H", "4H", "1D"],
        help="Таймфреймы для обработки",
    )
    p.add_argument(
        "--specs",
        nargs="+",
        default=None,
        help="Список индикаторов для расчёта (None = все доступные)",
    )
    p.add_argument(
        "--normalize", action="store_true", help="Включить волатильностную нормировку"
    )
    p.add_argument(
        "--normalize-window", type=int, default=20, help="Окно для нормировки"
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Количество баров для обработки (None = все данные)",
    )
    p.add_argument(
        "--refill-incomplete",
        action="store_true",
        help="Пересчитать только строки с data_status='inc'",
    )
    p.add_argument(
        "--refill-null",
        nargs="+",
        default=None,
        help="Пересчитать записи с NULL для указанных индикаторов (например: --refill-null willr ultosc)",
    )
    p.add_argument(
        "--features-debug",
        action="store_true",
        help="Подробные DEBUG-логи расчёта индикаторов",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Включить режим отладки с подробными логами (alias для --features-debug)",
    )
    p.add_argument(
        "--backend",
        choices=["auto", "pandas_ta", "talib", "fallback"],
        default="auto",
        help="Бэкенд для расчёта индикаторов (auto=pandas_ta->talib->fallback)",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Показать план без выполнения"
    )
    p.add_argument(
        "--repair",
        action="store_true",
        help="Режим восстановления: загрузить последние 24 часа вместо инкрементного режима",
    )
    p.add_argument(
        "--parallel-workers",
        type=int,
        default=1,
        help="Количество параллельных воркеров (1 = последовательно, 2-6 рекомендуется)",
    )
    p.add_argument(
        "--order",
        choices=["symbol-first", "timeframe-first"],
        default="symbol-first",
        help="Порядок обработки: symbol-first (по символам) или timeframe-first (по таймфреймам)",
    )
    p.set_defaults(_handler=handle)


async def handle(args):
    """Handle features command execution."""
    # Устанавливаем бэкенд для расчёта индикаторов
    import os

    backend = getattr(args, "backend", "auto")
    os.environ["FEATURES_TA_BACKEND"] = backend
    logger.info(f"🚀 ЗАПУСК ЭТАПА FEATURES (backend: {backend})")

    # Включаем подробные логи по флагу --features-debug или --debug
    debug_mode = getattr(args, "features_debug", False) or getattr(args, "debug", False)
    if debug_mode:
        os.environ["FEATURES_VERBOSE"] = "true"
        os.environ["FEATURES_DEBUG"] = "true"
        # Note: Level is controlled by FEATURES_DEBUG env var in logging_config
        logger.info("🔧 DEBUG MODE ENABLED: Detailed logging activated")
        logger.info("Debug logging test: Verbose mode is active")

    if args.dry_run:
        await _show_plan(args)
        return

    start_time = datetime.now()
    start_time_ts = time.time()  # Для расчёта ETA
    logger.info(f"⏰ Начало: {start_time.strftime('%H:%M:%S')}")

    try:
        # Получаем список символов для обработки
        symbols = await _get_symbols_to_process(args.symbols)
        if not symbols:
            logger.warning("⚠️ Нет символов для обработки")
            return

        # Определяем спецификации индикаторов
        feature_specs = _get_feature_specs(args.specs)

        # Обрабатываем каждый символ и таймфрейм с прогресс-баром
        total_processed = 0
        total_features = 0
        stats = []
        total_saved = 0

        # Подсчитываем общее количество задач
        total_tasks = len(symbols) * len(args.timeframes)

        logger.info(
            f"📊 План работы: {len(symbols)} символов × {len(args.timeframes)} таймфреймов = {total_tasks} задач"
        )
        if len(symbols) > 0:
            logger.info(
                f"📈 Символы: {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}"
            )
        logger.info(f"⏰ Таймфреймы: {', '.join(args.timeframes)}")
        logger.info(f"🎯 Индикаторов для расчёта: {len(feature_specs)}")

        # Параллелизм
        parallel_workers = getattr(args, "parallel_workers", 1)
        # Ограничиваем количество воркеров (DB pool_size=5, max_overflow=10)
        parallel_workers = min(max(1, parallel_workers), 6)
        logger.info(
            f"🚀 Начинаем обработку (воркеров: {parallel_workers})..."
        )

        if parallel_workers > 1:
            # Параллельная обработка с Semaphore
            stats, total_processed, total_features, total_saved = await _process_parallel(
                symbols=symbols,
                timeframes=args.timeframes,
                feature_specs=feature_specs,
                args=args,
                parallel_workers=parallel_workers,
                total_tasks=total_tasks,
                start_time_ts=start_time_ts,
            )
        else:
            # Последовательная обработка (legacy)
            stats, total_processed, total_features, total_saved = await _process_sequential(
                symbols=symbols,
                timeframes=args.timeframes,
                feature_specs=feature_specs,
                args=args,
                total_tasks=total_tasks,
                start_time_ts=start_time_ts,
            )

        # Итоговая статистика
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("\n📊 ИТОГИ ЭТАПА FEATURES:")
        logger.info(f"⏰ Время выполнения: {duration:.1f} сек")
        logger.info(f"📈 Обработано символов: {len(symbols)}")
        logger.info(f"📊 Обработано баров: {total_processed:,}")
        logger.info(f"🎯 Рассчитано индикаторов: {total_features:,}")
        logger.info(f"💾 Сохранено записей: {total_saved:,}")
        logger.info(f"⚡ Скорость: {total_processed/duration:.1f} баров/сек")

        if total_processed > 0:
            logger.info(
                f"📈 Среднее индикаторов на бар: {total_features/total_processed:.1f}"
            )

        # Сводка по каждому символу и таймфрейму
        if stats:
            # Группируем по символам для использования log_features_summary
            summary_by_symbol: dict[str, dict[str, dict[str, int]]] = {}
            for entry in stats:
                symbol = entry["symbol"]
                tf = entry["timeframe"]
                if symbol not in summary_by_symbol:
                    summary_by_symbol[symbol] = {}
                summary_by_symbol[symbol][tf] = {
                    "bars": entry["bars_in"],
                    "features": entry["features_out"],
                    "saved": entry["saved"],
                }

            # Добавляем нулевые записи для таймфреймов без данных
            for symbol in symbols:
                if symbol not in summary_by_symbol:
                    summary_by_symbol[symbol] = {}
                for tf in args.timeframes:
                    if tf not in summary_by_symbol[symbol]:
                        summary_by_symbol[symbol][tf] = {
                            "bars": 0,
                            "features": 0,
                            "saved": 0,
                        }

            # Выводим сводку для каждого символа
            for symbol, summary in summary_by_symbol.items():
                log_features_summary(logger, summary, symbol=symbol)

        # Реальная статистика уже показана в _log_feature_groups_progress

        logger.info("✅ ЭТАП FEATURES ЗАВЕРШЕН УСПЕШНО")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в этапе features: {e}")
        raise


# Приоритетный порядок таймфреймов (младшие первыми)
PRIORITY_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1H", "2H", "4H", "6H", "8H", "12H", "1D", "3D", "1W"]


def _generate_task_pairs(
    symbols: list[str],
    timeframes: list[str],
    order: str,
) -> list[tuple[str, str]]:
    """
    Генерирует список пар (symbol, timeframe) в нужном порядке.

    Args:
        symbols: Список символов
        timeframes: Список таймфреймов
        order: "symbol-first" или "timeframe-first"

    Returns:
        Список пар (symbol, timeframe)
    """
    if order == "timeframe-first":
        # Сортируем таймфреймы по приоритету
        sorted_tfs = sorted(
            timeframes,
            key=lambda tf: PRIORITY_TIMEFRAMES.index(tf) if tf in PRIORITY_TIMEFRAMES else 999
        )
        return [(s, tf) for tf in sorted_tfs for s in symbols]
    # symbol-first (по умолчанию)
    return [(s, tf) for s in symbols for tf in timeframes]


async def _process_sequential(
    symbols: list[str],
    timeframes: list[str],
    feature_specs: list,
    args,
    total_tasks: int,
    start_time_ts: float,
) -> tuple[list[dict], int, int, int]:
    """Последовательная обработка (legacy режим)."""
    stats = []
    total_processed = 0
    total_features = 0
    total_saved = 0
    tasks_completed = 0
    last_heartbeat_time = time.time()
    heartbeat_interval = 30

    # Генерируем пары в нужном порядке
    order = getattr(args, "order", "symbol-first")
    task_pairs = _generate_task_pairs(symbols, timeframes, order)
    logger.debug(f"Порядок обработки: {order}")

    with tqdm(
        total=total_tasks,
        desc="🎯 Обработка features",
        unit="задача",
        ncols=100,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        disable=os.getenv("TQDM_DISABLE") == "1",
    ) as pbar:
        for symbol, timeframe in task_pairs:
            try:
                pbar.set_description(f"🎯 {symbol} {timeframe}")

                tf_result = await _process_symbol_timeframe(
                    symbol, timeframe, feature_specs, args
                )
                stats.append(tf_result)
                total_processed += tf_result["bars_in"]
                total_features += tf_result["features_out"]
                total_saved += tf_result["saved"]
                tasks_completed += 1

                pbar.set_postfix(
                    {
                        "баров": tf_result["bars_in"],
                        "индикаторов": tf_result["features_out"],
                        "всего баров": total_processed,
                    }
                )

                # Heartbeat
                current_time = time.time()
                if current_time - last_heartbeat_time >= heartbeat_interval:
                    elapsed = current_time - start_time_ts
                    progress_pct = (tasks_completed / total_tasks * 100) if total_tasks > 0 else 0
                    rate = tasks_completed / elapsed if elapsed > 0 else 0
                    remaining_tasks = total_tasks - tasks_completed
                    eta_seconds = remaining_tasks / rate if rate > 0 else 0

                    logger.info(
                        f"💓 ПРОГРЕСС: {tasks_completed}/{total_tasks} задач "
                        f"({progress_pct:.1f}%) | "
                        f"Баров: {total_processed:,} | "
                        f"Индикаторов: {total_features:,} | "
                        f"Сохранено: {total_saved:,} | "
                        f"Скорость: {rate:.2f} задач/сек | "
                        f"Осталось: ~{eta_seconds/60:.1f} мин"
                    )
                    last_heartbeat_time = current_time

            except Exception as e:
                import traceback
                logger.error(f"❌ Ошибка при обработке {symbol} {timeframe}: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                pbar.set_postfix({"ошибка": "да"})
            finally:
                pbar.update(1)

    return stats, total_processed, total_features, total_saved


async def _process_parallel(
    symbols: list[str],
    timeframes: list[str],
    feature_specs: list,
    args,
    parallel_workers: int,
    total_tasks: int,
    start_time_ts: float,
) -> tuple[list[dict], int, int, int]:
    """Параллельная обработка с Semaphore."""
    import traceback

    stats = []
    total_processed = 0
    total_features = 0
    total_saved = 0
    errors_count = 0

    # Semaphore для ограничения параллельных задач
    semaphore = asyncio.Semaphore(parallel_workers)

    async def process_with_limit(symbol: str, tf: str) -> dict:
        """Обработка одной пары с ограничением через Semaphore."""
        async with semaphore:
            try:
                return await _process_symbol_timeframe(symbol, tf, feature_specs, args)
            except Exception as e:
                logger.error(f"❌ Ошибка {symbol} {tf}: {e}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                return {
                    "symbol": symbol,
                    "timeframe": tf,
                    "bars_in": 0,
                    "features_out": 0,
                    "saved": 0,
                    "error": str(e),
                }

    # Генерируем пары в нужном порядке
    order = getattr(args, "order", "symbol-first")
    task_pairs = _generate_task_pairs(symbols, timeframes, order)
    logger.debug(f"Порядок обработки: {order}")

    # Создаём все задачи
    tasks = [process_with_limit(s, tf) for s, tf in task_pairs]

    logger.info(f"🔄 Запуск {len(tasks)} задач с параллелизмом {parallel_workers}")

    # Прогресс-бар для параллельной обработки
    with tqdm(
        total=total_tasks,
        desc=f"🎯 Обработка features (×{parallel_workers})",
        unit="задача",
        ncols=100,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        disable=os.getenv("TQDM_DISABLE") == "1",
    ) as pbar:
        # Используем as_completed для обновления прогресса по мере завершения
        for coro in asyncio.as_completed(tasks):
            result = await coro

            if "error" not in result:
                stats.append(result)
                total_processed += result["bars_in"]
                total_features += result["features_out"]
                total_saved += result["saved"]
            else:
                errors_count += 1

            pbar.update(1)
            pbar.set_postfix(
                {
                    "баров": total_processed,
                    "ошибок": errors_count,
                }
            )

    if errors_count > 0:
        logger.warning(f"⚠️ Завершено с {errors_count} ошибками")

    return stats, total_processed, total_features, total_saved


async def _show_plan(args):
    """Показать план выполнения без выполнения."""
    symbols = await _get_symbols_to_process(args.symbols)
    feature_specs = _get_feature_specs(args.specs)

    logger.info("🔍 ПЛАН ЭТАПА FEATURES (dry-run):")
    logger.info(f"📈 Символы: {len(symbols)}")
    logger.info(f"⏰ Таймфреймы: {args.timeframes}")
    logger.info(f"🎯 Индикаторы: {len(feature_specs)}")
    logger.info(f"📊 Лимит баров: {args.limit}")
    logger.info(f"🔧 Нормировка: {'Включена' if args.normalize else 'Отключена'}")

    if symbols:
        logger.info(
            f"📋 Символы: {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}"
        )
    if feature_specs:
        spec_names = [spec.name for spec in feature_specs[:5]]
        logger.info(
            f"🎯 Индикаторы: {', '.join(spec_names)}{'...' if len(feature_specs) > 5 else ''}"
        )


async def _get_symbols_to_process(requested_symbols: list[str] | None) -> list[str]:
    """Получить список символов для обработки."""
    logger.debug(
        f"🔍 _get_symbols_to_process вызвана с: {requested_symbols} (тип: {type(requested_symbols)})"
    )

    # Фильтруем None, "None", "null", пустые строки
    if requested_symbols:
        logger.debug(f"🔍 Фильтрация {len(requested_symbols)} символов...")
        filtered = [
            s
            for s in requested_symbols
            if s and s.strip().lower() not in ("none", "null", "")
        ]
        logger.debug(f"🔍 После фильтрации осталось {len(filtered)} символов")
        if filtered:
            logger.info(f"📈 Используются указанные символы: {filtered}")
            return filtered
        # Если все символы были отфильтрованы, обрабатываем все
        logger.info(
            "📈 Все указанные символы были None/null/пустые, обрабатываем все символы из БД"
        )
    else:
        logger.debug("🔍 requested_symbols пустой или None, обрабатываем все символы")

    # Получаем все символы из базы данных (таблица swap_ohlcv_p)
    logger.debug("🔍 Запрос всех символов из swap_ohlcv_p...")
    async with get_db_session() as session:
        query = text(
            """
            SELECT DISTINCT symbol
            FROM swap_ohlcv_p
            WHERE symbol LIKE '%-USDT-SWAP'
            ORDER BY symbol
        """
        )
        result = await session.execute(query)
        symbols = [row[0] for row in result.fetchall()]

        logger.info(f"📈 Найдено {len(symbols)} символов в таблице swap_ohlcv_p")
        if symbols:
            logger.debug(f"📈 Примеры символов: {symbols[:5]}...")
        return symbols


def _get_feature_specs(requested_specs: list[str] | None) -> list:
    """Получить спецификации индикаторов для расчёта."""
    if requested_specs:
        # Фильтруем только запрошенные индикаторы
        specs = []
        for spec_name in requested_specs:
            if spec_name in FEATURE_SPECS:
                specs.append(FEATURE_SPECS[spec_name])
            else:
                logger.warning(f"⚠️ Неизвестный индикатор: {spec_name}")
        return specs

    # Возвращаем все доступные индикаторы
    return list(FEATURE_SPECS.values())


async def _refill_null_indicators(
    symbol: str, timeframe: str, null_indicators: list[str]
) -> None:
    """Пересчитать записи с NULL для указанных индикаторов."""
    logger.info(
        f"🔄 Пересчёт NULL значений для {symbol} {timeframe}: {null_indicators}"
    )

    # Валидация имён индикаторов (защита от SQL injection)
    from src.models import Indicator

    valid_columns = {col.name for col in Indicator.__table__.columns}
    invalid_inds = [ind for ind in null_indicators if ind not in valid_columns]
    if invalid_inds:
        logger.error(f"❌ Некорректные индикаторы (не в схеме): {invalid_inds}")
        return

    async with get_db_session() as session:
        # Находим записи с NULL для указанных индикаторов
        # Используем параметризованный запрос с безопасной конкатенацией условий
        conditions_parts = []
        for ind in null_indicators:
            if ind in valid_columns:
                conditions_parts.append(f"i.{ind} IS NULL")

        if not conditions_parts:
            logger.warning("⚠️ Нет валидных условий для поиска NULL")
            return

        null_conditions = " OR ".join(conditions_parts)
        query = text(
            f"""
            SELECT DISTINCT i.timestamp
            FROM indicators i
            INNER JOIN swap_ohlcv_p o ON
                i.symbol = o.symbol AND
                i.timeframe = o.timeframe AND
                i.timestamp = o.timestamp
            WHERE i.symbol = :symbol
                AND i.timeframe = :timeframe
                AND ({null_conditions})
            ORDER BY i.timestamp
        """
        )
        result = await session.execute(
            query, {"symbol": symbol, "timeframe": timeframe}
        )
        null_timestamps = [row[0] for row in result.fetchall()]

        if not null_timestamps:
            logger.info(f"✅ Нет записей с NULL для {null_indicators}")
            return

        logger.info(f"📊 Найдено {len(null_timestamps)} записей с NULL")

        # Получаем OHLCV данные для этих timestamp'ов с окном для расчёта индикаторов
        max_window = 100  # Максимальное окно для индикаторов
        min_ts = min(null_timestamps) - max_window * 60 * 1000  # Миллисекунды
        max_ts = max(null_timestamps) + 60 * 1000

        ohlcv_query = text(
            """
            SELECT
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                timestamp / 1000 as ts
            FROM swap_ohlcv_p
            WHERE symbol = :symbol
                AND timeframe = :timeframe
                AND timestamp >= :min_ts
                AND timestamp <= :max_ts
            ORDER BY timestamp
        """
        )
        ohlcv_result = await session.execute(
            ohlcv_query,
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "min_ts": min_ts,
                "max_ts": max_ts,
            },
        )
        ohlcv_rows = ohlcv_result.fetchall()

        if not ohlcv_rows:
            logger.warning("⚠️ Нет OHLCV данных для пересчёта")
            return

        # Преобразуем в DataFrame
        df_ohlcv = pd.DataFrame(
            ohlcv_rows,
            columns=["timestamp", "open", "high", "low", "close", "volume", "ts"],
        )
        df_ohlcv["ts"] = df_ohlcv["timestamp"] / 1000

        logger.info(f"📊 Загружено {len(df_ohlcv)} OHLCV записей")

        # Рассчитываем только указанные индикаторы
        from src.features.specs import FEATURE_SPECS

        refill_specs = [
            FEATURE_SPECS[ind] for ind in null_indicators if ind in FEATURE_SPECS
        ]

        if not refill_specs:
            logger.warning(f"⚠️ Некорректные индикаторы: {null_indicators}")
            return

        from src.features import compute_features

        features_df = compute_features(
            df_ohlcv, specs=refill_specs, volatility_normalize=False
        )

        # Обновляем только записи с NULL
        updated_count = 0
        for ind in null_indicators:
            if ind not in valid_columns:
                continue
            if ind not in features_df.columns:
                logger.warning(f"⚠️ Индикатор {ind} не рассчитан")
                continue

            # Формируем UPDATE для записей с NULL (используем безопасный способ)
            # Создаём словарь для batch update
            updates_dict = {}
            for ts in null_timestamps:
                # Находим индекс в features_df через совпадение timestamp
                matching_rows = df_ohlcv[df_ohlcv["timestamp"] == ts]
                if len(matching_rows) == 0:
                    continue

                df_idx = matching_rows.index[0]
                if df_idx >= len(features_df):
                    continue

                value = features_df.iloc[df_idx][ind]
                if pd.isna(value):
                    continue

                updates_dict[ts] = float(value)

            # Batch update через execute_values или по одному
            if updates_dict:
                for ts, val in updates_dict.items():
                    # Используем безопасное имя колонки (уже валидировано)
                    update_query = text(
                        f"""
                        UPDATE indicators
                        SET {ind} = :value
                        WHERE symbol = :symbol
                            AND timeframe = :timeframe
                            AND timestamp = :timestamp
                            AND {ind} IS NULL
                    """
                    )
                    await session.execute(
                        update_query,
                        {
                            "value": val,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "timestamp": ts,
                        },
                    )
                    updated_count += 1

        await session.commit()
        logger.info(f"✅ Обновлено {updated_count} записей")


async def _process_symbol_timeframe(
    symbol: str, timeframe: str, feature_specs: list, args
) -> dict:
    """Обработать один символ и таймфрейм."""
    logger.info(f"🔄 Обработка {symbol} {timeframe}")

    # Обработка --refill-null: пересчёт записей с NULL для указанных индикаторов
    if args.refill_null:
        await _refill_null_indicators(symbol, timeframe, args.refill_null)
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "bars_in": 0,
            "features_out": 0,
            "saved": 0,
        }

    # Получаем OHLCV данные
    repair_mode = getattr(args, "repair", False)
    logger.debug(f"Запрос данных для {symbol} {timeframe} (repair={repair_mode})")
    df_ohlcv = await _get_ohlcv_data(symbol, timeframe, args.limit, repair_mode=repair_mode)
    if df_ohlcv is None:
        logger.warning(f"⚠️ _get_ohlcv_data вернул None для {symbol} {timeframe}")
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "bars_in": 0,
            "features_out": 0,
            "saved": 0,
        }
    if len(df_ohlcv) == 0:
        logger.warning(f"⚠️ DataFrame пустой для {symbol} {timeframe}")
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "bars_in": 0,
            "features_out": 0,
            "saved": 0,
        }
    logger.info(f"✅ Получено {len(df_ohlcv)} баров для {symbol} {timeframe}")

    # Диагностика входных данных: проверим заполненность OHLCV перед расчётом
    try:
        ohlcv_cols = [
            c
            for c in ["open", "high", "low", "close", "volume", "timestamp", "ts"]
            if c in df_ohlcv.columns
        ]
        non_nulls = df_ohlcv[ohlcv_cols].notna().sum().to_dict()
        logger.info(f"🔍 OHLCV non-null before compute: {non_nulls}")
        head_preview = df_ohlcv[ohlcv_cols].head(3).to_dict(orient="records")
        tail_preview = df_ohlcv[ohlcv_cols].tail(3).to_dict(orient="records")
        logger.info(f"🔍 OHLCV head(3): {head_preview}")
        logger.info(f"🔍 OHLCV tail(3): {tail_preview}")
    except Exception:
        pass

    # Рассчитываем индикаторы
    features_df = compute_features(
        df_ohlcv,
        specs=feature_specs,
        volatility_normalize=True,
        normalize_window=args.normalize_window,
    )

    # Диагностика результата расчёта по ключевым фичам
    try:
        # dtypes входного df
        try:
            dtypes_str = {c: str(t) for c, t in df_ohlcv.dtypes.items()}
            logger.info(f"🔍 OHLCV dtypes: {dtypes_str}")
        except Exception:
            pass

        # ручной hlc3 для сравнения
        try:
            manual_hlc3 = (
                df_ohlcv["high"].astype(float)
                + df_ohlcv["low"].astype(float)
                + df_ohlcv["close"].astype(float)
            ) / 3.0
            logger.info(
                f"🔍 manual hlc3 non-null: {int(manual_hlc3.notna().sum())}/{len(manual_hlc3)}"
            )
            logger.info(f"🔍 manual hlc3 head(2): {manual_hlc3.head(2).tolist()}")
        except Exception as e:
            logger.info(f"🔍 manual hlc3 calc error: {e}")

        # Список колонок и их заполненность
        all_cols = [
            c
            for c in features_df.columns
            if c not in ["open", "high", "low", "close", "volume", "timestamp", "ts"]
        ]
        logger.info(f"🔍 FEATURES columns: {len(all_cols)} cols")
        if all_cols:
            non_null_pct = features_df[all_cols].notna().mean().sort_values()
            worst = non_null_pct.head(min(10, len(non_null_pct)))
            best = non_null_pct.tail(min(10, len(non_null_pct)))
            logger.info(
                "🔍 FEATURES worst fill: "
                + ", ".join([f"{k}:{v*100:.0f}%" for k, v in worst.items()])
            )
            logger.info(
                "🔍 FEATURES best fill:  "
                + ", ".join([f"{k}:{v*100:.0f}%" for k, v in best.items()])
            )

        # Пробы по ключевым
        probe_cols = [
            c
            for c in [
                "hlc3",
                "ema_8",
                "ema_21",
                "sma_20",
                "sma_50",
                "rsi_14",
                "atr_14",
                "macd",
                "obv",
            ]
            if c in features_df.columns
        ]
        if probe_cols:
            counts = features_df[probe_cols].notna().sum().to_dict()
            logger.info(f"🔍 FEATURES non-null after compute: {counts}")
            logger.info(
                f"🔍 FEATURES head(2) {probe_cols}: "
                f"{features_df[probe_cols].head(2).to_dict(orient='records')}"
            )

        # Какие спеки отсутствуют в колонках
        try:
            from src.features.specs import FEATURE_SPECS

            expected = set(FEATURE_SPECS.keys())
            present = set(all_cols)
            missing = sorted(expected - present)[:20]
            logger.info(f"🔍 FEATURES missing first20: {missing}")
        except Exception:
            pass
    except Exception:
        pass

    # Детальная статистика по группам индикаторов
    _log_feature_groups_progress(symbol, timeframe, features_df, feature_specs)

    # Сохраняем результаты в базу данных
    # Сохраняем результаты батч-UPSERT-ом через инфраструктуру
    try:
        async with get_db_session() as session:
            # Формируем компактный DataFrame для вставки: ts + индикаторы (исключая OHLCV/временные колонки)
            cols_exclude = {"open", "high", "low", "close", "volume", "timestamp"}
            keep_cols = [c for c in features_df.columns if c not in cols_exclude]
            ind_df = features_df[keep_cols].copy()
            # Гарантируем наличие ts в секундах
            if "ts" not in ind_df.columns and "timestamp" in features_df.columns:
                ind_df["ts"] = (
                    features_df["timestamp"].astype("int64") // 1000
                ).astype("int64")
            saved_count = await infra_insert_indicators(
                session, ind_df, symbol, timeframe
            )
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении батч-UPSERT: {e}")
        # FIXED: Пробрасываем ошибку, чтобы DAG падал при сбое вставки
        # Не маскируем проблему под saved_count = 0
        raise RuntimeError(
            f"Failed to save indicators for {symbol} {timeframe}: {e}"
        ) from e

    logger.info(
        f"✅ {symbol} {timeframe}: {len(df_ohlcv)} баров, {len(feature_specs)} индикаторов, {saved_count} сохранено"
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars_in": len(df_ohlcv),
        "features_out": len(feature_specs),
        "saved": saved_count,
    }


def _log_feature_groups_progress(
    symbol: str, timeframe: str, features_df, feature_specs: list
):
    """Логирует прогресс расчета по группам индикаторов."""

    # Группируем индикаторы по типам
    feature_groups = {}
    for spec in feature_specs:
        group_type = spec.type
        if group_type not in feature_groups:
            feature_groups[group_type] = []
        feature_groups[group_type].append(spec.name)

    # Проверяем заполненность по группам
    for group_type, feature_names in feature_groups.items():
        group_name = group_type.upper()
        total_features = len(feature_names)
        calculated_features = 0
        non_null_features = 0

        for feature_name in feature_names:
            if feature_name in features_df.columns:
                calculated_features += 1
                non_null_count = features_df[feature_name].notna().sum()
                if non_null_count > 0:
                    non_null_features += 1

        # Вычисляем проценты
        calc_pct = (
            (calculated_features / total_features * 100) if total_features > 0 else 0
        )
        fill_pct = (
            (non_null_features / total_features * 100) if total_features > 0 else 0
        )

        # Логируем результат группы
        logger.info(
            f"📊 {symbol} {timeframe} {group_name}: {calc_pct:.0f}% рассчитано ({calculated_features}/{total_features}), {fill_pct:.0f}% заполнено ({non_null_features}/{total_features})"
        )

        # Детальная информация для ключевых групп
        if (
            group_type in ["oscillator", "trend", "volatility"]
            and os.getenv("FEATURES_VERBOSE", "false").lower() == "true"
        ):
            for feature_name in feature_names:
                if feature_name in features_df.columns:
                    non_null_count = features_df[feature_name].notna().sum()
                    total_rows = len(features_df)
                    fill_pct = (
                        (non_null_count / total_rows * 100) if total_rows > 0 else 0
                    )
                    logger.info(
                        f"  🔍 {feature_name}: {non_null_count}/{total_rows} ({fill_pct:.1f}%)"
                    )


async def _get_ohlcv_data(
    symbol: str, timeframe: str, limit: int | None, *, repair_mode: bool = False
) -> pd.DataFrame | None:
    """Получить OHLCV данные из базы данных.

    Режимы работы:
    - Инкрементный (по умолчанию): загружает данные с max_ts - warmup_offset
    - Repair (--repair): загружает последние 24 часа для восстановления

    Args:
        symbol: Торговая пара
        timeframe: Таймфрейм
        limit: Лимит записей (None = без лимита)
        repair_mode: Если True, загружает последние 24 часа

    Returns:
        DataFrame с OHLCV данными или None
    """
    from src.features.domain.strategy import get_max_lookback_for_strategies
    from src.features.specs import FEATURE_SPECS
    from src.features.utils.time_utils import timeframe_to_ms

    async with get_db_session() as session:
        # Определяем фильтр по времени в зависимости от режима
        if repair_mode:
            # Repair режим: последние 24 часа
            time_filter = """
                AND timestamp >= EXTRACT(EPOCH FROM NOW() - INTERVAL '1 day') * 1000
            """
            mode_desc = "repair (24 часа)"
        else:
            # Инкрементный режим: с max_ts - warmup_offset
            # Получаем max_ts из таблицы indicators
            max_ts_query = text(
                """
                SELECT MAX(timestamp) as max_ts
                FROM indicators
                WHERE symbol = :symbol AND timeframe = :timeframe
            """
            )
            max_ts_result = await session.execute(
                max_ts_query, {"symbol": symbol, "timeframe": timeframe}
            )
            max_ts_ms = max_ts_result.scalar() or 0

            if max_ts_ms == 0:
                # Первый запуск: загружаем последние 24 часа
                time_filter = """
                    AND timestamp >= EXTRACT(EPOCH FROM NOW() - INTERVAL '1 day') * 1000
                """
                mode_desc = "первый запуск (24 часа)"
            else:
                # Рассчитываем warmup offset
                available_specs = list(FEATURE_SPECS.keys())
                max_lookback = get_max_lookback_for_strategies(available_specs)
                warmup_bars = int(max_lookback * 1.2)  # 20% буфер
                warmup_offset_ms = warmup_bars * timeframe_to_ms(timeframe)
                since_ts_ms = max(0, max_ts_ms - warmup_offset_ms)

                time_filter = f"""
                    AND timestamp >= {since_ts_ms}
                """
                mode_desc = f"инкремент (с {since_ts_ms}, warmup={warmup_bars} баров)"

        logger.debug(f"Режим загрузки для {symbol} {timeframe}: {mode_desc}")

        # Проверяем наличие данных
        check_query = text(
            f"""
            SELECT COUNT(*) as cnt
            FROM swap_ohlcv_p
            WHERE symbol = :symbol AND timeframe = :timeframe
            {time_filter}
        """
        )
        check_result = await session.execute(
            check_query, {"symbol": symbol, "timeframe": timeframe}
        )
        count = check_result.scalar()

        if count == 0:
            similar_query = text(
                """
                SELECT DISTINCT timeframe
                FROM swap_ohlcv_p
                WHERE symbol = :symbol
                ORDER BY timeframe
            """
            )
            similar_result = await session.execute(similar_query, {"symbol": symbol})
            available_tfs = [row[0] for row in similar_result.fetchall()]
            logger.warning(
                f"Нет данных для {symbol} {timeframe} ({mode_desc}). "
                f"Доступные ТФ: {', '.join(available_tfs)}"
            )
            return None

        logger.debug(f"Найдено {count} записей для {symbol} {timeframe} ({mode_desc})")

        # Загружаем данные
        if limit is not None:
            query = text(
                f"""
                SELECT open, high, low, close, volume, timestamp
                FROM swap_ohlcv_p
                WHERE symbol = :symbol AND timeframe = :timeframe
                {time_filter}
                ORDER BY timestamp DESC
                LIMIT :limit
            """
            )
            params = {"symbol": symbol, "timeframe": timeframe, "limit": limit}
        else:
            query = text(
                f"""
                SELECT open, high, low, close, volume, timestamp
                FROM swap_ohlcv_p
                WHERE symbol = :symbol AND timeframe = :timeframe
                {time_filter}
                ORDER BY timestamp DESC
            """
            )
            params = {"symbol": symbol, "timeframe": timeframe}

        result = await session.execute(query, params)
        rows = result.fetchall()

        if not rows:
            logger.warning(
                f"Запрос вернул 0 строк для {symbol} {timeframe}, "
                f"хотя COUNT показал {count}"
            )
            return None

        # Преобразуем в DataFrame
        return pd.DataFrame(
            [
                {
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "volume": float(row.volume),
                    "timestamp": row.timestamp,
                }
                for row in reversed(rows)  # Восстанавливаем хронологический порядок
            ]
        )


async def _save_features_to_db(
    symbol: str,
    timeframe: str,
    df_ohlcv: pd.DataFrame,
    features_df: pd.DataFrame,
    feature_specs: list,
    args,
) -> int:
    """Сохранить результаты features в базу данных."""
    try:
        # Генерируем run_id и params_hash
        run_id = str(uuid.uuid4())
        params_hash = _generate_params_hash(feature_specs, args)

        # Подготавливаем данные для сохранения
        saved_count = 0
        logger.info(
            f"💾 Начинаем сохранение в таблицу indicators: {symbol} {timeframe}, баров: {len(df_ohlcv)}"
        )

        # 🔍 DEBUG: Детальная диагностика features_df
        logger.info(f"🔍 DEBUG features_df shape: {features_df.shape}")
        logger.info(
            f"🔍 DEBUG features_df columns (first 20): {list(features_df.columns[:20])}"
        )

        # Проверяем ключевые индикаторы
        key_indicators = [
            "ema_8",
            "ema_12",
            "ema_21",
            "sma_20",
            "rsi_14",
            "macd",
            "atr_14",
            "obv",
        ]
        for indicator in key_indicators:
            if indicator in features_df.columns:
                non_null_count = features_df[indicator].notna().sum()
                logger.info(
                    f"🔍 DEBUG {indicator}: {non_null_count}/{len(features_df)} non-null values"
                )
                if non_null_count > 0:
                    sample_values = features_df[indicator].dropna().head(3).tolist()
                    logger.info(f"🔍 DEBUG {indicator} sample values: {sample_values}")
            else:
                logger.warning(f"🔍 DEBUG {indicator} NOT FOUND in features_df columns")

        # Проверяем первые несколько строк features_df
        if len(features_df) > 0:
            logger.info(
                f"🔍 DEBUG features_df first row (first 10 columns): {features_df.iloc[0].head(10).to_dict()}"
            )

        async with get_db_session() as session:
            # Создаем прогресс-бар для сохранения данных
            with tqdm(
                total=len(df_ohlcv),
                desc=f"💾 Сохранение {symbol} {timeframe}",
                unit="бар",
                leave=False,
                ncols=80,
            ) as save_pbar:
                for i, (_, ohlcv_row) in enumerate(df_ohlcv.iterrows()):
                    # Получаем соответствующие features
                    if i < len(features_df):
                        features_row = features_df.iloc[i]
                        features_dict = features_row.to_dict()
                    else:
                        features_dict = {}

                    # Очищаем NaN значения из features и исключаем OHLCV данные
                    cleaned_features = {}
                    ohlcv_columns = {
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "timestamp",
                        "ts",
                    }

                    for k, v in features_dict.items():
                        # Пропускаем OHLCV колонки - они есть в swap_ohlcv_p
                        if k in ohlcv_columns:
                            continue

                        # Сохраняем все значения, включая NaN
                        try:
                            if pd.notna(v):
                                cleaned_features[k] = float(v)
                            else:
                                # NaN значения сохраняем как None (станут NULL в базе)
                                cleaned_features[k] = None
                        except (ValueError, TypeError):
                            cleaned_features[k] = None

                    # Анализируем качество данных
                    nan_count = sum(1 for v in cleaned_features.values() if v is None)
                    valid_rate = (
                        1.0 - (nan_count / len(cleaned_features))
                        if cleaned_features
                        else 1.0
                    )
                    data_quality_status = "good" if valid_rate >= 0.8 else "poor"

                    # Подготавливаем данные для вставки в единую таблицу indicators
                    # OHLCV данные больше не сохраняем - они есть в swap_ohlcv_p
                    insert_data = {
                        "run_id": run_id,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "timestamp": int(ohlcv_row["timestamp"]),
                        "params_hash": params_hash,
                        "data_quality_status": data_quality_status,
                        "nan_count": nan_count,
                        "valid_rate": valid_rate,
                        "schema_version": "v2",
                        "algo_version": "2.0.0",
                    }

                    # DEBUG: Проверяем cleaned_features
                    logger.debug(
                        f"🔍 DEBUG: cleaned_features keys: {list(cleaned_features.keys())}"
                    )
                    stage_a_in_cleaned = [
                        f
                        for f in [
                            "stochrsi_k",
                            "stochrsi_d",
                            "hl2",
                            "hlc3",
                            "ohlc4",
                            "wcp",
                            "median_20",
                            "stdev_20",
                            "zscore_20",
                            "log_return",
                            "percent_return",
                            "drawdown",
                        ]
                        if f in cleaned_features
                    ]
                    if stage_a_in_cleaned:
                        logger.info(
                            f"🔍 DEBUG: Stage A in cleaned_features: {stage_a_in_cleaned}"
                        )

                    # Добавляем все индикаторы из cleaned_features с правильными именами колонок
                    for indicator_name, value in cleaned_features.items():
                        # Пропускаем служебные колонки, которые не должны попадать в таблицу
                        if indicator_name in ["ts", "timestamp"]:
                            continue
                        # Сохраняем все индикаторы (включая None значения, которые станут NULL в базе)
                        # Полный маппинг имен индикаторов на имена колонок в таблице
                        column_mapping = {
                            "aberration": "aberration",
                            "accbands_lower": "accbands_lower",
                            "accbands_middle": "accbands_middle",
                            "accbands_upper": "accbands_upper",
                            "ad": "ad",
                            "adosc": "adosc",
                            "adx_14": "adx_14",
                            "adx_neg_di": "adx_neg_di",
                            "adx_pos_di": "adx_pos_di",
                            "alma_20": "alma_20",
                            "amat": "amat",
                            "ao": "ao",
                            "apo": "apo",
                            "aroon_down": "aroon_down",
                            "aroon_osc": "aroon_osc",
                            "aroon_up": "aroon_up",
                            "atr_14": "atr_14",
                            "bb_lower": "bb_lower",
                            "bb_middle": "bb_middle",
                            "bb_percent": "bb_percent",
                            "bb_upper": "bb_upper",
                            "bb_width": "bb_width",
                            "bbands_lower": "bbands_lower",
                            "bbands_middle": "bbands_middle",
                            "bbands_percent": "bbands_percent",
                            "bbands_upper": "bbands_upper",
                            "bbands_width": "bbands_width",
                            "bias": "bias",
                            "bop": "bop",
                            "brar": "brar",
                            "cci_20": "cci_20",
                            "cdl_doji": "cdl_doji",
                            "cdl_inside": "cdl_inside",
                            "cfo": "cfo",
                            "cg": "cg",
                            "chop": "chop",
                            "cmf": "cmf",
                            "coppock": "coppock",
                            "dc_lower": "dc_lower",
                            "dc_middle": "dc_middle",
                            "dc_upper": "dc_upper",
                            "decay": "decay",
                            "decreasing": "decreasing",
                            "dema_20": "dema_20",
                            "dpo": "dpo",
                            "dpo_20": "dpo_20",
                            "drawdown": "drawdown",
                            "efi": "efi",
                            "ema_8": "ema_8",
                            "ema_12": "ema_12",
                            "ema_13": "ema_13",
                            "ema_21": "ema_21",
                            "ema_26": "ema_26",
                            "ema_34": "ema_34",
                            "ema_50": "ema_50",
                            "ema_55": "ema_55",
                            "ema_89": "ema_89",
                            "ema_144": "ema_144",
                            "ema_200": "ema_200",
                            "ema_233": "ema_233",
                            "eom": "eom",
                            "er": "er",
                            "eri": "eri",
                            "fisher": "fisher",
                            "fwma_20": "fwma_20",
                            "ha_close": "ha_close",
                            "ha_high": "ha_high",
                            "ha_low": "ha_low",
                            "ha_open": "ha_open",
                            "hl2": "hl2",
                            "hlc3": "hlc3",
                            "hma_20": "hma_20",
                            "hwma_20": "hwma_20",
                            "ichimoku_a": "ichimoku_a",
                            "ichimoku_b": "ichimoku_b",
                            "ichimoku_chikou": "ichimoku_chikou",
                            "ichimoku_kijun": "ichimoku_kijun",
                            "ichimoku_senkou_a": "ichimoku_senkou_a",
                            "ichimoku_senkou_b": "ichimoku_senkou_b",
                            "ichimoku_tenkan": "ichimoku_tenkan",
                            "increasing": "increasing",
                            "inertia": "inertia",
                            "kama_20": "kama_20",
                            "kc_lower": "kc_lower",
                            "kc_middle": "kc_middle",
                            "kc_upper": "kc_upper",
                            "kdj_d": "kdj_d",
                            "kdj_k": "kdj_k",
                            "kst": "kst",
                            "kurt_20": "kurt_20",
                            "kurtosis_20": "kurtosis_20",
                            "linreg_20": "linreg_20",
                            "log_return": "log_return",
                            "long_run": "long_run",
                            "macd": "macd",
                            "macd_histogram": "macd_histogram",
                            "macd_signal": "macd_signal",
                            "mad_20": "mad_20",
                            "massi": "massi",
                            "max_drawdown_20": "max_drawdown_20",
                            "median_20": "median_20",
                            "mfi": "mfi",
                            "midpoint": "midpoint",
                            "midprice": "midprice",
                            "mom_10": "mom_10",
                            "natr_14": "natr_14",
                            "nvi": "nvi",
                            "obv": "obv",
                            "ohlc4": "ohlc4",
                            "parkinson_vol": "parkinson_vol",
                            "pdist": "pdist",
                            "percent_return": "percent_return",
                            "pgo": "pgo",
                            "ppo": "ppo",
                            "psar": "psar",
                            "psar_direction": "psar_direction",
                            "psar_long": "psar_long",
                            "psar_short": "psar_short",
                            "psl": "psl",
                            "pvi": "pvi",
                            "pvo": "pvo",
                            "pvt": "pvt",
                            "pwma_20": "pwma_20",
                            "qqe": "qqe",
                            "qstick": "qstick",
                            "returns_20": "returns_20",
                            "rma_20": "rma_20",
                            "roc_10": "roc_10",
                            "rsi_14": "rsi_14",
                            "rsx": "rsx",
                            "rsx_14": "rsx_14",
                            "rvgi": "rvgi",
                            "rvi": "rvi",
                            "sharpe_20": "sharpe_20",
                            "short_run": "short_run",
                            "sinwma_20": "sinwma_20",
                            "skew_20": "skew_20",
                            "slope_20": "slope_20",
                            "sma_20": "sma_20",
                            "sma_34": "sma_34",
                            "sma_50": "sma_50",
                            "sma_200": "sma_200",
                            "smi": "smi",
                            "std_20": "std_20",
                            "stdev_20": "stdev_20",
                            "stoch_d": "stoch_d",
                            "stoch_k": "stoch_k",
                            "stochrsi_d": "stochrsi_d",
                            "stochrsi_k": "stochrsi_k",
                            "supertrend": "supertrend",
                            "supertrend_direction": "supertrend_direction",
                            "supertrend_long": "supertrend_long",
                            "supertrend_short": "supertrend_short",
                            "swma_20": "swma_20",
                            "t3_20": "t3_20",
                            "tema_20": "tema_20",
                            "trange": "trange",
                            "trend_return_20": "trend_return_20",
                            "trima_20": "trima_20",
                            "trix": "trix",
                            "tsf": "tsf",
                            "tsi": "tsi",
                            "ttm_squeeze_hist": "ttm_squeeze_hist",
                            "ttm_squeeze_on": "ttm_squeeze_on",
                            "ttm_squeeze_value": "ttm_squeeze_value",
                            "ttm_trend": "ttm_trend",
                            "ui": "ui",
                            "ultosc": "ultosc",
                            "uo": "uo",
                            "var_20": "var_20",
                            "variance_20": "variance_20",
                            "vidya_20": "vidya_20",
                            "volatility_20": "volatility_20",
                            "volume_sma20": "volume_sma20",
                            "vortex": "vortex",
                            "vp_point_of_control": "vp_point_of_control",
                            "vp_value_area_high": "vp_value_area_high",
                            "vp_value_area_low": "vp_value_area_low",
                            "vwap": "vwap",
                            "vwma": "vwma",
                            "wcp": "wcp",
                            "willr": "willr",
                            "wma_20": "wma_20",
                            "zlma_20": "zlma_20",
                            "zscore_20": "zscore_20",
                        }

                        column_name = column_mapping.get(indicator_name, indicator_name)
                        # DEBUG: Логируем Stage A фичи
                        if indicator_name in [
                            "stochrsi_k",
                            "stochrsi_d",
                            "hl2",
                            "hlc3",
                            "ohlc4",
                            "wcp",
                            "median_20",
                            "stdev_20",
                            "zscore_20",
                            "log_return",
                            "percent_return",
                            "drawdown",
                        ]:
                            logger.info(
                                f"🔍 DEBUG: Saving Stage A feature {indicator_name} -> {column_name} = {value}"
                            )
                        # Сохраняем все индикаторы, которые есть в features_df
                        insert_data[column_name] = value

                    # Строим динамический INSERT запрос (имена колонок без пробелов)
                    columns = list(insert_data.keys())
                    values = [f":{col}" for col in columns]

                    # Строим динамический UPDATE для всех колонок кроме базовых
                    update_columns = []
                    for col in columns:
                        if col not in ["symbol", "timeframe", "timestamp"]:
                            update_columns.append(f"{col} = EXCLUDED.{col}")

                    insert_query = text(
                        f"""
                        INSERT INTO indicators (
                            {', '.join(columns)}
                        ) VALUES (
                            {', '.join(values)}
                        )
                        ON CONFLICT (symbol, timeframe, timestamp)
                        DO UPDATE SET
                            {', '.join(update_columns)},
                            updated_at = NOW()
                    """
                    )

                    # DEBUG: Логируем SQL запрос и параметры
                    if i < 3:  # Логируем только первые 3 записи
                        logger.info(f"🔍 DEBUG SQL: {insert_query}")
                        logger.info(
                            f"🔍 DEBUG PARAMS: {list(insert_data.keys())[:10]}..."
                        )  # Первые 10 параметров
                        logger.info(
                            f"🔍 DEBUG VALUES: {list(insert_data.values())[:5]}..."
                        )  # Первые 5 значений

                    await session.execute(insert_query, insert_data)
                    saved_count += 1

                    # Обновляем прогресс-бар сохранения
                    save_pbar.update(1)
                    save_pbar.set_postfix({"сохранено": saved_count})

                await session.commit()

            logger.info(
                f"📥 ДАННЫЕ ЗАГРУЖЕНЫ В ТАБЛИЦУ indicators: {symbol} {timeframe} | сохранено строк: {saved_count}"
            )
            return saved_count

    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении features для {symbol} {timeframe}: {e}")
        return 0


def _generate_params_hash(feature_specs: list, args) -> str:
    """Генерировать хеш параметров для версионирования."""
    params_str = json.dumps(
        [
            {"name": spec.name, "type": spec.type, "params": spec.params}
            for spec in feature_specs
        ],
        sort_keys=True,
    )

    params_str += f"|normalize:{args.normalize}|window:{args.normalize_window}"

    return hashlib.md5(params_str.encode()).hexdigest()[:16]


if __name__ == "__main__":
    # Тестирование модуля
    async def test():
        from argparse import Namespace

        args = Namespace(
            symbols=None,
            timeframes=["1H"],
            specs=["rsi_14", "atr_14"],
            normalize=True,
            normalize_window=20,
            limit=100,
            dry_run=False,
        )

        await handle(args)

    asyncio.run(test())
