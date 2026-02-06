# AIEC 每日日志同步（A2A 增强版）

## 功能概述

将用户口述的工作内容整理成 **A2A 友好的结构化日志**，推送到 GitHub 团队仓库。

## 用户配置

```yaml
member_id: kkkaka-oss
member_name: Jiahe Gong
team: china
```

## 触发场景

### 日志相关
- "今天做了 xxx"
- "帮我写/生成日志"
- "推送到 GitHub"
- "同步工作记录"
- 查看团队其他人的日志

### Issue 自动回复
- "检查 Issue" / "有没有新问题"
- "查看回复" / "有人回复我吗"
- "回复 Issue #xx"
- 当检测到新问题时，Claude 会自动：
  1. 读取问题内容
  2. 结合用户的工作背景生成回复
  3. 推送到 GitHub Issue

### 团队知识检索（新增）✨
- "有人做过 xxx 吗"
- "查一下 xxx 项目"
- "看看 xxx 的日报"
- "xxx 最近在做什么"
- "团队在 xxx 上有什么经验"
- "搜索关于 xxx 的内容"

---

## 工作流程

### 用户口述 → Claude 整理 → 推送

```
用户随便说今天做了啥
       ↓
Claude 提取关键信息，生成：
  1. 人类可读的 Markdown 正文
  2. A2A 结构化数据（YAML front matter）
       ↓
用户确认/修改
       ↓
调用 scripts/github_sync.py 推送
```

---

## 日志格式（A2A 增强版）

```markdown
---
member_id: kkkaka-oss
member_name: Jiahe Gong
date: 2026-01-26
synced_at: 2026-01-26T18:30:00+08:00
team: china
source: claude-skill

# === A2A Structured Data ===
tasks_done:
  - content: "配置 GitHub Token"
    project: agent-hub
  - content: "测试推送功能"
    project: agent-hub

tasks_in_progress:
  - content: "接入飞书数据源"
    blockers: ["等待 API 审批"]

tasks_tomorrow:
  - content: "完成飞书集成"

ai_learning:
  topic: "Claude Skills 开发"
  insight: "SKILL.md 结构设计影响触发准确率"
  applied_to: "daily-log-sync skill"

blockers: ["等待 API 审批"]
---

# Jiahe Gong | 2026.01.26 Mon

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ✅ 完成
- 配置 GitHub Personal Access Token
- 测试 Skill 与 GitHub Agent Hub 连接

## 🔄 进行中
- 接入飞书数据源
  - ⚠️ blocked: 等待 API 审批

## 🎯 明日
- 完成飞书集成

## 📚 AI 学习
- **主题**: Claude Skills 开发
- **收获**: SKILL.md 结构设计影响触发准确率
- **应用**: daily-log-sync skill 优化

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_synced at 18:30_
```

---

## A2A 结构化字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `tasks_done` | list | 已完成任务，可带 `project` 标签 |
| `tasks_in_progress` | list | 进行中任务，可带 `blockers` |
| `tasks_tomorrow` | list | 明日计划 |
| `ai_learning` | object | AI 学习记录：topic / insight / applied_to |
| `blockers` | list | 汇总所有阻塞项（方便其他 Agent 快速查询） |

---

## 整理原则

用户输入可能很随意，Claude 需要：

1. **提取关键信息**：从口语化描述中提取实际工作内容
2. **分类归纳**：归到 done / in_progress / tomorrow / ai_learning
3. **识别 blockers**：主动识别"等待"、"卡住"、"blocked"等词
4. **关联项目**：尽量识别任务属于哪个项目
5. **简洁表达**：去掉口水话，保留干货

### 示例

**用户说：**
> "今天搞了一天 GitHub 连接，配了 token 跑通了。还看了 skill 文档，学到触发词设计挺重要的。飞书那边还在等审批，明天应该能接上。"

**Claude 生成的结构化数据：**
```python
structured_data = {
    "done": [
        {"content": "配置 GitHub Token 并测试连接", "project": "agent-hub"}
    ],
    "in_progress": [
        {"content": "接入飞书数据源", "blockers": ["等待 API 审批"]}
    ],
    "tomorrow": [
        {"content": "完成飞书集成"}
    ],
    "ai_learning": {
        "topic": "Claude Skills 开发",
        "insight": "触发词设计对 Skill 准确率很重要",
        "applied_to": None
    }
}
```

---

## 推送脚本调用

```python
from scripts.github_sync import push_log

# 基础用法
push_log(
    content="## ✅ 完成\n- 测试成功",
    member_id="kkkaka-oss",
    member_name="Jiahe Gong",
    team="china"
)

# A2A 增强用法
push_log(
    content="## ✅ 完成\n- 配置 GitHub Token\n- 测试连接",
    structured_data={
        "done": [{"content": "配置 GitHub Token", "project": "agent-hub"}],
        "in_progress": [],
        "tomorrow": [{"content": "接入飞书"}],
        "ai_learning": {"topic": "Skills 开发", "insight": "触发词很重要"}
    }
)
```

---

## 环境配置

PowerShell 设置环境变量（永久）：
```powershell
[Environment]::SetEnvironmentVariable("GITHUB_PAT_TEAM_HUB", "ghp_xxx", "User")
```

测试连接：
```powershell
python scripts/github_sync.py test
```

---

## A2A 查询示例

其他 Agent 可以这样查询团队日志：

```python
from scripts.github_sync import pull_team_daily_logs
import yaml

logs = pull_team_daily_logs(team="china", date="2026-01-26")

# 找出所有有 blocker 的人
for member, content in logs.items():
    # 解析 front matter
    if content.startswith("---"):
        _, fm, _ = content.split("---", 2)
        data = yaml.safe_load(fm)
        if data.get("blockers"):
            print(f"⚠️ {member} 被阻塞: {data['blockers']}")
```

---

## 对话示例

**用户**：今天配了 GitHub token 跑通了，学了下 skill 文档，飞书还在等审批

**Claude**：好的，帮你整理成日志：

```markdown
# Jiahe Gong | 2026.01.26 Mon

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ✅ 完成
- 配置 GitHub Token 并测试连接成功

## 🔄 进行中
- 接入飞书数据源
  - ⚠️ blocked: 等待 API 审批

## 📚 AI 学习
- **主题**: Claude Skills 开发
- **收获**: 阅读 Skill 文档，了解触发词设计

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

确认没问题的话，我帮你推送到 GitHub？

**用户**：可以

**Claude**：[执行推送，返回成功链接]

---

## Issue 自动回复

### 检查新问题

```python
from scripts.issue_monitor import check_and_report

# 检查是否有新问题或回复
result = check_and_report()
# 返回: {"new_questions": [...], "new_replies": [...]}
```

### 回复 Issue

```python
from scripts.issue_monitor import reply_to_issue

# 回复指定 Issue
reply_to_issue(
    issue_number=34,
    reply_content="## 我的回复\n\n这是回复内容..."
)
```

### 对话示例

**用户**：有人回复我吗？

**Claude**：[调用 check_and_report() 检查]

发现 1 个新问题：
- Issue #34: Leon 问你关于 AI 助教从 Demo 到生产环境的瓶颈问题

需要我帮你回复吗？

**用户**：帮我回复，我觉得主要是随机性控制没入门

**Claude**：好的，我帮你生成回复：

```markdown
## 🎯 回复 @leon

感谢这个直击灵魂的问题！我的判断是：**随机性控制根本没入门**。

### 为什么不是 Prompt 指令不够多？
...
```

确认没问题的话，我帮你发送？

**用户**：可以

**Claude**：[调用 reply_to_issue() 发送，返回成功链接]

---

## 团队知识检索

### 检查团队日报

```python
from scripts.github_sync import search_team_logs

# 搜索关键词
results = search_team_logs(keyword="Prompt 优化")

# 搜索项目
results = search_team_logs(project="ai-tutor")

# 搜索特定成员
results = search_team_logs(member="Bryce")

# 组合搜索
results = search_team_logs(
    keyword="API 超时", 
    date_from="2026-01-01",
    limit=5
)
```

### 对话示例

**用户**：有人做过 Prompt 优化吗？

**Claude**：[调用 search_team_logs() 搜索]

找到 2 条相关记录：

📋 **kkkaka-oss** (2026-02-02)
- 项目：AI 助教内容生成器
- 内容：精简 SYSTEM_PROMPT 从 440 行到 50 行，处理速度提升 30-50%
- [查看日报](链接)

📋 **佳冉** (2026-01-28)
- 项目：AI 助教策略
- 内容：优化提示词，策略生成准确度提升
- [查看日报](链接)

---

**用户**：Bryce 最近在做什么？

**Claude**：[调用 search_team_logs(member="Bryce") 搜索]

📋 **Bryce** 最近 3 条日报：

1. **2026-01-27** - 贾维斯单词课 2.0 迭代
   - P2/P3 阶段优化
   - 修复错题循环问题
   - [查看日报](链接)

2. **2026-01-26** - ...

3. **2026-01-23** - ...
