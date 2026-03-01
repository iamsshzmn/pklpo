"""
Модуль для системы алертов и уведомлений.
"""

from .slack_webhook import SlackNotifier

__all__ = ["SlackNotifier"]
