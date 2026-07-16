from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _module_imports(relative_path: str) -> list[str]:
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative_path)
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append("." * node.level + module)

    return imports


def test_candles_domain_repair_does_not_depend_on_infrastructure_or_interfaces() -> (
    None
):
    imports = _module_imports("src/candles/domain/repair.py")

    assert not any("src.candles.infrastructure" in item for item in imports)
    assert not any("src.candles.interfaces" in item for item in imports)


def test_candles_application_repair_use_cases_do_not_import_infrastructure_modules() -> (
    None
):
    imports = _module_imports("src/candles/application/repair/use_cases.py")

    assert not any("src.candles.infrastructure" in item for item in imports)
    assert not any("src.candles.interfaces" in item for item in imports)


def test_candles_interfaces_repair_is_allowed_to_wire_application_and_infrastructure() -> (
    None
):
    imports = _module_imports("src/candles/interfaces/repair.py")

    assert any("src.candles.application.repair" in item for item in imports)
    assert any(
        "src.candles.infrastructure.repair_repository" in item for item in imports
    )
