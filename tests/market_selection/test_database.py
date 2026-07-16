"""
Тесты для database operations (инфраструктура БД).
"""

from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest

from src.market_selection.config import MarketSelectionConfig
from src.market_selection.infrastructure.database import MarketSelectionDB


@pytest.fixture
def config():
    """Фикстура конфигурации."""
    return MarketSelectionConfig()


@pytest.fixture
def mock_session():
    """Фикстура мок-сессии БД."""
    return AsyncMock()


@pytest.fixture
def db(mock_session, config):
    """Фикстура MarketSelectionDB."""
    return MarketSelectionDB(mock_session, config)


def create_mock_result(rows: list):
    """Создать мок результата запроса."""
    result = Mock()
    result.fetchone = Mock(return_value=rows[0] if rows else None)
    result.fetchall = Mock(return_value=rows)
    result.rowcount = len(rows)
    return result


@pytest.mark.asyncio
async def test_get_max_timestamp(db, mock_session):
    """Тест получения максимального timestamp."""
    # Мок результата запроса
    mock_result = create_mock_result([(1000000,)])
    mock_session.execute = AsyncMock(return_value=mock_result)

    max_ts = await db.get_max_timestamp("1H")

    assert max_ts == 1000000
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_max_timestamp_none(db, mock_session):
    """Тест получения timestamp при отсутствии данных."""
    mock_result = create_mock_result([(None,)])
    mock_session.execute = AsyncMock(return_value=mock_result)

    max_ts = await db.get_max_timestamp("1H")

    assert max_ts is None


@pytest.mark.asyncio
async def test_resolve_ts_eval(db, mock_session):
    """Тест определения ts_eval."""
    # Моки для разных таймфреймов
    results = {
        "5m": create_mock_result([(1000000,)]),
        "15m": create_mock_result([(1000100,)]),
        "1H": create_mock_result([(1000200,)]),
        "4H": create_mock_result([(1000300,)]),
    }

    async def mock_execute(query, params):
        tf = params.get("tf")
        return results.get(tf, create_mock_result([(None,)]))

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    ts_eval = await db.resolve_ts_eval()

    # Должен вернуть минимальный timestamp
    assert ts_eval == 1000000


@pytest.mark.asyncio
async def test_resolve_ts_eval_no_data(db, mock_session):
    """Тест определения ts_eval при отсутствии данных."""
    mock_result = create_mock_result([(None,)])
    mock_session.execute = AsyncMock(return_value=mock_result)

    ts_eval = await db.resolve_ts_eval()

    assert ts_eval is None


@pytest.mark.asyncio
async def test_validate_short_features_valid(db, mock_session):
    """Тест валидации фич - все фичи присутствуют."""
    # Мок существующих колонок
    existing_columns = set(db.config.short_feature_set)
    mock_rows = [(col,) for col in existing_columns]

    mock_result = create_mock_result(mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    is_valid, missing = await db.validate_short_features()

    assert is_valid is True
    assert len(missing) == 0


@pytest.mark.asyncio
async def test_validate_short_features_missing(db, mock_session):
    """Тест валидации фич - некоторые фичи отсутствуют."""
    # Убираем несколько фич
    existing_columns = set(db.config.short_feature_set) - {"ema_21", "ema_55"}
    mock_rows = [(col,) for col in existing_columns]

    mock_result = create_mock_result(mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    _is_valid, missing = await db.validate_short_features()

    # Должно быть валидно, если missing <= max_missing_features (2)
    assert len(missing) == 2
    assert "ema_21" in missing
    assert "ema_55" in missing


@pytest.mark.asyncio
async def test_fetch_quality_data(db, mock_session):
    """Тест получения данных для quality gate."""
    mock_rows = [
        ("BTC-USDT", 1000, 5, 1000000, 950, True),
        ("ETH-USDT", 800, 3, 999000, 780, True),
    ]

    mock_result = create_mock_result(mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    df = await db.fetch_quality_data("1H", 1000000)

    assert len(df) == 2
    assert "symbol" in df.columns
    assert "valid_bars" in df.columns
    assert "gaps_count" in df.columns
    assert df.iloc[0]["symbol"] == "BTC-USDT"


@pytest.mark.asyncio
async def test_fetch_quality_data_empty(db, mock_session):
    """Тест получения данных quality gate при отсутствии данных."""
    mock_result = create_mock_result([])
    mock_session.execute = AsyncMock(return_value=mock_result)

    df = await db.fetch_quality_data("1H", 1000000)

    assert df.empty


@pytest.mark.asyncio
async def test_fetch_pair_metrics_data(db, mock_session):
    """Тест получения данных для расчета метрик пар."""
    mock_rows = [
        ("BTC-USDT", 1000000, 50000.0, 1000000.0, None, 0.02, 25.0, 50000.0),
        ("BTC-USDT", 1000060, 50100.0, 1100000.0, 50000.0, 0.021, 26.0, 50050.0),
    ]

    mock_result = create_mock_result(mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    df = await db.fetch_pair_metrics_data("1H", 1000000)

    assert len(df) == 2
    assert "symbol" in df.columns
    assert "close" in df.columns
    assert "atr_14" in df.columns
    assert "adx_14" in df.columns


@pytest.mark.asyncio
async def test_fetch_pair_metrics_data_handles_decimal_values(db, mock_session):
    mock_rows = [
        (
            "BTC-USDT",
            1000000,
            Decimal("50000.0"),
            Decimal("1000000.0"),
            Decimal("49900.0"),
            Decimal("0.02"),
            Decimal("25.0"),
            Decimal("50000.0"),
        ),
    ]

    mock_result = create_mock_result(mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    df = await db.fetch_pair_metrics_data("1H", 1000000)

    assert len(df) == 1
    assert isinstance(df.iloc[0]["close"], float)
    assert isinstance(df.iloc[0]["ema"], float)


@pytest.mark.asyncio
async def test_fetch_basket_volume_data(db, mock_session):
    """Тест получения данных объема для корзины."""
    mock_rows = [
        ("BTC-USDT", 1000000.0),
        ("ETH-USDT", 800000.0),
        ("SOL-USDT", 600000.0),
    ]

    mock_result = create_mock_result(mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    df = await db.fetch_basket_volume_data("4H", 1000000, window_days=30)

    assert len(df) == 3
    assert "symbol" in df.columns
    assert "volume_median" in df.columns
    assert df.iloc[0]["symbol"] == "BTC-USDT"
    assert df.iloc[0]["volume_median"] == 1000000.0


@pytest.mark.asyncio
async def test_fetch_regime_metrics(db, mock_session):
    """Тест получения метрик режима."""
    # Мок данных для расчета метрик (минимум 10 баров для каждого символа)
    mock_rows = []
    # BTC-USDT: 15 баров
    for i in range(15):
        mock_rows.append(
            (
                "BTC-USDT",
                1000000 + i * 60000,
                25.0 + i * 0.1,
                0.02 + i * 0.001,
                50000.0 + i * 10.0,
                50000.0 + i * 10.0,
                1000000.0 + i * 10000.0,
            )
        )
    # ETH-USDT: 12 баров
    for i in range(12):
        mock_rows.append(
            (
                "ETH-USDT",
                1000000 + i * 60000,
                20.0 + i * 0.1,
                0.015 + i * 0.0005,
                3000.0 + i * 5.0,
                3000.0 + i * 5.0,
                800000.0 + i * 5000.0,
            )
        )

    mock_result = create_mock_result(mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    df = await db.fetch_regime_metrics("1H", 1000000, ["BTC-USDT", "ETH-USDT"])

    assert (
        len(df) >= 1
    )  # Должен быть хотя бы один символ с достаточным количеством баров
    assert "symbol" in df.columns
    assert "adx_median" in df.columns
    assert "atr_close_ratio" in df.columns
    assert "ema_slope" in df.columns


@pytest.mark.asyncio
async def test_fetch_regime_metrics_handles_decimal_ema(db, mock_session):
    """Р•РњРђ РјРѕР¶РµС‚ РїСЂРёС…РѕРґРёС‚СЊ РєР°Рє Decimal Рё РЅРµ РґРѕР»Р¶РЅР° Р»РѕРјР°С‚СЊ slope."""
    mock_rows = []
    for i in range(12):
        mock_rows.append(
            (
                "BTC-USDT",
                1000000 + i * 60000,
                25.0 + i * 0.1,
                0.02 + i * 0.001,
                Decimal("50000.0") + Decimal(str(i)),
                50000.0 + i * 10.0,
                1000000.0 + i * 10000.0,
            )
        )

    mock_result = create_mock_result(mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    df = await db.fetch_regime_metrics("1H", 1000000, ["BTC-USDT"])

    assert not df.empty
    assert isinstance(df.iloc[0]["ema_slope"], float)


@pytest.mark.asyncio
async def test_fetch_atr_percentile(db, mock_session):
    """Тест получения перцентиля ATR."""
    mock_result = create_mock_result([(0.03,)])
    mock_session.execute = AsyncMock(return_value=mock_result)

    percentile = await db.fetch_atr_percentile("1H", 1000000, percentile=80)

    assert percentile == 0.03


@pytest.mark.asyncio
async def test_fetch_atr_percentile_default(db, mock_session):
    """Тест получения перцентиля ATR при отсутствии данных."""
    mock_result = create_mock_result([(None,)])
    mock_session.execute = AsyncMock(return_value=mock_result)

    percentile = await db.fetch_atr_percentile("1H", 1000000)

    assert percentile == 0.02  # Дефолтное значение


@pytest.mark.asyncio
async def test_fetch_previous_universe(db, mock_session):
    """Тест получения предыдущей вселенной."""
    mock_rows = [
        ("BTC-USDT",),
        ("ETH-USDT",),
        ("SOL-USDT",),
    ]

    mock_result = create_mock_result(mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    universe = await db.fetch_previous_universe()

    assert isinstance(universe, set)
    assert len(universe) == 3
    assert "BTC-USDT" in universe


@pytest.mark.asyncio
async def test_fetch_score_history(db, mock_session):
    """Тест получения истории оценок."""
    mock_rows = [
        ("BTC-USDT", 0.9),
        ("BTC-USDT", 0.88),
        ("BTC-USDT", 0.91),
        ("ETH-USDT", 0.8),
        ("ETH-USDT", 0.82),
    ]

    mock_result = create_mock_result(mock_rows)
    mock_session.execute = AsyncMock(return_value=mock_result)

    history = await db.fetch_score_history(["BTC-USDT", "ETH-USDT"], days=30)

    assert isinstance(history, dict)
    assert "BTC-USDT" in history
    assert len(history["BTC-USDT"]) == 3
    assert history["BTC-USDT"][0] == 0.9


@pytest.mark.asyncio
async def test_get_last_published_version(db, mock_session):
    """Тест получения последней опубликованной версии."""
    mock_result = create_mock_result([(1000000,)])
    mock_session.execute = AsyncMock(return_value=mock_result)

    version = await db.get_last_published_version()

    assert version == 1000000


@pytest.mark.asyncio
async def test_get_last_published_version_none(db, mock_session):
    """Тест получения версии при отсутствии опубликованных."""
    mock_result = create_mock_result([])
    mock_session.execute = AsyncMock(return_value=mock_result)

    version = await db.get_last_published_version()

    assert version is None


@pytest.mark.asyncio
async def test_get_last_valid_regime(db, mock_session):
    """Тест получения последнего валидного режима."""
    mock_row = (
        1000000,  # ts_eval
        "TREND_UP",  # global_regime
        0.8,  # global_strength
        0.9,  # regime_confidence
        "TREND_UP",  # regime_1d
        0.75,  # regime_1d_strength
        "TREND_UP",  # regime_4h
        0.8,  # regime_4h_strength
        "TREND_UP",  # regime_1h
        0.7,  # regime_1h_strength
        20,  # basket_size
        ["BTC-USDT", "ETH-USDT"],  # basket_symbols
        25.0,  # basket_adx_median
        0.02,  # basket_atr_close_median
        0.001,  # basket_ema_slope_median
    )

    mock_result = create_mock_result([mock_row])
    mock_session.execute = AsyncMock(return_value=mock_result)

    regime = await db.get_last_valid_regime()

    assert regime is not None
    assert regime["ts_eval"] == 1000000
    assert regime["global_regime"] == "TREND_UP"
    assert regime["global_strength"] == 0.8


@pytest.mark.asyncio
async def test_check_regime_tf_lag(db, mock_session):
    """Тест проверки лага данных для режима."""
    mock_result = create_mock_result([(999000,)])  # max_ts
    mock_session.execute = AsyncMock(return_value=mock_result)

    lag = await db.check_regime_tf_lag("1H", 1000000)

    # lag = (1000000 - 999000) / 1000 = 1 секунда
    assert lag == 1


@pytest.mark.asyncio
async def test_check_regime_tf_lag_no_data(db, mock_session):
    """Тест проверки лага при отсутствии данных."""
    mock_result = create_mock_result([(None,)])
    mock_session.execute = AsyncMock(return_value=mock_result)

    lag = await db.check_regime_tf_lag("1H", 1000000)

    assert lag == 999999  # Очень большой лаг
