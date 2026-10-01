================================================================================
项目编号：064                    难度等级：★★★★☆（中型项目）
项目名称：加密货币行情告警器
所属分类：内容采集与自动化 / 实时行情与告警
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：websockets、requests
================================================================================

【一、项目背景与目标】

加密货币 7x24 小时交易，人不可能一直盯着屏幕，但价格在凌晨三点插针、某个币一小时内暴涨 8%
这类事件又必须知道。本项目做一个常驻的行情订阅与告警程序：通过交易所公开的 WebSocket
行情推送实时接收成交价，按用户配置的阈值与涨跌幅规则判断是否值得通知，并把重复的行情噪声
过滤掉，只在真正有意义时推送一条干净的消息。

目标用户是持有多种加密资产的个人用户、需要观察行情波动的开发者、以及想学习 WebSocket 长连接
与告警去重设计的 Python 学习者。做成之后，可以配置“BTC 跌破 60000 提醒我”“ETH 一小时内
涨幅超过 5% 提醒我”“SOL 价格高于 180 且 30 分钟内不重复提醒”，程序会按规则准确推送。

合规与安全说明：只订阅交易所公开的行情推送接口，不接入任何交易、下单、转账接口，本项目不涉及
资金操作；使用前阅读并遵守交易所 API 服务条款与频率限制（如订阅上限、连接数上限），出现限频
错误必须按官方要求的退避时间重连，禁止用多连接绕过限制；不采集、不存储、不转发任何他人的
个人信息与账号凭据。抓取到的行情数据仅用于个人学习研究与自用提醒，不得用于转售、不得对外提供
行情服务、不得作为投资建议传播。所有密钥类配置（webhook token、邮箱密码）必须来自环境变量
或本地未提交的 config.ini，代码中禁止硬编码。

【二、功能需求清单】

1. 核心功能
   1.1 多币种订阅：支持一次订阅多个交易对（如 BTCUSDT、ETHUSDT、SOLUSDT），
       每个交易对可单独配置是否启用；订阅字符串按交易所要求拼接并在日志中打印实际订阅列表。
   1.2 行情接收：通过 WebSocket 接收逐笔成交或最新价推送，解析出 symbol、price、timestamp，
       维护内存中的最新价快照（dict），不落库高频明细。
   1.3 价格阈值告警：规则类型 price_above（价格高于等于阈值）与 price_below（价格低于等于阈值），
       支持为每个交易对配置多个阈值规则。
   1.4 涨跌幅告警：规则类型 change_up / change_down，参数为 window_minutes（默认 60）与
       percent（默认 5.0）；用滑动窗口计算窗口内首个价格与当前价的涨跌幅，超过阈值触发告警。
   1.5 去重与静默期：同一交易对同一规则在静默期内（默认 30 分钟）只告警一次；价格在阈值附近
       反复穿越时，必须等价格回到阈值的另一端并稳定超过 1 分钟，才允许再次触发（滞回带）。
   1.6 告警渠道：webhook（POST JSON）、邮件（SMTP）、桌面通知（Windows 用标准库
       ctypes 调用 MessageBox 或 PowerShell 提示，失败不影响其他渠道），可在配置中多选。
   1.7 断线重连：连接断开后按 1、2、4、8、16、30 秒指数退避重连，最多 30 秒封顶；
       连续 10 次重连失败则退出并写入错误日志，避免无效空转。
   1.8 运行统计：每 5 分钟打印一次心跳日志，包含已运行时长、收到的消息条数、最近价快照数量、
       已告警次数、重连次数。
   1.9 规则校验命令：启动前用 check 子命令校验规则文件，指出阈值方向矛盾（如同时要求
       高于 100 且低于 90）与重复规则。
2. 输入与交互
   2.1 配置文件 rules.json 定义交易对与规则；启动时读取并做 schema 校验，字段缺失或类型错误
       直接报错退出，退出码 2。
   2.2 命令行：--config 配置路径（默认 rules.json）；--channels webhook,email,desktop；
       --log-level；--dry-run 只打印将要发送的告警，不真实发送。
   2.3 支持 --test-notify 参数，向所有启用渠道发送一条测试消息，用于验证配置是否正确。
   2.4 运行中支持 Ctrl+C 优雅退出：先关闭 WebSocket，再打印本次运行统计后退出，退出码 0。
3. 输出与展示
   3.1 logs/alert.log：每次告警的时间、交易对、规则类型、触发价、阈值、渠道与发送结果。
   3.2 控制台实时打印接收到的首次价格与告警事件，价格保留 8 位小数并按交易对精度截断。
   3.3 启动时打印行情订阅地址（隐藏任何查询参数中的密钥）、订阅交易对数量与规则数量。
4. 异常与边界处理
   4.1 WebSocket 收到非 JSON 或缺少 price 字段的消息时丢弃并计入 parse_error 计数，不崩溃。
   4.2 行情长时间无更新（超过 120 秒没有该交易对消息）时打印警告，并在恢复后记录中断时长。
   4.3 涨跌幅窗口内样本不足 2 个价格点时，不触发涨跌幅告警，避免刚启动就误报。
   4.4 价格跳变超过 30%（疑似错误数据或极端行情）时，先记录警告，同一规则的连续两次触发
       需间隔 60 秒以上，防止异常数据刷屏告警。
   4.5 webhook 返回非 2xx 时重试 2 次（2 秒、6 秒），仍失败记入日志且不阻塞行情接收。
   4.6 规则中引用了未订阅的交易对时，校验阶段即报错，不进入运行态。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用 asyncio 与类型注解。
2. 允许使用的库：websockets、requests；其余使用标准库（asyncio、json、sqlite3、smtplib、
   email.message、logging、argparse、datetime、collections.deque、os、pathlib、ctypes、signal）。
3. 禁止事项：禁止接入任何交易撮合、下单、提现接口；禁止多连接并发绕过交易所限制；
   禁止硬编码 API Key 或 webhook token；禁止把行情数据转发到第三方平台；
   禁止在告警文案中给出“建议买入”“必涨”等投资建议性表述。
4. 代码组织：config.py（配置加载与校验）、models.py（Rule、Ticker、AlertEvent）、
   feed.py（WebSocket 连接与重连）、rules.py（阈值与涨跌幅判定、静默期与滞回带）、
   notifier.py（三种渠道）、state.py（内存快照与滑动窗口）、app.py（主循环）、cli.py。
5. 编码规范：所有协程函数写 docstring 并说明异常传播方式；时间统一使用带时区的 datetime
   （timezone.utc）；不得在事件循环中执行阻塞 IO，邮件发送与 requests 调用放入
   asyncio.to_thread 执行；日志中禁止输出密钥内容。
6. 测试要求：rules.py 的阈值判断、涨跌幅计算、静默期与滞回带逻辑必须有 pytest 用例，
   覆盖“连续穿越阈值只告警一次”“窗口样本不足不告警”“静默期结束后可再次告警”三种场景；
   测试使用伪造时间函数，不依赖真实 sleep。

【四、设计要点】

1. 数据结构
   1.1 Rule：rule_id(str)、symbol(str)、kind(str，取值 price_above/price_below/change_up/change_down)、
       threshold(float)、window_minutes(int|None)、percent(float|None)、quiet_minutes(int)、
       channels(list[str])、enabled(bool)、last_fired_at(datetime|None)、armed(bool)。
   1.2 Ticker：symbol(str)、price(float)、ts(datetime)、source(str)。
   1.3 AlertEvent：event_id(str)、symbol(str)、kind(str)、price(float)、threshold(float)、
       message(str)、channels(list[str])、created_at(datetime)、results(dict[str, bool])。
   1.4 内存状态：latest = dict[str, Ticker]；windows = dict[str, deque[tuple[datetime, float]]]，
       deque 设置 maxlen 以限制内存；alert_state = dict[str, dict]，按 rule_id 记录最近触发时间与 armed 状态。
2. 关键算法或流程
   2.1 主流程：加载与校验配置 → 建立 WebSocket 连接（异步）→ 循环接收消息 → 解析价格 →
       更新快照与滑动窗口 → 遍历该交易对的所有启用规则 → 判定 → 去重检查 → 发送告警 → 记录日志。
   2.2 涨跌幅计算：从窗口左侧弹出早于 now - window_minutes 的样本，取窗口内最早价格 base，
       涨跌幅 = (current - base) / base * 100；base 为 0 或窗口样本数小于 2 时直接返回 None。
   2.3 静默期判定：last_fired_at 为空则通过；否则要求 now - last_fired_at >= quiet_minutes * 60 秒。
   2.4 滞回带判定：price_above 类规则触发后把 armed 置为 False，只有当价格回落到
       threshold * (1 - hysteresis_ratio)（默认 0.5%）以下并保持 60 秒，才把 armed 重新置为 True。
   2.5 重连退避：delay = min(pow(2, attempt), 30) 秒；连接成功后 attempt 归零；
       attempt 达到 10 时抛出异常结束主循环。
3. 接口或命令设计
   3.1 命令行：
       python main.py --config rules.json --channels webhook,desktop --log-level INFO
       python main.py check --config rules.json
       python main.py --test-notify --channels email
   3.2 关键函数签名：
       async def connect_and_consume(symbols: list[str], on_ticker: Callable[[Ticker], None]) -> None
       def evaluate(rule: Rule, ticker: Ticker, window: deque, now: datetime) -> AlertEvent | None
       def change_percent(window: deque, current: float, window_minutes: int, now: datetime) -> float | None
       def notify(event: AlertEvent, channels: list[str], config: AppConfig) -> dict[str, bool]
   3.3 webhook 载荷：
       {"event_id": "a1b2c3", "symbol": "BTCUSDT", "kind": "price_below", "price": 59880.5,
        "threshold": 60000.0, "message": "BTCUSDT 现价 59880.5，已跌破 60000.0", "ts": "2024-05-20T03:12:00Z"}
   3.4 rules.json 片段：
       {"symbols": ["BTCUSDT", "ETHUSDT"],
        "rules": [{"rule_id": "btc_low", "symbol": "BTCUSDT", "kind": "price_below",
                   "threshold": 60000, "quiet_minutes": 30, "channels": ["webhook", "desktop"]},
                  {"rule_id": "eth_pump", "symbol": "ETHUSDT", "kind": "change_up",
                   "percent": 5.0, "window_minutes": 60, "quiet_minutes": 60, "channels": ["email"]}]}

【五、运行方式与示例】

安装依赖：
   pip install websockets requests

运行示例一（校验配置）：
   python main.py check --config rules.json
   输出：
   [INFO] 配置校验通过：2 个交易对，2 条规则
   [INFO] 规则 btc_low：BTCUSDT 跌破 60000.0，静默 30 分钟，渠道 webhook,desktop

运行示例二（正式运行）：
   python main.py --config rules.json --channels webhook,desktop
   输出：
   [INFO] 订阅地址 wss://example-stream.test/ws/combined（参数已省略）
   [INFO] 已连接，订阅 2 个交易对
   [INFO] BTCUSDT 首笔价格 61230.40000000
   [INFO] 告警触发：BTCUSDT 现价 59880.50000000 已跌破 60000.0，渠道 webhook 成功、desktop 成功
   [INFO] 心跳：已运行 5m00s，消息 18234 条，快照 2，告警 1，重连 0 次

运行示例三（渠道自测）：
   python main.py --test-notify --channels email,webhook
   输出：[INFO] 测试消息发送结果：email 成功，webhook 成功

异常示例：
   python main.py --config bad_rules.json
   输出：
   [ERROR] 配置校验失败：规则 eth_pump 的 kind=change_up 缺少 percent 字段（第 4 条规则）
   [ERROR] 未进入运行态（退出码 2）

【六、验收标准】

[ ] check 子命令能识别缺少必填字段的规则并给出规则 ID 与原因
[ ] 同时配置“高于 100”和“低于 90”的矛盾规则时能给出警告或错误
[ ] 启动日志打印的订阅交易对数量与 rules.json 中一致
[ ] 收到缺少 price 字段的畸形消息时程序不崩溃且 parse_error 计数增加
[ ] price_below 规则在价格跌破阈值时触发一次告警
[ ] 价格在阈值上下反复穿越时，静默期内只告警一次，且 60 秒滞回逻辑生效
[ ] 静默期结束且条件重新满足时可再次告警
[ ] 涨跌幅窗口内只有一个价格样本时不触发 change_up 告警
[ ] change_up 在 60 分钟窗口涨幅达到 5% 时触发，且计算值与手工核对一致
[ ] webhook 非 2xx 时按 2 秒、6 秒重试两次，失败后写入 alert.log 且不阻塞后续行情
[ ] --dry-run 模式不发送任何真实请求，仅在控制台打印将要发送的内容
[ ] --test-notify 能向所有启用渠道发送测试消息
[ ] 断开网络后程序按指数退避重连，恢复后继续正常告警
[ ] Ctrl+C 能优雅退出并打印本次运行统计，退出码为 0
[ ] 代码与日志中均不出现任何密钥明文，且不存在交易/下单相关接口调用

【七、可选扩展】

1. 增加更多技术型规则：N 分钟成交量放大倍数、连续 N 根 K 线同向、距 24 小时最高价回撤百分比。
2. 增加告警分级：普通提醒、重要提醒，分别对应不同渠道（例如重要告警才发短信/webhook）。
3. 增加本地 SQLite 记录告警历史，并提供 report 子命令输出每个币种本月触发次数统计。
4. 增加多交易所价格对比，当同一币种在两个来源价差超过设定百分比时提示可能是数据异常。

【八、涉及知识点】

- asyncio 事件循环、协程调度与异步任务取消
- websockets 客户端连接、消息循环与心跳（ping/pong）机制
- 指数退避重连策略与失败上限
- 滑动窗口（collections.deque）实现时间区间统计
- 告警去重：静默期 + 滞回带（hysteresis）双机制
- JSON 配置的 schema 校验与错误定位
- 非阻塞编程：异步环境中处理阻塞 IO（asyncio.to_thread）
- smtplib 邮件、webhook POST、Windows 桌面通知三种渠道的封装与降级
- 结构化日志与运行统计心跳设计
- 第三方行情接口的服务条款与限频合规要求
================================================================================
