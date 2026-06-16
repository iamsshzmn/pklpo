from __future__ import annotations

import asyncio

import pytest

from src.logging.context import get_current_context, get_current_run_id, set_log_context


def test_set_log_context_restores_nested_context() -> None:
    with set_log_context(
        run_id="outer-run",
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        component="swap_sync",
        task_id="outer-task",
    ):
        with set_log_context(
            run_id="inner-run",
            symbol="ETH-USDT-SWAP",
            timeframe="5m",
            component="features",
            task_id="inner-task",
        ):
            assert get_current_context() == {
                "run_id": "inner-run",
                "symbol": "ETH-USDT-SWAP",
                "timeframe": "5m",
                "component": "features",
                "task_id": "inner-task",
            }

        assert get_current_context() == {
            "run_id": "outer-run",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "component": "swap_sync",
            "task_id": "outer-task",
        }

    assert get_current_run_id() is None


def test_log_context_is_isolated_between_concurrent_async_tasks() -> None:
    async def run_workers() -> dict[str, dict[str, str | None]]:
        release = asyncio.Event()
        results: dict[str, dict[str, str | None]] = {}

        async def worker(name: str, run_id: str, symbol: str) -> None:
            with set_log_context(
                run_id=run_id,
                symbol=symbol,
                timeframe="1m",
                component="swap_sync",
            ):
                await release.wait()
                results[name] = get_current_context()

        left = asyncio.create_task(worker("left", "run-left", "BTC-USDT-SWAP"))
        right = asyncio.create_task(worker("right", "run-right", "ETH-USDT-SWAP"))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(left, right)
        return results

    results = asyncio.run(run_workers())

    assert results["left"]["run_id"] == "run-left"
    assert results["left"]["symbol"] == "BTC-USDT-SWAP"
    assert results["right"]["run_id"] == "run-right"
    assert results["right"]["symbol"] == "ETH-USDT-SWAP"
    assert get_current_run_id() is None
