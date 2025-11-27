# utils/dates.py
from datetime import date

def roc_to_ad_year(roc_year: int) -> int:
    return int(roc_year) + 1911

def parse_roc_date(roc_year: int, month: int, day: int = 1) -> date:
    return date(roc_to_ad_year(roc_year), int(month), int(day))

def ad_to_roc(dt: date) -> int:
    return dt.year - 1911
