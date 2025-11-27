# services/company.py
import re
from functools import lru_cache
from pathlib import Path
import pandas as pd

# 로컬 JSON 파일 경로 설정
# 예: project_root/data/t187ap03_L.json
LOCAL_JSON = Path(__file__).resolve().parent.parent / "data" / "t187ap03_L.json"

def _normalize_company_df(df: pd.DataFrame) -> pd.DataFrame:
    """열 이름 정리 후 code/name만 깔끔하게 뽑기"""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    code_candidates = [
        c for c in df.columns
        if ("公司代號" in c)
        or ("證券代號" in c)
        or (str(c).lower() == "code")
    ]
    name_candidates = [
        c for c in df.columns
        if ("公司名稱" in c)
        or ("證券名稱" in c)
        or (str(c).lower() == "name")
    ]

    if not code_candidates or not name_candidates:
        raise ValueError("회사 기본자료의 열 이름을 찾을 수 없습니다.")

    code_col = code_candidates[0]
    name_col = name_candidates[0]

    out = pd.DataFrame({
        "code": df[code_col].astype(str).str.replace(".0", "", regex=False).str.strip(),
        "name": df[name_col].astype(str).str.strip(),
    })

    # 4자리 숫자 코드만 남기기
    out = out[out["code"].str.fullmatch(r"\d{4}")]
    out = out.drop_duplicates(subset=["code"], keep="first").reset_index(drop=True)

    return out


@lru_cache(maxsize=1)
def load_company_table() -> pd.DataFrame:
    """로컬 JSON 파일만 읽어서 회사 테이블 생성"""
    if not LOCAL_JSON.exists():
        print(f"회사 기본자료 JSON 파일을 찾을 수 없습니다: {LOCAL_JSON}")
        return pd.DataFrame(columns=["code", "name"])

    try:
        df = pd.read_json(LOCAL_JSON)
        return _normalize_company_df(df)
    except Exception as e:
        print("JSON 로딩 실패:", e)
        return pd.DataFrame(columns=["code", "name"])


def search_code(keyword: str) -> pd.DataFrame:
    """회사 이름/코드 검색"""
    t = load_company_table()
    if t.empty:
        return t

    k = (keyword or "").strip().lower().replace("\u3000", " ")

    mask = (
        t["name"].str.lower().str.contains(k, na=False)
        | t["code"].str.contains(k, na=False)
    )

    return t[mask].copy()
