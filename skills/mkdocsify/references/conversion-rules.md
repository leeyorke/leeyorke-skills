# 转换规则与边界情况

`scripts/mkdocsify.py` 的完整行为约定。改脚本前先读这份；改完请同步更新这里。

## 1. 文件收集

- 递归扫描源文件夹下所有 `*.md`，子目录结构在 `docs/` 下原样保留。
- 跳过这些目录：`docs/`、`site/`、`.venv/`、`.git/`、`.obsidian/`、`.trash/`、`__pycache__/`，以及任何以 `.` 开头的中间目录。
- `mkdocs.yml` 如果躺在源文件夹里，不会被当成页面搬走。
- 非 Markdown 文件**不会**被整体搬过去，只搬被 Markdown 引用到的本地图片（见第 4 条）。

## 2. home page 的选取顺序

按优先级，命中即停：

1. 源里已有 `index.md` → 原样保留，原样搬进 `docs/`
2. 有 `00-*.md` → 重命名为 `docs/index.md`
3. 文件名带「导读/说明」类标记的页面 → 重命名为 `docs/index.md`；有多个时取编号前缀最小的
4. 有 `README.md` → 重命名为 `docs/index.md`
5. 都没有 → 用文件列表生成一个最简单的 `index.md`

第 3 条的标记词（不区分大小写，匹配编号前缀剥掉之后的文件名）：

```
说明  导读  介绍  目录  概览  前言  引言  总览
readme  intro  overview  index  guide  about
```

**为什么需要第 3 条**：真实文件夹并不总是用 `00-` 前缀。`01-NGSL 主题阅读说明.md` 就是编号 `01` 的说明页，只有 `00-*.md` 规则的话它会漏掉，首页退化成自动生成的干瘪列表。实测本仓库走的就是这条。

第 2–4 条是**移动**而非复制：原文件在源文件夹里消失，换来 `index.md`。需要保留原文件的场景，先自己备份，或者用 `--out` 走非破坏模式。

## 3. 文件名里的编号前缀

`01-日常生活 A Day in the Life.md` 这类编号前缀会被保留在文件名里，也保留在 URL 里。脚本不会重命名文件——重命名会破坏用户已有的相对路径引用，收益不足以抵消风险。

导航顺序由编号前缀决定，这是 mkdocs 的默认行为，不需要额外配 `nav`。

## 4. 本地图片与附件

只搬**被 Markdown 真正引用到**的本地文件，匹配 `![alt](path)` 形式。规则：

- 以 `http://`、`https://`、`data:`、`#`、`/` 开头的引用跳过（外链或绝对路径）
- 引用路径做了 URL 解码后才去磁盘上找
- 指到源文件夹之外的路径跳过
- 找不到的文件只报数，不报错

`![[图片.png]]` 这种 Obsidian 嵌入语法**不支持**，会被原样留下。附件多的仓库请另写迁移脚本。

## 5. Obsidian `[[双链]]` 重写

这是本 skill 唯一会改动正文内容的地方。默认开启，`--keep-wikilinks` 可关掉。

**匹配规则**—— pages 在 `docs/` 里，每篇按文件名建立索引键。除了完整键之外，还把「按空格切分后的每一个后缀」都登记进去，所以双语文件名能对上只写了英文部分的双链：

```
文件   01-日常生活 A Day in the Life.md
键     "日常生活 a day in the life" / "a day in the life" / "in the life" / ...
双链   [[A Day in the Life]]  →  命中 "a day in the life"
```

查找时用双链自身的最长后缀优先，同一个键被多篇占据时取精确匹配那篇；仍冲突则取字母序第一篇并计入 ambiguous。

**四种情况分开处理：**

| 写法 | 处理 |
| --- | --- |
| `[[A Day in the Life]]` | 转成 `[A Day in the Life](01-%E6%97%A5%E5%B8%B8%E7%94%9F%E6%B4%BB%20A%20Day%20in%20the%20Life.md)` |
| `[[The Shape of a City\|城市这篇]]` | 转成 `[城市这篇](03-...md)`，别名成为链接文字 |
| `[[A Day in the Life#开头]]` | 原样保留，计入 skipped |
| `[[不存在的页面]]` | 原样保留，计入 unresolved |

带 `#锚点` 的跨页链接不转：锚点 slug 依赖目标页渲染后的标题文本，不渲染就无法可靠推断，硬猜比留着更糟。

链接里的文件名做了 URL 百分号编码，空格和中文都编码。这是有意为之——未编码的空格在部分 Markdown 实现里会截断链接。副作用是原文可读性变差，但转换是一次性动作，改完只在 `docs/` 里。

## 6. 生成的配置文件

`mkdocs.yml` 来自 `assets/mkdocs.yml` 模板，只替换三处：`{{site_name}}`、`{{site_description}}`、`{{site_url}}`。主题部分一行不动——这是 skill 的固定契约。

如果源文件里检出 YAML frontmatter（`---` 开头），会往 `markdown_extensions` 里插一个 `meta`。没有 frontmatter 就不插。原因：模板里没开 `meta`，mkdocs 会把 frontmatter 那几行当成正文渲染。

`.python-version` 固定写入 `3.8.5`（一行，带换行结尾），不做探测、不给选项——保持和主题一样是固定契约。它只影响 pyenv / mise / uv 这类会读该文件的版本管理器，脚本自己建 venv 时仍走第 8 节的解释器选择顺序。

## 7. git 行为

- 需要 PATH 上有 `git`；没有就跳过并告警，不视为失败。
- `git init -b main`，老版本 git 不支持 `-b` 时退回 `git init`。
- **原地转换**时，动文件之前先提交一次「Original Markdown folder (pre-mkdocsify)」作为基线，转换完再提交一次。回滚：`git reset --hard HEAD~1`。
- `--out` 模式不碰源文件夹，只在新目录里提交一次。
- 目标已有 `.git` 时（`--force` 刷新）不再取基线，避免把上一次的转换状态也当成"原始状态"提交进去。
- 没有 git 身份时，给仓库配一个 local 的 `mkdocsify <mkdocsify@localhost>` 再提交，保证基线一定存在。

## 8. 虚拟环境与依赖

- 解释器选择顺序：`--python` 指定 > `sys.executable` > PATH 上的 `python` / `python3` > Windows 的 `py -3`。
- 虚拟环境建在 `<项目>/.venv`，只认 Python 3。
- 依赖来自 `requirements.txt`：默认用内置固定四件套，`--requirements FILE` 可换成自己的。
- `mkdocs.yml` 的 `plugins:` 里声明了但 venv 里 import 不上的插件，会补装并追加进 `requirements.txt`。`search` 和 `shadcn.extensions.iconify` 视为内置，不处理。
- 装不上不中断已完成的文件转换，退出码 3，并打印重试命令。

## 9. 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 全部完成，构建通过 |
| 1 | 文件转换完成，但 `mkdocs build` 失败 |
| 2 | 启动前失败：源文件夹不存在、里面没有 Markdown、目标已是 mkdocs 项目而未加 `--force`、git 操作失败、找不到 Python 3 |
| 3 | 文件转换完成，但依赖安装失败（多为网络问题） |
