"""
主流程：讀設定 → 抓資料 → 評分 → 產出 web/data/dashboard.json
用法：
    python run.py            # 正式抓真實資料 (需網路)
    python run.py --mock     # 用合成資料產生範例 JSON (無需網路，供測試/展示)
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import os
import random

import pandas as pd
import yaml

import score as S

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "config")
OUT = os.path.normpath(os.path.join(HERE, "..", "web", "data", "dashboard.json"))


def load_yaml(name):
    with open(os.path.join(CFG, name), encoding="utf-8") as f:
        return yaml.safe_load(f)


# --------------------------- 合成資料 (mock) ---------------------------
def mock_price(seed: int) -> pd.DataFrame:
    random.seed(seed)
    n = 260
    base = random.uniform(50, 900)
    closes, vols = [], []
    p = base
    for i in range(n):
        p *= (1 + random.gauss(0.0003, 0.02))
        closes.append(p)
        vols.append(random.uniform(1e6, 5e7))
    # 製造最後幾天的急跌情境給部分標的
    if seed % 3 == 0:
        for k in range(1, 6):
            closes[-k] = closes[-6] * (1 - 0.03 * (6 - k))
    idx = pd.date_range(end=dt.date.today(), periods=n)
    df = pd.DataFrame({"Open": closes, "High": [c * 1.01 for c in closes],
                       "Low": [c * 0.98 for c in closes], "Close": closes,
                       "Volume": vols}, index=idx)
    return df


def mock_margin(seed: int) -> pd.DataFrame:
    random.seed(seed + 99)
    bal = [random.uniform(20000, 80000)]
    for _ in range(29):
        bal.append(bal[-1] * (1 + random.gauss(-0.004, 0.01)))  # 偏向減碼
    return pd.DataFrame({"MarginPurchaseTodayBalance": bal})


# --------------------------- 主流程 ---------------------------
def build(mock: bool):
    universe = load_yaml("universe.yaml")
    wcfg = load_yaml("weights.yaml")
    weights = wcfg["weights"]
    ma_list = wcfg["moving_averages"]
    sharp_cfg = wcfg["sharp_drop"]
    total_ma = len(ma_list)

    if not mock:
        import fetch as F  # 延遲匯入，mock 模式不需 yfinance

    groups_out = {}
    all_for_hotness = []
    sid = 0

    for gname, stocks in universe["groups"].items():
        rows = []
        for st in stocks:
            sid += 1
            ticker, name, fid = st["ticker"], st["name"], st.get("finmind_id", "")
            if mock:
                price = mock_price(sid)
                margin = mock_margin(sid) if fid else pd.DataFrame()
                fpe = round(random.uniform(8, 35), 1)
                news = [{"title": f"{name} 範例新聞 {k+1}",
                         "link": "https://news.google.com",
                         "published": ""} for k in range(2)]
                glink = "https://www.google.com/search?q=" + name + "+股票"
                quote = {"price": float(price["Close"].iloc[-1]),
                         "prev_close": float(price["Close"].iloc[-2]),
                         "currency": "TWD", "forward_pe": fpe}
            else:
                price = F.fetch_price_history(ticker, "1y")
                quote = F.fetch_quote_info(ticker)
                margin = F.fetch_margin(fid) if fid else pd.DataFrame()
                news = F.fetch_news(name, limit=3)
                glink = F.google_search_link(name)
                fpe = quote.get("forward_pe")
                F.polite_sleep()

            ind = S.compute_indicators(price, ma_list, sharp_cfg)
            msig = S.compute_margin_signal(margin)
            price_now = quote.get("price") or ind.get("price")
            chg = None
            if price_now and quote.get("prev_close"):
                chg = round((price_now / quote["prev_close"] - 1) * 100, 2)

            rows.append({
                "ticker": ticker, "name": name, "google": glink,
                "price": round(price_now, 3) if price_now else None,
                "change_pct": chg, "currency": quote.get("currency"),
                "forward_pe": fpe,
                "ind": ind, "margin": msig,
                "pricing_power": st.get("pricing_power"),
                "competitiveness": st.get("competitiveness"),
                "news_reliability": st.get("news_reliability"),
                "news": news,
            })

        ranked = S.score_group(rows, weights, total_ma)
        # 精簡輸出 (移除大物件，前端只需摘要)
        for r in ranked:
            r["ma"] = r["ind"].get("ma", {})
            r["below_ma"] = r["ind"].get("below_ma", [])
            r["sharp_drop"] = r["ind"].get("sharp_drop")
            r["drop_pct"] = r["ind"].get("drop_pct")
            r["dist_to_support_pct"] = r["ind"].get("dist_to_support_pct")
            r["support"] = r["ind"].get("support")
            r["ret_60d"] = r["ind"].get("ret_60d")
            r["margin_change"] = r["margin"].get("margin_change")
            r["margin_change_pct"] = r["margin"].get("margin_change_pct")
            del r["ind"], r["margin"]
            all_for_hotness.append({**r, "group": gname})
        groups_out[gname] = ranked

    # 過去幾週熱門 (依 60 日報酬近似；前端可改週數重排)
    hot = sorted([s for s in all_for_hotness if s.get("ret_60d") is not None],
                 key=lambda x: x["ret_60d"], reverse=True)[:15]

    out = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "mock": mock,
        "weights": weights,
        "hotness_default_weeks": wcfg["hotness"]["default_weeks"],
        "groups": groups_out,
        "hottest": hot,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"已輸出 {OUT}  (mock={mock})  族群數={len(groups_out)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="用合成資料 (無需網路)")
    build(ap.parse_args().mock)
