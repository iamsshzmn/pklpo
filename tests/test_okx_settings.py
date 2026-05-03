from pathlib import Path

from src.config.settings import OKXSettings, reload_settings


def test_okx_settings_week_anchor_uses_code_placeholder(monkeypatch):
    monkeypatch.delenv("OKX_WEEK_ANCHOR_TS_MS", raising=False)
    settings = OKXSettings()
    assert settings.week_anchor_ts_ms == 0


def test_okx_settings_ignores_week_anchor_env_override(monkeypatch):
    monkeypatch.setenv("OKX_WEEK_ANCHOR_TS_MS", "1234567890000")
    settings = OKXSettings()
    assert settings.week_anchor_ts_ms == 0


def test_okx_settings_still_reads_other_env_values(monkeypatch):
    monkeypatch.setenv("OKX_API_KEY", "live-key")
    monkeypatch.setenv("OKX_BASE_URL", "https://example.test")

    settings = OKXSettings()

    assert settings.api_key.get_secret_value() == "live-key"
    assert settings.base_url == "https://example.test"


def test_okx_settings_ignores_week_anchor_dotenv_override(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("OKX_WEEK_ANCHOR_TS_MS=1234567890000\n", encoding="utf-8")

    settings = OKXSettings(_env_file=env_file)

    assert settings.week_anchor_ts_ms == 0


def test_okx_settings_still_reads_other_dotenv_values(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OKX_WEEK_ANCHOR_TS_MS=1234567890000\n"
        "OKX_API_KEY=dotenv-key\n"
        "OKX_BASE_URL=https://dotenv.test\n",
        encoding="utf-8",
    )

    settings = OKXSettings(_env_file=env_file)

    assert settings.week_anchor_ts_ms == 0
    assert settings.api_key.get_secret_value() == "dotenv-key"
    assert settings.base_url == "https://dotenv.test"


def test_reload_settings_ignores_week_anchor_env_override(monkeypatch):
    monkeypatch.setenv("OKX_WEEK_ANCHOR_TS_MS", "1234567890000")

    settings = reload_settings()

    assert settings.okx.week_anchor_ts_ms == 0
