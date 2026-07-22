"""给 data/resources.json 里的书籍补 ISBN + 作者。

来源是业务可信清单，不是模型生成 —— 所以这里是「能核实就核实，查不到也保留」，
不再像 resolve_isbn 那样查无即淘汰。查不到的书标 meta_pending=True，前端显示「元数据待补」。
"""

import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "data" / "resources.json"
SEARCH = "https://openlibrary.org/search.json"


def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", t.lower())


def resolve(title: str):
    """返回 (isbn13 or None, authors[list], year or None)。尽量挑英文版、书名最接近的一条。"""
    q = re.sub(r"[《》]", "", title).split(":")[0]
    try:
        r = requests.get(SEARCH, params={
            "q": q, "limit": 8,
            "fields": "title,author_name,first_publish_year,isbn,language",
        }, timeout=25)
        docs = r.json().get("docs", [])
    except requests.RequestException:
        return None, [], None

    want = norm(q)
    best = None
    for d in docs:
        langs = d.get("language") or []
        if langs and not any("eng" in l for l in langs):
            continue
        dt = norm(d.get("title", ""))
        # 书名要足够接近：一方包含另一方，且长度比 ≥0.75（否则 "aiengineering"
        # 会错配成 "agenticaiengineering" 的子串）
        if not dt or not want:
            continue
        contained = want in dt or dt in want
        ratio = min(len(want), len(dt)) / max(len(want), len(dt))
        if not (contained and ratio >= 0.75):
            continue
        isbns = [i for i in (d.get("isbn") or []) if len(i) == 13 and i.startswith("978")]
        if not isbns:
            continue
        best = (isbns[0], (d.get("author_name") or [])[:2], d.get("first_publish_year"))
        break
    return best if best else (None, [], None)


def main():
    data = json.loads(RES.read_text())
    hit = 0
    used = set()
    for o in data:
        if o["rtype"] != "book":
            continue
        isbn, authors, year = resolve(o["title"])
        time.sleep(0.4)
        if isbn and isbn in used:      # 撞车 = 错配到了别的书，宁可待补
            isbn = None
        if isbn:
            used.add(isbn)
            o["isbn"] = isbn
            o["authors"] = authors
            o["published"] = year
            o["meta_pending"] = False
            hit += 1
            print(f"  ✓ {o['title'][:46]:<46} {isbn}  {', '.join(authors)[:30]}")
        else:
            o["meta_pending"] = True
            print(f"  … {o['title'][:46]:<46} 元数据待补")
    RES.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    books = [o for o in data if o["rtype"] == "book"]
    print(f"\n书籍 {len(books)} 本 · 核到 ISBN {hit} 本 · 待补 {len(books)-hit} 本")


if __name__ == "__main__":
    main()
