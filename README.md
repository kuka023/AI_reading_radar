# AI 读书雷达 · AI Reading Radar

面向 AI 从业者的个性化读书雷达。受 ThoughtWorks 技术雷达启发，把书目做成一片可探索的**星云**——选一个角色，拉近属于你的那片星系。

它做三件通用书单做不到的事：**针对具体的人**排推荐、**在后台持续淘汰过时的书**、用**天体可视化**把「该读什么」变成一张有观点的图。

---

## 三个空间

| 空间 | 是什么 |
|---|---|
| 🌌 **雷达** | **给你的** —— 选角色，看按「立场」排布的个性化推荐：现在就读 / 值得投入 / 知道即可。 |
| 📚 **图书馆** | **所有的** —— 全量策展书目 + Open Library 外部大库检索，把想读的加进你的雷达（个人图层）。 |
| 💬 **社区** | **大家的** —— 读过的人写下的书评。评价资格绑定阅读，没读过不能评。 |

---

## 核心设计

- **环 = 立场，不是难度。** 难度用星球大小表达，是属性不是环。
- **星球材质编码内容类型。** 气态巨行星 = 思想书（理论/叙事），岩石行星 = 工具书（工程/实操）——剪影就能区分。
- **防幻觉是死线。** 雷达上每本书的 ISBN 都经 Open Library 权威端点核实，查无即淘汰；模型只能从真实书目库检索，绝不生成书名。
- **衰变引擎（纯规则，零 LLM）。** 在后台淘汰「有新版取代 / 绑死废弃框架 / 技术路线被取代」的书，不让过时的书进推荐——判死靠硬事实，不靠出版年。
- **数据飞轮。** 用户的选角色、点书、加书、打分、书评都进事件流，作为将来校准推荐的燃料。

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
data/
  curation.json     人工策展清单（书名+作者+标注，不写 ISBN）
  books.json        由 resolve_isbn 生成，每个 ISBN 经 Open Library 核实
  roles.json        角色定义（前端入口）
src/
  server.py         FastAPI：雷达 / 图书馆 / 社区 / 账号 / 事件流
  db.py             SQLite 数据层（users/events/shelf/books/reviews）
  resolve_isbn.py   ISBN 校验闸门（防幻觉第一道）
  decay.py          衰变引擎（纯规则，判过时的书）
  placement.py      排环引擎（按角色的个性化，纯规则）
  merge_prd.py      书目增量合并工具
web/
  index.html        前端（星云可视化 + 三空间）
```

---

## 常用命令

```bash
.venv/bin/python src/resolve_isbn.py    # 重新校验 ISBN（改了 curation.json 后）
.venv/bin/python src/decay.py           # 看衰变引擎判了哪些书过时
.venv/bin/python src/placement.py researcher   # 看某角色的排环结果
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

---

## 路线图

- **L1 地基核心** ✅ — SQLite + 匿名账号 + 事件流 + 书架
- **L2 图书馆** ✅ — 全量浏览 + 外部大库检索 + 加书进个人图层
- **L3 社区** ✅ — 书评 + 有用投票（读过才能评）
- **L4 账号升级** ⏳ — OAuth 登录（社区实名信任的前提）
