"""
Модуль для генерации торговых рекомендаций

Анализирует score_results и создаёт торговые рекомендации
с расчётом параметров позиции.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.models import INDICATORS_TABLE_NAME, Indicator
from src.scoring_engine.models import ScoreResult

from .position_model import calculate_position

logger = logging.getLogger(__name__)
# Настраиваем логгер для записи только в файл, а не в консоль
logger.setLevel(logging.DEBUG)
# Удаляем все существующие обработчики
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
# Добавляем только файловый обработчик
file_handler = logging.FileHandler("trade_recommender.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Константы для валидации сигналов
MIN_P_WIN = 0.6  # Минимальная вероятность выигрыша
MIN_EDGE_NET = 0.01  # Минимальное чистое преимущество
MIN_CONFIDENCE = 0.3  # Минимальная уверенность


async def get_score_by_id(session: AsyncSession, score_id: int) -> ScoreResult | None:
    """Получает score_result по ID"""
    try:
        query = select(ScoreResult).where(ScoreResult.id == score_id)
        result = await session.execute(query)
        score = result.scalar_one_or_none()

        if score:
            logger.debug(f"Найден score {score_id}: {score.symbol} {score.timeframe}")
            return score
        logger.debug(f"Score {score_id} не найден")
        return None

    except Exception as e:
        logger.error(f"Ошибка при получении score {score_id}: {e}")
        return None


def validate_score_quality(score: ScoreResult) -> tuple[bool, str]:
    """
    Проверяет качество сигнала по критериям

    Returns:
        (is_valid, reason)
    """
    reasons = []

    # Проверка валидности
    if not score.is_valid:
        reasons.append("score.is_valid = false")

    # Проверка вероятности выигрыша
    if score.p_win is None or score.p_win < MIN_P_WIN:
        reasons.append(f"p_win ({score.p_win}) < {MIN_P_WIN}")

    # Проверка чистого преимущества
    if score.edge_net is None or score.edge_net < MIN_EDGE_NET:
        reasons.append(f"edge_net ({score.edge_net}) < {MIN_EDGE_NET}")

    # Проверка уверенности
    if score.confidence is None or score.confidence < MIN_CONFIDENCE:
        reasons.append(f"confidence ({score.confidence}) < {MIN_CONFIDENCE}")

    is_valid = len(reasons) == 0
    reason = "; ".join(reasons) if reasons else "OK"

    return is_valid, reason


async def get_indicators_data(
    session: AsyncSession, symbol: str, timeframe: str, ts: int
) -> dict | None:
    """Получает данные индикаторов для расчёта позиции"""
    try:
        if Indicator.__tablename__ != INDICATORS_TABLE_NAME:
            logger.warning(
                "Indicator ORM is routed to %s instead of %s",
                Indicator.__tablename__,
                INDICATORS_TABLE_NAME,
            )
        # Используем JOIN для получения OHLCV данных из swap_ohlcv_p
        from src.models import SwapOhlcvP

        query = (
            select(Indicator, SwapOhlcvP)
            .join(
                SwapOhlcvP,
                (Indicator.symbol == SwapOhlcvP.symbol)
                & (Indicator.timeframe == SwapOhlcvP.timeframe)
                & (Indicator.timestamp == SwapOhlcvP.timestamp),
            )
            .where(
                Indicator.symbol == symbol,
                Indicator.timeframe == timeframe,
                Indicator.timestamp == ts,
            )
        )

        result = await session.execute(query)
        row = result.first()

        if not row:
            logger.warning(f"Индикаторы не найдены: {symbol} {timeframe} {ts}")
            return None

        indicator, ohlcv = row

        # Проверяем наличие обязательных данных
        if ohlcv.close is None:
            logger.warning(f"Close цена отсутствует: {symbol} {timeframe} {ts}")
            return None

        if indicator.atr_14 is None:
            logger.warning(f"ATR14 отсутствует: {symbol} {timeframe} {ts}")
            return None

        return {
            "close": float(ohlcv.close),
            "atr14": float(indicator.atr_14),
            "open": float(ohlcv.open) if ohlcv.open else None,
            "high": float(ohlcv.high) if ohlcv.high else None,
            "low": float(ohlcv.low) if ohlcv.low else None,
            "volume": float(ohlcv.volume) if ohlcv.volume else None,
        }

    except Exception as e:
        logger.error(f"Ошибка при получении индикаторов: {e}")
        return None


def determine_direction(score_calibrated: float) -> str:
    """Определяет направление позиции на основе калиброванного score"""
    if score_calibrated > 0.5:
        return "LONG"
    return "SHORT"


async def save_trade_recommendation(
    session: AsyncSession,
    score_id: int,
    position_data: dict,
    score: ScoreResult,
    is_valid: bool,
    validation_reasons: list[str],
    status: str,
) -> bool:
    """Сохраняет торговую рекомендацию в БД"""
    try:
        from .models import TradeRecommendation

        # Создаём запись рекомендации
        recommendation = TradeRecommendation(
            score_id=score_id,
            symbol=score.symbol,
            timeframe=score.timeframe,
            ts=score.ts,
            # Результат валидации
            is_valid=is_valid,
            validation_reasons=validation_reasons if validation_reasons else None,
            # Направление и цены
            direction=position_data.get("direction"),
            entry_price=position_data.get("entry_price"),
            stop_loss_price=position_data.get("stop_loss_price"),
            take_profit_price=position_data.get("take_profit_price"),
            # Размеры позиции
            position_size=position_data.get("position_size"),
            position_value_usdt=position_data.get("position_value_usdt"),
            risk_amount_usdt=position_data.get("risk_amount_usdt"),
            # Плечо и маржа
            leverage_used=position_data.get("leverage_used"),
            margin_required=position_data.get("margin_required"),
            # Параметры расчёта
            atr=position_data.get("atr"),
            atr_multiplier=position_data.get("atr_multiplier"),
            rr_ratio=position_data.get("rr_ratio"),
            balance_usdt=position_data.get("balance"),
            risk_pct=position_data.get("risk_pct"),
            # Статус
            status=status,
            dry_run=True,  # Всегда True для рекомендаций
        )

        session.add(recommendation)
        await session.commit()

        logger.debug(f"Сохранена торговая рекомендация: ID {recommendation.id}")
        return True

    except Exception as e:
        logger.error(f"Ошибка при сохранении рекомендации: {e}")
        await session.rollback()
        return False


async def recommend_for_score(score_id: int, dry_run: bool = True) -> dict:
    """
    Генерирует торговую рекомендацию для score_id

    Args:
        score_id: ID записи из score_results
        dry_run: Если True - не сохраняет в БД

    Returns:
        Dict с рекомендацией или ошибкой
    """
    logger.debug(f"Генерация рекомендации для score_id={score_id}")

    async for session in get_async_session():
        try:
            # 1. Получаем score
            score = await get_score_by_id(session, score_id)
            if not score:
                return {
                    "status": "error",
                    "message": f"Score {score_id} не найден",
                    "score_id": score_id,
                }

            # 2. Проверяем качество сигнала
            is_valid, reason = validate_score_quality(score)
            if not is_valid:
                return {
                    "status": "rejected",
                    "message": f"Сигнал не прошёл валидацию: {reason}",
                    "score_id": score_id,
                    "symbol": score.symbol,
                    "timeframe": score.timeframe,
                    "reasons": reason,
                }

            # 3. Получаем данные индикаторов
            indicators = await get_indicators_data(
                session, score.symbol, score.timeframe, score.ts
            )
            if not indicators:
                return {
                    "status": "error",
                    "message": "Не удалось получить данные индикаторов",
                    "score_id": score_id,
                    "symbol": score.symbol,
                    "timeframe": score.timeframe,
                    "ts": score.ts,
                }

            # 4. Определяем направление
            direction = determine_direction(score.score_calibrated)

            # 5. Рассчитываем позицию
            try:
                position_data = calculate_position(
                    symbol=score.symbol,
                    direction=direction,
                    entry_price=indicators["close"],
                    atr=indicators["atr14"],
                )
            except ValueError as e:
                return {
                    "status": "error",
                    "message": f"Ошибка расчёта позиции: {e}",
                    "score_id": score_id,
                    "symbol": score.symbol,
                }

            # 6. Формируем результат
            recommendation = {
                "status": "ready",
                "score_id": score_id,
                "symbol": score.symbol,
                "timeframe": score.timeframe,
                "direction": direction,
                "entry_price": position_data["entry_price"],
                "stop_loss_price": position_data["stop_loss_price"],
                "take_profit_price": position_data["take_profit_price"],
                "position_size": position_data["position_size"],
                "risk_amount_usdt": position_data["risk_amount_usdt"],
                "leverage_used": position_data["leverage_used"],
                "position_value_usdt": position_data["position_value_usdt"],
                "margin_required": position_data["margin_required"],
                "atr": position_data["atr"],
                "atr_multiplier": position_data["atr_multiplier"],
                "rr_ratio": position_data["rr_ratio"],
                "balance": position_data["balance"],
                "risk_pct": position_data["risk_pct"],
                "dry_run": dry_run,
            }

            # 7. Сохраняем в БД если не dry_run
            if not dry_run:
                # Определяем статус и причины валидации
                validation_reasons = []
                if not is_valid:
                    validation_reasons = [reason]

                saved = await save_trade_recommendation(
                    session,
                    score_id,
                    position_data,
                    score,
                    is_valid,
                    validation_reasons,
                    "ready",
                )
                if not saved:
                    recommendation["status"] = "error"
                    recommendation["message"] = "Не удалось сохранить рекомендацию в БД"

            logger.debug(f"Рекомендация готова: {score.symbol} {direction}")
            return recommendation

        except Exception as e:
            logger.error(f"Критическая ошибка при генерации рекомендации: {e}")
            return {
                "status": "error",
                "message": f"Критическая ошибка: {e}",
                "score_id": score_id,
            }
    return None
