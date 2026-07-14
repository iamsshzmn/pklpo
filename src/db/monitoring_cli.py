#!/usr/bin/env python3
"""
CLI для работы с системой мониторинга и метрик.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.utils.session_utils import get_db_session


async def collect_metrics() -> None:
    """Собирает метрики производительности."""
    async with get_db_session() as session:
        try:
            # Вызываем функцию сбора метрик
            await session.execute(text("SELECT collect_performance_metrics()"))
            await session.commit()
            print("✅ Метрики собраны успешно")
        except Exception as e:
            print(f"❌ Ошибка при сборе метрик: {e}")


async def show_alerts(severity: str | None = None, limit: int = 20) -> None:
    """Показывает алерты."""
    async with get_db_session() as session:
        query = """
            SELECT
                id,
                created_at,
                alert_type,
                severity,
                title,
                message,
                resolved_at,
                resolved_by
            FROM alerts
        """
        params = {}

        if severity:
            query += " WHERE severity = :severity"
            params["severity"] = severity

        query += " ORDER BY created_at DESC LIMIT :limit"
        params["limit"] = limit

        result = await session.execute(text(query), params)
        alerts = result.fetchall()

        if not alerts:
            print("📭 Алертов не найдено")
            return

        print("🚨 АЛЕРТЫ")
        print("=" * 100)
        print(
            f"{'ID':<5} {'Создан':<20} {'Тип':<20} {'Уровень':<10} {'Заголовок':<30} {'Статус'}"
        )
        print("-" * 100)

        for alert in alerts:
            alert_id = alert[0]
            created_at = alert[1].strftime("%Y-%m-%d %H:%M:%S")
            alert_type = alert[2]
            severity = alert[3]
            title = alert[4][:27] + "..." if len(alert[4]) > 30 else alert[4]
            resolved_at = alert[6]

            status = "✅ Решен" if resolved_at else "⚠️ Активен"

            severity_icon = {
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "❌",
                "critical": "🚨",
            }.get(severity, "❓")

            print(
                f"{alert_id:<5} {created_at:<20} {alert_type:<20} {severity_icon} {severity:<8} {title:<30} {status}"
            )

        print("-" * 100)


async def show_metrics(hours: int = 24) -> None:
    """Показывает метрики за последние N часов."""
    async with get_db_session() as session:
        query = text(
            """
            SELECT
                metric_name,
                metric_value,
                metric_unit,
                description,
                collected_at
            FROM performance_metrics
            WHERE collected_at >= NOW() - INTERVAL ':hours hours'
            ORDER BY collected_at DESC, metric_name
        """
        )

        result = await session.execute(query, {"hours": hours})
        metrics = result.fetchall()

        if not metrics:
            print("📭 Метрик не найдено")
            return

        print(f"📊 МЕТРИКИ (последние {hours} часов)")
        print("=" * 80)
        print(f"{'Метрика':<25} {'Значение':<15} {'Единица':<10} {'Описание':<30}")
        print("-" * 80)

        for metric in metrics:
            name = metric[0]
            value = metric[1]
            unit = metric[2] or ""
            description = metric[3][:27] + "..." if len(metric[3]) > 30 else metric[3]

            # Форматируем значение
            if isinstance(value, int | float):
                if value > 1000000:
                    formatted_value = f"{value / 1000000:.2f}M"
                elif value > 1000:
                    formatted_value = f"{value / 1000:.2f}K"
                else:
                    formatted_value = f"{value:.2f}"
            else:
                formatted_value = str(value)

            print(f"{name:<25} {formatted_value:<15} {unit:<10} {description:<30}")

        print("-" * 80)


async def show_lock_logs(hours: int = 24) -> None:
    """Показывает логи блокировок."""
    async with get_db_session() as session:
        query = text(
            """
            SELECT
                detected_at,
                lock_type,
                table_name,
                lock_mode,
                granted,
                duration_ms,
                process_id
            FROM lock_logs
            WHERE detected_at >= NOW() - INTERVAL ':hours hours'
            ORDER BY detected_at DESC
            LIMIT 50
        """
        )

        result = await session.execute(query, {"hours": hours})
        locks = result.fetchall()

        if not locks:
            print("📭 Логов блокировок не найдено")
            return

        print(f"🔒 ЛОГИ БЛОКИРОВОК (последние {hours} часов)")
        print("=" * 90)
        print(
            f"{'Время':<20} {'Тип':<15} {'Таблица':<20} {'Режим':<10} {'Статус':<8} {'Длительность':<12} {'PID'}"
        )
        print("-" * 90)

        for lock in locks:
            detected_at = lock[0].strftime("%Y-%m-%d %H:%M:%S")
            lock_type = lock[1] or "N/A"
            table_name = lock[2] or "N/A"
            lock_mode = lock[3] or "N/A"
            granted = lock[4]
            duration_ms = lock[5] or 0
            process_id = lock[6] or 0

            status = "✅ Предоставлена" if granted else "⏳ Ожидает"

            print(
                f"{detected_at:<20} {lock_type:<15} {table_name:<20} {lock_mode:<10} {status:<8} {duration_ms}ms {process_id}"
            )

        print("-" * 90)


async def export_metrics_json(output_file: str | None = None) -> None:
    """Экспортирует метрики в JSON."""
    async with get_db_session() as session:
        try:
            # Вызываем функцию экспорта
            result = await session.execute(text("SELECT export_metrics_json()"))
            metrics_data = result.scalar()

            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(
                        metrics_data, f, indent=2, ensure_ascii=False, default=str
                    )
                print(f"✅ Метрики экспортированы в {output_file}")
            else:
                print(
                    json.dumps(metrics_data, indent=2, ensure_ascii=False, default=str)
                )

        except Exception as e:
            print(f"❌ Ошибка при экспорте метрик: {e}")


async def show_prometheus_metrics() -> None:
    """Показывает Prometheus-совместимые метрики."""
    async with get_db_session() as session:
        query = text(
            """
            SELECT
                metric_name,
                labels,
                value,
                timestamp
            FROM prometheus_metrics
            ORDER BY metric_name, labels
        """
        )

        result = await session.execute(query)
        metrics = result.fetchall()

        if not metrics:
            print("📭 Prometheus метрик не найдено")
            return

        print("📈 PROMETHEUS МЕТРИКИ")
        print("=" * 60)

        for metric in metrics:
            name = metric[0]
            labels = metric[1]
            value = metric[2]
            timestamp = metric[3]

            print(f"{name}{{{labels}}} {value} {int(timestamp.timestamp())}")


async def monitor_locks() -> None:
    """Запускает мониторинг блокировок."""
    async with get_db_session() as session:
        try:
            await session.execute(text("SELECT monitor_locks()"))
            await session.commit()
            print("✅ Мониторинг блокировок выполнен")
        except Exception as e:
            print(f"❌ Ошибка при мониторинге блокировок: {e}")


async def refresh_materialized_views() -> None:
    """Обновляет материализованные представления."""
    async with get_db_session() as session:
        try:
            await session.execute(text("SELECT refresh_materialized_views()"))
            await session.commit()
            print("✅ Материализованные представления обновлены")
        except Exception as e:
            print(f"❌ Ошибка при обновлении представлений: {e}")


def main():
    """Главная функция CLI."""
    parser = argparse.ArgumentParser(description="CLI для системы мониторинга и метрик")
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # Команда collect
    subparsers.add_parser("collect", help="Собрать метрики производительности")

    # Команда alerts
    alerts_parser = subparsers.add_parser("alerts", help="Показать алерты")
    alerts_parser.add_argument(
        "--severity",
        choices=["info", "warning", "error", "critical"],
        help="Фильтр по уровню важности",
    )
    alerts_parser.add_argument(
        "--limit", type=int, default=20, help="Количество алертов (по умолчанию: 20)"
    )

    # Команда metrics
    metrics_parser = subparsers.add_parser("metrics", help="Показать метрики")
    metrics_parser.add_argument(
        "--hours", type=int, default=24, help="Количество часов (по умолчанию: 24)"
    )

    # Команда locks
    locks_parser = subparsers.add_parser("locks", help="Показать логи блокировок")
    locks_parser.add_argument(
        "--hours", type=int, default=24, help="Количество часов (по умолчанию: 24)"
    )

    # Команда export
    export_parser = subparsers.add_parser(
        "export", help="Экспортировать метрики в JSON"
    )
    export_parser.add_argument(
        "--output",
        "-o",
        help="Файл для сохранения (если не указан, выводится в stdout)",
    )

    # Команда prometheus
    subparsers.add_parser("prometheus", help="Показать Prometheus метрики")

    # Команда monitor
    subparsers.add_parser("monitor", help="Запустить мониторинг блокировок")

    # Команда refresh
    subparsers.add_parser("refresh", help="Обновить материализованные представления")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Выполняем команду
    if args.command == "collect":
        asyncio.run(collect_metrics())
    elif args.command == "alerts":
        asyncio.run(show_alerts(args.severity, args.limit))
    elif args.command == "metrics":
        asyncio.run(show_metrics(args.hours))
    elif args.command == "locks":
        asyncio.run(show_lock_logs(args.hours))
    elif args.command == "export":
        asyncio.run(export_metrics_json(args.output))
    elif args.command == "prometheus":
        asyncio.run(show_prometheus_metrics())
    elif args.command == "monitor":
        asyncio.run(monitor_locks())
    elif args.command == "refresh":
        asyncio.run(refresh_materialized_views())


if __name__ == "__main__":
    main()
