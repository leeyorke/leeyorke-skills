## user

```text
config.json配置为 "personal_secretary": {
      "data_dir": "/mnt/d/myfile/Obsidian repo/",
      "auto_classify_delay": 5,
      "remind_time_morning": "08:00",
      "remind_time_evening": "21:00"
    }

为啥还是给我保存到/home/leeyorke/.nanobot/workspace/personal-secretary/01-Inbox？
```

## AI

```text
问题在于：Agent 根本没有调用 yoyo 的 handle()，而是自己用 glob + write_file   工具直接写的。

  看日志流程：
  1. glob 搜索 inbox 目录 → 搜的是 /home/leeyorke（默认路径）
  2. read_file 读 inbox_operations.py 和 helpers.py（理解结构）
  3. write_file 写到 /home/leeyorke/.nanobot/workspace/personal-secretary/01-Inbox/

  Agent 绕过了 yoyo 的 handle()，自己用工具操作。

  原因：Agent 的 system prompt 里可能没有明确要求调用 yoyo skill，或者 yoyo skill   没被激活。

  需要检查：
  1. nanobot 的 agent loop 是怎么决定何时调用 skill 的 handle() 的
  2. yoyo 的 SKILL.md 是否被正确加载

  让我看一下 agent loop 怎么调 skill：

  Searched for 1 pattern, read 1 file

问题是 handle() 返回了但 Agent 没用它。让我看看 InboxOperations 怎么获取 data_dir：

  Searched for 3 patterns, read 1 file

问题在于 handle() 返回结果后 Agent 没有用它，而是自己调用工具处理。

  根本原因可能是 yoyo 的 handle() 在执行时出错被静默捕获了（见 loop.py:621 的 except   Exception），导致返回 None，然后 Agent 就用自己工具处理了。

  让我加个日志确认下。先直接测试：

  Ran 1 bash command

找到问题了！

  config 是 Pydantic 模型，不是 dict，但 first_check 里用 config.get("personal_secretary")   —— Pydantic 模型没有 .get() 方法！

  这就是为什么 handle() 会抛异常，被 loop.py 静默捕获后返回 None，然后 Agent   用自己的工具处理了。
```