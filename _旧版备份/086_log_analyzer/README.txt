================================================================================
项目编号：086                    难度等级：★★★★☆（中型项目，偏难）
项目名称：日志聚合与异常检测
所属分类：运维监控 / 日志分析
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：watchdog、SQLAlchemy、Flask、jinja2、rich、pytest
================================================================================

【一、项目背景与目标】

一次线上故障排查最常见的开场是：登录三台机器，分别 grep 三个目录下的日志，把时间对不齐的
结果粘到聊天窗口里人肉比对。日志量大时更麻烦——每秒几千行，真正异常的可能只有几十行，但
没有任何工具能把“今天 10:05 的 NullPointerException 比平时多了 200 倍”这件事自动指出来。

本项目实现一个日志聚合与异常检测系统。它从多个来源（本地文件目录、glob 通配的文件集合、
程序通过 HTTP 上报的日志）持续收集日志行，把日志解析成结构化字段（时间戳、级别、来源、
进程或线程、消息体）；对消息体做模板挖掘，把 “Connection refused to 10.0.0.7:5432” 与
“Connection refused to 10.0.0.9:5432” 归为同一个模板；基于模板的历史频率建立基线，当某个
模板的词频在滑动窗口内相对基线突增时产生告警；Web 面板提供按来源、级别、关键字与时间范围
的检索，以及模板 TOP 排行与突增趋势。

目标用户是需要同时照看多台服务器日志的运维人员、排查线上问题的后端开发者，以及需要演示
“日志聚类与异常检测”原理的学习者。系统完成后，可以在不改造现有应用的前提下，仅通过读取
日志文件就能得到结构化检索能力与突增告警能力。

合规与边界：只采集用户显式配置的日志路径，不采集系统敏感目录；日志中可能含手机号、邮箱、
身份证号等个人信息，入库前默认做脱敏（正则替换为掩码），脱敏规则可配置；采集只读打开文件，
不修改、不删除原日志；系统明确声明数据仅用于本地学习与自有系统运维，禁止用于采集他人数据。

【二、功能需求清单】

1. 核心功能
   1.1 多源收集：支持三类 source——file（单个文件，支持滚动日志按 inode 与偏移量跟踪）、
       glob（如 logs/*.log，每 30 秒重新展开一次以发现新文件）、http（POST /api/ingest
       接收 JSON 数组，用于应用主动上报）。每个 source 有唯一 source_id、格式模板名与
       标签（如 host、service、env）。
   1.2 采集续读：为每个文件记录 (path, inode 或 file_id, offset, last_line_hash)，进程重启
       后从上次偏移继续读取；检测到文件被截断（大小小于上次偏移）或 inode 变化（轮转）时
       从新文件头部重新读取，并在日志中记录 rotation 事件。
   1.3 解析与结构化：内置三种日志格式解析器——apache_combined、python_logging（形如
       2025-03-16 10:00:05,123 ERROR [worker-1] message）、syslog（形如 Mar 16 10:00:05
       host app[123]: message），并支持用户以命名正则组自定义格式。解析结果字段统一为
       ts、level、source_id、logger、pid、thread、message、raw。
   1.4 脱敏：入库前对 message 与 raw 应用脱敏规则（手机号、邮箱、IPv4、身份证号、
       疑似 token 的长十六进制串），默认启用，可对某 source 关闭；脱敏只影响入库与展示，
       不修改原始文件。
   1.5 模板挖掘：把 message 中的变量部分（数字、UUID、IP、路径、引号内容、十六进制串）
       替换为占位符得到模板；再与已存在的模板集合计算相似度（按分词后的 Jaccard 相似度
       或编辑距离），相似度超过 0.7 则归入已有模板，否则新建模板。模板表记录首次出现
       时间、累计次数、示例原文与变量示例。
   1.6 频率统计与基线：按 1 分钟粒度统计每个模板的出现次数，形成时间序列；基线用过去
       7 天同一时刻（或同一小时）的中位数与 MAD（绝对中位差）估计。当前窗口次数超过
       中位数加 k 倍 MAD（默认 k=4）且绝对次数不低于 min_count（默认 10）时判定为突增。
   1.7 错误级别专项：ERROR 与 FATAL 级别日志单独统计，滑动窗口内占比超过基线两倍或
       出现全新模板（首次出现且级别为 ERROR 以上）时立即告警，不受 min_count 限制。
   1.8 告警去重与静默期：指纹为 template_id + alert_type；同一指纹在
       dedup_window_minutes（默认 20 分钟）内只累加 repeat_count 不重复发送；静默期通过
       CLI silence --source 或 --template 设置，静默期内告警入库不发；恢复（窗口频次回到
       基线以下）产生 RESOLVED 通知且不受静默期抑制。
   1.9 检索与面板：全文检索基于 SQLite FTS5 虚拟表（不可用时退化为 LIKE 查询），支持
       按来源、级别、时间范围、关键字与模板 ID 过滤；面板包含总览（各来源日志速率与错误
       率）、模板排行（TOP 50，含迷你趋势）、突增事件列表、日志检索页与单条详情页。

2. 输入与交互
   2.1 配置文件 sources.yaml 定义全部来源与解析格式；CLI 支持 source add/ls/rm 动态管理。
   2.2 命令：init、collect（前台采集）、serve（采集 + 面板）、tail（实时打印匹配关键字的
       日志行）、search、templates（查看模板排行）、alerts、silence、unsilence、ingest-test、
       export（导出检索结果为 JSONL 或 CSV）。
   2.3 HTTP 上报接口：POST /api/ingest，请求体 {"source_id":"app1","lines":[...]}，
       返回 {"accepted": 120, "rejected": 0}；单次上限 500 行，超出返回 413 并提示分批。
   2.4 检索语法：search 支持 --level ERROR,FATAL、--since 1h、--grep "connection refused"
       （大小写不敏感）、--template 4f2a，多条件为与关系。

3. 输出与展示
   3.1 tail 命令以 rich 实时渲染，ERROR 行标红，按模板折叠（相同模板在 3 秒内连续出现时
       合并显示为“x N”）。
   3.2 templates 命令输出：模板 ID、模板文本、累计次数、最近 1 小时次数、较基线倍数、
       首次出现时间。
   3.3 突增告警消息格式：[SPIKE] template=4f2a "Connection refused to <IP>:<PORT>"
       最近 5 分钟 312 次，基线 12 次（中位数 8，MAD 2，k=4），来源 app1@web-01。
   3.4 面板总览用表格 + 迷你柱状图展示各来源最近 60 分钟每分钟的日志行数与错误数。

4. 异常与边界处理
   4.1 日志行跨读取边界被切断时，把不完整的最后一行暂存到缓冲区，与下次读到的内容拼接
       后再解析；超过 1 MiB 仍未出现换行的超长行按截断处理并标记 truncated。
   4.2 编码问题：优先使用 utf-8，解码失败时按 errors=replace 处理并计数；GBK 日志可通过
       配置 source.encoding 指定。
   4.3 解析失败的行不丢弃，存入 unparsed 表并计入解析失败率；解析失败率超过 20% 时在
       面板与日志中给出“格式配置可能不正确”的提示。
   4.4 单个来源读取异常（文件被锁定、权限不足、路径不存在）不影响其他来源，采集循环
       继续运行并给出来源状态（OK/STALE/ERROR）。
   4.5 数据量控制：单条 message 超过 8000 字符被截断；raw 字段可配置是否保留；超过保留期
       （默认 14 天）的明细日志被归档为按天压缩文件后删除。
   4.6 模板表规模失控（超过 5 万个模板）时，提示用户提高相似度阈值或增加变量替换规则，
       并对低频模板做合并。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；字符串处理全部注意编码显式声明；正则使用预编译
   （re.compile）避免重复编译开销。
2. 允许使用的库：watchdog（文件变更监听，实现近实时采集）、SQLAlchemy 2.x（存储与
   FTS5 建表）、Flask + jinja2（面板与上报接口）、rich（终端渲染）、pandas（可选，用于
   批量统计与导出）、PyYAML（配置）、pytest（测试）。文件读取、正则、哈希、JSON、
   统计（statistics.median）一律使用标准库。
3. 禁止事项：禁止修改或删除被采集的日志文件；禁止默认把日志原文上传到任何外部服务；
   禁止在未脱敏的情况下把含个人信息的字段写入数据库；禁止硬编码数据库口令；禁止在
   采集循环中使用 while True 加 sleep(0) 的空转轮询。
4. 代码组织：模块划分为 sources（来源管理、文件跟踪与偏移存储）、parsers（各类格式解析
   器与自定义正则）、sanitizer（脱敏规则）、templater（变量替换与模板匹配）、stats（分钟
   级统计与基线计算）、detector（突增与错误专项判定）、alerter（去重、静默、通知）、
   store（写入、FTS 检索、归档清理）、webapp、cli。
5. 编码规范：全部函数带类型注解与 docstring；正则模板集中放在一个模块并逐条写注释说明
   匹配目标；数据库写入使用批量 executemany；日志使用 logging 且采集器自身日志不得写入
   被采集目录，避免自我递归。

【四、设计要点】

1. 数据结构
   - Source：source_id、kind（file/glob/http）、path_pattern、format（解析器名或自定义
     正则）、encoding、tags（JSON）、enabled、sanitize（bool）、retain_raw（bool）。
   - FileCursor：source_id、path、file_id、offset、last_read_at、last_line_hash、state。
   - LogRecord：record_id、ts、source_id、level、logger、pid、thread、message、raw、
     template_id、parsed（bool）、truncated（bool）。
   - Template：template_id、pattern（含占位符的模板文本）、tokens（JSON，分词结果）、
     first_seen_at、last_seen_at、total_count、sample_raw、sample_vars（JSON）。
   - TemplateBucket：template_id、bucket_ts（分钟对齐）、count、error_count。
   - AlertRecord：alert_id、template_id、alert_type（SPIKE/NEW_ERROR/RESOLVED）、
     baseline_median、baseline_mad、observed_count、fingerprint、repeat_count、
     first_seen_at、last_seen_at、silenced、notified_at。
   - 索引：log_records(ts)、log_records(source_id, ts)、log_records(template_id, ts)、
     template_buckets(template_id, bucket_ts) 唯一索引、FTS5(message, raw) 虚拟表。
2. 关键算法或流程
   - 采集流程：watchdog 事件（或 1 秒轮询兜底）触发某文件读取 → 从 FileCursor.offset 开始
     读新字节 → 按换行切分并把残留存入缓冲 → 逐行解析为 LogRecord → 脱敏 → 模板匹配
     （命中则复用 template_id，未命中则新建）→ 批量入库 → 更新 FileCursor。
   - 模板生成：对 message 依次应用规则——数字串替换为 <NUM>、UUID 替换为 <UUID>、
     点分 IP 替换为 <IP>、形如 /a/b/c 的路径替换为 <PATH>、引号内内容替换为 <STR>、
     长度不小于 16 的十六进制串替换为 <HEX>、剩余数字与字母混合的长 token 替换为 <ID>；
     得到候选模板文本后再做分词与相似度比较。
   - 相似度匹配：把模板按非字母数字边界切分为 token 集合，计算 Jaccard 相似度
     J = |A∩B| / |A∪B|；在模板索引（按 token 建倒排，取交集候选）中找 J 最大者，若
     J 不小于 0.7 且 token 数差值不超过 2 则归入该模板。
   - 突增判定：读取当前 5 分钟窗口计数 observed，与基线（同小时段过去 7 天的中位数
     median 与 MAD）比较，判定条件为 observed 不小于 min_count 且
     observed - median 大于 k * max(MAD, 1)；同时要求 observed 不小于 median * 2，避免
     低频模板误报。窗口结束 5 分钟后做一次复核，仍满足则告警。
   - 去重与静默：fingerprint = sha1(template_id + alert_type + source_id) 前 12 位；同一
     指纹在 20 分钟内只发一次，重复时累加 repeat_count 并更新 observed_count 峰值；
     silenced_until 覆盖当前时间时不发送；RESOLVED 一律发送。
   - 归档清理：每天凌晨把 ts 早于保留期的 log_records 按天导出为 logs-YYYYMMDD.jsonl.gz，
     校验行数后删除原始行；模板与桶统计按聚合粒度保留更长时间（默认 90 天）。
3. 接口或命令设计
   - CLI：python -m loghub init --db data/loghub.db
   - CLI：python -m loghub source add --id web01 --kind glob --pattern "D:\logs\*.log" ^
     --format python_logging --tags host=web-01,env=prod
   - CLI：python -m loghub serve --web-port 8096 --workers 4
   - CLI：python -m loghub search --since 2h --level ERROR,FATAL --grep "connection refused" --limit 50
   - HTTP：GET /api/templates?limit=50&order=spike 返回模板排行；
     GET /api/alerts?hours=24 返回突增事件；GET /api/search?q=timeout&level=ERROR 返回日志；
     POST /api/ingest 接收应用上报。
   - 核心函数：parse_line(raw, fmt, encoding) -> LogRecord | None；
     build_template(message) -> str；match_template(candidate, index) -> str（返回 template_id）；
     detect_spike(bucket_counts, baseline, k, min_count) -> bool。

【五、运行方式与示例】

安装与运行：
    pip install watchdog SQLAlchemy Flask jinja2 rich pandas PyYAML pytest
    python -m loghub init --db data/loghub.db
    python -m loghub source add --id app --kind file --pattern .\sample\app.log --format python_logging
    python -m loghub serve --workers 4 --web-port 8096

示例一（聚类效果）：
    输入：python -m loghub templates --since 1h --limit 5
    输出：
      TEMPLATE                                 COUNT  LAST_1H  SPIKE  FIRST_SEEN
      4f2a  Connection refused to <IP>:<PORT>  1842   312      26.0x  2025-03-10T02:11:40
      9b31  User <ID> login failed             402    12       0.9x   2025-03-11T08:00:02
      c7d0  GET <PATH> <NUM> <NUM>             98120  8210     1.0x   2025-03-01T00:00:01

示例二（突增告警与去重）：
    输入：python -m loghub alerts --hours 1
    输出：
      [10:42:11] [SPIKE] template=4f2a "Connection refused to <IP>:<PORT>"
                 最近 5 分钟 312 次，基线中位数 8，MAD 2，k=4，来源 app@web-01
                 fingerprint=6d1c9a70bb42 去重窗口 20 分钟（repeat_count=3）
      [10:58:40] [RESOLVED] template=4f2a 最近 5 分钟 6 次，已回到基线以下

示例三（检索）：
    输入：python -m loghub search --since 30m --level ERROR --grep "timeout"
    输出：
      10:55:02 ERROR [worker-3] upstream timeout after 30000 ms url=/api/orders
      10:55:07 ERROR [worker-1] upstream timeout after 30000 ms url=/api/users
      共命中 2 条，耗时 41 ms（FTS5 检索）

示例四（异常输入）：
    输入：python -m loghub source add --id bad --kind file --pattern .\logs\app.log --format myfmt
    输出：错误：未知的日志格式 "myfmt"，可选值为 apache_combined、python_logging、syslog
          或形如 (?P<ts>...)(?P<message>...) 的自定义正则；来源未添加，退出码 1

示例五（编码与解析失败）：
    输入：python -m loghub collect --once --source legacy
    输出：警告：logs/legacy.log 使用 GBK 解码（3 行含替换字符）
          解析失败 12 行已存入 unparsed 表，解析失败率 3.2%（未超过 20% 阈值）

【六、验收标准】

[ ] 三类来源（file、glob、http 上报）均能采集到日志并正确落库
[ ] 进程重启后从上次偏移继续读取，不重复入库也不漏行（用行数核对）
[ ] 检测到日志轮转（inode 变化）或截断时重新从头部读取并记录 rotation 事件
[ ] 跨读取边界的半行被正确拼接，超长行被标记 truncated 且不撑爆数据库
[ ] 三种内置格式与自定义正则均可解析，解析失败行进入 unparsed 表而非被丢弃
[ ] 脱敏规则对手机号、邮箱、IP、身份证号、长十六进制串均生效，可对 source 关闭
[ ] 同一类消息中的 IP、数字、UUID、路径被替换为占位符并归入同一模板
[ ] 相似但不同的模板不会被错误合并（用一组构造样例做回归验证）
[ ] 突增判定在构造数据上符合公式：observed 不小于 min_count 且超过 median + k*MAD
[ ] ERROR 级别新模板首次出现即告警，不受 min_count 限制
[ ] 同一指纹告警在 20 分钟内只发送一次且 repeat_count 正确累加
[ ] 静默期内的告警入库并可查，恢复通知不受静默期抑制
[ ] 全文检索按来源、级别、时间、关键字过滤结果正确，FTS5 不可用时自动降级
[ ] 采集器自身日志不会写入被采集目录，不会造成自我递归
[ ] 超过保留期的明细日志被归档为按天 gz 文件，行数与数据库删除行数一致

【七、可选扩展】

1. 对接 Elasticsearch 或 Loki 作为存储后端，把 store 模块抽象成接口，支持两种实现切换。
2. 增加告警上下文快照：突增时自动抓取该模板前后 20 条原始日志作为附件发送，便于快速定位。
3. 增加日志与指标的关联分析：把误码率、响应时间指标与日志模板频次做时间对齐，输出相关性
   排序。
4. 增加多节点采集：远程主机只跑轻量采集代理，通过 HTTP 上报到中心节点统一聚类与告警。

【八、涉及知识点】

- 文件增量读取、偏移量与文件标识跟踪、日志轮转检测
- 多种日志格式的正则解析与编码问题处理
- 敏感信息脱敏的正则实现与性能考量
- 日志模板挖掘（变量替换 + 分词 + 相似度聚类）与倒排索引加速
- 时间序列分桶统计、中位数与 MAD 稳健基线、突增检测阈值设计
- SQLite FTS5 全文检索与降级方案
- 告警工程：指纹去重、重复计数、静默期、恢复通知
- watchdog 文件事件监听、批量入库、数据保留与归档压缩
- 数据合规：最小化采集、脱敏、只读原则与使用边界声明
================================================================================
