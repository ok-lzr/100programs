================================================================================
项目编号：085                    难度等级：★★★★☆（中型项目，偏难）
项目名称：主机资源监控面板
所属分类：运维监控 / 主机性能
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：psutil、SQLAlchemy、Flask、jinja2、APScheduler、rich
================================================================================

【一、项目背景与目标】

一台跑着数据库、Web 服务和定时任务的服务器，最怕的不是突然宕机，而是“慢性病”：内存
一点点被缓存吃满、磁盘根分区每周减少 2%、某个进程句柄数持续上涨。这些趋势在 top 命令里
看不出来，因为 top 只给你当下这一秒。要做容量规划和故障预判，必须把指标留下来、按时间
串起来看。

本项目实现一个单机主机资源监控面板。它按固定间隔采集 CPU、内存、交换分区、磁盘分区、
磁盘 IO、网络 IO、进程 TOP N、系统负载与开机时长等指标，写入本地时序存储；通过 Web 面板
展示最近 1 小时、24 小时、7 天的趋势图与当前状态；当某项指标越过阈值并持续若干采集周期
时产生告警，告警支持去重与静默期，避免 CPU 每秒 95% 就发一条通知。

目标用户是自己维护 VPS 或家用服务器的开发者、需要做教学演示的信息技术老师，以及没有预算
上企业级监控、但需要一份可自控数据的个人用户。系统完成后，可以挂在服务器上长期运行，通过
浏览器随时查看主机健康趋势，并在磁盘将满、内存将耗尽时提前收到通知。

采集合规：本工具只采集本机资源指标，不采集用户文件内容、不读取命令行参数中的敏感信息、
不采集网络报文载荷；进程列表只保留进程名、PID、CPU 与内存占用，不记录进程完整命令行，
避免口令泄漏到数据库中。

【二、功能需求清单】

1. 核心功能
   1.1 指标采集：每个采集周期（默认 5 秒，可配置 1 ~ 300 秒）采集下列指标：
       CPU——总体使用率、每核心使用率、1/5/15 分钟负载、上下文切换次数、中断次数；
       内存——总量、已用、可用、缓存与缓冲、swap 总量与已用；
       磁盘——每个挂载点的总量/已用/使用率，每块设备的读写字节数与读写次数；
       网络——每张网卡的收发字节数、包数、错误数、丢包数；
       进程——CPU 占用前 10 与内存占用前 10 的进程（PID、进程名、CPU%、RSS）；
       其他——开机时长、登录用户数、温度（若 psutil.sensors_temperatures 可用）。
   1.2 派生指标：在写入前把累计计数器（磁盘读写字节、网络收发字节）转换为速率（字节/秒），
       把内存转换为使用百分比；速率计算基于相邻两次采集的时间差，首次采集因无前值而跳过。
   1.3 时序存储：原始数据存入 SQLite（metrics 表按 metric 名 + 时间戳索引），同时写入
       按天分表的汇总视图；超过保留期（默认原始 7 天）的数据由聚合任务压缩为 1 分钟与
       1 小时两种粒度的均值/最大值记录，再删除过期原始行。
   1.4 阈值告警：每类指标可配置 warn 与 critical 两级阈值、持续周期数
       （consecutive_periods）、比较方向（above/below）。例如磁盘使用率 above 85 持续
       3 个周期触发 warn，above 95 触发 critical。告警在恢复时产生 RESOLVED 通知。
   1.5 告警去重与静默期：指纹为 metric + target（如 disk:/ 或 cpu:total）+ level；
       同一指纹在 dedup_window_minutes（默认 15 分钟）内重复触发只累加 repeat_count；
       静默期可通过 CLI silence 设置（--for 2h），静默期内告警入库但不发送，恢复通知不受
       静默期限制；主机重启或采集器重启后指纹不重复计数（用 run_id 区分会话）。
   1.6 趋势与预测提示：对磁盘使用率做线性外推，给出“按当前增速约 N 天后达到 100%”的
       提示，N 小于 30 时在面板上以醒目样式展示。
   1.7 基线告警（可选开关）：对 CPU 与内存使用率计算最近 7 天同时段的均值与标准差，当
       当前值超过均值加 3 倍标准差时产生 ANOMALY 告警，与固定阈值告警分开统计。

2. 输入与交互
   2.1 配置文件 config.yaml 定义采集间隔、保留期、告警阈值、通知渠道、Web 监听地址。
   2.2 CLI 子命令：init、collect（前台采集一轮或持续采集）、serve（采集 + 面板）、
       list-metrics、query（按指标名与时间范围查询并打印）、thresholds（查看/修改阈值）、
       silence、unsilence、export、doctor。
   2.3 Web 路由：GET / 总览页；GET /metric/<name> 单指标详情页；GET /api/series?metric=
       cpu.total&from=...&to=...&step=60 返回时序数据点；GET /api/summary 返回当前快照；
       GET /api/alerts?hours=72；POST /api/thresholds 更新阈值并热加载。
   2.4 参数化查询：query 命令支持 --step 参数做降采样（原始、1 分钟、1 小时三档），
       避免一次拉取七天原始点导致页面卡顿。

3. 输出与展示
   3.1 面板总览页显示：CPU、内存、磁盘、网络四张卡片（当前值 + 迷你趋势）、活动告警列表、
       磁盘增长预测提示、采集器最后心跳时间。
   3.2 详情页显示可切换时间范围（1h/24h/7d）的曲线数据，用服务端生成的 SVG 折线实现，
       不依赖外部 CDN，断网环境也能正常渲染。
   3.3 collect 在前台模式每轮打印一行：ts=2025-03-16T10:00:05 cpu=12.4% mem=61.2%
       disk(C:)=78.1% net_rx=142.3KB/s。
   3.4 export 命令导出 CSV 与 JSON，字段包含时间戳、指标名、数值、单位、主机名。

4. 异常与边界处理
   4.1 psutil 在某些平台读不到的指标（如温度、部分磁盘 IO）必须降级处理：记录一次
       metric_unavailable 到日志并跳过，不能让采集循环崩掉。
   4.2 采集周期抖动（上一轮耗时超过间隔）时应跳过本轮而不是并发堆积，并在日志中记录
       skipped_ticks 计数。
   4.3 系统时间被向前或向后调整时，检测时间戳倒退并在 metrics 表用单调递增的 seq 字段
       排序，避免图表出现时间轴错乱。
   4.4 磁盘挂载点消失（U 盘拔出、网络盘断开）时，该挂载点的历史数据保留，新数据停止，
       面板标注“已离线”。
   4.5 数据库文件过大（超过 max_db_size_mb）时触发一次归档压缩并把旧数据导出为
       .csv.gz，然后清理。
   4.6 Web 服务与采集器同进程但相互隔离：采集在后台线程，异常不得导致 HTTP 服务退出。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；采集使用 psutil，时间使用 time.monotonic 计算间隔、
   使用 datetime 记录时间戳。
2. 允许使用的库：psutil（指标采集）、SQLAlchemy 2.x（存储模型）、Flask + jinja2（面板）、
   APScheduler（定时任务）或标准库 threading.Timer，rich（控制台）、pydantic（配置校验）、
   PyYAML（配置）、pytest（测试）。分位数与统计使用标准库 statistics，SVG 由字符串模板
   生成，不引入绘图库。
3. 禁止事项：禁止采集进程完整命令行与文件路径列表等可能含敏感信息的字段；禁止在采集
   循环中执行阻塞式网络请求；禁止把告警 Webhook Token、SMTP 授权码硬编码在配置或代码中
   （从环境变量 MONITOR_SMTP_PASSWORD、MONITOR_WEBHOOK_TOKEN 读取）；禁止用 print 输出
   采集日志，统一使用 logging 并做文件轮转。
4. 代码组织：模块划分为 collector（各项指标采集函数）、deriver（速率与百分比派生）、
   store（写入、聚合、清理、查询）、alerter（阈值判定、状态机、去重与静默）、
   forecast（线性外推）、webapp（路由与 SVG 渲染）、cli。
5. 编码规范：全部函数有类型注解与 docstring；指标名使用统一命名规范（cpu.total、
   mem.used_percent、disk.C.used_percent、net.eth0.rx_bytes_per_sec）；单位在字段名或
   单位表中明确；异常处理区分“平台不支持”与“真实错误”。

【四、设计要点】

1. 数据结构
   - Sample：seq（自增）、ts（UTC 秒级时间戳）、host、metric（字符串）、value（float）、
     unit（字符串）、tags（JSON，如 {"mount": "C:", "device": "sda"}）。
   - Threshold：metric_pattern、level（warn/critical）、direction（above/below）、
     value、consecutive_periods、enabled。
   - AlertState：fingerprint、metric、tags、level、state（FIRING/RESOLVED）、
     first_seen_at、last_seen_at、repeat_count、silenced_until、peak_value。
   - AggRow：bucket_ts、metric、granularity（60/3600）、avg_value、max_value、min_value、
     sample_count。
   - 索引：CREATE INDEX idx_metrics_name_ts ON metrics(metric, ts)；聚合表按
     (metric, granularity, bucket_ts) 建唯一索引。
2. 关键算法或流程
   - 采集流程：记录 t0 = time.monotonic() → 调用各采集函数得到原始计数 → 用上一轮
     (counters, t_prev) 计算速率 = (cur - prev) / (t0 - t_prev) → 组装 Sample 列表 →
     批量插入（每 20 轮或攒够 200 条 flush 一次）→ 交给 alerter 判定。
   - 速率计算的计数器回绕处理：网络与磁盘计数器可能是 32 位回绕或设备重置，若 cur 小于
     prev 则丢弃本轮速率并记 debug 日志，避免出现负值尖峰。
   - 聚合与清理：每小时执行一次 rollup：把 1 分钟前的原始样本按分钟分桶写入 AggRow(60)，
     把 1 小时前的 AggRow(60) 按小时分桶写入 AggRow(3600)，然后删除超过保留期的原始行
     与过期的 AggRow(60)。整个过程放在一个事务里，失败回滚。
   - 阈值状态机：对每个 (metric, tags) 组合维护连续越限计数 counter；越限时 counter 加一，
     达到 consecutive_periods 且状态非 FIRING 时进入 FIRING 并生成告警；未越限时 counter
     清零，若状态为 FIRING 则生成 RESOLVED 并清空 counter。
   - 去重与静默：fingerprint = sha1(metric + tags_json + level) 前 12 位；生成告警前查同
     指纹记录，last_seen_at 在 dedup_window 内则只更新 repeat_count 与 peak_value；
     否则再判断 silenced_until 是否晚于当前时间，是则入库标记 silenced 且不发送。
   - 磁盘线性外推：取最近 7 天每天的末值做最小二乘拟合斜率 k（百分比/天），当 k 大于 0
     时 estimated_days = (100 - current) / k，四舍五入保留一位小数。
3. 接口或命令设计
   - CLI：python -m sysmon serve --config config.yaml --web-port 8095
   - CLI：python -m sysmon query --metric disk.C.used_percent --from 2025-03-09 --to 2025-03-16 --step 3600
   - CLI：python -m sysmon thresholds --set "disk.*.used_percent warn above 85 for 3" ^
     --set "mem.used_percent critical above 95 for 2"
   - HTTP：GET /api/series?metric=mem.used_percent&from=1741000000&to=1741003600&step=60
     返回 {"metric":"mem.used_percent","unit":"%","points":[[1741000000,61.2],[1741000060,62.0]]}
   - 核心函数：collect_all(prev: Counters) -> list[Sample]；
     evaluate(samples, thresholds, state) -> list[AlertEvent]；
     rollup(conn, now) -> RollupReport；forecast_disk_full_days(series) -> float | None。

【五、运行方式与示例】

安装与运行：
    pip install psutil SQLAlchemy Flask jinja2 APScheduler rich pydantic PyYAML pytest
    python -m sysmon init --db data/sysmon.db
    python -m sysmon thresholds --load config/thresholds.yaml
    python -m sysmon serve --web-port 8095
    浏览器访问 http://127.0.0.1:8095/ 查看面板

示例一（采集一轮并查看快照）：
    输入：python -m sysmon collect --once
    输出：
      ts=2025-03-16T10:00:05 cpu=12.4% load=0.42/0.55/0.61 mem=61.2%(9.8G/16.0G)
      swap=3.1% disk(C:)=78.1% disk(D:)=41.0% net_rx=142.3KB/s net_tx=58.7KB/s
      已写入 47 条样本，耗时 82 ms

示例二（阈值告警与去重）：
    输入：python -m sysmon query --metric disk.C.used_percent --from 2025-03-16T09:00 --to 2025-03-16T10:00
    输出：
      2025-03-16T09:50 85.2  95.1（越限第 1 周期）
      2025-03-16T09:51 85.4  95.3（越限第 2 周期）
      2025-03-16T09:52 85.6  95.6（越限第 3 周期 -> warn 触发）
      告警：[WARN] disk.C.used_percent=85.6% 连续 3 周期超过 85
            fingerprint=4b71c2e0aa93 静默期 15 分钟，重复触发不再通知（repeat_count=4）

示例三（按小时降采样查询）：
    输入：python -m sysmon query --metric cpu.total --from 2025-03-09 --to 2025-03-16 --step 3600
    输出：返回 168 个点（粒度 3600 秒），avg=13.7% max=88.2% min=1.1%
          磁盘增长预测：D: 按最近 7 天增速约 47 天后达到 100%

示例四（异常输入）：
    输入：python -m sysmon thresholds --set "disk.*.used_percent warn above abc for 3"
    输出：错误：阈值 value 必须是数字，收到 "abc"；阈值未修改，退出码 1

示例五（平台不支持指标）：
    输入：python -m sysmon collect --once --include temperature
    输出：警告：当前平台不支持温度采集（psutil.sensors_temperatures 返回空），
          已跳过该指标；本轮成功写入 47 条样本，退出码 0

【六、验收标准】

[ ] 一个采集周期能得到 CPU、内存、swap、磁盘、网络、进程 TOP、负载、开机时长全部指标
[ ] 累计计数器被正确转换为速率，无负值、无异常尖峰（检查出现设备重置时的日志）
[ ] 样本批量写入后，按 metric 与时间范围查询返回条数与实际采集轮数一致
[ ] 聚合任务能生成 1 分钟与 1 小时粒度数据，且聚合值与原始数据均值误差小于 0.5%
[ ] 超过保留期的原始数据被清理，聚合数据保留，数据库体积受控
[ ] warn 与 critical 两级阈值均按 consecutive_periods 判定，未达周期数不告警
[ ] 指标恢复正常后产生 RESOLVED 通知，且该通知不受静默期抑制
[ ] 同一指纹告警在 15 分钟去重窗口内只发送一次，repeat_count 正确累加
[ ] 静默期内的告警在数据库可查且标记 silenced
[ ] 无温度传感器等不支持的指标不会中断采集循环，日志有明确说明
[ ] 采集耗时超过间隔时跳过本轮而不是堆积任务，skipped_ticks 有计数
[ ] Web 面板四张卡片、详情页曲线、告警列表均来自真实数据且断网可用
[ ] 磁盘使用率线性外推结果与手工按日末值算出的斜率结论一致
[ ] 采集器连续运行 2 小时无内存泄漏（RSS 增长小于 20 MB），日志文件正常轮转

【七、可选扩展】

1. 增加多主机模式：在被监控主机上跑一个只上报不存储的采集代理，中心节点汇总多机指标，
   面板增加主机切换。
2. 暴露 Prometheus /metrics 端点，把指标交给现有监控体系，本工具只做采集与面板。
3. 增加进程级监控：对指定进程名的存活、CPU 占用、重启次数做独立告警规则。
4. 增加容器指标采集（通过读取 cgroup 文件），支持监控 Docker 容器资源使用。

【八、涉及知识点】

- psutil 各接口语义、计数器累计值与速率派生、跨平台差异处理
- 时序数据建模：原始表、分桶聚合表、索引设计与降采样查询
- 保留期策略、rollup 任务、事务与数据清理的工程取舍
- 阈值告警状态机、连续周期判定、抖动抑制
- 告警去重指纹、重复计数、静默期与恢复通知的语义区别
- 线性回归外推与容量预测提示
- Flask 服务端渲染、JSON 时序接口、服务端 SVG 折线绘制
- 后台采集线程与 Web 线程的隔离、日志轮转与长期运行稳定性
================================================================================
