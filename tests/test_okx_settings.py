from src.config.settings import OKXSettings


def test_okx_settings_week_anchor_defaults_to_none(monkeypatch):
    monkeypatch.delenv("OKX_WEEK_ANCHOR_TS_MS", raising=False)
    settings = OKXSettings()
    assert settings.week_anchor_ts_ms is None


def test_okx_settings_reads_week_anchor_from_env(monkeypatch):
    monkeypatch.setenv("OKX_WEEK_ANCHOR_TS_MS", "1234567890000")
    settings = OKXSettings()
    assert settings.week_anchor_ts_ms == 1234567890000
