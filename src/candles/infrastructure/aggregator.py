"""
Агрегация расширенных данных для разных таймфреймов.

v1: агрегация 1m → {5m, 15m, 1H} с использованием реальных интервалов OHLCV.
"""

from datetime import datetime

import pandas as pd

from .logging_config import get_logger
from .ohlcv_aligner import OHLCVAligner

logger = get_logger("market_data_aggregator")


class MarketDataAggregator:
    """
    Агрегация расширенных данных для разных таймфреймов.

    v1: агрегация 1m → {5m, 15m, 1H} с использованием реальных интервалов OHLCV.
    """

    def __init__(self, ohlcv_aligner: OHLCVAligner):
        """
        Инициализация aggregator.

        Args:
            ohlcv_aligner: OHLCVAligner для синхронизации с фактическими барами
        """
        self.aligner = ohlcv_aligner

    def aggregate_1m_to_timeframe(
        self,
        data: pd.DataFrame,
        symbol: str,
        target_timeframe: str,  # 5m, 15m, 1H
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        *,
        run_id: str | None = None,
        algo_version: str | None = None,
        params_hash: str | None = None,
    ) -> pd.DataFrame:
        """
        Агрегирует данные от 1m к целевому таймфрейму с использованием реальных интервалов OHLCV.

        Правила:
        - OI: последнее значение в интервале фактического бара
        - Funding: последнее значение в интервале фактического бара
        - L2: последнее значение в интервале фактического бара (imbalance, spread)

        Поддерживаемые target_timeframe: 5m, 15m, 1H

        Args:
            data: DataFrame с нормализованными 1m данными (bar_timestamp как индекс или колонка)
            symbol: Символ для загрузки баров целевого таймфрейма
            target_timeframe: Целевой таймфрейм
            start_time: Начало периода
            end_time: Конец периода

        Returns:
            DataFrame с агрегированными данными
        """
        if data.empty:
            return pd.DataFrame()

        # Определяем bar_timestamp колонку
        if "bar_timestamp" not in data.columns:
            if data.index.name == "bar_timestamp" or isinstance(
                data.index, pd.DatetimeIndex
            ):
                data = data.reset_index()
                if "bar_timestamp" not in data.columns and "index" in data.columns:
                    data = data.rename(columns={"index": "bar_timestamp"})

        if "bar_timestamp" not in data.columns:
            logger.error("Не найдена колонка bar_timestamp в данных")
            return pd.DataFrame()

        # Загружаем фактические бары целевого таймфрейма
        if start_time is None:
            start_time = data["bar_timestamp"].min()
        if end_time is None:
            end_time = data["bar_timestamp"].max()

        target_bars = self.aligner.load_bar_timestamps(
            symbol=symbol,
            timeframe=target_timeframe,
            start_time=start_time,
            end_time=end_time,
        )

        if not target_bars:
            logger.warning(f"Нет баров OHLCV для {symbol} {target_timeframe}")
            return pd.DataFrame()

        # Группируем 1m данные по интервалам фактических баров
        aggregated_records = []

        for bar_idx, target_bar_ts in enumerate(target_bars):
            # Находим все 1m бары, которые попадают в этот интервал
            # Интервал: от предыдущего target_bar до текущего
            if bar_idx > 0:
                prev_bar_ts = target_bars[bar_idx - 1]
                # Берем данные между предыдущим и текущим баром (включая текущий)
                mask = (data["bar_timestamp"] > prev_bar_ts) & (
                    data["bar_timestamp"] <= target_bar_ts
                )
            else:
                # Первый бар - берем все до него включительно
                mask = data["bar_timestamp"] <= target_bar_ts

            bar_data = data[mask]

            if bar_data.empty:
                continue

            # Агрегируем по правилам
            aggregated_record = {
                "symbol": symbol,
                "bar_timestamp": target_bar_ts,
                "timeframe": target_timeframe,
                "source": (
                    bar_data["source"].iloc[0]
                    if "source" in bar_data.columns
                    else "okx"
                ),
            }

            # OI: последнее значение в интервале
            if "open_interest" in bar_data.columns:
                oi_values = bar_data["open_interest"].dropna()
                if not oi_values.empty:
                    aggregated_record["open_interest"] = oi_values.iloc[-1]

            # Funding: последнее значение в интервале
            if "funding_rate" in bar_data.columns:
                funding_values = bar_data["funding_rate"].dropna()
                if not funding_values.empty:
                    aggregated_record["funding_rate"] = funding_values.iloc[-1]
                    if "next_funding_time" in bar_data.columns:
                        next_funding = bar_data["next_funding_time"].dropna()
                        if not next_funding.empty:
                            aggregated_record["next_funding_time"] = next_funding.iloc[
                                -1
                            ]
                    if "funding_interval_hours" in bar_data.columns:
                        interval = bar_data["funding_interval_hours"].dropna()
                        if not interval.empty:
                            aggregated_record["funding_interval_hours"] = int(
                                interval.iloc[-1]
                            )

            # L2: последнее значение в интервале
            if "bid_imbalance" in bar_data.columns:
                bid_imbalance = bar_data["bid_imbalance"].dropna()
                if not bid_imbalance.empty:
                    aggregated_record["bid_imbalance"] = bid_imbalance.iloc[-1]
            if "ask_imbalance" in bar_data.columns:
                ask_imbalance = bar_data["ask_imbalance"].dropna()
                if not ask_imbalance.empty:
                    aggregated_record["ask_imbalance"] = ask_imbalance.iloc[-1]
            if "spread_bps" in bar_data.columns:
                spread = bar_data["spread_bps"].dropna()
                if not spread.empty:
                    aggregated_record["spread_bps"] = spread.iloc[-1]

            aggregated_records.append(aggregated_record)

        if not aggregated_records:
            return pd.DataFrame()

        result_df = pd.DataFrame(aggregated_records)

        # Добавляем версионирование если передано
        if run_id is not None:
            result_df["run_id"] = run_id
        if algo_version is not None:
            result_df["algo_version"] = algo_version
        if params_hash is not None:
            result_df["params_hash"] = params_hash

        result_df.set_index("bar_timestamp", inplace=True)
        return result_df
