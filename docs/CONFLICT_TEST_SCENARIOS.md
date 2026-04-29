# 必触发冲突测试用例（2 人 + 3 人）

> **私有文档。** 面向"我想当场触发 conflict 看 UI / 协议反应"的最小测试集 ——
> 每个用例都按 `mpac 0.2.4` + `mpac-mcp 0.2.8` 的算法**精心设计**，
> 不靠运气、不靠时序。
>
> 文档包含**两类**测试:
>
> * **Test 2.x / 3.x / N1** — announce 后停下不动,目的是把冲突时间窗拉长以便观察 UI/协议
> * **用例 3–6** — 让 Claude 真改文件(announce → read → write → withdraw),覆盖
>   真实工作流;包含 happy path / 主动让路 / 招牌冲突 / 反面教材 4 个场景
>
> 区别于 [`BETA_EXAMPLE.md`](BETA_EXAMPLE.md)（5 步教学剧本，含负向 case）和
> [`TWO_USER_TESTS.md`](TWO_USER_TESTS.md)（UI / 协议大杂烩 smoke）。

---

## 准备工作

- 任意一个 seed 过 `notes_app` 的项目（用 `scripts/seed_example_project.py` 跑出来，
  或者直接在项目页点 **Reset to seed** 按钮）
- 每个参与者都连上 Claude（看到 header `🟢 Claude connected`）；**或者**用
  `scripts/demo_driver.py` 直接发 envelope（不依赖 Claude，更快）
- **每个 case 之前都先 Reset to seed** —— 文件内容 + import 图必须干净，这是
  "必触发"的前提

---

## 📋 直接粘贴到 chat board 的对话（2 人测试速查）

> **谁用**：每个测试者各开一个浏览器，登录后打开**同一个项目页**，在右下角的
> **AI Assistant 聊天框**里粘贴下面对应的提示词即可。两个人的 Claude 会在
> 后台分别 announce intent，CONFLICTS 面板自动弹冲突卡。
>
> **为什么这么写**：Claude 默认行为是 announce → 改文件 → withdraw_intent，
> 改完就立刻释放 intent，常常两边对不上时机。下面的 prompt 都让 Claude
> **announce 之后停下来**，不动文件、不调 withdraw —— 这样两侧的 intent
> 重叠期能拉得任意长，conflict 必触发。
>
> **测之前**：任一方在浏览器点 **Reset to seed**。

### 用例 1 — 同文件 overlap（最简单）

**用户 A 粘到 chat：**

```
请在 notes_app/db.py 上 announce 一个 intent，objective 写"重构 save() 支持批量写入"。announce 成功之后停下来，回复我"已 announce，等待指令"，然后什么都不要做。

绝对不要：读文件、改文件、调用 withdraw_intent、再调用任何 MCP 工具。我会在测试结束后明确告诉你 withdraw。
```

**用户 B 粘到 chat**（等 A 的 Claude 回复"已 announce"之后再发）：

```
请在 notes_app/db.py 上 announce 一个 intent，objective 写"新增 load_recent() helper"。announce 成功之后停下来，回复我"已 announce，等待指令"，然后什么都不要做。

绝对不要：读文件、改文件、调用 withdraw_intent、再调用任何 MCP 工具。
```

**期望看到**：

- 两人的 CONFLICTS 面板都跳出一张 `Scope overlap` 卡（medium severity）
- WHO'S WORKING 面板显示 A 和 B 都在编辑 `notes_app/db.py`
- 卡片文案：`Same file — one side should Yield`

**收尾**（测完两人各自发）：

```
现在 withdraw 你的 intent。
```

---

### 用例 2 — 跨文件依赖冲突（招牌 demo，能看到具体符号名）

**用户 A 粘到 chat：**

```
请在 notes_app/db.py 上 announce 一个 intent，objective 写"把 save() 的返回类型改成 int"。announce 时把 symbols 参数设成 ["notes_app.db.save"]。announce 成功之后停下来，回复我"已 announce，等待指令"。

绝对不要：读文件、改文件、调用 withdraw_intent、再调用任何 MCP 工具。
```

**用户 B 粘到 chat**（等 A 回复"已 announce"之后再发）：

```
请在 notes_app/api.py 上 announce 一个 intent，objective 写"给 API 新增 CORS 头"。announce 成功之后停下来，回复我"已 announce，等待指令"。

绝对不要：读文件、改文件、调用 withdraw_intent、再调用任何 MCP 工具。
```

**期望看到**：

- CONFLICTS 面板跳一张 `Dependency breakage` 卡
- **关键**：卡片文案带具体符号名 —— 类似
  *"Alice is changing `notes_app.db.save` — affects Bob's `notes_app/api.py`"*
  （这是产品对外讲故事的招牌帧）
- WHO'S WORKING 面板：A 在 `db.py`、B 在 `api.py`（**不同**文件，说明跨文件分析生效）

**收尾**：跟用例 1 一样，两边各发 `现在 withdraw 你的 intent。`

---

### 如果 Claude 不听话

Claude 偶尔会"善意地"提前 withdraw（它认为 announce 之后就该礼貌地释放）。
如果在 chat 看到它说"已 withdraw"，重发一次提示词 + 加狠语气：

```
你刚才 withdraw 早了。请重新 announce 同一个 intent，这次 announce 完就停在原地，绝对不调用 withdraw_intent。我没让你 release。
```

或者把上面任一用例的提示词最后一行改成：
**"announced 之后 idle 到我说停为止，期间什么 MCP 工具都不要再调用。"**

---

## 🛠️ 让 Claude 真改文件的对话(用例 3–6)

> 上面用例 1/2 是 announce 后停住不动，方便观察冲突 UI。下面 4 个让 Claude 走完整流程
> (announce → read → write → withdraw)，跟真实用户行为一致 —— prompt 是**自然语言**，
> 不告诉 Claude 调哪个 MCP 工具,让 system prompt + Claude 自己判断怎么走。
>
> **每个用例之前都先点 Reset to seed**(这组会真改文件,清干净避免污染下一轮)。

### 用例 3 — 不同文件并行(无冲突 happy path)

**A 粘到 chat:**

```
在 notes_app/db.py 末尾加一个 count_notes() 函数，返回 _STORE 里的笔记数量。
```

**B 粘到 chat(跟 A 同时发,不用等):**

```
在 notes_app/auth.py 末尾加一个 list_active_sessions() 函数，返回 _SESSIONS 里所有 session_id。
```

**期望看到**:
- WHO'S WORKING 短暂出现 A 在 db.py / B 在 auth.py
- **CONFLICTS 面板始终空** —— 不同文件 + 无 import 依赖
- 浏览器编辑器打开 `db.py` 末尾有 `count_notes()`,`auth.py` 末尾有 `list_active_sessions()`

---

### 用例 4 — 同文件,B 主动让路(passive coordination)

**A 粘到 chat:**

```
在 notes_app/db.py 里加一个 update_note(note_id, **fields) 函数，找到对应的笔记，更新它的字段；找不到返回 False。
```

**B 粘到 chat(等几秒,趁 A 的 Claude 还在工作时):**

```
我想在 notes_app/db.py 里加一个 delete_all_notes() 清空 _STORE。但你先 check_overlap 看一下 —— 如果别人在改这个文件，直接放弃，回我"有人在改 db.py，等他完成我再来"，什么都不要做。只有 check 干净才往下走。
```

**期望看到**:
- A 走完整流程,db.py 末尾出现 `update_note()`
- B 的 Claude 调 check_overlap → 看到 A 的 intent → **不 announce**,回复让路
- **CONFLICTS 面板从头到尾空**(B 没 announce,server 端没创建 conflict)
- db.py **没有** delete_all_notes

---

### 用例 5 — 跨文件依赖冲突(招牌帧,符号级)

**A 粘到 chat:**

```
把 notes_app/db.py 里的 save() 改成 save(note, *, dry_run=False) -> int —— 加一个 dry_run 关键字参数(默认 False)，返回保存的笔记数量。announce 时把 symbols 设成 ["notes_app.db.save"]。
```

**B 粘到 chat(同时):**

```
在 notes_app/api.py 里加一个 save_with_log(note) 函数，内部调用 db.save() 然后 print 一句日志。
```

**期望看到**:
- 双方都 announce 成功(A 在 db.py,B 在 api.py)
- ⚡ 跳一张 `Dependency breakage` 卡,**文案里包含具体符号名 `notes_app.db.save`**
  例如:*"Alice is changing `notes_app.db.save` — affects Bob's `notes_app/api.py`"*
- 双方继续完成 → db.py 的 save() 有新签名,api.py 多了 save_with_log()

**这是产品的招牌帧** —— 屏幕上**真的能看到具体符号名**,不是笼统的"冲突"。

> 时机注意:如果 A 完成太快(withdraw 早于 B announce),B 那边就不会看到冲突。
> 用例失败时重测,让两边 prompt 间隔尽量小。

---

### 用例 6 — 双方都不让路(反面教材,验证 last-writer-wins)

**A 粘到 chat:**

```
在 notes_app/db.py 末尾加一个 archive_note(note_id) 函数 —— 把指定笔记从 _STORE 移到一个新的 _ARCHIVE 字典(如果还不存在就创建它)。如果遇到冲突，告诉我冲突内容但继续完成，不要让路。
```

**B 粘到 chat(同时):**

```
在 notes_app/db.py 末尾加一个 unarchive_note(note_id) 函数 —— 把笔记从 _ARCHIVE 移回 _STORE。如果遇到冲突，告诉我冲突内容但继续完成，不要让路。
```

**期望看到**:
- 双方都 announce on db.py → ⚡ `Scope overlap` 卡跳出
- 双方都在 chat 回复说"看到冲突了,但按指令继续"
- 双方都 write 完文件
- **db.py 最后只有其中一个函数** —— 第二个 write 覆盖了第一个(last-writer-wins)

**这个用例是反面教材**:演示 MPAC 的协议是**软约束**(警告但不阻止)。实际产品里
**应该 respect Yield 按钮**,这个用例展示忽略冲突的代价(数据丢失)。

---

## `notes_app` import 图速查

```
notes_app/
├── models.py    Note, User                          ← 被 db / search / api / cli import
├── db.py        save / load / delete / list_all     ← 被 search / api / cli / exporter import
├── search.py    from notes_app.db import load                      （单符号 from-import）
├── auth.py      hash_password / verify_password / create_session   （自包含，没人 import）
├── api.py       from notes_app import db; db.save()                （0.2.4 attr-chain）
│                from notes_app.auth import verify_password, create_session
│                from notes_app.models import Note
├── cli.py       from notes_app.db import save, load, delete         （多符号 from-import）
└── exporter.py  import notes_app.db; notes_app.db.list_all()        （dotted → wildcard）
```

**反向依赖表**（"我改这个文件的话，谁会被波及"）：

| 被改的文件 | 反向 importers | 备注 |
|---|---|---|
| `models.py` | db, search, api, cli | `Note` / `User` 数据类 |
| `db.py`     | search（只 import `load`）, api（`save` 走 attr-chain）, cli（save+load+delete）, exporter（wildcard） | hub 模块 |
| `auth.py`   | api（`verify_password`, `create_session`） | |
| 其余        | — | search / api / cli / exporter 都没人 import |

---

## 算法回顾（为什么"一定触发"）

冲突判定（在 [`mpac_protocol/core/scope.py`](../mpac-package/src/mpac_protocol/core/scope.py)）：

1. **`scope_overlap(A, B)`**：`A.resources ∩ B.resources` ≠ ∅ → fire `scope_overlap`
2. 第 1 条不命中时，再算 **`scope_dependency_conflict(A, B)`**：
   - 文件级：`(A.impact ∩ B.resources) ∪ (B.impact ∩ A.resources)` ≠ ∅ → fire `dependency_breakage`
   - 符号级：双侧都声明 `affects_symbols` 且 scanner 给出 `impact_symbols`（非 wildcard），
     且交集为空 → 这一对 PASS（精度收益，**不报**）
   - **任一侧 wildcard / 任一侧没声明 symbols → 退回文件级，必 fire**

所以"必触发"模板就两条路：

- **路径 A**：双方 `resources` 直接撞 → `scope_overlap`
- **路径 B**：A 改的文件被 B 改的文件 import（或反向）→ `dependency_breakage`，
  至少 file-level 必中

下面所有用例都按这两条路设计。

---

# 两人测试（Alice + Bob）

## Test 2.1 — 同文件 overlap（最基础，`scope_overlap`）

**剧本**：

1. Reset to seed
2. Alice：在 `notes_app/db.py` 上 announce intent，objective 写 "重构 `save()` 支持批量写入"
3. Bob（5–30 秒后）：在 `notes_app/db.py` 上 announce intent，objective 写
   "新增 `load_recent()` helper"

**期望结果**：

- 双方都收到 `CONFLICT_REPORT(category="scope_overlap", severity="medium")`
- ConflictCard 显示："Same file — one side should Yield"
- 任一方点 Yield → 卡片消失，另一方继续

**为什么必触发**：`{db.py} ∩ {db.py} = {db.py}` ≠ ∅。和 `affects_symbols` 完全
无关 —— `scope_overlap` 是文件级合约，按 SPEC.md §15.2.1.1 的 MUST 规则不允许被
符号精度"绕过"（同一文件总是冲突候选）。

---

## Test 2.2 — 跨文件文件级依赖冲突（双方都不声明 symbols）

**剧本**：

1. Reset to seed
2. Alice：在 `notes_app/db.py` 上 announce，objective 写 "把 `save()` 改名为
   `persist()`" —— **不声明 `symbols`**
3. Bob：在 `notes_app/api.py` 上 announce，objective 写 "新增请求参数校验" ——
   **不声明 `symbols`**

**期望结果**：

- 后端 scanner 给 Alice 算出 `extensions.impact = ["api.py", "cli.py", "search.py", "exporter.py"]`
- Coordinator：`Alice.impact ∩ Bob.resources = {api.py}` ≠ ∅ → fire
- 双方都收到 `CONFLICT_REPORT(category="dependency_breakage")`
- ConflictCard 显示文件级 fallback 文案：
  **"Alice is editing a file imported by — affects Bob's `notes_app/api.py`"**
- `dependency_detail.ab[0].symbols` = `null`（双方都没声明 symbols）

**为什么必触发**：文件级路径不依赖 `affects_symbols`；只要 impact 集合和对方
resources 集合相交就 fire。Alice 没声明 symbols → 直接走文件级，没有"减少误报"
的精度路径可以救场。

---

## Test 2.3 — 符号级精度冲突（hero case，0.2.3 attr-chain + 0.2.4 from-pkg-import）

**剧本**：

1. Reset to seed
2. Alice：在 `notes_app/db.py` 上 announce，objective 写 "把 `save()` 的返回类型
   改成 `int`"，**`symbols=["notes_app.db.save"]`**
3. Bob：在 `notes_app/api.py` 上 announce，objective 写 "新增 CORS 头"
   （symbols 声不声明都行 —— scanner 自己算 Bob 那侧的 `impact_symbols`）

**期望结果**：

- Scanner 跑 `compute_scope_impact_detailed`，对 api.py 的 import 详细解析：
  - `from notes_app import db` → 0.2.4 推测 `db = notes_app.db`
  - `db.save()` → 0.2.3 attr-chain 解出 `notes_app.db.save`
  - 结论：`impact_symbols[api.py] = ["notes_app.db.save"]`
- 交集：`{notes_app.db.save} ∩ {notes_app.db.save} = {notes_app.db.save}` ≠ ∅ → fire
- 双方收到 `CONFLICT_REPORT(category="dependency_breakage")` + 精确 `dependency_detail`：
  - `ab: [{file: "notes_app/api.py", symbols: ["notes_app.db.save"]}]`
- ConflictCard 显示**精确**文案：
  **"Alice is changing `notes_app.db.save` — affects Bob's `notes_app/api.py`"**

**为什么必触发**：scanner 把 api.py 的具体使用符号解出来了，正好和 Alice 声明的
`notes_app.db.save` 重合。这也是产品对外讲故事的"招牌"那一帧 —— Alice 改 `save`，
Bob 改 api.py，**屏幕上能看见 `notes_app.db.save` 这个具体名字**，而不是笼统的
"冲突"。

---

## Test 2.4 — Dotted-import wildcard 兜底（验证保守路径）

**剧本**：

1. Reset to seed
2. Alice：在 `notes_app/db.py` 上 announce，objective 写 "调整 `list_all()` 输出
   格式"，**`symbols=["notes_app.db.list_all"]`**
3. Bob：在 `notes_app/exporter.py` 上 announce，objective 写 "新增 JSON 导出选项"

**期望结果**：

- Scanner 看到 exporter.py 的 `import notes_app.db`（dotted 形式）→ 标记为 wildcard，
  `impact_symbols[exporter.py] = None`
- 符号判定：wildcard 永远算冲突候选（保守）→ fire
- 双方收到 `CONFLICT_REPORT(category="dependency_breakage")`，但
  `dependency_detail.ab[0].symbols = null`
- ConflictCard 退回 file-level 文案：
  **"Alice is editing a file imported by — affects Bob's `notes_app/exporter.py`"**

**为什么必触发**：`_symbols_actually_clash(symbols=None, …)` by design 返回 True ——
wildcard 是"我不知道你要不要这个 symbol，所以保守地报"。Alice 即便声明了精确
symbol 也救不回来，因为 Bob 那侧 wildcard。

> 💡 这个 case 同时是**反面教学**：BETA_EXAMPLE.md step 5 也用它告诉用户
> "写 `import pkg.sub` 风格会让 MPAC 失去精度，建议用 `from pkg import sub` 或
> `from pkg.sub import name`。"

---

## Test 2.5 — 保证时序重叠（解决"碰不到一起"的问题）

**问题描述**：Test 2.1 – 2.4 都假设 Alice 和 Bob 的 announce 时间窗口能重叠 ——
但用真 Claude relay 时，常见的失败模式是：Alice 的 Claude 收到 prompt → 几秒钟内
announce + 改完文件 + `withdraw_intent`，**Bob 还没敲完 prompt 就已经看不到
Alice 的 intent 了**，conflict 永远不 fire。

intent 的存活期由"持有方主动 withdraw"或"WS 断开"决定，不会因为时间过去就自动
消失。所以"碰在一起"= 把两边的 intent 持有期**强制拉长到能重叠**。下面三种
策略按可靠性排序。

---

### 策略 A — 浏览器 editor 长按住（最稳，不依赖 Claude）

**关键机制**：4-25 P1.3 fix 之后，浏览器 editor 的第一次 keystroke 自动
`begin_task` 一个 intent，**只在切文件 / 关 tab / unmount 时才 `yield_task`**。
所以"持有住 intent" = "tab 别动、文件别切"。

**剧本**：

1. Reset to seed
2. Alice 浏览器（普通窗口）：登录 → 打开项目页 → 点 `notes_app/db.py` → editor
   随便敲一个字符（在末尾加个空格也行）
   - 触发：浏览器自动 `begin_task` on `notes_app/db.py`
   - **不要切走、不要关 tab，不要点别的文件**
3. **不要等**，立刻在 Bob 浏览器（隐私窗口或另一个 profile）：登录 → 打开同一个
   项目页 → 点 `notes_app/db.py` → editor 敲一个字符
   - 触发：Bob 的浏览器 `begin_task` on `notes_app/db.py`
   - 此时 Alice 的 intent 还在 → coordinator pairwise 判定 → fire `CONFLICT_REPORT`
4. 双方 Conflicts 面板弹出 scope_overlap 卡

**期望结果**：跟 Test 2.1 完全一致 —— `scope_overlap` on db.py，severity medium，
双方都看到。区别只在于"intent 怎么被持续持有"。

**为什么必触发**：`begin_task` 的存活期锚定在**浏览器 tab 状态**上，不是锚定在
"Claude 改完文件就 withdraw"。只要 Alice 不切走、不关 tab，intent 一直活；Bob
随时进来都撞得上 —— 完全不依赖 Bob 在多少秒内到达。

**清理**：测完两人各自切到别的文件（`yield_task` 触发）或刷新页面，intent 释放。

---

### 策略 B — 用 `demo_driver.py` 占住一侧（synthetic，0 Claude 依赖）

**关键机制**：`scripts/demo_driver.py announce --hold <N>` 用 carol 账号开 WS、发
`begin_task`、然后**保持 WS 打开 N 秒**才关闭。期间 intent 一直 live。

**剧本**：

```bash
# 终端 1：Carol 占住 db.py 60 秒（足够另一边走完所有人工步骤）
.venv/bin/python scripts/demo_driver.py announce \
    --files notes_app/db.py --hold 60

# 输出会停在 "[carol] ← ..."  loop 等 envelope；intent 此刻 live

# 终端 2（或浏览器）：Bob / Alice / Dave 任意一个真用户开始 announce
#   走 Claude relay 也行、走浏览器 editor 也行
#   只要在 60 秒内到达，必撞
```

**期望结果**：Carol（synthetic 占位方）和真用户那侧都收到 `CONFLICT_REPORT`。
真用户那侧能看到 ConflictCard 显示 vs `Carol's session`（或 `carol@mpac.test`，
看 demo_driver 的 display name 怎么 mint 的）。

**为什么必触发**：60 秒 hold 是脚本自己的 `asyncio.sleep` 控制 WS 关闭时间，跟
对方任何节奏完全解耦。改 `--hold` 数值就能任意调整窗口宽度。

**注意**：脚本依赖事先跑过 `scripts/demo_driver.py setup` 把 carol 账号 + creds
mint 出来。如果在 prod 跑，要先改 `--base` / `--ws-base` 指向 prod URL，并且
确认 prod 上有 carol 账号（`scripts/seed_test_users.py` 或手动注册）。

---

### 策略 C — 给 Claude 明确的"announce 但不要 withdraw"prompt

**关键机制**：Claude 默认行为是 announce → do work → withdraw_intent。要让它
hold，得 prompt 里**明确说不要 withdraw**。

**剧本**：

1. Reset to seed
2. 在 Alice 的 chat board 输入：
   > "请你在 `notes_app/db.py` 上 announce 一个 intent（objective: 重构 `save()`，
   > affects_symbols=["notes_app.db.save"]）。**不要做任何代码修改，不要调用
   > `withdraw_intent`**。announce 成功后告诉我"已 announce，等待指令"然后停下。"
3. Alice 那边 chat 显示 "已 announce" 之后（说明 intent live），切到 Bob 的 chat：
   > "请你在 `notes_app/api.py` 上 announce 一个 intent（objective: 新增 CORS
   > 头）。announce 成功后告诉我结果。"
4. Bob 那边 announce 时 Alice 的 intent 还在 → fire `CONFLICT_REPORT`
5. 收尾：分别告诉两个 Claude "现在 withdraw 你的 intent"

**期望结果**：跟 Test 2.3 一致 —— `dependency_breakage` with precise
`notes_app.db.save` symbol。区别是验证了"真 Claude relay 路径"端到端能工作。

**坑**：

- Claude 偶尔会"善意地"提前 withdraw（"我已经 announce 完了，应该礼貌地释放"）。
  如果 chat 里看到它说"已 withdraw"，重来一次 + prompt 加狠"**绝对不要 withdraw_intent，
  你只 announce 就停**"。
- 如果 Alice 的 Claude 在等待时被刷新 / 重启 relay，WS 断开会 broadcast withdraw。
  保持 relay 终端别动。

---

### 一句话选型

| 想测什么 | 选哪个策略 |
|---|---|
| 协议 / coordinator 路径正确性 | A（浏览器，最快最稳） |
| 大批量自动化 / CI 风格 smoke | B（demo_driver `--hold`） |
| 真实 Claude relay 端到端 | C（prompt control） |
| 本周内测的"必复现冲突"演示 | A 起步，演完后再用 C 演完整 Claude 流 |

---

# 三人测试（Alice + Bob + Carol）

## Test 3.1 — 同文件三方撞（3-way `scope_overlap`）

**剧本**：

1. Reset to seed
2. Alice：在 `notes_app/db.py` 上 announce，objective 写 "新增事务包装"
3. Bob（晚 Alice 几秒）：在 `notes_app/db.py` 上 announce，objective 写
   "新增 `load_recent()` helper"
4. Carol（再晚几秒）：在 `notes_app/db.py` 上 announce，objective 写
   "把 `load()` 改名为 `fetch()`"

**期望结果**（按到达顺序）：

- Alice 到达 → 0 conflicts（独自一人）
- Bob 到达 → 1 个新 `CONFLICT_REPORT`：Alice ↔ Bob（scope_overlap on db.py），双方都收到
- Carol 到达 → 2 个新 `CONFLICT_REPORT`：Carol ↔ Alice + Carol ↔ Bob
- 三人各自的 Conflicts 面板：
  - Alice：2 张卡（vs Bob，vs Carol）
  - Bob：2 张卡（vs Alice，vs Carol）
  - Carol：2 张卡（vs Alice，vs Bob）
- 全局 live conflicts 总数 = 3（每对一张）

**为什么必触发**：每一对 pairwise 都 `scope_overlap` 命中。Coordinator 在
`_detect_scope_overlaps()` 里对每个新进来的 intent 跟所有现存 intent **逐对**
比较，每命中一对就 emit 一个 `CONFLICT_REPORT`。

**收尾观察**：随便一人点 Yield → 跟他相关的 2 张卡消失（双向都消）；剩下两人之间
那一张还在，继续撞。这是验证 routing 的好 demo —— `CONFLICT_REPORT` 必须送到
"当事人 + 当事人浏览器 sibling" 四个 socket（详见 4-26 daily report）。

---

## Test 3.2 — Hub-and-spoke（一个枢纽 + 两个下游）

**剧本**：

1. Reset to seed
2. Alice（hub）：在 `notes_app/db.py` 上 announce，objective 写 "重构整个 DB 层"，
   **`symbols=["notes_app.db.save", "notes_app.db.load"]`**
3. Bob（spoke 1）：在 `notes_app/api.py` 上 announce，objective 写 "新增日志中间件"
4. Carol（spoke 2）：在 `notes_app/cli.py` 上 announce，objective 写 "新增交互式 REPL"

**期望结果**：

- Scanner 给 Alice 算出 `impact_symbols`：
  - api.py → `["notes_app.db.save"]`（attr-chain 解 `db.save()`）
  - cli.py → `["notes_app.db.save", "notes_app.db.load", "notes_app.db.delete"]`
    （多符号 from-import）
  - search.py → `["notes_app.db.load"]`（**只 import `load`，本剧本没人在它身上**）
  - exporter.py → `None`（dotted）
- Pairwise 判定：
  - Alice ↔ Bob：`{save, load} ∩ {save} = {save}` ≠ ∅ → fire（精确 `notes_app.db.save`）
  - Alice ↔ Carol：`{save, load} ∩ {save, load, delete} = {save, load}` ≠ ∅ → fire
    （精确 `notes_app.db.save, notes_app.db.load`）
  - Bob ↔ Carol：api.py 和 cli.py 互不 import → **没有冲突**
- 总计 2 个 `CONFLICT_REPORT`：
  - Alice 看到 2 张卡（vs Bob + vs Carol）
  - Bob / Carol 各看到 1 张（都只 vs Alice）

**为什么必触发**：Alice 的 `affects_symbols` 故意挑了能同时撞 Bob 和 Carol 的两个
符号。Bob 和 Carol 之间不撞的原因是 api.py 和 cli.py 在 import 图里**没有边**，
所以哪怕都涉及 db.py 的下游，也不会互相 fire。

**对比观察**：换一种声明 —— Alice 只声明 `symbols=["notes_app.db.delete"]`：

- api.py 没用 `delete` → Alice ↔ Bob 不 fire（精度收益看得见）
- cli.py 用了 `delete` → Alice ↔ Carol 仍 fire
- 总冲突数从 2 降为 1。可以现场对比 demo 出"声明范围 = 冲突半径"的关系。

---

## Test 3.3 — 混合矩阵（overlap + dependency 同时出现）

**剧本**：

1. Reset to seed
2. Alice：在 `notes_app/db.py` 上 announce，objective "重构 `save()`" —— 不声明 symbols
3. Bob：在 `notes_app/db.py` 上 announce，objective "新增事务支持" —— 不声明 symbols
4. Carol：在 `notes_app/cli.py` 上 announce，objective "新增 CSV 导入" —— 不声明 symbols

**期望结果**：

- Pairwise 判定：
  - Alice ↔ Bob：同文件 db.py → `scope_overlap`
  - Alice ↔ Carol：cli.py imports db.py → 文件级 `dependency_breakage`
  - Bob ↔ Carol：cli.py imports db.py → 文件级 `dependency_breakage`
- 总计 3 个 `CONFLICT_REPORT`，**两种 category 同时出现**：
  - Alice / Bob 各 2 张卡（一张 scope_overlap、一张 dependency_breakage）
  - Carol 2 张卡（vs Alice + vs Bob，都是 dependency_breakage）

**为什么必触发**：

- scope_overlap 路径：`{db.py} ∩ {db.py}` 必中
- dependency 路径：scanner 给 Alice / Bob 算出的 impact 都包含 cli.py，和 Carol
  的 resources 必中
- 三个人都不声明 symbols → 全走文件级，没有精度路径可以减误报

**好处**：一个剧本同时验证 ConflictCard 渲染两种不同 category 的文案 + 同一参与者
出现多张卡的 UI 排版（v3 review 抓到过 broadcast 排错 principal 的 bug，
就是这种"一个用户多张卡"场景容易暴露 routing 问题）。

---

## Test 3.4（可选）— 长链（验证 depth-2 不传递）

**剧本**：

1. Reset to seed
2. Alice：在 `notes_app/models.py` 上 announce，objective "调整 `Note` dataclass 结构"
   —— 不声明 symbols
3. Bob：在 `notes_app/db.py` 上 announce，objective "适配新 Note 结构调整 `save()`
   签名" —— 不声明 symbols
4. Carol：在 `notes_app/api.py` 上 announce，objective "适配新 Note 结构更新 HTTP
   序列化" —— 不声明 symbols

**期望结果**：

- models.py 反向依赖 = `[db, search, api, cli]`
- db.py 反向依赖 = `[search, api, cli, exporter]`
- Pairwise：
  - Alice ↔ Bob：models.impact 包含 db.py → fire（dependency_breakage）
  - Alice ↔ Carol：models.impact 包含 api.py → fire（dependency_breakage）
  - Bob ↔ Carol：db.impact 包含 api.py → fire（dependency_breakage）
- 总计 3 个 `CONFLICT_REPORT`，**全部 dependency_breakage**

**为什么必触发**：每对都走"一侧的 impact 集合包含另一侧的 resources 文件"路径。

**重要注意**：MPAC **不算传递闭包**。"models.py 改 → 影响 db.py → 影响 api.py" 这条
链条只算到 1 层 —— Alice ↔ Carol fire 是因为 models.py 的反向依赖里**直接**有
api.py（api.py 自己 `from notes_app.models import Note`），不是因为"传递了 db
那一跳"。

要观察传递性的缺失：把 Alice 改成 announce on **search.py**（search.py 没人 import），
那 Alice 跟谁都不会撞 —— 即便 search 自己 import 了 db.py，也不会"传递"出去。
未来支持传递闭包后这个 case 会变 fire；现在的版本不会，作为已知行为记录。

---

# 反向控制（应该 NOT fire 的 case，作为精度回归探针）

## Test N1 — 符号 disjoint 安全编辑（验证 0.2.2 精度）

**剧本**：

1. Reset to seed
2. Alice：在 `notes_app/db.py` 上 announce，**`symbols=["notes_app.db.save"]`**
3. Carol：在 `notes_app/search.py` 上 announce，objective "新增模糊匹配"

**期望结果**：

- Scanner：search.py 的 import 是 `from notes_app.db import load` →
  `impact_symbols[search.py] = ["notes_app.db.load"]`
- 交集：`{notes_app.db.save} ∩ {notes_app.db.load} = ∅` → **不 fire**
- 两人安静干活，Conflicts 面板空

**为什么这个 case 重要**：如果它**fire 了**冲突，说明：

1. 要么 relay 把 Alice 的 `symbols` 字段吞了（mpac-mcp `announce_intent` schema bug）
2. 要么 web-app 的 `compute_scope_impact_detailed` 路径退化成了 `compute_scope_impact`（文件级）
3. 要么 scanner 的 attr-chain / from-import 解析回退到 wildcard

任何一种都是 0.2.2 / 0.2.3 / 0.2.4 三个版本里某项能力的回归。把它放在测试集
最后跑一遍 = 一只精度的金丝雀。

---

# 测试执行清单

每个 case 跑前：

- [ ] 项目 **Reset to seed**（项目页右上角按钮 / `POST /api/projects/{id}/reset-to-seed`）
- [ ] 每个参与者一个浏览器（隐私窗口 / 不同 profile，避免 cookie 串）；
      或者用 `scripts/demo_driver.py` 直接发 envelope 不依赖 Claude
- [ ] WHO'S WORKING 面板里能看到所有参与者
- [ ] 想用 Claude 真发 announce 的话：每人 header 是 `🟢 Claude connected` +
      终端 relay 显示 `[relay] Connected to wss://...`

每个 case 跑后捕获：

- [ ] 每个参与者的 Conflicts 面板截图（卡片数 + category 标签）
- [ ] 每个 Claude 的 chat board 文字（"Detected conflict with Bob on db.py"）
- [ ] DevTools Network → WS frames 里 `CONFLICT_REPORT` 信封 payload
      （特别是 `dependency_detail` 字段）
- [ ] 解决（Yield）后，相关卡片在 < 1 秒内消失

跑完一组：

- [ ] 还原项目状态：再点一次 Reset to seed，或直接把 `notes_app/` 还原回 seed
      字典（这一步只对**真编辑过文件**的剧本有意义；只 announce + Yield 不实际
      改文件的剧本本来就没污染）

---

# 一句话备忘

| Test | 人数 | 触发的 category | 关键算法路径 |
|---|---|---|---|
| 2.1 | 2 | `scope_overlap`           | resources 直接相交 |
| 2.2 | 2 | `dependency_breakage`     | 文件级 fallback（无 symbols） |
| 2.3 | 2 | `dependency_breakage`     | 符号级 attr-chain + from-pkg-import 精确命中 |
| 2.4 | 2 | `dependency_breakage`     | dotted-import wildcard 保守 fire |
| 2.5 | 2 | (跟 2.1–2.4 一样)          | **保证时序重叠**的三种执行方式（浏览器 hold / demo_driver `--hold` / Claude prompt） |
| **用例 3** | **2** | **不 fire**(基线 happy path)| 不同文件并行,真改文件,自然 prompt |
| **用例 4** | **2** | **不 fire**(被动让路)        | check_overlap 后主动放弃,server 端不创建 conflict |
| **用例 5** | **2** | **`dependency_breakage`**(招牌)| 真改文件 + 符号级冲突文案,产品讲故事帧 |
| **用例 6** | **2** | **`scope_overlap`** + last-writer-wins | 软约束语义验证,反面教材 |
| 3.1 | 3 | `scope_overlap` × 3       | pairwise overlap，3 张卡 |
| 3.2 | 3 | `dependency_breakage` × 2 | 1 hub + 2 spoke，spoke 之间不撞 |
| 3.3 | 3 | overlap + dependency × 3  | 矩阵混合，验证 ConflictCard 多 category |
| 3.4 | 3 | `dependency_breakage` × 3 | 长链每对相邻层 fire（不传递） |
| N1  | 2 | （静默 — 必须不 fire）       | 符号精度金丝雀 |
