from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Instrument(Base):
    __tablename__ = "instruments"

    symbol = Column(String, primary_key=True)  # PK
    inst_id = Column(String, unique=True, nullable=False)  # было instId
    base_ccy = Column(String, nullable=True)  # было baseCcy
    quote_ccy = Column(String, nullable=True)  # было quoteCcy
    inst_type = Column(String, nullable=True)  # было instType
    uly = Column(String, nullable=True)
    ct_val_ccy = Column(String, nullable=True)  # было ctValCcy
    ct_val = Column(Float, nullable=True)  # было ctVal
    lever = Column(Float, nullable=True)
    state = Column(String, nullable=True)
    list_time = Column(
        BigInteger, nullable=True
    )  # было listTime - время листинга в миллисекундах

    # Новые поля для свопов (SWAP)
    contract_val = Column(Float, nullable=True)  # стоимость одного контракта
    settle_ccy = Column(
        String, nullable=True
    )  # валюта расчётов (важна при cross-марже)
    ct_type = Column(
        String, nullable=True
    )  # linear или inverse; влияет на расчёт PnL и ликвидации
    min_sz = Column(
        Float, nullable=True
    )  # было minSz - минимальное количество контрактов для ордера
    max_sz = Column(Float, nullable=True)  # было maxSz - ограничение по объёму
    min_notional = Column(
        Float, nullable=True
    )  # было minNotional - минимальный размер сделки в долларах


class OHLCV(Base):
    __tablename__ = "ohlcv"
    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)  # timestamp в миллисекундах
    open = Column(Numeric)
    high = Column(Numeric)
    low = Column(Numeric)
    close = Column(Numeric)
    volume = Column(Numeric)
    volCcy = Column(Numeric, nullable=True)  # Добавлено для SPOT
    volUsd = Column(Numeric, nullable=True)  # Добавлено для SPOT
    fetched_at = Column(DateTime, nullable=True)  # Время получения данных


class Indicator(Base):
    __tablename__ = "indicators"
    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    timestamp = Column(BigInteger, primary_key=True)  # timestamp в миллисекундах

    # OHLCV данные удалены - они есть в swap_ohlcv_p

    # RSI
    rsi_14 = Column(Numeric, nullable=True)

    # Moving Averages
    ema_12 = Column(Numeric, nullable=True)
    ema_21 = Column(Numeric, nullable=True)
    ema_26 = Column(Numeric, nullable=True)
    ema_50 = Column(Numeric, nullable=True)
    ema_200 = Column(Numeric, nullable=True)
    sma_34 = Column(Numeric, nullable=True)
    sma_50 = Column(Numeric, nullable=True)
    sma_200 = Column(Numeric, nullable=True)

    # MACD
    macd = Column(Numeric, nullable=True)
    macd_signal = Column(Numeric, nullable=True)
    macd_histogram = Column(Numeric, nullable=True)

    # Bollinger Bands
    bb_upper = Column(Numeric, nullable=True)
    bb_middle = Column(Numeric, nullable=True)
    bb_lower = Column(Numeric, nullable=True)

    # Stochastic
    stoch_k = Column(Numeric, nullable=True)
    stoch_d = Column(Numeric, nullable=True)

    # ATR (Average True Range)
    atr_14 = Column(Numeric, nullable=True)

    # Volume indicators
    volume_sma20 = Column(Numeric, nullable=True)

    # Ichimoku
    ichimoku_tenkan = Column(Numeric, nullable=True)
    ichimoku_kijun = Column(Numeric, nullable=True)
    ichimoku_senkou_a = Column(Numeric, nullable=True)
    ichimoku_senkou_b = Column(Numeric, nullable=True)
    ichimoku_chikou = Column(Numeric, nullable=True)

    # ADX
    adx_14 = Column(Numeric, nullable=True)
    adx_pos_di = Column(Numeric, nullable=True)
    adx_neg_di = Column(Numeric, nullable=True)

    # OBV
    obv = Column(Numeric, nullable=True)

    # CMF
    cmf = Column(Numeric, nullable=True)

    # VWAP
    vwap = Column(Numeric, nullable=True)

    # Volume Profile (VP)
    vp_value_area_high = Column(Numeric, nullable=True)
    vp_value_area_low = Column(Numeric, nullable=True)
    vp_point_of_control = Column(Numeric, nullable=True)

    # Keltner Channel
    kc_upper = Column(Numeric, nullable=True)
    kc_middle = Column(Numeric, nullable=True)
    kc_lower = Column(Numeric, nullable=True)

    # TTM Squeeze
    ttm_squeeze_on = Column(Numeric, nullable=True)
    ttm_squeeze_hist = Column(Numeric, nullable=True)
    ttm_squeeze_value = Column(Numeric, nullable=True)

    # EMA-Ribbon
    ema_8 = Column(Numeric, nullable=True)
    ema_13 = Column(Numeric, nullable=True)
    ema_21 = Column(Numeric, nullable=True)
    ema_34 = Column(Numeric, nullable=True)
    ema_55 = Column(Numeric, nullable=True)
    ema_89 = Column(Numeric, nullable=True)
    ema_144 = Column(Numeric, nullable=True)
    ema_233 = Column(Numeric, nullable=True)

    # Candle indicators
    ha_open = Column(Numeric, nullable=True)
    ha_high = Column(Numeric, nullable=True)
    ha_low = Column(Numeric, nullable=True)
    ha_close = Column(Numeric, nullable=True)
    cdl_doji = Column(SmallInteger, nullable=True)
    cdl_inside = Column(SmallInteger, nullable=True)

    # Performance indicators
    drawdown = Column(Numeric, nullable=True)
    log_return = Column(Numeric, nullable=True)
    percent_return = Column(Numeric, nullable=True)
    trend_return_20 = Column(Numeric, nullable=True)
    returns_20 = Column(Numeric, nullable=True)
    volatility_20 = Column(Numeric, nullable=True)
    sharpe_20 = Column(Numeric, nullable=True)
    max_drawdown_20 = Column(Numeric, nullable=True)

    # Время расчета индикатора
    calculated_at = Column(DateTime, nullable=True)

    # Дополнительные поля для overlap индикаторов
    hl2 = Column(Numeric, nullable=True)  # (high + low) / 2
    hlc3 = Column(Numeric, nullable=True)  # (high + low + close) / 3
    ohlc4 = Column(Numeric, nullable=True)  # (open + high + low + close) / 4
    midpoint = Column(Numeric, nullable=True)  # Alias for hl2 (deprecated)
    midprice = Column(Numeric, nullable=True)  # Alias for hl2 (deprecated)
    wcp = Column(Numeric, nullable=True)  # Weighted Close Price

    # Дополнительные MA индикаторы
    hwma_20 = Column(Numeric, nullable=True)
    rma_20 = Column(Numeric, nullable=True)  # Wilder RMA (20)
    ics_26 = Column(Numeric, nullable=True)  # Wilder RMA (26) - Ichimoku Cloud Support
    t3_20 = Column(Numeric, nullable=True)  # T3 Moving Average (20)

    # TTM индикаторы
    ttm_trend = Column(Numeric, nullable=True)

    # Дополнительные трендовые индикаторы
    decay = Column(Numeric, nullable=True)
    long_run = Column(Numeric, nullable=True)
    decreasing = Column(Numeric, nullable=True)
    increasing = Column(Numeric, nullable=True)
    amat = Column(Numeric, nullable=True)
    short_run = Column(Numeric, nullable=True)

    # Недостающие колонки из лога ошибок
    pvi = Column(Numeric, nullable=True)  # Positive Volume Index
    ad = Column(Numeric, nullable=True)  # Accumulation/Distribution
    rsx_14 = Column(Numeric, nullable=True)  # RSX (Relative Strength Index)
    trange = Column(Numeric, nullable=True)  # True Range
    nvi = Column(Numeric, nullable=True)  # Negative Volume Index
    bop = Column(Numeric, nullable=True)  # Balance of Power
    rsx = Column(Numeric, nullable=True)  # RSX (без периода)

    # Versioning fields (FEAT-001: ML reproducibility)
    # TODO: Раскомментировать после миграции БД (FEAT-001)
    # algorithm_version = Column(String(20), nullable=True, default='1.0.0')
    # snapshot_id = Column(String(50), nullable=True)
    # calculation_config = Column(String, nullable=True)  # JSON as text
    calculated_at = Column(
        DateTime(timezone=True), nullable=True
    )  # Timestamp of calculation

    # Data completeness status
    data_status = Column(
        String(10), nullable=True, server_default="ok"
    )  # 'ok' or 'inc'
    failed_groups = Column(
        String, nullable=True
    )  # Comma-separated list of failed indicator groups

    # Недостающие колонки из расчёта индикаторов (добавлены автоматически)
    pwma_20 = Column(Numeric, nullable=True)
    slope_20 = Column(Numeric, nullable=True)
    vidya_20 = Column(Numeric, nullable=True)
    median_20 = Column(Numeric, nullable=True)
    aroon_up = Column(Numeric, nullable=True)
    wma_20 = Column(Numeric, nullable=True)
    inertia = Column(Numeric, nullable=True)
    mad_20 = Column(Numeric, nullable=True)
    vortex = Column(Numeric, nullable=True)
    er = Column(Numeric, nullable=True)
    dc_upper = Column(Numeric, nullable=True)
    rvgi = Column(Numeric, nullable=True)
    kurtosis_20 = Column(Numeric, nullable=True)
    zlma_20 = Column(Numeric, nullable=True)
    dema_20 = Column(Numeric, nullable=True)
    rvi = Column(Numeric, nullable=True)
    ao = Column(Numeric, nullable=True)
    pdist = Column(Numeric, nullable=True)
    trix = Column(Numeric, nullable=True)
    mfi = Column(Numeric, nullable=True)
    kama_20 = Column(Numeric, nullable=True)
    cg = Column(Numeric, nullable=True)
    linreg_20 = Column(Numeric, nullable=True)
    roc_10 = Column(Numeric, nullable=True)
    variance_20 = Column(Numeric, nullable=True)
    fwma_20 = Column(Numeric, nullable=True)
    natr_14 = Column(Numeric, nullable=True)
    sma_20 = Column(Numeric, nullable=True)
    cci_20 = Column(Numeric, nullable=True)
    hma_20 = Column(Numeric, nullable=True)
    cfo = Column(Numeric, nullable=True)
    parkinson_vol = Column(Numeric, nullable=True)
    adosc = Column(Numeric, nullable=True)
    dc_lower = Column(Numeric, nullable=True)
    fisher = Column(Numeric, nullable=True)
    alma_20 = Column(Numeric, nullable=True)
    apo = Column(Numeric, nullable=True)
    vwma = Column(Numeric, nullable=True)
    var_20 = Column(Numeric, nullable=True)
    brar = Column(Numeric, nullable=True)
    pvt = Column(Numeric, nullable=True)
    willr = Column(Numeric, nullable=True)
    massi = Column(Numeric, nullable=True)
    tsi = Column(Numeric, nullable=True)
    aroon_osc = Column(Numeric, nullable=True)
    trima_20 = Column(Numeric, nullable=True)
    bias = Column(Numeric, nullable=True)
    kurt_20 = Column(Numeric, nullable=True)
    ppo = Column(Numeric, nullable=True)
    zscore_20 = Column(Numeric, nullable=True)
    stdev_20 = Column(Numeric, nullable=True)
    smi = Column(Numeric, nullable=True)
    pvo = Column(Numeric, nullable=True)
    tema_20 = Column(Numeric, nullable=True)
    dc_middle = Column(Numeric, nullable=True)
    pgo = Column(Numeric, nullable=True)
    sinwma_20 = Column(Numeric, nullable=True)
    eri = Column(Numeric, nullable=True)
    swma_20 = Column(Numeric, nullable=True)
    skew_20 = Column(Numeric, nullable=True)
    aroon_down = Column(Numeric, nullable=True)
    psl = Column(Numeric, nullable=True)
    coppock = Column(Numeric, nullable=True)
    uo = Column(Numeric, nullable=True)
    ultosc = Column(Numeric, nullable=True)
    std_20 = Column(Numeric, nullable=True)
    ui = Column(Numeric, nullable=True)
    percent_return = Column(Numeric, nullable=True)
    trend_return_20 = Column(Numeric, nullable=True)
    qstick = Column(Numeric, nullable=True)
    psar = Column(Numeric, nullable=True)
    psar_direction = Column(Numeric, nullable=True)
    psar_long = Column(Numeric, nullable=True)
    psar_short = Column(Numeric, nullable=True)
    supertrend = Column(Numeric, nullable=True)
    supertrend_direction = Column(Numeric, nullable=True)
    supertrend_long = Column(Numeric, nullable=True)
    supertrend_short = Column(Numeric, nullable=True)
    chop = Column(Numeric, nullable=True)
    dpo = Column(Numeric, nullable=True)
    stochrsi_k = Column(Numeric, nullable=True)
    stochrsi_d = Column(Numeric, nullable=True)
    kdj_k = Column(Numeric, nullable=True)
    kdj_d = Column(Numeric, nullable=True)
    kc_upper = Column(Numeric, nullable=True)
    kc_middle = Column(Numeric, nullable=True)
    kc_lower = Column(Numeric, nullable=True)
    vp_point_of_control = Column(Numeric, nullable=True)
    vp_value_area_high = Column(Numeric, nullable=True)
    vp_value_area_low = Column(Numeric, nullable=True)


class Signal(Base):
    __tablename__ = "signals"
    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)  # timestamp в миллисекундах
    signal = Column(Numeric)  # -1 = sell, 0 = hold, 1 = buy
    reason = Column(String, nullable=True)  # JSON-строка: какие правила сработали
    created_at = Column(DateTime, nullable=True)  # Время создания сигнала


class SignalDetailed(Base):
    """Детализированная таблица сигналов с отдельными колонками для каждого правила"""

    __tablename__ = "signals_detailed"

    # Основные ключи
    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)  # timestamp в секундах

    # Финальный сигнал
    signal = Column(SmallInteger)  # -1 = sell, 0 = hold, 1 = buy
    total_score = Column(Numeric, nullable=True)  # Общий взвешенный score

    # Детализированные сигналы по правилам (текстовые)
    sma50_sma200 = Column(String, nullable=True)  # "bullish", "bearish", "neutral"
    ema21_sma50 = Column(String, nullable=True)
    macd = Column(String, nullable=True)
    rsi14 = Column(String, nullable=True)
    bollinger = Column(String, nullable=True)
    stochastic = Column(String, nullable=True)
    adx14 = Column(String, nullable=True)
    ichimoku = Column(String, nullable=True)
    keltner = Column(String, nullable=True)
    volume_obv_cmf = Column(String, nullable=True)

    # Числовые scores для каждого правила
    sma50_sma200_score = Column(Numeric, nullable=True)
    ema21_sma50_score = Column(Numeric, nullable=True)
    macd_score = Column(Numeric, nullable=True)
    rsi14_score = Column(Numeric, nullable=True)
    bollinger_score = Column(Numeric, nullable=True)
    stochastic_score = Column(Numeric, nullable=True)
    adx14_score = Column(Numeric, nullable=True)
    ichimoku_score = Column(Numeric, nullable=True)
    keltner_score = Column(Numeric, nullable=True)
    volume_obv_cmf_score = Column(Numeric, nullable=True)

    # Время создания
    created_at = Column(DateTime, nullable=True)


class SignalRuleCodes(Base):
    """Справочник кодов правил для числового представления"""

    __tablename__ = "signal_rule_codes"

    code = Column(SmallInteger, primary_key=True)
    rule_name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    # Примеры:
    # code=1, rule_name="sma50_sma200", description="SMA50 > SMA200 (bullish)"
    # code=-1, rule_name="sma50_sma200", description="SMA50 < SMA200 (bearish)"
    # code=0, rule_name="sma50_sma200", description="SMA50 = SMA200 (neutral)"


class CombinationResult(Base):
    """Результаты анализа комбинаций индикаторов"""

    __tablename__ = "combination_results"

    # Основные ключи
    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)  # timestamp в секундах
    combination_name = Column(String, primary_key=True)

    # Результаты анализа
    signal_strength = Column(Numeric, nullable=True)  # Сила сигнала (0-1)
    agreement_count = Column(
        SmallInteger, nullable=True
    )  # Количество согласованных сигналов
    conflict_count = Column(
        SmallInteger, nullable=True
    )  # Количество конфликтующих сигналов

    # Рекомендации
    recommendation = Column(String, nullable=True)  # Основная рекомендация
    trading_action = Column(String, nullable=True)  # Торговое действие
    risk_assessment = Column(String, nullable=True)  # Оценка риска
    timeframe_advice = Column(String, nullable=True)  # Совет по таймфрейму
    confidence_level = Column(String, nullable=True)  # Уровень уверенности

    # Метаданные
    indicators_used = Column(
        String, nullable=True
    )  # JSON список использованных индикаторов
    calculated_at = Column(DateTime(timezone=True), nullable=True)  # Время расчета


class CalculationMetadata(Base):
    """
    Metadata for feature calculations to enable ML model reproducibility.

    This table stores information about each calculation run, allowing ML engineers
    to track which version of algorithms was used and reproduce results exactly.

    Usage:
        - Create snapshot before calculation starts
        - Update with results after calculation completes
        - Query to find calculations by version/date/config
    """

    __tablename__ = "calculation_metadata"

    # Primary key: unique snapshot identifier
    snapshot_id = Column(String(50), primary_key=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Versioning information
    algorithm_version = Column(String(20), nullable=False)  # e.g. "1.0.0"
    module_version = Column(
        String(20), nullable=False, default="1.0.0"
    )  # features module version

    # Configuration (stored as JSON text)
    config = Column(String, nullable=False)  # JSON: calculation parameters

    # Scope of calculation
    symbols = Column(String, nullable=True)  # Array as JSON string
    timeframes = Column(String, nullable=True)  # Array as JSON string

    # Execution status
    status = Column(String(20), nullable=False, default="in_progress")
    # status values: 'in_progress', 'completed', 'failed', 'cancelled'

    # Statistics
    rows_calculated = Column(BigInteger, default=0)
    execution_duration_seconds = Column(Numeric(10, 2), nullable=True)

    # Error tracking
    error_message = Column(String, nullable=True)
