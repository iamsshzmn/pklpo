"""
Настройки по умолчанию для системы расчёта позиций
"""

from decimal import Decimal
from typing import Any


class DefaultSettings:
    """Настройки по умолчанию для пользователей"""

    # Параметры риска
    BALANCE_USDT = Decimal("10000.00")
    RISK_PER_TRADE_PCT = Decimal("0.02")  # 2%
    LEVERAGE_TARGET = 10

    # Настройки стопов и тейк-профитов
    DEFAULT_STOP_METHOD = "percent"
    DEFAULT_STOP_VALUE = Decimal("0.03")  # 3%
    DEFAULT_TP_LEVELS_PCT = [Decimal("0.03"), Decimal("0.06")]  # 3%, 6%

    # Настройки ордеров
    DEFAULT_ORDER_TYPE_ENTRY = "market"
    DEFAULT_SLIPPAGE_PCT = Decimal("0.001")  # 0.1%

    # Настройки сигналов
    CONSENSUS_THRESHOLD = Decimal("0.05")  # 5%
    TIMEFRAME_ENTRY = "1m"
    SIGNAL_AGE_MAX = 60  # баров

    @classmethod
    def get_default_settings(cls, user_id: str = "default_user") -> dict[str, Any]:
        """Возвращает настройки по умолчанию для пользователя"""
        return {
            "user_id": user_id,
            "balance_usdt": cls.BALANCE_USDT,
            "risk_per_trade_pct": cls.RISK_PER_TRADE_PCT,
            "leverage_target": cls.LEVERAGE_TARGET,
            "default_stop_method": cls.DEFAULT_STOP_METHOD,
            "default_stop_value": cls.DEFAULT_STOP_VALUE,
            "default_tp_levels_pct": cls.DEFAULT_TP_LEVELS_PCT,
            "default_order_type_entry": cls.DEFAULT_ORDER_TYPE_ENTRY,
            "default_slippage_pct": cls.DEFAULT_SLIPPAGE_PCT,
            "consensus_threshold": cls.CONSENSUS_THRESHOLD,
            "timeframe_entry": cls.TIMEFRAME_ENTRY,
            "signal_age_max": cls.SIGNAL_AGE_MAX,
        }

    @classmethod
    def get_preset_settings(cls, preset_name: str) -> dict[str, Any]:
        """Возвращает предустановленные настройки"""
        presets = {
            "conservative": {
                "balance_usdt": Decimal("5000.00"),
                "risk_per_trade_pct": Decimal("0.01"),  # 1%
                "leverage_target": 5,
                "default_stop_value": Decimal("0.02"),  # 2%
                "default_tp_levels_pct": [Decimal("0.02"), Decimal("0.04")],
                "consensus_threshold": Decimal("0.08"),  # 8%
            },
            "aggressive": {
                "balance_usdt": Decimal("20000.00"),
                "risk_per_trade_pct": Decimal("0.05"),  # 5%
                "leverage_target": 20,
                "default_stop_value": Decimal("0.05"),  # 5%
                "default_tp_levels_pct": [Decimal("0.05"), Decimal("0.10")],
                "consensus_threshold": Decimal("0.03"),  # 3%
            },
            "balanced": {
                "balance_usdt": Decimal("10000.00"),
                "risk_per_trade_pct": Decimal("0.02"),  # 2%
                "leverage_target": 10,
                "default_stop_value": Decimal("0.03"),  # 3%
                "default_tp_levels_pct": [Decimal("0.03"), Decimal("0.06")],
                "consensus_threshold": Decimal("0.05"),  # 5%
            },
        }

        if preset_name not in presets:
            raise ValueError(
                f"Неизвестный пресет: {preset_name}. Доступные: {list(presets.keys())}"
            )

        return presets[preset_name]

    @classmethod
    def list_presets(cls) -> list[str]:
        """Возвращает список доступных пресетов"""
        return ["conservative", "balanced", "aggressive"]
