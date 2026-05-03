"""
Compatibility package for legacy tests.

Legacy tests under ``tests/features/tests`` use relative imports such as
``from ..core import ...``. The production code now lives under ``src.features``,
so this package re-exports the current modules without changing the tests.
"""
