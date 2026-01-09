import json, requests, time, os, re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# 你要的四檔（用「表格上的契約名稱」做精準比對）
TARGETS = [
    {"ticker": "2330", "name": "台積電期貨", "contract": "台積電期貨"},
    {"ticker": "2317", "name": "鴻海期貨",   "contract": "鴻海期貨"},
    {"ticker": "3231", "name": "緯創期貨",   "contract": "緯創期貨"},
    {"ticker": "2382", "name": "廣達期貨",   "contract": "廣達期貨"},
]

# ✅ 改抓「靜態表」：不需要 JS、不需要下拉選單參數
TAIFEX_TBL_URL = "https://www.taifex.com.tw/cht/3/largeTraderFutQryTbl"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def first_int(s: str) -> int:
    m = re.search(r"-?\d+", s.replace(",", ""))
    return int(m.group(0)) if m else 0

def parse_table(html: str):
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return {"error": "找不到表格(table)"}

    rows = table.find_all("tr")
    found = {}
    current_contract = None

    want = {t["contract"] for t in TARGETS}

    for tr in rows:
        tds = tr.find_all(["td", "th"])
        cols = [td.get_text(strip=True) for td in tds]
        if not cols:
            continue

        # 契約名稱通常會在第一欄（可能有 rowspan）
        # 這張表的格式：第一欄可能是「契約」，第二欄「交易人種類」等
        # 我們用最保守方式：如果某格包含「期貨」字樣且不是「所有契約」，就當作契約名稱
        for c in cols:
            if ("期貨" in c) and ("所有" not in c) and ("契約" not in c) and (len(c) <= 20):
                current_contract = c
                break

        # 「所有契約」那列（contract 名稱通常靠 rowspan 在上一列，所以要用 current_contract）
        if any(("所有" in x and "契約" in x) for x in cols):
            if current_contract in want and current_contract not in found:
                # 這列固定長這樣：
                # [0]=所有契約
                # [1]=買方前五(部位數+括號)
                # [3]=買方前十
                # [5]=賣方前五
                # [7]=賣方前十
                # [9]=全市場未沖銷部位數
                if len(cols) < 10:
                    found[current_contract] = {"error": f"表格欄位不足(len={len(cols)})"}
                    continue

                t5b = first_int(cols[1])
                t10b = first_int(cols[3])
                t5s = first_int(cols[5])
                t10s = first_int(cols[7])
                oi = first_int(cols[9])

                found[current_contract] = {
                    "top5":  {"buy": t5b,  "sell": t5s,  "net": t5b - t5s},
                    "top10": {"buy": t10b, "sell": t10s, "net": t10b - t10s},
                    "oi": oi,
                }

    # 確保每個目標都有結果
    for t in want:
        if t not in found:
            found[t] = {"error": "找不到該契約（可能名稱變動或當日無資料）"}

    return found

def main():
    tz_tw = timezone(timedelta(hours=8))
    today = datetime.now(tz_tw)

    # 交易所多半用「交易日」概念；如果你要抓「昨天」可自行改
    date_s = today.strftime("%Y%m%d")

    try:
        r = requests.get(TAIFEX_TBL_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        out = {"date": date_s, "items": [], "error": f"抓取失敗：{e}"}
        os.makedirs("docs", exist_ok=True)
        with open("docs/futures_data.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        return

    found = parse_table(r.text)

    items = []
    for t in TARGETS:
        c = t["contract"]
        items.append({
            "ticker": t["ticker"],
            "name": t["name"],
            "data": found.get(c, {"error": "未知錯誤"})
        })

    # --- 新增：保留最近 7 天歷史（給「一週變化」用） ---
    tz_tw = timezone(timedelta(hours=8))
    today_ymd = date_s or datetime.now(tz_tw).strftime("%Y%m%d")

    snapshot = {
        "date": today_ymd,
        "items": items,
    }

    history_file = "docs/futures_data.json"
    history = []

    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                old = json.load(f)
            history = old.get("history", [])
        except Exception:
            history = []

    # 去掉同一天（避免 Actions 重跑造成重複）
    history = [h for h in history if isinstance(h, dict) and h.get("date") != today_ymd]

    # 今天放最前面
    history.insert(0, snapshot)

    # 只留最近 7 天
    history = history[:7]

    out = {
        "date": today_ymd,
        "items": items,
        "update_time": datetime.now(tz_tw).isoformat(timespec="seconds"),
        "history": history,
    }

    # ⚠️ 輸出位置要跟你的 index.html 同資料夾
    os.makedirs("docs", exist_ok=True)
    with open("docs/futures_data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

