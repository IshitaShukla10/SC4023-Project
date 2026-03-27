"""
column_store.py — backward-compatibility shim.

The implementation has moved to the store/ package.
This file re-exports everything so any existing import still works:

    from column_store import load_csv      # still works
    from column_store import ColumnStore   # still works
"""

from store.column_store import ColumnStore
from store.loader import load_csv, MONTH_ABBR, _parse_month

__all__ = ["ColumnStore", "load_csv", "MONTH_ABBR", "_parse_month"]
