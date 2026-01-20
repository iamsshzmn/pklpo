#!/usr/bin/env python3
"""
MTF Alert System

Система алертов для MTF модуля с поддержкой различных каналов:
- Slack webhook
- Telegram bot
- Логирование
- Email (опционально)
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import aiohttp


class AlertLevel(Enum):
    """Уровни алертов"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


@dataclass
class AlertMessage:
    """Сообщение алерта"""

    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AlertChannel:
    """Базовый класс для каналов алертов"""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"alerts.{name}")

    async def send_alert(self, alert: AlertMessage) -> bool:
        """Отправить алерт (должен быть переопределен)"""
        raise NotImplementedError

    async def test_connection(self) -> bool:
        """Проверить соединение (должен быть переопределен)"""
        raise NotImplementedError


class LoggingAlertChannel(AlertChannel):
    """Канал алертов через логирование"""

    def __init__(self):
        super().__init__("logging")

    async def send_alert(self, alert: AlertMessage) -> bool:
        """Отправить алерт через логирование"""
        try:
            log_message = (
                f"[{alert.level.value.upper()}] {alert.title}: {alert.message}"
            )

            if alert.level == AlertLevel.CRITICAL or alert.level == AlertLevel.ERROR:
                self.logger.error(log_message)
            elif alert.level == AlertLevel.WARNING:
                self.logger.warning(log_message)
            else:
                self.logger.info(log_message)

            return True
        except Exception as e:
            self.logger.error(f"Ошибка отправки алерта через логирование: {e}")
            return False

    async def test_connection(self) -> bool:
        """Проверить соединение (всегда доступно)"""
        return True


class SlackAlertChannel(AlertChannel):
    """Канал алертов через Slack webhook"""

    def __init__(self, webhook_url: str | None = None):
        super().__init__("slack")
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)

    async def send_alert(self, alert: AlertMessage) -> bool:
        """Отправить алерт в Slack"""
        if not self.enabled:
            self.logger.warning("Slack webhook не настроен")
            return False

        try:
            # Формируем сообщение для Slack
            color = self._get_color_for_level(alert.level)
            emoji = self._get_emoji_for_level(alert.level)

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"{emoji} {alert.title}",
                        "text": alert.message,
                        "fields": [
                            {"title": "Источник", "value": alert.source, "short": True},
                            {
                                "title": "Время",
                                "value": alert.timestamp.strftime(
                                    "%Y-%m-%d %H:%M:%S UTC"
                                ),
                                "short": True,
                            },
                        ],
                        "footer": "MTF Alert System",
                        "ts": int(alert.timestamp.timestamp()),
                    }
                ]
            }

            # Добавляем метаданные если есть
            if alert.metadata:
                metadata_text = "\n".join(
                    [f"• {k}: {v}" for k, v in alert.metadata.items()]
                )
                payload["attachments"][0]["fields"].append(
                    {"title": "Детали", "value": metadata_text, "short": False}
                )

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response,
            ):
                if response.status == 200:
                    self.logger.info(f"Алерт отправлен в Slack: {alert.title}")
                    return True
                self.logger.error(f"Ошибка отправки в Slack: {response.status}")
                return False

        except Exception as e:
            self.logger.error(f"Ошибка отправки алерта в Slack: {e}")
            return False

    async def test_connection(self) -> bool:
        """Проверить соединение со Slack"""
        if not self.enabled:
            return False

        test_alert = AlertMessage(
            level=AlertLevel.INFO,
            title="Тест соединения",
            message="Проверка работоспособности Slack webhook",
            timestamp=datetime.utcnow(),
            source="MTF Alert System",
        )

        return await self.send_alert(test_alert)

    def _get_color_for_level(self, level: AlertLevel) -> str:
        """Получить цвет для уровня алерта"""
        colors = {
            AlertLevel.INFO: "#36a64f",  # Зеленый
            AlertLevel.WARNING: "#ff9500",  # Оранжевый
            AlertLevel.CRITICAL: "#ff0000",  # Красный
            AlertLevel.ERROR: "#8b0000",  # Темно-красный
        }
        return colors.get(level, "#808080")

    def _get_emoji_for_level(self, level: AlertLevel) -> str:
        """Получить эмодзи для уровня алерта"""
        emojis = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨",
            AlertLevel.ERROR: "💥",
        }
        return emojis.get(level, "📢")


class TelegramAlertChannel(AlertChannel):
    """Канал алертов через Telegram bot"""

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        super().__init__("telegram")
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)

    async def send_alert(self, alert: AlertMessage) -> bool:
        """Отправить алерт в Telegram"""
        if not self.enabled:
            self.logger.warning("Telegram bot не настроен")
            return False

        try:
            # Формируем сообщение для Telegram
            emoji = self._get_emoji_for_level(alert.level)
            level_text = alert.level.value.upper()

            message = f"""
{emoji} *{level_text}*: {alert.title}

{alert.message}

📊 *Источник:* {alert.source}
🕐 *Время:* {alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}
"""

            # Добавляем метаданные если есть
            if alert.metadata:
                message += "\n📋 *Детали:*\n"
                for k, v in alert.metadata.items():
                    message += f"• {k}: {v}\n"

            # Отправляем через Telegram Bot API
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                ) as response,
            ):
                if response.status == 200:
                    self.logger.info(f"Алерт отправлен в Telegram: {alert.title}")
                    return True
                response_text = await response.text()
                self.logger.error(
                    f"Ошибка отправки в Telegram: {response.status} - {response_text}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Ошибка отправки алерта в Telegram: {e}")
            return False

    async def test_connection(self) -> bool:
        """Проверить соединение с Telegram"""
        if not self.enabled:
            return False

        test_alert = AlertMessage(
            level=AlertLevel.INFO,
            title="Тест соединения",
            message="Проверка работоспособности Telegram bot",
            timestamp=datetime.utcnow(),
            source="MTF Alert System",
        )

        return await self.send_alert(test_alert)

    def _get_emoji_for_level(self, level: AlertLevel) -> str:
        """Получить эмодзи для уровня алерта"""
        emojis = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨",
            AlertLevel.ERROR: "💥",
        }
        return emojis.get(level, "📢")


class AlertManager:
    """Менеджер алертов"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.channels: list[AlertChannel] = []
        self.alert_history: list[AlertMessage] = []
        self.max_history = 1000

        # Инициализируем каналы
        self._setup_channels()

    def _setup_channels(self):
        """Настроить каналы алертов"""
        # Логирование (всегда доступно)
        self.channels.append(LoggingAlertChannel())

        # Slack (если настроен)
        slack_channel = SlackAlertChannel()
        if slack_channel.enabled:
            self.channels.append(slack_channel)
            self.logger.info("Slack канал алертов подключен")

        # Telegram (если настроен)
        telegram_channel = TelegramAlertChannel()
        if telegram_channel.enabled:
            self.channels.append(telegram_channel)
            self.logger.info("Telegram канал алертов подключен")

    async def send_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: str = "MTF",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Отправить алерт через все доступные каналы"""
        alert = AlertMessage(
            level=level,
            title=title,
            message=message,
            timestamp=datetime.utcnow(),
            source=source,
            metadata=metadata or {},
        )

        # Добавляем в историю
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history.pop(0)

        # Отправляем через все каналы
        success_count = 0
        for channel in self.channels:
            try:
                if await channel.send_alert(alert):
                    success_count += 1
            except Exception as e:
                self.logger.error(f"Ошибка отправки через канал {channel.name}: {e}")

        self.logger.info(
            f"Алерт отправлен через {success_count}/{len(self.channels)} каналов"
        )
        return success_count > 0

    async def send_info_alert(
        self,
        title: str,
        message: str,
        source: str = "MTF",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Отправить информационный алерт"""
        return await self.send_alert(AlertLevel.INFO, title, message, source, metadata)

    async def send_warning_alert(
        self,
        title: str,
        message: str,
        source: str = "MTF",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Отправить предупреждение"""
        return await self.send_alert(
            AlertLevel.WARNING, title, message, source, metadata
        )

    async def send_critical_alert(
        self,
        title: str,
        message: str,
        source: str = "MTF",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Отправить критический алерт"""
        return await self.send_alert(
            AlertLevel.CRITICAL, title, message, source, metadata
        )

    async def send_error_alert(
        self,
        title: str,
        message: str,
        source: str = "MTF",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Отправить алерт об ошибке"""
        return await self.send_alert(AlertLevel.ERROR, title, message, source, metadata)

    async def test_all_channels(self) -> dict[str, bool]:
        """Протестировать все каналы"""
        results = {}

        for channel in self.channels:
            try:
                results[channel.name] = await channel.test_connection()
                self.logger.info(
                    f"Тест канала {channel.name}: {'OK' if results[channel.name] else 'FAIL'}"
                )
            except Exception as e:
                self.logger.error(f"Ошибка тестирования канала {channel.name}: {e}")
                results[channel.name] = False

        return results

    def get_recent_alerts(
        self, hours: int = 24, level: AlertLevel | None = None
    ) -> list[AlertMessage]:
        """Получить недавние алерты"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        filtered_alerts = [
            alert for alert in self.alert_history if alert.timestamp >= cutoff_time
        ]

        if level:
            filtered_alerts = [
                alert for alert in filtered_alerts if alert.level == level
            ]

        return filtered_alerts

    def get_alert_stats(self, hours: int = 24) -> dict[str, int]:
        """Получить статистику алертов"""
        recent_alerts = self.get_recent_alerts(hours)

        stats = {level.value: 0 for level in AlertLevel}
        for alert in recent_alerts:
            stats[alert.level.value] += 1

        return stats


# Глобальный экземпляр менеджера алертов
alert_manager = AlertManager()
