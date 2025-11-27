# services/market.py
import json
from functools import lru_cache
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import pandas as pd
import requests

TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"

def to_num(s):
    import math
    if s is None: return math.nan
    s = str(s).strip().replace(",", "")
    if s in ["", "--", "—", "－", "null", "None"]: return math.nan
    try: return float(s)
    except: return math.nan

def month_list(start_d: date, end_d: date):
    cur = date(start_d.year, start_d.month, 1)
    last = date(end_d.year, end_d.month, 1)
    out = []
    while cur <= last:
        out.append(cur.strftime("%Y%m01"))
        cur += relativedelta(months=1)
    return out

@lru_cache(maxsize=4096)
def fetch_month(stock_no: str, yyyymm01: str) -> str:
    params = {"response": "json", "date": yyyymm01, "stockNo": stock_no}
    js = requests.get(TWSE_STOCK_DAY_URL, params=params, timeout=15).json()
    return json.dumps(js, ensure_ascii=False)

def month_json_to_df(js_str: str) -> pd.DataFrame:
    js = json.loads(js_str)
    data, fields = js.get("data", []), js.get("fields", [])
    if not data or not fields:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=fields)
    # ROC -> AD
    def parse_roc_date_str(s):
        y, m, d = s.strip().split("/")
        return datetime(int(y) + 1911, int(m), int(d))
    df["日期_dt"] = df["日期"].apply(parse_roc_date_str)
    for col in ["成交股數","成交金額","開盤價","最高價","最低價","收盤價","漲跌價差","成交筆數"]:
        df[col] = df[col].apply(to_num)
    return df

def fetch_range(stock_no: str, start_d: date, end_d: date) -> pd.DataFrame:
    parts = []
    for m in month_list(start_d, end_d):
        js = fetch_month(stock_no, m)
        dfm = month_json_to_df(js)
        if not dfm.empty:
            parts.append(dfm)
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    df = df[(df["日期_dt"].dt.date >= start_d) & (df["日期_dt"].dt.date <= end_d)]
    return df.sort_values("日期_dt").reset_index(drop=True)
