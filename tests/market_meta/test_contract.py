"""
Тесты для ContractLoader и params_hash.

Проверяет, что изменение контракта меняет params_hash (golden snapshot).
"""

from pathlib import Path

from src.market_meta_backup.domain.contract import (
    ContractLoader,
    get_params_hash,
)


class TestContractLoader:
    """Тесты загрузчика контракта."""

    def test_load_contract_returns_dict(self) -> None:
        """Контракт загружается и возвращает dict."""
        loader = ContractLoader()
        data = loader.load()

        assert isinstance(data, dict)
        assert "contract_version" in data
        assert "normalization" in data
        assert "aggregation" in data

    def test_contract_version_parsed(self) -> None:
        """Версия контракта корректно парсится."""
        loader = ContractLoader()
        version = loader.version

        assert version == "1.0.0"

    def test_params_hash_is_stable(self) -> None:
        """params_hash стабилен при повторных вызовах."""
        hash1 = get_params_hash()
        hash2 = get_params_hash()

        assert hash1 == hash2
        assert len(hash1) == 16

    def test_params_hash_changes_with_contract(self, tmp_path: Path) -> None:
        """params_hash меняется при изменении контракта."""
        # Создаём временный контракт v1
        contract_v1 = tmp_path / "contract_v1.md"
        contract_v1.write_text(
            "> Версия: 1.0.0\n## Test\nContent",
            encoding="utf-8",
        )

        # Создаём временный контракт v2
        contract_v2 = tmp_path / "contract_v2.md"
        contract_v2.write_text(
            "> Версия: 2.0.0\n## Test\nContent",
            encoding="utf-8",
        )

        loader_v1 = ContractLoader(contract_v1)
        loader_v2 = ContractLoader(contract_v2)

        hash_v1 = loader_v1.compute_params_hash()
        hash_v2 = loader_v2.compute_params_hash()

        assert hash_v1 != hash_v2, "Изменение версии должно менять params_hash"

    def test_golden_snapshot_params_hash(self) -> None:
        """
        Golden snapshot: params_hash для контракта v1.0.0.

        Если этот тест падает — значит контракт изменился.
        Обнови GOLDEN_HASH после ревью изменений.
        """
        # GOLDEN: хеш для контракта v1.0.0
        GOLDEN_HASH = "5034cff9cfa7ee5d"

        current_hash = get_params_hash()
        assert current_hash == GOLDEN_HASH, (
            f"params_hash изменился! "
            f"Было: {GOLDEN_HASH}, стало: {current_hash}. "
            f"Если изменение контракта намеренное — обнови GOLDEN_HASH."
        )

    def test_normalization_rules_present(self) -> None:
        """Правила нормализации присутствуют в контракте."""
        loader = ContractLoader()
        data = loader.load()

        norm = data["normalization"]
        assert "funding" in norm
        assert "open_interest" in norm
        assert "l2" in norm

    def test_aggregation_rules_present(self) -> None:
        """Правила агрегации присутствуют в контракте."""
        loader = ContractLoader()
        data = loader.load()

        agg = data["aggregation"]
        assert "funding_rate" in agg
        assert "open_interest" in agg


class TestContractIntegrity:
    """Тесты целостности контракта."""

    def test_contract_file_exists(self) -> None:
        """Файл контракта существует."""
        loader = ContractLoader()
        assert loader._path.exists(), f"Контракт не найден: {loader._path}"

    def test_params_hash_subset_complete(self) -> None:
        """params_hash_subset содержит все необходимые поля."""
        loader = ContractLoader()
        subset = loader.get_params_hash_subset()

        required_fields = [
            "contract_version",
            "normalization",
            "aggregation",
            "l2_policy",
            "upsert_policy",
        ]
        for field in required_fields:
            assert field in subset, f"Отсутствует поле {field} в params_hash_subset"
