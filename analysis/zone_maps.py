"""
SC4023 Analysis — Section 2: Zone Maps.

A zone map stores (min, max) per block.  Before reading a block we
check whether the filter value could possibly fall in [min, max].
If not, the entire block is skipped without touching its data.

Key finding: zone maps only help when data is sorted/clustered by the
filtered column.  year_col (sorted chronologically) gets ~93% skip rate;
floor_area (scattered) gets 0%.
"""

from .utils import divider, sub_divider, total_blocks
from .constants import BLOCK_SIZE, TARGET_YEAR, START_MONTH, DEMO_X, DEMO_Y


def build_zone_map(col: list) -> list:
    """
    Build a (min, max) zone map for a column.

    Returns
    -------
    list of (min_val, max_val) tuples, one per block.
    """
    zones = []
    for b in range(0, len(col), BLOCK_SIZE):
        chunk = col[b : b + BLOCK_SIZE]
        zones.append((min(chunk), max(chunk)))
    return zones


def zone_map_skip_count(zones: list, condition) -> int:
    """
    Count blocks that can be skipped because condition(min, max) is False.

    Parameters
    ----------
    zones     : list     output of build_zone_map()
    condition : callable (min_val, max_val) -> bool
                Returns True if the block MIGHT contain matching rows.
    """
    return sum(1 for mn, mx in zones if not condition(mn, mx))


def show_zone_maps(store):
    divider("SECTION 2 - ZONE MAPS")

    print("""
  Zone maps store (min, max) per block so we can skip blocks entirely
  when the filter value is outside that range.

  Key insight: this ONLY works well when data is sorted/clustered by the
  filtered column.  year_col is ordered chronologically → huge skip rate.
  floor_area is scattered → every block spans the full range → 0% skipped.
    """)

    n      = len(store)
    n_blks = total_blocks(n)

    zm_year  = build_zone_map(store.year_col)
    zm_month = build_zone_map(store.month_num_col)
    zm_area  = build_zone_map(store.floor_area_col)
    zm_price = build_zone_map(store.resale_price_col)
    zm_lcd   = build_zone_map(store.lease_commence_date_col)

    end_month = min(START_MONTH + DEMO_X - 1, 12)
    tests = [
        ("year_col",            zm_year,  f"year == {TARGET_YEAR}",
         lambda mn, mx: mn <= TARGET_YEAR <= mx),
        ("month_num_col",       zm_month, f"month in [{START_MONTH}..{end_month}]",
         lambda mn, mx: not (mx < START_MONTH or mn > end_month)),
        ("floor_area_sqm",      zm_area,  f"area >= {DEMO_Y}",
         lambda mn, mx: mx >= DEMO_Y),
        ("resale_price",        zm_price, "price >= 400,000",
         lambda mn, mx: mx >= 400_000),
        ("lease_commence_date", zm_lcd,   "lcd >= 2000",
         lambda mn, mx: mx >= 2000),
    ]

    print(f"  {'Column':<25} {'Filter':<30} {'Skippable':>10} {'Out of':>8} {'Skip %':>8}  Verdict")
    print(f"  {'-'*25} {'-'*30} {'-'*10} {'-'*8} {'-'*8}  {'-'*15}")
    for col_name, zm, condition_str, cond in tests:
        skipped = zone_map_skip_count(zm, cond)
        pct     = skipped / n_blks * 100
        verdict = "VERY USEFUL" if pct >= 50 else ("Moderate" if pct >= 10 else "Not useful")
        print(f"  {col_name:<25} {condition_str:<30} {skipped:>10} {n_blks:>8} "
              f"{pct:>7.1f}%  {verdict}")

    sub_divider("Walkthrough: year_col zone map (first 5 blocks)")
    print(f"\n  {'Block':<8} {'Min year':<12} {'Max year':<12} "
          f"{'Filter: year==2015':<22} Decision")
    print(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*22} {'-'*15}")
    for b, (mn, mx) in enumerate(zm_year[:5]):
        keep     = mn <= TARGET_YEAR <= mx
        decision = "READ block" if keep else "SKIP block"
        marker   = " <-- skipped" if not keep else ""
        print(f"  {b:<8} {mn:<12} {mx:<12} "
              f"{'could match' if keep else 'impossible':<22} {decision}{marker}")

    kept    = n_blks - zone_map_skip_count(zm_year, lambda mn, mx: mn <= TARGET_YEAR <= mx)
    skipped = n_blks - kept
    print(f"\n  Result: read {kept} blocks, skipped {skipped}")
    print(f"  Without zone map: all {n_blks} blocks scanned")
    print(f"  With zone map: only {kept} blocks ({kept/n_blks*100:.1f}%) — "
          f"{skipped/n_blks*100:.1f}% reduction")
