================================================================================
项目编号：063                    难度等级：★★★★☆（中型项目）
项目名称：股票行情分析器
所属分类：数据分析与可视化 / 金融行情
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：pandas、numpy、requests、matplotlib、openpyxl
================================================================================

【一、项目背景与目标】

很多人看盘时只会看一根 K 线，讲不出“这只股票现在是在多头还是空头”“是不是超买了”。
本项目不预测涨跌，只做一件事：把公开的历史行情数据整理成一份标准的技术分析报告，
用均线、RSI、MACD 三个最常用的指标把趋势与动能状态讲清楚，并画出可以直接贴进笔记的图。

目标用户是学习量化与数据分析的开发者、需要批量跟踪一篮子自选股的个人投资者。做成之后，
输入股票代码与时间区间，就能得到一份包含收盘价与均线图、MACD 图、RSI 图、指标当前值表与
文字结论的 report.md 和 report.xlsx，一次跑完整个自选股清单。

数据来源与合规说明：本项目支持三种数据源，分别是本地 CSV 文件（推荐用于离线练习）、
公开行情接口（如新浪财经公开行情端点，仅抓取单只股票的公开日线数据）、以及可选的第三方库
akshare。使用任何在线数据源前，都必须读取并遵守该数据源网站的 robots.txt 与服务条款，
请求间隔不低于每秒 1 次且串行执行，不并发、不绕过访问限制、不抓取付费或需登录的数据。
所有数据仅用于个人学习与研究，不得用于对外提供行情服务、不得转售、不得作为投资建议，
报告首页必须固定输出风险提示文字。

【二、功能需求清单】

1. 核心功能
   1.1 数据获取：按代码与日期区间获取日线数据，字段包含 date、open、high、low、close、volume；
       本地 CSV 优先，其次在线接口，最后可选 akshare；数据落地为 data/<code>.csv 缓存。
   1.2 数据校验与清洗：按日期升序排序；去重（同一天只保留最后一条）；剔除收盘价为空或
       小于等于 0 的行；用交易日自然顺序补齐索引（不插值，缺失日直接跳过）；输出清洗前后的行数。
   1.3 均线计算：支持 MA5、MA10、MA20、MA60 与 EMA12、EMA26；新增列命名规则为 ma5、ma20、ema12。
   1.4 RSI 计算：默认周期 14，使用 Wilder 平滑法（首次用简单平均，其后用递推平滑），
       输出列 rsi14；同时给出 70 以上超买、30 以下超卖的区间统计天数与占比。
   1.5 MACD 计算：DIF = EMA12 - EMA26，DEA = DIF 的 9 日 EMA，MACD 柱 = (DIF - DEA) * 2；
       输出列 dif、dea、macd_hist；识别金叉（DIF 上穿 DEA）与死叉（DIF 下穿 DEA）并列出最近 5 次日期。
   1.6 状态判定：按规则给出当前状态标签：收盘价在 MA20 上方且 MA5 大于 MA10 记为“短期偏强”；
       收盘价在 MA20 下方且 MA5 小于 MA10 记为“短期偏弱”；其余记为“震荡整理”。
   1.7 绘图：输出三张图，分别是 K 线收盘价 + MA5/MA20/MA60 折线图、MACD（DIF、DEA 线与柱状图）、
       RSI 曲线（含 30/70 参考线）；图片输出到 output/charts/，宽 12 英寸、高 6 英寸、DPI 150。
   1.8 报告输出：report.md 含数据概览、指标当前值表、金叉死叉记录、区间统计与结论文字；
       report.xlsx 含原始数据页、指标计算页、统计摘要页，表头加粗并冻结首行。
   1.9 批量模式：支持一次分析多只股票，输出对比表（区间涨跌幅、波动率、当前 RSI、最新状态）。
2. 输入与交互
   2.1 命令行：--symbol 单只或多只（逗号分隔或多次传入）；--start、--end 日期（YYYY-MM-DD）；
       --source csv|sina|akshare；--csv-dir 本地数据目录；--out 输出目录；--no-cache 忽略缓存重新获取。
   2.2 内置自选股文件 watchlist.txt，每行一个代码，支持注释行（以 # 开头）。
   2.3 未指定日期时默认取最近 250 个交易日。
3. 输出与展示
   3.1 控制台打印每只股票的数据行数、时间区间、最新收盘价与状态标签。
   3.2 每只股票在 output/<code>/ 下生成 report.md、report.xlsx 与 charts 目录。
   3.3 批量模式额外生成 output/compare.md 对比表，按区间涨跌幅降序排列。
4. 异常与边界处理
   4.1 代码不存在或接口返回空数据时，提示“未获取到 <code> 的行情数据”并跳过该股票，退出码仍为 0。
   4.2 有效数据不足（少于 60 行）时仍计算 MA5/MA20 与 RSI，但跳过 MACD 并明确说明原因。
   4.3 有效数据不足 15 行时直接报错退出，避免产生无意义的指标。
   4.4 在线接口请求失败重试 2 次，每次间隔 2 秒；全部失败时若有本地缓存则使用缓存并标注数据日期。
   4.5 日期区间非法（start 晚于 end）或格式错误时，参数校验阶段即报错，退出码 2。
   4.6 停牌日或涨跌幅超过 20% 的异常数据点保留原值，但在报告“数据说明”一节列出日期，不做删除。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：pandas、numpy、requests、matplotlib、openpyxl，可选 akshare；
   其余使用标准库（argparse、csv、dataclasses、datetime、logging、pathlib、json、re、time）。
3. 禁止事项：禁止实现任何自动下单、交易接口或资金操作；禁止把指标结果包装为“买卖建议”；
   禁止在报告中出现“保证盈利”“稳赚”等表述；禁止多线程并发抓取行情。
4. 代码组织：datasource.py（三种数据源统一为 DataFrame）、cleaner.py（清洗）、indicators.py
   （MA/EMA/RSI/MACD，全部为纯函数且不修改入参）、analyzer.py（状态判定与统计）、plotter.py、
   report.py（Markdown 与 Excel 输出）、cli.py（参数解析与流程编排）。
5. 编码规范：indicators.py 中每个函数必须写清公式来源与参数含义的 docstring；
   所有 DataFrame 操作避免链式赋值警告，必要时显式 copy()；绘图统一封装函数与样式；
   使用 logging 而非 print；类型注解完整。
6. 测试要求：用固定的 20 行手算数据做指标测试，断言 MA5、RSI14、MACD 与预期值误差小于 1e-6；
   另需一个测试用例覆盖“数据不足 15 行应当抛异常”的边界。

【四、设计要点】

1. 数据结构
   1.1 Bar（dataclass）：date(datetime.date)、open(float)、high(float)、low(float)、close(float)、
       volume(int)。
   1.2 IndicatorConfig：ma_windows(list[int]，默认 [5,10,20,60])、rsi_period(int，默认 14)、
       fast_ema(int，默认 12)、slow_ema(int，默认 26)、signal_ema(int，默认 9)。
   1.3 AnalysisResult：symbol(str)、name(str|None)、start(str)、end(str)、rows(int)、
       last_close(float)、ma5(float)、ma20(float)、rsi14(float)、dif(float)、dea(float)、
       macd_hist(float)、trend_label(str)、golden_cross_dates(list[str])、
       dead_cross_dates(list[str])、overbought_days(int)、oversold_days(int)、change_percent(float)。
2. 关键算法或流程
   2.1 主流程：解析参数 → 读取 watchlist → 逐只股票获取数据（先看缓存）→ 清洗 → 计算指标 →
       生成统计与结论 → 绘图 → 输出 Markdown 与 Excel → 汇总对比表。
   2.2 RSI 递推公式：up = max(close - prev_close, 0)，down = max(prev_close - close, 0)；
       首个 RSI 用前 rsi_period 个 up/down 的简单平均计算 RS；其后 avg_up = (前 avg_up * 13 + up) / 14，
       avg_down 同理；RSI = 100 - 100 / (1 + avg_up / avg_down)；avg_down 为 0 时 RSI = 100。
   2.3 EMA 递推公式：首值取前 N 个收盘价的简单平均，其后 ema = close * k + prev_ema * (1 - k)，
       其中 k = 2 / (N + 1)。
   2.4 金叉死叉识别：构造 sign = (dif - dea) 的符号序列，用 shift(1) 比较，
       sign 由负转正记为金叉、由正转负记为死叉，忽略首行与相等值。
   2.5 波动率口径：区间年化波动率 = 日收益率标准差 * sqrt(250)，在报告中注明口径与样本天数。
3. 接口或命令设计
   3.1 命令行：
       python main.py --symbol 600519 --start 2024-01-01 --end 2024-06-30 --source csv --csv-dir ./data
       python main.py --symbol 600519,000001 --from-watchlist --out ./output
   3.2 关键函数签名：
       def load_bars(symbol: str, start: date, end: date, source: str) -> pandas.DataFrame
       def clean_bars(frame: pandas.DataFrame) -> tuple[pandas.DataFrame, dict]
       def add_ma(frame: pandas.DataFrame, windows: list[int]) -> pandas.DataFrame
       def add_rsi(frame: pandas.DataFrame, period: int = 14) -> pandas.DataFrame
       def add_macd(frame: pandas.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pandas.DataFrame
       def judge_trend(row: pandas.Series) -> str
       def render_report(result: AnalysisResult, frame: pandas.DataFrame, out_dir: Path) -> Path

【五、运行方式与示例】

安装依赖：
   pip install pandas numpy requests matplotlib openpyxl

运行示例一（本地 CSV，推荐离线练习）：
   python main.py --symbol 600519 --start 2024-01-01 --end 2024-06-30 --source csv --csv-dir ./data
   输出：
   [INFO] 读取本地文件 data/600519.csv，共 180 行
   [INFO] 清洗完成：去重 2 行，剔除无效行 0 行，有效 178 行
   [INFO] 最新收盘 1685.00  MA5 1672.40  MA20 1650.10  RSI14 58.3  状态：短期偏强
   [INFO] 报告已生成：output/600519/report.md、output/600519/report.xlsx

运行示例二（批量自选股对比）：
   python main.py --from-watchlist --start 2024-01-01 --end 2024-06-30 --source csv
   输出：
   [INFO] 自选股共 5 只，成功分析 5 只，跳过 0 只
   输出：output/compare.md 已生成，按区间涨跌幅降序排列（首行：000001 +18.42%）

运行示例三（在线数据源）：
   python main.py --symbol 600519 --source sina --start 2024-06-01
   输出：
   [INFO] 请求间隔 1.0s，串行抓取中
   [INFO] 获取 600519 共 20 行，已缓存到 data/600519.csv
   输出：报告正常生成，数据说明中标注“数据来源：公开行情接口，仅供参考”

异常示例：
   python main.py --symbol 999999 --source sina
   输出：
   [WARN] 未获取到 999999 的行情数据，已跳过
   [INFO] 批量汇总：成功 0 只，跳过 1 只（退出码 0）

【六、验收标准】

[ ] 本地 CSV 模式全程无网络请求即可完成报告生成
[ ] 清洗后数据按日期升序且无重复日期，日志打印清洗前后行数
[ ] MA5 的最后一行数值等于最近 5 个收盘价的算术平均（可用计算器核对）
[ ] RSI14 全列取值均在 0~100 之间，且无 NaN 出现在第 15 行之后
[ ] MACD 柱值等于 (dif - dea) * 2，误差小于 1e-6
[ ] 金叉死叉列表中的日期顺序正确且相邻两次符号相反
[ ] 三张图表均已生成，均线图包含 MA5/MA20/MA60 三条线且中文标题不乱码
[ ] report.md 固定包含风险提示与数据来源说明，且不含任何买卖建议措辞
[ ] report.xlsx 可被 Excel 打开，三个工作表名称与内容符合要求，首行已冻结
[ ] 数据不足 15 行时程序抛出明确异常并以非 0 退出码结束
[ ] 数据不足 60 行时跳过 MACD 并在报告中写明原因
[ ] 批量模式 compare.md 的排序与涨跌幅数值正确
[ ] 在线模式下请求间隔不小于 1 秒且有日志证明串行执行
[ ] pytest 指标测试全部通过，且测试过程中不访问网络

【七、可选扩展】

1. 增加布林带（BOLL）与 ATR 指标，并在报告中标注波动收敛与放大的区间。
2. 增加多股票归一化对比图（以区间首日为 100），直观展示相对强弱。
3. 增加简易回测：用 MA5 上穿 MA20 买入、下穿卖出的规则统计区间收益与最大回撤，
   报告中必须同时给出胜率与交易次数，避免只展示收益曲线造成误导。
4. 增加 Excel 图表页，用 openpyxl 的 LineChart 在 Excel 内嵌价格与指标图。

【八、涉及知识点】

- pandas 时间序列索引、排序去重、rolling 与 ewm 计算
- 递推型指标（RSI、EMA）的向量化实现与首值处理
- numpy 数值计算与浮点误差比较
- 技术指标的数学定义与边界情况（分母为 0、数据不足）
- matplotlib 多子图布局、双轴与中文乱码处理
- openpyxl 写入多工作表、样式与冻结窗格
- 命令行参数校验与批量任务的错误隔离
- 本地缓存策略与在线数据源的降级处理
- 类型注解、纯函数设计与单元测试意识
- 金融数据的合规边界与风险提示书写规范
================================================================================
