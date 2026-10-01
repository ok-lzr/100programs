================================================================================
项目编号：059                    难度等级：★★★☆☆（中型项目）
项目名称：终端 RSS 阅读器
所属分类：内容采集 / 命令行应用
建议工时：2 ~ 4 天
运行环境：Python 3.10+    第三方依赖：feedparser（RSS/Atom 解析）、requests（可选）
================================================================================

【一、项目背景与目标】

RSS 是少数还由用户完全掌控的信息获取方式：没有推荐算法，没有信息流广告，
订阅什么就看什么。但现代浏览器陆续取消了原生 RSS 支持，网页版阅读器又需要
账号，于是“在终端里读 RSS”成了一个非常实用的方案：一条命令看到所有未读，
用键盘翻页阅读摘要，标记已读，需要时再用浏览器打开原文。

本项目实现一个终端 RSS 阅读器：管理订阅源（分类、启用/停用、抓取间隔），
定时抓取并解析 RSS 2.0 与 Atom，按 guid 与标题+链接双规则去重入库，
以列表和详情两种视图展示，支持已读/收藏标记、按源与标签过滤、
关键词搜索与 OPML 导入导出。整个程序只用标准库 + feedparser，数据存本地 SQLite。

目标用户是每天需要跟踪几十个技术博客与新闻源的开发者。项目难点在于：
不同源的时间格式与 guid 规则差异很大（有的用链接、有的用自增 ID、
有的缺 pubDate）、编码混乱（GBK 与 UTF-8 混用）、
以及在终端里做出可读的排版（中文宽度对齐、长文本折行、分页浏览）。

【二、功能需求清单】

1. 核心功能
   1.1 订阅源管理（feed add/remove/list/enable/disable）：
       支持直接给 URL 或站点主页（自动发现 `<link rel="alternate"
       type="application/rss+xml">`）；记录标题、站点链接、描述、语言、
       分类、抓取间隔、上次抓取时间、连续失败次数。
   1.2 抓取（fetch）：并发抓取所有启用的源（默认 8 个线程），
       尊重每条源的抓取间隔（默认 60 分钟，可用 feed edit --interval 覆盖）；
       支持 `fetch --feed ID`、`fetch --all --force` 强制刷新。
   1.3 解析与入库（parse/store）：解析 RSS 2.0、Atom 1.0 与 RDF；
       提取标题、链接、作者、发布时间、摘要、正文（若 feed 提供）、
       分类、附件（enclosure）与封面图；缺失字段按规则兜底。
   1.4 去重（dedupe）：优先用 entry 的 id/guid；缺失时用链接的规范化形式
       （去 utm_* 等跟踪参数、去末尾斜杠、统一小写 scheme 与 host）；
       再缺失时用 “标题 + 源 ID” 的哈希；同一源内重复直接跳过，
       不同源出现同一链接时保留先入库者并记录 duplicate_of。
   1.5 阅读视图（list/show）：列表视图显示序号、源、标题、时间、
       已读标记、收藏标记；详情视图分页显示摘要或正文，
       支持 n（下一条）、p（上一条）、o（浏览器打开）、s（收藏）、
       m（标记已读）、q（退出）等单键操作。
   1.6 过滤与搜索（filter/search）：按源、分类、已读状态、收藏状态、
       时间范围过滤；关键词在标题与摘要中检索（SQLite LIKE，
       数据量超过 5 万条时切换 FTS5）；支持只显示未读的默认视图。
   1.7 标记（read/star）：标记单条或多条已读/未读、加星/取消星；
       `read --all --before 2024-05-01` 批量标记历史已读。
   1.8 OPML 导入导出（opml）：导出全部订阅源为标准 OPML 2.0
       （含分类嵌套结构），导入时按 xmlUrl 去重并可选是否自动抓取。
   1.9 统计（stats）：源数量、文章总数、未读数、今日新增、
       各源文章量与最后更新时间、连续抓取失败的源清单。

2. 输入与交互
   2.1 命令形如：
       `python -m rss feed add https://blog.example.com/feed.xml --category 技术`
       `python -m rss fetch --all --workers 8`
       `python -m rss list --unread --limit 20`
       `python -m rss show 137 --page 1`
   2.2 交互式浏览模式（`python -m rss read`）：进入全屏式列表浏览，
       方向键或 j/k 移动，回车进入详情，详情内 n/p 切换文章。
   2.3 支持 `--db PATH`、`--json`、`--no-color`（无 ANSI 颜色输出，
       便于重定向到文件或供脚本处理）。
   2.4 每次 fetch 前输出进度：正在抓取的源、已处理数/总数、
       各源新增文章数、失败原因。
   2.5 支持 `--proxy http://127.0.0.1:7890` 与 `--timeout 15`。

3. 输出与展示
   3.1 列表视图列：序号、状态（已读/未读用符号区分，如 `*` 与空格）、
       源缩写（最多 8 字符，中文按显示宽度计算）、标题（超长截断加 …）、
       相对时间（“3 小时前”“昨天”“2024-04-30”）。
   3.2 详情视图：标题、源名称、作者、发布时间、原文链接、分类标签、
       摘要或正文（按终端宽度折行，中文按 2 列宽计算，代码块保留缩进）、
       底部操作提示行。
   3.3 颜色：未读标题为高亮色，收藏为黄色星号，抓取失败源为红色；
       --no-color 时全部降级为纯文本符号。
   3.4 fetch 结束输出一行摘要，如
       `抓取 12 源：新增 34 篇，重复跳过 96 篇，失败 1 源（超时）`。

4. 异常与边界处理
   4.1 网络超时或 DNS 失败：单源失败不影响其他源；记录失败原因与
       连续失败次数；连续失败 5 次后自动把该源 interval 翻倍（最多 24 小时），
       并在 stats 中高亮。
   4.2 HTTP 状态码非 200：301/302 跟随重定向（最多 5 跳）并更新 feed.url；
       403/404 记录为永久性问题并在 list 中标记；429 读取 Retry-After
       并顺延下次抓取时间。
   4.3 返回内容不是 XML（如被 CDN 拦截返回 HTML 验证页）：
       检测内容类型与前 200 字节特征，报错“响应不是有效的 RSS/Atom”，
       不写库。
   4.4 编码问题：优先用 feedparser 的 detected_encoding，
       回退 xml 声明、HTTP 头、utf-8、gbk；最终用 errors='replace' 解码
       并记录告警，避免乱码导致解析中断。
   4.5 缺失 pubDate：依次回退 updated、dc:date、HTTP Last-Modified 头、
       抓取时间；并在文章上标记 `time_estimated=1`。
   4.6 缺失 guid 与链接：用标题+源哈希生成稳定 guid；标题也为空时跳过该条
       并计入 skipped。
   4.7 摘要含 HTML：用标准库 html.parser 派生的剥离器去掉标签、
       解码实体、压缩空白，保留纯文本；详情视图中按宽度折行。
   4.8 数据库为空时 list：输出“暂无文章，请先运行 fetch”，退出码 0。
   4.9 删除订阅源：默认保留其文章（标记为 orphan），
       `--purge` 同时删除文章，删除前需 --yes。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：
   2.1 第三方：feedparser（解析 RSS/Atom）；requests（可选，用于更细的
       HTTP 控制；若不用则用 urllib.request）。
   2.2 标准库：sqlite3、argparse、urllib.request、urllib.parse、
       concurrent.futures（线程池）、html.parser、html、re、json、
       xml.etree.ElementTree（OPML 生成与解析）、datetime、email.utils
       （解析 RFC 2822 时间）、hashlib、unicodedata、textwrap、
       dataclasses、logging、os、pathlib、shutil、webbrowser。
3. 禁止事项：禁止在抓取时不设 User-Agent（必须使用明确标识，如
   `TerminalRSSReader/1.0 (+local personal use)`）；
   禁止无节制并发（必须限流，默认 8 线程且同主机必须串行）；
   禁止把抓取间隔设为 0 或允许 --force 以外的绕过节流方式；
   禁止把文章正文以 HTML 原样渲染到终端（必须剥离标签）。
4. 采集合规要求（必须实现并写在代码注释中）：
   4.1 抓取前检查目标站点的 robots.txt（使用
       urllib.robotparser.RobotFileParser），对 Disallow 的路径跳过抓取，
       并在日志中说明；robots.txt 本身请求失败时按“允许”处理但记录告警。
   4.2 每个源两次抓取之间强制间隔不低于配置的 interval 且不低于 60 秒
       （即使 --force 也要提示“强制刷新仍受每源最小 60 秒限制”）。
   4.3 同一主机（host）的请求串行执行，不同主机才并发，
       避免对单个站点造成压力。
   4.4 请求携带明确的 User-Agent 与 If-Modified-Since / ETag 条件请求，
       服务端返回 304 时不重复解析。
   4.5 程序仅供个人学习与阅读订阅内容使用；不抓取需要登录的内容，
       不绕过付费墙，不存储全文用于再分发；README 与 --help 中必须
       写明该用途限制。
5. 代码组织：
   - `db.py` / `repository.py`：建表与 SQL 层。
   - `models.py`：Feed、Entry、FetchResult、Stats。
   - `fetcher.py`：HTTP 请求、robots 检查、条件请求、重试与限速（核心）。
   - `parser.py`：feedparser 封装、字段兜底、guid 规范化、时间解析。
   - `cleaner.py`：HTML 剥离、文本归一化、摘要生成。
   - `dedupe.py`：guid 与规范化链接的生成规则。
   - `render.py`：列表与详情渲染、宽度折行、颜色与降级。
   - `opml.py`：OPML 导入导出。
   - `cli.py`：命令行与交互式浏览循环。
6. 编码规范：所有网络相关函数带超时参数；异常分层
   （NetworkError、ParseError、RobotsDisallowed）便于分类统计；
   抓取与入库分离，先抓取到内存再统一写库，保证单源失败不污染数据库。

【四、设计要点】

1. 数据结构（SQLite 表结构）

   1.1 feeds（订阅源表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       url           TEXT NOT NULL UNIQUE      -- feed 的实际 XML 地址
       site_url      TEXT NOT NULL DEFAULT ''  -- 站点主页
       title         TEXT NOT NULL DEFAULT ''
       description   TEXT NOT NULL DEFAULT ''
       language      TEXT NOT NULL DEFAULT ''
       category      TEXT NOT NULL DEFAULT ''  -- 用户自定义分类
       interval_min  INTEGER NOT NULL DEFAULT 60   -- 抓取间隔（分钟）
       enabled       INTEGER NOT NULL DEFAULT 1
       etag          TEXT NOT NULL DEFAULT ''  -- 条件请求缓存
       last_modified TEXT NOT NULL DEFAULT ''
       last_fetch_at TEXT NULL
       last_status   INTEGER NULL              -- 最近一次 HTTP 状态码
       fail_count    INTEGER NOT NULL DEFAULT 0
       last_error    TEXT NOT NULL DEFAULT ''
       created_at    TEXT NOT NULL
       索引：idx_feeds_enabled(enabled, last_fetch_at)

   1.2 entries（文章表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       feed_id       INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE
       guid          TEXT NOT NULL             -- 规范化后的唯一标识
       guid_source   TEXT NOT NULL             -- 'id' | 'link' | 'hash' | 'title'
       title         TEXT NOT NULL DEFAULT ''
       link          TEXT NOT NULL DEFAULT ''
       author        TEXT NOT NULL DEFAULT ''
       summary       TEXT NOT NULL DEFAULT ''  -- 纯文本摘要
       content       TEXT NOT NULL DEFAULT ''  -- 纯文本正文（可能为空）
       categories    TEXT NOT NULL DEFAULT ''  -- 逗号分隔
       enclosure_url TEXT NOT NULL DEFAULT ''  -- 播客/附件
       image_url     TEXT NOT NULL DEFAULT ''
       published_at  TEXT NOT NULL             -- ISO8601 UTC
       time_estimated INTEGER NOT NULL DEFAULT 0
       fetched_at    TEXT NOT NULL
       is_read       INTEGER NOT NULL DEFAULT 0
       is_starred    INTEGER NOT NULL DEFAULT 0
       duplicate_of  INTEGER NULL REFERENCES entries(id) ON DELETE SET NULL
       read_at       TEXT NULL
       word_count    INTEGER NOT NULL DEFAULT 0
       约束：UNIQUE(feed_id, guid)
       索引：idx_entries_pub(published_at DESC)、
             idx_entries_unread(is_read, published_at DESC)、
             idx_entries_feed(feed_id, published_at DESC)、
             idx_entries_star(is_starred, published_at DESC)、
             idx_entries_link(link)

   1.3 fetch_log（抓取日志表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       feed_id       INTEGER NOT NULL
       started_at    TEXT NOT NULL
       finished_at   TEXT NOT NULL
       http_status   INTEGER NULL
       duration_ms   INTEGER NOT NULL
       new_entries   INTEGER NOT NULL DEFAULT 0
       dup_entries   INTEGER NOT NULL DEFAULT 0
       skipped       INTEGER NOT NULL DEFAULT 0
       error_type    TEXT NOT NULL DEFAULT ''
       error_message TEXT NOT NULL DEFAULT ''

   1.4 settings（键值配置表）
       key TEXT PRIMARY KEY, value TEXT NOT NULL
       -- 默认含 user_agent、timeout、workers、min_interval_sec、page_size、
       -- default_interval_min、mark_read_on_open 等

   1.5 schema_version（迁移版本表）
       version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL

2. 关键算法或流程

   2.1 抓取流程（fetcher.fetch_feed）：
       步骤一，读取 feed 记录，判断
       `now - last_fetch_at < interval_min` 且未加 --force 时跳过并计入 skipped；
       步骤二，用 urllib.robotparser 获取该站的 robots.txt（结果按 host 缓存
       24 小时），目标 URL 被 Disallow 则抛 RobotsDisallowed 并记录日志；
       步骤三，构造请求：User-Agent 来自 settings、Accept 指定
       `application/rss+xml, application/atom+xml, application/xml, text/xml`、
       若已有 etag/last_modified 则加 If-None-Match / If-Modified-Since；
       步骤四，发起请求，timeout=settings.timeout（默认 15 秒）；
       步骤五，处理响应：304 → 更新 last_fetch_at 并返回 0 新增；
       3xx → 跟随重定向（最多 5 跳）并更新 url；
       429 → 读 Retry-After 设置下次可抓取时间；
       4xx/5xx → 记录错误，fail_count 加 1；
       步骤六，校验响应体：前 200 字节必须能识别为 XML
       （以 `<?xml` 或 `<rss` 或 `<feed` 或 `<rdf:RDF` 开头，忽略 BOM），
       否则抛 ParseError；
       步骤七，交给 parser 解析并标准化为 Entry 列表；
       步骤八，去重后写库（在单个事务中完成），更新 feed 的 etag、
       last_modified、last_fetch_at、last_status、fail_count（成功时清零）；
       步骤九，写 fetch_log。

   2.2 并发与限速调度（fetcher.fetch_many）：
       步骤一，筛选出需要抓取的 feeds（enabled=1 且到达抓取时间）；
       步骤二，按 host 分组，同一 host 的源放入同一队列按顺序抓取；
       步骤三，用 ThreadPoolExecutor(max_workers=settings.workers)
       在“主机队列”层面并发（默认 8 个主机同时抓）；
       步骤四，每次请求之间全局 sleep 至少 min_interval_sec（默认 1 秒）
       通过共享的限速器（threading.Lock + 时间戳）保证不对服务器突发；
       步骤五，汇总所有 FetchResult 输出统计。

   2.3 guid 规范化与去重（dedupe）：
       优先级一，entry.id 或 entry.guid 存在：直接使用，保留原字符串，
       仅去除首尾空白；
       优先级二，entry.link 存在：规范化为
       scheme 小写 + host 小写 + 去默认端口 + 路径保留 + 去除以下跟踪参数
       （utm_source, utm_medium, utm_campaign, utm_term, utm_content,
       ref, source, spm, from） + 去除末尾斜杠（若路径非根） + 丢弃 fragment；
       优先级三，标题存在：sha1(feed_id + title 归一化) 前 20 位；
       优先级四，全部缺失：跳过该条并计入 skipped。
       入库时对同一 feed 内的重复 guid 直接跳过；跨 feed 的相同 link
       在 entries.link 索引上查一次，存在则新记录 duplicate_of 指向已有 id
       并且 is_read 默认置 1（避免重复显示），但不显示在默认列表中。

   2.4 时间解析与兜底（parser.parse_time）：
       依次尝试 feedparser 的 published_parsed、updated_parsed、
       dc:date（通过 entry 的 dict 属性）、
       对原始字符串用 email.utils.parsedate_to_datetime 解析 RFC 2822、
       用 datetime.fromisoformat 解析 ISO 8601（含 'Z' 需替换为 '+00:00'）；
       全部失败则使用 HTTP Last-Modified；
       再失败则使用抓取时刻并置 time_estimated=1；
       统一转为 UTC 后以 ISO8601 字符串存储，展示时再转本地时区。

   2.5 终端渲染与折行（render）：
       计算显示宽度函数 dw(s) = sum(2 if unicodedata.east_asian_width(c)
       in 'WF' else 1 for c in s)；
       截断：按显示宽度累计，超过上限时截断并补 `…`，保证不切断显示宽度为 2
       的字符（若剩余宽度为 1 且下一字符宽度为 2，则提前截断）；
       折行：对中文按字符累积宽度，对英文优先在空格处断行，
       代码行（以 4 个空格或 tab 开头）保留缩进不做重排；
       详情分页：每页行数 = 终端高度 - 4（用 shutil.get_terminal_size() 获取，
       非 TTY 时默认 24 × 80）。

3. 接口或命令设计

   feed add URL [--category 技术] [--interval 60] [--title 自定义标题]
   feed list [--category C] [--enabled-only] [--json]
   feed remove ID [--purge] --yes | feed enable ID | feed disable ID
   feed edit ID [--url --title --category --interval]
   feed discover SITE_URL          （自动发现 RSS 地址并列出候选）
   fetch [--all] [--feed ID ...] [--force] [--workers 8] [--json]
   list [--feed ID] [--category C] [--unread] [--starred] [--since D]
        [--limit 20] [--offset 0] [--json]
   show ID [--page N] [--raw] [--open]
   read ID [ID ...] [--all] [--before D] [--unread] [--yes]
   star ID [ID ...] | unstar ID [ID ...]
   search KEYWORD [--unread] [--limit N] [--json]
   read-mode                       （交互式浏览：j/k 移动，Enter 详情，o 打开）
   opml export PATH [--category C] | opml import PATH [--fetch]
   stats [--json]
   clean [--older-than 90] [--read-only] [--yes]   （清理历史已读文章）

   函数签名：
   def fetch_feed(feed: Feed, cfg: Settings, http) -> FetchResult
   def fetch_many(feeds: list[Feed], cfg: Settings) -> list[FetchResult]
   def normalize_guid(entry: dict, feed_id: int) -> tuple[str, str]
   def parse_feed_bytes(raw: bytes, encoding_hint: str | None) -> list[Entry]
   def strip_html(raw: str) -> str
   def make_snippet(text: str, width: int = 120) -> str
   def render_entry(entry: Entry, width: int, color: bool) -> list[str]

【五、运行方式与示例】

安装：
  cd C:\projects\100programs\059_rss_reader
  pip install feedparser requests
  python -m rss init

示例一（添加订阅并抓取）：
  输入：python -m rss feed add https://blog.python.org/feeds/all.atom.xml --category 技术
  输出：已添加订阅 #1 Python Blog（Atom），抓取间隔 60 分钟
  输入：python -m rss fetch --all
  输出：
        [1/1] Python Blog … 200 OK，新增 10 篇，重复 0 篇，耗时 480 ms
        抓取 1 源：新增 10 篇，重复跳过 0 篇，失败 0 源

示例二（列表与详情阅读）：
  输入：python -m rss list --unread --limit 5
  输出：
        #  源        标题                                        时间
        *   Python    Python 3.13 发布说明                       2 小时前
        *   Python    Security release: 3.12.4                   昨天
           (已读)     PEP 703 进展                               2024-04-30
  输入：python -m rss show 137
  输出：
        标题：Python 3.13 发布说明
        来源：Python Blog   作者：Release Manager   发布：2024-05-03 09:12 (+08:00)
        链接：https://blog.python.org/2024/05/python-3130-is-now-available.html
        摘要：Python 3.13.0 现已发布，主要变化包括新的交互式解释器、
              实验性的自由线程模式（PEP 703）与 JIT 编译器……
        [n]下一条 [p]上一条 [o]浏览器打开 [s]收藏 [m]标已读 [q]退出
  输入：python -m rss read 137
  输出：已标记 #137 为已读（未读数 9）

示例三（OPML 与异常输入）：
  输入：python -m rss opml export out\feeds.opml
  输出：已导出 12 个订阅源到 out\feeds.opml（分类 3 个）
  输入：python -m rss feed add https://example.com/notafeed
  输出：错误：响应不是有效的 RSS/Atom（Content-Type: text/html）  （退出码 2）
  输入：python -m rss fetch --feed 9
  输出：跳过 #9 某博客：距上次抓取仅 12 分钟（间隔 60 分钟），如确需刷新用 --force
  输入：python -m rss show 99999
  输出：错误：文章 #99999 不存在                                （退出码 2）

【六、验收标准】

[ ] `feed add` 传入站点主页时能自动发现 RSS 地址并给出候选列表。
[ ] 重复添加同一 URL 被 UNIQUE 约束拦住并提示已存在的 ID。
[ ] robots.txt 禁止抓取的路径会被跳过并记录日志（用本地测试服务器验证）。
[ ] 每个源的两次抓取间隔不低于 interval_min，--force 也不低于 60 秒。
[ ] 同一主机的多个源串行抓取（抓取日志时间戳不重叠）。
[ ] 支持 ETag/If-Modified-Since：服务端返回 304 时不新增文章且不报错。
[ ] 同一 feed 重复抓取两次，第二次新增为 0、重复计数等于第一次的文章数。
[ ] 带 utm_source 等跟踪参数的链接与不带参数的同一链接被识别为重复。
[ ] 缺少 guid 与 link 的条目使用标题哈希生成 guid，且多次抓取 guid 稳定。
[ ] 不同源出现同一链接时，后入库记录 duplicate_of 指向先入库记录。
[ ] 时间解析覆盖 RFC 2822 与 ISO 8601 两种格式；缺失时用抓取时间并标记估算。
[ ] GBK 编码的源能正确解析中文标题，不出现乱码。
[ ] 摘要中的 HTML 标签被剥离，`<p>` 与 `&amp;` 等实体被正确还原为文本。
[ ] 中文标题在列表中按显示宽度截断，不出现半角错位或半个汉字。
[ ] --no-color 输出中不含任何 ANSI 转义序列（用二进制方式检查）。
[ ] OPML 导出后重新导入，源数量与分类结构与导出前一致。
[ ] stats 中连续失败源被标红，且连续失败 5 次后 interval 自动翻倍。
[ ] 交互式浏览模式的 j/k/Enter/o/s/m/q 按键全部生效。
[ ] 无网络环境下 fetch 不崩溃，输出各源失败原因并保留已有数据。

【七、可选扩展】

1. 增加“每日摘要”导出：把未读文章标题与摘要写成 Markdown 日报。
2. 增加播客支持：解析 enclosure 音频，配合 045 项目显示时长与下载。
3. 增加规则过滤：按关键词白名单/黑名单自动标记或跳过文章。
4. 增加 FTS5 全文检索（正文非空时），支持中文 bigram 切分。
5. 增加后台守护模式：按 schedule 定时抓取，新文章触发桌面通知。
6. 增加与 065 项目联动：把未读摘要推送到邮箱或 webhook。

【八、涉及知识点】

- feedparser：RSS 2.0 / Atom 1.0 / RDF 的字段模型、bozo 异常与编码探测。
- HTTP 客户端细节：User-Agent、条件请求（ETag / If-Modified-Since）、
  重定向、Retry-After、超时与连接复用。
- robots.txt 协议：RobotFileParser、User-agent 匹配、Crawl-delay 与合规抓取。
- 并发控制：ThreadPoolExecutor、按主机串行、全局限速器与线程安全。
- 去重策略：guid 与 URL 规范化、跟踪参数剥离、跨源重复识别。
- 时间处理：RFC 2822 与 ISO 8601 解析、UTC 存储与本地化显示、相对时间。
- 文本清洗：html.parser 派生剥离器、实体解码、空白压缩与摘要截断。
- 终端 UI：显示宽度计算、折行与截断、ANSI 颜色、非 TTY 降级、单键交互。
- SQLite 索引与查询优化：覆盖时间排序与未读过滤的复合索引。
- OPML 与 XML：ElementTree 的命名空间处理、生成与解析的对称性。
================================================================================
