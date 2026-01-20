## Цели

- Перейти на инкрементальную загрузку OHLCV с водяными метками (watermarks).
- Снизить объём API-вызовов и время выполнения DAG, обеспечить идемпотентность.
- Добавить ремонт «дыр» и надёжную дозагрузку поздних правок биржи.

## Схемы данных

- Основная таблица свечей `swap_ohlcv_p` (уже есть): первичный ключ `(symbol, timeframe, timestamp)`.
- Состояние синка (новая): `sync_state_swap(symbol text, timeframe text, last_synced_ts timestamptz, last_full_repair_ts timestamptz, PRIMARY KEY(symbol, timeframe))`.
- Метаданные рынков: `markets_meta(symbol text PRIMARY KEY, listing_ts timestamptz, delisted_ts timestamptz)`.
- Отдельно для доп.метрик (этап 3):
  - `swap_funding(symbol, timestamp timestamptz, rate numeric, PRIMARY KEY(symbol, timestamp))`
  - `swap_open_interest(symbol, timestamp timestamptz, open_interest numeric, PRIMARY KEY(symbol, timestamp))`
  - `sync_state_swap_extra(kind text, symbol text, last_synced_ts timestamptz, PRIMARY KEY(kind, symbol))`

## Конфигурация инкремента

- OVERLAP (кол-во баров для «скользящего переиздания»):
  - 1m/5m/15m: 50; 30m/1H/4H: 10; 12H/1D: 5; 1W/1M: 2
- SAFETY_LAG (не брать незакрытый бар):
  - 1m–4H: 1; 12H: 1; 1D/1W/1M: 0 (на старте можно 1, затем 0)
- TF в миллисекундах: 1m=60k, 5m=300k, 15m=900k, 30m=1_800k, 1H=3_600k, 4H=14_400k, 12H=43_200k, 1D=86_400k, 1W=604_800k, 1M=calendar

## Водяные метки и границы

- `last_local = MAX(timestamp)` из БД по `(symbol, timeframe)` или `listing_ts` при пустоте.
- `overlap` в барах переводить в миллисекунды по TF.
- `safe_now = floor(now_utc, tf) - safety_lag*tf`.
- `start = max(listing_ts, last_local - overlap)`; `end = safe_now`.

## Логика запроса к API

- Предпочтительно запрашивать по временному диапазону `start/end`; если API только с `before`, то пагинация «назад», пока `min(ts_page) >= start`.
- Последнюю страницу фильтровать локально `row.ts >= start`.
- Нормализовать входящие `ts` к началу бара TF до вставки.

## Upsert и батчи

- Батчевый `INSERT ... ON CONFLICT (symbol,timeframe,timestamp) DO UPDATE ...`.
- Размер батча 1–5k строк, одна транзакция на батч.
- Индекс `btree(symbol, timeframe, timestamp)`; для больших объёмов — партиционирование по RANGE(timestamp by month) и/или LIST(timeframe).

## Контроль и ремонт «дыр» (этап 2)

- После загрузки: быстрый inline-скан последних X дней (1–3 для 1m) на шаг TF; ночная задача — глубокий repair.
- Алгоритм: выбрать `ts` на [start, end], ожидать равномерный шаг TF; пропуски собрать в интервалы и дозапросить диапазонами с тем же upsert.

## Funding и Open Interest (этап 3)

- Вынести из потока свечей: собственные таблицы и `sync_state_swap_extra`.
- Свои overlap: funding — 8 интервалов, OI — 3–8 интервалов.
- Те же правила `safe_now`, нормализация ts, батчевый upsert.

## Расписание и DAG

- Существующий DAG сохраняем, пробрасываем конфигурацию `incremental=True`, `OVERLAP`, `SAFETY_LAG`, `batch_size`.
- Рекомендуемые расписания:
  - 1m/5m/15m: каждые 5 минут
  - 30m/1H/4H: ежечасно
  - 12H/1D: ежедневно 00:10 UTC
  - 1W/1M: ежедневно (обновится только при смене бара)
  - Отдельные задачи: `swap_funding_incremental`, `swap_oi_incremental`, `swap_gaps_repair`

## Надёжность

- Экспоненциальный бэкофф + джиттер, `max_retries=5`.
- Идемпотентность обеспечивается `(symbol,timeframe,timestamp)` и overlap.
- Все сравнения времени — в UTC, точность до миллисекунд.

## Качество данных

- Инварианты: `low <= min(open,close)`, `max(open,close) <= high`, `volume >= 0`.
- Нормализация `ts` к началу интервала TF.
- Не тянуть незакрытый бар (`safety_lag`).

## Мониторинг и метрики

- На задачу/TF/символ: `rows_upserted`, `bars_per_second`, `retry_count`, `rate_limit_hits`, `gap_count`, `lag_sec = end - max_local`.
- Алерты: `lag_sec > 2*tf`, `gap_count > 0` после nightly-repair, рост `rate_limit_hits`.

## Производительность и хранение

- Партиционирование `swap_ohlcv_p` по месяцу (RANGE), опционально LIST(timeframe).
- Автовакуум для «горячих» партиций агрессивнее.
- COPY для бутстрапа, батчевый upsert для инкремента.
- Ограничение конкарренси по символам для соблюдения rate-limit.

## Бутстрап

- Взять `listing_ts` из метаданных; при отсутствии — определить по первой непустой странице.
- Качать до `safe_now` с батчами и upsert; по завершении зафиксировать `last_synced_ts = safe_now`.

## Критерии приёмки

- Повторный запуск инкремента не меняет итог на интервале `[end - 2*overlap, end]`.
- `lag_sec < 2*tf` по каждому TF.
- `gap_count == 0` после nightly-repair.
- Снижение API-вызовов и времени DAG относительно прежнего режима «N последних баров».

## Порядок включения (rollout)

1. Включить инкремент для TF: 1m, 5m, 15m (overlap=50, safety_lag=1).
2. Через сутки — 30m, 1H, 4H (overlap=10, safety_lag=1).
3. Затем — 12H, 1D (на старте safety_lag=1, далее 0).
4. Затем — 1W, 1M и отдельные DAG’и для funding/OI.

## Изменения в коде (минимальные точки внедрения)

- `src/candles/sync_swap_candles.py`:
  - добавить расчёт `safe_now`, `start` из watermark и `overlap`;
  - стоп-условие пагинации по `start` и фильтрация последней страницы;
  - нормализация `ts` к началу бара;
  - батчевый upsert;
  - метрики `lag_sec`, `gap_count` (после этапа 2).
- Миграции: создать `sync_state_swap`, при необходимости `markets_meta` и таблицы extra.
- DAG: проброс конфигурации `OVERLAP`, `SAFETY_LAG`, `incremental`.
