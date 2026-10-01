================================================================================
项目编号：069                    难度等级：★★★★☆（中型项目）
项目名称：数据清洗与质量报告流水线
所属分类：数据分析工程 / 数据治理
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：无（仅标准库）；可选校验器使用 pandas
================================================================================

【一、项目背景与目标】

拿到一份从业务系统导出的 CSV，第一件事通常不是分析，而是清理：有的行整列缺失、有的日期写成
“2024/13/45”、有的手机号是 11 位数字夹着字母、有的订单在同一天重复导入了两次。如果直接把这些
脏数据丢给报表或模型，结论一定是错的。本项目把清洗工作做成一条有配置、有日志、有报告的流水线，
让每一次清洗都可复现、可审计。

目标用户是做数据分析与数据治理的开发者、需要定期清洗业务导出数据的运营人员。做成之后，
输入一个原始 CSV 与一份规则 JSON，就能得到：清洗后的干净数据、被剔除或修正的记录明细、
每个字段的质量得分与整表质量报告（Markdown 格式），并且同样的输入和规则永远得到同样的输出。

本项目的核心实现仅使用标准库（csv、json、re、datetime、unicodedata、decimal、statistics、
hashlib、argparse、logging），不依赖 pandas 也能跑通全流程；另提供一个可选的 pandas 校验器
实现对同一规则做交叉验证。项目全程离线运行，不上传任何数据；报告中默认对敏感字段做脱敏
（手机号只保留后 4 位，身份证只保留前 6 位与后 4 位），原始数据文件不做原地修改。

【二、功能需求清单】

1. 核心功能
   1.1 输入输出：读取 CSV（自动探测编码 UTF-8/UTF-8-BOM/GBK，自动探测分隔符 , ; \t |），
       输出清洗后 CSV（UTF-8 with BOM）、清洗日志 CSV（每一条被修改/删除的记录）、
       质量报告 Markdown、以及可选的 SQLite 落库。
   1.2 缺失值处理：按字段配置策略，可选 keep（保留）、drop_row（删除该行）、
       fill_const（填固定值）、fill_mean/fill_median（数值列填充统计值）、forward_fill（用上一行同字段值填充）；
       所有动作都要在日志中记录原值与填充值。
   1.3 异常值处理：数值字段支持三种检测法，分别是标准差法（|x - mean| > k * std，默认 k = 3）、
       IQR 法（x < Q1 - 1.5 * IQR 或 x > Q3 + 1.5 * IQR）、固定区间法（min/max）；
       处理动作可选 flag（只标记）、clip（截断到边界）、nullify（置为空）、drop_row（删除）。
   1.4 重复值处理：支持按全字段判重与按子集字段判重；保留策略可选 first、last、
       most_complete（非空字段最多的一条）、aggregate（对指定数值列求和合并）；
       记录被删除的重复行及其与保留行的主键关系。
   1.5 规则校验：支持字段级规则，包括 not_null、unique、type（int/float/date/decimal/str）、
       range（数值区间）、length（字符串长度区间）、regex（正则）、enum（取值集合）、
       date_range、cross_field（如 结束日期 >= 开始日期）；
       校验失败的行默认写入错误清单，超过错误率阈值（默认 20%）时流水线整体失败。
   1.6 字段标准化：文本去首尾空白、全角转半角、连续空白合并为一个空格；手机号去掉分隔符；
       金额去千分位与货币符号后转 Decimal；日期识别 8 种常见写法并统一输出 YYYY-MM-DD。
   1.7 质量报告：输出每个字段的总行数、非空数、非空率、唯一值数、类型违规数、范围违规数、
       修正数、删除数，并给出该字段的质量分（0~100，按违规比例线性扣分）与整表质量等级
       （A：>= 95，B：>= 85，C：>= 70，D：< 70）。
   1.8 规则集版本化：规则文件带 version 与 hash，报告头部记录规则版本与输入文件哈希（sha256），
       保证“同样的输入 + 同样的规则”可复现同样的结果。
2. 输入与交互
   2.1 命令行：--input 输入 CSV；--rules 规则 JSON；--out 输出目录（默认 ./output）；
       --out-sqlite 可选落库；--sample 只处理前 N 行（调试）；--dry-run 只出报告不改数据；
       --report-only；--log-level。
   2.2 支持 --profile 参数：只做数据画像（行数、列数、类型推断、缺失率、唯一值 TOP 5），
       输出 profile.md，用于写规则前先看数据长什么样。
   2.3 规则文件格式为 JSON，字段顺序与执行顺序一致，禁止在规则中使用任何可执行表达式。
3. 输出与展示
   3.1 output/clean.csv：清洗结果。
   3.2 output/changes.csv：字段名、行号、主键、动作、原值、新值、原因。
   3.3 output/errors.csv：规则校验失败明细。
   3.4 output/quality_report.md：质量报告（含字段统计表、规则命中统计、扣除项说明）。
   3.5 控制台打印各阶段进度与耗时，最后打印“输入 N 行 → 输出 M 行，修正 X 处，删除 Y 行”。
4. 异常与边界处理
   4.1 输入文件不存在、为空或只有表头时，报错退出（退出码 2），不生成结果文件。
   4.2 规则引用了不存在的字段时，启动阶段即报错并列出可用字段名。
   4.3 同一字段配置了冲突策略（如既 drop_row 又 fill_const）时拒绝启动并指出冲突配置项。
   4.4 统计类填充（mean/median）在样本数为 0 时退化为 keep 并记录警告，不抛异常。
   4.5 标准差为 0（所有值相同）时标准差法不标记任何异常值，避免全部被判定为异常。
   4.6 IQR 法在四分位数相等时同样跳过检测并记录说明。
   4.7 数值转换失败（如“壹佰元”）不静默丢弃，按该字段配置的 invalid_action 处理
       （默认 flag 并保留原值文本）。
   4.8 --dry-run 时不写入 clean.csv，但 changes.csv 与 quality_report.md 照常生成，
       并在报告头部标注“试运行”。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用类型注解与 dataclass。
2. 允许使用的库：核心流水线仅使用标准库（csv、json、re、datetime、unicodedata、decimal、
   statistics、hashlib、sqlite3、argparse、logging、pathlib、collections、random、io）；
   可选的 pandas 校验器放在 validators_pandas.py 中，缺失时自动跳过并在日志中提示。
3. 禁止事项：禁止使用 eval/exec 解释规则；禁止原地修改或删除输入文件；禁止把数据写入日志正文
   （只记录字段名、行号、动作与脱敏后的值）；禁止引入网络请求；禁止在报告中输出完整手机号、
   身份证号与银行卡号。
4. 代码组织：models.py（FieldRule、PipelineConfig、ChangeRecord、FieldStats）、
   reader.py（编码与分隔符探测、流式读取）、normalizer.py（文本/数值/日期标准化）、
   missing.py、outliers.py、dedupe.py、rules_engine.py（规则校验与 cross_field）、
   profiler.py、reporter.py（质量报告）、writer.py（CSV 与 SQLite 输出）、pipeline.py（阶段编排）、
   cli.py。
5. 编码规范：流水线按阶段串行执行，每个阶段接收并返回行列表与统计对象，禁止在阶段函数中直接
   写文件；所有决策必须记录到 ChangeRecord；内存受限时使用生成器逐行处理（--stream 模式）；
   数值计算统一使用 Decimal（如涉及金额）或 float（其他统计量）并注明口径；
   日志使用 logging，非法数据定位到行号与列名。
6. 测试要求：normalizer 的日期与数值解析、outliers 的三种检测法、dedupe 的四种保留策略、
   rules_engine 的 cross_field 校验四部分必须有 pytest 用例；边界用例需覆盖“标准差为 0”
   “IQR 为零”“空表”“全为缺失值”的场景；测试数据全部内联在测试文件中，不依赖外部文件。

【四、设计要点】

1. 数据结构
   1.1 FieldRule：name(str)、type(str)、required(bool)、missing(str)、invalid_action(str)、
       outlier(dict|None，含 method、k、min、max、action)、patterns(list[str])、
       enum(list[str]|None)、min_length(int|None)、max_length(int|None)、date_format(str)、
       mask(bool，是否在报告中脱敏)。
   1.2 PipelineConfig：version(str)、primary_key(str|None)、delimiter(str|None)、encoding(str|None)、
       fields(list[FieldRule])、dedupe(dict|None，含 subset、keep、aggregate)、
       error_rate_limit(float，默认 0.2)、null_tokens(list[str]，默认 ["", "NA", "N/A", "null", "NULL",
       "-", "无", "未知"])。
   1.3 ChangeRecord：row_index(int)、primary_key(str)、field(str)、action(str)、
       old_value(str)、new_value(str)、reason(str)。
   1.4 FieldStats：field(str)、total(int)、non_null(int)、null_rate(float)、unique(int)、
       type_errors(int)、range_errors(int)、fixed(int)、dropped(int)、score(int)。
   1.5 行内表示：每一行统一为 dict[str, str]，所有阶段输入输出都使用该结构，
       保证可流式处理与可序列化。
2. 关键算法或流程
   2.1 阶段顺序（固定）：读取 → 文本标准化 → 类型转换 → 缺失值处理 → 异常值处理 →
       去重 → 规则校验 → 交叉字段校验 → 输出与报告。顺序不可调换，因为去重依赖已标准化的值。
   2.2 异常值检测：
       标准差法：mean = statistics.fmean(values)，std = statistics.pstdev(values)；
       std == 0 时跳过；否则 |x - mean| > k * std 判定为异常。
       IQR 法：排序后取 Q1 = 位置 (n-1)*0.25 的线性插值值，Q3 = (n-1)*0.75 的插值值；
       IQR = Q3 - Q1；IQR == 0 时跳过；否则 x < Q1 - 1.5*IQR 或 x > Q3 + 1.5*IQR 判定为异常。
   2.3 去重实现：用 dict 以判重键为 key 保存行索引；keep = first 保留首个出现，
       last 覆盖为最新，most_complete 比较非空字段数（相同则保留首个），
       aggregate 对配置的数值列求和并把该组的行合并为一条（其余字段取首个非空值）。
   2.4 质量分计算：score = round(100 * (1 - (type_errors + range_errors + dropped) /
       max(total, 1)))，分数下限 0；字段分加权（必填字段权重 1.5）后得到整表得分。
   2.5 可复现性：报告头部写入 input_sha256（对输入文件字节求 sha256）、rules_hash
       （对规则 JSON 规范化后求 sha256）与 pipeline_version，便于比对两次运行是否等价。
3. 接口或命令设计
   3.1 命令行：
       python main.py --input raw_orders.csv --rules orders_rules.json --out ./output
       python main.py --input raw_orders.csv --profile --out ./output
       python main.py --input raw_orders.csv --rules orders_rules.json --dry-run --sample 5000
       python main.py --input raw_orders.csv --rules orders_rules.json --out-sqlite ./output/clean.db
   3.2 关键函数签名：
       def detect_encoding(path: Path, sample_bytes: int = 65536) -> str
       def normalize_row(row: dict[str, str], rules: dict[str, FieldRule]) -> tuple[dict, list[ChangeRecord]]
       def detect_outliers(values: list[float], method: str, k: float, q1: float, q3: float) -> set[int]
       def dedupe_rows(rows: list[dict], subset: list[str], keep: str) -> tuple[list[dict], list[ChangeRecord]]
       def validate_row(row: dict, rules: dict[str, FieldRule]) -> list[str]
       def build_quality_report(stats: list[FieldStats], meta: dict) -> str
   3.3 rules JSON 片段：
       {"version": "1.2", "primary_key": "order_id",
        "null_tokens": ["", "NA", "null", "无"],
        "fields": [
          {"name": "order_id", "type": "str", "required": true, "missing": "drop_row"},
          {"name": "amount", "type": "decimal", "required": true, "missing": "drop_row",
           "outlier": {"method": "iqr", "action": "clip"}, "min": 0, "max": 1000000},
          {"name": "phone", "type": "str", "regex": "^1[3-9]\\\\d{9}$", "mask": true,
           "invalid_action": "nullify"},
          {"name": "order_date", "type": "date", "date_format": "%Y-%m-%d", "required": true},
          {"name": "status", "type": "str", "enum": ["待付款", "已付款", "已发货", "已完成", "已取消"]}],
        "dedupe": {"subset": ["order_id"], "keep": "most_complete"},
        "cross_field": [{"rule": "ship_date >= order_date", "message": "发货日期早于下单日期"}]}

【五、运行方式与示例】

安装依赖：无。直接使用标准库运行，无需安装任何第三方包。
   （可选：pip install pandas 以启用 validators_pandas.py 的交叉校验）

运行示例一（数据画像）：
   python main.py --input raw_orders.csv --profile --out ./output
   输出：
   [INFO] 探测编码 utf-8，分隔符 ','，共 50000 行 12 列
   [INFO] 字段 order_id：非空率 100.0%，唯一值 49980（疑似重复 20）
   [INFO] 字段 amount：类型推断 decimal，缺失 132 行，最大值 9999999.99（疑似异常）
   [INFO] 画像报告已生成：output/profile.md

运行示例二（正式清洗）：
   python main.py --input raw_orders.csv --rules orders_rules.json --out ./output
   输出：
   [INFO] 读取 50000 行，规则版本 1.2
   [INFO] 缺失值处理：amount 填充中位数 128.50（132 处），phone 置空（18 处）
   [INFO] 异常值处理：amount 使用 IQR 法命中 246 处，动作 clip 到 0 ~ 9999999.99
   [INFO] 去重：按 order_id 删除 20 行（保留 most_complete）
   [INFO] 规则校验：status 枚举违规 37 行，order_date 格式违规 5 行，错误率 0.08% 未超阈值
   [INFO] 输出 49980 行 -> output/clean.csv；变更记录 453 条 -> output/changes.csv
   [INFO] 质量报告已生成：output/quality_report.md，整表等级 A（96 分）

运行示例三（试运行与抽样）：
   python main.py --input raw_orders.csv --rules orders_rules.json --dry-run --sample 5000
   输出：
   [INFO] 试运行模式：不写出 clean.csv
   [INFO] 抽样 5000 行完成，预计全量变更 512 条
   [INFO] 质量报告头部已标注“试运行 / 抽样 5000 行”

异常示例一（规则字段不存在）：
   python main.py --input raw_orders.csv --rules bad_rules.json
   输出：
   [ERROR] 规则引用了不存在的字段：ship_date（可用字段：order_id, amount, phone, order_date, status）
   [ERROR] 流水线未启动（退出码 2）

异常示例二（错误率超阈值）：
   python main.py --input dirty.csv --rules orders_rules.json
   输出：
   [ERROR] 规则校验错误率 31.4% 超过阈值 20%
   [ERROR] 已生成 errors.csv 与质量报告，未输出 clean.csv（退出码 5）

【六、验收标准】

[ ] 能正确识别 UTF-8、UTF-8 with BOM、GBK 三种编码的输入文件
[ ] 能自动识别 , ; \t | 四种分隔符并在日志中打印识别结果
[ ] null_tokens 中定义的 "NA"、"无" 等被统一识别为缺失值
[ ] 全角字符与首尾空白在文本标准化阶段被正确处理
[ ] 8 种常见日期写法均能解析并统一输出 YYYY-MM-DD，非法日期按 invalid_action 处理
[ ] fill_mean/fill_median 的填充值与 statistics 手工计算结果一致
[ ] IQR 检测在 IQR 为 0 时跳过并记录说明，不把全部数据标记为异常
[ ] 标准差法在标准差为 0 时不产生任何异常标记
[ ] clip 动作把超出边界的值截断到边界，nullify 置空，drop_row 删除整行，三者在 changes.csv 中可区分
[ ] 四种去重保留策略的结果与预期一致（用 6 行构造数据可手工核对）
[ ] cross_field 规则能识别“发货日期早于下单日期”并写入 errors.csv
[ ] changes.csv 中每条记录都含行号、字段名、动作、原值、新值与原因
[ ] quality_report.md 含每字段的非空率、唯一值数、违规数与质量分，并给出整表等级
[ ] 报告中 phone 字段已脱敏为 138 加四个星号加 1234 形式，不含完整号码
[ ] --dry-run 不生成 clean.csv，但 changes.csv 与报告照常生成且标注试运行
[ ] 错误率超阈值时不输出 clean.csv，退出码为 5
[ ] 输入文件在运行前后 sha256 不变，证明未被修改
[ ] 报告头部的 input_sha256 与 rules_hash 与手工计算结果一致
[ ] 同一输入与规则连续运行两次，clean.csv 字节级一致
[ ] pytest 测试全部通过，且不依赖任何外部数据文件

【七、可选扩展】

1. 增加数据契约导出：把规则导出为 JSON Schema 或 Great Expectations 风格的声明，
   供上游系统在产出数据时自检。
2. 增加列级血缘记录：输出 lineage.json，说明每个输出字段由哪些输入字段与规则计算而来。
3. 增加多文件批处理模式：按目录扫描并分别清洗，输出跨文件的汇总质量看板。
4. 增加质量趋势对比：保存历史报告到 SQLite，输出“本月质量分较上月变化”的对比段落。

【八、涉及知识点】

- CSV 编码探测与分隔符嗅探（csv.Sniffer 与手工字节检查）
- 生成器与流式处理在内存受限场景下的应用
- 正则表达式、unicodedata 全角半角转换与文本标准化
- datetime 多格式解析（strptime 与 match 组合）
- decimal.Decimal 与金额精度处理
- statistics 模块的 fmean、median、pstdev 与分位数手工插值
- 异常值检测的统计学原理（标准差法、IQR 法）与退化场景处理
- 去重策略设计与集合/字典的高效使用
- 规则引擎设计：声明式规则、字段级与跨字段校验
- 数据质量度量：非空率、唯一率、违规率与质量评分口径
- 可复现性与审计：哈希记录、版本号与确定性输出
- 敏感数据脱敏原则与日志安全
================================================================================
