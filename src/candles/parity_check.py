from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Any

from src.candles.ports import MarketDataAdapterPort


@dataclass(frozen=True)
class CandlePoint:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class ParityGate:
    max_failed_symbols: int = 0
    max_mismatch_per_symbol: int = 0
    max_missing_per_symbol: int = 0
    max_extra_per_symbol: int = 0


def _to_candle_point(row: dict[str, Any]) -> CandlePoint:
    return CandlePoint(
        ts=int(row["ts"]),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
    )


def compare_candles(
    *,
    baseline_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    price_rel_tol: float = 1e-9,
    volume_rel_tol: float = 1e-6,
) -> dict[str, Any]:
    baseline_points = [_to_candle_point(r) for r in baseline_rows]
    candidate_points = [_to_candle_point(r) for r in candidate_rows]
    baseline = {p.ts: p for p in baseline_points}
    candidate = {p.ts: p for p in candidate_points}

    baseline_ts = set(baseline.keys())
    candidate_ts = set(candidate.keys())
    common_ts = sorted(baseline_ts & candidate_ts)
    missing_in_candidate = sorted(baseline_ts - candidate_ts)
    extra_in_candidate = sorted(candidate_ts - baseline_ts)

    max_open_diff = 0.0
    max_high_diff = 0.0
    max_low_diff = 0.0
    max_close_diff = 0.0
    max_volume_diff = 0.0
    mismatch_count = 0

    for ts in common_ts:
        b = baseline[ts]
        c = candidate[ts]

        open_diff = abs(b.open - c.open)
        high_diff = abs(b.high - c.high)
        low_diff = abs(b.low - c.low)
        close_diff = abs(b.close - c.close)
        volume_diff = abs(b.volume - c.volume)

        max_open_diff = max(max_open_diff, open_diff)
        max_high_diff = max(max_high_diff, high_diff)
        max_low_diff = max(max_low_diff, low_diff)
        max_close_diff = max(max_close_diff, close_diff)
        max_volume_diff = max(max_volume_diff, volume_diff)

        values_match = (
            isclose(b.open, c.open, rel_tol=price_rel_tol)
            and isclose(b.high, c.high, rel_tol=price_rel_tol)
            and isclose(b.low, c.low, rel_tol=price_rel_tol)
            and isclose(b.close, c.close, rel_tol=price_rel_tol)
            and isclose(b.volume, c.volume, rel_tol=volume_rel_tol)
        )
        if not values_match:
            mismatch_count += 1

    return {
        "baseline_count": len(baseline_rows),
        "candidate_count": len(candidate_rows),
        "common_count": len(common_ts),
        "missing_in_candidate_count": len(missing_in_candidate),
        "extra_in_candidate_count": len(extra_in_candidate),
        "mismatch_count": mismatch_count,
        "max_abs_diff": {
            "open": max_open_diff,
            "high": max_high_diff,
            "low": max_low_diff,
            "close": max_close_diff,
            "volume": max_volume_diff,
        },
        "ok": (
            len(missing_in_candidate) == 0
            and len(extra_in_candidate) == 0
            and mismatch_count == 0
        ),
    }


async def run_adapter_parity_check(
    *,
    baseline_adapter: MarketDataAdapterPort,
    candidate_adapter: MarketDataAdapterPort,
    symbols: list[str],
    timeframe: str,
    limit: int = 300,
    before: str | None = None,
) -> dict[str, Any]:
    per_symbol: dict[str, Any] = {}

    async with baseline_adapter, candidate_adapter:
        for symbol in symbols:
            baseline_rows = await baseline_adapter.get_candles(
                inst_id=symbol, bar=timeframe, limit=limit, before=before
            )
            candidate_rows = await candidate_adapter.get_candles(
                inst_id=symbol, bar=timeframe, limit=limit, before=before
            )
            per_symbol[symbol] = compare_candles(
                baseline_rows=baseline_rows,
                candidate_rows=candidate_rows,
            )

    failed = sum(1 for item in per_symbol.values() if not item["ok"])
    return {
        "symbols": symbols,
        "timeframe": timeframe,
        "limit": limit,
        "symbols_total": len(symbols),
        "symbols_failed": failed,
        "symbols_ok": len(symbols) - failed,
        "ok": failed == 0,
        "per_symbol": per_symbol,
    }


def evaluate_parity_gate(
    report: dict[str, Any],
    gate: ParityGate,
) -> dict[str, Any]:
    violations: dict[str, dict[str, int]] = {}
    failed_symbols = 0

    for symbol, item in report["per_symbol"].items():
        symbol_violations: dict[str, int] = {}
        mismatch_count = int(item.get("mismatch_count", 0))
        missing_count = int(item.get("missing_in_candidate_count", 0))
        extra_count = int(item.get("extra_in_candidate_count", 0))

        if mismatch_count > gate.max_mismatch_per_symbol:
            symbol_violations["mismatch_count"] = mismatch_count
        if missing_count > gate.max_missing_per_symbol:
            symbol_violations["missing_in_candidate_count"] = missing_count
        if extra_count > gate.max_extra_per_symbol:
            symbol_violations["extra_in_candidate_count"] = extra_count

        if symbol_violations:
            violations[symbol] = symbol_violations
            failed_symbols += 1

    failed_symbols_exceeds_gate = failed_symbols > gate.max_failed_symbols
    return {
        "ok": (not violations) and (not failed_symbols_exceeds_gate),
        "failed_symbols": failed_symbols,
        "max_failed_symbols": gate.max_failed_symbols,
        "violations": violations,
    }
