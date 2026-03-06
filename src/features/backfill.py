"""Legacy module alias for ``src.features.application.backfill``."""

import sys

from .application import backfill as _backfill_module

sys.modules[__name__] = _backfill_module
