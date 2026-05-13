#!/usr/bin/env python3
"""
宅建協会 業者データ スクレイピングスクリプト
取得先: https://takken.basekernel.ne.jp/meibo.php (POST)
使用方法: python3 scraper.py
出力: data.json
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import datetime

MEIBO_URL = "https://takken.basekernel.ne.jp/meibo.php"

SIBU_LIST = [
    {"name": "北支部", "sibu_cd": "7"},
    {"name": "東支部", "sibu_cd": "4"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Content-Type": "application/x-www-form-urlencoded",
}

def fetch_page(sibu_cd, page=1):
    data = {
        "strsql": f"sibu_cd={sibu_cd}",
        "page": str(page),
        "sel": "会員名簿の表示",
    }
    try:
        res = requests.post(MEIBO_URL, data=data, headers=HEADERS, timeout=20)
        return res.content  # 生バイトを返す
    except Exception as e:
        print(f"  エラー (page={page}): {e}")
        return None

def get_total_pages(html):
    soup = BeautifulSoup(html, "html.parser", from_encoding="utf-8")
    # <input name="page" type="submit" value="2"> の最大値を取得
    page_inputs = soup.find_all("input", {"name": "page", "type": "submit"})
    if page_inputs:
        nums = [int(i.get("value", 0)) for i in page_inputs if i.get("value", "").isdigit()]
        return max(nums) + 1 if nums else 1
    return 1

def parse_page(html, sibu_name):
    soup = BeautifulSoup(html, "html.parser", from_encoding="utf-8")
    companies = []

    rows = soup.select("table tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 6:
            continue

        texts = [c.get_text(strip=True) for c in cols]

        # ヘッダー行スキップ
        if not texts[0] or "宅建番号" in texts[0] or "宅建" in texts[0][:4]:
            continue

        # HP URLを抽出
        hp_url = ""
        for col in cols:
            a = col.find("a", href=True)
            if a and a["href"].startswith("http"):
                hp_url = a["href"]
                break

        # カラム順: [宅建番号+取得日], [商号], [代表者名], [郵便番号], [住所], [電話番号], ...
        try:
            # 宅建番号と取得日が1セルに結合されているケースに対応
            takken_raw = texts[0]
            takken_no = re.split(r'[RHS]\d{2}', takken_raw)[0].strip()

            company = {
                "id": "",
                "sibu": sibu_name,
                "takken_no": takken_no,
                "name": texts[1] if len(texts) > 1 else "",
                "representative": texts[2] if len(texts) > 2 else "",
                "zip": texts[3] if len(texts) > 3 else "",
                "address": texts[4] if len(texts) > 4 else "",
                "phone": texts[5] if len(texts) > 5 else "",
                "hp": hp_url,
            }

            if not company["name"]:
                continue

            companies.append(company)
        except IndexError:
            continue

    return companies

def scrape_sibu(sibu_name, sibu_cd):
    print(f"\n{sibu_name} (sibu_cd={sibu_cd}) を取得中...")

    html = fetch_page(sibu_cd, 1)
    if not html:
        return []

    total_pages = get_total_pages(html)
    print(f"  総ページ数: {total_pages}")

    all_companies = parse_page(html, sibu_name)
    print(f"  1ページ目: {len(all_companies)}件")

    for page in range(2, total_pages + 1):
        time.sleep(1.2)
        html = fetch_page(sibu_cd, page)
        if not html:
            print(f"  {page}ページ目: 取得失敗")
            break
        companies = parse_page(html, sibu_name)
        all_companies.extend(companies)
        print(f"  {page}ページ目: {len(companies)}件 (累計: {len(all_companies)}件)")

    return all_companies

def main():
    print("=== 宅建協会 業者データ スクレイピング開始 ===")
    all_data = []

    for s in SIBU_LIST:
        companies = scrape_sibu(s["name"], s["sibu_cd"])
        all_data.extend(companies)

    # IDを振り直す
    for i, c in enumerate(all_data):
        c["id"] = str(i + 1)

    output = {
        "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(all_data),
        "companies": all_data
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n完了！ 合計 {len(all_data)} 件を data.json に保存しました。")

if __name__ == "__main__":
    main()
