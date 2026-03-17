"""
SC4023 Group Project — Full Query Script
Matriculation: Ishita (digits: 2,3,2,3,4,6,5)

Query Parameters (derived from matric number)
----------------------------------------------
Target Year       : 2015        (last digit = 5 → 2015)
Starting Month    : June = 6    (second last digit = 6)
x range           : 1 to 8      (months window size, per assignment spec)
y range           : 80 to 150   (minimum floor area in sqm, step 1 each)
Towns             : CLEMENTI, CHOA CHU KANG, HOUGANG, JURONG WEST, PASIR RIS
                    (unique digits from matric: 2,3,4,5,6)
Valid pair (x,y)  : min price/sqm ≤ 4725

For each valid (x, y) pair:
    - Scan rows where:
        * year == 2015
        * month_num in [6, 6+x-1]   (x-month window starting June)
        * town in the 5 towns above
        * floor_area >= y
    - Compute price_per_sqm = resale_price / floor_area for each matched row
    - Find the row with the MINIMUM price_per_sqm
    - If that minimum ≤ 4725, the (x,y) pair is VALID → output it

Output file: ScanResult_Ishita.csv
"""

import sys
import os
import csv

# ── Import the column store from the module we already built ─────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from column_store_ishita import load_csv, ColumnStore


# ---------------------------------------------------------------------------
# Query Parameters — hardcoded from Ishita's matric number
# ---------------------------------------------------------------------------

TARGET_YEAR    = 2015
START_MONTH    = 6          # June
X_VALUES       = list(range(1, 9))          # 1 to 8 inclusive
Y_VALUES       = list(range(80, 151))       # 80 to 150 inclusive
MAX_PRICE_PSM  = 4725

TOWNS = {
    "CLEMENTI",
    "CHOA CHU KANG",
    "HOUGANG",
    "JURONG WEST",
    "PASIR RIS",
}

OUTPUT_FILE = "ScanResult_Ishita.csv"


# ---------------------------------------------------------------------------
# Query Engine
# ---------------------------------------------------------------------------

def run_query(store: ColumnStore, csv_output_path: str):
    """
    For every (x, y) combination, scan the column store and find the record
    with minimum price per square metre. Output all valid pairs to CSV.

    Strategy (column-oriented)
    --------------------------
    Step 1 — Pre-filter by YEAR once (build a boolean mask / index list).
              Year filter eliminates ~91% of rows immediately.
    Step 2 — From that subset, pre-filter by TOWN.
              Reduces to rows in our 5 towns only.
    Step 3 — For each (x, y) pair, scan only this smaller candidate pool:
              apply month window + floor_area filter, then find min price/sqm.

    This reuses the year+town filtered index across all 8×71 = 568 (x,y) pairs
    rather than rescanning all 259k rows each time.
    """

    n = len(store)

    # ── Step 1: Pre-filter by year ────────────────────────────────────────
    print(f"[1/3] Pre-filtering by year = {TARGET_YEAR} ...")
    year_indices = [
        i for i in range(n)
        if store.year_col[i] == TARGET_YEAR
    ]
    print(f"      → {len(year_indices):,} rows match year {TARGET_YEAR}")

    # ── Step 2: Pre-filter by town ────────────────────────────────────────
    print(f"[2/3] Pre-filtering by towns = {sorted(TOWNS)} ...")
    candidate_indices = [
        i for i in year_indices
        if store.town_col[i] in TOWNS
    ]
    print(f"      → {len(candidate_indices):,} rows match year + town")

    # ── Step 3: Loop over (x, y) pairs ───────────────────────────────────
    print(f"[3/3] Running {len(X_VALUES) * len(Y_VALUES)} (x, y) combinations ...")

    results = []  # list of dicts, one per valid (x, y)

    for x in X_VALUES:
        # Month window: START_MONTH to START_MONTH + x - 1 (capped at 12)
        end_month = min(START_MONTH + x - 1, 12)
        valid_months = set(range(START_MONTH, end_month + 1))

        # Pre-filter candidate_indices by this month window (reuse per y)
        month_indices = [
            i for i in candidate_indices
            if store.month_num_col[i] in valid_months
        ]

        for y in Y_VALUES:
            # Apply floor_area filter on top of month-filtered subset
            matched = [
                i for i in month_indices
                if store.floor_area_col[i] >= y
            ]

            if not matched:
                continue  # no data for this (x, y) — not valid

            # Find the row with minimum price per square metre
            best_idx = None
            best_psm = float('inf')

            for i in matched:
                psm = store.resale_price_col[i] / store.floor_area_col[i]
                if psm < best_psm:
                    best_psm = psm
                    best_idx = i

            # Check validity threshold
            if best_psm > MAX_PRICE_PSM:
                continue  # minimum psm still exceeds threshold — not valid

            # ── This (x, y) pair is VALID — record the result ────────────
            i = best_idx
            results.append({
                "x,y":                   f"({x}, {y})",
                "Year":                  store.year_col[i],
                "Month":                 f"{store.month_num_col[i]:02d}",
                "Town":                  store.town_col[i],
                "Block":                 store.block_col[i],
                "Floor_Area":            store.floor_area_col[i],
                "Flat_Model":            store.flat_model_col[i],
                "Lease_Commence_Date":   store.lease_commence_date_col[i],
                "Price_Per_Square_Meter": round(best_psm),
            })

    print(f"      → {len(results):,} valid (x, y) pairs found")

    # ── Write CSV ─────────────────────────────────────────────────────────
    fieldnames = [
        "(x,y)", "Year", "Month", "Town", "Block",
        "Floor_Area", "Flat_Model", "Lease_Commence_Date",
        "Price_Per_Square_Meter"
    ]

    with open(csv_output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            # rename key to match fieldname with parentheses
            row["(x,y)"] = row.pop("x,y")
            writer.writerow(row)

    print(f"\n[DONE] Results saved to: {csv_output_path}")
    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/ishitashukla/Desktop/SC4023-Project/ResalePricesSingapore.csv"

    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV not found: {csv_path}")
        sys.exit(1)

    print("=" * 65)
    print("  SC4023 — Ishita's Query")
    print(f"  Year={TARGET_YEAR}, Start Month={START_MONTH}, "
          f"x=[1..8], y=[80..150]")
    print(f"  Towns: {sorted(TOWNS)}")
    print("=" * 65)
    print()

    # Load data
    store = load_csv(csv_path)
    print()

    # Run query and write output
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_FILE)
    results = run_query(store, output_path)

    # Print first 10 rows as preview
    print()
    print("Preview (first 10 results):")
    header = f"{'(x,y)':<10} {'Year':<6} {'Mo':<4} {'Town':<16} {'Block':<8} {'Area':>6} {'Flat_Model':<18} {'LCD':>5} {'PSM':>6}"
    print(header)
    print("-" * len(header))
    for r in results[:10]:
        print(f"{r.get('(x,y)', r.get('x,y','')):<10} "
              f"{r['Year']:<6} "
              f"{r['Month']:<4} "
              f"{r['Town']:<16} "
              f"{r['Block']:<8} "
              f"{r['Floor_Area']:>6.0f} "
              f"{r['Flat_Model']:<18} "
              f"{r['Lease_Commence_Date']:>5} "
              f"{r['Price_Per_Square_Meter']:>6}")
