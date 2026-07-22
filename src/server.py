"""后端 API。

数据源 = 业务共建资料库（data/resources.json，由 ingest_xlsx + enrich_isbn 生成）。
角色 = 8 个业务能力族；环 = 立场（策展观点）；星球外形 = 资料类型。
排环走纯规则（radar.py），不调 LLM —— 免费、瞬时、确定性。

  GET /api/roles           能力族列表（前端的入口）
  GET /api/galaxy          全景星云（全部资料）
  GET /api/radar/{role}    该能力族的雷达（三立场环）
  GET /api/stats           资料库总览
  GET /                    前端
"""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import radar

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

app = FastAPI(title="AI 读书雷达")


@app.on_event("startup")
def startup() -> None:
    db.init_db()                     # 建表 + 导入资料库（幂等）
    s = radar.stats()
    print(f"  资料库 {s['total']} 项  ·  书 {s['books']} / 课 {s['courses']} / 文档 {s['docs']} / 文章 {s['articles']}")
    print(f"  立场  现在就读 {s['now']} · 值得投入 {s['invest']} · 知道即可 {s['know']}")
    print(f"  {s['families']} 个能力族")
    print(f"  DB: {db.stats()}")


@app.get("/api/roles")
def get_roles():
    return radar.roles()


@app.get("/api/galaxy")
def get_galaxy():
    """第一屏：全部资料组成的一整片星云，还没分环。

    用户先看到「这个领域的全貌」，选了能力族才拉近到属于他的那一部分。
    """
    return radar.galaxy()


@app.get("/api/radar/{role}")
def get_radar(role: str):
    r = radar.radar(role)
    if r is None:
        raise HTTPException(404, f"未知能力族: {role}")
    return r


@app.get("/api/stats")
def get_stats():
    return radar.stats()


# ── L1 地基核心：账号 / 事件流 / 书架 ──

class AnonReq(BaseModel):
    id: Optional[str] = None


@app.post("/api/user/anon")
def user_anon(req: AnonReq):
    """匿名账号：前端已有 uuid 就登记，没有就发一个。零注册。"""
    return {"id": db.get_or_create_anon(req.id)}


class EventReq(BaseModel):
    actor: str
    action: str
    isbn: Optional[str] = None
    context: Optional[dict] = None
    value: Optional[dict] = None


@app.post("/api/events")
def post_event(e: EventReq):
    """飞轮打点。前端所有交互都发这里 —— 这是飞轮的原始账本。"""
    db.log_event(e.actor, e.action, e.isbn, e.context, e.value)
    return {"ok": True}


class ShelfReq(BaseModel):
    actor: str
    isbn: str
    state: Optional[str] = None       # want | reading | read | (全空=删除)
    finished: Optional[str] = None
    useful: Optional[str] = None
    curated: int = 1
    meta: Optional[dict] = None
    stance: Optional[str] = None      # 个人雷达立场 now/invest/know，""=移出雷达


@app.put("/api/shelf")
def put_shelf(s: ShelfReq):
    """更新一本书的书架状态/打分/个人雷达立场，同时落一条 event。"""
    if (s.state is None and s.finished is None and s.useful is None
            and s.stance is None):
        db.remove_shelf(s.actor, s.isbn)
        db.log_event(s.actor, "shelve", s.isbn, value={"state": "removed"})
        return {"ok": True, "removed": True}
    db.upsert_shelf(s.actor, s.isbn, s.state, s.finished, s.useful,
                    s.curated, s.meta, s.stance)
    action = ("place" if s.stance is not None else
              "rate" if (s.finished or s.useful) else "shelve")
    db.log_event(s.actor, action, s.isbn,
                 value={"state": s.state, "finished": s.finished,
                        "useful": s.useful, "stance": s.stance})
    return {"ok": True}


@app.get("/api/shelf")
def get_shelf(actor: str):
    return db.get_shelf(actor)


# ── L2 图书馆：搜索 + 加外部书 ──

import requests as _rq


def _search_openlibrary(q: str, exclude: set, limit: int = 6):
    """搜 Open Library 外部大库，排除已在策展库的书。"""
    try:
        r = _rq.get(
            "https://openlibrary.org/search.json",
            params={"q": q, "limit": 12,
                    "fields": "title,author_name,isbn,first_publish_year,language"},
            timeout=12,
        )
        docs = r.json().get("docs", [])
    except _rq.RequestException:
        return []
    out, seen = [], set()
    for d in docs:
        isbns = [i for i in (d.get("isbn") or []) if len(i) == 13 and i.startswith("978")]
        langs = d.get("language") or []
        if langs and not any("eng" in l for l in langs):
            continue                       # 只要英文版
        isbn = next((i for i in isbns if i not in exclude and i not in seen), None)
        if not isbn:
            continue
        seen.add(isbn)
        out.append({
            "isbn": isbn,
            "title": d.get("title", ""),
            "authors": (d.get("author_name") or [])[:2],
            "published": d.get("first_publish_year"),
        })
        if len(out) >= limit:
            break
    return out


@app.get("/api/search")
def search(q: str, actor: Optional[str] = None):
    q = (q or "").strip()
    if len(q) < 2:
        return {"curated": [], "external": []}
    curated = db.search_curated(q)
    external = _search_openlibrary(q, db.curated_isbns())
    if actor:
        db.log_event(actor, "search", value={"q": q,
                     "curated": len(curated), "external": len(external)})
    return {"curated": curated, "external": external}


class AddBookReq(BaseModel):
    actor: str
    isbn: str
    title: str
    authors: list = []
    published: Optional[int] = None
    quadrant: str = "applied"


@app.post("/api/library/add")
def library_add(b: AddBookReq):
    """把外部书加进图书馆（curated=0）+ 用户书架（想读，个人图层）。"""
    db.add_external_book(b.isbn, b.title, b.authors, b.published, b.quadrant)
    db.upsert_shelf(b.actor, b.isbn, state="want", curated=0,
                    meta={"title": b.title, "authors": b.authors,
                          "published": b.published, "quadrant": b.quadrant})
    db.log_event(b.actor, "add_book", b.isbn, value={"quadrant": b.quadrant})
    return {"ok": True, "book": db.get_book(b.isbn)}


# ── L3 社区：书评 + 有用投票 ──

@app.get("/api/reviews")
def reviews(isbn: str, actor: Optional[str] = None):
    return db.get_reviews(isbn, viewer=actor)


class ReviewReq(BaseModel):
    actor: str
    isbn: str
    text: str
    score: Optional[int] = None       # 推荐打分 1–5（可空）


@app.post("/api/reviews")
def post_review(r: ReviewReq):
    """发书评/推荐。防刷：必须先标「读过」——评价资格绑定阅读行为。"""
    if not db.has_read(r.actor, r.isbn):
        raise HTTPException(403, "标记「读过」后才能写书评")
    text = (r.text or "").strip()
    if not (2 <= len(text) <= 2000):
        raise HTTPException(400, "书评长度需在 2–2000 字")
    score = r.score
    if score is not None and not (1 <= score <= 5):
        raise HTTPException(400, "打分需在 1–5")
    rid = db.add_review(r.actor, r.isbn, text, score)
    db.log_event(r.actor, "review", r.isbn, value={"score": score})
    return {"ok": True, "id": rid}


class VoteReq(BaseModel):
    actor: str
    useful: bool = True


@app.post("/api/reviews/{review_id}/vote")
def vote(review_id: int, v: VoteReq):
    db.vote_review(v.actor, review_id, v.useful)
    db.log_event(v.actor, "vote", value={"review_id": review_id, "useful": v.useful})
    return {"ok": True}


# ── 图书馆全量书目 / 社区书评流（独立页面用）──

@app.get("/api/books")
def books(actor: Optional[str] = None):
    """图书馆浏览：全量策展书 + 该用户加的外部书。"""
    return db.all_books(actor)


@app.get("/api/community")
def community(sort: str = "recent", limit: int = 60):
    """社区：全站书评流。"""
    return db.community_feed(sort, min(limit, 200))


@app.get("/api/paths")
def get_paths():
    """成长路径（社区主页）：按角色的目标导向学习序列。"""
    return radar.paths()


# ── Phase 3：个性化规划 ──

@app.get("/api/goals")
def get_goals():
    return radar.goals()


class PlanReq(BaseModel):
    actor: Optional[str] = None
    goal: str
    days: int = 30


@app.post("/api/plan")
def post_plan(p: PlanReq):
    """按目标 + 时限 + 阅读史，在策展库内规划一条学习路径。"""
    read_ids = []
    if p.actor:
        shelf = db.get_shelf(p.actor)
        read_ids = [i for i, s in shelf.items() if s.get("state") == "read"]
    return radar.plan(p.goal, p.days, read_ids)


# ── Phase 2：飞轮评审台（模拟信号）──

import flywheel


@app.get("/api/flywheel")
def get_flywheel():
    """飞轮：准入 / 降级的专家评审队列（现阶段模拟信号驱动）。"""
    return flywheel.run()


# ── 个人空间：个人雷达 + 我的推荐（也用于分享时按 actor 只读加载）──

@app.get("/api/personal")
def personal(actor: str):
    """某用户放到个人雷达上的书（含分享只读加载）。"""
    return {"radar": db.personal_radar(actor),
            "recommendations": db.recommendations(actor)}


# ── 星球详情：封面 / 简介（仅取自 Open Library，绝不由模型生成）+ 聚合评分 ──

_OL_CACHE = {}


def _ol_detail(isbn: str) -> dict:
    """从 Open Library 拉封面 + 简介 + 出版信息。简介是真实数据，不臆造。缓存。"""
    if not isbn:
        return {}
    if isbn in _OL_CACHE:
        return _OL_CACHE[isbn]
    out = {"cover_url": f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"}
    try:
        r = _rq.get(f"https://openlibrary.org/isbn/{isbn}.json", timeout=10)
        if r.status_code == 200:
            d = r.json()
            out["pages"] = d.get("number_of_pages")
            out["publish_date"] = d.get("publish_date")
            pubs = d.get("publishers") or []
            out["publisher"] = pubs[0] if pubs else None
            works = d.get("works") or []
            if works:
                wk = works[0].get("key")
                w = _rq.get(f"https://openlibrary.org{wk}.json", timeout=10)
                if w.status_code == 200:
                    desc = w.json().get("description")
                    if isinstance(desc, dict):
                        desc = desc.get("value")
                    out["description"] = desc
    except _rq.RequestException:
        pass
    _OL_CACHE[isbn] = out
    return out


@app.get("/api/detail")
def detail(id: str):
    """点开星球时按需拉：真实封面 + Open Library 简介 + 出版信息 + 聚合评分。"""
    res = radar.get(id)
    isbn = (res or {}).get("isbn")
    ol = _ol_detail(isbn) if isbn else {}
    pages = ol.get("pages")
    read_hours = round(pages / 40) if pages else None       # ~40 页/小时的粗估
    return {
        "id": id,
        "isbn": isbn,
        "cover_url": ol.get("cover_url"),
        "description": ol.get("description"),
        "publisher": ol.get("publisher"),
        "publish_date": ol.get("publish_date"),
        "pages": pages,
        "read_hours": read_hours,
        "rating": db.book_rating(id),
    }


if WEB.exists():
    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")

    app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
