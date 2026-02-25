"""
RunContext: единая точка генерации и передачи run_id по всему pipeline.

Обеспечивает DoP-принцип: каждый артефакт (bars, labels, ml_artifacts)
привязан к run_id, algo_version и params_hash для воспроизводимости.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def _get_algo_version() -> str:
    """Читает версию пакета из importlib.metadata, fallback — 'dev'."""
    try:
        from importlib.metadata import version

        return version("pklpo")
    except Exception:
        return "dev"


def _compute_params_hash(params: dict[str, Any]) -> str:
    """SHA-256 от JSON-сериализации словаря параметров (детерминированный порядок ключей)."""
    payload = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class RunContext:
    """
    Контекст выполнения pipeline.

    Создаётся один раз на запуск и передаётся через все блоки:
    bars → labels → features → metalabeling → artifacts.

    Attributes:
        run_id: Уникальный идентификатор запуска (UUID v4).
        algo_version: Версия пакета pklpo (из pyproject.toml).
        params_hash: SHA-256 от JSON-сериализации параметров запуска.
        created_at: Время создания контекста (UTC).
    """

    run_id: str
    algo_version: str
    params_hash: str
    created_at: datetime

    @classmethod
    def create(cls, params: dict[str, Any] | None = None) -> RunContext:
        """
        Создаёт новый RunContext с уникальным run_id.

        Args:
            params: Параметры запуска (bars_mode, barrier config и т.д.).
                    Используются для вычисления params_hash.

        Returns:
            RunContext с новым UUID v4 run_id.

        Example:
            ctx = RunContext.create({"bars_mode": "dollar", "triple_pt": 0.02})
        """
        return cls(
            run_id=str(uuid.uuid4()),
            algo_version=_get_algo_version(),
            params_hash=_compute_params_hash(params or {}),
            created_at=datetime.now(tz=UTC),
        )

    @classmethod
    def from_run_id(cls, run_id: str, params: dict[str, Any] | None = None) -> RunContext:
        """
        Восстанавливает RunContext из существующего run_id (для replay/debug).

        Args:
            run_id: Существующий run_id (например, из таблицы ml_artifacts).
            params: Параметры для восстановления params_hash.

        Returns:
            RunContext с заданным run_id.
        """
        return cls(
            run_id=run_id,
            algo_version=_get_algo_version(),
            params_hash=_compute_params_hash(params or {}),
            created_at=datetime.now(tz=UTC),
        )

    def __str__(self) -> str:
        return (
            f"RunContext(run_id={self.run_id[:8]}..., "
            f"version={self.algo_version}, "
            f"params_hash={self.params_hash[:8]}...)"
        )
