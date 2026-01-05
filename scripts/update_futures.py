import json, requests, time, os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# --- 設定區 ---
FUTURES_MAP = {"2330": "CDF", "2317": "CHF", "3231": "CKF", "2382": "CMF"} [cite: 15]
F_NAMES = {"2330": "台積電期貨", "2317": "鴻海期貨", "3231": "緯創期貨", "2382": "廣達期貨"} [cite: 57]
TAIFEX_URL = "https://www.taifex.com.tw/cht/3/ssoBigTraders" [cite: 14]

def clean_int(s):
    """移除逗號並安全轉為整數"""
    try:
        return int(str(s).replace(",", "").strip())
    except:
        return 0

def fetch_futures_data(ticker, date_s):
    f_code = FUTURES_MAP.get(ticker)
    try:
        # 轉換日期格式 YYYY/MM/DD
        query_date = f"{date_s[0:4]}/{date_s[4:6]}/{date_s[6:8]}"
        payload = {"queryDate": query_date, "commodityId": f_code}
        r = requests.post(TAIFEX_URL, data=payload, timeout=20)
        
        if "查無資料" in r.text: return {"error": "尚未提供資料"} [cite: 20, 60]
        
        soup = BeautifulSoup(r.text, "lxml")
        table = soup.find("table", class_="table_f")
        rows = table.find_all("tr")
        
        # 找尋「所有契約」彙總列 
        all_row = next((tr for tr in rows if "所有契約" in tr.get_text()), None)
        if not all_row: return {"error": "格式變動"}
        
        cols = [td.get_text(strip=True) for td in all_row.find_all("td")]
        # 索引：2:五多, 3:五空, 5:十多, 6:十空, 9:未平倉量 [cite: 17-19]
        top5_buy, top5_sell = clean_int(cols[2]), clean_int(cols[3])
        top10_buy, top10_sell = clean_int(cols[5]), clean_int(cols[6])
        
        return {
            "top5": {"buy": top5_buy, "sell": top5_sell, "net": top5_buy - top5_sell},
            "top10": {"buy": top10_buy, "sell": top10_sell, "net": top10_buy - top10_sell},
            "oi": cols[9]
        }
    except Exception as e:
        return {"error": f"抓取異常: {str(e)}"} [cite: 76]

def main():
    # 取得台北時間 
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    if now.hour < 16: now -= timedelta(days=1)
    date_s = now.strftime("%Y%m%d")

    results = []
    for ticker, name in F_NAMES.items():
        print(f"正在處理 {name}...")
        data = fetch_futures_data(ticker, date_s)
        results.append({"ticker": ticker, "name": name, "data": data})
        time.sleep(2)

    # 確保 docs 目錄存在
    os.makedirs("docs", exist_ok=True)
    with open("docs/futures_data.json", "w", encoding="utf-8") as f:
        json.dump({"date": date_s, "items": results}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
