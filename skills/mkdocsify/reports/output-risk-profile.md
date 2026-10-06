# 输出风险档案

本 skill 的产物是一个**可运行的 MkDocs 项目**，不是给人读的文档。所以"输出质量"的含义是：用户拿到项目后，能不能不救火就直接 `mkdocs serve`。下面列出这次转换里最可能出错的地方，以及脚本里已经对应的防线。

按「发生概率 × 用户痛苦程度」排序。

## 1. home page 选错文件（高概率 · 中痛苦）

`00-*.md` 被重命名成 `index.md` 是**移动**操作，原文件在源文件夹消失。如果用户的 `00-` 文件其实是正文第一章而不是导读，首页就变成了第一章，而且原文位置没了。

**已设防线**：`index.md` 的选取顺序固定为「已有 index.md > `00-*.md` > `README.md` > 生成」，并优先保留已存在的 `index.md`。日志会打印选用了哪个文件。

**执行时必做**：报告里明确写出 home page 用了哪个源文件。用户说不对，`git reset --hard HEAD~1` 就能退回去。

## 2. 依赖装不上，只交付半成品（高概率 · 高痛苦）

`mkdocs==1.6.11` **不存在于 PyPI**——1.6 系列止于 1.6.1。原样照抄这条 pin，项目 100% 建不起来。

**已设防线**：默认写入 `1.6.1`，在 `requirements.txt` 里留下注释说明改了什么、原值是什么，并提供 `--requirements` 覆盖。装不上时退出码 3，打印重试命令，文件转换部分不回滚。

**残留风险（本次未能验证）**：`mkdocs-shadcn==0.12.1`、`bottle==0.13.4`、`pymdown-extensions==10.15` 三项在本机网络阻断期间**无法逐一确认存在**。它们是按用户原始指定原样写入的，属于「未验证证据」，不是「已验证正确」。真机上第一次跑完请核对 pip 的实际输出。

## 3. `macros` 插件声明了却没装（高概率 · 高痛苦）

`mkdocs.yml` 模板的 `plugins:` 里有 `macros`，但用户给的依赖四件套里没有 `mkdocs-macros`。缺这个插件 `mkdocs build` 直接失败。

**已设防线**：构建前检测 `plugins:` 列表，声明了但 import 不上的自动补装并追加进 `requirements.txt`。

**残留风险**：如果上次是 `--no-venv` 跑的、或补装时网络断开，这一步不会执行。下次重建 venv 时若忘了把 `mkdocs-macros` 留在 `requirements.txt` 里，问题复现。详见 [../references/troubleshooting.md](../references/troubleshooting.md)。

## 4. 双链转换不完整（中概率 · 中痛苦）

`[[...]]` 换成 Markdown 链接有三种不会被处理的情况：目标页不存在（unresolved）、带 `#锚点`（skipped）、多个文件争同一个键（ambiguous）。

**已设防线**：四类分开计数并在日志里分别报告；解析不了的**原样保留**而不是猜一个目标——留着比错链更容易被发现。

**残留风险**：文件名后缀索引会把「日常生活 A Day in the Life」拆成 `a day in the life` / `in the life` / `life` 等多个键，短词可能撞车。日志会报 ambiguous 数量，但不列出具体是哪几条，需要时直接 `grep -n "\[\[" docs/*.md`。

## 5. 未编码链接失效（中概率 · 低痛苦）

文件名含中文和空格。脚本输出百分号编码链接（`01-%E6%97%A5...md`），功能正确但原文难读；用户若手改成未编码形式，mkdocs 可能解析不到。

**已设防线**：编码是刻意选择，见 [../references/conversion-rules.md](../references/conversion-rules.md) 第 5 条；`troubleshooting.md` 给了 `<...>` 尖括号写法作为替代。

## 6. 原地转换毁掉源文件夹（低概率 · 高痛苦）

默认原地跑，文件被移动。

**已设防线**：动文件前先 `git init` + 提交基线，转换后第二次提交，`git reset --hard HEAD~1` 一键回滚。命令行摘要里直接打印这条回滚命令。汇景不明（`--no-git`、或目标已在 git 仓库里）时摘要显示 `n/a`，不会假装有回滚点。

## 7. `site_url` 用了开发端口（低概率 · 低痛苦）

默认 `http://localhost:8081/`，照搬参考项目。本地预览无影响；对外发布时 canonical URL 和 sitemap 会指向错地方。

**已设防线**：`--site-url` 可覆盖，`SKILL.md` 和主题说明里都写明了。

## 自检清单

执行完至少确认这四条，再向用户报告"完成"：

- [ ] `docs/index.md` 存在，且内容是用户预期的那个文件
- [ ] `mkdocs.yml` 的 `theme.name` 是 `shadcn`
- [ ] 依赖装齐（`.venv` 里 `import mkdocs, shadcn` 都通过），或已明确告知未装上的原因
- [ ] `mkdocs build` 通过；没跑就明说没验证
