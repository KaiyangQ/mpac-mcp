# MPAC v0.1.4 Developer Reference

面向实现者的技术参考文档。本文档以数据结构为中心，定义所有模块、字段、枚举值、状态机和模块间引用关系。

**约定**：R = 必填，O = 可选，C = 条件必填（取决于其他字段的值）

---

## 1. 核心数据对象

MPAC 的所有消息和状态都由以下核心数据对象组成。理解它们之间的引用关系是实现协议的基础。

### 1.1 Principal（参与者身份）

描述一个参与 session 的主体。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `principal_id` | string | R | 唯一标识，格式推荐 `{type}:{name}`，如 `agent:alice-coder-1` |
| `principal_type` | string | R | 枚举：`human` / `agent` / `service` |
| `display_name` | string | O | 人类可读名称 |
| `roles` | string[] | O | 角色列表，见 [枚举：Roles](#61-roles) |
| `capabilities` | string[] | O | 能力列表，见 [枚举：Capabilities](#62-capabilities) |

**被引用于**：Message Envelope 的 `sender` 字段、INTENT_CLAIM 的 `original_principal_id`、CONFLICT_ESCALATE 的 `escalate_to`

---

### 1.2 Message Envelope（消息信封）

所有 MPAC 消息的外层包装。每条消息无论类型都必须有这个结构。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `protocol` | string | R | 固定值 `"MPAC"` |
| `version` | string | R | 协议版本，如 `"0.1.4"` |
| `message_type` | string | R | 消息类型，见 [消息类型清单](#2-消息类型清单) |
| `message_id` | string | R | 消息唯一 ID，在系统范围内唯一 |
| `session_id` | string | R | 所属 session 的 ID → 关联 [Session](#13-session) |
| `sender` | object | R | 发送者信息，结构为 `{ principal_id, principal_type }` → 关联 [Principal](#11-principal参与者身份) |
| `ts` | string | R | RFC 3339 UTC 时间戳，如 `"2026-04-02T10:00:00Z"` |
| `payload` | object | R | 消息体，结构因 `message_type` 不同而不同 |
| `watermark` | Watermark | O | 因果上下文，见 [Watermark](#14-watermark因果水位) |
| `in_reply_to` | string | O | 回复的目标 `message_id` |
| `trace_id` | string | O | 分布式追踪 ID |
| `policy_ref` | string | O | 策略引用 |
| `signature` | string | O | 消息签名（Authenticated/Verified profile 下使用） |
| `extensions` | object | O | 扩展字段，格式 `{ "vendor.name": { ... } }` |

**关键约束**：
- `OP_COMMIT`、`CONFLICT_REPORT`、`RESOLUTION` 的 `watermark` 为 **MUST**（虽然信封层面它是 optional 字段，但这三种消息类型强制要求）
- `message_id` 在 Authenticated profile 下用于重放检测，coordinator 会拒绝重复值

---

### 1.3 Session（会话）

Session 不是一条消息，而是一个状态容器，通过 session metadata 配置。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | R | 唯一标识 |
| `protocol_version` | string | R | MPAC 版本 |
| `security_profile` | string | R | 枚举：`open` / `authenticated` / `verified` |
| `compliance_profile` | string | O | 枚举：`core` / `governance` / `semantic` |
| `governance_policy` | object | O | 治理配置，见 [Governance Policy](#15-governance-policy治理策略) |
| `liveness_policy` | object | O | 活性配置，见 [Liveness Policy](#16-liveness-policy活性策略) |
| `resource_registry` | object | O | 资源注册表，见 [Resource Registry](#17-resource-registry资源注册表) |
| `state_ref_format` | string | O | state_ref 的格式声明，如 `"sha256"` / `"git_hash"` / `"monotonic_version"` |

**注意**：Session 不在消息中直接传输。它通过 `SESSION_INFO` 消息的 payload 暴露给参与者。

---

### 1.4 Watermark（因果水位）

表达"我发送这条消息时，已经知道了哪些前置状态"。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `kind` | string | R | 枚举：`lamport_clock`（MUST 支持） / `vector_clock` / `causal_frontier` / `opaque` |
| `value` | any | R | kind 决定类型：`lamport_clock` → integer，`vector_clock` → `{ participant: clock }` 对象，其他 → string |
| `lamport_value` | integer | O | 当 kind 不是 `lamport_clock` 时 SHOULD 提供此字段作为降级比较值 |

**比较语义**（`lamport_clock`）：
- `a < b` → a happened-before b
- `a == b` 或不可比 → 并发或不确定

**被引用于**：Message Envelope 的 `watermark` 字段、CONFLICT_REPORT 的 `based_on_watermark` 字段

---

### 1.5 Governance Policy（治理策略）

Session 级配置，控制冲突解决和权限行为。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `require_arbiter` | boolean | `false` | Governance profile 下 MUST 为 true |
| `resolution_timeout_sec` | integer | `300` | 冲突未解决超时秒数，0 = 禁用 |
| `timeout_action` | string | `"escalate_then_freeze"` | 超时后动作 |
| `frozen_scope_behavior` | string | `"reject_writes_and_intents"` | frozen scope 下的拒绝策略 |
| `frozen_scope_timeout_sec` | integer | `1800` | frozen scope 兜底超时秒数，0 = 禁用 |
| `intent_expiry_grace_sec` | integer | `30` | Intent 过期后，关联 proposal 被自动拒绝前的宽限期 |

---

### 1.6 Liveness Policy（活性策略）

Session 级配置，控制心跳和不可用检测。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `heartbeat_interval_sec` | integer | `30` | 心跳发送间隔 |
| `unavailability_timeout_sec` | integer | `90` | 连续无消息超过此时间判定不可用 |
| `orphaned_intent_action` | string | `"suspend"` | 不可用时 intent 的处理方式 |
| `orphaned_proposal_action` | string | `"abandon"` | 不可用时 proposal 的处理方式 |
| `intent_claim_approval` | string | `"governance"` | INTENT_CLAIM 的审批方式 |
| `intent_claim_grace_period_sec` | integer | `30` | Core profile 下 claim 自动审批前的宽限期 |

---

### 1.7 Resource Registry（资源注册表）

可选的 session 级配置。将不同 scope kind 的表示映射到统一的 canonical URI。

```
resource_registry.mappings[] → 每项包含：
  canonical_uri: string        → 标准资源 URI
  aliases[]:                   → 别名列表
    kind: string               → scope kind
    value: string              → 该 kind 下的资源标识
```

**用途**：当 session 中的参与者使用不同 scope kind（如一方用 `file_set`，另一方用 `entity_set`）时，registry 让 coordinator 能判断它们是否指向同一资源。

---

### 1.8 Scope（作用域）

描述一个 intent 或 operation 的目标资源集合。是冲突检测的核心输入。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `kind` | string | R | 枚举：`file_set` / `resource_path` / `task_set` / `query` / `entity_set` / `custom` |
| `resources` | string[] | C | kind = `file_set` 时必填。文件路径数组 |
| `pattern` | string | C | kind = `resource_path` 时必填。glob 模式 |
| `task_ids` | string[] | C | kind = `task_set` 时必填。任务 ID 数组 |
| `expression` | string | C | kind = `query` 时必填。查询表达式 |
| `language` | string | C | kind = `query` 时必填。查询语言标识 |
| `entities` | string[] | C | kind = `entity_set` 时必填。实体名称数组 |
| `canonical_uris` | string[] | O | 标准资源 URI。Authenticated/Verified profile 跨 kind session 下为 MUST |
| `extensions` | object | O | 实现特定扩展 |

**Overlap 判定规则**：

| kind | 算法 | 级别 |
|------|------|------|
| `file_set` | 规范化路径（去 `./`、折叠 `//`、去尾 `/`）后字符串精确匹配，取集合交集 | MUST |
| `entity_set` | 字符串精确匹配，取集合交集 | MUST |
| `task_set` | 字符串精确匹配，取集合交集 | MUST |
| `resource_path` | 最小支持 `*` 和 `**` glob 匹配 | SHOULD |
| `query` / `custom` | 保守假设：可能重叠 | 默认行为 |
| 跨 kind | 通过 `canonical_uris` 或 resource registry 判定；均不可用时保守假设重叠 | MUST NOT 仅凭 kind 不同就假设不重叠 |

**被引用于**：INTENT_ANNOUNCE / INTENT_UPDATE / INTENT_CLAIM 的 `scope` 字段

---

### 1.9 Basis（冲突检测依据）

描述冲突是如何被检测到的。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `kind` | string | R | 枚举：`rule` / `heuristic` / `model_inference` / `semantic_match` / `human_report` |
| `rule_id` | string | O | kind = `rule` 时的规则标识 |
| `matcher` | string | O | kind = `semantic_match` 时的匹配器标识 |
| `match_type` | string | O | kind = `semantic_match` 时的匹配结果：`contradictory` / `equivalent` / `uncertain` |
| `confidence` | number | O | 0.0–1.0 之间的置信度。低于阈值（默认 0.7）时应视为 `uncertain` |
| `matched_pair` | object | O | `{ left: { source_intent_id, content }, right: { source_intent_id, content } }` |
| `explanation` | string | O | 人类可读的匹配解释 |

**被引用于**：CONFLICT_REPORT 的 `basis` 字段

---

### 1.10 Outcome（解决结果）

描述 RESOLUTION 的具体决策结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `accepted` | string[] | O | 被接受的 intent/operation ID 列表 |
| `rejected` | string[] | O | 被拒绝的 intent/operation ID 列表 |
| `merged` | string[] | O | 被合并的 intent/operation ID 列表 |
| `rollback` | string | C | 当 rejected 列表中存在 COMMITTED 状态的 operation 时 **MUST 填写**。值为补偿 OP_COMMIT 的引用或 `"not_required"` |

**被引用于**：RESOLUTION 的 `outcome` 字段

---

## 2. 消息类型清单

MPAC v0.1.4 共 17 种消息类型，分布在 4 个协议层中。

| 层 | 消息类型 | 方向 | Core Profile | Governance Profile |
|----|---------|------|-------------|-------------------|
| Session | `HELLO` | 参与者 → Coordinator | ✅ | ✅ |
| Session | `SESSION_INFO` | Coordinator → 参与者 | ✅ | ✅ |
| Session | `HEARTBEAT` | 参与者 → All | ✅ | ✅ |
| Session | `GOODBYE` | 参与者 → All | ✅ | ✅ |
| Intent | `INTENT_ANNOUNCE` | 参与者 → All | ✅ | ✅ |
| Intent | `INTENT_UPDATE` | 参与者 → All | | ✅ |
| Intent | `INTENT_WITHDRAW` | 参与者 → All | | ✅ |
| Intent | `INTENT_CLAIM` | 参与者 → Coordinator | | ✅ |
| Operation | `OP_PROPOSE` | 参与者 → Coordinator | | ✅ |
| Operation | `OP_COMMIT` | 参与者 → All | ✅ | ✅ |
| Operation | `OP_REJECT` | Reviewer/Coordinator → 参与者 | | ✅ |
| Operation | `OP_SUPERSEDE` | 参与者 → All | | ✅ |
| Conflict | `CONFLICT_REPORT` | 检测者 → All | ✅ | ✅ |
| Conflict | `CONFLICT_ACK` | 参与者 → All | | ✅ |
| Conflict | `CONFLICT_ESCALATE` | 参与者 → Arbiter | | ✅ |
| Governance | `RESOLUTION` | Arbiter/Owner → All | ✅ | ✅ |
| Error | `PROTOCOL_ERROR` | Any → Any | ✅ | ✅ |

---

## 3. 消息 Payload 详细定义

### 3.1 HELLO

加入 session，声明身份和能力。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `display_name` | string | R | 人类可读名称 | |
| `roles` | string[] | R | 请求的角色列表 | → [Roles 枚举](#61-roles) |
| `capabilities` | string[] | R | 支持的能力列表 | → [Capabilities 枚举](#62-capabilities) |
| `implementation` | object | O | `{ name: string, version: string }` | |

**后续**：Coordinator 收到后 MUST 回复 SESSION_INFO。

---

### 3.2 SESSION_INFO

Coordinator 对 HELLO 的响应，携带 session 配置和兼容性检查结果。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `session_id` | string | R | Session ID | → [Session](#13-session) |
| `protocol_version` | string | R | 协议版本 | |
| `security_profile` | string | R | 安全级别 | → [Security Profile 枚举](#63-security-profile) |
| `compliance_profile` | string | R | 合规级别 | → [Compliance Profile 枚举](#64-compliance-profile) |
| `watermark_kind` | string | R | 基线 watermark 类型 | → [Watermark](#14-watermark因果水位) |
| `state_ref_format` | string | R | state_ref 格式 | → OP_COMMIT 的 `state_ref_before/after` |
| `governance_policy` | object | O | 治理配置 | → [Governance Policy](#15-governance-policy治理策略) |
| `liveness_policy` | object | O | 活性配置 | → [Liveness Policy](#16-liveness-policy活性策略) |
| `participant_count` | integer | O | 当前参与者数 | |
| `granted_roles` | string[] | R | 实际授予的角色（可能与 HELLO 请求不同） | → [Roles 枚举](#61-roles) |
| `compatibility_errors` | string[] | O | 检测到的不兼容项列表 | |

---

### 3.3 HEARTBEAT

维持活性，发布状态摘要。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `status` | string | R | 枚举：`idle` / `working` / `blocked` / `awaiting_review` / `offline` | |
| `active_intent_id` | string | O | 当前活跃的 intent ID | → INTENT_ANNOUNCE 的 `intent_id` |
| `summary` | string | O | 人类可读的活动摘要 | |

**频率**：SHOULD 每 30 秒发送一次。连续 90 秒无消息 → 判定不可用。

---

### 3.4 GOODBYE

离开 session。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `reason` | string | R | 枚举：`user_exit` / `session_complete` / `error` / `timeout` | |
| `active_intents` | string[] | O | 离开时仍活跃的 intent ID 列表 | → INTENT_ANNOUNCE 的 `intent_id` |
| `intent_disposition` | string | O | 枚举：`withdraw` / `transfer` / `expire`。默认 `withdraw` | |

---

### 3.5 INTENT_ANNOUNCE

声明计划执行的工作。**Governance Profile 下 MUST 在 OP_PROPOSE/OP_COMMIT 之前发送。**

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `intent_id` | string | R | 唯一标识 | 被 OP_PROPOSE/OP_COMMIT/CONFLICT_REPORT 引用 |
| `objective` | string | R | 人类可读的目标描述 | |
| `scope` | Scope | R | 目标资源集合 | → [Scope](#18-scope作用域) |
| `assumptions` | string[] | O | 重要的隐含依赖。默认 `[]` | 被 semantic_match 用于矛盾检测 |
| `priority` | string | O | 枚举：`low` / `normal` / `high` / `critical`。默认 `normal` | |
| `ttl_sec` | integer | O | 墙钟秒数，由 coordinator 基于 received_at 判定过期。默认 `300` | |
| `parent_intent_id` | string | O | 父级 intent ID（层级关系） | → 另一个 intent 的 `intent_id` |
| `supersedes_intent_id` | string | O | 被本 intent 替代的 intent ID | → 另一个 intent 的 `intent_id` |

---

### 3.6 INTENT_UPDATE

修改活跃 intent 的属性。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `intent_id` | string | R | 要更新的 intent ID | → INTENT_ANNOUNCE 的 `intent_id` |
| `objective` | string | O | 新目标 | |
| `scope` | Scope | O | 新作用域 | → [Scope](#18-scope作用域) |
| `assumptions` | string[] | O | 新假设列表 | |
| `ttl_sec` | integer | O | 新 TTL | |

**约束**：除 `intent_id` 外至少填一个字段。

---

### 3.7 INTENT_WITHDRAW

取消活跃 intent。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `intent_id` | string | R | 要取消的 intent ID | → INTENT_ANNOUNCE 的 `intent_id` |
| `reason` | string | O | 取消原因 | |

**副作用**：触发 Intent Expiry Cascade（Section 15.7），关联的 pending proposal 被自动 reject。

---

### 3.8 INTENT_CLAIM

认领不可用参与者的 suspended intent。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `claim_id` | string | R | Claim 的唯一标识 | |
| `original_intent_id` | string | R | 被认领的 suspended intent | → 必须是 SUSPENDED 状态的 intent |
| `original_principal_id` | string | R | 原 intent 所有者的 principal ID | → [Principal](#11-principal参与者身份) |
| `new_intent_id` | string | R | 新创建的 intent ID | |
| `objective` | string | R | 新 intent 的目标 | |
| `scope` | Scope | R | 新 scope（必须等于或窄于原 scope） | → [Scope](#18-scope作用域) |
| `justification` | string | O | 认领理由 | |

**竞态规则**：first-claim-wins，后续 claim 收到 `CLAIM_CONFLICT` 错误。原参与者在审批前重连 → claim 自动撤回。

---

### 3.9 OP_PROPOSE

提议一个待审批的变更（Governance Profile 下使用）。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `op_id` | string | R | 操作唯一标识 | 被 OP_COMMIT/OP_REJECT/CONFLICT_REPORT 引用 |
| `intent_id` | string | O | 关联的 intent ID | → INTENT_ANNOUNCE 的 `intent_id` |
| `target` | string | R | 被修改的资源 | |
| `op_kind` | string | R | 变更类型，如 `replace` / `insert` / `delete` / `patch` | |
| `change_ref` | string | O | 变更内容的引用（如 diff blob 的 hash） | |
| `summary` | string | O | 人类可读摘要 | |

---

### 3.10 OP_COMMIT

声明变更已提交到 shared state。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `op_id` | string | R | 操作唯一标识 | |
| `intent_id` | string | O (Governance: R) | 关联的 intent ID | → INTENT_ANNOUNCE 的 `intent_id` |
| `target` | string | R | 被修改的资源 | |
| `op_kind` | string | R | 变更类型 | |
| `state_ref_before` | string | R | 变更前的状态引用（格式由 session 的 `state_ref_format` 决定） | |
| `state_ref_after` | string | R | 变更后的状态引用 | |
| `change_ref` | string | O | 变更内容的引用 | |
| `summary` | string | O | 人类可读摘要 | |

**关键逻辑**：接收方如果本地状态与 `state_ref_before` 不匹配，SHOULD 标记为 `causally_unverifiable`，不基于此操作做冲突判断。

---

### 3.11 OP_REJECT

拒绝一个 proposed 操作。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `op_id` | string | R | 被拒绝的操作 ID | → OP_PROPOSE 的 `op_id` |
| `reason` | string | R | 拒绝原因（如 `policy_violation` / `intent_terminated` / `participant_unavailable` / `frozen_scope_timeout`） | |

---

### 3.12 OP_SUPERSEDE

用新操作替代已提交的旧操作。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `op_id` | string | R | 新操作 ID | |
| `supersedes_op_id` | string | R | 被替代的操作 ID | → 必须是 COMMITTED 状态的操作 |
| `intent_id` | string | O | 关联的 intent ID | → INTENT_ANNOUNCE 的 `intent_id` |
| `target` | string | R | 目标资源 | |
| `reason` | string | O | 替代原因 | |

---

### 3.13 CONFLICT_REPORT

发布一个结构化的冲突判定。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `conflict_id` | string | R | 冲突唯一标识 | 被 CONFLICT_ACK/ESCALATE/RESOLUTION 引用 |
| `related_intents` | string[] | O | 相关 intent ID 列表。默认 `[]` | → INTENT_ANNOUNCE 的 `intent_id` |
| `related_ops` | string[] | O | 相关 operation ID 列表。默认 `[]` | → OP_PROPOSE/OP_COMMIT 的 `op_id` |
| `category` | string | R | 冲突类别 | → [Conflict Category 枚举](#65-conflict-category) |
| `severity` | string | R | 严重程度 | → [Severity 枚举](#66-severity) |
| `basis` | Basis | R | 检测依据 | → [Basis](#19-basis冲突检测依据) |
| `based_on_watermark` | Watermark | R | 判定时的因果状态 | → [Watermark](#14-watermark因果水位) |
| `description` | string | R | 人类可读描述 | |
| `suggested_action` | string | O | 建议的下一步 | |

**约束**：`related_intents` 和 `related_ops` 至少有一个非空。

---

### 3.14 CONFLICT_ACK

确认收到冲突报告。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `conflict_id` | string | R | 被确认的冲突 ID | → CONFLICT_REPORT 的 `conflict_id` |
| `ack_type` | string | R | 枚举：`seen` / `accepted` / `disputed` | |

---

### 3.15 CONFLICT_ESCALATE

将冲突升级给更高权限的裁决者。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `conflict_id` | string | R | 被升级的冲突 ID | → CONFLICT_REPORT 的 `conflict_id` |
| `escalate_to` | string | R | 升级目标的 principal ID | → [Principal](#11-principal参与者身份)，通常是 owner/arbiter |
| `reason` | string | R | 升级原因 | |
| `context` | string | O | 给裁决者的附加上下文 | |

---

### 3.16 RESOLUTION

对冲突做出裁决。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `resolution_id` | string | R | 裁决唯一标识 | |
| `conflict_id` | string | R | 被裁决的冲突 ID | → CONFLICT_REPORT 的 `conflict_id` |
| `decision` | string | R | 裁决类型 | → [Decision 枚举](#67-decision) |
| `outcome` | Outcome | O | 结构化结果 | → [Outcome](#110-outcome解决结果) |
| `rationale` | string | R | 人类可读的裁决理由 | |

**信封要求**：MUST 包含 `watermark`。Authenticated/Verified profile 下缺失 watermark 的 RESOLUTION 会被拒绝。

---

### 3.17 PROTOCOL_ERROR

信令协议级别错误。

| 字段 | 类型 | 必填 | 说明 | 关联 |
|------|------|------|------|------|
| `error_code` | string | R | 错误码 | → [Error Code 枚举](#68-error-code) |
| `refers_to` | string | O | 触发错误的消息的 `message_id` | → Message Envelope 的 `message_id` |
| `description` | string | R | 人类可读的错误描述 | |

---

## 4. 实体关系图

下图展示所有核心实体之间的引用关系。箭头表示"引用/关联"。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              SESSION                                     │
│  session_id, security_profile, governance_policy, liveness_policy        │
│                                                                          │
│  ┌──────────┐   SESSION_INFO    ┌─────────────┐                        │
│  │Coordinator│ ────────────────→ │ Participant  │                        │
│  │ (service) │ ←──── HELLO ──── │ (Principal)  │                        │
│  └─────┬─────┘                  └──────┬───────┘                        │
│        │                               │                                 │
└────────┼───────────────────────────────┼─────────────────────────────────┘
         │ 管理/执行                     │ 发送
         ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           INTENT LAYER                                   │
│                                                                          │
│  INTENT_ANNOUNCE ──┐                                                    │
│    intent_id ◄─────┼──── 被以下实体引用:                                │
│    scope ───────────┼──→ Scope 对象                                     │
│    ttl_sec          │    (冲突检测的输入)                                │
│                     │                                                    │
│  INTENT_UPDATE ─────┤ intent_id → 引用 INTENT_ANNOUNCE                  │
│  INTENT_WITHDRAW ───┤ intent_id → 引用 INTENT_ANNOUNCE                  │
│  INTENT_CLAIM ──────┘ original_intent_id → 引用 SUSPENDED 的 intent     │
│                       new_intent_id → 创建新 intent                     │
│                       original_principal_id → 引用 Principal            │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │ intent_id
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         OPERATION LAYER                                  │
│                                                                          │
│  OP_PROPOSE ────┐                                                       │
│    op_id ◄──────┼──── 被以下实体引用:                                   │
│    intent_id ───┼──→ INTENT_ANNOUNCE (可选, Governance 下必填)          │
│    target       │                                                        │
│                 │                                                        │
│  OP_COMMIT ─────┤ op_id, intent_id → 同上                              │
│    state_ref_before ──→ 变更前状态 (格式由 session.state_ref_format)    │
│    state_ref_after ───→ 变更后状态                                      │
│                 │                                                        │
│  OP_REJECT ─────┤ op_id → 引用 OP_PROPOSE                              │
│  OP_SUPERSEDE ──┘ supersedes_op_id → 引用 COMMITTED 的操作              │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │ op_id, intent_id
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CONFLICT LAYER                                   │
│                                                                          │
│  CONFLICT_REPORT ──┐                                                    │
│    conflict_id ◄───┼──── 被以下实体引用:                                │
│    related_intents ┼──→ INTENT_ANNOUNCE 的 intent_id (数组)             │
│    related_ops ────┼──→ OP_PROPOSE/OP_COMMIT 的 op_id (数组)            │
│    basis ──────────┼──→ Basis 对象                                      │
│    based_on_watermark → Watermark 对象                                  │
│                    │                                                     │
│  CONFLICT_ACK ─────┤ conflict_id → 引用 CONFLICT_REPORT                │
│  CONFLICT_ESCALATE ┤ conflict_id → 引用 CONFLICT_REPORT                │
│                    │ escalate_to → 引用 Principal                       │
└────────────────────┼─────────────────────────────────────────────────────┘
                     │ conflict_id
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        GOVERNANCE LAYER                                  │
│                                                                          │
│  RESOLUTION                                                              │
│    resolution_id                                                         │
│    conflict_id ────→ CONFLICT_REPORT 的 conflict_id                     │
│    outcome ────────→ Outcome 对象                                       │
│      accepted[] ──→ intent_id / op_id                                   │
│      rejected[] ──→ intent_id / op_id                                   │
│      merged[] ────→ intent_id / op_id                                   │
│      rollback ────→ 补偿 OP_COMMIT 引用 或 "not_required"              │
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.1 关键引用链总结

| 源字段 | → 目标字段 | 关系说明 |
|--------|-----------|---------|
| OP_PROPOSE.`intent_id` | → INTENT_ANNOUNCE.`intent_id` | 操作属于哪个 intent |
| OP_COMMIT.`intent_id` | → INTENT_ANNOUNCE.`intent_id` | 同上 |
| OP_REJECT.`op_id` | → OP_PROPOSE.`op_id` | 拒绝哪个提案 |
| OP_SUPERSEDE.`supersedes_op_id` | → OP_COMMIT.`op_id` | 替代哪个已提交操作 |
| CONFLICT_REPORT.`related_intents[]` | → INTENT_ANNOUNCE.`intent_id` | 冲突涉及哪些 intent |
| CONFLICT_REPORT.`related_ops[]` | → OP_PROPOSE/OP_COMMIT.`op_id` | 冲突涉及哪些操作 |
| CONFLICT_ACK.`conflict_id` | → CONFLICT_REPORT.`conflict_id` | 确认哪个冲突 |
| CONFLICT_ESCALATE.`conflict_id` | → CONFLICT_REPORT.`conflict_id` | 升级哪个冲突 |
| CONFLICT_ESCALATE.`escalate_to` | → Principal.`principal_id` | 升级给谁 |
| RESOLUTION.`conflict_id` | → CONFLICT_REPORT.`conflict_id` | 裁决哪个冲突 |
| RESOLUTION.`outcome.accepted/rejected[]` | → `intent_id` 或 `op_id` | 裁决结果涉及的实体 |
| INTENT_CLAIM.`original_intent_id` | → INTENT_ANNOUNCE.`intent_id` | 认领哪个 suspended intent |
| INTENT_CLAIM.`original_principal_id` | → Principal.`principal_id` | 原 intent 所有者 |
| INTENT_ANNOUNCE.`parent_intent_id` | → INTENT_ANNOUNCE.`intent_id` | Intent 层级关系 |
| INTENT_ANNOUNCE.`supersedes_intent_id` | → INTENT_ANNOUNCE.`intent_id` | Intent 替代关系 |
| HEARTBEAT.`active_intent_id` | → INTENT_ANNOUNCE.`intent_id` | 当前工作的 intent |
| GOODBYE.`active_intents[]` | → INTENT_ANNOUNCE.`intent_id` | 离开时的活跃 intent |
| Message Envelope.`in_reply_to` | → Message Envelope.`message_id` | 消息回复链 |

---

## 5. 状态机

### 5.1 Intent 状态机

```
           ┌──────────────────────────────────────────────┐
           │                                              │
   ┌───────▼──────┐   INTENT_ANNOUNCE   ┌──────────────┐ │
   │    DRAFT     │ ──────────────────→ │   ANNOUNCED   │ │
   │  (概念状态,   │                     │               │ │
   │   不上线)     │                     └───────┬───────┘ │
   └──────────────┘                             │         │
                                                ▼         │
                                        ┌──────────────┐  │
                             ┌─────────│    ACTIVE     │  │
                             │          └───┬──┬──┬────┘  │
                             │              │  │  │       │
              INTENT_WITHDRAW│    TTL 过期  │  │  │ SUPERSEDED
                             │              │  │  │       │
                             ▼              ▼  │  ▼       │
                     ┌──────────┐  ┌────────┐ │ ┌──────────────┐
                     │WITHDRAWN │  │EXPIRED │ │ │ SUPERSEDED   │
                     └──────────┘  └────────┘ │ └──────────────┘
                                              │
                              参与者不可用     │
                                              ▼
                                      ┌──────────────┐
                           ┌─────────│  SUSPENDED    │──────────┐
                           │          └──────────────┘          │
                     参与者重连                           INTENT_CLAIM 通过
                           │                                    │
                           ▼                                    ▼
                   ┌──────────────┐                    ┌──────────────┐
                   │    ACTIVE    │                    │ TRANSFERRED  │
                   └──────────────┘                    └──────────────┘
```

| 转换 | 触发条件 | 副作用 |
|------|---------|--------|
| DRAFT → ANNOUNCED | 发送 INTENT_ANNOUNCE | |
| ANNOUNCED → ACTIVE | Coordinator 接受 | |
| ACTIVE → EXPIRED | TTL 过期（coordinator 墙钟判定） | **触发 Intent Expiry Cascade**：关联 PROPOSED 操作 auto-reject |
| ACTIVE → WITHDRAWN | 发送 INTENT_WITHDRAW | **触发 Intent Expiry Cascade** |
| ACTIVE → SUPERSEDED | 新 intent 声明 supersedes | **触发 Intent Expiry Cascade** |
| ACTIVE → SUSPENDED | 所有者不可用检测 | 关联 PROPOSED 操作进入 FROZEN |
| SUSPENDED → ACTIVE | 所有者重连 | FROZEN 操作恢复 PROPOSED |
| SUSPENDED → TRANSFERRED | INTENT_CLAIM 审批通过 | |
| SUSPENDED → EXPIRED/WITHDRAWN | 超时或外部决策 | **触发 Intent Expiry Cascade** |

---

### 5.2 Operation 状态机

```
                INTENT 活跃时
   ┌────────────────────────────────────────┐
   │                                        │
   │  ┌──────────────┐    OP_COMMIT    ┌──────────────┐    OP_SUPERSEDE   ┌──────────────┐
   │  │   PROPOSED   │ ─────────────→ │  COMMITTED   │ ────────────────→│  SUPERSEDED  │
   │  └──┬──┬──┬─────┘                └──────────────┘                   └──────────────┘
   │     │  │  │
   │     │  │  │  OP_REJECT / intent_terminated / frozen_scope_timeout
   │     │  │  └──────────────────────────────────────────→ ┌──────────────┐
   │     │  │                                                │   REJECTED   │
   │     │  │                                                └──────────────┘
   │     │  │  发送者不可用
   │     │  └─────────────────────────────────────────────→ ┌──────────────┐
   │     │                                                   │  ABANDONED   │
   │     │  引用的 intent 进入 SUSPENDED                      └──────────────┘
   │     └────────────────────────────────────────────────→ ┌──────────────┐
   │                                                        │   FROZEN     │──→ PROPOSED (intent 恢复)
   │                                                        └──────┬───────┘
   │                                                               │ intent 终态
   │                                                               ▼
   │                                                        ┌──────────────┐
   │                                                        │   REJECTED   │
   └────────────────────────────────────────────────────────└──────────────┘
```

| 转换 | 触发条件 |
|------|---------|
| PROPOSED → COMMITTED | 变更已应用到 shared state |
| PROPOSED → REJECTED | Reviewer 拒绝 / intent 终态触发 auto-reject / frozen scope 超时 |
| PROPOSED → ABANDONED | 发送者被判定不可用 |
| PROPOSED → FROZEN | 引用的 intent 进入 SUSPENDED |
| FROZEN → PROPOSED | 引用的 intent 恢复 ACTIVE |
| FROZEN → REJECTED | 引用的 intent 从 SUSPENDED 进入终态 |
| COMMITTED → SUPERSEDED | 被 OP_SUPERSEDE 替代 |

---

### 5.3 Conflict 状态机

```
   ┌──────────────┐     CONFLICT_ACK      ┌──────────────┐     RESOLUTION     ┌──────────────┐
   │     OPEN     │ ───────────────────→  │    ACKED     │ ─────────────────→ │   RESOLVED   │ ──→ CLOSED
   └──┬──┬────────┘                       └──────────────┘                     └──────────────┘
      │  │
      │  │  CONFLICT_ESCALATE
      │  └──────────────────────────────→ ┌──────────────┐     RESOLUTION     ┌──────────────┐
      │                                   │  ESCALATED   │ ─────────────────→ │   RESOLVED   │ ──→ CLOSED
      │                                   └──────┬───────┘                     └──────────────┘
      │                                          │
      │  所有关联 intent/op 终结 (Section 17.9)   │ 所有关联 intent/op 终结
      ▼                                          ▼
   ┌──────────────┐                       ┌──────────────┐
   │  DISMISSED   │                       │  DISMISSED   │
   └──────────────┘                       └──────────────┘
```

| 转换 | 触发条件 |
|------|---------|
| OPEN → ACKED | 收到 CONFLICT_ACK |
| OPEN → ESCALATED | 收到 CONFLICT_ESCALATE |
| OPEN → DISMISSED | 手动 dismiss 或所有关联实体终结（auto-dismiss） |
| ESCALATED → DISMISSED | 所有关联实体终结（auto-dismiss） |
| ACKED → RESOLVED | 收到 RESOLUTION |
| ESCALATED → RESOLVED | 收到 RESOLUTION |
| RESOLVED → CLOSED | 裁决执行完毕 |

**Auto-Dismiss 触发条件**：`related_intents` 全部在终态（EXPIRED/WITHDRAWN/SUPERSEDED）且 `related_ops` 全部在终态（REJECTED/ABANDONED/SUPERSEDED）。

---

### 5.4 跨状态机联动规则

这是 v0.1.4 的核心新增内容——定义状态机之间的因果传播。

```
Intent 终态 ─────────┬──→ 关联 PROPOSED 操作 auto-reject (或 grace period 后 reject)
(EXPIRED/WITHDRAWN/  │
 SUPERSEDED)         └──→ 如果是冲突的最后一个活跃关联实体 → Conflict auto-dismiss
                                                              └──→ 释放 frozen scope

Intent SUSPENDED ────────→ 关联 PROPOSED 操作 → FROZEN

Intent 恢复 ACTIVE ──────→ 关联 FROZEN 操作 → PROPOSED

参与者不可用 ─────────────→ Intent → SUSPENDED
                          → 本人的 PROPOSED 操作 → ABANDONED
```

---

## 6. 枚举值注册表

### 6.1 Roles

| 值 | 权限 |
|----|------|
| `observer` | 只读，无决策权 |
| `contributor` | 可以提交 intent 和 operation |
| `reviewer` | 可以批准/拒绝 OP_PROPOSE |
| `owner` | 可以解决冲突，覆盖 contributor 操作 |
| `arbiter` | 最高裁决权，可解决任何冲突、覆盖任何参与者 |

### 6.2 Capabilities

| 值 | 说明 |
|----|------|
| `intent.broadcast` | 可发送 INTENT_ANNOUNCE |
| `intent.update` | 可发送 INTENT_UPDATE |
| `intent.withdraw` | 可发送 INTENT_WITHDRAW |
| `intent.claim` | 可发送 INTENT_CLAIM |
| `op.propose` | 可发送 OP_PROPOSE |
| `op.commit` | 可发送 OP_COMMIT |
| `op.reject` | 可发送 OP_REJECT |
| `conflict.report` | 可发送 CONFLICT_REPORT |
| `conflict.ack` | 可发送 CONFLICT_ACK |
| `governance.vote` | 可参与治理投票 |
| `governance.override` | 可发送覆盖性 RESOLUTION |
| `causality.vector_clock` | 支持 vector_clock 水位 |
| `causality.lamport_clock` | 支持 lamport_clock 水位（MUST 支持） |
| `semantic.analysis` | 支持语义冲突检测 |

### 6.3 Security Profile

| 值 | 认证 | 签名 | 审计 | 适用场景 |
|----|------|------|------|---------|
| `open` | 无 | 无 | SHOULD | 内部团队/开发环境 |
| `authenticated` | MUST（OAuth/mTLS/API Key） | SHOULD（MAC 或数字签名） | MUST | 跨团队协作 |
| `verified` | MUST（X.509 证书链） | MUST（数字签名） | MUST（防篡改日志） | 跨组织高风险场景 |

### 6.4 Compliance Profile

| 值 | 必须支持的消息类型 | 额外要求 |
|----|--------------------|---------|
| `core` | HELLO, SESSION_INFO, GOODBYE, HEARTBEAT, INTENT_ANNOUNCE, OP_COMMIT, CONFLICT_REPORT, RESOLUTION, PROTOCOL_ERROR | |
| `governance` | core + INTENT_UPDATE, INTENT_WITHDRAW, INTENT_CLAIM, OP_PROPOSE, OP_REJECT, OP_SUPERSEDE, CONFLICT_ACK, CONFLICT_ESCALATE | 必须指定 arbiter；intent-before-action 为 MUST |
| `semantic` | governance + semantic conflict reporting | 支持 basis.kind = model_inference |

### 6.5 Conflict Category

| 值 | 说明 |
|----|------|
| `scope_overlap` | 两个 intent/operation 的 scope 有交集 |
| `concurrent_write` | 同一资源的并发写入 |
| `semantic_goal_conflict` | 语义层面的目标冲突 |
| `assumption_contradiction` | 假设之间的矛盾 |
| `policy_violation` | 违反 session 策略 |
| `authority_conflict` | 权限冲突 |
| `dependency_breakage` | 依赖关系被破坏 |
| `resource_contention` | 资源争用 |

### 6.6 Severity

`info` < `low` < `medium` < `high` < `critical`

### 6.7 Decision

| 值 | 说明 |
|----|------|
| `approved` | 批准 |
| `rejected` | 拒绝 |
| `dismissed` | 驳回（冲突不成立或已失效） |
| `human_override` | 人工覆盖 |
| `policy_override` | 策略覆盖 |
| `merged` | 合并处理 |
| `deferred` | 暂缓处理 |

### 6.8 Error Code

| 值 | 说明 | 触发场景 |
|----|------|---------|
| `MALFORMED_MESSAGE` | 消息格式错误或缺少必填字段 | 解析失败 |
| `UNKNOWN_MESSAGE_TYPE` | 未知的 message_type | 不支持的消息类型 |
| `INVALID_REFERENCE` | 引用了不存在的 session/intent/operation/conflict | 找不到引用目标 |
| `VERSION_MISMATCH` | 协议版本不兼容 | HELLO 中版本不匹配 |
| `CAPABILITY_UNSUPPORTED` | 消息要求接收方不支持的能力 | 能力缺失 |
| `AUTHORIZATION_FAILED` | 发送者权限不足 | 角色不匹配 |
| `PARTICIPANT_UNAVAILABLE` | 检测到参与者不可用 | 心跳超时 |
| `RESOLUTION_TIMEOUT` | 冲突解决超时 | 超过 resolution_timeout_sec |
| `SCOPE_FROZEN` | 目标 scope 被冻结 | 操作/intent 命中冻结区域 |
| `CLAIM_CONFLICT` | INTENT_CLAIM 目标已被他人认领 | 并发 claim |

---

## 7. 协议顺序约束

实现时必须遵守的消息顺序规则：

| 约束 | 规则 | 违反时的行为 |
|------|------|-------------|
| **Session-first** | HELLO 必须是参与者在 session 中发送的第一条消息 | 拒绝或延迟处理非 HELLO 消息 |
| **Session-info-before-activity** | 参与者在收到 SESSION_INFO 前不应发送业务消息 | Coordinator 在 SESSION_INFO 之前不处理业务消息 |
| **Intent-before-operation** | OP_PROPOSE/OP_COMMIT 引用的 intent_id 必须已存在 | 可缓冲/警告/拒绝（PROTOCOL_ERROR） |
| **Conflict-before-resolution** | RESOLUTION 引用的 conflict_id 必须已存在 | 拒绝未知冲突的裁决 |
| **Causal consistency** | 携带 watermark 的消息不应被视为对 watermark 覆盖范围之外事件的权威声明 | 对超范围判断标记为 partial |

---

## 8. 实现检查清单

开发者实现 MPAC 时的快速对照表：

- [ ] 所有消息包装在 Message Envelope 中，8 个必填字段齐全
- [ ] HELLO 作为首条消息发送，收到 SESSION_INFO 后验证兼容性
- [ ] 支持 `lamport_clock` watermark 的生成、比较和 lamport_value 降级
- [ ] OP_COMMIT 包含 state_ref_before 和 state_ref_after
- [ ] OP_COMMIT / CONFLICT_REPORT / RESOLUTION 的信封包含 watermark
- [ ] Scope overlap 对 file_set / entity_set / task_set 使用 MUST 级算法
- [ ] Intent 终态触发关联 PROPOSED 操作的 auto-reject（Section 15.7）
- [ ] 冲突关联实体全部终结时触发 auto-dismiss（Section 17.9）
- [ ] TTL 由 coordinator 基于 received_at + ttl_sec 墙钟判定
- [ ] RESOLUTION 拒绝 COMMITTED 操作时 MUST 包含 rollback 字段
- [ ] Authenticated profile: 重放检测、角色验证、身份绑定
- [ ] 心跳间隔 ≤ 30 秒，不可用超时 = 90 秒
- [ ] GOODBYE 时声明 active_intents 和 intent_disposition
