#!/usr/bin/env python3
"""
Скрипт для исправления файла oscillators.py
"""

import re

# Читаем файл
with open("src/features/indicator_groups/oscillators.py", encoding="utf-8") as f:
    content = f.read()

# Исправляем все сломанные вызовы
# Паттерн: safe_ta_call("function_name(param1, param2, ...)
# Заменяем на: safe_ta_call("function_name", param1, param2, ...)


def fix_safe_ta_call(match):
    full_call = match.group(0)
    # Извлекаем имя функции и параметры
    func_name = full_call.split("(")[0].split('"')[1]
    params = full_call.split("(")[1].rstrip(")")

    # Формируем правильный вызов
    return f'safe_ta_call("{func_name}", {params})'


# Применяем исправления
content = re.sub(r'safe_ta_call\("([^"]+)\(([^)]+)\)', fix_safe_ta_call, content)

# Записываем исправленный файл
with open("src/features/indicator_groups/oscillators.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Файл oscillators.py исправлен!")
