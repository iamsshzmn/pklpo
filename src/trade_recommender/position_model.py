"""
Модуль для расчёта параметров позиции

Содержит логику расчёта:
- стоп-лосса на основе ATR
- размера позиции на основе риска
- take-profit на основе risk-reward ratio
- плеча и маржи
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)
# Настраиваем логгер для записи только в файл, а не в консоль
logger.setLevel(logging.DEBUG)
# Удаляем все существующие обработчики
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
# Добавляем только файловый обработчик
file_handler = logging.FileHandler("trade_recommender.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Константы по умолчанию
DEFAULT_BALANCE = 20.0  # USDT
DEFAULT_RISK_PCT = 0.02  # 2%
DEFAULT_ATR_MULTIPLIER = 1.5  # множитель ATR для стопа
DEFAULT_RR_RATIO = 2.0  # risk-reward ratio для take-profit


def calculate_position(
    symbol: str,
    direction: Literal["LONG", "SHORT"],
    entry_price: float,
    atr: float,
    balance: float = DEFAULT_BALANCE,
    risk_pct: float = DEFAULT_RISK_PCT,
    atr_multiplier: float = DEFAULT_ATR_MULTIPLIER,
    rr_ratio: float = DEFAULT_RR_RATIO,
) -> dict:
    """
    Рассчитывает параметры позиции на основе ATR и управления риском

    Args:
        symbol: Торговый символ
        direction: Направление позиции (LONG/SHORT)
        entry_price: Цена входа
        atr: Average True Range
        balance: Баланс в USDT
        risk_pct: Процент риска от баланса (0.01 = 1%)
        atr_multiplier: Множитель ATR для стоп-лосса
        rr_ratio: Risk-reward ratio для take-profit

    Returns:
        Dict с параметрами позиции
    """

    # Валидация входных данных
    if entry_price <= 0:
        raise ValueError("entry_price должен быть положительным")
    if atr <= 0:
        raise ValueError("atr должен быть положительным")
    if balance <= 0:
        raise ValueError("balance должен быть положительным")
    if risk_pct <= 0 or risk_pct > 1:
        raise ValueError("risk_pct должен быть в диапазоне (0, 1]")
    if atr_multiplier <= 0:
        raise ValueError("atr_multiplier должен быть положительным")
    if rr_ratio <= 0:
        raise ValueError("rr_ratio должен быть положительным")

    # 1. Расчёт стоп-лосса
    stop_distance = atr * atr_multiplier

    if direction == "LONG":
        stop_price = entry_price - stop_distance
    else:  # SHORT
        stop_price = entry_price + stop_distance

    # 2. Расчёт риска в USDT
    risk_usdt = balance * risk_pct

    # 3. Расчёт размера позиции
    price_distance = abs(entry_price - stop_price)
    if price_distance == 0:
        raise ValueError("Невозможно рассчитать позицию: цена входа равна стопу")

    position_size = risk_usdt / price_distance

    # 4. Расчёт take-profit
    if direction == "LONG":
        take_profit_price = entry_price + (price_distance * rr_ratio)
    else:  # SHORT
        take_profit_price = entry_price - (price_distance * rr_ratio)

    # 5. Расчёт стоимости позиции и плеча
    position_value_usdt = position_size * entry_price
    leverage_used = position_value_usdt / balance
    margin_required = position_value_usdt / leverage_used if leverage_used > 0 else 0

    # Логирование результатов
    logger.debug(f"Расчёт позиции для {symbol} {direction}:")
    logger.debug(f"  Вход: {entry_price:.6f}")
    logger.debug(f"  Стоп: {stop_price:.6f} (расстояние: {price_distance:.6f})")
    logger.debug(f"  Тейк: {take_profit_price:.6f}")
    logger.debug(f"  Размер: {position_size:.2f}")
    logger.debug(f"  Риск: ${risk_usdt:.2f}")
    logger.debug(f"  Плечо: {leverage_used:.2f}x")

    return {
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss_price": stop_price,
        "take_profit_price": take_profit_price,
        "position_size": position_size,
        "position_value_usdt": position_value_usdt,
        "risk_amount_usdt": risk_usdt,
        "leverage_used": leverage_used,
        "margin_required": margin_required,
        "atr": atr,
        "atr_multiplier": atr_multiplier,
        "rr_ratio": rr_ratio,
        "balance": balance,
        "risk_pct": risk_pct,
    }
