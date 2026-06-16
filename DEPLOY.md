# 部署指南（免費）

> 全部指令請在**你自己的 Mac 終端機**執行（有完整權限與網路）。
> 預估 10 分鐘完成上線。

---

## 步驟 0：重新初始化 git（清掉沙箱殘留鎖檔）

```bash
cd "/Users/bertlee/Claude/Projects/股票自動推薦儀表板"
rm -rf .git
git init
git add -A
git commit -m "feat: 股票自動推薦儀表板 MVP"
```

---

## 步驟 1：本機先確認能跑

```bash
# 抓真實資料（需網路）
cd pipeline
pip3 install -r requirements.txt
python3 run.py
# 開前端
cd ../web
python3 -m http.server 8000
```
瀏覽器開 http://localhost:8000 ，確認看得到儀表板與真實股價後，Ctrl+C 關掉。

---

## 步驟 2：推上 GitHub

**方法 A — 用 gh CLI（最快，若已安裝）**
```bash
cd "/Users/bertlee/Claude/Projects/股票自動推薦儀表板"
gh repo create stock-dashboard --public --source=. --remote=origin --push
```

**方法 B — 用網頁**
1. 到 https://github.com/new 建立一個 repo（例如 `stock-dashboard`），**不要**勾選 Add README。
2. 回終端機執行（網址換成你的）：
```bash
cd "/Users/bertlee/Claude/Projects/股票自動推薦儀表板"
git branch -M main
git remote add origin https://github.com/<你的帳號>/stock-dashboard.git
git push -u origin main
```

---

## 步驟 3：Vercel 部署前端（手機隨時可開）

1. 到 https://vercel.com → 用 GitHub 登入。
2. **Add New → Project** → 匯入剛剛的 repo。
3. 設定畫面**不用改任何東西**（`vercel.json` 已設定只發佈 `web/` 資料夾）→ **Deploy**。
4. 完成後會給你一個網址（例如 `https://stock-dashboard-xxx.vercel.app`），手機、電腦、任何瀏覽器都能開。

---

## 步驟 4：開啟自動更新（GitHub Actions）

1. 到你的 GitHub repo → **Settings → Actions → General**。
2. 確認 **Workflow permissions** 設為 **Read and write permissions**（這樣 bot 才能提交更新的資料）→ Save。
3. 到 **Actions** 分頁，若提示啟用就按啟用。
4. 點 **更新儀表板資料** workflow → **Run workflow** 手動跑一次測試。
5. 之後它會在台股/美股盤中時段自動抓資料、提交，Vercel 偵測到 commit 會自動重新部署。

> 排程時間可在 `.github/workflows/update.yml` 的 cron 調整（時間為 UTC）。

---

## 常見問題

- **Vercel 開起來空白 / 讀不到資料**：確認 repo 裡有 `web/data/dashboard.json`（步驟 1 跑過 `run.py` 就會有），且已 push。
- **Actions 紅燈（push 失敗）**：多半是步驟 4-2 沒設成 Read and write permissions。
- **想要秒級即時報價**：免費源是延遲約 15–20 分。要即時需在 `pipeline/fetch.py` 改接付費 API（Fugle、券商 API、Polygon 等）。
