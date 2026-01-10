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

def first_int(text: str) -> int:
    m = re.search(r"[-\d,]+", text or "")
    return int(m.group(0).replace(",", "")) if m else 0

def norm_cell(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True))

def fetch_table_html(timeout=25) -> str:
    r = requests.get(TAIFEX_TBL_URL, headers=HEADERS, timeout=timeout)
    r.encoding = "utf-8"
    return r.text

def parse_targets(html: str):
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="table_f")
    if not table:
        return None, {t["contract"]: {"error": "找不到 TAIFEX 表格(table_f)"} for t in TARGETS}

    # 從頁面抓日期（YYYY/MM/DD）
    m = re.search(r"\d{4}/\d{2}/\d{2}", html)
    date_ymd = m.group(0) if m else ""
    date_s = date_ymd.replace("/", "") if date_ymd else ""

    want = {t["contract"] for t in TARGETS}
    found = {}  # contract -> data
    current_contract = None

    rows = table.find_all("tr")
    for tr in rows:
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        cols = [norm_cell(c) for c in cells]
        if not cols:
            continue

        # 新契約段落開始：第一欄含「期貨」，但不是「所有契約」，也不是年月列
        if (
            "期貨" in cols[0]
            and "所有" not in cols[0]
            and not re.match(r"^\d{4}\s*\d{2}", cols[0])
        ):
            current_contract = cols[0]

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
                    "top5": {"buy": t5b, "sell": t5s, "net": t5b - t5s},
                    "top10": {"buy": t10b, "sell": t10s, "net": t10b - t10s},
                    "oi": str(oi),
                    "contract_month": "所有契約",
                }

    # 沒抓到的補 error
    for t in TARGETS:
        c = t["contract"]
        if c not in found:
            found[c] = {"error": "找不到該契約的『所有契約』列（可能當日尚未出或版面變動）"}

    return date_s, found

def main():
    # ✅ 日期不靠自己推算，直接以 TAIFEX 表上顯示的日期為準
    html = fetch_table_html()
    date_s, found = parse_targets(html)

    items = []
    for t in TARGETS:
        c = t["contract"]
        items.append({
            "ticker": t["ticker"],
            "name": t["name"],
            "data": found.get(c, {"error": "未知錯誤"})
        })

    out = {"date": date_s or "", "items": items}


  # --- 近 30 日累積（history）---
    tz_tw = timezone(timedelta(hours=8))
    today = date_s or datetime.now(tz_tw).strftime("%Y%m%d")
    snapshot = {"date": today, "items": items}

    history_file = "docs/futures_data.json"
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                old = json.load(f)
            history = old.get("history", [])
        except Exception:
            history = []

    # 去重（同一天只留最新一筆）
    history = [h for h in history if isinstance(h, dict) and h.get("date") != today]
    history.insert(0, snapshot)
    history = history[:30]

    out["update_time"] = datetime.now(tz_tw).isoformat(timespec="seconds")
    out["history"] = history

    # ⚠️ 輸出位置要跟你的 index.html 同資料夾
    # 如果你的 GitHub Pages 是用 /docs 當來源：就維持 docs/
    os.makedirs("docs", exist_ok=True)
    with open("docs/futures_data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()



