"""
SC4023 Group Project — Column-oriented query engine.

Scans the ColumnStore for all (x, y) combinations using a three-stage
pre-filtering strategy that reuses intermediate results:

  Stage 1 (once)         : filter by year AND town → candidate_idx
  Stage 2 (once per x)   : filter candidate_idx by month window → month_idx
  Stage 3 (once per x,y) : filter month_idx by floor_area ≥ y, find min PSM
"""

from .constants import X_MIN, X_MAX, Y_MIN, Y_MAX, MAX_PRICE_PSM


def _no_result_row(x: int, y: int) -> dict:
    """Return a 'No result' placeholder dict for the given (x, y) pair."""
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


def run_query(store, params: dict) -> list:
    """
    Scan the ColumnStore for all (x, y) combinations and return results.

    Parameters
    ----------
    store  : ColumnStore   populated by store.loader.load_csv()
    params : dict          output of query.matric.parse_matric()

    Returns
    -------
    list of result dicts, one per (x, y) pair, sorted x-then-y.
    """
    target_year = params["year"]
    start_month = params["start_month"]
    towns       = params["towns"]
    n           = len(store)

    # Stage 1: candidate index (year + town filter, computed once)
    candidate_idx = [
        i for i in range(n)
        if store.year_col[i] == target_year
        and store.town_col[i] in towns
    ]

    results = []

    for x in range(X_MIN, X_MAX + 1):
        end_month    = min(start_month + x - 1, 12)
        valid_months = set(range(start_month, end_month + 1))

        # Stage 2: month window filter (reused for all y values at this x)
        month_idx = [
            i for i in candidate_idx
            if store.month_num_col[i] in valid_months
        ]

        for y in range(Y_MIN, Y_MAX + 1):

            # Stage 3a: floor area filter
            matched = [
                i for i in month_idx
                if store.floor_area_col[i] >= y
            ]

            if not matched:
                results.append(_no_result_row(x, y))
                continue

            # Stage 3b: find row with minimum price per square metre
            best_i   = None
            best_psm = float("inf")
            for i in matched:
                psm = store.resale_price_col[i] / store.floor_area_col[i]
                if psm < best_psm:
                    best_psm = psm
                    best_i   = i

            if best_psm > MAX_PRICE_PSM:
                results.append(_no_result_row(x, y))
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
