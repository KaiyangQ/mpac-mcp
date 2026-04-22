# MPAC Internal Beta — Scenarios Playbook (LEGACY)

> **⚠ LEGACY — 已被 `docs/BETA_EXAMPLE.md` 取代（2026-04-22 下午重写）。**
>
> 留着这份的理由：里面 **scenario 4**（`from pkg import mod` + `mod.attr()`）
> 是一份**反面教材**。当时按 0.2.3 日报宣传的"覆盖最常见 Python 写法"设计了
> 这个 scenario，但 seed 实际种子在 0.2.3 scanner 下**触发的不是退回文件级，
> 是完全零冲突** —— `from pkg import mod` 这条分支根本没被 0.2.3 的 attr-chain
> walker 看到（只处理 `ast.Import`，不处理 `ast.ImportFrom`）。今天下午修掉
> （`mpac 0.2.4`，commit `e45c920`），顺手把剧本重构成一个综合项目
> `notes_app`，见 `BETA_EXAMPLE.md`。
>
> 如果日后想查 "4 个分离 scenario" 的历史版本、或者想手动重现 0.2.3 vs 0.2.4
> 的行为差异，可以继续读这份。
>
> **现役剧本**：`docs/BETA_EXAMPLE.md`。

---

> **私有文档。** 面向内测参与者（和你自己）。里面含示例 invite 码和测试账号 —— 不要贴到公开仓库。
>
> 旧测试项目引用（2026-04-22 下午前）：`projects/8` 即 `beta-demo-20260422-1342`。
> 运行 `scripts/seed_beta_scenarios.py` 可以创建同款新的一份（如果想重现旧行为的话）。

---

## 👋 先看这个：**一行命令接上 Claude**

```
┌──────────────────┐    ┌────────────────────────┐
│ 1. 加入测试项目   │ →  │ 2. 粘一行命令到终端     │
│   (~30 秒)       │    │  (剩下都是自动的)        │
└──────────────────┘    └────────────────────────┘
```

**仅有的前置条件**：你的机器得有 `node` 和 `python3`。没有的话先装：
- Node.js LTS：<https://nodejs.org/>
- Python 3.9+（macOS 自带；Windows/Linux 按官方文档）

**以及你要有 Claude Pro 或 Max 订阅** —— 内测依赖你自己的订阅走 Claude Code。

---

### 步骤 1：加入测试项目（~30 秒）

1. 打开你收到的 **invite 链接**（组织者发给你，形如 `https://mpac-web.duckdns.org/invite/xxx`）
2. 如果还没账号，用 invite 码在 <https://mpac-web.duckdns.org/register> 注册
3. 登录后自动跳到项目页，网址形如 `https://mpac-web.duckdns.org/projects/N`

### 步骤 2：粘一行命令到你的本地终端（~20 秒 + 首次安装时间）

在项目页右上角点 **🤖 Connect Claude**。弹出的 Modal 里 **根据你的系统** 显示一行命令。

**macOS / Linux / WSL / Git Bash**（Modal 顶上会自动选中 "macOS / Linux"）:

```bash
bash <(curl -fsSL 'https://mpac-web.duckdns.org/api/projects/N/bootstrap.sh?token=xxx')
```

**Windows PowerShell**（Modal 顶上切到 "Windows"）:

```powershell
iex (irm 'https://mpac-web.duckdns.org/api/projects/N/bootstrap.ps1?token=xxx')
```

**点 Modal 里的 Copy → 粘到一个新终端窗口 → 回车**。就这样。Modal 会按浏览器 userAgent 自动猜你的系统，不对就手动点 toggle 切换。

这条命令会让服务端返回一个 shell 脚本，脚本自动处理：
1. 检测 Claude Code 是否装了；没装就 `npm install -g @anthropic-ai/claude-code`
2. 检测是否登录过 Claude；没登过就**自动跳出浏览器**让你登（一辈子只登一次）
3. 装 `mpac-mcp`（已装了就跳过；装不上会自动 fallback `--user` 或 `--break-system-packages`）
4. 启动 relay，连进项目

**第一次跑大概 1-3 分钟**（主要是 npm 装 Claude Code 的时间）。之后每次重新 connect 都是秒级。

**浏览器 Modal** 会自动从 "Waiting for relay..." 变成 "**Connected**"，你名字边上出现 🤖，可以关 Modal 了。

---

### 故障排查

| 症状 | 解法 |
|---|---|
| `bash: command not found: npm` | 装 Node.js LTS：<https://nodejs.org/> |
| `No Python >= 3.10 found` | `brew install python@3.12`（macOS）／ `apt install python3.12`（Ubuntu 22+）／ `winget install Python.Python.3.12`（Windows） |
| 浏览器自动跳出 Claude 登录但你关了 | 重新跑一次那条命令就好 |
| Token 已过期 / 401 / 403 | 浏览器关 Modal 再点 Connect Claude，拿一条新命令 |
| 脚本跑完终端日志停住了 | **那就对了**！这是 relay 长驻进程，别关终端窗口 |

> **注意 macOS 系统 Python 不够用**：`/usr/bin/python3` 是 Command Line Tools 自带的 3.9.6，mpac-mcp 依赖 `mcp` 要求 ≥ 3.10。脚本会自动扫描 `python3.13 → 3.10` 然后才回退 `python3`；brew / pyenv / python.org 随便装一个 3.10+ 就能自动识别。

**三个测试者都完成步骤 2**，项目页 WHO'S WORKING 面板里会看到**三个 🤖**。然后开始下面的场景剧本。

---

## Why this doc exists

本次内测主要验证 MPAC **协调能力**，不验证"能不能在 web 里跑代码"（那个功能我们没做）。四个场景从最简单的文件级冲突，一步步展到最新的符号级精度 + 前端具体冲突显示。

**测试者每人要做的**：用 Claude Code 本地连进来（上面三步）→ 照剧本对 Claude 说话 → 肉眼在浏览器观察 MPAC 的反应是否符合预期。

> **小 tip**：Files 面板现在支持**右键新建 / 删除文件**（VSCode 风格）。右键空白 = "New file"；右键文件夹 = "New file in pkg/"（自动预填路径）；右键文件 = New file + Delete。顶栏的 `+` 按钮还在。

---

## 共享约定

- 每个场景都用独立的顶层包（`scenario_1_same_file/`, `scenario_2_dep_breakage/`, ...），导入链用 **完整路径**（`from scenario_2_dep_breakage.utils import fetch_data`），MPAC scanner 能正确解析。
- 每一步说完"**对 Claude 说**: ..."之后，给 Claude 5-15 秒处理时间，同时**紧盯浏览器**。
- 每个场景结束后，最好让所有人点 **Acknowledge** 或 **Yield** 把冲突清掉，避免状态污染下一个场景。
- **每个场景开始前**，建议让每个人的 Claude 先调一次 `list_active_intents()`（新工具，mpac-mcp 0.2.2+）—— Claude 会自己报告"我看到 Alice 在做 X、Bob 在做 Y"，全局视角从第一秒就建立。

以下叙述里约定**三人**：**Alice / Bob / Carol**。如果只有两个测试者，可以跳过场景 3 的 Carol 那段或者让同一个人分饰两角（轮流）。

---

## 场景 1：**Same-file overlap**（热身，~2 分钟）

**目标**：见证最原始的文件级冲突检测。

**涉及文件**：`scenario_1_same_file/auth.py`（项目里已预先种好）

### 脚本

1. **Alice** 对她本地的 Claude 说：
   > "改 `scenario_1_same_file/auth.py` 里的 verify_password，让它用 bcrypt 校验。"
2. 等大约 10 秒，**Bob** 对他本地的 Claude 说：
   > "在 `scenario_1_same_file/auth.py` 里加 MFA 支持。"

### 期望观察

- Alice 的 Claude 先 `check_overlap()` → 通过 → `announce_intent([auth.py])`
- Bob 的 Claude `check_overlap()` → **看到 Alice** → 要么主动 yield、要么硬冲
- 如果 Bob 硬冲：三个浏览器（包括观察方 Carol）都看到一张红色冲突卡：
  ```
  ⚠ Scope overlap
  Alice ↔ Bob
  ```
- Bob 可以点 **Yield** 撤掉自己的 intent，冲突卡消失

### Debrief

"**当两个人声明编辑同一个文件时 MPAC 会警告**" —— 这是最无争议的用例，给接下来的场景建立 baseline。

---

## 场景 2：**跨文件依赖冲突**（MPAC 0.2.1 核心卖点，~3 分钟）

**目标**：展示"文件路径不重叠也会报冲突" —— 这是普通 IDE / git 做不到的。

**涉及文件**：
```
scenario_2_dep_breakage/
  utils.py       ← fetch_data, parse_result
  api.py         ← imports fetch_data
  handler.py     ← imports parse_result
```

### 脚本

1. **Alice** 对 Claude 说：
   > "重构 `scenario_2_dep_breakage/utils.py`，把 fetch_data 改成用 httpx 的 async 版本。"
2. 等 10 秒，**Bob** 对 Claude 说：
   > "在 `scenario_2_dep_breakage/api.py` 里加 try/except 错误处理。"

### 期望观察

- Alice announce `[utils.py]` → 服务端**自动**算出 impact `[api.py, handler.py]`
- Bob announce `[api.py]` → **冲突触发**！
- 冲突卡（新样式 v0.2.3）：
  ```
  ⚠ Dependency
  Alice ↔ Bob

  Alice is editing a file imported by — affects Bob's `api.py`
  ```
  （因为 Alice 没声明具体 symbols，退回文件级文案）

### Debrief

"**MPAC 读你的 import 关系图**" —— 这是它比 git merge 或 IDE 文件锁更强的地方。0.2.1 开始就有。

---

## 场景 3：**符号级精度 + 三人协调**（Hero Demo，MPAC 0.2.2 + 0.2.3，~5 分钟）

**目标**：展示 MPAC **不会误报** —— 改同一个文件的不同符号，别人不受打扰；改到了同一个符号，立刻明确告知。

**涉及文件**：
```
scenario_3_symbol_precision/
  utils.py       ← def fetch, def parse
  main.py        ← from ... import fetch
  cli.py         ← from ... import parse
```

关键：`main.py` 只用 `fetch`，`cli.py` 只用 `parse` —— 两个 importer 用的**符号完全不同**。

### 脚本

**先各自建立全局视图**（这一步是新的，0.2.2 起强烈建议）：
- 三人同时对自己的 Claude 说："**先调 `list_active_intents()` 看看现在项目里有谁在做什么**，然后我告诉你我的任务。"
- 预期：Claude 返回"没人在干活"（第一轮），人再讲自己的任务

1. **Alice** 对 Claude 说：
   > "给 `scenario_3_symbol_precision/utils.py` 里的 **fetch** 函数加 functools.lru_cache。注意只改 fetch，不要碰 parse。announce_intent 的时候把 symbols 参数设成 `[\"scenario_3_symbol_precision.utils.fetch\"]`。"

   （我们在 prompt 里主动让 Claude 用 `symbols` —— 0.2.1 的 mpac-mcp 工具支持这个参数，但 Claude 需要被教才会填。内测中这是**学到的一招**：用户显式指令最可靠。）

2. 等 10 秒，**Bob** 对 Claude 说：
   > "**先调 `list_active_intents()` 看看有没有人在忙**。然后帮我给 `scenario_3_symbol_precision/main.py` 里的 run 函数加重试机制（失败最多 3 次）。"

   期望：Claude 会报告"Alice 在改 utils.fetch"，然后继续。

3. 再等 10 秒，**Carol** 对 Claude 说：
   > "**先 `list_active_intents()`**。然后在 `scenario_3_symbol_precision/cli.py` 里加一个 --json 标志，输出 parse 结果的 JSON。"

   期望：Claude 会报告"Alice 在改 utils.fetch（影响 main.py）、Bob 在改 main.py。我要改 cli.py，用的是 utils.parse，和他们不冲突 —— 开干"。**这就是全局视角带来的协作感**。

### 期望观察

| 谁 | 期望看到 |
|---|---|
| Alice | intent 带 `extensions.affects_symbols = [scenario_3_symbol_precision.utils.fetch]` |
| Bob | ⚠ 红色冲突卡：**"Alice is changing `scenario_3_symbol_precision.utils.fetch` — affects Bob's `scenario_3_symbol_precision/main.py`"** |
| Carol | **✅ 没有冲突。**Claude 平静开始改 cli.py |

### Debrief

**这是整场内测最值得"哇一下"的时刻**：
- 普通协作工具：两个人改 utils.py 的不同函数也会互锁
- MPAC 0.2.2：服务端知道符号级意图，Carol 不被打扰
- MPAC 0.2.3：Bob 的冲突提示里**直接打出具体符号名**，不用猜

如果 Alice 那步没带 `symbols` 参数（Claude 没按指令填），Carol 也会被误拦。这是功能 gate，演示时要确认生效了 —— 看 Alice 的 intent 在浏览器里展开时 `affects_symbols` 字段有没有值。

---

## 场景 4：**Attribute-chain 解析**（MPAC 0.2.3 细节补丁，~3 分钟）

**目标**：证明用 `import cache` + `cache.store()` 这种写法也能被解析成具体符号，不退回通配。

**涉及文件**：
```
scenario_4_attr_chain/
  cache.py       ← def store, def load
  service.py     ← import cache; cache.store(...)       ← 关键写法
  noop.py        ← 无关文件，用作"负控制"
```

### 脚本

1. **Alice**：
   > "给 `scenario_4_attr_chain/cache.py` 的 **store** 加一个 TTL 过期参数。announce_intent 时 symbols 传 `[\"scenario_4_attr_chain.cache.store\"]`。"

2. 等 10 秒，**Bob**：
   > "改 `scenario_4_attr_chain/service.py`，让 save 函数在调用 cache.store 前先打印日志。"

3. 等 10 秒，**Carol**：
   > "改 `scenario_4_attr_chain/noop.py`，把 unrelated 的返回值改成 100。"

### 期望观察

- Bob 的 `service.py` 里是 `import cache; cache.store(...)` —— 0.2.2 scanner 会标通配 → 误报。**0.2.3 scanner 识别出了具体访问的是 `cache.store`** → 和 Alice 的 `affects_symbols` 对得上 → **精确冲突**。
- 冲突卡："Alice is changing `scenario_4_attr_chain.cache.store` — affects Bob's `scenario_4_attr_chain/service.py`"
- Carol 改 `noop.py`：**无冲突**，完全安静

### Debrief

"**`import utils; utils.foo()` 这种超常见写法也能精到符号**" —— 0.2.3 填的这个坑看似小，但 real-world Python 代码里太多这种写法，不处理就等于 0.2.2 的精度在一半项目里失效。

---

## 内测过程中观察什么

每个场景跑完，请测试者反馈这几件事：

1. **Claude 有没有按指令填 `symbols` 参数？** 预期：场景 3、4 显式要求时 Claude 会填。如果不填 → prompt 工程问题。
2. **冲突卡片的文案能不能一眼看懂？** 预期：场景 3 里 Bob 看到"Alice is changing X"直接知道要干嘛；如果反而更困惑 → UI 反馈。
3. **Claude 自己的反应**：它看到 `check_overlap` 返回非空时，是主动 yield、还是硬冲？哪种更符合期望？
4. **延迟**：从 announce 到冲突卡出现大约多长？生产实测 < 1 秒，如果明显更慢 → 汇报。
5. **有没有发生过"应该报冲突但没报"**（漏报）？或"不该报却报了"（误报）？每次都记下来，带上浏览器 DevTools 里 WS 收到的 `INTENT_ANNOUNCE` / `CONFLICT_REPORT` payload。

---

## 故障排查速查

| 症状 | 可能原因 | 解法 |
|---|---|---|
| Terminal 运行 `mpac-mcp-relay` 命令，浏览器一直没出现 🤖 | Token 失效 / CORS / relay 挂 | 浏览器重新点 Connect Claude，换条命令再跑；查 terminal 里有没有 `Switching Protocols` 这行 |
| Claude 说"check_overlap 没返回任何人" 但你确信别人在 | WS 未打开 / 账号不是同一个项目 | 浏览器刷新一下，确认 WHO'S WORKING 能看到别人；如果看不到，自己的 relay 没挂上 |
| 冲突卡片显示 `dependency_breakage` 而不是 "Dependency" | 前端 bundle 太老 | Ctrl+Shift+R 强刷浏览器 |
| 场景 3 Carol 也被报了冲突 | Alice 没填 symbols；`mpac-mcp < 0.2.1`；或内嵌 Claude agent 路径没传 symbols | 核对 Alice `pip show mpac-mcp` 是否 0.2.1；看 Alice 的 intent payload 里 `extensions.affects_symbols` 有没有值 |
| 场景 4 Bob 没被报冲突（应该报） | 服务端 mpac < 0.2.3 / prod 没重启 | SSH 到 Lightsail：`sudo docker exec aws-lightsail-api-1 pip show mpac` 应返回 Version 0.2.3 |

---

## 结束后请收集的反馈

1. 四个场景中，哪些"符合预期"？哪些"没按预期跑"？
2. 最"值得记住"的一刻是什么？（拿来写推广文案）
3. 最"让人困惑"的一刻是什么？（下一轮迭代的首要候选）
4. 如果要推广给外面（不是内测），**真正的障碍**是什么？是概念难懂、还是设置麻烦、还是集成方式怪？

反馈随便一张纸 / 一段语音都行，跑完就发。

---

## 相关链接

- **生产 URL**: <https://mpac-web.duckdns.org>
- **BETA_ACCESS.md**（测试账号凭据，私有）：`./BETA_ACCESS.md`
- **mpac 在 PyPI**: <https://pypi.org/project/mpac/> — 目前 0.2.3
- **mpac-mcp 在 PyPI**: <https://pypi.org/project/mpac-mcp/> — 目前 0.2.2
- **协议规范**: `./SPEC.md` —— 想了解冲突类别 / envelope 结构来源的，这里有权威定义
- **上线记录**: `./daily_reports/` —— 每次新版本上线的 changelog + 决策记录
