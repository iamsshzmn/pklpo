"""Тесты для модуля reprocess."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.market_meta.infrastructure.reprocess import (
    ReprocessConf,
    ceil_to_tf,
    filter_symbols,
    floor_to_tf,
    get_run_window,
    maybe_update_watermark,
    parse_dag_conf,
)


class TestParseDagConf:
    """Тесты парсинга dag_run.conf."""

    def test_empty_conf_returns_defaults(self) -> None:
        """Пустой conf возвращает defaults."""
        result = parse_dag_conf(None)
        assert result.reprocess is False
        assert result.t0 is None
        assert result.t1 is None
        assert result.symbols is None

    def test_reprocess_true_with_valid_window(self) -> None:
        """reprocess=True с валидным окном."""
        conf = {
            "reprocess": True,
            "t0": "2025-12-18T00:00:00Z",
            "t1": "2025-12-18T06:00:00Z",
            "symbols": ["BTC-USDT-SWAP"],
        }
        result = parse_dag_conf(conf)
        assert result.reprocess is True
        assert result.t0 == datetime(2025, 12, 18, 0, 0, tzinfo=UTC)
        assert result.t1 == datetime(2025, 12, 18, 6, 0, tzinfo=UTC)
        assert result.symbols == ["BTC-USDT-SWAP"]

    def test_reprocess_true_without_t0_raises(self) -> None:
        """reprocess=True без t0 вызывает ошибку."""
        conf = {"reprocess": True, "t1": "2025-12-18T06:00:00Z"}
        with pytest.raises(ValueError, match="требует t0 и t1"):
            parse_dag_conf(conf)

    def test_reprocess_true_t0_gte_t1_raises(self) -> None:
        """reprocess=True с t0 >= t1 вызывает ошибку."""
        conf = {
            "reprocess": True,
            "t0": "2025-12-18T06:00:00Z",
            "t1": "2025-12-18T00:00:00Z",
        }
        with pytest.raises(ValueError, match="должен быть <"):
            parse_dag_conf(conf)


class TestFloorCeilTf:
    """Тесты округления к таймфрейму."""

    def test_floor_to_1m(self) -> None:
        """floor к 1m."""
        ts = datetime(2025, 12, 18, 10, 23, 45, tzinfo=UTC)
        result = floor_to_tf(ts, 1)
        assert result == datetime(2025, 12, 18, 10, 23, 0, tzinfo=UTC)

    def test_floor_to_5m(self) -> None:
        """floor к 5m."""
        ts = datetime(2025, 12, 18, 10, 23, 45, tzinfo=UTC)
        result = floor_to_tf(ts, 5)
        assert result == datetime(2025, 12, 18, 10, 20, 0, tzinfo=UTC)

    def test_ceil_to_5m_not_aligned(self) -> None:
        """ceil к 5m если не выровнен."""
        ts = datetime(2025, 12, 18, 10, 23, 0, tzinfo=UTC)
        result = ceil_to_tf(ts, 5)
        assert result == datetime(2025, 12, 18, 10, 25, 0, tzinfo=UTC)

    def test_ceil_to_5m_already_aligned(self) -> None:
        """ceil к 5m если уже выровнен."""
        ts = datetime(2025, 12, 18, 10, 20, 0, tzinfo=UTC)
        result = ceil_to_tf(ts, 5)
        assert result == datetime(2025, 12, 18, 10, 20, 0, tzinfo=UTC)


class TestGetRunWindow:
    """Тесты get_run_window."""

    def test_reprocess_mode_uses_conf_window(self) -> None:
        """Reprocess режим использует окно из conf."""
        conf = ReprocessConf(
            reprocess=True,
            t0=datetime(2025, 12, 18, 0, 0, tzinfo=UTC),
            t1=datetime(2025, 12, 18, 6, 0, tzinfo=UTC),
        )
        sync_state = MagicMock()

        result = get_run_window(
            conf=conf,
            sync_state=sync_state,
            pipeline="normalize_1m",
            symbol="BTC-USDT-SWAP",
            data_type="oi",
        )

        assert result.mode == "reprocess"
        assert result.t0 == datetime(2025, 12, 18, 0, 0, tzinfo=UTC)
        assert result.t1 == datetime(2025, 12, 18, 6, 0, tzinfo=UTC)
        assert result.skip is False
        sync_state.get_last_ts.assert_not_called()

    def test_incremental_mode_uses_watermark(self) -> None:
        """Incremental режим использует watermark."""
        conf = ReprocessConf(reprocess=False)
        sync_state = MagicMock()
        wm = datetime(2025, 12, 18, 5, 0, tzinfo=UTC)
        sync_state.get_last_ts.return_value = wm
        now = datetime(2025, 12, 18, 6, 0, tzinfo=UTC)

        result = get_run_window(
            conf=conf,
            sync_state=sync_state,
            pipeline="normalize_1m",
            symbol="BTC-USDT-SWAP",
            data_type="oi",
            now_utc=now,
            overlap_seconds=600,
            safety_lag_seconds=120,
        )

        assert result.mode == "incremental"
        # t0 = wm - overlap = 05:00 - 10min = 04:50
        assert result.t0 == datetime(2025, 12, 18, 4, 50, tzinfo=UTC)
        # t1 = now - safety_lag = 06:00 - 2min = 05:58
        assert result.t1 == datetime(2025, 12, 18, 5, 58, tzinfo=UTC)

    def test_incremental_no_watermark_uses_default_lookback(self) -> None:
        """Incremental без watermark использует default lookback."""
        conf = ReprocessConf(reprocess=False)
        sync_state = MagicMock()
        sync_state.get_last_ts.return_value = None
        now = datetime(2025, 12, 18, 12, 0, tzinfo=UTC)

        result = get_run_window(
            conf=conf,
            sync_state=sync_state,
            pipeline="normalize_1m",
            symbol="BTC-USDT-SWAP",
            data_type="oi",
            now_utc=now,
            default_lookback_hours=24,
        )

        # t0 = now - 24h = 17 декабря 12:00
        assert result.t0.day == 17
        assert result.mode == "incremental"


class TestMaybeUpdateWatermark:
    """Тесты maybe_update_watermark."""

    def test_reprocess_does_not_update_watermark(self) -> None:
        """Reprocess НЕ обновляет watermark."""
        sync_state = MagicMock()
        new_ts = datetime(2025, 12, 18, 6, 0, tzinfo=UTC)

        result = maybe_update_watermark(
            sync_state=sync_state,
            mode="reprocess",
            pipeline="normalize_1m",
            symbol="BTC-USDT-SWAP",
            data_type="oi",
            new_ts=new_ts,
            dry_run=False,
        )

        assert result is False
        sync_state.set_last_ts.assert_called_once()
        call_kwargs = sync_state.set_last_ts.call_args.kwargs
        assert call_kwargs["is_reprocess"] is True

    def test_incremental_updates_watermark(self) -> None:
        """Incremental обновляет watermark."""
        sync_state = MagicMock()
        new_ts = datetime(2025, 12, 18, 6, 0, tzinfo=UTC)

        result = maybe_update_watermark(
            sync_state=sync_state,
            mode="incremental",
            pipeline="normalize_1m",
            symbol="BTC-USDT-SWAP",
            data_type="oi",
            new_ts=new_ts,
            dry_run=False,
        )

        assert result is True
        sync_state.set_last_ts.assert_called_once()
        call_kwargs = sync_state.set_last_ts.call_args.kwargs
        assert call_kwargs["is_reprocess"] is False


class TestFilterSymbols:
    """Тесты filter_symbols."""

    def test_no_conf_symbols_returns_all_allowed(self) -> None:
        """Без symbols в conf возвращает все allowed."""
        conf = ReprocessConf()
        allowed = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
        result = filter_symbols(conf, allowed)
        assert result == allowed

    def test_conf_symbols_filters_to_intersection(self) -> None:
        """С symbols в conf возвращает пересечение."""
        conf = ReprocessConf(symbols=["BTC-USDT-SWAP", "SOL-USDT-SWAP"])
        allowed = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
        result = filter_symbols(conf, allowed)
        assert result == ["BTC-USDT-SWAP"]
