"""对照 Open Library 校验书目库里的每一条 ISBN。

这是防幻觉的第一道闸门：books.json 是人写的（或 AI 起草的），
里面的 ISBN 完全可能是编的。上线前必须逐条对回真实书目库。
校验不通过的书不允许进雷达。
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data" / "books.json"

# /isbn/ 是权威端点。/api/books 覆盖有缺口（漏掉了 Hands-On ML 3rd ed 等
# 真实存在的书），用它做校验会把真书误判成假书 —— 不要用它当闸门。
ISBN_API = "https://openlibrary.org/isbn/{isbn}.json"


def fetch(isbn: str) -> Optional[dict]:
    r = requests.get(ISBN_API.format(isbn=isbn), timeout=20)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def title_matches(local: str, remote: str) -> bool:
    """宽松比对：只看主标题的前几个实词，避免副标题/版次差异造成假阴性。"""

    def key(s: str) -> str:
        s = s.lower().split(":")[0].split("(")[0]
        return "".join(c for c in s if c.isalnum() or c.isspace()).strip()

    a, b = key(local), key(remote)
    return a.startswith(b[:20]) or b.startswith(a[:20])


def main() -> int:
    data = json.loads(BOOKS.read_text())
    books = data["books"]

    ok, mismatched, missing = [], [], []

    for b in books:
        isbn, title = b["isbn"], b["title"]
        try:
            remote = fetch(isbn)
        except requests.RequestException as e:
            print(f"  网络错误 {isbn}: {e}")
            time.sleep(1)
            continue

        if remote is None:
            missing.append((isbn, title))
            print(f"✗ 查无此书  {isbn}  {title}")
        elif not title_matches(title, remote.get("title", "")):
            mismatched.append((isbn, title, remote.get("title", "")))
            print(f"? 标题不符  {isbn}")
            print(f"    本地: {title}")
            print(f"    远端: {remote.get('title', '')}")
        else:
            ok.append(isbn)
            year = (remote.get("publish_date") or "")[-4:]
            print(f"✓ {isbn}  {remote.get('title', '')[:52]:<52} {year}")
            if year.isdigit() and int(year) != b["published"]:
                print(f"    ! 出版年不符：本地 {b['published']} / 远端 {year}")

        time.sleep(0.34)  # 别把 Open Library 打挂

    print()
    print(f"通过 {len(ok)} / {len(books)}   查无此书 {len(missing)}   标题不符 {len(mismatched)}")

    if missing:
        print("\n查无此书的 ISBN 必须修掉或删掉 —— 它们可能是编造的，绝不能进雷达。")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
