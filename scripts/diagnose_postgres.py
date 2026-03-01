"""Диагностика подключения к PostgreSQL."""

import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

# Устанавливаем кодировку для Windows
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Загружаем переменные окружения
try:
    from dotenv import load_dotenv

    load_dotenv()
    from src.config.env_validator import get_database_url

    DB_URL = get_database_url()
    parsed = urlparse(DB_URL.replace("postgresql+asyncpg://", "postgresql://"))
    DB_USER = parsed.username or "pklpo_user"
    DB_NAME = parsed.path.lstrip("/") or "pklpo"
except Exception:
    # Fallback значения
    DB_USER = "pklpo_user"
    DB_NAME = "pklpo"


def run_command(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Выполнить команду и вернуть код возврата, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",  # Заменяем невалидные символы
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout after {timeout}s"
    except FileNotFoundError:
        return -1, "", "Command not found"
    except Exception as e:
        return -1, "", str(e)


def check_port_listener():
    """Проверка, кто слушает порт 5432."""
    print("\n" + "=" * 60)
    print("1. Проверка, кто слушает порт 5432")
    print("=" * 60)

    # Windows: netstat -ano | findstr :5432
    if sys.platform == "win32":
        code, out, err = run_command(["netstat", "-ano"], timeout=5)
        if code == 0 and out:
            lines = [l for l in out.split("\n") if ":5432" in l and "LISTENING" in l]
            if lines:
                print("[OK] Найдены процессы, слушающие порт 5432:")
                for line in lines:
                    print(f"  {line.strip()}")
                    # Извлекаем PID
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        # Проверяем, что это за процесс
                        code2, out2, _ = run_command(
                            ["tasklist", "/FI", f"PID eq {pid}"], timeout=3
                        )
                        if code2 == 0 and out2:
                            proc_lines = [
                                l for l in out2.split("\n") if pid in l and ".exe" in l
                            ]
                            if proc_lines:
                                proc_name = proc_lines[0].strip()
                                # Убираем невалидные символы для вывода
                                proc_name = proc_name.encode(
                                    "ascii", errors="replace"
                                ).decode("ascii")
                                print(f"    Процесс: {proc_name}")
            else:
                print("[WARNING] Не найдено процессов, слушающих порт 5432")
        else:
            print(f"[ERROR] Ошибка выполнения netstat: {err}")
    else:
        # Linux/Mac
        code, out, err = run_command(["lsof", "-i", ":5432"], timeout=5)
        if code == 0 and out:
            print("[OK] Процессы на порту 5432:")
            print(out)
        else:
            print("[WARNING] Не удалось проверить процессы на порту 5432")


def check_docker_container():
    """Проверка Docker контейнера."""
    print("\n" + "=" * 60)
    print("2. Проверка Docker контейнера pklpo_db")
    print("=" * 60)

    code, out, err = run_command(["docker", "ps"], timeout=5)
    if code != 0:
        print(f"[ERROR] Docker недоступен: {err}")
        return False

    if "pklpo_db" in out:
        print("[OK] Контейнер pklpo_db найден")
        # Ищем строку с pklpo_db
        for line in out.split("\n"):
            if "pklpo_db" in line:
                print(f"  {line.strip()}")
                # Проверяем порты
                if "5432->5432" in line or ":5432->" in line:
                    print("[OK] Порт 5432 проброшен правильно")
                else:
                    print(
                        "[WARNING] Порт 5432 не проброшен или проброшен на другой порт"
                    )
                    print("  Проверьте docker-compose.yml")
    else:
        print("[WARNING] Контейнер pklpo_db не найден в запущенных контейнерах")
        print("[INFO] Попробуйте: docker-compose up -d db")

    return True


def check_docker_logs():
    """Проверка логов контейнера."""
    print("\n" + "=" * 60)
    print("3. Проверка логов контейнера pklpo_db")
    print("=" * 60)

    code, out, err = run_command(
        ["docker", "logs", "pklpo_db", "--tail", "30"], timeout=5
    )
    if code == 0:
        if "ready to accept connections" in out.lower():
            print("[OK] PostgreSQL готов принимать подключения")
        elif "error" in out.lower() or "fatal" in out.lower():
            print("[ERROR] Обнаружены ошибки в логах:")
            error_lines = [
                l
                for l in out.split("\n")
                if "error" in l.lower() or "fatal" in l.lower()
            ]
            for line in error_lines[:5]:
                print(f"  {line.strip()}")
        else:
            print("[INFO] Последние строки логов:")
            print(out[-500:] if len(out) > 500 else out)
    else:
        print(f"[WARNING] Не удалось получить логи: {err}")


def check_container_connection():
    """Проверка подключения изнутри контейнера."""
    print("\n" + "=" * 60)
    print("4. Проверка подключения изнутри контейнера")
    print("=" * 60)

    # Проверяем подключение под правильным пользователем
    print(f"[INFO] Пробую подключение: {DB_USER}/{DB_NAME}")
    code, out, err = run_command(
        [
            "docker",
            "exec",
            "pklpo_db",
            "psql",
            "-U",
            DB_USER,
            "-d",
            DB_NAME,
            "-c",
            "SELECT 1;",
        ],
        timeout=5,
    )
    if code == 0:
        print(f"[OK] Подключение из контейнера работает ({DB_USER}/{DB_NAME})")
    else:
        print(f"[ERROR] Не удалось подключиться из контейнера: {err}")
        print(f"[INFO] Использовались параметры: user={DB_USER}, db={DB_NAME}")


def check_postgres_settings():
    """Проверка настроек PostgreSQL."""
    print("\n" + "=" * 60)
    print("5. Проверка настроек PostgreSQL")
    print("=" * 60)

    # listen_addresses
    print(f"[INFO] Проверяю настройки под пользователем: {DB_USER}")
    code, out, err = run_command(
        [
            "docker",
            "exec",
            "pklpo_db",
            "psql",
            "-U",
            DB_USER,
            "-d",
            DB_NAME,
            "-c",
            "SHOW listen_addresses;",
        ],
        timeout=5,
    )
    if code == 0:
        print("[INFO] listen_addresses:")
        print(out)
        if "*" in out or "0.0.0.0" in out:
            print("[OK] PostgreSQL слушает на всех адресах")
        elif "localhost" in out.lower() or "127.0.0.1" in out:
            print("[WARNING] PostgreSQL слушает только на localhost")
            print("  Это может мешать внешним подключениям")
    else:
        print(f"[WARNING] Не удалось проверить listen_addresses: {err}")

    # pg_hba.conf
    code, out, err = run_command(
        [
            "docker",
            "exec",
            "pklpo_db",
            "bash",
            "-c",
            "cat /var/lib/postgresql/data/pg_hba.conf | grep -v '^#' | grep -v '^$'",
        ],
        timeout=5,
    )
    if code == 0 and out.strip():
        print("\n[INFO] pg_hba.conf (активные строки):")
        print(out)
    else:
        print("[WARNING] Не удалось прочитать pg_hba.conf")


def check_env_vars():
    """Проверка переменных окружения в контейнере."""
    print("\n" + "=" * 60)
    print("6. Проверка переменных окружения")
    print("=" * 60)

    print("[INFO] Используемые параметры подключения:")
    print(f"  POSTGRES_USER: {DB_USER}")
    print(f"  POSTGRES_DB: {DB_NAME}")
    print("  (из .env или переменных окружения)")

    code, out, err = run_command(["docker", "exec", "pklpo_db", "printenv"], timeout=5)
    if code == 0:
        postgres_vars = [l for l in out.split("\n") if "POSTGRES" in l]
        if postgres_vars:
            print("\n[INFO] Переменные окружения в контейнере:")
            for var in postgres_vars:
                # Маскируем пароль
                if "PASSWORD" in var:
                    key, _ = var.split("=", 1)
                    print(f"  {key}=***")
                else:
                    print(f"  {var}")
        else:
            print("[WARNING] Не найдены переменные POSTGRES_* в контейнере")
    else:
        print(f"[WARNING] Не удалось получить переменные окружения: {err}")


def check_docker_compose():
    """Проверка docker-compose.yml."""
    print("\n" + "=" * 60)
    print("7. Проверка docker-compose.yml")
    print("=" * 60)

    compose_file = Path("docker-compose.yml")
    if compose_file.exists():
        content = compose_file.read_text(encoding="utf-8")
        if "pklpo_db" in content or "db:" in content:
            print("[OK] docker-compose.yml найден")
            # Ищем настройки портов
            if '"5432:5432"' in content or "'5432:5432'" in content:
                print("[OK] Порт 5432:5432 настроен")
            else:
                print("[WARNING] Порт 5432:5432 не найден в конфигурации")
                # Ищем другие порты
                import re

                port_matches = re.findall(r'"(\d+):5432"', content)
                if port_matches:
                    print(f"[INFO] Найден другой внешний порт: {port_matches[0]}:5432")
        else:
            print("[WARNING] docker-compose.yml не содержит настройки для db")
    else:
        print("[WARNING] docker-compose.yml не найден")


def main():
    """Основная функция диагностики."""
    print("=" * 60)
    print("Диагностика подключения к PostgreSQL")
    print("=" * 60)
    print("[INFO] Параметры подключения:")
    print(f"  Пользователь: {DB_USER}")
    print(f"  База данных: {DB_NAME}")
    print()

    check_port_listener()
    if check_docker_container():
        check_docker_logs()
        check_container_connection()
        check_postgres_settings()
        check_env_vars()
    check_docker_compose()

    print("\n" + "=" * 60)
    print("Диагностика завершена")
    print("=" * 60)
    print("\nРекомендации:")
    print("1. Если контейнер не запущен: docker-compose up -d db")
    print("2. Если порт не проброшен: проверьте docker-compose.yml")
    print("3. Если есть ошибки в логах: исправьте их и перезапустите")
    print("4. Если listen_addresses = 'localhost': настройте на '*' или '0.0.0.0'")
    print("5. Если pg_hba.conf не разрешает подключения: добавьте строку:")
    print("   host    all    all    0.0.0.0/0    md5")


if __name__ == "__main__":
    main()
