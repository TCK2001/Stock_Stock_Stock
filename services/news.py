# services/news.py
from collections import OrderedDict, defaultdict
from datetime import datetime, date
from typing import Dict, List
import time
import urllib.parse

import feedparser
from bs4 import BeautifulSoup

def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"

def _clean_summary(html: str) -> str:
    # RSS summary에서 태그 제거 + 공백 정리
    soup = BeautifulSoup(html or "", "html.parser")
    txt = " ".join(soup.get_text(" ").split())
    return txt

def fetch_monthly_top_news(
    keyword: str,
    start_d: date,
    end_d: date,
    per_month: int = 5,
    lang_region: str = "zh-TW",   # Google News 표시 언어
    geo: str = "TW"               # Google News 지역
) -> "OrderedDict[str, List[dict]]":
    """
    Google News RSS에서 keyword 관련 뉴스를 가져와
    [YYYY-MM] → [{title, link, published, summary}] 형태로 월별 상위 N개 반환
    """
    # 1) RSS 요청 (Google News RSS)
    print(keyword)
    q = urllib.parse.quote(keyword.strip())
    print(q)
    rss_url = f"https://news.google.com/rss/search?q={q}&hl={lang_region}&gl={geo}&ceid={geo}:{'zh-Hant'}"
    print("url : ",rss_url)
    feed = feedparser.parse(rss_url)

    # 2) 기간 필터링
    items = []
    for e in feed.entries:
        # published_parsed가 없으면 스킵
        if not getattr(e, "published_parsed", None):
            continue
        pub_dt = datetime.fromtimestamp(time.mktime(e.published_parsed))
        pub_d = pub_dt.date()
        if not (start_d <= pub_d <= end_d):
            continue

        link = getattr(e, "link", "")
        title = getattr(e, "title", "")
        summary_html = getattr(e, "summary", "")
        summary = _clean_summary(summary_html)

        items.append({
            "title": title,
            "link": link,
            "published": pub_dt,
            "summary": summary,
            "month": _month_key(pub_d)
        })

    # 3) 월별 그룹 → 최신순 정렬 → 상위 N개
    by_month: Dict[str, List[dict]] = defaultdict(list)
    for it in items:
        by_month[it["month"]].append(it)

    # 월 키 정렬 (오래된 달 → 최신 달)
    month_keys = sorted(by_month.keys())
    out = OrderedDict()
    for mk in month_keys:
        # 최신순 정렬
        out[mk] = sorted(by_month[mk], key=lambda x: x["published"], reverse=True)[:per_month]

    return out
