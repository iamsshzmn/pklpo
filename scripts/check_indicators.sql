-- Проверка данных в таблице indicators
SELECT
    symbol,
    timeframe,
    timestamp,
    "Ema 8",
    "Sma 20",
    "Rsi 14",
    "Macd",
    "Atr 14",
    "Obv",
    "Log Return",
    "Percent Return",
    "Drawdown",
    "Data Quality Status",
    "Nan Count",
    "Valid Rate"
FROM indicators
WHERE symbol = 'BTC-USDT-SWAP'
    AND timeframe = '1m'
ORDER BY timestamp DESC
LIMIT 5;
