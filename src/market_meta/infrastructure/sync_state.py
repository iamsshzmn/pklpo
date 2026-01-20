"""Sync State - управление watermark для инкрементальной загрузки.

Модуль отвечает за:
- Чтение/запись последнего обработанного timestamp
- Инкрементальная загрузка: from last_ts -> now - safety_lag
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Literal

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

Pipeline = Literal["raw_ingest", "normalize_1m", "aggregate"]
DataType = Literal["funding", "oi", "l2"]


class SyncStateManager:
    """Менеджер состояния синхронизации (watermark)."""

    DEFAULT_SAFETY_LAG_SECONDS = 120  # 2 минуты

    def __init__(
        self,
        engine: Engine,
        safety_lag_seconds: int = DEFAULT_SAFETY_LAG_SECONDS,
    ) -> None:
        """Инициализация менеджера.

        Args:
            engine: SQLAlchemy engine.
            safety_lag_seconds: Задержка от now() для избежания неполных данных.
        """
        self._engine = engine
        self._safety_lag = timedelta(seconds=safety_lag_seconds)

    def get_last_ts(
        self,
        pipeline: Pipeline,
        symbol: str,
        data_type: DataType,
    ) -> datetime | None:
        """Получает последний обработанный timestamp.

        Args:
            pipeline: Имя pipeline.
            symbol: Символ инструмента.
            data_type: Тип данных.

        Returns:
            Последний timestamp или None если записи нет.
        """
        sql = text(
            """
            SELECT last_ts
            FROM ops.sync_state
            WHERE pipeline = :pipeline
              AND symbol = :symbol
              AND data_type = :data_type
        """
        )

        with self._engine.connect() as conn:
            result = conn.execute(
                sql,
                {"pipeline": pipeline, "symbol": symbol, "data_type": data_type},
            )
            row = result.fetchone()
            return row.last_ts if row else None

    def set_last_ts(
        self,
        pipeline: Pipeline,
        symbol: str,
        data_type: DataType,
        last_ts: datetime,
        *,
        dry_run: bool = True,
        is_reprocess: bool = False,
    ) -> None:
        """Устанавливает последний обработанный timestamp.

        Args:
            pipeline: Имя pipeline.
            symbol: Символ инструмента.
            data_type: Тип данных.
            last_ts: Новый timestamp.
            dry_run: Если True, только печатает план.
            is_reprocess: Если True, watermark не обновляется (защита курсора).
        """
        if is_reprocess:
            print(f"[REPROCESS] Watermark не обновляется для {pipeline}/{symbol}/{data_type}")
            return

        if dry_run:
            print(f"[DRY-RUN] Обновление sync_state:")
            print(f"  pipeline={pipeline}, symbol={symbol}, data_type={data_type}")
            print(f"  last_ts={last_ts}")
            return

        sql = text(
            """
            INSERT INTO ops.sync_state (pipeline, symbol, data_type, last_ts)
            VALUES (:pipeline, :symbol, :data_type, :last_ts)
            ON CONFLICT (pipeline, symbol, data_type)
            DO UPDATE SET last_ts = EXCLUDED.last_ts
        """
        )

        with self._engine.begin() as conn:
            conn.execute(
                sql,
                {
                    "pipeline": pipeline,
                    "symbol": symbol,
                    "data_type": data_type,
                    "last_ts": last_ts,
                },
            )

    def get_sync_window(
        self,
        pipeline: Pipeline,
        symbol: str,
        data_type: DataType,
        default_lookback: timedelta = timedelta(hours=24),
        lookback_sec: int = 600,
        max_window_hours: int = 24,
    ) -> tuple[datetime, datetime]:
        """Вычисляет окно для синхронизации.

        Формула:
        - from = last_ts - lookback_sec (overlap для защиты от пропусков)
        - to = now() - safety_lag (защита от неполных данных)

        Args:
            pipeline: Имя pipeline.
            symbol: Символ инструмента.
            data_type: Тип данных.
            default_lookback: Период по умолчанию если нет watermark.
            lookback_sec: Overlap в секундах для защиты от пропусков.
            max_window_hours: Максимальный размер окна (защита при первом запуске).

        Returns:
            Кортеж (start_ts, end_ts) для загрузки. Если end_ts <= start_ts, окно пустое.
        """
        now = datetime.now(timezone.utc)
        end_ts = now - self._safety_lag

        last_ts = self.get_last_ts(pipeline, symbol, data_type)
        if last_ts is None:
            start_ts = now - default_lookback
        else:
            # Overlap для защиты от пропусков на границах
            start_ts = last_ts - timedelta(seconds=lookback_sec)

        # Ограничиваем максимальный размер окна
        max_window = timedelta(hours=max_window_hours)
        if end_ts - start_ts > max_window:
            start_ts = end_ts - max_window

        return start_ts, end_ts

    def get_all_states(self, pipeline: Pipeline | None = None) -> list[dict]:
        """Получает все записи sync_state.

        Args:
            pipeline: Фильтр по pipeline (опционально).

        Returns:
            Список записей.
        """
        if pipeline:
            sql = text(
                """
                SELECT pipeline, symbol, data_type, last_ts, updated_at
                FROM ops.sync_state
                WHERE pipeline = :pipeline
                ORDER BY symbol, data_type
            """
            )
            params = {"pipeline": pipeline}
        else:
            sql = text(
                """
                SELECT pipeline, symbol, data_type, last_ts, updated_at
                FROM ops.sync_state
                ORDER BY pipeline, symbol, data_type
            """
            )
            params = {}

        with self._engine.connect() as conn:
            result = conn.execute(sql, params)
            return [
                {
                    "pipeline": row.pipeline,
                    "symbol": row.symbol,
                    "data_type": row.data_type,
                    "last_ts": row.last_ts,
                    "updated_at": row.updated_at,
                }
                for row in result
            ]
