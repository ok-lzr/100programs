================================================================================
项目编号：052                    难度等级：★★★☆☆（中型项目）
项目名称：消费数据可视化看板
所属分类：数据分析 / 报表可视化
建议工时：2 ~ 3 天
运行环境：Python 3.10+    第三方依赖：pandas、matplotlib、openpyxl、jinja2
================================================================================

【一、项目背景与目标】

很多人把记账数据存在某个 App 里，导出 CSV 之后却只能看到一堆行，看不出
“钱到底花在哪了、比上个月多了还是少了、哪一类在悄悄上涨”。本项目不做记账，
只做分析：读取支付宝/微信/银行导出的账单 CSV（或上一项目 051 生成的 CSV），
统一字段口径后计算指标，画出图表，最终生成一份可以双击打开、可离线发送给
家人的单文件 HTML 报告。

目标用户是需要月度消费复盘的个人与家庭。使用者不需要懂 pandas，只需要把
账单文件丢进 data/raw/ 目录，运行一条命令，就能得到 reports/2024-05.html。

项目的核心价值在于“指标口径统一”：同一个“餐饮支出”在不同账单里可能叫
“餐饮美食”“美团外卖”，本项目通过映射规则把原始分类归一到固定的一级分类，
保证跨月对比时口径一致，这也是本项目的真正难点。

【二、功能需求清单】

1. 核心功能
   1.1 多源账单读取（load）：自动识别支持的源格式（wechat / alipay / bank /
       generic），跳过文件头部的说明行与尾部的汇总行，只保留交易明细。
   1.2 字段归一化（normalize）：把各源字段映射为统一列
       transaction_time、amount、direction、raw_category、counterparty、
       product_desc、pay_method、status。
   1.3 分类映射（map_category）：按关键词规则表把 raw_category 与
       product_desc 归一到一级分类（餐饮、交通、购物、居住、娱乐、医疗、
       教育、人情、其他），规则可配置、可覆盖、可查看命中明细。
   1.4 数据清洗（clean）：剔除退款、已关闭、金额为 0 的记录；把支出记为
       正数，收入单列；去重（同源同时间同金额同商户只保留一条）。
   1.5 指标计算（metrics）：月度总收入、总支出、净结余、支出环比、日均支出、
       最大单笔支出、消费笔数、客单价、Top10 商户、Top10 单笔交易。
   1.6 图表生成（charts）：生成至少 6 张图并保存为 PNG，同时内嵌到 HTML。
   1.7 报告生成（report）：用 jinja2 渲染单文件 HTML，图表以 base64 内嵌，
       不依赖任何外链与 CDN，离线可看，含文字结论摘要。
   1.8 多期对比（compare）：支持指定两个月份对比，输出分类环比表与差异条形图。

2. 输入与交互
   2.1 命令形式：
       `python -m dashboard --input data/raw --month 2024-05 --out reports/2024-05.html`
   2.2 支持 --input 传单个文件或整个目录；目录下所有 .csv 按文件名顺序处理。
   2.3 支持 --month all 汇总全部数据，--month 2024-05 只看单月。
   2.4 支持 --config config/rules.yaml 或 config/rules.json 指定分类映射规则。
   2.5 支持 --top-n 控制排行榜条数，默认 10；--no-charts 只出指标表不画图。
   2.6 交互补充：`python -m dashboard rules --unmatched` 列出未命中任何规则的
       原始分类及其金额合计，方便用户补规则。

3. 输出与展示
   3.1 控制台输出：读取文件数、原始行数、清洗后行数、剔除原因统计、生成路径。
   3.2 HTML 报告分区：概览卡片（收入/支出/结余/环比）、分类占比环形图、
       分类金额横向条形图、近 12 个月收支柱状图、每日支出折线图、
       Top 商户条形图、单笔金额分布直方图、明细表 Top50、结论文本区。
   3.3 图表统一中文字体与配色（matplotlib rcParams 设置 font.sans-serif），
       避免中文显示为方块。
   3.4 报告中所有金额单位统一为元、保留两位小数，环比用百分比保留一位小数。

4. 异常与边界处理
   4.1 输入目录为空：输出明确提示并退出码 1，不生成空报告。
   4.2 CSV 编码不是 UTF-8：依次尝试 utf-8-sig、gbk、gb18030，全部失败则报错
       并指出文件名与字节偏移提示。
   4.3 缺少必需列：报错并列出该文件实际列名与期望列名，方便定位。
   4.4 金额列含 “¥”“,”“+”“-” 等字符：清洗为纯数字，无法解析的行计入
       剔除统计并写入 rejects.csv 供人工复核。
   4.5 月份无数据：报告显示“该月无有效记录”，图表区域显示占位提示。
   4.6 上期无数据：环比显示“N/A”，不显示除零或无穷大。
   4.7 图表数量为 0（无分类）：跳过环形图，其他图表正常生成。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：
   2.1 第三方：pandas（数据框处理）、matplotlib（绘图）、openpyxl（读取 xlsx
       账单）、jinja2（HTML 模板）。
   2.2 标准库：argparse、base64、io、json、pathlib、re、datetime、logging、
       collections、hashlib、dataclasses。
   2.3 禁止引入 plotly、pyecharts 之外的动态 JS 依赖；本项目要求图表静态内嵌，
       因此不引入任何需要联网加载的 JS 库。
3. 禁止事项：禁止对 DataFrame 逐行 for 循环做数值计算（必须向量化）；
   禁止把 Matplotlib 默认后端切到交互后端导致无显示环境报错
   （必须 `matplotlib.use("Agg")`）；禁止在模板里写业务计算逻辑。
4. 代码组织：
   - `loader.py`：各源账单读取器，统一返回原始 DataFrame。
   - `normalizer.py`：字段映射、类型转换、金额清洗。
   - `categorizer.py`：规则加载与分类映射，输出命中来源与置信度。
   - `metrics.py`：纯函数式计算指标，输入 DataFrame 输出 dataclass。
   - `charts.py`：绘图函数，每个函数返回 PNG 字节流，不落盘。
   - `report.py`：jinja2 渲染与单文件 HTML 打包。
   - `rules.py`：默认规则表与规则的增删查。
   - `cli.py`：命令行入口。
5. 编码规范：所有函数带类型注解；DataFrame 操作用链式写法并保持可读；
   绘图函数不修改全局 rcParams 之外的输入；关键步骤写 logging.info 记录行数变化。

【四、设计要点】

1. 数据结构

   1.1 统一交易表（清洗后 DataFrame）字段与口径
       transaction_time : datetime64  交易发生时间（本地时间，不带时区）
       date             : date        交易日，用于按天聚合
       month            : str 'YYYY-MM'，用于按月聚合
       amount_yuan      : float       金额（元），支出为正、收入为正
       direction        : str         'expense' | 'income'
       category         : str         一级分类（归一后，支出才有意义）
       raw_category     : str         账单原始分类，保留以便追溯
       counterparty     : str         交易对方/商户
       product_desc     : str         商品说明
       pay_method       : str         支付方式
       source           : str         来源：wechat / alipay / bank / generic
       fingerprint      : str         去重指纹（sha1 前 16 位）

   1.2 分类规则表（config/rules.json）
       结构：[{"category":"餐饮","keywords":["餐饮","美食","外卖","快餐","咖啡",
       "奶茶","餐厅"],"priority":10,"source":["wechat","alipay"]}, ...]
       匹配顺序：先看 source 限定，再按 priority 降序，再按关键词长度降序，
       保证“美团外卖”命中“餐饮”而不是“购物”。

   1.3 指标结果 dataclass
       MonthMetrics: month, income, expense, net, expense_mom_pct,
       daily_avg, tx_count, avg_ticket, max_single, category_breakdown(list),
       top_merchants(list), top_transactions(list), unmatched_categories(list)

2. 关键算法或流程
   2.1 读取流程：探测编码 → 用 csv 模块嗅探前 30 行找到表头行号
       （含“交易时间”或“交易创建时间”等关键字）→ 以该行为 header 读入
       → 丢弃“合计/汇总/说明”行 → 返回原始 DataFrame。
   2.2 金额清洗：正则去除 `[¥￥,\s]`，括号内数字视为负数表示退款，
       方向判定优先级：账单 direction 列 > 金额符号 > 交易类型关键词。
   2.3 分类映射：对 raw_category + product_desc 拼接后的字符串做关键词包含
       匹配；命中多条取 priority 最高者；无命中归入“其他”并记录到未命中清单。
   2.4 环比计算：expense_mom_pct = (本月支出 - 上月支出) / 上月支出 * 100；
       上月为 0 或缺失时输出 None，展示为 “N/A”。
   2.5 去重：fingerprint = sha1(f"{source}|{transaction_time}|{amount}|{counterparty}")
       前 16 位，保留首次出现；同日同商户同金额的多次真实消费通过“时间戳精确到
       秒”区分，若账单只精确到日则仅按 (日期, 金额, 商户, 商品) 去重并提示。
   2.6 图表生成：每个绘图函数接收 DataFrame 与参数字典，返回 io.BytesIO 的
       PNG 字节；report.py 统一读取字节并 base64 编码嵌入 HTML。

3. 图表清单与指标口径（每张图必须写清口径）
   图1 分类占比环形图：口径为“本期支出按 category 求和”，排除收入与
        已剔除记录；标签显示分类名与占比（保留 1 位小数）；占比 < 2% 的
        合并为“其他”以便阅读。
   图2 分类金额横向条形图：口径同上，按金额降序，最多显示 Top12。
   图3 近 12 个月收支柱状图：口径为按月分组的 expense 与 income 双柱，
        横轴为 'YYYY-MM'，缺月补 0 以保持连续。
   图4 每日支出折线图：口径为按 date 求和的支出，横轴覆盖当月全部日期，
        无消费日为 0；叠加 7 日移动平均线以观察趋势。
   图5 Top 商户条形图：口径为按 counterparty 求和的支出，Top N 由 --top-n 决定，
        排除空商户名归入“未知”。
   图6 单笔金额分布直方图：口径为支出单笔金额，分箱采用对数等距
        （1,2,5,10,20,50,100,200,500,1000,2000,+∞）以适应长尾分布。

4. 接口或命令设计
   loader.load_any(path: Path) -> RawFrame
   normalizer.normalize(raw: RawFrame, source: str) -> pd.DataFrame
   categorizer.apply_rules(df: pd.DataFrame, rules: list[Rule]) -> pd.DataFrame
   metrics.compute_month(df: pd.DataFrame, month: str) -> MonthMetrics
   metrics.compare(metrics_a: MonthMetrics, metrics_b: MonthMetrics) -> CompareResult
   charts.category_donut(df, top_n=8) -> bytes
   charts.monthly_bars(df, months=12) -> bytes
   charts.daily_line(df, month: str) -> bytes
   report.render(metrics: MonthMetrics, charts: dict[str, bytes], tpl: Path) -> str

【五、运行方式与示例】

安装：
  cd C:\projects\100programs\052_expense_dashboard
  pip install pandas matplotlib openpyxl jinja2
  mkdir data\raw reports

示例一（单月报告）：
  输入：python -m dashboard --input data\raw\alipay_202405.csv --month 2024-05
        --out reports\2024-05.html
  输出：
        读取文件 1 个，原始 312 行
        编码探测：utf-8-sig
        清洗后 298 行（剔除：退款 6，已关闭 3，金额解析失败 5，详见 rejects.csv）
        分类命中率 96.3%（未命中 11 行 → 其他）
        2024-05 支出 6842.30 元，收入 12000.00 元，净结余 5157.70 元
        环比：+12.4%（上月 6088.10 元）
        报告已生成：reports\2024-05.html（2.1 MB，图表 6 张内嵌）

示例二（多源合并 + 全部月份）：
  输入：python -m dashboard --input data\raw --month all --out reports\all.html
  输出：读取文件 5 个，原始 3241 行，清洗后 3055 行；区间 2023-08 ~ 2024-05
        （共 10 个月）；总支出 71230.55 元；报告已生成：reports\all.html

示例三（查看未命中规则并补规则，含异常输入）：
  输入：python -m dashboard rules --unmatched
  输出：
        未命中分类 Top5（金额合计）：
          数码电器        1288.00
          宠物用品         460.50
          知识付费         299.00
  输入：python -m dashboard --input data\raw --month 2024-13
  输出：错误：月份格式非法，应为 YYYY-MM 且月份在 01~12，收到 “2024-13”（退出码 2）

【六、验收标准】

[ ] 对支付宝、微信两种导出格式的样例文件均能正确识别编码与表头行并读入。
[ ] 清洗报告中的原始行数 = 清洗后行数 + 各类剔除行数，数量守恒。
[ ] 剔除的异常行全部写入 rejects.csv，含文件名、行号、原始内容、剔除原因。
[ ] 统一字段表包含全部 12 个约定列，无中文列名残留。
[ ] 分类映射命中率在样例数据上不低于 90%，未命中项可在 rules --unmatched 中列出。
[ ] “美团外卖”被归入“餐饮”，“滴滴出行”被归入“交通”，验证规则优先级生效。
[ ] 单月报告 HTML 双击可离线打开，图表全部显示，中文无方块。
[ ] HTML 文件不含 http:// 或 https:// 的外链资源引用。
[ ] 分类金额合计与明细表金额合计一致（误差为 0）。
[ ] 支出环比与手工计算一致；上月无数据时显示 N/A 而非报错。
[ ] 每日支出折线图覆盖当月所有日期，无消费日为 0 而不是断线。
[ ] 12 个月柱状图中缺失月份补 0，横轴连续无跳跃。
[ ] 直方图使用对数分箱，长尾数据（存在 5000 元单笔）时图表不被压扁。
[ ] 同一份账单重复运行两次，去重后行数与指标完全一致（幂等）。
[ ] 代码中不存在对 DataFrame 的逐行 Python 循环数值计算（可人工抽查）。

【七、可选扩展】

1. 支持读取 XLSX 与银行 PDF 电子账单（pypdf 提取文本后解析）。
2. 生成带折叠交互的分类明细（纯内联 JS，不引外部库）。
3. 预算对照：读入 051 项目的预算表，在报告中叠加“预算达成进度条”。
4. 自动生成文字版月报结论（基于规则的模板化叙述，如“餐饮环比上涨 23%”）。
5. 输出 emoji 或彩色终端摘要，支持 `--stdout` 管道给其他工具。
6. 用 pytest 编写快照测试：固定样例账单 → 固定指标 JSON，防止口径漂移。

【八、涉及知识点】

- pandas：read_csv 参数（encoding、skiprows、dtype、na_values）、groupby、
  resample、pivot_table、merge、apply、向量化字符串 str.replace/str.contains。
- 数据清洗流程：编码探测、表头定位、异常行隔离、去重指纹。
- matplotlib：Agg 后端、中文字体配置、subplots、barh、pie、hist 分箱、
  base64 图片内嵌。
- jinja2 模板：变量、循环、过滤器（round、format）、模板继承与自动转义。
- 指标口径设计：同比/环比、日均值、占比、Top-N 与长尾处理。
- 单文件 HTML 报告打包：base64 Data URI、文件体积控制。
- 命令行工具设计：argparse 参数分组、默认值与配置优先级。
- 可复现性：固定随机种子、幂等处理、快照测试。
================================================================================
