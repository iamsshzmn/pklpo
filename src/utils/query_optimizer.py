"""
Утилиты для оптимизации запросов и анализа производительности
"""

import asyncio
import logging
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import INDICATORS_TABLE_NAME

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """Класс для оптимизации запросов и анализа производительности"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def analyze_query_plan(
        self, query: str, params: dict | None = None
    ) -> dict[str, Any]:
        """Анализирует план выполнения запроса"""
        try:
            explain_query = text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}")
            result = await self.session.execute(explain_query, params or {})
            plan_data = result.fetchone()

            if plan_data and plan_data[0]:
                plan = plan_data[0][0]
                return {
                    "execution_time": plan.get("Execution Time", 0),
                    "planning_time": plan.get("Planning Time", 0),
                    "total_cost": plan.get("Total Cost", 0),
                    "node_type": plan.get("Node Type", ""),
                    "actual_rows": plan.get("Actual Rows", 0),
                    "planned_rows": plan.get("Planned Rows", 0),
                }
            return {}
        except Exception as e:
            logger.error(f"Ошибка при анализе плана запроса: {e}")
            return {}

    async def benchmark_query(
        self, query: str, params: dict | None = None, iterations: int = 5
    ) -> dict[str, Any]:
        """Бенчмарк запроса с многократным выполнением"""
        times = []
        results = []

        for i in range(iterations):
            start_time = time.time()
            try:
                result = await self.session.execute(text(query), params or {})
                data = result.fetchall()
                results.append(len(data))

                end_time = time.time()
                execution_time = (end_time - start_time) * 1000
                times.append(execution_time)

                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка в итерации {i}: {e}")
                times.append(0)
                results.append(0)

        if times:
            return {
                "min_time": min(times),
                "max_time": max(times),
                "avg_time": sum(times) / len(times),
                "median_time": sorted(times)[len(times) // 2],
                "total_iterations": iterations,
                "successful_iterations": len([t for t in times if t > 0]),
                "avg_results": sum(results) / len(results) if results else 0,
            }
        return {}

    async def suggest_indexes(self, table_name: str) -> list[str]:
        """Предлагает индексы для таблицы на основе статистики"""
        try:
            stats_query = text(
                """
                SELECT attname, n_distinct, correlation
                FROM pg_stats
                WHERE schemaname = 'public' AND tablename = :table_name
                ORDER BY n_distinct DESC
            """
            )

            result = await self.session.execute(stats_query, {"table_name": table_name})
            suggestions = []

            for row in result.fetchall():
                if row.n_distinct > 100 and abs(row.correlation) < 0.8:
                    suggestions.append(
                        f"CREATE INDEX idx_{table_name}_{row.attname} ON {table_name}({row.attname})"
                    )

            return suggestions
        except Exception as e:
            logger.error(f"Ошибка при предложении индексов: {e}")
            return []


class QueryCache:
    """Кэш для запросов с TTL"""

    def __init__(self, ttl_seconds: int = 300):
        self.cache = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> Any | None:
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self.cache[key] = (value, time.time())

    def clear(self) -> None:
        self.cache.clear()

    def size(self) -> int:
        return len(self.cache)


async def optimize_common_queries(session: AsyncSession) -> dict[str, Any]:
    """Оптимизирует часто используемые запросы"""
    optimizer = QueryOptimizer(session)
    results = {}

    common_queries = [
        {
            "name": "get_symbols",
            "query": f"SELECT DISTINCT symbol FROM {INDICATORS_TABLE_NAME}",
            "params": {},
        },
        {
            "name": "get_timeframes",
            "query": f"SELECT DISTINCT timeframe FROM {INDICATORS_TABLE_NAME} WHERE symbol = :symbol",
            "params": {"symbol": "BTC-USDT"},
        },
        {
            "name": "get_latest_indicators",
            "query": f"""
                SELECT * FROM {INDICATORS_TABLE_NAME}
                WHERE symbol = :symbol AND timeframe = :timeframe
                ORDER BY timestamp DESC LIMIT 100
            """,
            "params": {"symbol": "BTC-USDT", "timeframe": "1m"},
        },
    ]

    for query_info in common_queries:
        print(f"\n🔍 Анализируем запрос: {query_info['name']}")

        plan = await optimizer.analyze_query_plan(
            query_info["query"], query_info["params"]
        )
        benchmark = await optimizer.benchmark_query(
            query_info["query"], query_info["params"]
        )

        results[query_info["name"]] = {"plan": plan, "benchmark": benchmark}

        print(f"  ⏱️ Среднее время: {benchmark.get('avg_time', 0):.2f}мс")
        print(f"  📊 Время выполнения: {plan.get('execution_time', 0):.2f}мс")

    return results


def create_query_optimizer(session: AsyncSession) -> QueryOptimizer:
    """Создает экземпляр QueryOptimizer"""
    return QueryOptimizer(session)


def create_query_cache(ttl_seconds: int = 300) -> QueryCache:
    """Создает экземпляр QueryCache"""
    return QueryCache(ttl_seconds)
