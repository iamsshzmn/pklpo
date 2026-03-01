# Market Selection

Модуль выбирает торговый universe (top-N символов) на основе качества данных, метрик пары, глобального режима рынка и multi-timeframe scoring.

## Что делает pipeline

Основной оркестратор: `src/market_selection/application/pipeline.py`.

Шаги выполнения:
1. Определяет `ts_eval` (границу данных).
2. Валидирует `short_feature_set` в таблице `indicators`.
3. Вычисляет глобальный режим (`TREND_UP`, `TREND_DOWN`, `RANGE`, `VOLATILE`).
4. По каждому TF из `selection_tfs` (`5m`, `15m`, `1H`, `4H`):
   - Quality Gate,
   - расчет pair metrics,
   - нормализация и scoring,
   - запись в `market_scores_tf`.
5. Агрегирует final score по TF.
6. Отбирает universe через `UniverseManager` (top-N, buffer/hysteresis, blacklist/whitelist).
7. Публикует версию в `market_universe` / `market_universe_versions`.

Если условия не выполняются, используется fallback на предыдущую published-версию (`fallback_prev`).

## Конфигурация

Конфиг: `src/market_selection/config.py`.

Ключевые секции:
- `regime`: выбор basket, пороги ADX/ATR, stale-пороги по TF режима.
- `quality`: пороги `fill_min`, `gap_max`, `lag_max_min`, warmup.
- `scoring`: веса метрик, regime deltas, MTF-веса, штрафы за missing TF.
- `universe`: `top_n`, `buffer`, soft/hard fallback thresholds, retention.

Для воспроизводимости рассчитывается `config_hash()`.

## CLI

Команда: `pklpo market-selection <action>`

Доступные actions:
- `run [--top-n N] [--dry-run]`
- `status`
- `explain <SYMBOL>`
- `universe [--limit N] [--format table|json|csv]`
- `regime`
- `metrics [--history N] [--format table|json]`
- `migrate`

Файл команд: `src/market_selection/cli/commands.py`.

## Схема данных

Миграции: `src/market_selection/migrations/`.

Основные таблицы:
- `market_scores_tf`: score по `(symbol, timeframe, ts_eval)` + quality/regime metadata.
- `market_universe`: итоговые символы версии universe.
- `market_universe_versions`: статус версии (`building`, `published`, `failed`, `fallback_prev`) и статистика запуска.
- `market_regime_history`: история глобального режима и stale-флаг.

## Fallback и отказоустойчивость

Fallback на предыдущую версию активируется в случаях:
- системный outage старших TF (`1H`/`4H`),
- слишком маленький universe (`< soft/hard threshold`),
- отсутствие final scores.

При fallback копируется предыдущий universe в новую `ts_version`, статус версии = `fallback_prev`.

## Monitoring

Реализация: `src/market_selection/infrastructure/monitoring.py`.

Поддерживаются:
- in-memory история запусков,
- опциональные Prometheus-метрики (если установлен `prometheus_client`),
- summary/history для команды `metrics`.

## Очистка данных

Реализация: `src/market_selection/infrastructure/persistence.py::cleanup_old_data`.

По умолчанию:
- `market_scores_tf`: 180 дней,
- `market_universe`/`market_universe_versions`: 90 дней.

## Быстрый старт

1. Применить миграции:
```bash
pklpo market-selection migrate
```

2. Запустить pipeline:
```bash
pklpo market-selection run --top-n 30
```

3. Проверить результат:
```bash
pklpo market-selection status
pklpo market-selection universe --limit 30
```
