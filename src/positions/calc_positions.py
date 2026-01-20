#!/usr/bin/env python3
"""
Модуль для расчёта позиций на SWAP инструментах (параллельная версия)
Интегрирован в основной цикл системы
"""

import asyncio
import logging
import multiprocessing
import time
import uuid

from sqlalchemy import text
from tqdm import tqdm

from src.database import get_async_session
from src.positions.calculator import PositionCalculator
from src.positions.models import PositionCalculation, PositionOrder

logger = logging.getLogger(__name__)
# Настраиваем логгер для записи только в файл, а не в консоль
logger.setLevel(logging.DEBUG)
# Удаляем все существующие обработчики
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
# Добавляем только файловый обработчик
file_handler = logging.FileHandler("positions_calculator.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


# Функции для управления логированием
def enable_verbose_logging():
    """Включает подробное логирование в консоль"""
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def disable_verbose_logging():
    """Отключает подробное логирование в консоль"""
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            logger.removeHandler(handler)


BATCH_SIZE = 1000  # размер пакета для обработки
MAX_WORKERS = min(multiprocessing.cpu_count(), 8)  # количество параллельных потоков
CHUNK_SIZE = 5  # размер пакета для параллельной обработки


def decimal_to_float(value):
    """Конвертирует Decimal в float для JSON"""
    if value is None:
        return None
    if hasattr(value, "__float__"):
        return float(value)
    return value


async def get_swap_instruments(symbol=None) -> list:
    """
    Получает список SWAP инструментов для обработки.

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)

    Returns:
        List: Список инструментов
    """
    async for session in get_async_session():
        try:
            # Получаем все SWAP инструменты
            query = text(
                """
                SELECT symbol, margin_mode, tick_size, lot_size,
                       maker_fee, taker_fee, maintenance_margin_rate,
                       max_leverage, funding_rate, contract_val,
                       settle_ccy, ct_type, min_sz, max_sz, min_notional
                FROM instruments
                WHERE symbol LIKE '%-SWAP'
            """
            )

            if symbol:
                query = text(
                    """
                    SELECT symbol, margin_mode, tick_size, lot_size,
                           maker_fee, taker_fee, maintenance_margin_rate,
                           max_leverage, funding_rate, contract_val,
                           settle_ccy, ct_type, min_sz, max_sz, min_notional
                    FROM instruments
                    WHERE symbol = :symbol AND symbol LIKE '%-SWAP'
                """
                )

            result = await session.execute(query, {"symbol": symbol} if symbol else {})
            instruments = result.fetchall()

            logger.debug(f"📊 Найдено {len(instruments)} SWAP инструментов")
            return instruments

        except Exception as e:
            logger.error(f"❌ Ошибка при получении инструментов: {e}")
            return []
    return None


async def get_ohlcv_data(session, symbol: str, limit: int = 300) -> list[dict]:
    """
    Получает OHLCV данные для символа.

    Args:
        session: Сессия БД
        symbol: Символ
        limit: Количество баров

    Returns:
        List[Dict]: OHLCV данные
    """
    try:
        ohlcv_query = text(
            """
            SELECT open, high, low, close, volume, ts as timestamp
            FROM ohlcv
            WHERE symbol = :symbol
            ORDER BY ts DESC
            LIMIT :limit
        """
        )

        ohlcv_result = await session.execute(
            ohlcv_query, {"symbol": symbol, "limit": limit}
        )
        ohlcv_rows = ohlcv_result.fetchall()

        if len(ohlcv_rows) < 200:
            logger.debug(f"⚠️ Недостаточно данных для {symbol}: {len(ohlcv_rows)} баров")
            return []

        # Преобразуем OHLCV данные в правильный формат
        ohlcv_data = []
        for row in ohlcv_rows:
            ohlcv_data.append(
                {
                    "open": float(row.open) if row.open else 0,
                    "high": float(row.high) if row.high else 0,
                    "low": float(row.low) if row.low else 0,
                    "close": float(row.close) if row.close else 0,
                    "volume": float(row.volume) if row.volume else 0,
                    "timestamp": int(row.timestamp) if row.timestamp else 0,
                }
            )

        return ohlcv_data

    except Exception as e:
        logger.error(f"❌ Ошибка при получении OHLCV для {symbol}: {e}")
        return []


def prepare_position_data(symbol: str, instrument, ohlcv_data: list[dict]) -> dict:
    """
    Подготавливает данные для расчёта позиции.

    Args:
        symbol: Символ
        instrument: Данные инструмента
        ohlcv_data: OHLCV данные

    Returns:
        Dict: Данные для расчёта позиции
    """
    return {
        # Блок 1: Биржевые метаданные
        "symbol": symbol,
        "margin_mode": instrument.margin_mode or "isolated",
        "tick_size": instrument.tick_size or 0.01,
        "lot_size": instrument.lot_size or 1,
        "maker_fee": instrument.maker_fee or 0.0001,
        "taker_fee": instrument.taker_fee or 0.0005,
        "maintenance_margin_rate": instrument.maintenance_margin_rate or 0.005,
        "max_leverage": min(
            instrument.max_leverage or 100, 1000
        ),  # Ограничиваем до 1000
        "funding_rate": instrument.funding_rate or 0.0001,
        # Блок 2: Рыночные данные
        "spot_ohlcv": ohlcv_data,  # Упрощённо, в реальности нужны spot данные
        "swap_ohlcv": ohlcv_data,
        "P_last": ohlcv_data[0]["close"] if ohlcv_data else 0,
        # Блок 3: Параметры пользователя
        "balance_usdt": 10000,  # Пример баланса
        "risk_per_trade_pct": 0.02,  # 2% риска на сделку
        "leverage_target": 10,
        # Блок 4: Условия сделки
        "direction": "long",  # Пример направления
        "stop_method": "percent",
        "stop_value": 0.03,  # 3% стоп
        "tp_levels_pct": [0.03, 0.06],  # Тейк-профиты
        "order_type_entry": "market",
        "slippage_pct": 0.001,
        # Блок 5: Контроль сигналов
        "consensus_threshold": 0.05,  # Более реалистичный порог
        "timeframe_entry": "1m",
        "signal_age_max": 60,
    }


async def save_position_to_db(
    session, symbol: str, position_data: dict, result
) -> bool:
    """
    Сохраняет расчёт позиции в базу данных.

    Args:
        session: Сессия БД
        symbol: Символ
        position_data: Данные позиции
        result: Результат расчёта

    Returns:
        bool: Успех сохранения
    """
    try:
        # Конвертируем input_data для JSON
        json_safe_position_data = {}
        for key, value in position_data.items():
            if isinstance(value, dict):
                json_safe_position_data[key] = {
                    k: decimal_to_float(v) for k, v in value.items()
                }
            elif isinstance(value, list):
                json_safe_position_data[key] = [decimal_to_float(v) for v in value]
            else:
                json_safe_position_data[key] = decimal_to_float(value)

        # Конвертируем warnings для JSON
        json_safe_warnings = []
        if result.warnings:
            for warning in result.warnings:
                if isinstance(warning, dict):
                    json_safe_warnings.append(
                        {k: decimal_to_float(v) for k, v in warning.items()}
                    )
                else:
                    json_safe_warnings.append(str(warning))

        # Конвертируем take_profit_prices для JSON
        json_safe_tp_prices = []
        if result.take_profit_prices:
            for price in result.take_profit_prices:
                json_safe_tp_prices.append(decimal_to_float(price))

        # Создаём запись расчёта
        calc_id = str(uuid.uuid4())
        calc_record = PositionCalculation(
            id=calc_id,
            symbol=symbol,
            user_id="default_user",  # Можно сделать настраиваемым
            input_data=json_safe_position_data,
            position_size=result.position_size,
            position_value_usdt=result.position_value_usdt,
            entry_price=result.entry_price,
            stop_loss_price=result.stop_loss_price,
            take_profit_prices=json_safe_tp_prices,
            risk_amount_usdt=result.risk_amount_usdt,
            stop_distance_pct=result.stop_distance_pct,
            leverage_used=result.leverage_used,
            margin_required=result.margin_required,
            liquidation_distance_pct=result.liquidation_distance_pct,
            is_valid=True,
            warnings=json_safe_warnings,
            signal_consensus=position_data.get("consensus_threshold"),
            signal_timeframe=position_data.get("timeframe_entry"),
        )

        session.add(calc_record)

        # Создаём ордера
        if result.entry_price:
            entry_order = PositionOrder(
                id=str(uuid.uuid4()),
                position_calculation_id=calc_id,
                order_type="entry",
                side="buy" if position_data.get("direction") == "long" else "sell",
                order_type_exchange=position_data.get("order_type_entry", "market"),
                quantity=result.position_size,
                price=result.entry_price,
                status="calculated",
            )
            session.add(entry_order)

        if result.stop_loss_price:
            stop_order = PositionOrder(
                id=str(uuid.uuid4()),
                position_calculation_id=calc_id,
                order_type="stop_loss",
                side="sell" if position_data.get("direction") == "long" else "buy",
                order_type_exchange="stop",
                quantity=result.position_size,
                price=result.stop_loss_price,
                reduce_only=True,
                status="calculated",
            )
            session.add(stop_order)

        if result.take_profit_prices:
            for _i, tp_price in enumerate(result.take_profit_prices):
                tp_order = PositionOrder(
                    id=str(uuid.uuid4()),
                    position_calculation_id=calc_id,
                    order_type="take_profit",
                    side="sell" if position_data.get("direction") == "long" else "buy",
                    order_type_exchange="limit",
                    quantity=result.position_size
                    / len(result.take_profit_prices),  # Разделяем на части
                    price=tp_price,
                    reduce_only=True,
                    status="calculated",
                )
                session.add(tp_order)

        await session.commit()
        logger.debug(f"💾 {symbol}: Данные сохранены в БД")
        return True

    except Exception as e:
        logger.error(f"❌ {symbol}: Ошибка сохранения в БД: {e}")
        await session.rollback()
        return False


async def process_single_position(instrument) -> dict:
    """
    Обрабатывает один инструмент для расчёта позиции.

    Args:
        instrument: Инструмент для обработки

    Returns:
        Dict: Результат обработки
    """
    start_time = time.time()
    sym = instrument.symbol

    # Отключаем подробное логирование для консоли во время расчетов
    disable_verbose_logging()

    try:
        async for session in get_async_session():
            try:
                # Получаем OHLCV данные
                ohlcv_data = await get_ohlcv_data(session, sym)
                if not ohlcv_data:
                    return {
                        "symbol": sym,
                        "success": False,
                        "error": "Недостаточно OHLCV данных",
                        "calculation_time": time.time() - start_time,
                    }

                # Формируем данные для расчёта позиции
                position_data = prepare_position_data(sym, instrument, ohlcv_data)

                # Рассчитываем позицию
                calculator = PositionCalculator()
                result = calculator.calculate_position(position_data)

                if result.is_valid:
                    # Сохраняем в БД
                    save_success = await save_position_to_db(
                        session, sym, position_data, result
                    )

                    return {
                        "symbol": sym,
                        "success": save_success,
                        "position_size": result.position_size,
                        "position_value": result.position_value_usdt,
                        "calculation_time": time.time() - start_time,
                    }
                return {
                    "symbol": sym,
                    "success": False,
                    "error": f"Ошибка расчёта: {result.validation_errors}",
                    "calculation_time": time.time() - start_time,
                }

            except Exception as e:
                return {
                    "symbol": sym,
                    "success": False,
                    "error": str(e),
                    "calculation_time": time.time() - start_time,
                }

    except Exception as e:
        return {
            "symbol": sym,
            "success": False,
            "error": str(e),
            "calculation_time": time.time() - start_time,
        }


async def process_position_chunk(chunk: list) -> list[dict]:
    """
    Обрабатывает чанк инструментов для расчёта позиций.

    Args:
        chunk: Список инструментов для обработки

    Returns:
        List[Dict]: Результаты обработки каждого инструмента
    """
    results = []

    # Создаём задачи для параллельной обработки
    tasks = []
    for instrument in chunk:
        task = asyncio.create_task(process_single_position(instrument))
        tasks.append(task)

    # Выполняем все задачи параллельно
    chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Обрабатываем результаты
    for i, result in enumerate(chunk_results):
        if isinstance(result, Exception):
            results.append(
                {
                    "symbol": chunk[i].symbol,
                    "success": False,
                    "error": str(result),
                    "calculation_time": 0.0,
                }
            )
        else:
            results.append(result)

    return results


async def calculate_positions_for_all(symbol: str | None = None) -> dict:
    """
    Рассчитывает позиции для всех символов с параллельной обработкой.

    Args:
        symbol: Конкретный символ (если None, обрабатываются все)

    Returns:
        dict: Статистика обработки
    """
    logger.info("⚡ Запуск параллельного расчёта позиций на SWAP инструментах...")
    logger.info(f"⚡ Используем {MAX_WORKERS} параллельных потоков")
    # Включаем подробное логирование для основных сообщений
    enable_verbose_logging()

    # Получаем инструменты для обработки
    instruments = await get_swap_instruments(symbol)
    if not instruments:
        logger.warning("⚠️ Не найдено SWAP инструментов для расчёта позиций")
        return {"status": "no_instruments", "processed": 0, "positions": 0, "errors": 0}

    total_positions = 0
    total_processed = 0
    total_errors = 0
    total_calculation_time = 0.0

    # Параллельная обработка
    # Разбиваем инструменты на чанки
    chunks = [
        instruments[i : i + CHUNK_SIZE] for i in range(0, len(instruments), CHUNK_SIZE)
    ]
    logger.debug(f"📦 Разбито на {len(chunks)} чанков по {CHUNK_SIZE} инструментов")

    with tqdm(
        total=len(chunks),
        desc="🎯 Параллельная обработка позиций",
        unit="чанк",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        position=0,
        leave=True,
        dynamic_ncols=True,
    ) as pbar:
        for chunk in chunks:
            try:
                # Обрабатываем чанк параллельно
                chunk_results = await process_position_chunk(chunk)

                # Подсчитываем результаты
                for result in chunk_results:
                    if result["success"]:
                        total_processed += 1
                        total_positions += 1
                    else:
                        total_errors += 1

                    total_calculation_time += result.get("calculation_time", 0.0)

                pbar.update(1)
                pbar.set_postfix(
                    {"Обработано": f"{total_processed}", "Ошибок": f"{total_errors}"}
                )

            except Exception as e:
                logger.error(f"❌ Ошибка при обработке чанка: {e}")
                total_errors += len(chunk)
                pbar.update(1)

    # Итоговая статистика
    logger.info("=" * 60)
    logger.info("📊 ИТОГОВАЯ СТАТИСТИКА ОБРАБОТКИ ПОЗИЦИЙ:")
    logger.info(f"📋 Всего инструментов: {len(instruments)}")
    logger.info(f"✅ Успешно обработано: {total_processed}")
    logger.info(f"💰 Всего позиций создано: {total_positions}")
    logger.info(f"❌ Ошибок: {total_errors}")
    logger.info(f"⏱️ Общее время расчётов: {total_calculation_time:.2f}с")

    if total_processed > 0:
        success_rate = total_processed / len(instruments) * 100
        avg_time = total_calculation_time / total_processed
        logger.info(f"📈 Успешность: {success_rate:.1f}%")
        logger.info(f"⏱️ Среднее время на позицию: {avg_time:.2f}с")

    logger.info("🎉 Расчёт позиций завершён успешно!")

    return {
        "status": "completed",
        "processed": total_processed,
        "positions": total_positions,
        "errors": total_errors,
        "total_instruments": len(instruments),
        "calculation_time": total_calculation_time,
    }


async def main(symbol: str | None = None):
    """
    Основная функция для расчёта позиций (параллельная версия)

    Args:
        symbol: Конкретный символ для анализа (если None, анализируются все)
    """
    try:
        result = await calculate_positions_for_all(symbol)

        if result.get("status") == "completed":
            logger.info("🎉 Расчёт позиций завершён успешно!")
        elif result.get("status") == "no_instruments":
            logger.info("ℹ️ Нет инструментов для расчёта позиций")
        else:
            logger.warning(f"⚠️ Расчёт завершился со статусом: {result.get('status')}")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при расчёте позиций: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Расчёт позиций на SWAP инструментах (параллельная версия)"
    )
    parser.add_argument("--symbol", "-s", help="Конкретный символ")

    args = parser.parse_args()

    asyncio.run(main(args.symbol))
