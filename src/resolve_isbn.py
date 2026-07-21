"""把策展清单（书名+作者）解析成带真实 ISBN 的书目库。

为什么要有这一步：
  凭记忆写 ISBN 必然出错。12 本的原型里就错了一个。60 本只会更糟。
  所以策展环节**只写书名和作者**，ISBN 一律从 Open Library 查回来。
  查不到的书直接淘汰，绝不进库。

这是防幻觉的第一道闸门，而且它作用在**策展环节**，不是模型环节 ——
等到模型那一层再防就晚了，脏数据已经在库里了。

输出：data/books.json
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
CURATION = ROOT / "data" / "curation.json"
OUT = ROOT / "data" / "books.json"

SEARCH = "https://openlibrary.org/search.json"
ISBN_EP = "https://openlibrary.org/isbn/{isbn}.json"


def verify_isbn(isbn: str) -> Optional[dict]:
    """确认一个 ISBN 真实存在（权威端点）。"""
    try:
        r = requests.get(ISBN_EP.format(isbn=isbn), timeout=20)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def score(meta: dict, want_year: Optional[int]) -> int:
    """给一条 ISBN 记录打分。分越高越可能是我们要的那一本。

    「ISBN 真实存在」不等于「ISBN 是对的」—— 第一版解析器就栽在这：
    它把 Designing Data-Intensive Applications 解析成了西班牙语译本，
    把 Speech and Language Processing 解析成了 2008 年的旧版。
    必须再核语言和年份。
    """
    s = 0

    langs = [l.get("key", "") for l in (meta.get("languages") or [])]
    if not langs:
        s += 1                      # 没标语言，弱信号，不惩罚
    elif any("eng" in l for l in langs):
        s += 10                     # 英文版 —— 我们要的
    else:
        s -= 20                     # 译本 —— 直接排除

    pd = meta.get("publish_date") or ""
    yrs = [int(t) for t in pd.replace(",", " ").split() if t.isdigit() and len(t) == 4]
    if yrs and want_year:
        gap = min(abs(y - want_year) for y in yrs)
        if gap == 0:
            s += 10
        elif gap <= 2:
            s += 5                  # 印次差异，可接受
        else:
            s -= gap                # 差得越远越可能是错版次

    return s


def search_isbn(title: str, author: str, year: Optional[int]) -> Optional[str]:
    """按书名+作者搜 Open Library，挑出**最匹配**的英文版 ISBN。"""
    docs = []
    # 两轮：先带作者精确搜；搜不到再退回只按书名（作者名拼写/顺序可能不匹配）
    for params in (
        {"title": title, "author": author, "limit": 5},
        {"q": f"{title} {author}", "limit": 8},
    ):
        try:
            r = requests.get(
                SEARCH,
                params={**params, "fields": "title,author_name,first_publish_year,isbn"},
                timeout=30,
            )
            r.raise_for_status()
            docs = r.json().get("docs", [])
        except requests.RequestException:
            docs = []
        if docs:
            break
        time.sleep(0.3)

    candidates = []
    for d in docs:
        for isbn in [i for i in (d.get("isbn") or []) if len(i) == 13 and i.startswith("978")][:12]:
            meta = verify_isbn(isbn)
            time.sleep(0.12)
            if not meta:
                continue
            sc = score(meta, year)
            candidates.append((sc, isbn, meta))
            if sc >= 20:            # 英文 + 年份精确 —— 不用再找了
                return isbn
        if candidates:
            break                   # 第一条 doc 已经有候选，别再往下翻（往下多是译本）

    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    best_score, best_isbn, best_meta = candidates[0]
    if best_score < 0:
        return None                 # 只剩译本 —— 宁可淘汰
    return best_isbn


def resolve(entry: Dict) -> Optional[Dict]:
    title, author = entry["title"], entry["author"]
    label = f"{title[:44]:<44} {author[:18]:<18}"

    # 先用 hint（原型里已经人工核实过的），核不过再退回搜索
    hint = entry.get("isbn_hint")
    isbn = None
    if hint and verify_isbn(hint):
        isbn = hint
    else:
        isbn = search_isbn(title, author, entry.get("year"))

    if not isbn:
        print(f"  ✗ {label} 查无此书 —— 淘汰")
        return None

    meta = verify_isbn(isbn)
    print(f"  ✓ {label} {isbn}")

    decay = dict(entry["decay"])
    decay.setdefault("pinned_apis", [])
    decay.setdefault("superseded_by", [])

    return {
        "isbn": isbn,
        "title": entry["title"] + (f" ({entry['edition']}nd Edition)" if entry.get("edition") == 2 else f" ({entry['edition']}rd Edition)" if entry.get("edition") == 3 else ""),
        "authors": [entry["author"]],
        "published": entry.get("year") or 0,
        "edition": entry.get("edition", 1),
        "quadrant": entry["quadrant"],
        "difficulty": entry["difficulty"],
        "kind": entry["kind"],
        "decay": decay,
        "note": entry["note"],
        "_superseded_by_title": entry["decay"].get("superseded_by_title"),
    }


def main() -> int:
    curation = json.loads(CURATION.read_text())
    entries = curation["books"]

    print(f"解析 {len(entries)} 本策展书目 → Open Library\n")

    resolved: List[Dict] = []
    for e in entries:
        b = resolve(e)
        if b:
            resolved.append(b)
        time.sleep(0.3)

    # 第二遍：把 superseded_by_title 解析成真实 ISBN
    by_title = {}
    for b in resolved:
        key = b["title"].split(" (")[0].lower()
        by_title.setdefault(key, []).append(b)

    for b in resolved:
        t = b.pop("_superseded_by_title", None)
        if not t:
            continue
        base = t.split(" (")[0].lower()
        cands = [x for x in by_title.get(base, []) if x["isbn"] != b["isbn"] and x["edition"] > b["edition"]]
        if not cands:
            # 跨书取代（如 Python ML → ML with PyTorch and Sklearn）
            cands = [x for x in resolved if x["title"].lower().startswith(base[:30]) and x["isbn"] != b["isbn"]]
        if cands:
            b["decay"]["superseded_by"] = [cands[0]["isbn"]]
            print(f"\n  取代关系: 《{b['title'][:40]}》 ← 《{cands[0]['title'][:40]}》")
        else:
            print(f"\n  ! 未能解析取代关系: {b['title'][:40]} → {t}")
        b["decay"].pop("superseded_by_title", None)

    dropped = len(entries) - len(resolved)
    print(f"\n{'='*66}")
    print(f"  入库 {len(resolved)} 本   淘汰 {dropped} 本")
    print(f"{'='*66}")

    from collections import Counter
    print("\n象限分布:", dict(Counter(b["quadrant"] for b in resolved)))
    print("难度分布:", dict(Counter(b["difficulty"] for b in resolved)))
    print("经典/时效:", dict(Counter(b["kind"] for b in resolved)))

    out = {
        "_comment": "由 resolve_isbn.py 从 data/curation.json 生成。每个 ISBN 都经 Open Library 权威端点回验 —— 查不到的书已淘汰，不在此处。",
        "_generated_from": "data/curation.json",
        "books": resolved,
        "_difficulty": {
            "entry": "● 入门 —— 有编程基础即可读",
            "intermediate": "◆ 进阶 —— 需要一定的 ML 或系统背景",
            "hardcore": "▲ 硬核 —— 数学密集，投入巨大",
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
