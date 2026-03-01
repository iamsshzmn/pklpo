"""
OKX API client for market data integration
"""

import asyncio
import base64
import hashlib
import hmac
import time
from typing import Any

import aiohttp
import pandas as pd

from ..logging_config import create_log_context, get_integration_logger

logger = get_integration_logger()


class OKXClient:
    """Клиент для работы с OKX API"""

    def __init__(
        self, api_key: str, secret_key: str, passphrase: str, sandbox: bool = False
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.sandbox = sandbox

        # URL для API
        if sandbox:
            self.base_url = "https://www.okx.com"
        else:
            self.base_url = "https://www.okx.com"

        # Сессия для HTTP запросов
        self.session: aiohttp.ClientSession | None = None

        # Rate limiting
        self.rate_limit = 20  # запросов в секунду
        self.last_request_time = 0.0

        logger.info(f"OKXClient initialized (sandbox: {sandbox})")

    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход"""
        if self.session:
            await self.session.close()

    async def _rate_limit_wait(self):
        """Ожидание для соблюдения rate limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.rate_limit

        if time_since_last < min_interval:
            await asyncio.sleep(min_interval - time_since_last)

        self.last_request_time = time.time()

    def _generate_signature(
        self, timestamp: str, method: str, request_path: str, body: str = ""
    ) -> str:
        """Генерация подписи для API запроса"""
        message = timestamp + method.upper() + request_path + body
        signature = hmac.new(
            self.secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode("utf-8")

    def _get_headers(
        self, method: str, request_path: str, body: str = ""
    ) -> dict[str, str]:
        """Получение заголовков для API запроса"""
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(timestamp, method, request_path, body)

        return {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        data: dict | None = None,
    ) -> dict[str, Any]:
        """Выполнение HTTP запроса к API"""
        await self._rate_limit_wait()

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(method, endpoint, str(data) if data else "")

        try:
            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response_data = await response.json()

                if response.status == 200:
                    return response_data
                error_msg = f"API request failed: {response.status} - {response_data}"
                logger.error(error_msg)
                raise Exception(error_msg)

        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

    async def get_instruments(self, inst_type: str = "SPOT") -> list[dict[str, Any]]:
        """Получение списка инструментов"""
        with create_log_context("okx_client", "get_instruments"):
            endpoint = "/api/v5/public/instruments"
            params = {"instType": inst_type}

            response = await self._make_request("GET", endpoint, params=params)
            return response.get("data", [])

    async def get_ticker(self, inst_id: str) -> dict[str, Any]:
        """Получение тикера для инструмента"""
        with create_log_context("okx_client", "get_ticker"):
            endpoint = "/api/v5/market/ticker"
            params = {"instId": inst_id}

            response = await self._make_request("GET", endpoint, params=params)
            data = response.get("data", [])
            return data[0] if data else {}

    async def get_klines(
        self, inst_id: str, bar: str = "1m", limit: int = 100
    ) -> list[list[str]]:
        """Получение свечных данных"""
        with create_log_context("okx_client", "get_klines"):
            endpoint = "/api/v5/market/candles"
            params = {"instId": inst_id, "bar": bar, "limit": str(limit)}

            response = await self._make_request("GET", endpoint, params=params)
            return response.get("data", [])

    async def get_klines_dataframe(
        self, inst_id: str, bar: str = "1m", limit: int = 100
    ) -> pd.DataFrame:
        """Получение свечных данных в формате DataFrame"""
        klines = await self.get_klines(inst_id, bar, limit)

        if not klines:
            return pd.DataFrame()

        # Преобразование в DataFrame
        df = pd.DataFrame(
            klines,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "vol_ccy",
                "vol_ccy_quote",
                "confirm",
            ],
        )

        # Преобразование типов данных
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["open"] = pd.to_numeric(df["open"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["close"] = pd.to_numeric(df["close"])
        df["volume"] = pd.to_numeric(df["volume"])

        # Установка индекса
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)

        return df

    async def get_market_data(
        self, symbol: str, timeframes: list[str], limit: int = 100
    ) -> dict[str, pd.DataFrame]:
        """Получение рыночных данных для нескольких таймфреймов"""
        with create_log_context("okx_client", "get_market_data"):
            results = {}

            # Маппинг таймфреймов OKX
            timeframe_mapping = {
                "1m": "1m",
                "5m": "5m",
                "15m": "15m",
                "1H": "1H",
                "4H": "4H",
                "1D": "1D",
            }

            for tf in timeframes:
                okx_tf = timeframe_mapping.get(tf, "1m")
                try:
                    df = await self.get_klines_dataframe(symbol, okx_tf, limit)
                    if not df.empty:
                        results[tf] = df
                        logger.info(f"Retrieved {len(df)} candles for {symbol} {tf}")
                    else:
                        logger.warning(f"No data received for {symbol} {tf}")
                except Exception as e:
                    logger.error(f"Failed to get data for {symbol} {tf}: {e}")

            return results

    async def get_account_balance(self) -> dict[str, Any]:
        """Получение баланса аккаунта"""
        with create_log_context("okx_client", "get_account_balance"):
            endpoint = "/api/v5/account/balance"
            response = await self._make_request("GET", endpoint)
            return response.get("data", [])

    async def get_positions(self) -> list[dict[str, Any]]:
        """Получение позиций"""
        with create_log_context("okx_client", "get_positions"):
            endpoint = "/api/v5/account/positions"
            response = await self._make_request("GET", endpoint)
            return response.get("data", [])

    async def health_check(self) -> dict[str, Any]:
        """Проверка здоровья API"""
        try:
            # Простой запрос для проверки доступности
            instruments = await self.get_instruments()
            return {
                "status": "healthy",
                "instruments_count": len(instruments),
                "api_accessible": True,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "api_accessible": False}
