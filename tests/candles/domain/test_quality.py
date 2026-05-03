from src.candles.domain.quality import CheckResult, QualityReport, Severity


def _result(check_name: str, severity: Severity) -> CheckResult:
    return CheckResult(check_name=check_name, severity=severity)


def test_quality_report_summary_empty() -> None:
    report = QualityReport()

    assert report.summary() == {"total": 0, "ok": 0, "warn": 0, "critical": 0}


def test_quality_report_summary_mixed() -> None:
    report = QualityReport(
        results=[
            _result("ok_check", Severity.OK),
            _result("warn_check", Severity.WARN),
            _result("critical_check", Severity.CRITICAL),
            _result("ok_check_2", Severity.OK),
        ]
    )

    assert report.summary() == {"total": 4, "ok": 2, "warn": 1, "critical": 1}


def test_quality_report_summary_all_critical() -> None:
    report = QualityReport(
        results=[
            _result("critical_1", Severity.CRITICAL),
            _result("critical_2", Severity.CRITICAL),
        ]
    )

    assert report.summary() == {"total": 2, "ok": 0, "warn": 0, "critical": 2}
