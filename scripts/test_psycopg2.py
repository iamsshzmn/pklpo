"""Тест подключения через psycopg2 (синхронный драйвер)."""

import signal
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

from src.config.env_validator import get_database_url


def test_psycopg2():
    """Тест подключения через psycopg2 с подробным логированием."""

    def timeout_handler(signum, frame):
        print("\n[ERROR] Timeout! Подключение зависло более 30 секунд")
        sys.exit(1)

    try:
        import psycopg2

        db_url = get_database_url()
        print(
            f"[INFO] Тестирую подключение: {db_url.split('@')[-1] if '@' in db_url else db_url[:50]}"
        )

        # Парсим URL
        parsed = urlparse(db_url.replace("postgresql+asyncpg://", "postgresql://"))

        # Принудительно используем IPv4 вместо localhost для избежания проблем с IPv6
        original_host = parsed.hostname or "localhost"
        host = "127.0.0.1" if original_host == "localhost" else original_host
        port = parsed.port or 5432
        user = parsed.username
        database = parsed.path.lstrip("/")

        print("[INFO] Параметры подключения:")
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  User: {user}")
        print(f"  Password: {'установлен' if parsed.password else 'не установлен'}")
        print(f"  Database: {database}")

        # Проверяем, запущен ли Docker контейнер
        print("\n[INFO] Проверяю статус Docker контейнера...")
        import subprocess

        try:
            # Сначала быстрая проверка через docker ps без фильтра
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                if "pklpo_db" in result.stdout:
                    print("[OK] Контейнер pklpo_db запущен")
                else:
                    print("[WARNING] Контейнер pklpo_db не найден в списке запущенных")
                    print("[INFO] Попробуйте: docker-compose up -d db")
            else:
                print("[WARNING] Не удалось проверить статус контейнеров")
        except subprocess.TimeoutExpired:
            print("[WARNING] Проверка Docker заняла слишком много времени")
            print("[INFO] Docker может быть недоступен или медленно отвечает")
        except FileNotFoundError:
            print("[INFO] Docker не найден, возможно PostgreSQL запущен локально")
        except Exception as e:
            print(
                f"[WARNING] Ошибка проверки контейнера: {type(e).__name__}: {str(e)[:100]}"
            )

        # Сначала проверяем TCP соединение
        print("\n[INFO] Проверяю TCP соединение...")
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                print("[OK] TCP соединение установлено")
            else:
                print(f"[ERROR] TCP соединение не установлено (код: {result})")
                print(
                    "[INFO] Убедитесь, что PostgreSQL запущен и слушает на порту 5432"
                )
                return False
        except Exception as e:
            print(f"[ERROR] Ошибка TCP соединения: {e}")
            return False

        print("\n[INFO] Начинаю подключение через psycopg2...")

        # Устанавливаем таймаут для сигнала (только на Unix)
        if hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)

        try:
            # Пробуем подключиться с таймаутом
            print("[INFO] Вызываю psycopg2.connect()...")
            print(
                f"[DEBUG] Параметры: host={host}, port={port}, user={user}, db={database}"
            )
            print("[DEBUG] Используем IPv4 адрес для избежания проблем с IPv6")

            # Пробуем подключиться с принудительным использованием IPv4
            connection_params = {
                "host": host,
                "port": port,
                "user": user,
                "password": parsed.password,
                "database": database,
                "connect_timeout": 10,
            }

            # Пробуем разные варианты подключения
            print("[DEBUG] Пробую подключение с параметрами...")

            # Сначала пробуем без hostaddr
            try:
                print("[DEBUG] Попытка 1: без hostaddr")
                conn = psycopg2.connect(**connection_params)
            except psycopg2.OperationalError as e:
                if "timeout" in str(e).lower() and host == "127.0.0.1":
                    # Если таймаут и используем IPv4, пробуем с явным указанием hostaddr
                    print("[DEBUG] Попытка 2: с hostaddr=127.0.0.1")
                    connection_params["hostaddr"] = "127.0.0.1"
                    conn = psycopg2.connect(**connection_params)
                else:
                    raise
            print("[OK] Подключение через psycopg2 успешно!")

            print("[INFO] Создаю курсор...")
            cur = conn.cursor()

            print("[INFO] Выполняю запрос SELECT 1...")
            cur.execute("SELECT 1")

            print("[INFO] Получаю результат...")
            result = cur.fetchone()
            print(f"[OK] Запрос выполнен: {result}")

            print("[INFO] Закрываю курсор...")
            cur.close()

            print("[INFO] Закрываю соединение...")
            conn.close()
            print("[OK] Все операции завершены успешно!")

            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)  # Отменяем таймаут
            return True
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            print(f"[ERROR] Ошибка подключения: {error_msg}")
            print(f"[ERROR] Тип ошибки: {type(e).__name__}")

            # Детальная диагностика
            if "timeout" in error_msg.lower():
                print("\n[DIAGNOSTIC] Проблема с таймаутом подключения:")
                print("  - PostgreSQL может быть не настроен для приема подключений")
                print("  - Проверьте pg_hba.conf настройки в Docker контейнере")
                print(
                    "  - Проверьте, что PostgreSQL слушает на 0.0.0.0:5432 (внутри контейнера)"
                )
                print("\n[SOLUTION] Попробуйте выполнить в контейнере:")
                print(
                    '  docker exec -it pklpo_db psql -U postgres -c "SHOW listen_addresses;"'
                )
                print(
                    "  docker exec -it pklpo_db cat /var/lib/postgresql/data/pg_hba.conf | grep -v '^#'"
                )
                print("\n[SOLUTION] Или перезапустите контейнер:")
                print("  docker-compose restart db")
                print("  docker-compose logs db | tail -20")
            elif (
                "authentication" in error_msg.lower() or "password" in error_msg.lower()
            ):
                print("\n[DIAGNOSTIC] Проблема с аутентификацией:")
                print("  - Проверьте правильность пароля")
                print("  - Проверьте настройки pg_hba.conf")
            elif "refused" in error_msg.lower():
                print("\n[DIAGNOSTIC] Подключение отклонено:")
                print("  - PostgreSQL может быть не запущен")
                print("  - Порт может быть заблокирован")

            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            return False
        except Exception as e:
            print(f"[ERROR] Неожиданная ошибка: {type(e).__name__}: {e}")
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            import traceback

            traceback.print_exc()
            return False
    except ImportError:
        print("[WARNING] psycopg2 не установлен, пропускаю тест")
        return None
    except Exception as e:
        print(f"[ERROR] Критическая ошибка: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_psycopg2()
