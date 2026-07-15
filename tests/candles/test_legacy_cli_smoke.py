"""Smoke coverage for the legacy candles click CLI."""

from click.testing import CliRunner

from src.candles.cli.cli import market_meta


def test_market_meta_cli_help_lists_safe_commands() -> None:
    result = CliRunner().invoke(market_meta, ["--help"])

    assert result.exit_code == 0
    assert "refresh" in result.output
    assert "status" in result.output


def test_market_meta_cli_status_does_not_require_metadata() -> None:
    result = CliRunner().invoke(market_meta, ["status"])

    assert result.exit_code == 0
    assert "market_meta module status" in result.output
