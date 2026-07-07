from __future__ import annotations

from pathlib import Path


def test_scan_flags_raw_sql_marker_outside_allowlist() -> None:
    from src.identity.application.raw_read_guard import scan_source_for_raw_markers

    content = "SELECT close FROM swap_ohlcv_p WHERE symbol = :symbol"
    violations = scan_source_for_raw_markers("src/scoring_engine/compute.py", content)

    assert len(violations) == 1
    assert violations[0].marker == "swap_ohlcv_p"
    assert violations[0].line_no == 1


def test_scan_flags_orm_marker_outside_allowlist() -> None:
    from src.identity.application.raw_read_guard import scan_source_for_raw_markers

    content = "from src.models import SwapOhlcvP\n"
    violations = scan_source_for_raw_markers(
        "src/trade_recommender/recommend.py", content
    )

    assert len(violations) == 1
    assert violations[0].marker == "SwapOhlcvP"


def test_scan_allows_marker_inside_allowlisted_path() -> None:
    """The operational allowlist (§12.3) is real writers/DQ/health/cleanup —
    a raw reference there is intentional, not a violation."""
    from src.identity.application.raw_read_guard import scan_source_for_raw_markers

    content = "SELECT * FROM swap_ohlcv_p"
    violations = scan_source_for_raw_markers(
        "src/candles/infrastructure/raw_ingest.py", content
    )

    assert violations == []


def test_scan_passes_clean_facade_only_module() -> None:
    from src.identity.application.raw_read_guard import scan_source_for_raw_markers

    content = "from src.identity.application.ohlcv_facade import OhlcvFacade\n"
    violations = scan_source_for_raw_markers("src/scoring_engine/compute.py", content)

    assert violations == []


def test_allowlist_matches_matrix_operational_exceptions() -> None:
    """Drift guard on the guard's own config: the allowlist must be exactly
    the operational exceptions documented in
    consumer_writer_cutover_matrix_2026-07-02.md's 'Raw writers and
    operational direct-read allowlist' table — silently growing this list is
    exactly the failure mode the guard exists to prevent."""
    from src.identity.application.raw_read_guard import OPERATIONAL_ALLOWLIST

    expected_operational_paths = {
        "src/candles/",
        "src/utils/health_checks.py",
        "src/cli/commands/cleanup.py",
        "ops/airflow/dags/pipeline_monitoring.py",
        "ops/airflow/dags/swap_ohlcv_retention.py",
        "ops/monitoring/grafana/dashboards/pklpo-candle-coverage.json",
        "ops/monitoring/grafana/sql/create_grafana_ro_role.sql",
    }
    # Everything else in the allowlist must be explicitly justified as a
    # guard-self-reference, not a silently-added reader exception.
    guard_self_reference = {"src/identity/application/raw_read_guard.py"}

    assert (
        set(OPERATIONAL_ALLOWLIST) == expected_operational_paths | guard_self_reference
    )


def test_identity_application_layer_is_facade_only_by_construction() -> None:
    """The concrete, currently-true enforcement this task delivers: every
    module in src/identity/application/ (the seams Tasks 4.2/4.4/5.1-5.4
    built for analytical consumers to call) is facade-only. This is
    deliberately scoped to application/, not infrastructure/ — the facade's
    own backend (src/identity/infrastructure/ohlcv_facade_repository.py) and
    the continuous build job legitimately read raw OHLCV to build/serve the
    facade in the first place, exactly like src/candles/infrastructure does
    for candle ingest. That is not a bypass; it is the one writer/reader the
    rest of the system is supposed to go through."""
    from src.identity.application.raw_read_guard import (
        find_raw_read_violations_in_repo,
    )

    repo_root = Path(__file__).resolve().parents[2]
    violations = find_raw_read_violations_in_repo(
        repo_root, scan_dirs=("src/identity/application",)
    )

    assert violations == []
