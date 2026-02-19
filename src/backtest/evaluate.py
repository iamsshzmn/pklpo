"""
Оценка качества торговых сигналов.
"""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import text

from src.database import get_async_session
from src.logging_config import setup_logging

from .metrics import calc_metrics


class SignalEvaluator:
    """
    Класс для оценки качества торговых сигналов.
    """

    def __init__(self, commission: float = 0.0005):
        """
        Инициализация оценщика сигналов.

        Args:
            commission: Комиссия за сделку (по умолчанию 0.05%)
        """
        self.commission = commission
        setup_logging("backtest.log")

    async def evaluate_symbol(
        self, symbol: str, timeframe: str = "1m", days_back: int = 7
    ) -> dict:
        """
        Оценивает качество сигналов для конкретного символа.

        Args:
            symbol: Торговый символ
            timeframe: Таймфрейм
            days_back: Количество дней назад для анализа

        Returns:
            Dict: Результаты оценки
        """
        print(f"🔍 Оценка сигналов для {symbol} {timeframe}...")

        async for session in get_async_session():
            try:
                # Получаем сигналы
                signals = await self._fetch_signals(
                    session, symbol, timeframe, days_back
                )

                if not signals:
                    print(f"❌ Нет сигналов для {symbol}")
                    return {}

                # Получаем цены OHLCV
                prices = await self._fetch_prices(session, symbol, timeframe, days_back)

                if not prices:
                    print(f"❌ Нет цен для {symbol}")
                    return {}

                # Рассчитываем метрики
                metrics = calc_metrics(signals, prices, self.commission)

                # Добавляем дополнительную информацию
                result = {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "period_days": days_back,
                    "signals_count": len(signals),
                    "prices_count": len(prices),
                    "commission": self.commission,
                    **metrics,
                }

                print(f"✅ Оценка завершена для {symbol}")
                self._print_metrics(result)

                return result

            except Exception as e:
                print(f"❌ Ошибка при оценке {symbol}: {e}")
                return {}
            finally:
                break
        return None

    async def evaluate_all_symbols(
        self, timeframe: str = "1m", days_back: int = 7
    ) -> list[dict]:
        """
        Оценивает качество сигналов для всех символов.

        Args:
            timeframe: Таймфрейм
            days_back: Количество дней назад для анализа

        Returns:
            List[Dict]: Список результатов оценки
        """
        print("🚀 Оценка сигналов для всех символов...")

        async for session in get_async_session():
            try:
                # Получаем список символов с сигналами
                symbols = await self._fetch_symbols_with_signals(
                    session, timeframe, days_back
                )

                if not symbols:
                    print("❌ Нет символов с сигналами")
                    return []

                print(f"📊 Найдено {len(symbols)} символов для оценки")

                results = []
                for symbol in symbols:
                    result = await self.evaluate_symbol(symbol, timeframe, days_back)
                    if result:
                        results.append(result)

                # Сортируем по Sharpe ratio
                results.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)

                print("\n📈 Топ-5 символов по Sharpe ratio:")
                for i, result in enumerate(results[:5], 1):
                    print(
                        f"   {i}. {result['symbol']}: Sharpe={result['sharpe_ratio']:.2f}, "
                        f"PnL={result['total_pnl_percent']:.2f}%, "
                        f"DD={result['max_drawdown']:.2f}%"
                    )

                return results

            except Exception as e:
                print(f"❌ Ошибка при оценке всех символов: {e}")
                return []
            finally:
                break
        return None

    async def _fetch_signals(
        self, session, symbol: str, timeframe: str, days_back: int
    ) -> list[dict]:
        """Получает сигналы из базы данных."""
        cutoff_time = datetime.now() - timedelta(days=days_back)

        query = text(
            """
            SELECT ts, signal, reason, created_at
            FROM signals
            WHERE symbol = :symbol
            AND timeframe = :timeframe
            AND created_at > :cutoff_time
            ORDER BY ts
        """
        )

        result = await session.execute(
            query,
            {"symbol": symbol, "timeframe": timeframe, "cutoff_time": cutoff_time},
        )

        signals = []
        for row in result.fetchall():
            signals.append(
                {
                    "ts": row.ts,
                    "signal": float(row.signal),
                    "reason": row.reason,
                    "created_at": row.created_at,
                }
            )

        return signals

    async def _fetch_prices(
        self, session, symbol: str, timeframe: str, days_back: int
    ) -> list[dict]:
        """Получает цены OHLCV из базы данных."""
        cutoff_time = datetime.now() - timedelta(days=days_back)

        query = text(
            """
            SELECT ts, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol = :symbol
            AND timeframe = :timeframe
            AND ts >= :cutoff_ts
            ORDER BY ts
        """
        )

        # Конвертируем datetime в timestamp
        cutoff_ts = int(cutoff_time.timestamp() * 1000)

        result = await session.execute(
            query, {"symbol": symbol, "timeframe": timeframe, "cutoff_ts": cutoff_ts}
        )

        prices = []
        for row in result.fetchall():
            prices.append(
                {
                    "ts": row.ts,
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "volume": float(row.volume),
                }
            )

        return prices

    async def _fetch_symbols_with_signals(
        self, session, timeframe: str, days_back: int
    ) -> list[str]:
        """Получает список символов с сигналами."""
        cutoff_time = datetime.now() - timedelta(days=days_back)

        query = text(
            """
            SELECT DISTINCT symbol
            FROM signals
            WHERE timeframe = :timeframe
            AND created_at > :cutoff_time
            ORDER BY symbol
        """
        )

        result = await session.execute(
            query, {"timeframe": timeframe, "cutoff_time": cutoff_time}
        )

        return [row.symbol for row in result.fetchall()]

    def _print_metrics(self, metrics: dict):
        """Выводит метрики в консоль."""
        print(f"   📊 PnL: {metrics['total_pnl_percent']:.2f}%")
        print(f"   📈 Sharpe: {metrics['sharpe_ratio']:.2f}")
        print(f"   📉 Max DD: {metrics['max_drawdown']:.2f}%")
        print(f"   🎯 Win Rate: {metrics['win_rate']:.1f}%")
        print(f"   🔄 Trades: {metrics['total_trades']}")


async def main():
    """Основная функция для запуска оценки."""
    evaluator = SignalEvaluator()

    # Оцениваем все символы
    results = await evaluator.evaluate_all_symbols(days_back=7)

    if results:
        print(f"\n✅ Оценка завершена для {len(results)} символов")

        # Сохраняем результаты в файл
        import json
        from datetime import datetime

        filename = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        print(f"💾 Результаты сохранены в {filename}")
    else:
        print("❌ Нет результатов для оценки")


if __name__ == "__main__":
    asyncio.run(main())
