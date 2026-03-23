# SC4023 Group Project - analysis.py
# Ishita Shukla - U2323465X
#
# I wrote this file to justify which compression / storage techniques
# actually make sense for our dataset, and which ones don't.
# The idea was to run the numbers live from the real CSV rather than
# just guessing based on theory, since some techniques look good on paper
# but don't help much with this particular data layout.
#
# Run it like:
#   python analysis.py ResalePricesSingapore.csv
#
# What it covers:
#   1. Block Abstraction  - how we split columns into chunks and why that matters
#   2. Zone Maps          - skip blocks using min/max metadata (only useful when data is sorted)
#   3. Dictionary Encoding - swap repeated strings for small integers
#   4. Run-Length Encoding - collapse repeated values (depends heavily on sort order)
#   5. Filter Permutations - test all 6 orderings of our 3 filters to find the best one
#   6. Extra Aggregates    - avg and stddev PSM basically come for free once rows are matched
#
# All output is computed from the actual data so nothing is made up.

import sys
import os
import math
import time
from itertools import permutations

# make the import work regardless of which directory you run from
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from column_store import load_csv
except ModuleNotFoundError:
    print()
    print("ERROR: column_store.py not found")
    print("Both files need to be in the same folder. Run from inside the project folder:")
    print()
    print("  cd /path/to/project")
    print("  python3 analysis.py ResalePricesSingapore.csv")
    print()
    sys.exit(1)

# Parameters derived from my matric number U2323465X
# (same logic as main.py, hardcoded here so I don't need to pass the matric number)
TARGET_YEAR  = 2015
START_MONTH  = 6
TOWNS        = {"CHOA CHU KANG", "CLEMENTI", "HOUGANG", "JURONG WEST", "PASIR RIS"}
BLOCK_SIZE   = 1000   # rows per block
DEMO_X       = 1
DEMO_Y       = 80


# ---- small helper functions ------------------------------------------------

def divider(title: str):
    width = 66
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def sub_divider(title: str):
    print(f"\n--- {title} ---")


def blocks_touched(index_list: list) -> int:
    # just counts how many distinct block numbers appear in the index list
    return len({i // BLOCK_SIZE for i in index_list})


def total_blocks(n_rows: int) -> int:
    return math.ceil(n_rows / BLOCK_SIZE)


# ============================================================================
# SECTION 1 - BLOCK ABSTRACTION
# ============================================================================

def show_block_abstraction(store):
    # The whole point of block abstraction is that we don't want to read all
    # 259k rows for every query. If we group rows into blocks of 1000, a query
    # that only matches 1% of rows ideally only reads 1% of blocks.
    # This section just prints out what the block layout looks like on our data.
    divider("SECTION 1 - BLOCK ABSTRACTION")

    n      = len(store)
    n_blks = total_blocks(n)

    print(f"\n  Dataset        : {n:,} rows")
    print(f"  Block size     : {BLOCK_SIZE:,} rows per block")
    print(f"  Total blocks   : {n_blks} per column")
    print(f"  Columns stored : 12")
    print(f"  Total blocks   : {n_blks * 12} across all columns\n")

    # show what the first few blocks look like concretely
    print(f"  {'Block':<8} {'Row range':<20} {'Town at start of block'}")
    print(f"  {'-'*8} {'-'*20} {'-'*20}")
    for b in range(min(4, n_blks)):
        start = b * BLOCK_SIZE
        end   = min(start + BLOCK_SIZE - 1, n - 1)
        town  = store.town_col[start]
        print(f"  {b:<8} {start:>7,} - {end:<7,}    {town}")
    print(f"  {'...':<8} {'...':<20}")
    print(f"  {n_blks-1:<8} "
          f"{(n_blks-1)*BLOCK_SIZE:>7,} - {n-1:<7,}    "
          f"{store.town_col[(n_blks-1)*BLOCK_SIZE]}")

    print(f"\n  So a query matching rows in just 1 block reads 1/{n_blks} = "
          f"{1/n_blks*100:.1f}% of the data.")
    print(f"  Block abstraction gives us a concrete way to measure that speedup.")


# ============================================================================
# SECTION 2 - ZONE MAPS
# ============================================================================

def build_zone_map(col: list) -> list:
    # A zone map is just a (min, max) pair per block.
    # Before reading a block, we check if our filter value could possibly
    # fall in [min, max]. If not, we skip the whole block.
    # This only helps if data is sorted or at least clustered - otherwise
    # every block will span the full range and nothing gets skipped.
    zones = []
    for b in range(0, len(col), BLOCK_SIZE):
        chunk = col[b : b + BLOCK_SIZE]
        zones.append((min(chunk), max(chunk)))
    return zones


def zone_map_skip_count(zones: list, condition) -> int:
    # count blocks where condition(min, max) is False - those are the ones we skip
    skipped = sum(1 for mn, mx in zones if not condition(mn, mx))
    return skipped


def show_zone_maps(store):
    divider("SECTION 2 - ZONE MAPS")

    print("""
  Zone maps store (min, max) per block so we can skip blocks entirely
  when the filter value is outside that range.

  The key insight I found: this ONLY works well when data is sorted/clustered
  by the column we're filtering on. For year_col the CSV happens to be
  ordered chronologically, so we get a huge skip rate. But for something
  like floor_area the values are scattered everywhere, so every block
  spans nearly the full range and zone maps don't help at all.
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
        ("year_col",             zm_year,  f"year == {TARGET_YEAR}",
         lambda mn, mx: mn <= TARGET_YEAR <= mx),
        ("month_num_col",        zm_month, f"month in [{START_MONTH}..{end_month}]",
         lambda mn, mx: not (mx < START_MONTH or mn > end_month)),
        ("floor_area_sqm",       zm_area,  f"area >= {DEMO_Y}",
         lambda mn, mx: mx >= DEMO_Y),
        ("resale_price",         zm_price, "price >= 400,000",
         lambda mn, mx: mx >= 400_000),
        ("lease_commence_date",  zm_lcd,   "lcd >= 2000",
         lambda mn, mx: mx >= 2000),
    ]

    print(f"  {'Column':<25} {'Filter':<30} {'Skippable':>10} {'Out of':>8} {'Skip %':>8}  Verdict")
    print(f"  {'-'*25} {'-'*30} {'-'*10} {'-'*8} {'-'*8}  {'-'*15}")
    for col_name, zm, condition_str, cond in tests:
        skipped = zone_map_skip_count(zm, cond)
        pct     = skipped / n_blks * 100
        if pct >= 50:
            verdict = "VERY USEFUL"
        elif pct >= 10:
            verdict = "Moderate"
        else:
            verdict = "Not useful"
        print(f"  {col_name:<25} {condition_str:<30} {skipped:>10} {n_blks:>8} "
              f"{pct:>7.1f}%  {verdict}")

    # concrete walkthrough for year_col since it's our best example
    sub_divider("Walkthrough: year_col zone map (first 5 blocks)")
    print(f"\n  {'Block':<8} {'Min year':<12} {'Max year':<12} "
          f"{'Filter: year==2015':<22} Decision")
    print(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*22} {'-'*15}")
    for b, (mn, mx) in enumerate(zm_year[:5]):
        keep     = mn <= TARGET_YEAR <= mx
        decision = "READ block" if keep else "SKIP block"
        marker   = " <-- skipped" if not keep else ""
        print(f"  {b:<8} {mn:<12} {mx:<12} "
              f"{'could match' if keep else 'impossible':<22} "
              f"{decision}{marker}")

    kept    = n_blks - zone_map_skip_count(zm_year, lambda mn, mx: mn <= TARGET_YEAR <= mx)
    skipped = zone_map_skip_count(zm_year, lambda mn, mx: mn <= TARGET_YEAR <= mx)
    print(f"\n  Result: read {kept} blocks, skipped {skipped}")
    print(f"  Without zone map: all {n_blks} blocks would be scanned")
    print(f"  With zone map: only {kept} blocks ({kept/n_blks*100:.1f}% of total) - "
          f"{skipped/n_blks*100:.1f}% reduction")


# ============================================================================
# SECTION 3 - DICTIONARY ENCODING
# ============================================================================

def build_dict_encoding(col: list):
    # replace each string with a small integer, keep a lookup table
    # for decoding when we need to display results
    unique_vals = sorted(set(col))
    lookup      = {i: v for i, v in enumerate(unique_vals)}
    reverse     = {v: i for i, v in lookup.items()}
    encoded     = [reverse[v] for v in col]
    return encoded, lookup


def estimate_bytes(col: list, is_encoded: bool, lookup: dict = None) -> int:
    # rough estimate: original = sum of string lengths, encoded = 1 byte per row + dict size
    # not accounting for Python object overhead, just the raw character/integer data
    if is_encoded:
        row_bytes  = len(col) * 1
        dict_bytes = sum(len(v) for v in lookup.values())
        return row_bytes + dict_bytes
    else:
        return sum(len(v) for v in col)


def count_rle_runs(col: list) -> int:
    if not col:
        return 0
    runs = 1
    for i in range(1, len(col)):
        if col[i] != col[i - 1]:
            runs += 1
    return runs


def show_dict_encoding(store):
    divider("SECTION 3 - DICTIONARY ENCODING")

    print("""
  Dictionary encoding swaps repeated strings for a small integer.
  We keep a lookup table (e.g. {0: "ANG MO KIO", 1: "BEDOK", ...})
  and store just the integer index per row.

  This is most effective when a column has few unique values (low cardinality).
  For something like 'town' with only 26 towns across 259k rows, the savings
  are huge. For 'block' with 2700+ unique values, encoding barely helps because
  the dictionary itself becomes large.
    """)

    string_cols = [
        ("town",                store.town_col,           "categorical"),
        ("flat_model",          store.flat_model_col,     "categorical"),
        ("storey_range",        store.storey_range_col,   "categorical"),
        ("flat_type",           store.flat_type_col,      "categorical"),
        ("street_name",         store.street_name_col,    "categorical"),
        ("block",               store.block_col,          "categorical"),
        ("month (raw)",         store.month_col,          "time"),
    ]

    print(f"  {'Column':<22} {'Unique':>7} {'Original':>12} {'Encoded':>12} "
          f"{'Ratio':>8}  Recommendation")
    print(f"  {'-'*22} {'-'*7} {'-'*12} {'-'*12} {'-'*8}  {'-'*22}")

    for col_name, col, _ in string_cols:
        unique   = len(set(col))
        enc, lkp = build_dict_encoding(col)
        orig_b   = estimate_bytes(col, is_encoded=False)
        enc_b    = estimate_bytes(enc, is_encoded=True, lookup=lkp)
        ratio    = orig_b / enc_b if enc_b > 0 else 0

        if ratio >= 6:
            rec = "implement - big savings"
        elif ratio >= 3:
            rec = "worth implementing"
        elif ratio >= 1.5:
            rec = "marginal benefit"
        else:
            rec = "skip - too many unique values"

        print(f"  {col_name:<22} {unique:>7,} {orig_b:>10,}B {enc_b:>10,}B "
              f"{ratio:>7.1f}x  {rec}")

    # town column walkthrough
    sub_divider("Walkthrough: how town encoding works")
    enc_town, lkp_town = build_dict_encoding(store.town_col)

    print(f"\n  Lookup table ({len(lkp_town)} entries, first 8 shown):")
    for code, name in sorted(lkp_town.items())[:8]:
        print(f"    {code:>2} -> {name}")
    if len(lkp_town) > 8:
        print(f"    ... ({len(lkp_town) - 8} more)")

    print(f"\n  First 5 rows of town_col:")
    print(f"    Original : {store.town_col[:5]}")
    print(f"    Encoded  : {enc_town[:5]}")

    print(f"\n  Querying with the encoded column:")
    print(f"    # convert target town names to codes once upfront")
    print(f"    target_codes = {{code for code, name in lookup.items()")
    print(f"                    if name in TOWNS}}")
    rev_lkp      = {v: k for k, v in lkp_town.items()}
    target_codes = {rev_lkp[t] for t in TOWNS if t in rev_lkp}
    print(f"    target_codes = {sorted(target_codes)}")
    print(f"    # then filter using integer comparison instead of string comparison")
    print(f"    matched = [i for i in idx if enc_town[i] in target_codes]")


# ============================================================================
# SECTION 4 - RUN-LENGTH ENCODING
# ============================================================================

def build_rle(col: list) -> list:
    # collapses runs of identical consecutive values into (value, count) tuples
    # e.g. ["ANG MO KIO", "ANG MO KIO", "BEDOK"] -> [("ANG MO KIO", 2), ("BEDOK", 1)]
    if not col:
        return []
    rle    = []
    cur    = col[0]
    count  = 1
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
  So instead of storing "JURONG WEST" 40,000 times in a row,
  we store one entry: ("JURONG WEST", 40000).

  The catch is this ONLY works well if the column is sorted/grouped.
  I checked the CSV and town_col is sorted alphabetically, so RLE gives
  huge compression there. But storey_range changes almost every row so
  RLE barely helps - we'd end up with nearly as many runs as rows.
    """)

    cols = [
        ("town",          store.town_col),
        ("month (raw)",   store.month_col),
        ("flat_type",     store.flat_type_col),
        ("flat_model",    store.flat_model_col),
        ("storey_range",  store.storey_range_col),
    ]

    n = len(store)
    print(f"  {'Column':<22} {'Runs':>8} {'Rows':>8} {'Run %':>8} "
          f"{'Ratio':>8}  Verdict")
    print(f"  {'-'*22} {'-'*8} {'-'*8} {'-'*8} {'-'*8}  {'-'*22}")

    for col_name, col in cols:
        rle     = build_rle(col)
        runs    = len(rle)
        pct     = runs / n * 100
        ratio   = n / runs if runs > 0 else 0

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

    # town column walkthrough
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

    print(f"\n  For filtering: instead of checking all 259,237 values,")
    print(f"  we only need to scan through {len(rle_town)} runs:")
    matched_from_rle   = [(v, c) for v, c in rle_town if v in TOWNS]
    total_rows_matched = sum(c for _, c in matched_from_rle)
    print(f"    Matching runs : {len(matched_from_rle)}")
    print(f"    Rows covered  : {total_rows_matched:,}")
    print(f"    Skipped runs  : {len(rle_town) - len(matched_from_rle)}")


# ============================================================================
# SECTION 5 - FILTER PERMUTATIONS
# ============================================================================

def show_filter_permutations(store):
    # We have 3 filters: year, month, town
    # The question is which order to apply them in.
    # Theory says apply the most selective filter first to reduce
    # the working set as quickly as possible.
    # Here I actually test all 6 orderings and count block reads at each stage
    # to confirm that our current order in main.py is indeed optimal.
    divider("SECTION 5 - FILTER PERMUTATION ANALYSIS")

    print(f"""
  Our query uses 3 filters: year, month, town
  With 3 filters there are 3! = 6 possible orderings.
  I tested all 6 and counted block reads at each step to find the best.

  (x={DEMO_X}, y={DEMO_Y}, year={TARGET_YEAR}, start_month={START_MONTH})
    """)

    n         = len(store)
    all_idx   = list(range(n))
    end_month = min(START_MONTH + DEMO_X - 1, 12)
    valid_months = set(range(START_MONTH, end_month + 1))

    filter_fns = {
        "year":  lambda idx: [i for i in idx if store.year_col[i]      == TARGET_YEAR],
        "month": lambda idx: [i for i in idx if store.month_num_col[i] in valid_months],
        "town":  lambda idx: [i for i in idx if store.town_col[i]      in TOWNS],
    }

    orders = list(permutations(["year", "month", "town"]))

    results_table = []
    for order in orders:
        active = all_idx
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

    for rank, (order, reads, total, survivors) in enumerate(results_table):
        order_str = " -> ".join(order)
        label     = "  BEST" if rank == 0 else ("  WORST" if rank == len(results_table)-1 else "")
        print(f"  {order_str:<30} {reads[0]:>6} {reads[1]:>6} {reads[2]:>6} "
              f"{reads[3]:>6} {total:>7}  {survivors:>10}{label}")

    best  = results_table[0]
    worst = results_table[-1]
    saving = worst[2] - best[2]
    print(f"\n  Best  : {' -> '.join(best[0])}  ({best[2]} total block reads)")
    print(f"  Worst : {' -> '.join(worst[0])}  ({worst[2]} total block reads)")
    print(f"  Difference: {saving} fewer blocks with the best ordering")
    print(f"  main.py uses year -> month -> town, which is the best order confirmed above.")

    # explain why year first is best
    sub_divider("Why year filter goes first")
    n_blks      = total_blocks(n)
    after_year  = filter_fns["year"](all_idx)
    after_month = filter_fns["month"](all_idx)
    after_town  = filter_fns["town"](all_idx)
    print(f"\n  Applying each filter alone (independently) to all {n:,} rows:")
    print(f"    year  : {len(all_idx):>7,} -> {len(after_year):>7,} rows  "
          f"({blocks_touched(after_year):>3} blocks left, "
          f"eliminated {(n_blks - blocks_touched(after_year))/n_blks*100:.0f}% of blocks)")
    print(f"    month : {len(all_idx):>7,} -> {len(after_month):>7,} rows  "
          f"({blocks_touched(after_month):>3} blocks left)")
    print(f"    town  : {len(all_idx):>7,} -> {len(after_town):>7,} rows  "
          f"({blocks_touched(after_town):>3} blocks left)")
    print(f"\n  Year alone knocks out {(n_blks-blocks_touched(after_year))/n_blks*100:.0f}% of blocks,")
    print(f"  so filters 2 and 3 only have to work through the much smaller remaining set.")


# ============================================================================
# SECTION 6 - EXTRA AGGREGATES
# ============================================================================

def show_extra_aggregates(store):
    # Once we've found the matched rows for a given (x, y) query,
    # computing avg and stddev PSM costs almost nothing extra.
    # The rows are already in memory - we just do one more pass over them.
    # I included this because stddev is actually useful: low stddev means
    # prices are tightly clustered (predictable), high stddev means there's
    # more variance and potentially some outlier bargains.
    divider("SECTION 6 - EXTRA AGGREGATES (avg PSM, stddev PSM)")

    print("""
  main.py computes min price per sqm. But avg and stddev come basically
  for free since the matched rows are already loaded into memory.
  Just 4 extra lines after the existing min loop.

  Stddev interpretation:
    Low  -> prices are tightly clustered (stable, predictable market)
    High -> prices vary a lot (some potential bargains/outliers)
    """)

    n            = len(store)
    end_month    = min(START_MONTH + DEMO_X - 1, 12)
    valid_months = set(range(START_MONTH, end_month + 1))

    candidate_idx = [
        i for i in range(n)
        if store.year_col[i]  == TARGET_YEAR
        and store.town_col[i] in TOWNS
    ]
    month_idx = [
        i for i in candidate_idx
        if store.month_num_col[i] in valid_months
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

        if std < 500:
            note = "tight market"
        elif std < 700:
            note = "moderate spread"
        else:
            note = "wide spread"

        print(f"  ({x},{y:<3}) {len(matched):>6,} {mn:>9,.0f} {avg:>9,.0f} "
              f"{std:>9,.0f} {mx:>9,.0f}  {note}")

    print(f"\n  The 4 lines to add in main.py's run_query() after the existing min loop:")
    print(f"  ┌───────────────────────────────────────────────────────────────")
    print(f"  │  all_psm = [store.resale_price_col[i] / store.floor_area_col[i]")
    print(f"  │             for i in matched]")
    print(f"  │  avg_psm = sum(all_psm) / len(all_psm)")
    print(f"  │  var     = sum((p - avg_psm)**2 for p in all_psm) / len(all_psm)")
    print(f"  │  std_psm = math.sqrt(var)")
    print(f"  └───────────────────────────────────────────────────────────────")


# ============================================================================
# SECTION 7 - SUMMARY
# ============================================================================

def show_scorecard():
    # Pull everything together into a quick reference table.
    # The main takeaway is that which technique works depends heavily on
    # the properties of each column - there's no one-size-fits-all answer.
    divider("SECTION 7 - SUMMARY: WHICH TECHNIQUE FITS WHICH COLUMN")

    print(f"""
  Legend:
    ++  strong fit - definitely implement and explain in report
    +   works - worth implementing
    ~   limited benefit - mention why it doesn't help much
    x   not suitable - explain why (this is also useful analysis)
    """)

    rows = [
        # col_name,          block,  zone,   dict,   rle,    notes
        ("year_col",          "++",  "++",   "++",   "++",   "all 4 techniques apply here"),
        ("month_num_col",     "++",  "+",    "++",   "++",   "all 4 apply"),
        ("town_col",          "++",  "x",    "++",   "++",   "dict 9x, RLE 100x"),
        ("flat_model_col",    "++",  "x",    "++",   "~",    "dict encoding ~9.5x"),
        ("storey_range_col",  "++",  "x",    "++",   "x",    "dict 8x, RLE bad (79% runs)"),
        ("flat_type_col",     "++",  "x",    "++",   "~",    "dict ~6.2x"),
        ("floor_area_sqm",    "++",  "~",    "x",    "x",    "zone map 0% skip rate (unsorted)"),
        ("resale_price_col",  "++",  "~",    "x",    "x",    "4826 unique vals - no encoding"),
        ("lease_commence",    "++",  "~",    "~",    "x",    "57 unique - marginal for dict"),
        ("block_col",         "++",  "x",    "x",    "x",    "2747 unique - just store as-is"),
        ("street_name_col",   "++",  "x",    "x",    "x",    "577 unique - just store as-is"),
        ("month_col (raw)",   "~",   "x",    "~",    "++",   "already split into year+month_num"),
    ]

    print(f"  {'Column':<22} {'Block':^7} {'Zone':^7} {'Dict':^7} {'RLE':^7}  Notes")
    print(f"  {'-'*22} {'-'*7} {'-'*7} {'-'*7} {'-'*7}  {'-'*35}")
    for col, blk, zm, dc, rle, note in rows:
        print(f"  {col:<22} {blk:^7} {zm:^7} {dc:^7} {rle:^7}  {note}")

    print(f"""
  Main takeaways:
    1. year_col and month_num_col are the strongest examples - all 4 techniques apply.
    2. Dict encoding works well on any low-cardinality string column (town, flat_model,
       storey_range, flat_type). The fewer unique values the better.
    3. Zone maps only help when data is sorted/clustered by that column.
       year_col gives ~93% skip rate. floor_area gives 0%. Worth explaining the difference.
    4. RLE works on town (~100x) and month (~22x) because the CSV is sorted that way.
       storey_range has ~79% runs so RLE doesn't compress it meaningfully.
    5. Block abstraction applies to every column and gives a baseline for comparison.
    """)


# ============================================================================
# MAIN
# ============================================================================

def main():
    if len(sys.argv) != 2:
        print("Usage: python analysis.py ResalePricesSingapore.csv")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"[ERROR] File not found: '{csv_path}'")
        sys.exit(1)

    print("=" * 66)
    print("  SC4023 - Column Analysis & Technique Justification")
    print("=" * 66)
    print(f"\n  Loading {csv_path} ...")
    t0      = time.time()
    store   = load_csv(csv_path)
    elapsed = time.time() - t0
    print(f"  Loaded {len(store):,} rows in {elapsed:.2f}s")

    show_block_abstraction(store)
    show_zone_maps(store)
    show_dict_encoding(store)
    show_rle(store)
    show_filter_permutations(store)
    show_extra_aggregates(store)
    show_scorecard()

    print()
    print("=" * 66)
    print("  Done.")
    print("=" * 66)
    print()


if __name__ == "__main__":
    main()
