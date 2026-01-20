"""
Логирование для системы индикаторов.
"""

import logging
from datetime import datetime
from typing import Any


class IndicatorsLogger:
    """
    Логгер для технических индикаторов.
    """

    def __init__(self, log_file: str = "indicators.log"):
        """
        Инициализация логгера индикаторов.

        Args:
            log_file: Файл для логирования
        """
        self.logger = logging.getLogger("indicators")
        self.logger.setLevel(logging.INFO)

        # Очищаем существующие обработчики
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # Отключаем передачу логов родительскому логгеру
        self.logger.propagate = False

        # Создаем файловый обработчик
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)

        # Создаем форматтер
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # Добавляем обработчик к логгеру
        self.logger.addHandler(file_handler)

        # Статистика за сессию
        self.session_stats: dict[str, Any] = {
            "symbols_processed": 0,
            "timeframes_processed": 0,
            "total_indicators": 0,
            "errors_count": 0,
            "start_time": datetime.now(),
            "indicators_calculated": {},  # Счетчик по типам индикаторов
            "symbols_errors": [],  # Список символов с ошибками
        }

    def log_indicator_calculation(
        self,
        symbol: str,
        timeframe: str,
        indicators_count: int,
        calculation_time: float | None = None,
        errors: list[str] | None = None,
    ):
        """
        Логирует расчёт индикаторов для пары symbol-timeframe.

        Args:
            symbol: Торговый символ
            timeframe: Таймфрейм
            indicators_count: Количество рассчитанных индикаторов
            calculation_time: Время расчёта в секундах
            errors: Список ошибок при расчёте
        """
        time_info = f" | Время: {calculation_time:.2f}s" if calculation_time else ""
        error_info = f" | Ошибки: {', '.join(errors)}" if errors else ""

        message = (
            f"Indicators: {symbol} {timeframe} | "
            f"Рассчитано: {indicators_count} индикаторов{time_info}{error_info}"
        )

        self.logger.info(message)

        # Обновляем статистику
        self.session_stats["symbols_processed"] += 1
        self.session_stats["timeframes_processed"] += 1
        self.session_stats["total_indicators"] += indicators_count

        if errors:
            self.session_stats["errors_count"] += 1
            self.session_stats["symbols_errors"].append(f"{symbol} {timeframe}")

    def log_indicator_type(self, indicator_name: str, success: bool = True):
        """
        Логирует успешность расчёта конкретного типа индикатора.

        Args:
            indicator_name: Название индикатора
            success: Успешно ли рассчитан
        """
        if indicator_name not in self.session_stats["indicators_calculated"]:
            self.session_stats["indicators_calculated"][indicator_name] = {
                "success": 0,
                "failed": 0,
            }

        if success:
            self.session_stats["indicators_calculated"][indicator_name]["success"] += 1
        else:
            self.session_stats["indicators_calculated"][indicator_name]["failed"] += 1

    def log_batch_start(self, total_pairs: int, symbols: list[str] | None = None):
        """
        Логирует начало пакетной обработки.

        Args:
            total_pairs: Общее количество пар symbol-timeframe
            symbols: Список символов для обработки
        """
        symbols_info = (
            f" | Символы: {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}"
            if symbols
            else ""
        )

        message = (
            f"🚀 Начало расчёта индикаторов | Всего пар: {total_pairs}{symbols_info}"
        )
        self.logger.info(message)

    def log_batch_progress(
        self, processed: int, total: int, current_symbol: str, current_timeframe: str
    ):
        """
        Логирует прогресс обработки.

        Args:
            processed: Обработано пар
            total: Всего пар
            current_symbol: Текущий символ
            current_timeframe: Текущий таймфрейм
        """
        progress = (processed / total) * 100
        message = (
            f"📈 Прогресс: {processed}/{total} ({progress:.1f}%) | "
            f"Текущий: {current_symbol} {current_timeframe}"
        )
        self.logger.info(message)

    def log_session_summary(self):
        """Логирует сводку сессии."""
        duration = datetime.now() - self.session_stats["start_time"]

        # Статистика по типам индикаторов
        indicators_summary = []
        for indicator, stats in self.session_stats["indicators_calculated"].items():
            total = stats["success"] + stats["failed"]
            success_rate = (stats["success"] / total * 100) if total > 0 else 0
            indicators_summary.append(f"{indicator}: {success_rate:.1f}%")

        summary = (
            f"Session Summary | Duration: {duration} | "
            f"Symbols: {self.session_stats['symbols_processed']} | "
            f"Timeframes: {self.session_stats['timeframes_processed']} | "
            f"Total Indicators: {self.session_stats['total_indicators']} | "
            f"Errors: {self.session_stats['errors_count']} | "
            f"Success Rate: {((self.session_stats['timeframes_processed'] - self.session_stats['errors_count']) / self.session_stats['timeframes_processed'] * 100) if self.session_stats['timeframes_processed'] > 0 else 0:.1f}%"
        )

        self.logger.info(summary)

        # Детальная статистика по индикаторам
        if indicators_summary:
            self.logger.info(
                f"Indicators Success Rates: {' | '.join(indicators_summary)}"
            )

        # Список ошибок
        if self.session_stats["symbols_errors"]:
            self.logger.warning(
                f"Symbols with errors: {', '.join(self.session_stats['symbols_errors'])}"
            )

        # Выводим только в файл, не в терминал
        # print(f"📊 {summary}")

    def get_session_stats(self) -> dict[str, Any]:
        """Возвращает статистику сессии."""
        return self.session_stats.copy()

    def reset_session_stats(self):
        """Сбрасывает статистику сессии."""
        self.session_stats = {
            "symbols_processed": 0,
            "timeframes_processed": 0,
            "total_indicators": 0,
            "errors_count": 0,
            "start_time": datetime.now(),
            "indicators_calculated": {},
            "symbols_errors": [],
        }


# Глобальный экземпляр логгера (ленивая инициализация)
_indicators_logger = None


def get_indicators_logger():
    """Получить глобальный экземпляр логгера (ленивая инициализация)"""
    global _indicators_logger
    if _indicators_logger is None:
        _indicators_logger = IndicatorsLogger()
    return _indicators_logger


def log_indicator_calculation(
    symbol: str,
    timeframe: str,
    indicators_count: int,
    calculation_time: float | None = None,
    errors: list[str] | None = None,
):
    """Удобная функция для логирования расчёта индикаторов."""
    print(
        f"DEBUG log_indicator_calculation: {symbol} {timeframe} - {indicators_count} indicators, {calculation_time}s, errors: {errors}"
    )
    get_indicators_logger().log_indicator_calculation(
        symbol, timeframe, indicators_count, calculation_time, errors
    )


def log_indicator_type(indicator_name: str, success: bool = True):
    """Удобная функция для логирования типа индикатора."""
    get_indicators_logger().log_indicator_type(indicator_name, success)


def log_batch_start(total_pairs: int, symbols: list[str] | None = None):
    """Удобная функция для логирования начала пакетной обработки."""
    get_indicators_logger().log_batch_start(total_pairs, symbols)


def log_batch_progress(
    processed: int, total: int, current_symbol: str, current_timeframe: str
):
    """Удобная функция для логирования прогресса."""
    get_indicators_logger().log_batch_progress(
        processed, total, current_symbol, current_timeframe
    )


def log_session_summary():
    """Удобная функция для логирования сводки сессии."""
    get_indicators_logger().log_session_summary()


def get_session_stats() -> dict[str, Any]:
    """Удобная функция для получения статистики сессии."""
    result: dict[str, Any] = get_indicators_logger().get_session_stats()
    return result


def reset_session_stats():
    """Удобная функция для сброса статистики сессии."""
    get_indicators_logger().reset_session_stats()
