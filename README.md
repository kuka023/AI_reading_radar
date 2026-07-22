# AI 读书雷达 · AI Reading Radar

面向 AI 从业者的个性化学习雷达。受 ThoughtWorks 技术雷达启发，把业务共建的资料库做成一片可探索的**星云**——选一个能力族，拉近属于你的那片星系。

它做三件通用书单做不到的事：**按业务能力族**排推荐、把**书 / 课程 / 文档 / 文章**四类资料放进同一张图、用**天体可视化**把「该学什么」变成一张有观点的图。

数据源为业务 AI-Native 能力模型的**共建资料库**（`AI-Native读书雷达·资料共建.xlsx`）：88 行 → 去重 64 项（书 25 / 在线课程 12 / 官方文档 20 / 文章 7）。

---

## 四个空间

| 空间 | 是什么 |
|---|---|
| 🌌 **雷达** | **给你的** —— 选能力族，看按「立场」排布的个性化推荐：现在就读 / 值得投入 / 知道即可。 |
| 📚 **图书馆** | **所有的** —— 全量共建资料 + Open Library 外部大库检索，把想读的加进你的雷达（个人图层）。 |
| 💬 **社区** | **大家的** —— 学过的人写下的推荐（1–5 星打分 + 理由）。评价资格绑定阅读，没读过不能评。 |
| ★ **我的** | **你自己的** —— 空白个人雷达 + 书架（未读 / 在读 / 已读）。把书从书架拖到雷达标你自己的立场，一键分享给同行（`?me=` 只读链接）。 |

---

## 核心设计

- **角色轴 = 业务 8 个能力族。** 全员通用 / 技术·应用 / 技术·数据 / 技术·平台 / 产品 / 测试 / 项目管理 / FDE，与业务能力模型对齐。
- **环 = 立场，不是难度。** 现在就读 / 值得投入 / 知道即可，由人工策展；难度用星球大小表达，是属性不是环。
- **四类资料 = 四种天体，一眼可辨。** 书籍 = 行星（气态思想书 / 岩石工具书）、在线课程 = 星环行星、官方文档 = 方片、文章 = 彗星。
- **角向 = 能力主题；暖光 = 业务强推（★★★★）。**
- **防幻觉 + 元数据核实。** 书籍 ISBN 经 Open Library 权威端点核实；业务清单收录但外部库暂无的新书（多为 MEAP）保留并标「元数据待补」，不臆造。
- **数据飞轮。** 用户的选族、点资料、加书、打分、评价都进事件流，作为将来校准推荐的燃料。

---

## 技术栈

- **前端**：原生 Canvas + JavaScript（无框架，程序化天体渲染）
- **后端**：FastAPI + SQLite（轻地基，读多写少够用；规模化再迁 Postgres）
- **书目数据源**：Open Library

---

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cd src && ../.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8000
# → 打开 http://127.0.0.1:8000
```

首次启动会自动建 SQLite 库并导入策展书目（`db.init_db`）。

---

## 项目结构

```
AI-Native读书雷达·资料共建.xlsx   业务共建的原始资料库（数据源头）
data/
  resources.json    由 ingest_xlsx + enrich_isbn 生成的规范数据源（64 项）
  roles.json        8 个业务能力族（前端入口）
src/
  server.py         FastAPI：雷达 / 图书馆 / 社区 / 账号 / 事件流
  radar.py          从 resources 组装星云与各能力族雷达（纯规则）
  db.py             SQLite 数据层（users/events/shelf/books/reviews）
  ingest_xlsx.py    xlsx → resources.json（分类 / 归族 / 去重 / 策展立场）
  enrich_isbn.py    给书籍补 ISBN + 作者（查无也保留，标元数据待补）
web/
  index.html        前端（星云可视化 + 三空间）
```

> 早期原型的 `resolve_isbn.py` / `decay.py` / `placement.py` / `curation.json` 仍保留在库中，
> 记录衰变引擎与排环引擎的方法，但当前服务路径已切换到 `radar.py` + `resources.json`。

---

## 常用命令

```bash
.venv/bin/python src/ingest_xlsx.py     # 从 xlsx 重新生成 resources.json
.venv/bin/python src/enrich_isbn.py     # 给书籍补 ISBN + 作者
.venv/bin/python src/radar.py applied   # 看某能力族的排环结果
```

---

## 设计文档

| 文档 | 内容 |
|---|---|
| `DESIGN.md` | 产品设计与核心决策 |
| `FLYWHEEL.md` | 数据飞轮规划 |
| `SPEC-catalog-v1.md` | 书目构建方案 |
| `SPEC-backend-v1.md` | 后端地基架构 |
| `SPEC-flywheel-v1.md` | 事件流与书架旅程 |
| `SPEC-evolution-v1.md` | **自进化路线：成长路径 / 飞轮阈值 / 个性化** |

---

## 路线图

**地基（L1–L3）**

- **L1 地基核心** ✅ — SQLite + 匿名账号 + 事件流 + 书架
- **L2 图书馆** ✅ — 全量浏览 + 外部大库检索 + 加书进个人图层
- **L3 社区** ✅ — 带分推荐 + 有用投票（读过才能评）
- **个人空间** ✅ — 空白个人雷达（拖书标立场）+ 书架 + 分享（`?me=` 只读）

**自进化（见 `SPEC-evolution-v1.md`）**

- **Phase 1 · 成长路径** ✅ — 社区主页按目标的学习序列（初期人工撰写，`data/paths.json`）
- **Phase 2 · 飞轮** 🧪 — 准入/降级评审台（阈值 v0，**模拟信号**，`src/flywheel.py`）；待专家评审责任人与真实流量
- **Phase 3 · 个性化** 🧪 — 结构化目标 → 策展库内重排规划路径（**模拟时长维度**，`data/goals.json`）
- **L4 账号升级** ⏳ — OAuth 登录（社区实名信任的前提）
