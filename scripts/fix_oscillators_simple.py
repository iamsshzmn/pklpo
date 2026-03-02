#!/usr/bin/env python3
"""
Простой скрипт для исправления файла oscillators.py
"""

# Читаем файл
with open("src/features/indicator_groups/oscillators.py", encoding="utf-8") as f:
    content = f.read()

# Исправляем все сломанные вызовы
# Паттерн: safe_ta_call("function_name(param1, param2, ...)
# Заменяем на: safe_ta_call("function_name", param1, param2, ...)

import re


# Находим все сломанные вызовы и исправляем их
def fix_call(match):
    full_match = match.group(0)
    # Извлекаем имя функции
    func_name = full_match.split("(")[0].split('"')[1]
    # Извлекаем параметры
    params = full_match.split("(")[1].rstrip(")")
    # Формируем правильный вызов
    return f'safe_ta_call("{func_name}", {params})'


# Применяем исправления
content = re.sub(r'safe_ta_call\("([^"]+)\(([^)]+)\)', fix_call, content)

# Записываем исправленный файл
with open("src/features/indicator_groups/oscillators.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Файл oscillators.py исправлен!")
