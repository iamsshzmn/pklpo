from __future__ import annotations

import asyncio
import json
import tempfile

from hypothesis import given, settings, strategies as st

from src.candles.application.sync.policy import RetryPolicy
from src.candles.application.sync.use_cases import RunCandleSyncUseCase
from src.candles.instruments_service import load_symbols_from_file


def _expected_symbols(values: list[object | None]) -> list[str]:
    expected: list[str] = []
    for item in values:
        if item is None:
            continue
        normalized = item.strip() if isinstance(item, str) else str(item).strip()
        if normalized and normalized.lower() not in {"none", "null"}:
            expected.append(normalized)
    return expected


class _MarketDataStub:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None


class _CandleStoreStub:
    async def get_fill_stats(self, start_timestamp_ms: int):
        return {"rows_today": 1}


class _InstrumentCatalogStub:
    def __init__(
        self,
        *,
        curated: list[str],
        cached: list[str],
        refreshed: list[str],
        listed: list[str],
    ) -> None:
        self.curated = curated
        self.cached = cached
        self.refreshed = refreshed
        self.listed = listed
        self.calls: list[str] = []

    async def load_curated_symbols(self) -> list[str]:
        self.calls.append("curated")
        return list(self.curated)

    async def load_cached_symbols(self) -> list[str]:
        self.calls.append("cached")
        return list(self.cached)

    async def refresh_catalog(self) -> list[str]:
        self.calls.append("refresh")
        return list(self.refreshed)

    async def list_symbols(self) -> list[str]:
        self.calls.append("list")
        return list(self.listed)


@settings(max_examples=100)
@given(
    values=st.lists(
        st.one_of(
            st.none(),
            st.text(max_size=20),
            st.integers(min_value=-1000, max_value=1000),
        ),
        min_size=0,
        max_size=50,
    )
)
def test_load_symbols_from_file_normalizes_json_payload(values: list[object | None]) -> None:
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp_dir:
        instruments_file = Path(tmp_dir) / "instruments_list.json"
        instruments_file.write_text(json.dumps(values), encoding="utf-8")

        result = load_symbols_from_file(instruments_file)

    assert result == _expected_symbols(values)


@settings(max_examples=100)
@given(
    requested=st.lists(st.text(min_size=1, max_size=12), min_size=0, max_size=5),
    curated=st.lists(st.text(min_size=1, max_size=12), min_size=0, max_size=5),
    cached=st.lists(st.text(min_size=1, max_size=12), min_size=0, max_size=5),
    refreshed=st.lists(st.text(min_size=1, max_size=12), min_size=0, max_size=5),
    listed=st.lists(st.text(min_size=1, max_size=12), min_size=0, max_size=5),
)
def test_resolve_symbols_respects_priority_order(
    requested: list[str],
    curated: list[str],
    cached: list[str],
    refreshed: list[str],
    listed: list[str],
) -> None:
    use_case = RunCandleSyncUseCase(
        market_data=_MarketDataStub(),  # type: ignore[arg-type]
        candle_store=_CandleStoreStub(),  # type: ignore[arg-type]
        instrument_catalog=_InstrumentCatalogStub(
            curated=curated,
            cached=cached,
            refreshed=refreshed,
            listed=listed,
        ),
        retry_policy=RetryPolicy(max_retries=0, retry_delay=0.1, batch_size=10),
        telemetry=None,
    )

    result = asyncio.run(use_case._resolve_symbols(tuple(requested)))

    if requested:
        assert result == requested
        assert use_case._instrument_catalog.calls == []  # type: ignore[attr-defined]
        return

    expected = curated or cached or refreshed or listed
    assert result == expected

    calls = use_case._instrument_catalog.calls  # type: ignore[attr-defined]
    if curated:
        assert calls == ["curated"]
    elif cached:
        assert calls == ["curated", "cached"]
    elif refreshed:
        assert calls == ["curated", "cached", "refresh"]
    else:
        assert calls == ["curated", "cached", "refresh", "list"]
