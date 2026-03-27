"""
SC4023 Group Project — HDB Resale Column-Store Query

Usage: python main.py <csv_path> <matric_number>
  e.g. python main.py ResalePricesSingapore.csv U2323465X
"""

import sys
import os
import csv

from column_store import load_csv

# ── Assignment constants ────────────────────────────────────────────────────

DIGIT_TO_YEAR = {
    "0": 2020, "1": 2021, "2": 2022, "3": 2023, "4": 2024,
    "5": 2015, "6": 2016, "7": 2017, "8": 2018, "9": 2019,
}

# digit 0 maps to October per the spec
DIGIT_TO_MONTH = {
    "0": 10, "1": 1, "2": 2, "3": 3, "4": 4,
    "5": 5,  "6": 6, "7": 7, "8": 8, "9": 9,
}

DIGIT_TO_TOWN = {
    "0": "BEDOK",         "1": "BUKIT PANJANG", "2": "CLEMENTI",
    "3": "CHOA CHU KANG", "4": "HOUGANG",        "5": "JURONG WEST",
    "6": "PASIR RIS",     "7": "TAMPINES",       "8": "WOODLANDS",
    "9": "YISHUN",
}

MAX_PRICE_PSM = 4725
X_MIN, X_MAX  = 1, 8
Y_MIN, Y_MAX  = 80, 150


# ── Matric parsing ──────────────────────────────────────────────────────────

def parse_matric(matric):
    """Return (year, start_month, towns) derived from the matric number."""
    digits = [c for c in matric if c.isdigit()]
    if len(digits) < 2:
        raise ValueError(f"Matric '{matric}' must contain at least 2 digits")
    year   = DIGIT_TO_YEAR[digits[-1]]
    month  = DIGIT_TO_MONTH[digits[-2]]
    towns  = {DIGIT_TO_TOWN[d] for d in set(digits) if d in DIGIT_TO_TOWN}
    return year, month, towns


# ── Query engine ────────────────────────────────────────────────────────────

def _no_result(x, y):
    return {
        "(x, y)":                 f"({x}, {y})",
        "Year":                   "No result",
        "Month":                  "No result",
        "Town":                   "No result",
        "Block":                  "No result",
        "Floor_Area":             "No result",
        "Flat_Model":             "No result",
        "Lease_Commence_Date":    "No result",
        "Price_Per_Square_Meter": "No result",
    }


def run_query(store, year, start_month, towns):
    """Scan all (x, y) combinations and return one result row per pair.

    Three-stage filtering to avoid redundant work:
      Stage 1 (once)       — year + town filter
      Stage 2 (once per x) — month window filter, reused across all y
      Stage 3 (per x,y)    — floor area filter, then find min PSM
    """
    n = len(store)

    # Stage 1: filter by year and town once — reused across all (x, y)
    base = [
        i for i in range(n)
        if store.year_col[i] == year and store.town_col[i] in towns
    ]

    results = []
    for x in range(X_MIN, X_MAX + 1):
        end_month    = min(start_month + x - 1, 12)
        valid_months = set(range(start_month, end_month + 1))

        # Stage 2: narrow to the x-month window — reused for all y at this x
        in_window = [i for i in base if store.month_num_col[i] in valid_months]

        for y in range(Y_MIN, Y_MAX + 1):
            matched = [i for i in in_window if store.floor_area_col[i] >= y]

            if not matched:
                results.append(_no_result(x, y))
                continue

            best_i, best_psm = None, float("inf")
            for i in matched:
                psm = store.resale_price_col[i] / store.floor_area_col[i]
                if psm < best_psm:
                    best_psm, best_i = psm, i

            if best_psm > MAX_PRICE_PSM:
                results.append(_no_result(x, y))
                continue

            i = best_i
            results.append({
                "(x, y)":                 f"({x}, {y})",
                "Year":                   store.year_col[i],
                "Month":                  f"{store.month_num_col[i]:02d}",
                "Town":                   store.town_col[i],
                "Block":                  store.block_col[i],
                "Floor_Area":             int(store.floor_area_col[i]),
                "Flat_Model":             store.flat_model_col[i],
                "Lease_Commence_Date":    store.lease_commence_date_col[i],
                "Price_Per_Square_Meter": round(best_psm),
            })

    return results


# ── Output ──────────────────────────────────────────────────────────────────

def write_output(results, path):
    fields = [
        "(x, y)", "Year", "Month", "Town", "Block",
        "Floor_Area", "Flat_Model", "Lease_Commence_Date", "Price_Per_Square_Meter",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(results)

    valid   = sum(1 for r in results if r["Year"] != "No result")
    no_res  = len(results) - valid
    print(f"Written to {path}")
    print(f"  {valid} valid rows, {no_res} 'No result' rows, {len(results)} total")


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) != 3:
        print("Usage: python main.py <csv_path> <matric_number>")
        print("  e.g. python main.py ResalePricesSingapore.csv U2323465X")
        sys.exit(1)

    csv_path = sys.argv[1]
    matric   = sys.argv[2].strip().upper()

    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        sys.exit(1)

    try:
        year, start_month, towns = parse_matric(matric)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Matric: {matric}  |  Year: {year}  |  Start month: {start_month:02d}")
    print(f"Towns:  {sorted(towns)}\n")

    store   = load_csv(csv_path)
    results = run_query(store, year, start_month, towns)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"ScanResult_{matric}.csv")
    write_output(results, out)

    valid = [r for r in results if r["Year"] != "No result"]
    if valid:
        print("\nSample results:")
        print(f"  {'(x,y)':<10} {'Year'} {'Mo':>2}  {'Town':<16} {'Block':<6} {'Area':>4}  {'PSM':>6}")
        for r in valid[:5]:
            print(f"  {r['(x, y)']:<10} {r['Year']} {r['Month']:>2}  {r['Town']:<16} "
                  f"{r['Block']:<6} {r['Floor_Area']:>4}  {r['Price_Per_Square_Meter']:>6}")


if __name__ == "__main__":
    main()
