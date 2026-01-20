# MTF Расширенная система - Быстрый старт

## 🚀 Быстрая установка

### 1. Создание базы данных

```bash
# Создание расширенной MTF архитектуры
python src/db/migrate_create_mtf_expanded.py
```

### 2. Проверка установки

```bash
# Запуск тестов
python test_mtf_expanded.py
```

## 📊 Первый запуск

### Полный pipeline для всех символов

```bash
# Запуск полного MTF pipeline
python src/mtf/cli_expanded.py pipeline
```

### Для конкретного символа

```bash
# Тестирование на BTC-USDT
python src/mtf/cli_expanded.py pipeline --symbol BTC-USDT
```

## 🎯 Просмотр результатов

### Топ кандидаты

```bash
# Лучшие intraday LONG сигналы
python src/mtf/cli_expanded.py candidates --horizon intraday --side long --limit 10

# Лучшие swing сигналы с высоким score
python src/mtf/cli_expanded.py candidates --horizon swing --min-score 0.7 --limit 20
```

### Детали по символу

```bash
# Подробная информация по BTC-USDT
python src/mtf/cli_expanded.py details --symbol BTC-USDT
```

## 🔧 Поэтапная обработка

```bash
# 1. Загрузка контекстных данных
python src/mtf/cli_expanded.py context --symbol BTC-USDT

# 2. Загрузка триггерных данных
python src/mtf/cli_expanded.py triggers --symbol BTC-USDT

# 3. Запись финальных решений
python src/mtf/cli_expanded.py consensus --symbol BTC-USDT --horizons intraday,swing,week
```

## 📈 Примеры SQL запросов

### Самые сильные сигналы

```sql
SELECT symbol, side, score,
       input_data->>'context_score' as context_score,
       input_data->>'bias' as bias
FROM mtf.consensus
WHERE input_data->>'context_score'::numeric >= 0.5
  AND input_data->>'micro_ok' = 'true'
ORDER BY score DESC
LIMIT 20;
```

### Лучшие LONG с высоким ADX

```sql
SELECT c.*, i.adx14
FROM mtf.top_intraday c
LEFT JOIN LATERAL (
    SELECT adx14 FROM indicators i
    WHERE i.symbol = c.symbol AND i.timeframe = '4H'
    ORDER BY i.ts DESC LIMIT 1
) i ON TRUE
WHERE c.side = 1 AND i.adx14 >= 20
ORDER BY c.score DESC;
```

## 🎛️ Настройка параметров

### Пороги валидности (в `context_loader.py`)

```python
VALIDITY_THRESHOLDS = {
    "1M": 0.4,   # Более строгий для месячного
    "1W": 0.35,  # Строгий для недельного
    "1D": 0.3,   # Стандартный для дневного
    "4H": 0.3,   # Стандартный для 4-часового
    "1H": 0.25,  # Менее строгий для часового
    "30m": 0.2   # Самый мягкий для 30-минутного
}
```

### Веса горизонтов (в `consensus_writer.py`)

```python
HORIZON_WEIGHTS = {
    "intraday": {"1D": 0.6, "4H": 0.4},
    "swing": {"1D": 0.5, "4H": 0.3, "1W": 0.2},
    "week": {"1D": 0.4, "1W": 0.3, "1M": 0.3}
}
```

## 🔍 Мониторинг

### Проверка структуры БД

```bash
python -c "
import asyncio
from src.database import get_async_session
from sqlalchemy import text

async def check():
    async for session in get_async_session():
        result = await session.execute(text('SELECT table_name FROM information_schema.tables WHERE table_schema = \'mtf\''))
        tables = [row[0] for row in result.fetchall()]
        print('MTF таблицы:', tables)
        break

asyncio.run(check())
"
```

### Проверка данных

```bash
python -c "
import asyncio
from src.database import get_async_session
from sqlalchemy import text

async def check():
    async for session in get_async_session():
        result = await session.execute(text('SELECT COUNT(*) FROM mtf.consensus'))
        count = result.scalar()
        print(f'Consensus записей: {count}')
        break

asyncio.run(check())
"
```

## 🚨 Troubleshooting

### Нет данных индикаторов

```bash
# Проверьте наличие данных
python -c "
import asyncio
from src.database import get_async_session
from sqlalchemy import text

async def check():
    async for session in get_async_session():
        result = await session.execute(text('SELECT COUNT(*) FROM indicators WHERE timeframe = \'1D\''))
        count = result.scalar()
        print(f'1D индикаторы: {count}')
        break

asyncio.run(check())
"
```

### Ошибки миграции

```bash
# Проверьте схему mtf
python -c "
import asyncio
from src.database import get_async_session
from sqlalchemy import text

async def check():
    async for session in get_async_session():
        result = await session.execute(text('SELECT table_name FROM information_schema.tables WHERE table_schema = \'mtf\''))
        tables = [row[0] for row in result.fetchall()]
        print('MTF таблицы:', tables)
        break

asyncio.run(check())
"
```

## 📚 Дополнительная документация

- [README.md](README.md) - Основная документация MTF модуля
- [README_EXPANDED.md](README_EXPANDED.md) - Подробная документация расширенной системы
- [INTEGRATION_README.md](INTEGRATION_README.md) - Документация по интеграции

## 🎯 Следующие шаги

1. **Настройте параметры** под ваши требования
2. **Запустите полный pipeline** для всех символов
3. **Анализируйте результаты** через CLI команды
4. **Интегрируйте** с существующими системами
5. **Мониторьте производительность** и качество сигналов
