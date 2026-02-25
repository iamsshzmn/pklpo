"""
Проверки качества данных market_data_ext.

Содержит:
- check_freshness: лаг витрины (последняя свеча)
- check_smoke_10m: smoke-тест за 10 минут
- check_coverage_1m: покрытие относительно OHLCV
- check_fill_rate: заполненность полей
- check_event_freshness: свежесть событий funding/oi/l2
"""


from asyncpg import Pool

from ..domain.quality import (
    COVERAGE_THRESHOLDS,
    FRESHNESS_THRESHOLDS,
    FUNDING_EVENT_LAG_THRESHOLDS,
    FUNDING_FILL_THRESHOLDS,
    L2_EVENT_LAG_THRESHOLDS,
    L2_FILL_THRESHOLDS,
    OI_EVENT_LAG_THRESHOLDS,
    OI_FILL_THRESHOLDS,
    SMOKE_THRESHOLDS,
    CheckResult,
    QualityReport,
    Thresholds,
)


async def check_freshness(
    pool: Pool,
    thresholds: Thresholds = FRESHNESS_THRESHOLDS,
) -> list[CheckResult]:
    """
    Проверка лага витрины: now() - max(bar_timestamp) по timeframe='1m'.

    Returns:
        Список CheckResult по каждому symbol.
    """
    query = """
        SELECT
            symbol,
            EXTRACT(EPOCH FROM (now() - MAX(bar_timestamp))) / 60.0 AS lag_min
        FROM core.market_data_ext
        WHERE timeframe = '1m'
        GROUP BY symbol
    """
    results: list[CheckResult] = []
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)

    for row in rows:
        symbol = row["symbol"]
        lag_min = row["lag_min"]
        severity = thresholds.evaluate(lag_min)
        results.append(
            CheckResult(
                check_name="freshness",
                severity=severity,
                symbol=symbol,
                timeframe="1m",
                value=round(lag_min, 2) if lag_min else None,
                meta={
                    "thresholds": {"warn": thresholds.warn, "critical": thresholds.critical},
                },
            )
        )
    return results


async def check_smoke_10m(
    pool: Pool,
    min_rows: int = 8,
) -> list[CheckResult]:
    """
    Smoke-тест: за последние 10 минут должно быть минимум min_rows строк.

    Returns:
        Список CheckResult только для проблемных symbols (rows < min_rows).
    """
    query = """
        WITH recent AS (
            SELECT symbol, COUNT(*) AS rows_10m
            FROM core.market_data_ext
            WHERE timeframe = '1m'
              AND bar_timestamp >= now() - interval '10 minutes'
            GROUP BY symbol
        )
        SELECT symbol, rows_10m
        FROM recent
        WHERE rows_10m < $1
    """
    results: list[CheckResult] = []
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, min_rows)

    for row in rows:
        symbol = row["symbol"]
        rows_10m = row["rows_10m"]
        severity = SMOKE_THRESHOLDS.evaluate(rows_10m)
        results.append(
            CheckResult(
                check_name="smoke_10m",
                severity=severity,
                symbol=symbol,
                timeframe="1m",
                value=rows_10m,
                meta={"min_required": min_rows},
            )
        )
    return results


async def check_coverage_1m(
    pool: Pool,
    window_minutes: int = 60,
    thresholds: Thresholds = COVERAGE_THRESHOLDS,
) -> list[CheckResult]:
    """
    Покрытие market_data_ext относительно OHLCV за последние N минут.

    Returns:
        Список CheckResult по каждому symbol.
    """
    query = """
        WITH bars AS (
            SELECT symbol, ts AS bar_ts
            FROM swap.swap_ohlcv_p
            WHERE timeframe = '1m'
              AND ts >= now() - ($1 || ' minutes')::interval
        ),
        ext AS (
            SELECT symbol, bar_timestamp AS bar_ts
            FROM core.market_data_ext
            WHERE timeframe = '1m'
              AND bar_timestamp >= now() - ($1 || ' minutes')::interval
        )
        SELECT
            b.symbol,
            COUNT(*) AS ohlcv_minutes,
            COUNT(e.bar_ts) AS ext_minutes,
            ROUND(100.0 * COUNT(e.bar_ts) / NULLIF(COUNT(*), 0), 2) AS coverage_pct
        FROM bars b
        LEFT JOIN ext e
            ON e.symbol = b.symbol AND e.bar_ts = b.bar_ts
        GROUP BY b.symbol
    """
    results: list[CheckResult] = []
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, str(window_minutes))

    for row in rows:
        symbol = row["symbol"]
        coverage_pct = float(row["coverage_pct"]) if row["coverage_pct"] else 0.0
        severity = thresholds.evaluate(coverage_pct)
        results.append(
            CheckResult(
                check_name="coverage_1m",
                severity=severity,
                symbol=symbol,
                timeframe="1m",
                value=coverage_pct,
                meta={
                    "ohlcv_minutes": row["ohlcv_minutes"],
                    "ext_minutes": row["ext_minutes"],
                    "window_minutes": window_minutes,
                    "thresholds": {"warn": thresholds.warn, "critical": thresholds.critical},
                },
            )
        )
    return results


async def check_fill_rate(
    pool: Pool,
    window_hours: int = 6,
) -> list[CheckResult]:
    """
    Заполненность полей funding_rate, open_interest, l2 за последние N часов.

    Returns:
        Список CheckResult (3 записи на symbol: funding, oi, l2).
    """
    query = """
        SELECT
            symbol,
            COUNT(*) AS rows_cnt,
            ROUND(100.0 * COUNT(*) FILTER (WHERE funding_rate IS NOT NULL)
                / NULLIF(COUNT(*), 0), 2) AS funding_fill_pct,
            ROUND(100.0 * COUNT(*) FILTER (WHERE open_interest IS NOT NULL)
                / NULLIF(COUNT(*), 0), 2) AS oi_fill_pct,
            ROUND(100.0 * COUNT(*) FILTER (WHERE spread_bps IS NOT NULL OR imbalance IS NOT NULL)
                / NULLIF(COUNT(*), 0), 2) AS l2_fill_pct
        FROM core.market_data_ext
        WHERE timeframe = '1m'
          AND bar_timestamp >= now() - ($1 || ' hours')::interval
        GROUP BY symbol
    """
    results: list[CheckResult] = []
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, str(window_hours))

    for row in rows:
        symbol = row["symbol"]
        # Funding fill
        funding_pct = float(row["funding_fill_pct"]) if row["funding_fill_pct"] else 0.0
        results.append(
            CheckResult(
                check_name="fill_rate_funding",
                severity=FUNDING_FILL_THRESHOLDS.evaluate(funding_pct),
                symbol=symbol,
                timeframe="1m",
                value=funding_pct,
                meta={"window_hours": window_hours},
            )
        )
        # OI fill
        oi_pct = float(row["oi_fill_pct"]) if row["oi_fill_pct"] else 0.0
        results.append(
            CheckResult(
                check_name="fill_rate_oi",
                severity=OI_FILL_THRESHOLDS.evaluate(oi_pct),
                symbol=symbol,
                timeframe="1m",
                value=oi_pct,
                meta={"window_hours": window_hours},
            )
        )
        # L2 fill
        l2_pct = float(row["l2_fill_pct"]) if row["l2_fill_pct"] else 0.0
        results.append(
            CheckResult(
                check_name="fill_rate_l2",
                severity=L2_FILL_THRESHOLDS.evaluate(l2_pct),
                symbol=symbol,
                timeframe="1m",
                value=l2_pct,
                meta={"window_hours": window_hours},
            )
        )
    return results


async def check_event_freshness(
    pool: Pool,
    window_hours: int = 6,
) -> list[CheckResult]:
    """
    Свежесть событий: funding_ts, oi_ts, l2_ts.

    Returns:
        Список CheckResult (3 записи на symbol).
    """
    query = """
        SELECT
            symbol,
            EXTRACT(EPOCH FROM (now() - MAX(funding_ts))) / 60.0 AS funding_lag_min,
            EXTRACT(EPOCH FROM (now() - MAX(oi_ts))) / 60.0 AS oi_lag_min,
            EXTRACT(EPOCH FROM (now() - MAX(l2_ts))) / 60.0 AS l2_lag_min
        FROM core.market_data_ext
        WHERE timeframe = '1m'
          AND bar_timestamp >= now() - ($1 || ' hours')::interval
        GROUP BY symbol
    """
    results: list[CheckResult] = []
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, str(window_hours))

    for row in rows:
        symbol = row["symbol"]
        # Funding event lag
        funding_lag = row["funding_lag_min"]
        results.append(
            CheckResult(
                check_name="event_freshness_funding",
                severity=FUNDING_EVENT_LAG_THRESHOLDS.evaluate(funding_lag),
                symbol=symbol,
                timeframe="1m",
                value=round(funding_lag, 2) if funding_lag else None,
                meta={"window_hours": window_hours},
            )
        )
        # OI event lag
        oi_lag = row["oi_lag_min"]
        results.append(
            CheckResult(
                check_name="event_freshness_oi",
                severity=OI_EVENT_LAG_THRESHOLDS.evaluate(oi_lag),
                symbol=symbol,
                timeframe="1m",
                value=round(oi_lag, 2) if oi_lag else None,
                meta={"window_hours": window_hours},
            )
        )
        # L2 event lag
        l2_lag = row["l2_lag_min"]
        results.append(
            CheckResult(
                check_name="event_freshness_l2",
                severity=L2_EVENT_LAG_THRESHOLDS.evaluate(l2_lag),
                symbol=symbol,
                timeframe="1m",
                value=round(l2_lag, 2) if l2_lag else None,
                meta={"window_hours": window_hours},
            )
        )
    return results


async def run_all_checks(pool: Pool) -> QualityReport:
    """Запустить все проверки и вернуть агрегированный отчет."""
    report = QualityReport()

    # День 1: freshness + smoke
    report.extend(await check_freshness(pool))
    report.extend(await check_smoke_10m(pool))

    # День 2: coverage
    report.extend(await check_coverage_1m(pool))

    # День 3: fill-rate + event freshness
    report.extend(await check_fill_rate(pool))
    report.extend(await check_event_freshness(pool))

    return report
