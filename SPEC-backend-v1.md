# 后端地基 · 规格

一个能同时承载**图书馆、社区、飞轮**的数据地基。这三者此前都卡在「没有后端」上——它们需要的是同一样东西：真账号 + 数据层。本文档定义这个地基。

---

## 1. 关键技术判断：SQLite 起步，不上重架构

PRD 的技术章节给的是 PostgreSQL + Redis + Celery + Elasticsearch + Kubernetes。**那是规模化之后的架构，现在上是过度工程。**

第一版地基用 **SQLite + FastAPI**：

| 维度 | SQLite 起步 | 现在就上 Postgres+Redis+Celery |
|---|---|---|
| 运维 | 零（单文件数据库） | 要部署/维护多个服务 |
| 落地速度 | 快，当天跑通 | 慢，地基还没验证就先背运维 |
| 迁移成本 | SQLite→Postgres 路径成熟，等有真实并发再迁 | —— |
| 适用规模 | 几千用户、读多写少，够 | 高并发才需要 |

**判断：在产品形态还没被用户验证前，用最轻的地基把数据流跑通。** 上重架构不会让产品更快成立，只会让验证更慢、返工更贵。等有真实的并发和数据量，再迁 Postgres（迁移是成熟工程）。

技术栈：SQLite（Python 内置 `sqlite3`，零依赖）+ FastAPI（已在用）。

---

## 2. 数据模型（五张核心表）

```
users              身份 —— 社区和飞轮的主键
  id            TEXT PK      匿名 uuid 起步；升级账号后绑 email/oauth
  handle        TEXT         昵称（社区显示名）
  auth_provider TEXT         anon | github | wechat
  created_at    INTEGER

events             飞轮燃料 —— append-only，只追加不改
  id       INTEGER PK
  actor    TEXT             users.id
  action   TEXT             role_select|open|jump|shelve|rate|search|add_book|review|vote…
  isbn     TEXT
  context  TEXT(json)       {role, goal, ring, …} 让信号可切片
  value    TEXT(json)       因 action 而异
  ts       INTEGER

shelf              个人书架 —— events 的派生视图，另存便于快查
  actor    TEXT
  isbn     TEXT
  state    TEXT             want | reading | read
  finished TEXT             yes | partial | dropped
  useful   TEXT             high | some | none
  curated  INTEGER          1 策展书 / 0 外部书（图书馆加的）
  meta     TEXT(json)       外部书的 title/author/quadrant
  ts       INTEGER
  PK(actor, isbn)

books              图书馆书目 —— 策展 89 本导入；外部书按需存
  isbn     TEXT PK
  title, authors(json), published, quadrant, difficulty, kind,
  content_type, paradigm, note, decay(json)
  curated  INTEGER          1 策展（有观点） / 0 外部（中性）

reviews            社区书评
  id     INTEGER PK
  actor  TEXT
  isbn   TEXT
  text   TEXT
  ts     INTEGER

votes              书评有用投票（防刷：一人一评一票）
  actor TEXT, review_id INTEGER, useful INTEGER
  PK(actor, review_id)
```

`events` 是飞轮的原始账本；`shelf`/`reviews` 是它的派生业务视图。派生态出错能从 events 重建。

---

## 3. API 面

```
账号
  POST /api/user/anon            创建/取回匿名账号 → {id}
  （OAuth 微信/GitHub 升级：后续）

飞轮
  POST /api/events               打点，前端所有交互都发这里

书架
  GET  /api/shelf?actor=         我的书架
  PUT  /api/shelf                更新一本书的状态/打分（同时落 events）

图书馆
  GET  /api/search?q=            策展命中 + 外部（Open Library）
  POST /api/library/add          加外部书进图书馆（books 表 curated=0）

社区
  GET  /api/reviews?isbn=        某书的书评（含有用票数）
  POST /api/reviews              发书评（防刷：需先标「读过」）
  POST /api/reviews/{id}/vote    有用投票
```

---

## 4. 从 localStorage 迁移

现有前端的书架数据在浏览器 localStorage。地基就绪后：

1. 前端首次加载生成/读取 `anon uuid`，调 `POST /api/user/anon` 登记。
2. 已有的 localStorage 书架，一次性 `PUT /api/shelf` 同步到后端。
3. 之后书架操作**双写**（localStorage 即时反馈 + 后端持久化 + 打 events）。

用户无感——零注册体验不变，数据从「只在你电脑」变成「后端也有一份」，飞轮开始有燃料。

---

## 5. 分层落地顺序

**不一次建完整个平台。** 先建核心、验证数据流通，再叠功能层：

| 层 | 内容 | 状态 |
|---|---|---|
| **L1 地基核心** | DB schema + 导入策展书 + 匿名账号 + 事件流 + 书架 API | 本轮 |
| **L2 图书馆** | 搜索（策展+外部）+ 加外部书进个人图层 | 下一轮 |
| **L3 社区** | 书评 + 有用投票（需先标「读过」防刷） | L2 后 |
| **L4 账号升级** | OAuth 登录（社区实名信任的前提） | 按需 |

**L1 的验收标准**：前端标记一本书 → 后端 events + shelf 存下 → 换个请求能查出来。数据真正流通，飞轮才算接通。

---

## 6. 风险

- **SQLite 写并发**：单写者锁。读多写少的场景够用；若社区写入密集，是迁 Postgres 的信号，不是现在的问题。
- **匿名账号的可信度**：L3 社区要实名信任，匿名 uuid 撑不住书评的公信力——所以 L4 的 OAuth 是社区真正开放前的前提，不能跳。
- **外部书污染书目**：图书馆加的外部书 `curated=0`，必须和策展书在数据和展示上都分明，别让它稀释雷达的观点（已在个人图层方案里定死）。
