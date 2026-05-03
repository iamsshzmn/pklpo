from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEATURES_ROOT = PROJECT_ROOT / "src" / "features"
OUTER_ENTRYPOINTS = (
    PROJECT_ROOT / "src" / "cli" / "commands" / "features.py",
    PROJECT_ROOT / "ops" / "airflow" / "dags" / "features_calc.py",
    PROJECT_ROOT / "ops" / "airflow" / "dags" / "features_calc_short.py",
)
FORBIDDEN_FEATURE_LAYER_PREFIXES = (
    "src.features.application",
    "src.features.core",
    "src.features.infrastructure",
    "src.features.container",
)


def _iter_python_files(path: Path):
    if path.is_file():
        return [path] if path.suffix == ".py" else []
    return sorted(p for p in path.rglob("*.py") if "__pycache__" not in p.parts)


def _collect_feature_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src.features"):
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
            "src.features"
        ):
            imports.add(node.module)

    return imports


def test_application_layer_has_no_infrastructure_imports() -> None:
    forbidden = (
        "from ..infrastructure",
        "from .infrastructure",
        "from src.features.infrastructure",
        "import src.features.infrastructure",
    )

    for path in _iter_python_files(FEATURES_ROOT / "application"):
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden), str(path)


def test_domain_layer_has_no_infrastructure_or_orm_imports() -> None:
    forbidden = (
        "infrastructure",
        "sqlalchemy",
        "src.models",
        "from src.features.infrastructure.models",
    )

    for path in _iter_python_files(FEATURES_ROOT / "domain"):
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden), str(path)


def test_features_package_has_no_src_models_imports() -> None:
    for path in _iter_python_files(FEATURES_ROOT):
        source = path.read_text(encoding="utf-8")
        assert "from src.models import" not in source, str(path)
        assert "import src.models" not in source, str(path)


def test_legacy_flat_entrypoints_are_removed() -> None:
    for relative_path in ("core.py", "specs.py", "ta_safe.py", "config.py"):
        assert not (FEATURES_ROOT / relative_path).exists(), relative_path


def test_outer_entrypoints_use_only_public_features_surface() -> None:
    violations: list[str] = []

    for path in OUTER_ENTRYPOINTS:
        for imported in _collect_feature_imports(path):
            if imported.startswith(FORBIDDEN_FEATURE_LAYER_PREFIXES):
                violations.append(f"{path}: {imported}")

    assert not violations, (
        "External code must not import features application/core/infrastructure/container "
        "layers directly:\n" + "\n".join(violations)
    )
