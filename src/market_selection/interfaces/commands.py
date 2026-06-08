"""
Market Selection CLI Commands

Commands:
- market-selection run: Run the full pipeline
- market-selection status: Show current universe status
- market-selection explain <symbol>: Explain why a symbol was included/excluded
- market-selection migrate: Run database migrations
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register market-selection command."""
    parser = subparsers.add_parser(
        "market-selection",
        help="Market selection operations",
    )

    sub = parser.add_subparsers(dest="action", help="Action to perform")

    # run
    run_parser = sub.add_parser("run", help="Run market selection pipeline")
    run_parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Number of symbols in universe (default: 30)",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute but don't persist results",
    )

    # status
    sub.add_parser("status", help="Show current universe status")

    # explain
    explain_parser = sub.add_parser(
        "explain",
        help="Explain why a symbol was included/excluded",
    )
    explain_parser.add_argument("symbol", help="Symbol to explain (e.g., BTCUSDT)")

    # migrate
    sub.add_parser("migrate", help="Run database migrations")

    # universe
    universe_parser = sub.add_parser("universe", help="Show current universe")
    universe_parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Limit number of symbols (default: 30)",
    )
    universe_parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )

    # regime
    sub.add_parser("regime", help="Show current global regime")

    # metrics
    metrics_parser = sub.add_parser("metrics", help="Show pipeline metrics")
    metrics_parser.add_argument(
        "--history",
        type=int,
        default=10,
        help="Number of recent runs to show (default: 10)",
    )
    metrics_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )

    parser.set_defaults(_handler=handle)


async def _run_pipeline(top_n: int, dry_run: bool) -> dict:
    """Run the market selection pipeline."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.database import get_async_engine
    from src.market_selection.config import MarketSelectionConfig
    from src.market_selection.infrastructure.factory import (
        build_market_selection_pipeline,
    )

    config = MarketSelectionConfig()
    config.universe.top_n = top_n

    engine = get_async_engine()

    async with AsyncSession(engine) as session:
        pipeline = build_market_selection_pipeline(session, config)

        if dry_run:
            # Just compute ts_eval and regime
            ts_eval = await pipeline.db.resolve_ts_eval()
            regime = await pipeline._compute_regime(ts_eval) if ts_eval else None

            return {
                "dry_run": True,
                "ts_eval": ts_eval,
                "regime": regime.regime.value if regime else None,
                "strength": regime.strength if regime else None,
            }

        result = await pipeline.run()

        return {
            "success": result.success,
            "ts_version": result.ts_version,
            "universe_size": result.universe_size,
            "status": result.status.value,
            "regime": result.global_regime.value if result.global_regime else None,
            "execution_time": result.execution_time_seconds,
            "error": result.error_message,
        }


async def _get_status() -> dict:
    """Get current universe status."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.database import get_async_engine

    engine = get_async_engine()

    async with AsyncSession(engine) as session:
        result = await session.execute(
            text(
                """
            SELECT
                ts_version,
                ts_eval,
                status,
                universe_size,
                global_regime,
                global_strength,
                execution_time_seconds,
                config_hash,
                created_at
            FROM market_universe_versions
            ORDER BY ts_version DESC
            LIMIT 5
        """
            )
        )

        versions = []
        for row in result.fetchall():
            versions.append(
                {
                    "ts_version": row[0],
                    "ts_eval": row[1],
                    "status": row[2],
                    "universe_size": row[3],
                    "regime": row[4],
                    "strength": row[5],
                    "execution_time": row[6],
                    "config_hash": row[7],
                    "created_at": str(row[8]) if row[8] else None,
                }
            )

        return {"versions": versions}


async def _explain_symbol(symbol: str) -> dict:
    """Explain why a symbol was included/excluded."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.database import get_async_engine

    engine = get_async_engine()

    async with AsyncSession(engine) as session:
        # Get latest universe version
        version_result = await session.execute(
            text(
                """
            SELECT ts_version, ts_eval
            FROM market_universe_versions
            WHERE status IN ('published', 'fallback_prev')
            ORDER BY ts_version DESC
            LIMIT 1
        """
            )
        )
        version_row = version_result.fetchone()

        if not version_row:
            return {"error": "No published universe found"}

        ts_version, ts_eval = version_row

        # Check if symbol is in universe
        universe_result = await session.execute(
            text(
                """
            SELECT final_score, rank, best_tf, worst_tf,
                   score_4h, score_1h, score_15m, score_5m,
                   reason_flags, penalty_applied
            FROM market_universe
            WHERE ts_version = :ts_version AND symbol = :symbol
        """
            ),
            {"ts_version": ts_version, "symbol": symbol},
        )

        universe_row = universe_result.fetchone()

        # Get TF scores
        scores_result = await session.execute(
            text(
                """
            SELECT
                timeframe,
                score_tf,
                quality_score,
                fill_rate,
                gap_rate,
                eligible,
                reason_flags,
                vol_score, trend_q_score, noise_score, stability_score, liq_score
            FROM market_scores_tf
            WHERE ts_eval = :ts_eval AND symbol = :symbol
            ORDER BY timeframe
        """
            ),
            {"ts_eval": ts_eval, "symbol": symbol},
        )

        tf_scores = []
        for row in scores_result.fetchall():
            tf_scores.append(
                {
                    "timeframe": row[0],
                    "score_tf": row[1],
                    "quality_score": row[2],
                    "fill_rate": row[3],
                    "gap_rate": row[4],
                    "eligible": row[5],
                    "reason_flags": row[6],
                    "metrics": {
                        "vol": row[7],
                        "trend_q": row[8],
                        "noise": row[9],
                        "stability": row[10],
                        "liq": row[11],
                    },
                }
            )

        result = {
            "symbol": symbol,
            "ts_version": ts_version,
            "ts_eval": ts_eval,
            "in_universe": universe_row is not None,
            "tf_scores": tf_scores,
        }

        if universe_row:
            result["universe"] = {
                "final_score": universe_row[0],
                "rank": universe_row[1],
                "best_tf": universe_row[2],
                "worst_tf": universe_row[3],
                "score_4h": universe_row[4],
                "score_1h": universe_row[5],
                "score_15m": universe_row[6],
                "score_5m": universe_row[7],
                "reason_flags": universe_row[8],
                "penalty_applied": universe_row[9],
            }

        return result


async def _run_migrations() -> dict:
    """Run database migrations."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.database import get_async_engine
    from src.market_selection.migrations import (
        check_tables_exist,
        run_market_selection_migrations,
    )

    engine = get_async_engine()

    async with AsyncSession(engine) as session:
        before = await check_tables_exist(session)
        await run_market_selection_migrations(session)
        after = await check_tables_exist(session)

        return {
            "before": before,
            "after": after,
            "created": [k for k, v in after.items() if v and not before.get(k)],
        }


async def _get_universe(limit: int) -> list:
    """Get current universe."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.database import get_async_engine

    engine = get_async_engine()

    async with AsyncSession(engine) as session:
        result = await session.execute(
            text(
                """
            SELECT
                mu.symbol,
                mu.final_score,
                mu.rank,
                mu.best_tf,
                mu.score_4h,
                mu.score_1h,
                mu.score_15m,
                mu.score_5m,
                mu.global_regime_at_time
            FROM market_universe mu
            JOIN market_universe_versions muv ON mu.ts_version = muv.ts_version
            WHERE muv.status IN ('published', 'fallback_prev')
            ORDER BY muv.ts_version DESC, mu.rank
            LIMIT :limit
        """
            ),
            {"limit": limit},
        )

        return [
            {
                "symbol": row[0],
                "score": row[1],
                "rank": row[2],
                "best_tf": row[3],
                "score_4h": row[4],
                "score_1h": row[5],
                "score_15m": row[6],
                "score_5m": row[7],
                "regime": row[8],
            }
            for row in result.fetchall()
        ]


async def _get_regime() -> dict:
    """Get current global regime."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.database import get_async_engine

    engine = get_async_engine()

    async with AsyncSession(engine) as session:
        result = await session.execute(
            text(
                """
            SELECT
                ts_eval,
                global_regime,
                global_strength,
                regime_confidence,
                regime_1d,
                regime_4h,
                regime_1h,
                basket_size,
                basket_adx_median,
                basket_atr_close_median,
                created_at
            FROM market_regime_history
            ORDER BY ts_eval DESC
            LIMIT 1
        """
            )
        )

        row = result.fetchone()
        if not row:
            return {"error": "No regime history found"}

        return {
            "ts_eval": row[0],
            "regime": row[1],
            "strength": row[2],
            "confidence": row[3],
            "regime_1d": row[4],
            "regime_4h": row[5],
            "regime_1h": row[6],
            "basket_size": row[7],
            "basket_adx_median": row[8],
            "basket_atr_close_median": row[9],
            "created_at": str(row[10]) if row[10] else None,
        }


def _get_metrics(history: int) -> dict:
    """Get pipeline metrics."""
    from ..infrastructure.monitoring import get_metrics

    metrics = get_metrics()

    return {
        "summary": metrics.get_summary(),
        "history": metrics.get_recent_history(history),
        "eligible_counts": metrics.get_eligible_counts(),
        "regime_distribution": metrics.get_regime_distribution(),
    }


def handle(args: argparse.Namespace) -> int:
    """Handle market-selection command."""
    action = getattr(args, "action", None)

    if not action:
        print("Usage: pklpo market-selection <action>")
        print("Actions: run, status, explain, migrate, universe, regime, metrics")
        return 1

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if action == "run":
            result = loop.run_until_complete(_run_pipeline(args.top_n, args.dry_run))
            if result.get("success"):
                print("Pipeline completed successfully")
                print(f"  Universe size: {result['universe_size']}")
                print(f"  Status: {result['status']}")
                print(f"  Regime: {result['regime']}")
                print(f"  Time: {result['execution_time']:.2f}s")
            else:
                print(f"Pipeline failed: {result.get('error')}")
                return 1

        elif action == "status":
            result = loop.run_until_complete(_get_status())
            print("Recent Universe Versions:")
            print("-" * 80)
            for v in result["versions"]:
                print(
                    f"  {v['ts_version']} | {v['status']:12} | "
                    f"size={v['universe_size']:3} | {v['regime'] or 'N/A':10} | "
                    f"{v['created_at']}"
                )

        elif action == "explain":
            result = loop.run_until_complete(_explain_symbol(args.symbol))
            if "error" in result:
                print(f"Error: {result['error']}")
                return 1

            print(f"Symbol: {result['symbol']}")
            print(f"In Universe: {'Yes' if result['in_universe'] else 'No'}")
            print()

            if result.get("universe"):
                u = result["universe"]
                print("Universe Position:")
                print(f"  Rank: {u['rank']}")
                print(f"  Final Score: {u['final_score']:.4f}")
                print(f"  Best TF: {u['best_tf']}")
                print(f"  Flags: {u['reason_flags']}")
                print()

            print("TF Scores:")
            print("-" * 70)
            for tf in result["tf_scores"]:
                eligible = "Y" if tf["eligible"] else "N"
                print(
                    f"  {tf['timeframe']:4} | score={tf['score_tf']:.4f} | "
                    f"quality={tf['quality_score']:.3f} | eligible={eligible} | "
                    f"flags={tf['reason_flags']}"
                )

        elif action == "migrate":
            result = loop.run_until_complete(_run_migrations())
            print("Migrations completed")
            print(f"  Tables created: {result['created'] or 'none'}")
            print(f"  Tables after: {result['after']}")

        elif action == "universe":
            result = loop.run_until_complete(_get_universe(args.limit))

            if args.format == "json":
                print(json.dumps(result, indent=2))
            elif args.format == "csv":
                print("symbol,score,rank,best_tf,score_4h,score_1h,score_15m,score_5m")
                for r in result:
                    print(
                        f"{r['symbol']},{r['score']:.4f},{r['rank']},"
                        f"{r['best_tf']},{r['score_4h']},{r['score_1h']},"
                        f"{r['score_15m']},{r['score_5m']}"
                    )
            else:
                print("Current Universe:")
                print("-" * 80)
                for r in result:
                    print(
                        f"  {r['rank']:3}. {r['symbol']:12} | "
                        f"score={r['score']:.4f} | best={r['best_tf']}"
                    )

        elif action == "regime":
            result = loop.run_until_complete(_get_regime())
            if "error" in result:
                print(f"Error: {result['error']}")
                return 1

            print("Current Global Regime:")
            print(f"  Regime: {result['regime']}")
            print(f"  Strength: {result['strength']:.2f}")
            print(f"  Confidence: {result['confidence']:.2f}")
            print()
            print("Per-TF Breakdown:")
            print(f"  1D: {result['regime_1d']}")
            print(f"  4H: {result['regime_4h']}")
            print(f"  1H: {result['regime_1h']}")
            print()
            print(f"Basket: {result['basket_size']} symbols")
            print(f"  ADX median: {result['basket_adx_median']:.2f}")
            print(f"  ATR/close median: {result['basket_atr_close_median']:.4f}")

        elif action == "metrics":
            result = _get_metrics(args.history)

            if args.format == "json":
                print(json.dumps(result, indent=2, default=str))
            else:
                summary = result["summary"]
                print("Pipeline Metrics Summary:")
                print("-" * 60)

                if "error" in summary:
                    print(f"  {summary['error']}")
                else:
                    print(f"  Total runs: {summary.get('total_runs', 0)}")
                    print(f"  Success: {summary.get('success_runs', 0)}")
                    print(f"  Failed: {summary.get('failed_runs', 0)}")
                    print(f"  Success rate: {summary.get('success_rate', 0):.1%}")
                    print(
                        f"  Current universe: {summary.get('current_universe_size', 0)}"
                    )
                    print(
                        f"  Avg execution time: {summary.get('avg_execution_time', 0):.2f}s"
                    )
                    print()

                    print("Regime Distribution (last 24 runs):")
                    for regime, count in result.get("regime_distribution", {}).items():
                        print(f"  {regime}: {count}")
                    print()

                    print("Eligible Counts:")
                    for tf, count in result.get("eligible_counts", {}).items():
                        print(f"  {tf}: {count}")
                    print()

                    if result.get("history"):
                        print("Recent Runs:")
                        print("-" * 60)
                        for h in result["history"][:5]:
                            status = "OK" if h["success"] else "FAIL"
                            print(
                                f"  {h['recorded_at'][:19]} | {status} | "
                                f"size={h['universe_size']:3} | "
                                f"{h['global_regime'] or 'N/A':10} | "
                                f"{h['execution_time_seconds']:.1f}s"
                            )

        return 0

    except Exception as e:
        logger.exception(f"Command failed: {e}")
        print(f"Error: {e}")
        return 1
