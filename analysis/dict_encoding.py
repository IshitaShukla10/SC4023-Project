"""
SC4023 Analysis — Section 3: Dictionary Encoding.

Replaces repeated string values with a small integer code and a lookup
table.  Most effective on low-cardinality columns (few unique values).
town (26 unique) → 9x compression.  block (2747 unique) → barely helps.
"""

from .utils import divider, sub_divider
from .constants import TOWNS


def build_dict_encoding(col: list):
    """
    Encode a string column as integers with a lookup table.

    Returns
    -------
    encoded : list[int]   one integer per row
    lookup  : dict        {code: original_value}
    """
    unique_vals = sorted(set(col))
    lookup      = {i: v for i, v in enumerate(unique_vals)}
    reverse     = {v: i for i, v in lookup.items()}
    encoded     = [reverse[v] for v in col]
    return encoded, lookup


def estimate_bytes(col: list, is_encoded: bool, lookup: dict = None) -> int:
    """
    Rough byte estimate for a column.

    Original  : sum of character counts across all string values.
    Encoded   : 1 byte per row + total characters in the lookup table.
    (Python object overhead is excluded; this measures raw data size.)
    """
    if is_encoded:
        return len(col) * 1 + sum(len(v) for v in lookup.values())
    return sum(len(v) for v in col)


def show_dict_encoding(store):
    divider("SECTION 3 - DICTIONARY ENCODING")

    print("""
  Dictionary encoding swaps repeated strings for a small integer.
  We keep a lookup table (e.g. {0: "ANG MO KIO", 1: "BEDOK", ...})
  and store just the integer index per row.

  Most effective when a column has few unique values (low cardinality).
  'town' with only 26 unique values across 259k rows → huge savings.
  'block' with 2700+ unique values → encoding barely helps because the
  dictionary itself becomes large.
    """)

    string_cols = [
        ("town",          store.town_col),
        ("flat_model",    store.flat_model_col),
        ("storey_range",  store.storey_range_col),
        ("flat_type",     store.flat_type_col),
        ("street_name",   store.street_name_col),
        ("block",         store.block_col),
        ("month (raw)",   store.month_col),
    ]

    print(f"  {'Column':<22} {'Unique':>7} {'Original':>12} {'Encoded':>12} "
          f"{'Ratio':>8}  Recommendation")
    print(f"  {'-'*22} {'-'*7} {'-'*12} {'-'*12} {'-'*8}  {'-'*22}")

    for col_name, col in string_cols:
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

    rev_lkp      = {v: k for k, v in lkp_town.items()}
    target_codes = {rev_lkp[t] for t in TOWNS if t in rev_lkp}
    print(f"\n  Querying with the encoded column:")
    print(f"    # convert target town names to codes once upfront")
    print(f"    target_codes = {{code for code, name in lookup.items()")
    print(f"                    if name in TOWNS}}")
    print(f"    target_codes = {sorted(target_codes)}")
    print(f"    # then filter using integer comparison instead of string comparison")
    print(f"    matched = [i for i in idx if enc_town[i] in target_codes]")
