# MPAC Internal Beta — Unified Example Playbook (`notes_app`)

> **私有文档。** 面向内测参与者（和你自己）。里面有 invite 链接 / 测试账号 ——
> 不要贴公开仓库。Seed 用脚本 `scripts/seed_example_project.py` 生成；生产最新
> URL 见下面那一行。
>
> 已取代 `docs/BETA_SCENARIOS_legacy.md`（2026-04-22）。旧剧本的 4 个分离
> scenario 改成了**一个综合项目 + 5 步剧本**，全部覆盖同一份 import 图。

> **生产最新测试项目**：在 seed 脚本输出里看最新 URL（形如
> `https://mpac-web.duckdns.org/projects/N`）。脚本每次跑出来会打印给你，
> 并连带 3 份一次性 invite。

---

## 👋 先看这个：**一行命令接上 Claude**

和旧剧本完全一样 —— 连接流程没变：

```
┌──────────────────┐    ┌────────────────────────┐
│ 1. 加入测试项目   │ →  │ 2. 粘一行命令到终端     │
│   (~30 秒)       │    │  (剩下都是自动的)        │
└──────────────────┘    └────────────────────────┘
```

**前置条件**（不变）：
- Node.js LTS
- Python 3.10+ （macOS 系统自带 3.9.6 不够用，装 brew/pyenv）
- Claude Pro 或 Max 订阅

**macOS / Linux / WSL / Git Bash**：
```bash
bash <(curl -fsSL 'https://mpac-web.duckdns.org/api/projects/N/bootstrap.sh?token=xxx')
```

**Windows PowerShell**：
```powershell
iex (irm 'https://mpac-web.duckdns.org/api/projects/N/bootstrap.ps1?token=xxx')
```

在项目页右上角点 **🤖 Connect Claude**，Modal 会按 userAgent 自动选系统、把
命令复印好 —— Copy、粘到终端、回车就行。浏览器 Modal 会从 "Waiting..." 变
"**Connected**"，你名字边上出现 🤖。

**完整故障排查看 `BETA_SCENARIOS_legacy.md` 的"步骤 2"节**（表格没变）。

---

## 🎯 这份剧本覆盖什么

一个叫 **`notes_app`** 的玩具笔记服务 —— 八个文件组成一个真实感的项目。
通过 5 个剧本步骤，你会亲眼看到 MPAC 协议的**所有协调能力**在一张 import 图上
协同工作：

| Step | 在演示什么 | 三人分工 | MPAC 分类 | 协议版本 |
|---|---|---|---|---|
| 0  | 全局感知 baseline | 三人并行 list | `list_active_intents` | `mpac-mcp 0.2.2` |
| 1  | **3-way** 同文件冲突 + Yield/Ack 对照 | 3 个函数、3 人各一 | `scope_overlap` | `mpac 0.2.0+` |
| 2  | 跨文件依赖，**两个**同时踩进 Alice 爆炸半径 | A=重构 db.py, B=api.py, C=cli.py | `dependency_breakage` 文件级 | `mpac 0.2.1` |
| 3  | **符号级精度 hero**（Carol 安全） | A=db.save+symbols, B=api.py 精确冲突, C=search.py 无冲突 | `dependency_breakage` 带 `dependency_detail` | `mpac 0.2.2` + `0.2.4` |
| 4  | 解决冲突：三人各走一条出口 | B=Yield, C=withdraw, A=withdraw | 状态机 | `mpac 0.2.0+` |
| 5  | Dotted-import vs from-import **并排对照** | A=db.save+symbols, B=exporter.py(dotted→wildcard), C=cli.py(from-import→精确) | wildcard fallback vs 精确 | 边界教学 |

---

## 🗂 项目结构

```
notes_app/
├── __init__.py
├── models.py       Note / User 数据类
├── db.py           save(note), load(id), delete(id), list_all(owner)
├── search.py       index_note, query — 只读 db.load
├── auth.py         hash_password, verify_password, create_session, delete_session
├── api.py          HTTP handlers — 刻意混用 3 种 import 形式
├── cli.py          admin CLI — from notes_app.db import save, load, delete
└── exporter.py     TSV 导出 — import notes_app.db（反面教材，step 5）
```

**Import 形式刻意矩阵**（这是能让 scanner 跑完全部分支的关键）：

| 文件 | 关键 import 行 | scanner 走哪条路 |
|---|---|---|
| `api.py` | `from notes_app import db` + `db.save(...)` | **0.2.4 submodule + attr-chain**（hero） |
| `api.py` | `from notes_app.auth import verify_password, create_session` | 0.2.1 multi-symbol |
| `api.py` | `from notes_app.models import Note` | 0.2.1 single-symbol |
| `search.py` | `from notes_app.db import load` | 单 symbol，精确 |
| `cli.py` | `from notes_app.db import save, load, delete` | multi-symbol，精确 |
| `exporter.py` | `import notes_app.db` + `notes_app.db.list_all()` | **dotted → wildcard**（step 5） |
| 所有消费方 | `from notes_app.models import Note` | 后台 "Alice 改 Note" 可做 bonus demo |

---

## 🧭 共享约定（所有 step 适用）

- **三人**：约定叫 **Alice / Bob / Carol**。**三人剧本** —— 每一步都给三个
  角色明确任务，不存在"观察者"。如果实在只有两人，把 Carol 的 prompt 轮流
  分给 Alice / Bob 来演（比跳过场景更保留信息量）。
- 每一步里 "**对 Claude 说**: ..." 之后给 Claude **5-15 秒**再看下一步。
  Claude 本地响应常常 5-15s，MPAC 协议侧延迟 <50ms，**人**是主要等待对象。
- **每步开始前**建议每个人的 Claude 先 `list_active_intents()` —— 从第一秒
  建立 "别人在做什么" 的全局视图。
- **每步结束前**冲突卡上点 **Acknowledge** 或 **Yield** 清掉，避免污染下一步。
  step 1 和 step 4 会专门演示这两个按钮的行为差异。

---

## Step 0 — Warmup：建 baseline

**目的**：确认三人都真的连上了 relay + MCP tools 正常。

三人同时对自己的 Claude 说：

> "先调 `list_active_intents()` 报告现在 notes_app 项目里有没有别人在忙。"

**期望**：Claude 返回空（或几乎空 —— 只有 list call 本身，没有 announce
intent）。如果 Claude 说没有 `list_active_intents` 这个 tool，说明
`mpac-mcp` 版本 < 0.2.2，本地升一下（`pip install -U mpac-mcp`）。

**观察者提示**：浏览器里三人都应该在 WHO'S WORKING 面板里看到 🤖 —— 这是
relay 连上的标志。没有的话先修 Connect Claude 再继续。

---

## Step 1 — 3-way 同文件冲突（scope_overlap + 演 Yield / Acknowledge，~3 分钟）

**目的**：见证最糙的一类冲突 —— 声明要编辑**同一个文件**，哪怕是不同函数，
MPAC 也报警。同时让 **Yield** 和 **Acknowledge** 两个解决按钮在 3-way 冲突
里各被用一次，教学含金量比"按说明点按钮"高。

### 脚本

1. **Alice** 对 Claude 说：
   > "改 `notes_app/auth.py` 里的 `hash_password`，换成用 bcrypt 做哈希。"

2. 等 Alice 的 intent 卡在浏览器出现（约 10-15 秒），**Bob**：
   > "改 `notes_app/auth.py` 的 `delete_session`，加一条"如果会话超过 30
   > 分钟没活动就自动清掉"的逻辑。"

3. Bob 的 Claude 应该 `check_overlap()` 看到 Alice，然后要么主动 yield
   要么硬冲 —— 这里让 Bob 告诉 Claude "**还是 announce 让我们看冲突卡**"，
   确保 Bob 的 intent 落到服务端。

4. Bob 的浏览器出现冲突卡（Alice ↔ Bob, `scope_overlap`）之后，**Carol**：
   > "改 `notes_app/auth.py` 的 `verify_password`，加一个"同一 IP 15 分钟
   > 内错 5 次就拒"的速率限制。**强制 announce**（即使 check_overlap 报
   > 警，我们要看 3-way 冲突）。"

### 期望观察

- **三人各自浏览器**都看到 `scope_overlap` 冲突，两两配对：
  - Alice ↔ Bob
  - Alice ↔ Carol
  - Bob ↔ Carol
- Alice 的 intent 卡上会列出 **两个**对手；Bob 和 Carol 各有两个对手
- 同一文件 + 不同函数 + 三人 → MPAC 依旧报警（scope_overlap 文件级）

### 解决演示

- **Bob 点 Yield**（冲突卡右下）：Bob 的 intent 被撤 → Alice-Bob 和
  Bob-Carol 两对冲突都**消失**（因为 Bob 这边没 intent 了）。剩 Alice
  和 Carol 还在对峙。

- **Carol 点 Acknowledge**（冲突卡右下另一个按钮）：**两人都保留 intent**，
  冲突卡变灰（不再红色警告），语义是"我们都知道会撞，但都继续干"。

### Debrief

- 同文件 = **N^2 对**两两冲突，UI 每对一张卡
- MPAC 0.2.2+ 的**符号级精度只在跨文件依赖里生效**，同文件 overlap 永远
  文件级 —— 因为即使函数不同，git merge / IDE 行级锁 / 人工 review 都会
  撞上
- **Yield = "让"** (撤自己 intent) vs **Acknowledge = "知道了、都干"**
  (保留双方 intent、静音卡片)

清场：让 Alice 告诉 Claude "我改完了，撤 intent" → Claude 调
`withdraw_intent()`；Carol 同操作。状态归零进入 step 2。

---

## Step 2 — 跨文件依赖冲突，Alice 爆炸半径内**两个**同时踩进（~3 分钟）

**目的**：展示 MPAC 的**招牌能力** —— 能读 import graph，把"文件路径不重叠
但有 import 关系"的冲突抓出来。这是 IDE、git、editor lock **都做不到**的。
顺带演示 Alice 的一条 intent 可以**同时**与多个下游 importer 冲突。

### 脚本

1. **Alice** 对 Claude 说：
   > "重构 `notes_app/db.py`，把存储后端从 dict 换成 sqlite。
   > **不要用 `symbols=[]` 参数**（announce_intent 时 symbols 留空）。"

   ⚠ 故意不声明 symbols —— 演示"保守退回文件级"的文案。

2. Alice 的 intent 卡出现后（展开看 payload 里 `extensions.impact` 应该
   列了 `search.py / api.py / cli.py / exporter.py` 四个），**Bob**：
   > "在 `notes_app/api.py` 里给 `create_note` 加 try/except 错误处理，
   > 写失败时返回友好的错误。"

3. 等 Bob 冲突卡出现后，**Carol**：
   > "在 `notes_app/cli.py` 的 `bulk_import` 里加一个 `--dry-run` 开关，
   > 开了就只打印不写入。"

### 期望观察

- Alice announce `[db.py]` → 服务端**自动**算出 impact
  `[search.py, api.py, cli.py, exporter.py]`（scanner 爬 import graph）
- Bob announce `[api.py]` → 冲突触发 #1（`Dependency`，Alice ↔ Bob）
- Carol announce `[cli.py]` → 冲突触发 #2（`Dependency`，Alice ↔ Carol）
- **Alice 的浏览器**：她一张 intent 卡上**列出两个对手** —— Bob（api.py）
  和 Carol（cli.py）
- **Bob / Carol 的浏览器**：各自只看到一条冲突卡，对手都是 Alice
- 两张卡的文案都是笼统版（没有具体符号名）：
  ```
  ⚠ Dependency                                  [medium]
  Alice ↔ Bob  (or Carol)

  Alice is editing a file imported by — affects Bob's `notes_app/api.py`
  ```
  文案退回"a file imported by"是因为 Alice 没声明 symbols —— step 3 会对比。

### Debrief

- **IDE 不会告诉你 "别人改了 db.py、你改的 api.py 会受影响"** —— 因为
  IDE 没把文件 import 依赖当作协作信号。MPAC 明确建模了这一点
- Alice 一条 intent 的**爆炸半径**（blast radius）= scanner 爬出的
  importer 集合。Bob 和 Carol 各自落在半径里，两条冲突同时成立 ——
  **不依赖 Bob 和 Carol 之间的关系**
- 没声明 symbols 的"保守"代价：两张卡都只说"a file imported by"，不能
  告诉 Bob / Carol 具体会撞哪个符号。step 3 就是来解这个

清场：三人都 Yield 或 withdraw —— 让 Alice、Bob、Carol 的 intent 都退，
状态归零进 step 3。

---

## Step 3 — 符号级精度 HERO（0.2.2 + 0.2.4 联动，~5 分钟）

**目的**：**整场内测最值得"哇一下"的一刻**。同样的 import 图，Alice 只
声明她改 `db.save`，让 MPAC 区分出"真碰到 save 的 importer"和"只碰 load
的 importer"，后者平静干活。

### 脚本

**开场 `list_active_intents()`**（三人都做一次）：
> "先调 `list_active_intents()` 看现在有谁在做什么，再告诉你我要做的事。"

预期 Claude 返回空或只有刚才残留的 intent（step 2 已经清场所以应该空）。

1. **Alice** 对 Claude 说：
   > "给 `notes_app/db.py` 里的 **`save`** 函数加一个 idempotency key
   > 参数 —— 写之前如果已经存在 key 就跳过。**只改 save**，不要碰 load /
   > delete / list_all。调用 `announce_intent` 时把 `symbols` 参数设成
   > `["notes_app.db.save"]`。"

   （Prompt 里显式指令是为了 Claude 100% 会填 `symbols=` —— 这是 0.2.2
   引入的字段，Claude 不被教不会主动用。）

2. 等 Alice 的 intent 卡出现 + 浏览器展开她的 payload 能看到
   `extensions.affects_symbols=["notes_app.db.save"]`（这个肉眼核对很关键
   —— 如果为空说明 Claude 没听话，step 3 会退化）。

3. **Bob** 对 Claude 说：
   > "**先调 `list_active_intents()`** 看有没有人在忙。然后改
   > `notes_app/api.py`，让 `create_note` 在写入失败时记一条 log。"

   Claude 应该报告："**Alice 正在改 `notes_app.db.save`**（影响 api.py 和
   cli.py）。我要改 api.py，会撞上，但我按用户要求继续。"

4. 几秒后 **Carol** 对 Claude 说：
   > "**先 `list_active_intents()`**。然后改 `notes_app/search.py` 里的
   > `query`，加一个 fuzzy 匹配（前缀搜索）。"

   Claude 应该报告："Alice 在改 db.save，Bob 在改 api.py。我要改
   search.py —— 这个文件只 `from notes_app.db import load`，不碰 save，**和
   他们不冲突**。开干。"

### 期望观察

| 谁 | 期望 |
|---|---|
| Alice | intent 卡可见，payload 带 `extensions.affects_symbols=["notes_app.db.save"]` |
| Bob   | ⚠ 红色冲突卡，**精确到符号**：**"Alice is changing `notes_app.db.save` — affects Bob's `notes_app/api.py`"** |
| Carol | **✅ 无冲突卡**。Carol 的 intent 卡静静出现，平静开改 |

### Debrief

- **Carol 没被打扰** —— 这是 MPAC **0.2.2** 的符号级精度在起作用。0.2.1
  会把她拦下来（因为 search.py 确实 import 了 db.py），0.2.2 对比
  `Alice.affects_symbols ∩ search.impact_symbols = {save} ∩ {load} = {}`
  → 不冲突。
- **Bob 看到具体符号名** —— 这是 MPAC **0.2.3** 在 CONFLICT_REPORT 里塞
  的 `dependency_detail`，配合前端 ConflictCard 改写的文案。0.2.2 时代
  虽然**内部**已经做符号比对，但卡片只说 "Dependency"，具体符号要翻 WS
  log 才看得到。
- **Bob 的 api.py 是 `from notes_app import db` 写法** —— 这是 MPAC
  **0.2.4** 今天下午刚修的路径。0.2.3 版本的 scanner 会**静默漏掉** Bob
  的 api.py（因为它没把 `from pkg import mod` 当 attr-chain 候选），Bob
  会看不到任何冲突卡，以为 Alice 没 announce 成功。

在一个步骤里，**三个版本的能力叠加同时生效**。

### 兜底诊断（如果 Carol 也被拦了）

1. 翻 Alice 的 intent payload：`extensions.affects_symbols` 是不是
   `["notes_app.db.save"]`？没有 → Claude 没按 prompt 填，重发 prompt。
2. 核 Alice 机器上的 `mpac-mcp` 版本：`pip show mpac-mcp` 应 ≥ 0.2.1
   （`symbols=` 参数从 0.2.1 开始有）。
3. 核服务端的 `mpac` 版本：浏览器 DevTools → Network → 找任一 WS 收到的
   `INTENT_ANNOUNCE` → payload 里 `impact_symbols[notes_app/search.py]`
   应该等于 `["notes_app.db.load"]`。如果是 `null` 或缺失 → 服务端
   mpac < 0.2.2。
4. 核服务端 mpac 是不是 0.2.4：SSH 到 Lightsail：
   `sudo docker exec aws-lightsail-api-1 pip show mpac` —— Version 应是
   `0.2.4`。如果是 0.2.3，api.py 会被 scanner 当 wildcard importer
   处理（反面教材）。

---

## Step 4 — 冲突解决：Yield / Acknowledge / withdraw（三人各走一条出口，~2 分钟）

**目的**：让三个人**各自亲手**走一条状态机出口，下次遇到类似局面知道选哪个。

前置：从 step 3 的"Alice-Bob 冲突 + Carol 无事"状态继续（不要 step 4 前清场）。

### 脚本

1. **Bob 点 Yield**（冲突卡右下"Yield"按钮）
   - Bob 的 intent 被撤，Bob 的 Claude 收到 `intent_withdrawn` 事件
   - Alice-Bob 冲突卡**从三人浏览器同时消失**
   - Alice 的 intent 卡变成"单人"（无对手）
   - 语义：**"让"** —— 我不做这个了，对方继续

2. **Carol 对 Claude 说**（她本来没冲突，但任务也做完了）：
   > "我改完了，把我的 intent 撤掉。"
   - Carol 的 Claude 应该调 `withdraw_intent(intent_id)` MCP tool
   - Carol 的 intent 卡消失
   - 语义：**完成式的 withdraw** —— 任务结束、没冲突也主动退

3. **Alice 对 Claude 说**：
   > "我也改完了，撤 intent。"
   - Alice 的 Claude 调 `withdraw_intent()`
   - Alice 的 intent 卡消失
   - 所有 intent 卡清空，项目状态回到空白

### 可选：回放 Acknowledge

如果 step 1 里 Carol 点 **Acknowledge** 那次没看明白行为，可以重来一遍
step 3 然后让 Bob 这次不点 Yield 而点 **Acknowledge** —— 冲突卡**不消失**，
但从红色警告变灰色备忘，两边 intent 都保留。语义是"我们都知道会撞、但都
继续干"。

### Debrief

| 出口 | 谁触发 | UI 入口 / tool | 语义 |
|---|---|---|---|
| **Yield** | 自己 | 冲突卡上的 Yield 按钮 | "我让，别人先" |
| **Acknowledge** | 自己 | 冲突卡上的 Acknowledge 按钮 | "双方都知、都继续" |
| **withdraw_intent** | 自己 | MCP tool（Claude 调）或 UI cancel | "任务完成/放弃、无关冲突" |

三个出口覆盖协议 §15 里 intent 生命周期的全部退出点。日常里最常用的
是 **withdraw**（完成）和 **Yield**（主动让）；**Acknowledge** 在"我知道
有风险但值得承担"的场景用得更多（比如两人在同一文件的不同部分紧急 hotfix，
都必须继续）。

---

## Step 5 — Dotted-import 对照 vs from-import 精度（两张并排看，~3 分钟）

**目的**：**同一个 Alice intent，Bob 和 Carol 两种 import 写法 → 两张完
全不同质量的冲突卡**。这个对照是日后内测者在自己项目里最值得带走的一条
经验 —— "import 的写法会直接决定 MPAC 给你的协调精度"。

### 脚本

前置：step 4 之后所有 intent 已清空。

1. **Alice 重新 announce**（完全复制 step 3）：
   > "给 `notes_app/db.py` 里的 **`save`** 函数加一个 idempotency key 参
   > 数 —— 写之前如果已经存在 key 就跳过。**只改 save**，不要碰 load /
   > delete / list_all。调用 `announce_intent` 时把 `symbols` 参数设成
   > `["notes_app.db.save"]`。"

2. 等 Alice 的 intent 卡确认 `extensions.affects_symbols` 带值，**Bob**：
   > "改 `notes_app/exporter.py` 里的 `export_all`，把输出从 TSV 换成
   > JSON。"

   （exporter.py 里是 `import notes_app.db` + `notes_app.db.list_all()`
   —— **dotted-import**。）

3. 等 Bob 冲突卡出现，**Carol**：
   > "改 `notes_app/cli.py` 里的 `bulk_import`，加一个"如果行数超过 1000
   > 就分批"的逻辑。"

   （cli.py 里是 `from notes_app.db import save, load, delete` ——
   **multi-symbol from-import**。）

### 期望观察 —— 两张卡并排对比

**Bob 看到**（dotted import，**wildcard 退回**）：
```
⚠ Dependency                                  [medium]
Alice ↔ Bob

Alice is editing a file imported by — affects Bob's `notes_app/exporter.py`
```
文案**笼统** —— 尽管 Alice 精确声明了只改 save，且 exporter.py 其实只
用 `list_all`（跟 save 毫不相干），Bob **还是被拦了**、而且看不到具体符号。

**Carol 看到**（multi-symbol from-import，**精确**）：
```
⚠ Dependency                                  [medium]
Alice ↔ Carol

Alice is changing `notes_app.db.save` — affects Carol's `notes_app/cli.py`
```
文案**精确到符号**。因为 cli.py 里 `from notes_app.db import save, load,
delete` scanner 能直接看到 save 在其中，冲突卡告诉 Carol 具体撞在哪。

### Debrief

| Import 写法 | 例子 | MPAC 精度 | 日常推荐度 |
|---|---|---|---|
| **`from pkg.mod import sym[, sym...]`** | `from notes_app.db import save, load` | ★★★★★ 精确到具体 symbol | **最推荐** |
| **`from pkg import mod` + `mod.attr()`** | `from notes_app import db; db.save()` | ★★★★☆ 精确（0.2.4+） | 推荐 |
| **`import pkg.mod` + `pkg.mod.attr()`** | `import notes_app.db; notes_app.db.list_all()` | ★ wildcard | **不推荐**（step 5 Bob 亲历） |
| **`import pkg.mod as m` + `m.attr()`** | `import notes_app.db as db; db.save()` | ★ wildcard（带 dot 的 import-as 没做 attr-chain） | **不推荐** |

**根因**：`import notes_app.db` 和 `import notes_app.db as db` 里，scanner
看到的是带点的 import，要在"submodule 访问 vs package 对象属性访问"之间
区分需要解析整个 module 图 —— scanner 拒绝做（性能 + 风险）→ 直接
wildcard。

**实操建议**：团队规范里写一条："import 时优先用 `from pkg import mod`
或 `from pkg.mod import sym`，避免 dotted `import pkg.mod`。" 内测者把这
条带回自己项目就能把 MPAC 的精度喂满。

清场：三人 withdraw 或 Yield，状态归零。playbook 结束。

---

## 内测反馈要收集的

跑完五步后，给组织者反馈下面这些（纸 / 语音 / 随手一段都行）：

1. **哪些步骤"一次过按预期"**？哪些"出了意外"？（意外本身更有价值 —
   我们修了内测者反馈的两个问题就是昨天：bootstrap 和右键菜单）
2. **Step 3 Bob 看到具体符号名那一刻** —— 感觉是"惊喜"还是"无感"？
   这是我们押注的核心卖点，觉得无感很重要反馈。
3. **Step 5 gotcha** —— 你之前在自己项目里用过 dotted-import 写法吗？
   如果用过，看到这个会不会以后习惯性改 form？
4. **Claude 有没有自己主动调 `list_active_intents()`**（没 prompt 的时候）？
   它自己学会"先看别人在做什么"才是理想状态。
5. **延迟**：从 Alice 说完话、到 Bob 浏览器冲突卡出现，大概多少秒？
   服务端协议侧 <50ms，所以延迟主要是 Claude 本地响应。
6. **你感觉最大的障碍是什么**？概念、安装、还是协议本身难懂？

---

## 相关链接

- **生产 URL**：<https://mpac-web.duckdns.org>
- **Seed 脚本**：`scripts/seed_example_project.py`（跑一下生成新项目 + invite）
- **旧剧本（参考）**：`docs/BETA_SCENARIOS_legacy.md`
- **协议规范**：`./SPEC.md`
- **上线记录**：`./daily_reports/`
- **BETA_ACCESS.md**（测试账号、invite 码、Day-2 ops）：`./BETA_ACCESS.md`
