"""衰变引擎 —— 判断一本书是不是已经死了。

**这里没有 LLM，一行都没有。**

这是整个产品的核心论点：一本 AI 书是否过时，可以从结构化事实机械地推出来，
不需要（也不应该）让模型凭印象判断。模型会给你一个听起来很有道理、
但完全不可靠的答案。

判断来自规则和人工标注的证据；LLM 只负责把结论写成人话（见 personalize.py）。

输出的 `evidence` 字段是给 LLM 的原料，也是给用户看的申诉依据 ——
每一个 Hold 都必须能指着一条具体的事实说"因为这个"。
"""

import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data" / "books.json"

# 范式代际。
#
# ⚠️ 注意这里刻意「不」用它做生死判断。
#
# 原型第一版曾经这么干：把 paradigm 当成一条线性阶梯，落后当前 2 代以上的
# 动手书一律判死。结果它把 Hands-On ML 第 3 版（2022，当前最好的入门书）
# 和 Chollet 的 Deep Learning with Python 全判死了。
#
# 错在哪：AI 不是一条线性阶梯。agent 没有淘汰监督学习，transformer 没有淘汰
# 梯度提升树在表格数据上的地位。它们是不同的层，不是先后的代。
# 拿单一的「当前范式」去量每一本书，就会机械地处死所有不讲最新东西的书。
#
# 所以 paradigm 只留作**信息**，喂给个性化层参考「这本书有多新」，
# 不参与生死判断。生死只由能被独立核实的硬事实决定。
PARADIGMS = ["pre-dl", "dl", "pre-transformer", "transformer", "llm", "agentic"]
CURRENT = "agentic"

# 已经废弃的框架大版本。绑死了这些的动手书，今天读只会学到错的心智模型。
DEAD_APIS = {
    "tensorflow-1.x": "TensorFlow 1.x（静态图时代，API 已彻底重写）",
    "keras-legacy": "Keras 旧版 API",
    "nltk": "NLTK 流水线（已被 transformer 全面取代）",
    "theano": "Theano（项目已停止维护）",
    "caffe": "Caffe（已停止维护）",
}


def generation_gap(paradigm: str) -> int:
    """这本书的范式落后当前几代 —— 仅供参考，不参与判死。"""
    return PARADIGMS.index(CURRENT) - PARADIGMS.index(paradigm)


def assess(book: Dict, library: Dict[str, Dict]) -> Dict:
    """对一本书跑衰变规则。返回 alive/dead + 证据链。

    判死只有三条规则，每一条都建立在**能被独立核实的硬事实**上：
    有没有新版、绑没绑死框架、策展人有没有明确判定它教的技术已被取代。

    刻意不做的：不从「出版年 + 范式」推断死活。那是幻觉的另一种形式 ——
    只不过幻觉的主体从 LLM 换成了一条拍脑袋的规则。
    """
    d = book["decay"]
    ev: List[str] = []

    # 规则 1：有更新版次 —— 最硬的信号，零争议。
    if d["superseded_by"]:
        for isbn in d["superseded_by"]:
            newer = library.get(isbn)
            label = f"《{newer['title']}》" if newer else isbn
            ev.append(f"已被更新版次取代：{label}")
        return {"verdict": "dead", "rule": "superseded_edition", "evidence": ev}

    # 规则 2：绑死了已废弃的框架大版本。可核实，无争议。
    dead_pins = [p for p in d["pinned_apis"] if p in DEAD_APIS]
    if dead_pins:
        for p in dead_pins:
            ev.append(f"绑定已废弃的技术栈：{DEAD_APIS[p]}")
        return {"verdict": "dead", "rule": "dead_api", "evidence": ev}

    # 规则 3：策展人明确判定「它教的技术路线已被取代」。
    #
    # 这一条是人的判断，不是算出来的 —— 因为它本来就不可能算出来。
    # 要求填 reason，让每个 Hold 都能被指着申诉。这是 Hold 环可信的代价。
    st = d.get("superseded_technique")
    if st:
        ev.append(f"技术路线已被取代：{st}")
        return {"verdict": "dead", "rule": "superseded_technique", "evidence": ev}

    # 活着。剩下的都是「有多新」的信息，交给个性化层去权衡。
    gap = generation_gap(d["paradigm"])
    if d["content_type"] == "theory":
        ev.append("理论/数学著作 —— 不随框架演进衰变")
    elif gap == 0:
        ev.append("当前范式")
    elif gap == 1:
        ev.append("范式落后 1 代，仍然主流")
    else:
        ev.append(f"范式落后 {gap} 代（{d['paradigm']}）—— 不代表过时，但读之前想清楚你要什么")

    if d["pinned_apis"]:
        ev.append(f"绑定技术栈 {', '.join(d['pinned_apis'])} —— 框架大版本变更时需重新评估")

    return {"verdict": "alive", "rule": "alive", "evidence": ev}


def load_library() -> Dict[str, Dict]:
    data = json.loads(BOOKS.read_text())
    return {b["isbn"]: b for b in data["books"]}


def run() -> List[Dict]:
    library = load_library()
    out = []
    for book in library.values():
        r = assess(book, library)
        out.append({**book, "decay_result": r})
    return out


if __name__ == "__main__":
    results = run()
    dead = [b for b in results if b["decay_result"]["verdict"] == "dead"]
    alive = [b for b in results if b["decay_result"]["verdict"] == "alive"]

    print("=" * 78)
    print(f"衰变引擎  —  {len(alive)} 本存活 / {len(dead)} 本判死")
    print("=" * 78)

    print(f"\n【HOLD — 不必读了】 {len(dead)} 本\n")
    for b in dead:
        print(f"  ✗ {b['title']}")
        print(f"    {b['authors'][0]}, {b['published']}   [规则: {b['decay_result']['rule']}]")
        for e in b["decay_result"]["evidence"]:
            print(f"    → {e}")
        print()

    print(f"\n【存活 — 进入个性化排序】 {len(alive)} 本\n")
    for b in alive:
        print(f"  ✓ {b['title'][:56]}")
        print(f"    [{b['decay_result']['rule']}] {b['decay_result']['evidence'][0]}")
        print()
