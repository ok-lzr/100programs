================================================================================
项目编号：024                    难度等级：★★☆☆☆（小型项目）
项目名称：本机网络信息查看器
所属分类：网络与在线服务 / 系统信息
建议工时：4 ~ 5 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库，psutil 为可选增强）
================================================================================

【一、项目背景与目标】
换到新网络后，很多人第一反应是打开一堆命令行：ipconfig 看内网 IP，nslookup 看
DNS，ping 网关看通不通，再去网页查公网出口 IP，最后还要确认系统代理有没有把流量
劫持到一个连不上的地址。这些信息散落在四五个命令和网页里，排查一次要来回切换。
本项目把这些步骤合并成一个命令，一次性输出网卡清单、地址、网关、DNS、代理配置，
并做一次连通性体检。

目标用户是需要快速判断「网到底通不通、出口是谁」的远程办公者、学生与运维人员。
做出来之后，你把报告贴给同事或服务商，对方一眼就能看出是 DNS 配置问题、网关不可
达，还是代理设置导致的。

工具只读取本机配置，不修改任何网络设置；唯一的对外行为是可选地向一个公开的
「查询我的 IP」接口发一次 HTTPS 请求，用于获取公网出口地址，该行为可通过
--no-public-ip 关闭，并遵守该服务的 robots.txt、使用条款与调用频率限制。

【二、功能需求清单】
1. 核心功能
   1.1 网卡清单：列出所有网络接口的名称、状态（up/down）、MAC 地址、IPv4 地址与
       前缀长度、IPv6 地址、是否回环、是否启用。
   1.2 默认路由与网关：识别默认网关地址，并给出该网关所在网卡；无法获取时明确显示
       「未获取到默认网关」而不是留空。
   1.3 DNS 配置：读取系统配置的 DNS 服务器列表（Windows 用 ipconfig /all 与注册表
       查询组合，Linux 读 /etc/resolv.conf，macOS 用 scutil --dns）；对每个 DNS
       做一次解析测试（解析 example.com），记录耗时与是否成功。
   1.4 代理配置：读取环境变量 HTTP_PROXY、HTTPS_PROXY、NO_PROXY 以及 Windows 的
       Internet 选项代理设置（注册表 HKCU\Software\Microsoft\Windows\CurrentVersion\
       Internet Settings 下的 ProxyEnable 与 ProxyServer），统一展示为「直连 / 系统
       代理 / 环境变量代理」。
   1.5 公网出口 IP：默认向 https://api.ipify.org?format=json 发一次 GET 请求（超时
       3 秒），解析返回的 IP；失败时展示「未获取到公网 IP」并给出失败原因。可用
       --public-api 指定其他接口地址，或用 --no-public-ip 完全关闭。
   1.6 连通性体检：依次检测本机回环、默认网关、DNS 服务器、公网出口，四项各给出
       通过 / 失败与耗时；最终给出结论行，例如「网关可达但 DNS 解析失败，建议检查
       DNS 配置」。
   1.7 报告导出：--json PATH 输出结构化结果，--report PATH 输出纯文本报告文件。

2. 输入与交互
   2.1 命令形式：python netinfo.py [--json PATH] [--no-public-ip] [--public-api URL]
       [--dns-test-domain example.com] [--timeout 3]。
   2.2 无位置参数，所有参数均为可选；直接运行即输出完整报告。
   2.3 --timeout 控制所有网络探测的单次超时，默认 3 秒，范围 1 ~ 10。
   2.4 --section 参数可只输出指定段落，取值 interfaces/routes/dns/proxy/public/health，
       可重复传入，便于脚本化调用。

3. 输出与展示
   3.1 分段标题使用中文方括号，如【网卡】、【默认路由】、【DNS】、【代理】、
       【公网出口】、【体检结论】。
   3.2 网卡每行格式：名称（左对齐 16）、状态（up/down）、IPv4（左对齐 16）、
       前缀（右对齐 3）、MAC（17 字符）、标志（loopback 时标注 LOOPBACK）。
   3.3 DNS 行格式：地址（左对齐 20）、类型（系统配置 / 环境变量）、解析测试结果
       （OK 12.3 ms 或 FAIL）。
   3.4 体检结论每项格式：项目（左对齐 10）、结果（PASS/FAIL）、说明。
   3.5 全部时间字段统一毫秒，保留 1 位小数。

4. 异常与边界处理
   4.1 未安装 psutil 时正常降级：用 socket 与平台命令获取信息，不能因为缺依赖而崩溃。
   4.2 系统命令不存在或返回非零时，捕获异常并把该字段标记为 unavailable，其余段落
       继续输出。
   4.3 存在多个默认网关（如同时有以太网与 VPN）时全部列出，并标注哪一个是当前出口
       （按路由优先级或第一条判定），同时提示可能存在流量分流。
   4.4 没有可用网卡（全 down）时体检结论直接给出「无可用网络接口」，跳过其余探测。
   4.5 公网 IP 接口返回非 JSON 或超时，最多重试 1 次，仍失败则记录原因，不抛异常。
   4.6 读取注册表失败（权限不足或非 Windows）时静默跳过系统代理段落并提示 unavailable。
   4.7 DNS 测试域名解析失败时，若四个 DNS 全部失败，结论指向 DNS 配置而非网络断开。

【三、技术要求与约束】
1. 语言与版本：Python 3.10 及以上；代码需在 Windows 与 Linux 上可运行，用
   sys.platform 分支处理平台差异，禁止只在 Windows 下可用。
2. 允许使用的库：标准库 socket、subprocess、platform、os、json、urllib.request、
   ipaddress、argparse、time、logging、pathlib。可选第三方 psutil（未安装时自动
   降级），除此之外不得引入其他依赖。
3. 并发模型：网络探测（DNS 测试、网关探测、公网 IP 查询）使用
   concurrent.futures.ThreadPoolExecutor，默认 4 个 worker，总探测项不超过 8 个，
   一次性并发执行而非串行等待，报告中按固定顺序展示结果。
4. 超时与重试：所有 socket 与 HTTP 操作必须设置超时，禁止无限等待；公网 IP 查询
   失败重试 1 次，重试间隔 1 秒；DNS 测试不重试（避免放大问题）。
5. 限速要求：公网 IP 查询每次运行最多发起 2 次请求（含重试），不得在循环中反复
   调用公开接口；建议同一台机器两次运行间隔不少于 30 秒。DNS 测试每次运行每个
   服务器只查询一次。
6. 合规要求：仅访问公开且无需鉴权的 IP 查询接口，遵守目标服务的使用条款与
   robots.txt；不支持可配置的高频轮询模式；禁止把本机网卡信息、MAC 地址等发送到
   任何第三方接口，除公网 IP 查询这一项（且可关闭）。
7. 禁止事项：禁止修改系统网络配置（如改 DNS、改代理、重启网卡）；禁止执行任何
   需要提权的写操作；禁止硬编码任何 API 密钥；如果将来接入需要密钥的服务，必须从
   环境变量读取。
8. 代码组织：collectors/（interfaces.py、routes.py、dns.py、proxy.py、public_ip.py
   各负责一类采集）、health.py（四项体检与结论生成）、render.py（文本与 JSON 渲染）、
   cli.py（参数与入口）。每个采集函数返回统一的结构化 dict 或 dataclass。
9. 编码规范：使用 dataclasses 定义 InterfaceInfo、DnsServer、HealthCheck 等模型；
   全部函数带类型注解与 docstring；日志写 stderr；采集失败用 logging.warning 记录，
   不向 stdout 混入调试内容。

【四、设计要点】
1. 数据结构：
   InterfaceInfo = {name, is_up, mac, ipv4, prefix_len, ipv6_list, is_loopback,
                    speed_mbps}
   DnsServer = {address, source, ok, latency_ms, error}
   ProxyInfo = {mode, http_proxy, https_proxy, no_proxy, source}
   HealthCheck = {item, ok, latency_ms, detail}
   NetReport = {generated_at, hostname, platform, interfaces, gateways, dns_servers,
                proxy, public_ip, public_ip_error, health, conclusion}
2. 关键算法或流程：
   2.1 网卡采集：优先尝试 import psutil，成功则用 psutil.net_if_addrs() 与
       net_if_stats()；失败则 Windows 解析 ipconfig /all，Linux 读
       /sys/class/net 与 socket 的地址探测，统一填充 InterfaceInfo。
   2.2 网关采集：Windows 从 ipconfig 输出中正则匹配「默认网关」或 "Default
       Gateway" 行；Linux 读 /proc/net/route 找 Destination 为 00000000 的行并转换
       十六进制小端地址；macOS 用 route -n get default。
   2.3 DNS 采集：Windows 执行 ipconfig /all 提取「DNS 服务器」段的多行地址；Linux
       解析 /etc/resolv.conf 的 nameserver 行；macOS 解析 scutil --dns 的
       nameserver[0] 行。随后对每个地址执行 socket.getaddrinfo(测试域名, 80) 并计时。
   2.4 体检流程：把四项检查包装成可调用对象提交线程池 → as_completed 收集 →
       按回环、网关、DNS、公网出口固定顺序排列 → 依据失败项组合生成结论文案
       （网关失败优先提示物理链路，DNS 失败优先提示配置，前两项通过而公网失败提示
       出口或代理问题）。
   2.5 代理判定：环境变量优先于系统设置；若 HTTPS_PROXY 存在则 mode 为 env，若仅
       系统代理开启则 mode 为 system，两者都无则为 direct。
3. 接口或命令设计：
   python netinfo.py
   python netinfo.py --section interfaces --section dns
   python netinfo.py --no-public-ip --json net.json --timeout 5
   关键函数签名：
   def collect_interfaces() -> list[InterfaceInfo]
   def collect_gateways() -> list[str]
   def collect_dns_servers() -> list[DnsServer]
   def detect_proxy() -> ProxyInfo
   def fetch_public_ip(api_url: str, timeout: float) -> tuple[str | None, str | None]
   def run_health_checks(report: NetReport, timeout: float) -> list[HealthCheck]

【五、运行方式与示例】
安装与运行（默认零依赖，可选安装 psutil 提升采集完整度）：
   python netinfo.py
   pip install psutil           可选，增加网卡速率与更完整的地址信息
示例一（正常输出片段）：
   【网卡】
   Ethernet          up    192.168.1.23     24  3C-7C-3F-1A-2B-4D
   Loopback          up    127.0.0.1         8  00-00-00-00-00-00  LOOPBACK
   【默认路由】
   网关：192.168.1.1（接口 Ethernet）
   【DNS】
   192.168.1.1      系统配置   OK 12.3 ms
   223.5.5.5        系统配置   OK 21.7 ms
   【代理】
   模式：直连（未检测到环境变量代理与系统代理）
   【公网出口】
   203.0.113.45（来源：api.ipify.org，耗时 412.0 ms）
   【体检结论】
   回环        PASS   127.0.0.1 可访问
   网关        PASS   192.168.1.1 响应 1.8 ms
   DNS         PASS   2/2 服务器解析成功
   公网出口    PASS   已获取公网 IP
   结论：网络连接正常，DNS 解析与公网出口均可用。
示例二（关闭公网查询并导出）：
   python netinfo.py --no-public-ip --json net.json
   输出：【公网出口】已按 --no-public-ip 跳过；报告已写入 net.json
   退出码：0
示例三（异常输入与故障场景）：
   python netinfo.py --timeout 0
   输出：错误：--timeout 取值范围为 1 ~ 10
   退出码：2
   python netinfo.py（在断网环境下）
   输出：
   回环        PASS
   网关        FAIL   192.168.1.1 无响应（超时 3.0 s）
   DNS         FAIL   0/2 服务器解析成功
   公网出口    FAIL   未获取到公网 IP（网络不可达）
   结论：网关不可达，请检查网线或 Wi-Fi 连接。

【六、验收标准】
[ ] 在 Windows 与 Linux 上分别运行，均能列出非回环网卡的 IPv4 地址且格式正确。
[ ] 拔掉网线（或关闭 Wi-Fi）后运行，体检结论给出「无可用网络接口」或网关 FAIL。
[ ] 卸载 psutil 后运行不报 ImportError，网卡段落仍能输出。
[ ] DNS 段落正确读取 /etc/resolv.conf（Linux）或 ipconfig /all（Windows）中的地址。
[ ] 手工设置 HTTPS_PROXY 环境变量后，代理段落显示环境变量代理及对应地址。
[ ] 设置 NO_PROXY 后，代理段落同时展示 NO_PROXY 内容。
[ ] --no-public-ip 时不发起任何外部 HTTP 请求（可用抓包或断网验证）。
[ ] --public-api 指向一个 404 地址时，公网出口段落显示失败原因且程序不崩溃。
[ ] --section interfaces 只输出网卡段落，其他段落不出现。
[ ] --timeout 0 与 --timeout 99 均报参数错误，退出码 2。
[ ] --json 导出的文件可被 json.load 解析，且包含 interfaces、dns_servers、health
    等约定字段。
[ ] 存在两个默认网关时全部列出，并标注当前出口。
[ ] 代码中不存在任何写入系统网络配置的调用。
[ ] 公网 IP 查询在一次运行中最多 2 次（可用日志计数验证）。
[ ] python -m py_compile 对所有模块通过，无语法错误。

【七、可选扩展】
1. 增加 --watch 模式，按固定间隔（最小 30 秒）刷新延迟与丢包，检测网络切换并在
   断开与恢复时各打印一行事件。
2. 增加 traceroute 风格的路径探测（基于 ICMP TTL 递增），输出到公网出口的逐跳
   延迟，仍限自有与已授权网络使用。
3. 增加历史记录，把每次体检结果存入 ~/.netinfo/history.jsonl，支持对比两次报告，
   显示 IP 或 DNS 的变化。
4. 增加 Wi-Fi 信号强度与连接速率读取（Windows 用 netsh wlan show interfaces，
   Linux 用 /proc/net/wireless），在网卡段落补充无线信息。

【八、涉及知识点】
- socket、getaddrinfo 与 DNS 解析流程
- subprocess 调用系统命令并解析多平台输出
- 正则表达式提取结构化字段
- ipaddress 模块处理网段与地址分类
- urllib.request 发起 HTTPS 请求与超时处理
- concurrent.futures 线程池做并行探测
- dataclasses 建模与类型注解
- 环境变量与系统代理的读取优先级
- 平台差异处理与优雅降级设计
- 公开 API 的调用频率限制与使用条款
================================================================================
