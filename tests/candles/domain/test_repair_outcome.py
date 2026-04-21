from __future__ import annotations

import pytest

from src.candles.domain.repair import RepairOutcome, classify_repair_outcome


@pytest.mark.parametrize(
    ("requested", "received", "exception", "expected"),
    [
        # exception dominates regardless of other inputs
        (10, 5, True, RepairOutcome.FAIL),
        (0, 0, True, RepairOutcome.FAIL),
        (100, 100, True, RepairOutcome.FAIL),
        # received == 0 and requested > 0 → EMPTY
        (10, 0, False, RepairOutcome.EMPTY),
        (1, 0, False, RepairOutcome.EMPTY),
        # 0 < received < requested → PARTIAL
        (100, 50, False, RepairOutcome.PARTIAL),
        (10, 1, False, RepairOutcome.PARTIAL),
        # received >= requested → SUCCESS
        (100, 100, False, RepairOutcome.SUCCESS),
        (100, 150, False, RepairOutcome.SUCCESS),
        # requested == 0 and not exception → SUCCESS (noop is success)
        (0, 0, False, RepairOutcome.SUCCESS),
    ],
)
def test_classify_repair_outcome(
    requested: int,
    received: int,
    exception: bool,
    expected: RepairOutcome,
) -> None:
    assert (
        classify_repair_outcome(
            requested=requested,
            received=received,
            exception=exception,
        )
        is expected
    )
