"""
Persistence layer for indicators insertion.

This package provides modules for validating, normalizing, and inserting
indicator data into the database.
"""

from .inserter import insert_indicators

__all__ = ["insert_indicators"]
