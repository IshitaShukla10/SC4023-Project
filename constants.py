DIGIT_TO_YEAR = {
    "0": 2020, "1": 2021, "2": 2022, "3": 2023, "4": 2024,
    "5": 2015, "6": 2016, "7": 2017, "8": 2018, "9": 2019,
}

# digit 0 maps to October per the spec
DIGIT_TO_MONTH = {
    "0": 10, "1": 1, "2": 2, "3": 3, "4": 4,
    "5": 5,  "6": 6, "7": 7, "8": 8, "9": 9,
}

DIGIT_TO_TOWN = {
    "0": "BEDOK",         "1": "BUKIT PANJANG", "2": "CLEMENTI",
    "3": "CHOA CHU KANG", "4": "HOUGANG",        "5": "JURONG WEST",
    "6": "PASIR RIS",     "7": "TAMPINES",       "8": "WOODLANDS",
    "9": "YISHUN",
}

MONTH_ABBR = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

MAX_PRICE_PSM = 4725
X_MIN, X_MAX  = 1, 8
Y_MIN, Y_MAX  = 80, 150
BLOCK_SIZE = 1000