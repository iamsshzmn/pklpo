from aiolimiter import AsyncLimiter


class InstrumentLimiter:
    """
    Лимитер для каждого инструмента (symbol).
    Например, для OKX: 27 запросов в секунду на инструмент.
    """

    def __init__(self, max_rps=27, period=1):
        self.max_rps = max_rps
        self.period = period
        self._limiters = {}

    def get(self, symbol):
        """
        Получить лимитер для инструмента.
        """
        if symbol not in self._limiters:
            self._limiters[symbol] = AsyncLimiter(self.max_rps, self.period)
        return self._limiters[symbol]
