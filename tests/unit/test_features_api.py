from __future__ import annotations


def test_features_api_exports_short_path_and_save_entrypoints() -> None:
    from src.features.api import (
        IndicatorStorageContract,
        compute_features,
        create_feature_application_bootstrap,
        create_feature_service,
        run_features_calc_short,
        run_features_calc_short_validate,
        save_batch,
        save_parquet_to_pg,
    )

    assert callable(compute_features)
    assert callable(create_feature_service)
    assert callable(create_feature_application_bootstrap)
    assert callable(save_batch)
    assert callable(save_parquet_to_pg)
    assert callable(run_features_calc_short)
    assert callable(run_features_calc_short_validate)
    assert IndicatorStorageContract.table_name
