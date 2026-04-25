# 两人手动测试用例 (Alice + Bob)

> **私有文档。** 面向"开两个浏览器手动验证 UI 行为"的内部测试场景。
> 区别于 [`BETA_EXAMPLE.md`](BETA_EXAMPLE.md)（3 人剧本，用真 Claude 走 import 图），
> 本文是**两个人 + 大量无 Claude 快测**的体感回归清单 —— 用于：
> - 改完 UI / 后端拍一遍 smoke
> - 部署后到 prod 验真
> - 给新参与者讲 demo 时的"剧本"

## 准备

- **prod 环境**：[https://mpac-web.duckdns.org/projects/N](https://mpac-web.duckdns.org/projects/N)，N 是当前测试项目 id（`scripts/seed_example_project.py` 跑出来给你的）
- **local dev**：`http://localhost:3000/projects/N`（参考 [`scripts/demo_driver.py`](../scripts/demo_driver.py) 的 setup 子命令一键开账号）
- **两个浏览器窗口**：
  - `Alice tab` — 普通窗口，登 owner 账号
  - `Bob tab` — 隐私/incognito 窗口（避免 cookie 串），登 contributor 账号
- **能 Claude 测的还要**：本机装 `claude` CLI（Pro/Max 订阅），Settings 里设过 Anthropic API key

> **协议小贴士**：`CONFLICT_REPORT` 只 unicast 给 `principal_a` / `principal_b` 两个当事人
> （[mpac_bridge.py:495-500](../web-app/api/mpac_bridge.py:495)）。所以**旁观者的 CONFLICTS 面板永远空** —— 这不是 bug。
> 旁观者通过 "WHO'S WORKING 同一文件出现两个名字 + 文件树绿点" 来感知冲突。

---

## A. 快测组（无需 Claude，每个 ≤30 秒）

### TC-1 出席 sync（最基础 smoke）

**目的**：两个浏览器互相能"看见"彼此 + 离开能"看见"对方走。

**步骤**：
1. Alice tab 已开在项目页 → 看 header："1 online"
2. Bob tab 打开同一个项目 URL（在 incognito）
3. **3 秒内**两个 tab 都应该变 "2 online"
4. Alice tab 的 WHO'S WORKING 面板：从只有 "Alice (you) idle" → 多出 "Bob idle"
5. Bob tab 的 WHO'S WORKING 面板：能看到 "Alice idle" + "Bob (you) idle"
6. 关掉 Bob tab → Alice tab 应该 ~3 秒内回到 "1 online"，Bob 从面板消失

**触发链**：Bob 浏览器 WS HELLO → bridge 发 PARTICIPANT_UPDATE 到 Alice → Alice 的 useMpacSession hook 更新本地 state → 渲染。

**失败信号**：
- 计数不更新 / 名字不出现 → WS 连接断了或 PARTICIPANT_UPDATE 丢了；看 Alice tab 浏览器 console 有没有 WS reconnect 错误
- 名字短暂闪现又消失 → 可能命中 reconnect dedup（[mpac_bridge.py:570](../web-app/api/mpac_bridge.py:570)），同一 user 在多 tab 里登

---

### TC-2 Owner vs Contributor 按钮可见性

**目的**：权限渲染正确 —— Alice 看到 Reset/Delete/Invite，Bob 只能 Leave。

**步骤**：
1. Alice tab header 右上角应该有：`Connect Claude` `Invite` `Reset` `Delete` `Settings` `Sign out`
2. Bob tab header 右上角应该有：`Connect Claude` `Leave` `Settings` `Sign out`（**没有** Invite/Reset/Delete）
3. Alice tab 状态栏（底部）右下角：`owner · Alice`
4. Bob tab 状态栏右下角：`contributor · Bob`

**失败信号**：Bob tab 出现 Reset/Delete 按钮 → 后端权限检查通过但前端没 gate；可能 owner 字段没下发。

---

### TC-3 Invite Modal（Alice 单边）

**目的**：Invite 流程能 mint code，复制按钮可用。

**步骤**：
1. Alice tab 点 `Invite` → 弹出 InviteModal
2. Modal 应显示：roles 选择（默认 contributor）+ "Generate Invite" 按钮
3. 点 Generate → 出现一段 invite code（形如 `inv-xxxxxxxx`）+ 一个完整 URL（`https://mpac-web.duckdns.org/invite/inv-xxx`）
4. 点 "Copy" → 应有 toast/反馈
5. 关 Modal → 重开一个 → 之前的 code 不应再显示（无状态）
6. **副作用确认**：把 URL 粘到 Bob tab 的地址栏 → 看 Bob 是不是已经是项目成员（应该是 "你已经在项目里" 提示，不是 "接受邀请"）

**失败信号**：Generate 按钮无反应 → POST `/api/projects/{id}/invite` 失败，看 Network；或 token 过期。

---

### TC-4 Reset to seed 实时传播

**目的**：Alice 的 Reset 把 8 个 notes_app 文件回退；Bob 在另一边能立刻看到文件内容回到 seed。

**前置**：Bob 当前打开的文件是 `notes_app/db.py`。可以是 seed 内容也可以已被改过。

**步骤**：
1. **基线截图**：Bob tab 看 `db.py` 当前文件内容（前 5 行）
2. （可选准备："污染"文件）Alice 走 Claude 流改一改 db.py（见 TC-7）；或暂跳过此步直接走 reset
3. Alice tab 点 `Reset` → DestructiveConfirmModal 弹出 → 二次确认输入框输 `Reset` → 点确认
4. Alice tab：Modal 关闭，无错误 toast
5. Bob tab `db.py` viewer：**3 秒内**内容刷新回 seed（如果之前不一样）

**触发链**：`POST /api/projects/{id}/reset-to-seed` → 数据库覆写 → ProjectFile 更新 → 推一个 file-changed 事件给所有 WS 客户端 → 前端重 fetch 文件。

**失败信号**：
- Bob 的 viewer 不刷新 → file-change 事件没广播；F5 后能看到 seed 内容则是 push 路径问题
- Alice 点确认后 500 → 看 [api 日志](../web-app/api/main.py)，多半是 seed_data 模块缺 file 或权限错误

---

### TC-5 Bob Leave + 自动跳走

**目的**：Bob 点 Leave 后自己跳走 + Alice 看到 Bob 消失。

**步骤**：
1. 双方都在线（TC-1 的状态）
2. Bob tab 点 `Leave` → 弹 DestructiveConfirmModal → 二次确认（输 `Leave`）→ 点确认
3. Bob tab：应自动 redirect 到 `/projects` 项目列表，并且这个项目**不再出现**在列表里
4. Alice tab：~3 秒内 Bob 从 WHO'S WORKING 消失 + "online" 计数 -1

**失败信号**：
- Bob redirect 但 Alice 仍看见 Bob 在线 → bridge 没收到 GOODBYE，参考 [mpac_bridge.py:653](../web-app/api/mpac_bridge.py:653)
- Bob 点 Leave 后还能用 URL 直接回项目 → 后端 membership 没真撤销

**清理**：要重新做 TC-1～TC-4，让 Alice 重新 invite Bob（TC-3）。

---

### TC-6 Project Delete 强退（**破坏性，慎做**）

**目的**：Alice Delete 项目后 Bob 立刻从项目页被踢走。

> ⚠️ 不可逆。做完这一组 case 后整个 project 就没了，要重新跑 [`scripts/seed_example_project.py`](../scripts/seed_example_project.py) 才有新项目。

**步骤**：
1. 双方都在线，Bob 在 `/projects/N` 页面
2. Alice tab 点 `Delete` → DestructiveConfirmModal → 输入项目名确认 → 确认
3. Alice tab：redirect 到 `/projects`，列表里没了
4. Bob tab：**3 秒内**应该出现错误 banner（"project deleted" 之类）+ 自动 redirect 到 `/projects`
5. Bob 列表里也应该没这个项目了

**失败信号**：Bob 没被踢走还能浏览代码 → bridge 没 broadcast SESSION_CLOSE 或前端没 handle。

---

## B. Claude 组（双方各装 claude CLI）

> 这一组每个 case 大约 1-3 分钟（取决于 Claude 响应速度）。

### TC-7 单 Claude 编辑（无冲突）

**目的**：一个 Claude announce intent + commit 改动，**两边浏览器都看到**：WHO'S WORKING 多一个 "Alice's Claude" + 文件树绿点 + 文件内容更新。

**步骤**：
1. 双方都在线
2. Alice tab 点 `Connect Claude` → modal 给一行 bootstrap 命令 → 在本机 terminal 跑
3. Modal 状态从 "Waiting…" → "Connected" 后关掉
4. 验证：**两个 tab 的 WHO'S WORKING** 都多了一行 `Alice's Claude` (idle)
5. Alice tab 在底部 AI ASSISTANT 输入框打："给 notes_app/db.py 加个 module 级 docstring，简短一两行就行"
6. 点 Send
7. **观察**：
   - 1-3 秒内：两个 tab 的 WHO'S WORKING 中 `Alice's Claude` 状态变 active，下面挂 `notes_app/db.py` + objective 文案
   - 文件树 `db.py` 旁出现绿点
   - Claude 完成后：两边的 `db.py` viewer 内容更新 + Claude 回 idle + 绿点消失
8. CONFLICTS 面板：**始终空**（只有一个参与方，无冲突）

**失败信号**：
- Bob 看不到 "Alice's Claude" → relay 没把 PARTICIPANT_UPDATE 广播，看 [ws_relay.py:203](../web-app/api/routes/ws_relay.py:203) 的 `register_and_hello`
- 文件内容没更新，但 Claude 说"完成了" → file-write 走的是 mpac-mcp 的 `submit_change` 工具，需要 mpac-mcp 0.2.4+，老版本静默 fail；用 [`scripts/demo_driver.py`](../scripts/demo_driver.py) reset 后重试

---

### TC-8 双 Claude 同文件冲突（**头牌 demo**）

**目的**：两个 Claude 同时改同一文件 → CONFLICTS 面板**对双方填充** + WHO'S WORKING 同文件双名字。

**步骤**：
1. 双方先各自 Connect Claude（按 TC-7 步骤 2-4），两边都看到 `Alice's Claude` 和 `Bob's Claude` 两个 idle agent
2. **快速一前一后**（最好 5 秒内）：
   - Alice tab AI ASSISTANT 发：「重构 notes_app/db.py 的 save() 函数，加 type hints」 → Send
   - Bob tab AI ASSISTANT 发：「修改 notes_app/db.py 的 load() 函数，让它支持 batch」 → Send
3. **观察 WHO'S WORKING**（两个 tab 都看到）：
   - `Alice's Claude` active on `notes_app/db.py`
   - `Bob's Claude` active on `notes_app/db.py`
   - 文件树 `db.py` 旁绿点
4. **观察 CONFLICTS 面板**（**两个 tab 都该填，因为双方都是 principal**）：
   - 出现一条 entry：`scope_overlap` 类别，显示对方的 principal 名字 + 涉及文件
   - 应有 `Ack` 和 `Yield` 两个按钮
5. 选一边（比如 Bob tab）点 `Yield` → Bob 的 Claude 收到指令 → Bob 的 intent withdraw
6. **预期**：
   - 双方 CONFLICTS 面板该 entry 消失
   - WHO'S WORKING 中 `Bob's Claude` 回到 idle
   - `Alice's Claude` 继续工作，最终 commit 改动
   - `db.py` 内容更新成 Alice 的版本

**失败信号**：
- 一边 CONFLICTS 面板填了一边没填 → unicast 路由错；查 [mpac_bridge.py:495](../web-app/api/mpac_bridge.py:495)
- 都没 CONFLICTS → coordinator 的 scope overlap 没检出；可能是 v0.2.2 symbol-level 检测把 save vs load 当成不冲突（**这是 feature 不是 bug**，见 TC-9）
- Yield 按钮点了没反应 → relay 没把 user yield 翻成 INTENT_WITHDRAW；看 mpac-mcp tool 路径
- Yield 后 Alice 的 Claude 没继续改 → Alice 那边没收到 INTENT_WITHDRAW；查 broadcast

---

### TC-9 符号级精度（v0.2.2 hero）

**目的**：两个 Claude 改**同文件不同符号**，预期**不应该**有 CONFLICTS（mpac 0.2.2 的 `affects_symbols` 起作用）。

**前置**：本机 mpac/mpac-mcp 都是 0.2.2+（`pip show mpac` 看版本）。

**步骤**：
1. 同 TC-8 步骤 1（双方 Claude 上线）
2. 一前一后：
   - Alice：「**只改** notes_app/db.py 的 `save` 函数加 type hints，**不要碰其他函数**」
   - Bob：「**只改** notes_app/db.py 的 `delete` 函数加日志，**不要碰其他函数**」
3. **预期**：
   - WHO'S WORKING：双方都 active on `db.py`
   - CONFLICTS 面板：**应该是空**（symbols 不重叠）
   - 两个改动最后**都成功 commit**，db.py 同时有 typed save + 加日志的 delete

**失败信号**：
- CONFLICTS 还是触发了 → Claude 没生成 `affects_symbols` 字段（可能 Claude 没用 0.2.2+ 的工具签名）
- 两边都成功了但 db.py 只剩一边的改动 → 缺 OCC（state_ref_before）保护，后提交的把先提交的盖了；这是 protocol bug

---

### TC-10 Dependency breakage（跨文件影响）

**目的**：Alice 改 db.py 的导出符号 → Bob 改 import db 的 api.py → 应触发 `dependency_breakage` 类别（不是 `scope_overlap`）。

**步骤**：
1. 双 Claude 上线
2. Alice：「把 notes_app/db.py 的 `save(note)` 改名成 `save_note(note)`」
3. Bob：「在 notes_app/api.py 加个新 endpoint，调用 db.save 来存数据」
4. **预期**：
   - WHO'S WORKING：Alice 在 `db.py`，Bob 在 `api.py`（**不同文件**）
   - CONFLICTS 面板：依然出现 entry，但 `category` 是 `dependency_breakage`，payload 里有 `dependency_detail` 字段说明 api.py 用了 db.save
5. 一边 Yield → 走通

**失败信号**：
- 没出冲突 → reverse-dep 扫描挂了；看 [mpac_bridge.py:289-310](../web-app/api/mpac_bridge.py:289) 的 `compute_scope_impact`
- 出冲突但 category 是 `scope_overlap` → reverse-dep 路径走对了但分类错；查 coordinator 侧分类逻辑

---

## C. 调试路径速查

| 现象 | 先看哪儿 |
|---|---|
| 两边浏览器 online 数对不上 | Alice/Bob tab 的 DevTools → Network → WS frames |
| WHO'S WORKING 没更新 | 后端 [api/main.py log](../web-app/api/main.py)：找 `HELLO accepted` / `GOODBYE` 行 |
| CONFLICTS 该填没填 | 看 coordinator 出的 envelope，[mpac_bridge.py:460-505](../web-app/api/mpac_bridge.py:460) 的 `process_envelope` |
| Claude commit 后文件不更新 | mpac-mcp 版本：`pip show mpac-mcp` ≥ 0.2.4 |
| Bob 被 Leave / Delete 后能回项目 | 后端 token 表：`is_revoked` 字段是否真置位 |
| Reset 报 500 | seed_data 模块导入路径，[web-app/api/seed_data/notes_app.py](../web-app/api/seed_data/notes_app.py) |

## D. 用脚本跑非 Claude 那部分（可选）

[`scripts/demo_driver.py`](../scripts/demo_driver.py) 用 4 个 puppet 账号 (Alice/Bob/Carol/Dave) 通过 browser-WS 协议直接 begin_task / yield_task，可以在不开 Claude 的情况下复现 TC-7 / TC-8 的**协议层**效果（CONFLICTS 面板因为是 puppet 账号才看得到，要登 Carol/Dave 才能观察当事人视角）。两套测试是互补的：
- 手动 TC：测 UI 渲染 + 真实 Claude 集成
- demo_driver：测协议层 + 后端路由 + 不依赖 Claude 上线
