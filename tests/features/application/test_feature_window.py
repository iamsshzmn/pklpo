from src.features.application.feature_window import limit_for_timeframe


def test_1m_feature_window_stays_within_hot_retention_buffer() -> None:
    assert limit_for_timeframe("1m") == 2880
