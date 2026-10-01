================================================================================
项目编号：050                    难度等级：★★★☆☆（小型项目）
项目名称：系统体检报告生成器
所属分类：命令行工具 / 系统运维
建议工时：6 ~ 8 小时
运行环境：Python 3.10+    第三方依赖：psutil >= 5.9（pip install psutil）
================================================================================

【一、项目背景与目标】

电脑变慢、风扇狂转、C 盘变红、某个进程把内存吃光——这些问题在出故障的当下很难判断原因，
因为任务管理器只能看“此刻”，看不到趋势，也不会告诉你“过去 30 秒里 CPU 有 12 秒处于 95% 以上”。
给别人远程排障时更麻烦：只能靠对方口述“我的电脑很卡”。

本项目做一个系统体检报告生成器：采集一段时间的系统指标（CPU、内存、交换分区、磁盘空间与
IO、网络收发速率、电池、温度传感器、进程 Top 榜、开机时长），做几次采样形成趋势，然后生成
一份人可读的文本报告或单文件 HTML 报告。报告可以保存、可以发给同事、可以作为排障的历史
基线——下次再出问题，把两份报告一对比就知道哪里变了。

技术上以 psutil 为核心。跨平台差异是必须认真处理的：温度传感器在 macOS 与部分 Linux 上才
有、电池信息在台式机上不存在、Linux 的 load average 在 Windows 上不可用、磁盘 inode 只对
Linux 有意义。程序必须在缺失数据时优雅降级，报告里明确写“该项在当前平台不可用”，而不是抛异常。

目标用户是需要给家人朋友远程排障的技术人员、做性能基线记录的开发者、以及想了解自己电脑
状况的普通用户。程序只采集本机信息，绝不上传任何数据。

【二、功能需求清单】

1. 核心功能
   1.1 概览信息：用 platform 模块取系统（Windows/macOS/Linux 与版本）、架构、主机名、
       Python 版本、psutil 版本；用 psutil.boot_time() 计算开机时长（格式化为 N 天 N 小时）。
   1.2 CPU：psutil.cpu_count(logical=True/False) 逻辑与物理核数、cpu_freq() 当前/最小/最大
       频率、cpu_percent(interval=None) 的两次采样差、per-cpu 各核心占用、cpu_times_percent()
       中 user/system/idle/iowait 占比。Linux/macOS 上额外取 getloadavg()（用 hasattr 探测）。
   1.3 内存：virtual_memory() 的 total/available/used/percent、swap_memory() 的
       total/used/percent；若可用内存低于 --mem-warn（默认 15%）在报告中高亮告警。
   1.4 磁盘：disk_partitions() 列出每个挂载点（过滤掉 0 字节的临时分区），
       对每个分区取 disk_usage() 的 total/used/free/percent；使用率超过 --disk-warn
       （默认 85%）时标注 [警告]。disk_io_counters(perdisk=True) 采集读写字节与次数，
       两次采样求差得到速率（MB/s、IOPS）。
   1.5 网络：net_io_counters(pernic=True) 采集每张网卡的收发字节与包数，两次采样求差得到
       上/下行速度（KB/s、Mbps）；net_if_addrs() 列出 IPv4/IPv6 地址与 MAC，默认隐藏公网
       IP（--show-ip 才显示完整地址，否则打码为 192.168.*.*）。
   1.6 进程：process_iter(["pid","name","username","cpu_percent","memory_percent",
       "create_time","status"]) 取 Top N（默认 10）按 CPU 与 Top N 按内存；每个进程补充
       cmdline（截断到 120 字符）、num_threads、exe 路径；--filter 'python,chrome'
       只看指定进程名；--pid 采集单个进程的详细快照。
   1.7 其他硬件：sensors_temperatures()（有则列出 CPU/主板温度）、sensors_battery()
       （有则给电量、是否充电、剩余时间）、sensors_fans()（有则给风扇转速）。
   1.8 采样与阈值：--samples N（默认 3）与 --interval S（默认 2）组成采样窗口；
       对 CPU/内存/磁盘 IO/网络分别记录平均值、最大值与峰值时刻；超过阈值的项目生成
       “问题清单”，放在报告开头。

2. 输入与交互
   2.1 命令行：python sysreport.py --samples 5 --interval 3 --format html --output report.html。
   2.2 --quick 只做一次采样（等价 --samples 1），用于快速了解现状（2 秒内出结果）。
   2.3 --watch 进入持续监控模式，每 --interval 秒在终端刷新一行摘要，Ctrl+C 后生成报告。
   2.4 --compare old.json 加载上一次的 JSON 报告并生成“变化对比”章节（CPU 均值、
       内存占用、磁盘剩余、Top 进程的差异）。
   2.5 --json report.json 始终附加导出结构化数据，便于做趋势跟踪或接入其他工具。
   2.6 --thresholds thresholds.toml 从配置文件读取各项告警阈值，命令行参数优先。

3. 输出与展示
   3.1 文本报告（默认）分节排版，用全角序号与分隔线，关键项用 [警告]/[正常] 前缀标记；
       终端输出时对 [警告] 使用 ANSI 红色（--no-color 关闭，Windows 老版本终端自动降级）。
   3.2 HTML 报告：单文件、内联 CSS、无外部资源；顶部为“体检结论”卡片，
       中部为各项指标表格与用 div 宽度百分比的纯 CSS 条形图，底部为进程 Top 榜。
   3.3 报告开头给出结论摘要：例如“本次体检：发现 2 个问题（磁盘 C: 使用率 92%、
       可用内存仅 8%），其余 14 项正常”。
   3.4 每次采集的原始样本也写入正文附录（时间、CPU%、内存%、网络速率），便于核对。
   3.5 报告文件末尾写明生成时间、耗时、采样参数与主机标识（主机名 + 平台），便于归档。

4. 异常与边界处理
   4.1 psutil.AccessDenied：读取某些进程信息（其他用户的进程）时被拒，跳过该进程并计数，
       报告中说明“N 个进程因权限不足未采集”。
   4.2 psutil.NoSuchProcess / ZombieProcess：进程在采集瞬间退出，捕获后跳过，不中断循环。
   4.3 平台不支持某项指标（温度、风扇、电池、load average）：报告写“当前平台不支持该项”，
       不计为错误；用 hasattr(psutil, "sensors_temperatures") 与 try/except 双重保护。
   4.4 磁盘分区在采集时被卸载（如 U 盘拔出）：捕获 OSError 并跳过该分区。
   4.5 第一次调用 cpu_percent(interval=None) 总是返回 0.0：实现里必须先调用一次“预热”
       再采样；或在采样点之间使用 interval 参数直接取值。文档中必须写清这一点。
   4.6 采样期间系统休眠：检测两次采样实际间隔远大于 --interval 时，丢弃该样本并重新采样，
       报告中注明。
   4.7 容器环境（Docker/WSL）：部分指标来自宿主或受限，报告顶部标注“检测到容器/WSL
       环境，部分指标可能不准确”。
   4.8 输出路径不可写或磁盘满：报错并给出可用空间，退出码 1，不生成半截文件。
   4.9 进程列表过长（数百个）时只保留 Top N，但总和统计仍基于全部进程。
   4.10 --pid 指定的进程不存在：明确报错并退出码 1；进程在采样中退出时输出“进程已结束”。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：psutil（核心采集）；标准库 argparse、platform、socket、datetime、time、
   json、csv、html、pathlib、logging、os、shutil、collections、dataclasses、tomllib、
   statistics、sys。不做图形界面，不引入 matplotlib 等绘图库（用字符与纯 CSS 表达图形）。
3. 禁止事项：禁止上传或发送任何采集数据到网络；禁止读取或输出用户文件内容（只采集系统
   指标与进程元数据）；禁止无故结束进程（本项目只读，不杀进程）；禁止在报告中输出完整
   公网 IP 与用户名之外的隐私信息（默认脱敏）；禁止用 os.system 调用 wmic/top 等外部命令
   取数据（必须用 psutil 跨平台 API）。
4. 代码组织：
   - collect.py：collect_static() -> StaticInfo（一次性的系统与硬件信息）、
     collect_dynamic() -> DynamicSample（每轮的 CPU/内存/IO/网络/进程）、
     collect_processes(top_n) -> list[ProcInfo]。
   - models.py：@dataclass StaticInfo / DynamicSample / ProcInfo / Finding / Report。
   - analyze.py：aggregate(samples) -> Aggregated（均值/峰值）、detect_findings(agg, thresholds)
     -> list[Finding]、compare(prev: dict, cur: Report) -> list[str]。
   - render_text.py：render(report) -> str，含分节排版与 ANSI 颜色。
   - render_html.py：render(report) -> str，内联 CSS 模板与纯 CSS 条形图。
   - render_json.py：to_dict(report) / from_dict(data)（用于 --compare）。
   - cli.py：参数解析、采样循环、Ctrl+C 处理与输出分发。
5. 编码规范：类型注解完整；单位统一在字段名中体现（bytes、percent 0-100、seconds），
   渲染层负责换算成人读单位（用自定义 human_bytes()，不用第三方库）；所有跨平台差异都要
   在代码注释与 docstring 中说明；日志用 logging，采集异常记 WARNING 并累计；报告文本宽度
   78 列，保证在邮件与终端中都不折行。

【四、设计要点】

1. 数据结构：
   StaticInfo：hostname、platform(str)、platform_release、platform_version、architecture、
   python_version、psutil_version、boot_time(datetime)、uptime_seconds(float)、
   cpu_logical(int)、cpu_physical(int)、cpu_freq_max(float|None)、total_memory(int)、
   total_swap(int)、partitions(list[PartitionInfo])、nics(list[NicInfo])、is_container(bool)、
   is_wsl(bool)。
   DynamicSample：ts(datetime)、cpu_percent(float)、cpu_per_core(list[float])、
   cpu_times_percent(dict)、load_avg(tuple|None)、mem_percent(float)、mem_available(int)、
   swap_percent(float)、disk_read_bps(float)、disk_write_bps(float)、
   net_sent_bps(float)、net_recv_bps(float)、battery(dict|None)、temperatures(dict|None)、
   top_procs(list[ProcInfo])。
   ProcInfo：pid、name、username、cpu_percent、memory_percent、rss_bytes、vms_bytes、
   num_threads、status、create_time(datetime)、cmdline(str)、exe(str)。
   Finding：level(str: 警告|提示)、category(str)、title(str)、detail(str)、value(str)。
   Report：static(StaticInfo)、samples(list[DynamicSample])、aggregated(dict)、
   findings(list[Finding])、generated_at(datetime)、duration_seconds(float)、options(dict)。

2. 关键算法或流程：
   2.1 采样循环（精确控时）：psutil.cpu_percent(interval=None) 先预热一次；
       循环 for i in range(samples)：t0 = time.monotonic()；采集各类计数器的瞬时值 ->
       time.sleep(interval) -> 再取瞬时值求差得到速率 -> 计算 cpu_percent() -> 记录样本 ->
       drift = time.monotonic() - t0；若 drift > interval * 2 记一条“系统可能休眠”的警告。
   2.2 速率计算：对 net_io_counters 与 disk_io_counters 保存上一轮快照，
       rate = (cur - prev) / 实际间隔秒数；计数器回绕或为 None 时跳过该项并记 DEBUG。
   2.3 进程 CPU 占用：process_iter 得到的 cpu_percent 是自上次调用以来的值，必须先对所有
       进程做一次预热调用（在采样循环开始时），再在后续轮次取值，否则首次全是 0.0；
       把进程列表按 cpu_percent 降序取 Top N，同时按 memory_percent 再取一份。
       注意 cpu_percent 在多核机器上可能超过 100（表示占满多个核心），报告中要说明这一点。
   2.4 聚合：对每个指标用 statistics.fmean 求均值、max 求峰值，并记录峰值出现的样本序号与
       时间；CPU 均值与峰值分别与 --cpu-warn（默认 85%）比较生成 Finding。
   2.5 问题判定规则：CPU 均值超阈值 -> 警告；内存 available 占比低于阈值 -> 警告；
       任一分区使用率超阈值 -> 警告；磁盘 IO 等待（iowait）占比 > 20% -> 提示；
       电池剩余 < 20% 且未充电 -> 提示；交换分区使用率 > 50% -> 提示。
   2.6 对比逻辑：按 category + title 匹配两份报告，输出四类差异——新增问题、消失问题、
       数值变化（CPU 均值 ±10 个百分点以上、内存占用 ±5 个百分点以上、磁盘剩余变化
       超过 1GB）；生成一段中文结论。
   2.7 HTML 生成：模板中所有动态值经 html.escape 处理；条形图用
       <div class="bar"><span style="width:87%"></span></div> 表达；表格与卡片用少量内联
       CSS 类；不引入任何外部 CSS/JS 文件，确保单文件可离线打开。
   2.8 脱敏：用户名保留（排障需要），IP 地址默认把后两段替换为 *；
       --show-ip 输出完整地址；进程命令行中若含疑似口令参数（--password、-p 后跟值、
       token=）则替换为 ***，并在报告脚注说明已做脱敏。

3. 接口设计：
   python sysreport.py [--samples 3] [--interval 2] [--quick] [--watch]
     [--top 10] [--filter 'python,chrome'] [--pid PID]
     [--format text|html|json] [--output FILE] [--no-color]
     [--cpu-warn 85] [--mem-warn 15] [--disk-warn 85]
     [--thresholds thresholds.toml] [--compare old.json]
     [--show-ip] [--include-network] [--verbose]
   核心函数：collect_static() -> StaticInfo
             collect_dynamic(prev: DynamicSample|None) -> DynamicSample
             aggregate(samples: list[DynamicSample]) -> dict
             detect_findings(agg: dict, thresholds: dict) -> list[Finding]
             render_text(report: Report) -> str

【五、运行方式与示例】

1. 安装依赖：
   pip install "psutil>=5.9"

2. 快速体检（3 秒内出结果）：
   python sysreport.py --quick
   输出：系统体检报告  2025-05-06 14:32:05
         主机：DESKTOP-8F2K  Windows 11 10.0.22631  x86_64  开机 3 天 4 小时
         结论：发现 2 个问题 —— 磁盘 C: 使用率 92%（剩余 24.1GB）、可用内存仅 8%（2.6GB/32GB）
         CPU：8 核 16 线程  当前 34.2%（峰值 78.4%）  频率 3.6GHz
         内存：总 32.0GB  已用 29.4GB  可用 2.6GB  交换 4.0GB/8.0GB
         磁盘：C: 92% [警告]  D: 61%  E: 44%
         网络：以太网 下行 1.24 MB/s  上行 86 KB/s   回环已忽略
         进程 Top3（按 CPU）：chrome 12.4% / python 8.1% / Code 3.2%

3. 采样 5 次、间隔 3 秒，生成 HTML 报告：
   python sysreport.py --samples 5 --interval 3 --format html --output report.html
   输出：已采集 5 个样本（15 秒），检测到 1 个问题；报告：report.html（双击查看）
         结构化数据：report.html.json

4. 只看几个进程并导出 JSON：
   python sysreport.py --quick --filter 'python,chrome,postgres' --format json
     --output snap.json

5. 与上次报告对比：
   python sysreport.py --quick --json today.json --compare snap.json
   输出：与上次对比（2025-05-06 09:10:00）：
         CPU 均值 34.2% -> 71.8%（+37.6 个百分点，明显上升）
         可用内存 12.4GB -> 2.6GB（-9.8GB）
         新增问题：磁盘 C: 使用率 85% -> 92% 越线
         消失问题：无

6. 异常示例：指定的 PID 不存在
   python sysreport.py --pid 999999
   输出：错误：进程 999999 不存在或已结束（退出码 1）

7. 异常示例：非管理员权限下的部分进程
   python sysreport.py --quick --top 20
   输出：提示：3 个进程因权限不足未采集（AccessDenied），已跳过；其余指标正常
         （退出码 0）

【六、验收标准】

[ ] --quick 在 5 秒内完成并在终端输出完整报告，退出码 0。
[ ] 报告中报告的 CPU 逻辑核数与物理核数与本机任务管理器/系统信息一致。
[ ] CPU 占用百分比在做 CPU 密集运算时明显上升（与任务管理器读数偏差小于 10 个百分点）。
[ ] 内存 total 值与系统属性显示一致（误差小于 1%），已用/可用之和与 total 吻合。
[ ] 每个磁盘分区的使用率与系统“此电脑”显示的百分比一致（±1%）。
[ ] 连续两次采样计算出的网络速率与同时用任务管理器观察的速率量级一致。
[ ] --samples 5 --interval 1 的采样总耗时在 5~7 秒之间（不出现明显漂移）。
[ ] 进程 Top 榜按 CPU 与内存两列分别正确排序，且能说明 >100% 的含义。
[ ] macOS 或 Linux 上能读到温度或 load average；Windows 上相应位置显示“当前平台不支持”。
[ ] 无电池的台式机上不出现电池章节，且不报错。
[ ] 非管理员运行时遇到 AccessDenied 只跳过不崩溃，报告中说明跳过数量。
[ ] --output report.html 生成的文件双击可离线打开，样式完整，无外部资源请求。
[ ] HTML 中所有来自系统的字符串都被转义（构造含 <b> 的进程名或主机名验证）。
[ ] --compare 能正确列出新增与消失的问题，数值变化方向正确。
[ ] 报告中默认不出现完整公网 IP（后两段为 *），加 --show-ip 后完整显示。
[ ] 进程命令行中的 --password 值在报告中显示为 ***。
[ ] Ctrl+C 中断 --watch 后仍生成一份基于已采集样本的报告。
[ ] JSON 报告可被 json.load 解析，且能被 --compare 正确读回。

【七、可选扩展】

1. 增加 --watch-web：用标准库 http.server 起一个只读的本地页面，实时刷新指标。
2. 增加磁盘增长预测：记录多次报告后按日增量估算“剩余空间还能用几天”。
3. 增加启动项与计划任务清单（Windows 注册表 Run 键、Linux systemd units）的只读收集。
4. 增加 --zip：把报告与关键截图/日志打包成 zip，方便一次性发给排障人员。
5. 增加 --baseline-dir DIR，按主机名与日期自动归档 JSON，形成长期趋势库。
6. 增加 Windows 事件日志摘要（用 ctypes 调 wevtapi 或 pywin32，作为可选依赖）。

【八、涉及知识点】

- psutil 的核心 API：cpu_percent/cpu_times_percent/cpu_freq、virtual_memory/swap_memory、
  disk_partitions/disk_usage/disk_io_counters、net_io_counters/net_if_addrs、
  process_iter/Process、boot_time、sensors_temperatures/sensors_battery/sensors_fans。
- 计数器型指标的速率计算（差分 + 时间戳）与计数器回绕处理。
- cpu_percent 的首次调用返回 0 的问题与预热技巧；多核下 >100% 的语义。
- 进程采集的三种典型异常：NoSuchProcess、AccessDenied、ZombieProcess 及其处理策略。
- 跨平台差异：load average 仅 Unix、温度传感器依赖驱动、电池仅笔记本、
  Windows 无 iowait、容器与 WSL 的指标语义。
- platform 模块与 sys.getwindowsversion() 等平台探测手段。
- 人读单位换算（bytes 到 KB/MB/GB/TB，bit/s 到 Mbps）与格式化对齐。
- 报告生成的三种渲染：终端文本（含 ANSI 颜色）、单文件 HTML（内联 CSS）、
  JSON（结构化与可对比）。
- 数据脱敏原则与隐私边界（IP、命令行中的口令、用户名）。
================================================================================
