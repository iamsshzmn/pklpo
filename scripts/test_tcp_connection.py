"""Тест TCP соединения с PostgreSQL."""

import socket
import sys

# На Windows используем правильную политику event loop
if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def test_tcp_connection():
    """Проверка TCP соединения с портом 5432."""
    print("[INFO] Проверяю TCP соединение с localhost:5432...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("localhost", 5432))
        sock.close()

        if result == 0:
            print("[OK] TCP соединение с портом 5432 установлено")
            return True
        print(f"[ERROR] Не удалось установить TCP соединение (код: {result})")
        return False
    except Exception as e:
        print(f"[ERROR] Ошибка TCP соединения: {e}")
        return False


def test_tcp_ipv4():
    """Проверка TCP соединения с 127.0.0.1:5432."""
    print("\n[INFO] Проверяю TCP соединение с 127.0.0.1:5432...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("127.0.0.1", 5432))
        sock.close()

        if result == 0:
            print("[OK] TCP соединение с 127.0.0.1:5432 установлено")
            return True
        print(f"[ERROR] Не удалось установить TCP соединение (код: {result})")
        return False
    except Exception as e:
        print(f"[ERROR] Ошибка TCP соединения: {e}")
        return False


if __name__ == "__main__":
    test_tcp_connection()
    test_tcp_ipv4()
