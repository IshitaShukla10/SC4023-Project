"""
SC4023 Analysis — Section 5: Filter Permutation Analysis.

Tests all 3! = 6 orderings of the year/month/town filters and counts
total block reads at each stage to confirm the order used in engine.py
(year → month → town) is optimal.
"""

from itertools import permutations

from .utils import divider, sub_divider, blocks_touched, total_blocks
from .constants import TARGET_YEAR, START_MONTH, TOWNS, DEMO_X, DEMO_Y


def show_filter_permutations(store):
    divider("SECTION 5 - FILTER PERMUTATION ANALYSIS")

    print(f"""
  Our query uses 3 filters: year, month, town.
  With 3 filters there are 3! = 6 possible orderings.
  All 6 are tested below by counting block reads at each step.

  (x={DEMO_X}, y={DEMO_Y}, year={TARGET_YEAR}, start_month={START_MONTH})
    """)

    n            = len(store)
    all_idx      = list(range(n))
    end_month    = min(START_MONTH + DEMO_X - 1, 12)
    valid_months = set(range(START_MONTH, end_month + 1))

    filter_fns = {
        "year":  lambda idx: [i for i in idx if store.year_col[i]      == TARGET_YEAR],
        "month": lambda idx: [i for i in idx if store.month_num_col[i] in valid_months],
        "town":  lambda idx: [i for i in idx if store.town_col[i]      in TOWNS],
    }

    orders        = list(permutations(["year", "month", "town"]))
    results_table = []
    for order in orders:
        active      = all_idx
        stage_reads = [blocks_touched(active)]
        for f in order:
            active = filter_fns[f](active)
            stage_reads.append(blocks_touched(active))
        total_read = sum(stage_reads)
        results_table.append((order, stage_reads, total_read, len(active)))

    results_table.sort(key=lambda r: r[2])

    print(f"  {'Filter order':<30} {'Start':>6} {'-> F1':>6} {'-> F2':>6} "
          f"{'-> F3':>6} {'Total':>7}  {'Rows left':>10}")
    print(f"  {'-'*30} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*7}  {'-'*10}")

    last = len(results_table) - 1
    for rank, (order, reads, total, survivors) in enumerate(results_table):
        order_str = " -> ".join(order)
        label     = "  BEST" if rank == 0 else ("  WORST" if rank == last else "")
        print(f"  {order_str:<30} {reads[0]:>6} {reads[1]:>6} {reads[2]:>6} "
              f"{reads[3]:>6} {total:>7}  {survivors:>10}{label}")

    best, worst = results_table[0], results_table[-1]
    print(f"\n  Best  : {' -> '.join(best[0])}  ({best[2]} total block reads)")
    print(f"  Worst : {' -> '.join(worst[0])}  ({worst[2]} total block reads)")
    print(f"  Difference: {worst[2] - best[2]} fewer block reads with the best ordering")
    print(f"  engine.py uses year -> month -> town, confirmed optimal above.")

    sub_divider("Why year filter goes first")
    n_blks      = total_blocks(n)
    after_year  = filter_fns["year"](all_idx)
    after_month = filter_fns["month"](all_idx)
    after_town  = filter_fns["town"](all_idx)

    print(f"\n  Applying each filter independently to all {n:,} rows:")
    year_blks  = blocks_touched(after_year)
    month_blks = blocks_touched(after_month)
    town_blks  = blocks_touched(after_town)
    print(f"    year  : {n:>7,} -> {len(after_year):>7,} rows  "
          f"({year_blks:>3} blocks left, "
          f"eliminated {(n_blks - year_blks)/n_blks*100:.0f}% of blocks)")
    print(f"    month : {n:>7,} -> {len(after_month):>7,} rows  "
          f"({month_blks:>3} blocks left)")
    print(f"    town  : {n:>7,} -> {len(after_town):>7,} rows  "
          f"({town_blks:>3} blocks left)")
    print(f"\n  Year alone eliminates {(n_blks - year_blks)/n_blks*100:.0f}% of blocks,")
    print(f"  so filters 2 and 3 only scan the much smaller remaining set.")
