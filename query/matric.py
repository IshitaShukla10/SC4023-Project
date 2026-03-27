"""
SC4023 Group Project — Matriculation number parser.

Derives the three query parameters (target year, start month, matched
towns) from the digits embedded in a NTU matriculation number.
"""

from .constants import DIGIT_TO_TOWN, DIGIT_TO_MONTH


def parse_matric(matric: str) -> dict:
    """
    Derive query parameters from a matriculation number.

    Rules (from assignment spec)
    ----------------------------
    Last digit        → target year  (5-9 → 2015-2019, 0-4 → 2020-2024)
    Second-last digit → start month  (0 = October, 1-9 = Jan-Sep)
    All unique digits → matched towns (see DIGIT_TO_TOWN)

    Parameters
    ----------
    matric : str  e.g. "U2323465X"

    Returns
    -------
    dict with keys:
        year        : int   target year
        start_month : int   starting month number (1-12)
        towns       : set   set of town name strings
    """
    digits = "".join(c for c in matric if c.isdigit())

    if len(digits) < 2:
        raise ValueError(
            f"Matriculation number '{matric}' must contain at least 2 digits."
        )

    last        = int(digits[-1])
    target_year = 2010 + last if last >= 5 else 2020 + last
    start_month = DIGIT_TO_MONTH[digits[-2]]
    towns       = {DIGIT_TO_TOWN[d] for d in set(digits) if d in DIGIT_TO_TOWN}

    return {"year": target_year, "start_month": start_month, "towns": towns}
