"""
DAG: features_calc

Назначение
- Запуск расчёта технических индикаторов (этап Features) через CLI `src.cli.main features`.
- Production режим: расчёт для всех символов из swap_ohlcv_p по всем доступным свечам.
- Поддержка фильтрации: можно указать конкретные символы через параметр symbols.

Состав задач
- features_run: запускает расчёт индикаторов без лимита (все доступные бары).
- smoke_validate_features: проверяет наличие записей в таблице `indicators` после расчёта.

Параметры запуска (через dag_run.conf или params)
- symbols: None или "none" = все символы из swap_ohlcv_p, иначе конкретный символ или список
- timeframes: "1m,5m,15m,30m,1H,4H,12H,1D,1W,1M" (по умолчанию все таймфреймы)
- limit: None или "none" = все свечи, иначе число = последние N свечей

Логирование и артефакты
- Логи печатаются в stdout Airflow. Для детальных логов см. логи CLI `features`.

Расписание
- schedule=None: запуск вручную из UI/CLI. Рекомендуется избегать одновременных запусков с ingest.
"""

import os
import sys
from datetime import datetime, timedelta

# Устанавливаем переменные окружения ДО импорта модулей Airflow
os.environ["FEATURES_LOG_FILE"] = "/tmp/pklpo/features.log"
os.environ["MARKET_META_LOG_FILE"] = "/tmp/pklpo/market_meta.log"
os.environ["MARKET_META_FILE_LOG"] = "false"
os.environ["MARKET_META_LOG_LEVEL"] = "WARNING"
os.environ["MARKET_META_DATA_DIR"] = "/tmp/pklpo/data"
os.environ["INSTRUMENTS_CACHE_DIR"] = "/tmp/pklpo"

# Add project to path for imports
sys.path.insert(0, "/opt/airflow/project")

from airflow import DAG
from airflow.operators.python import PythonOperator


def _normalize_async_database_uri(uri: str) -> str:
    if uri.startswith("postgresql+asyncpg://"):
        return uri
    if uri.startswith("postgresql://"):
        return uri.replace("postgresql://", "postgresql+asyncpg://", 1)
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql+asyncpg://", 1)
    return uri


def _get_database_url() -> str:
    from airflow.hooks.base import BaseHook

    conn = BaseHook.get_connection("pklpo_db")
    if not conn:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set Airflow Connection 'pklpo_db'."
        )
    return _normalize_async_database_uri(conn.get_uri())


def _redact_database_url(uri: str) -> str:
    scheme, separator, rest = uri.partition("://")
    if not separator or "@" not in rest:
        return uri
    return f"{scheme}{separator}***@{rest.rsplit('@', 1)[1]}"


# Import alerting callbacks through the public features bootstrap boundary.
try:
    from src.features.bootstrap import create_feature_airflow_callbacks

    callbacks = create_feature_airflow_callbacks()
    combined_failure_callback = callbacks.on_failure_callback
    combined_sla_miss_callback = callbacks.sla_miss_callback
    success_callback = callbacks.on_success_callback
    ALERTS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Warning: Could not import alerts module: {e}")
    print("   Alerting will be disabled for this DAG")
    ALERTS_AVAILABLE = False
    # Define dummy callbacks
    combined_failure_callback = None
    combined_sla_miss_callback = None
    success_callback = None


def features_run_task(
    symbols: str | None = None, timeframes=None, limit: int | None = None
):
    """
    Задача для запуска расчёта технических индикаторов через CLI.
    """
    # Принудительно сбрасываем буфер для немедленного вывода в логи Airflow
    import sys

    sys.stdout.flush()
    sys.stderr.flush()

    print("=" * 80)
    print("🚀 НАЧАЛО ВЫПОЛНЕНИЯ ЗАДАЧИ features_run_task")
    print("=" * 80)
    sys.stdout.flush()  # Гарантируем немедленный вывод

    # Запускаем CLI команду features через subprocess
    import subprocess
    import time
    from pathlib import Path

    # КРИТИЧНО: Jinja2 может передать строку "None" вместо Python None
    # Нормализуем symbols ДО логирования и обработки
    if isinstance(symbols, str) and symbols.strip().lower() in ("none", "null", ""):
        symbols = None
    elif symbols is not None and not isinstance(symbols, str):
        # Если передан не строковый тип (например, список из Jinja2), конвертируем
        symbols = None

    print("📋 Входные параметры (после нормализации):")
    print(f"   - symbols: {symbols} (тип: {type(symbols).__name__})")
    print(f"   - timeframes: {timeframes}")
    print(f"   - limit: {limit}")
    print(f"   - timestamp: {datetime.now()}")
    sys.stdout.flush()  # Гарантируем немедленный вывод

    print("\n🔧 Настройка переменных окружения...")
    env = os.environ.copy()
    env["DATABASE_URL"] = _get_database_url()
    env["FEATURES_LOG_FILE"] = "/tmp/pklpo/features.log"
    # Важно: гарантируем, что используется смонтированный код проекта, а не установленный пакет
    env["PYTHONPATH"] = "/opt/airflow/project"
    # Для тестов с малым количеством данных (599 свечей): ОТКЛЮЧАЕМ gate validation
    # ВНИМАНИЕ: Это только для тестирования! В production нужны полноценные данные
    # Добавляем текущую директорию в PYTHONPATH для корректного импорта модулей
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"/opt/airflow/project:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = "/opt/airflow/project"
    # Включаем детальное логирование прогресса
    env["FEATURES_VERBOSE"] = "true"
    # Отключаем tqdm для чистого вывода
    env["TQDM_DISABLE"] = "1"

    print(f"✅ PYTHONPATH: {env['PYTHONPATH']}")
    print(f"✅ DATABASE_URL: {_redact_database_url(env['DATABASE_URL'])}")
    print(f"✅ FEATURES_LOG_FILE: {env['FEATURES_LOG_FILE']}")
    print(f"✅ FEATURES_VERBOSE: {env['FEATURES_VERBOSE']}")

    print("\n📁 Создание временных директорий...")
    # Гарантируем доступность временных директорий
    Path("/tmp/pklpo").mkdir(parents=True, exist_ok=True)
    Path("/tmp/pklpo/data").mkdir(parents=True, exist_ok=True)
    print("✅ Директории созданы: /tmp/pklpo, /tmp/pklpo/data")

    print("\n🔄 Обработка параметров...")
    # Нормализуем параметр symbols из dag_run.conf
    # Важно: Jinja2 может вернуть строку "None" вместо None, обрабатываем это
    normalized_symbols: str | None = None

    # Обрабатываем случай, когда symbols приходит как строка "None" из Jinja2
    if symbols is None:
        normalized_symbols = None
        print("   - symbols (None): будут обработаны все символы")
    elif isinstance(symbols, str):
        sym_str = symbols.strip().lower()
        print(f"   - symbols (строка): '{symbols}' -> '{sym_str}'")
        # Проверяем, что это не "none", "null" или пустая строка
        if sym_str not in ("", "none", "null"):
            normalized_symbols = symbols  # Сохраняем оригинальное значение
            print(f"   - symbols (нормализован): {normalized_symbols}")
        else:
            normalized_symbols = None
            print("   - symbols (пустое значение, будут обработаны все символы)")
    else:
        # Для других типов (например, список) - конвертируем в строку или None
        normalized_symbols = None
        print(
            f"   - symbols (неожиданный тип {type(symbols)}): {symbols}, будет обработан как None"
        )

    # Приводим параметры к ожидаемому виду
    if isinstance(timeframes, str):
        # поддержка строк вида "1m,5m,15m" и "1m 5m 15m"
        timeframes = [
            t.strip() for t in timeframes.replace(",", " ").split() if t.strip()
        ]
        print(f"   - timeframes (строка): '{timeframes}' -> список: {timeframes}")
    if not timeframes:
        timeframes = ["1m", "5m", "15m", "30m", "1H", "4H", "12H", "1D", "1W", "1M"]
        print(f"   - timeframes (по умолчанию): {timeframes}")

    # Нормализуем параметр limit из dag_run.conf (может приходить строкой)
    normalized_limit: int | None = None
    if isinstance(limit, str):
        lim_str = limit.strip().lower()
        print(f"   - limit (строка): '{limit}' -> '{lim_str}'")
        if lim_str not in ("", "none", "null"):
            try:
                normalized_limit = int(float(limit))
                print(f"   - limit (нормализован): {normalized_limit}")
            except Exception as e:
                print(f"   - limit (ошибка парсинга): {e}")
                normalized_limit = None
    elif isinstance(limit, int | float):  # type: ignore[unreachable]
        try:
            normalized_limit = int(limit)
            print(f"   - limit (число): {limit} -> {normalized_limit}")
        except Exception as e:
            print(f"   - limit (ошибка конвертации): {e}")
            normalized_limit = None
    else:  # type: ignore[unreachable]
        print(f"   - limit (None): {limit}")

    print("\n📊 Итоговые параметры:")
    print(f"   - symbols: {normalized_symbols} (None = все символы)")
    print(f"   - timeframes: {timeframes}")
    print(f"   - limit: {normalized_limit} (None = все свечи)")
    print(f"   - timestamp: {datetime.now()}")

    eligible_by_tf = _run_async(
        _resolve_feature_eligible_work_items(normalized_symbols, timeframes)
    )
    timeframes = [tf for tf in timeframes if eligible_by_tf.get(tf)]
    if normalized_symbols is not None:
        eligible_symbols = sorted(
            {symbol for tf_symbols in eligible_by_tf.values() for symbol in tf_symbols}
        )
        normalized_symbols = ",".join(eligible_symbols) if eligible_symbols else None
    if not timeframes or (symbols is not None and normalized_symbols is None):
        print("⚠️ Feature eligibility blocked all requested work")
        return {
            "status": "skipped",
            "reason": "feature_eligibility_blocked",
            "eligible_by_tf": eligible_by_tf,
        }

    print("\n🔨 Формирование команды...")
    # Запуск с параметрами (по умолчанию без лимита — все доступные бары)
    # Используем все доступные фичи (specs=None означает все доступные)
    cmd = [
        "python",
        "-u",
        "-m",
        "src.cli.main",
        "features",
        "--timeframes",
        *timeframes,
        "--features-debug",  # Включаем подробные DEBUG-логи расчёта индикаторов
    ]
    # Добавляем --symbols только если указаны конкретные символы (НЕ None и НЕ "None")
    # Проверяем, что normalized_symbols - это непустая строка, не равная "none"/"null"
    if (
        normalized_symbols is not None
        and isinstance(normalized_symbols, str)
        and normalized_symbols.strip().lower() not in ("none", "null", "")
    ):
        cmd.extend(["--symbols", normalized_symbols])
    # Если symbols=None или пустая строка, не добавляем параметр --symbols вообще (обработаются все символы)
    # Добавляем --limit только если он задан
    if normalized_limit is not None:
        cmd.extend(["--limit", str(normalized_limit)])

    print("📝 Команда для выполнения:")
    print(f"   {' '.join(cmd)}")
    print("📁 Рабочая директория: /opt/airflow/project")
    print(f"🔧 Переменные окружения: {len(env)} переменных")

    print(f"\n⏰ Запуск команды в {datetime.now()}...")
    start_time = time.time()

    # Используем Popen для потокового чтения вывода в реальном времени
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # Line buffered
        cwd="/opt/airflow/project",
    )

    # Собираем вывод в реальном времени
    stdout_lines = []
    stderr_lines = []

    # Читаем вывод построчно в реальном времени
    # Для Unix-подобных систем используем threading для потокового чтения
    try:
        import threading

        def read_output(pipe, lines_list, prefix):
            """Читает вывод из pipe и логирует в реальном времени."""
            for line in iter(pipe.readline, ""):
                if line:
                    line = line.rstrip()
                    lines_list.append(line)
                    # Логируем важные строки сразу
                    if any(
                        marker in line
                        for marker in (
                            "💓",
                            "📊",
                            "✅",
                            "❌",
                            "🚀",
                            "📈",
                            "🎯",
                            "⏰",
                            "ERROR",
                            "Exception",
                        )
                    ):
                        print(f"[{prefix}] {line}", flush=True)
            pipe.close()

        stdout_thread = threading.Thread(
            target=read_output, args=(process.stdout, stdout_lines, "STDOUT")
        )
        stderr_thread = threading.Thread(
            target=read_output, args=(process.stderr, stderr_lines, "STDERR")
        )

        stdout_thread.start()
        stderr_thread.start()

        # Ждём завершения процесса
        returncode = process.wait()

        # Ждём завершения потоков чтения
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

    except Exception as e:
        print(f"⚠️ Ошибка при потоковом чтении: {e}, используем обычный режим")
        # Fallback: ждём завершения и читаем весь вывод
        stdout, stderr = process.communicate()
        stdout_lines = stdout.splitlines() if stdout else []
        stderr_lines = stderr.splitlines() if stderr else []
        returncode = process.returncode

    end_time = time.time()
    duration = end_time - start_time

    stdout_joined = "\n".join(stdout_lines)
    stderr_joined = "\n".join(stderr_lines)

    print(f"\n⏱️ Команда завершена за {duration:.2f} секунд")
    print(f"📊 Код возврата: {returncode}")
    print(f"📤 Размер stdout: {len(stdout_joined)} символов, {len(stdout_lines)} строк")
    print(f"📤 Размер stderr: {len(stderr_joined)} символов, {len(stderr_lines)} строк")

    # Создаём объект result для совместимости с существующим кодом
    class Result:
        def __init__(self, returncode, stdout, stderr):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    result = Result(returncode, stdout_joined, stderr_joined)

    def _enhanced_print(stdout: str, stderr: str, ok: bool):
        print("\n" + "=" * 60)
        print("📋 АНАЛИЗ ВЫВОДА КОМАНДЫ")
        print("=" * 60)

        # Печатаем детальную информацию о прогрессе
        stdout_lines = stdout.splitlines() if stdout else []
        stderr_lines = stderr.splitlines() if stderr else []

        print("📊 Статистика вывода:")
        print(f"   - Строк в stdout: {len(stdout_lines)}")
        print(f"   - Строк в stderr: {len(stderr_lines)}")
        print(f"   - Статус выполнения: {'✅ УСПЕХ' if ok else '❌ ОШИБКА'}")

        # Объединяем stdout и stderr для поиска маркеров
        all_lines = stdout_lines + stderr_lines

        # Ключевые маркеры для поиска важной информации
        progress_markers = (
            "🎯",  # Прогресс по символам
            "✅",  # Успешное завершение
            "📊",  # Статистика
            "🔍",  # DEBUG информация
            "FEATURE READY",  # DEBUG: готовность индикаторов
            "FEATURE SUMMARY",  # DEBUG: сводка по заполненности
            "FEATURES_VERBOSE: ON",  # Подтверждение включения verbose режима
            "ИТОГИ ЭТАПА FEATURES",
            "METRICS",
            "features CLI finished OK",
            "ДАННЫЕ ЗАГРУЖЕНЫ В ТАБЛИЦУ indicators",  # Подтверждение загрузки данных
            "DEBUG: Saving Stage A feature",  # DEBUG: сохранение индикаторов
            "🚀 ЗАПУСК ЭТАПА FEATURES",
            "📈 Обработано символов",
            "📊 Обработано баров",
            "🎯 Рассчитано индикаторов",
        )

        error_markers = (
            "❌",
            "ERROR",
            "Критическая ошибка",
            "Exception",
            "Traceback",
            "ModuleNotFoundError",
            "ImportError",
            "AttributeError",
        )

        # Фильтруем строки с прогрессом и результатами из всех источников
        progress_lines = [l for l in all_lines if any(m in l for m in progress_markers)]
        error_lines = [l for l in all_lines if any(m in l for m in error_markers)]

        if progress_lines:
            print(f"\n🎯 НАЙДЕНО {len(progress_lines)} СТРОК С ПРОГРЕССОМ:")
            for i, line in enumerate(progress_lines, 1):
                print(f"   {i:2d}. {line}")

        if error_lines:
            print(f"\n❌ НАЙДЕНО {len(error_lines)} СТРОК С ОШИБКАМИ:")
            for i, line in enumerate(error_lines, 1):
                print(f"   {i:2d}. {line}")

        # Если нет специальных маркеров, показываем последние строки из stdout
        if not progress_lines and not error_lines and stdout_lines:
            print("\n📄 ПОСЛЕДНИЕ 20 СТРОК ИЗ STDOUT:")
            tail = "\n".join(stdout_lines[-20:])
            if tail:
                for i, line in enumerate(stdout_lines[-20:], 1):
                    print(f"   {i:2d}. {line}")

        # Показываем stderr только если есть ошибки или если нет прогресса
        if stderr_lines and (not ok or not progress_lines):
            print("\n⚠️ ПОСЛЕДНИЕ 50 СТРОК ИЗ STDERR:")
            err_tail = "\n".join(stderr_lines[-50:])
            if err_tail:
                for i, line in enumerate(stderr_lines[-50:], 1):
                    print(f"   {i:2d}. {line}")

        print("=" * 60)

    ok = result.returncode == 0
    _enhanced_print(result.stdout, result.stderr, ok)

    print("\n" + "=" * 80)
    print("🏁 ЗАВЕРШЕНИЕ ЗАДАЧИ features_run_task")
    print("=" * 80)

    if not ok:
        print("❌ ЗАДАЧА ЗАВЕРШИЛАСЬ С ОШИБКОЙ")
        print(f"   - Код возврата: {result.returncode}")
        print(f"   - Время выполнения: {duration:.2f} секунд")
        print(f"   - Время завершения: {datetime.now()}")
        raise Exception(f"features CLI failed with code {result.returncode}")

    print("✅ ЗАДАЧА ВЫПОЛНЕНА УСПЕШНО")
    print(f"   - Код возврата: {result.returncode}")
    print(f"   - Время выполнения: {duration:.2f} секунд")
    print(f"   - Время завершения: {datetime.now()}")

    # Краткий итог для Dag логов
    all_output = (result.stdout or "") + (result.stderr or "")
    if "ДАННЫЕ ЗАГРУЖЕНЫ В ТАБЛИЦУ indicators" in all_output:
        all_lines = all_output.splitlines()
        last_lines = [
            l for l in all_lines if "ДАННЫЕ ЗАГРУЖЕНЫ В ТАБЛИЦУ indicators" in l
        ]
        if last_lines:
            print(f"📊 ИТОГОВАЯ СВОДКА: {last_lines[-1]}")

    print("=" * 80)


def smoke_validate_features_task():
    """
    Задача для проверки результатов расчёта features и получения метрик.
    Использует новую систему smoke validation из features модуля.
    """
    # Принудительно сбрасываем буфер для немедленного вывода в логи Airflow
    import sys

    sys.stdout.flush()
    sys.stderr.flush()

    print("=" * 80)
    print("🔍 НАЧАЛО ВЫПОЛНЕНИЯ ЗАДАЧИ smoke_validate_features_task")
    print("=" * 80)
    sys.stdout.flush()  # Гарантируем немедленный вывод

    # Smoke-проверка и метрики по таблице indicators
    import subprocess
    import time
    from pathlib import Path

    print("📋 Параметры задачи:")
    print(f"   - timestamp: {datetime.now()}")
    print("   - цель: проверка результатов расчёта features с новой системой метрик")

    print("\n🔧 Настройка переменных окружения...")
    env = os.environ.copy()
    env["DATABASE_URL"] = _get_database_url()
    env["FEATURES_LOG_FILE"] = "/tmp/pklpo/features.log"
    # Обеспечиваем импорт актуального кода проекта
    env["PYTHONPATH"] = "/opt/airflow/project"
    # Добавляем текущую директорию в PYTHONPATH для корректного импорта модулей
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"/opt/airflow/project:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = "/opt/airflow/project"
    env["TQDM_DISABLE"] = "1"
    # Включаем детальное логирование прогресса
    env["FEATURES_VERBOSE"] = "true"

    print(f"✅ PYTHONPATH: {env['PYTHONPATH']}")
    print(f"✅ DATABASE_URL: {_redact_database_url(env['DATABASE_URL'])}")
    print(f"✅ FEATURES_LOG_FILE: {env['FEATURES_LOG_FILE']}")

    print("\n📁 Создание временных директорий...")
    Path("/tmp/pklpo").mkdir(parents=True, exist_ok=True)
    Path("/tmp/pklpo/data").mkdir(parents=True, exist_ok=True)
    print("✅ Директории созданы: /tmp/pklpo, /tmp/pklpo/data")

    print(f"\n⏰ Запуск enhanced smoke validation в {datetime.now()}...")
    start_time = time.time()
    print("📝 Используем новую систему smoke validation...")
    cmd = [
        "python",
        "-u",
        "-c",
        (
            "import asyncio, sys, traceback, json\n"
            "from datetime import datetime, timedelta, timezone\n"
            "import os\n"
            "from src.database import get_async_session\n"
            "from src.features.smoke_validation import run_smoke_validation, print_smoke_report\n"
            "async def check():\n"
            "    try:\n"
            "        async for session in get_async_session():\n"
            "            results = await run_smoke_validation(session, hours_back=24)\n"
            "            print_smoke_report(results)\n"
            "            # Export metrics for Airflow\n"
            "            metrics_json = json.dumps(results, ensure_ascii=False, default=str)\n"
            "            print(f'[features_calc] METRICS {metrics_json}')\n"
            "            break\n"
            "    except Exception as e:\n"
            "        traceback.print_exc()\n"
            "        sys.exit(1)\n"
            "asyncio.run(check())\n"
        ),
    ]

    print("📝 Команда для выполнения:")
    print("   python -u -c '...'")
    print("📁 Рабочая директория: /opt/airflow/project")

    # Используем Popen для потокового чтения вывода в реальном времени
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # Line buffered
        cwd="/opt/airflow/project",
    )

    # Собираем вывод в реальном времени
    stdout_lines = []
    stderr_lines = []

    # Читаем вывод построчно в реальном времени
    try:
        import threading

        def read_output(pipe, lines_list, prefix):
            """Читает вывод из pipe и логирует в реальном времени."""
            for line in iter(pipe.readline, ""):
                if line:
                    line = line.rstrip()
                    lines_list.append(line)
                    # Логируем все строки сразу для smoke validation
                    print(f"[{prefix}] {line}", flush=True)
            pipe.close()

        stdout_thread = threading.Thread(
            target=read_output, args=(process.stdout, stdout_lines, "STDOUT")
        )
        stderr_thread = threading.Thread(
            target=read_output, args=(process.stderr, stderr_lines, "STDERR")
        )

        stdout_thread.start()
        stderr_thread.start()

        # Ждём завершения процесса
        returncode = process.wait()

        # Ждём завершения потоков чтения
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

    except Exception as e:
        print(f"⚠️ Ошибка при потоковом чтении: {e}, используем обычный режим")
        # Fallback: ждём завершения и читаем весь вывод
        stdout, stderr = process.communicate()
        stdout_lines = stdout.splitlines() if stdout else []
        stderr_lines = stderr.splitlines() if stderr else []
        returncode = process.returncode

    end_time = time.time()
    duration = end_time - start_time

    stdout_joined = "\n".join(stdout_lines)
    stderr_joined = "\n".join(stderr_lines)

    print(f"\n⏱️ Smoke validation завершена за {duration:.2f} секунд")
    print(f"📊 Код возврата: {returncode}")
    print(f"📤 Размер stdout: {len(stdout_joined)} символов, {len(stdout_lines)} строк")
    print(f"📤 Размер stderr: {len(stderr_joined)} символов, {len(stderr_lines)} строк")

    # Создаём объект result для совместимости с существующим кодом
    class Result:
        def __init__(self, returncode, stdout, stderr):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    result = Result(returncode, stdout_joined, stderr_joined)

    print("\n" + "=" * 80)
    print("🏁 ЗАВЕРШЕНИЕ ЗАДАЧИ smoke_validate_features_task")
    print("=" * 80)

    if result.returncode != 0:
        print("❌ ЗАДАЧА ЗАВЕРШИЛАСЬ С ОШИБКОЙ")
        print(f"   - Код возврата: {result.returncode}")
        print(f"   - Время выполнения: {duration:.2f} секунд")
        print(f"   - Время завершения: {datetime.now()}")
        if result.stderr:
            print("\n⚠️ STDERR (последние 20 строк):")
            for line in result.stderr.splitlines()[-20:]:
                print(f"   {line}")
        raise Exception(f"features validation failed with code {result.returncode}")

    print("✅ ЗАДАЧА ВЫПОЛНЕНА УСПЕШНО")
    print(f"   - Код возврата: {result.returncode}")
    print(f"   - Время выполнения: {duration:.2f} секунд")
    print(f"   - Время завершения: {datetime.now()}")
    print("=" * 80)


def _run_async(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _resolve_feature_eligible_work_items(
    normalized_symbols: str | None,
    timeframes: list[str],
) -> dict[str, list[str]]:
    from src.candles.interfaces import eligibility as eligibility_interface

    requested_symbols = (
        [item for item in normalized_symbols.split(",") if item]
        if normalized_symbols is not None
        else None
    )
    eligible_by_tf: dict[str, list[str]] = {}
    for timeframe in timeframes:
        if requested_symbols is None:
            eligible_by_tf[timeframe] = await eligibility_interface.eligible_symbols(
                timeframe
            )
            continue
        eligible_symbols: list[str] = []
        for symbol in requested_symbols:
            record = await eligibility_interface.get_state(symbol, timeframe)
            if record is None:
                print(f"Feature eligibility missing for {symbol}/{timeframe} — skipping (fail close)")
                continue
            if record.can_compute_features:
                eligible_symbols.append(symbol)
        eligible_by_tf[timeframe] = eligible_symbols
    return eligible_by_tf


def combinations_run_task(
    symbols: str | None = None, timeframes=None, limit: int | None = None
):
    """
    Задача для запуска расчёта комбинаций фичей через CLI.
    """
    import sys

    sys.stdout.flush()
    sys.stderr.flush()

    print("=" * 80)
    print("🚀 НАЧАЛО ВЫПОЛНЕНИЯ ЗАДАЧИ combinations_run_task")
    print("=" * 80)
    sys.stdout.flush()

    import subprocess

    # Нормализуем параметры
    if isinstance(symbols, str) and symbols.strip().lower() in ("none", "null", ""):
        symbols = None

    if isinstance(timeframes, str):
        timeframes = [tf.strip() for tf in timeframes.split(",") if tf.strip()]
    elif timeframes is None:
        timeframes = ["1m", "5m", "15m", "30m", "1H", "4H", "12H", "1D"]

    normalized_limit = None
    if limit is not None:
        if isinstance(limit, str) and limit.strip().lower() in ("none", "null", ""):
            normalized_limit = None
        else:
            try:
                normalized_limit = int(limit)
            except (ValueError, TypeError):
                normalized_limit = None

    print("📋 Входные параметры:")
    print(f"   - symbols: {symbols}")
    print(f"   - timeframes: {timeframes}")
    print(f"   - limit: {normalized_limit}")
    sys.stdout.flush()

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    # Строим команду для каждого symbol×timeframe
    total_saved = 0
    errors = []

    # Если symbols не указаны, получаем список из БД
    if symbols is None:
        from sqlalchemy import text

        from src.utils.session_utils import get_db_session

        async def get_symbols():
            async with get_db_session() as session:
                query = text("SELECT DISTINCT symbol FROM swap_ohlcv_p ORDER BY symbol")
                result = await session.execute(query)
                return [row[0] for row in result.all()]

        import asyncio

        symbol_list = asyncio.run(get_symbols())
    else:
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]

    print(f"📊 Обработка {len(symbol_list)} символов × {len(timeframes)} таймфреймов")
    sys.stdout.flush()

    for symbol in symbol_list:
        for timeframe in timeframes:
            try:
                cmd = [
                    "python",
                    "-u",
                    "-m",
                    "src.features_combinations.cli",
                    "compute-latest",
                    "--symbol",
                    symbol,
                    "--timeframes",
                    timeframe,
                ]

                if normalized_limit is not None:
                    cmd.extend(["--limit", str(normalized_limit)])

                print(f"\n🔄 {symbol}/{timeframe}...")
                sys.stdout.flush()

                result = subprocess.run(
                    cmd,
                    env=env,
                    cwd="/opt/airflow/project",
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 минут на комбинацию
                )

                if result.returncode == 0:
                    # Парсим количество сохранённых строк из вывода
                    for line in result.stdout.splitlines():
                        if "Total saved:" in line or "saved" in line.lower():
                            print(f"   {line}")
                    print(f"   ✅ {symbol}/{timeframe} completed")
                else:
                    error_msg = f"{symbol}/{timeframe}: {result.stderr[-200:]}"
                    errors.append(error_msg)
                    print(f"   ❌ {symbol}/{timeframe} failed: {error_msg}")
                sys.stdout.flush()

            except subprocess.TimeoutExpired:
                errors.append(f"{symbol}/{timeframe}: timeout")
                print(f"   ⏱️ {symbol}/{timeframe} timeout")
            except Exception as e:
                errors.append(f"{symbol}/{timeframe}: {e}")
                print(f"   ❌ {symbol}/{timeframe} error: {e}")

    print("\n" + "=" * 80)
    if errors:
        print(f"⚠️ Ошибки ({len(errors)}):")
        for err in errors[:10]:  # Показываем первые 10
            print(f"   {err}")
        if len(errors) > 10:
            print(f"   ... и ещё {len(errors) - 10} ошибок")
    print("✅ ЗАДАЧА ВЫПОЛНЕНА")
    print("=" * 80)

    if errors:
        raise Exception(f"Combinations calculation completed with {len(errors)} errors")


# Configure default_args with alerting (FEAT-002)
default_args = {
    "owner": "features_calc",
    "retries": 2,  # Increased from 0 for better resilience
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),  # Prevent hanging tasks
    "sla": timedelta(hours=1),  # SLA: tasks should complete within 1 hour
}

# Add alerting callbacks if available (FEAT-002)
if ALERTS_AVAILABLE:
    default_args["on_failure_callback"] = combined_failure_callback
    default_args["sla_miss_callback"] = combined_sla_miss_callback
    # Optional: uncomment to get success notifications
    # default_args["on_success_callback"] = success_callback

    # Email configuration (if SMTP is configured in Airflow)
    default_args["email_on_failure"] = True
    default_args["email_on_retry"] = False  # Don't spam on retries
    default_args["email"] = os.getenv(
        "AIRFLOW_ALERT_EMAIL", "data-team@company.com"
    ).split(",")

    print("✅ Alerting enabled for features_calc DAG")
else:
    print("⚠️ Alerting disabled for features_calc DAG")


with DAG(
    dag_id="features_calc",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    default_args=default_args,
    # Параметры DAG с дефолтами; могут быть переопределены через dag_run.conf
    params={
        # None или "none" = все символы из swap_ohlcv_p
        # Конкретный символ или список через запятую = только указанные
        "symbols": None,
        # Используем строку, которую потом распарсим в функции задачи
        "timeframes": "1m,5m,15m,30m,1H,4H,12H,1D,1W,1M",
        # None или "none" = все доступные бары (без лимита)
        # Число = только последние N свечей
        "limit": None,
    },
    description="Features calculation DAG with alerting (FEAT-002)",
    tags=["features", "calculation", "ml", "monitored"],  # Added tags for filtering
) as dag:
    features_run = PythonOperator(
        task_id="features_run",
        python_callable=features_run_task,
        pool="compute_pool",
        pool_slots=1,
        op_kwargs={
            # Позволяем переопределять через dag_run.conf, иначе берём из params
            "symbols": "{{ dag_run.conf.get('symbols', params.symbols) }}",
            "timeframes": "{{ dag_run.conf.get('timeframes', params.timeframes) }}",
            "limit": "{{ dag_run.conf.get('limit', params.limit) }}",
        },
    )

    smoke_validate_features = PythonOperator(
        task_id="smoke_validate_features",
        python_callable=smoke_validate_features_task,
    )

    combinations_run = PythonOperator(
        task_id="combinations_run",
        python_callable=combinations_run_task,
        pool="compute_pool",
        pool_slots=1,
        op_kwargs={
            "symbols": "{{ dag_run.conf.get('symbols', params.symbols) }}",
            "timeframes": "{{ dag_run.conf.get('timeframes', params.timeframes) }}",
            "limit": "{{ dag_run.conf.get('limit', params.limit) }}",
        },
    )

    # Цепочка: features_run → smoke_validate_features → combinations_run
    features_run >> smoke_validate_features >> combinations_run
