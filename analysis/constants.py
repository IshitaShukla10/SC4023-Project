"""
SC4023 Analysis — Parameters hardcoded from Ishita's matric U2323465X.

These mirror what parse_matric() returns for U2323465X and are used
throughout the analysis sections so they don't need to be recomputed.
"""

TARGET_YEAR = 2015
START_MONTH = 6
TOWNS       = {"CHOA CHU KANG", "CLEMENTI", "HOUGANG", "JURONG WEST", "PASIR RIS"}
BLOCK_SIZE  = 1000   # rows per block (used in block abstraction + zone maps)
DEMO_X      = 1      # x value used in single-pair demonstrations
DEMO_Y      = 80     # y value used in single-pair demonstrations
