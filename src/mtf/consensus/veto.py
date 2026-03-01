"""
Veto логика для Consensus Builder
"""

from typing import Any

from .models import VetoAnalysis


class VetoEngine:
    """Движок veto логики"""

    def __init__(self, veto_settings: dict[str, Any]):
        self.settings = veto_settings

    def check_veto_conditions(
        self,
        horizon: str,
        context_data: dict[str, Any],
        trigger_data: dict[str, Any],
        bias: str,
    ) -> VetoAnalysis:
        """
        Проверка условий veto

        Args:
            horizon: Горизонт торговли
            context_data: Данные контекста
            trigger_data: Данные триггеров
            bias: Bias (bullish/bearish/neutral)

        Returns:
            VetoAnalysis: Анализ veto
        """
        reasoning = []
        veto_applied = False
        veto_reason = ""

        # Проверка микро-фильтра veto
        micro_filter_veto = self._check_micro_filter_veto(trigger_data, reasoning)

        # Проверка конфликта контекста
        context_conflict_veto = self._check_context_conflict_veto(
            context_data, bias, reasoning
        )

        # Проверка конфликта триггеров
        trigger_conflict_veto = self._check_trigger_conflict_veto(
            trigger_data, reasoning
        )

        # Проверка пороговых условий
        threshold_veto = self._check_threshold_veto(
            horizon, context_data, trigger_data, reasoning
        )

        # Определение применения veto
        veto_conditions = [
            micro_filter_veto,
            context_conflict_veto,
            trigger_conflict_veto,
            threshold_veto,
        ]

        if any(veto_conditions):
            veto_applied = True
            veto_reasons = []
            if micro_filter_veto:
                veto_reasons.append("micro_filter")
            if context_conflict_veto:
                veto_reasons.append("context_conflict")
            if trigger_conflict_veto:
                veto_reasons.append("trigger_conflict")
            if threshold_veto:
                veto_reasons.append("threshold")
            veto_reason = f"Veto applied: {', '.join(veto_reasons)}"
        else:
            veto_reason = "No veto conditions met"

        # Расчет уровня конфликта
        conflict_level = self._calculate_conflict_level(
            context_data, trigger_data, bias
        )

        return VetoAnalysis(
            veto_applied=veto_applied,
            veto_reason=veto_reason,
            conflict_level=conflict_level,
            micro_filter_veto=micro_filter_veto,
            context_conflict_veto=context_conflict_veto,
            trigger_conflict_veto=trigger_conflict_veto,
            threshold_veto=threshold_veto,
            reasoning=reasoning,
        )

    def _check_micro_filter_veto(
        self, trigger_data: dict[str, Any], reasoning: list[str]
    ) -> bool:
        """Проверка veto по микро-фильтру"""
        if not self.settings.get("micro_filter_veto", True):
            return False

        # Проверка прохождения микро-фильтра
        micro_ok_count = 0
        total_triggers = 0

        for _timeframe, trigger in trigger_data.items():
            if hasattr(trigger, "micro_ok"):
                total_triggers += 1
                if trigger.micro_ok:
                    micro_ok_count += 1

        if total_triggers == 0:
            reasoning.append("No trigger data for micro filter check")
            return False

        micro_ok_ratio = micro_ok_count / total_triggers

        if micro_ok_ratio < 0.5:  # Менее 50% триггеров прошли микро-фильтр
            reasoning.append(f"Micro filter veto: only {micro_ok_ratio:.1%} passed")
            return True
        reasoning.append(f"Micro filter OK: {micro_ok_ratio:.1%} passed")
        return False

    def _check_context_conflict_veto(
        self, context_data: dict[str, Any], bias: str, reasoning: list[str]
    ) -> bool:
        """Проверка veto по конфликту контекста"""
        if not context_data:
            reasoning.append("No context data for conflict check")
            return False

        # Анализ согласованности контекстов
        scores = []
        for _timeframe, context in context_data.items():
            if hasattr(context, "score"):
                scores.append(context.score)

        if len(scores) < 2:
            reasoning.append("Insufficient context data for conflict analysis")
            return False

        # Проверка на конфликт направлений
        positive_scores = sum(1 for score in scores if score > 0.1)
        negative_scores = sum(1 for score in scores if score < -0.1)
        total_scores = len(scores)

        conflict_threshold = self.settings.get("context_conflict_threshold", 0.4)

        # Конфликт если есть значительное количество противоположных сигналов
        if bias == "bullish" and negative_scores / total_scores > conflict_threshold:
            reasoning.append(
                f"Context conflict veto: {negative_scores}/{total_scores} bearish signals"
            )
            return True
        if bias == "bearish" and positive_scores / total_scores > conflict_threshold:
            reasoning.append(
                f"Context conflict veto: {positive_scores}/{total_scores} bullish signals"
            )
            return True
        reasoning.append(
            f"Context conflict OK: {positive_scores} bullish, {negative_scores} bearish"
        )
        return False

    def _check_trigger_conflict_veto(
        self, trigger_data: dict[str, Any], reasoning: list[str]
    ) -> bool:
        """Проверка veto по конфликту триггеров"""
        if not trigger_data:
            reasoning.append("No trigger data for conflict check")
            return False

        # Анализ согласованности триггеров
        p_up_values = []
        p_down_values = []
        accel_values = []

        for _timeframe, trigger in trigger_data.items():
            if hasattr(trigger, "p_up") and hasattr(trigger, "p_down"):
                p_up_values.append(trigger.p_up)
                p_down_values.append(trigger.p_down)
            if hasattr(trigger, "accel"):
                accel_values.append(trigger.accel)

        if not p_up_values or not p_down_values:
            reasoning.append("Insufficient trigger data for conflict analysis")
            return False

        # Проверка конфликта вероятностей
        avg_p_up = sum(p_up_values) / len(p_up_values)
        avg_p_down = sum(p_down_values) / len(p_down_values)

        conflict_threshold = self.settings.get("trigger_conflict_threshold", 0.3)

        # Конфликт если вероятности близки (неопределенность)
        if abs(avg_p_up - avg_p_down) < conflict_threshold:
            reasoning.append(
                f"Trigger conflict veto: probabilities too close ({avg_p_up:.3f} vs {avg_p_down:.3f})"
            )
            return True

        # Проверка конфликта ускорения
        if accel_values:
            accel_conflicts = 0
            for i in range(len(accel_values) - 1):
                if accel_values[i] != accel_values[i + 1]:
                    accel_conflicts += 1

            if accel_conflicts > len(accel_values) / 2:
                reasoning.append(
                    f"Acceleration conflict veto: {accel_conflicts} conflicts"
                )
                return True

        reasoning.append("Trigger conflict OK")
        return False

    def _check_threshold_veto(
        self,
        horizon: str,
        context_data: dict[str, Any],
        trigger_data: dict[str, Any],
        reasoning: list[str],
    ) -> bool:
        """Проверка veto по пороговым условиям"""
        if not self.settings.get("threshold_veto_enabled", True):
            return False

        # Проверка минимального количества данных
        min_context_timeframes = self.settings.get("min_context_timeframes", 2)
        min_trigger_timeframes = self.settings.get("min_trigger_timeframes", 1)

        context_count = len(
            [
                tf
                for tf, ctx in context_data.items()
                if hasattr(ctx, "valid") and ctx.valid
            ]
        )
        trigger_count = len(trigger_data)

        if context_count < min_context_timeframes:
            reasoning.append(
                f"Threshold veto: insufficient context data ({context_count} < {min_context_timeframes})"
            )
            return True

        if trigger_count < min_trigger_timeframes:
            reasoning.append(
                f"Threshold veto: insufficient trigger data ({trigger_count} < {min_trigger_timeframes})"
            )
            return True

        # Проверка качества данных
        max_disagreement = self.settings.get("max_disagreement_threshold", 0.5)
        min_coverage = self.settings.get("min_coverage_threshold", 0.6)

        # Расчет disagreement (упрощенный)
        if context_data:
            scores = [
                ctx.score for tf, ctx in context_data.items() if hasattr(ctx, "score")
            ]
            if scores:
                disagreement = self._calculate_disagreement(scores)
                if disagreement > max_disagreement:
                    reasoning.append(
                        f"Threshold veto: high disagreement ({disagreement:.3f} > {max_disagreement})"
                    )
                    return True

        # Расчет coverage
        total_expected = 5  # Ожидаемое количество таймфреймов
        coverage = (context_count + trigger_count) / (total_expected * 2)
        if coverage < min_coverage:
            reasoning.append(
                f"Threshold veto: low coverage ({coverage:.3f} < {min_coverage})"
            )
            return True

        reasoning.append("Threshold conditions OK")
        return False

    def _calculate_conflict_level(
        self, context_data: dict[str, Any], trigger_data: dict[str, Any], bias: str
    ) -> float:
        """Расчет уровня конфликта"""
        conflict_score = 0.0

        # Конфликт контекста
        if context_data:
            scores = [
                ctx.score for tf, ctx in context_data.items() if hasattr(ctx, "score")
            ]
            if scores:
                if bias == "bullish":
                    conflict_score += sum(1 for score in scores if score < -0.1) / len(
                        scores
                    )
                elif bias == "bearish":
                    conflict_score += sum(1 for score in scores if score > 0.1) / len(
                        scores
                    )

        # Конфликт триггеров
        if trigger_data:
            p_up_values = [
                t.p_up for tf, t in trigger_data.items() if hasattr(t, "p_up")
            ]
            p_down_values = [
                t.p_down for tf, t in trigger_data.items() if hasattr(t, "p_down")
            ]

            if p_up_values and p_down_values:
                avg_p_up = sum(p_up_values) / len(p_up_values)
                avg_p_down = sum(p_down_values) / len(p_down_values)
                # Конфликт если вероятности близки
                conflict_score += max(0, 0.5 - abs(avg_p_up - avg_p_down))

        return max(0.0, min(1.0, conflict_score))

    def _calculate_disagreement(self, scores: list[float]) -> float:
        """Расчет уровня разногласий"""
        if len(scores) < 2:
            return 0.0

        # Расчет стандартного отклонения как меры разногласий
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        std_dev = variance**0.5

        # Нормализация к [0, 1]
        return min(std_dev, 1.0)

    def calculate_conflict_level(
        self, context_data: dict[str, Any], bias: str
    ) -> float:
        """
        Расчет уровня конфликта (публичный метод)

        Args:
            context_data: Данные контекста
            bias: Bias

        Returns:
            float: Уровень конфликта [0, 1]
        """
        if not context_data:
            return 0.0

        scores = [
            ctx.score for tf, ctx in context_data.items() if hasattr(ctx, "score")
        ]
        if not scores:
            return 0.0

        # Подсчет противоречащих сигналов
        if bias == "bullish":
            conflicting = sum(1 for score in scores if score < -0.1)
        elif bias == "bearish":
            conflicting = sum(1 for score in scores if score > 0.1)
        else:
            # Для нейтрального bias считаем общий разброс
            return self._calculate_disagreement(scores)

        return conflicting / len(scores)
