from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings, strategies as st

from src.candles.domain.batch_policy import DynamicBatchPolicy
from src.candles.domain.metadata import (
    InstrumentMetadata,
    InstrumentType,
    LotSize,
    TickSize,
)
from src.candles.domain.timeframes import TF_TO_MS, TF_TO_SEC
from src.candles.infrastructure.sqlalchemy_pool_adapter import (
    _build_params,
    _convert_pg_placeholders,
)


def _decimal_steps() -> st.SearchStrategy[Decimal]:
    return st.sampled_from(
        [
            Decimal("1"),
            Decimal("0.1"),
            Decimal("0.01"),
            Decimal("0.001"),
        ]
    )


@settings(max_examples=100)
@given(tf=st.sampled_from(sorted(TF_TO_MS)))
def test_timeframe_conversion_tables_stay_consistent(tf: str) -> None:
    assert TF_TO_MS[tf] == TF_TO_SEC[tf] * 1000


@settings(max_examples=100, deadline=None)
@given(
    samples=st.lists(
        st.tuples(
            st.floats(
                min_value=0.0,
                max_value=10_000.0,
                allow_nan=False,
                allow_infinity=False,
            ),
            st.floats(
                min_value=0.0,
                max_value=100.0,
                allow_nan=False,
                allow_infinity=False,
            ),
        ),
        min_size=1,
        max_size=50,
    )
)
def test_dynamic_batch_policy_always_respects_bounds(
    samples: list[tuple[float, float]],
) -> None:
    policy = DynamicBatchPolicy(default_batch_size=300, min_batch_size=50)

    for latency_ms, cpu_pct in samples:
        batch_size = policy.get_batch_size("1m", latency_ms, cpu_pct)
        assert 50 <= batch_size <= 300


@settings(max_examples=100)
@given(
    latency_ms=st.floats(
        min_value=0.0,
        max_value=10_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    cpu_pct=st.floats(
        min_value=80.0,
        max_value=100.0,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_dynamic_batch_policy_forces_min_batch_on_high_cpu(
    latency_ms: float, cpu_pct: float
) -> None:
    policy = DynamicBatchPolicy(default_batch_size=300, min_batch_size=50)
    assert policy.get_batch_size("1m", latency_ms, cpu_pct) == 50


@settings(max_examples=100)
@given(
    step_size=_decimal_steps(),
    min_units=st.integers(min_value=1, max_value=20),
    span=st.integers(min_value=1, max_value=200),
    valid_units=st.integers(min_value=0, max_value=200),
)
def test_tick_and_lot_validation_preserve_step_contracts(
    step_size: Decimal,
    min_units: int,
    span: int,
    valid_units: int,
) -> None:
    max_units = min_units + span
    bounded_units = min_units + (valid_units % (span + 1))

    tick = TickSize(
        min_size=step_size * min_units,
        max_size=step_size * max_units,
        step_size=step_size,
    )
    lot = LotSize(
        min_qty=step_size * min_units,
        max_qty=step_size * max_units,
        step_size=step_size,
    )

    valid_value = step_size * bounded_units
    invalid_value = valid_value + (step_size / 2)

    instrument = InstrumentMetadata(
        symbol="BTC-USDT-SWAP",
        inst_id="BTC-USDT-SWAP",
        inst_type=InstrumentType.SWAP,
        base_ccy="BTC",
        quote_ccy="USDT",
        tick_size=tick,
        lot_size=lot,
    )

    assert tick.validate_price(valid_value)
    assert lot.validate_quantity(valid_value)
    assert instrument.validate_order(float(valid_value), float(valid_value))

    if invalid_value <= tick.max_size:
        assert not tick.validate_price(invalid_value)
    if invalid_value <= lot.max_qty:
        assert not lot.validate_quantity(invalid_value)


@settings(max_examples=100)
@given(
    values=st.lists(
        st.integers(min_value=-1_000_000, max_value=1_000_000),
        min_size=1,
        max_size=25,
    )
)
def test_sqlalchemy_placeholder_adapter_keeps_param_order(values: list[int]) -> None:
    query = "SELECT " + ", ".join(f"${idx}" for idx in range(1, len(values) + 1))
    converted = _convert_pg_placeholders(query)

    for idx in range(1, len(values) + 1):
        assert f":p{idx}" in converted
        assert f"${idx}" not in converted

    assert _build_params(tuple(values)) == {
        f"p{idx}": value for idx, value in enumerate(values, start=1)
    }
