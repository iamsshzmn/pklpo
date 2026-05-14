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

    def get_public_limiter(self) -> AsyncLimiter:
        return self._public_limiter

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
            # Auto-initialize session if not using context manager
            self._session = aiohttp.ClientSession(
                base_url=self._base_url,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
                raise_for_status=True,
                headers={"Accept": "application/json"},
            )
        # Acquire all applicable rate limiters BEFORE the request
        limiters: list[AsyncLimiter] = []
        if is_public:
            limiters.append(self._public_limiter)
        if symbol:
            limiters.append(self.get_instrument_limiter(symbol))
        if is_order:
            limiters.extend([self._account_limiter] * order_count)

        return await self._execute_with_limiters(method, path, params, limiters)

    async def _execute_with_limiters(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None,
        limiters: list[AsyncLimiter],
    ) -> dict[str, Any]:
        """Execute request inside all rate limiter contexts."""
        if limiters:
            async with limiters[0]:
                return await self._execute_with_limiters(
                    method, path, params, limiters[1:]
                )

        assert self._session is not None
        async with self._session.request(method, path, params=params) as resp:
            payload = await resp.json()
            logger.debug(
                "OKX response %s %s: code=%s", method, path, payload.get("code")
            )
            return payload
