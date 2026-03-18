"""
SC4023 Group Project — Column-Oriented Storage
Ishita's Module: Columns 7–10
    - Storey_Range      (string, stored as-is)
    - Floor_Area        (float)
    - Lease_Commence_Date (int)
    - Resale_Price      (float)

Also houses the shared ColumnStore class and load_csv() that all group
members can import from, since the CSV must be read in one single pass
to keep all column arrays index-synced.

Design Rationale
----------------
We use a pure Python approach with no external libraries (no pandas/numpy)
so the column-oriented design choice is explicit and educationally clear.

Column-oriented storage means each attribute lives in its own flat list:
    storey_range_col[i], floor_area_col[i], ... all belong to row i.

This lets the query engine scan ONLY the columns it cares about, skipping
every other attribute — exactly the column-store advantage.
"""

import csv
from datetime import datetime


# ---------------------------------------------------------------------------
# Month abbreviation → integer mapping
# The CSV stores months as "Jan-15", "Feb-15", etc. (Mon-YY).
# We parse these into (year: int, month_num: int) for fast numeric filtering.
# ---------------------------------------------------------------------------
MONTH_ABBR = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def _parse_month(raw: str):
    """
    Parse a CSV month string like 'Jan-15' or '2015-01' into (year, month_num).

    The dataset appears to use 'Mon-YY' format (e.g. 'Jan-15' → 2015, 1).
    We also handle 'YYYY-MM' in case newer entries differ.

    Returns
    -------
    (year: int, month_num: int)
    """
    raw = raw.strip()

    # Handle 'YYYY-MM' format (e.g. '2015-01')
    if len(raw) == 7 and raw[4] == '-' and raw[:4].isdigit():
        year = int(raw[:4])
        month_num = int(raw[5:])
        return year, month_num

    # Handle 'Mon-YY' format (e.g. 'Jan-15')
    parts = raw.split('-')
    if len(parts) == 2:
        month_abbr = parts[0].capitalize()
        year_short = int(parts[1])
        # Two-digit year: 00–99 → 2000–2099 (safe for this dataset)
        year = 2000 + year_short
        month_num = MONTH_ABBR.get(month_abbr, 0)
        return year, month_num

    raise ValueError(f"Unrecognised month format: '{raw}'")


# ---------------------------------------------------------------------------
# ColumnStore — the central storage object shared by the whole group
# ---------------------------------------------------------------------------

class ColumnStore:
    """
    Column-oriented storage for the Singapore HDB Resale dataset.

    Each column is a plain Python list.  All lists are index-synced:
    col_X[i] and col_Y[i] describe the same transaction.

    Group column responsibilities
    -----------------------------
    Chavi  (cols 1–3): month_col, town_col, block_col
                        + derived year_col, month_num_col
    Justin (cols 4–6): street_name_col, flat_type_col, flat_model_col
    Ishita (cols 7–10): storey_range_col, floor_area_col,
                         lease_commence_date_col, resale_price_col
    """

    def __init__(self):
        # ── Chavi's columns ──────────────────────────────────────────────
        self.month_col: list[str] = []          # raw 'Mon-YY' string
        self.town_col: list[str] = []
        self.block_col: list[str] = []

        # Derived from month_col (split on load — no recomputation needed)
        self.year_col: list[int] = []           # e.g. 2015
        self.month_num_col: list[int] = []      # e.g. 1 for January

        # ── Justin's columns ─────────────────────────────────────────────
        self.street_name_col: list[str] = []
        self.flat_type_col: list[str] = []
        self.flat_model_col: list[str] = []

        # ── Ishita's columns ─────────────────────────────────────────────
        self.storey_range_col: list[str] = []
        self.floor_area_col: list[float] = []           # numeric (sqm)
        self.lease_commence_date_col: list[int] = []    # numeric (year)
        self.resale_price_col: list[float] = []         # numeric (SGD)

        # Row count for quick sanity checks
        self._n_rows: int = 0

    # ------------------------------------------------------------------
    # Integrity helpers
    # ------------------------------------------------------------------

    def validate_sync(self) -> bool:
        """Assert every column has the same length (index-sync check)."""
        lengths = {
            'month':               len(self.month_col),
            'town':                len(self.town_col),
            'block':               len(self.block_col),
            'year':                len(self.year_col),
            'month_num':           len(self.month_num_col),
            'street_name':         len(self.street_name_col),
            'flat_type':           len(self.flat_type_col),
            'flat_model':          len(self.flat_model_col),
            'storey_range':        len(self.storey_range_col),
            'floor_area':          len(self.floor_area_col),
            'lease_commence_date': len(self.lease_commence_date_col),
            'resale_price':        len(self.resale_price_col),
        }
        unique_lengths = set(lengths.values())
        if len(unique_lengths) != 1:
            print("[ERROR] Column length mismatch:", lengths)
            return False
        return True

    def __len__(self) -> int:
        return self._n_rows

    def __repr__(self) -> str:
        return (f"ColumnStore("
                f"rows={self._n_rows}, "
                f"cols=[month, town, block, year, month_num, "
                f"street_name, flat_type, flat_model, "
                f"storey_range, floor_area, lease_commence_date, resale_price]"
                f")")


# ---------------------------------------------------------------------------
# load_csv — single-pass CSV reader that populates the ColumnStore
# ---------------------------------------------------------------------------

def load_csv(filepath: str) -> ColumnStore:
    """
    Read /Users/ishitashukla/Desktop/SC4023-Project/ResalePricesSingapore.csv and populate a ColumnStore in one pass.

    Design decisions
    ----------------
    1. Single pass: we touch each row exactly once, appending to each column.
       This is O(n) time and avoids repeated file reads.

    2. Numeric conversion on load: Floor_Area and Resale_Price are cast to
       float; Lease_Commence_Date is cast to int.  Downstream query code
       can then do arithmetic comparisons without per-row casting overhead.

    3. Month parsing: the 'Mon-YY' string is split into year_col (int) and
       month_num_col (int) at load time.  The raw string is also kept in
       month_col for output formatting.

    4. Error tolerance: if a row has a malformed month or non-numeric numeric
       field, we skip that row and print a warning.  This keeps the store
       valid without crashing.

    Parameters
    ----------
    filepath : str
        Path to /Users/ishitashukla/Desktop/SC4023-Project/ResalePricesSingapore.csv

    Returns
    -------
    ColumnStore
        Fully populated store ready for querying.
    """
    store = ColumnStore()
    skipped = 0

    with open(filepath, newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)

        for row_num, row in enumerate(reader, start=2):  # row 1 = header
            # ── Parse month → year + month_num ───────────────────────────
            try:
                year, month_num = _parse_month(row['month'])
            except (ValueError, KeyError) as exc:
                print(f"[WARN] Row {row_num}: skipping — bad month ({exc})")
                skipped += 1
                continue

            # ── Parse Ishita's numeric columns ───────────────────────────
            try:
                floor_area = float(row['floor_area_sqm'])
                lease_commence_date = int(row['lease_commence_date'])
                resale_price = float(row['resale_price'])
            except (ValueError, KeyError) as exc:
                print(f"[WARN] Row {row_num}: skipping — bad numeric field ({exc})")
                skipped += 1
                continue

            # ── Append to every column ────────────────────────────────────
            # Chavi's columns
            store.month_col.append(row['month'].strip())
            store.town_col.append(row['town'].strip().upper())
            store.block_col.append(row['block'].strip())

            # Derived columns (from month parsing above)
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

    # Final sanity check
    assert store.validate_sync(), "Column arrays are not index-synced after loading!"

    return store


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os

    # Accept CSV path as command-line arg, else use default relative path
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/ishitashukla/Desktop/SC4023-Project/ResalePricesSingapore.csv"

    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV file not found: {csv_path}")
        sys.exit(1)

    print("=" * 60)
    print("  SC4023 Column Store — Ishita's Module — Self-Test")
    print("=" * 60)

    store = load_csv(csv_path)
    print()
    print(store)
    print()

    # ── Print first 3 rows across Ishita's columns ───────────────────────
    print("Sample — first 3 rows (Ishita's columns + year/month for context):")
    print(f"{'idx':>4}  {'year':>4}  {'mon':>3}  {'storey_range':<12}  "
          f"{'floor_area':>10}  {'lease_date':>10}  {'resale_price':>12}")
    print("-" * 65)
    for i in range(min(3, store._n_rows)):
        print(f"{i:>4}  {store.year_col[i]:>4}  {store.month_num_col[i]:>3}  "
              f"{store.storey_range_col[i]:<12}  "
              f"{store.floor_area_col[i]:>10.1f}  "
              f"{store.lease_commence_date_col[i]:>10}  "
              f"{store.resale_price_col[i]:>12.2f}")

    # ── Basic statistics on Ishita's numeric columns ─────────────────────
    print()
    print("Statistics on Ishita's numeric columns:")
    fa = store.floor_area_col
    rp = store.resale_price_col
    lcd = store.lease_commence_date_col
    print(f"  Floor Area      — min: {min(fa):.1f} m²  |  max: {max(fa):.1f} m²  "
          f"|  mean: {sum(fa)/len(fa):.1f} m²")
    print(f"  Resale Price    — min: SGD {min(rp):,.0f}  |  max: SGD {max(rp):,.0f}")
    print(f"  Lease Commence  — min: {min(lcd)}  |  max: {max(lcd)}")

    # ── Demonstrate index-sync: print one full row ────────────────────────
    idx = 0
    print()
    print(f"Full row at index {idx}:")
    print(f"  month             : {store.month_col[idx]}")
    print(f"  year (derived)    : {store.year_col[idx]}")
    print(f"  month_num (derived): {store.month_num_col[idx]}")
    print(f"  town              : {store.town_col[idx]}")
    print(f"  block             : {store.block_col[idx]}")
    print(f"  street_name       : {store.street_name_col[idx]}")
    print(f"  flat_type         : {store.flat_type_col[idx]}")
    print(f"  storey_range      : {store.storey_range_col[idx]}")
    print(f"  floor_area        : {store.floor_area_col[idx]}")
    print(f"  flat_model        : {store.flat_model_col[idx]}")
    print(f"  lease_commence_date: {store.lease_commence_date_col[idx]}")
    print(f"  resale_price      : {store.resale_price_col[idx]}")

    print()
    print("[PASS] All checks completed successfully.")
