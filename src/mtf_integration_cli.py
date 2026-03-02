#!/usr/bin/env python3
"""
CLI для интеграции MTF данных с существующими системами

Предоставляет команды для:
- Расчёта позиций с MTF интеграцией
- Scoring с MTF интеграцией
- Рекомендаций с MTF интеграцией
- Валидации MTF выравнивания
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text

from src.database import get_async_session
from src.logging_config import setup_logging
from src.mtf.integrator import mtf_integrator
from src.positions.calculator_mtf import MTFEnhancedPositionCalculator
from src.scoring_engine.compute_mtf import mtf_scoring_engine
from src.trade_recommender.batch_recommendations import get_all_score_ids
from src.trade_recommender.recommend_mtf import mtf_trade_recommender

setup_logging("mtf_integration.log")
logger = logging.getLogger(__name__)


async def calculate_positions_with_mtf(
    symbol: str | None = None, mtf_weight: float = 0.3
):
    """
    Рассчитывает позиции с MTF интеграцией

    Args:
        symbol: Конкретный символ (если None, обрабатываются все SWAP)
        mtf_weight: Вес MTF сигнала
    """
    try:
        logger.info("💰 Запуск расчёта позиций с MTF интеграцией...")

        async for session in get_async_session():
            try:
                # Получаем все SWAP инструменты
                query = text(
                    """
                    SELECT symbol, margin_mode, tick_size, lot_size,
                           maker_fee, taker_fee, maintenance_margin_rate,
                           max_leverage, funding_rate, contract_val,
                           settle_ccy, ct_type, min_sz, max_sz, min_notional
                    FROM instruments
                    WHERE symbol LIKE '%-SWAP'
                """
                )

                if symbol:
                    query = text(
                        """
                        SELECT symbol, margin_mode, tick_size, lot_size,
                               maker_fee, taker_fee, maintenance_margin_rate,
                               max_leverage, funding_rate, contract_val,
                               settle_ccy, ct_type, min_sz, max_sz, min_notional
                        FROM instruments
                        WHERE symbol = :symbol AND symbol LIKE '%-SWAP'
                    """
                    )

                result = await session.execute(
                    query, {"symbol": symbol} if symbol else {}
                )
                instruments = result.fetchall()

                if not instruments:
                    logger.warning("⚠️ Не найдено SWAP инструментов для расчёта позиций")
                    return

                logger.info(f"📊 Найдено {len(instruments)} SWAP инструментов")

                calculator = MTFEnhancedPositionCalculator()
                total_positions = 0
                mtf_enhanced = 0

                for instrument in instruments:
                    try:
                        sym = instrument.symbol
                        logger.info(f"🔍 Обработка {sym} с MTF интеграцией...")

                        # Получаем последние OHLCV данные
                        ohlcv_query = text(
                            """
                            SELECT open, high, low, close, volume, ts as timestamp
                            FROM ohlcv
                            WHERE symbol = :symbol
                            ORDER BY ts DESC
                            LIMIT 300
                        """
                        )

                        ohlcv_result = await session.execute(
                            ohlcv_query, {"symbol": sym}
                        )
                        ohlcv_rows = ohlcv_result.fetchall()

                        if len(ohlcv_rows) < 200:
                            logger.warning(
                                f"⚠️ Недостаточно данных для {sym}: {len(ohlcv_rows)} баров"
                            )
                            continue

                        # Преобразуем OHLCV данные
                        ohlcv_data = []
                        for row in ohlcv_rows:
                            ohlcv_data.append(
                                {
                                    "open": float(row.open) if row.open else 0,
                                    "high": float(row.high) if row.high else 0,
                                    "low": float(row.low) if row.low else 0,
                                    "close": float(row.close) if row.close else 0,
                                    "volume": float(row.volume) if row.volume else 0,
                                    "timestamp": (
                                        int(row.timestamp) if row.timestamp else 0
                                    ),
                                }
                            )

                        # Формируем данные для расчёта позиции
                        position_data = {
                            "symbol": sym,
                            "margin_mode": instrument.margin_mode or "isolated",
                            "tick_size": instrument.tick_size or 0.01,
                            "lot_size": instrument.lot_size or 1,
                            "maker_fee": instrument.maker_fee or 0.0001,
                            "taker_fee": instrument.taker_fee or 0.0005,
                            "maintenance_margin_rate": instrument.maintenance_margin_rate
                            or 0.005,
                            "max_leverage": min(instrument.max_leverage or 100, 1000),
                            "funding_rate": instrument.funding_rate or 0.0001,
                            "spot_ohlcv": ohlcv_data,
                            "swap_ohlcv": ohlcv_data,
                            "P_last": ohlcv_data[0]["close"],
                            "balance_usdt": 10000,
                            "risk_per_trade_pct": 0.02,
                            "leverage_target": 10,
                            "direction": "long",
                            "stop_method": "percent",
                            "stop_value": 0.03,
                            "tp_levels_pct": [0.03, 0.06],
                            "order_type_entry": "market",
                            "slippage_pct": 0.001,
                            "consensus_threshold": 0.05,
                            "timeframe_entry": "1m",
                            "signal_age_max": 60,
                        }

                        # Рассчитываем позицию с MTF интеграцией
                        result = await calculator.calculate_position_with_mtf(
                            position_data, use_mtf=True, mtf_weight=mtf_weight
                        )

                        if result.is_valid:
                            logger.info(
                                f"✅ {sym}: MTF-улучшенная позиция рассчитана успешно"
                            )
                            logger.info(f"   Размер: {result.position_size}")
                            logger.info(
                                f"   Стоимость: {result.position_value_usdt} USDT"
                            )
                            logger.info(f"   Риск: {result.risk_amount_usdt} USDT")

                            # Проверяем MTF выравнивание
                            mtf_validation = await calculator.validate_mtf_alignment(
                                sym, "long"
                            )
                            if mtf_validation.get("is_aligned"):
                                mtf_enhanced += 1
                                logger.info(f"🧭 {sym}: MTF выравнивание подтверждено")
                            else:
                                logger.warning(
                                    f"⚠️ {sym}: MTF выравнивание не подтверждено - {mtf_validation.get('reason')}"
                                )

                            total_positions += 1
                        else:
                            logger.warning(f"⚠️ {sym}: Ошибка расчёта позиции")
                            for error in result.validation_errors:
                                logger.warning(f"   {error}")

                    except Exception as e:
                        logger.error(f"❌ Ошибка при обработке {sym}: {e}")
                        continue

                logger.info(f"🎉 Всего рассчитано {total_positions} позиций")
                logger.info(f"🧭 MTF-улучшенных: {mtf_enhanced}")
                if total_positions > 0:
                    mtf_rate = mtf_enhanced / total_positions * 100
                    logger.info(f"📈 MTF улучшение: {mtf_rate:.1f}%")
                break

            except Exception as e:
                logger.error(f"❌ Ошибка при работе с базой данных: {e}")
                break

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при расчёте позиций с MTF: {e}")
        raise


async def calculate_scoring_with_mtf(
    symbol: str | None = None, mtf_weight: float = 0.25
):
    """
    Рассчитывает scores с MTF интеграцией

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)
        mtf_weight: Вес MTF сигнала
    """
    try:
        logger.info("🎯 Запуск расчёта scores с MTF интеграцией...")

        async for session in get_async_session():
            try:
                # Получаем символы для обработки
                if symbol:
                    symbols = [symbol]
                else:
                    query = text(
                        "SELECT DISTINCT symbol FROM indicators WHERE timeframe = '1m'"
                    )
                    result = await session.execute(query)
                    symbols = [row[0] for row in result.fetchall()]

                logger.info(f"📊 Найдено {len(symbols)} символов для MTF scoring")

                # Получаем MTF-улучшенные scores
                mtf_scores = await mtf_scoring_engine.get_mtf_enhanced_scores(
                    symbols, "1m", use_mtf=True
                )

                total_scores = 0
                mtf_aligned = 0

                for sym, score_result in mtf_scores.items():
                    try:
                        logger.info(
                            f"📊 {sym}: MTF-улучшенный score = {score_result.score_calibrated:.3f}"
                        )

                        # Проверяем MTF выравнивание
                        mtf_validation = (
                            await mtf_scoring_engine.validate_mtf_score_alignment(
                                sym, score_result
                            )
                        )

                        if mtf_validation.get("is_aligned"):
                            mtf_aligned += 1
                            logger.info(f"🧭 {sym}: MTF выравнивание подтверждено")
                        else:
                            logger.warning(
                                f"⚠️ {sym}: MTF выравнивание не подтверждено - {mtf_validation.get('reason')}"
                            )

                        total_scores += 1

                    except Exception as e:
                        logger.error(f"❌ Ошибка при обработке score для {sym}: {e}")
                        continue

                logger.info(f"🎉 Всего обработано {total_scores} scores")
                logger.info(f"🧭 MTF-выровненных: {mtf_aligned}")
                if total_scores > 0:
                    mtf_rate = mtf_aligned / total_scores * 100
                    logger.info(f"📈 MTF выравнивание: {mtf_rate:.1f}%")
                break

            except Exception as e:
                logger.error(f"❌ Ошибка при работе с базой данных: {e}")
                break

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при расчёте scores с MTF: {e}")
        raise


async def calculate_recommendations_with_mtf(
    limit: int | None = None, mtf_weight: float = 0.3
):
    """
    Рассчитывает рекомендации с MTF интеграцией

    Args:
        limit: Ограничение количества записей
        mtf_weight: Вес MTF сигнала
    """
    try:
        logger.info("🎯 Запуск генерации рекомендаций с MTF интеграцией...")

        async for session in get_async_session():
            try:
                # Получаем все score_ids
                all_score_ids = await get_all_score_ids(session)

                if not all_score_ids:
                    logger.warning("⚠️ Нет score_results для генерации рекомендаций")
                    return

                # Применяем ограничения
                score_ids = all_score_ids
                if limit:
                    score_ids = score_ids[:limit]
                    logger.info(
                        f"📊 Ограничение: обработаем {len(score_ids)} записей из {len(all_score_ids)}"
                    )

                logger.info(
                    f"📊 Найдено {len(score_ids)} score_results для MTF обработки"
                )

                # Обрабатываем MTF-улучшенные рекомендации
                results = await mtf_trade_recommender.get_mtf_enhanced_recommendations(
                    score_ids, dry_run=False, use_mtf=True
                )

                # Выводим итоговую статистику
                logger.info("📊 ИТОГОВАЯ СТАТИСТИКА MTF-РЕКОМЕНДАЦИЙ:")
                logger.info(f"📋 Всего записей: {results['total']}")
                logger.info(f"✅ Обработано: {results['processed']}")
                logger.info(f"🎯 Готовых рекомендаций: {results['ready']}")
                logger.info(f"🧭 MTF-выровненных: {results['mtf_aligned']}")
                logger.info(f"❌ Отклонённых: {results['rejected']}")
                logger.info(f"💥 Ошибок: {results['errors']}")

                if results["ready"] > 0:
                    mtf_alignment_rate = results["mtf_aligned"] / results["ready"] * 100
                    logger.info(f"📈 MTF выравнивание: {mtf_alignment_rate:.1f}%")

                logger.info("✅ MTF-интегрированная генерация рекомендаций завершена!")
                break

            except Exception as e:
                logger.error(f"❌ Ошибка при работе с базой данных: {e}")
                break

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при генерации рекомендаций с MTF: {e}")
        raise


async def validate_mtf_alignment(symbol: str):
    """
    Валидирует MTF выравнивание для символа

    Args:
        symbol: Торговый символ
    """
    try:
        logger.info(f"🧭 Валидация MTF выравнивания для {symbol}...")

        # Получаем MTF сигнал
        mtf_data = await mtf_integrator.get_latest_mtf_signal(symbol)
        if not mtf_data:
            logger.warning(f"⚠️ MTF сигнал не найден для {symbol}")
            return

        # Анализируем MTF сигнал
        mtf_direction = mtf_integrator.get_mtf_direction(mtf_data)
        mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)
        mtf_strength = mtf_integrator.get_mtf_strength(mtf_data)

        logger.info(f"📊 MTF анализ для {symbol}:")
        logger.info(f"  Направление: {mtf_direction}")
        logger.info(f"  Уверенность: {mtf_confidence:.3f}")
        logger.info(f"  Сила: {mtf_strength}")
        logger.info(f"  Context Score: {mtf_data.context_score:.3f}")
        logger.info(f"  Bias: {mtf_data.bias}")
        logger.info(f"  P(Up): {mtf_data.p_reversal_up:.3f}")
        logger.info(f"  P(Down): {mtf_data.p_reversal_down:.3f}")

        # Проверяем выравнивание с позициями
        calculator = MTFEnhancedPositionCalculator()
        position_alignment = await calculator.validate_mtf_alignment(symbol, "long")
        logger.info(f"📊 Выравнивание с позициями: {position_alignment}")

        # Проверяем выравнивание с scores
        async for session in get_async_session():
            try:
                query = text(
                    """
                    SELECT * FROM score_results
                    WHERE symbol = :symbol
                    ORDER BY ts DESC
                    LIMIT 1
                """
                )
                result = await session.execute(query, {"symbol": symbol})
                score_row = result.fetchone()

                if score_row:
                    from src.scoring_engine.models import ScoreResult

                    score_result = ScoreResult(
                        symbol=score_row.symbol,
                        timeframe=score_row.timeframe,
                        ts=score_row.ts,
                        score_raw=score_row.score_raw,
                        score_calibrated=score_row.score_calibrated,
                        p_win=score_row.p_win,
                        edge_net=score_row.edge_net,
                        confidence=score_row.confidence,
                        is_valid=score_row.is_valid,
                        reasons=score_row.reasons,
                    )

                    score_alignment = (
                        await mtf_scoring_engine.validate_mtf_score_alignment(
                            symbol, score_result
                        )
                    )
                    logger.info(f"📊 Выравнивание с scores: {score_alignment}")
                break

            except Exception as e:
                logger.error(f"❌ Ошибка при получении score для {symbol}: {e}")
                break

        logger.info(f"✅ MTF валидация для {symbol} завершена")

    except Exception as e:
        logger.error(f"❌ Ошибка при MTF валидации для {symbol}: {e}")
        raise


def create_parser():
    """Создает парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="CLI для интеграции MTF данных с существующими системами"
    )

    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # Команда для расчёта позиций с MTF
    positions_parser = subparsers.add_parser(
        "positions", help="Расчёт позиций с MTF интеграцией"
    )
    positions_parser.add_argument("--symbol", "-s", type=str, help="Конкретный символ")
    positions_parser.add_argument(
        "--mtf-weight", "-w", type=float, default=0.3, help="Вес MTF сигнала (0.0-1.0)"
    )

    # Команда для расчёта scores с MTF
    scoring_parser = subparsers.add_parser(
        "scoring", help="Расчёт scores с MTF интеграцией"
    )
    scoring_parser.add_argument("--symbol", "-s", type=str, help="Конкретный символ")
    scoring_parser.add_argument(
        "--mtf-weight", "-w", type=float, default=0.25, help="Вес MTF сигнала (0.0-1.0)"
    )

    # Команда для рекомендаций с MTF
    recommendations_parser = subparsers.add_parser(
        "recommendations", help="Генерация рекомендаций с MTF интеграцией"
    )
    recommendations_parser.add_argument(
        "--limit", "-l", type=int, help="Ограничение количества записей"
    )
    recommendations_parser.add_argument(
        "--mtf-weight", "-w", type=float, default=0.3, help="Вес MTF сигнала (0.0-1.0)"
    )

    # Команда для валидации MTF
    validate_parser = subparsers.add_parser(
        "validate", help="Валидация MTF выравнивания"
    )
    validate_parser.add_argument(
        "--symbol", "-s", type=str, required=True, help="Торговый символ"
    )

    return parser


async def main():
    """Основная функция."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "positions":
            await calculate_positions_with_mtf(args.symbol, args.mtf_weight)
        elif args.command == "scoring":
            await calculate_scoring_with_mtf(args.symbol, args.mtf_weight)
        elif args.command == "recommendations":
            await calculate_recommendations_with_mtf(args.limit, args.mtf_weight)
        elif args.command == "validate":
            await validate_mtf_alignment(args.symbol)
        else:
            logger.error(f"Неизвестная команда: {args.command}")

    except Exception as e:
        logger.error(f"Ошибка выполнения команды {args.command}: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
