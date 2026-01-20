"""
Workflow Module - Управление жизненным циклом сигналов

Основные компоненты:
- PromoteWorkflow: продвижение candidate → live → history
"""

from .promote import PromoteWorkflow

__all__ = ["PromoteWorkflow"]
