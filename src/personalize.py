"""个性化引擎 —— 把存活的书排进内三环。

分工（这是整个架构的关键）：
  衰变引擎（decay.py）  判断书死没死 —— 纯规则，对所有人一致，无 LLM
  个性化引擎（本文件）  判断该不该你现在读 —— 因人而异，用 LLM

LLM 在这里做两件事，且只做这两件事：
  1. 把「书 × 人」映射到环（Adopt / Trial / Assess）
  2. 把已有的证据写成一句人话理由

它**不能**做的事：
  - 不能生成书名。只能从传进去的候选里选，返回的 ISBN 必须在库内 —— 强制校验。
  - 不能判断书死没死。那是衰变引擎的活，结论已经定了。
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

import anthropic

import decay

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "data" / "profiles.json"

MODEL = "claude-opus-4-8"

RINGS = ["adopt", "trial", "assess"]

SYSTEM = """你是一个面向 AI 从业者的读书雷达的定位引擎。

雷达的环表达**立场**，不是难度：

  adopt  — 现在就读。对这个人当前的目标来说是地基性的，不读会有明显缺口。
  trial  — 值得投入。有真价值，但不普适；要花几十小时，得确认值得。
  assess — 知道即可。不必通读；是参考书，或理念重要但可按需查阅。

（第四个环 hold「不必读了」不归你管 —— 那是书本身的客观属性，已经由规则引擎判完了。
你面前的每一本书都是活的。）

**难度不是环。** 每本书带一个 difficulty（entry 入门 / intermediate 进阶 / hardcore 硬核），
它是 blip 的符号，独立于环。一本硬核书可以是 adopt（研究员该现在就啃），
一本入门书也可以是 assess（跟你的目标无关，知道就行）。
「是不是经典」「难不难」「该不该你现在读」是三个正交的维度 —— 别把它们搅在一起。

铁律：
1. 你只能从给定的候选书目里选。绝对不能提到、推荐、或编造任何不在列表里的书。
2. 每本候选书都必须被分配到一个环 —— 不能漏，不能重复。
3. 理由必须落到这个人的具体情况上（他的目标、水平、已读的书、时间预算）。
   「这是一本经典好书」是废话，不要写。要写「因为你的目标是 X，而这本书给你 Y」。
4. 已读过的书不要再放进雷达。
5. 数学承受度是硬约束。math_tolerance = low 的人，hardcore 的书**不能**放 adopt ——
   那只会让他在第三章放弃，然后再也不回来。放 assess，并在理由里说清楚
   「等你需要时再来查」。math_tolerance = high 的人则反过来：别怕给他硬书。
6. path（阅读路径）是「由浅入深」落地的地方：只放 adopt 环的书，
   **按难度和依赖排序** —— 能直接上手的在前，需要前置知识的在后。
   路径要体现真实的学习顺序，不是重要性排序。

理由用中文，每条不超过 45 字，说人话，别客套。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "placements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "isbn": {"type": "string"},
                    "ring": {"type": "string", "enum": RINGS},
                    "reason": {"type": "string"},
                },
                "required": ["isbn", "ring", "reason"],
                "additionalProperties": False,
            },
        },
        "path": {
            "type": "array",
            "description": "建议的阅读顺序，只包含 adopt 环的 ISBN",
            "items": {"type": "string"},
        },
        "note": {
            "type": "string",
            "description": "给这个人的一句话总结：这张雷达的核心主张是什么",
        },
    },
    "required": ["placements", "path", "note"],
    "additionalProperties": False,
}


def build_candidates(alive: List[Dict], profile: Dict) -> List[Dict]:
    """把存活书目整理成喂给模型的候选集，排除已读。"""
    read = set(profile.get("read", []))
    out = []
    for b in alive:
        if b["isbn"] in read:
            continue
        out.append(
            {
                "isbn": b["isbn"],
                "title": b["title"],
                "authors": b["authors"],
                "published": b["published"],
                "quadrant": b["quadrant"],
                "difficulty": b["difficulty"],
                "content_type": b["decay"]["content_type"],
                "paradigm": b["decay"]["paradigm"],
                "curator_note": b["note"],
                "decay_evidence": b["decay_result"]["evidence"],
            }
        )
    return out


def place(profile: Dict, candidates: List[Dict]) -> Dict:
    client = anthropic.Anthropic()

    read_titles = profile.get("read", [])
    user_msg = f"""这个人的画像：

  角色：{profile['role']}
  当前目标：{profile['goal']}
  数学承受度：{profile['math_tolerance']}
  每周可投入：{profile['time_budget']}
  已读过（不要再推荐）：{read_titles or '无'}

候选书目（全部存活，你只能从这里选）：

{json.dumps(candidates, ensure_ascii=False, indent=2)}

把每一本候选书放进 adopt / trial / assess，并给出理由。"""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        messages=[{"role": "user", "content": user_msg}],
    )

    if resp.stop_reason == "refusal":
        raise RuntimeError(f"模型拒绝了请求: {resp.stop_details}")

    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


def validate(result: Dict, candidates: List[Dict]) -> List[str]:
    """防幻觉闸门。模型返回的每一个 ISBN 都必须在候选集里。

    这不是可选的健全性检查 —— 这是产品可信的前提。
    一旦模型能塞进一本不存在的书，整张雷达就一文不值。
    """
    valid = {c["isbn"] for c in candidates}
    errors = []

    seen = set()
    for p in result["placements"]:
        if p["isbn"] not in valid:
            errors.append(f"幻觉 ISBN（不在候选集内）: {p['isbn']} — {p.get('reason','')[:30]}")
        if p["isbn"] in seen:
            errors.append(f"重复放置: {p['isbn']}")
        seen.add(p["isbn"])

    for missing in valid - seen:
        errors.append(f"漏掉了候选书: {missing}")

    for isbn in result.get("path", []):
        if isbn not in valid:
            errors.append(f"阅读路径里有幻觉 ISBN: {isbn}")

    return errors


def run(profile_key: str) -> Dict:
    profiles = json.loads(PROFILES.read_text())["profiles"]
    if profile_key not in profiles:
        raise SystemExit(f"未知画像 '{profile_key}'。可选: {', '.join(profiles)}")
    profile = profiles[profile_key]

    assessed = decay.run()
    alive = [b for b in assessed if b["decay_result"]["verdict"] == "alive"]
    dead = [b for b in assessed if b["decay_result"]["verdict"] == "dead"]

    candidates = build_candidates(alive, profile)
    print(f"画像: {profile['label']}", file=sys.stderr)
    print(f"候选 {len(candidates)} 本（存活 {len(alive)}，已读排除 {len(alive)-len(candidates)}）", file=sys.stderr)
    print(f"调用 {MODEL} ...", file=sys.stderr)

    result = place(profile, candidates)

    errors = validate(result, candidates)
    if errors:
        print("\n✗ 校验失败 —— 模型输出不可信：", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        raise SystemExit(1)
    print("✓ 防幻觉校验通过：所有 ISBN 均在库内\n", file=sys.stderr)

    lib = {b["isbn"]: b for b in assessed}
    return {"profile": profile, "result": result, "dead": dead, "library": lib}


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "llm-app-dev"
    print(json.dumps(run(key), ensure_ascii=False, indent=2))
