"""
Тестовый скрипт для модуля торговых рекомендаций
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.trade_recommender.position_model import calculate_position
from src.trade_recommender.recommend import recommend_for_score

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_position_model():
    """Тестирует функцию расчёта позиции"""
    print("\n🧪 ТЕСТ: position_model.py")
    print("=" * 50)

    # Тест 1: LONG позиция
    try:
        result = calculate_position(
            symbol="XRP-USDT",
            direction="LONG",
            entry_price=0.620,
            atr=0.0067,
            balance=20.0,
            risk_pct=0.02,
            atr_multiplier=1.5,
            rr_ratio=2.0,
        )

        print("✅ Тест LONG позиции:")
        print(f"  Вход: {result['entry_price']:.6f}")
        print(f"  Стоп: {result['stop_loss_price']:.6f}")
        print(f"  Тейк: {result['take_profit_price']:.6f}")
        print(f"  Размер: {result['position_size']:.2f}")
        print(f"  Риск: ${result['risk_amount_usdt']:.2f}")
        print(f"  Плечо: {result['leverage_used']:.2f}x")

    except Exception as e:
        print(f"❌ Ошибка в тесте LONG: {e}")

    # Тест 2: SHORT позиция
    try:
        result = calculate_position(
            symbol="BTC-USDT",
            direction="SHORT",
            entry_price=45000.0,
            atr=1200.0,
            balance=20.0,
            risk_pct=0.02,
            atr_multiplier=1.5,
            rr_ratio=2.0,
        )

        print("\n✅ Тест SHORT позиции:")
        print(f"  Вход: {result['entry_price']:.2f}")
        print(f"  Стоп: {result['stop_loss_price']:.2f}")
        print(f"  Тейк: {result['take_profit_price']:.2f}")
        print(f"  Размер: {result['position_size']:.4f}")
        print(f"  Риск: ${result['risk_amount_usdt']:.2f}")
        print(f"  Плечо: {result['leverage_used']:.2f}x")

    except Exception as e:
        print(f"❌ Ошибка в тесте SHORT: {e}")

    # Тест 3: Валидация ошибок
    print("\n🧪 Тест валидации:")

    try:
        calculate_position(
            symbol="TEST",
            direction="LONG",
            entry_price=-1.0,  # Отрицательная цена
            atr=0.001,
        )
        print("❌ Ошибка: должна была выбросить исключение")
    except ValueError as e:
        print(f"✅ Правильно обработана ошибка: {e}")

    try:
        calculate_position(
            symbol="TEST",
            direction="LONG",
            entry_price=1.0,
            atr=0.0,  # Нулевой ATR
        )
        print("❌ Ошибка: должна была выбросить исключение")
    except ValueError as e:
        print(f"✅ Правильно обработана ошибка: {e}")


async def test_recommend_for_score():
    """Тестирует функцию генерации рекомендаций"""
    print("\n🧪 ТЕСТ: recommend.py")
    print("=" * 50)

    # Тест с несуществующим score_id
    print("Тест с несуществующим score_id:")
    result = await recommend_for_score(score_id=999999, dry_run=True)
    print(f"  Статус: {result.get('status')}")
    print(f"  Сообщение: {result.get('message')}")

    # Тест с реальным score_id (если есть данные)
    print("\nТест с реальным score_id (если есть данные):")
    # Здесь можно добавить тест с реальным ID из БД
    # result = await recommend_for_score(score_id=4815, dry_run=True)
    # print(f"  Статус: {result.get('status')}")
    # print(f"  Символ: {result.get('symbol')}")
    # print(f"  Направление: {result.get('direction')}")


def test_validation_logic():
    """Тестирует логику валидации"""
    print("\n🧪 ТЕСТ: Логика валидации")
    print("=" * 50)

    from src.scoring_engine.models import ScoreResult
    from src.trade_recommender.recommend import validate_score_quality

    # Создаём тестовые объекты
    test_cases = [
        {
            "name": "Валидный сигнал",
            "score": ScoreResult(
                id=1,
                symbol="XRP-USDT",
                timeframe="1h",
                ts=1703127600,
                score_calibrated=0.7,
                p_win=0.65,
                edge_net=0.015,
                confidence=0.4,
                is_valid=True,
            ),
            "expected": True,
        },
        {
            "name": "Низкая вероятность выигрыша",
            "score": ScoreResult(
                id=2,
                symbol="XRP-USDT",
                timeframe="1h",
                ts=1703127600,
                score_calibrated=0.7,
                p_win=0.45,  # < 0.6
                edge_net=0.015,
                confidence=0.4,
                is_valid=True,
            ),
            "expected": False,
        },
        {
            "name": "Низкое преимущество",
            "score": ScoreResult(
                id=3,
                symbol="XRP-USDT",
                timeframe="1h",
                ts=1703127600,
                score_calibrated=0.7,
                p_win=0.65,
                edge_net=0.005,  # < 0.01
                confidence=0.4,
                is_valid=True,
            ),
            "expected": False,
        },
        {
            "name": "Низкая уверенность",
            "score": ScoreResult(
                id=4,
                symbol="XRP-USDT",
                timeframe="1h",
                ts=1703127600,
                score_calibrated=0.7,
                p_win=0.65,
                edge_net=0.015,
                confidence=0.2,  # < 0.3
                is_valid=True,
            ),
            "expected": False,
        },
        {
            "name": "Невалидный сигнал",
            "score": ScoreResult(
                id=5,
                symbol="XRP-USDT",
                timeframe="1h",
                ts=1703127600,
                score_calibrated=0.7,
                p_win=0.65,
                edge_net=0.015,
                confidence=0.4,
                is_valid=False,  # False
            ),
            "expected": False,
        },
    ]

    for test_case in test_cases:
        is_valid, reason = validate_score_quality(test_case["score"])
        expected = test_case["expected"]

        if is_valid == expected:
            print(f"✅ {test_case['name']}: {is_valid} ({reason})")
        else:
            print(
                f"❌ {test_case['name']}: ожидалось {expected}, получено {is_valid} ({reason})"
            )


async def main():
    """Главная функция тестирования"""
    print("🧪 ТЕСТИРОВАНИЕ МОДУЛЯ ТОРГОВЫХ РЕКОМЕНДАЦИЙ")
    print("=" * 60)

    # Тест position_model
    await test_position_model()

    # Тест логики валидации
    test_validation_logic()

    # Тест recommend_for_score
    await test_recommend_for_score()

    print("\n🎉 Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(main())
