import pytest
from pydantic import ValidationError

from src.config import FeaturesSettings


def test_features_settings_accepts_valid_ta_backend_from_env(monkeypatch):
    monkeypatch.setenv("FEATURES_TA_BACKEND", "talib")
    settings = FeaturesSettings()
    assert settings.ta_backend == "talib"


def test_features_settings_rejects_invalid_ta_backend():
    with pytest.raises(ValidationError):
        FeaturesSettings(ta_backend="invalid-backend")

