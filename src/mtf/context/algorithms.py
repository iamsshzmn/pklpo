"""
Алгоритмы для Context Builder
"""

import logging
import math

import numpy as np
import pandas as pd

from .config import ContextConfig
from .models import (
    ReasonCode,
    RegimeAnalysis,
    RegimeType,
    TrendScoreComponents,
)

logger = logging.getLogger(__name__)


class RegimeDetector:
    """Детектор режимов рынка"""

    def __init__(self, config: dict[str, float]):
        self.config = config

    def detect_regime(self, features: dict[str, float], score: float) -> RegimeAnalysis:
        """
        Определение режима рынка на основе индикаторов и score

        Args:
            features: Словарь с индикаторами
            score: Trend score

        Returns:
            RegimeAnalysis: Анализ режима
        """
        # Анализ силы тренда
        trend_strength = abs(score)
        adx = features.get("adx_14", 0)

        # Анализ волатильности
        atr = features.get("atr_14", 0)
        volatility_level = self._calculate_volatility_level(
            atr, features.get("close", 0)
        )

        # Анализ объема
        volume_profile = self._analyze_volume_profile(features)

        # Определение режима
        regime, confidence, reasoning = self._determine_regime_type(
            score, trend_strength, adx, volatility_level, volume_profile
        )

        return RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            trend_strength=trend_strength,
            volatility_level=volatility_level,
            volume_profile=volume_profile,
            timeframe_consistency=0.0,  # Будет рассчитано в builder
            reasoning=reasoning,
        )

    def _calculate_volatility_level(self, atr: float, close: float) -> float:
        """Расчет уровня волатильности"""
        if close == 0:
            return 0.0
        return min(atr / close, 1.0)

    def _analyze_volume_profile(self, features: dict[str, float]) -> str:
        """Анализ профиля объема"""
        volume = features.get("volume", 0)
        obv = features.get("obv", 0)

        if volume > 0 and obv > 0:
            return "high"
        if volume > 0:
            return "medium"
        return "low"

    def _determine_regime_type(
        self,
        score: float,
        trend_strength: float,
        adx: float,
        volatility: float,
        volume: str,
    ) -> tuple[RegimeType, float, list[str]]:
        """Определение типа режима"""
        reasoning = []
        confidence = 0.0

        # Пороги из конфигурации
        trend_min = self.config.get("trend_min_score", 0.3)
        range_max = self.config.get("range_max_score", 0.2)
        bull_min = self.config.get("bull_min_score", 0.1)
        bear_max = self.config.get("bear_max_score", -0.1)

        # Определение режима
        if trend_strength >= trend_min and adx >= 25:
            # Сильный тренд
            if score >= bull_min:
                regime = RegimeType.TREND_UP
                reasoning.append(
                    f"Strong bullish trend: score={score:.3f}, ADX={adx:.1f}"
                )
                confidence = min(trend_strength * 1.5, 1.0)
            else:
                regime = RegimeType.TREND_DOWN
                reasoning.append(
                    f"Strong bearish trend: score={score:.3f}, ADX={adx:.1f}"
                )
                confidence = min(trend_strength * 1.5, 1.0)
        elif trend_strength <= range_max:
            # Боковое движение
            if score >= bull_min:
                regime = RegimeType.FLAT
                reasoning.append(f"Bullish range: score={score:.3f}, low volatility")
                confidence = 0.6
            elif score <= bear_max:
                regime = RegimeType.FLAT
                reasoning.append(f"Bearish range: score={score:.3f}, low volatility")
                confidence = 0.6
            else:
                regime = RegimeType.FLAT  # По умолчанию
                reasoning.append(f"Neutral range: score={score:.3f}")
                confidence = 0.4
        else:
            # Слабый тренд
            if score >= bull_min:
                regime = RegimeType.TREND_UP
                reasoning.append(f"Weak bullish trend: score={score:.3f}")
                confidence = 0.5
            else:
                regime = RegimeType.TREND_DOWN
                reasoning.append(f"Weak bearish trend: score={score:.3f}")
                confidence = 0.5

        # Корректировка confidence на основе объема
        if volume == "high":
            confidence *= 1.1
        elif volume == "low":
            confidence *= 0.9

        confidence = max(0.0, min(1.0, confidence))

        return regime, confidence, reasoning


class TrendScoreCalculator:
    """Калькулятор trend score"""

    def __init__(self, weights: dict[str, float]):
        self.weights = weights

    def calculate_trend_score(self, features: dict[str, float]) -> TrendScoreComponents:
        """
        Расчет trend score на основе индикаторов

        Args:
            features: Словарь с индикаторами

        Returns:
            TrendScoreComponents: Компоненты trend score
        """
        # EMA тренд
        ema21 = features.get("ema_21", 0)
        ema55 = features.get("ema_55", 0)
        close = features.get("close", 0)

        if ema55 != 0 and close != 0:
            ema_trend = math.tanh((ema21 - ema55) / ema55 * 10)
        else:
            ema_trend = 0.0

        # ADX сила тренда
        adx = features.get("adx_14", 0)
        adx_strength = min(adx / 100.0, 1.0)

        # RSI momentum
        rsi = features.get("rsi_14", 50)
        rsi_momentum = (rsi - 50) / 50.0  # Нормализация к [-1, 1]

        # MACD signal
        macd = features.get("macd", 0)
        macd_signal = features.get("macd_signal", 0)
        macd_factor = math.tanh(macd / macd_signal * 5) if macd_signal != 0 else 0.0

        # Volume confirmation
        volume = features.get("volume", 0)
        obv = features.get("obv", 0)
        volume_confirmation = min(obv / volume, 1.0) if volume > 0 and obv > 0 else 0.5

        # Volatility factor
        atr = features.get("atr_14", 0)
        volatility_factor = min(atr / close, 2.0) if close != 0 else 1.0

        # Итоговый score
        final_score = (
            self.weights.get("ema_trend", 0.4) * ema_trend
            + self.weights.get("adx_strength", 0.25) * adx_strength
            + self.weights.get("rsi_momentum", 0.15) * rsi_momentum
            + self.weights.get("macd_signal", 0.1) * macd_factor
            + self.weights.get("volume_confirmation", 0.1) * volume_confirmation
        ) * volatility_factor

        # Ограничение диапазона
        final_score = max(-1.0, min(1.0, final_score))

        return TrendScoreComponents(
            ema_trend=ema_trend,
            adx_strength=adx_strength,
            rsi_momentum=rsi_momentum,
            macd_signal=macd_factor,
            volume_confirmation=volume_confirmation,
            volatility_factor=volatility_factor,
            final_score=final_score,
        )


class EnhancedTrendScoreCalculator:
    """Улучшенный калькулятор trend score с поддержкой DataFrame"""

    def __init__(self, config: ContextConfig):
        self.config = config

    def calculate_trend_score(
        self, features_data: pd.DataFrame
    ) -> TrendScoreComponents:
        """Расчет trend score на основе индикаторов"""
        try:
            # EMA trend component
            ema_trend = self._calculate_ema_trend(features_data)

            # ADX strength component
            adx_strength = self._calculate_adx_strength(features_data)

            # RSI momentum component
            rsi_momentum = self._calculate_rsi_momentum(features_data)

            # MACD signal component
            macd_signal = self._calculate_macd_signal(features_data)

            # Volume confirmation component
            volume_confirmation = self._calculate_volume_confirmation(features_data)

            # Volatility factor
            volatility_factor = self._calculate_volatility_factor(features_data)

            # Final weighted score
            final_score = (
                ema_trend * self.config.ema_weight
                + adx_strength * self.config.adx_weight
                + rsi_momentum * self.config.rsi_weight
                + macd_signal * self.config.macd_weight
                + volume_confirmation * self.config.volume_weight
            ) * volatility_factor

            # Ограничение в диапазоне [-1, 1]
            final_score = np.clip(final_score, -1.0, 1.0)

            return TrendScoreComponents(
                ema_trend=ema_trend,
                adx_strength=adx_strength,
                rsi_momentum=rsi_momentum,
                macd_signal=macd_signal,
                volume_confirmation=volume_confirmation,
                volatility_factor=volatility_factor,
                final_score=final_score,
            )

        except Exception as e:
            logger.error(f"Error calculating trend score: {e}")
            return TrendScoreComponents(
                ema_trend=0.0,
                adx_strength=0.0,
                rsi_momentum=0.0,
                macd_signal=0.0,
                volume_confirmation=0.0,
                volatility_factor=1.0,
                final_score=0.0,
            )

    def _calculate_ema_trend(self, features_data: pd.DataFrame) -> float:
        """Расчет EMA trend компонента"""
        try:
            if (
                "ema_21" not in features_data.columns
                or "close" not in features_data.columns
            ):
                return 0.0

            # Последние значения
            current_price = features_data["close"].iloc[-1]
            current_ema = features_data["ema_21"].iloc[-1]

            # Предыдущие значения для сравнения
            if len(features_data) < 2:
                return 0.0

            features_data["close"].iloc[-2]
            prev_ema = features_data["ema_21"].iloc[-2]

            # Тренд по цене относительно EMA
            price_ema_ratio = (current_price - current_ema) / current_ema

            # Тренд по изменению EMA
            ema_change = (current_ema - prev_ema) / prev_ema if prev_ema != 0 else 0

            # Комбинированный тренд
            trend = (price_ema_ratio + ema_change) / 2

            # Нормализация в диапазон [-1, 1]
            return np.tanh(trend * 10)

        except Exception as e:
            logger.warning(f"Error calculating EMA trend: {e}")
            return 0.0

    def _calculate_adx_strength(self, features_data: pd.DataFrame) -> float:
        """Расчет ADX strength компонента"""
        try:
            if "adx" not in features_data.columns:
                return 0.0

            current_adx = features_data["adx"].iloc[-1]

            # Определение силы тренда
            if current_adx >= self.config.adx_strong_trend:
                # Сильный тренд - проверяем направление
                if (
                    "di_plus" in features_data.columns
                    and "di_minus" in features_data.columns
                ):
                    di_plus = features_data["di_plus"].iloc[-1]
                    di_minus = features_data["di_minus"].iloc[-1]

                    if di_plus > di_minus:
                        return 0.8  # Сильный восходящий тренд
                    return -0.8  # Сильный нисходящий тренд
                return 0.5  # Сильный тренд без направления
            if current_adx >= self.config.adx_weak_trend:
                # Слабый тренд
                if (
                    "di_plus" in features_data.columns
                    and "di_minus" in features_data.columns
                ):
                    di_plus = features_data["di_plus"].iloc[-1]
                    di_minus = features_data["di_minus"].iloc[-1]

                    if di_plus > di_minus:
                        return 0.3
                    return -0.3
                return 0.2
            # Боковое движение
            return 0.0

        except Exception as e:
            logger.warning(f"Error calculating ADX strength: {e}")
            return 0.0

    def _calculate_rsi_momentum(self, features_data: pd.DataFrame) -> float:
        """Расчет RSI momentum компонента"""
        try:
            if "rsi_14" not in features_data.columns:
                return 0.0

            current_rsi = features_data["rsi_14"].iloc[-1]

            # Определение momentum на основе RSI
            if current_rsi <= self.config.rsi_oversold:
                return 0.6  # Потенциал для роста
            if current_rsi >= self.config.rsi_overbought:
                return -0.6  # Потенциал для падения
            if current_rsi < 50:
                # Ниже средней линии - слабый медвежий momentum
                return -0.2
            # Выше средней линии - слабый бычий momentum
            return 0.2

        except Exception as e:
            logger.warning(f"Error calculating RSI momentum: {e}")
            return 0.0

    def _calculate_macd_signal(self, features_data: pd.DataFrame) -> float:
        """Расчет MACD signal компонента"""
        try:
            if (
                "macd" not in features_data.columns
                or "macd_signal" not in features_data.columns
            ):
                return 0.0

            current_macd = features_data["macd"].iloc[-1]
            current_signal = features_data["macd_signal"].iloc[-1]

            # MACD выше сигнальной линии - бычий сигнал
            if current_macd > current_signal:
                # Дополнительно проверяем гистограмму
                if "macd_histogram" in features_data.columns:
                    current_hist = features_data["macd_histogram"].iloc[-1]
                    if current_hist > 0:
                        return 0.4  # Сильный бычий сигнал
                    return 0.2  # Слабый бычий сигнал
                return 0.3
            # MACD ниже сигнальной линии - медвежий сигнал
            if "macd_histogram" in features_data.columns:
                current_hist = features_data["macd_histogram"].iloc[-1]
                if current_hist < 0:
                    return -0.4  # Сильный медвежий сигнал
                return -0.2  # Слабый медвежий сигнал
            return -0.3

        except Exception as e:
            logger.warning(f"Error calculating MACD signal: {e}")
            return 0.0

    def _calculate_volume_confirmation(self, features_data: pd.DataFrame) -> float:
        """Расчет volume confirmation компонента"""
        try:
            if (
                "volume" not in features_data.columns
                or "close" not in features_data.columns
            ):
                return 0.0

            # Проверяем объем за последние несколько периодов
            recent_volume = features_data["volume"].tail(5)
            recent_prices = features_data["close"].tail(5)

            if len(recent_volume) < 2 or len(recent_prices) < 2:
                return 0.0

            # Средний объем
            avg_volume = recent_volume.mean()
            current_volume = recent_volume.iloc[-1]

            # Изменение цены
            price_change = (
                recent_prices.iloc[-1] - recent_prices.iloc[-2]
            ) / recent_prices.iloc[-2]

            # Объемное подтверждение
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Если цена растет и объем выше среднего - бычье подтверждение
            if price_change > 0 and volume_ratio > 1.2:
                return 0.3
            # Если цена падает и объем выше среднего - медвежье подтверждение
            if price_change < 0 and volume_ratio > 1.2:
                return -0.3
            # Если объем низкий - слабое подтверждение
            if volume_ratio < 0.8:
                return 0.1
            return 0.0

        except Exception as e:
            logger.warning(f"Error calculating volume confirmation: {e}")
            return 0.0

    def _calculate_volatility_factor(self, features_data: pd.DataFrame) -> float:
        """Расчет volatility factor"""
        try:
            if (
                "atr" not in features_data.columns
                or "close" not in features_data.columns
            ):
                return 1.0

            current_atr = features_data["atr"].iloc[-1]
            current_price = features_data["close"].iloc[-1]

            # ATR как процент от цены
            atr_ratio = current_atr / current_price if current_price > 0 else 0

            # Высокая волатильность снижает уверенность
            if atr_ratio > 0.05:  # 5% ATR
                return 0.7
            if atr_ratio > 0.03:  # 3% ATR
                return 0.85
            return 1.0

        except Exception as e:
            logger.warning(f"Error calculating volatility factor: {e}")
            return 1.0


class ReasonCodeGenerator:
    """Генератор кодов причин"""

    def __init__(self, config: ContextConfig):
        self.config = config

    def generate_reason_codes(
        self, trend_components: TrendScoreComponents, features_data: pd.DataFrame
    ) -> list[ReasonCode]:
        """Генерация кодов причин"""
        reason_codes = []

        try:
            # EMA trend codes
            if trend_components.ema_trend > 0.3:
                reason_codes.append(ReasonCode.EMA_TREND_UP)
            elif trend_components.ema_trend < -0.3:
                reason_codes.append(ReasonCode.EMA_TREND_DOWN)

            # ADX strength codes
            if "adx" in features_data.columns:
                current_adx = features_data["adx"].iloc[-1]
                if current_adx >= self.config.adx_strong_trend:
                    reason_codes.append(ReasonCode.ADX_STRONG_TREND)
                elif current_adx <= self.config.adx_weak_trend:
                    reason_codes.append(ReasonCode.ADX_WEAK_TREND)

            # RSI codes
            if "rsi_14" in features_data.columns:
                current_rsi = features_data["rsi_14"].iloc[-1]
                if current_rsi <= self.config.rsi_oversold:
                    reason_codes.append(ReasonCode.RSI_OVERSOLD)
                elif current_rsi >= self.config.rsi_overbought:
                    reason_codes.append(ReasonCode.RSI_OVERBOUGHT)

            # MACD codes
            if trend_components.macd_signal > 0.2:
                reason_codes.append(ReasonCode.MACD_BULLISH)
            elif trend_components.macd_signal < -0.2:
                reason_codes.append(ReasonCode.MACD_BEARISH)

            # Volume codes
            if trend_components.volume_confirmation > 0.2:
                reason_codes.append(ReasonCode.VOLUME_CONFIRMATION)

            # ATR codes
            if "atr" in features_data.columns and "close" in features_data.columns:
                current_atr = features_data["atr"].iloc[-1]
                current_price = features_data["close"].iloc[-1]
                atr_ratio = current_atr / current_price if current_price > 0 else 0

                if atr_ratio > 0.05:
                    reason_codes.append(ReasonCode.ATR_HIGH_VOLATILITY)
                elif atr_ratio < 0.02:
                    reason_codes.append(ReasonCode.ATR_LOW_VOLATILITY)

            # Проверка на конфликтующие сигналы
            if len(reason_codes) == 0:
                reason_codes.append(ReasonCode.INSUFFICIENT_DATA)
            elif self._has_conflicting_signals(reason_codes):
                reason_codes.append(ReasonCode.CONFLICTING_SIGNALS)

        except Exception as e:
            logger.error(f"Error generating reason codes: {e}")
            reason_codes.append(ReasonCode.INSUFFICIENT_DATA)

        return reason_codes

    def _has_conflicting_signals(self, reason_codes: list[ReasonCode]) -> bool:
        """Проверка на конфликтующие сигналы"""
        bullish_codes = {
            ReasonCode.EMA_TREND_UP,
            ReasonCode.RSI_OVERSOLD,
            ReasonCode.MACD_BULLISH,
            ReasonCode.VOLUME_CONFIRMATION,
        }
        bearish_codes = {
            ReasonCode.EMA_TREND_DOWN,
            ReasonCode.RSI_OVERBOUGHT,
            ReasonCode.MACD_BEARISH,
        }

        has_bullish = any(code in bullish_codes for code in reason_codes)
        has_bearish = any(code in bearish_codes for code in reason_codes)

        return has_bullish and has_bearish
