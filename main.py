"""
SC4023 Group Project — HDB Resale Column-Store Query

Usage: python main.py <csv_path> <matric_number>
  e.g. python main.py ResalePricesSingapore.csv U2323465X
"""

import sys
import os
import csv

from column_store import load_csv
from constants import *

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

# Candidate Blocks for zone map

def candidate_blocks_from_zone_map(zones, predicate):
    """Return block ids whose (min, max) range may satisfy the predicate."""
    return [b for b, (mn, mx) in enumerate(zones) if predicate(mn, mx)]

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

    town_codes = {store.town_dict[t] for t in towns if t in store.town_dict}

    # Use year zone map to prune blocks first
    candidate_blocks = candidate_blocks_from_zone_map(
        store.year_zm,
        lambda mn, mx: mn <= year <= mx
    )

    # Scan only those candidate blocks
    base = []
    for b in candidate_blocks:
        start = b * store.block_size
        end = min(start + store.block_size, n)

        for i in range(start, end):
            if store.year_col[i] == year and store.town_codes[i] in town_codes:
                base.append(i)

    results = []
    for x in range(X_MIN, X_MAX + 1):
        end_month    = min(start_month + x - 1, 12)
        valid_months = set(range(start_month, end_month + 1))

        # Stage 2: narrow to the x-month window — reused for all y at this x
        in_window = [i for i in base if store.month_num_col[i] in valid_months]

        sorted_idx = sorted(in_window, key=lambda i: store.floor_area_col[i])

        pointer = 0
        n = len(sorted_idx)

        for y in range(Y_MIN, Y_MAX + 1):

            while pointer < n and store.floor_area_col[sorted_idx[pointer]] < y:
                pointer += 1

            matched = sorted_idx[pointer:]

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
                "Town":                   store.decode_town(store.town_codes[i]),
                "Block":                  store.block_col[i],
                "Floor_Area":             int(store.floor_area_col[i]),
                "Flat_Model":             store.decode_flat_model(store.flat_model_codes[i]),
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
