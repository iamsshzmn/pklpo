# Как передавать параметры в DAG features_calc

## Способы передачи параметров

### 1. Через UI Airflow (Trigger DAG with config)

В поле "Configuration JSON" можно передать:

#### Вариант A: Все символы (рекомендуется)
```json
{
    "timeframes": "1m,5m,15m,30m,1H,4H,12H,1D,1W,1M"
}
```

Или просто пустой объект (будут использованы дефолты):
```json
{}
```

#### Вариант B: Конкретный символ
```json
{
    "symbols": "BTC-USDT-SWAP",
    "timeframes": "1m,5m,15m",
    "limit": 1000
}
```

#### Вариант C: Несколько символов
```json
{
    "symbols": "BTC-USDT-SWAP,ETH-USDT-SWAP",
    "timeframes": "1m,5m,15m"
}
```

### 2. Через CLI Airflow

```bash
# Все символы, все таймфреймы
airflow dags trigger features_calc

# Конкретный символ
airflow dags trigger features_calc --conf '{"symbols": "BTC-USDT-SWAP", "timeframes": "1m,5m"}'

# С лимитом баров
airflow dags trigger features_calc --conf '{"symbols": "BTC-USDT-SWAP", "timeframes": "1m", "limit": 1000}'
```

### 3. Через API

```bash
curl -X POST http://localhost:8080/api/v1/dags/features_calc/dagRuns \
  -H "Content-Type: application/json" \
  -d '{
    "conf": {
      "symbols": "BTC-USDT-SWAP",
      "timeframes": "1m,5m,15m",
      "limit": 1000
    }
  }'
```

## Важные замечания

### Проблема с `null` в JSON

**НЕ ИСПОЛЬЗУЙТЕ:**
```json
{
    "symbols": null,
    "timeframes": "1m,5m",
    "limit": null
}
```

Airflow/Jinja2 может интерпретировать `null` как строку `"None"`, что приведет к поиску символа с именем "None".

**ПРАВИЛЬНО:**

1. **Для обработки всех символов** - просто не указывайте параметр `symbols`:
```json
{
    "timeframes": "1m,5m,15m"
}
```

2. **Для обработки всех баров** - просто не указывайте параметр `limit`:
```json
{
    "symbols": "BTC-USDT-SWAP",
    "timeframes": "1m"
}
```

### Формат параметров

- **symbols**: строка (один символ) или строка с запятыми (несколько символов)
  - `"BTC-USDT-SWAP"` - один символ
  - `"BTC-USDT-SWAP,ETH-USDT-SWAP"` - несколько символов
  - Не указывать = все символы из БД

- **timeframes**: строка с запятыми или пробелами
  - `"1m,5m,15m"` - через запятую
  - `"1m 5m 15m"` - через пробел (также поддерживается)
  - По умолчанию: `"1m,5m,15m,30m,1H,4H,12H,1D,1W,1M"`

- **limit**: число (целое)
  - `1000` - последние 1000 баров
  - Не указывать = все доступные бары

## Примеры правильных конфигураций

### Пример 1: Все символы, все таймфреймы, все бары
```json
{}
```

### Пример 2: Один символ, несколько таймфреймов, лимит
```json
{
    "symbols": "BTC-USDT-SWAP",
    "timeframes": "1m,5m,15m,1H",
    "limit": 5000
}
```

### Пример 3: Несколько символов, один таймфрейм
```json
{
    "symbols": "BTC-USDT-SWAP,ETH-USDT-SWAP,BNB-USDT-SWAP",
    "timeframes": "1m"
}
```

### Пример 4: Все символы, только дневной таймфрейм
```json
{
    "timeframes": "1D"
}
```

## Проверка параметров в логах

После запуска DAG проверьте логи задачи `features_run`:

1. **Правильная передача (все символы):**
```
📋 Входные параметры:
   - symbols: None
   - timeframes: ['1m', '5m', '15m']
   - limit: None

🔄 Обработка параметров...
   - symbols (None): будут обработаны все символы

📝 Команда для выполнения:
   python -u -m src.cli.main features --timeframes 1m 5m 15m --features-debug
```

2. **Неправильная передача (строка "None"):**
```
📋 Входные параметры:
   - symbols: None
   - timeframes: ['1m', '5m', '15m']
   - limit: None

🔄 Обработка параметров...
   - symbols (строка): 'None' -> 'none'
   - symbols (пустое значение, будут обработаны все символы)

📝 Команда для выполнения:
   python -u -m src.cli.main features --timeframes 1m 5m 15m --features-debug
```

Обратите внимание: в команде НЕ должно быть `--symbols None`!

## Рекомендации

1. **Для production:** не указывайте `symbols` и `limit` - обрабатываются все данные
2. **Для тестирования:** укажите конкретный символ и небольшой `limit`
3. **Для отладки:** используйте один символ и один таймфрейм с лимитом
