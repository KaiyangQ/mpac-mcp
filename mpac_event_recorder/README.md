# MPAC Event Recorder

一个**可随时删除**的事件录像器。开启后把 MPAC session 里发生的一切(coordinator
envelope、`mpac.*` log、relay 子进程生命周期)写到一个 JSONL 文件,测试完拿这份
文件做分析。

> **删除方式:** `rm -rf mpac_event_recorder/`。两个入口点(`web-app/api/main.py`
> 和 `mpac-mcp/src/mpac_mcp/relay.py`)的 `try-import` 会自动 swallow,系统
> 跟没装过一模一样。

---

## 🤖 当 Claude 帮你开启录音时(给未来的 Claude 看的速查)

**典型对话:** 用户说"读 mpac_event_recorder/README.md 然后帮我开启 log"。

按这个顺序操作:

1. **先问一句:** "本地测试还是 AWS prod?"(不要默认 prod —— 每次都该确认)
2. **AWS prod 路径:** 跳到下方 [用法 1 步骤 A](#步骤-a在-aws-lightsail-上开启-web-app-录音)。
   不需要 `docker compose build`(env_file 在容器**启动**时读,只 `restart api` 即可)。
3. **本地路径:** 跳到下方 [用法 2](#用法-2--纯本地开发单-mac)。
4. **测试结束后,用户说"关掉"**: 按 [步骤 E](#步骤-e测完关录音)。

**重要边界:**
- AWS 上**只录 web-app 端**的事件流(coordinator envelope + mpac.* log)。
  3 个测试者本地的 relay 不会被录,除非他们各自在自己机器 export env var。
- Docker image 里的 `mpac_event_recorder/` 是**构建时**拷进去的。如果用户改了
  recorder 代码,要 `docker compose build api` 才生效。
- **toggle env var 必须用 `up -d --force-recreate`,不是 `restart`!**
  `docker compose restart` 只是 stop+start 已存在的容器,**不会**重读 env_file —— 环境
  变量在容器**创建**时就 baked 了。`up -d --force-recreate --no-deps api` 才会用新
  env 重建容器。这是 2026-04-28 实际操作时踩的坑,不要再写错。
- JSONL 写到 host 的 `/var/mpac/data/`(容器里挂载到 `/data/`)。这是 SQLite 同
  目录,host 上能直接 `scp` 走。

---

## 它是什么

| 字段 | 说明 |
|---|---|
| 触发开关 | 环境变量 `MPAC_EVENT_LOG=<path>` |
| 进程行为 | 进程启动时读一次该 env var → 设了 = 录,没设 = no-op |
| 输出格式 | JSONL(每行一个 JSON,append-only,line-buffered) |
| 默认状态 | **不录**(env var 不设) |
| 性能影响 | 每条 envelope 多一次 JSON encode + write,实测 < 1 ms |

**关键:启动后改环境变量没用。** 想中途开/关必须重启进程(详见下方
"如果中途想停录" 一节)。

---

## 用法 1 — 本地三人测试(最常见)

适用于你用 Zoom 开会、三人各自笔记本跑 relay、共享访问 prod web-app
(`mpac-web.duckdns.org`)的场景。

### 步骤 A:在 AWS Lightsail 上开启 web-app 录音

部署用的是 **Docker Compose**,api 容器读 `/etc/mpac/api.env` 拿环境变量,
SQLite + 持久化数据挂在 host 的 `/var/mpac/data` → 容器里的 `/data`。
所以录音文件**必须写到 `/data/`** 才能在容器外看得到。

```bash
ssh ubuntu@mpac-web.duckdns.org

# 1. 在 api.env 末尾追加一行(注意是 host 的 /etc/mpac/api.env)
echo 'MPAC_EVENT_LOG=/data/session.jsonl' | sudo tee -a /etc/mpac/api.env

# 2. 重启 api 容器让它重读 env(不用重 build)
cd ~/Agent_talking   # 或者你 git clone 时的位置
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml \
     --env-file /etc/mpac/compose.env up -d --force-recreate --no-deps api

# 3. 确认录音器已加载
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml logs --tail=50 api \
    | grep -i recorder
# 应该看到一行: "kind":"recorder_started" ...
```

### 步骤 B:三个测试者各自的 relay(可选,但推荐)

如果你想把每个人 `claude -p` 子进程的 spawn / exit / 内容过滤错误也录下来,
让每个测试者在跑 relay 之前加 env var:

```bash
# 每个人在自己 Mac/PC 上:
export MPAC_EVENT_LOG="$HOME/mpac-relay-$(whoami)-$(date +%H%M).jsonl"
mpac-mcp-relay --project-url wss://mpac-web.duckdns.org/ws/relay/1 --token mpac_agent_xxx
```

> Windows PowerShell 改成 `$env:MPAC_EVENT_LOG = "C:\temp\mpac-relay.jsonl"`。

不开也行 —— web-app 端的 envelope 流已经能告诉你 90% 想知道的事(谁声明了什么
intent、谁触发了什么 CONFLICT_REPORT、谁 withdrew)。客户端 relay 录音只在你
怀疑「子进程是不是悄悄崩了」时才需要。

### 步骤 C:跑测试

按 `docs/CONFLICT_TEST_SCENARIOS.md` 里的剧本走就行,录音器在背后默默写。

### 步骤 D:测完拿日志

```bash
# AWS:host 上的文件路径是 /var/mpac/data/session.jsonl(容器内的 /data/ 挂载点)
scp ubuntu@mpac-web.duckdns.org:/var/mpac/data/session.jsonl ./session-aws.jsonl

# 测试者本机(如果开了 relay 录音):
# 让他们把 ~/mpac-relay-xxx.jsonl 发给你
```

### 步骤 E:测完关录音

把 api.env 里的那一行删掉再 restart api 容器:

```bash
ssh ubuntu@mpac-web.duckdns.org
sudo sed -i '/^MPAC_EVENT_LOG=/d' /etc/mpac/api.env
cd ~/Agent_talking
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml \
     --env-file /etc/mpac/compose.env up -d --force-recreate --no-deps api
```

可选:把已经写满的 JSONL 移走或删除,避免下次测试 append 到同一个文件:

```bash
sudo mv /var/mpac/data/session.jsonl \
        /var/mpac/data/session-$(date +%Y%m%d-%H%M).jsonl.bak
# 或直接删: sudo rm /var/mpac/data/session.jsonl
```

---

## 用法 2 — 纯本地开发(单 Mac)

跑本地 web-app 自测时:

```bash
cd /path/to/Agent_talking
export MPAC_EVENT_LOG=/tmp/mpac-local-$(date +%H%M%S).jsonl

# 起本地 web-app
PYTHONPATH=mpac-package/src .venv/bin/uvicorn api.main:app \
    --app-dir web-app --reload --port 8001

# 另开一个 terminal,跑本地 relay(同样 export 一份)
export MPAC_EVENT_LOG=/tmp/mpac-relay-local.jsonl
mpac-mcp-relay --project-url ws://127.0.0.1:8001/ws/relay/1 --token <dev_token>
```

测完直接看文件:

```bash
ls -lh /tmp/mpac-*.jsonl
```

---

## 怎么读 JSONL

最简单的办法是 `jq`(macOS: `brew install jq`)。

### 看时间线总览

```bash
jq -r '"\(.ts | sub("\\..*";""))  \(.kind)  \(.message_type // .event // .level // "")"' \
   /tmp/mpac-local.jsonl
```

输出大概长这样:

```
2026-04-28T17:11:30  recorder_started
2026-04-28T17:11:31  process_envelope_call  HELLO
2026-04-28T17:11:31  envelope                INTENT_ANNOUNCE
2026-04-28T17:11:31  envelope                CONFLICT_REPORT
...
```

### 找所有冲突报告

```bash
jq 'select(.kind == "envelope" and .message_type == "CONFLICT_REPORT")' \
   /tmp/mpac-local.jsonl
```

### 找自冲突回归(对应你 4-28 那个 bug)

```bash
jq 'select(.message_type == "CONFLICT_REPORT" 
           and .payload.principal_a == .payload.principal_b)' \
   /tmp/mpac-local.jsonl
# 期望:空。如果有内容 = 2a/2c 修复回归了。
```

### 看每个用户做了什么

```bash
jq -r 'select(.kind == "envelope" and .direction == "inbound") 
       | "\(.sender)  \(.message_type)  \(.payload.intent_id // "")"' \
   /tmp/mpac-local.jsonl
```

### 看 relay 子进程哪里失败了

```bash
jq 'select(.kind == "relay_subprocess" 
           and (.event == "reply" and .looks_like_error == true))' \
   /tmp/mpac-relay-*.jsonl
```

---

## 录到了什么(完整 schema)

每行 JSON 至少有:

```json
{
  "ts": "ISO 8601 UTC",
  "monotonic": 12345.678,
  "role": "web" | "relay",
  "kind": "<see below>"
}
```

**`kind` 取值:**

| `kind` | 字段 | 含义 |
|---|---|---|
| `recorder_started` | `pid`, `python`, `path` | 进程加载录音器 |
| `process_envelope_call` | `sender`, `message_type`, `message_id`, `project_id` | bridge 收到一条 envelope |
| `envelope` (`direction=inbound`) | `sender`, `message_type`, `payload`, `message_id` | coordinator 处理的入站消息 |
| `envelope` (`direction=coordinator_response`) | `in_reply_to`, `message_type`, `payload`, `recipient` | coordinator 产生的响应(CONFLICT_REPORT 等) |
| `log` | `level`, `logger`, `message`, `module`, `func`, `line` | `mpac.*` logger 的输出 |
| `relay_subprocess` (`event=dispatch`) | `project_id`, `message_len`, `message_preview` | 收到聊天消息,准备 spawn `claude -p` |
| `relay_subprocess` (`event=reply`) | `duration_sec`, `reply_preview`, `looks_like_error` | 子进程结束(成功或失败) |
| `relay_subprocess` (`event=orphan_cleanup_call`) | `reason` | 子进程异常,relay 调清理端点 |
| `relay_subprocess` (`event=orphan_cleanup_result`) | `withdrawn_intent_ids` | 清理端点返回 |

---

## 如果中途想停录

录音器没法热关 —— 但你可以让进程崩到中途也无所谓,因为 `buffering=1`(line-buffered)
保证每条事件**写一行就刷一行**到磁盘。

如果非要中途停:`sudo systemctl stop mpac-web`,文件就停在那不再加新行。
重新启动后(env var 还在的话)会**追加**(append 模式),不会覆盖。

---

## 常见问题

### Q: 文件创建了但是空的

A: web-app 进程内的 `install()` 静默 return 了,通常是 sys.path 找不到
`mpac_event_recorder`。在 AWS 上检查:

```bash
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml logs api 2>&1 \
    | grep -i recorder
```

应该有 `recorder_started` 这一行。如果没有,可能是 docker image 没把
`mpac_event_recorder/` 目录 `COPY` 进容器(检查 [deploy/dockerfiles/api/Dockerfile](deploy/dockerfiles/api/Dockerfile))。

### Q: 文件越写越大

A: 长时间录会比较大。一次 30 分钟的 3-人测试大概几 MB 量级,可控。生产长开
不建议(没做轮转)。如果担心,在 host 上加个 cron:

```bash
# /etc/cron.daily/mpac-log-rotate
find /var/mpac/data -name 'session*.jsonl' -mtime +7 -delete
```

### Q: 录到了用户输入的聊天内容,涉及隐私吗

A: `relay_subprocess.message_preview` 截了前 200 字符,会包含用户聊天。
如果敏感,加 env var `MPAC_EVENT_REDACT_PREVIEWS=1`(暂未实现 —— 真要保护
隐私我们再加这个开关)。生产长开建议先想清楚这个。

### Q: 删掉 `mpac_event_recorder/` 之后怎么样?

A: web-app 和 relay 启动时打印一行 `ImportError` 被 swallow,继续正常跑。
**没有任何副作用** —— 这是这个模块的核心设计承诺。

### Q: 别人不小心把这个目录提交到 main 分支了怎么办?

A: 这个目录是新代码,提交到 main 没问题(它本来就是项目一部分)。
真正"删除"的是: 1) 不设 env var,或 2) 完全清理:`git rm -r mpac_event_recorder/`
然后 commit,两处入口的 try-import 会照常 swallow。

---

## 给未来的我:升级路径

短期(这个 README 写的)够用就够用了。如果哪天要升级:

1. **运行时开关**(不重启)→ 加 `POST /api/admin/recording/start|stop` 端点,
   内部就是调 `install()` / `shutdown()`。
2. **可视化时间线**(像 Chrome Network 面板)→ 把 JSONL 喂给 Grafana Loki +
   一个简单的 dashboard。
3. **真·SaaS observability** → 改用 OpenTelemetry SDK,signal 三件套
   (logs/metrics/traces)统一发到 Honeycomb / Grafana Cloud。

JSONL 是上面三种方案的最低公分母,所以现在写的代码不会浪费。
