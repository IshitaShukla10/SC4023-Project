# SC4023 Group Project — HDB Resale Price Analysis

Column-oriented data storage and query system for Singapore HDB resale flat transactions (2015–2025).

## Project Overview

This program finds the **Minimum Price per Square Metre** for HDB resale flats across all valid (x, y) combinations, where:
- **x** = months window size (1 to 8), starting from a derived start month
- **y** = minimum floor area requirement in sqm (80 to 150)
- A pair is **valid** if the minimum price/sqm found is ≤ 4725

All parameters (target year, start month, matched towns) are derived automatically from the input matriculation number.

## Files

| File | Description |
|------|-------------|
| `main.py` | Entry point — parses matric number, runs full pipeline, writes output CSV |
| `column_store.py` | Column-oriented storage class (`ColumnStore`) and `load_csv()` function |
| `ScanResult_<MatricNum>.csv` | Output file generated after running `main.py` |

## Requirements

- Python 3.8 or higher
- No external libraries required (pure Python standard library only)

## How to Run

```bash
python main.py ResalePricesSingapore.csv <matriculation_number>
```

**Example:**
```bash
python main.py ResalePricesSingapore.csv U2323465X
```

This will:
1. Parse the matriculation number to derive query parameters
2. Load `ResalePricesSingapore.csv` into column-oriented storage
3. Run the query across all 568 (x, y) combinations
4. Write `ScanResult_U2323465X.csv` to the same directory

## Output Format

The output CSV has the following columns:

```
(x, y),Year,Month,Town,Block,Floor_Area,Flat_Model,Lease_Commence_Date,Price_Per_Square_Meter
(1, 80),2015,06,CHOA CHU KANG,705,114,Model A,1995,2807
...
```

If no qualifying data exists for a given (x, y) pair, all fields are written as `No result`.

## Column-Oriented Design

Data is stored as separate column arrays rather than rows:

```python
# Column store (our approach)
floor_area_col   = [60.0, 68.0, 69.0, ...]
resale_price_col = [255000.0, 275000.0, 285000.0, ...]

# NOT row-oriented (avoided)
rows = [{"floor_area": 60, "resale_price": 255000, ...}, ...]
```

All arrays are index-synced: `floor_area_col[i]` and `resale_price_col[i]` always describe the same transaction. This allows the query engine to scan only the columns it needs, skipping all others.

## Query Efficiency

The query engine uses a 3-step pre-filtering strategy to avoid redundant work:

1. **Year + Town filter (once):** Reduces 259,237 rows to ~4,227 candidates
2. **Month window filter (once per x):** Further reduces the candidate pool
3. **Floor area + PSM scan (once per x,y):** Finds minimum on the small subset

This reuses intermediate results across all 568 (x, y) combinations instead of rescanning the full dataset each time.

## Matriculation Number Parsing

| Rule | Example |
|------|---------|
| Last digit → target year (5–9 → 2015–2019, 0–4 → 2020–2024) | digit `5` → year `2015` |
| Second last digit → start month (0 = October) | digit `6` → month `06` (June) |
| All unique digits → matched towns (Table 1 from spec) | digits `2,3,4,5,6` → 5 towns |

## Group Member Column Assignments

| Member | Columns |
|--------|---------|
| Chavi | Month, Town, Block (+ derived Year, Month_Num) |
| Justin | Street_Name, Flat_Type, Flat_Model |
| Ishita | Storey_Range, Floor_Area, Lease_Commence_Date, Resale_Price |
