"""把 PRD 书单的增量并入 curation.json。

现有 59 本已覆盖 PRD 核心（DL/PRML/ESL/ISLR/RL/DDIA/ML Eng/SRE…）。
这里只补 PRD 有而我们没有的：
  - AIPM 的真 AI 产品专业书（用户明确要）
  - Data Scientist 的统计/因果/可视化（PRD 第 4 角色，我们缺）
  - Researcher 的理论补充（Convex Opt / PGM / CV / Nielsen）
  - 代表性软工/产品通识（归入最贴近的现有象限，不新增象限）
  - 中文书换英文原版（规则 A）
  - Hold 候选（规则 B：Murphy 老版被新版取代）

不写 ISBN —— 由 resolve_isbn.py 从 Open Library 校验，查无即淘汰。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUR = ROOT / "data" / "curation.json"

# 增量书目。decay.content_type 决定材质与衰变：theory/narrative=气态且不衰变，
# hands-on/systems=岩石；绑框架的实操标 pinned_apis 但框架仍活跳过判死。
NEW = [
    # ── AIPM · 真正的 AI 产品专业书（用户明确要补）──
    {"title": "Building Intelligent Systems", "author": "Geoff Hulten", "year": 2018,
     "quadrant": "applied", "difficulty": "intermediate", "kind": "classic",
     "decay": {"paradigm": "pre-transformer", "content_type": "systems"},
     "note": "怎么造一个真正的 AI 产品：从问题定义、数据、模型到线上迭代的产品视角。AIPM 少见的专业书。"},
    {"title": "The AI-First Company", "author": "Ash Fontana", "year": 2021,
     "quadrant": "applied", "difficulty": "entry", "kind": "classic",
     "decay": {"paradigm": "transformer", "content_type": "narrative"},
     "note": "AI 优先的公司怎么建：数据飞轮、护城河、组织。投资人视角，讲战略不讲模型。"},
    {"title": "Competing in the Age of AI", "author": "Marco Iansiti", "year": 2020,
     "quadrant": "applied", "difficulty": "entry", "kind": "classic",
     "decay": {"paradigm": "transformer", "content_type": "narrative"},
     "note": "哈佛商学院视角：AI 如何重构公司的运营核心与竞争边界。AIPM 的战略地图。"},
    {"title": "Human + Machine: Reimagining Work in the Age of AI", "author": "Paul Daugherty", "year": 2018,
     "quadrant": "applied", "difficulty": "entry", "kind": "classic",
     "decay": {"paradigm": "pre-transformer", "content_type": "narrative"},
     "note": "AI 不是取代人，是重排人机分工。讲落地的流程改造，比空谈未来实在。"},

    # ── AIPM · 产品/思维通识（选代表，归 applied）──
    {"title": "Inspired: How to Create Tech Products Customers Love", "author": "Marty Cagan", "year": 2017,
     "quadrant": "applied", "difficulty": "entry", "kind": "classic",
     "decay": {"paradigm": "dl", "content_type": "narrative"},
     "note": "产品管理的方法论经典。不讲 AI，但讲怎么做出人要的产品 —— PM 的地基。",
     "isbn_hint": "9781119387503"},
    {"title": "The Lean Startup", "author": "Eric Ries", "year": 2011,
     "quadrant": "applied", "difficulty": "entry", "kind": "classic",
     "decay": {"paradigm": "pre-dl", "content_type": "narrative"},
     "note": "验证学习循环。AI 产品尤其需要 —— 模型效果只有上线才知道。",
     "isbn_hint": "9780307887894"},
    {"title": "Thinking, Fast and Slow", "author": "Daniel Kahneman", "year": 2011,
     "quadrant": "applied", "difficulty": "intermediate", "kind": "classic",
     "decay": {"paradigm": "pre-dl", "content_type": "narrative"},
     "note": "人类决策的两个系统。理解人的偏差，才设计得好人机交互。",
     "isbn_hint": "9780374533557"},
    {"title": "The Design of Everyday Things", "author": "Don Norman", "year": 2013,
     "quadrant": "applied", "difficulty": "entry", "kind": "classic",
     "decay": {"paradigm": "pre-dl", "content_type": "narrative"},
     "note": "设计心理学经典。以人为中心的设计原理，AI 产品的交互地基。",
     "isbn_hint": "9780465050659"},

    # ── Researcher · 理论补充 ──
    {"title": "Convex Optimization", "author": "Stephen Boyd", "year": 2004,
     "quadrant": "foundations", "difficulty": "hardcore", "kind": "classic",
     "decay": {"paradigm": "pre-dl", "content_type": "theory"},
     "note": "凸优化圣经。理解 SVM、正则化、几乎所有训练算法的理论底座。免费 PDF。",
     "isbn_hint": "9780521833783"},
    {"title": "The Book of Why", "author": "Judea Pearl", "year": 2018,
     "quadrant": "foundations", "difficulty": "intermediate", "kind": "classic",
     "decay": {"paradigm": "pre-transformer", "content_type": "narrative"},
     "note": "因果推理的科普。从相关到因果，是当前 ML 最薄弱的一环。",
     "isbn_hint": "9780465097609"},
    {"title": "Neural Networks and Deep Learning", "author": "Michael Nielsen", "year": 2015,
     "quadrant": "foundations", "difficulty": "entry", "kind": "classic",
     "decay": {"paradigm": "pre-transformer", "content_type": "theory"},
     "note": "在线免费书，把反向传播讲得最直观的一本。入门神经网络的最短路径。"},
    {"title": "Computer Vision: Algorithms and Applications", "author": "Richard Szeliski", "year": 2022,
     "quadrant": "models", "difficulty": "intermediate", "kind": "classic",
     "decay": {"paradigm": "transformer", "content_type": "theory"},
     "note": "CV 综合教科书，第 2 版补上了深度学习方法。免费 PDF。"},
    {"title": "Probabilistic Graphical Models: Principles and Techniques", "author": "Daphne Koller", "year": 2009,
     "quadrant": "models", "difficulty": "hardcore", "kind": "classic",
     "decay": {"paradigm": "pre-dl", "content_type": "theory"},
     "note": "概率图模型权威。硬，但贝叶斯网络与推理的完整理论都在这。"},

    # ── Data Scientist · 统计/因果/可视化（新角色核心）──
    {"title": "Naked Statistics", "author": "Charles Wheelan", "year": 2013,
     "quadrant": "foundations", "difficulty": "entry", "kind": "classic",
     "decay": {"paradigm": "pre-dl", "content_type": "narrative"},
     "note": "把标准差、相关、回归讲成故事。数学恐惧者的统计入口。",
     "isbn_hint": "9780393347777"},
    {"title": "Practical Statistics for Data Scientists", "author": "Peter Bruce", "year": 2020,
     "quadrant": "foundations", "difficulty": "intermediate", "kind": "timely",
     "decay": {"paradigm": "dl", "content_type": "theory"},
     "note": "面向数据科学家的实用统计：A/B 测试、回归、聚类。够用不啰嗦。"},
    {"title": "Causal Inference in Statistics: A Primer", "author": "Judea Pearl", "year": 2016,
     "quadrant": "foundations", "difficulty": "intermediate", "kind": "classic",
     "decay": {"paradigm": "pre-transformer", "content_type": "theory"},
     "note": "因果推断入门教材，从有向无环图到后门准则。比《The Book of Why》技术。"},
    {"title": "Statistical Inference", "author": "George Casella", "year": 2001,
     "quadrant": "foundations", "difficulty": "hardcore", "kind": "classic",
     "decay": {"paradigm": "pre-dl", "content_type": "theory"},
     "note": "数理统计经典（换《概率论与数理统计》）。假设检验、估计理论的严谨底座。",
     "isbn_hint": "9780534243128"},
    {"title": "Bayesian Data Analysis", "author": "Andrew Gelman", "year": 2013,
     "quadrant": "foundations", "difficulty": "hardcore", "kind": "classic",
     "decay": {"paradigm": "dl", "content_type": "theory"},
     "note": "贝叶斯数据分析权威：层次模型、MCMC、模型检验。深。"},
    {"title": "Data Science from Scratch", "author": "Joel Grus", "year": 2019,
     "quadrant": "models", "difficulty": "entry", "kind": "timely",
     "decay": {"paradigm": "pre-transformer", "content_type": "hands-on"},
     "note": "从零用 Python 实现数据科学核心算法。理解底层原理，不调库。"},
    {"title": "Feature Engineering for Machine Learning", "author": "Alice Zheng", "year": 2018,
     "quadrant": "models", "difficulty": "intermediate", "kind": "timely",
     "decay": {"paradigm": "pre-transformer", "content_type": "hands-on"},
     "note": "特征工程专项：数值、文本、图像特征的编码与变换。经典 ML 时代仍适用。"},

    # ── Data Scientist · 数据工具（归 systems）──
    {"title": "Python Data Science Handbook", "author": "Jake VanderPlas", "year": 2022,
     "quadrant": "systems", "difficulty": "entry", "kind": "timely",
     "decay": {"paradigm": "transformer", "content_type": "hands-on", "pinned_apis": ["numpy", "pandas", "scikit-learn"]},
     "note": "NumPy/Pandas/Matplotlib/Sklearn 生态全景。数据科学的工具地图。",
     "isbn_hint": "9781098121228"},
    {"title": "Python for Data Analysis", "author": "Wes McKinney", "year": 2022,
     "quadrant": "systems", "difficulty": "entry", "kind": "timely",
     "decay": {"paradigm": "transformer", "content_type": "hands-on", "pinned_apis": ["pandas"]},
     "note": "Pandas 作者亲笔。数据清洗与处理的权威参考。绑 pandas 生态。",
     "isbn_hint": "9781098104030"},
    {"title": "Mining of Massive Datasets", "author": "Jure Leskovec", "year": 2020,
     "quadrant": "systems", "difficulty": "intermediate", "kind": "classic",
     "decay": {"paradigm": "dl", "content_type": "systems"},
     "note": "大规模数据挖掘（换《数据科学实战》原版）。MapReduce、相似性、流处理。免费 PDF。"},

    # ── Engineer · 软工代表（归 systems）──
    {"title": "Clean Code", "author": "Robert Martin", "year": 2008,
     "quadrant": "systems", "difficulty": "entry", "kind": "classic",
     "decay": {"paradigm": "pre-dl", "content_type": "systems"},
     "note": "编码规范经典。AI 代码一样要人读、要维护 —— 工程师的基本素养。",
     "isbn_hint": "9780132350884"},
    {"title": "The Pragmatic Programmer", "author": "David Thomas", "year": 2019,
     "quadrant": "systems", "difficulty": "entry", "kind": "classic",
     "decay": {"paradigm": "dl", "content_type": "systems"},
     "note": "程序员实用主义经典，20 周年版。讲习惯与判断，不讲具体技术，所以不过时。",
     "isbn_hint": "9780135957059"},
    {"title": "System Design Interview – An Insider's Guide", "author": "Alex Xu", "year": 2020,
     "quadrant": "systems", "difficulty": "intermediate", "kind": "timely",
     "decay": {"paradigm": "dl", "content_type": "systems"},
     "note": "系统设计的 80+ 模式：一致性哈希、消息队列、限流。ML 系统也跑在这上面。"},
    {"title": "Fluent Python", "author": "Luciano Ramalho", "year": 2022,
     "quadrant": "systems", "difficulty": "intermediate", "kind": "timely",
     "decay": {"paradigm": "transformer", "content_type": "hands-on", "pinned_apis": ["python-3"]},
     "note": "Python 高级特性深度解析。AI 全在 Python 上写，值得精通语言本身。",
     "isbn_hint": "9781492056355"},
    {"title": "Database System Concepts", "author": "Abraham Silberschatz", "year": 2019,
     "quadrant": "systems", "difficulty": "intermediate", "kind": "classic",
     "decay": {"paradigm": "pre-dl", "content_type": "systems"},
     "note": "数据库系统经典教材（换《数据库系统概论》）。关系模型、事务、查询优化。"},

    # ── 数据可视化（归 applied）──
    {"title": "Storytelling with Data", "author": "Cole Nussbaumer Knaflic", "year": 2015,
     "quadrant": "applied", "difficulty": "entry", "kind": "classic",
     "decay": {"paradigm": "pre-transformer", "content_type": "narrative"},
     "note": "数据可视化叙事方法论。分析做得再好，讲不清就没用。",
     "isbn_hint": "9781119002253"},
    {"title": "The Visual Display of Quantitative Information", "author": "Edward Tufte", "year": 2001,
     "quadrant": "applied", "difficulty": "intermediate", "kind": "classic",
     "decay": {"paradigm": "pre-dl", "content_type": "narrative"},
     "note": "可视化理论的圣经，「数据墨水比」的出处。至今是黄金标准。"},

    # ── Hold 候选（护城河，规则 B）──
    {"title": "Machine Learning: A Probabilistic Perspective", "author": "Kevin Murphy", "year": 2012,
     "quadrant": "foundations", "difficulty": "hardcore", "kind": "timely",
     "decay": {"paradigm": "pre-dl", "content_type": "theory",
               "superseded_by_title": "Probabilistic Machine Learning: An Introduction"},
     "note": "Murphy 2012 老版。已被作者自己的《Probabilistic Machine Learning》(2022) 重写取代 —— 别买旧的。",
     "isbn_hint": "9780262018029"},
]


def norm(t):
    # 归一化整条标题做严格比较 —— 子串匹配会误杀
    # （"deep learning" 命中 "neural networks and deep learning"）
    t = t.split(" (")[0].lower()
    return "".join(c for c in t if c.isalnum())


def main():
    data = json.loads(CUR.read_text())
    existing = {norm(b["title"]) for b in data["books"]}

    added, skipped = 0, 0
    for b in NEW:
        if norm(b["title"]) in existing:
            print(f"  跳过（已有）: {b['title']}")
            skipped += 1
            continue
        data["books"].append(b)
        added += 1

    CUR.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"\n新增 {added} 本，跳过 {skipped} 本，现共 {len(data['books'])} 本")

    from collections import Counter
    print("象限:", dict(Counter(b["quadrant"] for b in data["books"])))


if __name__ == "__main__":
    main()
