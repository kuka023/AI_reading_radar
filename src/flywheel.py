"""飞轮引擎（Phase 2）：把用户信号 → 准入/降级的专家评审队列。

阈值见 SPEC-evolution-v1.md §3（v0，待专项讨论后修订）。
现阶段用**模拟信号**驱动，真实流量够了再把 signal 源切到 db（shelf/reviews）。

铁律：飞轮只产出**候选队列**，是否入雷达由专家评审拍板 —— 人工闸门不可省。
"""

# ── 阈值 v0 ──
PROMOTE = {"R_MIN": 8, "S_MIN": 5, "SBAR_MIN": 4.2, "USEFUL_MIN": 0.70}
DEMOTE = {"R_MIN": 8, "SBAR_MAX": 2.5, "USEFUL_MAX": 0.35}


def _metrics(s: dict) -> dict:
    """由原始信号算派生指标。s: {V,R,S,sbar,U_high,U_some,U_none}。"""
    uh, us, un = s.get("U_high", 0), s.get("U_some", 0), s.get("U_none", 0)
    ut = uh + us + un
    useful_rate = (uh + 0.5 * us) / ut if ut else 0.0
    V = s.get("V", 0)
    return {
        "V": V, "R": s.get("R", 0), "S": s.get("S", 0),
        "sbar": s.get("sbar", 0.0),
        "useful_rate": round(useful_rate, 2),
        "conversion": round(s.get("R", 0) / V, 2) if V else 0.0,
    }


def assess_promote(cands: list) -> list:
    """候选书（不在雷达）→ 准入评审。四项全过才入队。按有用度排序（防热门偏差）。"""
    out = []
    for c in cands:
        m = _metrics(c["signals"])
        checks = {
            "读过人数 ≥ 8": m["R"] >= PROMOTE["R_MIN"],
            "带分推荐 ≥ 5": m["S"] >= PROMOTE["S_MIN"],
            "推荐分 ≥ 4.2": m["sbar"] >= PROMOTE["SBAR_MIN"],
            "有用度 ≥ 70%": m["useful_rate"] >= PROMOTE["USEFUL_MIN"],
        }
        out.append({
            "title": c["title"], "authors": c.get("authors", []),
            "metrics": m, "checks": checks,
            "verdict": "promote" if all(checks.values()) else "hold",
            "fails": [k for k, v in checks.items() if not v],
        })
    # 队列按有用度转化率排序，而非热度 —— 让冷门好书也能浮上来
    out.sort(key=lambda x: (-x["metrics"]["useful_rate"], -x["metrics"]["sbar"]))
    return out


def assess_demote(items: list) -> list:
    """雷达在册书 → 降级评审。任一低分信号即入队。"""
    out = []
    for it in items:
        m = _metrics(it["signals"])
        reasons = []
        if m["R"] >= DEMOTE["R_MIN"] and m["sbar"] <= DEMOTE["SBAR_MAX"]:
            reasons.append(f"读过 {m['R']} 人但均分仅 {m['sbar']}")
        if m["useful_rate"] <= DEMOTE["USEFUL_MAX"] and (it["signals"].get("U_high", 0)
                + it["signals"].get("U_some", 0) + it["signals"].get("U_none", 0)) >= DEMOTE["R_MIN"]:
            reasons.append(f"有用度仅 {int(m['useful_rate']*100)}%")
        if it.get("decayed"):
            reasons.append("衰变引擎判定过时")
        if reasons:
            out.append({"title": it["title"], "metrics": m,
                        "verdict": "demote", "reasons": reasons})
    return out


def simulate() -> dict:
    """模拟信号：造几本候选书与几本在册书，覆盖『通过/热门但读者少/低分』等情形。"""
    promote_cands = [
        {"title": "Prompt Engineering for LLMs", "authors": ["John Berryman"],
         "signals": {"V": 60, "R": 12, "S": 8, "sbar": 4.5, "U_high": 8, "U_some": 2, "U_none": 1}},
        {"title": "Building LLM Powered Applications", "authors": ["Valentina Alto"],
         "signals": {"V": 80, "R": 15, "S": 9, "sbar": 4.3, "U_high": 9, "U_some": 3, "U_none": 2}},
        {"title": "AI Superpowers", "authors": ["Kai-Fu Lee"],
         "signals": {"V": 40, "R": 6, "S": 3, "sbar": 4.6, "U_high": 5, "U_some": 1, "U_none": 0}},
        {"title": "The AI-First Company", "authors": ["Ash Fontana"],
         "signals": {"V": 70, "R": 9, "S": 6, "sbar": 3.8, "U_high": 3, "U_some": 3, "U_none": 3}},
        {"title": "某本蹭热点的 LLM 书", "authors": [],
         "signals": {"V": 55, "R": 10, "S": 7, "sbar": 2.3, "U_high": 1, "U_some": 2, "U_none": 6}},
    ]
    demote_items = [
        {"title": "AI Risk Management Framework",
         "signals": {"V": 30, "R": 9, "S": 5, "sbar": 2.4, "U_high": 1, "U_some": 2, "U_none": 6}},
        {"title": "DAMA-DMBOK: Data Management Body of Knowledge",
         "signals": {"V": 25, "R": 8, "S": 4, "sbar": 3.1, "U_high": 1, "U_some": 2, "U_none": 6}},
    ]
    return {"promote_candidates": promote_cands, "demote_candidates": demote_items}


def run() -> dict:
    sim = simulate()
    promote = assess_promote(sim["promote_candidates"])
    demote = assess_demote(sim["demote_candidates"])
    return {
        "simulated": True,
        "thresholds": {"promote": PROMOTE, "demote": DEMOTE},
        "promote": promote,
        "demote": demote,
        "note": "模拟信号驱动。真实活跃评分用户约 50 人前，准入以专家手工加书为主。",
    }


if __name__ == "__main__":
    import json
    r = run()
    print("准入队列（按有用度排序）:")
    for c in r["promote"]:
        mark = "✅ 建议入雷达" if c["verdict"] == "promote" else "⏸ 不满足：" + "、".join(c["fails"])
        m = c["metrics"]
        print(f"  {c['title'][:40]:<40} R{m['R']} S{m['S']} 分{m['sbar']} 有用{int(m['useful_rate']*100)}%  {mark}")
    print("\n降级队列:")
    for c in r["demote"]:
        print(f"  {c['title'][:40]:<40} {'、'.join(c['reasons'])}")
