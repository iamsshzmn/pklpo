"""Ports for the features bounded context."""

from .calculator_backend import FeatureBackendId, FeatureCalculatorBackend
from .partition import PartitionManager
from .persistence import IndicatorRepository, RepositoryStorageProfile
from .quality import (
    QualityConnectionProtocol,
    QualityEngineProtocol,
    QualityPipelineRunner,
    QualityPoolProtocol,
    QualityReportProtocol,
)
from .recalc import FeatureRecalcPort, RecalcOutcome
from .save import FeatureSaveObservation, FeatureSaveObserver, FeatureSaveValidator
from .schema_ddl import SchemaDDLPort
from .storage import FeatureSaveDependenciesFactory, FeatureStorageGateway

__all__ = [
    "FeatureBackendId",
    "FeatureCalculatorBackend",
    "FeatureRecalcPort",
    "FeatureSaveDependenciesFactory",
    "FeatureSaveObservation",
    "FeatureSaveObserver",
    "FeatureSaveValidator",
    "FeatureStorageGateway",
    "IndicatorRepository",
    "PartitionManager",
    "QualityConnectionProtocol",
    "QualityEngineProtocol",
    "QualityPipelineRunner",
    "QualityPoolProtocol",
    "QualityReportProtocol",
    "RecalcOutcome",
    "RepositoryStorageProfile",
    "SchemaDDLPort",
]
