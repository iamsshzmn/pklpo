"""
CLI для управления метаданными рынка.

Команды:
- refresh: обновление метаданных с OKX
- validate: валидация ордера
- info: информация об инструменте
- cache: управление кэшем
"""

import asyncio
import json
import os

import click

from ..application.api import (
    get_instrument_info,
    market_meta_api,
    refresh_okx_meta,
    validate_order,
)
from ..infrastructure.config import get_config, reload_config
from ..infrastructure.database import create_tables, drop_tables
from ..infrastructure.logging_config import configure_logging
from ..infrastructure.metrics import (
    get_metrics_collector,
    get_metrics_monitor,
    start_metrics_services,
    stop_metrics_services,
)


@click.group()
def market_meta():
    """Управление метаданными рынка"""
    pass


@market_meta.command()
@click.option("--force", is_flag=True, help="Принудительное обновление")
@click.option(
    "--types", default="SPOT,SWAP,FUTURES", help="Типы инструментов для загрузки"
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def refresh(force: bool, types: str, verbose: bool):
    """Обновить метаданные с OKX"""
    click.echo("🔄 Обновление метаданных OKX...")

    async def _refresh():
        try:
            # Парсим типы инструментов
            inst_types = [t.strip() for t in types.split(",")]

            if verbose:
                click.echo(f"Загружаем типы: {inst_types}")

            # Обновляем метаданные
            success = await refresh_okx_meta(force=force)

            if success:
                click.echo("✅ Метаданные успешно обновлены")

                if verbose:
                    # Показываем статистику
                    if market_meta_api.market_metadata:
                        total = len(market_meta_api.market_metadata.instruments)
                        click.echo(f"Загружено инструментов: {total}")

                        # Группируем по типам
                        by_type = {}
                        for (
                            instrument
                        ) in market_meta_api.market_metadata.instruments.values():
                            inst_type = instrument.inst_type.value
                            by_type[inst_type] = by_type.get(inst_type, 0) + 1

                        for inst_type, count in by_type.items():
                            click.echo(f"  {inst_type}: {count}")
            else:
                click.echo("❌ Ошибка обновления метаданных", err=True)
                return 1

        except Exception as e:
            click.echo(f"❌ Ошибка: {e}", err=True)
            return 1

    return asyncio.run(_refresh())


@market_meta.command()
@click.argument("symbol")
@click.option("--price", "-p", type=float, required=True, help="Цена")
@click.option("--qty", "-q", type=float, required=True, help="Количество")
@click.option("--balance", "-b", type=float, help="Баланс аккаунта")
@click.option("--order-type", default="limit", help="Тип ордера (limit/market)")
@click.option("--side", default="buy", help="Сторона (buy/sell)")
@click.option("--leverage", type=float, help="Плечо")
@click.option("--margin-mode", default="isolated", help="Режим маржи (isolated/cross)")
@click.option("--spread-bps", type=float, help="Спред в базисных пунктах")
@click.option("--vol-usdt", type=float, help="Объем за 24ч в USDT")
@click.option("--book-depth", type=float, help="Глубина стакана в USDT")
@click.option("--json", "output_json", is_flag=True, help="Вывод в JSON")
def validate(
    symbol: str,
    price: float,
    qty: float,
    balance: float | None,
    order_type: str,
    side: str,
    leverage: float | None,
    margin_mode: str,
    spread_bps: float | None,
    vol_usdt: float | None,
    book_depth: float | None,
    output_json: bool,
):
    """Валидировать ордер"""

    # Проверяем, загружены ли метаданные
    if not market_meta_api.market_metadata:
        click.echo("❌ Метаданные не загружены. Выполните 'refresh'", err=True)
        return 1

    # Валидируем ордер
    violations = validate_order(
        symbol=symbol,
        price=price,
        qty=qty,
        order_type=order_type,
        side=side,
        account_balance=balance,
    )

    # Дополнительная валидация рисков и ликвидности
    if leverage is not None or spread_bps is not None:
        if market_meta_api.validator:
            # Валидация рисков
            if leverage is not None:
                risk_result = market_meta_api.validator.validate_risk(
                    symbol, leverage, margin_mode
                )
                if not risk_result.is_valid:
                    violations.extend(risk_result.errors)

            # Валидация ликвидности
            if all(param is not None for param in [spread_bps, vol_usdt, book_depth]):
                liquidity_result = market_meta_api.validator.validate_liquidity(
                    symbol, spread_bps, vol_usdt, book_depth
                )
                if not liquidity_result.is_valid:
                    violations.extend(liquidity_result.errors)

    # Выводим результат
    if output_json:
        result = {
            "symbol": symbol,
            "price": price,
            "qty": qty,
            "is_valid": len(violations) == 0,
            "violations": violations,
            "violations_count": len(violations),
        }
        click.echo(json.dumps(result, indent=2))
    else:
        if violations:
            click.echo(f"❌ Найдено {len(violations)} нарушений:")
            for i, violation in enumerate(violations, 1):
                click.echo(f"  {i}. {violation}")
        else:
            click.echo("✅ Ордер валиден")

    return 0 if not violations else 1


@market_meta.command()
@click.argument("symbol")
@click.option("--json", "output_json", is_flag=True, help="Вывод в JSON")
def info(symbol: str, output_json: bool):
    """Получить информацию об инструменте"""

    # Проверяем, загружены ли метаданные
    if not market_meta_api.market_metadata:
        click.echo("❌ Метаданные не загружены. Выполните 'refresh'", err=True)
        return 1

    # Получаем информацию
    info = get_instrument_info(symbol)

    if not info:
        click.echo(f"❌ Инструмент {symbol} не найден", err=True)
        return 1

    if output_json:
        click.echo(json.dumps(info, indent=2))
    else:
        click.echo(f"📊 Информация об инструменте: {symbol}")
        click.echo(f"  Тип: {info['inst_type']}")
        click.echo(f"  Базовая валюта: {info['base_ccy']}")
        click.echo(f"  Котируемая валюта: {info['quote_ccy']}")
        click.echo(f"  Торгуется: {'✅' if info['is_tradable'] else '❌'}")

        if info["tick_size"]:
            click.echo(f"  Размер тика: {info['tick_size']['step']}")

        if info["lot_size"]:
            click.echo(f"  Размер лота: {info['lot_size']['step']}")

        if info["contract_val"]:
            click.echo(f"  Номинальная стоимость: {info['contract_val']}")

        if info["margin_mode"]:
            click.echo(f"  Режим маржи: {info['margin_mode']}")

    return 0


@market_meta.command()
def cache():
    """Показать статус кэша метаданных"""
    if not market_meta_api.market_metadata:
        click.echo("❌ Метаданные не загружены")
        return 1

    status = market_meta_api.get_cache_status()

    click.echo("📊 Статус кэша метаданных:")
    click.echo(f"  Актуален: {'✅' if status['is_valid'] else '❌'}")
    click.echo(f"  Последнее обновление: {status['last_refresh'] or 'Нет'}")
    click.echo(f"  TTL: {status['ttl_hours']:.1f} часов")
    click.echo(f"  Авто-refresh: {'✅' if status['auto_refresh_enabled'] else '❌'}")
    click.echo(f"  Инструментов: {status['instruments_count']}")
    return None


@market_meta.command()
@click.option("--hours", type=int, default=1, help="TTL в часах")
def set_ttl(hours: int):
    """Установить TTL кэша"""
    market_meta_api.set_cache_ttl(hours)
    click.echo(f"✅ TTL установлен на {hours} часов")


@market_meta.command()
def clear_cache():
    """Очистить кэш метаданных"""
    market_meta_api._last_refresh = None
    click.echo("✅ Кэш очищен")


@market_meta.command()
@click.option(
    "--enable/--disable", default=True, help="Включить/выключить авто-refresh"
)
def auto_refresh(enable: bool):
    """Управление авто-refresh"""
    if enable:
        market_meta_api._auto_refresh_enabled = True
        market_meta_api.start_auto_refresh()
        click.echo("✅ Авто-refresh включен")
    else:
        market_meta_api.stop_auto_refresh()
        click.echo("✅ Авто-refresh выключен")


@market_meta.command()
@click.option("--drop", is_flag=True, help="Удалить таблицы")
@click.option("--create", is_flag=True, help="Создать таблицы")
def db(drop: bool, create: bool):
    """Управление базой данных"""

    # TODO: Получить engine из конфигурации
    from sqlalchemy import create_engine

    engine = create_engine("postgresql://localhost/market_meta")

    if drop:
        click.echo("🗑️ Удаление таблиц market_meta...")
        drop_tables(engine)
        click.echo("✅ Таблицы удалены")

    if create:
        click.echo("📊 Создание таблиц market_meta...")
        create_tables(engine)
        click.echo("✅ Таблицы созданы")

    if not drop and not create:
        click.echo("Используйте --create для создания или --drop для удаления таблиц")


@market_meta.command()
def status():
    """Показать статус модуля"""

    click.echo("📊 Статус модуля market_meta:")

    # Проверяем метаданные
    if market_meta_api.market_metadata:
        total = len(market_meta_api.market_metadata.instruments)
        click.echo(f"  Метаданные: ✅ Загружено {total} инструментов")

        # Группируем по типам
        by_type = {}
        for instrument in market_meta_api.market_metadata.instruments.values():
            inst_type = instrument.inst_type.value
            by_type[inst_type] = by_type.get(inst_type, 0) + 1

        for inst_type, count in by_type.items():
            click.echo(f"    {inst_type}: {count}")
    else:
        click.echo("  Метаданные: ❌ Не загружены")

    # Проверяем валидаторы
    if market_meta_api.validator:
        click.echo("  Валидаторы: ✅ Инициализированы")
    else:
        click.echo("  Валидаторы: ❌ Не инициализированы")

    # Проверяем лимиты риска
    if market_meta_api.risk_limits:
        click.echo("  Лимиты риска: ✅ Настроены")
    else:
        click.echo("  Лимиты риска: ❌ Не настроены")


@market_meta.command()
@click.option("--level", default="INFO", help="Уровень логирования")
@click.option("--file", help="Файл для логов")
@click.option("--console/--no-console", default=True, help="Вывод в консоль")
@click.option("--file-output/--no-file-output", default=True, help="Запись в файл")
def setup_logging(level: str, file: str, console: bool, file_output: bool):
    """Настроить логирование"""

    configure_logging(
        level=level, log_file=file, console_output=console, file_output=file_output
    )

    click.echo("✅ Логирование настроено:")
    click.echo(f"  Уровень: {level}")
    click.echo(f"  Файл: {file or 'market_meta.log'}")
    click.echo(f"  Консоль: {'✅' if console else '❌'}")
    click.echo(f"  Файл: {'✅' if file_output else '❌'}")


@market_meta.command()
def logs():
    """Показать последние логи"""

    from pathlib import Path

    log_file = Path("market_meta.log")
    if not log_file.exists():
        click.echo("❌ Файл логов не найден")
        return

    try:
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
            # Показываем последние 20 строк
            recent_lines = lines[-20:] if len(lines) > 20 else lines

            click.echo("📋 Последние логи:")
            for line in recent_lines:
                click.echo(f"  {line.strip()}")

    except Exception as e:
        click.echo(f"❌ Ошибка чтения логов: {e}")


@market_meta.command()
def clear_logs():
    """Очистить файлы логов"""

    from pathlib import Path

    log_files = [
        Path("market_meta.log"),
        Path("logs/market_meta.log"),
        Path("logs/market_meta_errors.log"),
    ]

    cleared = 0
    for log_file in log_files:
        if log_file.exists():
            try:
                log_file.unlink()
                click.echo(f"✅ Удален: {log_file}")
                cleared += 1
            except Exception as e:
                click.echo(f"❌ Ошибка удаления {log_file}: {e}")

    if cleared == 0:
        click.echo("ℹ️ Файлы логов не найдены")
    else:
        click.echo(f"✅ Очищено файлов: {cleared}")


@market_meta.command()
@click.option("--json", "output_json", is_flag=True, help="Вывод в JSON")
@click.option("--env", is_flag=True, help="Показать переменные окружения")
def config(output_json: bool, env: bool):
    """Показать текущую конфигурацию"""

    try:
        config = get_config()

        if output_json:
            click.echo(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
        else:
            click.echo("⚙️ Конфигурация market_meta:")
            click.echo(f"  Окружение: {config.environment}")
            click.echo(f"  Режим отладки: {'✅' if config.debug_mode else '❌'}")
            click.echo(f"  Директория данных: {config.data_dir}")

            click.echo("\n🔗 OKX API:")
            click.echo(f"  URL: {config.okx.base_url}")
            click.echo(f"  Таймаут: {config.okx.timeout_seconds}с")
            click.echo(f"  Rate limit: {config.okx.max_requests_per_second}/сек")
            click.echo(f"  Retry: {config.okx.max_retries} попыток")

            click.echo("\n💾 Кэширование:")
            click.echo(f"  TTL метаданных: {config.cache.metadata_ttl_hours}ч")
            click.echo(
                f"  Авто-refresh: {'✅' if config.cache.auto_refresh_enabled else '❌'}"
            )
            click.echo(f"  Интервал: {config.cache.auto_refresh_interval_hours}ч")

            click.echo("\n📝 Логирование:")
            click.echo(f"  Уровень: {config.logging.log_level}")
            click.echo(f"  Формат: {config.logging.log_format}")
            click.echo(f"  Файл: {config.logging.log_file or 'market_meta.log'}")
            click.echo(
                f"  Маскировка API ключей: {'✅' if config.logging.mask_api_keys else '❌'}"
            )

            click.echo("\n✅ Валидация:")
            click.echo(
                f"  Строгий режим: {'✅' if config.validation.strict_mode else '❌'}"
            )
            click.echo(
                f"  Разрешить предупреждения: {'✅' if config.validation.allow_warnings else '❌'}"
            )
            click.echo(
                f"  Проверка рисков: {'✅' if config.validation.validate_risk_limits else '❌'}"
            )

            click.echo("\n⚠️ Риск-менеджмент:")
            click.echo(
                f"  Макс. размер позиции: ${config.risk.max_position_size_usd:,.0f}"
            )
            click.echo(
                f"  Макс. общая экспозиция: ${config.risk.max_total_exposure_usd:,.0f}"
            )
            click.echo(f"  Макс. плечо: {config.risk.max_leverage}x")
            click.echo(f"  Толерантность к риску: {config.risk.risk_tolerance}")

            click.echo("\n📊 Метрики:")
            click.echo(f"  Включены: {'✅' if config.metrics.enabled else '❌'}")
            click.echo(f"  Экспорт: {'✅' if config.metrics.export_metrics else '❌'}")
            click.echo(f"  Порт: {config.metrics.metrics_port}")

        if env:
            click.echo("\n🔧 Переменные окружения:")
            env_vars = [
                "MARKET_META_ENVIRONMENT",
                "MARKET_META_DEBUG_MODE",
                "OKX_API_KEY",
                "OKX_BASE_URL",
                "MARKET_META_CACHE_TTL_HOURS",
                "MARKET_META_LOG_LEVEL",
                "MARKET_META_STRICT_VALIDATION",
                "MARKET_META_MAX_POSITION_SIZE_USD",
            ]

            for var in env_vars:
                value = os.environ.get(var, "не установлена")
                if var in ["OKX_API_KEY"] and value != "не установлена":
                    value = "***"
                click.echo(f"  {var}: {value}")

    except Exception as e:
        click.echo(f"❌ Ошибка загрузки конфигурации: {e}", err=True)
        return 1


@market_meta.command()
def reload_config_cmd():
    """Перезагрузить конфигурацию из переменных окружения"""

    try:
        config = reload_config()
        click.echo("✅ Конфигурация перезагружена")
        click.echo(f"  Окружение: {config.environment}")
        click.echo(f"  Режим отладки: {'✅' if config.debug_mode else '❌'}")

    except Exception as e:
        click.echo(f"❌ Ошибка перезагрузки конфигурации: {e}", err=True)
        return 1


@market_meta.command()
@click.option("--validate", is_flag=True, help="Проверить конфигурацию")
def validate_config(validate: bool):
    """Проверить конфигурацию"""

    try:
        config = get_config()

        if validate:
            errors = config.validate()
            if errors:
                click.echo("❌ Ошибки в конфигурации:")
                for error in errors:
                    click.echo(f"  - {error}")
                return 1
            click.echo("✅ Конфигурация корректна")
        else:
            click.echo("ℹ️ Используйте --validate для проверки конфигурации")

    except Exception as e:
        click.echo(f"❌ Ошибка проверки конфигурации: {e}", err=True)
        return 1


@market_meta.command()
@click.option("--json", "output_json", is_flag=True, help="Вывод в JSON")
@click.option("--prometheus", is_flag=True, help="Вывод в формате Prometheus")
def metrics(output_json: bool, prometheus: bool):
    """Показать метрики"""

    try:
        collector = get_metrics_collector()

        if prometheus:
            click.echo(collector.export_metrics("prometheus"))
        elif output_json:
            click.echo(collector.export_metrics("json"))
        else:
            summary = collector.get_metrics_summary()

            click.echo("📊 Метрики market_meta:")

            # Cache метрики
            cache_hit = summary.get("cache_hit_ratio", {})
            if cache_hit.get("latest") is not None:
                click.echo(f"  Cache hit ratio: {cache_hit['latest']:.1f}%")

            # Validation метрики
            validation_success = summary.get("validation_success_rate", {})
            if validation_success.get("latest") is not None:
                click.echo(
                    f"  Validation success rate: {validation_success['latest']:.1f}%"
                )

            # API метрики
            api_latency = summary.get("api_request_duration", {})
            if api_latency.get("latest") is not None:
                click.echo(f"  API latency: {api_latency['latest']:.3f}s")

            api_success = summary.get("api_success_rate", {})
            if api_success.get("latest") is not None:
                click.echo(f"  API success rate: {api_success['latest']:.1f}%")

            # OKX метрики
            okx_latency = summary.get("okx_request_duration", {})
            if okx_latency.get("latest") is not None:
                click.echo(f"  OKX latency: {okx_latency['latest']:.3f}s")

            okx_retries = summary.get("okx_retry_count", {})
            if okx_retries.get("count_5m", 0) > 0:
                click.echo(f"  OKX retries (5m): {okx_retries['count_5m']}")

            # Error метрики
            error_rate = summary.get("error_rate", {})
            if error_rate.get("latest") is not None:
                click.echo(f"  Error rate: {error_rate['latest']:.1f}%")

    except Exception as e:
        click.echo(f"❌ Ошибка получения метрик: {e}", err=True)
        return 1


@market_meta.command()
@click.option("--hours", type=int, default=24, help="Количество часов для просмотра")
def alerts(hours: int):
    """Показать алерты"""

    try:
        monitor = get_metrics_monitor()
        alerts = monitor.get_alerts(hours=hours)

        if not alerts:
            click.echo(f"ℹ️ Алертов за последние {hours} часов нет")
            return None

        click.echo(f"⚠️ Алерты за последние {hours} часов:")
        for i, alert in enumerate(alerts, 1):
            click.echo(f"  {i}. {alert['type']} - {alert['timestamp']}")
            if "context" in alert:
                for key, value in alert["context"].items():
                    click.echo(f"     {key}: {value}")

    except Exception as e:
        click.echo(f"❌ Ошибка получения алертов: {e}", err=True)
        return 1


@market_meta.command()
async def start_metrics():
    """Запустить сервисы метрик"""

    try:
        await start_metrics_services()
        click.echo("✅ Сервисы метрик запущены")

        # Показываем информацию о портах
        config = get_config()
        if config.metrics.export_metrics:
            click.echo(
                f"📊 Метрики доступны на http://localhost:{config.metrics.metrics_port}/metrics"
            )
            click.echo(
                f"🏥 Health check: http://localhost:{config.metrics.metrics_port}/health"
            )

    except Exception as e:
        click.echo(f"❌ Ошибка запуска сервисов метрик: {e}", err=True)
        return 1


@market_meta.command()
async def stop_metrics():
    """Остановить сервисы метрик"""

    try:
        await stop_metrics_services()
        click.echo("✅ Сервисы метрик остановлены")

    except Exception as e:
        click.echo(f"❌ Ошибка остановки сервисов метрик: {e}", err=True)
        return 1


@market_meta.command()
@click.option(
    "--symbols",
    required=True,
    help="Список символов через запятую (например: BTC-USDT-SWAP,ETH-USDT-SWAP)",
)
@click.option(
    "--timeframes",
    default="1m,5m,15m,1H",
    help="Список таймфреймов через запятую (по умолчанию: 1m,5m,15m,1H)",
)
@click.option(
    "--start-time",
    default=None,
    help="Начало периода (ISO format, например: 2025-01-01T00:00:00Z)",
)
@click.option(
    "--end-time",
    default=None,
    help="Конец периода (ISO format, например: 2025-01-02T00:00:00Z)",
)
@click.option(
    "--types",
    default="funding,oi,l2",
    help="Типы данных для загрузки (по умолчанию: funding,oi,l2)",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def sync_market_data_ext(
    symbols: str,
    timeframes: str,
    start_time: str | None,
    end_time: str | None,
    types: str,
    verbose: bool,
):
    """
    Синхронизация расширенных рыночных данных.

    Загружает, нормализует, агрегирует и сохраняет данные в market_data_ext.
    """
    import asyncio
    from datetime import datetime

    from sqlalchemy import create_engine

    from ..infrastructure.aggregator import MarketDataAggregator
    from ..infrastructure.data_loader import MarketDataLoader
    from ..infrastructure.database import MarketDataExtRepository
    from ..infrastructure.normalizer import MarketDataNormalizer
    from ..infrastructure.ohlcv_aligner import OHLCVAligner

    async def _sync_async():
        try:
            # Парсим параметры
            symbol_list = [s.strip() for s in symbols.split(",")]
            timeframe_list = [tf.strip() for tf in timeframes.split(",")]
            type_list = [t.strip() for t in types.split(",")]

            # Парсим даты
            start_dt = None
            end_dt = None
            if start_time:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            if end_time:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            if verbose:
                click.echo(f"Символы: {symbol_list}")
                click.echo(f"Таймфреймы: {timeframe_list}")
                click.echo(f"Типы данных: {type_list}")
                if start_dt:
                    click.echo(f"Начало: {start_dt}")
                if end_dt:
                    click.echo(f"Конец: {end_dt}")

            # Создаём sync engine для репозитория
            from src.config.env_validator import get_database_url

            database_url = get_database_url()
            # Конвертируем async URL в sync (убираем +asyncpg)
            if database_url.startswith("postgresql+asyncpg://"):
                database_url = database_url.replace(
                    "postgresql+asyncpg://", "postgresql://"
                )
            elif database_url.startswith("postgresql+psycopg2://"):
                database_url = database_url.replace(
                    "postgresql+psycopg2://", "postgresql://"
                )
            engine = create_engine(database_url, pool_pre_ping=True)

            # Инициализируем компоненты
            aligner = OHLCVAligner(engine)
            loader = MarketDataLoader()
            normalizer = MarketDataNormalizer(aligner)
            aggregator = MarketDataAggregator(aligner)
            repo = MarketDataExtRepository(engine)

            # Загружаем 1m бары для всех символов
            for symbol in symbol_list:
                aligner.load_bar_timestamps(
                    symbol, "1m", start_time=start_dt, end_time=end_dt
                )

            # Загружаем данные
            click.echo("📥 Загрузка данных с OKX...")
            all_data = await loader.load_all(symbol_list, start_dt, end_dt)

            total_records = 0

            # Обрабатываем каждый тип данных
            for data_type in type_list:
                if data_type not in all_data:
                    continue

                records = all_data[data_type]
                if not records:
                    continue

                click.echo(f"📊 Обработка {data_type}: {len(records)} записей")

                # Нормализуем к 1m барам
                normalized_1m = []
                for symbol in symbol_list:
                    symbol_records = [r for r in records if r.get("symbol") == symbol]
                    if symbol_records:
                        normalized = normalizer.normalize_to_1m_bars(
                            symbol_records, symbol
                        )
                        normalized_1m.extend(normalized)

                if not normalized_1m:
                    continue

                # Сохраняем 1m данные
                saved_1m = repo.upsert_records(normalized_1m)
                total_records += saved_1m
                click.echo(f"✅ Сохранено {saved_1m} записей 1m для {data_type}")

                # Агрегируем для других таймфреймов
                import pandas as pd

                df_1m = pd.DataFrame(normalized_1m)
                if not df_1m.empty and "bar_timestamp" in df_1m.columns:
                    for tf in timeframe_list:
                        if tf == "1m":
                            continue

                        click.echo(f"📈 Агрегация {data_type} {tf}...")

                        # Агрегируем для каждого символа отдельно
                        all_agg_records = []
                        for symbol in symbol_list:
                            # Фильтруем данные по символу
                            df_symbol = df_1m[df_1m["symbol"] == symbol].copy()
                            if df_symbol.empty:
                                continue

                            df_agg = aggregator.aggregate_1m_to_timeframe(
                                df_symbol, symbol, tf, start_dt, end_dt
                            )

                            if not df_agg.empty:
                                agg_records = df_agg.reset_index().to_dict("records")
                                # Убеждаемся, что symbol присутствует в записях
                                for rec in agg_records:
                                    if "symbol" not in rec:
                                        rec["symbol"] = symbol
                                all_agg_records.extend(agg_records)

                        if all_agg_records:
                            saved_agg = repo.upsert_records(all_agg_records)
                            total_records += saved_agg
                            click.echo(
                                f"✅ Сохранено {saved_agg} записей {tf} для {data_type}"
                            )

            click.echo(f"✅ Всего сохранено {total_records} записей")

        except Exception as e:
            click.echo(f"❌ Ошибка: {e}", err=True)
            if verbose:
                import traceback

                traceback.print_exc()
            return 1

    return asyncio.run(_sync_async())


@market_meta.command("cleanup-market-data-ext")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Только показать, что будет удалено, без фактического удаления",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def cleanup_market_data_ext(dry_run: bool, verbose: bool):
    """
    Очистка старых расширенных рыночных данных согласно retention-политикам.

    L2: 7 дней, OI: 90 дней, Funding: 730 дней.
    """

    from sqlalchemy import create_engine

    from ..infrastructure.retention import MarketDataExtRetention

    try:
        from src.config.env_validator import get_database_url

        database_url = get_database_url()
        # Конвертируем async URL в sync
        if database_url.startswith("postgresql+asyncpg://"):
            database_url = database_url.replace(
                "postgresql+asyncpg://", "postgresql://"
            )
        elif database_url.startswith("postgresql+psycopg2://"):
            database_url = database_url.replace(
                "postgresql+psycopg2://", "postgresql://"
            )
        engine = create_engine(database_url, pool_pre_ping=True)

        retention_service = MarketDataExtRetention(engine)
        deleted_counts = retention_service.cleanup_old_data(dry_run=dry_run)

        if dry_run:
            click.echo(f"🔍 Dry run завершен. Было бы удалено: {deleted_counts}")
        else:
            click.echo(f"✅ Очистка завершена. Удалено записей: {deleted_counts}")

    except Exception as e:
        click.echo(f"❌ Ошибка: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    market_meta()
