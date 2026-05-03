from src.config.settings import OKXSettings


def test_okx_settings_week_anchor_uses_code_placeholder(monkeypatch):
    monkeypatch.delenv("OKX_WEEK_ANCHOR_TS_MS", raising=False)
    settings = OKXSettings()
    assert settings.week_anchor_ts_ms == 0


def test_okx_settings_ignores_week_anchor_env_override(monkeypatch):
    monkeypatch.setenv("OKX_WEEK_ANCHOR_TS_MS", "1234567890000")
    settings = OKXSettings()
    assert settings.week_anchor_ts_ms == 0
