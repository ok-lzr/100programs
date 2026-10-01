================================================================================
项目编号：081                    难度等级：★★★★☆（中型项目，偏难）
项目名称：定时任务调度平台
所属分类：业务管理系统 / 运维自动化
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：APScheduler、croniter、Flask、SQLAlchemy、click、rich
================================================================================

【一、项目背景与目标】

服务器上散落着几十条 crontab 记录是很多团队的常态：备份脚本写在 root 的 crontab 里，
数据清洗脚本写在某个业务账号下，定时报表又是另一台机器上的 Windows 计划任务。想知道
“昨晚的备份到底跑没有跑成功”，只能一台台机器登录上去翻日志；想调整一条任务的执行时间，
需要记住它到底在哪台机器的哪个用户下。更麻烦的是任务之间其实有隐含顺序：必须先下载行情
数据，再计算指标，最后生成报表，但 crontab 里只能靠“把时间错开二十分钟”这种经验性做法
来保证顺序，一旦前一步变慢就会雪崩。

本项目要做一个单机可运行、后期可扩展为多工作节点的定时任务调度平台。它把每一件周期性
工作抽象成一条任务记录，用标准 Cron 表达式描述触发时间，用显式的依赖关系描述任务之间的
先后顺序，用可配置的重试策略应对偶发失败，并把每一次执行的开始时间、结束时间、退出码、
标准输出与标准错误全部落库，形成可检索的执行历史。

目标用户是需要维护一批批处理脚本的开发者与运维人员。平台做成之后，你可以用它替换掉
散落的 crontab：所有任务集中登记、集中查看、集中改时间；一次触发失败自动重试并告警；
依赖任务在前置任务成功后才出队执行；任何一个历史执行都能通过 run_id 精确回溯。

平台不追求分布式与高可用，单进程即可跑通全部功能，但数据模型与内部接口必须为后续增加
远程执行器预留位置（任务表里保存执行节点字段，执行器抽象成可替换的接口）。

【二、功能需求清单】

1. 核心功能
   1.1 Cron 表达式解析：支持标准 5 字段（分 时 日 月 周）与 6 字段（秒 分 时 日 月 周）
       两种写法；支持 星号、区间 a-b、步长 星号斜杠n 与 a-b/n、列表 a,b,c、问号 ?（等价
       于星号）。解析结果必须给出“下一次触发的本地时间”，解析失败时抛出明确异常。
   1.2 任务登记：每个任务包含 job_id（字符串主键）、name、command（命令行字符串）、
       cron、timezone、enabled、max_parallel（同一任务同时允许的实例数）、timeout_seconds、
       依赖任务列表 depends_on、重试策略 retry、告警配置 alert。
   1.3 依赖编排：把全部任务构成有向无环图（DAG）。每一次调度周期按拓扑顺序求解，只有
       当所有前置依赖在本周期内执行成功，当前任务才可进入运行队列；前置失败或跳过时，
       当前任务标记为 SKIPPED 并记录 skip_reason。
   1.4 失败重试：重试策略字段包含 max_retries（0 表示不重试）、backoff（fixed 或
       exponential）、delay_seconds、max_delay_seconds。第 n 次重试等待时间：fixed 时为
       delay_seconds；exponential 时为 min(delay_seconds * 2 的 n-1 次方, max_delay_seconds)。
   1.5 执行引擎：用 subprocess 启动命令，捕获 stdout/stderr，施加 timeout_seconds 超时，
       超时后先 terminate，等待 5 秒仍未退出则 kill，并把该次执行判定为 TIMEOUT。
   1.6 执行日志：每次运行生成唯一 run_id（UUID4），落库记录 job_id、run_id、trigger_type
       （cron/manual/retry）、scheduled_at、started_at、finished_at、duration_ms、exit_code、
       status、stdout 摘要（前 4000 字符）、stderr 摘要（前 4000 字符）、完整日志文件路径。
   1.7 告警通知：任务最终失败（重试耗尽）时写入告警表，并调用通知器（控制台 + 可选邮件
       SMTP）。同一 job_id 在 silence_minutes 静默期内只发一次告警；相同告警指纹
       （job_id + status + 命令首行哈希）在 dedup_window_minutes 内去重，只累加重复次数。

2. 输入与交互
   2.1 任务定义支持两种来源：YAML/JSON 配置文件批量导入，以及 CLI 子命令单条增删改。
   2.2 CLI 命令：init（初始化数据库）、add、ls、show、enable、disable、run（立即手动执行）、
       log（按 job_id 或 run_id 查询执行历史）、retry（对指定 run 手工重跑）、
       dag（以文本形式打印依赖图）、serve（启动调度循环）、web（启动只读面板）。
   2.3 YAML 导入需做严格校验：字段缺失、cron 非法、依赖引用了不存在的 job_id、依赖成环
       时，逐条给出错误行号与原因，且整体导入失败不做部分写入。
   2.4 手动触发 run 命令必须绕过 cron 时间判断，但仍然遵守依赖检查，允许用 force 参数
       跳过依赖检查（用于补数据场景），force 执行时 trigger_type 记为 manual_force。

3. 输出与展示
   3.1 ls 命令以表格化纯文本输出：job_id、名称、cron、下次触发时间、启用状态、上次执行
       状态与耗时，未启用任务用中括号标注 DISABLED。
   3.2 log 命令输出某个 job 最近 N 次运行的列表，可加 --failed 只看失败，可加 --tail 直接
       打印某次运行的 stdout 与 stderr。
   3.3 web 面板提供三个只读页面：任务列表（含下次触发时间）、运行历史（可按状态过滤）、
       依赖图（用嵌套列表渲染拓扑层级，不依赖前端框架）。
   3.4 每次执行结束向控制台打印一行结构化摘要：时间、job_id、run_id、状态、耗时毫秒。

4. 异常与边界处理
   4.1 command 在 60 秒内被重复调度时，若该任务已在 RUNNING 且 running 数量达到
       max_parallel，本次触发记为 SKIPPED，skip_reason 为 concurrency_limit。
   4.2 服务重启后要处理“错过的时间窗”：catch_up 为 true 的任务，对停机期间错过的最近
       一次触发时间补跑一次（只补最近一次，避免堆积）；catch_up 为 false 则直接跳到下一次。
   4.3 数据库被并发写入时使用 SQLite 的 WAL 模式，并对 run 状态更新使用事务包裹，避免
       出现 started_at 已写入而 finished_at 永远为空记录悬挂的情况。
   4.4 依赖图存在环时，dag 命令输出环路径（如 A -> B -> C -> A），serve 命令拒绝启动。
   4.5 命令为空、命令以分号拼接多个外部命令、任务名重复时，均在登记阶段即报错。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用 match 语句处理状态分支，使用 zoneinfo 处理时区。
2. 允许使用的库：croniter（Cron 解析与下次触发时间计算）、APScheduler（可选，用于把
   调度循环跑在后台线程，若自行实现 tick 循环则不必引入）、SQLAlchemy 2.x（ORM 与建表）、
   Flask + jinja2（只读 Web 面板）、click（CLI）、rich（表格与彩色日志）、pydantic（配置
   校验）、PyYAML（导入 YAML）、pytest（测试）。命令行执行、哈希、UUID、SMTP、JSON 处理
   一律使用标准库 subprocess、hashlib、uuid、smtplib、json、dataclasses、logging。
3. 禁止事项：禁止使用 shell=True 拼接用户输入直接执行（必须用 shlex.split 解析后传入
   参数列表）；禁止在代码中硬编码数据库口令、SMTP 授权码，必须从环境变量
   （DSH_SCHED_SMTP_PASSWORD 等）或 .env 文件读取；禁止在 README 之外提交真实生产命令；
   禁止用 print 做运行日志，统一使用 logging 并输出到 logs/scheduler.log 与控制台。
4. 代码组织：至少划分 storage（数据访问）、cron_parser（表达式解析封装）、dag（拓扑排序
   与环检测）、executor（子进程执行与超时控制）、retry（退避计算）、notifier（告警与去重）、
   cli（命令入口）、web（面板）八个模块，每个模块单一职责，禁止在 CLI 层直接写 SQL。
5. 编码规范：全部函数与公开方法写类型注解与 docstring（说明参数、返回值、可能抛出的
   异常）；命名用 snake_case 函数与 PascalCase 类；时间统一以 UTC 存库、展示时转换时区；
   对 status 使用 Enum 而非裸字符串。

【四、设计要点】

1. 数据结构
   - Job：job_id、name、command、cron、timezone、enabled、max_parallel、timeout_seconds、
     catch_up、depends_on（list 字符串）、retry（RetryPolicy）、alert（AlertPolicy）。
   - RetryPolicy：max_retries、backoff、delay_seconds、max_delay_seconds。
   - AlertPolicy：channel（console/smtp/both）、silence_minutes、dedup_window_minutes、
     recipients。
   - JobRun：run_id、job_id、trigger_type、scheduled_at、started_at、finished_at、
     duration_ms、exit_code、status（PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/SKIPPED/
     RETRYING）、attempt、skip_reason、stdout_tail、stderr_tail、log_path。
   - AlertRecord：alert_id、job_id、run_id、fingerprint、message、first_seen_at、
     last_seen_at、repeat_count、notified_at。
2. 关键算法或流程
   - 调度主循环：每 1 秒 tick 一次，取当前时间戳的整秒，遍历启用任务，用 croniter 判断
     本秒是否为触发点（6 字段模式）或本分钟是否为触发点（5 字段模式）；是则创建 PENDING
     记录并入待执行集合。
   - DAG 求解：构建邻接表，用 Kahn 算法做拓扑排序并同时检测环；每一轮执行时按拓扑层
     依次推进，每层内部可并发执行（用 ThreadPoolExecutor，最大并发数全局可配）。
   - 退避计算：retry_delay(attempt, policy) 返回秒数，attempt 从 1 开始计数。
   - 告警去重：fingerprint = sha256(job_id + 状态 + 命令首行) 的前 16 个十六进制字符；
     写入前先查同 fingerprint 且 last_seen_at 在 dedup_window 内的记录，命中则
     repeat_count 加一且不发通知；否则检查 silence_minutes 内是否已对该 job 发过通知。
3. 接口或命令设计
   - CLI：python -m scheduler add --id backup_db --cron "0 3 * * *" --cmd "python backup.py"
     --timeout 1800 --retry 2 --backoff exponential
   - CLI：python -m scheduler serve --workers 4 --tick 1
   - HTTP：GET /api/jobs 返回任务列表；GET /api/runs?status=FAILED&limit=50 返回运行历史；
     GET /api/dag 返回 {"nodes": [...], "edges": [...]} 供画图使用。
   - 核心函数签名：parse_cron(expr: str, base: datetime) -> datetime；
     topo_sort(jobs: list[Job]) -> list[list[str]]；execute(job: Job) -> JobRun；
     should_alert(record: AlertRecord) -> bool。

【五、运行方式与示例】

安装与运行：
    python -m venv .venv
    .venv\Scripts\activate
    pip install croniter SQLAlchemy Flask click rich pydantic PyYAML pytest
    python -m scheduler init --db data/scheduler.db
    python -m scheduler import --file jobs.example.yaml
    python -m scheduler serve --workers 4
    python -m scheduler web --port 8088

示例一（登记并查看）：
    输入：python -m scheduler add --id daily_report --cron "30 7 * * 1-5" ^
          --cmd "python report.py --date today" --depends download_data --timeout 600
    输出：已登记任务 daily_report，下次触发时间 2025-03-17 07:30:00 +08:00

示例二（手动执行并读日志）：
    输入：python -m scheduler run --id daily_report --force
    输出：
      [2025-03-16 09:12:03] job=daily_report run=6f1c...e2 status=SUCCESS
      exit_code=0 duration_ms=8421 log=logs/daily_report/6f1c...e2.log

示例三（失败重试与告警去重）：
    输入：python -m scheduler log --id nightly_backup --failed --tail
    输出：
      run=a91b... status=FAILED attempt=3/3 exit_code=2
      stderr: PermissionError: [WinError 5] 拒绝访问: 'D:\\backup'
      alert: 已发送（fingerprint=3c9a1b77e0a4c2d5，静默期 30 分钟内重复失败不再通知）

示例四（异常输入）：
    输入：python -m scheduler add --id bad --cron "0 25 * * *" --cmd "echo hi"
    输出：错误：cron 表达式非法，小时字段 25 超出 0-23（表达式：0 25 * * *），
          任务未登记，数据库无任何变更。

【六、验收标准】

[ ] 支持 5 字段与 6 字段 Cron，星号、区间、步长、列表、问号五类语法均可正确解析
[ ] 对 0 25 星号 星号 星号 这类非法表达式能从 CLI 与导入两个入口给出明确错误
[ ] 依赖任务在前置成功后才执行，前置失败时后置任务状态为 SKIPPED 且 skip_reason 可查
[ ] 依赖成环时 dag 命令打印环路径，serve 命令拒绝启动并给出非零退出码
[ ] 重试次数、固定退避与指数退避的实际等待时间与公式一致（可通过日志时间戳核对）
[ ] 命令超时能被强制结束，状态记为 TIMEOUT，且进程树无残留
[ ] 每一次执行都有唯一 run_id，execution 表同时含 started_at 与 finished_at
[ ] 同一 job 在静默期内的多次失败只产生一条通知，重复次数被累加
[ ] 服务重启后 catch_up 为 true 的任务只补跑最近一次错过的触发
[ ] max_parallel 生效：并发触发的第 N+1 次被记为 SKIPPED 且原因正确
[ ] web 面板三个页面均可打开，不用前端框架也能正常显示中文
[ ] 全库无 print 调试残留，日志文件按天切分且保留最近 14 天
[ ] pytest 用例覆盖 cron 解析、DAG 检测、退避计算、去重逻辑，全部通过
[ ] 代码中不存在硬编码的 SMTP 授权码或数据库口令

【七、可选扩展】

1. 增加远程执行器：把 executor 抽成接口，实现 SSH 执行器在不同主机上跑任务，任务表增加
   node 字段做节点亲和调度。
2. 把调度中心与执行器拆成两个进程，用消息队列（如 Redis 列表）下发任务，实现多工作节点
   的水平扩展与心跳存活检测。
3. 增加任务流水线 DSL：用 YAML 描述多步骤任务，支持步骤间传参、条件分支与并行分支。
4. 暴露 Prometheus 指标端点 /metrics，输出任务成功率、平均耗时、队列长度，接入告警系统。

【八、涉及知识点】

- Cron 表达式语法与 croniter 库的 next 计算、时区与夏令时处理
- 有向无环图的构建、Kahn 拓扑排序与环检测
- subprocess 的进程控制、超时终止、输出捕获与编码问题（Windows 下 GBK 与 UTF-8）
- 重试与退避策略设计，固定退避与指数退避的区别与适用场景
- 告警去重、静默期、指纹哈希等运维告警工程实践
- SQLAlchemy ORM 建模、事务、SQLite WAL 模式与并发写入
- click 子命令设计、rich 表格输出、logging 分级与文件轮转
- 后台线程调度、ThreadPoolExecutor 并发控制与线程安全的状态更新
================================================================================
