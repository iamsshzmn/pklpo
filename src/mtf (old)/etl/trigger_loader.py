"""
ETL модуль для загрузки триггерных данных

Загружает данные из таблицы indicators в mtf.triggers для TF: 15m, 5m, 1m
Рассчитывает p_up, p_down, accel, micro_ok для каждого TF
"""

import json
import logging
import math
from datetime import datetime
from typing import Any

from sqlalchemy import text

from src.database import get_async_session

logger = logging.getLogger(__name__)


class TriggerLoader:
    """Загрузчик триггерных данных для MTF"""

    # Поддерживаемые таймфреймы для триггеров (реальные названия в БД)
    TRIGGER_TFS = ["15m", "5m", "1m"]

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def load_triggers_for_symbol(
        self, symbol: str, max_age_hours: int = 24
    ) -> bool:
        """
        Загружает триггерные данные для одного символа

        Args:
            symbol: Торговый символ
            max_age_hours: Максимальный возраст данных в часах

        Returns:
            True если данные загружены успешно
        """
        try:
            async for session in get_async_session():
                # Получаем последние индикаторы для всех триггерных TF
                indicators = await self._get_latest_indicators(
                    session, symbol, max_age_hours
                )

                if not indicators:
                    self.logger.warning(f"Нет данных индикаторов для {symbol}")
                    return False

                # Рассчитываем триггерные данные для каждого TF
                trigger_data = []
                for tf in self.TRIGGER_TFS:
                    if tf in indicators:
                        trigger = await self._calculate_trigger(
                            session, symbol, tf, indicators[tf]
                        )
                        if trigger:
                            trigger_data.append(trigger)

                # Сохраняем в mtf.triggers
                if trigger_data:
                    await self._save_trigger_data(session, trigger_data)
                    self.logger.info(
                        f"Загружены триггеры для {symbol}: {len(trigger_data)} TF"
                    )
                    return True

                return False

        except Exception as e:
            self.logger.error(f"Ошибка загрузки триггеров для {symbol}: {e}")
            return False

    async def load_triggers_for_all_symbols(
        self, max_age_hours: int = 24
    ) -> dict[str, bool]:
        """
        Загружает триггерные данные для всех символов

        Args:
            max_age_hours: Максимальный возраст данных в часах

        Returns:
            Словарь {symbol: success}
        """
        try:
            async for session in get_async_session():
                # Получаем список всех символов
                symbols = await self._get_all_symbols(session)

                results = {}
                for symbol in symbols:
                    success = await self.load_triggers_for_symbol(symbol, max_age_hours)
                    results[symbol] = success

                self.logger.info(
                    f"Загрузка триггеров завершена: {sum(results.values())}/{len(results)} успешно"
                )
                return results

        except Exception as e:
            self.logger.error(f"Ошибка массовой загрузки триггеров: {e}")
            return {}

    async def _get_latest_indicators(
        self, session, symbol: str, max_age_hours: int
    ) -> dict[str, Any]:
        """Получает последние индикаторы для всех триггерных TF"""
        # Берем последние данные независимо от времени, так как данные могут быть из будущего
        query = text(
            """
            SELECT timeframe, ts, rsi14, macd, macd_signal, bb_upper, bb_lower,
                   close, ema21, sma50, stoch_k, stoch_d, adx14, atr14,
                   volume, obv, cmf, kc_upper, kc_lower
            FROM indicators
            WHERE symbol = :symbol
            AND timeframe = ANY(:timeframes)
            ORDER BY timeframe, ts DESC
        """
        )

        result = await session.execute(
            query, {"symbol": symbol, "timeframes": self.TRIGGER_TFS}
        )

        indicators = {}
        for row in result.fetchall():
            tf = row.timeframe
            if tf not in indicators:
                indicators[tf] = row._asdict()

        return indicators

    async def _calculate_trigger(
        self, session, symbol: str, timeframe: str, indicators: dict
    ) -> dict | None:
        """Рассчитывает триггерные данные для одного TF"""
        try:
            # Рассчитываем вероятности разворота
            p_up, p_down = self._calculate_reversal_probabilities(indicators, timeframe)

            # Рассчитываем ускорение (только для 5m)
            accel = None
            if timeframe == "5m":
                accel = self._calculate_acceleration(indicators)

            # Рассчитываем микро-фильтр (только для 1m)
            micro_ok = None
            if timeframe == "1m":
                micro_ok = self._calculate_micro_filter(indicators)

            # Особенности для каждого TF
            features = self._extract_features(indicators, timeframe)

            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "ts": (
                    datetime.fromtimestamp(indicators["ts"])
                    if isinstance(indicators["ts"], int | float)
                    else indicators["ts"]
                ),
                "p_up": p_up,
                "p_down": p_down,
                "accel": accel,
                "micro_ok": micro_ok,
                "features": json.dumps(features),
            }

        except Exception as e:
            self.logger.error(f"Ошибка расчета триггера для {symbol} {timeframe}: {e}")
            return None

    def _calculate_reversal_probabilities(
        self, indicators: dict, timeframe: str
    ) -> tuple[float, float]:
        """Рассчитывает вероятности разворота вверх и вниз"""
        try:
            # Базовые компоненты
            rsi_factor = 0.0
            macd_factor = 0.0
            bollinger_factor = 0.0
            stochastic_factor = 0.0
            volume_factor = 0.0

            # RSI компонент
            if indicators.get("rsi14"):
                rsi = (
                    float(indicators["rsi14"])
                    if indicators["rsi14"] is not None
                    else 50.0
                )
                if rsi < 30:  # Перепроданность
                    rsi_factor = (30 - rsi) / 30
                elif rsi > 70:  # Перекупленность
                    rsi_factor = -(rsi - 70) / 30

            # MACD компонент
            if indicators.get("macd") and indicators.get("macd_signal"):
                macd = (
                    float(indicators["macd"]) if indicators["macd"] is not None else 0.0
                )
                macd_signal = (
                    float(indicators["macd_signal"])
                    if indicators["macd_signal"] is not None
                    else 0.0
                )
                macd_diff = macd - macd_signal
                macd_factor = math.tanh(macd_diff * 10)  # Нормализация

            # Bollinger компонент
            if all(k in indicators for k in ["close", "bb_upper", "bb_lower"]):
                close = (
                    float(indicators["close"])
                    if indicators["close"] is not None
                    else 0.0
                )
                upper = (
                    float(indicators["bb_upper"])
                    if indicators["bb_upper"] is not None
                    else 0.0
                )
                lower = (
                    float(indicators["bb_lower"])
                    if indicators["bb_lower"] is not None
                    else 0.0
                )

                if upper > lower and close <= lower:  # Нижняя полоса
                    bollinger_factor = (lower - close) / (upper - lower)
                elif upper > lower and close >= upper:  # Верхняя полоса
                    bollinger_factor = -(close - upper) / (upper - lower)

            # Stochastic компонент
            if indicators.get("stoch_k") and indicators.get("stoch_d"):
                k = (
                    float(indicators["stoch_k"])
                    if indicators["stoch_k"] is not None
                    else 50.0
                )
                d = (
                    float(indicators["stoch_d"])
                    if indicators["stoch_d"] is not None
                    else 50.0
                )

                if k < 20 and d < 20:  # Перепроданность
                    stochastic_factor = (20 - min(k, d)) / 20
                elif k > 80 and d > 80:  # Перекупленность
                    stochastic_factor = -(max(k, d) - 80) / 20

            # Volume компонент
            if indicators.get("volume") and indicators.get("obv"):
                # Простая нормализация объема (можно улучшить)
                volume = (
                    float(indicators["volume"])
                    if indicators["volume"] is not None
                    else 0.0
                )
                volume_factor = min(volume / 1000000, 1.0)  # Примерная нормализация

            # Взвешивание по таймфрейму
            weights = {
                "15m": {
                    "rsi": 0.3,
                    "macd": 0.3,
                    "bollinger": 0.2,
                    "stochastic": 0.1,
                    "volume": 0.1,
                },
                "5m": {
                    "rsi": 0.25,
                    "macd": 0.25,
                    "bollinger": 0.25,
                    "stochastic": 0.15,
                    "volume": 0.1,
                },
                "1m": {
                    "rsi": 0.2,
                    "macd": 0.2,
                    "bollinger": 0.3,
                    "stochastic": 0.2,
                    "volume": 0.1,
                },
            }

            w = weights.get(timeframe, weights["15m"])

            # Итоговый score
            total_score = (
                rsi_factor * w["rsi"]
                + macd_factor * w["macd"]
                + bollinger_factor * w["bollinger"]
                + stochastic_factor * w["stochastic"]
                + volume_factor * w["volume"]
            )

            # Преобразуем в вероятности
            p_up = max(0.0, min(1.0, 0.5 + total_score * 0.5))
            p_down = max(0.0, min(1.0, 0.5 - total_score * 0.5))

            return p_up, p_down

        except Exception as e:
            self.logger.error(f"Ошибка расчета вероятностей разворота: {e}")
            return 0.5, 0.5

    def _calculate_acceleration(self, indicators: dict) -> int:
        """Рассчитывает ускорение для 5m таймфрейма"""
        try:
            # Простая логика ускорения на основе MACD и RSI
            accel = 0

            if indicators.get("macd") and indicators.get("macd_signal"):
                macd = (
                    float(indicators["macd"]) if indicators["macd"] is not None else 0.0
                )
                macd_signal = (
                    float(indicators["macd_signal"])
                    if indicators["macd_signal"] is not None
                    else 0.0
                )
                macd_diff = macd - macd_signal
                if macd_diff > 0.001:  # Положительное ускорение
                    accel = 1
                elif macd_diff < -0.001:  # Отрицательное ускорение
                    accel = -1

            return accel

        except Exception as e:
            self.logger.error(f"Ошибка расчета ускорения: {e}")
            return 0

    def _calculate_micro_filter(self, indicators: dict) -> bool:
        """Рассчитывает микро-фильтр для 1m таймфрейма"""
        try:
            # Проверяем ликвидность и качество сигнала
            checks = []

            # Проверка объема
            if indicators.get("volume"):
                volume = (
                    float(indicators["volume"])
                    if indicators["volume"] is not None
                    else 0.0
                )
                checks.append(volume > 100000)  # Минимальный объем

            # Проверка спреда (через ATR)
            if indicators.get("atr14"):
                atr = (
                    float(indicators["atr14"])
                    if indicators["atr14"] is not None
                    else 0.0
                )
                checks.append(atr < 0.01)  # Не слишком высокая волатильность

            # Проверка ADX (сила тренда)
            if indicators.get("adx14"):
                adx = (
                    float(indicators["adx14"])
                    if indicators["adx14"] is not None
                    else 0.0
                )
                checks.append(adx > 15)  # Минимальная сила тренда

            # Все проверки должны пройти
            return all(checks) if checks else True

        except Exception as e:
            self.logger.error(f"Ошибка расчета микро-фильтра: {e}")
            return True

    def _extract_features(self, indicators: dict, timeframe: str) -> dict:
        """Извлекает особенности для каждого TF"""

        # Конвертируем Decimal в float для JSON сериализации
        def safe_float(value):
            if value is None:
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        features = {
            "timeframe": timeframe,
            "rsi14": safe_float(indicators.get("rsi14")),
            "macd": safe_float(indicators.get("macd")),
            "macd_signal": safe_float(indicators.get("macd_signal")),
            "bb_upper": safe_float(indicators.get("bb_upper")),
            "bb_lower": safe_float(indicators.get("bb_lower")),
            "stoch_k": safe_float(indicators.get("stoch_k")),
            "stoch_d": safe_float(indicators.get("stoch_d")),
            "adx14": safe_float(indicators.get("adx14")),
            "atr14": safe_float(indicators.get("atr14")),
            "volume": safe_float(indicators.get("volume")),
            "obv": safe_float(indicators.get("obv")),
            "cmf": safe_float(indicators.get("cmf")),
        }

        # Добавляем специфичные для TF особенности
        if timeframe == "5m":
            features["accel_calculation"] = "macd_based"
        elif timeframe == "1m":
            features["micro_filter_type"] = "liquidity_volatility"

        return features

    async def _save_trigger_data(self, session, trigger_data: list[dict]) -> None:
        """Сохраняет триггерные данные в mtf.triggers"""
        for trigger in trigger_data:
            query = text(
                """
                INSERT INTO mtf.triggers (symbol, timeframe, ts, p_up, p_down, accel, micro_ok, features)
                VALUES (:symbol, :timeframe, :ts, :p_up, :p_down, :accel, :micro_ok, :features)
            """
            )

            await session.execute(query, trigger)

        await session.commit()

    async def _get_all_symbols(self, session) -> list[str]:
        """Получает список всех символов из indicators"""
        query = text(
            """
            SELECT DISTINCT symbol
            FROM indicators
            WHERE timeframe = ANY(:timeframes)
            AND symbol LIKE '%-SWAP'  -- Фильтруем только SWAP символы
            ORDER BY symbol
        """
        )

        result = await session.execute(query, {"timeframes": self.TRIGGER_TFS})
        return [row[0] for row in result.fetchall()]


# Глобальный экземпляр загрузчика
trigger_loader = TriggerLoader()
