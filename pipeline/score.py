"""
推薦評分引擎 (純計算，無網路)
實作需求 1-2 的各項因子，並在族群內排序。
所有因子先正規化到 0~1，再依 weights.yaml 加權加總。
"""
from __future__ import annotations
import statistics
import pandas as pd


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# 技術指標
# ---------------------------------------------------------------------------
def compute_indicators(price: pd.DataFrame, ma_list, sharp_cfg) -> dict:
    """從日線價量算出均線、跌破狀態、急跌、主力支撐估計。"""
    out = {"price": None, "ma": {}, "below_ma": [], "below_count": 0,
           "sharp_drop": False, "drop_pct": None, "dev20": None,
           "support": None, "dist_to_support_pct": None,
           "ret_60d": None}
    if price is None or price.empty or "Close" not in price:
        return out
    close = price["Close"].dropna()
    if len(close) < 5:
        return out
    last = float(close.iloc[-1])
    out["price"] = last

    # 均線與跌破
    for m in ma_list:
        if len(close) >= m:
            val = float(close.tail(m).mean())
            out["ma"][str(m)] = round(val, 3)
            if last < val:
                out["below_ma"].append(m)
    out["below_count"] = len(out["below_ma"])

    # 急跌 (近 lookback 日累計報酬)
    lb = int(sharp_cfg.get("lookback_days", 5))
    if len(close) > lb:
        drop = (last / float(close.iloc[-lb - 1]) - 1) * 100
        out["drop_pct"] = round(drop, 2)
        out["sharp_drop"] = drop <= float(sharp_cfg.get("drop_pct_threshold", -8.0))

    # 20MA 乖離
    if "20" in out["ma"]:
        out["dev20"] = round((last / out["ma"]["20"] - 1) * 100, 2)

    # 主力支撐：近 60 日成交量最大那天的收盤 + 近 60 日低點，取較高者為支撐參考
    window = price.tail(60)
    try:
        vol_day_close = float(window.loc[window["Volume"].idxmax(), "Close"])
        low60 = float(window["Low"].min())
        support = max(low60, vol_day_close * 0.97)
        out["support"] = round(support, 3)
        out["dist_to_support_pct"] = round((last / support - 1) * 100, 2)
    except Exception:  # noqa: BLE001
        pass

    if len(close) >= 60:
        out["ret_60d"] = round((last / float(close.iloc[-60]) - 1) * 100, 2)
    return out


def compute_margin_signal(margin: pd.DataFrame) -> dict:
    """融資減碼：期間融資餘額變化的絕對張數與比例 (僅台股)。"""
    out = {"margin_balance": None, "margin_change": None, "margin_change_pct": None}
    if margin is None or margin.empty:
        return out
    col = "MarginPurchaseTodayBalance"
    if col not in margin.columns:
        return out
    s = pd.to_numeric(margin[col], errors="coerce").dropna()
    if len(s) < 2:
        return out
    start, end = float(s.iloc[0]), float(s.iloc[-1])
    out["margin_balance"] = end
    out["margin_change"] = end - start            # 負值=減碼
    if start > 0:
        out["margin_change_pct"] = round((end - start) / start * 100, 2)
    return out


# ---------------------------------------------------------------------------
# 各因子正規化 (0~1)
# ---------------------------------------------------------------------------
def factor_below_ma(ind, total_ma) -> float:
    if total_ma == 0:
        return 0.0
    ratio = ind["below_count"] / total_ma
    return _clamp(ratio * (1.0 if ind["sharp_drop"] else 0.5))


def factor_near_support(ind) -> float:
    d = ind.get("dist_to_support_pct")
    if d is None:
        return 0.0
    # 距支撐 0% → 1 分；距支撐 +15% 以上 → 0 分；跌破支撐略扣
    return _clamp(1 - d / 15.0)


def factor_not_overextended(ind) -> float:
    dev = ind.get("dev20")
    if dev is None:
        return 0.5
    return _clamp(1 - dev / 20.0)


def factor_margin_reduction(msig) -> float:
    pct = msig.get("margin_change_pct")
    if pct is None:
        return 0.0
    # 減碼 10% → 滿分；增加 → 0
    return _clamp(-pct / 10.0)


def factor_qualitative(v) -> float:
    return _clamp((v or 0) / 5.0)


# ---------------------------------------------------------------------------
# 族群評分 + 排序
# ---------------------------------------------------------------------------
def score_group(stocks: list[dict], weights: dict, total_ma: int) -> list[dict]:
    """stocks 每筆需含 ind / margin / forward_pe / 質化分數。回傳排序後清單。"""
    pes = [s["forward_pe"] for s in stocks if isinstance(s.get("forward_pe"), (int, float)) and s["forward_pe"] > 0]
    pe_median = statistics.median(pes) if pes else None

    for s in stocks:
        ind, msig = s["ind"], s["margin"]
        f = {}
        f["below_ma"] = factor_below_ma(ind, total_ma)
        f["near_main_support"] = factor_near_support(ind)
        f["not_overextended"] = factor_not_overextended(ind)
        f["margin_reduction"] = factor_margin_reduction(msig)

        # forward PE vs 同族群中位數：低於中位數加分
        pe = s.get("forward_pe")
        if pe and pe > 0 and pe_median:
            f["forward_pe_vs_peers"] = _clamp((pe_median - pe) / pe_median + 0.5)
        else:
            f["forward_pe_vs_peers"] = 0.5

        f["pricing_power"] = factor_qualitative(s.get("pricing_power"))
        f["competitiveness"] = factor_qualitative(s.get("competitiveness"))
        f["news_reliability"] = factor_qualitative(s.get("news_reliability"))

        total = sum(weights.get(k, 0) * v for k, v in f.items())
        s["factors"] = {k: round(v, 3) for k, v in f.items()}
        s["score"] = round(total, 4)

    stocks.sort(key=lambda x: x["score"], reverse=True)
    for i, s in enumerate(stocks, 1):
        s["rank"] = i
    return stocks
