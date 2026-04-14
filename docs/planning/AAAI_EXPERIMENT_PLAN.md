# AAAI 2027 投稿方案：实验设计 + 投稿要求 + 产品方向

---

## 一、Research Question + 理论框架

### 1.1 Research Question

> 在多个 LLM-based agent 并发操作共享资源时，基于 intent declaration + scope overlap detection + optimistic concurrency control 的轻量协调协议，能否在保证安全性（冲突全检测、无丢失更新）的前提下，实现高效的多 agent 协作？

### 1.2 形式化模型

将 MPAC 建模为一个 **并发资源访问协调系统** $(N, M, \mathcal{I}, \mathcal{C})$：

- $N$ 个 agent $\{a_1, a_2, ..., a_N\}$，各自独立运行
- $M$ 个共享资源 $\{r_1, r_2, ..., r_M\}$，每个资源有 state reference $s_j$
- 每个 agent 在操作前声明 **intent** $I_i = (a_i, S_i, obj_i)$，其中 $S_i \subseteq \{r_1, ..., r_M\}$ 是 scope（目标资源子集）
- Coordinator 维护 **conflict graph** $G = (V, E)$，其中 $V = \{I_1, ..., I_N\}$，$(I_i, I_j) \in E \iff S_i \cap S_j \neq \emptyset$

### 1.3 三个核心理论性质

#### 性质 1: Conflict Detection Completeness（冲突检测完备性）

$$\forall I_i, I_j \in \mathcal{I}: S_i \cap S_j \neq \emptyset \implies (I_i, I_j) \in E$$

**含义**：任何两个 scope 有交集的 intent，coordinator 一定会检测到并生成 CONFLICT_REPORT。没有漏报。

**理论基础**：coordinator 的 `_detect_scope_overlaps()` 对每个新 intent 做穷举比较（O(N) 对当前所有 active intent），`scope_overlap()` 对 file_set 做集合交集判定。可以通过证明算法的完备性来建立这个性质。

#### 性质 2: No Lost Updates（无丢失更新）

$$\forall op_i, op_j \text{ targeting same resource } r: \text{state\_ref}_{before}(op_j) \neq s_r^{current} \implies op_j \text{ is REJECTED}$$

**含义**：如果一个 agent 基于过期的 state reference 提交修改，提交会被拒绝（STALE_STATE_REF）。这保证了：
- 每个成功提交都基于最新的资源状态
- 不会发生"覆盖别人的修改"
- 冲突通过 rebase（重新读取 + 重新生成）解决，而不是静默丢失

**理论基础**：等价于 **乐观并发控制（OCC）** 的 validation phase。与数据库 MVCC 的 write-write conflict detection 同构。

#### 性质 3: Bounded Resolution（有界解决）

$$\forall c \in \mathcal{C}: \exists T_{max} \text{ s.t. } c \text{ is resolved or escalated within } T_{max}$$

**含义**：任何冲突不会无限期悬而未决。通过以下机制保证：
- `resolution_timeout_sec`（默认 300s）后自动 escalate 到 arbiter
- 无 arbiter 可用时 scope frozen，阻止新 intent 进入冲突区域
- Agent 不可用时 intent 自动 suspend，可被其他 agent claim

**理论基础**：类似分布式系统中的 **failure detector + escalation chain**。每个超时都是一个 progress guarantee。

### 1.4 与已有理论的关系

| MPAC 概念 | 分布式系统对应 | 区别 |
|-----------|-------------|------|
| state_ref + OCC | MVCC / optimistic locking | MPAC 粒度是文件级而非行级 |
| intent declaration | two-phase commit 的 prepare 阶段 | MPAC 不锁资源，只声明意图 |
| scope overlap detection | conflict detection in STM | MPAC 是集合交集而非内存地址 |
| conflict escalation | failure escalation in consensus protocols | MPAC 引入人/arbiter 角色 |
| Lamport watermark | Lamport logical clock | 标准实现 |

### 1.5 论文叙事

**核心论点**：现有多 agent 系统要么没有协调（agent 互不知情，冲突在最后才发现），要么用悲观锁（一次只允许一个 agent 操作）。MPAC 提出第三条路：**先声明意图、再检测冲突、用乐观并发控制保证安全性**。这在保持高吞吐的同时，把冲突检测点从"最终结果"提前到"开始操作前"。

---

## 二、实验设计（3 组核心实验）

### 2.1 实验 1: Conflict Detection Completeness

#### 假设
MPAC 的 scope overlap 检测是完备的：对于任意 intent 集合，所有 scope 有交集的 intent 对都会被检测为冲突。

#### 方法

1. **数据生成**：随机生成 intent 集合
   - 参数空间：
     - Agent 数量 $N \in \{2, 5, 10, 20, 50\}$
     - 资源池大小 $M \in \{10, 50, 100\}$
     - 每个 intent 的 scope 大小 $|S_i| \in \{1, 3, 5, 10\}$
     - 目标重叠率 $\rho \in \{0\%, 10\%, 30\%, 50\%, 80\%, 100\%\}$
   - 每组参数跑 100 次，不同随机种子

2. **Ground truth 计算**：对每组生成的 intent，暴力计算所有 $\binom{N}{2}$ 个 intent 对的 scope 交集，得到"理论应检测到的冲突集合" $C_{truth}$

3. **MPAC 检测**：将 intent 逐个注入 coordinator，收集所有 CONFLICT_REPORT，得到"MPAC 实际检测到的冲突集合" $C_{mpac}$

4. **对比**：计算 precision = $|C_{mpac} \cap C_{truth}| / |C_{mpac}|$，recall = $|C_{mpac} \cap C_{truth}| / |C_{truth}|$

#### 指标
| 指标 | 定义 | 预期结果 |
|------|------|---------|
| Recall | 实际检测到的冲突 / 理论应检测到的冲突 | **100%**（完备性） |
| Precision | 正确检测的冲突 / MPAC 报告的冲突 | **100%**（无误报） |
| 检测延迟 | 从 intent announce 到 conflict report 的时间 | < 10ms（本地） |

#### 预期结果
- Recall = 100%，Precision = 100%（这是算法保证的，不是统计结果）
- 这一组实验的目的不是"发现 MPAC 是否完备"，而是**提供实验证据支持理论证明**
- 额外 insight：检测延迟随 N 线性增长（每次 announce 都遍历所有 active intent）

#### 论文呈现
- 一个表格：不同 (N, M, scope_size) 下的 precision/recall/latency
- 一个图：检测延迟 vs agent 数量（展示 O(N) 线性关系）
- 约占 **1 页**

---

### 2.2 实验 2: Optimistic Concurrency Safety

#### 假设
MPAC 的 state_ref 机制在并发写入下保证零丢失更新，同时吞吐量优于悲观锁。

#### 方法

3 个 baseline 对比：

| 方案 | 机制 | 实现 |
|------|------|------|
| **No Coordination** | Agent 直接覆盖文件，不检查 state_ref | 模拟"没有协调协议"的情况 |
| **Pessimistic Lock** | 一次只允许一个 agent 操作同一文件 | 用互斥锁模拟 |
| **MPAC (OCC)** | 声明 intent → 检测冲突 → 提交时验证 state_ref → stale 则 rebase | 现有实现 |

实验设置：
- $N$ 个 agent 并发修改同一个文件（`auth.py`）
- 每个 agent 做一次"读取 → 修改 → 提交"操作
- 变量：$N \in \{2, 5, 10, 20\}$
- 每组参数跑 50 次

"修改"操作：每个 agent 在文件末尾追加一行 `# Agent-{id} was here at {timestamp}`（简单但可验证）。

#### 指标
| 指标 | 定义 | 
|------|------|
| Lost Updates | 最终文件中缺少的 agent 标记数量 |
| Throughput | 所有 agent 完成的总时间（越短越好） |
| Rebase Count | STALE_STATE_REF 导致的重试次数（仅 MPAC） |
| Final State Correctness | 最终文件是否包含所有 N 个 agent 的标记 |

#### 预期结果

| | No Coordination | Pessimistic Lock | MPAC |
|---|:---:|:---:|:---:|
| Lost Updates | 多（N-1 次覆盖） | 0 | **0** |
| Throughput | 最快（但结果错误） | 最慢（串行等待） | **接近无协调** |
| Correctness | 错误 | 正确 | **正确** |

核心 insight：**MPAC 在安全性上等同于悲观锁（零丢失），在效率上接近无协调（并行执行，仅冲突时 rebase）**。

#### 论文呈现
- 一个柱状图：3 种方案 × 4 种 N 下的 lost update count
- 一个折线图：throughput vs N（3 条线对应 3 种方案）
- 约占 **1.5 页**

---

### 2.3 实验 3: Real-World MCP Integration

#### 假设
MPAC 通过 MCP Server 接入真实 AI coding agent 后，能有效减少"agent 撞车"（竞争同一文件导致的冲突和返工）。

#### 方法

使用已打通的 `mpac-mcp` + Claude Code 集成，设计 3 个真实编程子场景：

**场景 3a: 无冲突协作**
- Agent A: 实现 `auth.py` 的登录功能
- Agent B: 实现 `api.py` 的数据接口
- 预期：两人独立工作，无冲突，MPAC 开销 ≈ 2 条 intent announce + 0 conflict

**场景 3b: 竞争同一文件**
- Agent A: 重构 `auth.py` 的 token 验证
- Agent B: 修复 `auth.py` 的安全漏洞
- 预期：MPAC 提前检测到 scope overlap → 一方 yield 或双方 proceed + rebase
- 对照组：无 MPAC 时，两人同时改完才发现冲突（git merge conflict）

**场景 3c: 依赖链**
- Agent A: 先重构 `auth.py`
- Agent B: 基于 A 的新版本添加功能
- 预期：B 的 `state_ref_before` 指向 A 的提交结果，链式更新成功

**治理验证**（嵌入场景 3b）：
- 如果两个 agent 都坚持 proceed → 冲突升级到 arbiter
- 如果一方 agent 中途断开 → intent suspend → 另一方 claim 接管
- 这些在场景 3b 的多次运行中自然发生

#### 指标
| 指标 | 定义 |
|------|------|
| 冲突早期发现率 | MPAC 在 intent 阶段就检测到的冲突 / 实际存在的冲突 |
| 返工次数 | 因为冲突需要重新修改的次数 |
| 任务完成率 | 最终所有修改都被正确应用的比例 |
| 代码质量 | 最终代码是否通过语法检查 / 逻辑正确 |
| 端到端耗时 | 从所有 agent 开始到所有任务完成的总时间 |

#### 对照组设计

| | 无协调（对照） | MPAC（实验） |
|---|---|---|
| 冲突发现时机 | 提交后（git merge conflict） | 声明 intent 时 |
| 冲突解决方式 | 手动 merge | 自动 yield/rebase |
| 信息可见性 | 不知道对方在做什么 | `who_is_working` 实时可见 |

#### 论文呈现
- 一个表格：3 个子场景 × (无协调 vs MPAC) 的指标对比
- 一个时序图：展示 MPAC 协调消息在真实 coding 场景中的流动
- 约占 **1.5 页**

---

## 三、AAAI 2027 投稿要求 + 时间线

### 3.1 关键日期

| 事件 | 日期 |
|------|------|
| 摘要截止 | **2026-07-25** |
| 全文截止 | **2026-08-01** 23:59 |
| Rebuttal | 2026-10-02 至 10-08 |
| 通知 | 2026-11-03 |
| 会议 | 2027-02-16 至 02-23（蒙特利尔） |

### 3.2 格式要求

- **正文**：7 页（不含参考文献）
- **参考文献**：不限页数
- **附录/Reproducibility checklist**：不限页数，不计入正文
- **模板**：AAAI 官方 LaTeX/Word 模板
- **匿名**：提交时需匿名（去除作者信息）
- **LLM 生成文本**：禁止直接用 LLM 写论文正文，但可以作为实验分析对象

### 3.3 Track 选择建议

| Track | 适合度 | 理由 |
|-------|:---:|------|
| **Main Track** | ★★★ | 有理论性质 + 实验验证，符合 main track 要求 |
| AI Alignment | ★★ | MPAC 的 governance/arbiter 可以 frame 成 alignment |
| AI for Social Impact | ★ | 不太直接对应 |
| **WMAC Workshop**（Multi-Agent Collaboration） | ★★★ | 最精准匹配，但 workshop paper 影响力较低 |

**建议**：投 Main Track。如果被拒，改投 WMAC Workshop 作为 fallback。

### 3.4 7 页分配建议

| 章节 | 页数 | 内容 |
|------|:---:|------|
| Introduction | 1 | 问题动机 + 贡献摘要 |
| Related Work | 0.75 | 多 agent 协调、分布式并发控制、LLM agent 框架 |
| MPAC Protocol | 1.5 | 形式化模型 + 三个理论性质 |
| Experiments | 3 | 实验 1（1页）+ 实验 2（1页）+ 实验 3（1页） |
| Conclusion | 0.75 | 总结 + limitation + future work |

### 3.5 执行时间线

| 时间段 | 任务 | 交付物 |
|--------|------|--------|
| **4/14 - 4/27**（2 周） | 实验 1 + 2 代码编写和运行 | 实验数据 JSON + 图表 |
| **4/28 - 5/11**（2 周） | 实验 3（MCP 真实场景）+ Milestone C demo | 实验数据 + demo 视频 |
| **5/12 - 5/25**（2 周） | 论文初稿（Introduction + Protocol + Experiments） | LaTeX 初稿 |
| **5/26 - 6/08**（2 周） | Related Work + 理论证明细化 | 完整草稿 |
| **6/09 - 6/22**（2 周） | 导师审阅 + 修改 | 修改稿 |
| **6/23 - 7/06**（2 周） | 第二轮修改 + 润色 | 终稿草案 |
| **7/07 - 7/25**（2.5 周） | 最终打磨 + 摘要提交 | 摘要提交 |
| **7/25 - 8/01**（1 周） | 全文最终提交 | 提交完成 |

---

## 四、MCP Server 部署方案 + 产品方向

### 4.1 三种部署模式成本分析

#### 模式 A: 纯本地部署（当前 v0）

```
用户机器
  ├─ Claude Code / Cursor（MCP 客户端）
  ├─ mpac-mcp（stdio MCP server）
  └─ MPACServer sidecar（WebSocket，localhost）
```

| 项目 | 成本 |
|------|------|
| 服务器 | **$0**（全部运行在用户本机） |
| 带宽 | **$0**（纯 localhost） |
| 维护 | **$0**（用户自行 pip install） |
| 适用场景 | 单人多 agent、同一台机器上的 Cursor + Claude Code |

**限制**：不支持跨机器协作。两个人在两台机器上用，无法共享 coordinator 状态。

#### 模式 B: 自托管 Shared Coordinator

```
用户 A 机器                    用户 B 机器
  ├─ mpac-mcp (stdio)          ├─ mpac-mcp (stdio)
  └─ ws://shared-server:port ──┘
        ↓
  团队自己的服务器或 VPS
  └─ MPACServer（公网或内网 WebSocket）
```

| 项目 | 成本估算 |
|------|---------|
| VPS | $5-20/月（DigitalOcean, Hetzner, AWS Lightsail） |
| 带宽 | 极低——MPAC 消息很小（每条 < 1KB），10 人团队每天 < 10MB |
| 维护 | 团队自行管理（启动/更新/备份） |
| 适用场景 | 小团队（2-10 人）跨机器协作 |

**关键 insight**：MPAC 是轻量文本协议，不传文件内容（OP_COMMIT 广播时已剥离 file_changes），带宽几乎可以忽略。一台 $5/月的 VPS 足以支撑 50 人团队。

#### 模式 C: 云托管 SaaS

| 项目 | 成本估算 |
|------|---------|
| 基础设施 | $50-200/月（含 WebSocket 长连接 + 持久化 + 监控） |
| 开发 | 需要做认证、多租户、dashboard |
| 运营 | 持续维护 |
| 适用场景 | 大规模商业化 |

### 4.2 导师约束下的推荐方案

导师纪要明确说："采用开源模式，用户本地部署，避免服务器流量费用"。

**推荐路径**：

```
Phase 1 (现在): 纯本地（模式 A）→ 零成本，专注论文
Phase 2 (论文后): 开源自托管指南（模式 B）→ 用户自己部署，我们零成本
Phase 3 (如需): 考虑 hosted（模式 C）→ 但目前不需要
```

**核心结论**：模式 A 完全满足论文实验需求；模式 B 的文档准备好就行，不需要我们自己跑服务器。MCP Server 的部署成本问题在开源模式下**本质上不是我们的问题**——用户自己部署，我们只提供代码和文档。

### 4.3 周四会议讨论要点

#### 要汇报的

1. **Milestone B 已完成**（不是"进行中"）：
   - Claude Code 能真实调用 10 个 MCP tool
   - who_is_working / begin_task / check_overlap 全部验证通过
   - 环境已搭建（Python 3.12 venv + mcp 1.27.0 + Claude Code 2.1.104）

2. **产品形态已定义**：
   - 不是独立 app，是 MCP Server
   - 第一版只服务"AI 协作编程"场景
   - 用户安装方式：`pip install mpac-mcp` + 一行 MCP 配置

3. **部署方案**：纯本地部署，零服务器成本

#### 要讨论的

1. **论文 vs 产品的节奏**：
   - AAAI 截止 8/1，论文优先还是 demo 优先？
   - 建议：先跑实验 1-2（纯理论验证，不依赖 MCP），同时准备 Milestone C demo

2. **理论贡献的深度**：
   - 方案一：把三个性质（完备性、无丢失更新、有界解决）做成形式化证明
   - 方案二：用实验数据 + 正确性论证，不做完整形式化证明
   - 导师偏好哪种？

3. **实验 3 的规模**：
   - 最小版：2 个 agent，3 个子场景，手动运行
   - 理想版：自动化脚本，多次运行取统计值
   - 取决于人力和时间

4. **Related Work 方向**：
   - 主要对标：AutoGen、CrewAI、LangGraph（LLM agent 框架，无协调协议）
   - 理论对标：分布式数据库并发控制（OCC/MVCC）、multi-agent coordination（BDI、game theory）
   - 导师有没有特别想加的参考文献？

#### 不要在会上讨论的

- VS Code 扩展（太早）
- Hosted SaaS（不符合当前约束）
- 非代码场景（论文聚焦 coding 场景）
