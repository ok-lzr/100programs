================================================================================
项目编号：028                    难度等级：★★☆☆☆（小型项目）
项目名称：汇率转换命令行工具
所属分类：网络与在线服务 / 金融小工具
建议工时：3 ~ 5 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】
做跨境购物结算、给海外同事分摊费用、看海外订阅的月账单时，往往要临时查一次汇率，
而搜索结果里的汇率没有说明数据时间与来源，也不知道是买入价还是中间价。本项目做一
个命令行汇率工具，一次拉取多币种汇率并缓存到本地，支持任意两种货币互转、批量换算
与历史记录查询。

目标用户是有小额跨境结算需求的开发者、留学生和自由职业者。做出来之后，你可以
一条命令把 199 USD 换成 CNY，也可以把一份含多行金额的账单文件整体换算成另一种
货币，事后还能从本地历史记录里翻出上周换算时用的汇率是多少。

数据来源使用公开的免密钥汇率接口（示例：https://open.er-api.com/v6/latest/USD 与
https://api.frankfurter.app/latest）。使用前必须阅读其使用条款：仅用于个人学习与
非商业用途，禁止高频轮询，禁止二次分发数据。汇率仅供参考，不构成任何投资或交易
建议，这一点必须在程序输出中明确声明。

【二、功能需求清单】
1. 核心功能
   1.1 汇率拉取：以指定基准货币（默认 USD）调用接口获取全量汇率表，返回形如
       {"base": "USD", "date": "2024-05-12", "rates": {"CNY": 7.2345, ...}} 的
       结构；同时记录数据时间（接口提供或本地获取时间）。
   1.2 货币换算：convert --amount 100 --from USD --to CNY，输出换算结果、使用的
       汇率、汇率方向说明（1 USD = 7.2345 CNY）与数据日期。
   1.3 交叉换算：当基准货币不是源货币时，用 rates[to] / rates[from] 计算交叉汇率，
       并在输出中说明这是通过基准货币间接计算的。
   1.4 批量换算：--input FILE 读取每行一个金额的文本文件（允许前后空白与逗号分隔
       符），逐个换算后输出对齐的表格；--output FILE 写出结果 CSV。
   1.5 多目标换算：--to 可接受逗号分隔的多个货币，一次输出同一金额在多种货币下的
       结果。
   1.6 离线缓存：换算优先读缓存（默认有效期 12 小时，--cache-ttl 可调），缓存按
       基准货币分别存为 ~/.currencycli/rates_<BASE>.json；无网络但有缓存时正常
       换算并标注「离线缓存，数据日期 2024-05-10」。
   1.7 历史记录：每次成功换算追加一行到 ~/.currencycli/history.jsonl，字段包括
       时间、金额、源货币、目标货币、汇率、结果、数据日期与是否来自缓存；提供
       history 子命令按时间倒序列出，支持 --limit 与 --since 过滤。
   1.8 强制刷新：refresh 子命令忽略缓存重新拉取，并打印前后两次汇率的差异（涨跌
       百分比）。

2. 输入与交互
   2.1 子命令共 4 个：convert、rates（列出某基准下的全部汇率或筛选部分货币）、
       history、refresh。
   2.2 命令形式：
       python currency.py convert --amount 199 --from USD --to CNY
       python currency.py rates --base CNY --symbols USD,EUR,JPY --top 10
       python currency.py history --limit 20 --since 2024-05-01
       python currency.py refresh --base USD
   2.3 货币代码大小写不敏感，统一转为大写后校验；必须是三位字母且在内置的
       CURRENCY_NAMES 表中存在（表覆盖约 40 种常用货币及其中文名）。
   2.4 --amount 支持负数与小数，负数表示反向金额，输出中保留原始符号。
   2.5 网络超时 --timeout 默认 8 秒，范围 3 ~ 30。

3. 输出与展示
   3.1 convert 输出格式：
       199.00 USD = 1439.67 CNY
       汇率：1 USD = 7.2345 CNY（数据日期 2024-05-12，来源 open.er-api.com）
       反向：1 CNY = 0.13823 USD
   3.2 批量换算输出表格列：序号（右对齐 4）、原金额（右对齐 14）、源货币、结果
       （右对齐 14）、目标货币、汇率。
   3.3 rates 子命令默认按货币代码字母升序输出「代码 中文名 汇率」，--top N 改为按
       汇率数值降序取前 N 条。
   3.4 history 输出每行：时间、金额、源→目标、汇率、结果、来源标记（在线/缓存）。
   3.5 金额展示统一保留 2 位小数，汇率保留 4 ~ 6 位有效数字（小于 0.01 时用 6 位
       小数），并在末尾固定打印一行「汇率仅供参考，不构成交易建议」。
   3.6 --json 输出结构化结果，包含 amount、from、to、rate、result、rate_date、
       source、cached 字段。

4. 异常与边界处理
   4.1 货币代码非法或不在支持列表中时报错并给出最接近的候选（用字符串相似度给出
       1 条建议），退出码 2。
   4.2 目标货币与源货币相同时直接返回原金额，汇率记为 1.0，不发起网络请求。
   4.3 --amount 为非数字时报错退出码 2；金额绝对值超过 1e15 时报错提示超出可精确
       表示范围。
   4.4 接口不可达时按 1 秒、2 秒、4 秒退避重试 2 次，全部失败后使用缓存（即使过期）
       并标注；无缓存则退出码 4。
   4.5 接口返回结构中缺少目标货币时提示「该接口不支持货币 XXX」，退出码 5，并列出
       当前接口支持的货币数量。
   4.6 缓存文件损坏时删除并视为未命中；缓存目录不可写时降级为纯内存模式并打印一次
       警告，不影响本次换算。
   4.7 history.jsonl 中某行损坏时跳过该行并计数，最后提示跳过了 N 行坏记录。
   4.8 浮点精度：换算结果用 decimal.Decimal 计算，保留 2 位小数并采用
       ROUND_HALF_UP，避免 0.1+0.2 类误差导致的显示异常。

【三、技术要求与约束】
1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库 urllib.request、json、decimal、argparse、datetime、
   pathlib、hashlib、logging、csv、difflib（用于货币代码纠错建议）。禁止引入
   forex-python、requests 等第三方库。
3. 网络与并发：换算为轻量交互操作，采用串行请求；batch 模式下若需为多个基准货币
   拉取汇率，使用 ThreadPoolExecutor（最多 3 个 worker），但同一基准货币只请求一次。
4. 超时与重试：所有请求必须设置超时（默认 8 秒）；失败重试采用 1/2/4 秒指数退避，
   最多 2 次；HTTP 4xx 不重试；同一接口连续失败 3 次后本次运行不再请求该接口。
5. 限速要求：两次外部请求间隔不少于 1 秒；单次运行的外部请求总数不超过 10 次；
   缓存有效期默认 12 小时，禁止实现分钟级自动刷新；refresh 子命令也受同一限速约束，
   且提示用户不要频繁执行。
6. 合规要求：遵守所选汇率接口的使用条款与 robots.txt；仅在必要时请求，禁止批量
   拉取历史时间序列；禁止把拉取到的汇率数据打包分发或用于商业产品；输出中必须
   声明数据仅供参考。
7. 禁止事项：禁止硬编码任何 API Key；若切换到需要密钥的接口，密钥必须从环境变量
   EXCHANGE_API_KEY 读取；禁止记录或输出用户的任何支付信息；禁止在 history 中保存
   除金额与货币对之外的敏感信息。
8. 代码组织：providers.py（各汇率接口的统一适配器与 ProviderResult）、cache.py
   （缓存读写与 TTL）、convert.py（交叉汇率与 Decimal 换算）、history.py（JSONL
   追加与查询）、render.py（表格与 JSON 渲染）、cli.py（子命令分发）。
9. 编码规范：类型注解与 docstring 全覆盖；金额与汇率一律使用 Decimal 而非 float；
   网络层不直接打印，返回结构化结果；日志写 stderr；时间为带时区的 ISO 8601。

【四、设计要点】
1. 数据结构：
   RateTable = {base: str, date: str, rates: dict[str, Decimal], source: str,
                fetched_at: str, cached: bool}
   ConversionResult = {amount: Decimal, src: str, dst: str, rate: Decimal,
                       result: Decimal, rate_date: str, source: str, cached: bool,
                       cross: bool}
   HistoryRecord = {ts, amount, src, dst, rate, result, rate_date, cached}
   CURRENCY_NAMES: dict[str, str]（代码到中文名），ALIASES: dict[str, str]
   （如 "人民币"→CNY、"美元"→USD、"日元"→JPY、"RMB"→CNY）。
2. 关键算法或流程：
   2.1 convert 流程：规范化货币代码（大写 + 别名映射 + 校验）→ 相同货币直接返回 →
       读取缓存判断是否在 TTL 内 → 需要时请求接口 → 构造 RateTable → 计算汇率
       （源为基准时 rate = rates[dst]；目标为基准时 rate = 1/rates[src]；否则
       cross = rates[dst]/rates[src]）→ Decimal 量化到 2 位小数 → 追加历史 → 渲染。
   2.2 Decimal 使用规范：所有汇率与金额用 Decimal(str(x)) 构造（禁止 Decimal(float)）；
       除法用 getcontext().prec = 28；最终结果用 quantize(Decimal("0.01"),
       rounding=ROUND_HALF_UP)。
   2.3 缓存键与文件：文件名为 rates_<BASE>.json，内容为 RateTable 的序列化（Decimal
       转为字符串存储）；读取时把字符串转回 Decimal；fetched_at 与实际当前时间比较
       得到剩余有效期。
   2.4 货币代码纠错：用 difflib.get_close_matches(code, 支持列表, n=1, cutoff=0.6)，
       命中则提示「是否想输入 XXX？」。
   2.5 涨跌计算：refresh 时比较新旧汇率，变动百分比 = (new - old) / old * 100，保留
       2 位小数并标注 ↑ 或 ↓（纯文本用 上涨/下跌 文字）。
3. 接口或命令设计（外部 API 与内部命令）：
   GET https://open.er-api.com/v6/latest/<BASE>      返回 result、time_last_update_utc、rates
   GET https://api.frankfurter.app/latest?from=<BASE>&to=<LIST>  作为备用接口
   python currency.py convert --amount 199 --from USD --to CNY,JPY,EUR --json
   python currency.py convert --input bill.txt --from USD --to CNY --output bill_cny.csv
   python currency.py rates --base CNY --symbols USD,EUR --top 5
   python currency.py history --limit 10 --since 2024-05-01
   python currency.py refresh --base USD
   关键函数签名：
   def normalize_currency(code: str) -> str
   def load_rates(base: str, ttl_hours: float, force: bool) -> RateTable
   def convert(amount: Decimal, src: str, dst: str, table: RateTable) -> ConversionResult
   def append_history(rec: HistoryRecord) -> None

【五、运行方式与示例】
安装与运行（无需第三方依赖，无需 API Key）：
   python currency.py convert --amount 199 --from USD --to CNY
   python currency.py rates --base CNY --symbols USD,EUR,JPY
示例一（单次换算）：
   199.00 USD = 1439.67 CNY
   汇率：1 USD = 7.2345 CNY（数据日期 2024-05-12，来源 open.er-api.com）
   反向：1 CNY = 0.13823 USD
   汇率仅供参考，不构成交易建议
   退出码：0
示例二（多目标与批量文件）：
   python currency.py convert --amount 100 --from CNY --to USD,EUR,JPY
   100.00 CNY = 13.82 USD（1 CNY = 0.13823 USD）
   100.00 CNY = 12.74 EUR（1 CNY = 0.12741 EUR，经 USD 交叉计算）
   100.00 CNY = 2163.50 JPY（1 CNY = 21.63500 JPY，经 USD 交叉计算）
   bill.txt 内容为 12.5 / 199 / 45.9 三行，执行：
   python currency.py convert --input bill.txt --from USD --to CNY --output out.csv
      1        12.50 USD       90.43 CNY  7.2345
      2       199.00 USD     1439.67 CNY  7.2345
      3        45.90 USD      332.06 CNY  7.2345
示例三（异常输入与离线场景）：
   python currency.py convert --amount 10 --from USDD --to CNY
   输出：错误：不支持的货币代码 USDD，是否想输入 USD？
   退出码：2
   python currency.py convert --amount 199 --from USD --to CNY（断网且有 3 天前缓存）
   输出：
   199.00 USD = 1429.31 CNY
   汇率：1 USD = 7.1824 CNY（离线缓存，数据日期 2024-05-09）
   退出码：0
   python currency.py convert --amount 199 --from USD --to CNY（断网且无缓存）
   输出：错误：无法获取汇率（网络不可达），本地无可用缓存
   退出码：4

【六、验收标准】
[ ] convert --amount 199 --from USD --to CNY 输出结果、汇率、数据日期与来源行。
[ ] 源货币与目标货币相同时返回原金额且不发起网络请求（可用日志验证）。
[ ] 从 CNY 换 USD 时展示的是经基准货币交叉计算的说明。
[ ] --to 传三个货币时输出三行结果，各自汇率正确。
[ ] --input 读取含空行与多余空格的金额文件，跳过空行并正确换算。
[ ] --output 生成的 CSV 可被 csv 模块解析，列与设计一致。
[ ] 货币代码小写输入（如 usd）被正确识别为大写。
[ ] 非法代码 USDD 报错并给出 USD 建议，退出码 2。
[ ] --amount abc 报错退出码 2；--amount 1e20 提示超出范围。
[ ] 12 小时内重复换算命中缓存；--cache-ttl 0 时强制刷新。
[ ] 断网且有缓存时使用缓存并标注数据日期，退出码 0。
[ ] 断网且无缓存时报错退出码 4。
[ ] history 追加的记录条数与换算次数一致，--since 过滤有效。
[ ] 手工写坏 history.jsonl 的一行后，history 跳过坏行并提示跳过数量。
[ ] refresh 打印新旧汇率与变动百分比。
[ ] 金额计算使用 Decimal，0.1 + 0.2 类场景结果精确（无 0.30000000000000004）。
[ ] 单次运行的请求间隔不小于 1 秒，总请求数不超过 10 次。
[ ] 输出末尾包含「汇率仅供参考」声明；源码中无硬编码密钥。

【七、可选扩展】
1. 增加历史汇率折线（仅文本 ASCII 图），通过公开的历史时间序列接口展示近 30 天走势
   （需注意接口额度与使用条款，默认关闭）。
2. 增加 --round-to 参数控制结果小数位，支持金融场景下的 4 位小数展示。
3. 增加本地自定义汇率表 rates_manual.json，允许用户用固定汇率覆盖在线汇率（如公司
   内部结算汇率），并在输出中标注「手工汇率」。
4. 增加月度汇总子命令，把 history.jsonl 按月份聚合，输出每月换算次数与主要货币对。

【八、涉及知识点】
- urllib.request 调用 REST 接口并解析 JSON
- decimal.Decimal 做精确金额计算与舍入控制
- 本地缓存的键设计、TTL 判定与损坏恢复
- JSONL 追加写入与逐行容错解析
- difflib 做输入纠错建议
- 指数退避重试与错误分类
- argparse 子命令与参数范围校验
- 汇率交叉计算与基准货币概念
- API 使用条款、限速与数据免责声明
================================================================================
