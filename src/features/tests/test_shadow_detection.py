"""
Тест для обнаружения теневых вызовов (name shadowing).

Этот тест проверяет, что в коде нет ситуаций типа:
rsi = ta.rsi(...)
rsi(...)  # <- это вызов функции, а не переменной!
"""

import inspect
import re
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.features import ta_safe


def test_no_callable_shadow():
    """
    Тест, ловящий 'callable после присваивания'.

    Ищет паттерны:
    1. variable = ta.function(...)
    2. variable(...)  # вызов переменной как функции
    """
    bad_patterns: list[tuple[str, set[str]]] = []

    # Получаем все модули features
    features_modules = [
        "src.features.indicator_groups.ma",
        "src.features.indicator_groups.oscillators",
        "src.features.indicator_groups.volatility",
        "src.features.indicator_groups.volume",
        "src.features.indicator_groups.trend",
        "src.features.indicator_groups.squeeze",
        "src.features.indicator_groups.candles",
        "src.features.indicator_groups.statistics",
        "src.features.indicator_groups.performance",
        "src.features.indicator_groups.overlap",
    ]

    for module_name in features_modules:
        try:
            module = __import__(module_name, fromlist=[""])

            # Проверяем все функции в модуле
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if name.startswith("calc_"):
                    try:
                        source = inspect.getsource(obj)
                        bad_vars = find_shadow_variables(source, name)
                        if bad_vars:
                            bad_patterns.append((f"{module_name}.{name}", bad_vars))
                    except (OSError, TypeError):
                        # Не можем получить исходный код (например, для C-функций)
                        continue

        except ImportError:
            # Модуль не найден, пропускаем
            continue

    # Проверяем, что нет плохих паттернов
    assert not bad_patterns, f"Найдены теневые вызовы: {bad_patterns}"


def find_shadow_variables(source: str, function_name: str) -> set[str]:
    """
    Находит переменные, которые могут быть вызваны как функции.

    Args:
        source: Исходный код функции
        function_name: Имя функции для отладки

    Returns:
        Множество проблемных переменных
    """
    bad_vars = set()

    # Паттерн 1: variable = ta.function(...)
    ta_assignments = re.findall(r"(\w+)\s*=\s*ta\.\w+\([^)]*\)", source)

    # Паттерн 2: variable(...) - вызов переменной
    for var_name in ta_assignments:
        # Ищем вызовы этой переменной как функции
        call_pattern = rf"\b{re.escape(var_name)}\s*\("
        if re.search(call_pattern, source):
            bad_vars.add(var_name)

    # Паттерн 3: safe_ta_call с неправильным именованием
    # Ищем: variable = safe_ta_call("function", ...)
    # Затем: variable(...)
    safe_assignments = re.findall(
        r'(\w+)\s*=\s*safe_ta_call\("[^"]+",\s*[^)]*\)', source
    )
    for var_name in safe_assignments:
        call_pattern = rf"\b{re.escape(var_name)}\s*\("
        if re.search(call_pattern, source):
            bad_vars.add(var_name)

    return bad_vars


def test_naming_conventions():
    """
    Тест правил именования переменных.

    Проверяет, что переменные с результатами pandas_ta имеют правильные суффиксы:
    - _val для pd.Series
    - _df для pd.DataFrame
    - _series для pd.Series (альтернатива)
    """
    violations = []

    # Паттерны для поиска неправильного именования

    # Проверяем файлы индикаторов
    indicator_files = [
        "src/features/indicator_groups/ma.py",
        "src/features/indicator_groups/oscillators.py",
        "src/features/indicator_groups/volatility.py",
        "src/features/indicator_groups/volume.py",
    ]

    for file_path in indicator_files:
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Ищем переменные, которые не следуют конвенциям
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                # Пропускаем комментарии и пустые строки
                if line.strip().startswith("#") or not line.strip():
                    continue

                # Ищем присваивания результатов pandas_ta
                if "= ta." in line or "= safe_ta_call(" in line:
                    # Проверяем, что переменная имеет правильный суффикс
                    var_match = re.search(r"(\w+)\s*=", line)
                    if var_match:
                        var_name = var_match.group(1)
                        if not (
                            var_name.endswith("_val")
                            or var_name.endswith("_df")
                            or var_name.endswith("_series")
                        ):
                            violations.append(
                                f"{file_path}:{i} - {var_name} не следует конвенциям именования"
                            )

        except FileNotFoundError:
            continue

    # Проверяем, что нет нарушений
    assert not violations, f"Нарушения конвенций именования: {violations}"


def test_no_direct_ta_imports():
    """
    Тест, что нет прямых импортов pandas_ta в модулях индикаторов.

    Проверяет, что все вызовы идут через ta_safe.py фасад.
    """
    violations = []

    indicator_files = [
        "src/features/indicator_groups/ma.py",
        "src/features/indicator_groups/oscillators.py",
        "src/features/indicator_groups/volatility.py",
        "src/features/indicator_groups/volume.py",
        "src/features/indicator_groups/trend.py",
        "src/features/indicator_groups/squeeze.py",
        "src/features/indicator_groups/candles.py",
        "src/features/indicator_groups/statistics.py",
        "src/features/indicator_groups/performance.py",
        "src/features/indicator_groups/overlap.py",
    ]

    for file_path in indicator_files:
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Ищем прямые вызовы ta.
            ta_calls = re.findall(r"ta\.\w+\(", content)
            if ta_calls:
                violations.append(
                    f"{file_path}: найдены прямые вызовы ta.*: {ta_calls}"
                )

            # Ищем импорты pandas_ta
            if "import pandas_ta" in content or "from pandas_ta import" in content:
                violations.append(f"{file_path}: найден прямой импорт pandas_ta")

        except FileNotFoundError:
            continue

    # Проверяем, что нет нарушений
    assert not violations, f"Найдены прямые вызовы pandas_ta: {violations}"


def test_ta_safe_facade_completeness():
    """
    Тест полноты фасада ta_safe.py.

    Проверяет, что все необходимые функции доступны в фасаде.
    """
    required_functions = [
        "rsi_val",
        "macd_df",
        "bbands_df",
        "kc_df",
        "atr_val",
        "stoch_df",
        "adx_df",
        "ema_val",
        "sma_val",
        "stochrsi_df",
        "ao_val",
        "apo_val",
        "bop_val",
        "kdj_df",
        "rsx_val",
        "tsi_df",
        "fisher_df",
        "slope_val",
        "bias_val",
        "brar_df",
        "cfo_val",
        "cg_val",
        "coppock_val",
        "er_val",
        "eri_df",
        "inertia_val",
        "pgo_val",
        "psl_val",
        "pvo_df",
        "qqe_df",
        "rvgi_df",
        "smi_df",
        "uo_val",
        "obv_val",
        "ad_val",
        "adosc_val",
        "cmf_val",
        "efi_val",
        "eom_val",
        "mfi_val",
        "nvi_val",
        "pvi_val",
        "pvt_val",
        "vwap_val",
    ]

    missing_functions = []
    for func_name in required_functions:
        if not hasattr(ta_safe, func_name):
            missing_functions.append(func_name)

    assert not missing_functions, f"Отсутствуют функции в фасаде: {missing_functions}"


if __name__ == "__main__":
    # Запуск тестов
    test_no_callable_shadow()
    test_naming_conventions()
    test_no_direct_ta_imports()
    test_ta_safe_facade_completeness()
    print("✅ Все тесты на теневые вызовы прошли успешно!")
