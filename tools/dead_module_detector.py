#!/usr/bin/env python3
"""
Detector of dead modules inside src/features/.

A module is "dead" if it has no incoming imports from any Python file
in src/, tests/, or ops/ -- including other files inside src/features/ itself.

Handles both absolute imports (from src.features.X import ...)
and relative imports (from .X import ..., from ..X import ...).

Usage:
    python tools/dead_module_detector.py [--verbose] [--include-init]

Exits with code 0 always (detector, not enforcer).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent  # repo root

SCAN_ROOTS = [
    ROOT / "src",
    ROOT / "tests",
    ROOT / "ops",
]

FEATURES_ROOT = ROOT / "src" / "features"


def collect_feature_modules():
    return sorted(FEATURES_ROOT.rglob("*.py"))


def collect_all_source_files():
    files = []
    for root in SCAN_ROOTS:
        if root.exists():
            files.extend(root.rglob("*.py"))
    return files


def path_to_dotted(path):
    rel = path.relative_to(ROOT)
    return ".".join(rel.with_suffix("").parts)


def make_import_ids(fpath):
    full = path_to_dotted(fpath)
    parts = full.split(".")
    short = ".".join(parts[1:]) if parts[0] == "src" else full

    ids = []
    for variant in [full, short]:
        ids.append(variant)
        if variant.endswith(".__init__"):
            ids.append(variant[: -len(".__init__")])

    seen = set()
    result = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            result.append(i)
    return result


def resolve_relative_import(from_file, dots, module_part):
    pkg_parts = list(from_file.relative_to(ROOT).with_suffix("").parts)
    if pkg_parts[-1] == "__init__":
        anchor = pkg_parts[:-1]
    else:
        anchor = pkg_parts[:-1]
    go_up = dots - 1
    if go_up > 0:
        anchor = anchor[:-go_up] if go_up < len(anchor) else anchor
    full = ".".join(anchor) + ("." + module_part if module_part else "")
    parts = full.split(".")
    short = ".".join(parts[1:]) if parts and parts[0] == "src" else full
    return list({full, short})


RE_IMPORT = re.compile(r"^\s*import\s+([\w\.]+)", re.MULTILINE)
RE_FROM_ABS = re.compile(r"^\s*from\s+([\w][\w\.]*)\s+import", re.MULTILINE)
RE_FROM_REL = re.compile(r"^\s*from\s+(\.+)([\w\.]*)\s+import", re.MULTILINE)


def extract_referenced_ids(fpath):
    try:
        text = fpath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    ids = set()
    for m in RE_IMPORT.finditer(text):
        ids.add(m.group(1))
    for m in RE_FROM_ABS.finditer(text):
        ids.add(m.group(1))
    for m in RE_FROM_REL.finditer(text):
        for rid in resolve_relative_import(fpath, len(m.group(1)), m.group(2)):
            ids.add(rid)
    return ids


def build_index(all_files):
    index = {}
    for fpath in all_files:
        for mod in extract_referenced_ids(fpath):
            index.setdefault(mod, []).append(str(fpath.relative_to(ROOT)))
    return index


def find_importers(import_ids, index, self_path):
    self_str = str(self_path.relative_to(ROOT))
    importers = set()
    for iid in import_ids:
        for f in index.get(iid, []):
            if f != self_str:
                importers.add(f)
    return sorted(importers)


def main():
    parser = argparse.ArgumentParser(description="Detect dead modules in src/features/")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--include-init", action="store_true")
    args = parser.parse_args()

    feature_files = collect_feature_modules()
    all_source_files = collect_all_source_files()

    print(f"Scanning {len(feature_files)} feature modules against {len(all_source_files)} source files...")

    index = build_index(all_source_files)

    dead = []
    live = []

    for fpath in feature_files:
        if not args.include_init and fpath.name == "__init__.py":
            continue
        ids = make_import_ids(fpath)
        importers = find_importers(ids, index, fpath)
        if importers:
            live.append((fpath, importers))
        else:
            dead.append((fpath, importers))

    print("=" * 70)
    print(f"DEAD MODULES ({len(dead)} files -- no incoming imports):")
    print("=" * 70)
    if dead:
        for fpath, _ in sorted(dead, key=lambda x: x[0]):
            rel = fpath.relative_to(ROOT)
            lines = len(fpath.read_text(encoding="utf-8", errors="replace").splitlines())
            print(f"  {rel}  ({lines} lines)")
    else:
        print("  (none found)")

    if args.verbose:
        print()
        print("=" * 70)
        print(f"LIVE MODULES ({len(live)} files):")
        print("=" * 70)
        for fpath, importers in sorted(live, key=lambda x: x[0]):
            rel = fpath.relative_to(ROOT)
            print(f"  {rel}")
            for imp in importers[:3]:
                print(f"      <- {imp}")
            if len(importers) > 3:
                print(f"      <- ... and {len(importers) - 3} more")

    dead_lines = sum(
        len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        for p, _ in dead
    )
    total_py_lines = sum(
        len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        for p in feature_files
    )
    print()
    print("SUMMARY")
    print(f"  Feature .py files  : {len(feature_files)}")
    print(f"  Total lines (.py)  : {total_py_lines}")
    print(f"  Dead (no importers): {len(dead)} files  /  {dead_lines} lines")
    print(f"  Live               : {len(live)} files")


if __name__ == "__main__":
    main()
