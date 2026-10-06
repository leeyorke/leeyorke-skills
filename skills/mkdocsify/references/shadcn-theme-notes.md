# shadcn 主题配置说明

本 skill 固定使用 [mkdocs-shadcn](https://pypi.org/project/mkdocs-shadcn/)。配置模板在
`assets/mkdocs.yml`，逐行来自参考项目，**不要随意改**——它是 skill 的输出契约的一部分。

下面只记录模板里每个键的作用和踩过的坑，便于出了问题能定位。

## 站点基础

| 键 | 值 | 说明 |
| --- | --- | --- |
| `site_name` | 文件夹名或 `--name` | 顶栏标题 |
| `site_description` | 生成或 `--description` | meta description |
| `site_url` | `http://localhost:8081/` | 默认照搬参考项目的开发端口。影响 canonical URL 和 sitemap.xml，纯本地预览无所谓；要发布就用 `--site-url` 改成真实域名 |
| `docs_dir` / `site_dir` | `docs` / `site` | 不要改，脚本按这两个路径走 |
| `use_directory_urls` | `true` | 页面 URL 带尾斜杠 |
| `strict` | `false` | 双链告警不升级成构建失败。调成 `true` 可以获得更严格的链接校验，代价是有告警就构建失败 |
| `edit_uri` | `null` | 不显示「编辑此页」按钮 |

## theme 块

- `name: shadcn` —— 固定。
- `show_title: true` —— 顶栏显示站点标题。
- `show_stargazers: true` —— 显示 GitHub stargazers。**只有配了 `repo_url` 才有意义**，模板里没有 `repo_url`，所以这个开关目前不起作用。留着是为了和参考项目保持一致。
- `hide_source_files: false` —— 保留「查看源码 / 复制页面」入口。设 `true` 则不输出 Markdown 源文件。
- `pygments_style` —— 亮/暗两套代码高亮：`shadcn-light` / `github-dark`。
- `icon: ./static/logo.svg` —— **相对 `mkdocs.yml` 所在目录**，不是相对 `docs/`。所以 `static/` 必须同时存在于项目根的引用位置和 `docs/static/`；脚本是把 logo 写进 `docs/static/`，主题按这个相对路径能找到。
- `topbar_sections: false` —— 顶栏不做分组。
- `katex_options.macros` —— KaTeX 宏。模板里 `\RR` / `\dx` 两个示例是从参考项目抄来的。文档不用数学公式的话，这两行可以删掉；注意 `markdown_extensions` 里**没有** `pymdownx.arithmatex`，所以 `$...$` 目前不会渲染成公式，只会原样显示。要用公式必须自己补扩展。
- `show_datetime: false`
- `accent: "oklch(64.5% 0.246 16.439)"` —— 主题强调色，shadcn 默认红的那个值。

## markdown_extensions

```
abbr  attr_list  admonition  footnotes  md_in_html  tables
fenced_code  codehilite  shadcn.extensions.iconify
```

- `codehilite` 和 `fenced_code` 同时开：mkdocs 会处理，围栏代码块走高亮。若还想用 PyMdown 的 `superfences`，装 `pymdown-extensions` 后自行加。
- `shadcn.extensions.iconify` 由 mkdocs-shadcn 提供，用于渲染 iconify 图标。
- `meta` **不在**列表里。源文件带 YAML frontmatter 时脚本会自动补上，见 [conversion-rules.md](conversion-rules.md) 第 6 条。

## plugins

```
search  macros
```

- `search` —— mkdocs 内置，无需安装。
- `macros` —— 来自第三方包 `mkdocs-macros`，**依赖清单里原本没有它**。脚本会检测到「声明了却 import 不上」并自动补装追加进 `requirements.txt`。这就是模板保留 `macros` 的同时脚本要多做一步的原因。
- 没有 `nav` 键：导航由 mkdocs 按 `docs/` 下的文件树自动生成，编号前缀决定顺序。

## extra_css

`static/style.css` 覆盖两处： admonition 里的链接去掉下划线、以及 `.rss*` 一组 RSS 卡片样式。后者在本仓库没有对应内容，属于参考项目遗留，留着不碍事。
