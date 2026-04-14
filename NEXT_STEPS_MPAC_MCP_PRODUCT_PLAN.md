# MPAC 下一步路线文档

## 1. 结论先行

我们下一步不应该在下面两个方向里二选一：

1. 做一个协作编程产品
2. 把 MPAC 暴露成 MCP Server

正确路线是把两者合并：

- **产品切口**：AI 协作编程
- **接入形态**：MCP Server
- **技术内核**：MPAC

一句话表述：

> 让不同人的 coding agent 在同一个 repo 里先协调、再动手。

第一版不做“大而全平台”，而是做一个面向协作编程场景的 `mpac-mcp`，先跑通本地和单机双 agent demo，再进入 shared coordinator 和团队化阶段。

---

## 2. 我们现在已经有什么

当前仓库已经具备的核心资产，不是概念，而是可运行能力：

- `mpac-package/src/mpac_protocol/core/coordinator.py`
  - MPAC 协调内核
  - 支持 intent、conflict、resolution、claim、pre-commit 等核心语义
- `mpac-package/src/mpac_protocol/server.py`
  - MPAC WebSocket server
  - 持有共享 workspace，并负责消息 relay 和 sideband 文件读写
- `mpac-package/src/mpac_protocol/agent.py`
  - 参考 agent/client
  - 已有 `execute_task()`、冲突检测、mutual yield 自动重试、rebase、pre-commit、claim、escalation 等工作流
- `test_e2e_scenarios.py`
  - 长连接协作测试
  - 验证无冲突、冲突、依赖链、rebase、不对称 yield、mutual yield 重试
- `test_ultimate.py`
  - 多场景终极测试
  - 覆盖 `task_set`、pre-commit、fault recovery、arbiter resolution 等能力
- PyPI 已发布 `mpac`
- GitHub 已有公开仓库 `KaiyangQ/mpac-protocol`

换句话说：

- 我们已经有 **协议内核**
- 已经有 **参考 server**
- 已经有 **参考 agent**
- 已经有 **强测试证据**

我们缺的不是“能力本体”，而是一个**让现有 AI 客户端可以直接接入的产品入口**。

---

## 3. MCP Server 和现有代码的关系

最容易混淆的一点是：MCP Server 不是来替代现有 MPAC 代码的。

### 3.1 现有代码负责什么

现有代码解决的是：

- agent 与 agent 如何协调
- intent 如何声明
- 冲突如何检测
- stale commit 如何处理
- 任务如何 claim
- 冲突如何 escalation / resolution

也就是：

**MPAC = 协调语义和运行时**

### 3.2 MCP Server 负责什么

MCP Server 解决的是：

- Cursor / Claude Code / VS Code / Copilot 这类现成 AI 客户端
- 怎么调用我们这套能力

也就是：

**MCP Server = 接入层 / 适配层**

### 3.3 一句话关系

- `mpac`：发动机
- `mpac-mcp`：把发动机接到现有 AI 客户端上的接口层

所以正确做法不是重写，而是：

- **保留 `mpac` 作为核心 runtime**
- **新增 `mpac-mcp` 作为 MCP 适配层**

---

## 4. 为什么第一刀选“协作编程”

原因不是“编程更酷”，而是它和我们现有资产最匹配。

### 4.1 现有验证最强

我们已经大量验证了下面这些代码协作能力：

- `file_set` 级别 scope overlap
- 并发改同一文件
- `STALE_STATE_REF` + rebase
- mutual yield 自动重试
- pre-commit 模式
- fault recovery / claim
- escalation to arbiter

这意味着：第一版做协作编程不是猜，是顺着已有证据走。

### 4.2 用户痛点最容易理解

比起“多主体协调协议”，开发者更容易理解下面这些价值：

- 两个 agent 别同时改同一个文件
- 先看到别人想干什么
- 冲突别等到 commit 才发现
- 出现争议时能升级

### 4.3 工程边界更清楚

如果第一版做旅游规划、合同审阅、会议纪要等通用内容场景，会引入更多产品定义成本。

而协作编程可以直接依赖现有 repo、文件、state_ref、diff、commit 语义，进入速度最快。

---

## 5. 产品形态怎么定义

第一版不要定义成“一个完整 app”。

第一版产品应该定义成：

### 5.1 用户看到的东西

- 一个可安装的 MCP Server：`mpac-mcp`
- 一组高层 tools
- 一份简单配置
- 一个清晰 demo

### 5.2 用户得到的价值

- 让 coding agent 在同一 repo 内彼此可见
- 在动手前 announce intent
- 冲突尽早暴露
- 冲突可 yield / escalate / claim

### 5.3 不要让用户一开始看到的东西

- 21 个协议消息类型
- Lamport watermark
- coordinator epoch
- 过多协议术语

用户要的不是“学习 MPAC”，而是“别撞车”。

---

## 6. 第一版 `mpac-mcp` 应该暴露什么

不要直接把 MPAC message type 暴露成 tool。

应该暴露高层工具，让宿主 agent 以任务视角使用。

建议第一版工具控制在 8 到 10 个：

### 6.1 `begin_task`

用途：

- 开始一个任务
- 宣告 intent
- 返回任务 ID、当前 scope、是否有冲突

输入建议：

- `objective`
- `files`
- 可选 `priority`

背后映射：

- `announce_intent`
- conflict detection

### 6.2 `who_is_working`

用途：

- 查看当前 repo 内有哪些 agent 正在工作
- 看每个 agent 的 objective 和 scope

背后映射：

- 当前 active intents
- participant / session state

### 6.3 `check_overlap`

用途：

- 在真正修改前，先看某个文件集合会不会和别人撞

背后映射：

- `scope_overlap`
- 当前 active intents 的比较

### 6.4 `submit_change`

用途：

- 尝试一次提交改动
- 带 `state_ref_before`
- 返回 `success` / `stale` / `conflict`
- 如果 stale，明确告诉 agent 应该刷新哪些文件和最新 `state_ref`

背后映射：

- `OP_COMMIT`
- optimistic concurrency

第一版建议：

- `submit_change` **只做单次提交尝试**
- 不在一个 tool call 里自动完成 “提交失败 -> re-read -> rebase -> retry” 的整条链
- 如果返回 stale，由宿主 agent 决定：
  - 重读文件后再次 `submit_change`
  - 或者直接 `yield_task`

建议返回字段：

- `status`: `success` / `stale` / `conflict`
- `current_state_ref`
- `conflicting_files`
- `message`

### 6.5 `yield_task`

用途：

- 当前 agent 主动礼让，释放 scope

背后映射：

- `INTENT_WITHDRAW`

### 6.6 `get_file_state`

用途：

- 读取 shared workspace 中某个文件的当前状态
- 返回 `state_ref`
- 按需返回文件内容

背后映射：

- sideband `FILE_READ`
- shared workspace state

为什么第一版需要它：

- `submit_change` 需要 `state_ref_before`
- 宿主 agent 不能靠猜测得到这个值
- 这个 tool 是 `begin_task -> read current state -> submit_change` 闭环中的关键一步

### 6.7 `ack_conflict`

用途：

- 对冲突进行确认或明确标记为 dispute
- 给后续 escalation / resolution 流程铺路

背后映射：

- `CONFLICT_ACK`

### 6.8 `escalate_conflict`

用途：

- 对 unresolved conflict 升级

背后映射：

- `CONFLICT_ESCALATE`

### 6.9 `resolve_conflict`

用途：

- 由 owner 或 arbiter 对冲突给出明确决议
- 关闭已经 ack / escalated 的 conflict

背后映射：

- `RESOLUTION`

### 6.10 `take_over_task`

用途：

- 处理 agent crash / unavailable 的场景

背后映射：

- `INTENT_CLAIM`

---

## 7. 第一版不该做什么

以下内容建议明确延后：

- 不做通用跨行业“多 agent 协作平台”
- 不先做独立桌面 app
- 不先做重型 VS Code 扩展
- 不先做 hosted SaaS
- 不先暴露全部协议消息
- 不先扩到非代码场景

第一版目标是：

**让别人今天就能把它接进 Claude Code / Cursor，看到它真的能避免 agent 撞车。**

补充一条执行经验：

- smoke / demo 脚本尽量运行在**隔离 scratch workspace**
- 不要直接复用长期存在的 repo sidecar 状态
- 这样更容易重复验证，也更不容易被旧 conflict / frozen scope 污染

---

## 8. 技术架构建议

### 8.1 v0：本地单机版

这是第一阶段最建议做的版本。

这里必须明确一个关键事实：

- MCP `stdio` server 是 request/response 形态
- Agent A 的 `mpac-mcp` 和 Agent B 的 `mpac-mcp` 是两个独立进程
- 两个 stdio 进程**不会天然共享内存状态**

所以 v0 不能只说“本地 coordinator”，必须明确**状态权威存放在哪里**。

### 8.1.1 v0 的推荐方案：本地 WebSocket sidecar

推荐方案：

- 每个 AI 客户端本地启动自己的 `mpac-mcp` stdio 进程
- `mpac-mcp` 不自己保存全局状态
- 所有状态统一放进一个本地 sidecar coordinator
- 这个 sidecar 直接复用现有 `MPACServer`

架构：

- 用户在本机启动或自动拉起本地 `MPACServer` sidecar
- `mpac-mcp` 作为 MCP 适配层，通过本地 WebSocket 连接这个 sidecar
- 两个不同 AI 客户端或两个 agent 通过 sidecar 共享同一 repo 状态

启动策略建议：

- `mpac-mcp` 启动时先探测当前 repo 对应的本地 sidecar 端口
- 如果 sidecar 已经在运行，则直接连接
- 如果端口上没有 sidecar，则自动拉起一个新的本地 sidecar

这样用户不需要手工记住“先启动 sidecar 再启动 MCP server”。

这样做的好处：

- 复用现有 `MPACServer` / coordinator 逻辑
- 避免把状态同步硬塞进 MCP stdio 进程
- 不需要第一版就重新设计共享状态存储
- 把 MCP 层保持成薄 wrapper

### 8.1.2 为什么 v0 不优先选共享文件或 SQLite

| 方案 | 优点 | 缺点 |
|------|------|------|
| 共享文件（如 `.mpac/state.json`） | 最简单 | 并发写、锁、崩溃恢复都麻烦 |
| SQLite | 单文件、并发较安全 | 需要重新设计 coordinator 状态持久化层 |
| 本地 WebSocket sidecar | 最大复用现有实现 | 本地多一个进程 |

v0 推荐结论：

**优先选本地 WebSocket sidecar。**

原因不是它理论上最优，而是它最贴合现有代码、最少改动、最能快速证明闭环。

### 8.1.3 v0 架构图

```text
Claude Code / Cursor
    -> mpac-mcp (stdio)
    -> local MPACServer sidecar (WebSocket)
    -> SessionCoordinator + shared workspace state
```

优点：

- 不涉及远程部署
- 不涉及认证
- 不涉及公网 coordinator
- 最容易录 demo
- 对现有 `mpac` 代码复用最多

### 8.2 v1：shared coordinator

第二阶段再做：

- 每个用户本地跑自己的 `mpac-mcp`
- 共同连接到一个 shared coordinator
- 开始支持真正跨人协作

### 8.3 v2：hosted product

最后再做：

- hosted coordinator
- session 管理
- dashboard
- 身份与权限
- 团队管理

---

## 9. 推荐的阶段路线

## Phase 0：概念冻结

目标：

- 明确第一版只做“AI 协作编程”
- 明确第一版通过 MCP Server 交付

完成标准：

- 对外一句话表述确定
- 第一版工具列表确定
- 不做事项确定

## Phase 1：Milestone 0，先验证本地共享状态管道

目标：

- 不涉及 MCP
- 先验证两个独立 Python 进程能通过本地 sidecar 共享状态
- 跑通 `announce -> query active intents -> overlap detection`

完成标准：

- 两个独立进程连到同一个本地 coordinator
- 一边 announce 后，另一边能查到 `who_is_working`
- overlap 检测在双进程下可复现

## Phase 2：`mpac-mcp` 最小原型

目标：

- 做本地 `stdio` MCP Server
- 能被 Claude Code / Inspector 连上

完成标准：

- server 能启动
- tools 可发现
- tools 可手工调用

## Phase 3：接入现有 MPAC 内核

目标：

- tools 背后真正接到本地 sidecar `MPACServer`
- 可以 begin task、check overlap、submit change

完成标准：

- 至少 3 个核心 tools 跑通
- 可在本地 repo 中验证 overlap 和 stale state

## Phase 4：双 agent demo

目标：

- 一个 Cursor + 一个 Claude Code
- 或一个 Claude Code + 一个测试 agent
- 在同一个 repo 里协作

完成标准：

- 录出一个完整 demo
- demo 中至少包含：
  - intent announce
  - overlap detection
  - yield 或 rebase

## Phase 5：shared coordinator

目标：

- 支持跨机器 / 跨人协作

完成标准：

- 可创建共享 session
- 两台机器连同一 coordinator
- 能复现同 repo 协作场景

---

## 10. 三周内的具体执行计划

## 第 1 周

### Day 1-2

- 新建 `mpac-mcp/` 目录
- 选用 Python MCP SDK
- 起一个最小可运行 server
- 只实现一个最小 tool：`who_is_working`

交付物：

- `python -m mpac_mcp.server` 可启动
- Inspector 可看到 tools 列表
- `who_is_working` 可返回固定或最小真实数据

### Day 3-5

- 不走 MCP，先做 Milestone 0
- 起本地 `MPACServer` sidecar
- 用两个独立 Python 进程连接 sidecar
- 验证 active intent 共享和 overlap 检测

交付物：

- 两个进程通过 sidecar 共享状态
- 证明“状态权威在 sidecar”这条路线可行

### Day 6-7

- 让 `mpac-mcp` 真正连到本地 sidecar
- 把 `who_is_working` 从假数据换成真实 coordinator 数据
- 打通 MCP -> sidecar 的完整链路

交付物：

- 一个最小端到端闭环：Claude/Inspector -> MCP -> sidecar -> coordinator

## 第 2 周

### Day 8-10

- 实现 `begin_task`
- 实现 `check_overlap`
- 设计标准返回字段，压缩协议术语

交付物：

- 本地单机演示可看到 active intents
- 可返回 overlap 结果
- tool 输出更接近产品接口

### Day 11-14

- 实现 `submit_change`
- 明确 `submit_change` 只做单次尝试
- 返回 `status/current_state_ref/conflicting_files`
- 实现 `yield_task`

交付物：

- 同 repo 的两个任务能出现冲突
- stale 时能明确告诉 agent 刷新什么
- 至少一种冲突处理链路跑通

## 第 3 周

### Day 15-17

- 接 Claude Code
- 写最小 `.mcp.json` 配置
- 做真实对话式测试

交付物：

- Claude Code 能调用 `mpac-mcp`
- 可自然触发 tool use

### Day 18-19

- 打磨 tool 参数、返回格式和错误语义
- 增加用户友好提示
- 处理 stdio / sidecar 启动边界情况

交付物：

- 返回值更像产品接口，而不是协议 dump

### Day 20-21

- 准备 demo repo
- 录 demo 视频
- 写简短安装说明

交付物：

- 一个可展示的视频
- 一份 quickstart

---

## 11. 测试策略

很多人会误以为“测试 MCP Server 就必须立刻用 GPT/Claude”。不是。

建议分三层测试：

### 11.1 第 1 层：能力测试

直接测试 Python 逻辑，不经过任何 LLM。

测试内容：

- 两个独立进程是否真的通过 sidecar 共享状态
- begin_task 是否成功创建 intent
- who_is_working 是否正确返回 active intents
- check_overlap 是否正确发现 scope overlap
- submit_change 是否正确返回 stale / success

### 11.2 第 2 层：MCP 协议测试

用 MCP Inspector 测 server。

测试内容：

- server 能否启动
- tools 是否可发现
- tools 是否可调用
- 输入输出是否符合预期

### 11.3 第 3 层：真实客户端测试

接入 Claude Code 或 Cursor。

测试内容：

- 宿主 agent 是否能自然调用 tools
- 工具命名和参数是否容易触发
- 多轮任务里是否真的降低撞车

---

## 12. 推荐的第一版测试顺序

建议按下面顺序走：

1. 先做 Milestone 0：双进程 + 本地 sidecar
2. `mpac-mcp` 单元测试
3. MCP Inspector 手工调用
4. Claude Code 本地接入
5. 双 agent 协作 demo
6. 再考虑 Cursor / VS Code / Copilot

不要一开始就追求：

- 多客户端兼容
- 多人远程协作
- SaaS 化部署

先把最小闭环打通。

---

## 13. 需要提前想清楚的设计问题

这些问题不一定现在全部做，但必须在设计时有明确方向。

### 13.1 session 是谁创建的

选项：

- MCP server 自己默认创建一个本地 session
- 用户手工创建 session
- 后续接 dashboard 创建 session

第一版建议：

- 默认自动创建本地 session

### 13.2 scope 谁来指定

选项：

- 用户手工传 `files`
- agent 自己推断
- 两者结合

第一版建议：

- 用户/agent 传 `files`
- 保持简单明确

### 13.2.1 repo context 从哪来

第一版建议采用下面的优先级：

1. `MPAC_WORKSPACE_DIR` 环境变量
2. 当前工作目录向上查找 `.git`，找到 git root 就用 git root
3. 如果找不到 `.git`，退回当前工作目录

这样大多数 coding 场景下不用额外配置，也保留了显式 override 的能力。

### 13.3 tool 返回多少协议细节

第一版建议：

- 返回产品化字段
- 不直接返回整包 message envelope，除非 debug 模式

### 13.4 rebase 谁来处理

第一版建议：

- 第一版先返回 “stale，需要重读后重试”
- `submit_change` 返回里明确给出：
  - `current_state_ref`
  - `conflicting_files`
  - `message`
- 自动 rebase 可以放在后续增强

---

## 14. 建议的仓库组织方式

建议在当前仓库中新增一个目录，而不是把 MCP 逻辑硬塞进现有 `mpac-package`。

建议结构：

```text
mpac-package/                 # 现有核心 runtime，继续保持
mpac-mcp/                     # 新增 MCP 适配层
  pyproject.toml
  README.md
  src/
    mpac_mcp/
      __init__.py
      server.py              # MCP server 入口
      tools.py               # 工具定义
      coordinator_bridge.py  # MCP tool -> local sidecar / MPAC runtime 映射
      models.py              # 返回给 MCP 的轻量数据模型
  tests/
    test_tools.py
    test_coordinator_bridge.py
```

原则：

- `mpac-package` 不负责 MCP
- `mpac-mcp` 不重复实现协议内核
- 两者边界清晰

---

## 15. 对外叙事建议

### 15.1 不建议的讲法

- “我们实现了一个 21-message protocol”
- “这是一个多主体协调语义框架”
- “它 complement MCP”

这些可以讲，但不是第一句话。

### 15.2 建议的讲法

第一句话：

> Stop your coding agents from stepping on each other.

第二句话：

> MPAC is an MCP server that coordinates multiple AI agents working on the same repo.

第三句话：

> The first use case is multi-agent collaboration on the same repository.

---

## 16. 近期最值得追求的里程碑

不是论文上“最完整”的里程碑，而是对外最有传播力的里程碑：

### Milestone 0

两个独立 Python 进程通过本地 coordinator sidecar 共享状态，不涉及 MCP。

这是 v0 的技术前提。如果这一步没通，MCP 层做得再漂亮也只是空壳。

### Milestone A

`mpac-mcp` 能在本地启动，并被 MCP Inspector 发现和调用

### Milestone B

Claude Code 能调用 `begin_task` / `check_overlap` / `submit_change`

### Milestone C

一个双 agent demo：

- agent A 要改 `auth.py`
- agent B 也要改 `auth.py`
- 先发现 overlap
- 然后 yield、rebase 或 escalate

### Milestone D

把这个 demo 录成视频并公开

如果这些做到了，产品方向就站住了。

---

## 17. 最终建议

下一步最值得做的不是再扩一版协议，也不是直接做大产品，而是：

**做一个面向 AI 协作编程场景的 `mpac-mcp`。**

执行原则：

- 先本地
- 先单机
- 先高层工具
- 先 demo
- 再 shared coordinator
- 最后再 dashboard / hosted product

一句话路线图：

> `mpac` 负责能力本体，`mpac-mcp` 负责生态接入，协作编程负责产品价值。
