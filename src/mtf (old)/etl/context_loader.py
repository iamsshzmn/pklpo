"""
ETL модуль для загрузки контекстных данных

Загружает данные из таблицы indicators в mtf.context для TF: 1M, 1W, 1D, 4H, 1H, 30m
Рассчитывает score, valid, regime для каждого TF
"""

import json
import logging
import math
from datetime import datetime
from typing import Any

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


class ContextLoader:
    """Загрузчик контекстных данных для MTF"""

    # Поддерживаемые таймфреймы для контекста (реальные названия в БД)
    CONTEXT_TFS = ["1Mutc", "1Wutc", "1Dutc", "4H", "1H", "15m"]

    # Пороги валидности для каждого TF
    VALIDITY_THRESHOLDS = {
        "1Mutc": 0.4,  # Более строгий для месячного
        "1Wutc": 0.35,  # Строгий для недельного
        "1Dutc": 0.3,  # Стандартный для дневного
        "4H": 0.3,  # Стандартный для 4-часового
        "1H": 0.25,  # Менее строгий для часового
        "15m": 0.2,  # Самый мягкий для 15-минутного
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def load_context_for_symbol(
        self, symbol: str, max_age_hours: int = 24
    ) -> bool:
        """
        Загружает контекстные данные для одного символа

        Args:
            symbol: Торговый символ
            max_age_hours: Максимальный возраст данных в часах

        Returns:
            True если данные загружены успешно
        """
        try:
            async with get_db_session() as session:
                # Получаем последние индикаторы для всех контекстных TF
                indicators = await self._get_latest_indicators(
                    session, symbol, max_age_hours
                )

                if not indicators:
                    self.logger.warning(f"Нет данных индикаторов для {symbol}")
                    return False

                # Рассчитываем контекстные данные для каждого TF
                context_data = []
                for tf in self.CONTEXT_TFS:
                    if tf in indicators:
                        context = await self._calculate_context(
                            session, symbol, tf, indicators[tf]
                        )
                        if context:
                            context_data.append(context)

                # Сохраняем в mtf.context
                if context_data:
                    await self._save_context_data(session, context_data)
                    self.logger.info(
                        f"Загружен контекст для {symbol}: {len(context_data)} TF"
                    )
                    return True

                return False

        except Exception as e:
            self.logger.error(f"Ошибка загрузки контекста для {symbol}: {e}")
            return False

    async def load_context_for_all_symbols(
        self, max_age_hours: int = 24
    ) -> dict[str, bool]:
        """
        Загружает контекстные данные для всех символов

        Args:
            max_age_hours: Максимальный возраст данных в часах

        Returns:
            Словарь {symbol: success}
        """
        try:
            async with get_db_session() as session:
                # Получаем список всех символов
                symbols = await self._get_all_symbols(session)

                results = {}
                for symbol in symbols:
                    success = await self.load_context_for_symbol(symbol, max_age_hours)
                    results[symbol] = success

                self.logger.info(
                    f"Загрузка контекста завершена: {sum(results.values())}/{len(results)} успешно"
                )
                return results

        except Exception as e:
            self.logger.error(f"Ошибка массовой загрузки контекста: {e}")
            return {}

    async def _get_latest_indicators(
        self, session, symbol: str, max_age_hours: int
    ) -> dict[str, Any]:
        """Получает последние индикаторы для всех контекстных TF"""
        # Убираем временной фильтр - берем последние данные независимо от времени
        query = text(
            """
            SELECT timeframe, ts, ema21, ema_55, adx14, atr14,
                   sma50, sma200, rsi14, macd, macd_signal
            FROM indicators
            WHERE symbol = :symbol
            AND timeframe = ANY(:timeframes)
            ORDER BY timeframe, ts DESC
        """
        )

        result = await session.execute(
            query, {"symbol": symbol, "timeframes": self.CONTEXT_TFS}
        )

        indicators = {}
        for row in result.fetchall():
            tf = row.timeframe
            if tf not in indicators:
                indicators[tf] = row._asdict()

        return indicators

    async def _calculate_context(
        self, session, symbol: str, timeframe: str, indicators: dict
    ) -> dict | None:
        """Рассчитывает контекстные данные для одного TF"""
        try:
            # Рассчитываем trend score
            score = self._calculate_trend_score(indicators)

            # Определяем валидность
            threshold = self.VALIDITY_THRESHOLDS.get(timeframe, 0.3)
            valid = abs(score) >= threshold

            # Определяем режим (для старших TF)
            regime = None
            if timeframe in ["1M", "1W"]:
                regime = self._determine_regime(indicators, score)

            # Метаданные с конвертацией Decimal в float для JSON сериализации
            def safe_float(value):
                if value is None:
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None

            meta = {
                "ema21": safe_float(indicators.get("ema21")),
                "ema_55": safe_float(indicators.get("ema_55")),
                "adx14": safe_float(indicators.get("adx14")),
                "atr14": safe_float(indicators.get("atr14")),
                "sma50": safe_float(indicators.get("sma50")),
                "sma200": safe_float(indicators.get("sma200")),
                "rsi14": safe_float(indicators.get("rsi14")),
                "macd": safe_float(indicators.get("macd")),
                "macd_signal": safe_float(indicators.get("macd_signal")),
            }

            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "ts": (
                    datetime.fromtimestamp(indicators["ts"])
                    if isinstance(indicators["ts"], int | float)
                    else indicators["ts"]
                ),
                "score": score,
                "valid": valid,
                "regime": regime,
                "meta": json.dumps(meta),
            }

        except Exception as e:
            self.logger.error(f"Ошибка расчета контекста для {symbol} {timeframe}: {e}")
            return None

    def _calculate_trend_score(self, indicators: dict) -> float:
        """Рассчитывает trend score на основе индикаторов"""
        try:
            # Конвертируем Decimal в float для математических операций
            def safe_float(value):
                if value is None:
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None

            # Основные компоненты тренда
            ema_trend = 0.0
            ema21 = safe_float(indicators.get("ema21"))
            ema55 = safe_float(indicators.get("ema_55"))

            if ema21 is not None and ema55 is not None and ema55 != 0:
                ema_diff = (ema21 - ema55) / ema55
                ema_trend = math.tanh(ema_diff * 10)  # Нормализация через tanh

            # ADX компонент (сила тренда)
            adx_factor = 0.0
            adx14 = safe_float(indicators.get("adx14"))
            if adx14 is not None:
                adx_factor = min(adx14 / 100.0, 1.0)

            # Волатильность компонент (используем ATR вместо vol_std_20)
            vol_factor = 1.0
            atr14 = safe_float(indicators.get("atr14"))
            if atr14 is not None:
                # Нормализуем ATR (можно настроить под конкретный рынок)
                vol_factor = min(atr14 / 0.01, 2.0)  # Примерная нормализация

            # Итоговый score
            score = ema_trend * adx_factor * vol_factor

            # Ограничиваем диапазон
            return max(-1.0, min(1.0, score))

        except Exception as e:
            self.logger.error(f"Ошибка расчета trend score: {e}")
            return 0.0

    def _determine_regime(self, indicators: dict, score: float) -> str:
        """Определяет режим рынка для старших TF"""
        try:
            # Конвертируем Decimal в float
            def safe_float(value):
                if value is None:
                    return 0.0
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return 0.0

            adx = safe_float(indicators.get("adx14"))

            if adx > 25:  # Сильный тренд
                return "trend_bull" if score > 0 else "trend_bear"
            # Слабый тренд или боковик
            return "range_bull" if score > 0 else "range_bear"

        except Exception as e:
            self.logger.error(f"Ошибка определения режима: {e}")
            return "unknown"

    async def _save_context_data(self, session, context_data: list[dict]) -> None:
        """Сохраняет контекстные данные в mtf.context"""
        for context in context_data:
            query = text(
                """
                INSERT INTO mtf.context (symbol, timeframe, ts, score, valid, regime, meta)
                VALUES (:symbol, :timeframe, :ts, :score, :valid, :regime, :meta)
            """
            )

            await session.execute(query, context)

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

        result = await session.execute(query, {"timeframes": self.CONTEXT_TFS})
        return [row[0] for row in result.fetchall()]


# Глобальный экземпляр загрузчика
context_loader = ContextLoader()
