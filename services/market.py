# services/market.py
import json
from functools import lru_cache
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import pandas as pd
import requests
import urllib3

TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"

# SSL 검증 끄면 경고가 뜨니까, 보기 싫으면 이 줄로 경고만 꺼줄 수 있음
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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
    try:
        # 🔥 핵심: verify=False 로 SSL 인증서 검증을 끄고 요청
        r = requests.get(TWSE_STOCK_DAY_URL, params=params, timeout=15, verify=False)
        r.raise_for_status()
        js = r.json()
        return json.dumps(js, ensure_ascii=False)
    except requests.exceptions.SSLError as e:
        # Streamlit Cloud 등에서 SSL 깨질 때
        print("SSL error when calling TWSE:", e)
    except Exception as e:
        print("Error when calling TWSE:", e)

    # 에러일 때는 빈 구조를 돌려줘서 아래에서 빈 DataFrame이 나오도록
    return json.dumps({"data": [], "fields": []}, ensure_ascii=False)


def month_json_to_df(js_str: str) -> pd.DataFrame:
    js = json.loads(js_str)
    data, fields = js.get("data", []), js.get("fields", [])
    if not data or not fields:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=fields)

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
