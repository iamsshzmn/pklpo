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

from src.features.storage_contract import IndicatorStorageContract

Base = declarative_base()
INDICATORS_TABLE_NAME = IndicatorStorageContract.table_name


class SwapOhlcvP(Base):
    __tablename__ = "swap_ohlcv_p"

    symbol = Column(String(50), primary_key=True)
    timeframe = Column(String(20), primary_key=True)
    timestamp = Column(BigInteger, primary_key=True)  # milliseconds
    open = Column(Numeric(20, 8), nullable=False)
    high = Column(Numeric(20, 8), nullable=False)
    low = Column(Numeric(20, 8), nullable=False)
    close = Column(Numeric(20, 8), nullable=False)
    volume = Column(Numeric(30, 8), nullable=False)
    vol_ccy = Column(Numeric(30, 8), nullable=True)
    vol_usd = Column(Numeric(30, 8), nullable=True)
    funding_rate = Column(Numeric(10, 8), nullable=True)
    open_interest = Column(Numeric(30, 8), nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)


class Instrument(Base):
    __tablename__ = "instruments"

    symbol = Column(String, primary_key=True)
    inst_id = Column(String, unique=True, nullable=False)
    base_ccy = Column(String, nullable=True)
    quote_ccy = Column(String, nullable=True)
    inst_type = Column(String, nullable=True)
    uly = Column(String, nullable=True)
    ct_val_ccy = Column(String, nullable=True)
    ct_val = Column(Float, nullable=True)
    lever = Column(Float, nullable=True)
    state = Column(String, nullable=True)
    list_time = Column(BigInteger, nullable=True)  # listing time in ms
    metadata_refreshed_at_ms = Column(
        BigInteger, nullable=True
    )  # persisted catalog refresh time in ms

    # Swap-specific fields
    contract_val = Column(Float, nullable=True)
    settle_ccy = Column(String, nullable=True)  # settlement currency
    ct_type = Column(String, nullable=True)  # linear or inverse
    min_sz = Column(Float, nullable=True)  # min order size in contracts
    max_sz = Column(Float, nullable=True)  # max order size
    min_notional = Column(Float, nullable=True)  # min trade size in USD


class OHLCV(Base):
    __tablename__ = "ohlcv"
    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)  # timestamp in ms
    open = Column(Numeric)
    high = Column(Numeric)
    low = Column(Numeric)
    close = Column(Numeric)
    volume = Column(Numeric)
    volCcy = Column(Numeric, nullable=True)
    volUsd = Column(Numeric, nullable=True)
    fetched_at = Column(DateTime, nullable=True)


class Signal(Base):
    __tablename__ = "signals"
    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)  # timestamp in ms
    signal = Column(Numeric)  # -1 = sell, 0 = hold, 1 = buy
    reason = Column(String, nullable=True)  # JSON: which rules triggered
    created_at = Column(DateTime, nullable=True)


class SignalDetailed(Base):
    """Detailed signals table with separate columns per rule."""

    __tablename__ = "signals_detailed"

    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)  # timestamp in seconds

    signal = Column(SmallInteger)  # -1 = sell, 0 = hold, 1 = buy
    total_score = Column(Numeric, nullable=True)

    # Per-rule signals (text): "bullish", "bearish", "neutral"
    sma50_sma200 = Column(String, nullable=True)
    ema21_sma50 = Column(String, nullable=True)
    macd = Column(String, nullable=True)
    rsi14 = Column(String, nullable=True)
    bollinger = Column(String, nullable=True)
    stochastic = Column(String, nullable=True)
    adx14 = Column(String, nullable=True)
    ichimoku = Column(String, nullable=True)
    keltner = Column(String, nullable=True)
    volume_obv_cmf = Column(String, nullable=True)

    # Per-rule numeric scores
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

    created_at = Column(DateTime, nullable=True)


class SignalRuleCodes(Base):
    """Rule code lookup for numeric representation."""

    __tablename__ = "signal_rule_codes"

    code = Column(SmallInteger, primary_key=True)
    rule_name = Column(String, nullable=False)
    description = Column(String, nullable=True)


class CombinationResult(Base):
    """Indicator combination analysis results."""

    __tablename__ = "combination_results"

    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)  # timestamp in seconds
    combination_name = Column(String, primary_key=True)

    signal_strength = Column(Numeric, nullable=True)  # 0-1
    agreement_count = Column(SmallInteger, nullable=True)
    conflict_count = Column(SmallInteger, nullable=True)

    recommendation = Column(String, nullable=True)
    trading_action = Column(String, nullable=True)
    risk_assessment = Column(String, nullable=True)
    timeframe_advice = Column(String, nullable=True)
    confidence_level = Column(String, nullable=True)

    indicators_used = Column(String, nullable=True)  # JSON list
    calculated_at = Column(DateTime(timezone=True), nullable=True)
