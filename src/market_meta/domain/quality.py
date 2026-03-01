"""
Domain модели для проверок качества данных.

Содержит:
- Severity: уровни критичности (ok/warn/critical)
- Thresholds: пороги для каждого типа проверки
- CheckResult: результат одной проверки
- QualityReport: агрегированный отчет
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Уровень критичности проверки."""

    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Thresholds:
    """Пороги для определения severity."""

    warn: float
    critical: float
    direction: str = "gt"  # "gt" = value > threshold is bad, "lt" = value < threshold is bad

    def evaluate(self, value: float | None) -> Severity:
        """Определить severity по значению."""
        if value is None:
            return Severity.CRITICAL

        if self.direction == "gt":
            if value > self.critical:
                return Severity.CRITICAL
            if value > self.warn:
                return Severity.WARN
            return Severity.OK
        # lt
        if value < self.critical:
            return Severity.CRITICAL
        if value < self.warn:
            return Severity.WARN
        return Severity.OK


# Дефолтные пороги из плана
FRESHNESS_THRESHOLDS = Thresholds(warn=5.0, critical=15.0, direction="gt")
COVERAGE_THRESHOLDS = Thresholds(warn=90.0, critical=70.0, direction="lt")
SMOKE_THRESHOLDS = Thresholds(warn=9.0, critical=8.0, direction="lt")

# Fill-rate пороги
FUNDING_FILL_THRESHOLDS = Thresholds(warn=95.0, critical=80.0, direction="lt")
OI_FILL_THRESHOLDS = Thresholds(warn=95.0, critical=80.0, direction="lt")
L2_FILL_THRESHOLDS = Thresholds(warn=50.0, critical=20.0, direction="lt")

# Event freshness пороги (минуты)
FUNDING_EVENT_LAG_THRESHOLDS = Thresholds(warn=30.0, critical=120.0, direction="gt")
OI_EVENT_LAG_THRESHOLDS = Thresholds(warn=30.0, critical=120.0, direction="gt")
L2_EVENT_LAG_THRESHOLDS = Thresholds(warn=10.0, critical=60.0, direction="gt")


@dataclass
class CheckResult:
    """Результат одной проверки качества данных."""

    check_name: str
    severity: Severity
    symbol: str | None = None
    timeframe: str | None = None
    value: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    ts: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Преобразование в словарь для JSON/БД."""
        return {
            "check_name": self.check_name,
            "severity": str(self.severity),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "value": self.value,
            "meta": self.meta,
            "ts": self.ts.isoformat(),
        }

    @property
    def is_critical(self) -> bool:
        """Проверка на критический уровень."""
        return self.severity == Severity.CRITICAL


@dataclass
class QualityReport:
    """Агрегированный отчет по всем проверкам."""

    results: list[CheckResult] = field(default_factory=list)
    ts: datetime = field(default_factory=datetime.utcnow)

    @property
    def max_severity(self) -> Severity:
        """Максимальный уровень критичности."""
        if not self.results:
            return Severity.OK
        severities = [r.severity for r in self.results]
        if Severity.CRITICAL in severities:
            return Severity.CRITICAL
        if Severity.WARN in severities:
            return Severity.WARN
        return Severity.OK

    @property
    def has_critical(self) -> bool:
        """Есть ли критические проблемы."""
        return any(r.is_critical for r in self.results)

    @property
    def critical_results(self) -> list[CheckResult]:
        """Список критических результатов."""
        return [r for r in self.results if r.is_critical]

    def add(self, result: CheckResult) -> None:
        """Добавить результат проверки."""
        self.results.append(result)

    def extend(self, results: list[CheckResult]) -> None:
        """Добавить несколько результатов."""
        self.results.extend(results)
