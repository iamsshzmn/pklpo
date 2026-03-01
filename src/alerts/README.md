# Alerts Module

Модуль для системы алертов и уведомлений. Предоставляет инструменты для отправки уведомлений о торговых сигналах, производительности системы и важных событиях через Slack.

## Обзор

Модуль `alerts` предназначен для:
- Отправки уведомлений о торговых сигналах в реальном времени
- Генерации ежедневных сводок по торговой активности
- Мониторинга производительности системы с алертами
- Интеграции с Slack для удобного получения уведомлений

## Структура модуля

### Основные компоненты:

#### 1. Конфигурация алертов (`AlertConfig`)
Dataclass для настройки параметров уведомлений:

```python
@dataclass
class AlertConfig:
    webhook_url: str                    # URL webhook'а Slack
    channel: str = "#trading-signals"   # Канал для уведомлений
    username: str = "Trading Bot"       # Имя бота
    icon_emoji: str = ":robot_face:"    # Эмодзи иконки

    # Пороги для алертов
    max_buy_signals_per_day: int = 50   # Максимум BUY сигналов в день
    max_sell_signals_per_day: int = 50  # Максимум SELL сигналов в день
    min_sharpe_ratio: float = 1.0       # Минимальный Sharpe Ratio
    max_drawdown_threshold: float = 15.0 # Максимальная просадка
```

#### 2. Slack уведомления (`SlackNotifier`)

##### Основные методы:

###### `send_message(text, attachments)`
Отправляет базовое сообщение в Slack.

###### `send_signal_alert(symbol, signal, score, reason, timeframe)`
Отправляет алерт о торговом сигнале:
- 🟢 BUY сигналы (зеленый цвет)
- 🔴 SELL сигналы (красный цвет)
- 🟡 HOLD сигналы (желтый цвет)

###### `send_daily_summary(stats)`
Отправляет ежедневную сводку с статистикой сигналов.

###### `send_performance_alert(metrics)`
Отправляет алерт о производительности системы.

#### 3. Фабрика уведомлений (`create_slack_notifier`)
Создает экземпляр Slack уведомлений из переменной окружения.

## Использование

### Базовое использование:

```python
from src.alerts import create_slack_notifier

# Создание уведомлений
notifier = create_slack_notifier()

if notifier:
    # Отправка сигнала
    notifier.send_signal_alert(
        symbol="BTC-USDT",
        signal=1,
        score=0.85,
        reason="Strong buy signal based on RSI and MACD",
        timeframe="1m"
    )
```

### Настройка конфигурации:

```python
from src.alerts.slack_webhook import SlackNotifier, AlertConfig

config = AlertConfig(
    webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    channel="#my-trading-channel",
    username="My Trading Bot",
    icon_emoji=":chart_with_upwards_trend:",
    max_buy_signals_per_day=30,
    max_sell_signals_per_day=30,
    min_sharpe_ratio=1.5,
    max_drawdown_threshold=10.0
)

notifier = SlackNotifier(config)
```

## Конфигурация

### Переменные окружения:

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### Настройка Slack:

1. Создайте Incoming Webhook в настройках Slack App
2. Выберите канал для уведомлений
3. Скопируйте URL webhook'а
4. Установите переменную окружения

## Форматы уведомлений

### Торговые сигналы:
```
🚨 🟢 BUY signal for BTC-USDT (1m)
Signal: 🟢 BUY
Timeframe: 1m
Score: 0.85
Time: 14:30:25
Reason: Strong buy signal based on RSI oversold condition...
```

### Ежедневная сводка:
```
📊 Daily Trading Summary - 2024-01-15
Total Signals: 150
Buy Signals: 45
Sell Signals: 35
Hold Signals: 70
Average Score: 0.72
Buy/Sell Ratio: 1.29
```

### Алерты производительности:
```
⚠️ Performance Alert - 14:30:25
Sharpe Ratio: 0.85
Max Drawdown: 18.5%
Total PnL: 5.2%
📉 Low Sharpe ratio: 0.85
📉 High drawdown: 18.5%
```

## Интеграция с системой

### Связь с другими модулями:

#### Signals:
```python
from src.alerts import create_slack_notifier

notifier = create_slack_notifier()
if notifier and signal != 0:
    notifier.send_signal_alert(
        symbol=symbol,
        signal=signal,
        score=score,
        reason=reason,
        timeframe=timeframe
    )
```

#### Backtest:
```python
from src.alerts import create_slack_notifier

notifier = create_slack_notifier()
if notifier:
    notifier.send_performance_alert(metrics)
```

## Рекомендации по использованию

### Настройка порогов:
- **Количество сигналов**: 10-50 в день
- **Sharpe Ratio**: минимум 1.0, желательно 1.5+
- **Max Drawdown**: максимум 15%, желательно <10%

### Оптимизация уведомлений:
- Отправляйте только значимые сигналы (score > 0.7)
- Группируйте похожие сигналы
- Используйте разные каналы для разных типов

## Примеры использования

### Интеграция с торговой системой:

```python
import asyncio
from src.alerts import create_slack_notifier

async def trading_system_with_alerts():
    notifier = create_slack_notifier()

    while True:
        # Получаем новые сигналы
        signals = await get_new_signals()

        for signal in signals:
            if signal['signal'] != 0 and notifier:
                notifier.send_signal_alert(
                    symbol=signal['symbol'],
                    signal=signal['signal'],
                    score=signal['score'],
                    reason=signal['reason'],
                    timeframe=signal['timeframe']
                )

        await asyncio.sleep(60)

asyncio.run(trading_system_with_alerts())
```

### Ежедневный отчет:

```python
from src.alerts import create_slack_notifier

async def generate_daily_report():
    notifier = create_slack_notifier()

    if notifier:
        stats = await calculate_daily_stats()
        notifier.send_daily_summary(stats)

asyncio.run(generate_daily_report())
```

## Обработка ошибок

### Проверка подключения:
```python
def test_slack_connection():
    notifier = create_slack_notifier()

    if not notifier:
        print("❌ Slack webhook не настроен")
        return False

    success = notifier.send_message("🧪 Test message")
    return success
```

## Безопасность

### Защита webhook URL:
- Используйте переменные окружения
- Никогда не коммитьте URL в код
- Регулярно ротируйте webhook URL

### Ограничение доступа:
- Используйте отдельный канал для ботов
- Настройте права доступа к каналу
- Мониторьте активность webhook'а
