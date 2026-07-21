"""排环引擎（阶段一：纯规则，无 LLM）。

分工回顾：
  decay.py       书死没死 —— 客观，对所有人一致        （Hold 环）
  placement.py   该不该你现在读 —— 因人而异            （内三环）  ← 本文件

阶段一刻意不上 LLM。不是因为贵（Opus 一次 5.6 分钱），
而是因为 **AI 现在没有燃料**：没有真实的打分数据，AI 的「因人而异」
就是凭先验瞎猜。先用规则跑通、收打分、攒矩阵，阶段二 AI 再进来。

personalize.py（LLM 版）作为可选升级保留，接口一致。
"""

import json
from pathlib import Path
from typing import Dict, List

import decay

ROOT = Path(__file__).resolve().parent.parent
ROLES = ROOT / "data" / "roles.json"

# 角色 × 象限的相关度。这是排环的主信号。
# 五角色对齐 PRD 的 AIPM/Researcher/Engineer/Data Scientist + 我们保留的 LLM 应用开发者。
AFFINITY = {
    "researcher":      {"foundations": 10, "models": 9, "systems": 3, "applied": 2},
    "ml-engineer":     {"foundations": 6,  "models": 9, "systems": 8, "applied": 3},
    "applied-llm-dev": {"foundations": 3,  "models": 6, "systems": 10, "applied": 5},
    "ai-pm":           {"foundations": 2,  "models": 3, "systems": 5, "applied": 10},
    # 数据科学家：统计/因果理论最重，数据工具其次，可视化与决策落在 applied。
    "data-scientist":  {"foundations": 9,  "models": 6, "systems": 6, "applied": 5},
}

DIFF_RANK = {"entry": 0, "intermediate": 1, "hardcore": 2}
TOL_RANK = {"low": 0, "medium": 1, "high": 2}


def score(book: Dict, role: str, tol: str) -> float:
    """给一本书对这个人的「该不该现在读」打分。"""
    s = float(AFFINITY[role][book["quadrant"]])

    # 难度匹配：书比你能承受的难多少
    over = DIFF_RANK[book["difficulty"]] - TOL_RANK[tol]
    if over > 0:
        s -= over * 3.5           # 太难 —— 会劝退
    elif over < 0:
        s -= abs(over) * 0.8      # 太浅 —— 浪费时间，但伤害小得多

    # 经典有稳定性溢价：投入的时间不会白费
    if book["kind"] == "classic":
        s += 1.5

    # 当前范式的时效书，对工程/应用岗有额外价值
    if book["decay"]["paradigm"] in ("llm", "agentic") and role in ("applied-llm-dev", "ml-engineer"):
        s += 2.0

    return s


# blip 密度约束。雷达图上一个环挤太多点就没法看了 ——
# 这个视觉约束反过来逼迫排序做取舍，这是好事：
# 一份「什么都是 Adopt」的雷达等于没有观点。
ADOPT_CAP = 7
TRIAL_CAP = 12


def place(books: List[Dict], profile: Dict) -> List[Dict]:
    role, tol = profile["role"], profile["math_tolerance"]
    read = set(profile.get("read", []))

    cands = [b for b in books if b["isbn"] not in read]
    scored = sorted(cands, key=lambda b: (-score(b, role, tol), b["title"]))

QNAME = {
    "foundations": "基础与理论",
    "models": "模型与算法",
    "systems": "工程与系统",
    "applied": "产品与应用",
}


def place(books: List[Dict], profile: Dict) -> List[Dict]:
    role, tol = profile["role"], profile["math_tolerance"]
    read = set(profile.get("read", []))

    cands = [b for b in books if b["isbn"] not in read]
    scored = sorted(cands, key=lambda b: (-score(b, role, tol), b["title"]))

    out = []
    n_adopt = n_trial = 0

    for b in scored:
        s = score(b, role, tol)
        q = QNAME[b["quadrant"]]

        # 硬约束：数学承受度低的人，硬核书禁止进 adopt。
        # 那只会让他在第三章放弃，然后再也不回来。
        blocked = tol == "low" and b["difficulty"] == "hardcore"

        # 理由要讲清楚「为什么在这个环」，不是复述简介 ——
        # 「这是一本经典好书」是废话，用户已经知道了。
        if blocked:
            ring = "assess"
            reason = f"门槛超出你当前的数学承受度。硬啃它，多半会在第三章放弃 —— 等真的需要时再来查。"
        elif s >= 10 and n_adopt < ADOPT_CAP:
            ring, n_adopt = "adopt", n_adopt + 1
            reason = f"「{q}」是你的主战场，而这本是其中的地基。不读会有明显缺口。"
        elif s >= 6.5 and n_trial < TRIAL_CAP:
            ring, n_trial = "trial", n_trial + 1
            reason = f"有真价值，但不在你的主线上。要花几十小时 —— 先确认值得再投入。"
        else:
            ring = "assess"
            if b["difficulty"] == "hardcore":
                reason = f"「{q}」离你当前的目标较远，且门槛不低。知道它存在，需要时再来查。"
            else:
                reason = f"「{q}」离你当前的目标较远。知道它存在就够了，不必通读。"

        out.append({**b, "ring": ring, "reason": reason, "score": round(s, 1), **links(b)})

    return out


def links(b: Dict) -> Dict:
    """跳转链接。Open Library 是权威条目（ISBN 已回验过，必然打得开）；
    豆瓣按书名搜 —— 中文读者大多在那里找中译本和评论。"""
    from urllib.parse import quote

    return {
        "link_openlibrary": f"https://openlibrary.org/isbn/{b['isbn']}",
        "link_douban": f"https://search.douban.com/book/subject_search?search_text={quote(b['title'])}",
    }


def reading_path(placed: List[Dict]) -> List[str]:
    """「由浅入深」落在这里 —— 是一条路径，不是一个圈层。
    只取 adopt 环，按难度排序：能直接上手的在前，需要前置知识的在后。
    """
    adopt = [b for b in placed if b["ring"] == "adopt"]
    adopt.sort(key=lambda b: (DIFF_RANK[b["difficulty"]], -b["score"]))
    return [b["isbn"] for b in adopt]


def build(profile_key: str) -> Dict:
    roles = json.loads(ROLES.read_text())["roles"]
    if profile_key not in roles:
        raise KeyError(profile_key)
    profile = roles[profile_key]

    assessed = decay.run()
    alive = [b for b in assessed if b["decay_result"]["verdict"] == "alive"]
    dead = [b for b in assessed if b["decay_result"]["verdict"] == "dead"]

    placed = place(alive, profile)

    return {
        "profile": {"key": profile_key, **profile},
        "rings": {
            r: [b for b in placed if b["ring"] == r]
            for r in ("adopt", "trial", "assess")
        },
        # Hold 是客观的：不因画像变化，对所有人一致。
        "hold": [
            {
                **b,
                "ring": "hold",
                "reason": "；".join(b["decay_result"]["evidence"]),
                "rule": b["decay_result"]["rule"],
                **links(b),
            }
            for b in dead
        ],
        "path": reading_path(placed),
        "stats": {
            "total": len(assessed),
            "alive": len(alive),
            "dead": len(dead),
        },
    }


if __name__ == "__main__":
    import sys

    key = sys.argv[1] if len(sys.argv) > 1 else "applied-llm-dev"
    d = build(key)
    print(f"\n{d['profile']['label']}  ·  {d['profile']['goal']}\n")
    for r in ("adopt", "trial", "assess"):
        print(f"  {r.upper():<7} {len(d['rings'][r]):>2} 本")
    print(f"  HOLD    {len(d['hold']):>2} 本  (客观，对所有人一致)")
    print(f"\n  ADOPT 环:")
    for b in d["rings"]["adopt"]:
        sym = {"entry": "●", "intermediate": "◆", "hardcore": "▲"}[b["difficulty"]]
        print(f"    {sym} [{b['score']:>4}] {b['title'][:52]}")
