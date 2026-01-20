"""
Инициализация пакета базы данных для модуля Risk
"""

from .client import RiskDatabaseClient
from .migrations import RiskDatabaseMigrations, run_risk_migrations
