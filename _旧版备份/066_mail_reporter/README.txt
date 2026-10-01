================================================================================
项目编号：066                    难度等级：★★★★☆（中型项目）
项目名称：自动邮件报表系统
所属分类：自动化与报表 / 邮件服务
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：requests、jinja2、pandas、openpyxl
================================================================================

【一、项目背景与目标】

工作中经常遇到“每周一早上把上周数据导出来，做成表，加几句说明，发给三个不同的群组”这类任务，
做一次不难，做一百次就是纯浪费时间，而且人工操作必然出现漏发、附件错版本、某个组没收到的情况。
本项目把这件事完全自动化：定义报表模板与数据源，配置收件人分组，程序自动生成正文与附件、
按组分发、失败重试，并留下可追溯的发送台账。

目标用户是需要定期发送经营周报、监控日报、财务月报的开发者与运营人员。做成之后，
只要数据文件按约定落位，一条命令或一个定时任务就能完成“取数、算指标、渲染正文、生成附件、
分组发送、记录结果”的全流程，任何一组发送失败都能在台账里查到原因并单独重发。

安全与合规要求：所有邮箱凭据必须来自环境变量或本地未提交的 config.ini，代码与日志中禁止出现
明文密码；发件必须使用配置中显式列明的收件人白名单，禁止向名单外地址群发；附件内容属于内部
数据，程序不得把任何报表内容上传到第三方服务；发送频率需遵守邮箱服务商的限制（本项目默认
同一账号每分钟不超过 20 封，单封收件人不超过 50 个），避免被判定为垃圾邮件；收件人邮箱属于
个人信息，测试环境必须使用脱敏的测试地址，禁止把真实收件人列表提交到公共仓库。

【二、功能需求清单】

1. 核心功能
   1.1 报表定义：一个 jobs/*.json 任务文件定义一个报表，字段包含 job_id、标题、模板名、
       数据源列表、附件规格、收件人分组、是否启用、发送时间描述。
   1.2 数据源读取：支持 CSV、JSON、SQLite 表、Excel 四种来源；CSV 自动识别编码（UTF-8、GBK）
       与分隔符；SQLite 通过 SQL 语句取数；所有数据统一转换为 pandas DataFrame。
   1.3 指标计算：支持配置派生列（如 环比 = 本期 / 上期 - 1）与汇总口径（求和、均值、计数、去重计数），
       派生表达式仅允许白名单函数（abs、round、min、max、len），禁止使用 eval 直接执行任意代码。
   1.4 正文渲染：用 jinja2 模板渲染 HTML 正文与纯文本兜底版本；模板可引用标题、日期、
       数据摘要、指标表与自定义段落；渲染后自动过滤未替换的占位符并报错。
   1.5 附件生成：按配置把一个或多个 DataFrame 输出为 xlsx（多 sheet、表头加粗、列宽自适应、
       数值列千分位格式）或 csv（UTF-8 with BOM）；附件名支持日期占位符 {date}、{job_id}。
   1.6 收件人分组：按分组（如 management、finance、ops）分别发送，每组可有独立模板变量
       （如显示敏感列开关），支持抄送与密送；分组为空时跳过并记录而不是报错。
   1.7 失败重试：单封邮件失败后按 5 秒、30 秒、120 秒重试共 3 次；仍失败则写入台账并标记为
       待重发，同时继续处理后续分组，绝不因一组失败中断整批。
   1.8 发送台账：SQLite 表 send_log 记录批次号、任务 ID、分组、收件人数、附件名、尝试次数、
       结果、错误摘要、耗时；支持 resend 子命令按批次号或失败记录重发。
   1.9 预演模式：--dry-run 完成取数、计算、渲染、附件生成，但不发送，把生成的正文与附件
       输出到 output/preview/，便于人工确认。
2. 输入与交互
   2.1 命令行子命令：run（执行任务，可指定 --job 或全部）、list（列出任务）、preview（等同 dry-run）、
       resend（重发）、report（输出近 7 天发送统计）、check（校验任务文件与收件人白名单）。
   2.2 关键参数：--job 任务 ID；--group 只发送指定分组；--date 指定业务日期（默认今天）；
       --config 配置路径；--log-level。
   2.3 无参数运行 run 时执行所有 enabled 为 true 的任务，按 job_id 升序，任务之间串行。
3. 输出与展示
   3.1 控制台按任务打印：取数行数、指标计算耗时、渲染耗时、附件列表、各分组发送结果。
   3.2 output/preview/<job_id>_<date>/ 保存正文 html、正文 txt 与生成的附件。
   3.3 每批次结束打印汇总：成功 N 组、失败 M 组、总耗时 T 秒、台账批次号。
   3.4 report 子命令输出近 7 天每个任务的发送成功率与平均耗时。
4. 异常与边界处理
   4.1 数据源文件不存在或为空（0 行）时，若任务配置 require_rows 为 true 则标记该任务失败并跳过
       发送，避免发出空报表；为 false 时在正文中标注“本次数据为空”。
   4.2 SQL 执行错误时记录 SQL 与错误信息（SQL 中的字面量不记录敏感值），任务标记失败。
   4.3 模板渲染缺失变量时直接报错并打印缺失的变量名，禁止发出半成品邮件。
   4.4 附件超过 10 MB 时给出警告，超过 20 MB 时拒绝发送并在台账中记录，提示改用下载链接方案。
   4.5 收件人地址格式非法（不匹配基本的邮箱正则）时该地址剔除并记录，其余地址照常发送。
   4.6 SMTP 认证失败（535）时停止本任务剩余分组的发送并给出“凭据可能已过期”的明确提示，
       避免连续触发服务商风控。
   4.7 同一任务同一业务日期已成功发送全部分组时，默认跳过重复发送；--force 可强制重发。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用类型注解与 dataclass。
2. 允许使用的库：requests、jinja2、pandas、openpyxl；其余使用标准库（smtplib、email.message、
   email.utils、sqlite3、json、csv、argparse、logging、datetime、pathlib、re、time、hashlib、os）。
3. 禁止事项：禁止使用 eval/exec 执行任务文件中的表达式；禁止硬编码邮箱口令；
   禁止向未在配置白名单中的地址发送；禁止在日志中打印完整收件人列表（只打印数量与前 2 个脱敏地址）；
   禁止把附件内容写入日志。
4. 代码组织：config.py、models.py（JobSpec、Group、AttachmentSpec、SendResult）、
   datasource.py（四种数据源统一读取）、metrics.py（派生列与汇总，白名单求值）、
   render.py（jinja2 渲染与占位符检查）、attachment.py（xlsx/csv 生成）、mailer.py（SMTP 发送与重试）、
   ledger.py（SQLite 台账）、cli.py。
5. 编码规范：所有公开函数写 docstring 并说明异常；邮件主题与文件名中的中文需正确编码
   （使用 email.header.Header 或 email.message.EmailMessage）；时间统一带时区；
   任务配置解析出错必须报出文件名与出错字段；重试逻辑封装为一个可复用函数而不是到处复制。
6. 测试要求：metrics.py 的白名单求值、attachment.py 的文件生成、mailer.py 的重试次数控制
   三部分需有 pytest 用例；SMTP 通过注入的假客户端对象测试，禁止真实发信；
   另需一个用例覆盖“模板缺变量应报错”的行为。

【四、设计要点】

1. 数据结构
   1.1 JobSpec：job_id(str)、title(str)、template(str)、sources(list[SourceSpec])、
       metrics(list[MetricSpec])、attachments(list[AttachmentSpec])、groups(list[str])、
       enabled(bool)、require_rows(bool)、schedule_desc(str)。
   1.2 SourceSpec：name(str)、kind(str，csv/json/sqlite/excel)、path(str)、sql(str|None)、
       sheet(str|None)、encoding(str|None)、parse_dates(list[str])。
   1.3 Group：group_id(str)、name(str)、to(list[str])、cc(list[str])、bcc(list[str])、
       variables(dict)、is_sensitive(bool)。
   1.4 SendResult：batch_id(str)、job_id(str)、group_id(str)、recipients(int)、attachments(list[str])、
       attempts(int)、success(bool)、error(str|None)、elapsed_ms(int)、sent_at(str)。
   1.5 台账表 send_log：主键 id，字段与 SendResult 对应，对 (job_id, group_id, sent_at) 建索引；
       表 task_state：job_id + biz_date 唯一，记录该任务该日期是否已成功发送全部分组。
2. 关键算法或流程
   2.1 主流程：解析命令行 → 读取任务配置 → 校验数据源与收件人白名单 → 逐任务取数 →
       派生指标 → 渲染正文 → 生成附件 → 逐分组发送（含重试）→ 写台账 → 打印汇总。
   2.2 重试策略：def send_with_retry(...) -> SendResult，退避序列 [5, 30, 120] 秒；
       每次尝试记录 attempts；认证类错误（535）不重试直接失败。
   2.3 附件生成：对每个 AttachmentSpec，若行数超过 100000 则提示改用 CSV；
       xlsx 写入时数值列设置 number_format 为 #,##0.00，日期列设置 yyyy-mm-dd，
       表头加粗并冻结首行，列宽按内容长度估算（最大 40 字符）。
   2.4 敏感列控制：分组变量 show_amount 为 false 时，渲染前从 DataFrame 中删除金额列，
       并在正文中提示“金额列已按权限隐藏”，避免越权展示。
   2.5 白名单校验：读取 config 中的 recipients_whitelist 域名与完整地址集合，
       分组中未命中的地址被剔除并记入 check 报告。

【五、运行方式与示例】

安装依赖：
   pip install jinja2 pandas openpyxl requests

配置：
   config.ini 中配置 SMTP 服务器、端口、发件地址（口令从环境变量 MAIL_PASSWORD 读取）；
   recipients.json 定义分组与白名单；jobs/weekly_sales.json 定义报表任务。

运行示例一（预演）：
   python main.py preview --job weekly_sales --date 2024-05-20
   输出：
   [INFO] 任务 weekly_sales：读取 data/sales.csv 共 1842 行
   [INFO] 派生指标完成：环比、达成率、去重客户数
   [INFO] 正文渲染完成：HTML 92 行，纯文本 31 行
   [INFO] 附件生成：附件_销售周报_2024-05-20.xlsx（2 个 sheet，1.8 MB）
   [INFO] 预演模式：未发送，文件已输出到 output/preview/weekly_sales_2024-05-20/

运行示例二（正式发送）：
   python main.py run --job weekly_sales
   输出：
   [INFO] 批次号 20240520-0730-3f9a
   [INFO] 分组 management 发送成功（收件人 2，抄送 1），尝试 1 次，耗时 1.9s
   [INFO] 分组 finance 第 1 次失败：421 服务不可用，5 秒后重试
   [INFO] 分组 finance 第 2 次发送成功（收件人 3），尝试 2 次，耗时 7.4s
   [INFO] 汇总：成功 2 组，失败 0 组，总耗时 9.3s，台账批次号 20240520-0730-3f9a

运行示例三（重发与统计）：
   python main.py resend --batch 20240520-0730-3f9a --group finance
   python main.py report
   输出：
   [INFO] 近 7 天发送统计：weekly_sales 成功率 100%（8/8），平均耗时 6.2s
   [INFO] daily_ops 成功率 87.5%（7/8），失败 1 次（分组 ops，错误 421）

异常示例：
   python main.py run --job weekly_sales --date 2024-05-20
   输出（模板缺变量场景）：
   [ERROR] 模板渲染失败：weekly_sales.html 缺少变量 prev_total
   [ERROR] 任务 weekly_sales 已跳过发送并记入台账（退出码 5）

【六、验收标准】

[ ] preview 模式不发起任何 SMTP 连接（可用网络工具确认）
[ ] 生成的 xlsx 附件可正常打开，表头加粗、首行冻结、数值列千分位格式生效
[ ] CSV 附件为 UTF-8 with BOM，Excel 打开中文不乱码
[ ] 模板缺少变量时任务失败且不发送任何邮件，错误信息包含缺失变量名
[ ] 数据源为 0 行且 require_rows 为 true 时任务失败并跳过发送
[ ] 派生指标表达式中出现白名单外函数时被拒绝执行
[ ] 金额列在 show_amount 为 false 的分组中被隐藏且正文有提示
[ ] 分组内的非法邮箱被剔除并出现在 check 报告中，其他地址正常发送
[ ] 失败分组按 5、30、120 秒重试，重试次数与台账 attempts 一致
[ ] 一组失败不影响其他组发送，批次内继续串行执行
[ ] SMTP 535 认证失败时立即停止该任务剩余分组并给出凭据过期提示
[ ] 同一任务同一业务日期重复运行默认跳过，--force 可强制重发
[ ] send_log 表能按批次号查询并支持 resend 重发
[ ] report 子命令输出的成功率与 send_log 统计数据一致
[ ] 日志与代码中均无明文口令，且日志中收件人地址已脱敏

【七、可选扩展】

1. 增加报表快照对比：把本次关键指标与上周写入快照文件比较，正文自动加一句“本周环比 +3.2%”。
2. 增加图表附件：用 matplotlib 生成趋势图 PNG 并作为内嵌图片（cid）插入 HTML 正文。
3. 增加发送限流器：按邮箱服务商配置每分钟最大发送量，超出自动排队等待。
4. 增加 webhook 渠道作为邮件补充，同一报表同时推送群机器人摘要。

【八、涉及知识点】

- smtplib 与 email.message 构造带 HTML 正文、中文主题与多附件的邮件
- 重试机制设计（退避序列、可重试与不可重试错误分类）
- jinja2 模板继承、变量与占位符缺失检测
- pandas 读取多格式数据源与派生列计算
- 安全求值：用白名单与 AST 校验替代 eval
- openpyxl 样式、数字格式、冻结窗格与列宽设置
- SQLite 台账设计与按批次查询
- 收件人白名单与敏感数据分级展示
- 配置与凭据管理（configparser + 环境变量）
- 日志脱敏与个人信息的合规处理
================================================================================
