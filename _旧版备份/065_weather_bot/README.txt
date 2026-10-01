================================================================================
项目编号：065                    难度等级：★★★★☆（中型项目）
项目名称：天气与日程推送机器人
所属分类：自动化与报表 / 定时推送服务
建议工时：3 ~ 4 天
运行环境：Python 3.10+    第三方依赖：requests、APScheduler、jinja2
================================================================================

【一、项目背景与目标】

每天出门前要分别看天气、翻日历、扫一眼待办清单，三件事分散在三个应用里，很容易漏。本项目
把这些信息在固定时间汇总成一条消息，通过邮件或 webhook（企业微信、钉钉、飞书等群机器人）
推送到你手上，早上 7:30 一条“今天要带伞、10 点有评审会、还有 2 个任务今天到期”。

目标用户是需要固定晨间简报的上班族、要给自己或小团队做提醒的开发者。做成之后，每天的推送
内容包含：当日天气实况与预报（温度、降水概率、风力、紫外线）、未来 3 天趋势、今日日程安排、
未来 48 小时待办到期项、以及一句根据天气自动生成的生活提示（如“降水概率 80%，记得带伞”）。

数据来源与合规说明：天气数据来自公开免费接口（如 Open-Meteo 公开接口或 wttr.in），调用前阅读
其使用条款，遵守调用频率限制（本项目默认每小时最多刷新 4 次并对结果做缓存），不并发请求、
不批量拉取历史数据；日程与待办数据全部来自本机文件（ICS 文件与 todos.json），不上传、不共享。
推送消息仅发给配置中列明的收件人，禁止用于群发营销。所有账号口令与 webhook 地址通过环境变量
或本地未提交的 config.ini 提供，代码中禁止硬编码。

【二、功能需求清单】

1. 核心功能
   1.1 天气获取：按城市（支持中文名与经纬度两种配置方式）获取当日与未来 3 天的数据，
       字段包括最高/最低温、当前温度、天气现象、降水概率、风速、紫外线指数、日出日落时间。
   1.2 天气缓存：同一城市同一小时内的重复请求直接读缓存（cache/weather_<city>_<YYYYMMDDHH>.json），
       缓存过期自动刷新，避免超过接口频率限制。
   1.3 日程读取：解析本地 ICS 文件（支持 VEVENT 的 DTSTART、DTEND、SUMMARY、LOCATION、RRULE 简单
       每日/每周重复），提取今日与明日的日程；全天事件单独标注。
   1.4 待办读取：从 todos.json 读取任务（字段 title、due、priority、done、tags），
       筛选出 48 小时内到期且未完成的任务，按到期时间升序排列，逾期任务置顶并标注“已逾期 N 天”。
   1.5 生活提示生成：按规则生成 1~3 条提示，规则包括降水概率 >= 60% 带伞、最高温 >= 33 度防晒、
       最低温 <= 5 度加衣、紫外线 >= 7 防晒、风速 >= 6 级注意出行、温差 >= 10 度注意穿搭。
   1.6 消息渲染：用 jinja2 模板渲染纯文本与 HTML 两种版本；纯文本用于 webhook markdown，
       HTML 用于邮件正文；模板文件位于 templates/ 目录，可自行修改而无需改代码。
   1.7 定时推送：APScheduler 配置多个推送时间点（默认 07:30 与 21:00），工作日与周末可使用
       不同时间表；支持 --send-now 立即推送一次用于调试。
   1.8 推送渠道：邮件（SMTP，支持多个收件人）与 webhook（POST JSON 或 markdown 文本），
       渠道可多选；每次推送记录结果到 logs/push.log。
   1.9 推送去重与静默期：同一天同一时段的推送只允许成功发送一次（成功则写入 sent_state.json），
       进程重启后不会重复发送；失败可重试，手动 --force 可强制重发。
2. 输入与交互
   2.1 命令行：--config 配置路径；--city 覆盖配置中的城市；--date 生成指定日期的简报
       （用于补发或预览）；--send-now；--preview-only 只打印不发送；--force 忽略已发送状态。
   2.2 config.ini 段落：weather（城市、坐标、超时）、schedule（推送时间、时区）、
       mail（服务器、端口、发件人）、webhook（地址）、files（ICS 路径、todos 路径）。
   2.3 时区统一使用配置文件中的时区（默认 Asia/Shanghai），所有时间比较前先本地化。
3. 输出与展示
   3.1 控制台打印简报预览（纯文本版）与各渠道发送结果。
   3.2 output/digest_<YYYYMMDD_HHMM>.txt 保存每次推送的纯文本快照，便于事后核对。
   3.3 logs/push.log 记录时间戳、渠道、收件人数、成功与否、错误摘要。
4. 异常与边界处理
   4.1 天气接口不可用时：使用最近一次成功缓存并在消息中标注“天气数据可能过期（截至 XX:XX）”，
       缓存也不存在时跳过天气段但其余段落照常推送，绝不因为一个数据源失败而整体不发。
   4.2 ICS 文件不存在或解析失败时，日程段显示“未配置日程数据”，并记录警告而不中断推送。
   4.3 todos.json 格式错误（非 JSON 或字段缺失）时提示具体行号，跳过待办段。
   4.4 时间非法（如 todos 中 due 字段不是 ISO 格式）时该条任务跳过并在日志中记录任务标题。
   4.5 邮件发送失败重试 2 次（间隔 5 秒、15 秒），webhook 失败重试 2 次（间隔 2 秒、6 秒）；
       渠道全部失败时退出码为 4，便于计划任务识别。
   4.6 推送内容为空（无天气、无日程、无待办）时仍发送一条“今天没有特别安排”的简报，
       不静默失败，避免用户误以为程序坏了。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用类型注解与 dataclass。
2. 允许使用的库：requests、APScheduler、jinja2；其余使用标准库（smtplib、email.message、
   icalendar 不可用时自行用标准库解析 ICS 文本、json、configparser、argparse、logging、
   datetime、zoneinfo、pathlib、os、re）。
3. 禁止事项：禁止在代码中硬编码邮箱密码、webhook 地址与手机号；禁止把待办与日程数据上传到
   任何第三方服务；禁止对天气接口高频轮询（必须经过缓存层）；禁止把简报内容写入公共日志文件。
4. 代码组织：config.py（配置加载与校验）、models.py（WeatherSummary、CalendarEvent、TodoItem、
   DailyDigest）、weather.py（获取与缓存）、calendar_reader.py（ICS 解析）、todo_reader.py、
   advise.py（提示规则）、render.py（jinja2 渲染）、notifier.py（邮件与 webhook）、
   scheduler.py（定时任务与发送状态）、main.py。
5. 编码规范：所有公开函数写 docstring；日期时间统一使用带时区的 aware datetime；
   模板渲染与业务逻辑分离，禁止在 Python 代码里拼长段 HTML；日志使用 logging 且分级；
   配置项缺失时给出明确的中文错误提示并指明配置文件位置。
6. 测试要求：advise.py 的提示规则、todo_reader 的到期筛选（含逾期置顶）、ICS 简单重复事件
   展开三部分必须有 pytest 用例；推送函数在测试中被替换，禁止真实发信。

【四、设计要点】

1. 数据结构
   1.1 WeatherSummary：city(str)、date(str)、current_temp(float)、temp_max(float)、temp_min(float)、
       condition(str)、precip_prob(int)、wind_level(str)、uv_index(float)、sunrise(str)、sunset(str)、
       from_cache(bool)、cache_time(str|None)。
   1.2 CalendarEvent：summary(str)、start(datetime)、end(datetime|None)、location(str|None)、
       all_day(bool)、calendar_name(str)。
   1.3 TodoItem：title(str)、due(datetime|None)、priority(str，high/medium/low)、done(bool)、
       tags(list[str])、overdue_days(int)。
   1.4 DailyDigest：date(str)、weather_today(WeatherSummary|None)、weather_trend(list[WeatherSummary])、
       events_today(list[CalendarEvent])、events_tomorrow(list[CalendarEvent])、
       todos_due(list[TodoItem])、tips(list[str])、generated_at(str)。
   1.5 状态文件 sent_state.json：{"2024-05-20|07:30": {"sent_at": "...", "channels": ["email"],
       "success": true}}，用于跨进程去重。
2. 关键算法或流程
   2.1 主流程：加载配置 → 读取天气（缓存优先）→ 读取日程 → 读取待办 → 生成提示 →
       渲染模板 → 去重检查 → 逐渠道发送 → 写入快照与状态文件。
   2.2 去重键：f"{本地日期}|{任务名}"，例如 "2024-05-20|morning"；发送成功才写入状态，
       失败不写入以便下次重试；--force 时忽略已存在状态。
   2.3 ICS 解析：逐行读取，遇到 BEGIN:VEVENT 开始收集属性，支持续行（以空格或制表符开头的行
       表示上一行内容的延续）；DTSTART 支持 YYYYMMDD 与 YYYYMMDDTHHMMSSZ 两种格式；
       RRULE 仅支持 FREQ=DAILY 与 FREQ=WEEKLY 且展开窗口不超过 14 天，其他规则原样记录一次。
   2.4 待办排序：先按是否逾期（逾期排前），再按 due 升序，最后按优先级 high > medium > low。
   2.5 天气趋势：未来 3 天逐日给出最高/最低温与天气现象，用一行文本表示，如
       “05-21 多云 22~30度 降水 20%”。

【五、运行方式与示例】

安装依赖：
   pip install requests APScheduler jinja2

配置：
   复制 config.example.ini 为 config.ini，填写城市、推送时间、SMTP 信息；
   设置环境变量 MAIL_PASSWORD 与 WEBHOOK_URL，程序从环境变量读取，不写入配置文件仓库。

运行示例一（预览不发送）：
   python main.py --preview-only --date 2024-05-20
   输出：
   ==== 2024-05-20（周一）每日简报 ====
   【天气】上海 今天多云转小雨，22~28 度，降水概率 75%，东南风 3 级，紫外线 5
   【提示】降水概率较高，出门请带伞；昼夜温差 6 度，注意增减衣物
   【日程】09:30-10:30 产品评审会（会议室 A）
   【日程】14:00-15:00 与客户对齐需求（线上）
   【待办】[高] 提交周报（今天 18:00 到期）
   【待办】[中] 整理接口文档（逾期 2 天）
   =================================

运行示例二（立即推送）：
   python main.py --send-now --force
   输出：
   [INFO] 简报已渲染，纯文本 28 行，HTML 76 行
   [INFO] 邮件发送成功，收件人 2 人，耗时 1.8s
   [INFO] webhook 发送成功，状态码 200，耗时 0.4s
   [INFO] 快照已保存：output/digest_20240520_0730.txt
   [INFO] 状态已写入：sent_state.json（键 2024-05-20|07:30）

运行示例三（常驻按点推送）：
   python main.py --config config.ini
   输出：
   [INFO] 调度器已启动，时区 Asia/Shanghai
   [INFO] 已注册推送任务：07:30（工作日）、09:00（周末）、21:00（每日）
   [INFO] 下一次推送时间：2024-05-21 07:30:00 +08:00

异常示例：
   python main.py --send-now --config missing.ini
   输出：
   [ERROR] 配置文件不存在：missing.ini（请先复制 config.example.ini）
   [ERROR] 未执行任何推送（退出码 2）

【六、验收标准】

[ ] 同一小时内重复运行天气获取，第二次命中缓存且无网络请求（可用抓包确认）
[ ] 天气接口失败时使用过期缓存并在简报中标注缓存时间
[ ] 天气接口与缓存都不可用时仍能推送其余段落
[ ] ICS 中全天事件被标注为全天且不参与时间排序
[ ] ICS 中 FREQ=WEEKLY 的事件在未来 14 天窗口内按正确日期展开
[ ] 待办中逾期任务排在未逾期任务之前，并显示逾期天数
[ ] 48 小时之外的待办不出现在简报中
[ ] 降水概率 75% 时自动生成带伞提示
[ ] 纯文本与 HTML 两个版本内容一致（同一数据源渲染）
[ ] 同一天同一时段第二次运行不会重复发送，--force 可强制重发
[ ] 进程重启后 sent_state.json 生效，不会重复推送
[ ] 邮件全部失败时退出码为 4，且 logs/push.log 记录了错误摘要
[ ] 简报纯文本快照文件按日期时间命名并正确保存
[ ] 配置中缺少必填项时给出中文错误提示并指明文件与字段名
[ ] 代码与日志中不出现邮箱密码、webhook 密钥明文

【七、可选扩展】

1. 增加推送前的内容变化检测：与昨天简报相比若没有新增日程与待办，则发送精简版简报。
2. 增加多城市支持，一次推送给出“常驻城市 + 出差城市”两份天气对比。
3. 增加生日与纪念日提醒（从 ICS 或独立 anniversaries.json 读取），提前 3 天开始提示。
4. 增加 webhook 消息卡片格式适配（企业微信 markdown、钉钉 markdown、飞书 interactive card）。

【八、涉及知识点】

- HTTP 接口调用、JSON 响应解析与本地文件缓存策略
- 时区处理（zoneinfo）与 aware datetime 比较
- ICS 日历格式解析与简单重复规则展开
- jinja2 模板渲染（纯文本与 HTML 双模板）
- APScheduler 的 CronTrigger 与多任务调度
- smtplib 发送 HTML 邮件与多收件人处理
- webhook 推送与失败重试
- 发送状态持久化实现跨进程去重
- 配置管理（configparser + 环境变量）与敏感信息保护
- 单点失败隔离设计：多数据源中一个失败不影响整体输出
================================================================================
