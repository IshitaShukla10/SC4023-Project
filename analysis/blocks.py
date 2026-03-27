"""
SC4023 Analysis — Section 1: Block Abstraction.

Shows how 259k rows split into fixed-size blocks of 1,000 and why
grouping rows into blocks gives us a concrete way to measure query
speedup (blocks read vs. total blocks).
"""

from .utils import divider, total_blocks
from .constants import BLOCK_SIZE


def show_block_abstraction(store):
    divider("SECTION 1 - BLOCK ABSTRACTION")

    n      = len(store)
    n_blks = total_blocks(n)

    print(f"\n  Dataset        : {n:,} rows")
    print(f"  Block size     : {BLOCK_SIZE:,} rows per block")
    print(f"  Total blocks   : {n_blks} per column")
    print(f"  Columns stored : 12")
    print(f"  Total blocks   : {n_blks * 12} across all columns\n")

    print(f"  {'Block':<8} {'Row range':<20} {'Town at start of block'}")
    print(f"  {'-'*8} {'-'*20} {'-'*20}")
    for b in range(min(4, n_blks)):
        start = b * BLOCK_SIZE
        end   = min(start + BLOCK_SIZE - 1, n - 1)
        print(f"  {b:<8} {start:>7,} - {end:<7,}    {store.town_col[start]}")
    print(f"  {'...':<8} {'...':<20}")
    last_start = (n_blks - 1) * BLOCK_SIZE
    print(f"  {n_blks-1:<8} {last_start:>7,} - {n-1:<7,}    {store.town_col[last_start]}")

    print(f"\n  So a query matching rows in just 1 block reads 1/{n_blks} = "
          f"{1/n_blks*100:.1f}% of the data.")
    print(f"  Block abstraction gives us a concrete way to measure that speedup.")
