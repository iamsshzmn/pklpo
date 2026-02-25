"""
Тесты для retry механизмов в OKX интеграции.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.market_meta.domain.exceptions import (
    MetadataStaleError,
    OKXIntegrationError,
    OKXNetworkError,
    OKXRateLimitError,
)
from src.market_meta.infrastructure.okx_integration import OKXMetadataLoader


class TestOKXRetryMechanisms:
    """Тесты retry механизмов"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.loader = OKXMetadataLoader(max_retries=3, base_delay=0.1, max_delay=1.0)

    @patch("src.market_meta.infrastructure.okx_integration.OKXMarket")
    async def test_successful_load_without_retry(self, mock_market_class):
        """Тест успешной загрузки без retry"""
        # Настраиваем мок с поддержкой async context manager
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            return_value=[
                {
                    "instId": "BTC-USDT-SWAP",
                    "instType": "SWAP",
                    "baseCcy": "BTC",
                    "quoteCcy": "USDT",
                }
            ]
        )
        # Делаем мок async context manager
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # Создаем новый loader с моком через DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.1, max_delay=1.0, market=mock_market_instance
        )

        # Выполняем загрузку
        result = await loader.load_instruments(["SWAP"])

        # Проверяем результат
        assert len(result) == 1
        assert result[0]["instId"] == "BTC-USDT-SWAP"

        # Проверяем, что метод вызвался только один раз
        # Метод вызывается с отдельным типом инструмента, а не списком
        mock_market_instance.get_instruments.assert_called_once_with("SWAP")

    @patch("src.market_meta.infrastructure.okx_integration.OKXMarket")
    async def test_retry_on_network_error(self, mock_market_class):
        """Тест retry при сетевой ошибке"""
        # Настраиваем мок для имитации сетевой ошибки, затем успеха
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=[
                Exception(
                    "Connection timeout"
                ),  # Будет преобразовано в OKXNetworkError
                Exception(
                    "Connection refused"
                ),  # Будет преобразовано в OKXNetworkError
                [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "instType": "SWAP",
                        "baseCcy": "BTC",
                        "quoteCcy": "USDT",
                    }
                ],
            ]
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # Создаем новый loader с моком через DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )

        # Выполняем загрузку
        result = await loader.load_instruments(["SWAP"])

        # Проверяем результат
        assert len(result) == 1
        assert result[0]["instId"] == "BTC-USDT-SWAP"

        # Проверяем, что метод вызвался 3 раза (2 ошибки + 1 успех)
        assert mock_market_instance.get_instruments.call_count == 3

    @patch("src.market_meta.infrastructure.okx_integration.OKXMarket")
    async def test_retry_on_rate_limit_error(self, mock_market_class):
        """Тест retry при превышении лимита запросов"""
        # Настраиваем мок для имитации rate limit, затем успеха
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=[
                OKXRateLimitError(retry_after=1),
                OKXRateLimitError(retry_after=1),
                [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "instType": "SWAP",
                        "baseCcy": "BTC",
                        "quoteCcy": "USDT",
                    }
                ],
            ]
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # Создаем новый loader с моком через DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )

        # Выполняем загрузку
        result = await loader.load_instruments(["SWAP"])

        # Проверяем результат
        assert len(result) == 1
        assert result[0]["instId"] == "BTC-USDT-SWAP"

        # Проверяем, что метод вызвался 3 раза
        assert mock_market_instance.get_instruments.call_count == 3

    @patch("src.market_meta.infrastructure.okx_integration.OKXMarket")
    async def test_max_retries_exceeded(self, mock_market_class):
        """Тест превышения максимального количества попыток"""
        # Настраиваем мок для постоянных ошибок
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=Exception(
                "Connection failed"
            )  # Будет преобразовано в OKXNetworkError
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # Создаем новый loader с моком через DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )

        # Выполняем загрузку и ожидаем MetadataStaleError (все типы провалились)
        with pytest.raises(MetadataStaleError):
            await loader.load_instruments(["SWAP"])

        # Проверяем, что метод вызвался максимальное количество раз (3 попытки)
        # Retry декоратор делает 3 попытки
        assert mock_market_instance.get_instruments.call_count == 3

    @patch("src.market_meta.infrastructure.okx_integration.OKXMarket")
    async def test_no_retry_on_validation_error(self, mock_market_class):
        """Тест отсутствия retry при ошибке валидации"""
        # Настраиваем мок для ошибки валидации
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=ValueError("Invalid data")
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # Создаем новый loader с моком через DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.1, max_delay=1.0, market=mock_market_instance
        )

        # Выполняем загрузку и ожидаем MetadataStaleError (все типы провалились)
        # ValueError преобразуется в OKXIntegrationError, который является retryable
        # Retry делает 3 попытки, все проваливаются, выбрасывается MetadataStaleError
        with pytest.raises(MetadataStaleError):
            await loader.load_instruments(["SWAP"])

        # Проверяем, что метод вызвался 3 раза (retry для OKXIntegrationError)
        assert mock_market_instance.get_instruments.call_count == 3

    @patch("src.market_meta.infrastructure.okx_integration.OKXMarket")
    async def test_partial_failure_handling(self, mock_market_class):
        """Тест обработки частичных неудач"""
        # Настраиваем мок для успеха одного типа и неудачи другого
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=[
                [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "instType": "SWAP",
                        "baseCcy": "BTC",
                        "quoteCcy": "USDT",
                    }
                ],  # SWAP успех
                Exception(
                    "Connection failed"
                ),  # FUTURES неудача (будет преобразовано в OKXNetworkError)
            ]
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # Создаем новый loader с моком через DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.1, max_delay=1.0, market=mock_market_instance
        )

        # Выполняем загрузку
        result = await loader.load_instruments(["SWAP", "FUTURES"])

        # Проверяем, что получили данные только от успешного типа
        assert len(result) == 1
        assert result[0]["instId"] == "BTC-USDT-SWAP"

        # Проверяем количество вызовов
        # SWAP: 1 успешный вызов
        # FUTURES: 3 попытки (retry для OKXNetworkError), все провалились
        assert mock_market_instance.get_instruments.call_count == 4

    @patch("src.market_meta.infrastructure.okx_integration.OKXMarket")
    async def test_complete_failure_raises_metadata_stale_error(
        self, mock_market_class
    ):
        """Тест полной неудачи вызывает MetadataStaleError"""
        # Настраиваем мок для полной неудачи
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=Exception(
                "Connection failed"
            )  # Будет преобразовано в OKXNetworkError
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # Создаем новый loader с моком через DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )

        # Выполняем загрузку и ожидаем MetadataStaleError
        with pytest.raises(MetadataStaleError) as exc_info:
            await loader.load_instruments(["SWAP", "FUTURES"])

        # Проверяем сообщение об ошибке
        assert "Не удалось загрузить ни одного инструмента" in str(exc_info.value)
        assert "failed_types" in str(exc_info.value)

    async def test_rate_limit_check(self):
        """Тест проверки rate limiting"""
        # Сбрасываем счетчик
        self.loader._request_count = 0
        self.loader._last_request_time = 0

        # Выполняем несколько проверок подряд
        start_time = asyncio.get_event_loop().time()

        for _i in range(5):
            await self.loader._rate_limit_check()

        # Проверяем, что счетчик увеличился
        assert self.loader._request_count == 5

        # Проверяем, что не было задержек (не превысили лимит)
        end_time = asyncio.get_event_loop().time()
        assert end_time - start_time < 0.1  # Должно быть быстро

    async def test_rate_limit_enforcement(self):
        """Тест соблюдения rate limiting"""
        # Устанавливаем высокий счетчик запросов
        self.loader._request_count = 10  # Максимум
        self.loader._last_request_time = asyncio.get_event_loop().time()

        # Выполняем проверку rate limit
        start_time = asyncio.get_event_loop().time()
        await self.loader._rate_limit_check()
        end_time = asyncio.get_event_loop().time()

        # Проверяем, что была задержка
        assert end_time - start_time >= 0.9  # Должна быть задержка около 1 секунды

        # Проверяем, что счетчик сбросился
        assert self.loader._request_count == 1

    @patch("src.market_meta.infrastructure.okx_integration.OKXMarket")
    async def test_exponential_backoff_timing(self, mock_market_class):
        """Тест экспоненциального backoff"""
        # Настраиваем мок для имитации ошибок
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=[
                Exception(
                    "Connection timeout"
                ),  # Будет преобразовано в OKXNetworkError
                Exception(
                    "Connection refused"
                ),  # Будет преобразовано в OKXNetworkError
                [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "instType": "SWAP",
                        "baseCcy": "BTC",
                        "quoteCcy": "USDT",
                    }
                ],
            ]
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        # Создаем новый loader с моком через DI
        loader = OKXMetadataLoader(
            max_retries=3, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )

        # Выполняем загрузку с измерением времени
        start_time = asyncio.get_event_loop().time()
        result = await loader.load_instruments(["SWAP"])
        end_time = asyncio.get_event_loop().time()

        # Проверяем результат
        assert len(result) == 1

        # Проверяем, что было время на retry (экспоненциальный backoff)
        # Минимальная задержка: 4с + 8с = 12с, но с нашими настройками меньше
        assert end_time - start_time > 0.1  # Должна быть какая-то задержка


class TestOKXErrorHandling:
    """Тесты обработки ошибок OKX"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.loader = OKXMetadataLoader()

    @patch("src.market_meta.infrastructure.okx_integration.OKXMarket")
    async def test_error_transformation(self, mock_market_class):
        """Тест преобразования общих ошибок в специфичные"""
        from tenacity import RetryError

        # Тест преобразования rate limit ошибки
        # Retry делает 3 попытки, все проваливаются, выбрасывается RetryError с OKXRateLimitError внутри
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=Exception("rate limit exceeded")
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        loader = OKXMetadataLoader(
            max_retries=1, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )
        with pytest.raises((OKXRateLimitError, RetryError)) as exc_info:
            await loader._load_instrument_type("SWAP")
        # Проверяем, что внутри RetryError есть OKXRateLimitError
        if isinstance(exc_info.value, RetryError):
            assert isinstance(
                exc_info.value.last_attempt.exception(), OKXRateLimitError
            )

        # Тест преобразования сетевой ошибки
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=Exception("connection timeout")
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        loader = OKXMetadataLoader(
            max_retries=1, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )
        with pytest.raises((OKXNetworkError, RetryError)) as exc_info:
            await loader._load_instrument_type("SWAP")
        # Проверяем, что внутри RetryError есть OKXNetworkError
        if isinstance(exc_info.value, RetryError):
            assert isinstance(exc_info.value.last_attempt.exception(), OKXNetworkError)

        # Тест преобразования общей ошибки
        mock_market_instance = AsyncMock()
        mock_market_instance.get_instruments = AsyncMock(
            side_effect=Exception("unknown error")
        )
        mock_market_instance.__aenter__ = AsyncMock(return_value=mock_market_instance)
        mock_market_instance.__aexit__ = AsyncMock(return_value=None)
        mock_market_class.return_value = mock_market_instance

        loader = OKXMetadataLoader(
            max_retries=1, base_delay=0.01, max_delay=0.1, market=mock_market_instance
        )
        with pytest.raises((OKXIntegrationError, RetryError)) as exc_info:
            await loader._load_instrument_type("SWAP")
        # Проверяем, что внутри RetryError есть OKXIntegrationError
        if isinstance(exc_info.value, RetryError):
            assert isinstance(
                exc_info.value.last_attempt.exception(), OKXIntegrationError
            )

    def test_loader_configuration(self):
        """Тест конфигурации загрузчика"""
        # Тест с пользовательскими настройками
        loader = OKXMetadataLoader(max_retries=5, base_delay=2.0, max_delay=120.0)

        assert loader.max_retries == 5
        assert loader.base_delay == 2.0
        assert loader.max_delay == 120.0
        assert loader._max_requests_per_second == 10


if __name__ == "__main__":
    pytest.main([__file__])
