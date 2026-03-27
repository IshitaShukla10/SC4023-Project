"""
SC4023 Analysis — Shared formatting and block-counting utilities.

These helpers are reused across multiple analysis sections.
"""

import math
from .constants import BLOCK_SIZE


def divider(title: str):
    """Print a major section header."""
    width = 66
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def sub_divider(title: str):
    """Print a minor subsection header."""
    print(f"\n--- {title} ---")


def blocks_touched(index_list: list) -> int:
    """Count how many distinct blocks the given row indices span."""
    return len({i // BLOCK_SIZE for i in index_list})


def total_blocks(n_rows: int) -> int:
    """Return the number of blocks needed to cover n_rows."""
    return math.ceil(n_rows / BLOCK_SIZE)
