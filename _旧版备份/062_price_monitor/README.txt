================================================================================
项目编号：062                    难度等级：★★★★☆（中型项目）
项目名称：电商价格监控提醒器
所属分类：内容采集与自动化 / 定时任务与告警
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：requests、beautifulsoup4、APScheduler、matplotlib
================================================================================

【一、项目背景与目标】

网购时最难受的场景不是买贵了，而是刚下单第二天就降价。人工每天去盯十个商品页面显然不现实，
本项目就是把这个动作自动化：把想盯的商品加进监控清单，程序按计划定时抓取当前价格，落库形成
历史价格序列，一旦价格低于设定的心理价位就立刻通过邮件或 webhook 通知你。

目标用户是想买大件、蹲促销的普通用户，以及需要跟踪竞品定价的小卖家。做成之后可以查看任意
商品的完整价格曲线、历史最低价、30 天均价，并收到“已经降到 1899 元，低于你设的 1900 元阈值”
这类明确通知，而不是含糊的促销短信。

合规与边界：只抓取公开商品页面上可见的价格文本，不登录、不使用优惠券接口、不调用非公开 API、
不绕过任何访问限制；抓取前读取并遵守目标站点 robots.txt，若 robots.txt 禁止抓取商品页则本项目
在该站点上停止工作；每个商品默认抓取间隔不少于 30 分钟，单站点同时监控商品数不超过 50；
抓取到的价格与商品信息仅用于个人消费决策与学习研究，禁止转卖、禁止用于商业比价产品的数据源。

【二、功能需求清单】

1. 核心功能
   1.1 监控清单管理：新增、删除、启用/停用监控项，每项包含商品名称、商品 URL、目标价、货币、
       抓取选择器（CSS 选择器字符串）、静默期（分钟）、是否启用。
   1.2 定时抓价：基于 APScheduler 的 IntervalTrigger 按全局间隔（默认 30 分钟）执行一轮抓取，
       每个商品的实际间隔按其自身 interval_minutes 判断是否到期，未到期则跳过。
   1.3 价格解析：用配置的 CSS 选择器提取价格文本，去除货币符号与千分位逗号，支持
       “￥1,899.00”“$29.99”“1899 元” 三种写法，统一解析为 float 并保留两位小数。
   1.4 价格落库：每次成功抓取写入一条价格记录（商品 ID、价格、抓取时间、原始文本），
       相同商品同一分钟内重复抓取只保留最新一条。
   1.5 降价告警：当 当前价 <= 目标价 且 距离上次同商品告警时间超过静默期 时，发送一条告警；
       告警内容含商品名、当前价、目标价、历史最低价、降幅百分比、商品链接。
   1.6 告警渠道：支持 email（SMTP）与 webhook（POST JSON）两种，可在配置文件中同时启用；
       任一渠道失败不影响其他渠道。
   1.7 历史曲线：为每个商品绘制价格折线图（横轴日期、纵轴价格、目标价水平虚线），
       输出 PNG 到 output/charts/，文件名用商品 ID 与月份。
   1.8 统计摘要：输出每个商品的当前价、历史最低价、历史最高价、30 天均价、抓取成功次数与失败次数。
2. 输入与交互
   2.1 命令行子命令：add（新增监控项）、remove（删除）、list（列出）、enable/disable、
       run（常驻调度）、once（立即抓取一轮）、report（生成图表与摘要）、check（校验配置与选择器）。
   2.2 add 示例：python main.py add --name "某品牌耳机" --url https://example.com/item/123
       --target 899 --selector "span.price-now" --interval 60 --quiet 720
   2.3 run 模式支持 --once-now 先抓一轮再进入调度，避免刚启动要等一整个间隔。
   2.4 所有子命令默认读写同一个 monitor.db，可通过 --db 指定其他路径。
3. 输出与展示
   3.1 控制台每轮打印：本轮到期商品数、成功数、失败数、告警条数、耗时。
   3.2 output/summary.md：每个商品一行，包含当前价与历史最低价的差值。
   3.3 output/alerts.log：追加写入的告警流水，含触发时间、渠道、发送结果。
   3.4 图表中文字体需正确设置，避免出现方框乱码，-号需使用 ASCII 连字符。
4. 异常与边界处理
   4.1 网络超时（默认 10 秒）或非 200 响应时，记为失败并写入抓取日志，不写价格记录。
   4.2 选择器匹配不到元素时，记为“解析失败”，连续失败 5 次自动把该商品置为停用并在日志中
       给出“页面结构可能已变化，请更新选择器”的提示。
   4.3 解析出的价格与上一次价格相差超过 80% 时，视为可疑数据，暂不入库并输出警告，
       防止把“配件价格”误当成“商品价格”触发假告警。
   4.4 邮件发送失败最多重试 2 次（间隔 5 秒、15 秒），仍失败则记录到 alerts.log 并继续处理下一个商品。
   4.5 静默期内即使满足阈值也不重复告警，静默期结束后价格仍低于阈值可再次告警。
   4.6 数据库不存在时自动建表；监控清单为空时 run 模式打印提示并以 0 退出。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用类型注解与 dataclass。
2. 允许使用的库：requests、beautifulsoup4、APScheduler、matplotlib；其余使用标准库
   （sqlite3、smtplib、email.message、argparse、logging、json、time、datetime、pathlib、configparser）。
3. 禁止事项：禁止硬编码邮箱密码与 webhook 密钥；禁止多线程高频并发抓取；禁止伪造 User-Agent
   绕过站点封禁；禁止把抓取结果同步到任何云服务。
4. 代码组织：config.py（读取 config.ini 与阈值）、models.py（MonitorItem、PricePoint、AlertEvent）、
   db.py（建表与读写）、fetcher.py（带重试的抓取）、parser.py（价格解析）、notifier.py（邮件与 webhook）、
   scheduler.py（任务调度）、plotter.py（曲线绘制）、main.py（子命令入口）。
5. 编码规范：敏感配置从环境变量或本地 config.ini 读取，config.ini 不提交到公共仓库；
   所有函数写 docstring；抓取与通知必须使用 logging 分级输出；异常必须捕获具体类型而非裸 except。
6. 测试要求：价格解析、阈值判断（含静默期）、可疑价过滤三块逻辑要有 pytest 用例；
   测试通过 monkeypatch 替换网络与发信函数，不得真实发送邮件。

【四、设计要点】

1. 数据结构
   1.1 MonitorItem：item_id(int)、name(str)、url(str)、target_price(float)、currency(str)、
       selector(str)、interval_minutes(int)、quiet_minutes(int)、enabled(bool)、fail_count(int)、
       last_alert_at(str|None)、last_price(float|None)、created_at(str)。
   1.2 PricePoint：id(int)、item_id(int)、price(float)、raw_text(str)、fetched_at(str)。
   1.3 AlertEvent：id(int)、item_id(int)、price(float)、target_price(float)、channel(str)、
       message(str)、sent(bool)、error(str|None)、created_at(str)。
   1.4 表结构：monitor_items（主键 item_id，url 唯一）、price_history（主键 id，item_id 外键，
       对 (item_id, fetched_at) 建唯一索引）、alert_events（主键 id，对 (item_id, created_at) 建索引）、
       fetch_logs（记录失败原因与状态码）。
2. 关键算法或流程
   2.1 单轮流程：读出启用中的监控项 → 逐项判断是否到达 interval → 抓取 → 解析 → 可疑价格校验
       → 入库 → 读取历史最低价 → 阈值与静默期判断 → 发送告警 → 更新 item 状态。
   2.2 静默期判断：若 last_alert_at 为空则允许告警；否则 now - last_alert_at 必须大于等于
       quiet_minutes * 60 秒才允许再次告警。
   2.3 价格归一化：先用正则去掉非数字字符（保留小数点），再 float 转换；解析失败返回 None
       并记录原始文本，绝不返回 0 造成误告警。
   2.4 降幅计算：drop_percent = round((last_price - current_price) / last_price * 100, 2)，
       last_price 为空时按 0.0 处理并在消息中省略该字段。
3. 接口或命令设计
   3.1 命令行：
       python main.py run --db monitor.db --log-level INFO
       python main.py add --name "某品牌耳机" --url https://example.com/item/123 --target 899 --selector "span.price-now"
       python main.py once --item 3
       python main.py report --days 30
   3.2 关键函数签名：
       def fetch_price(url: str, selector: str, timeout: int = 10) -> float | None
       def parse_price_text(text: str) -> float | None
       def should_alert(item: MonitorItem, price: float, now: datetime) -> bool
       def send_email(subject: str, body: str, config: SmtpConfig) -> bool
       def send_webhook(url: str, payload: dict, timeout: int = 5) -> bool
   3.3 webhook 载荷固定格式：
       {"item_id": 3, "name": "某品牌耳机", "price": 879.0, "target_price": 899.0,
        "lowest": 850.0, "drop_percent": 4.2, "url": "https://example.com/item/123",
        "triggered_at": "2024-05-20T10:30:00"}

【五、运行方式与示例】

安装依赖：
   pip install requests beautifulsoup4 APScheduler matplotlib

首次配置：
   复制 config.example.ini 为 config.ini，填写 SMTP 服务器、端口、发件账号（密码从环境变量
   PRICE_MONITOR_SMTP_PWD 读取）与 webhook 地址；未填写的渠道自动跳过。

运行示例一（新增并立即抓取）：
   python main.py add --name "某品牌耳机" --url https://example.com/item/123 --target 899 --selector "span.price-now"
   python main.py once --item 1
   输出：
   [INFO] 商品 1 抓取成功：当前价 879.00，目标价 899.00，历史最低 850.00
   [INFO] 触发告警：879.00 <= 899.00，已发送 email 成功，webhook 成功
   [INFO] 本轮完成：到期 1，成功 1，失败 0，告警 1，耗时 2.4s

运行示例二（常驻监控）：
   python main.py run --once-now
   输出：
   [INFO] 调度器已启动，全局间隔 30 分钟，启用中的监控项 4 个
   [INFO] 商品 2 未到抓取时间（下次 10:52），跳过
   [INFO] 商品 3 抓取失败：选择器未匹配到元素，失败计数 1/5

运行示例三（生成报告）：
   python main.py report --days 30
   输出：已生成 output/summary.md 与 4 张价格曲线图（output/charts/）

异常示例：
   python main.py once --item 99
   输出：[ERROR] 未找到监控项 99，可用 ID：1, 2, 3, 4（退出码 3）

【六、验收标准】

[ ] add 新增的监控项在 list 中可见，且 url 重复时给出明确提示而不是静默覆盖
[ ] parse_price_text 对 “￥1,899.00” 返回 1899.0，对 “$29.99” 返回 29.99，对 “暂无报价” 返回 None
[ ] 每轮抓取只对到期的商品发起请求，日志可证明未到期商品被跳过
[ ] price_history 中同一商品同一分钟的重复记录被唯一索引拦截
[ ] 当前价低于目标价时确实发出告警，且 alerts.log 有对应记录
[ ] 静默期内的第二次满足条件不重复发送通知
[ ] 静默期结束且价格仍低于目标价时能再次告警
[ ] 价格解析失败时不会写入 0 元记录，也不会触发告警
[ ] 价格突变超过 80% 时被标记为可疑且不入库
[ ] 连续 5 次解析失败后该商品自动停用并在日志中给出更新选择器的提示
[ ] 邮件失败不影响 webhook 发送，反之亦然
[ ] 每张价格曲线图带有目标价水平虚线与中文标题，且中文不乱码
[ ] summary.md 中每个商品的当前价、历史最低、30 天均价计算正确（可手工核对一天数据）
[ ] 代码中不存在明文邮箱密码或 webhook 密钥

【七、可选扩展】

1. 增加浏览器渲染模式（可选依赖 playwright）以支持价格由 JavaScript 动态加载的商品页面，
   仍然保持低速抓取并遵守 robots.txt。
2. 增加“降价预测”功能：用最近 30 天价格做简单线性回归，估算未来一周的价格走势区间。
3. 增加促销日历支持：在指定大促日期前后自动缩短抓取间隔，提高捕获瞬时低价的概率。
4. 增加本地 Web 面板，展示所有商品卡片、当前价标签与一键暂停按钮。

【八、涉及知识点】

- requests 会话、超时设置与状态码判断
- BeautifulSoup CSS 选择器与页面结构变化容错
- APScheduler 定时任务、任务持久化与调度器生命周期
- SQLite 表设计与唯一索引保证幂等写入
- 时间区间判断、静默期（冷却时间）算法
- smtplib 与 email.message 构造带中文正文的邮件
- webhook JSON 推送与 requests.post 的重试策略
- 环境变量管理敏感配置
- matplotlib 折线图、水平参考线与中文字体配置
- 日志分级、异常捕获粒度与守护型程序的基本结构
================================================================================
