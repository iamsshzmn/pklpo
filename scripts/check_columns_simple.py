#!/usr/bin/env python3
"""
Простая проверка колонок через SQL запрос
"""

import subprocess


def check_columns():
    """Проверить колонки через psql."""
    print("Проверка колонок в таблице indicators...")

    # SQL запрос для проверки колонок
    sql_query = """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'indicators'
    AND table_schema = 'public'
    ORDER BY column_name;
    """

    try:
        # Выполняем запрос через psql
        cmd = [
            "psql",
            "-h",
            "localhost",
            "-p",
            "5432",
            "-U",
            "pklpo_user",
            "-d",
            "pklpo",
            "-c",
            sql_query,
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, input="strongpassword\n"
        )

        if result.returncode == 0:
            print("Колонки в таблице indicators:")
            print(result.stdout)

            # Проверяем наличие hl2
            if "hl2" in result.stdout:
                print("✅ Колонка hl2 найдена")
            else:
                print("❌ Колонка hl2 НЕ найдена")

        else:
            print(f"Ошибка выполнения запроса: {result.stderr}")

    except FileNotFoundError:
        print("psql не найден. Попробуем другой способ...")
        return False
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

    return True


if __name__ == "__main__":
    check_columns()
