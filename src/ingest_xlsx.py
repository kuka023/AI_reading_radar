"""把业务共建的 xlsx 资料库 → 雷达的规范数据源 data/resources.json。

职责链：
  1. 读 xlsx 全量行
  2. 分类资料类型：book / course / doc / article（业务把课程与文档混在一个类型里，这里拆开以便一眼可辨）
  3. 归族：能力主题前缀 → 8 个业务能力族；同一资料出现在多族则合并 families
  4. 去重合并：同名资料只保留一个天体，聚合它的 families / topics / 推荐程度
  5. 附属链接折叠：O'Reilly 图书页 / Manning 图书页 / 播客 / 配套 GitHub 这类「书的买/看链接」不单独成星球，
     折进对应书的 companions 里 —— 否则雷达会被商店链接噪声淹没
  6. 策展层（人工观点）：立场 stance / 难度 difficulty / 材质 content_type
  7. 书籍过 ISBN 核实（查无也保留，标 metadata 待补）

立场语义（环）：now=现在就读 / invest=值得投入 / know=知道即可。
这是「有观点的策展」，不是业务给的推荐程度（那只有强弱）。
"""

import json
import re
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "AI-Native读书雷达·资料共建(1).xlsx"
OUT = ROOT / "data" / "resources.json"

# ── 能力主题 → 族 简称 ──
FAMILY_LABEL = {
    "全员通用": "全员通用",
    "技术-应用": "技术·应用",
    "技术-数据": "技术·数据",
    "技术-平台": "技术·平台",
    "产品": "产品",
    "测试": "测试",
    "项目管理": "项目管理",
    "FDE": "FDE",
}


def parse_topic(topic: str):
    """『【技术-应用】LLM应用技术选型与架构设计』→ (['技术-应用'], 'LLM应用技术选型与架构设计')

    多主题行（用逗号连了多个【..】）→ 收集全部族。
    """
    if not topic:
        return [], ""
    fams = re.findall(r"【([^】]+)】", topic)
    # 主题名 = 最后一个【】之后的文字
    sub = topic.split("】")[-1].strip(" ,，")
    fams = [f.strip() for f in fams] or ["全员通用"]
    return fams, sub


# ── 资料类型细分：course / doc（业务的「在线课程/官方文档」拆开）──
DOC_HINT = ("官方文档", "官网", "官方规范", "规范", "Documentation",
            "SRE Books", "Responsible Scaling", "RMF官网", "library/view", "O'Reilly图书页",
            "Manning图书页", "O'Reilly Blog")
COURSE_HINT = ("课程", "Specialization", "Course", "教程", "培训", "学习中心",
               "学习路径", "GraphAcademy", "Skills Boost", "Maven", "DeepLearning",
               "认证", "Skilljar")


def classify(name: str, rtype: str) -> str:
    if rtype == "书籍":
        return "book"
    if rtype == "文章/其他资料":
        return "article"
    # 在线课程/官方文档 —— 拆
    if any(h in name for h in COURSE_HINT):
        return "course"
    if any(h in name for h in DOC_HINT):
        return "doc"
    return "doc"


# ── 附属链接：不单独成星球，折进对应书 ──
APPENDAGE = ("图书页", "library/view", "liveBook", "配套", "aie-book",
             "播客访谈", "Coursera Blog", "Skilljar版")


def is_appendage(name: str) -> bool:
    return any(h in name for h in APPENDAGE)


# ── 书名归一 → slug（用于合并 + 策展表匹配）──
def book_slug(title: str) -> str:
    t = title.strip().strip("《》").strip()
    t = re.sub(r"[:：].*$", "", t)               # 去副标题
    t = re.sub(r",?\s*(Second|2nd)\s+Edition", "", t, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", t.lower())


# ── 策展层：书籍（我的观点）──
# slug -> (difficulty 1-5, content_type idea/tool, stance now/invest/know)
BOOK_CURATION = {
    "aiengineering":               (4, "tool", "now"),
    "designinglargelanguagemodelapplications": (3, "tool", "now"),
    "handsonlargelanguagemodels":  (3, "tool", "now"),
    "buildingasecondbrain":        (1, "idea", "invest"),
    "aiagentsinaction":            (3, "tool", "invest"),
    "evalsforaiengineers":         (3, "tool", "invest"),
    "asimpleguidetoretrievalaugmentedgeneration": (2, "tool", "invest"),
    "designingdataintensiveapplications": (4, "tool", "invest"),
    "damadmbok":                   (3, "tool", "know"),
    "sitereliabilityengineering":  (3, "tool", "invest"),
    "airiskmanagementframework":   (2, "idea", "know"),
    "aiproductmanagement":         (2, "idea", "invest"),
    "bpmnmethodandstyle":          (2, "tool", "know"),
    "peopleaiguidebook":           (2, "idea", "invest"),
    "leadingchange":               (2, "idea", "invest"),
    "llmengineershandbook":        (4, "tool", "invest"),
    "designingmultiagentsystems":  (4, "tool", "invest"),
    "buildingagenticai":           (3, "tool", "invest"),
    "agenticaiengineering":        (4, "tool", "invest"),
    "generativeaidesignpatterns":  (4, "tool", "invest"),
    "systemdesignforlargelanguagemodels": (4, "tool", "invest"),
    "llmops":                      (4, "tool", "invest"),
    "aisystemsperformanceengineering": (5, "tool", "invest"),
    "masteringretrievalaugmentedgeneration": (4, "tool", "invest"),
    "本体驱动的ai数据管理":          (3, "tool", "know"),
}

# ── 策展层：非书资料 stance 覆盖（默认见 default_stance）──
# 用名字里的关键片段匹配
STANCE_OVERRIDE = [
    ("AI Fluency: Framework", "now"),        # 全员通用旗舰课
    ("Prompt Engineering Interactive", "now"),
    ("ChatGPT Prompt Engineering", "now"),
    ("Claude Code官方文档", "invest"),        # 一线开发天天用
    ("GitHub Copilot官方文档", "invest"),
    ("Automated Testing for LLMOps", "invest"),
    ("AI Evals For Engineers", "invest"),
    ("Definitive Guide to LLM Evaluation", "invest"),
]


def default_stance(rtype: str) -> str:
    return {"book": "invest", "course": "invest", "doc": "know", "article": "know"}[rtype]


def curated_stance(name: str, rtype: str) -> str:
    for frag, st in STANCE_OVERRIDE:
        if frag in name:
            return st
    return default_stance(rtype)


# 非书资料的默认体量（难度轴复用为「体量/权重」）
TYPE_SIZE = {"course": 3, "doc": 2, "article": 2}


def clean_title(name: str) -> str:
    return name.strip().strip("《》").strip()


def main():
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    ws = wb["推荐资料库"]
    raw = [r for r in ws.iter_rows(min_row=2, values_only=True) if r and r[0]]

    merged = {}          # key -> resource
    appendage_count = 0
    last_primary = None  # 最近一条非附属资料的 key —— 附属链接按行相邻折叠到它

    for name, rtype, link, topic, level, reason, who in raw:
        name = (name or "").strip()
        link = (link or "").strip()
        fams_raw, sub = parse_topic(topic or "")
        fams = [FAMILY_LABEL.get(f, f) for f in fams_raw]
        stars = (level or "").count("⭐") or 3
        kind = classify(name, rtype)

        # 附属链接（图书页/镜像/配套/播客）不单独成星球，折进相邻的上一条主资料。
        # 父资料可能是书，也可能是课程（如 Skilljar版 属于 AI Fluency 课程）。
        if is_appendage(name) and last_primary in merged:
            merged[last_primary]["companions"].append({"name": name, "link": link})
            appendage_count += 1
            continue

        if kind == "book":
            key = "book:" + book_slug(name)
        else:
            key = "res:" + re.sub(r"\s+", "", name.lower())[:50]

        if key not in merged:
            merged[key] = {
                "key": key, "title": clean_title(name), "rtype": kind,
                "families": [], "topics": [], "fam_topics": {}, "rec": stars,
                "reason": (reason or "").strip(), "link": link, "companions": [],
            }
        m = merged[key]
        for f in fams:
            if f not in m["families"]:
                m["families"].append(f)
            if sub:
                m["fam_topics"].setdefault(f, [])
                if sub not in m["fam_topics"][f]:
                    m["fam_topics"][f].append(sub)     # 记住这条资料在每个族里对应的主题
        if sub and sub not in m["topics"]:
            m["topics"].append(sub)
        m["rec"] = max(m["rec"], stars)
        if link and not m["link"]:
            m["link"] = link
        last_primary = key

    # 策展 + 定稿
    out = []
    for m in merged.values():
        if m["rtype"] == "book":
            slug = book_slug(m["title"])
            diff, content, stance = BOOK_CURATION.get(slug, (3, "tool", "invest"))
        else:
            diff = TYPE_SIZE.get(m["rtype"], 2)
            content = None
            stance = curated_stance(m["title"], m["rtype"])
        primary = m["families"][0] if m["families"] else "全员通用"
        out.append({
            "id": m["key"],
            "title": m["title"],
            "rtype": m["rtype"],
            "family": primary,
            "families": m["families"],
            "topic": m["topics"][0] if m["topics"] else "",
            "topics": m["topics"],
            "fam_topics": m["fam_topics"],
            "stance": stance,
            "difficulty": diff,
            "content_type": content,
            "rec": m["rec"],
            "link": m["link"],
            "reason": m["reason"],
            "companions": m["companions"],
            "isbn": None,
            "authors": [],
        })

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))

    # ── 汇报 ──
    from collections import Counter
    print(f"唯一天体: {len(out)}   （折叠附属链接 {appendage_count} 条）")
    print("类型:", dict(Counter(o["rtype"] for o in out)))
    print("立场:", dict(Counter(o["stance"] for o in out)))
    print("\n各族天体数:")
    fam_ct = Counter()
    for o in out:
        for f in o["families"]:
            fam_ct[f] += 1
    for f, c in fam_ct.most_common():
        print(f"  {c:3}  {f}")
    print("\n书籍清单（策展）:")
    for o in out:
        if o["rtype"] == "book":
            comp = f" +{len(o['companions'])}配套" if o["companions"] else ""
            print(f"  [{o['stance']:<6} d{o['difficulty']} {o['content_type']:<4}] {o['title'][:48]}{comp}")


if __name__ == "__main__":
    main()
