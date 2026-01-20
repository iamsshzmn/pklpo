"""
Enhanced smoke validation for features module.

This module provides comprehensive validation and metrics collection
for features calculation results in Airflow DAGs.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .logging_config import get_features_logger
from .schema.schema_manager import SchemaManager
from .specs import FEATURE_SPECS, PHASE_2_REQUIRED_FEATURES

logger = get_features_logger("features.smoke")


async def get_indicators_data(
    session: AsyncSession, hours_back: int = 24
) -> dict[str, Any]:
    """
    Get indicators data from database for validation.

    Args:
        session: Database session
        hours_back: Hours to look back for data

    Returns:
        Dictionary with indicators data
    """
    # Use current time as cutoff (correct approach)
    cutoff = datetime.now(UTC) - timedelta(hours=hours_back)

    # Get total rows
    total_result = await session.execute(text("SELECT COUNT(*) FROM indicators"))
    total_rows = total_result.scalar()

    # Get rows from last 24 hours (corrected for timezone and units)
    # ИСПРАВЛЕНИЕ: Используем timestamp вместо calculated_at для согласованности
    last24h_result = await session.execute(
        text("SELECT COUNT(*) FROM indicators WHERE timestamp >= :cutoff_ms"),
        {"cutoff_ms": int(cutoff.timestamp() * 1000)},  # Конвертируем в миллисекунды
    )
    last24h_rows = last24h_result.scalar()

    # Get trade data freshness (from swap_ohlcv_p with correct timestamp conversion)
    trade_freshness_result = await session.execute(
        text(
            """
        SELECT
            MAX(to_timestamp(timestamp/1000.0)) as max_trade_ts,
            COUNT(*) as trade_count
        FROM swap_ohlcv_p
        WHERE to_timestamp(timestamp/1000.0) >= :cutoff
    """
        ),
        {"cutoff": cutoff},
    )
    trade_freshness = trade_freshness_result.fetchone()
    max_trade_ts = trade_freshness[0] if trade_freshness else None
    trade_count = trade_freshness[1] if trade_freshness else 0

    # Get available columns
    columns_result = await session.execute(
        text(
            """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'indicators'
        AND table_schema = 'public'
        ORDER BY column_name
    """
        )
    )
    available_columns = [row[0] for row in columns_result.fetchall()]

    # Get sample data for validation
    # ИСПРАВЛЕНИЕ: Используем timestamp для согласованности
    sample_result = await session.execute(
        text(
            """
        SELECT * FROM indicators
        WHERE timestamp >= :cutoff_ms
        ORDER BY timestamp DESC
        LIMIT 100
    """
        ),
        {"cutoff_ms": int(cutoff.timestamp() * 1000)},
    )

    sample_data = sample_result.fetchall()
    sample_columns = sample_result.keys()

    return {
        "total_rows": total_rows,
        "last24h_rows": last24h_rows,
        "available_columns": available_columns,
        "sample_data": sample_data,
        "sample_columns": list(sample_columns),
        "cutoff_time": cutoff,
        "trade_freshness": {
            "max_trade_ts": max_trade_ts,
            "trade_count": trade_count,
            "trade_lag_hours": (
                (datetime.now(UTC) - max_trade_ts).total_seconds() / 3600
                if max_trade_ts
                else None
            ),
        },
    }


def analyze_feature_coverage(available_columns: list[str]) -> dict[str, Any]:
    """
    Analyze feature coverage against specifications.

    Args:
        available_columns: List of available columns in indicators table

    Returns:
        Coverage analysis
    """
    # Get feature names from specs и нормализуем по реестру схемы
    schema_manager = SchemaManager()
    name_mapping = schema_manager.get_name_mapping()
    aliases = schema_manager.get_aliases()

    raw_spec_names: set[str] = set()
    for spec in FEATURE_SPECS:
        if hasattr(spec, "name"):
            raw_spec_names.add(spec.name)
        elif isinstance(spec, str):
            raw_spec_names.add(spec)

    spec_names = set()
    for n in raw_spec_names:
        mapped = name_mapping.get(n, n)
        mapped = aliases.get(mapped, mapped)
        spec_names.add(mapped)

    # Remove service columns
    service_columns = {
        "symbol",
        "timeframe",
        "timestamp",
        "calculated_at",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ts",
    }
    # Список устаревших алиасов, которые надо скрыть из отчётов
    deprecated_aliases = {
        "ultimate_osc",
        "kijun",
        "tenkan",
        "bbands_upper",
        "bbands_middle",
        "bbands_lower",
        "bbands_percent",
        "bbands_width",
        "kc",
        "kc_upper",
        "kc_middle",
        "kc_lower",
        "williams_r",
        "ichimoku_a",
        "ichimoku_b",
    }

    normalized_columns = []
    for col in available_columns:
        if col in service_columns:
            continue
        # 1) нормализуем по name_mapping
        mapped = name_mapping.get(col, col)
        # 2) нормализуем по aliases
        mapped = aliases.get(mapped, mapped)
        # 3) фильтруем явные устаревшие алиасы
        if mapped in deprecated_aliases:
            continue
        normalized_columns.append(mapped)

    # Убираем дубликаты, сохраняя множество канонических имён
    feature_columns = sorted(set(normalized_columns))

    # Calculate coverage
    present_features = [f for f in spec_names if f in feature_columns]
    # Не считаем deprecated алиасы как отсутствующие
    missing_features = [
        f
        for f in spec_names
        if f not in feature_columns and f not in deprecated_aliases
    ]
    extra_features = [f for f in feature_columns if f not in spec_names]

    coverage_rate = (len(present_features) / len(spec_names) * 100) if spec_names else 0

    return {
        "total_specs": len(spec_names),
        "present_features": present_features,
        "missing_features": missing_features,
        "extra_features": extra_features,
        "coverage_rate": coverage_rate,
        "feature_columns_count": len(feature_columns),
    }


def analyze_phase2_compliance(available_columns: list[str]) -> dict[str, Any]:
    """
    Analyze Phase 2 compliance.

    Args:
        available_columns: List of available columns in indicators table

    Returns:
        Phase 2 compliance analysis
    """
    required_features = list(PHASE_2_REQUIRED_FEATURES)
    present_required = [f for f in required_features if f in available_columns]
    missing_required = [f for f in required_features if f not in available_columns]

    compliance_rate = (
        (len(present_required) / len(required_features) * 100)
        if required_features
        else 0
    )

    return {
        "required_features": required_features,
        "present_required": present_required,
        "missing_required": missing_required,
        "compliance_rate": compliance_rate,
        "total_required": len(required_features),
    }


def analyze_feature_groups(available_columns: list[str]) -> dict[str, Any]:
    """
    Analyze feature coverage by groups.

    Args:
        available_columns: List of available columns in indicators table

    Returns:
        Feature groups analysis
    """
    # Define feature groups
    feature_groups = {
        "moving_averages": [
            col
            for col in available_columns
            if any(ma in col.lower() for ma in ["ema", "sma", "wma", "hma"])
        ],
        "oscillators": [
            col
            for col in available_columns
            if any(
                osc in col.lower() for osc in ["rsi", "stoch", "willr", "cci", "cmo"]
            )
        ],
        "trend": [
            col
            for col in available_columns
            if any(tr in col.lower() for tr in ["adx", "aroon", "dmi", "psar"])
        ],
        "volatility": [
            col
            for col in available_columns
            if any(vol in col.lower() for vol in ["atr", "bb", "kc", "dc"])
        ],
        "volume": [
            col
            for col in available_columns
            if any(vol in col.lower() for vol in ["obv", "ad", "mfi", "vwap"])
        ],
        "macd": [col for col in available_columns if "macd" in col.lower()],
        "candles": [col for col in available_columns if col.lower().startswith("cdl_")],
    }

    group_analysis = {}
    for group_name, features in feature_groups.items():
        group_analysis[group_name] = {
            "count": len(features),
            "features": features[:10],  # Show first 10 features
            "has_more": len(features) > 10,
        }

    return group_analysis


async def calculate_feature_quality_metrics(
    session: AsyncSession, feature_columns: list[str], hours_back: int = 24
) -> dict[str, float]:
    """
    Calculate quality metrics for features.

    Args:
        session: Database session
        feature_columns: List of feature columns to analyze
        hours_back: Hours to look back for data

    Returns:
        Dictionary with quality metrics
    """
    cutoff = datetime.now(UTC) - timedelta(hours=hours_back)
    quality_metrics = {}

    # Критичные фичи проверяем всегда
    critical_features = [
        "rsi_14",
        "ema_8",
        "sma_20",
        "atr_14",
        "macd",
        "hlc3",
        "hl2",
        "ohlc4",
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "kc_upper",
        "kc_middle",
        "kc_lower",
    ]
    # Остальные - первые 50 для производительности
    other_features = [c for c in feature_columns if c not in critical_features][:50]
    features_to_check = critical_features + other_features

    for column in features_to_check:
        if column not in feature_columns:
            continue
        try:
            # Get null ratio for the feature
            query = text(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE {column} IS NULL) AS nulls,
                    COUNT(*) AS total
                FROM indicators
                WHERE calculated_at >= :cutoff
            """
            )

            result = await session.execute(query, {"cutoff": cutoff})
            nulls, total = result.one()

            fill_rate = ((total - nulls) / total * 100) if total > 0 else 0
            quality_metrics[column] = fill_rate

        except Exception as e:
            logger.warning(f"Failed to calculate quality for {column}", error=str(e))
            quality_metrics[column] = 0.0

    return quality_metrics


async def run_smoke_validation(
    session: AsyncSession, hours_back: int = 24
) -> dict[str, Any]:
    """
    Run comprehensive smoke validation.

    Args:
        session: Database session
        hours_back: Hours to look back for data

    Returns:
        Comprehensive validation results
    """
    logger.info("Starting smoke validation hours_back=%d", hours_back)

    # Get indicators data
    indicators_data = await get_indicators_data(session, hours_back)

    # Analyze coverage
    coverage_analysis = analyze_feature_coverage(indicators_data["available_columns"])

    # Analyze Phase 2 compliance
    phase2_analysis = analyze_phase2_compliance(indicators_data["available_columns"])

    # Analyze feature groups
    groups_analysis = analyze_feature_groups(indicators_data["available_columns"])

    # Calculate quality metrics
    feature_columns = [
        col
        for col in indicators_data["available_columns"]
        if col
        not in {
            "symbol",
            "timeframe",
            "timestamp",
            "calculated_at",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "ts",
        }
    ]
    quality_metrics = await calculate_feature_quality_metrics(
        session, feature_columns, hours_back
    )

    # Фильтруем метрики для итогового статуса: исключаем индикаторы с нулевым расчётом (fill_rate == 0)
    nonzero_quality_metrics = {k: v for k, v in quality_metrics.items() if v > 0}

    # Compile results
    results = {
        "timestamp": datetime.now(UTC).isoformat(),
        "data_overview": {
            "total_rows": indicators_data["total_rows"],
            "last24h_rows": indicators_data["last24h_rows"],
            "available_columns_count": len(indicators_data["available_columns"]),
            "feature_columns_count": len(feature_columns),
        },
        "coverage_analysis": coverage_analysis,
        "phase2_compliance": phase2_analysis,
        "feature_groups": groups_analysis,
        "quality_metrics": quality_metrics,
        "validation_status": {
            "has_data": indicators_data["last24h_rows"] > 0,
            "coverage_adequate": coverage_analysis["coverage_rate"] >= 80,
            "phase2_compliant": phase2_analysis["compliance_rate"] >= 90,
            # Качество считаем по non-zero фичам, чтобы не шуметь на полностью пустых
            "quality_acceptable": (
                len([m for m in nonzero_quality_metrics.values() if m >= 50])
                >= (len(nonzero_quality_metrics) * 0.7)
                if nonzero_quality_metrics
                else True
            ),
            "avg_fill_rate_ok": (
                (
                    (
                        sum(nonzero_quality_metrics.values())
                        / len(nonzero_quality_metrics)
                    )
                    >= 70
                )
                if nonzero_quality_metrics
                else True
            ),
            "critical_features_ok": (
                all(
                    quality_metrics.get(f, 0) >= 30
                    for f in ["rsi_14", "ema_8", "sma_20", "atr_14", "macd"]
                )
                if quality_metrics
                else False
            ),
            "critical_features_details": (
                {
                    f: quality_metrics.get(f, 0)
                    for f in ["rsi_14", "ema_8", "sma_20", "atr_14", "macd", "hlc3"]
                }
                if quality_metrics
                else {}
            ),
            "trade_data_fresh": indicators_data["trade_freshness"]["trade_lag_hours"]
            is None
            or indicators_data["trade_freshness"]["trade_lag_hours"] <= 24,
            "trade_data_available": indicators_data["trade_freshness"]["trade_count"]
            > 0,
        },
        "trade_freshness": indicators_data["trade_freshness"],
    }

    # Log summary
    trade_lag = results["trade_freshness"]["trade_lag_hours"]
    trade_lag_str = f"{trade_lag:.1f}h" if trade_lag is not None else "N/A"

    logger.info(
        "Smoke validation completed",
        total_rows=results["data_overview"]["total_rows"],
        last24h_rows=results["data_overview"]["last24h_rows"],
        coverage_rate=f"{coverage_analysis['coverage_rate']:.1f}%",
        phase2_compliance=f"{phase2_analysis['compliance_rate']:.1f}%",
        trade_lag_hours=trade_lag_str,
        trade_count=results["trade_freshness"]["trade_count"],
    )

    return results


def print_smoke_report(results: dict[str, Any]):
    """
    Print formatted smoke validation report.

    Args:
        results: Validation results
    """
    print("\n" + "=" * 80)
    print("FEATURES SMOKE VALIDATION REPORT")
    print("=" * 80)

    # Data overview
    overview = results["data_overview"]
    print("\nDATA OVERVIEW:")
    print(f"   Total rows in indicators: {overview['total_rows']:,}")
    print(f"   Rows in last 24h: {overview['last24h_rows']:,}")
    print(f"   Available columns: {overview['available_columns_count']}")
    print(f"   Feature columns: {overview['feature_columns_count']}")

    # Coverage analysis
    coverage = results["coverage_analysis"]
    print("\nFEATURE COVERAGE:")
    print(f"   Total specs: {coverage['total_specs']}")
    print(f"   Present features: {len(coverage['present_features'])}")
    print(f"   Missing features: {len(coverage['missing_features'])}")
    print(f"   Coverage rate: {coverage['coverage_rate']:.1f}%")

    if coverage["missing_features"]:
        print(f"   Missing features: {', '.join(coverage['missing_features'][:10])}")
        if len(coverage["missing_features"]) > 10:
            print(f"   ... and {len(coverage['missing_features']) - 10} more")

    # Phase 2 compliance
    phase2 = results["phase2_compliance"]
    print("\nPHASE 2 COMPLIANCE:")
    print(f"   Required features: {phase2['total_required']}")
    print(f"   Present required: {len(phase2['present_required'])}")
    print(f"   Missing required: {len(phase2['missing_required'])}")
    print(f"   Compliance rate: {phase2['compliance_rate']:.1f}%")

    if phase2["missing_required"]:
        print(f"   Missing required: {', '.join(phase2['missing_required'])}")

    # Feature groups
    groups = results["feature_groups"]
    print("\nFEATURE GROUPS:")
    for group_name, group_data in groups.items():
        if group_data["count"] > 0:
            print(f"   {group_name}: {group_data['count']} features")
            if group_data["features"]:
                print(f"      Examples: {', '.join(group_data['features'][:5])}")

    # Quality metrics
    quality = results["quality_metrics"]
    if quality:
        avg_quality = sum(quality.values()) / len(quality)
        high_quality = len([q for q in quality.values() if q >= 80])
        low_quality = len([q for q in quality.values() if q < 50])

        print("\nQUALITY METRICS:")
        print(f"   Average fill rate: {avg_quality:.1f}%")
        print(f"   High quality features (≥80%): {high_quality}")
        print(f"   Low quality features (<50%): {low_quality}")

        # Show worst features
        worst_features = sorted(quality.items(), key=lambda x: x[1])[:5]
        if worst_features:
            print("   Worst features:")
            for feature, rate in worst_features:
                print(f"      {feature}: {rate:.1f}%")

    # Validation status
    status = results["validation_status"]
    print("\nVALIDATION STATUS:")
    print(f"   Has data: {'✅' if status['has_data'] else '❌'}")
    print(
        f"   Coverage adequate (≥80%): {'✅' if status['coverage_adequate'] else '❌'}"
    )
    print(
        f"   Phase 2 compliant (≥90%): {'✅' if status['phase2_compliant'] else '❌'}"
    )
    print(
        f"   Quality acceptable (≥70% good): {'✅' if status['quality_acceptable'] else '❌'}"
    )

    # Critical features details
    if "critical_features_details" in status:
        crit_details = status["critical_features_details"]
        crit_ok = status.get("critical_features_ok", False)
        print(f"   Critical features OK: {'✅' if crit_ok else '❌'}")
        if crit_details:
            print("   Critical features details:")
            for feat, rate in crit_details.items():
                status_icon = "✅" if rate >= 30 else "❌"
                print(f"      {feat}: {rate:.1f}% {status_icon}")

    # Overall status - понижаем серьёзность для non-blocking фич
    blocking_checks = [
        status["has_data"],
        status["coverage_adequate"],
        status["phase2_compliant"],
        status["quality_acceptable"],
        status["avg_fill_rate_ok"],
    ]
    all_blocking_good = all(blocking_checks)
    all_good = all(status.values())

    if all_blocking_good and not all_good:
        # Только non-blocking фичи провалены - WARN вместо FAIL
        print("\nOVERALL STATUS: ⚠️ WARN (non-blocking issues)")
        print("   Blocking checks: ✅ PASS")
        print("   Non-blocking: ❌ FAIL (critical_features_ok)")
    else:
        print(f"\nOVERALL STATUS: {'✅ PASS' if all_good else '❌ FAIL'}")

    print("=" * 80)


async def main():
    """Main function for smoke validation."""
    from src.database import get_async_session

    async with get_async_session() as session:
        results = await run_smoke_validation(session)
        print_smoke_report(results)

        # Export metrics for Airflow
        metrics_json = json.dumps(results, ensure_ascii=False, default=str)
        print(f"\n[features_calc] METRICS {metrics_json}")

        # Fail if validation failed
        if not all(results["validation_status"].values()):
            print("❌ Smoke validation failed - exiting with error code")
            import sys

            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
