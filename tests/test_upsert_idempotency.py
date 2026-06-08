"""Property-based tests for UPSERT idempotency contracts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from hypothesis import given, settings, strategies as st

PK_FIELDS = ("symbol", "timeframe", "timestamp")


def _key(record: dict[str, Any]) -> tuple[str, str, int]:
    return (str(record["symbol"]), str(record["timeframe"]), int(record["timestamp"]))


def _apply_upsert(
    state: dict[tuple[str, str, int], dict[str, Any]],
    records: list[dict[str, Any]],
) -> dict[tuple[str, str, int], dict[str, Any]]:
    """Apply last-write-wins UPSERT semantics for a record list."""
    next_state = deepcopy(state)
    for record in records:
        pk = _key(record)
        incoming = dict(record)
        if pk not in next_state:
            next_state[pk] = incoming
            continue

        # Emulate ON CONFLICT DO UPDATE for non-PK fields.
        current = next_state[pk]
        for field, value in incoming.items():
            if field in PK_FIELDS:
                continue
            current[field] = value
    return next_state


@st.composite
def _single_record(draw: st.DrawFn) -> dict[str, Any]:
    return {
        "symbol": draw(st.sampled_from(["BTC-USDT-SWAP", "ETH-USDT-SWAP"])),
        "timeframe": draw(st.sampled_from(["1m", "5m", "1h"])),
        "timestamp": draw(st.integers(min_value=1, max_value=2_000_000_000_000)),
        "ema_8": draw(
            st.one_of(st.none(), st.floats(allow_nan=False, allow_infinity=False))
        ),
        "sma_20": draw(
            st.one_of(st.none(), st.floats(allow_nan=False, allow_infinity=False))
        ),
        "run_id": draw(st.text(min_size=1, max_size=24)),
    }


@settings(max_examples=100)
@given(record=_single_record())
def test_upsert_is_idempotent_for_same_payload(record: dict[str, Any]) -> None:
    once = _apply_upsert({}, [record])
    twice = _apply_upsert({}, [record, record])
    assert once == twice


@settings(max_examples=100)
@given(
    base=_single_record(),
    ema_8=st.one_of(st.none(), st.floats(allow_nan=False, allow_infinity=False)),
    sma_20=st.one_of(st.none(), st.floats(allow_nan=False, allow_infinity=False)),
    run_id=st.text(min_size=1, max_size=24),
)
def test_last_upsert_wins_for_same_key(
    base: dict[str, Any], ema_8: float | None, sma_20: float | None, run_id: str
) -> None:
    v1 = dict(base)
    v2 = dict(base)
    v2["ema_8"] = ema_8
    v2["sma_20"] = sma_20
    v2["run_id"] = run_id

    expected = _apply_upsert({}, [v2])
    actual = _apply_upsert({}, [v1, v2])
    assert actual == expected


@settings(max_examples=100)
@given(record=_single_record())
def test_order_does_not_change_result_for_duplicate_same_key(
    record: dict[str, Any],
) -> None:
    forward = _apply_upsert({}, [record, record, record])
    reverse = _apply_upsert({}, [record, record, record][::-1])
    assert forward == reverse
