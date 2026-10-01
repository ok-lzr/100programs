================================================================================
项目编号：058                    难度等级：★★★☆☆（中型项目）
项目名称：静态博客生成器
所属分类：内容生成 / 站点构建
建议工时：3 ~ 4 天
运行环境：Python 3.10+    第三方依赖：jinja2、markdown（或 markdown-it-py）、Pygments
================================================================================

【一、项目背景与目标】

用 Markdown 写博客的好处是内容与展示分离，坏处是必须自己处理模板、分页、标签页、
归档页、RSS、站内搜索索引、代码高亮这一整套“站点基础设施”。本项目就是把这套
基础设施做出来：源目录放 Markdown 与模板，运行一条命令，输出一个可以直接上传到
任何静态托管（GitHub Pages、对象存储、Nginx 目录）的 dist/ 目录。

目标用户是想要完全掌控自己博客的技术写作者：他们希望文章是纯文本、可版本控制、
可全文检索，构建过程可重复、可增量，不希望依赖数据库或动态服务器。

项目难点在于：内容模型的设计（文章、草稿、独立页面）、URL 与永久链接策略、
分页与标签交叉组合的路径生成、增量构建的依赖判定，以及 RSS 与站点地图的
规范正确性（RSS 的日期格式、转义、绝对 URL 要求）。

【二、功能需求清单】

1. 核心功能
   1.1 内容加载（load）：扫描 content/ 下所有 .md 文件，解析 YAML 风格的
       front matter（title、date、updated、tags、categories、slug、draft、
       summary、cover、layout、permalink）；草稿默认不参与构建。
   1.2 Markdown 渲染（render）：转换为 HTML，支持标题、列表、表格、引用、
       代码块（带语言标记）、行内代码、链接、图片、脚注、删除线；
       生成标题锚点 id 并输出该文章的目录（TOC）。
   1.3 模板渲染（template）：用 jinja2 渲染首页、文章页、标签页、分类页、
       归档页、关于页、404 页；模板可继承 base.html 并支持 partial 片段。
   1.4 站点结构生成（build）：按 URL 策略生成 index.html、page/2/index.html、
       posts/<slug>/index.html、tags/<tag>/index.html、
       categories/<cat>/index.html、archives/2024/index.html。
   1.5 分页（paginate）：首页与标签页支持每页 N 篇（默认 10）的分页，
       生成上一页/下一页链接与页码列表（当前页附近 ±2 页，其余用省略号）。
   1.6 RSS 与 Sitemap（feed）：生成 feed.xml（RSS 2.0，含 channel 与 item 的
       title/link/guid/pubDate/description/content:encoded），以及 sitemap.xml
       与 robots.txt。
   1.7 静态资源处理（assets）：复制 static/ 下的 CSS、JS、图片到 dist/，
       计算文件内容哈希并写入 manifest.json 用于缓存失效；
       可选压缩：去掉 CSS 注释与多余空白。
   1.8 增量构建（incremental）：只重建内容或模板发生变化所影响的输出文件；
       用 sources.json 记录“输出文件 ← 依赖文件集合与哈希”，未变化则跳过。
   1.9 本地预览（serve）：启动 http.server 提供 dist/ 预览，支持 --watch
       轮询检测源文件变化并自动重建，支持 --port 与 --open。
   1.10 校验（check）：检查重复 slug、无效内部链接、缺失图片、未闭合代码块、
        日期格式错误、未来日期草稿，输出问题清单与退出码。

2. 输入与交互
   2.1 命令形如：
       `python -m blog build --source content --templates templates --out dist`
       `python -m blog new "我的第一篇博客" --tags python,工具`
       `python -m blog serve --port 8080 --watch`
   2.2 `new` 会按当前日期生成 content/YYYY/MM/<slug>.md 并写入 front matter 骨架。
   2.3 支持站点配置 config.json / config.yaml：站点名、副标题、作者、基础 URL
       （base_url 必填且用于 RSS 绝对链接）、每页文章数、时区、语言、
       主题名、社交链接、导航菜单。
   2.4 支持 `--drafts` 在本地预览中包含草稿；`--future` 包含未来日期的文章。
   2.5 支持 `--clean` 先清空输出目录；默认保留 dist/ 下无关文件（如 CNAME）。

3. 输出与展示
   3.1 构建日志输出：读取文章数（含草稿标记）、渲染页数、复制资源数、
       耗时、输出目录体积、增量跳过的文件数。
   3.2 文章页包含：标题、日期、更新日期、作者、标签链接、分类、阅读时长
       （按 300 字/分钟估算，中英文分别计权）、TOC、上一篇/下一篇导航、
       相关文章（同标签最多 5 篇）。
   3.3 首页包含：分页文章列表（标题、日期、摘要、标签）、站点侧栏
       （标签云、归档链接、最近文章）。
   3.4 生成的 HTML 使用语义化标签（article、nav、time、footer），
       每页含 canonical 链接与 Open Graph 基本标签。

4. 异常与边界处理
   4.1 front matter 格式错误（缺少结束的 ---）：报错并指出文件与行号，跳过该文件。
   4.2 date 缺失：使用文件 mtime 并在日志中告警；date 格式非法：跳过并报错。
   4.3 标题重复导致 slug 冲突：追加 -2、-3 并告警，保证 URL 唯一。
   4.4 内部链接指向不存在的文章：check 报告为错误，build 时渲染为普通文本
       并加 class="broken-link"，不使构建失败。
   4.5 图片路径不存在：check 报错；build 时保留原样并告警。
   4.6 模板渲染异常（变量缺失）：捕获并报出模板名与出错行，退出码 1。
   4.7 base_url 未配置：build 成功但 feed.xml 中的链接使用相对路径并输出
       醒目警告“RSS 需要绝对 URL，请配置 base_url”。
   4.8 输出目录不存在或不可写：自动创建；不可写时报错退出码 3。
   4.9 内容为空（无文章）：生成空首页与空 feed（合法 XML），退出码 0。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：
   2.1 第三方：jinja2（模板）、markdown 或 markdown-it-py（Markdown 渲染）、
       Pygments（代码高亮，可在模板中配合使用）。
   2.2 标准库：argparse、json、hashlib、pathlib、shutil、datetime、
       email.utils（生成 RFC 2822 日期）、xml.sax.saxutils（XML 转义）、
       http.server、threading、re、unicodedata、logging、dataclasses、
       html（HTML 转义）、urllib.parse。
   2.3 明确要求：front matter 解析、分页逻辑、URL 生成、增量依赖记录
       必须自己实现；不允许用 yaml 库之外再引入站点生成框架。
3. 禁止事项：禁止用字符串拼接生成 HTML 主体（必须走模板）；
   禁止用正则替换来实现 Markdown 渲染；禁止在输出中留下未转义的用户内容
   （jinja2 必须保持 autoescape=True）；禁止把绝对路径写进生成的 HTML。
4. 代码组织：
   - `config.py`：站点配置加载与默认值、校验。
   - `frontmatter.py`：front matter 解析与序列化。
   - `content.py`：内容加载、日期解析、slug 生成与去重、阅读时长估算。
   - `markdown_render.py`：Markdown 配置、锚点注入、TOC 提取、
     内部链接解析与改写。
   - `urls.py`：永久链接与各类索引页 URL 生成策略。
   - `pagination.py`：分页计算。
   - `builder.py`：构建流程编排、增量判定、依赖记录（核心）。
   - `feed.py`：RSS、sitemap、robots 生成。
   - `assets.py`：静态资源复制、哈希与 manifest。
   - `server.py`：预览服务器与 watch 循环。
   - `checker.py`：内容校验。
   - `cli.py`：命令行入口。
5. 编码规范：全部函数带类型注解；构建产物写入前先写临时目录再替换，
   避免半成品 dist；日志分级（info 显示进度，debug 显示每个输出文件）。

【四、设计要点】

1. 数据结构

   1.1 文章对象 Post（dataclass）
       source_path : Path          源文件绝对路径
       rel_path    : str           相对 content/ 的 POSIX 路径
       title       : str
       date        : datetime      发布日期（带时区，来自 config.timezone）
       updated     : datetime | None
       tags        : list[str]
       categories  : list[str]
       slug        : str           URL 片段（唯一）
       draft       : bool
       summary     : str           摘要（front matter 指定，否则取正文首段）
       cover       : str | None
       layout      : str           使用的模板名，默认 post.html
       permalink   : str | None    自定义永久链接（覆盖默认策略）
       body_md     : str           正文 Markdown（不含 front matter）
       html        : str           渲染后正文 HTML
       toc         : list[TocItem] 目录项（level、text、anchor）
       reading_min : int           估算阅读时长
       word_count  : int
       out_path    : Path          输出文件路径

   1.2 站点级数据结构
       SiteIndex：posts（按日期倒序）、tags（name → post_ids）、
       categories（name → post_ids）、archives（year → month → post_ids）、
       pages（独立页面）、prev_next（post_id → (prev, next)）
       BuildManifest：{"outputs": {"dist/posts/x/index.html":
       {"deps": ["content/x.md", "templates/post.html"],
        "hashes": {"content/x.md": "ab12…", "templates/post.html": "cd34…"}}}}

   1.3 输出的站点目录结构
       dist/
         index.html, page/2/index.html, ...
         posts/<slug>/index.html
         tags/<tag>/index.html, tags/<tag>/page/2/index.html
         categories/<cat>/index.html
         archives/2024/index.html, archives/2024/05/index.html
         about/index.html, 404.html
         feed.xml, sitemap.xml, robots.txt
         static/css/site.<hash>.css, static/js/site.<hash>.js
         manifest.json

2. 关键算法或流程

   2.1 front matter 解析：
       文件必须以 `---` 开头（允许前导 BOM 与空行）；找到第二处 `---` 作为
       结束；中间按行解析 `key: value`；值支持字符串、`[a, b]` 数组、
       裸数字、true/false 与 ISO 日期；`#` 开头的行为注释。
       解析失败抛出 FrontMatterError(带行号) 由调用方记录并跳过该文件。

   2.2 阅读时长估算：
       cjk_chars = 正则统计 [\u4e00-\u9fff] 字符数；
       words = 正则统计 ASCII 单词数；
       reading_min = max(1, round(cjk_chars / 400 + words / 220))。

   2.3 URL 策略（urls.py）：
       默认文章链接 = `{base_url}/posts/{slug}/`；
       若 front matter 指定 permalink 则优先使用；
       标签页 = `/tags/{safe(tag)}/`，分类页 = `/categories/{safe(cat)}/`；
       safe() 规则：小写化 → 空格换 `-` → 中文保留（URL 编码交给模板的
       filters 处理）→ 去掉 `/` 与 `?` 等保留字符。
       生成的所有站内链接统一走 `make_url(path)`，集中处理 base_url 前缀，
       确保 --serve 时可用相对路径、部署时可用绝对路径。

   2.4 分页计算（pagination.py）：
       total_pages = ceil(len(items) / per_page)，至少为 1；
       当前页校验在 [1, total_pages] 范围内，越界返回 404 内容；
       页码列表：始终显示第 1 页与最后一页，当前页 ±2，间隔用 None 表示省略号，
       模板中渲染为 `…`；上一页/下一页在第 1 页与最后一页分别为 None。

   2.5 增量构建（builder.py）：
       步骤一，计算输入依赖图：每个输出文件登记其依赖的源文件列表
       （文章页依赖该 .md + 模板 + config + 该文章引用的 partial）；
       步骤二，对所有依赖文件计算 sha256（小文件直接哈希，大文件按内容哈希，
       不使用 mtime 以避免 checkout 导致的误判）；
       步骤三，与上次 manifest 比对：全部依赖哈希一致则跳过该输出文件；
       步骤四，模板或 config 变更视为全局失效（重建所有页面）；
       步骤五，新增/删除文章会额外导致首页、标签页、归档页、feed 失效，
       这部分通过“集合型依赖”表达（deps 中包含 __index__ 伪依赖，
       其哈希 = 全部文章 (slug, date, tags) 列表的哈希）；
       步骤六，构建结束写回新的 manifest.json，并清理 dist 中已无对应源文件的
       陈旧输出（输出清单差集）；
       步骤七，--clean 时忽略 manifest 全量重建。

   2.6 TOC 与锚点注入：
       在 Markdown 渲染前用正则扫描 ATX 标题行 `^(#{1,6})\s+(.*)$`；
       生成锚点：标题文本 NFKC 归一化 → 小写 → 非字母数字与中文替换为 `-`
       → 去首尾 `-`；重复锚点追加 `-1`、`-2`；
       渲染后把 `<h2>` 等标签注入 `id="anchor"`，并用嵌套列表生成 TOC HTML。

   2.7 RSS 2.0 生成（feed.py）：
       channel：title、link（base_url）、description、language、
       lastBuildDate（最新文章时间，RFC 2822）、generator；
       item：title、link（绝对 URL）、guid（isPermaLink="true" 使用绝对 URL）、
       pubDate（RFC 2822，用 email.utils.format_datetime）、
       description（summary 或正文前 300 字，HTML 转义）、
       content:encoded（完整 HTML，需要声明命名空间
       xmlns:content="http://purl.org/rss/1.0/modules/content/"）、
       category（每个标签一项）；
       全部文本用 xml.sax.saxutils.escape 转义，日期统一转为 UTC 输出；
       输出为 UTF-8，文件头声明 `<?xml version="1.0" encoding="UTF-8"?>`。
       sitemap.xml 每项含 loc、lastmod、changefreq（首页 daily，文章 monthly）、
       priority（首页 1.0，文章 0.8，标签页 0.5）。

3. 接口或命令设计

   new TITLE [--tags a,b] [--categories c] [--date D] [--draft] [--dir 2024/05]
   build [--source content] [--templates templates] [--out dist]
         [--config config.json] [--drafts] [--future] [--clean] [--verbose]
   serve [--port 8080] [--watch] [--interval 2] [--open] [--drafts]
   check [--source content] [--strict] [--json]
   clean [--out dist] [--all]      （--all 连同 manifest 一起清理）
   list [--drafts] [--tag T] [--json]

   函数签名：
   def load_posts(source: Path, cfg: Config, include_drafts: bool,
                  include_future: bool) -> list[Post]
   def parse_front_matter(text: str, path: Path) -> tuple[dict, str]
   def render_markdown(body: str, cfg: Config) -> tuple[str, list[TocItem]]
   def paginate(items: list[Post], page: int, per_page: int) -> PageView
   def build_site(cfg: Config, posts: list[Post], manifest: BuildManifest,
                  incremental: bool) -> BuildReport
   def generate_feed(cfg: Config, posts: list[Post]) -> str
   def check_site(posts: list[Post], cfg: Config) -> list[Issue]

【五、运行方式与示例】

安装：
  cd C:\projects\100programs\058_static_blog_gen
  pip install jinja2 markdown pygments

示例一（新建文章并构建）：
  输入：python -m blog new "用 SQLite FTS5 做全文检索" --tags python,db
  输出：已创建 content\2024\05\用-sqlite-fts5-做全文检索.md（骨架已写入 front matter）
  输入：python -m blog build
  输出：
        读取文章 32 篇（草稿 2 篇已跳过）
        渲染页面 58 个（首页 4 页，标签页 12 个，归档页 9 个）
        复制资源 7 个，生成 feed.xml（32 项）、sitemap.xml（58 项）
        输出 dist/ 共 3.4 MB，增量跳过 41 个文件，耗时 1.9 s

示例二（增量构建与预览）：
  输入：python -m blog build
  输出：读取文章 32 篇；增量跳过 57 个文件，重建 1 个（posts/用-sqlite-fts5-做全文检索/index.html 及其索引页）
  输入：python -m blog serve --port 8080 --watch
  输出：预览地址 http://127.0.0.1:8080/（Ctrl+C 退出）；监听 content/ 与 templates/ 变化…

示例三（校验与异常输入）：
  输入：python -m blog check --strict
  输出：
        [错误] content/2024/03/旧文.md: 内部链接 "posts/不存在" 指向不存在的文章
        [错误] content/2024/04/重复.md: slug "hello-world" 与 hello.md 冲突（已改为 hello-world-2）
        [告警] content/2024/05/无日期.md: 缺少 date，已使用文件修改时间
        [告警] content/2024/05/图片缺失.md: 图片 static/img/a.png 不存在
        共 4 个问题（2 错误 2 告警）                            （退出码 1）
  输入：python -m blog build --config config_missing.json
  输出：错误：配置文件不存在：config_missing.json               （退出码 3）

【六、验收标准】

[ ] 对含 30 篇样例文章的 content/ 执行 build，dist 结构与本文档第 1.3 节一致。
[ ] 首页每页文章数等于配置的 per_page，页数等于 ceil(文章数 / per_page)。
[ ] 分页页码列表包含第 1 页与最后一页，中间用省略号，当前页高亮标记。
[ ] 标签页文章数与 search 该标签的文章数一致；空标签不生成页面。
[ ] 草稿在默认 build 中不出现，加 --drafts 后出现且带“草稿”标记。
[ ] 未来日期文章默认不出现，加 --future 后出现。
[ ] 文章页的 TOC 链接可点击跳转到对应标题，锚点无重复。
[ ] 代码块按语言高亮，HTML 中的代码内容被正确转义（`<script>` 显示为文本）。
[ ] 生成的 HTML 中用户内容全部转义，注入 `<script>alert(1)</script>` 不产生脚本。
[ ] feed.xml 通过 XML 解析器校验（xml.etree 可解析），pubDate 为合法 RFC 2822。
[ ] feed.xml 中所有 link 与 guid 都是绝对 URL（配置 base_url 后）。
[ ] sitemap.xml 中的 URL 数量等于生成的 HTML 页面数。
[ ] 第二次 build 在无改动时重建文件数为 0（全量跳过）。
[ ] 修改一篇文章后 build，只有该文章页与相关索引页被重建。
[ ] 修改 base.html 模板后 build，全部页面被重建。
[ ] static/ 资源复制后文件名含内容哈希，manifest.json 内容与实际文件一致。
[ ] check 能发现重复 slug、断链、缺图、缺日期四类问题并给出文件与行号。
[ ] serve --watch 在保存 .md 后 2 秒内自动重建并可通过浏览器刷新看到更新。

【七、可选扩展】

1. 增加站内搜索：生成静态 JSON 索引 + 纯前端过滤（不引外部 JS 库）。
2. 增加暗色主题与响应式 CSS，模板中提供主题切换按钮。
3. 增加系列文章（series）与“上一篇/下一篇同系列”导航。
4. 增加文章加密（口令保护单篇），静态端仍可用简单混淆方案。
5. 增加图片处理：自动生成响应式缩略图（Pillow）与 srcset。
6. 增加部署命令：一键 rsync 到服务器或生成 GitHub Pages 工作流文件。

【八、涉及知识点】

- 静态站点生成原理：内容 + 模板 → 输出，URL 设计与永久链接策略。
- jinja2：模板继承（extends/block）、include、宏、过滤器、autoescape 与安全。
- Markdown 渲染：扩展语法、代码高亮、锚点注入与 TOC 提取。
- 分页算法：总页数、边界页、页码窗口与省略号。
- RSS 2.0 与 Sitemap 规范：RFC 2822 日期、XML 转义、绝对 URL 与命名空间。
- 增量构建：依赖图建模、内容哈希比对、集合型依赖与陈旧产物清理。
- 文件系统操作：pathlib、原子写、目录树复制、manifest 管理。
- 静态资源缓存策略：内容哈希文件名与 manifest.json。
- 本地开发服务器：http.server、目录索引、轮询式文件监听。
- 内容质量工程：链接校验、slug 冲突处理、front matter 健壮解析。
================================================================================
