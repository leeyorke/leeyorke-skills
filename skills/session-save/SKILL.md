---
name: session-save
description: 保存当前Claude Code会话的对话历史到markdown文件。触发场景：用户输入/session-save命令、要求保存对话历史、记录学习笔记时使用。
---

# /session-save 命令使用说明
## 功能
自动将当前会话中的用户提问和Claude回答保存到新的markdown文件中，用于记录学习笔记、项目对话历史。

## 保存规则
1. **文件名**：总结当前对话主题，生成一个合适的文件名，如 `架构问题解决.md`。
2. **保存格式**：见文件模板: [template.md](./assets/template.md)。
3. **保存位置**：项目根目录的 `.learn/` 文件夹下面。。
