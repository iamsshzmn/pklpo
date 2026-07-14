"""
Notification client for sending alerts and notifications
"""

import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiohttp

from ..logging_config import create_log_context, get_integration_logger
from .models import NotificationType

logger = get_integration_logger()


class NotificationClient:
    """Клиент для отправки уведомлений"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.session: aiohttp.ClientSession | None = None

        logger.info("NotificationClient initialized")

    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход"""
        if self.session:
            await self.session.close()

    async def send_slack_notification(
        self, message: str, webhook_url: str | None = None
    ) -> bool:
        """Отправка уведомления в Slack"""
        with create_log_context("notification_client", "send_slack_notification"):
            try:
                webhook_url = webhook_url or self.config.get("slack_webhook_url")
                if not webhook_url:
                    logger.warning("Slack webhook URL not configured")
                    return False

                payload = {
                    "text": message,
                    "username": "MTF Bot",
                    "icon_emoji": ":robot_face:",
                    "timestamp": int(datetime.now().timestamp()),
                }

                async with self.session.post(
                    webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info("Slack notification sent successfully")
                        return True
                    logger.error(f"Slack notification failed: {response.status}")
                    return False

            except Exception as e:
                logger.error(f"Failed to send Slack notification: {e}")
                return False

    async def send_email_notification(
        self, subject: str, message: str, to_emails: list[str] | None = None
    ) -> bool:
        """Отправка email уведомления"""
        with create_log_context("notification_client", "send_email_notification"):
            try:
                smtp_server = self.config.get("email_smtp_server")
                smtp_port = self.config.get("email_smtp_port", 587)
                username = self.config.get("email_username")
                password = self.config.get("email_password")
                from_email = self.config.get("email_from")
                to_emails = to_emails or self.config.get("email_to", [])

                if not all([smtp_server, username, password, from_email, to_emails]):
                    logger.warning("Email configuration incomplete")
                    return False

                # Создание сообщения
                msg = MIMEMultipart()
                msg["From"] = from_email
                msg["To"] = ", ".join(to_emails)
                msg["Subject"] = subject

                msg.attach(MIMEText(message, "plain", "utf-8"))

                # Отправка email
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(username, password)

                text = msg.as_string()
                server.sendmail(from_email, to_emails, text)
                server.quit()

                logger.info(f"Email notification sent to {len(to_emails)} recipients")
                return True

            except Exception as e:
                logger.error(f"Failed to send email notification: {e}")
                return False

    async def send_webhook_notification(
        self, url: str, payload: dict[str, Any]
    ) -> bool:
        """Отправка webhook уведомления"""
        with create_log_context("notification_client", "send_webhook_notification"):
            try:
                async with self.session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status in [200, 201, 202]:
                        logger.info("Webhook notification sent successfully")
                        return True
                    logger.error(f"Webhook notification failed: {response.status}")
                    return False

            except Exception as e:
                logger.error(f"Failed to send webhook notification: {e}")
                return False

    async def send_notification(
        self, notification_type: NotificationType, **kwargs
    ) -> bool:
        """Универсальный метод для отправки уведомлений"""
        with create_log_context("notification_client", "send_notification"):
            try:
                if notification_type == NotificationType.SLACK:
                    return await self.send_slack_notification(**kwargs)
                if notification_type == NotificationType.EMAIL:
                    return await self.send_email_notification(**kwargs)
                if notification_type == NotificationType.WEBHOOK:
                    return await self.send_webhook_notification(**kwargs)
                if notification_type == NotificationType.LOG:
                    logger.info(
                        f"Log notification: {kwargs.get('message', 'No message')}"
                    )
                    return True
                logger.warning(f"Unsupported notification type: {notification_type}")
                return False

            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
                return False

    async def send_pipeline_completion_notification(
        self, result: dict[str, Any]
    ) -> bool:
        """Отправка уведомления о завершении pipeline"""
        with create_log_context(
            "notification_client", "send_pipeline_completion_notification"
        ):
            try:
                symbol = result.get("symbol", "Unknown")
                status = result.get("status", "Unknown")
                processing_time = result.get("processing_time_seconds", 0)

                # Формирование сообщения
                if status == "completed":
                    emoji = "✅"
                    status_text = "завершен успешно"
                elif status == "failed":
                    emoji = "❌"
                    status_text = "завершен с ошибкой"
                else:
                    emoji = "⚠️"
                    status_text = f"завершен со статусом {status}"

                message = f"""
{emoji} Pipeline для {symbol} {status_text}

📊 Детали:
• Символ: {symbol}
• Статус: {status}
• Время обработки: {processing_time:.2f}s
• Таймфреймы: {", ".join(result.get("timeframes", []))}

🕐 Время: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                """.strip()

                # Отправка в Slack
                slack_success = await self.send_slack_notification(message)

                # Отправка email
                email_success = await self.send_email_notification(
                    subject=f"MTF Pipeline {status_text} - {symbol}", message=message
                )

                return slack_success or email_success

            except Exception as e:
                logger.error(f"Failed to send pipeline completion notification: {e}")
                return False

    async def send_error_notification(
        self, error: str, context: dict[str, Any]
    ) -> bool:
        """Отправка уведомления об ошибке"""
        with create_log_context("notification_client", "send_error_notification"):
            try:
                symbol = context.get("symbol", "Unknown")

                message = f"""
🚨 Ошибка в MTF системе

❌ Ошибка: {error}

📊 Контекст:
• Символ: {symbol}
• Время: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
• Дополнительно: {json.dumps(context, ensure_ascii=False, indent=2)}
                """.strip()

                # Отправка в Slack
                slack_success = await self.send_slack_notification(message)

                # Отправка email
                email_success = await self.send_email_notification(
                    subject=f"MTF Error - {symbol}", message=message
                )

                return slack_success or email_success

            except Exception as e:
                logger.error(f"Failed to send error notification: {e}")
                return False

    async def send_metrics_notification(self, metrics: dict[str, Any]) -> bool:
        """Отправка уведомления с метриками"""
        with create_log_context("notification_client", "send_metrics_notification"):
            try:
                # Формирование сообщения с метриками
                message = f"""
📈 MTF Метрики

📊 Производительность:
• Всего запросов: {metrics.get("total_requests", 0)}
• Успешных: {metrics.get("successful_requests", 0)}
• Неудачных: {metrics.get("failed_requests", 0)}
• Процент успеха: {metrics.get("success_rate", 0):.1%}

⏱️ Время:
• Среднее время обработки: {metrics.get("avg_processing_time", 0):.2f}s
• Минимальное время: {metrics.get("min_processing_time", 0):.2f}s
• Максимальное время: {metrics.get("max_processing_time", 0):.2f}s

🕐 Время: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                """.strip()

                # Отправка в Slack
                slack_success = await self.send_slack_notification(message)

                # Отправка email
                email_success = await self.send_email_notification(
                    subject="MTF Metrics Report", message=message
                )

                return slack_success or email_success

            except Exception as e:
                logger.error(f"Failed to send metrics notification: {e}")
                return False

    async def health_check(self) -> dict[str, Any]:
        """Проверка здоровья системы уведомлений"""
        try:
            # Проверка конфигурации
            slack_configured = bool(self.config.get("slack_webhook_url"))
            email_configured = bool(self.config.get("email_smtp_server"))

            return {
                "status": "healthy",
                "slack_configured": slack_configured,
                "email_configured": email_configured,
                "notifications_available": slack_configured or email_configured,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "notifications_available": False,
            }
