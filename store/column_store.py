"""
SC4023 Group Project — ColumnStore class.

Column-oriented storage for the Singapore HDB Resale dataset.
Each column is a plain Python list; all lists are index-synced so
col_X[i] and col_Y[i] always describe the same transaction.

Group column responsibilities
------------------------------
Chavi  (cols 1-3):  month_col, town_col, block_col
                     + derived year_col, month_num_col
Justin (cols 4-6):  street_name_col, flat_type_col, flat_model_col
Ishita (cols 7-10): storey_range_col, floor_area_col,
                     lease_commence_date_col, resale_price_col
"""


class ColumnStore:
    """Column-oriented storage for the Singapore HDB Resale dataset."""

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

        self._n_rows: int = 0

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
        return (
            f"ColumnStore("
            f"rows={self._n_rows}, "
            f"cols=[month, town, block, year, month_num, "
            f"street_name, flat_type, flat_model, "
            f"storey_range, floor_area, lease_commence_date, resale_price]"
            f")"
        )
