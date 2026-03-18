# Index: src/db

## Module Structure

```
src/db/
├── README.md                    # Основная документация
├── INDEX.md                     # Этот файл
├── DEVELOPER_CHECKLIST.md       # Чек-лист разработчика
├── __init__.py
│
├── Core
├── migration_runner.py          # Движок выполнения миграций (run_all, dry_run, rollback)
├── migration_registry.py        # Упорядоченный реестр миграций (get_migrations)
├── schema_validation.py         # Валидация схемы БД (validate_schema)
├── db_schema_utils.py           # Утилиты для работы со схемой
│
├── Reports & Monitoring
├── migration_reports.py         # Генерация отчётов о миграциях
├── reports_cli.py               # CLI: status, health, stats, report, performance
├── monitoring_cli.py            # CLI: collect, metrics, alerts, locks, refresh, prometheus
│
├── Partition Maintenance
├── indicators_partition/        # Логика обслуживания партиций indicators_p
│   └── __init__.py
│
├── migrations/                  # Все файлы миграций
│   ├── __init__.py
│   │
│   ├── Bootstrap (registry-registered, ordered)
│   ├── migrate_create_schema_migrations.py      # 000
│   ├── migrate_create_ohlcv.py                  # 020
│   ├── migrate_add_swap_fields.py               # 030
│   ├── migrate_create_positions.py              # 040
│   ├── migrate_create_score_results.py          # 050
│   ├── migrate_fix_score_results_precision.py   # 060
│   ├── migrate_add_swap_fields_to_instruments.py  # 070
│   ├── migrate_create_trade_recommendations.py  # 080
│   ├── migrate_add_core_indexes.py              # 090
│   ├── migrate_create_ohlcv_partitioned.py      # 100
│   ├── migrate_create_indicators_partitioned.py # 110 — target bootstrap indicators_p
│   ├── migrate_add_data_constraints.py          # 130
│   ├── migrate_add_operational_reliability.py   # 140
│   ├── migrate_data_cleanup.py                  # 150
│   ├── migrate_materialized_views.py            # 160
│   ├── migrate_monitoring_metrics.py            # 170
│   ├── migrate_create_swap_ohlcv.py             # 180
│   ├── migrate_create_features_table.py         # 190
│   ├── migrate_add_data_retention.py            # 210
│   ├── migrate_expand_indicators_precision.py   # 230
│   ├── migrate_create_combination_features.py   # 240
│   ├── migrate_create_market_data_ext.py        # 250
│   ├── migrate_create_market_selection.py       # 260
│   ├── migrate_recreate_swap_ohlcv_partitioned.py # 270
│   │
│   ├── Transition-only
│   ├── migrate_backfill_partitioned.py          # 120 — только для переноса indicators→indicators_p
│   │
│   ├── Legacy compatibility
│   ├── migrate_create_unified_indicators_table.py   # 200 — legacy indicators
│   ├── migrate_update_indicators_table.py           # 205 — legacy indicators
│   ├── migrate_remove_ohlcv_from_indicators.py      # 220 — legacy indicators
│   │
│   └── Not in registry (orphaned / feature-specific)
│       ├── migrate_create_ohlcv.py                  # используется в CLI migrate напрямую
│       ├── migrate_create_indicators.py
│       ├── migrate_create_mtf_v2_tables.py
│       ├── migrate_create_mtf_expanded.py
│       ├── migrate_create_mtf_signals.py
│       ├── migrate_create_signals.py
│       ├── migrate_create_signals_detailed.py
│       ├── migrate_create_combination_results.py
│       ├── migrate_fix_combination_results_timezone.py
│       ├── migrate_create_data_quality_metrics.py
│       ├── migrate_add_missing_columns.py
│       ├── migrate_add_missing_ma_columns.py
│       ├── migrate_add_ohlcv_to_indicators.py
│       ├── migrate_add_ema200.py
│       ├── migrate_add_indexes.py
│       ├── migrate_cleanup_duplicate_columns.py
│       ├── migrate_fix_instrument_columns.py
│       └── migrate_phase3_quant_tables.py
│
├── rollback_phase3_quant_tables.sql  # SQL для отката phase3
│
└── reports/
    ├── STAGES_8_9_COMPLETION_SUMMARY.md
    ├── MIGRATION_TESTING_SUMMARY.md
    └── README_TESTING.md
```

---

## Key Files

### migration_registry.py

Единственный источник истины об упорядоченных миграциях. Любая новая миграция регистрируется здесь. Файлы в `migrations/`, не попавшие в реестр, не применяются автоматически.

### migration_runner.py

Движок применения: читает реестр, проверяет `schema_migrations`, пропускает уже применённые, поддерживает dry-run и откат при ошибке.

### indicators_partition/

Runtime-логика обслуживания партиций `indicators_p` (создание новых партиций, vacuum). Управляется через `python -m src.cli.main indicators-partitions`. Не является частью bootstrap-пути миграций.

---

## Quick Reference

```bash
# Применить миграции
python -m src.cli.main migrate

# Статус
python src/db/reports_cli.py status

# Валидация схемы
python -c "import asyncio; from src.db.schema_validation import validate_schema; asyncio.run(validate_schema())"

# Обслуживание партиций indicators_p
python -m src.cli.main indicators-partitions --apply --validate
```

---

Подробная документация: [README.md](README.md)
Чек-лист разработчика: [DEVELOPER_CHECKLIST.md](DEVELOPER_CHECKLIST.md)
