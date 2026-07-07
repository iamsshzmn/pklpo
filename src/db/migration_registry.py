from collections.abc import Awaitable, Callable


# Define a simple migration descriptor
class Migration:
    def __init__(self, id: str, name: str, func: Callable[[], Awaitable[None]]):
        self.id = id
        self.name = name
        self.func = func


def get_migrations() -> list[Migration]:
    """
    Ordered list of migrations to run.
    Add new migrations at the end to preserve order.
    """
    from src.db.migrations.migrate_add_core_indexes import migrate_add_core_indexes
    from src.db.migrations.migrate_add_data_constraints import (
        run_data_constraints_migration,
    )
    from src.db.migrations.migrate_add_data_retention import migrate_add_data_retention
    from src.db.migrations.migrate_add_indicators_parent_service_columns import (
        migrate_add_indicators_parent_service_columns,
    )
    from src.db.migrations.migrate_add_instruments_metadata_refreshed_at_ms import (
        migrate_add_instruments_metadata_refreshed_at_ms,
    )
    from src.db.migrations.migrate_add_operational_reliability import (
        run_operational_reliability_migration,
    )
    from src.db.migrations.migrate_add_swap_fields import (
        run_migrations as mig_add_swap_fields,
    )
    from src.db.migrations.migrate_add_swap_fields_to_instruments import (
        migrate_add_swap_fields_to_instruments,
    )
    from src.db.migrations.migrate_add_swap_ohlcv_alignment_trigger import (
        migrate_add_swap_ohlcv_alignment_trigger,
    )
    from src.db.migrations.migrate_add_swap_ohlcv_constraints import (
        migrate_add_swap_ohlcv_constraints,
    )
    from src.db.migrations.migrate_allow_candidate_pipeline_recovery_decisions import (
        migrate_allow_candidate_pipeline_recovery_decisions,
    )
    from src.db.migrations.migrate_create_combination_features import (
        migrate_create_combination_features,
    )
    from src.db.migrations.migrate_create_core_identity import (
        migrate_create_core_identity,
    )
    from src.db.migrations.migrate_create_continuous_ohlcv_build_audit import (
        migrate_create_continuous_ohlcv_build_audit,
    )
    from src.db.migrations.migrate_create_core_ohlcv_facade import (
        migrate_create_core_ohlcv_facade,
    )
    from src.db.migrations.migrate_create_features_table import (
        migrate_create_features_table,
    )
    from src.db.migrations.migrate_create_indicators_partitioned import (
        migrate_create_indicators_partitioned,
    )
    from src.db.migrations.migrate_create_market_data_ext import (
        migrate_create_market_data_ext,
    )
    from src.db.migrations.migrate_create_market_selection import (
        migrate_create_market_selection,
    )
    from src.db.migrations.migrate_create_ohlcv import run_migrations as mig_ohlcv
    from src.db.migrations.migrate_create_ohlcv_partitioned import (
        migrate_create_ohlcv_partitioned,
    )
    from src.db.migrations.migrate_create_ops_data_quality_metrics import (
        migrate_create_ops_data_quality_metrics,
    )
    from src.db.migrations.migrate_create_ops_feature_eligibility import (
        migrate_create_ops_feature_eligibility,
    )
    from src.db.migrations.migrate_create_ops_feature_eligibility_transitions import (
        migrate_create_ops_feature_eligibility_transitions,
    )
    from src.db.migrations.migrate_create_ops_indicator_recalc_queue import (
        migrate_create_ops_indicator_recalc_queue,
    )
    from src.db.migrations.migrate_create_ops_pipeline_recovery_decisions import (
        migrate_create_ops_pipeline_recovery_decisions,
    )
    from src.db.migrations.migrate_create_ops_recovery_symbol_discovery import (
        migrate_create_ops_recovery_symbol_discovery,
    )
    from src.db.migrations.migrate_create_ops_swap_ohlcv_bootstrap_state import (
        migrate_create_ops_swap_ohlcv_bootstrap_state,
    )
    from src.db.migrations.migrate_create_ops_swap_repair_audit import (
        migrate_create_ops_swap_repair_audit,
    )
    from src.db.migrations.migrate_create_ops_symbol_succession import (
        migrate_create_ops_symbol_succession,
    )
    from src.db.migrations.migrate_create_positions import (
        run_migrations as mig_positions,
    )
    from src.db.migrations.migrate_create_schema_migrations import (
        migrate_create_schema_migrations,
    )
    from src.db.migrations.migrate_create_score_results import (
        migrate_create_score_results,
    )
    from src.db.migrations.migrate_create_series_identity_build_audit import (
        migrate_create_series_identity_build_audit,
    )
    from src.db.migrations.migrate_create_swap_ohlcv import migrate_create_swap_ohlcv
    from src.db.migrations.migrate_create_trade_recommendations import (
        migrate_create_trade_recommendations,
    )
    from src.db.migrations.migrate_data_cleanup import migrate_data_cleanup
    from src.db.migrations.migrate_drop_ops_recovery_symbol_discovery import (
        migrate_drop_ops_recovery_symbol_discovery,
    )
    from src.db.migrations.migrate_drop_redundant_swap_ohlcv_indexes import (
        migrate_drop_redundant_swap_ohlcv_indexes,
    )
    from src.db.migrations.migrate_expand_indicators_precision import (
        migrate_expand_indicators_precision,
    )
    from src.db.migrations.migrate_extend_ops_identity_inputs import (
        migrate_extend_ops_identity_inputs,
    )
    from src.db.migrations.migrate_extend_ops_swap_repair_audit_semantics import (
        migrate_extend_ops_swap_repair_audit_semantics,
    )
    from src.db.migrations.migrate_fix_score_results_precision import (
        migrate_fix_score_results_precision,
    )
    from src.db.migrations.migrate_materialized_views import migrate_materialized_views
    from src.db.migrations.migrate_monitoring_metrics import migrate_monitoring_metrics
    from src.db.migrations.migrate_recreate_swap_ohlcv_partitioned import (
        migrate_recreate_swap_ohlcv_partitioned,
    )
    from src.db.migrations.migrate_retention_horizon_guard import (
        migrate_retention_horizon_guard,
    )
    from src.db.migrations.migrate_set_research_tf_infinite_retention import (
        migrate_set_research_tf_infinite_retention,
    )
    from src.db.migrations.migrate_swap_ohlcv_retention_policy import (
        migrate_swap_ohlcv_retention_policy,
    )
    from src.db.migrations.migrate_swap_ohlcv_timestamps_timestamptz import (
        migrate_swap_ohlcv_timestamps_timestamptz,
    )
    from src.db.migrations.migrate_validate_swap_ohlcv_constraints import (
        migrate_validate_swap_ohlcv_constraints,
    )
    from src.migrate_create_instruments import run_migrations as mig_instruments

    return [
        Migration(
            "000_base_migrations_table",
            "create schema_migrations",
            migrate_create_schema_migrations,
        ),
        Migration("010_instruments", "create instruments", mig_instruments),
        Migration("020_ohlcv", "create ohlcv", mig_ohlcv),
        Migration("030_add_swap_fields", "add swap fields", mig_add_swap_fields),
        Migration("040_positions", "create positions tables", mig_positions),
        Migration(
            "050_score_results", "create score_results", migrate_create_score_results
        ),
        Migration(
            "060_fix_score_precision",
            "fix score_results precision",
            migrate_fix_score_results_precision,
        ),
        Migration(
            "070_add_swap_fields_to_instruments",
            "add swap fields to instruments",
            migrate_add_swap_fields_to_instruments,
        ),
        Migration(
            "080_trade_recommendations",
            "create trade recommendations tables",
            migrate_create_trade_recommendations,
        ),
        Migration(
            "090_core_indexes",
            "add composite and BRIN indexes",
            migrate_add_core_indexes,
        ),
        Migration(
            "100_ohlcv_partitioned",
            "create ohlcv partitioned",
            migrate_create_ohlcv_partitioned,
        ),
        Migration(
            "110_indicators_partitioned",
            "create indicators partitioned",
            migrate_create_indicators_partitioned,
        ),
        Migration(
            "130_data_constraints",
            "add data quality constraints",
            run_data_constraints_migration,
        ),
        Migration(
            "140_operational_reliability",
            "add operational reliability features",
            run_operational_reliability_migration,
        ),
        Migration(
            "150_data_cleanup", "cleanup and normalize data", migrate_data_cleanup
        ),
        Migration(
            "160_materialized_views",
            "create materialized views and aggregations",
            migrate_materialized_views,
        ),
        Migration(
            "170_monitoring_metrics",
            "create monitoring and metrics system",
            migrate_monitoring_metrics,
        ),
        Migration(
            "180_swap_ohlcv",
            "create swap OHLCV table",
            migrate_create_swap_ohlcv,
        ),
        Migration(
            "190_features_table",
            "create features table for technical indicators",
            migrate_create_features_table,
        ),
        Migration(
            "210_data_retention",
            "add data retention policy (2 days)",
            migrate_add_data_retention,
        ),
        Migration(
            "230_expand_indicators_precision",
            "expand indicator columns to NUMERIC(38,12) for large values",
            migrate_expand_indicators_precision,
        ),
        Migration(
            "240_combination_features",
            "create combination_features table (numeric-only)",
            migrate_create_combination_features,
        ),
        Migration(
            "250_market_data_ext",
            "create market_data_ext table for extended market data (OI, funding, L2)",
            migrate_create_market_data_ext,
        ),
        Migration(
            "260_market_selection",
            "create market_selection tables (scores_tf, universe, versions, regime_history)",
            migrate_create_market_selection,
        ),
        Migration(
            "270_swap_ohlcv_partitioned",
            "recreate swap_ohlcv_p as partitioned parent",
            migrate_recreate_swap_ohlcv_partitioned,
        ),
        Migration(
            "280_ops_data_quality_metrics",
            "create ops schema and ops.data_quality_metrics table",
            migrate_create_ops_data_quality_metrics,
        ),
        Migration(
            "290_swap_ohlcv_timestamptz",
            "normalize swap_ohlcv_p fetched_at/created_at to timestamptz",
            migrate_swap_ohlcv_timestamps_timestamptz,
        ),
        Migration(
            "300_indicators_parent_service_columns",
            "ensure indicators_p runtime service columns exist",
            migrate_add_indicators_parent_service_columns,
        ),
        Migration(
            "310_ops_swap_repair_audit",
            "create ops.swap_repair_audit table",
            migrate_create_ops_swap_repair_audit,
        ),
        Migration(
            "320_instruments_metadata_refreshed_at_ms",
            "add instruments metadata_refreshed_at_ms",
            migrate_add_instruments_metadata_refreshed_at_ms,
        ),
        Migration(
            "330_ops_swap_repair_audit_semantics",
            "extend ops.swap_repair_audit with outcome + progress fields",
            migrate_extend_ops_swap_repair_audit_semantics,
        ),
        Migration(
            "340_swap_ohlcv_retention_policy",
            "replace swap OHLCV insert-trigger cleanup with per-timeframe retention",
            migrate_swap_ohlcv_retention_policy,
        ),
        Migration(
            "350_ops_swap_ohlcv_bootstrap_state",
            "create ops.swap_ohlcv_bootstrap_state table",
            migrate_create_ops_swap_ohlcv_bootstrap_state,
        ),
        Migration(
            "360_swap_ohlcv_constraints",
            "add swap OHLCV DB protection constraints",
            migrate_add_swap_ohlcv_constraints,
        ),
        Migration(
            "370_validate_swap_ohlcv_constraints",
            "validate swap OHLCV DB protection constraints",
            migrate_validate_swap_ohlcv_constraints,
        ),
        Migration(
            "380_swap_ohlcv_alignment_trigger",
            "create disabled swap OHLCV alignment trigger",
            migrate_add_swap_ohlcv_alignment_trigger,
        ),
        Migration(
            "390_research_tf_infinite_retention",
            "set research timeframes to infinite retention",
            migrate_set_research_tf_infinite_retention,
        ),
        Migration(
            "400_drop_redundant_swap_ohlcv_indexes",
            "drop redundant swap OHLCV lookup indexes",
            migrate_drop_redundant_swap_ohlcv_indexes,
        ),
        Migration(
            "410_retention_horizon_guard",
            "clamp swap OHLCV retention outside warm-up horizon",
            migrate_retention_horizon_guard,
        ),
        Migration(
            "420_ops_feature_eligibility",
            "create ops feature eligibility state table",
            migrate_create_ops_feature_eligibility,
        ),
        Migration(
            "430_ops_feature_eligibility_transitions",
            "create ops feature eligibility transition audit table",
            migrate_create_ops_feature_eligibility_transitions,
        ),
        Migration(
            "440_ops_indicator_recalc_queue",
            "create ops indicator recalculation queue",
            migrate_create_ops_indicator_recalc_queue,
        ),
        Migration(
            "450_ops_pipeline_recovery_decisions",
            "create ops pipeline recovery decisions table",
            migrate_create_ops_pipeline_recovery_decisions,
        ),
        Migration(
            "460_allow_candidate_pipeline_recovery_decisions",
            "allow candidate recovery decision status",
            migrate_allow_candidate_pipeline_recovery_decisions,
        ),
        Migration(
            "470_ops_recovery_symbol_discovery",
            "create ops recovery symbol discovery table",
            migrate_create_ops_recovery_symbol_discovery,
        ),
        Migration(
            "480_ops_symbol_succession",
            "create ops symbol succession",
            migrate_create_ops_symbol_succession,
        ),
        Migration(
            "490_drop_ops_recovery_symbol_discovery",
            "drop ops recovery symbol discovery table",
            migrate_drop_ops_recovery_symbol_discovery,
        ),
        Migration(
            "500_ops_identity_inputs",
            "extend ops identity input tables",
            migrate_extend_ops_identity_inputs,
        ),
        Migration(
            "510_core_identity",
            "create core identity tables",
            migrate_create_core_identity,
        ),
        Migration(
            "520_series_identity_build_audit",
            "create identity build audit table",
            migrate_create_series_identity_build_audit,
        ),
        Migration(
            "530_continuous_ohlcv_build_audit",
            "create continuous OHLCV build audit table",
            migrate_create_continuous_ohlcv_build_audit,
        ),
        Migration(
            "540_core_ohlcv_facade",
            "create DB-side OHLCV facade (view + PIT function) for BI/SQL",
            migrate_create_core_ohlcv_facade,
        ),
    ]
