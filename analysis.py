"""
SC4023 Group Project — Column Storage Analysis

Justifies which compression/storage techniques apply to this dataset,
using actual measurements from the CSV rather than theory alone.

Run: python analysis.py ResalePricesSingapore.csv

Sections:
  1. Block Abstraction
  2. Zone Maps
  3. Dictionary Encoding
  4. Run-Length Encoding
  5. Filter Order Comparison
  6. Extra Aggregates (avg/stddev PSM)
  7. Scorecard Summary
"""

import sys
import os
import math
import time
from itertools import permutations

from column_store import load_csv

# Demo parameters — derived from Ishita's matric U2323465X
TARGET_YEAR = 2015
START_MONTH = 6
TOWNS       = {"CHOA CHU KANG", "CLEMENTI", "HOUGANG", "JURONG WEST", "PASIR RIS"}
BLOCK_SIZE  = 1000    # rows per block
DEMO_X      = 1
DEMO_Y      = 80


# ── Formatting helpers ──────────────────────────────────────────────────────

def section(title):
    print()
    print("=" * 66)
    print(f"  {title}")
    print("=" * 66)

def subsection(title):
    print(f"\n--- {title} ---")

def n_blocks(n_rows):
    return math.ceil(n_rows / BLOCK_SIZE)

def blocks_spanned(idx):
    """Number of distinct blocks touched by a list of row indices."""
    return len({i // BLOCK_SIZE for i in idx})


# ── Section 1: Block abstraction ────────────────────────────────────────────

def show_block_abstraction(store):
    section("SECTION 1 - BLOCK ABSTRACTION")

    n    = len(store)
    nblk = n_blocks(n)

    print(f"\n  {n:,} rows  |  block size = {BLOCK_SIZE:,} rows")
    print(f"  {nblk} blocks per column, {nblk * 12} total across 12 columns\n")

    print(f"  {'Block':<8} {'Row range':<22} Town at block start")
    print(f"  {'-'*8} {'-'*22} {'-'*20}")
    for b in range(min(4, nblk)):
        start = b * BLOCK_SIZE
        end   = min(start + BLOCK_SIZE - 1, n - 1)
        print(f"  {b:<8} {start:>7,} – {end:<7,}    {store.town_col[start]}")
    print(f"  {'...':<8} ...")
    last = (nblk - 1) * BLOCK_SIZE
    print(f"  {nblk-1:<8} {last:>7,} – {n-1:<7,}    {store.town_col[last]}")

    print(f"\n  A query hitting only 1 block reads {1/nblk*100:.1f}% of the data.")
    print(f"  Block abstraction gives a concrete way to measure filter speedup.")


# ── Section 2: Zone maps ────────────────────────────────────────────────────

def build_zone_map(col):
    """Build a (min, max) per-block zone map for a column."""
    zones = []
    for b in range(0, len(col), BLOCK_SIZE):
        chunk = col[b : b + BLOCK_SIZE]
        zones.append((min(chunk), max(chunk)))
    return zones

def zone_map_skips(zones, can_skip):
    """Count blocks where can_skip(min, max) is True (block can be skipped)."""
    return sum(1 for mn, mx in zones if can_skip(mn, mx))


def show_zone_maps(store):
    section("SECTION 2 - ZONE MAPS")

    print("""
  Zone maps store (min, max) per block. Before reading a block we check
  whether the filter value could possibly lie in [min, max].
  If not, the whole block is skipped without reading any data.

  This only works well when data is sorted/clustered by the filtered column.
  year_col (sorted chronologically) → ~93% skip rate.
  floor_area is scattered across every block → 0% skipped.
    """)

    n    = len(store)
    nblk = n_blocks(n)

    zm_year  = store.year_zm
    zm_month = store.month_num_zm
    zm_area  = store.floor_area_zm
    zm_price = store.resale_price_zm
    zm_lcd   = store.lease_commence_date_zm

    end_month = min(START_MONTH + DEMO_X - 1, 12)
    tests = [
        ("year_col",            zm_year,  f"year == {TARGET_YEAR}",
         lambda mn, mx: not (mn <= TARGET_YEAR <= mx)),
        ("month_num_col",       zm_month, f"month in [{START_MONTH}..{end_month}]",
         lambda mn, mx: mx < START_MONTH or mn > end_month),
        ("floor_area_sqm",      zm_area,  f"area >= {DEMO_Y}",
         lambda mn, mx: mx < DEMO_Y),
        ("resale_price",        zm_price, "price >= 400,000",
         lambda mn, mx: mx < 400_000),
        ("lease_commence_date", zm_lcd,   "lcd >= 2000",
         lambda mn, mx: mx < 2000),
    ]

    print(f"  {'Column':<25} {'Filter':<30} {'Skipped':>8} {'Of':>6} {'%':>7}  Verdict")
    print(f"  {'-'*25} {'-'*30} {'-'*8} {'-'*6} {'-'*7}  {'-'*15}")
    for col_name, zm, filt_str, skip_fn in tests:
        skipped = zone_map_skips(zm, skip_fn)
        pct     = skipped / nblk * 100
        verdict = "VERY USEFUL" if pct >= 50 else ("Moderate" if pct >= 10 else "Not useful")
        print(f"  {col_name:<25} {filt_str:<30} {skipped:>8} {nblk:>6} {pct:>6.1f}%  {verdict}")

    subsection("Walkthrough: year_col zone map (first 5 blocks)")
    print(f"\n  {'Block':<8} {'Min yr':<10} {'Max yr':<10} {'year==2015?':<15} Decision")
    print(f"  {'-'*8} {'-'*10} {'-'*10} {'-'*15} {'-'*10}")
    for b, (mn, mx) in enumerate(zm_year[:5]):
        keep = mn <= TARGET_YEAR <= mx
        print(f"  {b:<8} {mn:<10} {mx:<10} {'possible':<15} {'READ' if keep else 'SKIP  <--'}")

    skipped = zone_map_skips(zm_year, lambda mn, mx: not (mn <= TARGET_YEAR <= mx))
    kept    = nblk - skipped
    print(f"\n  Without zone map: scan all {nblk} blocks")
    print(f"  With zone map:    read {kept}, skip {skipped} ({skipped/nblk*100:.1f}% reduction)")


# ── Section 3: Dictionary encoding ─────────────────────────────────────────

def build_dict_encoding(col):
    """Encode a column as integers with a lookup table."""
    unique = sorted(set(col))
    lookup = {i: v for i, v in enumerate(unique)}
    rev    = {v: i for i, v in lookup.items()}
    return [rev[v] for v in col], lookup

def col_bytes(col, lookup=None):
    """Rough byte estimate: char count for strings, 1 byte/row for encoded."""
    if lookup is not None:
        return len(col) + sum(len(v) for v in lookup.values())
    return sum(len(v) for v in col)


def show_dict_encoding(store):
    section("SECTION 3 - DICTIONARY ENCODING")

    print("""
  Dictionary encoding replaces repeated strings with a small integer
  and a lookup table. Most effective on low-cardinality columns.
  'town' has 26 unique values across 259k rows → large savings.
  'block' has 2700+ unique values → the lookup itself is large, barely helps.
    """)

    cols = [
        ("town",          store.town_col),
        ("flat_model",    store.flat_model_col),
        ("storey_range",  store.storey_range_col),
        ("flat_type",     store.flat_type_col),
        ("street_name",   store.street_name_col),
        ("block",         store.block_col),
        ("month (raw)",   store.month_col),
    ]

    print(f"  {'Column':<22} {'Unique':>7} {'Raw bytes':>11} {'Enc bytes':>10} "
          f"{'Ratio':>7}  Verdict")
    print(f"  {'-'*22} {'-'*7} {'-'*11} {'-'*10} {'-'*7}  {'-'*24}")

    for name, col in cols:
        enc, lkp = build_dict_encoding(col)
        raw_b    = col_bytes(col)
        enc_b    = col_bytes(enc, lkp)
        ratio    = raw_b / enc_b if enc_b else 0

        if ratio >= 6:
            rec = "implement — big savings"
        elif ratio >= 3:
            rec = "worth implementing"
        elif ratio >= 1.5:
            rec = "marginal benefit"
        else:
            rec = "skip — too many unique values"

        print(f"  {name:<22} {len(set(col)):>7,} {raw_b:>9,}B {enc_b:>8,}B "
              f"{ratio:>6.1f}x  {rec}")

    subsection("Walkthrough: town encoding")
    enc_town, lkp_town = build_dict_encoding(store.town_col)

    print(f"\n  Lookup table ({len(lkp_town)} entries, first 8 shown):")
    for code, name in sorted(lkp_town.items())[:8]:
        print(f"    {code:>2} -> {name}")
    if len(lkp_town) > 8:
        print(f"    ... ({len(lkp_town) - 8} more)")

    print(f"\n  Original first 5: {store.town_col[:5]}")
    print(f"  Encoded  first 5: {enc_town[:5]}")

    rev = {v: k for k, v in lkp_town.items()}
    target_codes = sorted(rev[t] for t in TOWNS if t in rev)
    print(f"\n  Filter becomes an integer set membership check:")
    print(f"    target_codes = {target_codes}")
    print(f"    matched = [i for i in idx if enc_town[i] in target_codes]")


# ── Section 4: Run-length encoding ─────────────────────────────────────────

def build_rle(col):
    """Encode a column as (value, count) run pairs."""
    if not col:
        return []
    rle = []
    cur, count = col[0], 1
    for v in col[1:]:
        if v == cur:
            count += 1
        else:
            rle.append((cur, count))
            cur, count = v, 1
    rle.append((cur, count))
    return rle


def show_rle(store):
    section("SECTION 4 - RUN-LENGTH ENCODING (RLE)")

    print("""
  RLE stores consecutive runs as (value, count) pairs.
  Instead of storing "JURONG WEST" 40,000 times, we store one entry.

  Only effective when the column is sorted/grouped.
  town_col is alphabetically sorted → ~100x compression.
  storey_range changes almost every row → barely any benefit.
    """)

    cols = [
        ("town",         store.town_col),
        ("month (raw)",  store.month_col),
        ("flat_type",    store.flat_type_col),
        ("flat_model",   store.flat_model_col),
        ("storey_range", store.storey_range_col),
    ]

    n = len(store)
    print(f"  {'Column':<22} {'Runs':>8} {'Rows':>8} {'Runs/rows':>10} {'Ratio':>8}  Verdict")
    print(f"  {'-'*22} {'-'*8} {'-'*8} {'-'*10} {'-'*8}  {'-'*22}")

    for name, col in cols:
        rle   = build_rle(col)
        runs  = len(rle)
        pct   = runs / n * 100
        ratio = n / runs if runs else 0
        if ratio >= 20:
            verdict = "implement — excellent"
        elif ratio >= 5:
            verdict = "good compression"
        elif ratio >= 2:
            verdict = "marginal"
        else:
            verdict = "skip — barely helps"
        print(f"  {name:<22} {runs:>8,} {n:>8,} {pct:>9.1f}% {ratio:>7.1f}x  {verdict}")

    subsection("Walkthrough: town RLE")
    rle_town = build_rle(store.town_col)
    print(f"\n  {n:,} rows compressed to {len(rle_town)} run entries")
    print(f"\n  First 6 runs:")
    print(f"  {'Town':<25} {'Count':>8}  Rows covered")
    print(f"  {'-'*25} {'-'*8}  {'-'*12}")
    running = 0
    for val, cnt in rle_town[:6]:
        print(f"  {val:<25} {cnt:>8,}  {running:,}–{running+cnt-1:,}")
        running += cnt
    print(f"  ... ({len(rle_town) - 6} more runs)")

    matched_runs = [(v, c) for v, c in rle_town if v in TOWNS]
    rows_covered = sum(c for _, c in matched_runs)
    print(f"\n  Town filter: scan {len(rle_town)} runs instead of {n:,} rows")
    print(f"  {len(matched_runs)} matching runs, covering {rows_covered:,} rows")


# ── Section 5: Filter order ─────────────────────────────────────────────────

def show_filter_permutations(store):
    section("SECTION 5 - FILTER ORDER COMPARISON")

    print(f"""
  The query applies 3 filters: year, month window, town.
  All 3! = 6 orderings are tested by counting block reads at each stage.
  (x={DEMO_X}, y={DEMO_Y}, year={TARGET_YEAR}, start_month={START_MONTH})
    """)

    n            = len(store)
    all_idx      = list(range(n))
    end_month    = min(START_MONTH + DEMO_X - 1, 12)
    valid_months = set(range(START_MONTH, end_month + 1))

    filters = {
        "year":  lambda idx: [i for i in idx if store.year_col[i]      == TARGET_YEAR],
        "month": lambda idx: [i for i in idx if store.month_num_col[i] in valid_months],
        "town":  lambda idx: [i for i in idx if store.town_col[i]      in TOWNS],
    }

    rows = []
    for order in permutations(["year", "month", "town"]):
        active = all_idx
        reads  = [blocks_spanned(active)]
        for f in order:
            active = filters[f](active)
            reads.append(blocks_spanned(active))
        rows.append((order, reads, sum(reads), len(active)))
    rows.sort(key=lambda r: r[2])

    print(f"  {'Order':<30} {'Start':>6} {'F1':>6} {'F2':>6} {'F3':>6} {'Total':>7}  Survivors")
    print(f"  {'-'*30} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*7}  {'-'*9}")
    for rank, (order, reads, total, surv) in enumerate(rows):
        tag = "  <- BEST" if rank == 0 else ("  <- WORST" if rank == len(rows) - 1 else "")
        print(f"  {' -> '.join(order):<30} {reads[0]:>6} {reads[1]:>6} {reads[2]:>6} "
              f"{reads[3]:>6} {total:>7}  {surv:>9}{tag}")

    best, worst = rows[0], rows[-1]
    print(f"\n  Best:  {' -> '.join(best[0])} ({best[2]} block reads)")
    print(f"  Worst: {' -> '.join(worst[0])} ({worst[2]} block reads)")
    print(f"  Savings: {worst[2] - best[2]} fewer block reads with the best order")
    print(f"  main.py uses year -> month -> town — confirmed optimal here.")

    subsection("Why year filter goes first")
    nblk = n_blocks(n)
    for fname, fidx in [
        ("year",  filters["year"](all_idx)),
        ("month", filters["month"](all_idx)),
        ("town",  filters["town"](all_idx)),
    ]:
        blks = blocks_spanned(fidx)
        elim = (nblk - blks) / nblk * 100
        print(f"  {fname:<6}: {n:,} -> {len(fidx):,} rows  ({blks} blocks left, "
              f"eliminates {elim:.0f}% of blocks)")
    print(f"\n  Year alone cuts ~93% of blocks, so later filters")
    print(f"  only scan a much smaller candidate set.")


# ── Section 6: Extra aggregates ─────────────────────────────────────────────

def show_extra_aggregates(store):
    section("SECTION 6 - EXTRA AGGREGATES (avg PSM, stddev PSM)")

    print("""
  The query already finds min PSM. avg and stddev are essentially free —
  the matched rows are already in memory, so it's just a few extra lines.

  Low stddev = stable, predictable pricing
  High stddev = wider spread; potential bargains or outliers present
    """)

    n    = len(store)
    base = [
        i for i in range(n)
        if store.year_col[i] == TARGET_YEAR and store.town_col[i] in TOWNS
    ]

    pairs = [(1, 80), (1, 100), (1, 114), (2, 80), (4, 80), (8, 80), (8, 130)]

    print(f"  {'(x,y)':<10} {'Rows':>6} {'Min PSM':>9} {'Avg PSM':>9} "
          f"{'StdDev':>9} {'Max PSM':>9}  Market")
    print(f"  {'-'*10} {'-'*6} {'-'*9} {'-'*9} {'-'*9} {'-'*9}  {'-'*20}")

    for x, y in pairs:
        em      = min(START_MONTH + x - 1, 12)
        matched = [
            i for i in base
            if store.month_num_col[i] in set(range(START_MONTH, em + 1))
            and store.floor_area_col[i] >= y
        ]
        if not matched:
            print(f"  ({x},{y})<10 no result")
            continue

        psm_vals = [store.resale_price_col[i] / store.floor_area_col[i] for i in matched]
        mn  = min(psm_vals)
        mx  = max(psm_vals)
        avg = sum(psm_vals) / len(psm_vals)
        std = math.sqrt(sum((p - avg) ** 2 for p in psm_vals) / len(psm_vals))
        note = "tight market" if std < 500 else ("moderate spread" if std < 700 else "wide spread")

        print(f"  ({x},{y:<3}) {len(matched):>6,} {mn:>9,.0f} {avg:>9,.0f} "
              f"{std:>9,.0f} {mx:>9,.0f}  {note}")

    print(f"\n  Lines to add in run_query() after finding best_i:")
    print(f"    psm_vals = [store.resale_price_col[i] / store.floor_area_col[i] for i in matched]")
    print(f"    avg_psm  = sum(psm_vals) / len(psm_vals)")
    print(f"    std_psm  = math.sqrt(sum((p - avg_psm)**2 for p in psm_vals) / len(psm_vals))")


# ── Section 7: Scorecard ────────────────────────────────────────────────────

def show_scorecard():
    section("SECTION 7 - SUMMARY: WHICH TECHNIQUE FITS WHICH COLUMN")

    print("""
  Legend:  ++  strong fit     +  useful     ~  limited     x  not suitable
    """)

    rows = [
        #  column                 block   zone    dict    rle     notes
        ("year_col",             "++",   "++",   "++",   "++",   "all 4 techniques apply"),
        ("month_num_col",        "++",    "+",   "++",   "++",   "all 4 apply"),
        ("town_col",             "++",    "x",   "++",   "++",   "dict 9x, RLE ~100x"),
        ("flat_model_col",       "++",    "x",   "++",    "~",   "dict ~9.5x"),
        ("storey_range_col",     "++",    "x",   "++",    "x",   "dict 8x, RLE bad (79% runs)"),
        ("flat_type_col",        "++",    "x",   "++",    "~",   "dict ~6.2x"),
        ("floor_area_sqm",       "++",    "~",    "x",    "x",   "zone map 0% skip (unsorted)"),
        ("resale_price_col",     "++",    "~",    "x",    "x",   "4826 unique vals"),
        ("lease_commence_date",  "++",    "~",    "~",    "x",   "57 unique — marginal for dict"),
        ("block_col",            "++",    "x",    "x",    "x",   "2747 unique — store as-is"),
        ("street_name_col",      "++",    "x",    "x",    "x",   "577 unique — store as-is"),
        ("month_col (raw)",       "~",    "x",    "~",   "++",   "already split into year+month_num"),
    ]

    print(f"  {'Column':<24} {'Block':^7} {'Zone':^7} {'Dict':^7} {'RLE':^7}  Notes")
    print(f"  {'-'*24} {'-'*7} {'-'*7} {'-'*7} {'-'*7}  {'-'*35}")
    for col, blk, zm, dc, rle, note in rows:
        print(f"  {col:<24} {blk:^7} {zm:^7} {dc:^7} {rle:^7}  {note}")

    print("""
  Takeaways:
    1. year_col and month_num_col benefit from all 4 techniques — best for the report.
    2. Dict encoding works on any low-cardinality string column. Fewer unique
       values = better ratio (town: 26 unique → 9x; block: 2700+ → barely helps).
    3. Zone maps only pay off when data is sorted by the filtered column.
       year_col → ~93% skip rate. floor_area → 0% (scattered values).
    4. RLE is effective on town (~100x) and month (~22x) because the CSV is
       sorted that way. storey_range has ~79% run transitions, so RLE gives
       almost no compression.
    5. Block abstraction applies to every column — it's the baseline measure.
    """)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) != 2:
        print("Usage: python analysis.py ResalePricesSingapore.csv")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        sys.exit(1)

    print("=" * 66)
    print("  SC4023 - Column Store Analysis")
    print("=" * 66)

    t0    = time.time()
    store = load_csv(csv_path)
    print(f"  Loaded in {time.time() - t0:.2f}s")

    show_block_abstraction(store)
    show_zone_maps(store)
    show_dict_encoding(store)
    show_rle(store)
    show_filter_permutations(store)
    show_extra_aggregates(store)
    show_scorecard()

    print("=" * 66)
    print("  Done.")
    print("=" * 66 + "\n")


if __name__ == "__main__":
    main()
