# MPAC — Multi-Principal Agent Coordination Protocol

**[SPEC.md](./SPEC.md) 是 MPAC 协议的最新规范（当前版本 v0.1.3）。** 协议的完整演进历史、每轮改动记录和独立评审报告保存在 [version_history/](./version_history/) 文件夹中，详见 [version_history/README.md](./version_history/README.md)。

---

## Repository Structure

```
SPEC.md                     ← 协议规范（source of truth）
README.md                   ← 本文件
local_config.json           ← API key 配置（不要提交到公开仓库）
local_config.example.json   ← 配置模板
pyproject.toml              ← 项目元数据
version_history/            ← 协议演进历史和评审报告
```

## API Key Configuration

Anthropic API key 保存在 `local_config.json` 中，供后续参考实现和测试使用：

```json
{
  "anthropic": {
    "api_key": "your_key_here",
    "model": "claude-sonnet-4-20250514"
  }
}
```

## Note

旧版参考实现代码（基于 v0.1.2 之前的协议）已清理。新的参考实现将基于 v0.1.3 规范重新构建。
