"""Унифицированный reprocess для DAG-ов.

Модуль содержит:
- ReprocessConf: конфигурация из dag_run.conf
- get_run_window: единая логика расчёта окна
- maybe_update_watermark: защита watermark при reprocess
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .sync_state import SyncStateManager

Mode = Literal["incremental", "reprocess"]


@dataclass
class ReprocessConf:
    """Конфигурация reprocess из dag_run.conf.

    Attributes:
        reprocess: True = работаем по окну t0..t1, watermark не трогаем.
        t0: Начало окна (обязательно если reprocess=True).
        t1: Конец окна (обязательно если reprocess=True).
        symbols: Список символов или None = все разрешённые.
    """

    reprocess: bool = False
    t0: datetime | None = None
    t1: datetime | None = None
    symbols: list[str] | None = None


def parse_dag_conf(conf: dict | None) -> ReprocessConf:
    """Парсит dag_run.conf в ReprocessConf.

    Args:
        conf: Словарь из dag_run.conf или None.

    Returns:
        ReprocessConf с валидированными значениями.

    Raises:
        ValueError: Если reprocess=True, но t0/t1 отсутствуют или невалидны.
    """
    if not conf:
        return ReprocessConf()

    reprocess = conf.get("reprocess", False)
    t0_raw = conf.get("t0")
    t1_raw = conf.get("t1")
    symbols = conf.get("symbols")

    t0 = _parse_iso_datetime(t0_raw) if t0_raw else None
    t1 = _parse_iso_datetime(t1_raw) if t1_raw else None

    if reprocess:
        if t0 is None or t1 is None:
            raise ValueError("reprocess=True требует t0 и t1")
        if t0 >= t1:
            raise ValueError(f"t0 ({t0}) должен быть < t1 ({t1})")

    return ReprocessConf(reprocess=reprocess, t0=t0, t1=t1, symbols=symbols)


def _parse_iso_datetime(value: str | datetime) -> datetime:
    """Парсит ISO-8601 строку или возвращает datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class RunWindowResult:
    """Результат расчёта окна."""

    t0: datetime
    t1: datetime
    mode: Mode
    skip: bool = False  # True если t0 >= t1 (нечего делать)


def get_run_window(
    conf: ReprocessConf,
    sync_state: SyncStateManager,
    pipeline: str,
    symbol: str,
    data_type: str,
    *,
    now_utc: datetime | None = None,
    overlap_seconds: int = 600,
    safety_lag_seconds: int = 120,
    default_lookback_hours: int = 24,
    timeframe_minutes: int = 1,
) -> RunWindowResult:
    """Вычисляет окно для запуска pipeline.

    Args:
        conf: Конфигурация reprocess.
        sync_state: Менеджер sync_state.
        pipeline: Имя pipeline.
        symbol: Символ инструмента.
        data_type: Тип данных.
        now_utc: Текущее время UTC (для тестов).
        overlap_seconds: Overlap для защиты от пропусков.
        safety_lag_seconds: Задержка от now для неполных данных.
        default_lookback_hours: Lookback если нет watermark.
        timeframe_minutes: Размер таймфрейма для выравнивания.

    Returns:
        RunWindowResult с t0, t1, mode и флагом skip.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    if conf.reprocess:
        # Reprocess: используем явное окно
        assert conf.t0 is not None and conf.t1 is not None
        t0 = floor_to_tf(conf.t0, timeframe_minutes)
        t1 = floor_to_tf(conf.t1, timeframe_minutes)
        mode: Mode = "reprocess"
    else:
        # Incremental: от watermark до now - safety_lag
        wm = sync_state.get_last_ts(pipeline, symbol, data_type)  # type: ignore[arg-type]
        if wm is None:
            t0 = now_utc - timedelta(hours=default_lookback_hours)
        else:
            t0 = wm - timedelta(seconds=overlap_seconds)
        t1 = now_utc - timedelta(seconds=safety_lag_seconds)
        t0 = floor_to_tf(t0, timeframe_minutes)
        t1 = floor_to_tf(t1, timeframe_minutes)
        mode = "incremental"

    skip = t0 >= t1
    return RunWindowResult(t0=t0, t1=t1, mode=mode, skip=skip)


def floor_to_tf(ts: datetime, tf_minutes: int) -> datetime:
    """Округляет timestamp вниз до границы таймфрейма.

    Args:
        ts: Timestamp.
        tf_minutes: Размер таймфрейма в минутах.

    Returns:
        Округлённый timestamp.
    """
    minutes = (ts.hour * 60 + ts.minute) // tf_minutes * tf_minutes
    return ts.replace(
        hour=minutes // 60,
        minute=minutes % 60,
        second=0,
        microsecond=0,
    )


def ceil_to_tf(ts: datetime, tf_minutes: int) -> datetime:
    """Округляет timestamp вверх до границы таймфрейма.

    Args:
        ts: Timestamp.
        tf_minutes: Размер таймфрейма в минутах.

    Returns:
        Округлённый timestamp.
    """
    floored = floor_to_tf(ts, tf_minutes)
    if floored == ts:
        return ts
    return floored + timedelta(minutes=tf_minutes)


def maybe_update_watermark(
    sync_state: SyncStateManager,
    mode: Mode,
    pipeline: str,
    symbol: str,
    data_type: str,
    new_ts: datetime,
    *,
    dry_run: bool = True,
) -> bool:
    """Обновляет watermark только в incremental режиме.

    Args:
        sync_state: Менеджер sync_state.
        mode: Режим работы.
        pipeline: Имя pipeline.
        symbol: Символ инструмента.
        data_type: Тип данных.
        new_ts: Новый timestamp.
        dry_run: Если True, только печатает план.

    Returns:
        True если watermark обновлён, False если пропущен.
    """
    is_reprocess = mode == "reprocess"
    sync_state.set_last_ts(
        pipeline,  # type: ignore[arg-type]
        symbol,
        data_type,  # type: ignore[arg-type]
        new_ts,
        dry_run=dry_run,
        is_reprocess=is_reprocess,
    )
    return not is_reprocess


def filter_symbols(
    conf: ReprocessConf,
    allowed_symbols: list[str],
) -> list[str]:
    """Фильтрует символы по конфигурации.

    Args:
        conf: Конфигурация reprocess.
        allowed_symbols: Разрешённые символы (ALLOWED_TRADING_PAIRS).

    Returns:
        Пересечение conf.symbols и allowed_symbols, или все allowed.
    """
    if not conf.symbols:
        return allowed_symbols
    return [s for s in conf.symbols if s in allowed_symbols]
