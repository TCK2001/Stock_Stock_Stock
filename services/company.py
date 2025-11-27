# services/company.py
import io, re
from functools import lru_cache
import pandas as pd
import requests

TWSE_COMPANY_BASIC = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
ISIN_URL = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"

def _normalize_company_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    code_candidates = [c for c in df.columns if ("公司代號" in c) or ("證券代號" in c) or (str(c).strip().lower() == "code")]
    name_candidates = [c for c in df.columns if ("公司名稱" in c) or ("證券名稱" in c) or (str(c).strip().lower() == "name")]
    if not code_candidates or not name_candidates:
        raise ValueError("회사 기본자료의 열 이름을 찾을 수 없습니다.")
    code_col = code_candidates[0]
    name_col = name_candidates[0]
    out = pd.DataFrame({
        "code": df[code_col].astype(str).str.replace(".0", "", regex=False).str.strip(),
        "name": df[name_col].astype(str).str.strip(),
    })
    out = out[out["code"].str.fullmatch(r"\d{4}")]
    out = out.drop_duplicates(subset=["code"], keep="first").reset_index(drop=True)
    return out

def _fetch_company_from_openapi() -> pd.DataFrame:
    r = requests.get(TWSE_COMPANY_BASIC, timeout=20)
    r.raise_for_status()
    txt = r.text.strip()
    # JSON 우선
    try:
        js = r.json()
        if isinstance(js, list) and js:
            return _normalize_company_df(pd.DataFrame(js))
    except Exception:
        pass
    # CSV 관대 파싱
    df = pd.read_csv(io.StringIO(txt), engine="python", on_bad_lines="skip")
    return _normalize_company_df(df)

def _fetch_company_from_isin_backup() -> pd.DataFrame:
    tables = pd.read_html(ISIN_URL)
    t = tables[0].copy()
    t.columns = t.iloc[0]
    t = t[1:].rename(columns=lambda x: str(x).strip())
    def split_code_name(x):
        s = str(x)
        m = re.match(r"^(\d{4})\s+(.+)$", s)
        if m: return m.group(1), m.group(2)
        return "", s
    t["code"], t["name"] = zip(*t["有價證券代號及名稱"].map(split_code_name))
    out = t[["code","name"]]
    out = out[out["code"].str.fullmatch(r"\d{4}")]
    return out.drop_duplicates(subset=["code"]).reset_index(drop=True)

@lru_cache(maxsize=1)
def load_company_table() -> pd.DataFrame:
    try:
        return _fetch_company_from_openapi()
    except Exception:
        return _fetch_company_from_isin_backup()

def search_code(keyword: str) -> pd.DataFrame:
    t = load_company_table()
    k = (keyword or "").strip().lower().replace("\u3000", " ")
    m = t["name"].str.lower().str.contains(k, na=False) | t["code"].str.contains(k, na=False)
    return t[m].copy()
