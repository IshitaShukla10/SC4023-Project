# SC4023 Group Project — Analysis Entry Point
#
# Justifies which compression/storage techniques make sense for the dataset
# using measurements from the actual CSV rather than theory alone.
#
# Run:
#   python analysis.py ResalePricesSingapore.csv
#
# Sections:
#   1. Block Abstraction      (analysis/blocks.py)
#   2. Zone Maps              (analysis/zone_maps.py)
#   3. Dictionary Encoding    (analysis/dict_encoding.py)
#   4. Run-Length Encoding    (analysis/rle.py)
#   5. Filter Permutations    (analysis/filter_perms.py)
#   6. Extra Aggregates       (analysis/aggregates.py)
#   7. Scorecard              (analysis/scorecard.py)

import sys
import os
import time

from store import load_csv
from analysis import (
    show_block_abstraction,
    show_zone_maps,
    show_dict_encoding,
    show_rle,
    show_filter_permutations,
    show_extra_aggregates,
    show_scorecard,
)


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
