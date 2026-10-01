================================================================================
项目编号：023                    难度等级：★★☆☆☆（小型项目）
项目名称：端口扫描器（教学版）
所属分类：网络与在线服务 / 网络安全基础
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】
想搞清楚「我家里这台 NAS 到底开了哪些服务」「我写的 Flask 应用有没有只监听到
127.0.0.1」，最有用的手段就是扫一遍自己的端口。现成工具功能强大但参数复杂，输
出也不告诉你每个端口对应的服务是什么。本项目实现一个教学版端口扫描器，用 TCP
connect 的方式探测目标端口是否开放，并对识别出的服务做简单指纹判断与横幅抓取。

目标用户是正在学习网络与运维的开发者。做出来之后，你可以扫描自己的主机、家里的
树莓派、实验室的服务器，得到一张「端口 - 状态 - 服务 - 横幅」的清单，顺带理解
TCP 三次握手、并发连接与超时控制这些基础概念。

安全与合规声明（必读）：本程序仅可用于扫描你自己拥有的主机、你所在且已获管理员
许可的局域网设备，或已取得书面授权的目标。未经授权对他人主机、校园网、公司内网、
运营商网络或任何公网地址进行端口扫描，在多数国家和地区属于违法行为，可能承担
法律责任。禁止把本工具改造成批量公网扫描、禁止加入分布式扫描能力、禁止用于漏洞
探测与入侵。程序在启动时会强制要求显式输入目标，且默认拒绝公网 IP 段，除非加
--i-own-this-target 参数二次确认。

【二、功能需求清单】
1. 核心功能
   1.1 TCP connect 扫描：对目标每个端口创建 socket 并调用 connect_ex，返回 0 记为
       open，返回 ECONNREFUSED 记为 closed，超时记为 filtered。
   1.2 端口集合选择：内置三套常见端口表——common（约 30 个高频端口，含 21、22、
       23、25、53、80、110、135、139、143、443、445、993、995、1433、1521、2049、
       3306、3389、5432、5900、6379、8080、8443、9200、11211、27017）、web（80、
       443、8000、8008、8080、8081、8443、8888、9000）、dev（3000、5000、5173、
       7000、8000、8001、8080、8888、9000）。可用 --ports 传入自定义列表，支持
       范围写法 1-1024 与逗号组合 22,80,443,8000-8010。
   1.3 服务识别：内置 端口→服务名 映射表（如 22→ssh、3306→mysql、6379→redis），
       输出时展示服务名，未知端口显示 unknown。
   1.4 横幅抓取：对识别为 open 且属于文本类协议（ssh、http、https、ftp、smtp、
       pop3、imap、redis、mysql）的端口，尝试在 --banner-timeout 内读取最多 256
       字节的响应作为横幅，清洗掉不可打印字符后截断到 60 字符展示；--no-banner
       关闭该行为。
   1.5 HTTP 探测：对开放且判定为 HTTP 的端口，发送极简 GET / HTTP/1.0 请求，从
       响应首行或 Server 头提取服务信息（如 nginx、Apache），写入横幅字段。
   1.6 结果排序与过滤：输出按端口号升序；--only-open 只展示开放端口；--json PATH
       导出结构化结果。
   1.7 汇总：输出开放端口数量、扫描耗时、平均单端口耗时，以及每个开放端口的风险
       提示文案（如 23/telnet 明文协议、6379/redis 未授权风险、3389/rdp 暴露面）。

2. 输入与交互
   2.1 命令形式：python scan.py TARGET [--ports common|web|dev|表达式]
       [--workers 100] [--timeout 0.8] [--banner-timeout 1.5] [--only-open]。
   2.2 TARGET 必填，支持单个 IPv4 地址或域名；本版本只允许单个目标，不接受网段
       （CIDR）写法，检测到斜杠时直接报错退出，从设计上避免批量扫描滥用。
   2.3 --workers 默认 100，范围 1 ~ 200，上限 200 用于限制瞬时并发连接数。
   2.4 --timeout 默认 0.8 秒，范围 0.1 ~ 5.0；--banner-timeout 默认 1.5 秒。
   2.5 --rate 限速参数，默认每秒最多 300 个连接尝试，范围 10 ~ 500。
   2.6 Ctrl+C 中断时打印已扫描进度与已发现结果，退出码 130。

3. 输出与展示
   3.1 表格列：端口（右对齐 6）、状态（左对齐 9）、服务（左对齐 10）、横幅（左
       对齐 60）。开放端口状态字段用绿色语义标记（纯文本环境下用 [OPEN] 前缀）。
   3.2 每扫描完 10% 的端口打印一次进度行（已完成数 / 总数、开放数、耗时）。
   3.3 汇总段落包含：目标、解析到的 IP、端口总数、开放数、closed 数、filtered 数、
       总耗时、平均每端口耗时、风险提示条数。
   3.4 --json 输出结构包含 target、resolved_ip、scanned_at、results 数组与 summary。

4. 异常与边界处理
   4.1 域名解析失败时输出错误并退出码 3；解析出多个 A 记录时取第一个并打印说明。
   4.2 目标是 0.0.0.0、255.255.255.255、组播地址或 169.254 网段时拒绝执行。
   4.3 目标是公网地址且未提供 --i-own-this-target 时拒绝执行，提示需要授权确认。
   4.4 端口表达式非法（如 70000、abc、5-3）时报错退出码 2，并指出出错片段。
   4.5 端口集合去重后按升序执行，重复端口只扫一次。
   4.6 单端口探测过程中出现 socket.error（非超时、非拒绝）时记为 error 状态并计入
       filtered 之外的独立计数字段，不中断整体扫描。
   4.7 横幅抓取失败或超时不应影响该端口状态判定，横幅显示为短横线。

【三、技术要求与约束】
1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库。socket、concurrent.futures.ThreadPoolExecutor、
   ipaddress（判断地址类型）、argparse、json、time、logging、re。
3. 并发模型：使用线程池，全流程复用一个 ThreadPoolExecutor，worker 数由
   --workers 控制且不超过 200；用信号量（threading.Semaphore）实现每秒连接数上限
   --rate，在每次探测前 acquire，按令牌桶思路补充令牌。禁止一个端口创建一个线程。
4. 超时与重试：每次 connect 前 setblocking(False) + select.select 实现可控超时，
   或使用 settimeout；默认不重试，--retry N（0~2）用于应对抖动，重试时端口状态取
   最后一次结果，并在结果中记录 attempts 字段。
5. 限速要求：默认速率上限 300 次连接/秒，程序必须实际生效而不是仅打印提示；对同一
   目标连续扫描的间隔建议不低于 10 分钟，并在文档中说明。
6. 合规要求：程序启动先打印一段合规声明并要求用户阅读；默认拒绝公网目标；不提供
   网段扫描；不实现 SYN 半开扫描与 UDP 扫描；不提供漏洞利用或弱口令尝试能力。
   若目标为网站，抓取横幅的行为须遵守该站点 robots.txt 与使用条款，且仅抓取根路径。
7. 禁止事项：禁止引入第三方库；禁止多目标批量模式；禁止统计结果上传网络；禁止在
   日志中记录任何凭据信息。
8. 代码组织：ports.py（端口表、服务映射、端口表达式解析）、scanner.py（scan_port、
   grab_banner、http_probe）、guard.py（目标合法性校验与合规拦截）、report.py
   （文本表格与 JSON 渲染）、cli.py（参数解析与主流程）。
9. 编码规范：类型注解 + docstring 全覆盖；异常统一捕获为自定义 ScanError；时间统计
   使用 perf_counter；日志写 stderr，报表写 stdout。

【四、设计要点】
1. 数据结构：
   PortResult = {
       "port": int,
       "state": str,        open / closed / filtered / error
       "service": str,      服务名或 unknown
       "banner": str | None,
       "attempts": int,
       "elapsed_ms": float,
       "risk": str | None   风险提示，无风险为 None
   }
   ScanSummary = {"target": str, "resolved_ip": str, "total": int, "open": int,
                  "closed": int, "filtered": int, "error": int, "elapsed_s": float}
   SERVICE_MAP: dict[int, str]，RISK_MAP: dict[int, str] 两个常量表。
2. 关键算法或流程：
   2.1 端口表达式解析：按逗号切分 → 每段若含短横线则解析为闭区间（起点必须小于
       终点、两端均在 1~65535 内）→ 展开为集合 → 排序去重 → 返回 list[int]。
   2.2 端口探测：创建 socket(AF_INET, SOCK_STREAM) → settimeout(timeout) →
       perf_counter 记开始 → connect_ex((ip, port)) → 记结束 → 按返回码映射状态：
       0 为 open，errno 111/61/10061 为 closed，EAGAIN/超时为 filtered，其余为 error。
   2.3 横幅抓取：仅在 state 为 open 时执行；对 80/8000/8080 类端口先发
       b"GET / HTTP/1.0\r\nHost: <ip>\r\n\r\n"；对其余端口直接 recv；用
       bytes.decode("utf-8", errors="replace") 解码，正则去掉控制字符与多余空白。
   2.4 限速实现：Semaphore(rate) 配合一个后台计时线程，每 1/rate 秒释放一个令牌；
       主调度在提交任务前 acquire，保证平均速率不超过上限。
   2.5 进度输出：用已完成计数与总端口数的比例判断是否跨过 10% 的整数倍阈值，跨过
       则打印一行进度，避免每扫一个端口都刷屏。
3. 接口或命令设计：
   python scan.py 192.168.1.10 --ports common --workers 100 --only-open
   python scan.py myserver.local --ports 22,80,443,8000-8010 --timeout 1.0 --json r.json
   关键函数签名：
   def parse_ports(expr: str) -> list[int]
   def scan_port(ip: str, port: int, timeout: float) -> PortResult
   def grab_banner(ip: str, port: int, timeout: float) -> str | None
   def validate_target(target: str, allow_public: bool) -> str

【五、运行方式与示例】
安装与运行（无需第三方依赖，建议只扫本机）：
   python scan.py 127.0.0.1 --ports common --only-open
示例一（扫描本机常见端口）：
   目标：127.0.0.1    端口数：30    并发：100
   [OPEN]    22  ssh        OpenSSH_9.6p1 Ubuntu-3ubuntu13
   [OPEN]  3306  mysql      J
   [OPEN]  8080  http-alt   HTTP/1.1 200 OK  Server: Werkzeug/3.0.1
   汇总：开放 3  closed 24  filtered 3  总耗时 1.24 s  平均每端口 41.3 ms
   风险提示：3306/mysql 建议仅监听 127.0.0.1，勿对公网暴露
   退出码：0
示例二（自定义端口区间并导出 JSON）：
   python scan.py 192.168.1.10 --ports 80,443,8000-8005 --timeout 1.0 --json r.json
   输出：开放 1（443/https），closed 5，filtered 2，JSON 已写入 r.json
示例三（异常输入，合规拦截）：
   python scan.py 8.8.8.8 --ports 80
   输出：错误：目标 8.8.8.8 属于公网地址。本工具仅限扫描自有或已授权主机，
         如确已获得授权请加 --i-own-this-target 参数
   退出码：3
   python scan.py 127.0.0.1 --ports 70000
   输出：错误：端口片段 70000 超出范围 1-65535
   退出码：2
   python scan.py 192.168.1.0/24
   输出：错误：本工具不支持网段（CIDR）扫描，请逐个指定已授权主机
   退出码：3

【六、验收标准】
[ ] --ports common 在 127.0.0.1 上能正确识别出已开启的本机服务端口。
[ ] 对确定关闭的端口（如未监听的 65530）状态为 closed，不是 filtered。
[ ] 对丢弃包的目标端口状态为 filtered，且耗时接近 --timeout 设定值。
[ ] 端口表达式 22,80,8000-8002 解析为 5 个端口且按升序去重。
[ ] 表达式 5-3、70000、abc 均报错退出码 2 并指出出错片段。
[ ] 目标为 8.8.8.8 且未加授权参数时被拒绝执行。
[ ] 目标为 192.168.1.0/24 时被拒绝执行。
[ ] --workers 500 被拒绝或收敛到 200。
[ ] --rate 10 时 1000 个端口的扫描总耗时不少于 90 秒（限速真实生效）。
[ ] 开放端口 8080 上能抓到含 HTTP 或 Server 字样的横幅。
[ ] --only-open 输出中不包含 closed 与 filtered 行。
[ ] --json 导出的文件可被 json.load 解析，字段与设计文档一致。
[ ] 每 10% 打印一次进度行，30 个端口时进度行不超过 12 行。
[ ] 源码无第三方 import，且不存在网段扫描或多目标批量扫描的代码路径。
[ ] 启动时打印合规声明，--help 中包含授权与限速说明。

【七、可选扩展】
1. 增加 --udp 选项，用 UDP 发送空包并依据 ICMP 端口不可达判断端口状态（仅限本机
   与局域网，且必须在文档中重申授权前提）。
2. 增加扫描历史记录，把每次扫描结果存入本地 JSONL，支持对比两次扫描的差异（新
   增开放端口、关闭端口）。
3. 增加服务指纹库文件 services.json，允许用户自行扩充 端口→服务→风险 的三级映射。
4. 输出可导出为 CSV 或 HTML 报表，便于整理成安全自查报告。

【八、涉及知识点】
- TCP 三次握手与 connect 语义、连接拒绝与超时的区别
- socket 超时控制与 errno 错误码映射
- concurrent.futures 线程池与批量结果收集
- threading.Semaphore 实现令牌桶限速
- ipaddress 模块判断地址类型与私有网段
- 端口与服务映射、常见服务默认端口
- 横幅抓取与服务指纹识别的基本思路
- argparse 自定义类型校验函数
- 网络安全合规边界：授权、范围控制与最小必要原则
================================================================================
