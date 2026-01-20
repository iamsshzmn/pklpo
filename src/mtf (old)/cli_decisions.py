#!/usr/bin/env python3
"""
MTF Decision CLI - Интерфейс для принятия торговых решений

Предоставляет читаемый интерфейс для анализа и принятия решений
"""

import argparse
import asyncio
import logging

from src.mtf.decision_maker import ConfidenceLevel, SignalType, decision_maker

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def print_header(title: str):
    """Печать заголовка"""
    print("\n" + "=" * 60)
    print(f"🎯 {title}")
    print("=" * 60)


def print_decision(decision):
    """Печать торгового решения"""
    print_header(f"ТОРГОВОЕ РЕШЕНИЕ: {decision.symbol}")

    # Основное решение
    signal_emoji = (
        "🟢"
        if decision.decision == SignalType.LONG
        else "🔴"
        if decision.decision == SignalType.SHORT
        else "⚪"
    )
    signal_text = (
        "LONG"
        if decision.decision == SignalType.LONG
        else "SHORT"
        if decision.decision == SignalType.SHORT
        else "FLAT"
    )
    confidence_emoji = (
        "🟢"
        if decision.confidence == ConfidenceLevel.HIGH
        else "🟡"
        if decision.confidence == ConfidenceLevel.MEDIUM
        else "🔴"
    )

    print(f"📊 Решение: {signal_emoji} {signal_text}")
    print(f"🎯 Уверенность: {confidence_emoji} {decision.confidence.value.upper()}")
    print(f"⏰ Горизонт: {decision.horizon}")
    print(f"⚠️  Уровень риска: {decision.risk_level}")
    print(f"🕐 Время анализа: {decision.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    # Обоснование
    print("\n💭 Обоснование:")
    for i, reason in enumerate(decision.reasoning, 1):
        print(f"   {i}. {reason}")

    # Анализ контекста
    print("\n📈 Анализ контекста:")
    for ctx in decision.context_analysis:
        status = "✅" if ctx.valid else "❌"
        confidence_icon = (
            "🟢"
            if ctx.confidence == ConfidenceLevel.HIGH
            else "🟡"
            if ctx.confidence == ConfidenceLevel.MEDIUM
            else "🔴"
        )
        print(f"   {status} {confidence_icon} {ctx.description}")

    # Анализ триггеров
    if decision.trigger_analysis:
        print("\n⚡ Анализ триггеров:")
        for trigger in decision.trigger_analysis:
            confidence_icon = (
                "🟢"
                if trigger.confidence == ConfidenceLevel.HIGH
                else "🟡"
                if trigger.confidence == ConfidenceLevel.MEDIUM
                else "🔴"
            )
            print(f"   {confidence_icon} {trigger.description}")

    # Consensus анализ
    consensus_icon = (
        "🟢"
        if decision.consensus_analysis.confidence == ConfidenceLevel.HIGH
        else (
            "🟡"
            if decision.consensus_analysis.confidence == ConfidenceLevel.MEDIUM
            else "🔴"
        )
    )
    print("\n🎯 Consensus анализ:")
    print(f"   {consensus_icon} {decision.consensus_analysis.description}")

    # Условия входа
    print("\n🚪 Условия для входа:")
    for i, condition in enumerate(decision.entry_conditions, 1):
        print(f"   {i}. {condition}")

    # Условия выхода
    print("\n🚪 Условия для выхода:")
    for i, condition in enumerate(decision.exit_conditions, 1):
        print(f"   {i}. {condition}")

    print("\n" + "=" * 60)


def print_market_overview(overview: list[dict]):
    """Печать обзора рынка"""
    print_header("ОБЗОР РЫНКА - ТОП СИГНАЛОВ")

    if not overview:
        print("❌ Нет активных сигналов")
        return

    print(f"{'Символ':<15} {'Горизонт':<12} {'Сигнал':<8} {'Score':<8} {'Время':<20}")
    print("-" * 70)

    for signal in overview:
        signal_emoji = (
            "🟢"
            if signal["signal_type"] == "LONG"
            else "🔴"
            if signal["signal_type"] == "SHORT"
            else "⚪"
        )
        time_str = signal["ts"].strftime("%m-%d %H:%M") if signal["ts"] else "N/A"
        print(
            f"{signal['symbol']:<15} {signal['horizon']:<12} {signal_emoji} {signal['signal_type']:<6} {signal['score']:<8.2f} {time_str:<20}"
        )


def print_swing_opportunities(opportunities: list[dict]):
    """Печать swing возможностей"""
    print_header("SWING ТОРГОВЫЕ ВОЗМОЖНОСТИ")

    if not opportunities:
        print("❌ Нет swing возможностей")
        return

    print(f"{'Символ':<15} {'Сигнал':<8} {'Score':<8} {'Context':<8} {'Режим':<15}")
    print("-" * 60)

    for opp in opportunities:
        signal_emoji = "🟢" if opp["side"] == 1 else "🔴" if opp["side"] == -1 else "⚪"
        signal_text = (
            "LONG" if opp["side"] == 1 else "SHORT" if opp["side"] == -1 else "FLAT"
        )
        regime = opp.get("regime", "N/A")
        print(
            f"{opp['symbol']:<15} {signal_emoji} {signal_text:<6} {opp['score']:<8.2f} {opp['context_score']:<8.2f} {regime:<15}"
        )


def print_intraday_signals(signals: list[dict]):
    """Печать внутридневных сигналов"""
    print_header("ВНУТРИДНЕВНЫЕ СИГНАЛЫ")

    if not signals:
        print("❌ Нет внутридневных сигналов")
        return

    print(
        f"{'Символ':<15} {'Сигнал':<8} {'Score':<8} {'P(Up)':<8} {'P(Down)':<8} {'Accel':<6}"
    )
    print("-" * 65)

    for signal in signals:
        signal_emoji = (
            "🟢" if signal["side"] == 1 else "🔴" if signal["side"] == -1 else "⚪"
        )
        signal_text = (
            "LONG"
            if signal["side"] == 1
            else "SHORT"
            if signal["side"] == -1
            else "FLAT"
        )
        accel_text = str(signal.get("accel", "N/A"))
        print(
            f"{signal['symbol']:<15} {signal_emoji} {signal_text:<6} {signal['score']:<8.2f} {signal['p_up']:<8.2f} {signal['p_down']:<8.2f} {accel_text:<6}"
        )


async def analyze_symbol(symbol: str):
    """Анализ одного символа"""
    try:
        print(f"🔍 Анализирую {symbol}...")
        decision = await decision_maker.analyze_symbol(symbol)
        print_decision(decision)
    except Exception as e:
        logger.error(f"Ошибка анализа {symbol}: {e}")
        print(f"❌ Ошибка анализа {symbol}: {e}")


async def show_market_overview(limit: int = 20):
    """Показать обзор рынка"""
    try:
        print(f"📊 Получаю обзор рынка (топ {limit})...")
        overview = await decision_maker.get_market_overview(limit)
        print_market_overview(overview)
    except Exception as e:
        logger.error(f"Ошибка получения обзора рынка: {e}")
        print(f"❌ Ошибка получения обзора рынка: {e}")


async def show_swing_opportunities():
    """Показать swing возможности"""
    try:
        print("📈 Ищу swing торговые возможности...")
        opportunities = await decision_maker.get_swing_opportunities()
        print_swing_opportunities(opportunities)
    except Exception as e:
        logger.error(f"Ошибка поиска swing возможностей: {e}")
        print(f"❌ Ошибка поиска swing возможностей: {e}")


async def show_intraday_signals():
    """Показать внутридневные сигналы"""
    try:
        print("⚡ Ищу внутридневные сигналы...")
        signals = await decision_maker.get_intraday_signals()
        print_intraday_signals(signals)
    except Exception as e:
        logger.error(f"Ошибка поиска внутридневных сигналов: {e}")
        print(f"❌ Ошибка поиска внутридневных сигналов: {e}")


async def main():
    """Главная функция CLI"""
    parser = argparse.ArgumentParser(description="MTF Decision Maker CLI")
    parser.add_argument(
        "command",
        choices=["analyze", "overview", "swing", "intraday"],
        help="Команда для выполнения",
    )
    parser.add_argument("--symbol", "-s", help="Символ для анализа")
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=20,
        help="Лимит для обзора рынка (по умолчанию: 20)",
    )

    args = parser.parse_args()

    if args.command == "analyze":
        if not args.symbol:
            print("❌ Для команды 'analyze' требуется указать символ (--symbol)")
            return
        await analyze_symbol(args.symbol)

    elif args.command == "overview":
        await show_market_overview(args.limit)

    elif args.command == "swing":
        await show_swing_opportunities()

    elif args.command == "intraday":
        await show_intraday_signals()


if __name__ == "__main__":
    asyncio.run(main())
