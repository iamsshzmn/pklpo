from __future__ import annotations

import importlib
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_tqdm() -> None:
    fake_tqdm = types.ModuleType("tqdm")
    fake_tqdm.tqdm = object()
    sys.modules.setdefault("tqdm", fake_tqdm)


@pytest.mark.smoke
@pytest.mark.parametrize(
    "module_name",
    [
        "src.candles",
        "src.candles.application",
        "src.candles.application.quality_checks",
        "src.candles.application.quality_pipeline",
        "src.candles.application.sync",
        "src.candles.domain.metadata",
        "src.candles.domain.policies",
        "src.candles.domain.quality",
        "src.candles.infrastructure.config",
        "src.candles.infrastructure.sqlalchemy_pool_adapter",
        "src.candles.interfaces.swap_sync",
    ],
)
def test_canonical_candles_modules_import(module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert module is not None


@pytest.mark.parametrize(
    "module_name",
    [
        "src.market_meta.api",  # no .api sub-module in new market_meta
        "src.candles.sync_swap_candles",
        "src.candles.swap_cli",
        "src.candles.parity_check",
    ],
)
def test_removed_transitional_modules_are_not_importable(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
