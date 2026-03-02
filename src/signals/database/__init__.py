"""
Database Module - Работа с базой данных signals

Основные компоненты:
- SignalsDatabaseClient: асинхронный клиент для работы с БД
"""

from .client import SignalsDatabaseClient

__all__ = ["SignalsDatabaseClient"]
