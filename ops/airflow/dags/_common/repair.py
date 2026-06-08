"""Shared repair-DAG helpers for coercion, windows, and XCom validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.candles.application.repair import resolve_repair_window
from src.candles.application.repair.summary import RepairSummary
from src.candles.domain.repair import RepairExecutionMode, RepairStrategy
from src.candles.domain.timeframes import TF_TO_MS

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

DEFAULT_SWAP_REPAIR_XCOM_KEYS = (
    "mode",
    "strategy",
    "symbol",
    "timeframe",
    "window",
    "gap_tasks",
    "requested_bars",
    "remaining_gap_tasks",
    "remaining_requested_bars",
    "verification_method",
    "rows_written",
    "fetch_calls",
    "verified",
    "guardrail_violations",
    "watermark_updated",
)

OPTIONAL_SWAP_REPAIR_OUTCOME_VALUES = ("success", "partial", "empty", "fail")
OPTIONAL_SWAP_REPAIR_INT_KEYS = (
    "received_bars",
    "remaining_missing_before",
    "remaining_missing_after",
    "progress",
)
OPTIONAL_SWAP_REPAIR_FLOAT_KEYS = (
    "api_fill_ratio",
    "write_success_ratio",
)
OPTIONAL_SWAP_REPAIR_BOOL_KEYS = ("blocked",)
OPTIONAL_SWAP_REPAIR_STR_KEYS = ("blocked_reason", "blocked_cause")

DEFAULT_SWAP_REPAIR_TIMEFRAMES = ("1m", "1H", "4H", "1D", "1W", "1M")
DEFAULT_SWAP_REPAIR_WINDOW_HOURS = 6
DEFAULT_SWAP_REPAIR_SYMBOL = "BTC-USDT-SWAP"


@dataclass(slots=True)
class SwapRepairValidatedConf:
    symbol: str
    timeframes: list[str]
    mode: str
    repair_strategy: str
    start_ts_ms: int | None
    end_ts_ms: int | None
    padding_bars: int
    max_gap_tasks_per_run: int
    max_requested_bars_per_run: int
    max_range_days: int
    max_fail_ratio: float
    auto_apply_anchor_strategy: str
    anchor_ts_ms: int | None
    auto_apply_window: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def coerce_int(
    value: Any,
    default: int | None = None,
    *,
    field_name: str,
    context_name: str = "swap_repair",
) -> int:
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{context_name} field {field_name!r} is required")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{context_name} field {field_name!r} must be an integer, got {value!r}"
        ) from exc


def coerce_float(
    value: Any,
    default: float | None = None,
    *,
    field_name: str,
    context_name: str = "swap_repair",
) -> float:
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{context_name} field {field_name!r} is required")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{context_name} field {field_name!r} must be a number, got {value!r}"
        ) from exc


def _parse_utc_timestamp_ms(value: str) -> int:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.astimezone(UTC).timestamp() * 1000)


parse_utc_timestamp_ms = _parse_utc_timestamp_ms


def _utc_now_ts_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def utc_now_ts_ms() -> int:
    return _utc_now_ts_ms()


def _normalize_swap_repair_symbol(value: Any) -> str:
    symbol = str(value or DEFAULT_SWAP_REPAIR_SYMBOL).strip()
    if not symbol:
        raise ValueError("swap_repair field 'symbol' must be a non-empty OKX instId (e.g. BTC-USDT-SWAP)")
    return symbol


def _normalize_swap_repair_timeframe(value: Any) -> str:
    timeframe = str(value).strip()
    if timeframe not in TF_TO_MS or timeframe not in DEFAULT_SWAP_REPAIR_TIMEFRAMES:
        supported = ", ".join(DEFAULT_SWAP_REPAIR_TIMEFRAMES)
        raise ValueError(f"Unsupported repair timeframe: {timeframe}. Expected one of: {supported}")
    return timeframe


normalize_swap_repair_timeframe = _normalize_swap_repair_timeframe


def _normalize_swap_repair_timeframes(conf: dict[str, Any]) -> list[str]:
    raw_timeframes = conf.get("timeframes")
    legacy_timeframe = conf.get("timeframe")
    if raw_timeframes is None or raw_timeframes == "":
        if legacy_timeframe is None or legacy_timeframe == "":
            raise ValueError("swap_repair requires explicit timeframes or legacy timeframe")
        raw_timeframes = legacy_timeframe

    if isinstance(raw_timeframes, str):
        candidates = [part.strip() for part in raw_timeframes.replace(",", " ").split()]
    elif isinstance(raw_timeframes, (list, tuple)):
        candidates = [str(part).strip() for part in raw_timeframes if str(part).strip()]
    else:
        candidates = [str(raw_timeframes).strip()]

    normalized: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        timeframe = _normalize_swap_repair_timeframe(candidate)
        if timeframe not in normalized:
            normalized.append(timeframe)

    if not normalized:
        raise ValueError("swap_repair timeframes is empty after normalization")
    return normalized


def _normalize_swap_repair_auto_apply_anchor_strategy(conf: dict[str, Any]) -> str:
    raw = str(conf.get("auto_apply_anchor_strategy", "first-coverage")).strip()
    allowed = {"first-coverage", "listing-date", "explicit"}
    if raw not in allowed:
        raise ValueError(
            "swap_repair field 'auto_apply_anchor_strategy' must be one of: "
            + ", ".join(sorted(allowed))
        )
    return raw


def _resolve_swap_repair_auto_apply_anchor_ts_ms(conf: dict[str, Any]) -> int | None:
    anchor_raw = conf.get("auto_apply_anchor")
    if anchor_raw in {None, ""}:
        return None
    return _parse_utc_timestamp_ms(str(anchor_raw))


def normalize_swap_repair_conf(
    conf: dict[str, Any],
    *,
    now_ts_ms: int | None = None,
    parse_timestamp_ms: Callable[[str], int] = _parse_utc_timestamp_ms,
    default_window_hours: int = DEFAULT_SWAP_REPAIR_WINDOW_HOURS,
) -> SwapRepairValidatedConf:
    symbol = _normalize_swap_repair_symbol(conf.get("symbol", DEFAULT_SWAP_REPAIR_SYMBOL))
    timeframes = _normalize_swap_repair_timeframes(conf)
    mode = RepairExecutionMode(str(conf.get("mode", RepairExecutionMode.DETECT_ONLY.value)))
    strategy = RepairStrategy(str(conf.get("repair_strategy", RepairStrategy.GAP_REPAIR.value)))
    has_window = conf.get("start") is not None or conf.get("end") is not None
    auto_apply_window = mode is RepairExecutionMode.APPLY and not has_window

    if auto_apply_window:
        start_ts_ms = None
        end_ts_ms = None
    else:
        resolved = resolve_repair_window_from_conf(
            conf,
            now_ts_ms=_utc_now_ts_ms() if now_ts_ms is None else now_ts_ms,
            parse_timestamp_ms=parse_timestamp_ms,
            default_window_hours=default_window_hours,
        )
        start_ts_ms, end_ts_ms = resolved

    return SwapRepairValidatedConf(
        symbol=symbol,
        timeframes=timeframes,
        mode=mode.value,
        repair_strategy=strategy.value,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        padding_bars=coerce_int(conf.get("padding_bars"), field_name="padding_bars", default=0),
        max_gap_tasks_per_run=coerce_int(
            conf.get("max_gap_tasks_per_run"),
            field_name="max_gap_tasks_per_run",
            default=50,
        ),
        max_requested_bars_per_run=coerce_int(
            conf.get("max_requested_bars_per_run"),
            field_name="max_requested_bars_per_run",
            default=10_000,
        ),
        max_range_days=coerce_int(
            conf.get("max_range_days"),
            field_name="max_range_days",
            default=7,
        ),
        max_fail_ratio=coerce_float(
            conf.get("max_fail_ratio"),
            field_name="max_fail_ratio",
            default=0.1,
        ),
        auto_apply_anchor_strategy=_normalize_swap_repair_auto_apply_anchor_strategy(conf),
        anchor_ts_ms=_resolve_swap_repair_auto_apply_anchor_ts_ms(conf),
        auto_apply_window=auto_apply_window,
    )


def payload_to_dict(payload: Any, *, context_name: str = "swap_repair") -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if is_dataclass(payload):
        return asdict(payload)

    attrs = getattr(payload, "__dict__", None)
    if isinstance(attrs, dict):
        return dict(attrs)
    raise TypeError(f"{context_name} payload must be dict-like, got {type(payload).__name__}")


def resolve_repair_window_from_conf(
    conf: dict[str, Any],
    *,
    now_ts_ms: int,
    parse_timestamp_ms: Callable[[str], int],
    default_window_hours: int,
    context_name: str = "swap_repair",
    window_hours_field: str = "window_hours",
) -> tuple[int, int]:
    has_start = conf.get("start") is not None
    has_end = conf.get("end") is not None
    if has_start != has_end:
        raise ValueError(f"{context_name} requires both start and end when either is provided")

    if has_start and has_end:
        start_ts_ms = parse_timestamp_ms(str(conf["start"]))
        end_ts_ms = parse_timestamp_ms(str(conf["end"]))
        resolved = resolve_repair_window(
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            window_hours=default_window_hours,
            now_ts_ms=now_ts_ms,
        )
        return resolved.start_ts_ms, resolved.end_ts_ms

    window_hours = coerce_int(
        conf.get(window_hours_field),
        default=default_window_hours,
        field_name=window_hours_field,
        context_name=context_name,
    )
    resolved = resolve_repair_window(
        start_ts_ms=None,
        end_ts_ms=None,
        window_hours=window_hours,
        now_ts_ms=now_ts_ms,
    )
    return resolved.start_ts_ms, resolved.end_ts_ms


def validate_swap_repair_xcom_payload(
    payload: Any,
    *,
    context_name: str = "swap_repair",
    allowed_symbols: Collection[str] | None = None,
    allowed_timeframes: Collection[str] | None = None,
    allow_empty_window_with_work: bool = False,
) -> dict[str, Any]:
    normalized = payload_to_dict(payload, context_name=context_name)
    missing_keys = [key for key in DEFAULT_SWAP_REPAIR_XCOM_KEYS if key not in normalized]
    if missing_keys:
        raise ValueError(f"{context_name} XCom missing keys: {missing_keys}")

    window = normalized["window"]
    if not isinstance(window, dict):
        raise ValueError(f"{context_name} window must be a dict")
    if "start_ts_ms" not in window or "end_ts_ms" not in window:
        raise ValueError(f"{context_name} window must contain start_ts_ms and end_ts_ms")

    start_ts_ms = coerce_int(
        window["start_ts_ms"],
        field_name="window.start_ts_ms",
        context_name=context_name,
    )
    end_ts_ms = coerce_int(
        window["end_ts_ms"],
        field_name="window.end_ts_ms",
        context_name=context_name,
    )
    if start_ts_ms > end_ts_ms:
        raise ValueError(f"{context_name} window must satisfy start_ts_ms < end_ts_ms")

    if allowed_symbols is not None and normalized["symbol"] not in allowed_symbols:
        raise ValueError(
            f"{context_name} symbol must stay within v1 scope: {tuple(allowed_symbols)}"
        )
    if allowed_timeframes is not None and normalized["timeframe"] not in allowed_timeframes:
        raise ValueError(
            f"{context_name} timeframe must stay within v1 scope: {tuple(allowed_timeframes)}"
        )

    gap_tasks = coerce_int(
        normalized.get("gap_tasks", 0),
        default=0,
        field_name="gap_tasks",
        context_name=context_name,
    )
    requested_bars = coerce_int(
        normalized.get("requested_bars", 0),
        default=0,
        field_name="requested_bars",
        context_name=context_name,
    )
    remaining_gap_tasks = coerce_int(
        normalized.get("remaining_gap_tasks", 0),
        default=0,
        field_name="remaining_gap_tasks",
        context_name=context_name,
    )
    remaining_requested_bars = coerce_int(
        normalized.get("remaining_requested_bars", 0),
        default=0,
        field_name="remaining_requested_bars",
        context_name=context_name,
    )
    auto_apply_incomplete = bool(normalized.get("auto_apply_incomplete", False))
    has_remaining_work = remaining_gap_tasks > 0 or remaining_requested_bars > 0

    if not allow_empty_window_with_work and start_ts_ms == end_ts_ms:
        if gap_tasks > 0 or requested_bars > 0 or has_remaining_work:
            raise ValueError(f"{context_name} empty window is allowed only for no-op results")

    violations = normalized.get("guardrail_violations") or []
    if violations:
        raise ValueError(f"{context_name} guardrail violations: {violations}")
    if normalized.get("watermark_updated"):
        raise ValueError(f"{context_name} must not update watermark")
    if normalized.get("mode") == "apply":
        if auto_apply_incomplete:
            if not has_remaining_work:
                raise ValueError(f"{context_name} partial apply must report remaining work")
        else:
            if not normalized.get("verified"):
                raise ValueError(f"{context_name} apply run must be verified")
            if has_remaining_work:
                raise ValueError(f"{context_name} apply run must not leave remaining gaps")
            if normalized.get("verification_method") != "gap-detection":
                raise ValueError(
                    f"{context_name} apply run must use gap-detection verification"
                )

    if "outcome" in normalized and normalized["outcome"] is not None:
        outcome_value = normalized["outcome"]
        if (
            not isinstance(outcome_value, str)
            or outcome_value not in OPTIONAL_SWAP_REPAIR_OUTCOME_VALUES
        ):
            raise ValueError(
                f"{context_name} outcome must be one of {OPTIONAL_SWAP_REPAIR_OUTCOME_VALUES}, "
                f"got {outcome_value!r}"
            )
    for key in OPTIONAL_SWAP_REPAIR_INT_KEYS:
        if key in normalized and normalized[key] is not None:
            normalized[key] = coerce_int(
                normalized[key],
                field_name=key,
                context_name=context_name,
            )
    for key in OPTIONAL_SWAP_REPAIR_FLOAT_KEYS:
        if key in normalized and normalized[key] is not None:
            value = normalized[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(
                    f"{context_name} {key} must be numeric, got {type(value).__name__}"
                )
            normalized[key] = float(value)
    for key in OPTIONAL_SWAP_REPAIR_BOOL_KEYS:
        if key in normalized and normalized[key] is not None:
            value = normalized[key]
            if not isinstance(value, bool):
                raise ValueError(
                    f"{context_name} {key} must be a boolean, got {type(value).__name__}"
                )
    for key in OPTIONAL_SWAP_REPAIR_STR_KEYS:
        if key in normalized and normalized[key] is not None:
            value = normalized[key]
            if not isinstance(value, str):
                raise ValueError(
                    f"{context_name} {key} must be a string, got {type(value).__name__}"
                )
    return normalized


def normalize_swap_repair_summary_payloads(
    payloads: Any,
    *,
    context_name: str = "swap_repair",
) -> list[dict[str, Any]]:
    if payloads is None:
        raise ValueError(f"{context_name} requires validated summary payloads")

    items = list(payloads) if isinstance(payloads, (list, tuple)) else [payloads]

    if not items:
        raise ValueError(f"{context_name} requires validated summary payloads")

    normalized_payloads: list[dict[str, Any]] = []
    for payload in items:
        summary = RepairSummary.from_mapping(payload_to_dict(payload, context_name=context_name))
        normalized_payloads.append(summary.to_dict())
    return normalized_payloads
