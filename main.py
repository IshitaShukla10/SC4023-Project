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

Query Definition
----------------
For each (x, y) pair where x in [1, 8] and y in [80, 150]:
    Filter rows where:
        year        == target_year
        month_num   in [start_month, start_month + x - 1]
        town        in matched_towns
        floor_area  >= y
    Find the row with minimum (resale_price / floor_area).
    If that minimum price/sqm <= 4725  ->  (x, y) is VALID.
    If no rows match at all            ->  output "No result".

Matriculation Number Parsing Rules (from assignment spec)
----------------------------------------------------------
    Last digit        -> target year  (5-9 -> 2015-2019, 0-4 -> 2020-2024)
    Second last digit -> start month  (0 = October, 1-9 = Jan-Sep)
    All unique digits -> matched towns (Table 1 from assignment)
"""

import sys
import os
import csv

# Import shared column store
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from column_store import load_csv


# ---------------------------------------------------------------------------
# Constants from assignment spec
# ---------------------------------------------------------------------------

# Table 1: digit -> town name
DIGIT_TO_TOWN = {
    "0": "BEDOK",
    "1": "BUKIT PANJANG",
    "2": "CLEMENTI",
    "3": "CHOA CHU KANG",
    "4": "HOUGANG",
    "5": "JURONG WEST",
    "6": "PASIR RIS",
    "7": "TAMPINES",
    "8": "WOODLANDS",
    "9": "YISHUN",
}

# Second-last digit -> start month (0 represents October per spec)
DIGIT_TO_MONTH = {
    "0": 10,
    "1": 1, "2": 2, "3": 3, "4": 4,
    "5": 5, "6": 6, "7": 7, "8": 8,
    "9": 9,
}

MAX_PRICE_PSM = 4725    # validity threshold
X_MIN, X_MAX  = 1, 8    # x range (months window)
Y_MIN, Y_MAX  = 80, 150 # y range (minimum floor area in sqm)


# ---------------------------------------------------------------------------
# Step 1: Parse matriculation number
# ---------------------------------------------------------------------------

def parse_matric(matric: str) -> dict:
    """
    Derive query parameters from a matriculation number.

    Parameters
    ----------
    matric : str  e.g. "U2323465X"

    Returns
    -------
    dict with keys:
        year        : int   target year
        start_month : int   starting month number (1-12)
        towns       : set   set of town name strings
    """
    digits = "".join(c for c in matric if c.isdigit())

    if len(digits) < 2:
        raise ValueError(
            f"Matriculation number '{matric}' must contain at least 2 digits."
        )

    # Target year from last digit (spec: digit 5 -> 2015, digit 7 -> 2017)
    last = int(digits[-1])
    target_year = 2010 + last if last >= 5 else 2020 + last

    # Start month from second-last digit
    start_month = DIGIT_TO_MONTH[digits[-2]]

    # Matched towns from ALL unique digits in the matric number
    towns = {DIGIT_TO_TOWN[d] for d in set(digits) if d in DIGIT_TO_TOWN}

    return {"year": target_year, "start_month": start_month, "towns": towns}


# ---------------------------------------------------------------------------
# Step 2: Query engine (column-oriented scan)
# ---------------------------------------------------------------------------

def run_query(store, params: dict) -> list:
    """
    Scan the column store for all (x, y) combinations and return results.

    Column-Oriented Efficiency Strategy
    ------------------------------------
    Rather than scanning all 259,237 rows for each of the 568 (x,y) pairs,
    we use a 3-step pre-filtering approach that reuses intermediate results:

    Step 1 - Build candidate index (done ONCE):
              Filter all rows by year AND town simultaneously.
              For Ishita's matric: 259,237 rows -> 4,227 candidates (~1.6%).
              This index list is reused for every (x, y) combination.

    Step 2 - Month window filter (done ONCE per x value, 8 times total):
              From the candidates, keep only rows whose month falls within
              [start_month, start_month + x - 1].
              This month-filtered index is reused for all 71 y values.

    Step 3 - Floor area filter + min PSM (done once per (x, y) pair):
              Drop rows with floor_area < y, then find minimum price/sqm.
              Apply validity threshold. Write "No result" if no data found
              or if minimum PSM exceeds 4725.

    Parameters
    ----------
    store  : ColumnStore
    params : dict  from parse_matric()

    Returns
    -------
    list of result dicts, one per (x, y) pair, sorted x then y
    """
    target_year = params["year"]
    start_month = params["start_month"]
    towns       = params["towns"]
    n           = len(store)

    # -- Step 1: Candidate index (year + town, computed once) --------------
    candidate_idx = [
        i for i in range(n)
        if store.year_col[i] == target_year
        and store.town_col[i] in towns
    ]

    results = []

    # -- Steps 2 & 3: Loop over all (x, y) pairs --------------------------
    for x in range(X_MIN, X_MAX + 1):

        # Month window: [start_month, start_month + x - 1], capped at Dec
        # Queries do not wrap into the following year
        end_month    = min(start_month + x - 1, 12)
        valid_months = set(range(start_month, end_month + 1))

        # Step 2: filter by month window (reused for all y at this x)
        month_idx = [
            i for i in candidate_idx
            if store.month_num_col[i] in valid_months
        ]

        for y in range(Y_MIN, Y_MAX + 1):

            # Step 3a: filter by minimum floor area
            matched = [
                i for i in month_idx
                if store.floor_area_col[i] >= y
            ]

            # No data at all for this (x, y) combination
            if not matched:
                results.append(_no_result_row(x, y))
                continue

            # Step 3b: find row with minimum price per square metre
            best_i   = None
            best_psm = float("inf")
            for i in matched:
                psm = store.resale_price_col[i] / store.floor_area_col[i]
                if psm < best_psm:
                    best_psm = psm
                    best_i   = i

            # PSM exceeds validity threshold
            if best_psm > MAX_PRICE_PSM:
                results.append(_no_result_row(x, y))
                continue

            # Valid pair - record the best matching record
            i = best_i
            results.append({
                "(x, y)":               f"({x}, {y})",
                "Year":                 store.year_col[i],
                "Month":                f"{store.month_num_col[i]:02d}",
                "Town":                 store.town_col[i],
                "Block":                store.block_col[i],
                "Floor_Area":           int(store.floor_area_col[i]),
                "Flat_Model":           store.flat_model_col[i],
                "Lease_Commence_Date":  store.lease_commence_date_col[i],
                "Price_Per_Square_Meter": round(best_psm),
            })

    return results


def _no_result_row(x: int, y: int) -> dict:
    """Return a 'No result' row for the given (x, y) pair."""
    return {
        "(x, y)":               f"({x}, {y})",
        "Year":                 "No result",
        "Month":                "No result",
        "Town":                 "No result",
        "Block":                "No result",
        "Floor_Area":           "No result",
        "Flat_Model":           "No result",
        "Lease_Commence_Date":  "No result",
        "Price_Per_Square_Meter": "No result",
    }


# ---------------------------------------------------------------------------
# Step 3: Write output CSV
# ---------------------------------------------------------------------------

def write_output(results: list, output_path: str):
    """
    Write query results to ScanResult_<MatricNum>.csv.

    Output format matches assignment spec exactly:
        (x, y),Year,Month,Town,Block,Floor_Area,Flat_Model,
        Lease_Commence_Date,Price_Per_Square_Meter

    Pairs with no qualifying data are written as "No result" in all fields.
    Rows are sorted x ascending then y ascending (guaranteed by loop order).
    """
    fieldnames = [
        "(x, y)", "Year", "Month", "Town", "Block",
        "Floor_Area", "Flat_Model", "Lease_Commence_Date",
        "Price_Per_Square_Meter",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    valid_count  = sum(1 for r in results if r["Year"] != "No result")
    no_res_count = sum(1 for r in results if r["Year"] == "No result")

    print(f"  Output file  : {output_path}")
    print(f"  Valid pairs  : {valid_count}")
    print(f"  No result    : {no_res_count}")
    print(f"  Total rows   : {len(results)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Argument validation
    if len(sys.argv) != 3:
        print("Usage  : python main.py <csv_path> <matriculation_number>")
        print("Example: python main.py ResalePricesSingapore.csv U2323465X")
        sys.exit(1)

    csv_path = sys.argv[1]
    matric   = sys.argv[2].strip().upper()

    if not os.path.exists(csv_path):
        print(f"[ERROR] File not found: '{csv_path}'")
        sys.exit(1)

    # Parse matric number
    try:
        params = parse_matric(matric)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # Print derived parameters
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

    # Step 1: Load CSV
    print("\nStep 1 — Loading data into column store...")
    store = load_csv(csv_path)
    print(f"  {store}")

    # Step 2: Run query
    print("\nStep 2 — Running query...")
    results = run_query(store, params)

    # Step 3: Write output
    print("\nStep 3 — Writing output...")
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"ScanResult_{matric}.csv"
    )
    write_output(results, output_path)

    # Preview first 5 valid rows
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
