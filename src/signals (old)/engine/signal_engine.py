"""
Основной класс движка сигналов.
"""

from ..config import get_rule_weight, get_threshold
from ..rules import RULES


class SignalEngine:
    """
    Движок для генерации торговых сигналов на основе технических индикаторов.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        min_score_for_buy: float | None = None,
        min_score_for_sell: float | None = None,
    ):
        """
        Инициализация движка сигналов.

        Args:
            weights: Словарь весов для правил {rule_name: weight}
            min_score_for_buy: Минимальный score для сигнала покупки
            min_score_for_sell: Минимальный score для сигнала продажи
        """
        self.weights = weights or {rule: get_rule_weight(rule) for rule in RULES}
        self.min_score_for_buy = min_score_for_buy or get_threshold(
            "min_score_for_buy", 3
        )
        self.min_score_for_sell = min_score_for_sell or get_threshold(
            "min_score_for_sell", -3
        )

    def generate_signal(self, current: dict, previous: dict | None = None) -> dict:
        """
        Генерирует сигнал на основе текущих и предыдущих данных.

        Args:
            current: Текущие данные индикаторов
            previous: Предыдущие данные индикаторов (опционально)

        Returns:
            Dict: Результат с сигналом и причинами
        """
        signals = []
        reasons = []
        rule_results = {}  # Детализированные результаты правил

        # Применяем каждое правило
        for rule_name, rule_func in RULES.items():
            try:
                signal, reason = self._apply_rule(rule_func, current, previous)
                weight = self.weights.get(rule_name, 1.0)
                weighted_signal = signal * weight

                # Сохраняем детализированные результаты
                rule_results[rule_name] = {
                    "signal": self._signal_to_text(signal),
                    "score": weighted_signal,
                    "reason": reason,
                }

                if signal != 0:
                    signals.append(weighted_signal)
                    reasons.append(f"{rule_name}: {reason}")
            except Exception as e:
                # Логируем ошибку, но продолжаем работу
                print(f"Ошибка в правиле {rule_name}: {e}")
                # Добавляем пустой результат для правила с ошибкой
                rule_results[rule_name] = {
                    "signal": "",
                    "score": 0,
                    "reason": f"Error: {e}",
                }
                continue

        # Вычисляем итоговый сигнал
        final_signal = self._calculate_final_signal(signals)
        final_reason = "; ".join(reasons) if reasons else "No signals"

        return {
            "signal": final_signal,
            "reason": final_reason,
            "rule_signals": signals,
            "rule_reasons": reasons,
            "rule_results": rule_results,  # Добавляем детализированные результаты
        }

    def _signal_to_text(self, signal: int) -> str:
        """Преобразует числовой сигнал в текстовый."""
        if signal == 1:
            return "bullish"
        if signal == -1:
            return "bearish"
        return "neutral"

    def _apply_rule(
        self, rule_func, current: dict, previous: dict | None
    ) -> tuple[int, str]:
        """
        Применяет конкретное правило к данным.

        Args:
            rule_func: Функция правила
            current: Текущие данные
            previous: Предыдущие данные

        Returns:
            Tuple[int, str]: (сигнал, причина)
        """
        # Извлекаем параметры для правила
        params = self._extract_rule_params(rule_func, current, previous)
        return rule_func(**params)

    def _extract_rule_params(
        self, rule_func, current: dict, previous: dict | None
    ) -> dict:
        """
        Извлекает параметры для правила из данных.

        Args:
            rule_func: Функция правила
            current: Текущие данные
            previous: Предыдущие данные

        Returns:
            Dict: Параметры для правила
        """
        import inspect

        # Маппинг названий колонок из БД в параметры правил
        column_mapping = {
            # ADX параметры
            "plus_di": "adx_pos_di",
            "minus_di": "adx_neg_di",
            # Ichimoku параметры
            "kijun": "ichimoku_kijun",
            "tenkan": "ichimoku_tenkan",
        }

        # Получаем сигнатуру функции правила
        sig = inspect.signature(rule_func)
        params = {}

        for param_name in sig.parameters:
            # Проверяем маппинг колонок
            db_column = column_mapping.get(param_name, param_name)

            if db_column in current:
                params[param_name] = current[db_column]
            elif previous and db_column in previous:
                params[param_name] = previous[db_column]
            else:
                # Если параметр не найден, передаем None
                params[param_name] = None

        return params

    def _calculate_final_signal(self, signals: list[float]) -> int:
        """
        Вычисляет итоговый сигнал на основе взвешенных сигналов.

        Args:
            signals: Список взвешенных сигналов

        Returns:
            int: Итоговый сигнал (-1, 0, 1)
        """
        if not signals:
            return 0

        total_score = sum(signals)

        if total_score >= self.min_score_for_buy:
            return 1
        if total_score <= self.min_score_for_sell:
            return -1
        return 0
