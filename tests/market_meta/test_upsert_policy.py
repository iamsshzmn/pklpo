"""Тесты upsert-политики DO_NOT_OVERWRITE_NON_NULL_WITH_NULL.

Проверяет:
1. NULL в батче не затирает существующее значение
2. Метаданные (algo_version, run_id, params_hash) всегда обновляются
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.market_meta.infrastructure.upsert_builder import (
    MARKET_DATA_EXT_COALESCE_FIELDS,
    MARKET_DATA_EXT_SKIP_FIELDS,
    build_upsert_set_clause,
)


class TestBuildUpsertSetClause:
    """Тесты для build_upsert_set_clause."""

    def test_coalesce_fields_protected(self) -> None:
        """Поля из coalesce_fields должны использовать COALESCE."""
        # Arrange
        mock_stmt = MagicMock()
        mock_stmt.excluded = {"open_interest": "excluded_oi", "algo_version": "excluded_av"}

        mock_col_oi = MagicMock()
        mock_col_oi.name = "open_interest"

        mock_col_av = MagicMock()
        mock_col_av.name = "algo_version"

        columns = [mock_col_oi, mock_col_av]
        coalesce_fields = frozenset({"open_interest"})

        # Act
        with patch("src.market_meta.infrastructure.upsert_builder.func") as mock_func:
            result = build_upsert_set_clause(
                stmt=mock_stmt,
                table_columns=columns,
                coalesce_fields=coalesce_fields,
                skip_fields=frozenset(),
            )

        # Assert
        # open_interest должен вызвать func.coalesce
        mock_func.coalesce.assert_called_once()
        # algo_version должен быть excluded напрямую
        assert "algo_version" in result

    def test_skip_fields_excluded(self) -> None:
        """Поля из skip_fields не должны попадать в результат."""
        # Arrange
        mock_stmt = MagicMock()
        mock_stmt.excluded = {"id": 1, "symbol": "BTC", "open_interest": 100}

        mock_col_id = MagicMock()
        mock_col_id.name = "id"

        mock_col_symbol = MagicMock()
        mock_col_symbol.name = "symbol"

        mock_col_oi = MagicMock()
        mock_col_oi.name = "open_interest"

        columns = [mock_col_id, mock_col_symbol, mock_col_oi]
        skip_fields = frozenset({"id", "symbol"})

        # Act
        with patch("src.market_meta.infrastructure.upsert_builder.func"):
            result = build_upsert_set_clause(
                stmt=mock_stmt,
                table_columns=columns,
                coalesce_fields=frozenset(),
                skip_fields=skip_fields,
            )

        # Assert
        assert "id" not in result
        assert "symbol" not in result
        assert "open_interest" in result

    def test_updated_at_uses_now(self) -> None:
        """updated_at должен использовать func.now()."""
        # Arrange
        mock_stmt = MagicMock()
        mock_stmt.excluded = {"updated_at": "some_value"}

        mock_col = MagicMock()
        mock_col.name = "updated_at"

        # Act
        with patch("src.market_meta.infrastructure.upsert_builder.func") as mock_func:
            result = build_upsert_set_clause(
                stmt=mock_stmt,
                table_columns=[mock_col],
                coalesce_fields=frozenset(),
                skip_fields=frozenset(),
            )

        # Assert
        mock_func.now.assert_called_once()
        assert "updated_at" in result

    def test_metadata_always_overwritten(self) -> None:
        """Метаданные (algo_version, run_id, params_hash) всегда перезаписываются."""
        # Arrange
        mock_stmt = MagicMock()
        mock_stmt.excluded = {
            "algo_version": "v2.0.0",
            "run_id": "run_123",
            "params_hash": "abc123",
        }

        columns = []
        for name in ["algo_version", "run_id", "params_hash"]:
            col = MagicMock()
            col.name = name
            columns.append(col)

        # Act
        with patch("src.market_meta.infrastructure.upsert_builder.func"):
            result = build_upsert_set_clause(
                stmt=mock_stmt,
                table_columns=columns,
                coalesce_fields=frozenset(),  # Метаданные НЕ в coalesce
                skip_fields=frozenset(),
            )

        # Assert — все метаданные должны быть в результате как excluded
        assert "algo_version" in result
        assert "run_id" in result
        assert "params_hash" in result


class TestMarketDataExtConstants:
    """Тесты констант для market_data_ext."""

    def test_coalesce_fields_contains_data_columns(self) -> None:
        """COALESCE_FIELDS должен содержать все data-колонки."""
        expected = {
            "open_interest",
            "oi_change_24h",
            "oi_change_pct_24h",
            "funding_rate",
            "next_funding_time",
            "funding_interval_hours",
            "bid_imbalance",
            "ask_imbalance",
            "spread_bps",
        }
        assert expected == MARKET_DATA_EXT_COALESCE_FIELDS

    def test_skip_fields_contains_pk_and_business_keys(self) -> None:
        """SKIP_FIELDS должен содержать PK и бизнес-ключи."""
        expected = {"id", "created_at", "symbol", "timeframe", "bar_timestamp"}
        assert expected == MARKET_DATA_EXT_SKIP_FIELDS

    def test_metadata_not_in_coalesce(self) -> None:
        """Метаданные НЕ должны быть в COALESCE_FIELDS."""
        metadata = {"algo_version", "run_id", "params_hash"}
        assert metadata.isdisjoint(MARKET_DATA_EXT_COALESCE_FIELDS)
