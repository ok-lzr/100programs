================================================================================
项目编号：084                    难度等级：★★★★☆（中型项目，偏难）
项目名称：网站可用性与证书监控
所属分类：运维监控 / 站点可用性
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：requests、APScheduler、SQLAlchemy、Flask、jinja2、rich
================================================================================

【一、项目背景与目标】

自建博客、公司官网、对外接口服务都依赖一个共同前提：域名能解析、HTTPS 证书没过期、服务
能正常返回内容。真实事故往往很朴素——证书到期前一周没人注意，某天凌晨自动续期失败，第二天
全站浏览器红屏；或者某个后端接口悄悄返回 500，直到用户投诉才发现。人工每天点开几个网址看
一眼既不现实，也无法形成可回溯的可用性数据。

本项目实现一个多站点可用性与证书监控系统。它按配置的间隔对一批目标地址发起 HTTP 探活，
记录状态码、响应时间、响应体关键字命中情况、重定向链长度与最终地址；同时建立 TLS 连接读取
证书的生效时间、到期时间、颁发者与主体，计算剩余有效天数；把每次探测结果写入时序存储，
按时间窗口计算可用率与响应时间的 P50/P95；当连续失败次数超过阈值或证书剩余天数低于阈值时
产生告警，告警必须支持去重与静默期，避免抖动导致通知风暴。

目标用户是需要同时盯十几个站点的个人站长、运维工程师，以及需要给学生演示“监控系统怎么
做”的教学场景。系统完成后可以提供：随时可打开的 Web 面板、可按目标与时间段查询的历史曲线
数据、可导出的可用性报表、以及通过邮件或 Webhook 发出的告警。

合规要求：只探测用户自己拥有或已获授权的站点；默认请求头带有可识别标识，遵守目标站点的
robots.txt 与访问频率限制；默认探测间隔不低于 30 秒，且对同一目标做串行探测，避免对小型
站点造成压力；本工具仅用于学习与自有系统运维。

【二、功能需求清单】

1. 核心功能
   1.1 目标管理：每个监控目标包含 target_id、name、url、method、interval_seconds、
       timeout_seconds、expected_status（可为范围如 200-299）、body_keyword（响应体必须
       包含的关键字）、headers、follow_redirects、verify_tls、enabled、tags。
   1.2 HTTP 探活：用 requests 发起请求，记录 dns_ms（可选）、connect_ms、ttfb_ms、
       total_ms（用 time.perf_counter 分段计时）、状态码、响应体前 64 KB 的字节数、
       是否命中关键字、重定向链（形如 http://a -> https://a -> https://a/home）。
       关键字未命中即使状态码为 200 也判定为失败，原因记为 keyword_miss。
   1.3 内容校验扩展：支持 --expect-json 校验响应体是合法 JSON，并可用 jsonpath 简化语法
       （如 data.status）判断字段值等于期望值。
   1.4 证书监控：对 https 目标建立 socket 连接并取 peer 证书，解析 notBefore、notAfter、
       subject、issuer、SAN 列表、签名算法，落库并计算 days_left。证书握手失败（自签、
       过期、域名不匹配）单独记录为 cert_error 并给出错误码。
   1.5 失败与恢复判定：连续失败次数达到 fail_threshold（默认 3 次）才判定目标 DOWN，
       连续成功次数达到 recover_threshold（默认 2 次）才判定 RECOVERED，中间状态记为
       DEGRADED，避免单次网络抖动误报。
   1.6 告警：告警类型包含 DOWN（目标不可用）、RECOVERED（恢复）、SLOW（响应时间超过
       slow_threshold_ms 连续 N 次）、CERT_EXPIRING（证书剩余天数低于 warn_days 阈值，
       分级为 30/14/7/3/1 天）、CERT_INVALID。告警写入 alerts 表并调用通知渠道。
   1.7 告警去重与静默期：以 target_id + alert_type 作为指纹，同一指纹在
       dedup_window_minutes（默认 10 分钟）内的重复告警只累加 repeat_count 不重复发送；
       静默期 silence_until 可由人工设置（silence 命令，支持 --for 2h 或 --until 指定时间），
       静默期内产生的告警仍然入库但不发送，恢复类告警不受静默期限制（保证知道好没好）。
   1.8 可用性统计：按小时与按天聚合，计算可用率 = 成功探测数 / 总探测数、
   平均响应时间、P50、P95、最大响应时间；CERT 剩余天数按天记录历史序列，用于画趋势。
   1.9 Web 面板：首页显示所有目标的状态灯、最近一次响应时间、证书剩余天数；目标详情页
       显示最近 24 小时响应时间折线数据（以 JSON 端点提供数据，用原生 Canvas 或 html 表格
       渲染）、最近 50 条探测记录与告警历史；告警页支持按类型与时间过滤。
   1.10 报表导出：export 命令按时间范围输出 CSV（每次探测一行）与 HTML 摘要（可用率、
       平均响应时间、最长故障时长）。

2. 输入与交互
   2.1 目标可用 CLI 逐条添加，也可从 YAML 批量导入：
       python -m monitor add --id blog --url https://blog.example.com --interval 60 ^
         --keyword "我的博客" --expect-status 200-299 --warn-days 30
   2.2 运行时命令：serve（启动调度与探测）、once（立即探测一轮）、list、show、silence、
       unsilence、export、web、doctor（自检：数据库可写、网络可达、通知渠道可用）。
   2.3 通知渠道配置在 config.yaml 中，包含 console、smtp、webhook 三种，凭据从环境变量
       MONITOR_SMTP_PASSWORD、MONITOR_WEBHOOK_TOKEN 读取，配置文件只写变量名。
   2.4 所有探测行为记录到目标自己的日志文件 logs/targets/<target_id>.log，便于单目标排查。

3. 输出与展示
   3.1 once 命令输出 ASCII 状态表：目标、状态码、响应时间、证书剩余天数、判定结果。
   3.2 serve 每轮探测打印一行结构化日志：target=blog status=UP code=200 ms=182 cert_days=64。
   3.3 Web 面板用纯服务端渲染 + 少量内联脚本，不依赖前端构建工具，页面在无网络环境下
       也能打开（静态资源内嵌）。
   3.4 告警消息格式固定为：[DOWN] blog https://blog.example.com 连续 3 次失败，
       最后一次 code=0 error=ConnectTimeout，开始时间 2025-03-16 10:02:11。

4. 异常与边界处理
   4.1 DNS 解析失败、连接超时、读超时、TLS 握手失败、证书过期分别给出不同 error_type，
       不能统一记成“请求失败”。
   4.2 目标返回 3xx 但 follow_redirects 为 false 时，按 expected_status 判定，并在记录中
       保留 Location 头。
   4.3 系统时间被调整导致 days_left 跳变时，以证书 notAfter 与当前 UTC 时间的绝对差值
       为准，不使用缓存值。
   4.4 单个目标探测异常不得影响其他目标与调度循环，用 try/except 包裹并计入该目标的
       失败计数。
   4.5 数据库写入失败（磁盘满、文件锁）时把结果写入本地 JSONL 缓冲文件，下次启动时回放
       入库，避免数据丢失。
   4.6 目标数量较大时限制并发探测数量（默认 8），超过时排队，避免打满本机网络。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；时间统一使用 UTC 存储，展示时按配置时区转换。
2. 允许使用的库：requests（HTTP 探测）、APScheduler（定时调度）、SQLAlchemy 2.x +
   SQLite（存储）、Flask + jinja2（面板）、rich（控制台表格）、pydantic（配置校验）、
   PyYAML（配置读取）、pytest（测试）。TLS 证书解析使用标准库 ssl 与
   ssl.SSLSocket.getpeercert()，socket 用于自定义握手端口，smtplib 用于邮件，
   statistics 用于分位数计算（或手写排序取分位）。
3. 禁止事项：禁止使用未授权的第三方网站作为监控目标；禁止把探测间隔设为小于 30 秒；
   禁止在代码或配置中硬编码邮箱授权码与 Webhook Token；禁止使用 verify=False 全局关闭
   证书校验（只允许按目标配置关闭并在报告中标记 insecure）。
4. 代码组织：模块划分为 prober（HTTP 与 TLS 探测）、tls_inspector（证书解析）、
   classifier（UP/DOWN/DEGRADED 状态机）、alerter（告警生成、去重、静默）、storage
   （模型与聚合查询）、scheduler（调度循环）、web（面板与 JSON 接口）、cli。
5. 编码规范：全部函数带类型注解与 docstring；数据库模型使用声明式 Base 并给关键字段建
   索引（target_id + checked_at）；日志使用 logging，禁止 print 做运行日志；异常分类用
   Enum（ConnectTimeout/DNSError/TLSError/HTTPError/KeywordMiss）。

【四、设计要点】

1. 数据结构
   - Target：target_id、name、url、method、interval_seconds、timeout_seconds、
     expected_status（字符串区间）、body_keyword、expect_json_path、expect_json_value、
     headers（dict）、follow_redirects、verify_tls、enabled、tags、fail_threshold、
     recover_threshold、slow_threshold_ms、warn_days。
   - ProbeResult：probe_id、target_id、checked_at、status_code、total_ms、connect_ms、
     ttfb_ms、ok（bool）、error_type、error_message、redirect_chain、body_bytes、
     keyword_hit、verdict（UP/DOWN/DEGRADED）。
   - CertInfo：cert_id、target_id、checked_at、subject、issuer、not_before、not_after、
     days_left、san（JSON）、sig_alg、valid（bool）、error_type。
   - AlertRecord：alert_id、target_id、alert_type、fingerprint、message、first_seen_at、
     last_seen_at、repeat_count、notified_at、silenced（bool）。
   - 状态机字段：target_state(target_id PK, verdict, consecutive_fail, consecutive_ok,
     since, last_change_at, silence_until)。
2. 关键算法或流程
   - 探测流程：读取目标配置 → 用 requests.Session 复用连接 → 分段计时发起请求 →
     记录状态码与耗时 → 校验 expected_status → 校验关键字或 JSON 字段 → 若 https 则
     另开 TLS 连接读取证书 → 组装 ProbeResult 落库 → 交给 classifier 更新状态机。
   - 状态机：ok 时 consecutive_ok 加一、consecutive_fail 清零；失败时反之。当
     consecutive_fail 达到 fail_threshold 且当前状态非 DOWN，才切到 DOWN 并生成告警；
     当 consecutive_ok 达到 recover_threshold 且当前状态为 DOWN，切到 UP 并生成
     RECOVERED 告警。其余情况保持原状态，仅更新指标。
   - 告警去重：fingerprint = sha1(target_id + alert_type) 前 12 位；发送前查询同指纹且
     last_seen_at 在 dedup_window 内的记录，命中则 repeat_count 加一并更新 last_seen_at，
     不发送；否则判断 silence_until 是否覆盖当前时间（RECOVERED 除外），再决定是否发送。
   - 分位数计算：把窗口内的 total_ms 排序后按 nearest-rank 取 P50 与 P95，样本少于 20 个
     时返回样本最大最小值区间并标注样本不足。
3. 接口或命令设计
   - CLI：python -m monitor serve --workers 8 --tick 5
   - CLI：python -m monitor add --id api --url https://api.example.com/health ^
     --interval 60 --timeout 10 --expect-status 200 --keyword '"status":"ok"' --warn-days 21
   - CLI：python -m monitor silence --id blog --for 2h --reason "计划内维护"
   - HTTP：GET / 面板首页；GET /target/<id> 详情页；GET /api/series/<id>?hours=24 返回
     {"points":[{"t":"...","ms":182,"ok":true}...]}；GET /api/alerts?type=DOWN&hours=72；
     POST /api/targets/<id>/pause 与 /resume 暂停或恢复监控。

【五、运行方式与示例】

安装与运行：
    pip install requests APScheduler SQLAlchemy Flask jinja2 rich pydantic PyYAML pytest
    python -m monitor init --db data/monitor.db
    python -m monitor import --file targets.example.yaml
    python -m monitor once
    python -m monitor serve --workers 8
    python -m monitor web --port 8090

示例一（立即探测一轮）：
    输入：python -m monitor once --tag prod
    输出：
      TARGET      VERDICT  CODE  MS     CERT_DAYS  NOTE
      blog        UP       200   182    64         -
      api         DOWN     0     5012   -          ConnectTimeout（连续 1/3）
      shop        DEGRADED 200   2410   11         SLOW 超过 2000ms 阈值（连续 2/3）

示例二（证书告警）：
    输入：python -m monitor list --cert
    输出：shop  https://shop.example.com  证书剩余 11 天（notAfter=2025-03-27T04:00:00Z）
          已发送告警 CERT_EXPIRING(fingerprint=9c2ab7f10de4)，静默期 360 分钟，重复失败不再通知

示例三（查询历史与导出）：
    输入：python -m monitor export --id blog --from 2025-03-01 --to 2025-03-16 --format csv
    输出：已导出 4321 条探测记录到 reports/blog_20250301_20250316.csv
          可用率 99.72%，平均 178 ms，P95 402 ms，最长故障 3 分 12 秒

示例四（异常输入）：
    输入：python -m monitor add --id bad --url "ftp://example.com" --interval 5
    输出：错误：不支持的协议 ftp；探测间隔 5 秒低于最小间隔 30 秒。
          目标未添加，数据库无变更，退出码 1

【六、验收标准】

[ ] 目标管理支持增删改查与 YAML 批量导入，非法 URL 与过短间隔被拒绝
[ ] 探测结果包含状态码、总耗时、连接耗时、TTFB 三项耗时且量级合理
[ ] 关键字未命中时即使状态码为 200 也判定失败，error_type 为 keyword_miss
[ ] 连续失败 3 次才产生 DOWN 告警，前两次为 DEGRADED 且不告警
[ ] 恢复后产生 RECOVERED 告警，且该告警不受静默期抑制
[ ] 证书剩余天数计算正确（与浏览器查看结果一致），30/14/7/3/1 天分级告警均可触发
[ ] 自签或过期证书被识别为 cert_error 且不影响该目标的 HTTP 探活记录
[ ] 同一指纹告警在 10 分钟窗口内只发送一次，repeat_count 正确累加
[ ] silence 命令设置静默期后普通告警不再发送但仍在库中可查
[ ] 按小时与按天的可用率、平均响应时间、P95 计算口径与手工核对一致
[ ] Web 面板首页、详情页、告警页均可打开，数据来自真实数据库
[ ] 数据库写入失败时结果进入 JSONL 缓冲并可在下次启动回放入库
[ ] 探测并发受限，同时运行目标数不超过配置的 workers 上限
[ ] 单元测试覆盖状态机、去重逻辑、证书剩余天数三部分且全部通过

【七、可选扩展】

1. 增加多地点探测：把探测执行器部署在两三台机器上，汇总结果区分“全网故障”与“单点网络
   问题”。
2. 增加 Webhook 到企业微信或钉钉机器人，支持告警卡片与一键静默链接。
3. 增加 Traceroute 与 DNS 解析链路采集，故障时自动附上定位信息。
4. 增加 SLA 月报：按目标输出月度可用率、故障时长、MTTR（平均恢复时间）并生成 PDF。

【八、涉及知识点】

- requests 的超时、重定向链、Session 连接复用与响应流式读取
- TLS 握手、证书链解析、notAfter/notBefore、SAN 与域名匹配校验
- 时序数据的表设计与按窗口聚合查询（GROUP BY 时间桶、分位数计算）
- 监控状态机（阈值、连续计数、抖动抑制）与告警工程（去重、静默期、分级）
- APScheduler 定时任务、并发控制与异常隔离
- Flask 服务端渲染、JSON 数据接口与轻量前端绘图
- 结构化日志、CSV/HTML 报表导出与数据可回溯性
- 采集伦理：授权范围、频率限制、可识别 User-Agent 与 robots.txt 遵守
================================================================================
