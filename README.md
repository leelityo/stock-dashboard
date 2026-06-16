# 股票自動推薦儀表板

跨平台（手機／電腦／跨瀏覽器）股票自動推薦儀表板，涵蓋**台股、美股、韓股、日本 ETF**。
資料全用免費來源，部署到免費雲端，手機隨時可開。

這是 **MVP 第一版**，已完成需求 1-1 ~ 1-6（推薦儀表板）。回測（第 2 階段）與自然語言新增條件（第 3 階段）為後續迭代。

---

## 架構

```
股票自動推薦儀表板/
├─ pipeline/                 # 資料抓取 + 評分 (Python，在有網路處執行)
│  ├─ config/
│  │  ├─ universe.yaml       # ★ 你的選股宇宙：族群、個股、質化評分
│  │  └─ weights.yaml        # ★ 推薦因子權重 (= 選股 criteria)
│  ├─ fetch.py               # yfinance(價量/forwardPE) + FinMind(融資) + Google News
│  ├─ score.py               # 推薦評分引擎 (實作需求 1-2 各因子)
│  ├─ run.py                 # 主流程 → web/data/dashboard.json
│  └─ requirements.txt
├─ web/
│  ├─ index.html             # 單檔前端 (手機/電腦/跨瀏覽器)
│  └─ data/dashboard.json    # pipeline 產出的資料 (已含範例)
├─ .github/workflows/update.yml  # 免費定時更新
└─ vercel.json               # Vercel 部署設定
```

**資料流**：`run.py` 抓資料、算分、排序 → 寫出 `dashboard.json` → 前端讀 JSON 顯示。
GitHub Actions 定時跑 `run.py` 並提交 JSON，達到「自動更新」。

---

## 快速開始（本機）

```bash
cd pipeline
pip install -r requirements.txt

python run.py --mock     # 先用合成資料看畫面 (免網路)
python run.py            # 抓真實資料 (需網路)

# 開前端：在專案根目錄起一個簡易伺服器
cd ../web && python -m http.server 8000
# 瀏覽器開 http://localhost:8000   (手機連同網路用電腦IP:8000)
```

> 直接雙擊 `index.html` 可能因瀏覽器安全限制讀不到 JSON，請用上面的 http.server。

---

## 部署到免費雲端

**前端（Vercel）**
1. 把整個資料夾推到 GitHub。
2. Vercel → New Project → 匯入此 repo → 直接 Deploy（`vercel.json` 已設好只發佈 `web/`）。
3. 取得網址，手機/電腦/任何瀏覽器都能開。

**自動更新（GitHub Actions）**
- `.github/workflows/update.yml` 已設定交易日定時跑 pipeline 並提交新的 `dashboard.json`。
- 進 repo 的 Settings → Actions 確認已啟用即可；也可在 Actions 頁手動觸發。
- Vercel 偵測到 commit 會自動重新部署，資料就更新了。

---

## 自訂（這就是「選股 criteria」）

**改選股名單**：編輯 `pipeline/config/universe.yaml`
- 新增/刪除族群與個股；`ticker` 用 yfinance 格式（台股 `.TW`／上櫃 `.TWO`／韓股 `.KS`／日股 `.T`／美股直接代號）。
- 台股要抓融資請填 `finmind_id`（數字代號）。
- 質化分數 `pricing_power`（定價權）、`competitiveness`（產業競爭力）、`news_reliability`（消息可靠度）1~5 分，由你判斷。

**改推薦邏輯**：編輯 `pipeline/config/weights.yaml`
- 每個因子的 `weight` 越大越重視；可正可負。
- `sharp_drop` 調整「外部急跌」的判定門檻；`moving_averages` 調整均線清單。

> ⚠️ `universe.yaml` 內標注「⚠️ 請核對代號」的 ETF（主動式 ETF、日股/韓股 ETF）請上線後確認代號正確。

---

## 推薦因子（需求 1-2 對應）

| 因子 | 說明 | 來源 |
|---|---|---|
| `below_ma` | 外部急跌跌破 5/10/20/60/120/240 日線 → 逢低加分 | yfinance |
| `near_main_support` | 接近主力支撐區（近期低點＋大量價位） | yfinance |
| `margin_reduction` | 融資減碼絕對金額與比例（浮額清洗） | FinMind（台股） |
| `forward_pe_vs_peers` | forward 本益比 vs 同族群中位數 | yfinance |
| `pricing_power` / `competitiveness` / `news_reliability` | 定價權／競爭力／消息來源 | 你維護 |

---

## 限制與注意

- 免費報價為**延遲約 15–20 分鐘**；融資/法人為**每日收盤更新**。要秒級即時需改接付費 API（架構已預留 `fetch.py`）。
- forward P/E 部分標的 Yahoo 可能缺值，會以中性分計算。
- 「定價權、產業競爭力」屬質化判斷，目前由你在 `universe.yaml` 評分；第 3 階段會用自然語言協助調整。

---

## Roadmap

- **第 1 階段（本版，已完成）**：族群推薦排序、即時(延遲)股價、新聞、熱門標的、Google 連結、台/美/韓/日標的。
- **第 2 階段**：歷史回測（多策略比重、對比大盤、不再平衡選項、top-N、自訂策略、個股歷史報酬率）。
- **第 3 階段**：自然語言新增/調整推薦 criteria（自動改 `weights.yaml` 或新增 custom 因子）。
```
