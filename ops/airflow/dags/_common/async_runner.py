"""Shared asyncio helpers for Airflow DAG task callables."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Return a usable event loop, creating one when the current loop is closed."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def run_coroutine(coro: Awaitable[Any]) -> Any:
    """Run an awaitable on the shared loop and return its result."""
    return get_or_create_event_loop().run_until_complete(coro)
