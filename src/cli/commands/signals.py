"""
CLI команды для модуля Signals (Фаза 4)

Основные команды:
- generate: генерация сигналов из MTF consensus
- list-candidates: список кандидатов
- promote: продвижение кандидата в live
- list-live: список активных сигналов
- cancel: отмена сигнала
- expire: истечение сигналов
- metrics: метрики производительности
"""

import sys
from datetime import datetime, timedelta

from src.mtf.logging_config import get_main_logger
from src.mtf.mtf_builder import MTFBuilder
from src.signals.database.client import SignalsDatabaseClient
from src.signals.decision.maker import DecisionMaker
from src.signals.models import SignalConfig, SignalStatus
from src.signals.validation.validator import SignalValidator
from src.signals.workflow.promote import PromoteWorkflow

logger = get_main_logger()


def register(subparsers):
    """Регистрация CLI команд для signals модуля"""

    # Основная команда signals
    signals_parser = subparsers.add_parser(
        "signals", help="Управление торговыми сигналами"
    )
    signals_subparsers = signals_parser.add_subparsers(
        dest="signals_command", help="Доступные команды"
    )

    # Команда generate
    generate_parser = signals_subparsers.add_parser(
        "generate", help="Генерация сигналов из MTF consensus"
    )
    generate_parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTC-USDT", "ETH-USDT", "BNB-USDT"],
        help="Символы для анализа",
    )
    generate_parser.add_argument(
        "--timeframes", nargs="+", default=["1m", "15m", "1h"], help="Временные рамки"
    )
    generate_parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Количество воркеров для параллельной обработки",
    )
    generate_parser.add_argument(
        "--database-url", type=str, help="URL базы данных для сохранения результатов"
    )
    generate_parser.add_argument(
        "--use-real-data",
        action="store_true",
        help="Использовать реальные данные из БД",
    )
    generate_parser.add_argument(
        "--algo-version", type=str, default="v1.0.0", help="Версия алгоритма"
    )
    generate_parser.add_argument(
        "--run-id",
        type=str,
        help="ID запуска (генерируется автоматически если не указан)",
    )
    generate_parser.set_defaults(_handler=handle_generate)

    # Команда list-candidates
    list_candidates_parser = signals_subparsers.add_parser(
        "list-candidates", help="Список кандидатов на сигналы"
    )
    list_candidates_parser.add_argument(
        "--symbol-id", type=int, help="ID символа для фильтрации"
    )
    list_candidates_parser.add_argument(
        "--status",
        choices=["pending", "validated", "rejected"],
        help="Статус для фильтрации",
    )
    list_candidates_parser.add_argument(
        "--limit", type=int, default=20, help="Максимальное количество записей"
    )
    list_candidates_parser.add_argument(
        "--database-url", type=str, help="URL базы данных"
    )
    list_candidates_parser.set_defaults(_handler=handle_list_candidates)

    # Команда show-candidate
    show_candidate_parser = signals_subparsers.add_parser(
        "show-candidate", help="Детальная информация о кандидате"
    )
    show_candidate_parser.add_argument("candidate_id", help="ID кандидата")
    show_candidate_parser.add_argument(
        "--database-url", type=str, help="URL базы данных"
    )
    show_candidate_parser.set_defaults(_handler=handle_show_candidate)

    # Команда promote
    promote_parser = signals_subparsers.add_parser(
        "promote", help="Продвижение кандидата в live сигнал"
    )
    promote_parser.add_argument("candidate_id", help="ID кандидата для продвижения")
    promote_parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительное продвижение (игнорирует некоторые проверки)",
    )
    promote_parser.add_argument("--database-url", type=str, help="URL базы данных")
    promote_parser.set_defaults(_handler=handle_promote)

    # Команда list-live
    list_live_parser = signals_subparsers.add_parser(
        "list-live", help="Список активных сигналов"
    )
    list_live_parser.add_argument(
        "--symbol-id", type=int, help="ID символа для фильтрации"
    )
    list_live_parser.add_argument(
        "--status",
        choices=["live", "expired", "cancelled", "executed", "failed"],
        help="Статус для фильтрации",
    )
    list_live_parser.add_argument(
        "--limit", type=int, default=20, help="Максимальное количество записей"
    )
    list_live_parser.add_argument("--database-url", type=str, help="URL базы данных")
    list_live_parser.set_defaults(_handler=handle_list_live)

    # Команда cancel
    cancel_parser = signals_subparsers.add_parser(
        "cancel", help="Отмена активного сигнала"
    )
    cancel_parser.add_argument("live_id", help="ID live сигнала для отмены")
    cancel_parser.add_argument(
        "--reason", type=str, default="Manual cancellation", help="Причина отмены"
    )
    cancel_parser.add_argument("--database-url", type=str, help="URL базы данных")
    cancel_parser.set_defaults(_handler=handle_cancel)

    # Команда expire
    expire_parser = signals_subparsers.add_parser(
        "expire", help="Принудительное истечение сигналов"
    )
    expire_parser.add_argument(
        "--symbol-id", type=int, help="ID символа для фильтрации"
    )
    expire_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать сигналы для истечения без выполнения",
    )
    expire_parser.add_argument("--database-url", type=str, help="URL базы данных")
    expire_parser.set_defaults(_handler=handle_expire)

    # Команда metrics
    metrics_parser = signals_subparsers.add_parser(
        "metrics", help="Метрики производительности сигналов"
    )
    metrics_parser.add_argument(
        "--symbol-id", type=int, help="ID символа для фильтрации"
    )
    metrics_parser.add_argument(
        "--days", type=int, default=7, help="Количество дней для анализа"
    )
    metrics_parser.add_argument("--database-url", type=str, help="URL базы данных")
    metrics_parser.set_defaults(_handler=handle_metrics)


async def handle_generate(args):
    """Обработка команды generate"""
    logger.info("Starting signal generation from MTF consensus")

    try:
        # Создаем конфигурацию
        config = SignalConfig()

        # Инициализируем MTF Builder
        mtf_builder = MTFBuilder(config, database_url=args.database_url)

        # Инициализируем DecisionMaker
        decision_maker = DecisionMaker(config)

        # Инициализируем валидатор
        validator = SignalValidator(config)

        # Инициализируем workflow
        db_client = None
        if args.database_url:
            db_client = SignalsDatabaseClient(args.database_url)
            await db_client.initialize()

        PromoteWorkflow(config, db_client)

        # Генерируем run_id если не указан
        run_id = args.run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Обрабатываем символы
        results = []
        for symbol in args.symbols:
            logger.info(f"Processing symbol: {symbol}")

            try:
                # Получаем MTF результаты
                mtf_result = await mtf_builder.process_symbol(
                    symbol=symbol,
                    timeframes=args.timeframes,
                    use_real_data=args.use_real_data,
                )

                if not mtf_result or not mtf_result.consensus_result:
                    logger.warning(f"No consensus result for {symbol}")
                    continue

                # Создаем торговое решение
                decision = decision_maker.create_decision(
                    symbol_id=1,  # TODO: получить реальный symbol_id
                    consensus_result=mtf_result.consensus_result,
                    context_result=mtf_result.context_result,
                    triggers_result=mtf_result.triggers_result,
                    current_price=50000.0,  # TODO: получить реальную цену
                    atr=1000.0,  # TODO: получить реальный ATR
                    algo_version=args.algo_version,
                    params_hash="hash123",  # TODO: рассчитать реальный хеш
                    run_id=run_id,
                )

                if not decision:
                    logger.info(f"No trading decision for {symbol}")
                    continue

                # Создаем кандидата
                from src.signals.models import SignalCandidate

                candidate = SignalCandidate(decision=decision)

                # Валидируем кандидата
                validation_result = validator.validate_candidate(candidate)
                candidate.validation_results = validation_result

                if validation_result.is_valid:
                    candidate.status = SignalStatus.VALIDATED
                    logger.info(f"Valid candidate created for {symbol}")
                else:
                    candidate.status = SignalStatus.REJECTED
                    logger.warning(
                        f"Invalid candidate for {symbol}: {validation_result.violations}"
                    )

                # Сохраняем в БД
                if db_client:
                    await db_client.save_signal_candidate(candidate)

                results.append(
                    {
                        "symbol": symbol,
                        "decision": decision,
                        "candidate": candidate,
                        "validation": validation_result,
                    }
                )

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue

        # Выводим результаты
        logger.info(f"Signal generation completed. Processed {len(results)} symbols")

        for result in results:
            decision = result["decision"]
            validation = result["validation"]

            print(f"\nSymbol: {result['symbol']}")
            print(f"  Side: {decision.side.value}")
            print(f"  Entry: {decision.entry:.4f}")
            print(f"  Stop: {decision.stop:.4f}")
            print(f"  Take: {decision.take:.4f}")
            print(f"  Confidence: {decision.confidence:.3f}")
            print(f"  Expected R: {decision.expected_r:.3f}")
            print(f"  Valid: {validation.is_valid}")
            if validation.violations:
                print(f"  Violations: {', '.join(validation.violations)}")

        # Закрываем соединения
        if db_client:
            await db_client.close()

    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        sys.exit(1)


async def handle_list_candidates(args):
    """Обработка команды list-candidates"""
    logger.info("Listing signal candidates")

    try:
        if not args.database_url:
            logger.error("Database URL is required for list-candidates command")
            sys.exit(1)

        db_client = SignalsDatabaseClient(args.database_url)
        await db_client.initialize()

        # Получаем статус для фильтрации
        status = None
        if args.status:
            status = SignalStatus(args.status)

        # Получаем список кандидатов
        candidates = await db_client.list_signal_candidates(
            symbol_id=args.symbol_id, status=status, limit=args.limit
        )

        # Выводим результаты
        print(f"\nFound {len(candidates)} candidates:")
        print("-" * 80)

        for candidate in candidates:
            decision = candidate.decision
            print(f"ID: {candidate.id}")
            print(f"  Symbol: {decision.symbol_id}")
            print(f"  Side: {decision.side.value}")
            print(f"  Entry: {decision.entry:.4f}")
            print(f"  Stop: {decision.stop:.4f}")
            print(f"  Take: {decision.take:.4f}")
            print(f"  Confidence: {decision.confidence:.3f}")
            print(f"  Status: {candidate.status.value}")
            print(f"  Created: {candidate.created_at}")
            if candidate.validation_results:
                print(f"  Valid: {candidate.validation_results.is_valid}")
                if candidate.validation_results.violations:
                    print(
                        f"  Violations: {', '.join(candidate.validation_results.violations)}"
                    )
            print()

        await db_client.close()

    except Exception as e:
        logger.error(f"Failed to list candidates: {e}")
        sys.exit(1)


async def handle_show_candidate(args):
    """Обработка команды show-candidate"""
    logger.info(f"Showing candidate details: {args.candidate_id}")

    try:
        if not args.database_url:
            logger.error("Database URL is required for show-candidate command")
            sys.exit(1)

        db_client = SignalsDatabaseClient(args.database_url)
        await db_client.initialize()

        # Получаем кандидата
        candidate = await db_client.get_signal_candidate(args.candidate_id)

        if not candidate:
            logger.error(f"Candidate {args.candidate_id} not found")
            sys.exit(1)

        # Выводим детальную информацию
        decision = candidate.decision
        print("\nCandidate Details:")
        print("=" * 50)
        print(f"ID: {candidate.id}")
        print(f"Status: {candidate.status.value}")
        print(f"Created: {candidate.created_at}")
        print(
            f"Validated: {candidate.validation_results.validated_at if candidate.validation_results else 'Not validated'}"
        )

        print("\nDecision:")
        print(f"  Symbol ID: {decision.symbol_id}")
        print(f"  Timestamp: {decision.ts}")
        print(f"  Horizon: {decision.horizon.value}")
        print(f"  Side: {decision.side.value}")
        print(f"  Entry: {decision.entry:.4f}")
        print(f"  Stop: {decision.stop:.4f}")
        print(f"  Take: {decision.take:.4f}")
        print(f"  TTL: {decision.ttl_sec}s")
        print(f"  Confidence: {decision.confidence:.3f}")
        print(f"  Expected R: {decision.expected_r:.3f}")
        print(f"  Algo Version: {decision.algo_version}")
        print(f"  Params Hash: {decision.params_hash}")
        print(f"  Run ID: {decision.run_id}")

        print("\nRationale:")
        for i, reason in enumerate(decision.rationale, 1):
            print(f"  {i}. {reason}")

        if candidate.validation_results:
            print("\nValidation Results:")
            print(f"  Valid: {candidate.validation_results.is_valid}")
            if candidate.validation_results.violations:
                print("  Violations:")
                for violation in candidate.validation_results.violations:
                    print(f"    - {violation}")
            if candidate.validation_results.warnings:
                print("  Warnings:")
                for warning in candidate.validation_results.warnings:
                    print(f"    - {warning}")

        await db_client.close()

    except Exception as e:
        logger.error(f"Failed to show candidate: {e}")
        sys.exit(1)


async def handle_promote(args):
    """Обработка команды promote"""
    logger.info(f"Promoting candidate: {args.candidate_id}")

    try:
        if not args.database_url:
            logger.error("Database URL is required for promote command")
            sys.exit(1)

        db_client = SignalsDatabaseClient(args.database_url)
        await db_client.initialize()

        # Получаем кандидата
        candidate = await db_client.get_signal_candidate(args.candidate_id)

        if not candidate:
            logger.error(f"Candidate {args.candidate_id} not found")
            sys.exit(1)

        # Создаем workflow
        config = SignalConfig()
        promote_workflow = PromoteWorkflow(config, db_client)

        # Продвигаем кандидата
        live_signal = await promote_workflow.promote_candidate(
            candidate, force=args.force
        )

        if live_signal:
            print(f"\nSuccessfully promoted candidate {args.candidate_id}")
            print(f"Live signal ID: {live_signal.id}")
            print(f"Symbol: {live_signal.decision.symbol_id}")
            print(f"Side: {live_signal.decision.side.value}")
            print(f"Entry: {live_signal.decision.entry:.4f}")
            print(f"Stop: {live_signal.decision.stop:.4f}")
            print(f"Take: {live_signal.decision.take:.4f}")
            print(f"Activated: {live_signal.activated_at}")
            print(f"Expires: {live_signal.expires_at}")
        else:
            logger.error(f"Failed to promote candidate {args.candidate_id}")
            sys.exit(1)

        await db_client.close()

    except Exception as e:
        logger.error(f"Failed to promote candidate: {e}")
        sys.exit(1)


async def handle_list_live(args):
    """Обработка команды list-live"""
    logger.info("Listing live signals")

    try:
        if not args.database_url:
            logger.error("Database URL is required for list-live command")
            sys.exit(1)

        db_client = SignalsDatabaseClient(args.database_url)
        await db_client.initialize()

        # Получаем статус для фильтрации
        status = None
        if args.status:
            status = SignalStatus(args.status)

        # Получаем список live сигналов
        live_signals = await db_client.list_signal_live(
            symbol_id=args.symbol_id, status=status, limit=args.limit
        )

        # Выводим результаты
        print(f"\nFound {len(live_signals)} live signals:")
        print("-" * 80)

        for signal in live_signals:
            decision = signal.decision
            print(f"ID: {signal.id}")
            print(f"  Symbol: {decision.symbol_id}")
            print(f"  Side: {decision.side.value}")
            print(f"  Entry: {decision.entry:.4f}")
            print(f"  Stop: {decision.stop:.4f}")
            print(f"  Take: {decision.take:.4f}")
            print(f"  Confidence: {decision.confidence:.3f}")
            print(f"  Status: {signal.status.value}")
            print(f"  Activated: {signal.activated_at}")
            print(f"  Expires: {signal.expires_at}")
            if signal.executed_at:
                print(f"  Executed: {signal.executed_at}")
            print()

        await db_client.close()

    except Exception as e:
        logger.error(f"Failed to list live signals: {e}")
        sys.exit(1)


async def handle_cancel(args):
    """Обработка команды cancel"""
    logger.info(f"Cancelling live signal: {args.live_id}")

    try:
        if not args.database_url:
            logger.error("Database URL is required for cancel command")
            sys.exit(1)

        db_client = SignalsDatabaseClient(args.database_url)
        await db_client.initialize()

        # Получаем live сигнал
        live_signal = await db_client.get_signal_live(args.live_id)

        if not live_signal:
            logger.error(f"Live signal {args.live_id} not found")
            sys.exit(1)

        # Создаем workflow
        config = SignalConfig()
        promote_workflow = PromoteWorkflow(config, db_client)

        # Отменяем сигнал
        success = await promote_workflow.cancel_signal(live_signal, args.reason)

        if success:
            print(f"\nSuccessfully cancelled signal {args.live_id}")
            print(f"Reason: {args.reason}")
        else:
            logger.error(f"Failed to cancel signal {args.live_id}")
            sys.exit(1)

        await db_client.close()

    except Exception as e:
        logger.error(f"Failed to cancel signal: {e}")
        sys.exit(1)


async def handle_expire(args):
    """Обработка команды expire"""
    logger.info("Expiring signals")

    try:
        if not args.database_url:
            logger.error("Database URL is required for expire command")
            sys.exit(1)

        db_client = SignalsDatabaseClient(args.database_url)
        await db_client.initialize()

        # Создаем workflow
        config = SignalConfig()
        promote_workflow = PromoteWorkflow(config, db_client)

        if args.dry_run:
            # Получаем активные сигналы для проверки
            live_signals = await db_client.list_signal_live(
                symbol_id=args.symbol_id, status=SignalStatus.LIVE
            )

            expired_count = 0
            for signal in live_signals:
                if signal.expires_at and datetime.utcnow() >= signal.expires_at:
                    expired_count += 1
                    print(
                        f"Would expire signal {signal.id} (expired at {signal.expires_at})"
                    )

            print(f"\nWould expire {expired_count} signals")
        else:
            # Выполняем истечение
            expired_count = await promote_workflow.cleanup_expired_signals()
            print(f"\nExpired {expired_count} signals")

        await db_client.close()

    except Exception as e:
        logger.error(f"Failed to expire signals: {e}")
        sys.exit(1)


async def handle_metrics(args):
    """Обработка команды metrics"""
    logger.info("Getting signal metrics")

    try:
        if not args.database_url:
            logger.error("Database URL is required for metrics command")
            sys.exit(1)

        db_client = SignalsDatabaseClient(args.database_url)
        await db_client.initialize()

        # Получаем метрики
        date_from = datetime.utcnow() - timedelta(days=args.days)
        metrics = await db_client.get_signal_metrics(
            symbol_id=args.symbol_id, date_from=date_from
        )

        # Выводим метрики
        print(f"\nSignal Metrics (last {args.days} days):")
        print("=" * 50)
        print(f"Total Generated: {metrics.total_generated}")
        print(f"Total Validated: {metrics.total_validated}")
        print(f"Total Promoted: {metrics.total_promoted}")
        print(f"Total Executed: {metrics.total_executed}")
        print(f"Total Failed: {metrics.total_failed}")
        print()
        print(f"Validation Pass Rate: {metrics.validation_pass_rate:.1%}")
        print(f"Promotion Rate: {metrics.promotion_rate:.1%}")
        print(f"Execution Success Rate: {metrics.execution_success_rate:.1%}")
        print()
        print(f"Average Expected R: {metrics.avg_expected_r:.3f}")
        print(f"Average Actual R: {metrics.avg_actual_r:.3f}")
        print(f"Average Confidence: {metrics.avg_confidence:.3f}")
        print(f"Average Execution Time: {metrics.avg_execution_time_sec:.1f}s")

        await db_client.close()

    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        sys.exit(1)


# Регистрация обработчиков команд
def _register_handlers():
    """Регистрация обработчиков команд"""

    # Получаем все функции-обработчики
    handlers = {
        "handle_generate": handle_generate,
        "handle_list_candidates": handle_list_candidates,
        "handle_show_candidate": handle_show_candidate,
        "handle_promote": handle_promote,
        "handle_list_live": handle_list_live,
        "handle_cancel": handle_cancel,
        "handle_expire": handle_expire,
        "handle_metrics": handle_metrics,
    }

    # Регистрируем обработчики в глобальном пространстве имен
    for name, handler in handlers.items():
        globals()[name] = handler


# Автоматическая регистрация при импорте
_register_handlers()
