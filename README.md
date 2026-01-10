# tw-stock-futures
Taiwan 4 key stock vs futures contact
把下面整段 **直接覆蓋貼到 `README.md`** 就好：

```md
# tw-stock-futures

Demo（GitHub Pages）  
https://mis23ms.github.io/tw-stock-futures/

台灣期貨資料自動更新 + 網頁展示（靜態站）。

---

## 目前進度（已完成）
- ✅ GitHub Actions 可跑、可寫回 repo（綠燈）
- ✅ 產出 `docs/futures_data.json`（含每日快照 / history 累積）
- ✅ Pages 用 `docs/` 發佈（`docs/index.html`）

---

## 自動更新（不用手動）
Workflow：`.github/workflows/update.yml`

目前排程：
- `cron: "20 9 * * 1-5"`（UTC）= 台北時間 **週一～週五 17:20** 自動跑一次
- 想改成每天（含六日）→ 把 `1-5` 改成 `*`

跑完會：
1) 執行 `scripts/update_futures.py`
2) 更新 `docs/futures_data.json`
3) commit 回 repo（commit 會顯示 `github-actions[bot] Update futures data`）
4) Pages 重新部署

---

## 資料檔（前端讀這個）
- `docs/futures_data.json`
  - `update_time`：最近更新時間
  - `history`：最近 N 天快照（目前做法是保留近 7 筆）

---

## 專案結構
```

.github/workflows/
update.yml          # Actions 排程 + 執行腳本 + 寫回 repo
docs/
index.html          # Pages 網站入口
futures_data.json   # 產出的資料（含 history）
scripts/
update_futures.py   # 抓取/解析/輸出 JSON（含 history 累積）
requirements.txt      # Python 依賴
README.md

```

---

## 手動跑一次（測試用）
Repo → Actions → `Update Futures` → Run workflow
```

如果你要我再加「其他期貨品項」也一樣最省事：你只要丟我**你想加的品項清單（用逗號）**，我就直接把 `scripts/update_futures.py` 改成「加一行就會多抓一個」。
