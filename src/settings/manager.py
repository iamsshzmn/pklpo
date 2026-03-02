"""
Менеджер пользовательских настроек
"""

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from src.database import get_async_session
from src.positions.models import UserSettings

from .defaults import DefaultSettings
from .validator import SettingsValidator

logger = logging.getLogger(__name__)


class UserSettingsManager:
    """Менеджер пользовательских настроек"""

    def __init__(self):
        self.default_settings = DefaultSettings()

    async def get_user_settings(self, user_id: str) -> dict[str, Any] | None:
        """Получает настройки пользователя из БД"""
        async for session in get_async_session():
            try:
                result = await session.execute(
                    text("SELECT * FROM user_settings WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )

                row = result.fetchone()
                if row:
                    return dict(row._mapping)
                logger.info(f"Настройки для пользователя {user_id} не найдены")
                return None

            except Exception as e:
                logger.error(
                    f"Ошибка при получении настроек пользователя {user_id}: {e}"
                )
                return None
        return None

    async def create_user_settings(
        self, user_id: str, settings: dict[str, Any] | None = None
    ) -> bool:
        """Создаёт настройки пользователя"""
        try:
            # Используем настройки по умолчанию, если не переданы
            if settings is None:
                settings = self.default_settings.get_default_settings(user_id)
            else:
                # Добавляем недостающие поля из настроек по умолчанию
                default_settings = self.default_settings.get_default_settings(user_id)
                for key, value in default_settings.items():
                    if key not in settings:
                        settings[key] = value

            # Валидируем настройки
            errors = SettingsValidator.validate_settings(settings)
            if errors:
                logger.error(f"Ошибки валидации настроек для {user_id}:")
                for error in errors:
                    logger.error(f"  {error.field}: {error.message}")
                return False

            async for session in get_async_session():
                try:
                    # Создаём запись настроек
                    user_settings = UserSettings(
                        user_id=user_id,
                        balance_usdt=settings["balance_usdt"],
                        risk_per_trade_pct=settings["risk_per_trade_pct"],
                        leverage_target=settings["leverage_target"],
                        default_stop_method=settings["default_stop_method"],
                        default_stop_value=settings["default_stop_value"],
                        default_tp_levels_pct=settings["default_tp_levels_pct"],
                        default_order_type_entry=settings["default_order_type_entry"],
                        default_slippage_pct=settings["default_slippage_pct"],
                        consensus_threshold=settings["consensus_threshold"],
                        timeframe_entry=settings["timeframe_entry"],
                        signal_age_max=settings["signal_age_max"],
                    )

                    session.add(user_settings)
                    await session.commit()

                    logger.info(f"Настройки для пользователя {user_id} созданы успешно")
                    return True

                except Exception as e:
                    logger.error(f"Ошибка при создании настроек для {user_id}: {e}")
                    await session.rollback()
                    return False

        except Exception as e:
            logger.error(f"Критическая ошибка при создании настроек для {user_id}: {e}")
            return False

    async def update_user_settings(
        self, user_id: str, settings: dict[str, Any]
    ) -> bool:
        """Обновляет настройки пользователя"""
        try:
            # Валидируем настройки
            errors = SettingsValidator.validate_settings(settings)
            if errors:
                logger.error(f"Ошибки валидации настроек для {user_id}:")
                for error in errors:
                    logger.error(f"  {error.field}: {error.message}")
                return False

            async for session in get_async_session():
                try:
                    # Проверяем, существуют ли настройки
                    result = await session.execute(
                        text(
                            "SELECT user_id FROM user_settings WHERE user_id = :user_id"
                        ),
                        {"user_id": user_id},
                    )

                    if not result.fetchone():
                        logger.warning(
                            f"Настройки для пользователя {user_id} не найдены, создаём новые"
                        )
                        return await self.create_user_settings(user_id, settings)

                    # Обновляем настройки
                    update_fields = []
                    params = {"user_id": user_id}

                    for field, value in settings.items():
                        if field != "user_id":  # Не обновляем primary key
                            update_fields.append(f"{field} = :{field}")
                            params[field] = value

                    if update_fields:
                        query = f"""
                            UPDATE user_settings
                            SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = :user_id
                        """

                        await session.execute(text(query), params)
                        await session.commit()

                        logger.info(
                            f"Настройки для пользователя {user_id} обновлены успешно"
                        )
                        return True
                    logger.warning(
                        f"Нет полей для обновления для пользователя {user_id}"
                    )
                    return True

                except Exception as e:
                    logger.error(f"Ошибка при обновлении настроек для {user_id}: {e}")
                    await session.rollback()
                    return False

        except Exception as e:
            logger.error(
                f"Критическая ошибка при обновлении настроек для {user_id}: {e}"
            )
            return False

    async def delete_user_settings(self, user_id: str) -> bool:
        """Удаляет настройки пользователя"""
        async for session in get_async_session():
            try:
                result = await session.execute(
                    text("DELETE FROM user_settings WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )

                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"Настройки для пользователя {user_id} удалены успешно")
                    return True
                logger.warning(f"Настройки для пользователя {user_id} не найдены")
                return False

            except Exception as e:
                logger.error(f"Ошибка при удалении настроек для {user_id}: {e}")
                await session.rollback()
                return False
        return None

    async def apply_preset(self, user_id: str, preset_name: str) -> bool:
        """Применяет предустановленные настройки"""
        try:
            preset_settings = self.default_settings.get_preset_settings(preset_name)

            # Получаем текущие настройки
            current_settings = await self.get_user_settings(user_id)

            if current_settings:
                # Обновляем только поля из пресета
                for key, value in preset_settings.items():
                    current_settings[key] = value

                return await self.update_user_settings(user_id, current_settings)
            # Создаём новые настройки с пресетом
            default_settings = self.default_settings.get_default_settings(user_id)
            for key, value in preset_settings.items():
                default_settings[key] = value

            return await self.create_user_settings(user_id, default_settings)

        except Exception as e:
            logger.error(
                f"Ошибка при применении пресета {preset_name} для {user_id}: {e}"
            )
            return False

    async def get_settings_for_position_calculation(
        self, user_id: str
    ) -> dict[str, Any] | None:
        """Получает настройки для расчёта позиций с валидацией"""
        settings = await self.get_user_settings(user_id)

        if settings is None:
            logger.warning(
                f"Настройки для пользователя {user_id} не найдены, используем по умолчанию"
            )
            settings = self.default_settings.get_default_settings(user_id)

        # Валидируем настройки для расчёта позиций
        errors = SettingsValidator.validate_settings_for_position_calculation(settings)
        if errors:
            logger.error(
                f"Ошибки валидации настроек для расчёта позиций пользователя {user_id}:"
            )
            for error in errors:
                logger.error(f"  {error.field}: {error.message}")
            return None

        return settings

    async def list_users(self) -> list[str]:
        """Возвращает список пользователей с настройками"""
        async for session in get_async_session():
            try:
                result = await session.execute(
                    text("SELECT user_id FROM user_settings ORDER BY user_id")
                )

                return [row[0] for row in result.fetchall()]

            except Exception as e:
                logger.error(f"Ошибка при получении списка пользователей: {e}")
                return []
        return None

    async def get_settings_summary(self, user_id: str) -> dict[str, Any] | None:
        """Возвращает краткую сводку настроек пользователя"""
        settings = await self.get_user_settings(user_id)

        if settings is None:
            return None

        # Рассчитываем дополнительные параметры
        try:
            balance = Decimal(str(settings["balance_usdt"]))
            risk_pct = Decimal(str(settings["risk_per_trade_pct"]))
            risk_amount = balance * risk_pct

            return {
                "user_id": user_id,
                "balance_usdt": float(balance),
                "risk_per_trade_pct": float(risk_pct * 100),  # в процентах
                "risk_amount_usdt": float(risk_amount),
                "leverage_target": settings["leverage_target"],
                "consensus_threshold": float(
                    settings["consensus_threshold"] * 100
                ),  # в процентах
                "timeframe_entry": settings["timeframe_entry"],
                "default_stop_value": float(
                    settings["default_stop_value"] * 100
                ),  # в процентах
                "default_tp_levels_pct": [
                    float(x * 100) for x in settings["default_tp_levels_pct"]
                ],  # в процентах
                "created_at": settings.get("created_at"),
                "updated_at": settings.get("updated_at"),
            }

        except Exception as e:
            logger.error(f"Ошибка при создании сводки настроек для {user_id}: {e}")
            return None
