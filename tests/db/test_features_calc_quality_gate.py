from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_features_calc_does_not_disable_quality_gate() -> None:
    text = (ROOT / "ops/airflow/dags/features_calc.py").read_text(encoding="utf-8")

    assert "FEATURES_MIN_FILL_RATE" not in text
    assert "FEATURES_MAX_NAN_RATIO" not in text


def test_features_calc_uses_materialized_feature_eligibility() -> None:
    text = (ROOT / "ops/airflow/dags/features_calc.py").read_text(encoding="utf-8")

    assert "eligibility_interface" in text
    assert "can_compute_features" in text


def test_features_calc_bulk_requested_symbols_fail_close_missing_eligibility() -> None:
    text = (ROOT / "ops/airflow/dags/features_calc.py").read_text(encoding="utf-8")

    assert "record is None" in text
    assert "Feature eligibility missing" in text
