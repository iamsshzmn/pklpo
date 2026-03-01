"""
Market Selection Module v1.0

Автоматический выбор торговых пар на основе:
- Data Quality Gate (fill_rate, gap_rate, lag)
- Pair Metrics (volatility, trend_quality, noise, stability, liquidity)
- Global Market Regime (TREND_UP/DOWN, RANGE, VOLATILE)
- Multi-Timeframe Scoring (4H, 1H, 15m, 5m)

Интеграция:
    DAG: features_calc_short → market_selection → features_calc_full

Выходные таблицы:
    - market_scores_tf: оценки по (symbol, timeframe, ts_eval)
    - market_universe: финальный список пар для торговли
    - market_universe_versions: версионность и fallback
"""

__version__ = "1.0.0"
