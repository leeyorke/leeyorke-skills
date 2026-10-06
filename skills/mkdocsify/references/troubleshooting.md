# 排错

按症状查。每条都给出**为什么会这样**和**下一步做什么**。

## 启动阶段就退出（退出码 2）

### `no Markdown files found under <目录>`

源文件夹里没有 `.md`，或者全在被跳过的目录里（`docs/`、`site/`、`.venv/`、`.obsidian/` 等）。

确认一下：`ls <目录>` 看得到 `.md` 吗？如果是 Obsidian 笔记，确认笔记不在 `.trash/` 里。

### `<目录> already looks like a MkDocs project`

目标已经有 `mkdocs.yml` + `docs/`。这是防重复转换的保护。

想刷新 `static/`、`mkdocs.yml`、`.gitignore` 而不重搬文件，加 `--force`。想从头转一遍，先把 `docs/`、`site/`、`mkdocs.yml` 移走。

### `git ... failed`

`git init` / `git add` / `git commit` 任一步失败。检查 `git --version` 能跑；检查目标目录的写入权限；检查是否在一个已有仓库的子目录里且状态异常。

完全不想要 git，加 `--no-git`。

### `no Python 3 interpreter found`

解释器选择顺序：`--python` > `sys.executable` > PATH 上 `python` / `python3` > `py -3`。全都没找到就说这句。

显式指定：`--python D:\software\python\python38\python.exe`。

## 依赖装不上（退出码 3）

### `ERROR: Could not find a version that satisfies the requirement ...`

两种原因，先看 `from versions:` 后面列出来的版本号：

- **`from versions: none`** —— 根本没连上 PyPI。代理或防火墙在挡。这是本机目前的状态，`pip` 会先打几行 `ProxyError` / `Retrying`。解法是恢复网络后重跑 pip，不是改版本号。
- **`from versions: 1.6.0, 1.6.1, ...`** —— 连上了，但你要的版本不存在。这正是 `mkdocs==1.6.11` 的情况。改 `requirements.txt` 或用 `--requirements` 传自己的清单。

### 装上了但 `import shadcn` 失败

`mkdocs-shadcn` 的包名和 import 名不一致，这是正常的。用 `.venv\Scripts\python.exe -c "import shadcn"` 直接验；报 `ModuleNotFoundError` 说明主题包没进这个 venv，检查是否装到了系统 Python。

### `The 'macros' plugin is not installed`

`mkdocs.yml` 的 `plugins:` 里声明了 `macros`，但 venv 里没有 `mkdocs-macros`。脚本本该自动补装并追加进 `requirements.txt`——如果没发生（比如上次是 `--no-venv` 跑的，或补装时网络断了），手动补：

```powershell
.venv\Scripts\python.exe -m pip install mkdocs-macros
```

然后把 `mkdocs-macros` 加进 `requirements.txt` 免得下次重建 venv 又丢。

## 构建失败（退出码 1）

### `Config value 'plugins': The "xxx" plugin is not installed`

同上，看 `mkdocs.yml` 的 `plugins:` 列表，逐个确认 venv 里有对应包。

### `Config value 'theme.name': ... shadcn ...`

`mkdocs-shadcn` 没装上或版本不兼容。先确认 import 得起来，再确认版本满足主题要求。

### 页面 404 / 链接点不动

先确认 `.md` 文件确实在 `docs/` 下而不是项目根。`docs_dir: docs` 之外的 Markdown 不参与构建。

中文或空格文件名的链接：脚本输出的链接是 URL 编码的。如果你手写了未编码的链接 `[x](01-日常生活.md)`，mkdocs 可能解析不到。改成 `[x](<01-日常生活.md>)` 或百分号编码形式。

想 Strict 校验所有链接，把 `mkdocs.yml` 的 `strict` 改成 `true` 再 build，未解析的内部链接会直接报错列出。

### 双链还是 `[[...]]` 原样

三种可能，脚本的日志会告诉你是哪一种：

- **unresolved** —— 目标页面在 `docs/` 里找不到对应文件名。检查 `[[...]]` 里写的名字和文件名后缀是否对得上。
- **skipped** —— 带 `#锚点`，见 [conversion-rules.md](conversion-rules.md) 第 5 条。
- **ambiguous** —— 同一个键被多篇文件名占据，取了一篇。改一下目标文件名让它更唯一。

## 页面看起来不对

### frontmatter 出现在正文里

源文件以 `---` 开头，但 `markdown_extensions` 里没有 `meta`。脚本只在检测到 frontmatter 时才自动加。如果是转换后手动加的前置数据，自己往 `markdown.yml` 的 `markdown_extensions` 里补 `- meta`。

### 公式显示成 `$...$` 原文

模板的 `markdown_extensions` 里没有 `pymdownx.arithmatex`。要用公式：装好 `pymdown-extensions` 后，把 `- pymdownx.arithmatex` 加进列表，并按 KaTeX 官方说明引入 JS。

### logo 不显示

`icon: ./static/logo.svg` 相对 `mkdocs.yml`，不是相对 `docs/`。检查 `docs/static/logo.svg` 存在；若你的 logo 放在别处，改这个相对路径。

## 想撤销

原地转换时脚本在动文件**之前**提交了一条基线：

```powershell
git reset --hard HEAD~1    # 回到原始 Markdown 文件夹
```

前提是那两次提交都成功（脚本日志里会打印 `rollback  : git reset --hard HEAD~1`）。如果日志显示 `n/a (no baseline commit taken)`，说明没拿到回滚点——`--no-git` 跑的、或目标本来就在一个 git 仓库里。
