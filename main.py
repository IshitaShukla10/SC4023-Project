"""
SC4023 Group Project — Main Entry Point
========================================
Usage:
    python main.py <csv_path> <matriculation_number>

Examples:
    python main.py ResalePricesSingapore.csv U2323465X
    python main.py ResalePricesSingapore.csv A6626226B

What this script does:
    1. Parses the matriculation number to derive query parameters
       (target year, start month, matched towns)
    2. Loads ResalePricesSingapore.csv into column-oriented storage
    3. Runs the query across all (x, y) combinations
    4. Writes ScanResult_<MatricNum>.csv to the working directory
"""

import sys
import os

from store import load_csv
from query import parse_matric, run_query, write_output
from query.constants import X_MIN, X_MAX, Y_MIN, Y_MAX, MAX_PRICE_PSM


def main():
    if len(sys.argv) != 3:
        print("Usage  : python main.py <csv_path> <matriculation_number>")
        print("Example: python main.py ResalePricesSingapore.csv U2323465X")
        sys.exit(1)

    csv_path = sys.argv[1]
    matric   = sys.argv[2].strip().upper()

    if not os.path.exists(csv_path):
        print(f"[ERROR] File not found: '{csv_path}'")
        sys.exit(1)

    try:
        params = parse_matric(matric)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    print("=" * 62)
    print("  SC4023 — HDB Resale Minimum Price per Square Metre")
    print("=" * 62)
    print(f"  Matriculation : {matric}")
    print(f"  Target Year   : {params['year']}")
    print(f"  Start Month   : {params['start_month']:02d}")
    print(f"  Towns         : {sorted(params['towns'])}")
    print(f"  x range       : {X_MIN} to {X_MAX}  (months window)")
    print(f"  y range       : {Y_MIN} to {Y_MAX}  (min floor area sqm)")
    print(f"  Max PSM       : {MAX_PRICE_PSM}")
    print("=" * 62)

    print("\nStep 1 — Loading data into column store...")
    store = load_csv(csv_path)
    print(f"  {store}")

    print("\nStep 2 — Running query...")
    results = run_query(store, params)

    print("\nStep 3 — Writing output...")
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"ScanResult_{matric}.csv"
    )
    write_output(results, output_path)

    valid_rows = [r for r in results if r["Year"] != "No result"]
    if valid_rows:
        print("\nPreview (first 5 valid results):")
        print(f"  {'(x, y)':<10} {'Year'} {'Mo'} {'Town':<16} "
              f"{'Block':<8} {'Area':>4} {'Model':<18} {'LCD':>4} {'PSM':>6}")
        print("  " + "-" * 76)
        for r in valid_rows[:5]:
            print(f"  {r['(x, y)']:<10} {r['Year']} {r['Month']} "
                  f"{r['Town']:<16} {r['Block']:<8} {r['Floor_Area']:>4} "
                  f"{r['Flat_Model']:<18} {r['Lease_Commence_Date']:>4} "
                  f"{r['Price_Per_Square_Meter']:>6}")

    print("\nDone.")


if __name__ == "__main__":
    main()
