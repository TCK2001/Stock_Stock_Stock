# services/company.py
import io, re
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests  # 필요 없으면 나중에 지워도 됨

LOCAL_COMPANY_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "t187ap03_L.json"
    # JSON이 아니라 CSV로 저장했다면 위 줄을 이렇게 바꿔
    # Path(__file__).resolve().parent.parent / "data" / "t187ap03_L.csv"
)

TWSE_COMPANY_BASIC = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
ISIN_URL = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"


def _normalize_company_df(df: pd.DataFrame) -> pd.DataFrame:
    """열 이름 정리 + code/name 추출 + 4자리 코드만 남기기"""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    code_candidates = [
        c
        for c in df.columns
        if ("公司代號" in c)
        or ("證券代號" in c)
        or (str(c).strip().lower() == "code")
    ]
    name_candidates = [
        c
        for c in df.columns
        if ("公司名稱" in c)
        or ("證券名稱" in c)
        or (str(c).strip().lower() == "name")
    ]

    if not code_candidates or not name_candidates:
        raise ValueError("회사 기본자료의 열 이름을 찾을 수 없습니다.")

    code_col = code_candidates[0]
    name_col = name_candidates[0]

    out = pd.DataFrame(
        {
            "code": df[code_col].astype(str).str.replace(".0", "", regex=False).str.strip(),
            "name": df[name_col].astype(str).str.strip(),
        }
    )

    # 4자리 숫자 코드만
    out = out[out["code"].str.fullmatch(r"\d{4}")]
    out = out.drop_duplicates(subset=["code"], keep="first").reset_index(drop=True)
    return out


# 🔹 1) "로컬에 저장해 둔 t187ap03_L 파일"에서 읽어오기
def _load_company_from_local() -> pd.DataFrame:
    if not LOCAL_COMPANY_FILE.exists():
        raise FileNotFoundError(f"회사 기본자료 파일을 찾을 수 없습니다: {LOCAL_COMPANY_FILE}")

    suffix = LOCAL_COMPANY_FILE.suffix.lower()

    if suffix == ".json":
        # TWSE openapi JSON 그대로 저장한 경우
        df = pd.read_json(LOCAL_COMPANY_FILE)
        return _normalize_company_df(df)

    elif suffix == ".csv":
        # CSV로 저장한 경우
        df = pd.read_csv(LOCAL_COMPANY_FILE, engine="python", on_bad_lines="skip")
        return _normalize_company_df(df)

    else:
        # 혹시 모를 경우: 확장자에 상관없이 한 번씩 시도
        try:
            df = pd.read_json(LOCAL_COMPANY_FILE)
            return _normalize_company_df(df)
        except Exception:
            df = pd.read_csv(LOCAL_COMPANY_FILE, engine="python", on_bad_lines="skip")
            return _normalize_company_df(df)


# 🔹 2) (선택) 여전히 온라인에서 받아오는 버전 – 로컬 실패 시 백업용
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


# 🔹 3) (선택) ISIN 백업 – 필요 없으면 완전히 지워도 됨
def _fetch_company_from_isin_backup() -> pd.DataFrame:
    try:
        tables = pd.read_html(ISIN_URL)
    except Exception as e:
        print("ISIN backup fetch failed:", e)
        return pd.DataFrame(columns=["code", "name"])

    t = tables[0].copy()
    t.columns = t.iloc[0]
    t = t[1:].rename(columns=lambda x: str(x).strip())

    def split_code_name(x):
        s = str(x)
        m = re.match(r"^(\d{4})\s+(.+)$", s)
        if m:
            return m.group(1), m.group(2)
        return "", s

    t["code"], t["name"] = zip(*t["有價證券代號及名稱"].map(split_code_name))
    out = t[["code", "name"]]
    out = out[out["code"].str.fullmatch(r"\d{4}")]
    return out.drop_duplicates(subset=["code"]).reset_index(drop=True)


@lru_cache(maxsize=1)
def load_company_table() -> pd.DataFrame:
    """
    1순위: 로컬 파일(data/t187ap03_L.*)
    2순위: TWSE openapi (온라인)
    3순위: ISIN 백업
    그래도 다 실패하면 빈 테이블
    """
    # 1) 로컬 파일 우선
    try:
        print(f"Loading company table from local file: {LOCAL_COMPANY_FILE}")
        return _load_company_from_local()
    except Exception as e0:
        print("Local company file load failed:", e0)

    # 2) 온라인 openapi (Streamlit Cloud에서 막혀 있을 수도 있음)
    try:
        print("Trying TWSE openapi...")
        return _fetch_company_from_openapi()
    except Exception as e1:
        print("OpenAPI fetch failed:", e1)

    # 3) ISIN 백업
    try:
        print("Trying ISIN backup...")
        return _fetch_company_from_isin_backup()
    except Exception as e2:
        print("ISIN backup fetch failed:", e2)

    # 4) 결국 전부 실패하면 빈 테이블
    print("All sources failed. Returning empty company table.")
    return pd.DataFrame(columns=["code", "name"])


def search_code(keyword: str) -> pd.DataFrame:
    t = load_company_table()
    k = (keyword or "").strip().lower().replace("\u3000", " ")
    if t.empty:
        # 회사 테이블 자체가 비어 있으면 바로 빈 결과
        return t.copy()

    m = t["name"].str.lower().str.contains(k, na=False) | t["code"].str.contains(k, na=False)
    return t[m].copy()
