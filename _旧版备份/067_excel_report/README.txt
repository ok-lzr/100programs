================================================================================
项目编号：067                    难度等级：★★★★☆（中型项目）
项目名称：Excel 报表自动化工具
所属分类：自动化与报表 / 电子表格处理
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：pandas、openpyxl、numpy
================================================================================

【一、项目背景与目标】

每月月底，业务同事会把十几个部门发来的 Excel 汇总表扔进一个文件夹，文件名格式不统一、
表头可能差一两列、日期列有的写文本有的写日期，然后需要手工把它们合到一起、做透视、
给超标数据标红、再加一张趋势图，最后交出一份能发给领导的报表。这个过程既枯燥又容易出错，
本项目就是把它变成一条可重复执行的流水线。

目标用户是负责做月度/周度报表的运营、财务、数据分析人员，以及想练 pandas 与 openpyxl
工程化用法的开发者。做成之后，只要把源文件放进 input 目录，运行一条命令，就能得到一份
包含汇总表、透视表、条件格式与内嵌图表的成品 xlsx，并且每一步都有日志和校验结果。

范围与边界说明：本项目只处理本地 Excel/CSV 文件，不涉及网络采集，不访问任何在线服务；
输出文件仅供内部分析使用；源文件与结果文件都属于业务数据，程序不得上传、不得写入日志正文
（日志只记录文件名、行数、列名等元信息，不打印单元格内容）；处理包含公式的工作簿时默认只读取
公式的计算结果值，不回写公式，如需保留公式请在配置中开启 keep_formulas 并自行确认兼容性；
读取第三方来源的 xlsx 时存在宏（xlsm）风险，本项目默认拒绝处理 xlsm 文件。

【二、功能需求清单】

1. 核心功能
   1.1 多表合并：扫描 input 目录下所有 .xlsx 与 .csv 文件，按配置的列映射把各表统一为相同列名，
       纵向合并为一个长表；记录每个来源文件的行数与贡献列，输出合并报告。
   1.2 列映射与表头识别：支持配置列别名映射（如 {"销售额": ["销售金额", "成交额"]}），
       自动跳过前 N 行说明文字（header_row 可配置），处理列名首尾空格与全角字符。
   1.3 数据类型规整：日期列统一解析为 datetime（支持 2024/5/1、2024-05-01、20240501、Excel 序列号），
       数值列去除千分位逗号与货币符号后转 float，文本列去除首尾空白；无法转换的值记为 NaN 并计数。
   1.4 透视统计：支持按一个或多个行维度与列维度做聚合，聚合函数支持 sum、mean、count、
       nunique、max、min；输出透视表到独立的汇总工作表，并保留行列合计。
   1.5 条件格式：对指定数值列应用规则，包括大于阈值标红底、低于阈值标绿字、重复值标黄、
       数据条（DataBar）与三色阶（ColorScale）；阈值从配置文件读取，支持按列单独配置。
   1.6 汇总行与小计：在明细表底部追加合计行（SUM 公式形式），并按指定维度生成分组小计块。
   1.7 内嵌图表：用 openpyxl 在汇总表旁插入图表，支持 BarChart（各维度对比）、LineChart
       （时间趋势）、PieChart（占比），图表引用实际的 Excel 区域而不是图片，打开后可随数据更新。
   1.8 多工作表输出：结果工作簿至少包含 明细、汇总、透视、说明 四个 sheet；sheet 顺序与命名
       可通过配置调整；所有 sheet 首行冻结、表头加粗、列宽自适应。
   1.9 校验报告：输出 validation.md，包含来源文件清单、合并前后行数、类型转换失败计数、
       透视表行列数、条件格式命中单元格数量，便于核对结果可信度。
2. 输入与交互
   2.1 命令行子命令：merge（只做合并并输出中间 CSV）、build（完整生成报表）、check（校验源文件
       与配置）、inspect（打印某个源文件的表头与前 3 行，用于确认列映射）。
   2.2 关键参数：--config 报表配置 JSON；--input 输入目录（默认 ./input）；--out 输出文件
       （默认 ./output/report_<日期>.xlsx）；--sheet 仅处理指定工作表名；--strict 严格模式下
       列缺失即报错，非严格模式下缺失列填 NaN 并记录警告。
   2.3 配置驱动：compose.json 定义列映射、透视维度、条件格式、图表规格与 sheet 顺序，
       修改报表结构不需要改代码。
3. 输出与展示
   3.1 output/report_<YYYYMMDD>.xlsx：成品报表。
   3.2 output/validation.md：校验报告。
   3.3 output/merged.csv：合并后的长表（UTF-8 with BOM），便于用其他工具复核。
   3.4 控制台日志：每个文件的读取行数、跳过的行数、列映射缺失项、透视耗时、图表数量。
4. 异常与边界处理
   4.1 源文件被其他程序占用（PermissionError）时，重试 3 次（间隔 1 秒、3 秒、5 秒），
       仍失败则跳过该文件并在报告中列出。
   4.2 空文件或只有表头没有数据行的文件被跳过，并计入 skipped_files。
   4.3 全部源文件都被跳过时，不生成报表并报错退出（退出码 6），避免产出一份空报表。
   4.4 严格模式下出现配置的必填列缺失时，列出文件名与缺失列并终止；非严格模式下该列全为 NaN
       且 validation.md 中高亮提示。
   4.5 数值列出现负数或极端值（超过该列均值的 10 倍标准差）时不做删除，只在校验报告中列为
       疑似异常并给出数量，交由人工判断。
   4.6 输出文件已存在且被占用时，自动改用带时间戳的文件名而不是覆盖失败。
   4.7 遇到 .xlsm 文件直接拒绝并提示转换为 xlsx，避免执行宏的风险。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用类型注解与 dataclass。
2. 允许使用的库：pandas、openpyxl、numpy；其余使用标准库（json、csv、argparse、logging、
   datetime、pathlib、re、unicodedata、shutil、time、dataclasses）。
3. 禁止事项：禁止使用 xlrd 旧版接口读取 xls（如需支持请在扩展方向说明并统一为 xlsx）；
   禁止在日志中打印单元格内容；禁止上传任何源数据；禁止对源文件做原地修改，所有输出写入 output 目录；
   禁止用 eval 执行配置中的公式字符串。
4. 代码组织：config.py（配置解析与校验）、reader.py（文件发现与读取）、normalizer.py
   （列映射与类型转换）、merger.py（合并且生成来源标记列 _source_file）、pivot.py（透视统计）、
   formatter.py（样式、条件格式、冻结与列宽）、charts.py（图表插入）、writer.py（工作簿输出）、
   validator.py（校验报告）、cli.py。
5. 编码规范：所有公开函数写 docstring 并说明参数 DataFrame 的必备列；配置校验失败必须报出
   配置文件名与字段路径；处理中文需注意列宽按显示宽度估算（中文按 2 个字符宽度计）；
   写出 Excel 时统一使用 openpyxl 引擎，禁止混用 xlwt；使用 logging 而非 print。
6. 测试要求：normalizer.py 的日期与数值转换（含 Excel 序列号、全角字符）、pivot.py 的透视口径、
   formatter.py 的条件格式规则三部分需有 pytest 用例；测试使用临时目录动态生成小样本 xlsx，
   断言输出工作簿的 sheet 名、单元格值与公式；不得依赖仓库中的大文件。

【四、设计要点】

1. 数据结构
   1.1 ReportConfig：input_dir(Path)、output_path(Path)、strict(bool)、header_row(int)、
       column_map(dict[str, list[str]])、dtypes(dict[str, str])、pivot(PivotSpec)、
       formats(list[FormatRule])、charts(list[ChartSpec])、sheet_order(list[str])。
   1.2 PivotSpec：index(list[str])、columns(list[str])、values(dict[str, str])、
       aggfunc(str)、margins(bool)、fill_value(float|int|None)。
   1.3 FormatRule：column(str)、kind(str，greater/less/duplicate/databar/colorscale)、
       threshold(float|None)、fill_color(str，十六进制)、font_color(str|None)。
   1.4 ChartSpec：sheet(str)、kind(str，bar/line/pie)、data_range(str，如 汇总!B2:B12)、
       categories_range(str)、title(str)、anchor(str，如 H2)、width(float)、height(float)。
   1.5 MergeReport：files(list[FileStat])、total_rows(int)、merged_rows(int)、
       skipped_files(list[str])、missing_columns(dict[str, list[str]])、type_failures(dict[str, int])。
2. 关键算法或流程
   2.1 主流程：加载配置 → 发现源文件 → 逐文件读取与规整 → 合并（新增 _source_file 列）→
       透视 → 写出明细与透视 → 应用样式与条件格式 → 插入图表 → 写说明 sheet → 输出校验报告。
   2.2 列映射算法：先做列名标准化（去空格、全角转半角、统一大小写），再按别名表匹配，
       匹配到多个候选时按配置顺序取第一个并记录警告；未匹配的原列保留为“未映射”并在报告中列出。
   2.3 日期解析顺序：datetime 类型直接沿用 → 数字且介于 20000 与 60000 之间视为 Excel 序列号
       （基准 1899-12-30）→ 依次尝试 %Y-%m-%d、%Y/%m/%d、%Y%m%d、%Y年%m月%d日；
       全部失败记为 NaT 并计入 type_failures。
   2.4 小计生成：按分组维度排序后，用 pandas groupby 计算每组 SUM，在明细表下方按组插入
       小计行与总计行，小计行的维度列显示“小计：<组名>”，数值列写 Excel SUM 公式。
   2.5 列宽估算：width = min(40, max(8, ceil(max_display_width * 1.2)))，中文按 2 计宽度。
3. 接口或命令设计
   3.1 命令行：
       python main.py build --config compose.json --input ./input --out ./output/report_202405.xlsx
       python main.py inspect --input ./input/销售明细_北京.xlsx --sheet Sheet1
       python main.py merge --config compose.json --input ./input --out ./output/merged.csv
       python main.py check --config compose.json --input ./input --strict
   3.2 关键函数签名：
       def read_source(path: Path, sheet: str | None, header_row: int) -> pandas.DataFrame
       def normalize(frame: pandas.DataFrame, cfg: ReportConfig) -> tuple[pandas.DataFrame, dict]
       def merge_all(frames: list[tuple[str, pandas.DataFrame]]) -> pandas.DataFrame
       def build_pivot(frame: pandas.DataFrame, spec: PivotSpec) -> pandas.DataFrame
       def apply_formats(ws, frame: pandas.DataFrame, rules: list[FormatRule]) -> dict
       def add_chart(ws, spec: ChartSpec) -> None
   3.3 compose.json 片段：
       {"header_row": 0,
        "column_map": {"日期": ["统计日期", "date"], "城市": ["地区", "city"],
                       "销售额": ["销售金额", "成交额"]},
        "pivot": {"index": ["城市"], "columns": ["月份"], "values": {"销售额": "sum"},
                  "aggfunc": "sum", "margins": true},
        "formats": [{"column": "销售额", "kind": "greater", "threshold": 100000,
                     "fill_color": "FFC7CE"},
                    {"column": "销售额", "kind": "databar"}],
        "charts": [{"sheet": "汇总", "kind": "bar", "data_range": "汇总!B2:B12",
                    "categories_range": "汇总!A2:A12", "title": "各城市销售额",
                    "anchor": "H2", "width": 16, "height": 8}]}

【五、运行方式与示例】

安装依赖：
   pip install pandas openpyxl numpy

运行示例一（查看源文件结构）：
   python main.py inspect --input ./input/销售明细_北京.xlsx
   输出：
   [INFO] 工作表：Sheet1，共 1240 行 8 列
   [INFO] 前 3 列表头：统计日期 | 地区 | 销售金额 ...
   [INFO] 建议映射：统计日期 -> 日期，地区 -> 城市，销售金额 -> 销售额

运行示例二（生成报表）：
   python main.py build --config compose.json --input ./input --out ./output/report_202405.xlsx
   输出：
   [INFO] 发现源文件 14 个（xlsx 12，csv 2），跳过 1 个空文件
   [INFO] 合并完成：明细 18420 行，来源列 _source_file 已写入
   [INFO] 类型转换：日期列失败 3 个，销售额列失败 0 个
   [INFO] 透视表 6 行 x 5 列（含合计行列）
   [INFO] 条件格式命中 128 个单元格；插入图表 3 个
   [INFO] 报表已生成：output/report_202405.xlsx，校验报告：output/validation.md

运行示例三（严格校验）：
   python main.py check --config compose.json --input ./input --strict
   输出：
   [ERROR] 严格模式：文件 销售明细_天津.xlsx 缺少必填列 销售额
   [ERROR] 校验未通过（退出码 3）

异常示例：
   python main.py build --config compose.json --input ./empty_dir
   输出：
   [ERROR] 未发现任何可用的 .xlsx 或 .csv 文件
   [ERROR] 已生成 0 行报表，任务终止（退出码 6）

【六、验收标准】

[ ] inspect 能正确打印源文件的 sheet 名、行列数与前 3 列表头
[ ] 列别名映射生效，不同文件中的“销售金额/成交额”被统一为“销售额”列
[ ] 全角字符与首尾空格的列名能被正确匹配
[ ] Excel 序列号格式的日期被正确解析为 datetime
[ ] 无法解析的日期与数值被计入 type_failures 并在 validation.md 中列出计数
[ ] 合并后的长表带有 _source_file 列，可回溯每行来源
[ ] 透视表的行维度、列维度、聚合值与 pandas 手工计算结果一致（含合计行列）
[ ] 大于阈值 100000 的销售额单元格确实标红底，且命中数量与日志一致
[ ] 数据条与三色阶条件格式在 Excel 中正常显示
[ ] 明细表底部的合计行使用 SUM 公式而非硬编码数值
[ ] 汇总表中的柱状图/折线图/饼图引用真实单元格区域且标题正确
[ ] 输出工作簿包含 明细、汇总、透视、说明 四个 sheet，顺序与配置一致
[ ] 所有 sheet 首行冻结、表头加粗、中文列宽合适（不出现 ### 截断）
[ ] 源文件被占用时按 1、3、5 秒重试，最终跳过并记录在 validation.md
[ ] 全部源文件被跳过时不生成报表且退出码为 6
[ ] 处理 .xlsm 文件时被明确拒绝并给出转换提示
[ ] 源文件在运行前后校验哈希一致，证明未被原地修改
[ ] 日志中不出现任何单元格内容，只出现文件名与统计数字
[ ] pytest 测试全部通过，且测试不依赖仓库中的真实数据文件

【七、可选扩展】

1. 增加数据字典 sheet：自动列出每列的名称、类型、取值范围与非空率，方便交接。
2. 增加同比/环比列自动计算，并在图表中同时展示本期与上期两条线。
3. 增加多期报表拼接模式，把每月结果追加到同一个工作簿的历史 sheet 中形成累计台账。
4. 增加密码或只读保护（openpyxl 的 sheet protection），防止成品被误改。

【八、涉及知识点】

- pandas 读取多格式文件、concat 合并与来源标记列
- 列名标准化（全角半角转换 unicodedata、大小写与空白处理）
- 混合类型列的健壮转换与失败计数
- pandas pivot_table 的多维聚合与 margins 合计
- openpyxl 样式对象（Font、PatternFill、Alignment、Border）
- 条件格式：CellIsRule、FormulaRule、DataBarRule、ColorScaleRule
- 内嵌图表：BarChart、LineChart、PieChart 与 Reference 区域绑定
- Excel 序列号日期基准（1899-12-30）与常见日期格式解析
- 文件占用与 PermissionError 的重试处理
- 配置驱动设计：用 JSON 描述报表结构而无需改代码
================================================================================
