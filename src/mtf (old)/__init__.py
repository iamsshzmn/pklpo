"""
MTF (Multi-Timeframe) Analysis Package

Промышленная система анализа мультитаймфреймовых сигналов с:
- Версионированием и контрактами данных
- Мониторингом качества данных
- Системой алертов
- Трассировкой выполнения
- Риск-менеджментом

Архитектура:
├── config/          - Конфигурация и настройки
├── monitoring/      - Мониторинг качества данных и алерты
├── models/          - Схемы данных и модели
├── utils/           - Утилиты (run_tracker, валидация)
├── etl/             - ETL процессы (context, triggers, consensus)
├── risk/            - Риск-менеджмент
├── signals/         - Генерация торговых сигналов
├── backtest/        - Бэктестинг
└── cli/             - Командные интерфейсы

Основные компоненты:
- ContextLoader: Загрузка контекстных данных
- TriggerLoader: Загрузка триггерных данных
- ConsensusWriter: Запись консенсусных решений
- DecisionMaker: Принятие торговых решений
- QualityMonitor: Мониторинг качества данных
- AlertManager: Система алертов
- RunTracker: Трассировка выполнения
"""

# ============================================================================
# Основные компоненты
# ============================================================================

# Конфигурация
# ============================================================================
# Экспорты для обратной совместимости
# ============================================================================
# Старые импорты для совместимости
from .aggregator import determine_bias_and_consensus
from .combinations import compute_combination_votes
from .config.settings import (
    ConfigManager,
    ConsensusConfig,
    DataQualityConfig,
    ExchangeConfig,
    IndicatorConfig,
    MTFConfig,
    RiskConfig,
    TimeframeConfig,
    config_manager,
    mtf_config,
)

# Основные компоненты
from .decision_maker import MTFDecisionMaker
from .etl.consensus_writer import ConsensusWriter

# ETL компоненты
from .etl.context_loader import ContextLoader
from .etl.trigger_loader import TriggerLoader
from .features import compute_trend_score, fetch_latest_indicators
from .manager import run_mtf_full_cycle

# Модели данных
from .models.schema import (
    MTFAlerts,
    MTFConsensus,
    MTFContext,
    MTFDataQuality,
    MTFRuns,
    MTFSignals,
    MTFTriggers,
    QualityStatus,
    RunStatus,
    SignalSide,
    get_schema_version,
    get_table_names,
    validate_data_contract,
)
from .monitoring.alerts import AlertLevel, AlertManager, AlertMessage, alert_manager

# Мониторинг и алерты
from .monitoring.data_quality import (
    DataQualityMetrics,
    DataQualityMonitor,
    QualityStatus,
    quality_monitor,
)
from .trigger import evaluate_trigger_probabilities

# Утилиты
from .utils.run_tracker import (
    RunContext,
    RunTracker,
    get_run_logger,
    run_context,
    run_tracker,
    track_run,
)
from .writer import save_mtf_result

# ============================================================================
# Версионирование
# ============================================================================

__version__ = "2.0.0"
__schema_version__ = "v1"

# ============================================================================
# Основные функции для быстрого старта
# ============================================================================


async def run_mtf_analysis(symbol: str | None = None, dry_run: bool = False):
    """
    Запустить полный анализ MTF

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)
        dry_run: Только проверка без выполнения действий

    Returns:
        Dict с результатами анализа
    """
    return await run_mtf_full_cycle(symbol, dry_run)


async def check_data_quality(symbol: str | None = None):
    """
    Проверить качество данных

    Args:
        symbol: Конкретный символ (если None, проверяются все)

    Returns:
        DataQualityMetrics или сводка качества
    """
    if symbol:
        return await quality_monitor.check_symbol_quality(symbol)
    return await quality_monitor.get_quality_summary()


async def get_mtf_signals(horizon: str | None = None, limit: int = 10):
    """
    Получить MTF сигналы

    Args:
        horizon: Горизонт (intraday, swing, week)
        limit: Максимальное количество сигналов

    Returns:
        List с сигналами
    """
    decision_maker = MTFDecisionMaker()

    if horizon == "intraday":
        return await decision_maker.get_intraday_signals(limit=limit)
    if horizon == "swing":
        return await decision_maker.get_swing_opportunities(limit=limit)
    if horizon == "week":
        return await decision_maker.get_week_opportunities(limit=limit)
    return await decision_maker.get_market_overview(limit=limit)


def get_config():
    """
    Получить текущую конфигурацию MTF

    Returns:
        MTFConfig объект
    """
    return mtf_config


async def test_alerts():
    """
    Протестировать систему алертов

    Returns:
        Dict с результатами тестирования каналов
    """
    return await alert_manager.test_all_channels()


# ============================================================================
# Экспорты
# ============================================================================

__all__ = [
    # Основные компоненты
    "MTFDecisionMaker",
    "run_mtf_full_cycle",
    "run_mtf_analysis",
    "check_data_quality",
    "get_mtf_signals",
    "get_config",
    "test_alerts",
    # Конфигурация
    "MTFConfig",
    "ConfigManager",
    "config_manager",
    "mtf_config",
    "TimeframeConfig",
    "IndicatorConfig",
    "ConsensusConfig",
    "RiskConfig",
    "DataQualityConfig",
    "ExchangeConfig",
    # Мониторинг
    "DataQualityMonitor",
    "DataQualityMetrics",
    "QualityStatus",
    "quality_monitor",
    "AlertManager",
    "AlertLevel",
    "AlertMessage",
    "alert_manager",
    # Модели
    "MTFContext",
    "MTFTriggers",
    "MTFConsensus",
    "MTFRuns",
    "MTFDataQuality",
    "MTFAlerts",
    "MTFSignals",
    "SignalSide",
    "RunStatus",
    "get_table_names",
    "get_schema_version",
    "validate_data_contract",
    # Утилиты
    "RunTracker",
    "RunContext",
    "run_tracker",
    "track_run",
    "run_context",
    "get_run_logger",
    # ETL
    "ContextLoader",
    "TriggerLoader",
    "ConsensusWriter",
    # Обратная совместимость
    "determine_bias_and_consensus",
    "fetch_latest_indicators",
    "compute_trend_score",
    "evaluate_trigger_probabilities",
    "compute_combination_votes",
    "save_mtf_result",
    # Версионирование
    "__version__",
    "__schema_version__",
]
