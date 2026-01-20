
### План внедрения (единый файл)

- Назначение: детальный пошаговый план работ по добавлению долларовых баров, triple-barrier маркировки, металейблинга, Purged K-Fold и CPCV, реалистичного исполнения и издержек, риск-менеджмента, метрик устойчивости, теста на look-ahead, мониторинга/алертов, конфигурации и CLI-обвязки, с миграциями БД и тестовым покрытием. Следует идеям из `plan/quantitative_trading_strategy_infrastructure_and_risk_management.md`.

## 1) Архитектура и принципы

- **Единый исполнитель для backtest и paper**: `backtest/execution.py` — единый класс(ы) исполнения с параметризацией, используемый и в бэктесте, и в paper/live. Это снижает риск look-ahead и расхождений логики.
- **Бары по активности**: переключаемый режим баров `BARS_MODE=time|dollar`; долларовые бары формируются из тиков/минуток по денежному обороту для лучшей синхронизации с информационным потоком.
- **Валидация без утечек**: Purged K-Fold + Embargo и CPCV, совместимые с scikit-learn, для честной оценки и распределений метрик.
- **Мета-маркировка**: ML-модель оценивает вероятность успеха базового сигнала и управляет фильтром входов/сайзингом.
- **Риск-менеджмент встроен в модель**: triple-barrier уровни в сигнальном пайплайне; Kelly с cap и волатильностным таргетированием.
- **Реалистичные издержки**: комиссии, implementation shortfall, %ADV лимиты.
- **Метрики устойчивости**: DSR, CPCV-распределения, IS, turnover, maxDD, hit-rate.
- **Мониторинг**: запись метрик в Postgres и CSV; алерты при аномалиях задержек/IS/reject rate.

#### Адаптации под крипто‑свапы и текущие источники данных

- **Перпетуальные контракты**: ролловер фьючерсов неактуален для перпетуалов; для квартальных — оставить поддержку обратной корректировки на будущее.
- **Источники цен**: крипто‑рынок часто предоставляет агрегированные данные. Для тестов контртрендовых моделей фиксируем конкретную биржу‑источник (избегая скрытого «консолидационного» преимущества). Добавляем в метаданные `source` при сохранении баров (опционально).
- **%ADV прокси**: рассчитываем на базе спот/перпет. оборота за окно 20–60 дней по символу/бирже. Стартовый лимит `MAX_ORDER_PCT_ADV=0.01`, далее калибровка по фактическому reject rate.
- **IS моделирование**: если нет L2/глубины, используем параметрическую модель IS в б.п., зависящую от волатильности (например, доля от ATR/σ) и спреда; при наличии — подключаем L2‑адаптер.
- **Долларовые бары при отсутствии тиков**: допустим fallback из минуток с использованием `turnover ≈ close * volume` и аккуратной агрегации, с флагом в отчёте (см. тесты на смещение).
- **Часовые пояса/метки**: нормализуем timestamps к UTC, сохраняем `ts_start/ts_end` для баров активности и `duration_s` для контроля задержек/агрегации.

## 2) Состав модулей и задачи

- `src/core/bars.py`
  - Функция генерации долларовых баров из тиков/минуток.
  - Вход: DataFrame с колонками `timestamp`, `price` и `volume` (или OHLCV минуток), параметры: `dollar_value: float`, `min_trades: int`.
  - Выход: DataFrame с `open, high, low, close, volume, turnover, timestamp, ts_start, ts_end, duration_s, trades_count` (turnover в валюте котировки, напр. USDT).
  - Учесть частичные бары, строгую монотонность времени, корректную агрегацию из минуток (fallback: накопление по `close*volume`; пометить `bars_source=fallback_minute`).
- Интеграция в pipeline
  - В точке загрузки OHLCV/тик данных добавить ветку: если `BARS_MODE=dollar`, прогнать через `core/bars.py` до расчёта признаков/маркировки.
  - Минимальные изменения в местах, откуда `src/features/core.compute_features` получает DataFrame.
- `src/ml/labeling/triple_barrier.py`
  - `triple_barrier_labels(df, pt, sl, max_h)` — векторизованно, без циклов по рядам.
  - Вход: df с `close` и временными индексами/метками; выход: метки `y` и горизонт времени до срабатывания; поддержка пропусков, крайних баров; возвращать DataFrame с `label, t1, vert_time`.
- `src/ml/metalabeling.py`
  - Класс с интерфейсом `fit(X, y)`, `predict_proba(X)`; обёртка над выбранной моделью (например, `RandomForestClassifier` или `XGBoost`, выбираемо через конфиг).
  - Поддержка sample weights (по давности, информации), возможность каллибровки вероятностей.
- `src/ml/validation/purged_kfold.py`
  - Реализация Purged K-Fold + Embargo совместимая со scikit-learn split API.
  - Параметр `embargo_pct`. Тщательные инварианты: отсутствующие пересечения луков в метках (по `t1`), корректная очистка.
- `src/ml/validation/cpcv.py`
  - Combinatorial Purged CV: генерация путей обучения/валидации и сбор распределения метрик; интерфейс удобный для grid-search и отчётности.
- `src/backtest/execution.py`
  - Исполнитель со слоями:
    - Комиссии (maker/taker, фикс/процент).
    - Проскальзывание через `implementation shortfall` (сценарии: фикс. б.п., стохастическая модель от волатильности/ликвидности/спреда; логировать IS).
    - Лимит по `%ADV` (учёт среднего объёма за окно; по превышению — частичное исполнение, отложка или reject).
  - Логи сделок в БД и CSV, агрегированный IS; метки задержек (paper).
  - Paper режим: подключение к реальному потоку котировок, сухое исполнение тем же движком; журнал задержек и IS.
  - (Опционально) учёт фондинга для перпетуалов в PnL‑метриках, если есть источник данных.
- `src/risk/position_sizing.py`
  - Kelly fraction (с cap `KELLY_CAP`), волатильностное таргетирование (цель `VOL_TARGET`), лимиты по инструментам/стратегии.
  - Интерфейс: функции вычисления размеров позиции от прогнозной вероятности/edge, реализующей output металейблинга; защита от экстремальных значений.
  - Лимиты по ликвидности: per‑symbol caps на основе ликвидностных «тиров» (из %ADV), глобальные caps по стратегии.
- Интеграция triple-barrier в сигнальный пайплайн
  - В местах генерации сигналов: рассчитать уровни pt/sl/max_h, отдавать в исполнителя; использовать метки y для обучения, t1 для Purged K-Fold.
- `src/metrics/dsr.py`
  - Функции вычисления SR и DSR (с учётом кол-ва тестов/переборов) и возврат p-value; совместимость со сводным отчётом.
- Отчёт
  - HTML/MD отчёт с: SR, DSR, turnover, maxDD, hit-rate, IS, CPCV-распределения; кривые капитала, карты параметров.
- Тест look-ahead
  - `tests/test_lookahead.py`: прогнать бэктест на полном датасете (файл A) и на усечённом (-N баров) (файл B); обрезать файл A и сравнить позиции — должны совпасть.
- Мониторинг/алерты
  - `src/monitoring/logging.py`: записывать метрики в Postgres и CSV; функции для публикации алертов (Slack/лог) при превышении порогов: рост IS, задержки, reject rate.
  - Reject rate определяется как доля неисполненных/урезанных заявок из‑за ограничений %ADV/ликвидности; пороги конфигурируемые.
- CLI
  - `src/cli/commands/cli.py` или расширение `src/cli/main.py`:
    - Команды: `build-bars`, `label`, `train`, `backtest`, `paper`, `live`, `metrics show`.
    - Все команды принимают путь к конфигу; поддержка `.env`, YAML.
- Конфигурация
  - `.env.example` добавить ключи:
    - `BARS_MODE=dollar`
    - `DOLLAR_BAR_VALUE=200000`
    - `TRIPLE_PT=0.02`
    - `TRIPLE_SL=0.01`
    - `TRIPLE_MAX_H=48`
    - `EMBARGO_PCT=0.01`
    - `MAX_ORDER_PCT_ADV=0.01`
    - `KELLY_CAP=0.25`
    - `VOL_TARGET=0.1`
    - `PAPER_TRADING=true`
    - `ALERT_IS_MAX_BPS=30`
    - `ALERT_LATENCY_MS=200`

## 3) Миграции БД

- Таблица `bars`
  - Поля: `id`, `symbol`, `timeframe`, `timestamp` (бар метка), `open, high, low, close, volume, turnover`, `ts_start, ts_end, duration_s, trades_count`, `bars_mode` (`time|dollar`), `created_at, updated_at`.
  - Индексы: `(symbol, timeframe, timestamp)`, отдельный по `(symbol, timestamp)`.
  - (Опционально) поле `source` для фиксации биржи/провайдера данных и `bars_source` (`ticks|fallback_minute`).
- Таблица `labels`
  - `id`, `symbol`, `timeframe`, `timestamp`, `label` (−1/0/+1), `t1` (время вертикального барьера), `pt`, `sl`, `max_h`.
  - Индекс `(symbol, timeframe, timestamp)`.
- Таблица `trades`
  - `id`, `run_id`, `mode` (`backtest|paper|live`), `symbol`, `timeframe`, `timestamp_signal`, `timestamp_exec`, `side`, `price_signal`, `price_exec`, `qty`, `commission`, `implementation_shortfall_bps`, `latency_ms`, `reject_reason`, `extra`.
  - Индексы: `(run_id)`, `(symbol, timeframe, timestamp_exec)`.
- Таблица `metrics`
  - `id`, `run_id`, `mode`, `name`, `value`, `unit`, `timestamp`, `window`, `extra`.
  - Индексы: `(run_id, name)`, `(timestamp)`.

## 4) Изменения pipeline

- В точке формирования входного OHLCV для фичей/маркировки (например, в `src/cli/commands/features.py` до `compute_features`):
  - Если `BARS_MODE=dollar`, загрузить тики/минутки, построить долларовые бары, сохранить в `bars`, далее использовать их для фичей/маркировки.
  - Если доступны только минутки: использовать fallback‑агрегацию и явно помечать источник в отчёте и логах, запускать дымовой тест на смещение (см. тесты ниже).
- Добавить шаги:
  - `build-bars`: строит `bars` по `symbols,timeframes`, пишет в БД.
  - `label`: читает `bars`, считает triple-barrier, пишет `labels`.
  - `train`: формирует `X,y` из features+labels, валидирует Purged K-Fold/CPCV, обучает металейблинг, сохраняет артефакты.
  - `backtest`: использует единый `execution` с параметрами комиссий/IS/%ADV, пишет `trades`/`metrics`, генерирует отчёт.
  - `paper`: запускает поток котировок, тот же `execution`, пишет задержки/IS; контролирует алерты.
  - `live`: адаптер к брокеру, тот же `execution` с реальным маршрутизатором ордеров.
  - `metrics show`: отображает SR, DSR, turnover, maxDD, hit-rate, IS; опция выгрузки HTML/MD.

## 5) Валидация и тесты

- PyTests:
  - `test_bars_dollar`: корректность агрегации, монотонность, соблюдение `dollar_value` и `min_trades`, соответствие сумм.
  - `test_bars_dollar_minute_fallback`: сравнение против эталонной тиковой агрегации на сэмпле; оценка смещения по цене/времени.
  - `test_triple_barrier_vectorized`: совпадение с эталонной петлевой реализацией; корректные `t1`, края.
  - `test_purged_kfold_properties`: отсутствие утечек при пересечении меток/времени; корректный Embargo.
  - `test_cpcv_paths`: количество путей и их непересечения валидации.
  - `test_execution_is`: корректный подсчёт IS в б.п., влияние волатильности/ликвидности, лимиты %ADV, логи `trades`.
  - `test_risk_sizing`: Kelly c cap и волатильностное таргетирование — соблюдение ограничений.
  - `tests/test_lookahead.py`: сравнение файлов позиций (полный vs усечённый) — идентичность.
  - Типизация mypy, стиль ruff; докстринги с примерами.
- Дымовые сценарии:
  - CLI: `build-bars`, `label`, `train`, `backtest`, `paper` с маленькими окнами/лимитами — успешный прогон и запись в БД.

## 6) Мониторинг и алерты

- `monitoring/logging.py`
  - Функции: `log_metric_pg(run_id, name, value, unit, extra)`, `log_metric_csv(...)`.
  - Алерты: при `implementation_shortfall_bps > ALERT_IS_MAX_BPS`, `latency_ms > ALERT_LATENCY_MS`, `reject_rate > threshold`; чтение порогов из `.env`.
- В `paper`/`live`: периодическая отправка алертов и агрегаций.
 - В отчётах и логах отражать `bars_mode`, `bars_source`, `data_source` (биржа), чтобы фиксировать потенциальные источники смещения.

## 7) Отчёт и артефакты

- Генерация HTML/MD отчёта:
  - Секции: описание конфигурации; кривые капитала; распределения CPCV; таблица метрик (SR, DSR с p-value, turnover, maxDD, hit-rate, средний IS, комиссии); графики IS/latency; покрытие активов/таймфреймов.
  - Сохранение отчёта с привязкой к `run_id`.
  - Breakdown по режимам рынка (высокая/низкая волатильность, низкая/высокая ликвидность) и по источнику данных (биржа), если доступно.
- Экспорт `metrics show`:
  - Консольная таблица ключевых метрик по `run_id`; опционально — путь до отчёта.

## 8) Конфигурация и секреты

- Обновить `.env.example` (ключи из раздела Требования).
- Обновить загрузчик конфигурации (если используется `src/config/env_validator.py`/pydantic): валидация новых ключей, значения по умолчанию, описание.

## 9) Пошаговые коммиты (минимальные атомарные)

1. Scaffold модулей: `core/bars.py`, `ml/labeling/triple_barrier.py`, `ml/metalabeling.py`, `ml/validation/purged_kfold.py`, `ml/validation/cpcv.py`, `backtest/execution.py`, `risk/position_sizing.py`, `metrics/dsr.py`, `monitoring/logging.py`; пустые каркасы и докстринги.
2. Миграции БД: таблицы `bars`, `labels`, `trades`, `metrics` с индексами.
3. Долларовые бары + CLI `build-bars` + интеграция `BARS_MODE`.
4. Triple-barrier + CLI `label`.
5. Purged K-Fold + Embargo; CPCV.
6. Metalabeling: обучение и сохранение артефактов; CLI `train`.
7. Исполнитель с комиссиями/IS/%ADV и логами; CLI `backtest`.
8. Paper режим с реальным потоком; задержки/IS; алерты.
9. Риск-менеджмент: Kelly cap, волатильностное таргетирование.
10. Метрики DSR и сводный отчёт HTML/MD; CLI `metrics show`.
11. Тесты, mypy, ruff; фиксы.
12. Look-ahead тест и финальная проверка acceptance criteria.

## 10) Acceptance mapping

- Общий исполнитель для backtest/paper — DONE в `backtest/execution.py`.
- Отчёт HTML/MD со списком метрик, CPCV, DSR, IS — DONE.
- Look-ahead тест проходит — DONE `tests/test_lookahead.py`.
- При `PAPER_TRADING=true` пишутся журналы задержек и IS — DONE.
- Метрики и алерты доступны через `metrics show` — DONE.

## 11) 30-60-90 ритм (из отчёта)

- 0–30: данные и бары по активности; triple-barrier; базовый backtest без издержек; первичный отчёт.
- 30–60: Purged K-Fold/Embargo, CPCV; реалистичные издержки (комиссии, IS, %ADV); DSR; металейблинг.
- 60–90: paper режим с алертами; риск-менеджмент (Kelly/VOL target); полноценный отчёт; финальная проверка Look-ahead и Go-live чек-лист.

- Ключевые риски и контроль:
  - Переобучение: use DSR, CPCV; простота базовой модели + металейблинг.
  - Утечки: Purged K-Fold + Embargo, единый исполнитель.
  - Издержки/ликвидность: IS, %ADV лимиты и мониторинг.
