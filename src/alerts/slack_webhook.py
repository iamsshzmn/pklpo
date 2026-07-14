"""
Slack уведомления для системы сигналов.
"""

import os
from dataclasses import dataclass
from datetime import datetime

import requests


@dataclass
class AlertConfig:
    """Конфигурация алертов."""

    webhook_url: str
    channel: str = "#trading-signals"
    username: str = "Trading Bot"
    icon_emoji: str = ":robot_face:"

    # Пороги для алертов
    max_buy_signals_per_day: int = 50
    max_sell_signals_per_day: int = 50
    min_sharpe_ratio: float = 1.0
    max_drawdown_threshold: float = 15.0


class SlackNotifier:
    """
    Отправка уведомлений в Slack.
    """

    def __init__(self, config: AlertConfig):
        """
        Инициализация Slack уведомлений.

        Args:
            config: Конфигурация алертов
        """
        self.config = config
        self.session = requests.Session()

    def send_message(self, text: str, attachments: list[dict] | None = None) -> bool:
        """
        Отправляет сообщение в Slack.

        Args:
            text: Текст сообщения
            attachments: Вложения (опционально)

        Returns:
            bool: Успешность отправки
        """
        payload = {
            "channel": self.config.channel,
            "username": self.config.username,
            "icon_emoji": self.config.icon_emoji,
            "text": text,
        }

        if attachments:
            payload["attachments"] = attachments

        try:
            response = self.session.post(
                self.config.webhook_url, json=payload, timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки в Slack: {e}")
            return False

    def send_signal_alert(
        self, symbol: str, signal: int, score: float, reason: str, timeframe: str = "1m"
    ) -> bool:
        """
        Отправляет алерт о торговом сигнале.

        Args:
            symbol: Торговый символ
            signal: Сигнал (-1, 0, 1)
            score: Взвешенный score
            reason: Причина сигнала
            timeframe: Таймфрейм

        Returns:
            bool: Успешность отправки
        """
        signal_type = (
            "🟢 BUY" if signal == 1 else "🔴 SELL" if signal == -1 else "🟡 HOLD"
        )
        color = "good" if signal == 1 else "danger" if signal == -1 else "warning"

        attachment = {
            "color": color,
            "title": f"Trading Signal: {symbol}",
            "fields": [
                {"title": "Signal", "value": signal_type, "short": True},
                {"title": "Timeframe", "value": timeframe, "short": True},
                {"title": "Score", "value": f"{score:.2f}", "short": True},
                {
                    "title": "Time",
                    "value": datetime.now().strftime("%H:%M:%S"),
                    "short": True,
                },
                {
                    "title": "Reason",
                    "value": reason[:200] + "..." if len(reason) > 200 else reason,
                    "short": False,
                },
            ],
            "footer": "Trading Bot",
            "ts": int(datetime.now().timestamp()),
        }

        text = f"🚨 {signal_type} signal for {symbol} ({timeframe})"

        return self.send_message(text, [attachment])

    def send_daily_summary(self, stats: dict) -> bool:
        """
        Отправляет ежедневную сводку.

        Args:
            stats: Статистика за день

        Returns:
            bool: Успешность отправки
        """
        total_signals = stats.get("total_signals", 0)
        buy_signals = stats.get("buy_signals", 0)
        sell_signals = stats.get("sell_signals", 0)
        hold_signals = stats.get("hold_signals", 0)
        avg_score = stats.get("avg_score", 0.0)

        # Проверяем пороги для алертов
        alerts = []

        if buy_signals > self.config.max_buy_signals_per_day:
            alerts.append(f"⚠️ Too many BUY signals: {buy_signals}")

        if sell_signals > self.config.max_sell_signals_per_day:
            alerts.append(f"⚠️ Too many SELL signals: {sell_signals}")

        # Формируем сообщение
        text = f"📊 Daily Trading Summary - {datetime.now().strftime('%Y-%m-%d')}"

        attachment = {
            "color": "good" if not alerts else "warning",
            "title": "Signal Statistics",
            "fields": [
                {"title": "Total Signals", "value": str(total_signals), "short": True},
                {"title": "Buy Signals", "value": str(buy_signals), "short": True},
                {"title": "Sell Signals", "value": str(sell_signals), "short": True},
                {"title": "Hold Signals", "value": str(hold_signals), "short": True},
                {"title": "Average Score", "value": f"{avg_score:.2f}", "short": True},
                {
                    "title": "Buy/Sell Ratio",
                    "value": (
                        f"{buy_signals / sell_signals:.2f}" if sell_signals > 0 else "∞"
                    ),
                    "short": True,
                },
            ],
            "footer": "Trading Bot",
            "ts": int(datetime.now().timestamp()),
        }

        if alerts:
            attachment["fields"].append(
                {"title": "⚠️ Alerts", "value": "\n".join(alerts), "short": False}
            )

        return self.send_message(text, [attachment])

    def send_performance_alert(self, metrics: dict) -> bool:
        """
        Отправляет алерт о производительности.

        Args:
            metrics: Метрики производительности

        Returns:
            bool: Успешность отправки
        """
        sharpe = metrics.get("sharpe_ratio", 0.0)
        drawdown = metrics.get("max_drawdown", 0.0)
        pnl = metrics.get("total_pnl_percent", 0.0)

        alerts = []
        color = "good"

        if sharpe < self.config.min_sharpe_ratio:
            alerts.append(f"📉 Low Sharpe ratio: {sharpe:.2f}")
            color = "warning"

        if drawdown > self.config.max_drawdown_threshold:
            alerts.append(f"📉 High drawdown: {drawdown:.2f}%")
            color = "danger"

        if not alerts:
            return True  # Не отправляем, если нет алертов

        text = f"⚠️ Performance Alert - {datetime.now().strftime('%H:%M:%S')}"

        attachment = {
            "color": color,
            "title": "Performance Metrics",
            "fields": [
                {"title": "Sharpe Ratio", "value": f"{sharpe:.2f}", "short": True},
                {"title": "Max Drawdown", "value": f"{drawdown:.2f}%", "short": True},
                {"title": "Total PnL", "value": f"{pnl:.2f}%", "short": True},
                {"title": "Alerts", "value": "\n".join(alerts), "short": False},
            ],
            "footer": "Trading Bot",
            "ts": int(datetime.now().timestamp()),
        }

        return self.send_message(text, [attachment])


def create_slack_notifier(webhook_url: str | None = None) -> SlackNotifier | None:
    """
    Создает экземпляр Slack уведомлений.

    Args:
        webhook_url: URL webhook'а Slack (берется из переменной окружения SLACK_WEBHOOK_URL)

    Returns:
        Optional[SlackNotifier]: Экземпляр уведомлений или None
    """
    if webhook_url is None:
        webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url:
        print("⚠️ SLACK_WEBHOOK_URL не настроен, уведомления отключены")
        return None

    config = AlertConfig(webhook_url=webhook_url)
    return SlackNotifier(config)
