```md
# tw-stock-futures（個股期貨大額交易人監控）

網站（GitHub Pages）  
https://mis23ms.github.io/tw-stock-futures/

每天自動更新資料 → 產出 `docs/futures_data.json` → 網頁讀 JSON 顯示卡片與「近 30 日變化」。

---

## 目前狀態
- ✅ Actions 綠燈可跑（抓資料 + 寫 JSON + commit 回 repo）
- ✅ Pages 已部署（`docs/`）
- ✅ history 改為保留 **30 天**（由後端控制）

---

## 專案結構（資料夾/檔案一覽）
```

.github/workflows/
update.yml              # GitHub Actions：排程、裝套件、跑 Python、commit 回 repo

docs/
index.html              # 網站本體（前端：讀 futures_data.json）
futures_data.json       # 自動產出的資料（網站讀這個）

scripts/
update_futures.py       # 後端：抓資料、解析、維護 history（近30天）、輸出 JSON

requirements.txt          # Python 依賴（requests/bs4/lxml 等）
README.md                 # 專案說明

````

---

## 它怎麼運作（白話）
1) Actions 到時間跑 `update.yml`  
2) `update.yml` 執行 `python scripts/update_futures.py`  
3) `update_futures.py` 產生/更新 `docs/futures_data.json`（包含 `history`）  
4) Actions 把更新 commit 回 repo  
5) Pages 讀到新 JSON，網站更新

---

## 自動更新排程（你目前設定）
在 `.github/workflows/update.yml`：

```yml
schedule:
  - cron: "20 9 * * 1-5"   # 台北時間 17:20（GitHub cron 用 UTC）
````

* `1-5`：週一～週五
* 想含六日就改 `*`（可選，不是必須）

---

## 近 30 日（history）怎麼控制

在 `scripts/update_futures.py`（你已改好）：

```py
history.insert(0, snapshot)   # 最新放最前
history = history[:30]        # ✅ 保留近 30 筆（約 30 個交易日/執行日）
```

注意：剛開始只會看到 1 筆、2 筆…要跑很多天才會累積到 30 筆。

---

## futures_data.json 重要欄位

`docs/futures_data.json`（前端讀這個）：

* `date`：資料日期（YYYYMMDD）
* `items`：今天的各標的資料
* `update_time`：更新時間（ISO 字串）
* `history`：近 30 筆快照（最新在最前）

---

## 常見坑（省時間）

### 1) Python 縮排最容易炸

* 全部用 **4 個空白**，不要混 Tab
* `NameError: date_s not defined` 幾乎都是那段 code 被貼到 `def main():` 外面（縮排層級錯）

### 2) 「綠燈但畫面文字不對」通常是前端文字寫死

* 你改成 30 天後，`docs/index.html` 的標題文字如果還寫「近 7 日」要**手動改文字**
* 同理，「每日 16:00/17:20 更新」那句也是文字，跟 workflow 不會自動同步

### 3) cron 是 UTC（不是台北時間）

看到時間怪，優先懷疑 cron 換算。

### 4) workflow 裡 `git add .` 可能提交多餘檔案（可選優化）

更穩可只 add：

* `docs/futures_data.json`
  （你要不要改都行，現在能跑就先別動）

---

## 如何 30 秒確認今天有沒有更新

1. 打開 `docs/futures_data.json`
2. 看：

* `update_time` 有沒有變新
* `history` 裡的第 1 筆日期是不是今天

---

## 手動跑一次（測試）

Repo → Actions → Update Futures → Run workflow
綠燈後再看 `docs/futures_data.json` 是否更新。

```

如果你要我再把「前端那句近7日」也一起對齊到 30 日：  
你不用貼整份 `index.html`，只要貼出「近 7 日變化」那一行文字所在的那一小段（前後各 2 行）我就能回你「改哪幾個字」。
::contentReference[oaicite:0]{index=0}
```


---

## 手動跑一次（測試用）
Repo → Actions → `Update Futures` → Run workflow
```

如果你要我再加「其他期貨品項」也一樣最省事：你只要丟我**你想加的品項清單（用逗號）**，我就直接把 `scripts/update_futures.py` 改成「加一行就會多抓一個」。
