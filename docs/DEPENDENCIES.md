
# Карта зависимостей модулей src/

Полный анализ зависимостей между модулями верхнего уровня `src/`.
Учитываются только кросс-модульные импорты (внутренние зависимости внутри модуля не показаны).

---

## Структура src/

```
src/
├── alerts/                 # Система оповещений
├── backtest/               # Бэктестирование
├── candles/                # Синхронизация OHLCV с OKX
├── cli/                    # CLI интерфейс (thin adapters)
├── config/                 # Централизованная конфигурация (Pydantic Settings)
├── core/                   # Общие доменные примитивы
├── data/                   # Обработка данных
├── database/               # Инициализация и управление БД
├── database.py             # get_async_session (legacy)
├── db/                     # Схемы, миграции, партиции
├── features/               # Расчёт индикаторов/фичей
├── features_combinations/  # Комбинации индикаторов
├── logging/                # Централизованное логирование
├── market_meta/            # Метаданные рынка
├── market_selection/       # Фильтрация и ранжирование рынков
├── metrics/                # Quant-метрики
├── ml/                     # ML: scoring, labeling, metalabeling
├── models.py               # SQLAlchemy ORM модели (legacy, shared)
├── mtf/                    # Multi-timeframe анализ
├── positions/              # Управление позициями
├── risk/                   # Risk management
├── scoring_engine/         # Scoring engine
├── settings/               # Runtime user preferences
├── signals/                # Генерация сигналов
├── trade_recommender/      # Рекомендации по сделкам
├── tuning/                 # Оптимизация параметров
├── utils/                  # Общие утилиты
└── visual/                 # Визуализация
```

---

## Полная карта зависимостей

### alerts
- Нет исходящих зависимостей на другие модули src/
- Нет входящих зависимостей

### backtest
| Зависит от | Что импортирует |
|------------|-----------------|
| core | RunContext и другие примитивы |
| database | `get_async_session` |
| logging | `setup_logging` |

### candles
| Зависит от | Что импортирует |
|------------|-----------------|
| alerts | оповещения |
| config | настройки |
| database | `reset_pool` |
| features | фичи (для quality pipeline) |
| logging | `get_logger`, `setup_logging` |
| market_meta | метаданные инструментов |
| models | `Instrument` |
| utils | утилиты |

### cli
| Зависит от | Что импортирует |
|------------|-----------------|
| backtest | команды бэктеста |
| candles | `swap-sync`, `swap-repair` команды |
| core | примитивы |
| db | утилиты БД |
| features | `compute_features`, `FEATURE_SPECS` |
| logging | `get_features_logger`, `log_features_summary`, `setup_logging` |
| market_selection | команды фильтрации рынков |
| ml | ML команды |
| mtf | `MTFBuilder` |
| risk | risk guard |
| signals | сигналы |
| utils | утилиты |

### config
- Нет явных исходящих зависимостей на другие src-модули
- **Входящие**: candles, database, features, utils

### core
- Нет исходящих зависимостей
- **Входящие**: backtest, cli, ml

### data
- Нет обнаруженных зависимостей в обе стороны

### database *(включая database.py)*
| Зависит от | Что импортирует |
|------------|-----------------|
| config | `check_required_env_vars`, `get_database_url` |
| market_selection | (настройки подключения) |
| models | `INDICATORS_TABLE_NAME`, `Base` |

**Входящие** (13 модулей используют database):
backtest, candles, db, features, market_selection, mtf, positions, scoring_engine, settings, trade_recommender, tuning, utils, cli (через db)

### db
| Зависит от | Что импортирует |
|------------|-----------------|
| database | `DATABASE_URL`, `create_session`, `get_async_session`, `engine` |
| features | фичи |
| models | `Base`, `INDICATORS_TABLE_NAME` |
| utils | утилиты |

**Входящие**: cli, features, trade_recommender

### features
| Зависит от | Что импортирует |
|------------|-----------------|
| candles | `run_quality_pipeline` |
| cli | `handle` (из `__main__.py`, ленивый импорт) |
| config | `FeaturesSettings`, `get_settings` |
| database | `get_async_session` |
| db | `ensure_columns`, partition adapters |
| logging | `get_features_logger`, `LogAggregator`, `LogCategory`, `set_log_context`, `Verbosity` |
| utils | `get_db_session`, `RetryableOperation`, `RetryConfig` |

**Входящие**: candles, cli, db, models, mtf

### features_combinations
| Зависит от | Что импортирует |
|------------|-----------------|
| logging | `get_logger`, `setup_logging` |
| models | `INDICATORS_TABLE_NAME` |
| utils | утилиты |

**Входящие**: нет явных

### logging
- Нет исходящих зависимостей на другие src-модули (базовый модуль)
- **Входящие** (14 модулей): backtest, candles, cli, features, features_combinations, mtf, positions, settings, tuning, utils, + косвенно через весь стек

### market_meta
| Зависит от | Что импортирует |
|------------|-----------------|
| utils | утилиты |

**Входящие**: candles, mtf

### market_selection
| Зависит от | Что импортирует |
|------------|-----------------|
| database | `get_async_engine` |

**Входящие**: cli, database

### metrics
| Зависит от | Что импортирует |
|------------|-----------------|
| models | `INDICATORS_TABLE_NAME` |

**Входящие**: нет явных

### ml
| Зависит от | Что импортирует |
|------------|-----------------|
| core | RunContext и примитивы |

**Входящие**: cli

### models *(models.py)*
| Зависит от | Что импортирует |
|------------|-----------------|
| features | `IndicatorStorageContract` |

**Входящие** (8 модулей): database, db, features_combinations, metrics, scoring_engine, trade_recommender, utils, visual

### mtf
| Зависит от | Что импортирует |
|------------|-----------------|
| database | `get_async_session` |
| features | `compute_features` (заглушка, закомментировано) |
| logging | `get_logger`, `LogCategory`, `setup_logging` |
| market_meta | метаданные |

**Входящие**: cli, signals

### positions
| Зависит от | Что импортирует |
|------------|-----------------|
| database | `get_async_session` |
| logging | `setup_logging` |

**Входящие**: settings

### risk
- Нет обнаруженных исходящих зависимостей
- **Входящие**: cli

### scoring_engine
| Зависит от | Что импортирует |
|------------|-----------------|
| database | `get_async_session` |
| models | `CombinationResult`, `INDICATORS_TABLE_NAME`, `Indicator` |

**Входящие**: trade_recommender

### settings
| Зависит от | Что импортирует |
|------------|-----------------|
| database | `get_async_session` |
| logging | `setup_logging` |
| positions | позиции |

**Входящие**: нет явных

### signals
| Зависит от | Что импортирует |
|------------|-----------------|
| candles | данные свечей |
| mtf | MTF сигналы |

**Входящие**: cli, tuning

### trade_recommender
| Зависит от | Что импортирует |
|------------|-----------------|
| database | `get_async_session` |
| db | утилиты |
| models | `INDICATORS_TABLE_NAME`, `Indicator`, `SwapOhlcvP` |
| scoring_engine | scoring |

**Входящие**: нет явных

### tuning
| Зависит от | Что импортирует |
|------------|-----------------|
| backtest | бэктест |
| database | `get_async_session` |
| logging | `setup_logging` |
| signals | сигналы |

**Входящие**: нет явных

### utils
| Зависит от | Что импортирует |
|------------|-----------------|
| candles | (утилиты свечей) |
| config | настройки |
| database | `AsyncSessionLocal` |
| logging | `SensitiveDataFilter`, `get_logger`, `log_function_call` |
| models | `INDICATORS_TABLE_NAME` |

**Входящие**: backtest, candles, cli, db, features, features_combinations, market_meta

### visual
| Зависит от | Что импортирует |
|------------|-----------------|
| models | `INDICATORS_TABLE_NAME` |

**Входящие**: нет явных

---

## Наиболее связанные модули

### По количеству входящих зависимостей

| Модуль | Входящих | Кто зависит |
|--------|----------|-------------|
| database / database.py | 13 | backtest, candles, db, features, market_selection, mtf, positions, scoring_engine, settings, trade_recommender, tuning, utils, cli |
| logging | 14+ | все слои |
| models.py | 8 | database, db, features_combinations, metrics, scoring_engine, trade_recommender, utils, visual |
| utils | 7 | backtest, candles, cli, db, features, features_combinations, market_meta |
| config | 4 | candles, database, features, utils |

### По количеству исходящих зависимостей

| Модуль | Исходящих | Зависит от |
|--------|-----------|------------|
| cli | 11 | backtest, candles, core, db, features, logging, market_selection, ml, mtf, risk, signals, utils |
| candles | 8 | alerts, config, database, features, logging, market_meta, models, utils |
| features | 7 | candles, cli, config, database, db, logging, utils |
| db | 4 | database, features, models, utils |
| utils | 5 | candles, config, database, logging, models |

---

## Независимые модули

Модули без зависимостей на другие src-модули верхнего уровня:
- **alerts** — изолированный
- **config** — только env/settings, нет импортов из src
- **core** — чистые доменные примитивы
- **logging** — базовый модуль
- **risk** — изолированный

---

## Диаграмма ключевых зависимостей

```
config ──────────────────────────────────────────────────┐
logging ─────────────────────────────────────────────────┤
                                                          ▼
                                              ┌───────────────────┐
                          ┌───────────────────│   database.py /   │
                          │                   │   database/       │◄─── market_selection
                          │                   └───────┬───────────┘
                          │                           │
          ┌───────────────┼───────────────────────────┤
          ▼               ▼               ▼           ▼
   ┌──────────┐  ┌──────────────┐  ┌─────────┐  ┌─────────┐
   │ candles  │  │   features   │  │   mtf   │  │  utils  │
   └────┬─────┘  └──────┬───────┘  └────┬────┘  └────┬────┘
        │               │               │             │
        └───────────────┴───────────────┘             │
                        │                             │
                        ▼                             ▼
              ┌──────────────────┐         ┌──────────────────┐
              │       cli        │         │     models.py     │
              └──────────────────┘         └──────────────────┘
                        │
          ┌─────────────┼──────────────────┐
          ▼             ▼                  ▼
      ┌───────┐  ┌──────────────┐  ┌───────────┐
      │  ml   │  │   signals    │  │  backtest │
      └───────┘  └──────┬───────┘  └─────┬─────┘
                        │                │
                        ▼                ▼
                   ┌─────────┐    ┌──────────┐
                   │  tuning │    │ scoring  │
                   └─────────┘    │  engine  │
                                  └────┬─────┘
                                       ▼
                               ┌──────────────────┐
                               │ trade_recommender │
                               └──────────────────┘
```

---

## Архитектурные замечания

1. **database.py / models.py — legacy shared state**: слишком много модулей зависит напрямую от `database.py` и `models.py`. При рефакторинге следует мигрировать к изолированным репозиториям в каждом модуле.

2. **Циклические зависимости**:
   - `features → cli → features` (обходится ленивым импортом в `features/__main__.py`)
   - `models.py → features → database → models` (транзитивный цикл через legacy)
   - `db → features` и `features → db` (взаимная зависимость)

3. **utils → candles**: нетипичная зависимость; утилиты не должны импортировать доменные модули.

4. **candles → features**: зависимость через `run_quality_pipeline`; рассмотреть абстракцию через порт.

---

*Последнее обновление: 2026-05-03*
