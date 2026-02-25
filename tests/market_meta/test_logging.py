"""
Тесты для системы логирования модуля market_meta.
"""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from src.market_meta.infrastructure.logging_config import (
    MarketMetaLogger,
    configure_logging,
    get_logger,
    log_cache_status,
    log_refresh_status,
    log_risk_check,
    log_validation_result,
)


class TestMarketMetaLogger:
    """Тесты для MarketMetaLogger"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        import logging

        # Очищаем root logger для тестов
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        root_logger.setLevel(logging.WARNING)

        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "test.log")
        self.logger = MarketMetaLogger("test_logger")

        # Очищаем handlers у логгера перед каждым тестом
        for handler in self.logger.logger.handlers[:]:
            self.logger.logger.removeHandler(handler)
        self.logger._configured = False

    def teardown_method(self):
        """Очистка после каждого теста"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_configure_basic(self):
        """Тест базовой настройки логирования"""
        self.logger.configure(
            level="INFO", log_file=self.log_file, console_output=False, file_output=True
        )

        assert self.logger._configured is True
        assert len(self.logger.logger.handlers) == 1  # только файловый обработчик

    def test_configure_console_only(self):
        """Тест настройки только консольного вывода"""
        self.logger.configure(level="DEBUG", console_output=True, file_output=False)

        assert self.logger._configured is True
        assert len(self.logger.logger.handlers) == 1  # только консольный обработчик

    def test_configure_both_outputs(self):
        """Тест настройки консольного и файлового вывода"""
        self.logger.configure(
            level="WARNING",
            log_file=self.log_file,
            console_output=True,
            file_output=True,
        )

        assert self.logger._configured is True
        assert len(self.logger.logger.handlers) == 2  # оба обработчика

    def test_get_logger_with_name(self):
        """Тест получения логгера с именем компонента"""
        self.logger.configure()
        component_logger = self.logger.get_logger("api")

        assert component_logger.name == "test_logger.api"

    def test_get_logger_without_name(self):
        """Тест получения основного логгера"""
        self.logger.configure()
        main_logger = self.logger.get_logger()

        assert main_logger.name == "test_logger"

    def test_log_validation_result_success(self):
        """Тест логирования успешной валидации"""
        self.logger.configure(
            log_file=self.log_file, console_output=False, file_output=True
        )

        self.logger.log_validation_result("BTC-USDT", [], ["Предупреждение"])

        # Убеждаемся, что файл создан и логи записаны
        import time

        time.sleep(0.1)  # Даём время на запись

        # Проверяем, что лог записан в файл
        assert os.path.exists(self.log_file), f"Log file not created: {self.log_file}"
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
            assert "Валидация ордера BTC-USDT прошла успешно" in content
            assert "Предупреждение для BTC-USDT" in content

    def test_log_validation_result_failure(self):
        """Тест логирования неуспешной валидации"""
        self.logger.configure(
            log_file=self.log_file, console_output=False, file_output=True
        )

        violations = ["Цена не соответствует размеру тика", "Недостаточно средств"]
        self.logger.log_validation_result("BTC-USDT", violations)

        # Проверяем, что лог записан в файл
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
            assert "Валидация ордера BTC-USDT не прошла: 2 нарушения" in content
            assert "1. Цена не соответствует размеру тика" in content
            assert "2. Недостаточно средств" in content

    def test_log_cache_status(self):
        """Тест логирования статуса кэша"""
        self.logger.configure(
            log_file=self.log_file, console_output=False, file_output=True
        )

        status = {"is_valid": True, "instruments_count": 150, "ttl_hours": 2.5}
        self.logger.log_cache_status(status)

        # Проверяем, что лог записан в файл
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
            assert "Статус кэша: актуален=True" in content
            assert "инструментов=150" in content
            assert "TTL=2.5ч" in content

    def test_log_refresh_status_success(self):
        """Тест логирования успешного обновления"""
        self.logger.configure(
            log_file=self.log_file, console_output=False, file_output=True
        )

        self.logger.log_refresh_status(True, 200)

        # Проверяем, что лог записан в файл
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
            assert (
                "Обновление метаданных успешно завершено: 200 инструментов" in content
            )

    def test_log_refresh_status_failure(self):
        """Тест логирования неуспешного обновления"""
        self.logger.configure(
            log_file=self.log_file, console_output=False, file_output=True
        )

        error_msg = "Ошибка подключения к API"
        self.logger.log_refresh_status(False, 0, error_msg)

        # Проверяем, что лог записан в файл
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
            assert "Ошибка обновления метаданных: Ошибка подключения к API" in content

    def test_log_risk_check_high_risk(self):
        """Тест логирования высокого риска"""
        self.logger.configure(
            log_file=self.log_file, console_output=False, file_output=True
        )

        self.logger.log_risk_check("BTC-USDT", "HIGH", "Превышен лимит позиции")

        # Проверяем, что лог записан в файл
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
            assert "Высокий риск для BTC-USDT: Превышен лимит позиции" in content

    def test_log_risk_check_normal_risk(self):
        """Тест логирования нормального риска"""
        self.logger.configure(
            log_file=self.log_file, console_output=False, file_output=True
        )

        self.logger.log_risk_check("BTC-USDT", "LOW", "Риск в пределах нормы")

        # Проверяем, что лог записан в файл
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
            assert "Проверка рисков BTC-USDT: Риск в пределах нормы" in content


class TestLoggingFunctions:
    """Тесты для функций логирования"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        from src.market_meta.infrastructure.logging_config import _market_meta_logger

        # Сбрасываем конфигурацию глобального логгера перед каждым тестом
        _market_meta_logger._configured = False
        for handler in _market_meta_logger.logger.handlers[:]:
            _market_meta_logger.logger.removeHandler(handler)

        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "test.log")

    def teardown_method(self):
        """Очистка после каждого теста"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_logger(self):
        """Тест функции get_logger"""
        logger = get_logger("test_component")
        assert logger.name == "market_meta.test_component"

    def test_configure_logging(self):
        """Тест функции configure_logging"""
        configure_logging(
            level="DEBUG",
            log_file=self.log_file,
            console_output=False,
            file_output=True,
        )

        # Проверяем, что логгер настроен
        logger = get_logger()
        # Проверяем эффективный уровень (может быть установлен на root)
        effective_level = logger.getEffectiveLevel()
        assert effective_level == 10 or logger.level == 10  # DEBUG level

    def test_log_validation_result_function(self):
        """Тест функции log_validation_result"""
        configure_logging(
            log_file=self.log_file, console_output=False, file_output=True
        )

        log_validation_result("ETH-USDT", ["Ошибка валидации"])

        # Убеждаемся, что файл создан
        import time

        time.sleep(0.1)
        assert os.path.exists(self.log_file), f"Log file not created: {self.log_file}"

        # Проверяем, что лог записан
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
            assert "Валидация ордера ETH-USDT не прошла" in content

    def test_log_cache_status_function(self):
        """Тест функции log_cache_status"""
        configure_logging(
            log_file=self.log_file, console_output=False, file_output=True
        )

        status = {"is_valid": False, "instruments_count": 0, "ttl_hours": 0.0}
        log_cache_status(status)

        # Убеждаемся, что файл создан
        import time

        time.sleep(0.1)
        assert os.path.exists(self.log_file), f"Log file not created: {self.log_file}"

        # Проверяем, что лог записан
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
            assert "Статус кэша" in content

    def test_log_refresh_status_function(self):
        """Тест функции log_refresh_status"""
        configure_logging(
            log_file=self.log_file, console_output=False, file_output=True
        )

        log_refresh_status(True, 100)

        # Убеждаемся, что файл создан
        import time

        time.sleep(0.1)
        assert os.path.exists(self.log_file), f"Log file not created: {self.log_file}"

        # Проверяем, что лог записан
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
            assert "Обновление метаданных успешно завершено" in content

    def test_log_risk_check_function(self):
        """Тест функции log_risk_check"""
        configure_logging(
            log_file=self.log_file, console_output=False, file_output=True
        )

        log_risk_check("BTC-USDT", "CRITICAL", "Критический риск")

        # Убеждаемся, что файл создан
        import time

        time.sleep(0.1)
        assert os.path.exists(self.log_file), f"Log file not created: {self.log_file}"

        # Проверяем, что лог записан
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
            assert "Высокий риск для BTC-USDT" in content


class TestEnvironmentConfiguration:
    """Тесты конфигурации через переменные окружения"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "env_test.log")

    def teardown_method(self):
        """Очистка после каждого теста"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Очищаем переменные окружения
        for key in [
            "MARKET_META_LOG_LEVEL",
            "MARKET_META_LOG_FILE",
            "MARKET_META_CONSOLE_LOG",
            "MARKET_META_FILE_LOG",
        ]:
            if key in os.environ:
                del os.environ[key]

    @patch("src.market_meta.infrastructure.logging_config.configure_logging")
    def test_auto_configure_defaults(self, mock_configure):
        """Тест автоматической настройки с дефолтными значениями"""
        from src.market_meta.infrastructure.logging_config import auto_configure

        auto_configure()

        from src.market_meta.infrastructure.logging_config import DEFAULT_LOG_FILE

        mock_configure.assert_called_once_with(
            level="INFO",
            log_file=DEFAULT_LOG_FILE,
            console_output=True,
            file_output=True,
        )

    @patch("src.market_meta.infrastructure.logging_config.configure_logging")
    def test_auto_configure_with_env_vars(self, mock_configure):
        """Тест автоматической настройки с переменными окружения"""
        from src.market_meta.infrastructure.logging_config import auto_configure

        os.environ["MARKET_META_LOG_LEVEL"] = "DEBUG"
        os.environ["MARKET_META_LOG_FILE"] = self.log_file
        os.environ["MARKET_META_CONSOLE_LOG"] = "false"
        os.environ["MARKET_META_FILE_LOG"] = "true"

        auto_configure()

        mock_configure.assert_called_once_with(
            level="DEBUG",
            log_file=self.log_file,
            console_output=False,
            file_output=True,
        )


if __name__ == "__main__":
    pytest.main([__file__])
