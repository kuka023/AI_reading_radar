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
RESOURCES_JSON = ROOT / "data" / "resources.json"


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
  state    TEXT,               -- 书架状态：want 未读 / reading 在读 / read 已读
  finished TEXT,
  useful   TEXT,
  curated  INTEGER DEFAULT 1,
  meta     TEXT,
  stance   TEXT,               -- 个人雷达立场：now / invest / know（正交于 state）
  ts       INTEGER,
  PRIMARY KEY (actor, isbn)
);

CREATE TABLE IF NOT EXISTS books (
  isbn         TEXT PRIMARY KEY,   -- 资料 id：书籍=book:slug，非书=res:...；沿用列名保持兼容
  title        TEXT,
  authors      TEXT,
  published    INTEGER,
  quadrant     TEXT,               -- 存能力族 family
  difficulty   TEXT,
  kind         TEXT,               -- 资料类型 rtype：book/course/doc/article
  content_type TEXT,
  paradigm     TEXT,
  note         TEXT,               -- 推荐理由
  decay        TEXT,
  curated      INTEGER DEFAULT 1,
  rtype        TEXT,
  link         TEXT,
  stance       TEXT,
  topic        TEXT,
  rec          INTEGER,
  meta_pending INTEGER DEFAULT 0,
  companions   TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
  id    INTEGER PRIMARY KEY AUTOINCREMENT,
  actor TEXT,
  isbn  TEXT,
  text  TEXT,
  score INTEGER,               -- 推荐打分 1–5（可空）
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
    """把业务共建资料库导入 books 表（curated=1）。重跑幂等。

    id（书籍=book:slug / 非书=res:...）存进 isbn 主键列，沿用旧列名保持兼容。
    """
    data = json.loads(RESOURCES_JSON.read_text())
    with conn() as c:
        for r in data:
            c.execute(
                """INSERT OR REPLACE INTO books
                   (isbn,title,authors,published,quadrant,difficulty,kind,
                    content_type,paradigm,note,decay,curated,
                    rtype,link,stance,topic,rec,meta_pending,companions)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?,?,?,?)""",
                (
                    r["id"], r["title"], json.dumps(r.get("authors", []), ensure_ascii=False),
                    r.get("published"), r["family"], str(r["difficulty"]), r["rtype"],
                    r.get("content_type") or "", "",
                    r.get("reason", ""), None,
                    r["rtype"], r.get("link", ""), r["stance"], r.get("topic", ""),
                    r.get("rec", 3), 1 if r.get("meta_pending") else 0,
                    json.dumps(r.get("companions", []), ensure_ascii=False),
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
                 curated=1, meta=None, stance=None):
    with conn() as c:
        row = c.execute("SELECT * FROM shelf WHERE actor=? AND isbn=?",
                        (actor, isbn)).fetchone()
        cur = dict(row) if row else {}
        c.execute(
            """INSERT OR REPLACE INTO shelf
               (actor,isbn,state,finished,useful,curated,meta,stance,ts)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (actor, isbn,
             state if state is not None else cur.get("state"),
             finished if finished is not None else cur.get("finished"),
             useful if useful is not None else cur.get("useful"),
             curated,
             json.dumps(meta, ensure_ascii=False) if meta else cur.get("meta"),
             (stance or None) if stance is not None else cur.get("stance"),  # "" = 清空
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
    if d.get("companions"):
        try:
            d["companions"] = json.loads(d["companions"])
        except (ValueError, TypeError):
            d["companions"] = []
    d["id"] = d.get("isbn")           # 对外统一叫 id
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
    link = f"https://openlibrary.org/isbn/{isbn}" if isbn else ""
    with conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO books
               (isbn,title,authors,published,quadrant,difficulty,kind,
                content_type,paradigm,note,decay,curated,
                rtype,link,stance,topic,rec,meta_pending,companions)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?,?,?,?)""",
            (isbn, title, json.dumps(authors, ensure_ascii=False), published,
             quadrant, "3", "book", "tool", "",
             "你从图书馆加进来的书 · 未经策展", None,
             "book", link, "know", "", 3, 1, "[]"),
        )


def get_book(isbn):
    with conn() as c:
        r = c.execute("SELECT * FROM books WHERE isbn=?", (isbn,)).fetchone()
    return _book_row(r) if r else None


# ── L3 社区：书评 + 有用投票 ──
def add_review(actor, isbn, text, score=None):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO reviews(actor,isbn,text,score,ts) VALUES (?,?,?,?,?)",
            (actor, isbn, text, score, int(time.time())),
        )
        return cur.lastrowid


def get_reviews(isbn, viewer=None):
    """某本书的书评，附打分 + 有用票数 + 观看者是否投过票。按票数降序。"""
    with conn() as c:
        rows = c.execute(
            """SELECT r.id, r.actor, r.text, r.score, r.ts,
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


def book_rating(rid):
    """聚合评分 —— 用飞轮的真实信号（读完 + 有用），不做假五星。

    评分口径：很有用=1 / 一般=0.5 / 没用=0，折算成 0–5 分展示。
    """
    with conn() as c:
        rows = c.execute(
            "SELECT useful, finished FROM shelf WHERE isbn=? AND useful IS NOT NULL",
            (rid,)).fetchall()
        n_reviews = c.execute("SELECT COUNT(*) FROM reviews WHERE isbn=?", (rid,)).fetchone()[0]
        n_read = c.execute("SELECT COUNT(*) FROM shelf WHERE isbn=? AND state='read'", (rid,)).fetchone()[0]
    useful = {"high": 0, "some": 0, "none": 0}
    for r in rows:
        if r["useful"] in useful:
            useful[r["useful"]] += 1
    n = sum(useful.values())
    score = round((useful["high"] + useful["some"] * 0.5) / n * 5, 1) if n else None
    return {"score": score, "n": n, "useful": useful,
            "reviews": n_reviews, "read": n_read}


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
            f"""SELECT r.id, r.actor, r.isbn, r.text, r.score, r.ts,
                       b.title AS book_title, b.quadrant,
                       COALESCE(SUM(v.useful),0) AS up
                FROM reviews r
                JOIN books b ON b.isbn=r.isbn
                LEFT JOIN votes v ON v.review_id=r.id
                GROUP BY r.id ORDER BY {order} LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── 个人空间：个人雷达（书架里带 stance 的书）+ 我的推荐 ──
def personal_radar(actor):
    """某用户放到个人雷达上的书（shelf.stance 非空），带渲染所需的书目元数据。"""
    with conn() as c:
        rows = c.execute(
            """SELECT s.isbn, s.state, s.stance, s.curated, s.meta,
                      b.title, b.authors, b.quadrant AS family, b.rtype,
                      b.difficulty, b.content_type
               FROM shelf s LEFT JOIN books b ON b.isbn=s.isbn
               WHERE s.actor=? AND s.stance IS NOT NULL AND s.stance!=''""",
            (actor,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["authors"] = json.loads(d["authors"]) if d.get("authors") else []
        if d.get("meta"):
            try:
                m = json.loads(d["meta"])
                d["title"] = d.get("title") or m.get("title")
                d["family"] = d.get("family") or m.get("quadrant")
            except (ValueError, TypeError):
                pass
        d["id"] = d.pop("isbn")
        out.append(d)
    return out


def recommendations(actor):
    """某用户的推荐（带分书评），按时间倒序。"""
    with conn() as c:
        rows = c.execute(
            """SELECT r.id, r.isbn, r.text, r.score, r.ts, b.title AS book_title,
                      b.quadrant AS family
               FROM reviews r JOIN books b ON b.isbn=r.isbn
               WHERE r.actor=? ORDER BY r.ts DESC""",
            (actor,),
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
