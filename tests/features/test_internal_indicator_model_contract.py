from src.features.infrastructure.models import CalculationMetadata, Indicator
from src.features.storage_contract import IndicatorStorageContract


def test_indicator_model_uses_storage_contract_table_name():
    assert Indicator.__tablename__ == IndicatorStorageContract.table_name


def test_indicator_model_has_no_duplicate_columns():
    column_names = [column.name for column in Indicator.__table__.columns]
    assert len(column_names) == len(set(column_names))

def test_calculation_metadata_model_exists():
    assert CalculationMetadata.__tablename__ == "calculation_metadata"
