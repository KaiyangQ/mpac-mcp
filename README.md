# MPAC — Multi-Principal Agent Coordination Protocol

**[SPEC.md](./SPEC.md) 是 MPAC 协议的最新规范（当前版本 v0.1.4）。** 协议的完整演进历史、每轮改动记录和独立评审报告保存在 [version_history/](./version_history/) 文件夹中，详见 [version_history/CHANGELOG.md](./version_history/CHANGELOG.md)。

---

## Repository Structure

```
SPEC.md                        ← 协议规范（source of truth，当前 v0.1.4）
MPAC_Developer_Reference.md    ← 开发者参考文档（数据字典、字段关联、状态机、枚举表）
MPAC_v0.1.3_Audit_Report.md    ← 最近一次的五维审计报告
README.md                      ← 本文件
local_config.json              ← API key 配置（不要提交到公开仓库）
local_config.example.json      ← 配置模板
pyproject.toml                 ← 项目元数据
version_history/               ← 协议演进历史和评审报告
```

## Documents

| 文档 | 受众 | 说明 |
|------|------|------|
| [SPEC.md](./SPEC.md) | 协议设计者 / 标准化讨论 | 完整协议规范，包含设计理念、语义定义、安全模型 |
| [MPAC_Developer_Reference.md](./MPAC_Developer_Reference.md) | 开发者 / 实现者 | 面向写代码的人：所有数据对象、字段定义、类型、必填/可选、模块间引用关系、状态机转换表、枚举值注册表、实现检查清单 |
| [version_history/](./version_history/) | 所有人 | 协议演进历史，每个版本的归档快照、改动记录和评审报告 |

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

旧版参考实现代码（基于 v0.1.2 之前的协议）已清理。新的参考实现将基于 v0.1.4 规范重新构建。
