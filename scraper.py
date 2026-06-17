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
    {"name": "中央支部", "sibu_cd": "1"},
    {"name": "東支部",   "sibu_cd": "4"},
    {"name": "西支部",   "sibu_cd": "5"},
    {"name": "南支部",   "sibu_cd": "6"},
    {"name": "北支部",   "sibu_cd": "7"},
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

# ============================================================
# 全日本不動産協会（全日）スクレイピング
# 取得先: https://www.zennichi.or.jp/member_search/list (GET)
# ============================================================
ZENNICHI_URL = "https://www.zennichi.or.jp/member_search/list"
ZENNICHI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
}

def _clean(s):
    return re.sub(r'\s+', ' ', s).strip()

def parse_zennichi_page(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = [tr for tr in soup.select('.member-result-table tr') if tr.find_all('td')]
    companies = []
    for tr in rows:
        tds = tr.find_all('td')
        if len(tds) < 3:
            continue
        # 免許番号
        lic = _clean(tds[0].get_text(' ')).replace('免許番号', '').strip()
        m = re.search(r'(\S+\(\d+\))\s*(\d+)', lic)
        takken = (m.group(1) + m.group(2)) if m else lic
        # 商号 / 代表者
        c1 = tds[1].get_text('\n', strip=True)
        name = _clean(c1.split('代表者')[0])
        rep = ''
        mr = re.search(r'代表者[:：]?\s*(.+)', c1)
        if mr:
            rep = _clean(mr.group(1))
        # ヘッダー行スキップ
        if not name or '商号' in name:
            continue
        # 所在地 / 電話 / HP
        c2 = tds[2].get_text('\n', strip=True)
        zip_m = re.search(r'〒?\s*(\d{3}-?\d{4})', c2)
        zipc = zip_m.group(1) if zip_m else ''
        tel_m = re.search(r'(0\d{1,3}-\d{1,4}-\d{3,4})', c2)
        phone = tel_m.group(1) if tel_m else ''
        addr = c2
        if zipc:
            addr = addr.split(zipc, 1)[-1]
        addr = _clean(re.split(r'TEL', addr)[0]).lstrip('　 ')
        hp = ''
        for a in tds[2].find_all('a', href=True):
            if a['href'].startswith('http') and 'zennichi' not in a['href']:
                hp = a['href']
                break
        companies.append({
            "id": "", "sibu": "全日", "takken_no": takken, "name": name,
            "representative": rep, "zip": zipc, "address": addr,
            "phone": phone, "hp": hp,
        })
    return companies

def get_zennichi_total_pages(html):
    soup = BeautifulSoup(html, "html.parser")
    maxp = 1
    for a in soup.find_all('a', href=True):
        m = re.search(r'pages=(\d+)', a['href'])
        if m:
            maxp = max(maxp, int(m.group(1)))
    return maxp

def scrape_zennichi():
    print(f"\n全日（北海道本部・札幌）を取得中...")
    params = {"prefecture": "01", "region": "01", "address": "札幌", "pages": "1"}
    try:
        res = requests.get(ZENNICHI_URL, params=params, headers=ZENNICHI_HEADERS, timeout=25)
        res.encoding = res.apparent_encoding
    except Exception as e:
        print(f"  エラー: {e}")
        return []

    total_pages = get_zennichi_total_pages(res.text)
    print(f"  総ページ数: {total_pages}")

    all_companies = parse_zennichi_page(res.text)
    print(f"  1ページ目: {len(all_companies)}件")

    for page in range(2, total_pages + 1):
        time.sleep(1.0)
        params["pages"] = str(page)
        try:
            res = requests.get(ZENNICHI_URL, params=params, headers=ZENNICHI_HEADERS, timeout=25)
            res.encoding = res.apparent_encoding
        except Exception as e:
            print(f"  {page}ページ目: 取得失敗 {e}")
            break
        companies = parse_zennichi_page(res.text)
        all_companies.extend(companies)
        if page % 10 == 0 or page == total_pages:
            print(f"  {page}/{total_pages}ページ (累計: {len(all_companies)}件)")

    return all_companies

def main():
    print("=== 業者データ スクレイピング開始 ===")
    all_data = []

    # --- 宅建協会（5支部） ---
    for s in SIBU_LIST:
        companies = scrape_sibu(s["name"], s["sibu_cd"])
        for c in companies:
            c["source"] = "宅建協会"
        all_data.extend(companies)

    # --- 全日 ---
    zennichi = scrape_zennichi()
    for c in zennichi:
        c["source"] = "全日"
    all_data.extend(zennichi)

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
