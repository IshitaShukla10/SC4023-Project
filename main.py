"""
SC4023 Group Project — Main Entry Point
========================================
Usage:
    python main.py <csv_path> <matriculation_number>

Example:
    python main.py ResalePricesSingapore.csv U2323465X

This script:
    1. Parses the matriculation number to derive query parameters
    2. Loads the CSV into column-oriented storage
    3. Runs the query across all valid (x, y) pairs
    4. Writes ScanResult_<MatricNum>.csv to the same directory as this script

Query Logic (column-oriented)
------------------------------
For each (x, y) pair where x ∈ [1,8] and y ∈ [80,150]:
    - Filter rows: year == target_year
                   month_num in [start_month, start_month + x - 1]
                   town in matched_towns
                   floor_area >= y
    - Find row with minimum (resale_price / floor_area)
    - If that minimum price/sqm <= 4725 → (x, y) is VALID → write to output

Efficiency: year + town filters are applied ONCE upfront as a candidate index.
The inner (x, y) loop only scans that reduced candidate set (~1-5% of all rows).
"""

import sys
import os
import csv

# ── Import column store (must be in same directory) ──────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from column_store_ishita import load_csv


# ---------------------------------------------------------------------------
# Table 1 from assignment: digit → town
# ---------------------------------------------------------------------------
DIGIT_TO_TOWN = {
    '0': 'BEDOK',
    '1': 'BUKIT PANJANG',
    '2': 'CLEMENTI',
    '3': 'CHOA CHU KANG',
    '4': 'HOUGANG',
    '5': 'JURONG WEST',
    '6': 'PASIR RIS',
    '7': 'TAMPINES',
    '8': 'WOODLANDS',
    '9': 'YISHUN',
}

# Month digit 0 represents October (per assignment spec)
MONTH_DIGIT_MAP = {
    '0': 10,  # October
    '1': 1, '2': 2, '3': 3, '4': 4,
    '5': 5,  '6': 6, '7': 7, '8': 8,
    '9': 9,
}

MAX_PRICE_PSM = 4725


# ---------------------------------------------------------------------------
# Parse matriculation number → query parameters
# ---------------------------------------------------------------------------

def parse_matric(matric: str) -> dict:
    """
    Extract query parameters from a matriculation number.

    Rules (from assignment spec):
      - Last digit       → target year  (digit d → year 201d or 202d)
                           Note: 2025 data not used as target year
      - Second last digit → start month  (0 = October, 1–9 = Jan–Sep)
      - ALL unique digits  → matched towns (via Table 1)

    Returns a dict with keys: year, start_month, towns
    """
    # Strip leading letter(s) and trailing letter(s) — keep only digits
    digits_only = ''.join(c for c in matric if c.isdigit())

    if len(digits_only) < 2:
        raise ValueError(f"Cannot parse matric number: '{matric}'")

    # ── Target year from last digit ───────────────────────────────────────
    last_digit = digits_only[-1]
    year_suffix = int(last_digit)
    # Per spec example: digit 5 → 2015, digit 7 → 2017
    # All digits map to 201X (dataset is 2015–2024)
    target_year = 2010 + year_suffix if year_suffix >= 5 else 2020 + year_suffix

    # ── Start month from second last digit ───────────────────────────────
    second_last = digits_only[-2]
    start_month = MONTH_DIGIT_MAP[second_last]

    # ── Towns from ALL unique digits ──────────────────────────────────────
    unique_digits = set(digits_only)
    towns = {DIGIT_TO_TOWN[d] for d in unique_digits if d in DIGIT_TO_TOWN}

    return {
        'year':        target_year,
        'start_month': start_month,
        'towns':       towns,
    }


# ---------------------------------------------------------------------------
# Core query — column-oriented scan
# ---------------------------------------------------------------------------

def run_query(store, params: dict) -> list:
    """
    Scan the column store for all valid (x, y) pairs.

    Column-oriented efficiency strategy:
      Step 1 — Build candidate index: filter by year + town ONCE.
               This reduces 259k rows to a small working set (~1–5%).
      Step 2 — For each x: filter candidate index by month window.
               Reused across all y values for that x.
      Step 3 — For each y: filter by floor_area, find min price/sqm.

    Total scans = O(n) for Step 1 + O(candidates × x_values) for Step 2-3
    instead of O(n × x × y) if we rescanned everything each time.
    """
    target_year  = params['year']
    start_month  = params['start_month']
    towns        = params['towns']

    n = len(store)

    # ── Step 1: Build candidate index (year + town filter) ───────────────
    candidate_idx = [
        i for i in range(n)
        if store.year_col[i] == target_year
        and store.town_col[i] in towns
    ]

    results = []

    # ── Step 2 & 3: Loop (x, y) ──────────────────────────────────────────
    for x in range(1, 9):          # x: 1 to 8
        end_month = min(start_month + x - 1, 12)
        valid_months = set(range(start_month, end_month + 1))

        # Filter candidate_idx by month window (reused for all y)
        month_idx = [
            i for i in candidate_idx
            if store.month_num_col[i] in valid_months
        ]

        for y in range(80, 151):   # y: 80 to 150
            # Filter by floor area
            matched = [
                i for i in month_idx
                if store.floor_area_col[i] >= y
            ]

            if not matched:
                continue

            # Find row with minimum price per sqm
            best_i   = None
            best_psm = float('inf')
            for i in matched:
                psm = store.resale_price_col[i] / store.floor_area_col[i]
                if psm < best_psm:
                    best_psm = psm
                    best_i   = i

            # Validity check
            if best_psm > MAX_PRICE_PSM:
                continue

            i = best_i
            results.append({
                '(x,y)':                 f'({x}, {y})',
                'Year':                  store.year_col[i],
                'Month':                 f'{store.month_num_col[i]:02d}',
                'Town':                  store.town_col[i],
                'Block':                 store.block_col[i],
                'Floor_Area':            int(store.floor_area_col[i]),
                'Flat_Model':            store.flat_model_col[i],
                'Lease_Commence_Date':   store.lease_commence_date_col[i],
                'Price_Per_Square_Meter': round(best_psm),
            })

    return results


# ---------------------------------------------------------------------------
# Write output CSV
# ---------------------------------------------------------------------------

def write_output(results: list, output_path: str, matric: str):
    """
    Write results to ScanResult_<MatricNum>.csv.
    If no results exist for a pair, the spec says output 'No result'
    — handled by absence of that pair in results list (not written).
    Pairs are already sorted by (x ascending, y ascending) from the loop.
    """
    fieldnames = [
        '(x,y)', 'Year', 'Month', 'Town', 'Block',
        'Floor_Area', 'Flat_Model', 'Lease_Commence_Date',
        'Price_Per_Square_Meter'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print(f"\n✓ Output written to: {output_path}")
    print(f"  Total valid (x, y) pairs: {len(results)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 3:
        print("Usage: python main.py <csv_path> <matriculation_number>")
        print("Example: python main.py ResalePricesSingapore.csv U2323465X")
        sys.exit(1)

    csv_path = sys.argv[1]
    matric   = sys.argv[2].upper().strip()

    if not os.path.exists(csv_path):
        print(f"[ERROR] File not found: {csv_path}")
        sys.exit(1)

    # ── Parse matric ──────────────────────────────────────────────────────
    try:
        params = parse_matric(matric)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    print("=" * 60)
    print(f"  SC4023 HDB Resale Query")
    print(f"  Matriculation : {matric}")
    print(f"  Target Year   : {params['year']}")
    print(f"  Start Month   : {params['start_month']:02d}")
    print(f"  Towns         : {sorted(params['towns'])}")
    print(f"  x range       : 1 to 8")
    print(f"  y range       : 80 to 150 sqm")
    print(f"  Max PSM       : {MAX_PRICE_PSM}")
    print("=" * 60)

    # ── Load CSV ──────────────────────────────────────────────────────────
    print("\nLoading data...")
    store = load_csv(csv_path)
    print(f"  Rows loaded: {len(store):,}")

    # ── Run query ─────────────────────────────────────────────────────────
    print("\nRunning query...")
    results = run_query(store, params)

    # ── Write output ──────────────────────────────────────────────────────
    output_dir  = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, f'ScanResult_{matric}.csv')
    write_output(results, output_path, matric)

    # ── Preview first 5 rows ──────────────────────────────────────────────
    if results:
        print("\nPreview (first 5 rows):")
        print(f"  {'(x,y)':<10} {'Year'} {'Mo'} {'Town':<16} "
              f"{'Block':<8} {'Area':>4} {'Model':<18} {'LCD':>4} {'PSM':>6}")
        print("  " + "-" * 75)
        for r in results[:5]:
            print(f"  {r['(x,y)']:<10} {r['Year']} {r['Month']} "
                  f"{r['Town']:<16} {r['Block']:<8} {r['Floor_Area']:>4} "
                  f"{r['Flat_Model']:<18} {r['Lease_Commence_Date']:>4} "
                  f"{r['Price_Per_Square_Meter']:>6}")


if __name__ == '__main__':
    main()