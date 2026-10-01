================================================================================
项目编号：060                    难度等级：★★★☆☆（中型项目）
项目名称：通用网页抓取与清洗管道
所属分类：内容采集 / 数据处理管道
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：requests、beautifulsoup4、lxml、pandas（可选）
================================================================================

【一、项目背景与目标】

抓取网页的代码往往写一次扔一次：换个站点就要重写解析逻辑，翻页、去重、限速、
重试、断点续爬这些通用问题每次都要重新解决。本项目把“抓取”抽象成一条可配置的
管道：用一份 JSON 配置描述站点（列表页 URL 模板、翻页规则、字段的 CSS 选择器、
清洗规则、输出字段），运行一条命令即可完成“取列表 → 翻页 → 抓详情 → 解析 →
清洗 → 入库 → 导出”的全过程。

目标用户是需要定期采集公开数据做分析的学习者与数据工程初学者。它同时是一个
教学项目：把 HTTP、HTML 解析、正则清洗、并发限速、状态持久化、断点续爬这些
知识点串成一个完整可运行的工程。

本项目明确且仅用于学习与技术研究：只抓取公开、无需登录、未被 robots.txt 禁止的
页面；默认低并发、强限速；不抓取个人隐私数据、不绕过任何访问控制、不做商用与
再分发；配置与文档中反复强调这一约束。项目难点在于配置驱动的通用性设计，
以及在保证合规与稳定的前提下实现断点续爬与失败重试。

【二、功能需求清单】

1. 核心功能
   1.1 配置驱动（config）：用 JSON 定义任务：站点名、起始 URL 列表、
       列表页选择器、详情链接选择器、翻页策略（下一页选择器 / URL 模板
       递增 / 最大页数）、字段映射（字段名 → 选择器 + 属性 + 类型 +
       必填标记）、清洗规则、输出目标。
   1.2 抓取（fetch）：按配置抓取列表页与详情页；支持并发（默认 4，
       同主机串行）；遵守 robots.txt；遵守限速（默认每域名 1.5 秒间隔、
       全局每分钟不超过 30 个请求）。
   1.3 解析（parse）：用 BeautifulSoup + lxml 解析 HTML；
       字段支持 CSS 选择器与 XPath（lxml 提供）；支持取文本、取属性、
       取 HTML 片段、正则抽取子串（如从“￥1,299.00”抽数字）。
   1.4 清洗（clean）：去首尾空白、压缩连续空白、全角转半角、去 HTML 标签、
       去多余换行、类型转换（int/float/date/bool）、枚举值映射、
       空值填充与必填校验；清洗失败的记录进入 rejects 输出并记录原因。
   1.5 翻页（paginate）：三种策略——跟随“下一页”链接；
       按 URL 模板递增页码直到无结果或达到 max_pages；
       基于“列表页总条数 / 每页条数”计算页数。必须支持终止条件与去重。
   1.6 去重（dedupe）：按配置的主键字段（如 URL、商品 ID）或用
       详情页 URL 规范化后哈希；同一次运行内与跨次运行都去重
       （查询数据库已存在的键）。
   1.7 入库（store）：写入 SQLite（结构由配置的字段自动建表或写入通用
       records 表 + JSON 列）；同时可导出 CSV/JSON/JSONL。
   1.8 断点续爬（resume）：状态表记录任务进度（当前页、已完成详情 URL、
       待抓取队列、失败 URL 及重试次数）；用 `--resume TASK_ID` 从上次
       中断处继续，已完成条目不重复抓取。
   1.9 失败重试（retry）：对网络错误与 5xx 做最多 3 次重试，退避 1/2/4 秒
       （加随机抖动）；对 4xx（除 429）不重试直接记失败；429 读取
       Retry-After 并等待后重试一次；失败清单可导出并用
       `--retry-failed TASK_ID` 单独重跑。
   1.10 报告（report）：输出本次运行统计：请求数、成功/失败数、新增记录、
        重复跳过、清洗失败、各阶段耗时、平均响应时间、被 robots 拒绝的 URL。

2. 输入与交互
   2.1 命令形如：
       `python -m scraper run --config configs\books.json --out data\books.db
        --resume auto`
       `python -m scraper run --config x.json --dry-run --max-pages 2`
       `python -m scraper retry-failed --task 12`
   2.2 `--dry-run` 只抓取与解析，输出前 5 条结果预览，不写库、不落盘。
   2.3 支持 `--limit N`（最多抓多少条详情）、`--max-pages N`、
       `--workers N`、`--delay FLOAT` 覆盖配置。
   2.4 支持 `--proxy`、`--timeout 15`、`--user-agent`、`--cookie-file`
       （仅用于公开页面的必要 Cookie，禁止用于绕过登录）；
       支持 `--header "Key: Value"` 追加请求头。
   2.5 运行中每处理完一条输出进度行（可 --quiet 关闭）：
       `[12/120] 详情 https://example.com/item/12 → 解析成功（4 字段）`。
   2.6 支持 Ctrl+C 优雅退出：捕获 KeyboardInterrupt 后
       保存进度与队列状态，输出“已保存断点，可用 --resume 继续”。

3. 输出与展示
   3.1 控制台输出分阶段日志：读取配置 → robots 检查 → 列表页抓取
       → 详情页抓取 → 清洗 → 入库 → 导出，每阶段带耗时。
   3.2 结束输出统计表（文本对齐），含各字段的非空率，便于判断选择器是否失效。
   3.3 生成三类产物：数据文件（SQLite/CSV/JSONL）、
       rejects.jsonl（清洗失败记录）、run_report.json（本次运行报告）。
   3.4 选择器失效检测：某必填字段的非空率低于 60% 时输出醒目告警
       “字段 X 命中率 12%，选择器可能已失效”。

4. 异常与边界处理
   4.1 robots.txt 禁止抓取：该 URL 被跳过，计入 skipped_robots，
       并在报告中列出；配置可显式声明 `"respect_robots": true`（默认且
       不允许在文档示例中关闭）。
   4.2 页面结构变化导致选择器匹配为空：该记录计入 rejects，
       原因写明“字段 X 未匹配到节点”，不产生半截数据入库。
   4.3 网络超时/连接重置：按重试策略重试；三次都失败则记录到失败清单。
   4.4 编码不为 UTF-8：优先用响应头声明的编码，其次用 HTML meta charset，
       再次用 apparent_encoding（requests 提供），最后回退 utf-8 + 替换。
   4.5 详情页返回 404 或重定向到列表页：记为失效链接，
       已入库的同键记录标记为 invalid=1，不重复报错。
   4.6 分页陷入死循环（下一页链接指向当前页）：用已访问 URL 集合检测，
       命中即终止翻页并告警。
   4.7 单页结果为空但未到 max_pages：连续 2 页为空则停止翻页并告警。
   4.8 磁盘空间不足或数据库被占用：捕获异常，保存断点后退出码 3。
   4.9 配置字段缺失（如无 detail_selector）：启动时校验配置并报错退出码 2，
       不做半途失败。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：
   2.1 第三方：requests（HTTP）、beautifulsoup4（HTML 解析）、
       lxml（解析器与 XPath）；pandas（可选，仅用于 CSV 导出与去重统计，
       也可用 csv 模块替代）。
   2.2 标准库：sqlite3、argparse、json、csv、re、time、random、hashlib、
       urllib.parse、urllib.robotparser、datetime、pathlib、logging、
       threading、concurrent.futures、signal、html、unicodedata、dataclasses、
       itertools。
3. 采集合规与安全约束（硬性，必须在代码与文档中体现）：
   3.1 遵守 robots.txt：使用 urllib.robotparser 按 host 缓存结果 24 小时；
       被 Disallow 的 URL 一律跳过，绝不提供绕过选项。
   3.2 限速：默认每域名请求间隔 1.5 秒、全局每分钟最多 30 次请求；
       同一域名串行；并发只在不同域名之间进行。
   3.3 User-Agent：默认
       `StudyScraperBot/1.0 (+https://example.local/about; for study only)`，
       必须可配置；禁止伪装成主流浏览器 UA 去规避识别。
   3.4 仅用于学习与合法用途：不抓取登录后内容、不绕过付费墙与验证码、
       不抓取个人隐私与敏感信息、不高频请求造成对方服务压力、
       不将抓取数据用于商业用途或再分发；抓取前应确认目标站点
       服务条款允许，并优先使用官方 API（README 与 --help 中必须写明）。
   3.5 失败重试与限速联动：重试等待期间同样计入限速，
       不因为重试而突破每域名间隔。
   3.6 断点续爬：所有进度写入数据库，中断后不重复请求已成功的 URL，
       避免对目标站点产生重复流量。
4. 禁止事项：禁止使用 selenium/playwright 等浏览器自动化去执行页面 JS
   （本项目只做静态 HTML 抓取，遇到 JS 渲染站点应在文档中说明不支持）；
   禁止在配置里写选择器以外的 Python 代码执行（不得 eval 配置）；
   禁止把响应全文写进日志（避免磁盘暴涨与隐私风险）。
5. 代码组织：
   - `config.py`：配置加载、JSON Schema 式校验（手写字段校验）、默认值合并。
   - `http_client.py`：会话复用、UA、超时、代理、robots 检查、限速器、重试。
   - `rate_limit.py`：按域名的令牌桶或时间戳限速器（线程安全）。
   - `fetcher.py`：列表页与详情页抓取、翻页策略。
   - `parser.py`：选择器提取、属性读取、正则抽取。
   - `cleaner.py`：清洗管道（按配置顺序执行的可组合步骤）。
   - `store.py`：SQLite 建表与写入、去重、状态与断点管理、导出。
   - `pipeline.py`：整体编排、并发、进度、优雅退出（核心）。
   - `report.py`：统计与报告生成。
   - `cli.py`：命令行入口。
6. 编码规范：所有网络访问必须经 http_client 封装（便于统一限速与日志）；
   日志中 URL 脱敏（去掉 query 中的 token、key 等敏感参数）；
   所有配置项有默认值并在 --help 或 config --show 中可见。

【四、设计要点】

1. 数据结构

   1.1 配置文件结构（JSON，示例字段）
       {
         "task_name": "books_toscrape",
         "start_urls": ["https://books.toscrape.com/catalogue/page-1.html"],
         "respect_robots": true,
         "delay_seconds": 1.5,
         "max_requests_per_minute": 30,
         "workers": 4,
         "timeout": 15,
         "headers": {"Accept-Language": "zh-CN,zh;q=0.9"},
         "list": {
           "detail_link_selector": "article.product_pod h3 a",
           "next_page_selector": "li.next a",
           "max_pages": 50,
           "stop_on_empty_pages": 2
         },
         "fields": [
           {"name": "title", "selector": "h1", "attr": "text",
            "required": true, "clean": ["strip", "collapse_ws"]},
           {"name": "price", "selector": "p.price_color", "attr": "text",
            "type": "float", "extract_regex": "([0-9.]+)", "required": true},
           {"name": "stock", "selector": "p.instock.availability", "attr": "text",
            "type": "int", "extract_regex": "(\\d+)"},
           {"name": "category", "selector": "ul.breadcrumb li:nth-of-type(3)",
            "attr": "text"},
           {"name": "cover", "selector": "#product_gallery img", "attr": "src",
            "type": "url_absolute"}
         ],
         "dedupe_key": ["url"],
         "output": {"sqlite": "data/books.db", "table": "books",
                    "csv": "data/books.csv", "jsonl": "data/books.jsonl"}
       }

   1.2 SQLite 表结构

       1.2.1 tasks（任务表）
             id            INTEGER PRIMARY KEY AUTOINCREMENT
             task_name     TEXT NOT NULL
             config_hash   TEXT NOT NULL      -- 配置内容 sha256 前 16 位
             config_json   TEXT NOT NULL      -- 配置快照，便于复现
             started_at    TEXT NOT NULL
             finished_at   TEXT NULL
             status        TEXT NOT NULL      -- running / paused / done / failed
             stats_json    TEXT NOT NULL DEFAULT '{}'
             索引：idx_tasks_name(task_name, started_at DESC)

       1.2.2 task_state（断点状态表）
             task_id       INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE
             key           TEXT NOT NULL      -- 'current_page' / 'pending_urls' /
                                              -- 'visited_urls_count' / 'next_index'
             value         TEXT NOT NULL      -- JSON 值
             updated_at    TEXT NOT NULL
             PRIMARY KEY (task_id, key)

       1.2.3 fetched_urls（已抓取 URL 表，断点续爬与去重的核心）
             id            INTEGER PRIMARY KEY AUTOINCREMENT
             task_id       INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE
             url           TEXT NOT NULL
             url_hash      TEXT NOT NULL      -- sha1(规范化 URL) 前 20 位
             kind          TEXT NOT NULL      -- 'list' | 'detail'
             status        TEXT NOT NULL      -- ok / http_error / parse_error /
                                              -- robots_denied / skipped
             http_status   INTEGER NULL
             attempts      INTEGER NOT NULL DEFAULT 0
             first_seen_at TEXT NOT NULL
             last_try_at   TEXT NOT NULL
             error_message TEXT NOT NULL DEFAULT ''
             约束：UNIQUE(task_id, url_hash)
             索引：idx_fetched_status(task_id, kind, status)、
                   idx_fetched_urlhash(url_hash)

       1.2.4 records（数据表，字段由配置决定；下表为动态建表的模板）
             id            INTEGER PRIMARY KEY AUTOINCREMENT
             task_id       INTEGER NOT NULL
             source_url    TEXT NOT NULL
             record_hash   TEXT NOT NULL      -- 去重键拼接后的 sha1
             scraped_at    TEXT NOT NULL
             is_valid      INTEGER NOT NULL DEFAULT 1   -- 0 表示失效链接
             <配置字段1>    <推断类型>        -- 如 title TEXT / price REAL
             <配置字段2>    <推断类型>
             extra_json    TEXT NOT NULL DEFAULT '{}'  -- 未在配置中声明的补充字段
             约束：UNIQUE(task_id, record_hash)
             索引：idx_records_task(task_id, is_valid)、
                   idx_records_hash(record_hash)

       1.2.5 run_log（运行日志表）
             id            INTEGER PRIMARY KEY AUTOINCREMENT
             task_id       INTEGER NOT NULL
             phase         TEXT NOT NULL      -- list / detail / clean / store
             url           TEXT NOT NULL DEFAULT ''
             level         TEXT NOT NULL      -- info / warn / error
             message       TEXT NOT NULL
             duration_ms   INTEGER NOT NULL DEFAULT 0
             created_at    TEXT NOT NULL
             索引：idx_runlog_task(task_id, phase, level)

       1.2.6 schema_version（迁移版本表）
             version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL

2. 关键算法或流程（分步骤）

   2.1 HTTP 客户端与合规检查流程：
       步骤一，规范化 URL（去除 fragment、统一小写 scheme 与 host、
       去除 utm_* 等跟踪参数、相对路径补全为绝对路径）；
       步骤二，取 host，检查 robots 缓存；未缓存则请求
       `https://host/robots.txt`（同样受限速约束，失败按“允许”处理并告警），
       用 RobotFileParser 解析并判断 `can_fetch(user_agent, url)`；
       不允许 → 记为 robots_denied 并直接返回；
       步骤三，进入按域名的限速器：若距该域名上次请求不足 delay_seconds，
       则 sleep 剩余时间；同时检查全局每分钟请求数配额；
       步骤四，发起请求（requests.Session 复用连接，timeout、headers、
       proxies 来自配置）；
       步骤五，按状态码分流：200 → 返回内容；304 → 复用缓存（可选实现）；
       301/302 跟随（requests 默认，限制 max_redirects=5）；
       429 → 读 Retry-After（秒或 HTTP 日期）后等待重试一次；
       5xx 或网络异常 → 按退避重试（1s、2s、4s，加 0~0.5s 随机抖动），
       最多 3 次；4xx（非 429）→ 不重试，直接记录失败；
       步骤六，判断内容类型是否为 HTML（text/html 或 application/xhtml+xml），
       否则记为 skipped 并说明；
       步骤七，编码处理：优先 response.encoding，其次 meta charset 嗅探，
       再次 response.apparent_encoding，最后 utf-8 且 errors='replace'；
       步骤八，返回 (html_text, status, attempts)，并把本次请求写入 run_log。

   2.2 列表页与翻页流程：
       步骤一，从 task_state 读取 current_page 与待抓取列表 URL 队列；
       步骤二，抓取当前列表页，用 detail_link_selector 提取详情链接，
       用 urllib.parse.urljoin 补全为绝对 URL，规范化后去重；
       步骤三，对每个详情 URL 查询 fetched_urls：
       已存在且 status='ok' 则跳过（断点续爬的关键）；
       步骤四，按详情链接选择器结果判断是否继续翻页：
       存在 next_page_selector 匹配 → 取其 href 作为下一页；
       否则若配置了 url_template 则按页码递增生成；
       否则若配置了 total_count_selector 则计算页数；
       步骤五，把下一页 URL 加入已访问集合，若已在集合中则终止并告警
       （防死循环）；连续 empty_pages >= stop_on_empty_pages 时终止；
       步骤六，每抓完一页就把 current_page 与剩余队列写回 task_state
       （这样 Ctrl+C 后的断点最坏只丢一页）。

   2.3 详情页并发抓取：
       步骤一，把待抓取详情 URL 按 host 分桶；
       步骤二，对每个 host 桶内部串行（保证同域名限速有效）；
       步骤三，用 ThreadPoolExecutor(workers) 在 host 桶之间并发；
       步骤四，每个工作线程内完成“抓取 → 解析 → 清洗 → 入库”，
       入库使用每个线程独立的 sqlite3 连接（或主线程单写队列），
       避免 SQLite 多线程写冲突；推荐做法：工作线程只产出记录，
       主线程批量写库（每 100 条 commit 一次）；
       步骤五，每完成一条更新 fetched_urls 的 status 与 attempts，
       并写 task_state 的进度计数；
       步骤六，KeyboardInterrupt 或收到 SIGINT 时设置停止标志，
       等待在途请求返回后保存断点并退出。

   2.4 清洗管道（cleaner）：
       按配置中 clean 数组的顺序执行可组合步骤，每个步骤是纯函数
       (value, ctx) -> value：
         strip            去首尾空白（含全角空格与不间断空格 \xa0）
         collapse_ws      连续空白（含换行）压缩为单个空格
         strip_html       去掉 HTML 标签并解码实体
         nfkc             全角转半角（unicodedata.normalize('NFKC')）
         lower / upper    大小写转换
         remove_prefix    去掉指定前缀（如“￥”“作者：”）
         remove_suffix    去掉指定后缀
         map_values       枚举映射（如 "In stock" → "有货"）
         default          空值时填充默认值
       之后按 type 做类型转换：
         int → 先用 extract_regex 抽数字再 int，失败则清洗失败
         float → 同上，保留原始小数位
         date → 用 datetime.strptime 依次尝试
                ['%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日', '%d %b %Y']
         bool → 支持 'true/1/yes/是/有货' 与 'false/0/no/否'
         url_absolute → 用 urljoin 补全为绝对 URL
       任一必填字段为空或类型转换失败 → 该记录写入 rejects，
       原因写明字段名与原始值。

   2.5 去重键生成：
       按 dedupe_key 列表取值（如 ["url"] 或 ["title","price"]），
       对每个值做 NFKC 归一化与小写化，用 `|` 连接后取
       sha1 前 20 位作为 record_hash；入库前先查 records 的
       UNIQUE(task_id, record_hash)。

   2.6 断点续爬恢复：
       `--resume auto` 取该 task_name 最近一条 status in
       ('running','paused','failed') 的任务；`--resume 12` 指定 task_id。
       恢复步骤：读取 task_state 的 current_page 与 pending_urls；
       重建待抓取队列；对每个 URL 查 fetched_urls 跳过已成功者；
       输出“恢复任务 12：已抓取 340 条，剩余 160 条，从第 5 页继续”。

3. 接口或命令设计

   init                                   （创建数据库与版本表）
   run --config FILE [--out DB] [--resume auto|ID] [--dry-run]
       [--limit N] [--max-pages N] [--workers N] [--delay F]
       [--timeout F] [--user-agent STR] [--proxy URL] [--header "K: V"]
       [--quiet] [--export csv,jsonl]
   retry-failed --task ID [--only http_error,parse_error] [--limit N]
   list-tasks [--limit 20]                （历史任务与状态）
   show-task ID [--report] [--failed]
   export --task ID --format csv|jsonl -o PATH
   config validate FILE                   （校验配置并输出默认值合并结果）
   config show FILE                       （打印生效配置）
   stats --task ID                        （字段非空率、失败原因分布）

   函数签名：
   def load_config(path: Path) -> TaskConfig
   def is_allowed(url: str, user_agent: str, cache: RobotsCache) -> bool
   def polite_get(url: str, client: HttpClient) -> Response
   def extract_fields(soup, spec: list[FieldSpec], base_url: str) -> dict
   def clean_record(raw: dict, spec: list[FieldSpec]) -> tuple[dict, list[str]]
   def iter_list_pages(cfg: TaskConfig, client: HttpClient,
                       state: TaskState) -> Iterator[list[str]]
   def run_pipeline(cfg: TaskConfig, store: Store,
                    resume: str | None) -> RunReport

【五、运行方式与示例】

安装：
  cd C:\projects\100programs\060_web_scraper
  pip install requests beautifulsoup4 lxml
  python -m scraper init

注意：请先确认目标站点的服务条款与 robots.txt 允许抓取，本项目仅用于学习。
推荐用公开的练习站点（如 books.toscrape.com、quotes.toscrape.com）做实验。

示例一（首次运行，抓取练习站点）：
  输入：python -m scraper run --config configs\books.json --limit 20
  输出：
        [配置] books_toscrape  起始 1 个 URL  字段 5 个  限速 1.5s/域名
        [robots] 已获取 https://books.toscrape.com/robots.txt → 允许抓取
        [列表] 第 1 页 → 20 个详情链接
        [详情] [5/20] https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html → 成功（5 字段）
        [详情] [20/20] … → 成功（5 字段）
        [清洗] 通过 20 条，拒绝 0 条
        [入库] 新增 20 条（重复 0 条），表 books
        [导出] data\books.csv（20 行）、data\books.jsonl（20 行）
        [报告] 请求 21 次，成功 21，失败 0，平均响应 320 ms，总耗时 34.2 s
               字段非空率：title 100%，price 100%，stock 100%，category 100%，cover 100%

示例二（中断后续爬）：
  输入：python -m scraper run --config configs\books.json
        （抓取到第 3 页时按 Ctrl+C）
  输出：收到中断信号，已保存断点：任务 #7，current_page=3，已抓取 60 条
        可用 `python -m scraper run --config configs\books.json --resume 7` 继续
  输入：python -m scraper run --config configs\books.json --resume 7
  输出：恢复任务 #7：已抓取 60 条，从第 3 页继续，已跳过 60 个已完成 URL
        [列表] 第 3 页 → 20 个详情链接（其中 0 个已抓取）

示例三（失败重试与异常输入）：
  输入：python -m scraper retry-failed --task 7 --only http_error,parse_error
  输出：重试 3 个失败 URL：成功 2，仍失败 1（404 不可恢复）
  输入：python -m scraper config validate configs\bad.json
  输出：错误：字段 price 缺少 name；list.detail_link_selector 不能为空（退出码 2）
  输入：python -m scraper run --config configs\books.json --max-pages 999999
  输出：警告：max_pages 超过安全上限 200，已收敛为 200（避免对目标站点造成压力）
  输入：python -m scraper run --config configs\quotes.json --delay 0
  输出：警告：delay 不能小于 0.5 秒（合规限速下限），已设为 0.5

【六、验收标准】

[ ] 使用 books.toscrape.com 的配置能抓取列表页并正确解析全部 5 个字段。
[ ] 翻页跟随 next_page_selector 直到无下一页，抓取条数与站点总条数一致。
[ ] robots.txt 被 Disallow 的 URL 被跳过并计入 skipped_robots（用本地测试站点验证）。
[ ] 同一域名两次请求间隔不少于 delay_seconds（用抓取日志时间戳验证）。
[ ] 全局每分钟请求数不超过配置上限（统计 run_log 后 60 秒窗口内的请求数）。
[ ] 请求头中的 User-Agent 为配置值，且不是常见浏览器 UA 的伪装串。
[ ] 5xx 响应触发最多 3 次重试，退避时间递增；4xx 不重试。
[ ] 429 响应读取 Retry-After 并等待后重试，等待期间不突破域名限速。
[ ] Ctrl+C 后状态表正确保存 current_page 与剩余队列，数据库无半截记录。
[ ] --resume 恢复后不会重复抓取 fetched_urls 中 status='ok' 的 URL。
[ ] 重复运行同一配置两次，第二次新增记录为 0（去重键生效）。
[ ] 必填字段缺失的记录进入 rejects.jsonl 且不入 records 表。
[ ] 选择器失效时（必填字段非空率 < 60%）输出醒目告警。
[ ] 编码为 GBK 的页面能正确解析中文（用 gb2312 测试页验证）。
[ ] 价格 “￥1,299.00” 经 extract_regex 与 type=float 后得到 1299.0。
[ ] 日期 “2024年5月3日” 经 type=date 后存为标准 ISO 日期。
[ ] 相对图片路径经 type=url_absolute 后变为绝对 URL。
[ ] 下一页链接指向当前页时翻页终止并告警（不死循环）。
[ ] run_report.json 中的请求数、成功数、失败数满足 总和守恒。
[ ] 配置缺少必填项时启动即报错退出码 2，不进入抓取阶段。

【七、可选扩展】

1. 支持 JSON API 型数据源（配置 response_path 直接提取 JSON 字段）。
2. 增加 XPath 配置项（用 lxml 直接支持更复杂的选择）。
3. 增加定时调度（APScheduler）与增量更新（只抓取变化的内容）。
4. 增加数据质量报告与字段分布统计（结合 pandas 输出 describe）。
5. 增加 Puppeteer/Playwright 的可选适配层（明确仅在目标站点允许、
   且静态抓取不可行时使用，并在文档中强调合规前提）。
6. 增加代理池与失败域名熔断（连续失败 N 次自动暂停该域名）。

【八、涉及知识点】

- HTTP 协议与 requests：Session 复用、请求头、重定向、状态码语义、超时、
  编码探测（encoding / apparent_encoding）、代理。
- robots.txt 协议与 urllib.robotparser：User-agent 匹配、缓存与合规抓取。
- 限速与礼貌抓取：按域名时间戳限速、全局配额、退避与抖动的重试策略。
- HTML 解析：BeautifulSoup 树结构、CSS 选择器、属性读取、
  lxml 解析器与 XPath、相对 URL 补全。
- 数据清洗：可组合的清洗步骤、Unicode NFKC 归一化、正则抽取与类型转换。
- 结构化存储：动态建表、UNIQUE 去重键、批量提交与事务。
- 状态机与断点续爬：任务表、URL 状态表、进度持久化、幂等恢复。
- 并发编程：ThreadPoolExecutor、按域名分桶串行、线程安全的限速器、
  SQLite 单写者模型、信号与优雅退出。
- 配置驱动设计：配置校验、默认值合并、配置快照与可复现性。
- 工程化：日志脱敏、运行报告、失败清单重跑、选择器失效监控。
================================================================================
