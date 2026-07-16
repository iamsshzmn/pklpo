"""Legacy audit CLI compatibility module."""

from .audit_simple import run_audit


def main() -> int:
    run_audit()
    return 0


__all__ = ["main", "run_audit"]
