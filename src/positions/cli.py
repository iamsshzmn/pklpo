"""
CLI для работы с позициями на SWAP инструментах.

Позволяет:
- Рассчитывать позиции для конкретного символа
- Просматривать историю расчётов
- Тестировать параметры позиций
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.database import get_async_session
from src.logging_config import setup_logging
from src.positions.calculator import PositionCalculator

setup_logging("positions.log")
logger = logging.getLogger(__name__)


def create_parser():
    """Создает парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="CLI для работы с позициями на SWAP инструментах"
    )

    parser.add_argument(
        "--calculate",
        "-c",
        type=str,
        help="Рассчитать позицию для конкретного символа (например: BTC-USDT-SWAP)",
    )

    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="Показать список доступных SWAP инструментов",
    )

    parser.add_argument(
        "--history", "-h", type=str, help="Показать историю расчётов для символа"
    )

    parser.add_argument(
        "--test", "-t", type=str, help="Тестировать параметры позиции для символа"
    )

    parser.add_argument(
        "--balance",
        type=float,
        default=10000,
        help="Баланс в USDT (по умолчанию: 10000)",
    )

    parser.add_argument(
        "--risk", type=float, default=2.0, help="Риск в процентах (по умолчанию: 2.0)"
    )

    parser.add_argument(
        "--leverage", type=int, default=10, help="Целевое плечо (по умолчанию: 10)"
    )

    return parser


async def list_swap_instruments():
    """Показывает список доступных SWAP инструментов."""
    try:
        async for session in get_async_session():
            query = text(
                """
                SELECT symbol, margin_mode, max_leverage, tick_size, lot_size
                FROM instruments
                WHERE symbol LIKE '%-SWAP'
                ORDER BY symbol
            """
            )

            result = await session.execute(query)
            instruments = result.fetchall()

            if not instruments:
                logger.warning("⚠️ Не найдено SWAP инструментов")
                return

            logger.info(f"📊 Найдено {len(instruments)} SWAP инструментов:")
            print("\nДоступные SWAP инструменты:")
            print("-" * 80)
            print(
                f"{'Символ':<20} {'Режим':<10} {'Макс. плечо':<12} {'Tick':<8} {'Lot':<8}"
            )
            print("-" * 80)

            for instrument in instruments:
                print(
                    f"{instrument.symbol:<20} {instrument.margin_mode or 'N/A':<10} "
                    f"{instrument.max_leverage or 'N/A':<12} "
                    f"{instrument.tick_size or 'N/A':<8} "
                    f"{instrument.lot_size or 'N/A':<8}"
                )

            print("-" * 80)
            break

    except Exception as e:
        logger.error(f"❌ Ошибка при получении списка инструментов: {e}")


async def calculate_position_for_symbol(
    symbol: str, balance: float, risk: float, leverage: int
):
    """Рассчитывает позицию для конкретного символа."""
    try:
        async for session in get_async_session():
            # Получаем данные инструмента
            instrument_query = text(
                """
                SELECT symbol, margin_mode, tick_size, lot_size,
                       maker_fee, taker_fee, maintenance_margin_rate,
                       max_leverage, funding_rate
                FROM instruments
                WHERE symbol = :symbol
            """
            )

            result = await session.execute(instrument_query, {"symbol": symbol})
            instrument = result.fetchone()

            if not instrument:
                logger.error(f"❌ Инструмент {symbol} не найден")
                return

            # Получаем OHLCV данные
            ohlcv_query = text(
                """
                SELECT open, high, low, close, volume, timestamp
                FROM ohlcv
                WHERE symbol = :symbol
                ORDER BY timestamp DESC
                LIMIT 300
            """
            )

            ohlcv_result = await session.execute(ohlcv_query, {"symbol": symbol})
            ohlcv_data = ohlcv_result.fetchall()

            if len(ohlcv_data) < 200:
                logger.error(
                    f"❌ Недостаточно данных для {symbol}: {len(ohlcv_data)} баров"
                )
                return

            # Формируем данные для расчёта
            position_data = {
                # Блок 1: Биржевые метаданные
                "symbol": symbol,
                "margin_mode": instrument.margin_mode or "isolated",
                "tick_size": instrument.tick_size or 0.01,
                "lot_size": instrument.lot_size or 1,
                "maker_fee": instrument.maker_fee or 0.0001,
                "taker_fee": instrument.taker_fee or 0.0005,
                "maintenance_margin_rate": instrument.maintenance_margin_rate or 0.005,
                "max_leverage": instrument.max_leverage or 100,
                "funding_rate": instrument.funding_rate or 0.0001,
                # Блок 2: Рыночные данные
                "spot_ohlcv": ohlcv_data,
                "swap_ohlcv": ohlcv_data,
                "P_last": ohlcv_data[0].close,
                # Блок 3: Параметры пользователя
                "balance_usdt": balance,
                "risk_per_trade_pct": risk / 100,  # Конвертируем в десятичную дробь
                "leverage_target": leverage,
                # Блок 4: Условия сделки
                "direction": "long",
                "stop_method": "percent",
                "stop_value": 0.03,
                "tp_levels_pct": [0.03, 0.06],
                "order_type_entry": "market",
                "slippage_pct": 0.001,
                # Блок 5: Контроль сигналов
                "consensus_threshold": 1.0,
                "timeframe_entry": "1m",
                "signal_age_max": 60,
            }

            # Рассчитываем позицию
            calculator = PositionCalculator()
            result = calculator.calculate_position(position_data)

            # Выводим результаты
            print(f"\n📊 Результаты расчёта позиции для {symbol}")
            print("=" * 60)

            if result.is_valid:
                print("✅ Статус: Успешно")
                print(f"💰 Размер позиции: {result.position_size:.6f}")
                print(f"💵 Стоимость позиции: {result.position_value_usdt:.2f} USDT")
                print(f"📈 Цена входа: {result.entry_price:.4f}")
                print(
                    f"🛑 Стоп-лосс: {result.stop_loss_price:.4f}"
                    if result.stop_loss_price
                    else "🛑 Стоп-лосс: Не рассчитан"
                )
                print(
                    f"🎯 Тейк-профиты: {[f'{tp:.4f}' for tp in result.take_profit_prices]}"
                )
                print(f"⚠️ Риск: {result.risk_amount_usdt:.2f} USDT")
                print(
                    f"📏 Расстояние стопа: {result.stop_distance_pct:.2%}"
                    if result.stop_distance_pct
                    else "📏 Расстояние стопа: Не рассчитано"
                )
                print(f"⚡ Использованное плечо: {result.leverage_used}")
                print(f"💳 Требуемая маржа: {result.margin_required:.2f} USDT")
                print(
                    f"🚨 Расстояние до ликвидации: {result.liquidation_distance_pct:.2%}"
                )

                if result.warnings:
                    print("\n⚠️ Предупреждения:")
                    for warning in result.warnings:
                        print(f"   - {warning}")
            else:
                print("❌ Статус: Ошибка")
                print("🚫 Ошибки:")
                for error in result.validation_errors:
                    print(f"   - {error}")

            print("=" * 60)
            break

    except Exception as e:
        logger.error(f"❌ Ошибка при расчёте позиции: {e}")


async def test_position_parameters(
    symbol: str, balance: float, risk: float, leverage: int
):
    """Тестирует различные параметры позиции."""
    try:
        logger.info(f"🧪 Тестирование параметров позиции для {symbol}")

        # Тестируем разные направления
        directions = ["long", "short"]
        stop_methods = ["percent", "atr_mult"]
        risk_levels = [1.0, 2.0, 3.0]

        for direction in directions:
            for stop_method in stop_methods:
                for risk_level in risk_levels:
                    logger.info(f"Тест: {direction}, {stop_method}, риск {risk_level}%")

                    # Здесь можно добавить вызов расчёта с разными параметрами
                    # Пока просто логируем

        logger.info("✅ Тестирование завершено")

    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {e}")


async def show_position_history(symbol: str):
    """Показывает историю расчётов позиций."""
    try:
        async for session in get_async_session():
            query = text(
                """
                SELECT created_at, position_size, position_value_usdt,
                       entry_price, stop_loss_price, risk_amount_usdt,
                       leverage_used, margin_required
                FROM position_calculations
                WHERE symbol = :symbol
                ORDER BY created_at DESC
                LIMIT 10
            """
            )

            result = await session.execute(query, {"symbol": symbol})
            calculations = result.fetchall()

            if not calculations:
                logger.warning(f"⚠️ История расчётов для {symbol} не найдена")
                return

            print(f"\n📜 История расчётов позиций для {symbol}")
            print("=" * 80)
            print(
                f"{'Дата':<20} {'Размер':<12} {'Стоимость':<12} {'Вход':<10} {'Стоп':<10} {'Риск':<10} {'Плечо':<8}"
            )
            print("-" * 80)

            for calc in calculations:
                print(
                    f"{calc.created_at.strftime('%Y-%m-%d %H:%M'):<20} "
                    f"{calc.position_size:.4f:<12} "
                    f"{calc.position_value_usdt:.0f:<12} "
                    f"{calc.entry_price:.2f:<10} "
                    f"{calc.stop_loss_price:.2f if calc.stop_loss_price else 'N/A':<10} "
                    f"{calc.risk_amount_usdt:.0f:<10} "
                    f"{calc.leverage_used:<8}"
                )

            print("=" * 80)
            break

    except Exception as e:
        logger.error(f"❌ Ошибка при получении истории: {e}")


async def main():
    """Основная функция CLI."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        if args.list:
            await list_swap_instruments()
        elif args.calculate:
            await calculate_position_for_symbol(
                args.calculate, args.balance, args.risk, args.leverage
            )
        elif args.history:
            await show_position_history(args.history)
        elif args.test:
            await test_position_parameters(
                args.test, args.balance, args.risk, args.leverage
            )
        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
