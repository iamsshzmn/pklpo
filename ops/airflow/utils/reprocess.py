"""Reprocess utilities для Airflow DAGs.

Модуль предоставляет:
- Парсинг dag_run.conf для режима reprocess
- Выбор окна: explicit (t0/t1) vs watermark
- Извлечение run_id из контекста
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ReprocessConfig:
    """Конфигурация reprocess режима."""

    is_reprocess: bool
    t0: datetime | None
    t1: datetime | None
    symbols: list[str] | None
    mode: str  # "soft" (COALESCE) или "hard" (DELETE + INSERT)

    @property
    def has_explicit_window(self) -> bool:
        """Проверяет наличие явно заданного окна."""
        return self.t0 is not None and self.t1 is not None


def parse_reprocess_conf(context: dict[str, Any]) -> ReprocessConfig:
    """Парсит dag_run.conf для определения режима reprocess.

    Args:
        context: Airflow task context.

    Returns:
        ReprocessConfig с параметрами reprocess.

    Example dag_run.conf:
        {
            "reprocess": true,
            "t0": "2025-12-01T00:00:00Z",
            "t1": "2025-12-02T00:00:00Z",
            "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
            "mode": "soft"
        }
    """
    dag_run = context.get("dag_run")
    conf: dict[str, Any] = {}
    if dag_run is not None:
        conf = dag_run.conf or {}

    is_reprocess = conf.get("reprocess", False)
    t0 = _parse_datetime(conf.get("t0"))
    t1 = _parse_datetime(conf.get("t1"))
    symbols = conf.get("symbols")
    mode = conf.get("mode", "soft")

    return ReprocessConfig(
        is_reprocess=is_reprocess,
        t0=t0,
        t1=t1,
        symbols=symbols,
        mode=mode,
    )


def get_run_id(context: dict[str, Any]) -> str:
    """Извлекает run_id из Airflow context.

    Args:
        context: Airflow task context.

    Returns:
        run_id строка.
    """
    return context.get("run_id", "unknown")


def get_window(
    context: dict[str, Any],
    default_start: datetime,
    default_end: datetime,
) -> tuple[datetime, datetime, bool]:
    """Определяет окно для обработки.

    Args:
        context: Airflow task context.
        default_start: Начало окна по умолчанию (из watermark).
        default_end: Конец окна по умолчанию.

    Returns:
        Кортеж (start, end, is_reprocess).
    """
    conf = parse_reprocess_conf(context)

    if conf.is_reprocess and conf.has_explicit_window:
        return conf.t0, conf.t1, True  # type: ignore[return-value]

    return default_start, default_end, False


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    """Парсит datetime из строки ISO8601 или возвращает как есть."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    # ISO8601 парсинг
    from datetime import timezone

    try:
        # Пробуем с Z
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None
