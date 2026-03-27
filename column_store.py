import csv

MONTH_ABBR = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


class ColumnStore:
    """Column-oriented storage for the HDB resale dataset.

    Each column is a plain list; all lists are index-synced so
    col_X[i] and col_Y[i] always refer to the same transaction.
    """

    def __init__(self):
        # Chavi's columns
        self.month_col = []          # raw string, e.g. '2015-01'
        self.town_col = []
        self.block_col = []
        self.year_col = []           # parsed from month_col at load time
        self.month_num_col = []      # parsed from month_col at load time

        # Justin's columns
        self.street_name_col = []
        self.flat_type_col = []
        self.flat_model_col = []

        # Ishita's columns
        self.storey_range_col = []
        self.floor_area_col = []
        self.lease_commence_date_col = []
        self.resale_price_col = []

        self._n_rows = 0

    def __len__(self):
        return self._n_rows

    def __repr__(self):
        return f"ColumnStore({self._n_rows:,} rows, 12 columns)"


def _parse_month(raw):
    """Parse 'YYYY-MM' or 'Mon-YY' strings into (year, month_num)."""
    raw = raw.strip()
    # newer format: '2015-01'
    if len(raw) == 7 and raw[4] == '-' and raw[:4].isdigit():
        return int(raw[:4]), int(raw[5:])
    # older format: 'Jan-15'
    parts = raw.split('-')
    if len(parts) == 2:
        return 2000 + int(parts[1]), MONTH_ABBR.get(parts[0].capitalize(), 0)
    raise ValueError(f"Unrecognised month format: '{raw}'")


def load_csv(filepath):
    """Read the CSV into a ColumnStore in a single pass."""
    store = ColumnStore()
    skipped = 0

    with open(filepath, newline='', encoding='utf-8-sig') as f:
        for row_num, row in enumerate(csv.DictReader(f), start=2):
            try:
                year, month_num = _parse_month(row['month'])
                floor_area = float(row['floor_area_sqm'])
                lcd = int(row['lease_commence_date'])
                price = float(row['resale_price'])
            except (ValueError, KeyError) as e:
                print(f"[WARN] row {row_num}: skipping ({e})")
                skipped += 1
                continue

            # Chavi
            store.month_col.append(row['month'].strip())
            store.town_col.append(row['town'].strip().upper())
            store.block_col.append(row['block'].strip())
            store.year_col.append(year)
            store.month_num_col.append(month_num)
            # Justin
            store.street_name_col.append(row['street_name'].strip())
            store.flat_type_col.append(row['flat_type'].strip())
            store.flat_model_col.append(row['flat_model'].strip())
            # Ishita
            store.storey_range_col.append(row['storey_range'].strip())
            store.floor_area_col.append(floor_area)
            store.lease_commence_date_col.append(lcd)
            store.resale_price_col.append(price)
            store._n_rows += 1

    msg = f"Loaded {store._n_rows:,} rows"
    print(msg if not skipped else msg + f", skipped {skipped} malformed rows")
    return store
