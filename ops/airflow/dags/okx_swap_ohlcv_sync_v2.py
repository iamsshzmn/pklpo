"""
DAG: okx_swap_ohlcv_sync

Назначение
- Сбор и загрузка OHLCV свечей для SWAP-инструментов OKX в таблицу `swap_ohlcv_p`.
- Дополнительно, при `extra_data=True`, подтягиваются `funding_rate` и `open_interest`.

Состав задач
- refresh_okx_meta: обновляет справочник инструментов (CLI: load-instruments) условно.
- swap_sync: вызывает Python-функцию `sync_swap_candles` и возвращает агрегированную
  статистику в XCom (`return_value`). Параметризуется через `dag_run.conf`.
- smoke_validate: быстрая проверка наличия записей и доли заполнения `funding_rate`/`open_interest` за сегодня.

Параметры запуска (через dag_run.conf)
- mode: "fast" (default), "slow", "ext", "bootstrap"
- extra_data: bool (default: False)
- timeframes: list[str] (optional, переопределяет режим)
- symbols: list[str] (optional)
- refresh_instruments: bool (default: False)
- max_concurrent_symbols: int (optional)

Примеры запуска:
- Fast режим (по умолчанию): Trigger DAG with config: {}
- Slow режим: Trigger DAG with config: {"mode": "slow"}
- Ext режим: Trigger DAG with config: {"mode": "ext", "symbols": ["BTC-USDT-SWAP"]}
- Bootstrap: Trigger DAG with config: {"mode": "bootstrap", "refresh_instruments": true}

Логирование и артефакты
- Лог-файл market_meta: `/tmp/pklpo/market_meta.log` внутри контейнеров Airflow.
- XCom у `swap_sync`: ключ `return_value` содержит компактную статистику.

Расписание
- schedule=None: запуск вручную из UI/CLI. Рекомендуется избегать одновременных запусков.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.candles.sync_swap_candles import sync_swap_candles
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
        # Если loop не существует или закрыт, создаем новый
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
        # Если connection не настроен, падаем с явной ошибкой (без fallback)
        raise RuntimeError(
            "DATABASE_URL не настроен. Установите Airflow Connection 'pklpo_db' "
            "(Conn Id: pklpo_db, Type: Postgres). "
            "Никаких дефолтов с паролями в коде!"
        ) from e

    # Остальные переменные (не секреты) из Variables с безопасными дефолтами
    env["DATABASE_SSL"] = Variable.get("pklpo_database_ssl", default_var="disable")
    env["MARKET_META_LOG_FILE"] = Variable.get(
        "market_meta_log_file", default_var="/tmp/pklpo/market_meta.log"
    )
    env["MARKET_META_FILE_LOG"] = Variable.get(
        "market_meta_file_log", default_var="true"
    )
    env["MARKET_META_LOG_LEVEL"] = Variable.get(
        "market_meta_log_level", default_var="DEBUG"
    )
    env["MARKET_META_DATA_DIR"] = Variable.get(
        "market_meta_data_dir", default_var="/tmp/pklpo/data"
    )
    env["INSTRUMENTS_CACHE_DIR"] = Variable.get(
        "instruments_cache_dir", default_var="/tmp/pklpo"
    )

    return env


def setup_env(env: dict[str, str | None]) -> None:
    """Устанавливает переменные окружения и создаёт необходимые директории."""
    import os

    for key, value in env.items():
        if value is not None:
            os.environ[key] = value

    # Ensure writable dirs exist
    Path("/tmp/pklpo").mkdir(parents=True, exist_ok=True)
    Path("/tmp/pklpo/data").mkdir(parents=True, exist_ok=True)


def get_sync_config(context: dict[str, Any]) -> dict[str, Any]:
    """Извлекает конфигурацию синхронизации из dag_run.conf."""
    dag_run = context.get("dag_run")
    conf: dict[str, Any] = (dag_run.conf or {}) if dag_run else {}

    # Если conf пустой (scheduled запуск), выбираем режим по времени (авто-слоты)
    if not conf:
        execution_date = context.get("execution_date")
        if execution_date:
            minute = execution_date.minute
            # slow запускается в 0, 15, 30, 45 минут, иначе fast
            # При расписании */5 slow будет в 0, 15, 30, 45
            conf = {"mode": "slow"} if minute in (0, 15, 30, 45) else {"mode": "fast"}
        else:
            # Fallback на fast
            conf = {"mode": "fast"}

    mode = conf.get("mode", "fast")  # fast, slow, ext, bootstrap

    # Предустановленные режимы (используем SWAP_BARS для консистентности)
    # SWAP_BARS = ["1m", "5m", "15m", "30m", "1H", "4H", "12H", "1D", "1W", "1M"]
    mode_configs = {
        "fast": {
            "timeframes": ["1m", "5m"],
            "extra_data": False,
            "max_concurrent_symbols": 10,
            "max_requests_per_second": 20,
        },
        "slow": {
            "timeframes": ["15m", "30m", "1H", "4H", "12H", "1D", "1W", "1M"],
            "extra_data": False,
            "max_concurrent_symbols": 2,
            "max_requests_per_second": 15,
        },
        "ext": {
            "timeframes": ["1m", "5m"],
            "extra_data": True,
            "max_concurrent_symbols": 5,
            "max_requests_per_second": 15,
        },
        "bootstrap": {
            "timeframes": None,  # все (использует SWAP_BARS из sync_swap_candles)
            "extra_data": True,
            "max_concurrent_symbols": 1,
            "max_requests_per_second": 15,
        },
    }

    # Получаем базовую конфигурацию для режима и копируем для модификации
    selected_config = cast(
        "dict[str, Any]", mode_configs.get(mode, mode_configs["fast"])
    )
    base_config: dict[str, Any] = dict(selected_config)

    # Переопределение из conf
    if "timeframes" in conf:
        base_config["timeframes"] = conf["timeframes"]
    if "extra_data" in conf:
        base_config["extra_data"] = conf["extra_data"]
    if "max_concurrent_symbols" in conf:
        base_config["max_concurrent_symbols"] = conf["max_concurrent_symbols"]
    if "symbols" in conf:
        base_config["symbols"] = conf["symbols"]

    base_config["mode"] = mode
    base_config["batch_size"] = 300
    base_config["max_retries"] = 5
    base_config["retry_delay"] = 1.5

    return base_config


def should_refresh_instruments(context: dict[str, Any]) -> bool:
    """Определяет, нужно ли обновлять инструменты."""
    dag_run = context.get("dag_run")
    conf: dict[str, Any] = (dag_run.conf or {}) if dag_run else {}

    # Явный флаг
    if conf.get("refresh_instruments", False):
        return True

    # Проверка возраста кэша
    cache_file = Path("/tmp/pklpo/instruments_list.json")
    if cache_file.exists():
        age_hours = (
            datetime.now(UTC).timestamp()
            - datetime.fromtimestamp(cache_file.stat().st_mtime, tz=UTC).timestamp()
        ) / 3600
        if age_hours < 24:
            return False

    return True


def format_stats_for_xcom(
    stats: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """Формирует компактную статистику для XCom."""
    # Агрегируем endpoint_stats (структура: dict[endpoint, dict[metric, count]])
    endpoint_stats = stats.get("endpoint_stats", {})
    api_429_count = 0
    api_timeout_count = 0

    if isinstance(endpoint_stats, dict):
        # endpoint_stats имеет структуру: {"candles": {"rate_limit": 5, ...}, ...}
        for endpoint_data in endpoint_stats.values():
            if isinstance(endpoint_data, dict):
                # rate_limit соответствует 429
                api_429_count += endpoint_data.get("rate_limit", 0)
                # errors могут включать таймауты (нужно проверить структуру)
                # Пока считаем только rate_limit как 429

    return {
        "mode": config.get("mode", "unknown"),
        "timeframes": config.get("timeframes", []),
        "symbols_count": stats.get("total_symbols", 0),
        "duration_sec": round(stats.get("duration_seconds", 0), 2),
        "rows_upserted_total": stats.get("total_candles_synced", 0),
        "errors_count": stats.get("errors_count", 0),
        "candles_per_second": round(stats.get("candles_per_second", 0), 2),
        "api_429_count": api_429_count,
        "api_timeout_count": api_timeout_count,
        "today_fill": stats.get("today_fill", {}),
    }


def refresh_okx_meta_task(**context):
    """Обновляет справочник инструментов через CLI (условно)."""
    import os
    import subprocess

    try:
        if not should_refresh_instruments(context):
            print("[okx_swap_ohlcv_sync] Skipping instruments refresh (cache is fresh)")
            return

        env = get_dag_env()
        setup_env(env)

        # Объединяем с текущими переменными окружения (важно для PATH, PYTHONPATH и т.д.)
        full_env = {**os.environ, **env}

        print("[okx_swap_ohlcv_sync] calling load-instruments CLI command")
        result = subprocess.run(
            ["python", "-m", "src.cli.main", "load-instruments"],
            env=full_env,
            check=False,
            cwd="/opt/airflow/project",
            capture_output=True,
            text=True,
        )

        # Выводим stdout и stderr для диагностики
        if result.stdout:
            print(f"[STDOUT]\n{result.stdout}")
        if result.stderr:
            print(f"[STDERR]\n{result.stderr}")

        if result.returncode != 0:
            raise Exception(
                f"load-instruments failed with code {result.returncode}\n"
                f"STDERR: {result.stderr}\nSTDOUT: {result.stdout}"
            )
        print("[okx_swap_ohlcv_sync] load-instruments finished OK")
    except Exception as e:
        print(f"[okx_swap_ohlcv_sync] Error in refresh_okx_meta_task: {e}")
        raise


def swap_sync_task(**context):
    """Запускает синхронизацию swap свечей с параметризацией через dag_run.conf."""
    from datetime import datetime

    from sqlalchemy import text

    env = get_dag_env()
    setup_env(env)

    # Получаем конфигурацию из dag_run.conf
    config = get_sync_config(context)
    mode = config.get("mode", "fast")

    # Freshness gate: пропускаем выполнение, если данные свежие
    # Для ручных запусков (manual) всегда выполняем синхронизацию
    dag_run = context.get("dag_run")
    is_manual_run = dag_run and dag_run.run_type == "manual"

    async def check_freshness() -> bool:
        """Проверяет свежесть данных. Возвращает True если нужно пропустить выполнение."""
        async with get_db_session() as session:
            # Для fast режима проверяем 1m таймфрейм
            # Для slow режима проверяем 15m таймфрейм
            timeframe_to_check = "1m" if mode == "fast" else "15m"
            max_lag_seconds = (
                120 if mode == "fast" else 900
            )  # 2 мин для fast, 15 мин для slow

            res_max = await session.execute(
                text(
                    """
                    SELECT MAX(timestamp)
                    FROM swap_ohlcv_p
                    WHERE timeframe = :tf
                    """
                ),
                {"tf": timeframe_to_check},
            )
            max_ts_ms = res_max.scalar()

            if not max_ts_ms:
                print(
                    f"[okx_swap_ohlcv_sync] Нет данных для {timeframe_to_check}, запускаем синхронизацию"
                )
                return False

            max_ts_dt = datetime.fromtimestamp(max_ts_ms / 1000, tz=UTC)
            lag_sec = (datetime.now(UTC) - max_ts_dt).total_seconds()

            if lag_sec < max_lag_seconds:
                print(
                    f"[okx_swap_ohlcv_sync] Данные свежие ({timeframe_to_check} lag: {lag_sec:.0f}s < {max_lag_seconds}s), "
                    f"пропускаем выполнение"
                )
                return True

            print(
                f"[okx_swap_ohlcv_sync] Данные требуют обновления ({timeframe_to_check} lag: {lag_sec:.0f}s >= {max_lag_seconds}s)"
            )
            return False

    # Получаем или создаем event loop для этой попытки
    loop = get_or_create_event_loop()

    # Проверяем свежесть данных (пропускаем для ручных запусков)
    if is_manual_run:
        print(
            "[okx_swap_ohlcv_sync] Ручной запуск: пропускаем freshness gate, "
            "выполняем синхронизацию"
        )
        should_skip = False
    else:
        should_skip = loop.run_until_complete(check_freshness())
    if should_skip:
        print("[okx_swap_ohlcv_sync] Задача пропущена (freshness gate)")
        return {
            "mode": mode,
            "skipped": True,
            "reason": "data_fresh",
            "message": "Данные свежие, синхронизация не требуется",
        }

    print(f"[okx_swap_ohlcv_sync] starting swap-sync in mode={mode}")
    print(f"[okx_swap_ohlcv_sync] config: {config}")

    stats = loop.run_until_complete(
        sync_swap_candles(
            symbols=config.get("symbols"),
            timeframes=config.get("timeframes"),
            config={
                "extra_data": config.get("extra_data", False),
                "max_requests_per_second": config.get("max_requests_per_second", 15),
                "batch_size": config.get("batch_size", 300),
                "max_concurrent_symbols": config.get("max_concurrent_symbols", 1),
                "max_retries": config.get("max_retries", 5),
                "retry_delay": config.get("retry_delay", 1.5),
            },
        )
    )

    # Формируем компактную статистику для XCom
    xcom_stats = format_stats_for_xcom(stats, config)
    print(f"[okx_swap_ohlcv_sync] sync completed: {xcom_stats}")

    return xcom_stats


def quality_pipeline_task(**context):
    """Run data quality checks (duplicate detection, freshness, fill-rate) and dispatch alerts."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.market_meta.application.quality_pipeline import run_quality_pipeline
    from src.market_meta.infrastructure.sqlalchemy_pool_adapter import (
        SQLAlchemyPoolAdapter,
    )

    env = get_dag_env()
    setup_env(env)

    loop = get_or_create_event_loop()

    async def _run():
        engine = create_async_engine(env["DATABASE_URL"])
        pool = SQLAlchemyPoolAdapter(engine)
        try:
            report, alert_stats = await run_quality_pipeline(pool, send_alerts=True)
            violations = sum(1 for r in report.results if str(r.severity) != "ok")
            print(
                f"[quality_pipeline] total_checks={len(report.results)} "
                f"violations={violations} alert_stats={alert_stats}"
            )
            return {
                "total_checks": len(report.results),
                "violations": violations,
                "alert_stats": alert_stats,
            }
        finally:
            await engine.dispose()

    return loop.run_until_complete(_run())


def smoke_validate_task(**context):
    """Валидация данных без subprocess."""
    from datetime import datetime

    from sqlalchemy import text

    env = get_dag_env()
    setup_env(env)

    # Используем get_sync_config для получения effective config (как в swap_sync_task)
    config = get_sync_config(context)
    extra_data_enabled = config.get("extra_data", False)
    mode = config.get("mode", "fast")

    # Получаем или создаем event loop для этой попытки
    loop = get_or_create_event_loop()

    async def validate():
        async with get_db_session() as session:
            # Общее количество записей
            res_total = await session.execute(text("SELECT COUNT(*) FROM swap_ohlcv_p"))
            total_rows = res_total.scalar() or 0
            print(f"Records in swap_ohlcv_p: {total_rows:,}")

            # Свежесть: max(timestamp)
            res_max = await session.execute(
                text("SELECT MAX(timestamp) FROM swap_ohlcv_p")
            )
            max_ts_ms = res_max.scalar()
            if max_ts_ms:
                max_ts_dt = datetime.fromtimestamp(max_ts_ms / 1000, tz=UTC)
                lag_sec = (datetime.now(UTC) - max_ts_dt).total_seconds()
                print(f"Max timestamp: {max_ts_dt} (lag: {lag_sec:.0f}s)")

            # Данные за сегодня (timestamp в миллисекундах)
            start_of_day_ms = int(
                datetime.now(UTC)
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .timestamp()
                * 1000
            )

            res_today = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS rows_today,
                        COUNT(*) FILTER (WHERE funding_rate IS NOT NULL) AS fr_filled,
                        COUNT(*) FILTER (WHERE open_interest IS NOT NULL) AS oi_filled
                    FROM swap_ohlcv_p
                    WHERE timestamp >= :start_ms
                """
                ),
                {"start_ms": start_of_day_ms},
            )
            rows_today, fr_filled, oi_filled = res_today.fetchone()
            print(
                f"Today rows: {rows_today}, FR filled: {fr_filled}, OI filled: {oi_filled}"
            )

            # Проверка лага по таймфреймам (только для fast/ext)
            if mode in ("fast", "ext"):
                for tf in ["1m", "5m"]:
                    res_tf = await session.execute(
                        text(
                            """
                            SELECT MAX(timestamp)
                            FROM swap_ohlcv_p
                            WHERE timeframe = :tf
                        """
                        ),
                        {"tf": tf},
                    )
                    max_tf_ts = res_tf.scalar()
                    if max_tf_ts:
                        lag_sec = (
                            datetime.now(UTC).timestamp() * 1000 - max_tf_ts
                        ) / 1000
                        print(f"Lag for {tf}: {lag_sec:.0f}s")

            # Проверка fill-rate только если extra_data включён
            if extra_data_enabled and rows_today > 0:
                fr_pct = (fr_filled / rows_today) * 100
                oi_pct = (oi_filled / rows_today) * 100
                print(f"FR fill rate: {fr_pct:.1f}%, OI fill rate: {oi_pct:.1f}%")

                # Предупреждение при низком fill-rate
                if fr_pct < 50:
                    print(f"WARNING: Low funding_rate fill rate: {fr_pct:.1f}%")
                if oi_pct < 50:
                    print(f"WARNING: Low open_interest fill rate: {oi_pct:.1f}%")

    loop.run_until_complete(validate())
    print("[okx_swap_ohlcv_sync] smoke validation finished OK")


default_args = {
    "owner": "okx_swap_ohlcv_sync",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(hours=2),  # дефолт для bootstrap
}

with DAG(
    dag_id="okx_swap_ohlcv_sync_v2",
    start_date=datetime(2025, 1, 1),
    schedule="*/5 * * * *",  # Каждые 5 минут (fast режим), slow запускается в 0, 15, 30, 45 минут
    catchup=False,
    max_active_runs=1,  # Только один активный запуск (критично для автономной работы)
    default_args=default_args,
) as dag:
    refresh_okx = PythonOperator(
        task_id="refresh_okx_meta",
        python_callable=refresh_okx_meta_task,
    )

    swap_sync = PythonOperator(
        task_id="swap_sync",
        python_callable=swap_sync_task,
    )

    smoke_validate = PythonOperator(
        task_id="smoke_validate",
        python_callable=smoke_validate_task,
    )

    quality_pipeline = PythonOperator(
        task_id="quality_pipeline",
        python_callable=quality_pipeline_task,
        trigger_rule="all_done",  # run even if smoke_validate fails
    )

    refresh_okx >> swap_sync >> smoke_validate >> quality_pipeline
