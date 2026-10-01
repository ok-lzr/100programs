================================================================================
项目编号：096                    难度等级：★★★★★（大型项目）
项目名称：量化交易回测平台
所属分类：数据分析 / 金融工程 / 策略研究工具
建议工时：3 ~ 4 周（约 110 ~ 170 小时）
运行环境：Python 3.10+    第三方依赖：FastAPI、uvicorn、pandas、numpy、SQLAlchemy、pydantic、matplotlib、APScheduler、pytest、httpx、openpyxl、pyarrow（可选）
================================================================================

【一、项目背景与目标】

做量化策略研究的人都会经历同一个循环：写一个想法 → 在历史数据上跑一遍 → 看到漂亮的
收益曲线 → 上线后亏钱。问题通常出在回测环节：用了未来数据（look-ahead bias）、忽略了
手续费与滑点、用不复权的价格算收益、把停牌与涨跌停当成可成交、样本内过拟合、把一段
恰好赚钱的区间当成规律。回测平台存在的价值不是“算出一条曲线”，而是用工程手段把这些
偏差变成可以被检测、被量化、被拒绝的机制。

本项目要实现一个完整的量化交易回测平台：行情数据的采集与清洗入库、策略编写与参数化、
事件驱动的逐 bar 撮合回测、手续费与滑点模型、持仓与资金账户核算、绩效指标计算、可视化
报告与多策略对比、参数网格搜索与过拟合提示。平台要支持至少 20 只标的、10 年日频数据、
1200 万根 bar 的规模，并保证回测结果可复现（相同数据 + 相同参数 + 相同随机种子 = 完全
相同的净值曲线）。

目标用户是：学习量化研究流程的开发者与在校学生、需要快速验证想法的个人研究者、以及
想理解“事件驱动回测引擎 vs 向量化回测”差异的工程师。项目定位为研究与教学工具，明确
声明：不构成任何投资建议、不接入真实券商下单接口、不做实盘交易、不承诺任何收益。所有
行情数据必须来自公开、合法、可自由使用的研究数据源，并在文档中标注数据来源与许可。

重点指标口径必须写清楚，避免自欺：收益率按逐日复利计算；年化收益使用 252 个交易日；
最大回撤按“净值相对历史最高点的最大跌幅”；夏普比率使用日收益均值除以标准差再乘
sqrt(252)，无风险利率默认 2% 且可配置；胜率按已平仓交易统计；换手率按成交金额除以
期初市值。所有指标的计算实现必须有单元测试与人工手算样例对照。

【二、功能需求清单】

本系统按四个子系统拆分：数据子系统（行情采集与存储）、回测引擎（策略与撮合）、分析与
可视化子系统、平台端（Web 界面与管理）。

1. 数据子系统
   1.1 数据源接入：支持 CSV 文件导入（用户自备数据）、公开研究数据源接口（按配置启用）、
       以及内置的本地样本数据集（随机游走生成，用于测试与演示，生成时固定随机种子）。
   1.2 数据表结构：统一为 (symbol, trade_date, open, high, low, close, volume, amount,
       adj_factor, is_suspended, limit_up, limit_down)；价格使用定点小数（存为分或保留
       4 位小数的整数）避免浮点误差累积。
   1.3 数据校验：导入时检查字段完整性、日期单调递增、high ≥ max(open, close)、
       low ≤ min(open, close)、volume ≥ 0、价格 > 0；异常行写入 rejected_rows 表并给出
       行号与原因，不静默丢弃。
   1.4 复权处理：支持前复权与后复权两种模式，按 adj_factor 计算；回测默认使用后复权价
       并明确提示“后复权不影响收益率计算，仅影响价格量级”。
   1.5 停牌与涨跌停标记：停牌日 is_suspended=1，撮合时禁止成交；涨停（close 达到涨停价
       且 limit_up=1）时禁止买入，跌停时禁止卖出（可配置为“允许按开盘价成交”的宽松模式）。
   1.6 交易日历：维护交易日历表（从数据中抽取所有出现过的交易日），回测按日历步进而非
       自然日；缺失交易日的标的按“持仓不变、无成交”处理。
   1.7 数据更新：支持增量导入（按 symbol + date 去重更新）；提供数据覆盖报告（每个标的的
       起止日期、bar 数量、缺失交易日数量）。
   1.8 数据缓存：常用标的的 DataFrame 缓存为 Parquet 或 pickle（带版本号），首次加载后
       后续回测直接读缓存，缓存失效条件为数据表 updated_at 变化。

2. 回测引擎子系统
   2.1 事件驱动循环：按交易日推进，每个 bar 触发顺序为 on_bar（策略计算信号）→ 订单生成
       → 撮合 → 更新持仓与账户 → 记录净值；禁止在同一 bar 内使用未来数据。
   2.2 成交价模型：可配置为“次日开盘价成交”（默认，避免同 bar 未来函数）或“当 bar 收盘价
       成交”（标记为激进模式并在报告中显示警告）；滑点模型支持固定比例（默认 0.05%）与
       固定跳数两种。
   2.3 手续费模型：A 股规则可配置——佣金万分之三且单笔最低 5 元、卖出印花税千分之一、
       过户费十万分之二；支持自定义费率表；每笔成交的手续费明细必须记录可查。
   2.4 资金与持仓：初始资金可配置（默认 100 万），支持现金、持仓市值、总资产、可用资金
       四个字段；T+1 规则（当日买入不可卖出）可开关；做空默认关闭（A 股融券复杂，本项目
       只做多）。
   2.5 下单接口：策略可通过 API 调用 buy(symbol, amount 或 percent)、sell、target_percent
       三种下单方式；订单类型支持市价（按撮合价成交）与限价（当日未触及则次日顺延或
       撤销，可配置）；下单数量按 100 股整手校验，不足一手拒绝并记录原因。
   2.6 部分成交与流动性约束：单 bar 成交量上限约束（默认不超过该 bar 成交量的 10%），
       超出部分按比例部分成交或拒单（可配置），避免“买下整个市场”的失真回测。
   2.7 持仓与组合：支持多标的组合、按权重调仓（rebalance）、等权/市值加权/自定义权重；
       调仓时先卖出再买入，卖出资金当日可用（可配置为 T+1 可用）。
   2.8 风控与约束：单标的最大仓位比例、最大持仓标的数、单日最大换手率、止损（固定比例）
       与止盈规则；触发风控时下单被拒绝并记录风控日志，回测报告中统计风控触发次数。
   2.9 基准与对比：支持配置基准指数（如沪深 300 的日收益序列），报告中给出策略净值、
       基准净值与超额收益曲线。
   2.10 可复现性：回测任务记录数据快照版本、策略代码版本、参数、随机种子与运行时间；
       相同配置重复运行的结果必须逐点一致（差异为 0）。
   2.11 策略加载：策略以独立 Python 文件实现，继承 BaseStrategy 并实现 on_bar 与可选
       on_init、on_finish；策略文件在受限命名空间中执行，禁止访问网络与文件系统（通过
       审计 hook 拦截 import socket、open 写模式等），加载失败给出明确错误行号。
   2.12 运行隔离：回测在子进程或线程池中执行，设置单任务超时（默认 10 分钟）与内存上限，
       超时任务标记为 failed 并保留日志。

3. 分析与可视化子系统
   3.1 绩效指标：总收益率、年化收益率、年化波动率、夏普比率、索提诺比率、卡玛比率、
       最大回撤与回撤区间、最长回撤天数、胜率、盈亏比、交易次数、平均持仓天数、换手率、
       Alpha/Beta（相对基准）。
   3.2 交易明细：每笔开平仓记录（标的、方向、价格、数量、手续费、盈亏、持仓天数），支持
       导出 CSV。
   3.3 净值与回撤图：净值曲线（策略与基准）、回撤曲线、日收益分布直方图，使用 matplotlib
       生成 PNG 或交互式 HTML（matplotlib 的 Agg 后端，保证无 GUI 环境可生成）。
   3.4 月度收益热力图：按年 × 月展示收益率，颜色映射盈亏；输出为 PNG 与数据表。
   3.5 持仓分析：持仓集中度、单标的贡献度、Top 10 盈利与亏损交易。
   3.6 参数敏感性：对指定参数做网格搜索后，输出参数-收益与参数-回撤的热力图，并标注
       最优参数与其邻域稳定性（邻域均值与最优值的差距，用于提示过拟合）。
   3.7 多策略对比：最多 5 个回测结果同图对比净值与指标表，支持导出对比报告。
   3.8 报告导出：生成完整的 HTML 报告（内嵌图表为 base64）与 Excel 报表（openpyxl：
       指标页、交易明细页、净值序列页），另存到 reports/{task_id}/ 目录。

4. 平台端子系统（Web 界面与管理）
   4.1 数据管理页：查看已有标的与数据覆盖情况、上传 CSV、触发数据校验报告、查看被拒绝行。
   4.2 策略管理页：上传/编辑策略文件（在线编辑器使用简单 textarea + 语法提示不做高亮）、
       查看策略列表与版本、策略说明文档编辑。
   4.3 回测任务页：选择策略、标的池、区间、初始资金、费率与滑点配置后提交回测；任务列表
       展示状态（排队/运行中/成功/失败）、耗时与创建人。
   4.4 结果页：指标卡片、净值图、回撤图、月度热力图、交易明细表（分页）、参数对比入口、
       报告下载按钮。
   4.5 网格搜索页：配置参数网格（JSON 形式，如 {"fast": [5,10,20], "slow": [30,60]}）提交
       批量任务，展示进度与结果排序；超过 200 个组合时提示预计耗时并要求确认。
   4.6 系统状态：任务队列长度、平均回测耗时、数据表大小、最近错误日志摘要。
   4.7 审计与权限：默认单用户；开启多用户时为每个用户隔离策略与回测结果，操作写入
       audit_log。

5. 模块清单（源码结构）
   5.1 app/main.py               FastAPI 应用与生命周期。
   5.2 app/config.py             配置（数据目录、缓存目录、报告目录、并发数、超时）。
   5.3 data/loader.py            CSV 与接口数据导入、字段映射与校验。
   5.4 data/store.py             数据库读写、交易日历、数据覆盖报告、缓存管理。
   5.5 data/adjust.py            复权因子计算与前/后复权价格生成。
   5.6 engine/events.py          事件定义（BarEvent、OrderEvent、FillEvent、SignalEvent）。
   5.7 engine/broker.py          撮合逻辑、滑点与手续费、流动性与整手约束。
   5.8 engine/account.py         资金、持仓、盈亏核算、T+1 与可用资金管理。
   5.9 engine/portfolio.py       组合调仓、权重计算与风控约束。
   5.10 engine/backtest.py       主循环、上下文（Context）、下单 API、结果收集。
   5.11 strategies/base.py       BaseStrategy 抽象与生命周期钩子。
   5.12 strategies/             示例策略：双均线、动量轮动、网格、买入持有（基准）。
   5.13 analytics/metrics.py     全部绩效指标计算（纯函数，便于测试）。
   5.14 analytics/plots.py       matplotlib 图表生成（净值、回撤、分布、热力图）。
   5.15 analytics/report.py      HTML 与 Excel 报告生成。
   5.16 app/api/                 data、strategies、backtests、optimize、reports 路由。
   5.17 app/runner.py            任务队列与子进程执行、超时与资源限制。
   5.18 tests/                   指标正确性、撮合规则、无未来函数、可复现性、API 测试。

6. 接口清单（HTTP，节选核心）
   6.1 POST /api/v1/data/import            导入 CSV（multipart）或触发行情同步
   6.2 GET  /api/v1/data/symbols           标的列表与覆盖情况
   6.3 GET  /api/v1/data/quality?symbol=   数据质量报告
   6.4 GET  /api/v1/data/bars?symbol=&from=&to=&limit=  查询 K 线
   6.5 POST /api/v1/strategies             创建/上传策略（name、code、description）
   6.6 GET  /api/v1/strategies             策略列表
   6.7 PUT  /api/v1/strategies/{id}        更新策略（版本 +1）
   6.8 POST /api/v1/backtests              提交回测 {strategy_id, symbols, start, end,
       cash, commission, slippage, fill_mode, seed}
   6.9 GET  /api/v1/backtests/{id}         查询状态与配置
   6.10 GET  /api/v1/backtests/{id}/metrics 绩效指标
   6.11 GET  /api/v1/backtests/{id}/trades  交易明细（分页）
   6.12 GET  /api/v1/backtests/{id}/equity  净值序列
   6.13 GET  /api/v1/backtests/{id}/charts/{name}  图表 PNG（equity/drawdown/monthly/returns）
   6.14 POST /api/v1/backtests/{id}/report  生成报告并返回下载路径
   6.15 POST /api/v1/optimize               提交网格搜索 {strategy_id, grid, base_config}
   6.16 GET  /api/v1/optimize/{id}          搜索进度与结果排序
   6.17 POST /api/v1/compare                多结果对比（ids 数组）
   6.18 GET  /api/v1/system/status          队列与资源状态

7. 数据模型概览
   7.1 symbols(code TEXT PK, name TEXT, exchange TEXT, board TEXT, lot_size INT,
       listed_at TEXT, delisted_at TEXT, updated_at TEXT)
   7.2 daily_bars(symbol TEXT, trade_date TEXT, open INT, high INT, low INT, close INT,
       volume BIGINT, amount BIGINT, adj_factor INT, is_suspended INT, limit_up INT,
       limit_down INT, updated_at TEXT)  主键 (symbol, trade_date)
       说明：价格以“分”为单位存整数（保留 4 位小数时可存为万分之一元，字段注释统一口径）
   7.3 calendars(trade_date TEXT PK, is_open INT)
   7.4 rejected_rows(id PK, source TEXT, line_no INT, raw_json TEXT, reason TEXT,
       created_at TEXT)
   7.5 strategies(id PK, name TEXT, description TEXT, code TEXT, version INT,
       created_by TEXT, created_at, updated_at)  唯一键 (name, version)
   7.6 backtests(id TEXT PK, strategy_id FK, strategy_version INT, config_json TEXT,
       data_version TEXT, seed INT, state TEXT, progress INT, started_at, finished_at,
       error TEXT, metrics_json TEXT, report_path TEXT)
   7.7 equity_curve(id PK, backtest_id FK, trade_date TEXT, cash BIGINT,
       market_value BIGINT, total_asset BIGINT, nav REAL, benchmark_nav REAL, drawdown REAL)
       唯一键 (backtest_id, trade_date)
   7.8 trades(id PK, backtest_id FK, symbol TEXT, side TEXT, open_date TEXT,
       close_date TEXT NULL, open_price REAL, close_price REAL NULL, quantity INT,
       commission BIGINT, pnl BIGINT NULL, hold_days INT NULL, reason TEXT)
   7.9 orders(id PK, backtest_id FK, ts TEXT, symbol TEXT, side TEXT, order_type TEXT,
       price REAL, quantity INT, filled INT, state TEXT, reject_reason TEXT)
   7.10 optimize_tasks(id TEXT PK, strategy_id FK, grid_json TEXT, state TEXT,
       total INT, done INT, best_params_json TEXT, created_at, finished_at)
   7.11 optimize_results(id PK, task_id FK, params_json TEXT, metrics_json TEXT,
       backtest_id TEXT)
   7.12 audit_log(id PK, user_id, action, target, detail_json, created_at)
   7.13 索引：daily_bars 建 (trade_date) 便于按日横截面查询；equity_curve 建
       (backtest_id, trade_date) 唯一；trades 建 (backtest_id, symbol)。

【三、里程碑拆解（建议 4 ~ 6 个阶段）】

阶段一：数据层与校验（约 18 小时）
  产出：CSV 导入、字段校验与被拒行记录、复权处理、交易日历、数据覆盖报告、样本数据
       生成器（固定种子）、K 线查询接口。
  验收：导入一份含 200 行错误的 CSV，被拒行报告能准确定位每一行问题；复权前后收益率
       一致性测试通过。

阶段二：账户与撮合引擎（约 28 小时）
  产出：事件循环、账户与持仓核算、整手与流动性约束、手续费与滑点模型、成交价模式、
       涨跌停与停牌处理、订单与成交记录。
  验收：构造 10 组人工场景（含涨停买入被拒、停牌不成交、T+1 限制）结果全部符合预期；
       手续费计算与人工手算一致。

阶段三：策略框架与示例策略（约 20 小时）
  产出：BaseStrategy 与 Context 下单 API、策略加载与沙箱限制、4 个示例策略、风控约束、
       基准对比。
  验收：双均线策略在样本数据上可复现运行；同一配置运行两次净值曲线逐点一致。

阶段四：绩效指标与可视化（约 24 小时）
  产出：全部指标计算（附手算样例测试）、净值/回撤/分布/月度热力图、交易明细导出、
       HTML 与 Excel 报告生成。
  验收：指标与手工计算结果误差为 0（除夏普等涉及浮点的指标允许 1e-9 误差）；报告中图表
       可正常打开。

阶段五：Web 平台与任务管理（约 22 小时）
  产出：数据管理页、策略管理页、回测提交与结果页、任务队列与子进程执行、网格搜索与
       参数敏感性、多策略对比。
  验收：提交回测后 3 秒内状态变为运行中；200 组参数网格搜索可完成并排序输出。

阶段六：测试、性能与文档（约 18 小时）
  产出：覆盖率报告、无未来函数检测用例、大数据量性能基准（1200 万 bar）、使用文档与
       策略编写指南、免责声明与数据来源说明。
  验收：1200 万 bar 的回测（20 标的、10 年）在 8 分钟内完成；文档中的策略示例可直接运行。

【四、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；类型注解全覆盖；核心计算避免 Python 层三重循环。
2. 允许使用的库：标准库（sqlite3、csv、decimal、dataclasses、enum、statistics、json、
   subprocess、multiprocessing、logging）；第三方限 FastAPI、uvicorn、pandas、numpy、
   SQLAlchemy、pydantic、matplotlib、APScheduler、openpyxl、httpx、pytest、
   pytest-asyncio、pyarrow（可选，用于 Parquet 缓存）。禁止引入 TA-Lib、backtrader、
   vectorbt、zipline 等现成回测框架（本项目要求自行实现撮合与账户核算）。
3. 禁止事项：禁止在 on_bar 中访问当前 bar 之后的任何数据（含通过 shift(-1) 等隐式未来
   数据）；禁止用收盘价撮合却把信号也基于同一收盘价计算（默认配置下必须用次日开盘成交）；
   禁止用浮点数直接比较金额相等；禁止把复权后价格当作真实成交价记账而不做说明；禁止在
   策略中执行网络请求与文件写入；禁止把回测结果包装成投资建议或收益承诺。
4. 指标口径必须固化并写明：年化交易日 252；无风险利率默认 2%（年化）；夏普 = (年化收益 -
   无风险利率) / 年化波动率；索提诺只用下行波动；卡玛 = 年化收益 / 最大回撤绝对值；最大
   回撤按总资产序列计算并在报告中给出起止日期；胜率仅统计已平仓交易；换手率 = 期间成交
   金额 / 期间平均总资产（年化需说明是否折算）。口径变更必须同步更新测试与文档。
5. 代码组织：engine 与 analytics 必须与 Web 层（app）解耦，可直接被命令行与测试调用；
   策略通过接口与引擎交互，不得直接读写引擎内部状态；数据访问统一走 data/store.py；
   指标计算全部为无副作用的纯函数（输入 DataFrame，输出 dict），便于单元测试。
6. 隔离与安全：策略加载使用受限 exec 与 __import__ 审计 hook，禁止 socket、requests、
   subprocess、os.system、open(…, 'w')；回测在子进程中运行并设置超时与内存上限（可用
   resource 模块或轮询 psutil 的替代实现，Windows 下退化为超时控制并在文档说明差异）。
7. 编码规范：PEP 8；模块与公有函数必须有 docstring；数值计算函数必须注明单位与量纲；
   日志中禁止输出策略源码全文（只记录策略 id 与版本）。
8. 测试要求：覆盖率 ≥ 75%；必须包含：指标手算对照测试（至少 8 个指标）、撮合规则测试
   （涨跌停、停牌、整手、流动性上限、T+1 共 ≥ 15 例）、无未来函数测试（构造“只使用当日
   收盘价”的策略并断言撮合价来自次日开盘）、可复现性测试（两次运行净值序列完全相同）、
   策略沙箱测试（尝试 import socket 必须失败）。
9. 性能要求：单机 4 核 8 GB；1000 万 bar 的回测（单策略）≤ 8 分钟；净值序列生成后指标
   计算 ≤ 3 秒；图表生成 ≤ 5 秒；网格搜索 200 组在 30 分钟内完成（并发度可配置，默认 4）。
   pandas 使用需避免逐行 apply，改用向量化与预索引。
10. 合规与免责：本项目仅用于技术学习与策略研究，不构成投资建议、不做实盘交易、不承诺
    收益；所有行情数据必须来自公开合法来源并在文档标注来源与许可，禁止使用未授权的付费
    数据或内幕信息；报告中必须包含“历史回测不代表未来表现”的提示；如接入第三方数据接口，
    必须遵守其服务条款与频率限制（含限速与缓存），不得批量抓取。

【五、设计要点】

1. 数据结构：
   1.1 BarEvent(symbol, trade_date, open, high, low, close, volume, is_suspended,
       limit_up, limit_down)。
   1.2 Order(id, symbol, side, order_type, price, quantity, created_date, state)。
   1.3 Fill(order_id, symbol, side, price, quantity, commission, tax, slippage_cost, date)。
   1.4 Position(symbol, quantity, available_quantity, avg_cost, market_value)。
   1.5 Account(cash, frozen_cash, positions: dict[str, Position], total_asset, nav)。
   1.6 BacktestResult(config, equity: DataFrame, trades: DataFrame, orders: DataFrame,
       metrics: dict, logs: list[str])。
2. 关键算法与流程：
   2.1 主循环（每交易日）：① 更新持仓市值（用当日收盘价）；② 处理未成交限价单（按当日
       价格区间判断能否成交）；③ 调用 strategy.on_bar(context) 生成信号；④ 信号转订单并做
       风控与整手校验；⑤ 依据 fill_mode 决定本日或次日撮合；⑥ 成交后更新持仓与现金、
       计算手续费；⑦ 以收盘价估值并写入 equity_curve；⑧ 更新 T+1 可用数量。
   2.2 撮合价与滑点：默认次日开盘价；买入价 = 开盘价 × (1 + slippage)，卖出价 = 开盘价 ×
       (1 - slippage)；涨停日禁止买入、跌停日禁止卖出（宽松模式可关闭）。
   2.3 手续费：commission = max(amount × 0.0003, 5.0)；卖出加印花税 amount × 0.001；
       过户费 amount × 0.00002（按配置）。金额以分计算，最后统一四舍五入到分。
   2.4 流动性约束：max_qty = floor(bar.volume × liquidity_ratio / lot_size) × lot_size；
       若下单量超出则按 max_qty 部分成交，剩余部分按配置撤销或顺延，并记录原因。
   2.5 指标计算：日收益 r_t = nav_t / nav_{t-1} - 1；年化收益 = (nav_end / nav_start) **
       (252 / n) - 1；年化波动 = std(r) × sqrt(252)；最大回撤 = min(nav / cummax(nav) - 1)。
   2.6 网格搜索：笛卡尔积生成参数组合 → 提交到进程池（并发 4）→ 每组独立回测 → 汇总
       指标 → 按夏普或年化收益排序 → 计算最优参数的邻域（相邻 1 格参数）指标均值与标准差，
       若邻域表现显著劣于最优值则标注“过拟合风险高”。
   2.7 无未来函数保障：信号与撮合分属不同交易日；数据访问通过上下文提供 as_of 视图，
       只暴露 ≤ 当前交易日的行；测试用“若访问未来数据则结果差异巨大”的策略做哨兵检测。
3. 数据库主要表结构已在功能清单第 7 节列出；补充实现细节：
   3.1 价格字段统一为整数“万分之一元”（便于保留 4 位小数且无浮点误差），字段注释与
       转换函数集中在 data/store.py，禁止在业务代码里手写换算。
   3.2 equity_curve 每回测每天一行，1000 万 bar 级回测的曲线行数不超过 2500（10 年 × 250），
       数据量可控；如需日内回测则另建表 intraday_equity。
   3.3 trades 与 orders 表在回测完成后批量写入（单事务 executemany），避免逐条提交。
   3.4 结果缓存：图表与报告按 backtest_id 缓存到 reports/{id}/，重复请求直接返回文件。
4. 接口设计要点：
   4.1 回测提交为异步任务：返回 202 与 backtest_id，前端轮询 /backtests/{id} 获取 progress。
   4.2 配置校验严格：日期区间不超过 20 年、标的不超过 500 个、初始资金不超过 10 亿、
       费率非负、fill_mode 只接受 next_open | close。
   4.3 结果接口返回 JSON 时数值统一保留 6 位有效小数，金额字段以分返回并注明单位。
   4.4 失败任务保留 error 摘要与日志路径，前端可查看失败原因（如“策略第 42 行 NameError”）。

【六、运行方式与示例】

1. 安装与初始化
   python -m venv .venv && .venv\Scripts\activate
   pip install fastapi uvicorn pandas numpy sqlalchemy pydantic matplotlib apscheduler
   pip install openpyxl httpx pytest pytest-asyncio
   python -m app.cli initdb
   python -m app.cli sample-data --symbols 20 --years 10 --seed 42   （生成样本数据）
   python -m app.cli import-csv --file D:\data\sh600000.csv --symbol 600000.SH
2. 启动
   uvicorn app.main:app --host 127.0.0.1 --port 8020
   浏览器访问 http://127.0.0.1:8020
3. 命令行回测（无需 Web）
   python -m app.cli backtest --strategy strategies/dual_ma.py --symbols 600000.SH,000001.SZ
          --start 2015-01-01 --end 2024-12-31 --cash 1000000 --fast 10 --slow 30
4. 示例一（提交回测）
   请求：POST /api/v1/backtests
   {"strategy_id": 3, "symbols": ["600000.SH", "000001.SZ"], "start": "2015-01-01",
    "end": "2024-12-31", "cash": 1000000, "commission_rate": 0.0003,
    "slippage_rate": 0.0005, "fill_mode": "next_open", "seed": 42}
   响应：202 {"backtest_id": "bt-7c31a0", "state": "queued", "progress": 0}
5. 示例二（查询绩效指标）
   请求：GET /api/v1/backtests/bt-7c31a0/metrics
   响应：200
   {
     "total_return": 1.8421, "annual_return": 0.1103, "annual_volatility": 0.1932,
     "sharpe": 0.4676, "sortino": 0.7124, "calmar": 0.5238,
     "max_drawdown": -0.2106, "max_drawdown_start": "2018-02-06",
     "max_drawdown_end": "2018-12-27", "longest_drawdown_days": 324,
     "win_rate": 0.4375, "profit_loss_ratio": 1.83, "trade_count": 96,
     "avg_hold_days": 18.4, "turnover_annual": 3.12, "alpha": 0.0312, "beta": 0.847,
     "benchmark_return": 0.6215, "excess_return": 1.2206
   }
6. 示例三（净值序列节选）
   请求：GET /api/v1/backtests/bt-7c31a0/equity?from=2018-01-01&to=2018-12-31
   响应：200
   {"items": [
     {"trade_date": "2018-12-27", "nav": 0.7894, "benchmark_nav": 0.8512,
      "drawdown": -0.2106, "cash_cent": 41200000, "market_value_cent": 37700000,
      "total_asset_cent": 78940000},
     {"trade_date": "2018-12-28", "nav": 0.7931, "benchmark_nav": 0.8540,
      "drawdown": -0.2069, "cash_cent": 41200000, "market_value_cent": 38050000,
      "total_asset_cent": 79250000}
   ]}
7. 示例四（数据校验拒绝行）
   导入含错误行的 CSV（第 18 行 high < low，第 43 行价格为 0，第 77 行日期重复）
   响应：200 {"imported": 1971, "rejected": 3,
         "rejected_detail": [
           {"line_no": 18, "reason": "HIGH_LESS_THAN_LOW"},
           {"line_no": 43, "reason": "NON_POSITIVE_PRICE"},
           {"line_no": 77, "reason": "DUPLICATE_DATE"}]}
8. 示例五（异常输入）
   请求：POST /api/v1/backtests {"start": "2024-12-31", "end": "2015-01-01", ...}
   响应：400 {"code": "BAD_RANGE", "message": "开始日期必须早于结束日期"}
   请求：提交含未来函数的策略（在 on_bar 中读取下一日收盘价）
   响应：200（回测可运行）但报告中包含警告：
   {"warnings": ["检测到策略在第 27 行访问了 index+1 的数据，结果可能失真"]}

【七、验收标准】

[ ] 1. 导入含 3 类错误的 CSV，被拒行报告精确定位行号与原因，合法行全部入库且可查询。
[ ] 2. 复权处理正确：用后复权价计算 2015 到 2024 的买入持有收益率与用复权因子手工计算
      结果一致（误差 < 1e-9）。
[ ] 3. 撮合规则测试 15 例全部通过：涨停买入被拒、跌停卖出被拒、停牌不成交、整手校验、
      流动性上限部分成交、T+1 不可卖、限价单次日处理等。
[ ] 4. 默认 fill_mode=next_open 下，信号基于 T 日收盘、成交价等于 T+1 日开盘价（含滑点），
      可通过 trades 表逐笔核对。
[ ] 5. 同一配置连续运行两次，equity_curve 全部字段逐点差异为 0。
[ ] 6. 指标计算结果与手算样例一致：总收益、年化、波动、夏普、最大回撤及区间、胜率、
      盈亏比、卡玛比率共 8 项误差 < 1e-9。
[ ] 7. 手续费计算与手工计算一致（含最低 5 元佣金、卖出印花税、过户费）。
[ ] 8. 策略沙箱有效：策略中 import socket、subprocess、open('w') 均被拦截且任务失败并给出
      明确错误信息。
[ ] 9. 1000 万 bar（20 标的 × 10 年）回测在 8 分钟内完成，内存占用不超过 4 GB。
[ ] 10. 图表生成成功：净值、回撤、月度热力图、收益分布四张图在无 GUI 环境可生成 PNG。
[ ] 11. HTML 报告与 Excel 报告可正常打开，Excel 含指标页、交易明细页、净值序列页。
[ ] 12. 网格搜索 200 组完成并输出排序结果，同时给出最优参数的邻域稳定性与过拟合提示。
[ ] 13. 多策略对比（5 个结果）在同一张净值图上正确渲染，图例与颜色区分明确。
[ ] 14. pytest 覆盖率 ≥ 75%，含指标、撮合、无未来函数、可复现性、沙箱五类专项测试。
[ ] 15. 文档包含：指标口径说明、数据来源与许可、免责声明、策略编写指南，且示例策略可
      直接运行。

【八、可选扩展】

1. 增加日内（分钟级）回测支持，引入成交量分布模型与更细的滑点模型。
2. 增加期货与 ETF 标的支持：保证金、逐日盯市、主力合约拼接。
3. 增加组合优化：均值方差、风险平价、Black-Litterman，与回测引擎联动。
4. 增加因子研究模块：因子计算、IC/IR 分析、分层回测与因子相关性矩阵。
5. 增加机器学习策略接口（可与 097 项目联动）：用滚动窗口训练模型生成信号，严格避免
   数据泄漏（训练集与测试集按时间切分）。
6. 增加模拟盘（paper trading）：按实时或延时行情驱动同一套引擎，但明确不下真实订单。
7. 增加分布式回测：任务拆分到多进程/多机，网格搜索时间随核数近线性下降。

【九、涉及知识点】

- 金融数据基础：K 线字段、复权因子、停牌与涨跌停、交易日历、整手与 T+1 规则
- 回测偏差：未来函数、幸存者偏差、滑点与手续费缺失、过拟合与样本外验证
- 事件驱动架构：事件队列、策略生命周期、上下文对象与下单 API 设计
- 数值计算：pandas 向量化与索引对齐、numpy 统计、浮点误差与定点金额处理
- 绩效评估：年化收益与波动、夏普/索提诺/卡玛、最大回撤与回撤区间、Alpha/Beta
- 可视化：matplotlib 无 GUI 后端、热力图与分布图、报告内嵌图片（base64）
- 系统与安全：子进程隔离与超时、受限执行沙箱、任务队列与并发控制
- 工程与合规：可复现性（种子与版本）、指标口径文档化、数据许可与免责声明
================================================================================
