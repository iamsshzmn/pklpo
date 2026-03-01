"""
Общие утилиты для всего quant pipeline.

Публичный API:
    RunContext: Сквозной контекст выполнения pipeline (run_id, версия, хэш параметров).
"""

from .run_context import RunContext

__all__ = ["RunContext"]
