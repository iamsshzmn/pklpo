import json
import os
from typing import Any

import aiohttp
from aiolimiter import AsyncLimiter
from dotenv import load_dotenv

from .logging_config import get_logger

load_dotenv()

OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_API_SECRET = os.getenv("OKX_API_SECRET")
OKX_API_PASSPHRASE = os.getenv("OKX_API_PASSPHRASE")
OKX_BASE_URL = os.getenv("OKX_BASE_URL", "https://www.okx.com")

logger = get_logger("client")


class OKXClient:
    def __init__(
        self,
        *,
        timeout: int = 30,
        session: aiohttp.ClientSession | None = None,
        base_url: str | None = None,
        instrument_limiter: dict | None = None,
        public_limiter: AsyncLimiter | None = None,
        account_limiter: AsyncLimiter | None = None,
    ):
        self._external_session = session
        self._session: aiohttp.ClientSession | None = session
        self._timeout = timeout
        self._base_url = base_url or OKX_BASE_URL
        self._public_limiter = public_limiter or AsyncLimiter(90, 1)
        self._account_limiter = account_limiter or AsyncLimiter(450, 1)
        self._instrument_limiters = instrument_limiter or {}

    def get_instrument_limiter(self, symbol):
        if symbol not in self._instrument_limiters:
            self._instrument_limiters[symbol] = AsyncLimiter(27, 1)
        return self._instrument_limiters[symbol]

    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession(
                base_url=self._base_url,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
                raise_for_status=True,
                headers={"Accept": "application/json"},
            )
        return self

    async def __aexit__(self, *exc):
        if not self._external_session and self._session:
            await self._session.close()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        symbol: str | None = None,
        is_public: bool = False,
        is_order: bool = False,
        order_count: int = 1,
    ) -> dict[str, Any]:
        if self._session is None:
            # Автоматическая инициализация сессии, если не используется контекстный менеджер
            self._session = aiohttp.ClientSession(
                base_url=self._base_url,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
                raise_for_status=True,
                headers={"Accept": "application/json"},
            )
        if is_public:
            async with self._public_limiter:
                pass
        if symbol:
            async with self.get_instrument_limiter(symbol):
                pass
        if is_order:
            for _ in range(order_count):
                async with self._account_limiter:
                    pass
        async with self._session.request(method, path, params=params) as resp:
            payload = await resp.json()
            try:
                with open("debug_okx_response.json", "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Error saving debug response: {e}")

            return payload
