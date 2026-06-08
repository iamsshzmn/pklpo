"""
Загрузчик и парсер контракта market_data_ext.

Контракт — единственный источник истины для правил нормализации,
агрегации и вычисления params_hash.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


class ContractLoader:
    """
    Загружает контракт из markdown-файла и предоставляет доступ к правилам.

    Контракт парсится в структурированный dict, из которого вычисляется
    params_hash для трассировки изменений.
    """

    def __init__(self, contract_path: Path | str | None = None) -> None:
        """
        Инициализация загрузчика.

        Args:
            contract_path: Путь к файлу контракта. По умолчанию —
                contracts/market_data_ext_contract.md относительно модуля.
        """
        if contract_path is None:
            module_dir = Path(__file__).parent.parent
            contract_path = module_dir / "contracts" / "market_data_ext_contract.md"
        self._path = Path(contract_path)
        self._data: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        """
        Загружает и парсит контракт.

        Returns:
            Структурированный dict с правилами контракта.

        Raises:
            FileNotFoundError: Если файл контракта не найден.
        """
        if self._data is not None:
            return self._data

        content = self._path.read_text(encoding="utf-8")
        self._data = self._parse_contract(content)
        return self._data

    def _parse_contract(self, content: str) -> dict[str, Any]:
        """Парсит markdown-контракт в структурированный dict."""
        data: dict[str, Any] = {}

        # Извлекаем метаданные из заголовка
        version_match = re.search(r">\s*Версия:\s*([\d.]+)", content)
        data["contract_version"] = version_match.group(1) if version_match else "0.0.0"

        # Правила нормализации
        data["normalization"] = self._parse_normalization_rules(content)

        # Правила агрегации
        data["aggregation"] = self._parse_aggregation_rules(content)

        # L2 policy
        data["l2_policy"] = self._parse_l2_policy(content)

        # Upsert policy
        data["upsert_policy"] = self._parse_upsert_policy(content)

        return data

    def _parse_normalization_rules(self, content: str) -> dict[str, Any]:
        """Извлекает правила нормализации из контракта."""
        rules: dict[str, Any] = {}

        # Funding
        rules["funding"] = {
            "method": "LKV",
            "window": "end_of_minute",
            "max_staleness_sec": 300,
        }

        # OI
        rules["open_interest"] = {
            "method": "LKV",
            "window": "end_of_minute",
        }

        # L2
        rules["l2"] = {
            "method": "LKV",
            "window": "end_of_minute",
            "features": ["bid_imbalance", "ask_imbalance", "spread_bps"],
        }

        return rules

    def _parse_aggregation_rules(self, content: str) -> dict[str, Any]:
        """Извлекает правила агрегации из контракта."""
        return {
            "funding_rate": {"5m": "last", "15m": "last", "1H": "last"},
            "open_interest": {"5m": "last", "15m": "last", "1H": "last"},
            "l2_features": {"5m": "last", "15m": "last", "1H": "last"},
        }

    def _parse_l2_policy(self, content: str) -> dict[str, Any]:
        """Извлекает L2 policy из контракта."""
        return {
            "raw_sampling_interval_sec": 10,
            "book_depth_levels": 25,
            "raw_retention_days": 3,
            "core_features_only": True,
            "core_features": ["spread_bps", "bid_imbalance", "ask_imbalance"],
        }

    def _parse_upsert_policy(self, content: str) -> dict[str, Any]:
        """Извлекает upsert policy из контракта."""
        return {
            "policy": "DO_NOT_OVERWRITE_NON_NULL_WITH_NULL",
            "sql_semantics": "COALESCE(excluded.col, target.col)",
        }

    def get_params_hash_subset(self) -> dict[str, Any]:
        """
        Возвращает подмножество контракта для вычисления params_hash.

        Returns:
            Dict с полями, влияющими на результат вычислений.
        """
        data = self.load()
        return {
            "contract_version": data["contract_version"],
            "normalization": data["normalization"],
            "aggregation": data["aggregation"],
            "l2_policy": data["l2_policy"],
            "upsert_policy": data["upsert_policy"],
        }

    def compute_params_hash(self) -> str:
        """
        Вычисляет SHA256 хеш параметров контракта.

        Returns:
            Hex-строка хеша (первые 16 символов).
        """
        subset = self.get_params_hash_subset()
        canonical = json.dumps(subset, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    @property
    def version(self) -> str:
        """Возвращает версию контракта."""
        return str(self.load()["contract_version"])


# Singleton для удобства
_default_loader: ContractLoader | None = None


def get_contract_loader() -> ContractLoader:
    """Возвращает singleton ContractLoader."""
    global _default_loader
    if _default_loader is None:
        _default_loader = ContractLoader()
    return _default_loader


def get_params_hash() -> str:
    """Shortcut для получения params_hash из контракта."""
    return get_contract_loader().compute_params_hash()


def get_contract_version() -> str:
    """Shortcut для получения версии контракта."""
    return get_contract_loader().version
