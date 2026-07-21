"""数据层（SQLite 起步）。

选型见 SPEC-backend-v1.md：形态未验证前用最轻的地基把数据流跑通，
不上 Postgres+Redis+Celery 那套规模化架构。等有真实并发再迁。

五张核心表：users / events / shelf / books / reviews(+votes)。
events 是飞轮的原始账本；shelf/reviews 是派生业务视图。
"""

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "radar.db"
BOOKS_JSON = ROOT / "data" / "books.json"


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")   # 读写不互相阻塞
    c.execute("PRAGMA foreign_keys=ON")
    return c


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  handle        TEXT,
  auth_provider TEXT DEFAULT 'anon',
  created_at    INTEGER
);

CREATE TABLE IF NOT EXISTS events (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  actor   TEXT,
  action  TEXT,
  isbn    TEXT,
  context TEXT,
  value   TEXT,
  ts      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor);
CREATE INDEX IF NOT EXISTS idx_events_action ON events(action);

CREATE TABLE IF NOT EXISTS shelf (
  actor    TEXT,
  isbn     TEXT,
  state    TEXT,
  finished TEXT,
  useful   TEXT,
  curated  INTEGER DEFAULT 1,
  meta     TEXT,
  ts       INTEGER,
  PRIMARY KEY (actor, isbn)
);

CREATE TABLE IF NOT EXISTS books (
  isbn         TEXT PRIMARY KEY,
  title        TEXT,
  authors      TEXT,
  published    INTEGER,
  quadrant     TEXT,
  difficulty   TEXT,
  kind         TEXT,
  content_type TEXT,
  paradigm     TEXT,
  note         TEXT,
  decay        TEXT,
  curated      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reviews (
  id    INTEGER PRIMARY KEY AUTOINCREMENT,
  actor TEXT,
  isbn  TEXT,
  text  TEXT,
  ts    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_reviews_isbn ON reviews(isbn);

CREATE TABLE IF NOT EXISTS votes (
  actor     TEXT,
  review_id INTEGER,
  useful    INTEGER,
  PRIMARY KEY (actor, review_id)
);
"""


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
    import_curated()


def import_curated():
    """把策展的 89 本导入 books 表（curated=1）。重跑幂等。"""
    data = json.loads(BOOKS_JSON.read_text())
    with conn() as c:
        for b in data["books"]:
            c.execute(
                """INSERT OR REPLACE INTO books
                   (isbn,title,authors,published,quadrant,difficulty,kind,
                    content_type,paradigm,note,decay,curated)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
                (
                    b["isbn"], b["title"], json.dumps(b["authors"], ensure_ascii=False),
                    b.get("published"), b["quadrant"], b["difficulty"], b["kind"],
                    b["decay"]["content_type"], b["decay"]["paradigm"],
                    b.get("note", ""), json.dumps(b["decay"], ensure_ascii=False),
                ),
            )


# ── 账号 ──
def get_or_create_anon(uid: Optional[str] = None) -> str:
    """匿名账号：前端已有 uuid 就登记，没有就发一个。"""
    uid = uid or ("anon_" + uuid.uuid4().hex[:16])
    with conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO users(id,auth_provider,created_at) VALUES (?,?,?)",
            (uid, "anon", int(time.time())),
        )
    return uid


# ── 事件流（飞轮燃料）──
def log_event(actor, action, isbn=None, context=None, value=None):
    with conn() as c:
        c.execute(
            "INSERT INTO events(actor,action,isbn,context,value,ts) VALUES (?,?,?,?,?,?)",
            (actor, action, isbn,
             json.dumps(context, ensure_ascii=False) if context else None,
             json.dumps(value, ensure_ascii=False) if value else None,
             int(time.time())),
        )


# ── 书架 ──
def upsert_shelf(actor, isbn, state=None, finished=None, useful=None,
                 curated=1, meta=None):
    with conn() as c:
        row = c.execute("SELECT * FROM shelf WHERE actor=? AND isbn=?",
                        (actor, isbn)).fetchone()
        cur = dict(row) if row else {}
        c.execute(
            """INSERT OR REPLACE INTO shelf
               (actor,isbn,state,finished,useful,curated,meta,ts)
               VALUES (?,?,?,?,?,?,?,?)""",
            (actor, isbn,
             state if state is not None else cur.get("state"),
             finished if finished is not None else cur.get("finished"),
             useful if useful is not None else cur.get("useful"),
             curated,
             json.dumps(meta, ensure_ascii=False) if meta else cur.get("meta"),
             int(time.time())),
        )


def remove_shelf(actor, isbn):
    with conn() as c:
        c.execute("DELETE FROM shelf WHERE actor=? AND isbn=?", (actor, isbn))


def get_shelf(actor):
    with conn() as c:
        rows = c.execute("SELECT * FROM shelf WHERE actor=?", (actor,)).fetchall()
    out = {}
    for r in rows:
        d = dict(r)
        if d.get("meta"):
            d["meta"] = json.loads(d["meta"])
        out[d["isbn"]] = d
    return out


# ── L2 图书馆：书目检索 + 加外部书 ──
def _book_row(r):
    d = dict(r)
    d["authors"] = json.loads(d["authors"]) if d.get("authors") else []
    if d.get("decay"):
        d["decay"] = json.loads(d["decay"])
    return d


def search_curated(q: str, limit: int = 8):
    """在策展库里搜（书名 / 作者）。命中的书是有观点的，前端可定位到雷达。"""
    like = f"%{q.lower()}%"
    with conn() as c:
        rows = c.execute(
            """SELECT * FROM books
               WHERE curated=1 AND (LOWER(title) LIKE ? OR LOWER(authors) LIKE ?)
               LIMIT ?""",
            (like, like, limit),
        ).fetchall()
    return [_book_row(r) for r in rows]


def curated_isbns():
    with conn() as c:
        return {r[0] for r in c.execute("SELECT isbn FROM books WHERE curated=1")}


def add_external_book(isbn, title, authors, published, quadrant):
    """把用户从外部大库加进来的书存进图书馆（curated=0，个人图层）。"""
    with conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO books
               (isbn,title,authors,published,quadrant,difficulty,kind,
                content_type,paradigm,note,decay,curated)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""",
            (isbn, title, json.dumps(authors, ensure_ascii=False), published,
             quadrant, "intermediate", "timely", "narrative", "llm",
             "你从图书馆加进来的书 · 未经策展", None),
        )


def get_book(isbn):
    with conn() as c:
        r = c.execute("SELECT * FROM books WHERE isbn=?", (isbn,)).fetchone()
    return _book_row(r) if r else None


# ── L3 社区：书评 + 有用投票 ──
def add_review(actor, isbn, text):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO reviews(actor,isbn,text,ts) VALUES (?,?,?,?)",
            (actor, isbn, text, int(time.time())),
        )
        return cur.lastrowid


def get_reviews(isbn, viewer=None):
    """某本书的书评，附有用票数 + 观看者是否投过票。按票数降序。"""
    with conn() as c:
        rows = c.execute(
            """SELECT r.id, r.actor, r.text, r.ts,
                      COALESCE(SUM(v.useful),0) AS up,
                      (SELECT useful FROM votes WHERE actor=? AND review_id=r.id) AS mine
               FROM reviews r LEFT JOIN votes v ON v.review_id=r.id
               WHERE r.isbn=?
               GROUP BY r.id ORDER BY up DESC, r.ts DESC""",
            (viewer, isbn),
        ).fetchall()
    return [dict(r) for r in rows]


def vote_review(actor, review_id, useful):
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO votes(actor,review_id,useful) VALUES (?,?,?)",
            (actor, review_id, 1 if useful else 0),
        )


def has_read(actor, isbn):
    """防刷：只有标了「读过」的人才能评。"""
    with conn() as c:
        r = c.execute(
            "SELECT state FROM shelf WHERE actor=? AND isbn=?", (actor, isbn)
        ).fetchone()
    return bool(r and r[0] == "read")


def all_books(actor=None):
    """图书馆浏览：全部策展书 + 该用户加的外部书。"""
    with conn() as c:
        rows = c.execute("SELECT * FROM books WHERE curated=1 ORDER BY quadrant, difficulty").fetchall()
        out = [_book_row(r) for r in rows]
        if actor:                        # 附上该用户从图书馆加的外部书
            ext = c.execute(
                """SELECT b.* FROM books b JOIN shelf s ON s.isbn=b.isbn
                   WHERE b.curated=0 AND s.actor=?""", (actor,)).fetchall()
            out += [_book_row(r) for r in ext]
    return out


def community_feed(sort="recent", limit=60):
    """全站书评流，附书名与有用票数。sort: recent | top。"""
    order = "up DESC, r.ts DESC" if sort == "top" else "r.ts DESC"
    with conn() as c:
        rows = c.execute(
            f"""SELECT r.id, r.actor, r.isbn, r.text, r.ts,
                       b.title AS book_title, b.quadrant,
                       COALESCE(SUM(v.useful),0) AS up
                FROM reviews r
                JOIN books b ON b.isbn=r.isbn
                LEFT JOIN votes v ON v.review_id=r.id
                GROUP BY r.id ORDER BY {order} LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def stats():
    with conn() as c:
        return {
            "users": c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "events": c.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "shelf_rows": c.execute("SELECT COUNT(*) FROM shelf").fetchone()[0],
            "books": c.execute("SELECT COUNT(*) FROM books").fetchone()[0],
            "reviews": c.execute("SELECT COUNT(*) FROM reviews").fetchone()[0],
        }


if __name__ == "__main__":
    init_db()
    print("DB 初始化完成:", DB)
    print("表状态:", stats())
