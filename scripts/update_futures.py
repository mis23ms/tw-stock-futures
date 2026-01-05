import json, requests, time, os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

F_STOCKS = [("2330", "台積電"), ("2317", "鴻海"), ("3231", "緯創"), ("2382", "廣達")]
F_MAP = {"2330": "CDF", "2317": "CHF", "3231": "CKF", "2382": "CMF"}
TAIFEX_URL = "https://www.taifex.com.tw/cht/3/largeTraderFutQry"

def clean_int(s):
    try:
        return int(str(s).replace(",", "").strip())
    except:
        return 0

def fetch_data(ticker, date_s):
    f_code = F_MAP.get(ticker)
    try:
        q_date = f"{date_s[0:4]}/{date_s[4:6]}/{date_s[6:8]}"
        payload = {"queryDate": q_date, "commodityId": f_code}
        r = requests.post(TAIFEX_URL, data=payload, timeout=20)
        
        if "查無資料" in r.text:
            return {"error": "期交所今日尚無資料"}
            
        soup = BeautifulSoup(r.text, "lxml")
        table = soup.find("table", class_="table_f")
        rows = table.find_all("tr") if table else []
        
        # 尋找「所有契約」彙總列
        all_row = None
        for tr in rows:
            if "所有契約" in tr.get_text():
                all_row = tr
                break
        
        if not all_row:
            return {"error": "找不到數據匯總列"}
            
        cols = [td.get_text(strip=True) for td in all_row.find_all("td")]
        if len(cols) < 10: return {"error": "表格欄位異常"}

        # 索引 2:五多, 3:五空, 5:十多, 6:十空, 9:總未平倉
        t5b, t5s = clean_int(cols[2]), clean_int(cols[3])
        t10b, t10s = clean_int(cols[5]), clean_int(cols[6])
        
        return {
            "top5": {"buy": t5b, "sell": t5s, "net": t5b - t5s},
            "top10": {"buy": t10b, "sell": t10s, "net": t10b - t10s},
            "oi": cols[9]
        }
    except Exception as e:
        return {"error": "連線或格式異常"}

def main():
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    # 若在 16:00 前跑，則抓前一天的盤後資料
    if now.hour < 16: now -= timedelta(days=1)
    date_s = now.strftime("%Y%m%d")

    results = []
    for t, n in F_STOCKS:
        print(f"抓取 {n}...")
        res = fetch_data(t, date_s)
        results.append({"ticker": t, "name": n, "data": res})
        time.sleep(2)

    os.makedirs("docs", exist_ok=True)
    with open("docs/futures_data.json", "w", encoding="utf-8") as f:
        json.dump({"date": date_s, "items": results}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
