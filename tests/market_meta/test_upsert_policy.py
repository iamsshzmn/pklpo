"""РўРµСЃС‚С‹ upsert-РїРѕР»РёС‚РёРєРё DO_NOT_OVERWRITE_NON_NULL_WITH_NULL.

РџСЂРѕРІРµСЂСЏРµС‚:
1. NULL РІ Р±Р°С‚С‡Рµ РЅРµ Р·Р°С‚РёСЂР°РµС‚ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРµ Р·РЅР°С‡РµРЅРёРµ
2. РњРµС‚Р°РґР°РЅРЅС‹Рµ (algo_version, run_id, params_hash) РІСЃРµРіРґР° РѕР±РЅРѕРІР»СЏСЋС‚СЃСЏ
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.market_meta_backup.infrastructure.upsert_builder import (
    MARKET_DATA_EXT_COALESCE_FIELDS,
    MARKET_DATA_EXT_SKIP_FIELDS,
    build_upsert_set_clause,
)


class TestBuildUpsertSetClause:
    """РўРµСЃС‚С‹ РґР»СЏ build_upsert_set_clause."""

    def test_coalesce_fields_protected(self) -> None:
        """РџРѕР»СЏ РёР· coalesce_fields РґРѕР»Р¶РЅС‹ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ COALESCE."""
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
        with patch("src.candles.infrastructure.upsert_builder.func") as mock_func:
            result = build_upsert_set_clause(
                stmt=mock_stmt,
                table_columns=columns,
                coalesce_fields=coalesce_fields,
                skip_fields=frozenset(),
            )

        # Assert
        # open_interest РґРѕР»Р¶РµРЅ РІС‹Р·РІР°С‚СЊ func.coalesce
        mock_func.coalesce.assert_called_once()
        # algo_version РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ excluded РЅР°РїСЂСЏРјСѓСЋ
        assert "algo_version" in result

    def test_skip_fields_excluded(self) -> None:
        """РџРѕР»СЏ РёР· skip_fields РЅРµ РґРѕР»Р¶РЅС‹ РїРѕРїР°РґР°С‚СЊ РІ СЂРµР·СѓР»СЊС‚Р°С‚."""
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
        with patch("src.candles.infrastructure.upsert_builder.func"):
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
        """updated_at РґРѕР»Р¶РµРЅ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ func.now()."""
        # Arrange
        mock_stmt = MagicMock()
        mock_stmt.excluded = {"updated_at": "some_value"}

        mock_col = MagicMock()
        mock_col.name = "updated_at"

        # Act
        with patch("src.candles.infrastructure.upsert_builder.func") as mock_func:
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
        """РњРµС‚Р°РґР°РЅРЅС‹Рµ (algo_version, run_id, params_hash) РІСЃРµРіРґР° РїРµСЂРµР·Р°РїРёСЃС‹РІР°СЋС‚СЃСЏ."""
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
        with patch("src.candles.infrastructure.upsert_builder.func"):
            result = build_upsert_set_clause(
                stmt=mock_stmt,
                table_columns=columns,
                coalesce_fields=frozenset(),  # РњРµС‚Р°РґР°РЅРЅС‹Рµ РќР• РІ coalesce
                skip_fields=frozenset(),
            )

        # Assert вЂ” РІСЃРµ РјРµС‚Р°РґР°РЅРЅС‹Рµ РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ РІ СЂРµР·СѓР»СЊС‚Р°С‚Рµ РєР°Рє excluded
        assert "algo_version" in result
        assert "run_id" in result
        assert "params_hash" in result


class TestMarketDataExtConstants:
    """РўРµСЃС‚С‹ РєРѕРЅСЃС‚Р°РЅС‚ РґР»СЏ market_data_ext."""

    def test_coalesce_fields_contains_data_columns(self) -> None:
        """COALESCE_FIELDS РґРѕР»Р¶РµРЅ СЃРѕРґРµСЂР¶Р°С‚СЊ РІСЃРµ data-РєРѕР»РѕРЅРєРё."""
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
        """SKIP_FIELDS РґРѕР»Р¶РµРЅ СЃРѕРґРµСЂР¶Р°С‚СЊ PK Рё Р±РёР·РЅРµСЃ-РєР»СЋС‡Рё."""
        expected = {"id", "created_at", "symbol", "timeframe", "bar_timestamp"}
        assert expected == MARKET_DATA_EXT_SKIP_FIELDS

    def test_metadata_not_in_coalesce(self) -> None:
        """РњРµС‚Р°РґР°РЅРЅС‹Рµ РќР• РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ РІ COALESCE_FIELDS."""
        metadata = {"algo_version", "run_id", "params_hash"}
        assert metadata.isdisjoint(MARKET_DATA_EXT_COALESCE_FIELDS)
