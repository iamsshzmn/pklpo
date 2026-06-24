# PKLPO Monitoring: инструкция оператора

> **Полная картина стека** (5 слоёв, рабочие сценарии, диаграммы) — в
> [`OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md). Этот README покрывает только метрики и
> дашборды; логи — в [`LOGS_RUNBOOK.md`](LOGS_RUNBOOK.md).

Этот раздел нужен, чтобы быстро понять состояние пайплайна PKLPO без чтения логов на сервере.
Основной рабочий экран - Grafana. Prometheus и Pushgateway нужны для проверки сырых метрик.
Loki используется для поиска логов по `run_id`.

## Что открыть

| Инструмент | Адрес | Логин | Для чего нужен |
|------------|-------|-------|----------------|
| Grafana | http://localhost:3001 | `admin` / `admin` | Основные dashboard, alerts, поиск логов |
| Prometheus | http://localhost:9090 | не нужен | Проверить, что метрика реально собирается |
| Pushgateway | http://localhost:9091 | не нужен | Проверить, что job уже отправил метрики |
| Airflow | http://localhost:8080 | `admin` / `admin` | Посмотреть DAG runs и взять `run_id` |

Если страница не открывается, не начинай менять код. Сначала проверь у ответственного за окружение,
что monitoring и Airflow stack запущены.

## Главный ежедневный сценарий

1. Открой Grafana: http://localhost:3001.
2. Перейди в **Dashboards**.
3. Открой dashboard **PKLPO Pipeline Observability v1**.
4. Проверь верхние панели:
   - pipeline свежий или есть задержка по свечам;
   - есть ли failed/blocked состояния;
   - живы ли зависимости `postgres` и `okx`;
   - есть ли critical/warning alerts.
5. Если видишь проблему, возьми `run_id` из Airflow и проверь логи через Loki.

Нормальный первый вывод: dashboard открывается, панели не пустые, `postgres_up` и `okx_up` равны `1`,
critical alerts отсутствуют.

## Dashboard: что смотреть

### PKLPO Pipeline Observability v1

Это основной dashboard для оператора. Он отвечает на вопросы:

- пайплайн свежий или отстает;
- есть ли дырки в данных;
- сколько задач в очереди recalculation;
- есть ли repair/fill проблемы;
- живы ли внешние зависимости;
- есть ли ошибки синхронизации, записи в БД и feature calculation;
- можно ли перейти от `run_id` к логам.

Dashboard UID: `pklpo-pipeline-obs-v1`.

### PKLPO Data Quality

Это дополнительный dashboard по качеству данных. Смотри его, когда главный dashboard показывает
проблему с freshness, fill rate, hole rate или качеством свечей.

## Как найти логи failed run по `run_id`

1. Открой Airflow: http://localhost:8080.
2. Найди нужный DAG run.
3. Скопируй его `run_id`.
4. Открой Grafana: http://localhost:3001.
5. Перейди в **Explore**.
6. В datasource выбери **Loki**.
7. Вставь запрос:

```logql
{job=~"pklpo_app|pklpo_airflow"} | json | run_id="<RUN_ID>"
```

8. Замени `<RUN_ID>` на настоящий `run_id`.
9. Увеличь time range, если результатов нет. Обычно достаточно последних 15 минут или 1 часа.

### Как перейти от лога к trace

`run_id` остается главным ключом расследования. Сначала найди полную хронологию в
Loki по `run_id`. Если строка лога содержит `trace_id` не равный `"-"`, Grafana
Explore показывает derived link `trace_id` в datasource **Tempo**.

1. Открой строку лога с непустым `trace_id`.
2. Нажми derived link `trace_id`.
3. Grafana откроет Tempo trace для соответствующего Airflow task span.

Если `trace_id` равен `"-"`, эта часть кода выполнялась вне активного span.
Продолжай расследование по `run_id` в Loki.

Если Loki ничего не вернул:

- проверь, что `run_id` скопирован полностью;
- проверь time range в Grafana;
- проверь, что DAG действительно запускался;
- если логи все равно пустые, передай проблему ответственному за observability/runtime.

## Как проверить метрику в Prometheus

Prometheus показывает метрики, которые уже собраны и доступны для запросов.

1. Открой http://localhost:9090.
2. В поле query вставь имя метрики.
3. Нажми **Execute**.

Полезные метрики:

```promql
pklpo_pipeline_candle_lag_seconds
```

```promql
pklpo_pipeline_recalc_queue_rows
```

```promql
pklpo_pipeline_alerts
```

```promql
pklpo_dependency_postgres_up
```

```promql
pklpo_dependency_okx_up
```

```promql
pklpo_swap_sync_db_write_latency_seconds_bucket
```

Если Prometheus ничего не показывает, проверь ту же метрику в Pushgateway.

## Как проверить метрику в Pushgateway

Pushgateway показывает, что приложение уже отправило метрики.

1. Открой http://localhost:9091.
2. Найди нужное имя метрики через поиск в браузере.
3. Если метрика есть в Pushgateway, но ее нет в Prometheus, проблема скорее всего в scrape path.
4. Если метрики нет в Pushgateway, job еще не запускался или не смог отправить метрики.

Минимальный набор, который должен появиться после запуска `pipeline_monitoring`:

- `pklpo_pipeline_candle_lag_seconds`
- `pklpo_pipeline_recalc_queue_rows`
- `pklpo_pipeline_alerts`
- `pklpo_dependency_postgres_up`
- `pklpo_dependency_okx_up`

Метрика `pklpo_swap_sync_db_write_latency_seconds_bucket` появляется после sync run.

## Alerts: как читать

Severity:

- `warning` - проблема уже видна, но система может продолжать работу;
- `critical` - нужен разбор, потому что пайплайн может не производить корректный результат.

Типовые сигналы:

| Alert | Что значит | Первое действие |
|-------|------------|-----------------|
| Freshness lag | Свечи давно не обновлялись | Проверь sync DAG и логи по `run_id` |
| Hole rate high | Есть пропуски в данных | Проверь repair DAG и Data Quality dashboard |
| Recalc queue high | Накопилась очередь пересчета | Проверь feature/recalc DAG runs |
| Postgres down | База недоступна | Не разбирай downstream alerts, сначала база |
| OKX down | OKX API недоступен или не отвечает | Проверь зависимые sync runs |
| Swap sync errors | Ошибки синхронизации свечей | Ищи конкретный `run_id` в Loki |

Если одновременно горит root-cause alert (`postgres_down` или `okx_down`) и много downstream alerts,
сначала разбирается root cause.

## Быстрые проверки при пустом dashboard

### Dashboard открылся, но панели пустые

1. Проверь time range в правом верхнем углу Grafana.
2. Поставь последние 1-6 часов.
3. Проверь, запускался ли `pipeline_monitoring` в Airflow.
4. Проверь нужные метрики в Pushgateway.
5. Если в Pushgateway метрик нет, проблема на стороне job/runtime.

### Логи по `run_id` не находятся

1. Проверь, что в запросе выбран datasource **Loki**.
2. Проверь time range.
3. Проверь точное значение `run_id` в Airflow.
4. Попробуй более широкий запрос:

```logql
{job=~"pklpo_app|pklpo_airflow"} | json
```

Если общий запрос возвращает логи, а запрос по `run_id` нет, проблема в structured log context.

### Метрика есть в Pushgateway, но нет в Prometheus

Это значит, что приложение метрику отправило, но Prometheus ее не видит. Передай это как проблему
scrape/configuration: укажи имя метрики и приложи скрин или текст результата из Pushgateway.

### Метрики нет ни в Pushgateway, ни в Prometheus

Проверь, запускался ли нужный DAG/job. Если запускался, смотри логи по `run_id`.

## Словарь

- `run_id` - главный ключ корреляции. По нему связываются Airflow run, structured logs и расследование инцидента.
- Grafana - UI для dashboard, alerts и поиска логов.
- Prometheus - хранилище и query engine для метрик.
- Pushgateway - буфер, куда batch jobs отправляют метрики.
- Loki - хранилище логов.
- Promtail - агент, который читает JSON logs и отправляет их в Loki.
- Freshness lag - насколько данные отстают от ожидаемого времени.
- Hole rate - доля пропусков в данных.
- RED - rate, errors, duration.
- USE - utilization, saturation, errors.

## Что не делать

- Не менять код, если просто не открывается UI.
- Не закрывать critical alert без проверки `run_id`.
- Не считать пустой dashboard нормой после успешного DAG run.
- Не искать `run_id` в Prometheus labels: `run_id` должен быть в логах, а не в Prometheus labels.
