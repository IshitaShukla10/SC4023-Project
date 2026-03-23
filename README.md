# SC4023 Group Project — HDB Resale Price Analysis

Column-oriented storage and query system for Singapore HDB resale flat transactions (2015–2025).

## What this project does

Given a matriculation number, the program derives a target year, start month, and a set of towns, then finds the **minimum price per square metre** across all valid (x, y) combinations where:
- **x** = month window size (1 to 8), starting from the derived start month
- **y** = minimum floor area in sqm (80 to 150)
- A pair is **valid** if the minimum price/sqm found is ≤ 4725

All parameters are derived automatically from the matric number, so running the same code with a different matric number gives different results.

## Files

| File | Description |
|------|-------------|
| `main.py` | Entry point — parses matric number, loads data, runs queries, writes output CSV |
| `column_store.py` | ColumnStore class and load_csv() — stores each column as a separate list |
| `analysis.py` | Justification for which compression techniques apply to each column and why |
| `ScanResult_<MatricNum>.csv` | Output file generated after running main.py |

## Requirements

- Python 3.8+
- No external libraries (pure standard library)

## How to Run

```bash
python main.py ResalePricesSingapore.csv <matriculation_number>
```

**Example:**
```bash
python main.py ResalePricesSingapore.csv U2323465X
```

To run the analysis/justification file:
```bash
python analysis.py ResalePricesSingapore.csv
```

## Output Format

```
(x, y),Year,Month,Town,Block,Floor_Area,Flat_Model,Lease_Commence_Date,Price_Per_Square_Meter
(1, 80),2015,06,CHOA CHU KANG,705,114,Model A,1995,2807
...
```

If no qualifying data exists for a given (x, y) pair, all fields are written as `No result`.

## Why column-oriented storage?

Instead of storing data row by row, each column lives in its own list:

```python
# our approach - column store
floor_area_col   = [60.0, 68.0, 69.0, ...]
resale_price_col = [255000.0, 275000.0, 285000.0, ...]

# not this - row-oriented
rows = [{"floor_area": 60, "resale_price": 255000, ...}, ...]
```

All arrays are index-synced: `floor_area_col[i]` and `resale_price_col[i]` always refer to the same transaction. The advantage is that a query only touching 2 columns doesn't need to read the other 10.

## Query efficiency

The query engine applies filters in 3 stages to avoid redundant work:

1. **Year + Town (computed once):** Narrows 259,237 rows down to ~4,227 candidates
2. **Month window (once per x value):** Further reduces the candidate pool
3. **Floor area + PSM scan (once per x,y pair):** Finds the minimum on the small subset

This means intermediate results are reused across all 568 (x, y) combinations rather than re-scanning the full dataset each time.

## Compression techniques — quick summary

The `analysis.py` file runs through these in detail with actual numbers from the dataset, but the main conclusions are:

- **Dictionary encoding** works well on low-cardinality string columns (town, flat_type, flat_model, storey_range). Replacing repeated strings with small integers gives 6–9x compression on those columns.
- **Zone maps** (min/max per block) are only useful when data is sorted by the filter column. For year_col the CSV is ordered chronologically so ~93% of blocks can be skipped. For floor_area the values are scattered so zone maps give 0% skip rate.
- **Run-length encoding** works on town (~100x) and month (~22x) because the CSV is sorted by those columns. storey_range and similar columns with ~79% run rate barely compress.
- **Block abstraction** applies to every column and is our baseline for measuring query efficiency.

## Matric number parsing

| Rule | Example |
|------|---------|
| Last digit → target year (5–9 → 2015–2019, 0–4 → 2020–2024) | digit `5` → year `2015` |
| Second last digit → start month (0 = October) | digit `6` → month `06` |
| All unique digits → matched towns (from spec Table 1) | digits `2,3,4,5,6` → 5 towns |

## Group Member Column Assignments

| Member | Columns |
|--------|---------|
| Chavi | Month, Town, Block (+ derived Year, Month_Num) |
| Justin | Street_Name, Flat_Type, Flat_Model |
| Ishita | Storey_Range, Floor_Area, Lease_Commence_Date, Resale_Price |
