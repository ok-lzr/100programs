================================================================================
项目编号：018                    难度等级：★★☆☆☆（小型项目）
项目名称：JSON 格式化与校验器
所属分类：命令行工具 / 文件与文本处理
建议工时：5 ~ 8 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

接口返回一大坨压缩过的 JSON，肉眼根本看不出结构；配置文件少了一个逗号，
报错只给一个字符位置，不知道对应哪一行；两个版本的配置需要比对，用文本 diff 工具
会把整段都标成不同；想从深层嵌套的对象里取出某个字段，又不值得为此写一个脚本。
这些都是日常开发中反复出现的琐碎需求。

本项目提供一个 JSON 处理命令行工具，覆盖四类操作：美化与压缩、语法校验（带精确行列定位）、
JSONPath 风格取值、以及两个 JSON 之间的结构化差异对比。所有功能都基于标准库 json 模块实现，
不依赖任何第三方库，并且对 100 MB 以上的 JSON Lines 文件采用逐行处理，避免内存被吃满。

目标用户是后端与前端开发者、运维与测试人员，以及需要人工核对配置文件的学习者。
工具的安全取向是：默认只输出到标准输出，不修改任何文件；需要原地格式化时必须显式加
--in-place 与 --force，并在写入前自动生成带时间戳的备份。

【二、功能需求清单】

1. 核心功能
   1.1 美化输出：默认以 2 空格缩进重新缩进，保持键的原始顺序；
       --indent N 指定缩进宽度（0 到 8），--indent-tab 使用制表符缩进；
       --sort-keys 按字典序排序键（递归作用于所有层级）；
       --ensure-ascii 控制是否把非 ASCII 字符转义为 Unicode 转义序列，默认不转义。
   1.2 压缩输出：--compact 时使用 separators=(",", ":") 去掉所有非必要空白，
       并保证输出为单行；--compact-lines 为每行一个顶层数组元素（便于阅读超大数组）。
   1.3 语法校验：--validate 只做校验不做转换；成功时输出"合法 JSON，顶层类型 object，
       共 3 个键，最大嵌套深度 4"；失败时输出精确位置：
       "第 7 行第 12 列（字符偏移 96）：Expecting ',' delimiter"。
   1.4 重复键检测：用 object_pairs_hook 检查同一对象内是否存在重复键，
       发现时按路径报告（例如 $.server.port 出现 2 次，取最后一个值）并计入警告；
       加 --strict-keys 时把重复键视为错误，退出码为 3。
   1.5 批量校验：--batch DIR 或 --glob "*.json" 逐个校验目录内文件，
       输出每个文件的通过与否、最大深度与键总数，最后汇总通过率；
       JSON Lines 文件加 --json-lines 时逐行校验并报告出错行号列表。
   1.6 路径取值：--query "$.server.host" 按 JSONPath 风格子集取值，支持：
       根符号 $、点号取键、方括号索引 [0] 与 [-1]、通配 [*] 与 .*、
       递归下降 ..key、数组切片 [1:3]、过滤 [?(@.id==3)]（仅支持等值与不等值比较）。
       结果默认以美化 JSON 输出；--raw 时字符串结果去掉引号直接输出；
       --first 只返回第一个匹配；--count 只输出匹配数量。
   1.7 差异对比：--diff other.json 递归比较两个 JSON，输出差异列表，
       每条形如 "路径 $.db.host：左 'a'，右 'b'"、"路径 $.items 长度：左 3，右 4"、
       "路径 $.flags.new：仅右侧存在"；--diff-only-keys 只比较键的增删，忽略值变化；
       --exit-code 在存在差异时返回退出码 1，便于脚本判断。
   1.8 其它转换：--keys 只输出所有键路径列表；--to-lines 把 JSON 数组拆分为 JSON Lines；
       --from-lines 把 JSON Lines 合并为数组；--minify-stats 输出压缩前后字节数与压缩率。

2. 输入与交互
   2.1 输入可为文件路径或标准输入（--stdin 或管道）；--output FILE 落盘，已存在时不覆盖，
       需加 --force。
   2.2 --in-place 语义为用格式化结果覆盖原文件，必须同时提供 --force，
       且写入前生成原文件名加 .bak_YYYYMMDD_HHMMSS 的备份；写入采用"先写临时文件再 os.replace"
       的原子方式，避免中途失败导致文件残缺。
   2.3 编码处理：读取时按 BOM 识别 utf-8-sig 与 utf-16；无 BOM 时尝试 utf-8，
       失败后尝试 gb18030 并提示"输入疑似非 UTF-8 编码，已按 gb18030 读取"；
       --encoding 可强制指定；输出默认 UTF-8 无 BOM，可用 --out-encoding 修改。
   2.4 --limit 与 --max-depth 用于超大 JSON 的抽样与截断展示。

3. 输出与展示
   3.1 默认输出到标准输出；所有诊断信息（校验结果、警告、统计）写标准错误流，
       保证管道中拿到的始终是干净的 JSON 文本。
   3.2 --color auto/always/never 控制语法高亮，默认 auto（仅在终端且输出为 TTY 时启用），
       高亮使用 ANSI 转义序列，实现方式为手动分词着色，不依赖第三方库。
   3.3 --summary 输出统计块：字节数、行数、顶层类型、键总数、最大深度、
       数组元素总数、字符串总数、数值总数。

4. 异常与边界处理
   4.1 JSON 语法错误时给出 line、column、pos 三个信息，并在 --context N 时额外打印
       出错行前后各 N 行内容并标出错误列位置（用箭头行标出）。
   4.2 空文件、只含空白字符的文件报错"输入为空"并退出码 2。
   4.3 输入含 BOM 时自动去除，不把 BOM 报成语法错误。
   4.4 顶层为字符串或数字的合法 JSON（如 "abc"、42）在校验时判为合法，
       但在 --diff 与 --query 场景下按标量处理，不报错。
   4.5 二进制文件保护：读取前 8 KB 检测到 NUL 字节时拒绝处理并提示可能不是 JSON 文本。
   4.6 数值超出双精度范围（如 1e400）时报错"数值超出可表示范围"并定位到位置；
       超大整数保持 int 精度输出，不转为浮点。
   4.7 JSONPath 表达式语法错误（缺少右括号、非法过滤条件）时给出表达式位置与期望语法，退出码 2。
   4.8 路径无匹配时 --query 输出 null 并以退出码 0 结束（--strict-query 时改为退出码 3）。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库 argparse、json、sys、os、re、io、time、logging、pathlib、
   difflib、dataclasses、typing、collections、shutil、tempfile；禁止使用 jsonpath-ng、
   jmespath、simplejson、orjson、rich 等第三方库，JSONPath 子集必须自行实现。
3. 禁止事项：禁止使用 eval 执行路径表达式或过滤条件（过滤条件用受限的解析器处理，
   只允许 @.字段、数字、字符串与 ==、!= 运算符）；禁止把整个 JSON Lines 大文件读入内存；
   禁止在未加 --in-place 与 --force 时改写任何文件；禁止在标准输出混入任何日志文本。
4. 代码组织：至少拆分为 loader.py（编码处理、去 BOM、重复键检测、JSON Lines 读取）、
   formatter.py（缩进、排序、压缩、高亮着色）、query.py（JSONPath 子集解析与求值）、
   diff.py（递归差异）、validate.py（校验与位置报告）、cli.py（参数与输出路由）。
   query 与 diff 必须与 I/O 解耦，只操作内存中的 Python 对象以便单元测试。
5. 编码规范：类型注解与 docstring 齐全；路径表达式在解析阶段一次性编译为操作序列
   （list[tuple[str, ...]]），求值阶段只做遍历；异常类型自定义（如 QuerySyntaxError）
   并携带位置信息。
6. 正确性约束：格式化必须保证"紧凑 JSON 与美化 JSON 解析后完全等价"，
   并用往返用例（美化 → 压缩 → 解析 → 与原始对象比较）自测。

【四、设计要点】

1. 数据结构
   1.1 FormatOptions：字段 indent、use_tab、sort_keys、ensure_ascii、compact、
       compact_lines、color。
   1.2 QueryToken：字段 kind（root / key / index / wildcard / recursive / slice / filter）、
       value；一条表达式编译为 list[QueryToken]。
   1.3 DiffEntry：字段 path（点号或方括号表示的路径）、kind（added / removed / changed /
       type_changed / length_changed）、left、right。
   1.4 ValidationReport：字段 path、ok、error_line、error_col、error_pos、error_msg、
       top_type、key_count、max_depth、duplicate_keys。
   1.5 重复键检测：object_pairs_hook 接收 list[tuple[str, Any]]，遍历时统计同名键，
       命中则记录当前路径（路径通过一个显式的路径栈维护）。

2. 关键算法或流程
   2.1 编码读取：以二进制读取，先看 BOM；解码失败时尝试 gb18030；解码成功后用
       json.loads(s, object_pairs_hook=...) 解析，捕获 JSONDecodeError 取其 lineno、
       colno、pos 字段。
   2.2 错误上下文展示：把原始文本按行切分，取 lineno 前后各 N 行，
       在错误行下方输出一行由空格与 "^" 组成的指示行，长度与列号对应。
   2.3 递归下降解析 JSONPath：用正则分词器切分 "$"、"."、".."、"["、"]"、"*"、"数字"、
       "字符串"、":"、"?"、"("、")"、运算符；再按顺序生成 token 列表并校验括号配对。
   2.4 求值：维护当前节点列表（初值为 [root]）；每遇到一个 token 就展开为新节点列表；
       recursive 下降用迭代式深度优先收集所有同名键；filter 对每个对象求值条件。
   2.5 递归差异：对 dict 比较键集合的增删，对共同键递归；对 list 比较长度并按索引递归
       （短的一侧越界即视为 added 或 removed）；对标量比较类型与值，
       类型不同记为 type_changed 并同时给出两侧类型名。
   2.6 深度统计：递归遍历时传递当前深度，取最大值；键总数与数组元素总数在同一遍遍历中累计。
   2.7 压缩率统计：比较原文本字节数与输出字节数，输出"压缩前 12480 字节，压缩后 6120 字节，
       压缩率 51.0%"。

3. 接口或命令设计
   3.1 python json_formatter.py config.json --indent 4 --sort-keys
   3.2 python json_formatter.py big.json --compact > min.json
   3.3 python json_formatter.py --validate bad.json --context 2
   3.4 python json_formatter.py data.json --query "$.users[*].name" --raw
   3.5 python json_formatter.py a.json --diff b.json --exit-code
   3.6 核心函数签名：load_json(path, encoding=None) -> tuple[Any, ValidationReport]；
       compile_query(expr: str) -> list[QueryToken]；evaluate(root, tokens) -> list[Any]；
       diff_json(left, right, path="$") -> list[DiffEntry]。

【五、运行方式与示例】

1. 安装与运行：无需安装依赖，执行 python json_formatter.py --help 查看全部参数。
2. 示例一（美化）：
   输入：python json_formatter.py compact.json --indent 4 --sort-keys
   输出：{
             "b": 2,
             "a": {"x": 1}
         }
3. 示例二（校验失败并显示上下文）：
   输入：python json_formatter.py --validate broken.json --context 1
   输出（stderr）：第 6 行第 9 列（字符偏移 84）：Expecting ',' delimiter
         第 5 行：  "name": "demo",
         第 6 行：  "port": 8080
                        ^
         第 7 行：}
         退出码 2
4. 示例三（路径取值）：
   输入：python json_formatter.py api.json --query "$.data.items[*].title" --raw
   输出：第一篇文章
         第二篇文章
5. 示例四（递归下降与计数）：
   输入：python json_formatter.py api.json --query "$..id" --count
   输出：3
6. 示例五（差异对比）：
   输入：python json_formatter.py old.json --diff new.json --exit-code
   输出：路径 $.server.port：左 8080，右 9090
         路径 $.flags.debug：仅右侧存在
         共 2 处差异，退出码 1
7. 示例六（重复键）：
   输入：python json_formatter.py dup.json --validate --strict-keys
   输出（stderr）：警告：路径 $.server.port 出现 2 次，取最后一个值
         校验失败：存在重复键（严格模式），退出码 3
8. 示例七（原地格式化）：
   输入：python json_formatter.py messy.json --indent 2 --in-place --force
   输出：已写入 messy.json，备份 messy.json.bak_20240301_101500，退出码 0

【六、验收标准】

[ ] 1. 对压缩 JSON 执行美化后再压缩，解析结果与原对象完全相等。
[ ] 2. --indent 4 时每层缩进为 4 个空格，--indent-tab 时使用制表符。
[ ] 3. --sort-keys 递归作用于所有层级，输出键按字典序排列。
[ ] 4. 默认输出中文不被转义，--ensure-ascii 时中文变为 \u 转义序列。
[ ] 5. --compact 输出为单行且不含空格，--compact-lines 每个数组元素一行。
[ ] 6. 校验合法文件时输出顶层类型、键总数与最大嵌套深度，退出码 0。
[ ] 7. 校验非法文件时行列号与实际错误位置一致，--context 输出的指示箭头指向错误列。
[ ] 8. 含 BOM 的文件被正确解析，不报语法错误。
[ ] 9. --query "$.a.b[0]"、"[*]"、"$..name"、"[-1]"、"[1:3]" 五种表达式结果符合预期。
[ ] 10. --query 表达式缺少右括号时报语法错误并退出码 2，不抛未捕获异常。
[ ] 11. --diff 能识别键增删、值变化、类型变化与数组长度变化四类差异。
[ ] 12. 两个完全相同的文件 --diff 输出空并返回退出码 0。
[ ] 13. 重复键在默认模式下给出警告但退出码为 0，--strict-keys 时退出码为 3。
[ ] 14. --in-place 未加 --force 时拒绝执行；加 --force 后生成备份且新文件可被解析。
[ ] 15. 校验 100 MB 的 JSON Lines 文件时内存占用低于 200 MB，且能列出全部出错行号。

【七、可选扩展】

1. 增加 --schema 模式，用简易 JSON Schema 子集校验类型、必填与取值范围。
2. 增加 --json-pointer 支持 RFC 6901 路径语法，与现有 JSONPath 子集共存。
3. 增加 --to-yaml 与 --from-yaml（仅在标准库范围内自行实现简单子集，不引入 PyYAML）。
4. 增加 --watch 模式，文件变化时自动重新格式化到另一个文件，便于调试配置文件。
5. 增加 --stats-chart 用字符柱状图展示各顶层键占用的字节数。

【八、涉及知识点】

- json 模块高级用法：object_pairs_hook、object_hook、JSONDecodeError 的 lineno/colno/pos
- 递归遍历、路径栈维护与深度统计
- JSONPath 表达式的词法分析与递归下降求值
- 受限表达式求值：避免 eval 的安全解析方法
- 递归差异算法与路径表示（键增删、类型变化）
- ANSI 颜色转义序列与终端 TTY 检测
- 编码与 BOM 处理、二进制文件判定
- 原子写入（临时文件加 os.replace）与备份策略
- 标准输出与标准错误流分离的 CLI 设计原则
================================================================================
