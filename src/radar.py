"""从 data/resources.json 组装星云（全景）与各能力族的雷达。

替代旧的 placement.py + decay.py 服务路径：
  - 角色 = 业务能力族（roles.json 的 family 对齐 resources 的 families）
  - 环 = 立场 stance（now/invest/know），这是策展观点，不是业务推荐程度
  - 角向 = 能力主题 topic
  - 星球大小 = difficulty，材质 = content_type（书籍），外形 = rtype（书/课/文档/文章）
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "data" / "resources.json"
ROLES = ROOT / "data" / "roles.json"
PATHS = ROOT / "data" / "paths.json"
GOALS = ROOT / "data" / "goals.json"

STANCE_ORDER = ["now", "invest", "know"]
STANCE_LABEL = {"now": "现在就读", "invest": "值得投入", "know": "知道即可"}
RTYPE_LABEL = {"book": "书籍", "course": "课程", "doc": "官方文档", "article": "文章"}

_RES = None
_ROLES = None


def _load():
    global _RES, _ROLES
    if _RES is None:
        _RES = json.loads(RES.read_text())
        _ROLES = json.loads(ROLES.read_text())["roles"]
    return _RES, _ROLES


def _public(r: dict, ctx_family: str = None) -> dict:
    """ctx_family 指定时，family/topic 上下文化到该族 —— 跨族资料在某族雷达里
    应显示它在这个族的主题，而不是主族的主题。"""
    fam = r["family"]
    topic = r["topic"]
    if ctx_family and ctx_family in r["families"]:
        fam = ctx_family
        ft = (r.get("fam_topics") or {}).get(ctx_family) or []
        if ft:
            topic = ft[0]
    return {
        "id": r["id"],
        "title": r["title"],
        "rtype": r["rtype"],
        "rtype_label": RTYPE_LABEL.get(r["rtype"], r["rtype"]),
        "family": fam,
        "families": r["families"],
        "topic": topic,
        "topics": r["topics"],
        "stance": r["stance"],
        "difficulty": r["difficulty"],
        "content_type": r.get("content_type"),
        "rec": r["rec"],
        "link": r.get("link", ""),
        "reason": r.get("reason", ""),
        "authors": r.get("authors", []),
        "isbn": r.get("isbn"),
        "meta_pending": r.get("meta_pending", False),
        "companions": r.get("companions", []),
    }


def galaxy() -> list:
    """第一屏：全部资料组成的一整片星云（还没分环）。"""
    res, _ = _load()
    return [_public(r) for r in res]


def get(rid: str):
    """按 id 取原始资料记录（含真实 isbn，用于拉封面 / 简介）。"""
    res, _ = _load()
    return next((r for r in res if r["id"] == rid), None)


def paths() -> list:
    """成长路径：每条路径的每一步补上资料标题 / 类型 / 族，供社区主页展示。"""
    res, roles = _load()
    by_id = {r["id"]: r for r in res}
    data = json.loads(PATHS.read_text())["paths"]
    out = []
    for p in data:
        role = roles.get(p.get("role"), {})
        steps = []
        for st in p.get("steps", []):
            r = by_id.get(st["resource_id"])
            steps.append({
                "id": st["resource_id"],
                "why": st.get("why", ""),
                "title": r["title"] if r else st["resource_id"],
                "rtype": r["rtype"] if r else "book",
                "family": r["family"] if r else "",
                "found": r is not None,
            })
        out.append({
            "id": p["id"], "title": p["title"], "role": p.get("role"),
            "role_label": role.get("label", ""), "color": role.get("color", "#16181d"),
            "level": p.get("level", ""), "goal": p.get("goal", ""),
            "status": p.get("status", "draft"), "author": p.get("author", ""),
            "steps": steps,
        })
    return out


def roles() -> list:
    _, roles = _load()
    return [
        {"key": k, "label": v["label"], "family": v["family"],
         "tagline": v["tagline"], "goal": v["goal"], "color": v["color"]}
        for k, v in roles.items()
    ]


def radar(role_key: str):
    res, roles = _load()
    if role_key not in roles:
        return None
    role = roles[role_key]
    fam = role["family"]
    items = [_public(r, ctx_family=fam) for r in res if fam in r["families"]]

    rings = []
    for st in STANCE_ORDER:
        ring_items = [i for i in items if i["stance"] == st]
        ring_items.sort(key=lambda i: (-i["rec"], -i["difficulty"]))
        rings.append({"stance": st, "label": STANCE_LABEL[st],
                      "count": len(ring_items), "items": ring_items})

    # 该族覆盖的主题（角向标签）
    topics = []
    for i in items:
        for t in i["topics"]:
            if t and t not in topics:
                topics.append(t)

    from collections import Counter
    by_type = Counter(i["rtype"] for i in items)
    return {
        "role": role_key,
        "label": role["label"],
        "family": fam,
        "tagline": role["tagline"],
        "goal": role["goal"],
        "color": role["color"],
        "topics": topics,
        "rings": rings,
        "stats": {
            "total": len(items),
            "books": by_type.get("book", 0),
            "courses": by_type.get("course", 0),
            "docs": by_type.get("doc", 0),
            "articles": by_type.get("article", 0),
        },
    }


# ── Phase 3：个性化规划（结构化目标 → 策展库内重排序，纯规则，绝不生成书名）──

# 模拟的时长维度（先用占位值，等有真实页数/学时再校准）
_HOURS = {"book": lambda d: 2 * max(1, min(5, d)), "course": lambda d: 6,
          "doc": lambda d: 1, "article": lambda d: 0.5}
_STANCE_RANK = {"now": 0, "invest": 1, "know": 2}


def goals() -> list:
    return json.loads(GOALS.read_text())["goals"]


def plan(goal_id: str, days: int = 30, read_ids=None) -> dict:
    """按目标 + 时限 + 阅读史，在策展库内规划一条学习路径。

    只重排序、只在库内选，绝不生成书名。输出每步都带「为什么」（立场 + 理由）。
    """
    res, roles = _load()
    read_ids = set(read_ids or [])
    goal = next((g for g in goals() if g["id"] == goal_id), None)
    if not goal:
        return {"error": "未知目标", "steps": []}
    fam = roles.get(goal["role"], {}).get("family")
    topics = set(goal.get("topics") or [])

    cands = [r for r in res if fam in r["families"] and r["id"] not in read_ids]

    def key(r):
        topic_hit = 0 if (set(r["topics"]) & topics) else 1   # 命中目标主题的排前
        return (topic_hit, _STANCE_RANK.get(r["stance"], 3), r["difficulty"], -r["rec"])
    cands.sort(key=key)

    budget = max(6, days * 1.0)          # 模拟：约 1 小时/天
    steps, total = [], 0.0
    for r in cands:
        h = _HOURS.get(r["rtype"], lambda d: 2)(r["difficulty"])
        if steps and total + h > budget and len(steps) >= 3:
            break
        total += h
        steps.append({
            "id": r["id"], "title": r["title"], "rtype": r["rtype"],
            "family": r["family"], "stance": r["stance"], "difficulty": r["difficulty"],
            "hours": h,
            "why": f"{STANCE_LABEL.get(r['stance'],'')} · {(r.get('reason') or '').strip()[:40]}",
            "on_topic": bool(set(r["topics"]) & topics),
        })
        if len(steps) >= 7:
            break

    return {
        "goal": goal["title"], "role": goal["role"],
        "role_label": roles.get(goal["role"], {}).get("label", ""),
        "color": roles.get(goal["role"], {}).get("color", "#16181d"),
        "level": goal["level"], "days": days,
        "total_hours": round(total, 1), "steps": steps,
        "note": "在策展库内按你的目标与时限重排（模拟时长维度）",
    }


def stats() -> dict:
    res, roles = _load()
    from collections import Counter
    ty = Counter(r["rtype"] for r in res)
    st = Counter(r["stance"] for r in res)
    return {
        "total": len(res),
        "books": ty.get("book", 0),
        "courses": ty.get("course", 0),
        "docs": ty.get("doc", 0),
        "articles": ty.get("article", 0),
        "now": st.get("now", 0),
        "invest": st.get("invest", 0),
        "know": st.get("know", 0),
        "families": len(roles),
    }


if __name__ == "__main__":
    import sys
    print("stats:", json.dumps(stats(), ensure_ascii=False))
    key = sys.argv[1] if len(sys.argv) > 1 else "applied"
    r = radar(key)
    print(f"\n族「{r['label']}」· {r['stats']['total']} 项 · {r['stats']}")
    for ring in r["rings"]:
        print(f"\n  ◍ {ring['label']}（{ring['count']}）")
        for i in ring["items"]:
            print(f"    · [{i['rtype']}] {i['title'][:44]}")
