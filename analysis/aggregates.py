"""
SC4023 Analysis — Section 6: Extra Aggregates (avg/stddev PSM).

Once the matched rows for a given (x, y) query are in memory, computing
avg and stddev PSM costs almost nothing extra — just 4 more lines after
the existing min loop.  Stddev is also useful: low = stable market,
high = wider spread with potential bargains.
"""

import math

from .utils import divider
from .constants import TARGET_YEAR, START_MONTH, TOWNS


def show_extra_aggregates(store):
    divider("SECTION 6 - EXTRA AGGREGATES (avg PSM, stddev PSM)")

    print("""
  engine.py computes min price per sqm.  avg and stddev come for free
  since the matched rows are already in memory — just 4 extra lines
  after the existing min loop.

  Stddev interpretation:
    Low  -> prices tightly clustered (stable, predictable market)
    High -> prices vary widely (potential bargains or outliers)
    """)

    n = len(store)
    candidate_idx = [
        i for i in range(n)
        if store.year_col[i] == TARGET_YEAR
        and store.town_col[i] in TOWNS
    ]

    demo_pairs = [(1, 80), (1, 100), (1, 114), (2, 80), (4, 80), (8, 80), (8, 130)]

    print(f"  {'(x,y)':<10} {'Rows':>6} {'Min PSM':>9} {'Avg PSM':>9} "
          f"{'StdDev':>9} {'Max PSM':>9}  Note")
    print(f"  {'-'*10} {'-'*6} {'-'*9} {'-'*9} {'-'*9} {'-'*9}  {'-'*25}")

    for x, y in demo_pairs:
        em      = min(START_MONTH + x - 1, 12)
        vm      = set(range(START_MONTH, em + 1))
        mid     = [i for i in candidate_idx if store.month_num_col[i] in vm]
        matched = [i for i in mid if store.floor_area_col[i] >= y]

        if not matched:
            print(f"  ({x},{y})<10 {'no result'}")
            continue

        psm_vals = [store.resale_price_col[i] / store.floor_area_col[i]
                    for i in matched]
        mn  = min(psm_vals)
        mx  = max(psm_vals)
        avg = sum(psm_vals) / len(psm_vals)
        var = sum((p - avg) ** 2 for p in psm_vals) / len(psm_vals)
        std = math.sqrt(var)

        note = ("tight market" if std < 500
                else "moderate spread" if std < 700
                else "wide spread")

        print(f"  ({x},{y:<3}) {len(matched):>6,} {mn:>9,.0f} {avg:>9,.0f} "
              f"{std:>9,.0f} {mx:>9,.0f}  {note}")

    print(f"\n  The 4 lines to add in engine.py's run_query() after the existing min loop:")
    print(f"  ┌───────────────────────────────────────────────────────────────")
    print(f"  │  all_psm = [store.resale_price_col[i] / store.floor_area_col[i]")
    print(f"  │             for i in matched]")
    print(f"  │  avg_psm = sum(all_psm) / len(all_psm)")
    print(f"  │  var     = sum((p - avg_psm)**2 for p in all_psm) / len(all_psm)")
    print(f"  │  std_psm = math.sqrt(var)")
    print(f"  └───────────────────────────────────────────────────────────────")
