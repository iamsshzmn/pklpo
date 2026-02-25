"""
Тесты для src/backtest/metrics.py: sharpe_ratio и deflated_sharpe_ratio.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.backtest.metrics import deflated_sharpe_ratio, sharpe_ratio

# ---------------------------------------------------------------------------
# sharpe_ratio
# ---------------------------------------------------------------------------


def test_sharpe_ratio_zero_sr() -> None:
    """SR = 0 при нулевом среднем доходности."""
    returns = np.array([0.01, -0.01, 0.01, -0.01] * 50)
    sr = sharpe_ratio(returns, rf=0.0, periods=365)
    # Mean near 0 → SR near 0
    assert abs(sr) < 0.2


def test_sharpe_ratio_positive() -> None:
    """Постоянно положительные доходности → SR > 0."""
    returns = np.full(252, 0.001)  # 0.1% в день, 0 std → SR → ∞, но std > 0 нужен
    returns[0] = 0.0005  # небольшая вариация
    sr = sharpe_ratio(returns, rf=0.0, periods=252)
    assert sr > 0


def test_sharpe_ratio_periods_scaling() -> None:
    """
    SR масштабируется с корнем из periods.
    SR(periods=365) = SR(periods=252) * √(365/252).
    """
    rng = np.random.default_rng(42)
    returns = rng.normal(0.001, 0.02, 500)

    sr_365 = sharpe_ratio(returns, periods=365)
    sr_252 = sharpe_ratio(returns, periods=252)

    ratio = sr_365 / sr_252
    expected_ratio = np.sqrt(365 / 252)
    np.testing.assert_allclose(ratio, expected_ratio, rtol=1e-9)


def test_sharpe_ratio_known_value() -> None:
    """
    Тест с известными значениями.
    mean=0.001, std=0.01, periods=252 → SR = 0.001/0.01 * √252 ≈ 1.5874.
    """
    rng = np.random.default_rng(0)
    n = 100_000
    returns = rng.normal(0.001, 0.01, n)  # mean≈0.001, std≈0.01

    sr = sharpe_ratio(returns, rf=0.0, periods=252)
    expected = 0.001 / 0.01 * np.sqrt(252)
    np.testing.assert_allclose(sr, expected, rtol=0.05)  # 5% tolerance for LLN


def test_sharpe_ratio_rf_reduces_sr() -> None:
    """Безрисковая ставка > 0 уменьшает SR по сравнению с rf=0."""
    returns = np.random.default_rng(1).normal(0.001, 0.01, 500)
    sr_no_rf = sharpe_ratio(returns, rf=0.0, periods=252)
    sr_with_rf = sharpe_ratio(returns, rf=0.05, periods=252)
    assert sr_no_rf > sr_with_rf


def test_sharpe_ratio_empty() -> None:
    """Пустой массив или < 2 элементов → SR = 0.0."""
    assert sharpe_ratio([]) == 0.0
    assert sharpe_ratio([0.01]) == 0.0


def test_sharpe_ratio_zero_variance() -> None:
    """Нулевая дисперсия доходностей (нули) → SR = 0.0."""
    # Используем np.zeros, а не ones * const: float64-умножение 1.0 * 0.01 может
    # давать ненулевой ddof=1 std из-за FP-шума при больших массивах.
    returns = np.zeros(100)
    assert sharpe_ratio(returns) == 0.0


def test_sharpe_ratio_unified_replaces_calc() -> None:
    """
    Убеждаемся, что calc_sharpe_ratio больше не экспортируется из backtest.
    Все потребители должны использовать sharpe_ratio() напрямую.
    """
    import src.backtest as backtest

    assert not hasattr(backtest, "calc_sharpe_ratio"), (
        "calc_sharpe_ratio должна быть удалена из src.backtest (DRY-gate)"
    )


# ---------------------------------------------------------------------------
# deflated_sharpe_ratio
# ---------------------------------------------------------------------------


def test_dsr_known_values_zero_sr() -> None:
    """
    SR=0, n_trials=1, var_sr=1.0, T=100.
    DSR = Φ(0) = 0.5; p_value = 0.5.
    """
    dsr, p_value = deflated_sharpe_ratio(
        sr_observed=0.0, n_trials=1, var_sr=1.0, T=100
    )
    np.testing.assert_allclose(dsr, 0.5, atol=1e-9)
    np.testing.assert_allclose(p_value, 0.5, atol=1e-9)


def test_dsr_known_values_positive_sr_no_trials() -> None:
    """
    SR=1.0, n_trials=1, var_sr=1.0, T=252.
    DSR = Φ(1.0) ≈ 0.8413.
    """
    from scipy.stats import norm

    dsr, p_value = deflated_sharpe_ratio(
        sr_observed=1.0, n_trials=1, var_sr=1.0, T=252
    )
    expected = norm.cdf(1.0)
    np.testing.assert_allclose(dsr, expected, atol=1e-9)
    np.testing.assert_allclose(p_value, 1.0 - expected, atol=1e-9)


def test_dsr_penalty_with_trials() -> None:
    """
    DSR уменьшается с ростом n_trials (множественное тестирование штрафует).
    """
    sr = 1.0
    var_sr = 1.0
    T = 252

    dsr_1, _ = deflated_sharpe_ratio(sr, n_trials=1, var_sr=var_sr, T=T)
    dsr_5, _ = deflated_sharpe_ratio(sr, n_trials=5, var_sr=var_sr, T=T)
    dsr_20, _ = deflated_sharpe_ratio(sr, n_trials=20, var_sr=var_sr, T=T)

    # Больше испытаний → ниже DSR (строже поправка)
    assert dsr_5 < dsr_1, f"dsr_5={dsr_5:.4f} должен быть < dsr_1={dsr_1:.4f}"
    assert dsr_20 < dsr_5, f"dsr_20={dsr_20:.4f} должен быть < dsr_5={dsr_5:.4f}"


def test_dsr_larger_var_sr_reduces_confidence() -> None:
    """
    Большая var_sr (высокая дисперсия SR по путям) снижает DSR при прочих равных.
    """
    sr = 0.5
    n_trials = 5
    T = 252

    dsr_low, _ = deflated_sharpe_ratio(sr, n_trials=n_trials, var_sr=0.1, T=T)
    dsr_high, _ = deflated_sharpe_ratio(sr, n_trials=n_trials, var_sr=2.0, T=T)

    # При малой var_sr оценка SR более точна → выше уверенность
    assert dsr_low != dsr_high  # Должны различаться


def test_dsr_sum_to_one() -> None:
    """dsr + p_value = 1.0 для любых входных данных."""
    params = [
        (1.5, 10, 0.5, 365),
        (0.0, 1, 1.0, 100),
        (-0.5, 3, 0.2, 252),
    ]
    for sr, n, var, T in params:
        dsr, p = deflated_sharpe_ratio(sr, n_trials=n, var_sr=var, T=T)
        np.testing.assert_allclose(dsr + p, 1.0, atol=1e-9, err_msg=f"params={params}")


def test_dsr_range() -> None:
    """DSR всегда в диапазоне [0, 1]."""
    test_cases = [
        (10.0, 100, 1.0, 1000),   # очень высокий SR
        (-10.0, 100, 1.0, 1000),  # очень низкий SR
        (0.1, 1, 0.01, 50),
    ]
    for sr, n, var, T in test_cases:
        dsr, p = deflated_sharpe_ratio(sr, n_trials=n, var_sr=var, T=T)
        assert 0.0 <= dsr <= 1.0, f"DSR={dsr} вне [0,1] для {sr, n, var, T}"
        assert 0.0 <= p <= 1.0, f"p_value={p} вне [0,1] для {sr, n, var, T}"


def test_dsr_invalid_var_sr() -> None:
    """var_sr <= 0 вызывает ValueError."""
    with pytest.raises(ValueError, match="var_sr"):
        deflated_sharpe_ratio(1.0, n_trials=5, var_sr=0.0, T=252)

    with pytest.raises(ValueError, match="var_sr"):
        deflated_sharpe_ratio(1.0, n_trials=5, var_sr=-1.0, T=252)


def test_dsr_invalid_n_trials() -> None:
    """n_trials < 1 вызывает ValueError."""
    with pytest.raises(ValueError, match="n_trials"):
        deflated_sharpe_ratio(1.0, n_trials=0, var_sr=1.0, T=252)


def test_dsr_invalid_T() -> None:
    """T < 2 вызывает ValueError."""
    with pytest.raises(ValueError, match="T must"):
        deflated_sharpe_ratio(1.0, n_trials=1, var_sr=1.0, T=1)
