#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch TAIFEX "large trader open interest structure" for selected single-stock futures,
write docs/futures_data.json for GitHub Pages, and keep a rolling 7-day history.

Why this exists:
- The "table" endpoint does not always include single-stock futures.
- This script queries the interactive page (POST) by contract code (e.g., CDF/DHF/DKF...).

Output (docs/futures_data.json):
{
  "date": "YYYYMMDD",
  "items": [
     {"name": "...", "stock": "2330", "code": "CDF", "data": {... or {"error": "..."} } }
  ],
  "history": [
     {"date": "YYYYMMDD", "items": [...] }, ... up to 7
  ]
}
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

TAIFEX_LARGE_TRADER_URL = "https://www.taifex.com.tw/cht/3/largeTraderFutQry"
TAIFEX_STOCK_FUTURES_LIST_URL = "https://www.taifex.com.tw/cht/2/stockMargining"

# You can edit this list freely (name is what shows on the page; stock is ticker).
TARGET_STOCKS = [
    {"stock": "2330", "name": "台積電期貨"},
    {"stock": "2317", "name": "鴻海期貨"},
    {"stock": "3231", "name": "緯創期貨"},
    {"stock": "2382", "name": "廣達期貨"},
]

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _to_int(s: str) -> int:
    """Extract first integer (supports commas and negative)."""
    m = re.search(r"-?\d[\d,]*", s.replace("\xa0", " "))
    return int(m.group(0).replace(",", "")) if m else 0


def _format_yyyymmdd(date_str: str) -> str:
    """
    Try to parse date from TAIFEX and format as YYYYMMDD.
    TAIFEX commonly uses YYYY/MM/DD; sometimes ROC year (e.g., 114/01/09).
    """
    date_str = date_str.strip()
    # YYYY/MM/DD
    m = re.search(r"(\d{4})/(\d{2})/(\d{2})", date_str)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"{y}{mo}{d}"
    # ROC: NNN/MM/DD
    m = re.search(r"(\d{2,3})/(\d{2})/(\d{2})", date_str)
    if m:
        roc_y, mo, d = int(m.group(1)), m.group(2), m.group(3)
        # ROC year + 1911
        y = roc_y + 1911
        return f"{y}{mo}{d}"
    # fallback
    return datetime.now().strftime("%Y%m%d")


def fetch_stock_futures_contract_map(session: requests.Session) -> Dict[str, str]:
    """
    Build mapping: stock ticker -> contract code (e.g., 2330 -> CDF)
    by parsing TAIFEX stockMargining list.
    """
    r = session.get(TAIFEX_STOCK_FUTURES_LIST_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    mp: Dict[str, str] = {}
    for tr in soup.find_all("tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not tds or len(tds) < 3:
            continue

        # Find a ticker like 2330 / 2317 / 3231...
        ticker = next((x for x in tds if re.fullmatch(r"\d{4}", x)), None)
        if not ticker:
            continue

        # Contract codes for single-stock futures are typically 3 chars and end with 'F' (e.g., CDF, DHF, DKF)
        code = next((x for x in tds if re.fullmatch(r"[A-Z0-9]{2,4}", x) and x.endswith("F")), None)
        if code:
            mp[ticker] = code

    return mp


def _post_large_trader(session: requests.Session, contract_code: str) -> str:
    """
    POST to the query page. TAIFEX has slightly different field names across revisions,
    so we send a superset and let the server ignore unknown fields.
    """
    payload_variants = [
        # Most common
        {"queryType": "1", "commodity_id": contract_code},
        {"queryType": "1", "commodityId": contract_code},
        # Superset (safe)
        {"queryType": "1", "commodity_id": contract_code, "commodityId": contract_code, "goDay": "", "dateaddcnt": "0", "queryDate": ""},
        # Some pages use 'commodity_id2' or 'commodity_idt' (rare)
        {"queryType": "1", "commodity_id2": contract_code, "commodity_id": contract_code},
    ]

    for payload in payload_variants:
        r = session.post(
            TAIFEX_LARGE_TRADER_URL,
            data=payload,
            headers={"User-Agent": UA, "Referer": TAIFEX_LARGE_TRADER_URL},
            timeout=30,
        )
        if r.ok and ("所有契約" in r.text or "契約" in r.text):
            return r.text

    # If none matched, return last response text for debugging.
    return r.text if "r" in locals() else ""


def parse_large_trader_html(html: str) -> Tuple[str, Dict[str, int]]:
    """
    Parse out:
    - date
    - All-contracts row fields: buy5, buy10, sell5, sell10, oi
    """
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)

    # Date
    # The page usually contains a "日期" line.
    m = re.search(r"日期\s*[:：]\s*([0-9]{2,4}/[0-9]{2}/[0-9]{2})", text)
    date_s = _format_yyyymmdd(m.group(1)) if m else datetime.now().strftime("%Y%m%d")

    # Find table row that contains "所有契約"
    # The row structure is usually:
    # [0]=所有契約
    # [1]=買方前五
    # [3]=買方前十
    # [5]=賣方前五
    # [7]=賣方前十
    # [9]=全市場未沖銷部位數
    all_row: Optional[List[str]] = None

    for tr in soup.find_all("tr"):
        cols = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if not cols:
            continue
        if any("所有契約" in c for c in cols):
            all_row = cols
            break

    if not all_row:
        raise ValueError("找不到「所有契約」那一列（可能是期交所頁面改版或該契約當日無資料）")

    if len(all_row) < 10:
        raise ValueError(f"表格欄位不足(len={len(all_row)})，抓到的欄位：{all_row}")

    buy5 = _to_int(all_row[1])
    buy10 = _to_int(all_row[3])
    sell5 = _to_int(all_row[5])
    sell10 = _to_int(all_row[7])
    oi = _to_int(all_row[9])

    return date_s, {"buy5": buy5, "buy10": buy10, "sell5": sell5, "sell10": sell10, "oi": oi}


def fetch_one_contract(session: requests.Session, contract_code: str) -> Tuple[str, Dict]:
    html = _post_large_trader(session, contract_code)
    if not html:
        raise ValueError("抓不到期交所回應（空白）")

    date_s, v = parse_large_trader_html(html)
    top5_net = v["buy5"] - v["sell5"]
    top10_net = v["buy10"] - v["sell10"]

    data = {
        "net": top5_net,  # keep UI simple: main net = top5 net
        "top5": {"buy": v["buy5"], "sell": v["sell5"], "net": top5_net},
        "top10": {"buy": v["buy10"], "sell": v["sell10"], "net": top10_net},
        "oi": v["oi"],
    }
    return date_s, data


def load_existing_history(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            old = json.load(f)
        hist = old.get("history", [])
        return hist if isinstance(hist, list) else []
    except Exception:
        return []


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    # 1) Map ticker -> contract code from TAIFEX list page
    try:
        code_map = fetch_stock_futures_contract_map(session)
    except Exception as e:
        code_map = {}

    items: List[Dict] = []
    date_out: Optional[str] = None

    for t in TARGET_STOCKS:
        stock = t["stock"]
        name = t["name"]

        code = code_map.get(stock)
        if not code:
            items.append(
                {"name": name, "stock": stock, "code": None, "data": {"error": "找不到對應的期交所合約代碼（可能沒有上市個股期貨）"}}
            )
            continue

        try:
            d, data = fetch_one_contract(session, code)
            date_out = date_out or d
            items.append({"name": name, "stock": stock, "code": code, "data": data})
        except Exception as e:
            items.append({"name": name, "stock": stock, "code": code, "data": {"error": str(e)}})

    date_out = date_out or datetime.now().strftime("%Y%m%d")

    out_path = "docs/futures_data.json"
    os.makedirs("docs", exist_ok=True)

    # 2) Rolling history
    history = load_existing_history(out_path)
    today_snapshot = {"date": date_out, "items": items}
    # de-dup by date
    history = [h for h in history if isinstance(h, dict) and h.get("date") != date_out]
    history.insert(0, today_snapshot)
    history = history[:7]

    out = {"date": date_out, "items": items, "history": history}

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {out_path} date={date_out}, items={len(items)}, history={len(history)}")


if __name__ == "__main__":
    main()
