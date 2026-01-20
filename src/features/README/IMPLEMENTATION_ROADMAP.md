# Implementation Roadmap - Рекомендации из Аудита

**Базовый документ:** [RECOMMENDATIONS_AUDIT.md](RECOMMENDATIONS_AUDIT.md)  
**Дата создания:** 27 октября 2025  
**Статус:** 🟢 В работе  

---

## 📋 Обзор задач

| Приоритет | Задач | Готово | В работе | Осталось |
|-----------|-------|--------|----------|----------|
| 🔴 Высокий | 3 | 0 | 0 | 3 |
| 🟡 Средний | 3 | 0 | 0 | 3 |
| 🟢 Низкий | 3 | 0 | 0 | 3 |
| **ИТОГО** | **9** | **0** | **0** | **9** |

---

## 🔴 Высокий приоритет (Критично для Production)

### Task 1: Версионность данных для ML

**ID:** `FEAT-001`  
**Приоритет:** 🔴 Critical  
**Оценка:** 3 дня  
**Статус:** ⏳ TODO  

**Описание:**
Добавить версионирование алгоритмов расчёта индикаторов для обеспечения воспроизводимости ML-моделей.

**Технические требования:**
1. Добавить поле `algorithm_version` в таблицу `indicators`
2. Создать таблицу `calculation_metadata` для хранения конфигурации
3. Добавить `snapshot_id` для группировки расчётов
4. Обновить модель `Indicator` в `src/models.py`
5. Реализовать версионирование в `src/features/versioning.py`

**Acceptance Criteria:**
- [ ] Миграция БД выполнена успешно
- [ ] Каждая запись в `indicators` имеет `algorithm_version`
- [ ] Метаданные расчёта сохраняются в `calculation_metadata`
- [ ] Можно воспроизвести расчёт по `snapshot_id`
- [ ] Тесты покрывают версионирование

**Файлы для изменения:**
```
src/models.py                         # Добавить поля
src/features/versioning.py            # Расширить функциональность
src/features/save.py                  # Сохранять version
src/database/migrations/              # Создать миграцию
src/features/tests/test_versioning.py # Расширить тесты
```

**SQL Migration:**
```sql
-- Add version fields to indicators table
ALTER TABLE indicators
  ADD COLUMN algorithm_version VARCHAR(20) DEFAULT '1.0.0',
  ADD COLUMN snapshot_id VARCHAR(50),
  ADD COLUMN calculation_config JSONB;

-- Create metadata table
CREATE TABLE IF NOT EXISTS calculation_metadata (
  snapshot_id VARCHAR(50) PRIMARY KEY,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  algorithm_version VARCHAR(20) NOT NULL,
  config JSONB NOT NULL,
  symbols TEXT[],
  timeframes TEXT[],
  status VARCHAR(20) DEFAULT 'completed'
);

CREATE INDEX idx_calc_metadata_created ON calculation_metadata(created_at);
```

**Пример кода:**
```python
# src/features/versioning.py (расширить)
from datetime import datetime
import uuid

def create_snapshot(config: dict, symbols: list, timeframes: list) -> str:
    """Create new calculation snapshot."""
    snapshot_id = f"snap_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    # Store metadata
    metadata = {
        'snapshot_id': snapshot_id,
        'algorithm_version': __version__,
        'config': config,
        'symbols': symbols,
        'timeframes': timeframes,
        'status': 'in_progress'
    }

    # Save to database
    # ...

    return snapshot_id
```

---

### Task 2: Алерты в Airflow

**ID:** `FEAT-002`  
**Приоритет:** 🔴 Critical  
**Оценка:** 2 дня  
**Статус:** ⏳ TODO  

**Описание:**
Настроить систему алертов в Airflow для мониторинга сбоев и превышения SLA.

**Технические требования:**
1. Добавить `email_on_failure=True` в DAG
2. Настроить SMTP в Airflow
3. Добавить SLA мониторинг для задач
4. Интегрировать Slack webhook для уведомлений
5. Создать custom callback для критичных ошибок

**Acceptance Criteria:**
- [ ] Email отправляется при сбое задачи
- [ ] SLA alerts настроены (1 час для расчёта)
- [ ] Slack получает уведомления о критичных ошибках
- [ ] Тестовые алерты работают корректно
- [ ] Документация обновлена

**Файлы для изменения:**
```
ops/airflow/dags/features_calc.py     # Добавить alerting
ops/airflow/config/airflow.cfg        # SMTP настройки
src/features/infrastructure/alerts.py # NEW: Alerting module
```

**Пример кода:**
```python
# ops/airflow/dags/features_calc.py
from airflow.operators.slack import SlackWebhookOperator

def failure_callback(context):
    """Custom failure callback for critical alerts."""
    slack_webhook = SlackWebhookOperator(
        task_id='slack_alert',
        http_conn_id='slack_webhook',
        message=f"""
        🚨 *Features Calculation Failed*

        *DAG*: {context['dag'].dag_id}
        *Task*: {context['task'].task_id}
        *Execution Time*: {context['execution_date']}
        *Log URL*: {context['task_instance'].log_url}

        Error: {context.get('exception', 'Unknown')}
        """,
        channel='#data-pipeline-alerts'
    )
    return slack_webhook.execute(context=context)

with DAG(
    dag_id="features_calc",
    default_args={
        "owner": "features_calc",
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "email_on_failure": True,
        "email_on_retry": False,
        "email": ["data-team@company.com"],
        "sla": timedelta(hours=1),
        "on_failure_callback": failure_callback,
    },
    # ... rest of config
) as dag:
    # ... tasks
```

---

### Task 3: JSON-логи для machine parsing

**ID:** `FEAT-003`  
**Приоритет:** 🔴 Critical  
**Оценка:** 2 дня  
**Статус:** ⏳ TODO  

**Описание:**
Переключить логирование на структурированный JSON формат для интеграции с ELK/Splunk.

**Технические требования:**
1. Использовать `python-json-logger` или `structlog`
2. Добавить JSON formatter в `logging_config.py`
3. Включить structured fields: timestamp, level, module, context, trace_id
4. Сохранить обратную совместимость (env var для переключения)
5. Обновить все логгеры модуля

**Acceptance Criteria:**
- [ ] Логи выводятся в JSON при `LOG_FORMAT=json`
- [ ] Все необходимые поля присутствуют
- [ ] Производительность не деградировала
- [ ] ELK может парсить логи
- [ ] Документация обновлена

**Файлы для изменения:**
```
src/features/logging_config.py         # JSON formatter
requirements.txt                       # Add python-json-logger
pyproject.toml                         # Add dependency
src/features/tests/test_logging_config.py # Тесты JSON логов
```

**Пример кода:**
```python
# src/features/logging_config.py
import os
import logging
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with extra fields."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record['timestamp'] = record.created
        log_record['level'] = record.levelname
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno

        # Add custom context
        if hasattr(record, 'symbol'):
            log_record['symbol'] = record.symbol
        if hasattr(record, 'timeframe'):
            log_record['timeframe'] = record.timeframe
        if hasattr(record, 'operation_id'):
            log_record['operation_id'] = record.operation_id

def setup_features_logging(level: str = "INFO", format: str = None):
    """Setup logging with optional JSON format."""

    log_format = format or os.getenv('LOG_FORMAT', 'text')

    logger = logging.getLogger('features')
    logger.setLevel(getattr(logging, level.upper()))

    handler = logging.StreamHandler()

    if log_format == 'json':
        # JSON format for production
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(module)s %(message)s'
        )
    else:
        # Text format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

    return logger

# Usage
logger = setup_features_logging(format='json')
logger.info("Feature calculation started", extra={
    'symbol': 'BTC-USDT-SWAP',
    'timeframe': '1H',
    'operation_id': 'calc_20251027_123456'
})

# Output:
# {"timestamp": 1698419656.123, "level": "INFO", "module": "core",
#  "message": "Feature calculation started", "symbol": "BTC-USDT-SWAP",
#  "timeframe": "1H", "operation_id": "calc_20251027_123456"}
```

---

## 🟡 Средний приоритет (Улучшит Production)

### Task 4: Prometheus метрики

**ID:** `FEAT-004`  
**Приоритет:** 🟡 High  
**Оценка:** 3 дня  
**Статус:** ⏳ TODO  

**Описание:**
Интегрировать экспорт метрик в Prometheus и создать Grafana дашборды.

**Технические требования:**
1. Установить `prometheus-client`
2. Создать metrics exporter в `infrastructure/monitoring.py`
3. Экспортировать ключевые метрики:
   - Время расчёта индикаторов (histogram)
   - Количество обработанных строк (counter)
   - Fill rate по группам (gauge)
   - Ошибки расчёта (counter)
4. Настроить Prometheus scraping
5. Создать Grafana dashboard

**Acceptance Criteria:**
- [ ] Метрики экспортируются в Prometheus
- [ ] Prometheus успешно скрапит endpoint
- [ ] Grafana dashboard показывает метрики
- [ ] Алерты настроены в Prometheus
- [ ] Документация обновлена

**Файлы для создания:**
```
src/features/infrastructure/monitoring.py  # NEW: Prometheus exporter
ops/monitoring/prometheus.yml              # NEW: Prometheus config
ops/monitoring/grafana/features_dashboard.json # NEW: Dashboard
requirements.txt                           # Add prometheus-client
```

**Пример кода:**
```python
# src/features/infrastructure/monitoring.py
from prometheus_client import Counter, Histogram, Gauge, push_to_gateway
import time

# Metrics definitions
CALCULATION_DURATION = Histogram(
    'features_calculation_duration_seconds',
    'Time spent calculating features',
    ['symbol', 'timeframe', 'group']
)

ROWS_PROCESSED = Counter(
    'features_rows_processed_total',
    'Total number of rows processed',
    ['symbol', 'timeframe']
)

FILL_RATE = Gauge(
    'features_fill_rate',
    'Fill rate of features',
    ['group']
)

CALCULATION_ERRORS = Counter(
    'features_calculation_errors_total',
    'Total number of calculation errors',
    ['error_type', 'indicator']
)

class MetricsExporter:
    """Export features metrics to Prometheus."""

    def __init__(self, pushgateway_url: str = None):
        self.pushgateway_url = pushgateway_url or 'localhost:9091'

    def record_calculation(self, symbol: str, timeframe: str,
                          group: str, duration: float):
        """Record calculation duration."""
        CALCULATION_DURATION.labels(
            symbol=symbol,
            timeframe=timeframe,
            group=group
        ).observe(duration)

    def record_rows_processed(self, symbol: str, timeframe: str, count: int):
        """Record number of rows processed."""
        ROWS_PROCESSED.labels(
            symbol=symbol,
            timeframe=timeframe
        ).inc(count)

    def update_fill_rate(self, group: str, fill_rate: float):
        """Update fill rate gauge."""
        FILL_RATE.labels(group=group).set(fill_rate)

    def record_error(self, error_type: str, indicator: str):
        """Record calculation error."""
        CALCULATION_ERRORS.labels(
            error_type=error_type,
            indicator=indicator
        ).inc()

    def push_metrics(self):
        """Push metrics to Pushgateway."""
        push_to_gateway(
            self.pushgateway_url,
            job='features_calculation',
            registry=None
        )

# Usage in core.py
metrics_exporter = MetricsExporter()

start = time.time()
# ... calculation ...
duration = time.time() - start

metrics_exporter.record_calculation('BTC-USDT-SWAP', '1H', 'ma', duration)
metrics_exporter.record_rows_processed('BTC-USDT-SWAP', '1H', len(df))
metrics_exporter.push_metrics()
```

---

### Task 5: Parquet экспорт для ML

**ID:** `FEAT-005`  
**Приоритет:** 🟡 High  
**Оценка:** 2 дня  
**Статус:** ⏳ TODO  

**Описание:**
Реализовать CLI команду для экспорта индикаторов в Parquet формат для ML-пайплайнов.

**Технические требования:**
1. Добавить команду `export-parquet` в CLI
2. Поддержка фильтрации по symbol, timeframe, date range
3. Партиционирование по symbol и date
4. Compression (snappy)
5. Metadata в Parquet файлах

**Acceptance Criteria:**
- [ ] CLI команда `features export-parquet` работает
- [ ] Экспорт партиционирован по symbol/date
- [ ] Compression включен (snappy)
- [ ] Metadata сохраняется
- [ ] Документация с примерами

**Файлы для изменения:**
```
src/features/cli.py                    # Добавить команду
src/features/export.py                 # NEW: Export module
src/features/tests/test_export.py     # NEW: Tests
requirements.txt                       # Add pyarrow/fastparquet
```

**Пример кода:**
```python
# src/features/export.py
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Optional

class ParquetExporter:
    """Export features to Parquet format."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def export(
        self,
        session,
        symbols: list[str],
        timeframes: list[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        partition_by: str = 'symbol'
    ) -> dict:
        """Export indicators to Parquet."""

        results = {
            'files_created': [],
            'rows_exported': 0
        }

        for symbol in symbols:
            for timeframe in timeframes:
                # Fetch data from database
                df = await self._fetch_indicators(
                    session, symbol, timeframe, start_date, end_date
                )

                if df.empty:
                    continue

                # Add metadata
                metadata = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'export_date': pd.Timestamp.now().isoformat(),
                    'row_count': len(df),
                    'algorithm_version': df['algorithm_version'].iloc[0]
                }

                # Create output path
                output_path = self._get_output_path(
                    symbol, timeframe, partition_by
                )

                # Write Parquet with metadata
                table = pa.Table.from_pandas(df)
                table = table.replace_schema_metadata({
                    **metadata,
                    **table.schema.metadata
                })

                pq.write_table(
                    table,
                    output_path,
                    compression='snappy',
                    row_group_size=10000
                )

                results['files_created'].append(str(output_path))
                results['rows_exported'] += len(df)

        return results

    def _get_output_path(self, symbol: str, timeframe: str,
                        partition_by: str) -> Path:
        """Get output path with partitioning."""
        if partition_by == 'symbol':
            return self.output_dir / f"symbol={symbol}" / f"{timeframe}.parquet"
        elif partition_by == 'timeframe':
            return self.output_dir / f"timeframe={timeframe}" / f"{symbol}.parquet"
        else:
            return self.output_dir / f"{symbol}_{timeframe}.parquet"

# CLI command
@click.command()
@click.option('--symbols', required=True, help='Comma-separated symbols')
@click.option('--timeframes', required=True, help='Comma-separated timeframes')
@click.option('--output-dir', required=True, help='Output directory')
@click.option('--start-date', help='Start date (YYYY-MM-DD)')
@click.option('--end-date', help='End date (YYYY-MM-DD)')
def export_parquet(symbols, timeframes, output_dir, start_date, end_date):
    """Export features to Parquet format."""
    exporter = ParquetExporter(output_dir)

    symbols_list = [s.strip() for s in symbols.split(',')]
    timeframes_list = [t.strip() for t in timeframes.split(',')]

    async def run():
        async with get_async_session() as session:
            results = await exporter.export(
                session, symbols_list, timeframes_list,
                start_date, end_date
            )
            click.echo(f"✅ Exported {results['rows_exported']} rows")
            click.echo(f"📁 Files: {len(results['files_created'])}")

    asyncio.run(run())
```

---

### Task 6: Circuit Breaker для БД

**ID:** `FEAT-006`  
**Приоритет:** 🟡 High  
**Оценка:** 2 дня  
**Статус:** ⏳ TODO  

**Описание:**
Реализовать Circuit Breaker pattern для защиты от каскадных сбоев БД.

**Технические требования:**
1. Использовать `pybreaker` библиотеку
2. Настроить threshold (5 ошибок за 60 секунд)
3. Half-open state с пробными запросами
4. Fallback strategy (cache, degraded mode)
5. Метрики circuit breaker состояния

**Acceptance Criteria:**
- [ ] Circuit breaker защищает БД операции
- [ ] Fallback strategy работает
- [ ] Метрики состояния логируются
- [ ] Тесты покрывают все состояния
- [ ] Документация обновлена

**Файлы для создания:**
```
src/features/infrastructure/circuit_breaker.py # NEW
requirements.txt                               # Add pybreaker
src/features/tests/test_circuit_breaker.py    # NEW
```

**Пример кода:**
```python
# src/features/infrastructure/circuit_breaker.py
from pybreaker import CircuitBreaker, CircuitBreakerError
import logging

logger = logging.getLogger(__name__)

# Configure circuit breaker
db_breaker = CircuitBreaker(
    fail_max=5,                  # Open after 5 failures
    timeout_duration=60,         # Try again after 60 seconds
    exclude=[ValueError],        # Don't count certain exceptions
    listeners=[                  # Event listeners
        lambda state: logger.warning(f"Circuit breaker state changed: {state}")
    ]
)

class DatabaseCircuitBreaker:
    """Circuit breaker wrapper for database operations."""

    def __init__(self, breaker: CircuitBreaker = db_breaker):
        self.breaker = breaker
        self.fallback_cache = {}

    @db_breaker
    async def execute_with_breaker(self, operation, *args, **kwargs):
        """Execute database operation with circuit breaker."""
        try:
            return await operation(*args, **kwargs)
        except CircuitBreakerError:
            logger.error("Circuit breaker is OPEN - using fallback")
            return self._fallback_strategy(*args, **kwargs)
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            raise

    def _fallback_strategy(self, *args, **kwargs):
        """Fallback when circuit is open."""
        # Return cached data if available
        cache_key = str(args) + str(kwargs)
        if cache_key in self.fallback_cache:
            logger.info("Returning cached data")
            return self.fallback_cache[cache_key]

        # Or return degraded response
        logger.warning("No cache available - degraded mode")
        return None

    def cache_result(self, key: str, value):
        """Cache successful result."""
        self.fallback_cache[key] = value

# Usage
breaker = DatabaseCircuitBreaker()

async def fetch_indicators_safe(session, symbol, timeframe):
    """Fetch indicators with circuit breaker protection."""
    return await breaker.execute_with_breaker(
        fetch_indicators,
        session, symbol, timeframe
    )
```

---

## 🟢 Низкий приоритет (Nice to Have)

### Task 7-9: OpenTelemetry, TimescaleDB, Property-based тесты

*Детали будут добавлены после завершения задач высокого приоритета.*

---

## 📊 Прогресс трекинг

### Sprint 1 (Неделя 1-2): Критичные задачи

- [ ] **FEAT-001**: Версионность данных (3 дня)
- [ ] **FEAT-002**: Алерты Airflow (2 дня)
- [ ] **FEAT-003**: JSON логи (2 дня)

**Target:** Завершить все критичные задачи

### Sprint 2 (Неделя 3-4): Улучшения

- [ ] **FEAT-004**: Prometheus метрики (3 дня)
- [ ] **FEAT-005**: Parquet экспорт (2 дня)
- [ ] **FEAT-006**: Circuit breaker (2 дня)

**Target:** Готовность к production deployment

### Sprint 3 (Неделя 5+): Nice-to-have

- [ ] **FEAT-007**: OpenTelemetry tracing
- [ ] **FEAT-008**: TimescaleDB оптимизации
- [ ] **FEAT-009**: Property-based тесты

---

## 🔄 Процесс реализации

### Для каждой задачи:

1. **Планирование** (0.5 дня)
   - Детальный технический дизайн
   - Review с командой
   - Оценка рисков

2. **Разработка** (указано в оценке)
   - Реализация функциональности
   - Unit тесты
   - Integration тесты

3. **Тестирование** (0.5 дня)
   - Smoke tests
   - Performance testing
   - Security review

4. **Документация** (включено в оценку)
   - Update README
   - API documentation
   - Migration guide

5. **Deploy** (0.5 дня)
   - Staging deployment
   - Production deployment
   - Monitoring setup

---

## 📝 Заметки

- Все изменения должны проходить code review
- Обязательное покрытие тестами (>80%)
- Backward compatibility для всех изменений API
- Feature flags для постепенного rollout

---

**Следующий шаг:** Начать с FEAT-001 (Версионность данных)
