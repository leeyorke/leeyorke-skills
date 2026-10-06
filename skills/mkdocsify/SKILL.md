---
name: mkdocsify
description: 把一个文件夹里的 Markdown 文件转换成一套可立即构建的 MkDocs 项目：docs/ 目录 + static 资源 + mkdocs.yml（固定 shadcn 主题）+ requirements.txt 固定版本依赖 + .gitignore + git init 双层提交 + Python 虚拟环境。当用户说「把这些 md 做成 mkdocs 站点/项目」「用 mkdocs 发布这个文件夹」「转成 mkdocs」时使用。不要用于：往已有 mkdocs 项目里增删内容、配 CI 部署到 GitHub Pages/Netlify、把整个 Obsidian 仓库迁移、Hugo/VuePress/Docusaurus 等其他静态站生成器。
metadata:
  version: 0.0.1
  requires:
    bins:
      - python
---

# MKdocsify · Markdown 文件夹 → MkDocs 项目

一个文件夹进去，一个能 `mkdocs serve` 的项目出来。

主题固定 `shadcn`。这不是可配置项——本 skill 的存在意义就是把一套**已经商定好的技术栈**变成可重复执行的固定动作。想换主题，不要改这个 skill，去改 `assets/mkdocs.yml` 里被复制出去的那份配置。

## 什么时候用

- 把一个平铺的 Markdown 文件夹（Obsidian 笔记导出、文章合集、手册草稿）变成一个带侧边栏导航的文档站点
- 项目已经建好了，但 `docs/`、`mkdocs.yml`、虚拟环境或 git 初始化漏了一步，需要补齐
- 同样的转换要做第二遍、第三遍（换一批文件、换一个文件夹）

## 什么时候不要用

- **不是**给已有 mkdocs 项目加页面、改导航、调样式——那是内容编辑，直接改文件
- **不是**配 GitHub Actions / Pages / Netlify 部署流水线
- **不是**迁移整个 Obsidian vault（附件、双链、块引用都需要另一套规则）
- **不是** Hugo、VuePress、Docusaurus、VitePress 等其他生成器
- 只转换一两个文件的一次性请求——直接手写更快

## 执行步骤

先看一遍再动手。默认是**原地转换**（把源文件夹变成 mkdocs 项目），这一步会移动文件，因此在真正改动之前脚本会先做一次 git 基线提交作为回滚点。

```powershell
python "C:\Users\leeyorke\.claude\skills\mkdocsify\scripts\mkdocsify.py" <源文件夹> [选项]
```

常用选项：

| 选项 | 作用 |
| --- | --- |
| `--name "站点名"` | 写入 `mkdocs.yml` 的 `site_name`，默认取文件夹名 |
| `--out DIR` | **不碰源文件夹**，把项目写到另一个目录（做试验时用这个） |
| `--site-url URL` | `site_url`，默认 `http://localhost:8081/` |
| `--requirements FILE` | 用自己的依赖清单，不用内置固定版本 |
| `--force` | 目标已经是 mkdocs 项目时，刷新 `static/`、`mkdocs.yml`、`.gitignore` |
| `--no-build` | 跳过 `mkdocs build` 验证（默认会构建一次） |
| `--python PATH` | 指定用来建虚拟环境的解释器 |
| `--keep-wikilinks` | 不把 Obsidian `[[双链]]` 转成普通链接 |

跑完后必须向用户报告四件事：**home page 用的哪个文件**、**多少个双链被转换/没转换上**、**有没有报错**、**怎么启动**（`.venv\Scripts\python.exe -m mkdocs serve`）。

## 它到底做了什么

1. `docs/` 下收集所有 `*.md`（子目录结构保留）
2. 生成 home page：已有 `index.md` 优先；否则 `00-*.md`；否则文件名带「说明/导读/intro」这类导读标记的页面（编号最小者）；否则 `README.md`；都没有就从文件列表生成一个
3. 复制 `docs/static/{logo.svg, style.css}`
4. 把 Markdown 里引用的本地图片一并搬进 `docs/`
5. 把 Obsidian `[[双链]]` 重写成 MkDocs 相对链接（按文件名匹配，兼容 `01-日常生活 A Day in the Life.md` ↔ `[[A Day in the Life]]`）
6. 写出 `mkdocs.yml`（shadcn 主题，来自 `assets/mkdocs.yml` 模板）
7. 写出 `requirements.txt` 和 `.gitignore`
8. `git init`，先提交原始文件夹作为基线，转换完再提交一次
9. 建 `.venv`，装固定版本依赖，补装 `mkdocs.yml` 里声明但没装的插件
10. `mkdocs build --clean` 验证一遍

细节、边界情况、已知坑见 [references/conversion-rules.md](references/conversion-rules.md)，
shadcn 主题的配置项和排错见 [references/shadcn-theme-notes.md](references/shadcn-theme-notes.md)，
装了但跑不起来见 [references/troubleshooting.md](references/troubleshooting.md)。

## 固定版本与一个必须知道的问题

内置 `requirements.txt` 是这四行：

```
mkdocs==1.6.1          # 原先指定 1.6.11 —— 该版本在 PyPI 不存在，1.6 系列止于 1.6.1
mkdocs-shadcn==0.12.1
bottle==0.13.4
pymdown-extensions==10.15
```

**`mkdocs 1.6.11` 不存在**（Live 查询 PyPI 确认：1.6.x 最高 1.6.1）。脚本默认写入可安装的 `1.6.1`，并在文件里留下注释说明改了什么。要覆盖就传 `--requirements`。另外三项（`mkdocs-shadcn 0.12.1`、`bottle 0.13.4`、`pymdown-extensions 10.15`）本机网络不稳定，**本次未能逐一验证**，按原样写入。

生成的 `mkdocs.yml` 里声明了 `macros` 插件但依赖清单里没有它，所以脚本会额外一步：发现声明了却装不上的插件就自动补装并追加进 `requirements.txt`。

## 输出契约

一次成功的执行应该交付：

- 一个 `docs/` 目录，`index.md` 是首页，`static/` 有 logo 和样式
- 根目录 `mkdocs.yml`（主题 `shadcn`）、`requirements.txt`、`.gitignore`
- 一个 `.venv/`，里面装着能跑的四件依赖
- 一个 git 仓库，至少一条提交；原地转换时有两条（基线 + 转换后）
- 一个通过 `mkdocs build` 的 `site/`

任何一项没达成，就不要向用户说"完成了"。输出质量上的已知风险见 [reports/output-risk-profile.md](reports/output-risk-profile.md)。
