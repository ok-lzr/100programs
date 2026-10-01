================================================================================
项目编号：017                    难度等级：★★☆☆☆（小型项目）
项目名称：CSV 与 JSON 互转工具
所属分类：命令行工具 / 文件与文本处理
建议工时：5 ~ 7 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

CSV 与 JSON 是数据交换中最常见的两种格式，但把一份真实的 CSV 变成 JSON 会遇到一连串
具体问题：从 Excel 导出的文件是 GBK 编码、开头带 BOM；分隔符有时是逗号，有时是分号或制表符；
有的文件用引号包住含逗号的字段，有的文件字段里带换行；表头有重复列名或者干脆缺失；
"007"这种编号被当成数字后会丢掉前导零。反过来把 JSON 转 CSV 也有坑：嵌套对象怎么展开、
数组怎么表示、不同记录字段不一致怎么对齐。

本项目实现一个双向转换命令行工具，把这些细节全部处理掉，并对超过内存的大文件采用
流式读写：CSV 逐行读取，JSON 逐条写出，内存占用不随文件增长。

目标用户是需要把数据库导出结果交给前端使用的人、做数据清洗准备的人、
以及需要在 Excel 与程序之间来回搬运数据的普通用户。工具只读写用户指定的文件，
不修改输入文件；需要原地改写时必须显式开启并自动留备份。

【二、功能需求清单】

1. 核心功能
   1.1 CSV 转 JSON：读取 CSV 首行作为字段名，逐行生成 JSON 对象；
       输出形式可选 --array（默认，输出一个 JSON 数组）与 --json-lines（每行一个独立对象，
       首尾无逗号与方括号，适合流式下发）。
   1.2 JSON 转 CSV：接受 JSON 数组、JSON Lines 与单个对象三种输入；
       字段并集作为表头，缺失字段填空字符串；默认按首次出现顺序排列字段，
       --sort-columns 改为字典序。
   1.3 类型推断：--infer-types 时把纯数字字符串转为 int 或 float、把 true/false 转为布尔、
       把 null 与空串转为 None；严格规则如下：只含数字与可选符号的转为整数；
       符合小数格式且能无损往返的转为浮点；带前导零的纯数字（如 007、0755）
       一律保持字符串；超出 2 的 53 次方的整数保持字符串以避免精度丢失。
       禁止使用 eval，数值转换只允许 int()、float() 与显式正则校验。
   1.4 嵌套结构处理：JSON 转 CSV 时，嵌套对象用点号路径展平（user.name、user.age），
       数组默认用分号连接的字符串表示；--flatten-sep 可自定义分隔符；
       --max-flatten-depth 限制展平深度（默认 5），超深结构整体序列化为紧凑 JSON 字符串。
   1.5 编码探测与处理：按 BOM 判断 utf-8-sig、utf-16-le、utf-16-be；
       无 BOM 时按 utf-8、gb18030、cp1252 顺序试解码，以"能完整解码且不出现大量替换字符"
       为判定条件；--encoding 可强制指定；--errors strict/replace/ignore 控制错误策略；
       输出编码由 --out-encoding 指定，默认 utf-8 无 BOM。
   1.6 分隔符嗅探：使用 csv.Sniffer 从文件前 8 KB 推断分隔符与是否含表头，
       置信度不足时回退到逗号并给出提示；--delimiter ";" 与 --no-header 可人工覆盖。
   1.7 引号与换行：读写均使用 csv 模块并显式设置 newline=""，支持字段内换行、
       引号转义与 QUOTE_MINIMAL 策略；--quoting all/minimal/nonnumeric 可选。
   1.8 表头处理：重复列名自动追加 _2、_3；--no-header 时自动生成 column_1、column_2……
       作为字段名；--columns 可显式指定字段列表，未在列表中的列被忽略。
   1.9 流式大文件：--stream 强制逐行处理；--chunk-rows N（默认 10000）控制每次写出的批量，
       处理过程中向标准错误流打印进度（已处理行数与速率）。
   1.10 批量转换：--batch 可将目录内所有 .csv 或 .json 文件按同一参数逐个转换到 --outdir。

2. 输入与交互
   2.1 方向由参数决定：--to-json 与 --to-csv 二选一，二者同时出现时参数校验失败。
   2.2 输入源可为文件路径或标准输入（--stdin 或直接管道）；输出默认写标准输出，--output FILE 落盘。
   2.3 --output 指向已存在文件时不覆盖，需加 --force；--in-place 只对单文件模式有效，
       语义为覆盖输入文件，必须加 --force 才会开启，且在写入前自动生成
       原文件名加 .bak_YYYYMMDD_HHMMSS 的备份。
   2.4 --limit N 只转换前 N 条记录，便于快速抽样检查。
   2.5 --pretty 控制 JSON 缩进（默认 2），--indent 0 表示紧凑输出；
       --ensure-ascii 控制是否转义非 ASCII 字符，默认不转义（直接写中文）。

3. 输出与展示
   3.1 转换完成后向标准错误流打印一行统计：输入行数、输出记录数、字段数、耗时、
       输入编码、嗅探得到的分隔符。
   3.2 --json-report 输出结构化统计，便于自动化流程收集。
   3.3 错误信息包含文件名、行号与列号（来自 csv.Error 与 json.JSONDecodeError 的位置信息）。

4. 异常与边界处理
   4.1 输入文件不存在、为空文件、或只有表头没有数据行时分别给出明确提示；
       空文件与只有表头的情况退出码为 0，结果为空数组或空文件。
   4.2 二进制文件保护：读取前 8 KB 检测到 NUL 字节即判定为二进制并拒绝处理，
       提示可能不是 CSV 或 JSON；--force-binary 可强制按 latin-1 处理。
   4.3 某行列数与表头不一致时，多出的列丢弃并累计警告，缺少的列补空字符串；
       单行错误不中断整个文件，最多报告前 20 条警告。
   4.4 JSON 输入不是数组也不是对象（例如是裸字符串或数字）时报错并退出码 2。
   4.5 JSON Lines 输入中某一行解析失败时记录行号并跳过，最终以退出码 3 报告存在错误行。
   4.6 CSV 写出的字段包含分隔符、引号或换行时自动加引号转义，不得产生歧义列。
   4.7 --in-place 写回失败（磁盘满或权限不足）时保留备份文件并提示恢复方法。
   4.8 输出目标与输入文件相同但未加 --force 时拒绝执行，避免误覆盖。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库 argparse、csv、json、sys、os、io、re、time、logging、
   pathlib、codecs、dataclasses、typing、collections、itertools、glob、shutil；
   禁止使用 pandas、openpyxl、chardet、chardet 替代品等第三方库（编码探测必须自行实现）。
3. 禁止事项：禁止使用 eval 或 pickle 解析输入；禁止把整个大文件读入内存（除显式 --limit
   的小文件抽样外，必须使用流式迭代器）；禁止修改输入文件内容（--in-place 除外，
   且必须先生成备份）；禁止静默丢弃数据行（丢弃必须计入警告统计）。
4. 代码组织：至少拆分为 encoding.py（编码探测）、reader.py（csv/json 读取器）、
   writer.py（csv/json 写出器）、transform.py（类型推断与结构展平）、cli.py（参数与统计输出）。
   读取器与写出器都必须以迭代器（生成器）形式提供数据，禁止返回完整列表。
5. 编码规范：类型注解与 docstring 齐全；所有 I/O 打开文件时显式指定 encoding 与 newline；
   使用 with 语句管理文件句柄；日志不打印整行数据（避免泄露与刷屏），只打印行号与简短原因。
6. 正确性约束：必须写自测用例覆盖"CSV 转 JSON 再转回 CSV"的往返一致性，
   对含引号、含换行、含前导零、含中文的字段全部保持一致。

【四、设计要点】

1. 数据结构
   1.1 CsvOptions：字段 delimiter、quotechar、quoting、has_header、encoding、
       errors、columns、allow_extra（多余列策略）。
   1.2 JsonOptions：字段 indent、ensure_ascii、sort_keys、json_lines、infer_types、
       flatten、flatten_sep、max_flatten_depth。
   1.3 ConversionStats：字段 input_path、output_path、rows_read、rows_written、fields、
       warnings、encoding_detected、delimiter_detected、elapsed_ms。
   1.4 展平函数输出统一为 dict[str, str | int | float | bool | None]，
       键为点号路径；数组与非展平对象用 json.dumps(..., ensure_ascii=False) 字符串表示。

2. 关键算法或流程
   2.1 编码探测：先读前 4 字节判断 BOM；无 BOM 时依次尝试 utf-8（严格模式），
       失败后尝试 gb18030，再尝试 cp1252；每种编码只解码前 64 KB 做试探，
       统计替换字符比例，选择第一个成功且替换字符少于 1% 的候选。
   2.2 分隔符嗅探：抽取前 8 KB 文本，用 csv.Sniffer().sniff 获取候选分隔符，
       若抛 csv.Error 则统计逗号、分号、制表符、竖线四种候选在行内出现次数的一致性，
       选择各行出现次数相同且大于 0 的候选；全部失败时回退逗号。
   2.3 CSV 到 JSON：用 csv.reader 逐行读取；首行作为字段名并做去重；
       每行映射为 dict；--infer-types 时对每个值调用 infer_value；
       写出时逐条 dump，数组模式需要手动写左方括号、逗号分隔与右方括号，保证流式。
   2.4 JSON 到 CSV：输入为数组时用 json.load 的流式替代方案——
       优先按 JSON Lines 逐行解析；对标准数组，用 json.JSONDecoder().raw_decode
       配合游标扫描逐条解析，避免整体载入；收集前 --chunk-rows 条记录确定字段并集后
       写出表头，后续新字段追加到表头之后的行？该情况必须禁止：
       要求先完整扫描一次字段并集，或用 --columns 显式指定字段以避免二次扫描。
   2.5 类型推断：整数用 ^[+-]?(0|[1-9]\d*)$ 匹配（前导零因此天然被排除）；
       浮点用 ^[+-]?(\d+\.\d*|\.\d+)([eE][+-]?\d+)?$ 匹配；
       布尔只接受小写的 true 与 false；null 只接受 null；其余保留字符串。
   2.6 展平：递归遍历 dict，遇到嵌套 dict 拼接点号路径；遇到 list 时序列化为字符串；
       达到最大深度后整体 json.dumps。

3. 接口或命令设计
   3.1 python csv_json.py --to-json data.csv --json-lines --infer-types
   3.2 python csv_json.py --to-csv data.json --sort-columns --flatten-sep "_" --output out.csv
   3.3 python csv_json.py --to-json semicolon.csv --delimiter ";" --encoding gbk --force
   3.4 python csv_json.py --to-csv --stdin --columns "id,name,amount" > out.csv
   3.5 核心函数签名：detect_encoding(head_bytes: bytes) -> str；
       iter_csv_rows(path: Path, opts: CsvOptions) -> Iterator[dict[str, str]]；
       write_json_stream(rows: Iterable[dict], out, opts: JsonOptions) -> ConversionStats。

【五、运行方式与示例】

1. 安装与运行：无需安装依赖，执行 python csv_json.py --help 查看全部参数。
2. 示例一（GBK 的 CSV 转 JSON Lines）：
   输入：python csv_json.py --to-json 销售.csv --json-lines --infer-types
   输出：{"订单号":"007","金额":1299,"城市":"北京"}
         {"订单号":"008","金额":88.5,"城市":"上海"}
         （stderr）已转换 2 行，字段 3 个，输入编码 gb18030，分隔符 ","，耗时 0.01 s
3. 示例二（JSON 数组转 CSV 并展平）：
   输入：python csv_json.py --to-csv users.json --output users.csv
   输出（users.csv 内容）：id,name,user.name,user.age,tags
                           1,张三,张三,28,"a;b"
         （stderr）已转换 1 条记录，字段 5 个
4. 示例三（分号分隔 + 显式编码）：
   输入：python csv_json.py --to-json export.csv --delimiter ";" --encoding gbk --limit 5
   输出：前 5 条记录的 JSON 数组（缩进 2），中文不转义
5. 示例四（原地改写需备份）：
   输入：python csv_json.py --to-csv data.json --in-place --force
   输出：已写入 data.json，备份为 data.json.bak_20240301_101500，退出码 0
6. 示例五（二进制文件被拒绝）：
   输入：python csv_json.py --to-json photo.jpg
   输出（stderr）：错误：photo.jpg 前 8 KB 含 NUL 字节，判定为二进制文件，已拒绝处理，退出码 2
7. 示例六（列数不一致）：
   输入：python csv_json.py --to-json messy.csv
   输出（stderr）：警告：第 4 行有 5 列，多于表头的 4 列，多余列已丢弃；
         共 2 条警告；结果仍正常输出，退出码 0

【六、验收标准】

[ ] 1. 含中文的 GBK CSV 文件能被正确探测编码并转换为可读 JSON。
[ ] 2. 带 UTF-8 BOM 的文件转换后输出不含 BOM 与多余的 \ufeff 字符。
[ ] 3. 分隔符为分号、制表符的 CSV 在不加 --delimiter 时也能被正确嗅探。
[ ] 4. "007" 在 --infer-types 下仍输出字符串 "007"，不变成 7。
[ ] 5. 超过 2 的 53 次方的大整数保持字符串输出，不发生精度丢失。
[ ] 6. 字段内含逗号、引号、换行的 CSV 往返转换后内容完全一致。
[ ] 7. JSON 数组转 CSV 时嵌套对象被展平为点号路径列，数组以分号连接。
[ ] 8. --json-lines 输出每行都是独立合法 JSON，可被逐行 json.loads 解析。
[ ] 9. 空文件输入时输出为空数组，程序退出码为 0 且不抛异常。
[ ] 10. 二进制文件（含 NUL 字节）在未加 --force-binary 时被拒绝，退出码为 2。
[ ] 11. --in-place 未加 --force 时拒绝执行，加 --force 后生成 .bak 备份文件。
[ ] 12. 处理 100 万行的 CSV 时进程内存占用稳定在 200 MB 以内（验证流式读写）。
[ ] 13. --sort-columns 时输出 CSV 表头按字典序排列，数据列与表头一一对应。
[ ] 14. 重复表头被改写为 name、name_2，转换结果无字段覆盖丢失。
[ ] 15. 输出的 CSV 在 Excel 中打开时中文不乱码（UTF-8 或指定编码正确）。

【七、可选扩展】

1. 增加 --to-ndjson-split 把大数组拆分为每 1 万条一个的小文件，便于分批上传。
2. 增加 --schema schema.json 校验，在转换时按字段类型与是否必填做数据质量检查。
3. 增加 --csv-to-sqlite 把 CSV 直接导入 SQLite 表，表结构由列名与推断类型生成。
4. 增加 --diff 模式，比较两个 CSV 文件的行级差异并输出新增、删除与修改的行。
5. 增加 --progress-bar 使用纯文本进度条展示大文件处理进度（不依赖第三方库）。

【八、涉及知识点】

- csv 模块：reader、writer、Dialect、Sniffer、quoting 策略与 newline="" 的必要性
- json 模块：dump、load、JSONDecoder.raw_decode 与流式解析思路
- 字符编码与 BOM：utf-8-sig、utf-16、gb18030 的差异与探测方法
- 类型推断的边界：前导零、大整数精度、布尔与 null 的字面量
- 生成器与迭代器管道，内存友好的流式 I/O
- 嵌套结构的展平与点号路径表示
- 二进制与文本文件的判定（NUL 字节检测）
- 备份、原子写入与幂等覆盖的工程做法
- argparse 互斥参数组与统计信息输出到标准错误流的惯例
================================================================================
