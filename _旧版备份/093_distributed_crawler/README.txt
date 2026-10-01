================================================================================
项目编号：093                    难度等级：★★★★★（大型项目）
项目名称：分布式爬虫框架
所属分类：网络采集 / 分布式系统 / 工程框架
建议工时：3 ~ 4 周（约 110 ~ 170 小时）
运行环境：Python 3.10+    第三方依赖：FastAPI、uvicorn、redis、httpx、beautifulsoup4、lxml、pydantic、APScheduler、pytest、uvloop（可选）
================================================================================

【一、项目背景与目标】

单机爬虫写起来只要几十行，一旦目标站点上千、页面数量上百万，问题就成倍放大：任务分
配不均导致某些机器空转、某些机器过载；URL 重复抓取浪费带宽；某台机器被封 IP 后整个
任务仍然卡死；某个解析函数报错导致队列全部阻塞；站点限速规则散落在各爬虫代码里，无
法统一调整；断点重启后只能从头再来。分布式爬虫框架存在的意义，就是把这些横切问题从
业务爬虫里抽出来，做成可复用、可观测、可扩展的基础设施。

本项目要实现一个“调度中心 + 多工作者”的分布式爬虫框架：调度中心负责 URL 去重、任务
派发、限速令牌、优先级与失败重试；工作者从调度中心领取任务、抓取页面、执行解析规则、
把新发现的 URL 回传，并把结构化结果写入本地或远端存储。框架提供 Web 管理界面查看队列
长度、抓取速率、错误率、各工作者状态与实时日志。整个系统可在一台机器上用多个进程演
示分布式行为，也可横向扩展为多机部署。

本框架的定位是教学与自用：用于抓取公开的、允许抓取的网页数据（例如公开的技术文档站、
公开的统计数据页面），必须在抓取前检查并遵守目标站点的 robots.txt，严格遵守站点声明
的抓取延迟与并发限制，禁止用于绕过反爬机制、禁止抓取需要登录或涉及个人隐私的数据、
禁止对目标站点造成压力。框架内置的合规开关不是装饰：robots 校验失败的 URL 必须被丢弃
并记录原因，这一条会被测试用例固化。

目标用户是：想学习分布式任务队列与并发调度的开发者、需要为自己维护的小型采集任务搭
一套稳定底座的工程师、以及需要理解“去重、限速、重试、幂等”四件事如何协同的进阶学习
者。做成之后，它可以直接作为通用采集底座，也可以把调度中心替换成消息队列版本作为对
比实验。

【二、功能需求清单】

本系统按四个子系统拆分：调度中心（Scheduler）、工作者（Worker）、管理端（Web 控制台）、
基础设施（存储、队列、配置与部署）。

1. 调度中心子系统
   1.1 URL 去重：对归一化后的 URL 计算指纹（sha1 前 16 字节）并写入去重集合；重复 URL
       直接丢弃并计入 duplicate_total 指标。归一化规则：小写 scheme 与 host、去掉默认
       端口、去掉 fragment、按 key 排序 query、移除常见跟踪参数（utm_*、spm、from）。
   1.2 任务队列：使用 Redis 的有序集合按优先级（priority + 入队时间）实现待抓队列；支持
       全局优先级与站点优先级叠加；队列长度可实时查询。
   1.3 任务派发：工作者通过长轮询（默认 3 秒超时）或短轮询从待抓队列取出任务；取任务
       时必须把任务同时写入“进行中”集合并记录租约到期时间，防止任务丢失。
   1.4 租约与超时回收：任务默认租约 120 秒；工作者未在租约内上报结果时，任务回到待抓队
       列并重试次数加一；连续超时超过 max_retry 的任务进入失败队列。
   1.5 站点限速：为每个域名维护令牌桶（默认 1 QPS，可配置），调度中心在派发前检查令牌；
       无令牌时任务重新入队并延后派发（延迟时间按桶余量动态计算），不得忙等空转。
   1.6 域名并发上限：每个域名同时进行中的任务数不超过 domain_concurrency（默认 2），避免
       对单站点造成压力。
   1.7 重试策略：失败任务按指数退避重试（1s、4s、16s，最多 3 次），HTTP 429 与 503 视为
       可重试，401/403/404 视为不可重试直接进入失败队列并记录原因。
   1.8 任务来源管理：支持通过 API 提交种子 URL（种子表 seeds）与定时增量种子；种子可在
       控制台启用/停用。
   1.9 全局开关：支持暂停/恢复整个采集（pause/resume）、清空队列（需二次确认参数）、
       调整限速参数（热更新，无需重启）。
   1.10 指标统计：维护 crawl_total、success_total、failed_total、duplicate_total、
       bytes_total、qps（滑动 60 秒窗口）、avg_latency_ms，按域名与全局两个维度统计。

2. 工作者子系统
   2.1 任务领取循环：向调度中心申请任务 → 执行抓取 → 上报结果 → 继续申请；空闲时按退避
       策略轮询，避免空转打满调度中心。
   2.2 HTTP 抓取：基于 httpx 异步客户端，连接超时 10 秒、读取超时 20 秒、最大重定向 5 次；
       默认请求头包含可识别的 User-Agent（含项目名与联系方式占位）；支持为特定站点配置
       自定义头与 Cookie（配置文件中声明，不硬编码在代码里）。
   2.3 响应处理：仅处理 Content-Type 为 text/html 与 application/json 的响应；超过
       max_body_bytes（默认 5 MB）的响应体截断并记录；非 HTML 内容按配置决定是否保存原文。
   2.4 字符集处理：优先使用 HTTP 头声明的 charset，其次看 meta 标签，最后用 chardet 风格
       的启发式回退（本项目允许使用 charset-normalizer）；解码失败时用 errors="replace"
       并在日志中记录 warc 级别警告。
   2.5 解析规则：解析器由站点配置定义，声明列表页的条目选择器、详情页的字段选择器
       （CSS 选择器语法）、翻页规则（下一页选择器或 URL 模板）。规则文件为 YAML 或 JSON，
       与代码解耦，新增站点不需要改代码。
   2.6 链接抽取：从页面中抽取全部 <a href>，用 urljoin 转成绝对 URL，按 allow_domains 与
       deny_patterns 过滤，再交回调度中心去重。
   2.7 结果输出：结构化结果写入本地 JSONL 文件（按天分片）或推送到 HTTP 接口；写入采用
       “先写临时文件再追加提交”的方式，避免半条记录；每条记录附 crawl_time、source_url、
       worker_id、rule_version 便于溯源。
   2.8 工作者心跳：每 10 秒向调度中心上报心跳（worker_id、当前任务数、已完成数、平均耗时、
       进程内存）；超过 60 秒无心跳的工作者标记为 offline 并从进行中集合释放其租约。
   2.9 优雅退出：收到 SIGTERM/SIGINT 后不再领取新任务，等待当前任务完成后上报并退出，
       最长等待 30 秒。
   2.10 本地限速兜底：工作者自身也维护一次域名限速（避免调度中心限速失效时打爆站点），
       取两者中更严格的值。

3. 管理端子系统（Web 控制台）
   3.1 概览页：实时展示待抓队列长度、进行中任务数、失败队列长度、全局 QPS、成功率、
       抓取字节数、活跃工作者数，数据每 3 秒自动刷新。
   3.2 工作者列表：展示每个 worker 的 id、主机名、状态（online/offline）、当前任务 URL、
       已完成数、平均耗时、最后心跳时间；支持一键标记下线。
   3.3 域名视图：按域名聚合展示抓取量、成功率、平均耗时、当前限速值与最近一次抓取时间；
       支持在页面上直接调整该域名的 QPS 与并发上限。
   3.4 任务查询：按 URL 关键字或状态（待抓/进行中/成功/失败）查询任务，展示重试次数与
       失败原因；支持对单条失败任务执行“重试一次”。
   3.5 失败队列管理：列出失败任务及原因分类（DNS 失败、连接超时、HTTP 4xx、解析异常、
       被限速），支持批量重试与批量丢弃（丢弃需填写原因）。
   3.6 实时日志：通过 WebSocket 推送调度中心与工作者的结构化日志流，支持按级别与关键字
       过滤，最多回放最近 500 条。
   3.7 规则管理：在页面上查看已加载的站点规则，展示规则版本与匹配域名，支持上传新规则
       文件并热加载（保留上一版本以便回滚）。
   3.8 合规中心：展示每个域名的 robots.txt 拉取状态与缓存内容摘要、允许路径与禁止路径
       数量、Crawl-delay 值，以及被合规策略拦截的 URL 列表与原因。

4. 基础设施子系统
   4.1 robots.txt 合规：抓取前必须检查 robots.txt；使用 urllib.robotparser 解析并缓存
       （按域名缓存 6 小时，按 User-Agent 分组）；被禁止的 URL 一律不入队，记录到
       compliance_log（url、domain、reason、robots_rule、checked_at）。
   4.2 存储：SQLite 用于任务元数据、域名配置、工作者与统计快照（生产可切 PostgreSQL）；
       Redis 用于队列、去重集合与令牌桶；抓取结果以 JSONL 落盘。三者职责不可混用。
   4.3 任务持久化与恢复：Redis 开启 AOF；调度中心启动时从数据库重建去重集合（对已成功
       URL 的指纹集合）与待抓任务，保证重启不丢队列、不重复抓取。
   4.4 配置管理：config.toml 定义 redis_url、db_url、default_qps、domain_concurrency、
       max_retry、lease_seconds、output_dir、rules_dir、user_agent、compliance_strict；
       支持环境变量 CRAWLER_ 前缀覆盖。
   4.5 日志：调度中心与工作者各自输出结构化 JSON 日志（含 trace_id、worker_id、task_id、
       domain），按天滚动，保留 14 天；不得在日志中输出页面正文全文。
   4.6 部署：支持单机多进程（1 调度 + N 工作者）与多机部署（调度中心独立，工作者指向
       调度中心地址）；提供 Dockerfile 与 docker-compose 示例。
   4.7 速率与规模上限保护：内置 max_queue_size（默认 100 万）与 max_pages_per_domain
       （默认 10 万）上限，达到上限时停止入队并告警，防止失控抓取。

5. 模块清单（源码结构）
   5.1 scheduler/app.py         调度中心 FastAPI 应用与生命周期管理。
   5.2 scheduler/queue.py       待抓队列、进行中集合、失败队列的 Redis 操作封装。
   5.3 scheduler/dedup.py       URL 归一化与指纹去重（含 Bloom 过滤器可选加速）。
   5.4 scheduler/ratelimit.py   域名令牌桶与域名并发计数（Redis Lua 实现）。
   5.5 scheduler/dispatch.py    派发逻辑、租约管理、超时回收与重试决策。
   5.6 scheduler/metrics.py     指标聚合与滑动窗口 QPS 计算。
   5.7 scheduler/compliance.py  robots.txt 拉取、缓存、检查与拦截记录。
   5.8 worker/main.py           工作者入口、信号处理、任务循环与心跳线程。
   5.9 worker/fetcher.py        httpx 异步抓取、重试、超时与体积控制。
   5.10 worker/parser.py        基于规则的 HTML 解析与字段抽取（CSS 选择器）。
   5.11 worker/pipeline.py      结果清洗、字段校验、去重与 JSONL 输出。
   5.12 worker/rules.py         规则文件加载、校验、热更新与版本记录。
   5.13 console/                控制台后端路由与前端静态页（原生 JS + fetch）。
   5.14 common/                 pydantic 模型、常量、日志、错误类型、配置加载。
   5.15 tests/                  单元、集成、限速与合规测试、多工作者联调脚本。

6. 接口清单（HTTP，节选核心）
   6.1 POST /api/v1/tasks/acquire          工作者领取任务 {worker_id, max_tasks}
   6.2 POST /api/v1/tasks/{task_id}/result 上报结果（成功/失败/新 URL 列表）
   6.3 POST /api/v1/tasks/{task_id}/renew  续租任务
   6.4 POST /api/v1/workers/heartbeat      心跳上报
   6.5 POST /api/v1/seeds                  提交种子 URL（数组）
   6.6 GET  /api/v1/stats/overview         全局指标
   6.7 GET  /api/v1/stats/domains?limit=   域名维度指标
   6.8 GET  /api/v1/workers                工作者列表
   6.9 GET  /api/v1/tasks?state=&kw=&page= 任务查询
   6.10 POST /api/v1/tasks/{task_id}/retry 单条重试
   6.11 POST /api/v1/failures/retry        批量重试（body 传 task_ids）
   6.12 POST /api/v1/failures/discard      批量丢弃（必带 reason）
   6.13 POST /api/v1/control/pause         暂停采集
   6.14 POST /api/v1/control/resume        恢复采集
   6.15 PUT  /api/v1/domains/{domain}/limit 调整该域名 QPS 与并发
   6.16 GET  /api/v1/compliance/blocked   合规拦截记录
   6.17 WS   /ws/logs                      实时日志流
   6.18 GET  /healthz                      健康检查

7. 数据模型概览
   7.1 tasks(id TEXT PK, url TEXT, url_hash TEXT UNIQUE, domain TEXT, priority INT,
       depth INT, state TEXT, retry INT, lease_until REAL, worker_id TEXT,
       parent_url TEXT, fail_reason TEXT, created_at TEXT, finished_at TEXT)
   7.2 domains(name TEXT PK, qps REAL, concurrency INT, enabled INT, robots_status TEXT,
       robots_fetched_at TEXT, crawl_delay REAL, max_pages INT, pages_crawled INT)
   7.3 workers(id TEXT PK, hostname TEXT, pid INT, state TEXT, current_url TEXT,
       done_total INT, fail_total INT, avg_latency_ms REAL, last_heartbeat TEXT)
   7.4 seeds(id PK, url TEXT UNIQUE, rule_name TEXT, interval_minutes INT, enabled INT,
       last_run_at TEXT)
   7.5 rules(id PK, name TEXT, domain_pattern TEXT, version INT, content TEXT,
       selector_spec_json TEXT, enabled INT, updated_at TEXT)
   7.6 compliance_log(id PK, url TEXT, domain TEXT, reason TEXT, robots_rule TEXT,
       checked_at TEXT)
   7.7 stats_snapshot(id PK, ts TEXT, scope TEXT, domain TEXT, qps REAL, success INT,
       failed INT, bytes INT, avg_latency_ms REAL)
   7.8 results（不入库，JSONL）：{"url": "...", "rule": "docs_site", "fields": {...},
       "links_found": 12, "crawl_time": "...", "worker_id": "w1", "http_status": 200}
   7.9 索引：tasks 上建 (state, priority desc)、idx_domain_state(domain, state)、
       uniq_url_hash；stats_snapshot 上建 (ts desc)、idx_scope_domain(scope, domain)。
   7.10 说明：Redis 中 dedup:urls 使用 SET 存指纹（或 Bloom 过滤器降低内存），
       queue:pending 使用 ZSET（score = priority * 1e12 + timestamp），
       queue:running 使用 HASH（task_id → 租约信息）。

【三、里程碑拆解（建议 4 ~ 6 个阶段）】

阶段一：单体抓取与规则引擎（约 18 小时）
  产出：httpx 抓取封装、编码处理、CSS 选择器规则解析、JSONL 输出、单进程顺序抓取。
  验收：对本地搭建的测试站（5 个页面）完整抓取，字段抽取正确率 100%，含分页。

阶段二：调度中心与去重队列（约 25 小时）
  产出：Redis 队列、URL 归一化与指纹去重、任务状态机、租约与超时回收、指标统计。
  验收：向队列灌入 1 万个含 30% 重复的 URL，去重后待抓数正确，重启调度中心不丢队列。

阶段三：限速、重试与合规（约 22 小时）
  产出：域名令牌桶（Lua）、域名并发上限、指数退避重试、robots.txt 检查与缓存、
       合规拦截记录与查询接口。
  验收：单域名 QPS 严格不超过配置值（用带时间戳的本地服务端记录验证）；robots 禁止的
       路径不入队且有记录。

阶段四：多工作者与容错（约 22 小时）
  产出：工作者心跳、优雅退出、任务续租、工作者离线后的租约回收、失败队列与批量重试。
  验收：启动 4 个工作者；杀掉其中 1 个，其未完成任务在 120 秒内被其他工作者接管完成。

阶段五：管理控制台与实时日志（约 20 小时）
  产出：概览页、工作者列表、域名视图、任务查询、失败队列操作、WebSocket 日志流、
       合规中心页面。
  验收：控制台数据与数据库/Redis 实际值一致；暂停后不再派发新任务，恢复后继续。

阶段六：测试、压测与部署（约 18 小时）
  产出：覆盖率报告、限速与去重的确定性测试、100 万 URL 队列内存与派发压测、Dockerfile
       与 docker-compose、部署与运维手册（含封禁处理与合规检查清单）。
  验收：队列 100 万条时调度中心内存占用与派发延迟达标；容器内一键启动并抓完测试站。

【四、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；使用 asyncio 编写抓取与派发热路径；类型注解全覆盖。
2. 允许使用的库：标准库（asyncio、hashlib、urllib.parse、urllib.robotparser、json、sqlite3、
   logging、signal、dataclasses、enum）；第三方限 FastAPI、uvicorn、redis、httpx、
   beautifulsoup4、lxml、pydantic、APScheduler、charset-normalizer、pytest、pytest-asyncio。
   禁止使用 Selenium/Playwright 等浏览器自动化绕过动态渲染限制（本项目只抓静态 HTML）。
3. 禁止事项：禁止绕过 robots.txt；禁止使用随机或伪造的 User-Agent 规避识别；禁止使用代理
   池对抗封禁；禁止抓取需要登录、付费或明显属于个人隐私的数据；禁止在代码中硬编码目标
   站点凭据；禁止对同一域名发起超过配置并发与 QPS 的请求；禁止把页面正文全文写进日志。
4. 合规要求（红线）：所有抓取活动必须用于学习研究与合法用途；框架必须默认开启 robots
   检查（compliance_strict=true），关闭该开关需要显式配置并在控制台顶部显示警告横幅；
   请求头中的 User-Agent 必须包含项目标识与可联系信息；遇到 429/503 必须自动降速，
   连续 3 次 429 时该域名 QPS 自动减半并记录告警；框架文档必须包含目标站点服务条款
   与著作权提示，抓取结果不得再分发。
5. 代码组织：common 不依赖 scheduler 与 worker；worker 只通过 HTTP API 与调度中心交互，
   不得直连 Redis（保证工作者可跨机部署）；调度中心不得执行解析逻辑；所有跨进程数据结构
   必须有 pydantic 模型定义与版本号，接口变更需兼容至少一个版本。
6. 一致性要求：任务“领取-执行-上报”必须满足至少一次语义，因此解析与结果输出必须幂等
   （同一 task_id 重复上报只落一条结果，写入 JSONL 前按 (task_id, url_hash) 查重）；
   去重集合与数据库状态不一致时以数据库为准并在启动时重建。
7. 编码规范：PEP 8；模块与公共函数必须有 docstring；日志采用 JSON 结构化格式并包含
   trace_id；禁止裸 except；所有网络异常必须分类为可重试与不可重试。
8. 测试要求：覆盖率 ≥ 70%；必须包含：URL 归一化表驱动测试（至少 30 组）、robots 拦截
   测试（含禁止路径与 Crawl-delay）、限速精度测试（1 秒内请求数不超过配置）、租约超时
   回收测试、工作者离线接管测试、重复上报幂等测试。
9. 性能要求：单工作者在局域网环境下稳定抓取 20 ~ 30 页/秒（页面平均 100 KB）；调度中心
   在队列 100 万条时派发接口 P95 ≤ 50 ms；单机 4 核 8 GB 支撑 8 个工作者与 50 个域名配置；
   Redis 内存占用不超过 1 GB（使用 Bloom 过滤器时不超过 300 MB）。
10. 安全要求：调度中心管理接口需 Token 鉴权（环境变量配置，禁止默认弱口令）；工作者的
    上报接口校验 worker 注册令牌；控制台不展示任何站点凭据；配置文件中不得存放账号密码，
    如需 Cookie 必须从环境变量注入。

【五、设计要点】

1. 数据结构：
   1.1 Task = (id, url, url_hash, domain, priority, depth, parent_url, retry, state)。
   1.2 队列三态：pending（待抓）、running（进行中，带租约）、failed / done（终态）。
   1.3 TokenBucket(domain, capacity, refill_rate, last_refill, tokens)，状态存 Redis HASH。
   1.4 Rule(name, domain_pattern, list_selector, item_selector, fields, next_page,
       allow_domains, deny_patterns, rule_version)。
   1.5 CrawlResult(url, rule, fields: dict[str, str | list[str]], links: list[str],
       http_status, bytes, elapsed_ms, task_id, worker_id)。
2. 关键算法与流程：
   2.1 URL 归一化与去重：解析 → 小写 host → 去默认端口 → 去 fragment → query 排序并
       过滤跟踪参数 → 去尾部斜杠（目录除外）→ sha1(url) 前 16 字节作为指纹。
   2.2 令牌桶（Lua 脚本）：先按 elapsed 补充令牌（上限为 capacity）→ 判断 tokens ≥ 1 →
       有则扣减并返回 1，否则返回 0 与建议等待毫秒；整个判断与扣减在一个脚本内原子完成。
   2.3 派发流程：从 ZSET 取 score 最小的候选（每次取 20 条）→ 逐条检查域名开关、域名并发、
       令牌、是否仍在进行中 → 首个通过者写入 running HASH 并返回给工作者；全部不通过时
       计算最早可派发时间并让工作者带 sleep_hint 返回。
   2.4 超时回收：调度中心后台任务每 10 秒扫描 running HASH 中 lease_until < now 的任务 →
       按重试次数决定放回 pending（retry+1）或置为 failed → 记录超时原因。
   2.5 重试退避：delay = base * (4 ** (retry - 1))，base=1 秒；退避通过把 score 加上未来
       时间戳实现延迟派发，不阻塞队列。
   2.6 增量种子：APScheduler 按 seeds.interval_minutes 周期性把种子 URL 重新入队，入队
       仍走去重，保证已抓过的页面不会重复抓取。
   2.7 结果幂等写入：以 (task_id, url_hash) 为幂等键，先在内存 set 与本地文件索引中查重，
       再追加写入 JSONL，避免重复上报产生重复数据。
   2.8 自治降速：当域名在 60 秒内出现 429 或 503 累计 3 次时，自动把该域名 qps 乘以 0.5
       （下限 0.1），并在控制台与日志中产生 WARN 告警。
3. 数据库主要表结构（关键字段与索引）已在功能清单第 7 节列出；补充约束：
   3.1 tasks.state 取值受限于 ('pending','running','done','failed','discarded')，使用 CHECK
       约束；discarded 必须带 fail_reason。
   3.2 domains.pages_crawled 达到 max_pages 时，调度中心拒绝该域名新任务入队并记录告警。
   3.3 workers 表只保留最近 7 天记录，历史数据由清理任务归档到 stats_snapshot。
4. 接口设计要点：
   4.1 领取任务响应结构：{"tasks": [...], "sleep_hint_ms": 0, "server_time": "..."}；
       无任务时返回空数组与建议休眠时间，禁止返回错误码让工作者忙重试。
   4.2 上报结果结构：{"task_id": "...", "status": "success|failed", "http_status": 200,
       "new_urls": ["..."], "result_count": 20, "elapsed_ms": 412, "fail_reason": null}。
   4.3 所有控制类接口（暂停、恢复、清空、改限速）写入 audit_log 并需要 Token。
   4.4 控制台与调度中心同源部署；WebSocket 日志按级别分频道，避免前端全量接收。

【六、运行方式与示例】

1. 安装与初始化
   python -m venv .venv && .venv\Scripts\activate
   pip install fastapi uvicorn redis httpx beautifulsoup4 lxml pydantic apscheduler
   pip install charset-normalizer pytest pytest-asyncio
   redis-server                       （或使用 docker run -p 6379:6379 redis:7）
   python -m scheduler.initdb         （建表并写入示例域名配置）
2. 启动
   uvicorn scheduler.app:app --host 127.0.0.1 --port 9000
   python -m worker.main --scheduler http://127.0.0.1:9000 --workers 4
   python -m worker.main --scheduler http://127.0.0.1:9000 --workers 4 --name w2
   浏览器打开 http://127.0.0.1:9000/console 查看控制台
3. 提交种子并抓取本地测试站
   curl -X POST http://127.0.0.1:9000/api/v1/seeds -H "X-Api-Token: $TOKEN" \
        -d '{"urls": ["http://127.0.0.1:8088/docs/index.html"], "rule_name": "local_docs"}'
4. 示例一（领取任务的请求与响应）
   请求：POST /api/v1/tasks/acquire
   {"worker_id": "w1-host-34721", "max_tasks": 2}
   响应：200
   {
     "tasks": [
       {"task_id": "t-8f21c0", "url": "http://127.0.0.1:8088/docs/index.html",
        "domain": "127.0.0.1:8088", "depth": 0, "retry": 0, "rule": "local_docs"},
       {"task_id": "t-8f21c1", "url": "http://127.0.0.1:8088/docs/api.html",
        "domain": "127.0.0.1:8088", "depth": 1, "retry": 0, "rule": "local_docs"}
     ],
     "sleep_hint_ms": 0, "server_time": "2025-01-15T10:00:00+08:00"
   }
5. 示例二（上报结果并带回新链接）
   请求：POST /api/v1/tasks/t-8f21c0/result
   {"task_id": "t-8f21c0", "status": "success", "http_status": 200,
    "new_urls": ["http://127.0.0.1:8088/docs/api.html",
                 "http://127.0.0.1:8088/docs/faq.html"],
    "result_count": 1, "elapsed_ms": 138, "fail_reason": null}
   响应：200 {"accepted": true, "queued_new": 2, "duplicated_new": 1}
   说明：api.html 若已存在则计入 duplicated_new，不重复入队。
6. 示例三（合规拦截）
   请求：提交种子 {"urls": ["http://example.com/private/admin"]}
   响应：200 {"accepted": false, "blocked": [{"url": "http://example.com/private/admin",
          "reason": "ROBOTS_DISALLOW", "rule": "Disallow: /private/"}]}
   控制台合规中心可查询到该条记录，tasks 表不产生任何行。
7. 示例四（限速生效的证据）
   配置：domains["127.0.0.1:8088"].qps = 1.0
   结果：本地测试服务器日志显示 10 秒内收到 10 次请求（允许 ±1 的时钟误差），
       控制台域名视图 QPS 指标稳定在 1.0，无 429 出现。
8. 示例五（异常与容错）
   场景 A：工作者 w2 被 kill -9，其 3 个进行中任务在 120 秒租约到期后被回收并重新派发给
          w1，最终这 3 个 URL 在 tasks 表中状态为 done。
   场景 B：站点返回 403：{"task_id": "...", "status": "failed", "http_status": 403,
          "fail_reason": "HTTP_403_NOT_RETRYABLE"}，任务直接进入 failed 队列，不再重试。

【七、验收标准】

[ ] 1. 抓取前对每个域名检查 robots.txt 并缓存；被 Disallow 的 URL 未进入 tasks 表，
      compliance_log 中有对应记录。
[ ] 2. 单域名 QPS 在 60 秒观察窗口内不超过配置值，验证使用本地记录时间戳的服务端日志。
[ ] 3. 向队列提交 10000 个含 30% 重复的 URL，pending 队列长度约为 7000，重复计数吻合。
[ ] 4. 4 个工作者同时运行，任务分布偏差不超过 20%（按完成数统计）；工作者视图实时更新。
[ ] 5. 强杀一个工作者后，其进行中任务在租约到期后被回收并最终完成，无任务永久卡在
      running 状态。
[ ] 6. 同一 task_id 重复上报 5 次，JSONL 结果文件只出现一条记录。
[ ] 7. 调度中心重启后队列与去重状态不丢失：重启前后 pending 数量与已完成 URL 集合一致。
[ ] 8. 暂停采集后 5 秒内不再有新任务被派发；恢复后 5 秒内派发恢复。
[ ] 9. 连续 3 次 429 后该域名 QPS 自动减半，日志与控制台产生 WARN 告警。
[ ] 10. 成功抓取 5 个本地页面后，JSONL 输出字段完整（url、rule、fields、crawl_time、
      worker_id），字段校验失败的记录被拒绝并计入 failed。
[ ] 11. URL 归一化表驱动测试 30 组全部通过（含大小写、默认端口、fragment、utm 参数、
      尾部斜杠等情形）。
[ ] 12. 队列达到 max_queue_size 时停止入队并产生告警，不再无限增长。
[ ] 13. 调度中心管理接口未带 Token 时返回 401，Token 错误返回 403。
[ ] 14. pytest 覆盖率 ≥ 70%，限速、去重、租约回收、合规四类专项测试全部通过。
[ ] 15. 提供部署文档与合规说明：包含 robots 政策、User-Agent 说明、目标站点服务条款
      与著作权提示，且明确本框架仅用于学习与合法用途。

【八、可选扩展】

1. 接入消息队列（RabbitMQ 或 Kafka）替换 Redis 队列，对比吞吐、可靠性与运维复杂度。
2. 增加 Bloom 过滤器与 Cuckoo 过滤器做亿级 URL 去重，比较内存与误判率。
3. 增加动态渲染支持（Playwright）作为可选插件，并默认禁用，需显式声明合规理由。
4. 增加分布式调度中心主备选举（Redis 锁或 etcd），消除单点。
5. 增加增量抓取：基于页面 etag/Last-Modified 与内容 sha1 判断是否需要重新解析。
6. 增加结果管道插件化：支持写入 PostgreSQL、Elasticsearch、对象存储，并支持字段映射。
7. 增加抓取质量评估：抽样人工标注与自动字段校验结合，输出抽取准确率报告。

【九、涉及知识点】

- 分布式任务调度：任务队列语义（至少一次）、租约与心跳、幂等上报、失败重试与退避
- Redis 高级用法：ZSET 优先级队列、HASH 状态、Lua 原子脚本、AOF 持久化与内存估算
- 异步编程：asyncio 事件循环、异步 HTTP 客户端、并发限流（Semaphore）与信号处理
- 网络协议细节：HTTP 重定向、字符集与编码探测、robots.txt 解析、Content-Type 判定
- 网页解析：CSS 选择器、lxml 解析性能、相对链接转绝对链接、规则化抽取设计
- 反爬与合规边界：robots 协议、Crawl-delay、User-Agent 规范、429 处理与自动降速
- 可观测性：结构化日志、指标聚合与滑动窗口、WebSocket 实时推送、控制台可视化
- 工程实践：配置与密钥管理、单机多进程与跨机部署、Docker 化、pytest 异步测试
================================================================================
