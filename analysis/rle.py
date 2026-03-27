"""
SC4023 Analysis — Section 4: Run-Length Encoding (RLE).

Collapses consecutive identical values into (value, count) pairs.
Highly effective when a column is sorted/clustered (town: ~100x).
Useless when values change every row (storey_range: ~1x).
"""

from .utils import divider, sub_divider
from .constants import TOWNS


def count_rle_runs(col: list) -> int:
    """Count the number of distinct consecutive runs in a column."""
    if not col:
        return 0
    runs = 1
    for i in range(1, len(col)):
        if col[i] != col[i - 1]:
            runs += 1
    return runs


def build_rle(col: list) -> list:
    """
    Encode a column as a list of (value, count) run tuples.

    Example
    -------
    ["ANG MO KIO", "ANG MO KIO", "BEDOK"] → [("ANG MO KIO", 2), ("BEDOK", 1)]
    """
    if not col:
        return []
    rle   = []
    cur   = col[0]
    count = 1
    for i in range(1, len(col)):
        if col[i] == cur:
            count += 1
        else:
            rle.append((cur, count))
            cur   = col[i]
            count = 1
    rle.append((cur, count))
    return rle


def show_rle(store):
    divider("SECTION 4 - RUN-LENGTH ENCODING (RLE)")

    print("""
  RLE stores consecutive runs as (value, count) pairs.
  Instead of storing "JURONG WEST" 40,000 times in a row,
  we store one entry: ("JURONG WEST", 40000).

  This ONLY works well if the column is sorted/grouped.
  town_col is sorted alphabetically → RLE gives huge compression.
  storey_range changes almost every row → RLE barely helps.
    """)

    cols = [
        ("town",         store.town_col),
        ("month (raw)",  store.month_col),
        ("flat_type",    store.flat_type_col),
        ("flat_model",   store.flat_model_col),
        ("storey_range", store.storey_range_col),
    ]

    n = len(store)
    print(f"  {'Column':<22} {'Runs':>8} {'Rows':>8} {'Run %':>8} "
          f"{'Ratio':>8}  Verdict")
    print(f"  {'-'*22} {'-'*8} {'-'*8} {'-'*8} {'-'*8}  {'-'*22}")

    for col_name, col in cols:
        rle   = build_rle(col)
        runs  = len(rle)
        pct   = runs / n * 100
        ratio = n / runs if runs > 0 else 0

        if ratio >= 20:
            verdict = "implement - excellent"
        elif ratio >= 5:
            verdict = "good compression"
        elif ratio >= 2:
            verdict = "marginal"
        else:
            verdict = "skip - barely compresses"

        print(f"  {col_name:<22} {runs:>8,} {n:>8,} {pct:>7.1f}% "
              f"{ratio:>7.1f}x  {verdict}")

    sub_divider("Walkthrough: town column RLE")
    rle_town = build_rle(store.town_col)
    print(f"\n  Full RLE compresses {n:,} rows down to {len(rle_town)} entries")
    print(f"\n  First 6 runs:")
    print(f"  {'Value':<25} {'Count':>8}  {'Rows covered'}")
    print(f"  {'-'*25} {'-'*8}  {'-'*12}")
    running = 0
    for val, cnt in rle_town[:6]:
        print(f"  {val:<25} {cnt:>8,}  rows {running:,}-{running+cnt-1:,}")
        running += cnt
    print(f"  ... ({len(rle_town) - 6} more runs)")

    matched_from_rle   = [(v, c) for v, c in rle_town if v in TOWNS]
    total_rows_matched = sum(c for _, c in matched_from_rle)
    print(f"\n  For filtering: instead of checking all {n:,} values,")
    print(f"  we only need to scan through {len(rle_town)} runs:")
    print(f"    Matching runs : {len(matched_from_rle)}")
    print(f"    Rows covered  : {total_rows_matched:,}")
    print(f"    Skipped runs  : {len(rle_town) - len(matched_from_rle)}")
