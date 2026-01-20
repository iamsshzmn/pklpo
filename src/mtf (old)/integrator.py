"""
MTF Data Integrator

Модуль для интеграции MTF данных с существующими системами:
- Position Calculator
- Scoring Engine
- Trade Recommender

Предоставляет дополнительную точку зрения на рынок, не заменяя существующие расчёты.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from src.database import get_async_session

logger = logging.getLogger(__name__)


@dataclass
class MTFSignalData:
    """Данные MTF сигнала"""

    symbol: str
    consensus: int  # 1 (LONG), -1 (SHORT), 0 (FLAT)
    context_score: float | None
    bias: str  # "long", "short", "neutral"
    p_reversal_up: float
    p_reversal_down: float
    combination_votes: dict[str, Any]
    timeframe: str
    calculated_at: datetime
    signal_age_bars: int


class MTFIntegrator:
    """Интегратор MTF данных"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def get_latest_mtf_signal(
        self, symbol: str, max_age_hours: int = 24
    ) -> MTFSignalData | None:
        """
        Получает последний MTF сигнал для символа

        Args:
            symbol: Торговый символ
            max_age_hours: Максимальный возраст сигнала в часах

        Returns:
            MTFSignalData или None если сигнал не найден/устарел
        """
        try:
            async for session in get_async_session():
                # Получаем последний MTF сигнал
                query = text(
                    """
                    SELECT symbol, signal_consensus, signal_timeframe,
                           calculated_at, signal_age_bars, input_data
                    FROM mtf_signals
                    WHERE symbol = :symbol
                    AND calculated_at >= :min_time
                    ORDER BY calculated_at DESC
                    LIMIT 1
                """
                )

                min_time = datetime.utcnow() - timedelta(hours=max_age_hours)

                result = await session.execute(
                    query, {"symbol": symbol, "min_time": min_time}
                )

                row = result.fetchone()
                if not row:
                    self.logger.debug(f"MTF сигнал не найден для {symbol}")
                    return None

                # Парсим input_data
                input_data = row.input_data if hasattr(row, "input_data") else {}

                mtf_data = MTFSignalData(
                    symbol=row.symbol,
                    consensus=row.signal_consensus,
                    context_score=input_data.get("context_score"),
                    bias=input_data.get("bias", "neutral"),
                    p_reversal_up=input_data.get("p_reversal_up", 0.0),
                    p_reversal_down=input_data.get("p_reversal_down", 0.0),
                    combination_votes=input_data.get("combination_votes", {}),
                    timeframe=row.signal_timeframe,
                    calculated_at=row.calculated_at,
                    signal_age_bars=row.signal_age_bars,
                )

                self.logger.info(
                    f"MTF сигнал для {symbol}: consensus={mtf_data.consensus}, "
                    f"bias={mtf_data.bias}, context_score={mtf_data.context_score:.3f}"
                )
                return mtf_data

        except Exception as e:
            self.logger.error(f"Ошибка при получении MTF сигнала для {symbol}: {e}")
            return None

    async def get_mtf_signals_batch(
        self, symbols: list[str], max_age_hours: int = 24
    ) -> dict[str, MTFSignalData]:
        """
        Получает MTF сигналы для списка символов

        Args:
            symbols: Список символов
            max_age_hours: Максимальный возраст сигнала в часах

        Returns:
            Словарь {symbol: MTFSignalData}
        """
        results = {}

        for symbol in symbols:
            mtf_data = await self.get_latest_mtf_signal(symbol, max_age_hours)
            if mtf_data:
                results[symbol] = mtf_data

        self.logger.info(
            f"Получено {len(results)} MTF сигналов из {len(symbols)} символов"
        )
        return results

    def calculate_mtf_confidence(self, mtf_data: MTFSignalData) -> float:
        """
        Рассчитывает уверенность MTF сигнала

        Args:
            mtf_data: Данные MTF сигнала

        Returns:
            Уверенность от 0 до 1
        """
        if not mtf_data:
            return 0.0

        # Базовая уверенность на основе consensus
        base_confidence = 0.5 if mtf_data.consensus != 0 else 0.0

        # Дополнительная уверенность на основе context_score
        context_confidence = 0.0
        if mtf_data.context_score is not None:
            context_confidence = min(abs(mtf_data.context_score) / 0.5, 1.0) * 0.3

        # Дополнительная уверенность на основе вероятностей разворота
        reversal_confidence = 0.0
        if mtf_data.consensus == 1:  # LONG
            reversal_confidence = mtf_data.p_reversal_up * 0.2
        elif mtf_data.consensus == -1:  # SHORT
            reversal_confidence = mtf_data.p_reversal_down * 0.2

        # Штраф за возраст сигнала
        age_penalty = min(mtf_data.signal_age_bars / 10.0, 0.3)

        total_confidence = (
            base_confidence + context_confidence + reversal_confidence - age_penalty
        )
        return max(0.0, min(1.0, total_confidence))

    def get_mtf_direction(self, mtf_data: MTFSignalData) -> str:
        """
        Получает направление MTF сигнала

        Args:
            mtf_data: Данные MTF сигнала

        Returns:
            "LONG", "SHORT", "FLAT"
        """
        if not mtf_data:
            return "FLAT"

        if mtf_data.consensus == 1:
            return "LONG"
        if mtf_data.consensus == -1:
            return "SHORT"
        return "FLAT"

    def get_mtf_strength(self, mtf_data: MTFSignalData) -> str:
        """
        Получает силу MTF сигнала

        Args:
            mtf_data: Данные MTF сигнала

        Returns:
            "STRONG", "MODERATE", "WEAK"
        """
        if not mtf_data:
            return "WEAK"

        confidence = self.calculate_mtf_confidence(mtf_data)

        if confidence >= 0.7:
            return "STRONG"
        if confidence >= 0.4:
            return "MODERATE"
        return "WEAK"


# Глобальный экземпляр интегратора
mtf_integrator = MTFIntegrator()
