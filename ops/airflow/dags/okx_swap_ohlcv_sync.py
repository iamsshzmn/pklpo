"""
DAG: okx_swap_ohlcv_sync

Назначение
- Сбор и загрузка OHLCV свечей для SWAP-инструментов OKX в таблицу `swap_ohlcv_p`.
- Дополнительно, при `extra_data=True`, подтягиваются `funding_rate` и `open_interest`.

Состав задач
- refresh_okx_meta: обновляет справочник инструментов (CLI: load-instruments).
- swap_sync: вызывает Python-функцию `sync_swap_candles` и возвращает агрегированную
  статистику в XCom (`return_value`). Включены консервативные лимиты и ретраи.
- smoke_validate: быстрая проверка наличия записей и доли заполнения `funding_rate`/`open_interest` за сегодня.

Логирование и артефакты
- Лог-файл market_meta: `/tmp/pklpo/market_meta.log` внутри контейнеров Airflow.
- XCom у `swap_sync`: ключ `return_value` содержит итоговую статистику (в т.ч. endpoint_stats и today_fill).

Параметры/лимиты (по умолчанию для swap_sync)
- max_requests_per_second=15, max_concurrent_symbols=1, max_retries=5, retry_delay=1.5, batch_size=300.
- Внутри синхронизатора реализованы раздельные лимитеры по эндпоинтам и джиттер для снижения 429.

Расписание
- schedule=None: запуск вручную из UI/CLI. Рекомендуется избегать одновременных запусков.
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator


def refresh_okx_meta_task():
    # Call load-instruments via CLI command
    import os
    import subprocess
    from pathlib import Path

    # Set up environment for the command
    env = os.environ.copy()
    env["DATABASE_URL"] = (
        "postgresql+asyncpg://pklpo_user:strongpassword@pklpo_db:5432/pklpo"
    )
    env["DATABASE_SSL"] = "disable"  # Отключаем SSL для Docker-окружения
    # Маршрутизируем файл логов market_meta в доступную на запись директорию
    env["MARKET_META_LOG_FILE"] = "/tmp/pklpo/market_meta.log"
    env["MARKET_META_FILE_LOG"] = "true"
    env["MARKET_META_LOG_LEVEL"] = "DEBUG"
    env["MARKET_META_DATA_DIR"] = "/tmp/pklpo/data"
    env["INSTRUMENTS_CACHE_DIR"] = "/tmp/pklpo"
    # Ensure writable dirs exist
    Path("/tmp/pklpo").mkdir(parents=True, exist_ok=True)
    Path("/tmp/pklpo/data").mkdir(parents=True, exist_ok=True)

    print("[okx_swap_ohlcv_sync] calling load-instruments CLI command")
    result = subprocess.run(
        ["python", "-m", "src.cli.main", "load-instruments"],
        env=env,
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


def swap_sync_task(**context):
    # Run swap candles synchronization in-process and return stats to XCom
    import asyncio
    import os
    from pathlib import Path

    # Set up environment for the task (must be set BEFORE importing sync_swap_candles
    # so that its logging auto-config picks them up)
    os.environ["DATABASE_URL"] = (
        "postgresql+asyncpg://pklpo_user:strongpassword@pklpo_db:5432/pklpo"
    )
    os.environ["DATABASE_SSL"] = "disable"  # Отключаем SSL для Docker-окружения
    os.environ["MARKET_META_LOG_FILE"] = "/tmp/pklpo/market_meta.log"
    os.environ["MARKET_META_FILE_LOG"] = "true"
    os.environ["MARKET_META_LOG_LEVEL"] = "DEBUG"
    os.environ["MARKET_META_DATA_DIR"] = "/tmp/pklpo/data"
    os.environ["INSTRUMENTS_CACHE_DIR"] = "/tmp/pklpo"

    # Ensure writable dirs exist
    Path("/tmp/pklpo").mkdir(parents=True, exist_ok=True)
    Path("/tmp/pklpo/data").mkdir(parents=True, exist_ok=True)

    # Import after env is set to avoid logging writing to /opt/airflow/project/logs
    from src.candles.interfaces.swap_sync import sync_swap_candles

    # Enable fetching extra metrics (funding rate, open interest)
    cfg = {
        "extra_data": True,
        "max_requests_per_second": 15,
        "batch_size": 300,
        "max_concurrent_symbols": 1,
        "max_retries": 5,
        "retry_delay": 1.5,
    }

    print("[okx_swap_ohlcv_sync] starting swap-sync (python call) with extra_data=True")
    stats = asyncio.run(sync_swap_candles(symbols=None, timeframes=None, config=cfg))
    # Returned value will be stored in XCom automatically by PythonOperator
    return stats


def smoke_validate_task():
    # Simple validation that data was written to the database
    import os
    import subprocess
    from pathlib import Path

    # Set up environment for the command
    env = os.environ.copy()
    env["DATABASE_URL"] = (
        "postgresql+asyncpg://pklpo_user:strongpassword@pklpo_db:5432/pklpo"
    )
    env["DATABASE_SSL"] = "disable"  # Отключаем SSL для Docker-окружения
    env["MARKET_META_LOG_FILE"] = "/tmp/pklpo/market_meta.log"
    env["MARKET_META_FILE_LOG"] = "true"
    env["MARKET_META_LOG_LEVEL"] = "DEBUG"
    env["MARKET_META_DATA_DIR"] = "/tmp/pklpo/data"
    env["INSTRUMENTS_CACHE_DIR"] = "/tmp/pklpo"
    # Ensure writable dirs exist
    Path("/tmp/pklpo").mkdir(parents=True, exist_ok=True)
    Path("/tmp/pklpo/data").mkdir(parents=True, exist_ok=True)

    print("[okx_swap_ohlcv_sync] running smoke validation")
    result = subprocess.run(
        [
            "python",
            "-u",
            "-c",
            (
                "import asyncio, sys, traceback\n"
                "from sqlalchemy import text\n"
                "from src.database import get_async_session\n"
                "async def check():\n"
                "    try:\n"
                "        async for session in get_async_session():\n"
                "            res = await session.execute('SELECT COUNT(*) FROM swap_ohlcv_p')\n"
                "            print('Records in swap_ohlcv_p:', res.scalar())\n"
                "            # Freshness check for today fill ratios\n"
                "            res2 = await session.execute(text(\n"
                '                """\n'
                "                WITH t AS (\n"
                "                  SELECT * FROM swap_ohlcv_p WHERE timestamp >= extract(epoch from date_trunc('day', now()))*1000\n"
                "                )\n"
                "                SELECT\n"
                "                  COUNT(*) AS rows_today,\n"
                "                  COUNT(*) FILTER (WHERE funding_rate IS NOT NULL) AS fr_filled,\n"
                "                  COUNT(*) FILTER (WHERE open_interest IS NOT NULL) AS oi_filled\n"
                "                FROM t\n"
                '                """\n'
                "            ))\n"
                "            rows_today, fr_filled, oi_filled = res2.fetchone()\n"
                "            print('Today rows:', rows_today, 'FR filled:', fr_filled, 'OI filled:', oi_filled)\n"
                "            break\n"
                "    except Exception as e:\n"
                "        traceback.print_exc()\n"
                "        sys.exit(1)\n"
                "asyncio.run(check())\n"
            ),
        ],
        env=env,
        check=False,
        cwd="/opt/airflow/project",
    )
    if result.returncode != 0:
        raise Exception(f"validation failed with code {result.returncode}")
    print("[okx_swap_ohlcv_sync] smoke validation finished OK")


with DAG(
    dag_id="okx_swap_ohlcv_sync",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    default_args={"owner": "okx_swap_ohlcv_sync", "retries": 0},
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

    refresh_okx >> swap_sync >> smoke_validate
