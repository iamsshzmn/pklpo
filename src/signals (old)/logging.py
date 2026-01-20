"""
Логирование для системы сигналов.
"""

import logging
from datetime import datetime


class SignalLogger:
    """
    Логгер для торговых сигналов.
    """

    def __init__(self, log_file: str = "signals.log", console_level: str = "WARNING"):
        """
        Инициализация логгера сигналов.

        Args:
            log_file: Файл для логирования
            console_level: Уровень логирования для консоли (INFO, WARNING, ERROR)
        """
        self.logger = logging.getLogger("signals")
        self.logger.setLevel(logging.INFO)

        # Очищаем существующие обработчики
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Создаем файловый обработчик (всегда INFO)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)

        # Создаем консольный обработчик (настраиваемый уровень)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, console_level.upper()))

        # Создаем форматтер
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Добавляем обработчики к логгеру
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # Статистика за сессию
        self.session_stats = {
            "buy_signals": 0,
            "sell_signals": 0,
            "hold_signals": 0,
            "total_signals": 0,
            "avg_score": 0.0,
            "start_time": datetime.now(),
        }

    def set_console_level(self, level: str):
        """
        Устанавливает уровень логирования для консоли.

        Args:
            level: Уровень логирования (INFO, WARNING, ERROR)
        """
        for handler in self.logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                handler.setLevel(getattr(logging, level.upper()))

    def log_signal(
        self,
        symbol: str,
        timeframe: str,
        signal: int,
        score: float,
        reason: str,
        ts: int,
    ):
        """
        Логирует торговый сигнал.

        Args:
            symbol: Торговый символ
            timeframe: Таймфрейм
            signal: Сигнал (-1, 0, 1)
            score: Взвешенный score
            reason: Причина сигнала
            ts: Timestamp
        """
        signal_type = "BUY" if signal == 1 else "SELL" if signal == -1 else "HOLD"

        message = (
            f"Signal: {symbol} {timeframe} | {signal_type} | "
            f"Score: {score:.2f} | Reason: {reason[:100]} | TS: {ts}"
        )

        self.logger.info(message)

        # Обновляем статистику
        self.session_stats["total_signals"] += 1

        if signal == 1:
            self.session_stats["buy_signals"] += 1
        elif signal == -1:
            self.session_stats["sell_signals"] += 1
        else:
            self.session_stats["hold_signals"] += 1

        # Обновляем средний score
        total_score = (
            self.session_stats["avg_score"] * (self.session_stats["total_signals"] - 1)
            + score
        )
        self.session_stats["avg_score"] = (
            total_score / self.session_stats["total_signals"]
        )

    def log_session_summary(self):
        """Логирует сводку сессии."""
        duration = datetime.now() - self.session_stats["start_time"]

        summary = (
            f"Session Summary | Duration: {duration} | "
            f"Total: {self.session_stats['total_signals']} | "
            f"Buy: {self.session_stats['buy_signals']} | "
            f"Sell: {self.session_stats['sell_signals']} | "
            f"Hold: {self.session_stats['hold_signals']} | "
            f"Avg Score: {self.session_stats['avg_score']:.2f}"
        )

        self.logger.info(summary)
        print(f"📊 {summary}")

    def get_session_stats(self) -> dict:
        """Возвращает статистику сессии."""
        return self.session_stats.copy()

    def reset_session_stats(self):
        """Сбрасывает статистику сессии."""
        self.session_stats = {
            "buy_signals": 0,
            "sell_signals": 0,
            "hold_signals": 0,
            "total_signals": 0,
            "avg_score": 0.0,
            "start_time": datetime.now(),
        }


# Глобальный экземпляр логгера
signal_logger = SignalLogger(
    console_level="WARNING"
)  # По умолчанию только WARNING и ERROR в консоль


def log_signal(
    symbol: str, timeframe: str, signal: int, score: float, reason: str, ts: int
):
    """Удобная функция для логирования сигнала."""
    signal_logger.log_signal(symbol, timeframe, signal, score, reason, ts)


def log_session_summary():
    """Удобная функция для логирования сводки сессии."""
    signal_logger.log_session_summary()


def get_session_stats() -> dict:
    """Удобная функция для получения статистики сессии."""
    return signal_logger.get_session_stats()


def set_console_log_level(level: str):
    """
    Устанавливает уровень логирования для консоли.

    Args:
        level: Уровень логирования (INFO, WARNING, ERROR)
    """
    signal_logger.set_console_level(level)


def enable_verbose_logging():
    """Включает подробное логирование в консоль."""
    signal_logger.set_console_level("INFO")


def disable_verbose_logging():
    """Отключает подробное логирование в консоль (только WARNING и ERROR)."""
    signal_logger.set_console_level("WARNING")


# Новые функции для скромного логирования
def log_batch_start(total_pairs: int, symbols: list[str] | None = None):
    """Логирует начало пакетной обработки сигналов."""
    symbols_info = (
        f" | Символы: {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}"
        if symbols
        else ""
    )
    message = f"🚀 Начало расчёта сигналов | Всего пар: {total_pairs}{symbols_info}"
    signal_logger.logger.info(message)


def log_batch_progress(
    processed: int,
    total: int,
    current_symbol: str,
    current_timeframe: str,
    signals_count: int,
):
    """Логирует прогресс обработки сигналов."""
    progress = (processed / total) * 100
    message = (
        f"📈 Прогресс: {processed}/{total} ({progress:.1f}%) | "
        f"Текущий: {current_symbol} {current_timeframe} | "
        f"Сигналов: {signals_count}"
    )
    signal_logger.logger.info(message)


def log_signal_calculation(
    symbol: str,
    timeframe: str,
    signals_count: int,
    calculation_time: float | None = None,
    errors: list[str] | None = None,
):
    """Логирует расчёт сигналов для пары symbol-timeframe."""
    time_info = f" | Время: {calculation_time:.2f}s" if calculation_time else ""
    error_info = f" | Ошибки: {', '.join(errors)}" if errors else ""

    message = (
        f"Signals: {symbol} {timeframe} | "
        f"Рассчитано: {signals_count} сигналов{time_info}{error_info}"
    )

    signal_logger.logger.info(message)


def log_recalc_summary(
    total_processed: int, total_pairs: int, total_signals: int, errors_count: int
):
    """Логирует сводку пересчёта."""
    duration = datetime.now() - signal_logger.session_stats["start_time"]

    summary = (
        f"Recalc Summary | Duration: {duration} | "
        f"Pairs: {total_processed}/{total_pairs} | "
        f"Total Signals: {total_signals} | "
        f"Errors: {errors_count}"
    )

    signal_logger.logger.info(summary)
    print(f"📊 {summary}")


def reset_session_stats():
    """Удобная функция для сброса статистики сессии."""
    signal_logger.reset_session_stats()
