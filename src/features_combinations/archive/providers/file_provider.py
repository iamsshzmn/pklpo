from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import pandas as pd

from .validator import validate_input_schema

if TYPE_CHECKING:
    from pathlib import Path

FileFormat = Literal["csv", "parquet"]


@dataclass
class FileIndicatorProvider:
    root: Path
    file_format: FileFormat = "parquet"
    ts_col: str = "ts"

    def load(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        path = self._resolve_path(symbol, timeframe)
        df = pd.read_csv(path) if self.file_format == "csv" else pd.read_parquet(path)
        # Сортировка и ограничение
        if self.ts_col in df.columns:
            df = df.sort_values(self.ts_col)
        if limit:
            df = df.tail(limit)
        return validate_input_schema(df, ts_col=self.ts_col)

    def _resolve_path(self, symbol: str, timeframe: str) -> Path:
        filename = f"{symbol.replace('/', '-')}_{timeframe}.{self.file_format}"
        return (self.root / filename).resolve()
