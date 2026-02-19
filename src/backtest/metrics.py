"""
Метрики для оценки качества торговых сигналов и quant-стратегий.

Единая точка для всех trading metrics: Sharpe, DSR, PnL, MaxDD.
"""

import numpy as np
import pandas as pd


def calc_pnl(
    signals: list[dict], prices: list[dict], commission: float = 0.0005
) -> tuple[list[float], float]:
    """
    Рассчитывает PnL (прибыль/убыток) на основе сигналов и цен.

    Args:
        signals: Список сигналов [{'ts': timestamp, 'signal': -1/0/1, 'reason': str}]
        prices: Список цен [{'ts': timestamp, 'open': float, 'high': float, 'low': float, 'close': float}]
        commission: Комиссия за сделку (по умолчанию 0.05%)

    Returns:
        Tuple[List[float], float]: (список PnL, общий PnL)
    """
    if not signals or not prices:
        return [], 0.0

    # Создаем DataFrame для удобства работы
    signals_df = pd.DataFrame(signals)
    prices_df = pd.DataFrame(prices)

    # Объединяем сигналы и цены по timestamp
    merged = pd.merge(signals_df, prices_df, on="ts", how="inner")

    if merged.empty:
        return [], 0.0

    # Сортируем по времени
    merged = merged.sort_values("ts")

    pnl_list = []
    position = 0  # 0 = нет позиции, 1 = длинная позиция, -1 = короткая позиция
    entry_price = 0.0
    total_pnl = 0.0

    for _, row in merged.iterrows():
        signal = row["signal"]
        close_price = float(row["close"])

        # Логика торговли
        if position == 0:  # Нет позиции
            if signal == 1:  # Сигнал на покупку
                position = 1
                entry_price = close_price
                pnl_list.append(0.0)  # Нет PnL при входе
            elif signal == -1:  # Сигнал на продажу
                position = -1
                entry_price = close_price
                pnl_list.append(0.0)  # Нет PnL при входе
            else:
                pnl_list.append(0.0)

        elif position == 1:  # Длинная позиция
            if signal == -1:  # Сигнал на продажу - закрываем позицию
                pnl = (close_price - entry_price) / entry_price - commission
                total_pnl += pnl
                pnl_list.append(pnl)
                position = 0
            else:
                # Рассчитываем текущий PnL
                pnl = (close_price - entry_price) / entry_price
                pnl_list.append(pnl)

        elif position == -1:  # Короткая позиция
            if signal == 1:  # Сигнал на покупку - закрываем позицию
                pnl = (entry_price - close_price) / entry_price - commission
                total_pnl += pnl
                pnl_list.append(pnl)
                position = 0
            else:
                # Рассчитываем текущий PnL
                pnl = (entry_price - close_price) / entry_price
                pnl_list.append(pnl)

    return pnl_list, total_pnl


def sharpe_ratio(
    returns: list[float] | np.ndarray,
    rf: float = 0.0,
    periods: int = 365,
) -> float:
    """
    Коэффициент Шарпа (единая реализация для всех потребителей).

    Args:
        returns: Массив периодических доходностей (не аннуализированных).
        rf: Безрисковая ставка в годовых (e.g. 0.02 = 2%).
        periods: Количество периодов в году для аннуализации.
            365 — для крипто (дни), 252 — для акций, 525600 — для 1m баров.

    Returns:
        float: Коэффициент Шарпа. 0.0 если недостаточно данных.
    """
    arr = np.asarray(returns, dtype=float)
    if arr.size < 2:
        return 0.0

    rf_per_period = rf / periods
    excess = arr - rf_per_period
    std = np.std(excess, ddof=1)

    if std == 0.0:
        return 0.0

    return float(np.mean(excess) / std * np.sqrt(periods))


def calc_sharpe_ratio(pnl_list: list[float], risk_free_rate: float = 0.02) -> float:
    """
    Коэффициент Шарпа (устаревший интерфейс, оставлен для совместимости).

    .. deprecated::
        Используй ``sharpe_ratio(returns, rf, periods)`` напрямую.
        Этот wrapper предполагает 1-минутные данные (periods=525600).
    """
    return sharpe_ratio(pnl_list, rf=risk_free_rate, periods=525600)


def calc_max_drawdown(pnl_list: list[float]) -> float:
    """
    Рассчитывает максимальную просадку.

    Args:
        pnl_list: Список значений PnL

    Returns:
        float: Максимальная просадка в процентах
    """
    if not pnl_list:
        return 0.0

    cumulative = np.cumsum(pnl_list)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max * 100

    max_dd = np.min(drawdown)
    return abs(max_dd)


def calc_win_rate(pnl_list: list[float]) -> float:
    """
    Рассчитывает процент прибыльных сделок.

    Args:
        pnl_list: Список значений PnL

    Returns:
        float: Процент прибыльных сделок
    """
    if not pnl_list:
        return 0.0

    # Фильтруем только закрытые сделки (ненулевые PnL)
    closed_trades = [pnl for pnl in pnl_list if pnl != 0.0]

    if not closed_trades:
        return 0.0

    winning_trades = sum(1 for pnl in closed_trades if pnl > 0)
    return winning_trades / len(closed_trades) * 100


def calc_metrics(
    signals: list[dict], prices: list[dict], commission: float = 0.0005
) -> dict[str, float]:
    """
    Рассчитывает все метрики качества сигналов.

    Args:
        signals: Список сигналов
        prices: Список цен
        commission: Комиссия за сделку

    Returns:
        Dict[str, float]: Словарь с метриками
    """
    pnl_list, total_pnl = calc_pnl(signals, prices, commission)

    return {
        "total_pnl": total_pnl,
        "total_pnl_percent": total_pnl * 100,
        "sharpe_ratio": calc_sharpe_ratio(pnl_list),
        "max_drawdown": calc_max_drawdown(pnl_list),
        "win_rate": calc_win_rate(pnl_list),
        "total_trades": len([pnl for pnl in pnl_list if pnl != 0.0]),
        "avg_trade_pnl": (
            np.mean([pnl for pnl in pnl_list if pnl != 0.0]) if pnl_list else 0.0
        ),
    }
