# 必触发冲突测试用例（2 人 + 3 人）

> **私有文档。** 面向"我想当场触发 conflict 看 UI / 协议反应"的最小测试集 ——
> 每个用例都按 `mpac 0.2.4` + `mpac-mcp 0.2.5` 的算法**精心设计成必触发**，
> 不靠运气、不靠时序。
>
> 区别于 [`BETA_EXAMPLE.md`](BETA_EXAMPLE.md)（5 步教学剧本，含负向 case）和
> [`TWO_USER_TESTS.md`](TWO_USER_TESTS.md)（UI / 协议大杂烩 smoke），本文只回答
> 一个问题："给我几个一定会出冲突的剧本，2 人和 3 人都要。"

---

## 准备工作

- 任意一个 seed 过 `notes_app` 的项目（用 `scripts/seed_example_project.py` 跑出来，
  或者直接在项目页点 **Reset to seed** 按钮）
- 每个参与者都连上 Claude（看到 header `🟢 Claude connected`）；**或者**用
  `scripts/demo_driver.py` 直接发 envelope（不依赖 Claude，更快）
- **每个 case 之前都先 Reset to seed** —— 文件内容 + import 图必须干净，这是
  "必触发"的前提

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
| 3.1 | 3 | `scope_overlap` × 3       | pairwise overlap，3 张卡 |
| 3.2 | 3 | `dependency_breakage` × 2 | 1 hub + 2 spoke，spoke 之间不撞 |
| 3.3 | 3 | overlap + dependency × 3  | 矩阵混合，验证 ConflictCard 多 category |
| 3.4 | 3 | `dependency_breakage` × 3 | 长链每对相邻层 fire（不传递） |
| N1  | 2 | （静默 — 必须不 fire）       | 符号精度金丝雀 |
