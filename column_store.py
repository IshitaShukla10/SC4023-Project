import csv
from typing import Dict, List
from constants import *

# ColumnStore implements a column-oriented storage layout.
# Data is stored column-wise in memory to enable efficient filtering

class ColumnStore:
    """Column-oriented storage for the HDB resale dataset.

    Each column is a plain list; all lists are index-synced so
    col_X[i] and col_Y[i] always refer to the same transaction.
    """

    def __init__(self):
        self.month_col = []          
        self.town_col = []
        self.town_codes: List[int] = []
        self.town_dict: Dict[str, int] = {}
        self.town_rev: List[str] = []
        self.town_rle: List[tuple[int, int]] = []  
        self.block_col = []
        self.year_col = []           
        self.month_num_col = []      
        self.month_rle: List[tuple[int, int]] = []  

        self.street_name_col = []
        self.flat_type_col = []
        self.flat_type_codes: List[int] = []
        self.flat_type_dict: Dict[str, int] = {}
        self.flat_type_rev: List[str] = []
        self.flat_model_col = []
        self.flat_model_codes: List[int] = []
        self.flat_model_dict: Dict[str, int] = {}
        self.flat_model_rev: List[str] = []

        self.storey_range_col = []
        self.storey_range_codes: List[int] = []
        self.storey_range_dict: Dict[str, int] = {}
        self.storey_range_rev: List[str] = []
        self.floor_area_col = []
        self.lease_commence_date_col = []
        self.resale_price_col = []

        self._n_rows = 0

        self.block_size = BLOCK_SIZE

        # Zone maps: one (min, max) pair per block
        self.year_zm: List[tuple[int, int]] = []
        self.month_num_zm: List[tuple[int, int]] = []
        self.floor_area_zm: List[tuple[float, float]] = []
        self.resale_price_zm: List[tuple[float, float]] = []
        self.lease_commence_date_zm: List[tuple[int, int]] = []

    @staticmethod
    def _build_zone_map(seq, block_size: int) -> List[tuple]:
        zones = []
        for i in range(0, len(seq), block_size):
            chunk = seq[i:i + block_size]
            zones.append((min(chunk), max(chunk)))
        return zones

    def __len__(self):
        return self._n_rows

    def __repr__(self):
        return f"ColumnStore({self._n_rows:,} rows, 12 columns; encoded: town/flat_type/flat_model/storey_range)"

    @staticmethod
    def _encode(value: str, mapping: Dict[str, int], reverse: List[str]) -> int:
        code = mapping.get(value)
        if code is None:
            code = len(reverse)
            mapping[value] = code
            reverse.append(value)
        return code

    def decode_town(self, code: int) -> str:
        return self.town_rev[code]

    def decode_flat_type(self, code: int) -> str:
        return self.flat_type_rev[code]

    def decode_flat_model(self, code: int) -> str:
        return self.flat_model_rev[code]

    def decode_storey_range(self, code: int) -> str:
        return self.storey_range_rev[code]

    @staticmethod
    def _build_rle(seq: List[int]) -> List[tuple[int, int]]:
        if not seq:
            return []
        runs: List[tuple[int, int]] = []
        cur = seq[0]
        count = 1
        for v in seq[1:]:
            if v == cur:
                count += 1
            else:
                runs.append((cur, count))
                cur = v
                count = 1
        runs.append((cur, count))
        return runs


def _parse_month(raw):
    """Parse 'YYYY-MM' or 'Mon-YY' strings into (year, month_num)."""
    raw = raw.strip()

    if len(raw) == 7 and raw[4] == '-' and raw[:4].isdigit():
        return int(raw[:4]), int(raw[5:])

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

            store.month_col.append(row['month'].strip())
            town_str = row['town'].strip().upper()
            store.town_col.append(town_str)
            town_code = store._encode(town_str, store.town_dict, store.town_rev)
            store.town_codes.append(town_code)
            store.block_col.append(row['block'].strip())
            store.year_col.append(year)
            store.month_num_col.append(month_num)

            store.street_name_col.append(row['street_name'].strip())
            ft_str = row['flat_type'].strip()
            fm_str = row['flat_model'].strip()
            store.flat_type_col.append(ft_str)
            store.flat_model_col.append(fm_str)
            ft_code = store._encode(ft_str, store.flat_type_dict, store.flat_type_rev)
            fm_code = store._encode(fm_str, store.flat_model_dict, store.flat_model_rev)
            store.flat_type_codes.append(ft_code)
            store.flat_model_codes.append(fm_code)

            sr_str = row['storey_range'].strip()
            store.storey_range_col.append(sr_str)
            sr_code = store._encode(sr_str, store.storey_range_dict, store.storey_range_rev)
            store.storey_range_codes.append(sr_code)
            store.floor_area_col.append(floor_area)
            store.lease_commence_date_col.append(lcd)
            store.resale_price_col.append(price)
            store._n_rows += 1

        msg = f"Loaded {store._n_rows:,} rows"
        print(msg if not skipped else msg + f", skipped {skipped} malformed rows")

        # Build RLE for encoded town codes and month numbers once after loading
        store.town_rle = store._build_rle(store.town_codes)
        store.month_rle = store._build_rle(store.month_num_col)

        # Build zone maps once after loading
        store.year_zm = store._build_zone_map(store.year_col, store.block_size)
        store.month_num_zm = store._build_zone_map(store.month_num_col, store.block_size)
        store.floor_area_zm = store._build_zone_map(store.floor_area_col, store.block_size)
        store.resale_price_zm = store._build_zone_map(store.resale_price_col, store.block_size)
        store.lease_commence_date_zm = store._build_zone_map(store.lease_commence_date_col, store.block_size)
        print(
            f"[INFO] RLE sizes — town runs: {len(store.town_rle)}, "
            f"month runs: {len(store.month_rle)}"
        )
        print(
            f"[INFO] Zone maps — year blocks: {len(store.year_zm)}, "
            f"month blocks: {len(store.month_num_zm)}"
        )
    return store
