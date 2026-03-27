"""
SC4023 Analysis — Section 7: Scorecard Summary.

Quick-reference table showing which compression technique fits each
column and why.  The main takeaway: no one technique fits all columns;
which technique helps depends on the data distribution of each column.
"""

from .utils import divider


def show_scorecard():
    divider("SECTION 7 - SUMMARY: WHICH TECHNIQUE FITS WHICH COLUMN")

    print(f"""
  Legend:
    ++  strong fit — definitely implement and explain in report
    +   works — worth implementing
    ~   limited benefit — mention why it doesn't help much
    x   not suitable — explain why (also valuable analysis)
    """)

    rows = [
        # col_name              block  zone   dict   rle    notes
        ("year_col",            "++",  "++",  "++",  "++",  "all 4 techniques apply"),
        ("month_num_col",       "++",  "+",   "++",  "++",  "all 4 apply"),
        ("town_col",            "++",  "x",   "++",  "++",  "dict 9x, RLE 100x"),
        ("flat_model_col",      "++",  "x",   "++",  "~",   "dict encoding ~9.5x"),
        ("storey_range_col",    "++",  "x",   "++",  "x",   "dict 8x, RLE bad (79% runs)"),
        ("flat_type_col",       "++",  "x",   "++",  "~",   "dict ~6.2x"),
        ("floor_area_sqm",      "++",  "~",   "x",   "x",   "zone map 0% skip rate (unsorted)"),
        ("resale_price_col",    "++",  "~",   "x",   "x",   "4826 unique vals — no encoding"),
        ("lease_commence_date", "++",  "~",   "~",   "x",   "57 unique — marginal for dict"),
        ("block_col",           "++",  "x",   "x",   "x",   "2747 unique — just store as-is"),
        ("street_name_col",     "++",  "x",   "x",   "x",   "577 unique — just store as-is"),
        ("month_col (raw)",     "~",   "x",   "~",   "++",  "already split into year+month_num"),
    ]

    print(f"  {'Column':<24} {'Block':^7} {'Zone':^7} {'Dict':^7} {'RLE':^7}  Notes")
    print(f"  {'-'*24} {'-'*7} {'-'*7} {'-'*7} {'-'*7}  {'-'*35}")
    for col, blk, zm, dc, rle, note in rows:
        print(f"  {col:<24} {blk:^7} {zm:^7} {dc:^7} {rle:^7}  {note}")

    print(f"""
  Main takeaways:
    1. year_col and month_num_col are the strongest examples — all 4 techniques apply.
    2. Dict encoding works on any low-cardinality string column (town, flat_model,
       storey_range, flat_type).  The fewer unique values, the better.
    3. Zone maps only help when data is sorted/clustered by that column.
       year_col → ~93% skip rate.  floor_area → 0%.  Worth explaining the difference.
    4. RLE works on town (~100x) and month (~22x) because the CSV is sorted that way.
       storey_range has ~79% runs, so RLE doesn't compress it meaningfully.
    5. Block abstraction applies to every column and gives a baseline for comparison.
    """)
