================================================================================
项目编号：022                    难度等级：★★☆☆☆（小型项目）
项目名称：网络连通性检测器
所属分类：网络与在线服务 / 运维小工具
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】
家庭宽带抖动、公司 VPN 偶发掉线、游戏延迟飙高，这类问题往往说不清是线路问题
还是目标服务问题。系统自带的 ping 只能一次盯一个目标，也不会给出抖动统计与连
续失败告警。本项目做一个多目标连通性检测器，同一轮里同时探测若干主机，分别统
计最小、平均、最大延迟与抖动（标准差），并在连续失败达到阈值时打印告警。

目标用户是需要排查网络质量的学生、运维和远程办公者。做出来之后，你可以用一条
命令同时盯着「网关、8.8.8.8、公司 VPN、对象存储域名」，一边开会一边看日志里
哪一跳开始丢包，事后用导出的 CSV 做趋势对照。

因为 ICMP 原始套接字需要管理员权限，本项目同时提供 TCP 探测模式（对指定端口做
connect 计时）作为默认方案，ICMP 作为可选增强，二者结果统一成同一份统计口径。

安全与合规声明：本工具只允许对自有主机、本机所在局域网设备或已经取得书面授权的
目标进行探测。禁止对任何第三方站点、公共网络或其他组织的主机发起扫描或压力测试。
使用前请确认目标方授权，并遵守所在国家或地区的法律法规以及目标网络的使用条款。

【二、功能需求清单】
1. 核心功能
   1.1 多目标探测：一次传入一个或多个目标，每个目标可写成 host、host:port 或
       tcp://host:port 形式；不带端口时默认使用 TCP 80 探测，若显式声明
       --mode icmp 则使用 ICMP。
   1.2 TCP 探测：记录 socket.connect_ex 的往返耗时（毫秒，保留 2 位小数），连接
       成功记为成功，超时或被拒绝分别记为 timeout、refused。
   1.3 ICMP 探测：Windows 上调用系统 ping 命令并解析输出中的时间字段，Linux/macOS
       上调用 ping -c 1 -W 超时；解析失败按失败计。程序启动时探测一次权限，无权
       限则自动回退到 TCP 模式并打印提示。
   1.4 统计指标：每个目标维护一份采样序列，实时输出成功次数、失败次数、丢包率
       （失败数 / 总次数，保留 1 位小数）、最小延迟、平均延迟、最大延迟、抖动
       （样本标准差，单位为毫秒）。
   1.5 连续失败告警：维护连续失败计数，达到 --fail-threshold（默认 3）时打印
       WARN 级别告警行，恢复成功后打印 RECOVER 行并清零计数。
   1.6 结果导出：--csv PATH 参数把每一轮每个目标的采样行追加写入 CSV，字段为
       timestamp,target,mode,seq,status,latency_ms。
   1.7 退出码约定：全部目标最终成功返回 0，存在丢包但未全部失败返回 1，全部目标
       均不可达返回 2，参数错误返回 3。

2. 输入与交互
   2.1 命令形式：python ping_tool.py TARGET [TARGET ...] --count N --interval SEC。
   2.2 --count 默认 5，取值 1 ~ 1000；--interval 默认 1.0 秒，取值 0.2 ~ 60。
   2.3 --workers 控制线程池大小，默认 8，上限 64，且不得超过目标数量的 4 倍。
   2.4 --timeout 单次探测超时，默认 1.0 秒，范围 0.1 ~ 10。
   2.5 --retry 单次探测失败后的重试次数，默认 1，范围 0 ~ 3；只有最终仍失败的
       采样才计为失败。
   2.6 Ctrl+C 中断时立即停止调度，等待已在运行的探测结束，然后输出统计摘要。

3. 输出与展示
   3.1 运行期每轮打印一行实时结果：
       时间戳（HH:MM:SS）目标名 状态（OK/TIMEOUT/REFUSED/ERROR）延迟（ms）
   3.2 结束时打印汇总表，一个目标一段，字段为：目标、模式、发送、成功、丢包率、
       最小/平均/最大延迟、抖动、末次状态。
   3.3 目标名统一为 host:port 形式，长度不足 24 字符时右侧补空格对齐。
   3.4 延迟数值统一保留两位小数，丢包率保留一位小数并带百分号。

4. 异常与边界处理
   4.1 目标字符串非法（端口非数字、端口越界）时打印错误并以退出码 3 结束。
   4.2 DNS 解析失败（socket.gaierror）记为 status=resolve_failed，并在该目标首轮
       失败时打印一次「无法解析主机名」提示，后续轮次不重复刷屏。
   4.3 workers 大于目标数量时实际线程数取目标数量，避免空转。
   4.4 CSV 文件已存在且首行不是预期表头时，另存为 PATH.1 并在日志中说明。
   4.5 count 为 1 时标准差无意义，抖动显示为 0.00 并在备注列标注「样本不足」。
   4.6 探测耗时统计使用 time.perf_counter，禁止使用 time.time，避免系统时间调整影响。

【三、技术要求与约束】
1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库。并发使用 concurrent.futures.ThreadPoolExecutor，
   套接字使用 socket，统计使用 statistics.pstdev，子进程调用 ICMP 使用
   subprocess.run，命令行使用 argparse，日志使用 logging，CSV 使用 csv 模块。
3. 并发模型：采用线程池，worker 数由 --workers 指定，线程池在整个检测周期内复用，
   不为每一次探测新建线程；共享统计对象用 threading.Lock 保护，禁止在锁内做 IO。
4. 超时与重试：TCP 用 socket.settimeout(timeout)；ICMP 用子进程 timeout 参数并在
   超时后 kill；每次失败按指数退避（0.2 秒、0.4 秒）重试，重试总耗时不得超过
   timeout 的 3 倍。
5. 限速要求：单个目标每秒探测次数不得超过 5 次，程序据此校验 interval，若
   interval 小于 0.2 秒直接拒绝启动；同时并发探测的目标总数不得超过 32 个，超出
   时按参数错误处理，防止对网络造成冲击。
6. 合规要求：程序启动时打印一行使用提示，声明「本工具仅可用于自有或已获得明确
   授权的网络与主机，禁止用于未经许可的探测、扫描与压测」；README 与 --help 中
   均需出现该声明。涉及网页类目标的探测须遵守目标站点 robots.txt 与使用条款。
7. 禁止事项：禁止使用原始套接字构造自定义 ICMP 包（需管理员权限且易被滥用）；
   禁止实现 SYN 半开扫描、禁止伪造源地址、禁止加入 DoS 性质的并发放大逻辑。
8. 代码组织：probe.py（tcp_probe、icmp_probe、统一 ProbeResult）、stats.py
   （LatencyStats 类）、runner.py（线程池调度与轮次控制）、cli.py（参数与输出）、
   export.py（CSV 写入）。全部函数带类型注解与 docstring。
9. 编码规范：日志输出到 stderr，正常结果输出到 stdout；禁止用 print 做调试；
   私有函数以下划线开头；常量集中定义在文件顶部。

【四、设计要点】
1. 数据结构：
   ProbeResult = {
       "target": str,         目标规范名，形如 10.0.0.1:443
       "mode": str,           tcp / icmp
       "seq": int,            轮次序号，从 1 开始
       "status": str,         ok / timeout / refused / resolve_failed / error
       "latency_ms": float,   失败时为 None
       "timestamp": str,      ISO 8601 本地时间
       "attempts": int        实际尝试次数，含重试
   }
   LatencyStats 字段：samples（成功延迟列表）、sent、ok、failed、consecutive_fail、
   last_status、lock。方法 add(result) 与 summary() -> dict。
2. 关键算法或流程：
   2.1 轮次循环：for seq in range(1, count+1)：提交所有目标的探测任务 → 用
       as_completed 收集 → 逐个更新统计与告警 → 打印实时行 → 睡眠剩余间隔时间
       （间隔减去本轮调度耗时，为负则不再睡）。
   2.2 TCP 探测：解析目标 → socket.getaddrinfo 取地址 → 创建 socket 设置超时 →
       perf_counter 记开始 → connect_ex → 记结束 → 依据返回码映射状态。
   2.3 ICMP 探测：subprocess.run(["ping", "-n", "1", "-w", str(ms), host], timeout=...)
       在 Windows 上执行；用正则 (\d+)ms 提取延迟；返回码非 0 判为失败。
   2.4 抖动计算：先算平均延迟 mean，再算 sqrt(sum((x-mean)^2)/n)，n 小于 2 时返回 0。
   2.5 告警判定：连续失败计数达到阈值时只打印一次告警（用 alerted 布尔位去重），
       恢复时若此前已告警则打印恢复行。
3. 接口或命令设计：
   python ping_tool.py 192.168.1.1:80 8.8.8.8:53 --count 10 --interval 1 --workers 4
   python ping_tool.py gateway.local --mode icmp --timeout 2 --retry 2 --csv out.csv
   关键函数签名：
   def tcp_probe(target: str, timeout: float, seq: int) -> ProbeResult
   def icmp_probe(host: str, timeout: float, seq: int) -> ProbeResult
   def run_round(targets: list[str], pool: ThreadPoolExecutor, seq: int) -> list[ProbeResult]

【五、运行方式与示例】
安装与运行（无需第三方依赖）：
   python ping_tool.py --help
   python ping_tool.py 192.168.1.1:80 1.1.1.1:53 --count 5 --interval 1 --workers 2
示例一（全部可达）：
   10:31:07  192.168.1.1:80    OK       3.42 ms
   10:31:07  1.1.1.1:53        OK      21.08 ms
   汇总：
   目标 192.168.1.1:80    TCP  发送 5  成功 5  丢包 0.0%  最小 3.10 平均 3.42 最大 3.91 抖动 0.29
   目标 1.1.1.1:53        TCP  发送 5  成功 5  丢包 0.0%  最小 20.4 平均 21.1 最大 22.3 抖动 0.62
   退出码：0
示例二（连续失败告警）：
   10:32:01  10.0.0.9:8080    TIMEOUT  --
   WARN      10.0.0.9:8080 连续失败 3 次，疑似不可达
   10:32:09  10.0.0.9:8080    OK       8.77 ms
   RECOVER   10.0.0.9:8080 已恢复
   退出码：1
示例三（异常输入）：
   python ping_tool.py 192.168.1.1:99999
   输出：错误：端口 99999 超出范围 1-65535
   退出码：3
   python ping_tool.py a.invalid --count 1
   输出：10:33:00  a.invalid:80  RESOLVE_FAILED  无法解析主机名 a.invalid
   退出码：2

【六、验收标准】
[ ] --count 5 时每个目标恰好产生 5 条采样记录，CSV 行数与目标数一致。
[ ] 对一个确定开放的端口做 TCP 探测，status 为 ok 且延迟为正数。
[ ] 对一个本机关闭的端口做 TCP 探测，status 为 refused 而不是 timeout。
[ ] --timeout 0.1 探测黑洞地址时全部为 timeout，且单轮总耗时约等于超时时间。
[ ] 连续失败 3 次后出现一行 WARN，恢复后出现一行 RECOVER，且告警不重复刷屏。
[ ] 只成功 3 次的 5 轮检测中丢包率显示 40.0%，退出码为 1。
[ ] count 为 1 时抖动显示 0.00。
[ ] --interval 0.05 被拒绝并提示最小间隔 0.2 秒，退出码为 3。
[ ] --workers 100 被拒绝或自动收敛到 64，并打印提示。
[ ] 传入 40 个目标时提示目标数量超过 32 的限制并退出。
[ ] 启动时打印合规声明行，--help 中也包含授权与限速说明。
[ ] --csv 导出的文件可被 csv.DictReader 正常解析，表头与字段定义一致。
[ ] 源码中没有 import 第三方库，python -m py_compile 全部通过。
[ ] 抖动数值与 statistics.pstdev 手动计算结果一致（误差小于 0.01）。

【七、可选扩展】
1. 增加 HTTP 探测模式，请求指定 URL 并同时记录状态码、TLS 握手耗时与首字节耗时。
2. 增加持续监控模式 --watch，按固定周期滚动输出，并生成简单 ASCII 折线图展示
   最近 60 轮延迟走势（仍不引入第三方库）。
3. 支持从配置文件读取目标分组，一次运行多组目标并分别汇总。
4. 达标判定：允许为每个目标配置延迟上限与丢包上限，超出时以非零退出码结束，方便
   接入计划任务做自动化巡检。

【八、涉及知识点】
- socket 编程：connect_ex、settimeout、getaddrinfo 与常见错误码映射
- concurrent.futures 线程池与 as_completed 收集结果
- threading.Lock 保护共享统计对象
- time.perf_counter 做高精度计时
- statistics 模块计算均值与总体标准差
- subprocess 调用系统命令并解析文本输出
- 指数退避重试与连续失败告警的状态机
- csv 模块追加写入与表头一致性校验
- 网络探测的合规边界与限速设计
================================================================================
