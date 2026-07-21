"""把雷达渲染成文本。

先做文本，不做图 —— 因为要验证的是**判断本身站不站得住**。
如果这些判断你看了觉得是废话，再漂亮的雷达图也救不回来。
"""

import sys

import personalize

QUADRANTS = {
    "foundations": "基础与理论",
    "models": "模型与算法",
    "systems": "工程与系统",
    "applied": "产品与应用",
}

RING_LABEL = {
    "adopt": "ADOPT  现在就读",
    "trial": "TRIAL  值得投入",
    "assess": "ASSESS 知道即可",
}

# 难度 = blip 符号，不占用环。
# 环回答「该不该你现在读」，符号回答「门槛有多高」—— 两个正交维度。
SYMBOL = {"entry": "●", "intermediate": "◆", "hardcore": "▲"}
DIFF_LABEL = {"entry": "入门", "intermediate": "进阶", "hardcore": "硬核"}

W = 78


def rule(ch: str = "─") -> str:
    return ch * W


def main() -> None:
    key = sys.argv[1] if len(sys.argv) > 1 else "llm-app-dev"
    data = personalize.run(key)

    profile, result, dead, lib = (
        data["profile"],
        data["result"],
        data["dead"],
        data["library"],
    )

    print(rule("═"))
    print(f"  AI 读书雷达  ·  {profile['label']}")
    print(f"  目标：{profile['goal']}")
    print(rule("═"))
    print(f"\n  {result['note']}\n")
    print(f"  环 = 立场（该不该你现在读）   符号 = 难度  ● 入门  ◆ 进阶  ▲ 硬核\n")

    by_ring = {r: [] for r in ("adopt", "trial", "assess")}
    for p in result["placements"]:
        by_ring[p["ring"]].append(p)

    for ring in ("adopt", "trial", "assess"):
        items = by_ring[ring]
        print(rule())
        print(f"  {RING_LABEL[ring]}   ({len(items)})")
        print(rule())
        if not items:
            print("    （空）\n")
            continue
        for p in items:
            b = lib[p["isbn"]]
            q = QUADRANTS.get(b["quadrant"], b["quadrant"])
            sym = SYMBOL[b["difficulty"]]
            diff = DIFF_LABEL[b["difficulty"]]
            print(f"\n  {sym} {b['title']}")
            print(f"    {b['authors'][0]}, {b['published']}  ·  {q}  ·  {diff}")
            print(f"    {p['reason']}")
        print()

    # Hold 环是客观的：对所有人一致，不因画像变化。
    print(rule())
    print(f"  HOLD   不必读了   ({len(dead)})   ← 与画像无关，对所有人一致")
    print(rule())
    for b in dead:
        print(f"\n  ✗ {b['title']}")
        print(f"    {b['authors'][0]}, {b['published']}")
        for e in b["decay_result"]["evidence"]:
            print(f"    → {e}")
    print()

    # 「由浅入深」落在这里 —— 是一条路径，不是一个圈层。
    # 路径能表达顺序和依赖（读完 A 才读得动 B），圈层不能；而且路径因人而异。
    path = result.get("path", [])
    if path:
        print(rule())
        print("  阅读路径（由浅入深）")
        print(rule())
        for i, isbn in enumerate(path, 1):
            b = lib[isbn]
            sym = SYMBOL[b["difficulty"]]
            print(f"    {i}. {sym} {b['title']}  ({DIFF_LABEL[b['difficulty']]})")
        print()


if __name__ == "__main__":
    main()
