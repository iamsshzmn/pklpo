"""Raw-OHLCV-read guard (§12.12 п.12-13, §14.13).

The consumer/writer cutover matrix
(`Captains_Logbook/planning/data_layers/consumer_writer_cutover_matrix_2026-07-02.md`)
distinguishes two kinds of `swap_ohlcv_p`/`SwapOhlcvP` reader:

- analytical consumers (features, market_selection, scoring, backtest,
  trade_recommender, BI, notebooks) — these must go through the candles
  facade (code or DB-side) once cut over; a direct raw read here is exactly
  the "BI bypass" / raw-symbol-leakage class of bug Stage 4/5 exists to
  close off.
- the explicit operational allowlist (§12.3) — candles ingest/sync,
  repair/bootstrap/backfill, raw DQ/alignment/eligibility, health/monitoring,
  cleanup/retention — these are intentionally raw-only and are not cutover
  targets.

This module is the reusable scanning primitive behind that guard: given a
file's path and text content, decide whether it references the raw OHLCV
table/model, and whether that reference is allowed for that path. It is pure
(no filesystem access) so it can be unit-tested with synthetic fixtures; a
thin, real-filesystem wrapper (`find_raw_read_violations_in_repo`) is what a
pytest guard test or CI check calls against the actual tree.

This guard intentionally does *not* yet run as a repo-wide `make check` gate
against every module — most analytical consumers (market_selection,
scoring_engine, trade_recommender, backtest, CLI train/label/bars,
src/features itself) still read raw directly today; Tasks 5.3/5.4 only
*proposed* their cutover diffs, they were not applied in this pass (see
those tasks' reports). Turning this into a hard, always-on gate before those
diffs are actually merged would fail `make check` for reasons that are
already known and documented, not new bugs — that activation step belongs
with whoever applies the real cutover PRs. What *is* enforced here, right
now, is scoped to `src/identity/` itself (see
`tests/identity/test_raw_read_guard.py`): every identity-layer module built
across Tasks 4.2-5.4 is proven, by this same guard, to be facade-only by
construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# The two ways source code references the raw OHLCV table: the bare SQL
# table name (raw string queries) and the ORM model class name.
RAW_OHLCV_MARKERS: tuple[str, ...] = ("swap_ohlcv_p", "SwapOhlcvP")

# Operational allowlist (§12.3): the exact set of path prefixes permitted to
# read/write the raw OHLCV table directly, per the matrix's own "Raw writers
# and operational direct-read allowlist" table. Kept as an explicit,
# reviewable list — silently exempting a path is exactly the failure mode
# this guard exists to prevent.
OPERATIONAL_ALLOWLIST: tuple[str, ...] = (
    "src/candles/",
    "src/utils/health_checks.py",
    "src/cli/commands/cleanup.py",
    "ops/airflow/dags/pipeline_monitoring.py",
    "ops/airflow/dags/swap_ohlcv_retention.py",
    "ops/monitoring/grafana/dashboards/pklpo-candle-coverage.json",
    "ops/monitoring/grafana/sql/create_grafana_ro_role.sql",
    # This module itself: it *defines* the raw markers/allowlist as string
    # literals (to scan for them) — it does not read the raw table. Without
    # this entry the guard would flag its own marker definitions.
    "src/identity/application/raw_read_guard.py",
)


@dataclass(frozen=True)
class RawReadViolation:
    path: str
    line_no: int
    marker: str
    line: str


def is_allowlisted(
    path: str, *, allowlist: tuple[str, ...] = OPERATIONAL_ALLOWLIST
) -> bool:
    normalized = path.replace("\\", "/")
    return any(
        normalized.startswith(prefix) or prefix in normalized for prefix in allowlist
    )


def scan_source_for_raw_markers(
    path: str,
    content: str,
    *,
    allowlist: tuple[str, ...] = OPERATIONAL_ALLOWLIST,
    markers: tuple[str, ...] = RAW_OHLCV_MARKERS,
) -> list[RawReadViolation]:
    """Pure scan: does `content` (as if read from `path`) reference a raw
    OHLCV marker outside the operational allowlist? Fails closed in the
    sense that matters here — an allowlist miss (path not in the explicit
    list) always means "flag it", never "assume it's fine"."""
    if is_allowlisted(path, allowlist=allowlist):
        return []

    violations: list[RawReadViolation] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        for marker in markers:
            if marker in line:
                violations.append(
                    RawReadViolation(
                        path=path, line_no=line_no, marker=marker, line=line.strip()
                    )
                )
    return violations


def find_raw_read_violations_in_repo(
    root: Path,
    *,
    scan_dirs: tuple[str, ...] = ("src", "ops"),
    allowlist: tuple[str, ...] = OPERATIONAL_ALLOWLIST,
    markers: tuple[str, ...] = RAW_OHLCV_MARKERS,
) -> list[RawReadViolation]:
    """Real-filesystem wrapper: walk `scan_dirs` under `root` and apply
    `scan_source_for_raw_markers` to every `.py` file. Not itself wired into
    `make check` yet (see module docstring) — intended for a scoped test
    (e.g. against `src/identity/`) or for the eventual repo-wide gate once
    Tasks 5.3/5.4's proposed diffs are actually applied."""
    violations: list[RawReadViolation] = []
    for scan_dir in scan_dirs:
        base = root / scan_dir
        if not base.exists():
            continue
        for file_path in sorted(base.rglob("*.py")):
            relative = str(file_path.relative_to(root)).replace("\\", "/")
            content = file_path.read_text(encoding="utf-8")
            violations.extend(
                scan_source_for_raw_markers(
                    relative, content, allowlist=allowlist, markers=markers
                )
            )
    return violations
