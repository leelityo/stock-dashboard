"""
資料抓取層 (免費資料源)
- 價量 / forward P/E : yfinance (Yahoo Finance)
- 台股融資融券 / 法人 : FinMind 免費 API
- 產業新聞           : Google News RSS

註：本檔需在「有網路」的環境執行 (你的電腦 / GitHub Actions / 雲端)。
"""
from __future__ import annotations
import datetime as dt
import time
import xml.etree.ElementTree as ET
import urllib.parse
import urllib.request

import pandas as pd
import yfinance as yf

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
# 可選：到 https://finmindtrade.com 註冊取得免費 token，放這裡可提高額度
FINMIND_TOKEN = ""


# ---------------------------------------------------------------------------
# 價量
# ---------------------------------------------------------------------------
def fetch_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """回傳含 OHLCV 的日線 DataFrame（抓不到回傳空表）。"""
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns=str.title)  # Open/High/Low/Close/Volume
        return df
    except Exception as e:  # noqa: BLE001
        print(f"[price] {ticker} 失敗: {e}")
        return pd.DataFrame()


def fetch_quote_info(ticker: str) -> dict:
    """即時(延遲)報價與基本面欄位。"""
    out = {"price": None, "prev_close": None, "forward_pe": None,
           "trailing_pe": None, "currency": None, "market_cap": None}
    try:
        t = yf.Ticker(ticker)
        # fast_info 較穩定
        fi = getattr(t, "fast_info", {}) or {}
        out["price"] = fi.get("last_price")
        out["prev_close"] = fi.get("previous_close")
        out["currency"] = fi.get("currency")
        out["market_cap"] = fi.get("market_cap")
        # info 提供 forward PE（部分標的可能缺）
        try:
            info = t.get_info()
            out["forward_pe"] = info.get("forwardPE")
            out["trailing_pe"] = info.get("trailingPE")
            if out["price"] is None:
                out["price"] = info.get("currentPrice")
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        print(f"[quote] {ticker} 失敗: {e}")
    return out


# ---------------------------------------------------------------------------
# 台股融資 (FinMind)
# ---------------------------------------------------------------------------
def fetch_margin(finmind_id: str, days: int = 30) -> pd.DataFrame:
    """台股融資融券。回傳近 days 天資料 (抓不到回傳空表)。"""
    if not finmind_id:
        return pd.DataFrame()
    start = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    params = {
        "dataset": "TaiwanStockMarginPurchaseShortSale",
        "data_id": finmind_id,
        "start_date": start,
    }
    if FINMIND_TOKEN:
        params["token"] = FINMIND_TOKEN
    url = FINMIND_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            import json
            data = json.loads(r.read().decode())
        rows = data.get("data", [])
        return pd.DataFrame(rows)
    except Exception as e:  # noqa: BLE001
        print(f"[margin] {finmind_id} 失敗: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# 新聞 (Google News RSS)
# ---------------------------------------------------------------------------
def fetch_news(query: str, limit: int = 5, lang: str = "zh-TW", country: str = "TW") -> list[dict]:
    """回傳 [{title, link, published}] 。"""
    q = urllib.parse.quote(query)
    url = (f"https://news.google.com/rss/search?q={q}"
           f"&hl={lang}&gl={country}&ceid={country}:{lang}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            root = ET.fromstring(r.read())
        items = []
        for it in root.iter("item"):
            items.append({
                "title": (it.findtext("title") or "").strip(),
                "link": (it.findtext("link") or "").strip(),
                "published": (it.findtext("pubDate") or "").strip(),
            })
            if len(items) >= limit:
                break
        return items
    except Exception as e:  # noqa: BLE001
        print(f"[news] {query} 失敗: {e}")
        return []


def google_search_link(name: str) -> str:
    """個股 Google 查詢超連結 (需求 1-6)。"""
    return "https://www.google.com/search?q=" + urllib.parse.quote(f"{name} 股票")


def polite_sleep(sec: float = 0.4):
    time.sleep(sec)
