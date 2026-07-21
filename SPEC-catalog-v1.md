# 第一版书目构建方案

基于用户 PRD（`AI从业者读书雷达应用 PRD.docx`）与五项方向裁决。本文档是第一版书目重建的执行依据。上位规划见 [DESIGN.md](DESIGN.md) / [FLYWHEEL.md](FLYWHEEL.md)。

---

## 1. 方向裁决记录

读 PRD 后校准，用户已裁决：

| # | 决策 | 结论 | 含义 |
|---|---|---|---|
| 1 | 定位 | 有观点的**垂直雷达** | 守 Hold 环 / 衰变引擎 / 完读矩阵 / 防幻觉书目这套护城河；借 PRD 的骨架与 UGC 细节增强 |
| 2 | 环语义 | **环=立场** | 现在读 / 值得投入 / 知道即可 / 别读；难度用星球大小，不占环。**不采纳** PRD 的「入门/进阶/高级」难度环 |
| 3 | 飞轮信号 | 完读矩阵为主，评分为辅 | 采纳 PRD 的「已读才能反馈」防刷；主信号仍是「你读完了吗 + 对你有用吗」 |
| 4 | 第一版书目 | 以 **PRD 书单**为基底 | PRD 的 80 本作骨料，但必须过我们的两道闸门 |
| 5 | 中文书 | **换英文等价书** | 保持一个干净、可查证的英文书目库 |

---

## 2. PRD 书单必须过的两道闸门

PRD 的 80 本是「全推荐、无 Hold、含中文、含通识」的原始清单。落地前逐本过闸门：

**闸门一 · 防幻觉（ISBN 校验）**
每本经 Open Library 权威端点回验，查无即淘汰或替换。**实测 PRD 中文书 0/5 可解**——中文书没有可靠元数据源（豆瓣 API 已关闭），必须换英文等价。

**闸门二 · 衰变标注**
PRD 书单无 `decay` 字段，无法判 Hold。逐本补标 `paradigm` / `content_type` / `pinned_apis` / `superseded_by`，才能跑衰变引擎。

---

## 3. 四条构建规则

### 规则 A · 中文书换英文等价

关键发现：**PRD 的中文书多数本身是英文书的中译本，换回原版即可**，不是另找替代。

| PRD 中文书 | 英文原版 / 等价 | 状态 |
|---|---|---|
| 《数据工程导论》Reis & Housley | *Fundamentals of Data Engineering* | **库中已有** |
| 《机器学习系统：设计与实现》 | Chip Huyen *Designing ML Systems* | **库中已有** |
| 《数据科学实战》拉贾拉曼 | *Mining of Massive Datasets* (Rajaraman & Ullman) | 换原版 |
| 《R语言实战》Kabacoff | *R in Action* | 换原版 |
| 《概率论与数理统计》陈希孺 | Casella & Berger *Statistical Inference* | 换等价（PRD DS 书单已列） |
| 《统计学习方法》李航 | ISLR / ESL / PRML | 已被库中英文经典覆盖 |
| 《数据库系统概论》王珊 | Silberschatz *Database System Concepts* | 换等价 |
| 《高可用架构》阿里 | *Site Reliability Engineering* | 库中已有覆盖 |
| 《AI产品经理》《AI战略》《数字跃迁》等纯中文商业书 | 用 Agrawal *Prediction Machines* / *Power and Prediction* 等英文 AI 商业书覆盖 | 概念覆盖，不逐本换 |

原则：先找英文原版；无原版则用同主题英文经典覆盖；两者皆无则该主题暂缺，不硬凑。

### 规则 B · 主动补 Hold 候选（护城河燃料）

PRD 的 80 本全是推荐，无一本 Hold。护城河要落地，**每个角色象限补 2–3 本「别读」**，来源限三类硬信号：

- **有新版取代**：如 HOML 2nd（被 3rd 取代）
- **绑死废弃框架**：如 NLTK 时代的 NLP 书、TF 1.x 实战书
- **技术路线被取代**：如 GAN 实战书（diffusion 取代）

其中数本我们现有库里已具备，可直接并入。

### 规则 C · 通识/软工书归入跨角色象限

PRD 混入的非 AI 书（Clean Code、Lean Startup、Zero to One、Building Microservices 等）技术上能过闸门。归入 PRD 2.6 已有的「跨角色通识」分类，不混进各角色的 AI 专业象限，避免稀释焦点。

### 规则 D · 角色体系对齐（待确认）

PRD 是 4 角色（AIPM / Researcher / Engineer / Data Scientist），我们现有 5 角色（含 applied-llm-dev、data-engineer，无 data-scientist）。

- 第一版书目按 **PRD 的 4 角色**组织（书单本就这么分类）。
- 但 PRD 缺 **applied-llm-dev（LLM 应用开发者）**——当下最热的角色。建议第一版并入 Engineer，作为后续独立第 5 角色的候选。
- 此项不阻塞书目录入，可后定。

---

## 4. 执行步骤

1. 把 PRD 80 本按角色结构化进 `curation.json` 格式（书名+作者+象限+难度+kind+decay 标注）。
2. 中文书按规则 A 替换为英文原版/等价。
3. 按规则 B 补 Hold 候选。
4. 跑 `resolve_isbn.py`：ISBN 逐条回验，出报告（过闸门数 / 淘汰数 / 替换数）。
5. 跑 `decay.py`：确认 Hold 环非空、零误杀。
6. 更新 `roles.json` 与前端角色，跑通全链路。

**先做 1–4，产出一份真实的「PRD 书单过管线报告」**，用数据确认最终书目形态，再进 5–6。

---

## 5. 风险

- **通识书占比**：PRD 通识/软工书较多，全部保留会让「AI 读书雷达」名不副实。跨角色象限要控制体量。
- **AIPM 角色的 AI 专业书偏薄**：PRD 该角色多为产品/商业通识，真正的 AI 产品书稀缺。补 Hold 和 AI 专业书时需额外策展。
- **中文替换的等价判断**：中译本换原版无损；同主题覆盖则有信息损失，需逐本记录替换理由备查。
