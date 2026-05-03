from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest


def _make_df(rows: int = 12) -> pd.DataFrame:
    base = np.arange(rows, dtype=float) + 100.0
    return pd.DataFrame(
        {
            "open": base,
            "high": base + 1.0,
            "low": base - 1.0,
            "close": base + 0.5,
            "volume": np.arange(rows, dtype=float) + 1000.0,
        }
    )


class TestExpandedTalibAdapters:
    def test_dispatch_contains_new_adapters(self):
        from src.features.ta_safe.adapters import TALIB_DISPATCH

        for name in ("apo", "bop", "uo", "adosc", "psar", "t3"):
            assert name in TALIB_DISPATCH

    @pytest.mark.parametrize(
        ("adapter_name", "expected_columns", "talib_method", "kwargs", "method_kwargs"),
        [
            ("apo", ["apo"], "APO", {"fast": 12, "slow": 26}, {"fastperiod": 12, "slowperiod": 26}),
            ("bop", ["bop"], "BOP", {}, {}),
            ("uo", ["uo"], "ULTOSC", {"fast": 7, "medium": 14, "slow": 28}, {"timeperiod1": 7, "timeperiod2": 14, "timeperiod3": 28}),
            ("adosc", ["adosc"], "ADOSC", {"fast": 3, "slow": 10}, {"fastperiod": 3, "slowperiod": 10}),
        ],
    )
    def test_new_adapter_output_contract(
        self,
        monkeypatch,
        adapter_name: str,
        expected_columns: list[str],
        talib_method: str,
        kwargs: dict[str, int],
        method_kwargs: dict[str, int],
    ):
        import src.features.ta_safe.adapters.talib_adapters as adapters

        df = _make_df()
        expected_result = np.linspace(0.0, 1.0, len(df))
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def _fake_method(*args, **call_kwargs):
            calls.append((args, call_kwargs))
            return expected_result

        fake_talib = SimpleNamespace(**{talib_method: _fake_method})
        monkeypatch.setattr(adapters, "_talib", lambda: fake_talib)

        adapter = adapters.TALIB_DISPATCH[adapter_name]
        result = adapter(df, **kwargs)

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == expected_columns
        assert result.index.equals(df.index)
        assert np.allclose(result.iloc[:, 0].values, expected_result)
        assert len(calls) == 1
        assert calls[0][1] == method_kwargs

    def test_psar_adapter_output_contract(self, monkeypatch):
        import src.features.ta_safe.adapters.talib_adapters as adapters

        df = _make_df()
        psar_values = df["close"].to_numpy() - 0.25
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def _fake_sar(*args, **call_kwargs):
            calls.append((args, call_kwargs))
            return psar_values

        fake_talib = SimpleNamespace(SAR=_fake_sar)
        monkeypatch.setattr(adapters, "_talib", lambda: fake_talib)

        result = adapters.TALIB_DISPATCH["psar"](df, af=0.02, max_af=0.2)

        assert list(result.columns) == ["psar", "psar_long", "psar_short"]
        assert result.index.equals(df.index)
        assert np.allclose(result["psar"].values, psar_values)
        assert result["psar_long"].notna().all()
        assert result["psar_short"].isna().all()
        assert len(calls) == 1
        assert calls[0][1] == {"acceleration": 0.02, "maximum": 0.2}

    def test_t3_adapter_output_contract(self, monkeypatch):
        import src.features.ta_safe.adapters.talib_adapters as adapters

        df = _make_df()
        expected_result = np.linspace(0.0, 1.0, len(df))
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def _fake_t3(*args, **call_kwargs):
            calls.append((args, call_kwargs))
            return expected_result

        fake_talib = SimpleNamespace(T3=_fake_t3)
        monkeypatch.setattr(adapters, "_talib", lambda: fake_talib)

        result = adapters.TALIB_DISPATCH["t3"](df, length=20, volume_factor=0.7)

        assert list(result.columns) == ["t3_20"]
        assert result.index.equals(df.index)
        assert np.allclose(result["t3_20"].values, expected_result)
        assert len(calls) == 1
        assert calls[0][1] == {"timeperiod": 20, "vfactor": 0.7}

    def test_uo_adapter_accepts_trend_alias_kwargs(self, monkeypatch):
        import src.features.ta_safe.adapters.talib_adapters as adapters

        df = _make_df()
        expected_result = np.linspace(0.0, 1.0, len(df))
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def _fake_ultosc(*args, **call_kwargs):
            calls.append((args, call_kwargs))
            return expected_result

        fake_talib = SimpleNamespace(ULTOSC=_fake_ultosc)
        monkeypatch.setattr(adapters, "_talib", lambda: fake_talib)

        result = adapters.TALIB_DISPATCH["uo"](df, short=7, medium=14, long=28)

        assert list(result.columns) == ["uo"]
        assert result.index.equals(df.index)
        assert np.allclose(result["uo"].values, expected_result)
        assert len(calls) == 1
        assert calls[0][1] == {
            "timeperiod1": 7,
            "timeperiod2": 14,
            "timeperiod3": 28,
        }
