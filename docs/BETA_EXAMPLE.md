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

| Step | 在演示什么 | MPAC 分类 | 协议版本 |
|---|---|---|---|
| 0  | 全局感知 baseline | `list_active_intents` | `mpac-mcp 0.2.2` |
| 1  | 同文件冲突 | `scope_overlap` | `mpac 0.2.0+` |
| 2  | 跨文件依赖（文件级） | `dependency_breakage` | `mpac 0.2.1` |
| 3  | **符号级精度 hero** | `dependency_breakage` 带 `dependency_detail` | `mpac 0.2.2` + `0.2.4` |
| 4  | 解决冲突：Yield / Acknowledge / withdraw | 状态机 | `mpac 0.2.0+` |
| 5  | Dotted-import 陷阱 | wildcard fallback | 边界教学 |

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

- **三人**：约定叫 **Alice / Bob / Carol**。两人也能跑，场景说明会标注。
- 每一步里 "**对 Claude 说**: ..." 之后给 Claude **5-15 秒**再看下一步。
  Claude 本地响应常常 5-15s，MPAC 协议侧延迟 <50ms，**人**是主要等待对象。
- **每步开始前**建议每个人的 Claude 先 `list_active_intents()` —— 从第一秒
  建立 "别人在做什么" 的全局视图。
- **每步结束前**冲突卡上点 **Acknowledge** 或 **Yield** 清掉，避免污染下一步。
  step 4 会专门演示这个。

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

## Step 1 — 同文件冲突（scope_overlap，~2 分钟）

**目的**：见证最糙的一类冲突 —— 两人声明要编辑**同一个文件**，哪怕是不同
函数，MPAC 也报警。这是 0.2.0 就有的能力、git 和 IDE 也做得到；先建立
baseline 再往上推。

### 脚本

1. **Alice** 对 Claude 说：
   > "改 `notes_app/auth.py` 里的 `hash_password`，换成用 bcrypt 做哈希。"

2. 等 10-15 秒看浏览器里 Alice 名字边上出现 intent 卡，然后 **Bob**：
   > "改 `notes_app/auth.py` 的 `delete_session`，加一条"如果会话超过 30
   > 分钟没活动就自动清掉"的逻辑。"

### 期望观察

- Alice 的 Claude `check_overlap()` → 空 → `announce_intent([auth.py])`
- Bob 的 Claude `check_overlap()` → **看到 Alice** → Bob 的 Claude 有
  两种反应都可以：
  - (a) 主动 Yield："Alice 在改这个文件，我等她先" —— 不 announce
  - (b) 硬冲：announce 了自己的 auth.py → 触发冲突卡
- 如果 (b)：三人浏览器都看到红色冲突卡，标签 `scope_overlap`

### Debrief

**关键点**：两人改的是**不同函数**（`hash_password` vs `delete_session`），
但 MPAC 还是报警。这是**故意保守** —— 即使函数不同，同一个源文件被两个人
同时改会导致 git merge 冲突、IDE 行级锁失效等一堆现实问题。MPAC 0.2.2+
的**符号级精度只在"跨文件依赖"里生效**，同文件 overlap 永远文件级。

清场：让 Bob 点 **Yield** 撤掉自己的 intent，冲突卡消失，auth.py 只剩
Alice 在改。然后让 Alice 也点 **Yield**（或让 Claude `withdraw_intent()`），
状态归零进入 step 2。

---

## Step 2 — 跨文件依赖冲突（dependency_breakage 文件级，~3 分钟）

**目的**：展示 MPAC 的**招牌能力** —— 能读 import graph，把"文件路径不重叠
但有 import 关系"的冲突抓出来。这是 IDE、git、editor lock **都做不到**的。

### 脚本

1. **Alice** 对 Claude 说：
   > "重构 `notes_app/db.py`，把存储后端从 dict 换成 sqlite。
   > **不要用 `symbols=[]` 参数**（announce_intent 时 symbols 留空）。"

   ⚠ 故意不声明 symbols —— 演示"保守退回文件级"的文案。

2. 等 Alice 的 intent 卡在浏览器出现，**Bob**：
   > "在 `notes_app/api.py` 里给 `create_note` 加 try/except 错误处理，
   > 写失败时返回友好的错误。"

### 期望观察

- Alice announce `[db.py]` → 服务端**自动**算出 impact
  `[search.py, api.py, cli.py, exporter.py]`（scanner 爬 import graph）
- Bob announce `[api.py]` → **冲突触发**！
- Bob 的浏览器看到 `⚠ Dependency` 冲突卡（不再是 `scope_overlap`）：
  ```
  ⚠ Dependency                                  [medium]
  Alice ↔ Bob

  Alice is editing a file imported by — affects Bob's `notes_app/api.py`
  ```
  文案退回"a file imported by"是因为 Alice 没声明 symbols —— 服务端不知
  道具体哪个符号在动，保守告诉 Bob "有东西 Alice 在改、你这边是 importer"。

### Debrief

**关键点**：IDE 不会告诉你 "别人改了 db.py、你改的 api.py 会受影响" ——
因为 IDE 没把文件 import 依赖当作协作信号。MPAC 明确建模了这一点。

清场：都点 **Acknowledge**（这次两人都保留 intent，仅表示"我知道了"），
或者让 Bob / Alice 点 Yield 撤一个也行。为了 step 3 的洁净状态，建议**都
Yield**。

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

## Step 4 — 冲突解决：Yield / Acknowledge / withdraw（~2 分钟）

**目的**：让内测者**亲手**用一次状态机的三个出口，知道什么时候用哪个。

### 脚本

从 step 3 的冲突状态继续：

1. **Bob 点 Yield**（冲突卡右下）：Bob 的 intent 被撤掉，Bob 的 Claude
   收到 `intent_withdrawn` 事件。Bob 和 Carol 的浏览器看到冲突卡**消失**，
   Alice 的 intent 卡变成"单人"。

2. **Alice** 对 Claude 说：
   > "我改完了，把我的 intent 撤掉。"

   Claude 应该调 `withdraw_intent(intent_id)` MCP tool。Alice 的 intent
   卡从浏览器消失。

3. *(二选一)* 如果想试试 **Acknowledge**：step 3 之前重来一次，Bob 这次
   不 Yield 而是点 **Acknowledge**。Acknowledge 的语义是："我知道撞了，
   但我们都继续干活"——双方 intent 都留着，冲突卡变灰（不再是红色警告）。

### Debrief

| 动作 | 语义 | 何时用 |
|---|---|---|
| **Yield** | 撤掉自己的 intent | "算了我晚点做，让对方先" |
| **Acknowledge** | 保留双方 intent、静音冲突 | "我们讨论过了，都知道风险，继续" |
| **withdraw_intent** (MCP tool) | 完成/放弃 | Claude 或 agent 自己收尾 |

这三个出口共同覆盖了协议 §15 里 intent 生命周期的全部退出点。

---

## Step 5 —（可选）Dotted-import gotcha（反面教材，~2 分钟）

**目的**：亲眼看到"**一行写法差别**导致 MPAC 精度完全失效"的例子。这是
日后内测者在自己真实项目里最可能踩的一个坑。

### 脚本

Alice 重新 announce 和 step 3 一样的事（`db.save` + symbols）。

**Dave**（或 Bob 二次上场）对 Claude 说：

> "改 `notes_app/exporter.py` 的 `export_all`，把输出从 TSV 改成 JSON。"

exporter.py 里写的是 `import notes_app.db` + `notes_app.db.list_all(...)`
—— dotted-import。

### 期望观察

Dave 看到的冲突卡：

```
⚠ Dependency                                  [medium]
Alice ↔ Dave

Alice is editing a file imported by — affects Dave's `notes_app/exporter.py`
```

**注意**：尽管 Alice 精确声明了只改 `save`，且 exporter.py 其实**只调用
`list_all`**（和 save 毫无关系），Dave **还是被拦了**。而且文案也退回到
了"a file imported by"这种笼统说法，**不像 step 3 Bob 那样看到具体符号**。

### Debrief

**根因**：`import notes_app.db` 这种 dotted 写法里，scanner 看到的是
`notes_app` 被 bind 成了一个名字，然后 `.db.list_all` 是连着三层的属性
访问。区分 "`notes_app.db` 是 submodule 还是 `notes_app` 这个 package 对
象的属性" 需要解析整个 module 图 —— scanner 拒绝做这件事（性能 + 风险）
→ 直接 wildcard。

**推荐做法**（三种都比 dotted 好）：
- `from notes_app import db` + `db.list_all()` ← 0.2.4 支持，精确到符号
- `from notes_app.db import list_all` + `list_all()` ← 0.2.1 就支持，最
  精确
- `import notes_app.db as db` + `db.list_all()` ← 目前仍是 wildcard（带
  dot 的 import-as 没做 attr-chain）**别用这条**

**在 Modal / 团队规范里可以写一条**："import 时优先用 `from pkg import
mod` 形式，避免 dotted import"—— 这样 MPAC 能给你最好的精度。

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
