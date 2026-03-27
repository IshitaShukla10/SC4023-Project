"""
SC4023 Group Project — CSV loader for ColumnStore.

Single-pass reader: touches each row exactly once, appending to all
column arrays simultaneously.  Month strings are parsed into (year,
month_num) integers at load time so the query engine can do numeric
comparisons without per-row casting overhead.
"""

import csv
from .column_store import ColumnStore


# ---------------------------------------------------------------------------
# Month abbreviation → integer mapping
# ---------------------------------------------------------------------------
MONTH_ABBR = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def _parse_month(raw: str):
    """
    Parse a CSV month string into (year: int, month_num: int).

    Handles two formats:
      'YYYY-MM'  e.g. '2015-01'
      'Mon-YY'   e.g. 'Jan-15'  (two-digit year → 2000 + YY)
    """
    raw = raw.strip()

    if len(raw) == 7 and raw[4] == '-' and raw[:4].isdigit():
        return int(raw[:4]), int(raw[5:])

    parts = raw.split('-')
    if len(parts) == 2:
        month_abbr = parts[0].capitalize()
        year       = 2000 + int(parts[1])
        month_num  = MONTH_ABBR.get(month_abbr, 0)
        return year, month_num

    raise ValueError(f"Unrecognised month format: '{raw}'")


def load_csv(filepath: str) -> ColumnStore:
    """
    Read ResalePricesSingapore.csv and populate a ColumnStore in one pass.

    Design decisions
    ----------------
    1. Single pass  : touch each row exactly once; O(n) time, no re-reads.
    2. Numeric cast : Floor_Area and Resale_Price → float;
                      Lease_Commence_Date → int.  No per-query casting.
    3. Month split  : 'Mon-YY' string → year_col (int) + month_num_col (int)
                      at load time; raw string kept in month_col for output.
    4. Error guard  : malformed rows are skipped with a warning; the store
                      remains valid without crashing.

    Parameters
    ----------
    filepath : str  path to ResalePricesSingapore.csv

    Returns
    -------
    ColumnStore  fully populated, index-synced, ready for querying.
    """
    store   = ColumnStore()
    skipped = 0

    with open(filepath, newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)

        for row_num, row in enumerate(reader, start=2):
            try:
                year, month_num = _parse_month(row['month'])
            except (ValueError, KeyError) as exc:
                print(f"[WARN] Row {row_num}: skipping — bad month ({exc})")
                skipped += 1
                continue

            try:
                floor_area          = float(row['floor_area_sqm'])
                lease_commence_date = int(row['lease_commence_date'])
                resale_price        = float(row['resale_price'])
            except (ValueError, KeyError) as exc:
                print(f"[WARN] Row {row_num}: skipping — bad numeric field ({exc})")
                skipped += 1
                continue

            # Chavi's columns
            store.month_col.append(row['month'].strip())
            store.town_col.append(row['town'].strip().upper())
            store.block_col.append(row['block'].strip())

            # Derived from month parsing
            store.year_col.append(year)
            store.month_num_col.append(month_num)

            # Justin's columns
            store.street_name_col.append(row['street_name'].strip())
            store.flat_type_col.append(row['flat_type'].strip())
            store.flat_model_col.append(row['flat_model'].strip())

            # Ishita's columns
            store.storey_range_col.append(row['storey_range'].strip())
            store.floor_area_col.append(floor_area)
            store.lease_commence_date_col.append(lease_commence_date)
            store.resale_price_col.append(resale_price)

            store._n_rows += 1

    if skipped:
        print(f"[INFO] load_csv complete. Loaded {store._n_rows:,} rows. "
              f"Skipped {skipped} malformed rows.")
    else:
        print(f"[INFO] load_csv complete. Loaded {store._n_rows:,} rows (0 skipped).")

    assert store.validate_sync(), "Column arrays are not index-synced after loading!"
    return store
