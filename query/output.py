"""
SC4023 Group Project — CSV output writer.

Writes query results to ScanResult_<MatricNum>.csv using the exact
column layout required by the assignment spec.
"""

import csv


def write_output(results: list, output_path: str):
    """
    Write query results to a CSV file.

    Output columns (assignment spec order):
        (x, y), Year, Month, Town, Block, Floor_Area, Flat_Model,
        Lease_Commence_Date, Price_Per_Square_Meter

    Rows with no qualifying data are written as "No result" in all fields.
    Row order is x ascending then y ascending (guaranteed by engine loop).

    Parameters
    ----------
    results     : list   output of query.engine.run_query()
    output_path : str    destination file path
    """
    fieldnames = [
        "(x, y)", "Year", "Month", "Town", "Block",
        "Floor_Area", "Flat_Model", "Lease_Commence_Date",
        "Price_Per_Square_Meter",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    valid_count  = sum(1 for r in results if r["Year"] != "No result")
    no_res_count = sum(1 for r in results if r["Year"] == "No result")

    print(f"  Output file  : {output_path}")
    print(f"  Valid pairs  : {valid_count}")
    print(f"  No result    : {no_res_count}")
    print(f"  Total rows   : {len(results)}")
