"""
SC4023 Group Project — Query constants from the assignment spec.
"""

# Table 1: digit → town name
DIGIT_TO_TOWN = {
    "0": "BEDOK",
    "1": "BUKIT PANJANG",
    "2": "CLEMENTI",
    "3": "CHOA CHU KANG",
    "4": "HOUGANG",
    "5": "JURONG WEST",
    "6": "PASIR RIS",
    "7": "TAMPINES",
    "8": "WOODLANDS",
    "9": "YISHUN",
}

# Second-last digit → start month (digit 0 represents October per spec)
DIGIT_TO_MONTH = {
    "0": 10,
    "1": 1, "2": 2, "3": 3, "4": 4,
    "5": 5, "6": 6, "7": 7, "8": 8,
    "9": 9,
}

MAX_PRICE_PSM = 4725    # validity threshold (SGD per sqm)
X_MIN, X_MAX  = 1, 8    # x range: months window size
Y_MIN, Y_MAX  = 80, 150 # y range: minimum floor area (sqm)
