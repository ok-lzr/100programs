================================================================================
项目编号：048                    难度等级：★★★☆☆（小型项目）
项目名称：日志解析统计工具
所属分类：命令行工具 / 运维分析
建议工时：5 ~ 7 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

出故障时最耗时的环节往往不是修，而是在几万行日志里找“那一条”。服务器日志格式五花八门：
Nginx 的组合日志、Apache 的 common/combined、Python logging 的默认格式、syslog、
JSON 结构化日志、以及各种自定义格式。用 grep 能筛，但回答不了这些真正有用的问题：
哪个 IP 请求最多、哪个接口 5xx 比例最高、错误在哪个小时突然涨了 10 倍、昨天和今天的错误
种类有什么变化。

本项目做一个纯标准库的日志解析统计工具：通过“格式模板 + 正则自动生成”的方式适配多种日志，
把每行解析成结构化记录，然后输出错误 Top 榜、URL 频次、状态码分布、按小时/分钟的时间趋势
（ASCII 柱状图），并支持与上一次统计结果对比出新增的错误类型。

之所以坚持只用标准库，是因为这个工具要能直接丢到生产服务器上跑，不能因为装不上第三方包而
失效。目标用户是运维、后端开发与需要排查线上问题的技术支持人员。做成之后，它可以在不接入
ELK 的前提下，五分钟内回答“昨晚到底出了什么问题”。

【二、功能需求清单】

1. 核心功能
   1.1 格式模板与自动识别：--format auto 时按行内容特征打分选择解析器（含
       '"GET /path HTTP/1.1"' 判为 nginx/apache；含 "level=INFO" 或 " - INFO - " 判为
       python；以 '{' 开头且能 json.loads 判为 json；含 "sshd[" 或 "<134>" 判为 syslog）。
       --format 也可显式指定 nginx|apache|common|python|syslog|json|custom。
   1.2 模板引擎：--pattern 接受带命名组的正则，如
       '(?P<ip>\S+) - - \[(?P<time>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+) [^"]*"
       (?P<status>\d{3}) (?P<bytes>\d+)'；内置模板以常量形式提供，用户可用 --pattern-file
       从外部文件加载，文件首行为注释说明字段含义。
   1.3 时间解析：支持 nginx 的 "%d/%b/%Y:%H:%M:%S %z"、ISO8601、syslog 的
       "%b %d %H:%M:%S"（缺年份时用 --year 或当前年补全并处理跨年边界）、Python logging 的
       "%Y-%m-%d %H:%M:%S,%f"。全部转成带时区的 datetime，无时区时按 --tz 指定（默认本地）。
   1.4 级别识别：从 time/level/severity/levelname 字段或消息正文的关键词
       （FATAL/ERROR/WARN/WARNING/INFO/DEBUG/TRACE、Exception、Traceback）推断级别，
       输出统一为 ERROR/WARN/INFO/DEBUG/OTHER 五档。
   1.5 统计维度：--group-by ip|path|status|level|hour|minute|method|ua|referer
       （可多选，逗号分隔，最多三个维度组合）；每个维度输出计数、占比、以及首次与末次出现时间。
   1.6 错误提取：--errors 输出 ERROR 及以上级别的记录（最多 --top 条，默认 20），
       按“归一化后的消息模板”聚合（把数字、UUID、IP、十六进制串替换成占位符），
       显示样例与条数，避免同一错误刷屏。
   1.7 时间趋势：--trend hour|minute 输出 ASCII 柱状图（用 # 字符，宽度自适应终端 80 列），
       并计算与上一时段相比的增长率，突增超过 --spike-ratio（默认 3.0）时用 [!!] 标注。
   1.8 结果输出：--output report.txt 写可读报告，--json report.json 写结构化结果，
       --baseline prev.json --diff 对比两次统计，只列出新增/消失的错误模板与数量变化。

2. 输入与交互
   2.1 单文件：python logstat.py access.log --format nginx --group-by ip,status --errors。
   2.2 多文件与目录：--files 'logs/*.log' 或 --dir ./logs --recursive，按文件名排序后合并统计；
       多文件时自动加 source 字段区分来源。
   2.3 标准输入：--stdin 从管道读取，支持 cat a.log | python logstat.py --stdin --format python。
   2.4 实时跟随：--follow 类似 tail -f，持续解析新增行并每 --interval 5 秒刷新一次摘要
       （用 time.sleep 轮询文件大小，记录上次读取偏移量）。
   2.5 --sample 1000 随机抽样行做格式探测与预览，处理大文件时先给结论。

3. 输出与展示
   3.1 概览段：文件 3 个，行数 128432，解析成功 128000（99.66%），失败 432；时间范围
       2025-05-01 00:00:03 ~ 2025-05-01 23:59:58；级别分布 ERROR 214 / WARN 1024 / INFO 126762。
   3.2 排行段：每行 "  1. 192.168.1.23              4120 次   3.22%  最后见 23:59:12"。
   3.3 错误模板段：按次数降序，显示模板、条数、占比与一条原始样例（截断到 160 字符）。
   3.4 趋势段：每小时一行，形如 "14:00 ######################################## 412"。
   3.5 解析失败段：前 5 行原始样例 + 失败原因，并提示可用的 --pattern 调整方向。

4. 异常与边界处理
   4.1 无法识别的行：计入 unparsed 并保留最多 100 条样例（避免内存爆炸），不中断处理。
   4.2 解析成功率低于 --min-parse-rate（默认 80%）时，报告顶部给出醒目警告并建议检查格式。
   4.3 超大文件（GB 级）：逐行流式读取，禁止 readlines()；--max-line-length（默认 65536）
       超长行截断并计数，防止单行吃爆内存。
   4.4 编码问题：默认按 utf-8 打开，失败时用 --encoding gbk|latin-1|errors=replace；
       Windows 中文日志常见 GBK，报告顶部打印实际使用的编码。
   4.5 时间字段缺失或非法：该行仍参与 IP/状态码统计，但不计入时间趋势，单独计数。
   4.6 文件被其他进程占用或读取中报错：捕获 OSError，跳过该文件并记录，其他文件继续。
   4.7 空文件与全空行：明确输出“文件中没有有效日志行”，退出码 0。
   4.8 时间跨度跨年（12 月 31 日到 1 月 1 日）：在 syslog 解析中若下一行月份小于上一行，
       年份自动加 1，并在报告中提示。
   4.9 --follow 时文件被轮转（重命名/删除）：检测 inode 变化后重新打开新文件，记录一条提示。
   4.10 状态码字段非数字（如 "-"）：记为 0 并归入 OTHER，不抛异常。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库——re、argparse、pathlib、collections（Counter、defaultdict、
   deque）、datetime、json、csv、logging、sys、os、gzip（读取 .gz 压缩日志）、glob、
   itertools、dataclasses、statistics。禁止使用 pandas、numpy 等第三方库。
3. 禁止事项：禁止一次性把整文件读入内存；禁止为正则写灾难性回溯的表达式（禁止嵌套量词
   如 (\S+)+）；禁止在网络或磁盘上留下中间文件（除用户指定输出）；禁止默认修改源日志。
4. 代码组织：
   - patterns.py：内置模板常量 NIGNX_PATTERN、APACHE_PATTERN、COMMON_PATTERN、
     PYTHON_PATTERN、SYSLOG_PATTERN，编译后的正则缓存，detect_format(line) -> str。
   - parsers.py：BaseParser 抽象类（parse(line, source) -> LogRecord | None），
     子类 NginxParser、PythonParser、SyslogParser、JsonParser、CustomParser。
   - normalize.py：normalize_message(text) -> str（数字/UUID/IP/路径/十六进制占位化）、
     guess_level(text) -> str、parse_time(text, fmt) -> datetime。
   - stats.py：StatsAccumulator 类，add(record)、top(field, n)、trend(freq)、
     error_templates(top)、spikes(ratio)。
   - render.py：render_text(stats, opts) -> str、render_json(stats) -> dict、
     bar_chart(values, width) 绘制 ASCII 柱状。
   - cli.py：输入源选择（文件/目录/标准输入/follow）、参数解析与输出分发。
5. 编码规范：类型注解完整；LogRecord 用 @dataclass(slots=True) 减少内存；解析器必须对
   任意输入不抛异常（内部 try/except 返回 None）；docstring 说明每个字段的来源与类型；
   报告文本宽度固定 78 列，保证在各种终端下不折行错乱。

【四、设计要点】

1. 数据结构：
   LogRecord：ts(datetime|None)、level(str)、message(str)、template(str)、
   source(str)、line_no(int)、raw(str)、fields(dict[str, str])。
   其中 fields 保存 ip、method、path、status、bytes、ua、referer 等原始字段，
   统一用字符串存，统计时按需转换。
   StatsResult：file_count、line_count、parsed、unparsed、start_time、end_time、
   level_counts(Counter)、groups(dict[str, Counter])、error_templates(Counter)、
   trend(Counter)、unparsed_samples(list[str])、encoding(str)、warnings(list[str])。

2. 关键算法或流程：
   2.1 主流程：确定输入源 -> 逐行读取（文件用 open(encoding=..., errors="replace")，
       .gz 用 gzip.open）-> detect_format（若 auto）-> parser.parse -> StatsAccumulator.add
       -> 结束后 render 输出。
   2.2 消息归一化（错误模板提取）：依次用正则替换——IPv4/IPv6、UUID、
       \b\d+(\.\d+)?\b、0x[0-9a-fA-F]+、长路径、引号内长字符串、时间戳；
       替换后再截断到 200 字符作为模板键；对同一模板保留一条最长的原始样例。
   2.3 级别推断：先看结构化字段；否则按关键词优先级 FATAL > ERROR > WARN > INFO > DEBUG；
       出现 "Traceback (most recent call last)" 视为 ERROR 并把后续缩进行（以空格开头）
       视作同一条错误的续行，合并到上一条记录（用 pending 记录实现）。
   2.4 趋势统计：key 为 ts.strftime("%Y-%m-%d %H:00")（小时）或 "%Y-%m-%d %H:%M"
       （分钟）；按 key 排序输出；缺失的时段补 0，保证甘特图连续。
   2.5 ASCII 柱状图：max_count 归一化到 --chart-width（默认 40）列，
       柱 = "#" * max(1, round(count / max_count * width))；count 为 0 时用 "." 占位。
   2.6 突增检测：对趋势序列计算相邻时段比值，count[i] / max(count[i-1], 1) >= ratio 且
       count[i] >= --min-spike-count（默认 5）时标注 [!!]。
   2.7 差异对比：把 (模板, 级别) 作为键，对比两次统计的 Counter，输出 added、removed、
       increased（超 20%）、decreased 四类。
   2.8 --follow 实现：记录 file.tell() 偏移；每轮循环比较 os.path.getsize 与上次大小，
       增长则 seek(offset) 后 readline 到底；文件 inode 变化（os.stat().st_ino 或
       在 Windows 上用 st_ctime + 大小回退比较）则重新打开。

3. 接口设计：
   python logstat.py [FILES...] [--dir DIR] [--glob 'logs/*.log'] [--recursive]
     [--stdin] [--format auto|nginx|apache|common|python|syslog|json|custom]
     [--pattern REGEX] [--pattern-file FILE] [--encoding utf-8|gbk|latin-1]
     [--year 2025] [--tz Asia/Shanghai]
     [--group-by ip,path,status,level,hour] [--top 20] [--errors]
     [--trend hour|minute] [--chart-width 40] [--spike-ratio 3.0]
     [--min-parse-rate 0.8] [--max-line-length 65536]
     [--output report.txt] [--json report.json] [--baseline prev.json] [--diff]
     [--follow] [--interval 5] [--quiet] [--verbose]
   核心函数：parse_line(line: str, fmt: str, source: str) -> LogRecord | None
             normalize_message(text: str) -> str
             render_text(result: StatsResult, opts: RenderOptions) -> str

【五、运行方式与示例】

1. 无第三方依赖，直接运行：
   python logstat.py --help

2. Nginx 访问日志 Top IP 与状态码：
   python logstat.py access.log --format nginx --group-by ip,status --top 10
   输出：概览：文件 1 个，行数 128432，解析成功 128000 (99.66%)，失败 432
         时间范围：2025-05-01 00:00:03 ~ 2025-05-01 23:59:58
         级别分布：ERROR 214 / WARN 1024 / INFO 126762
         Top IP： 1. 192.168.1.23  4120 次  3.22%  最后见 23:59:12
         Top 状态码： 200 -> 121004 (94.5%)   404 -> 3120 (2.4%)   500 -> 214 (0.2%)

3. 提取错误模板并看趋势突增：
   python logstat.py --dir ./logs --recursive --format python --errors --trend hour
   输出：[!!] 18:00 ######################################## 412
         错误模板 Top3：
         1. 412 次  Connection refused to {ip}:{port}
            样例 2025-05-01 18:12:03,441 ERROR [db] Connection refused to 10.0.0.8:5432
         2. 96 次  Task {uuid} failed after {num} retries
         3. 42 次  Timeout while reading {path}

4. 与昨天的统计对比：
   python logstat.py --glob 'logs/*.log' --json today.json
   python logstat.py --glob 'logs/*.log' --json today.json --baseline yesterday.json --diff
   输出：新增错误模板 2 类：Deadlock detected ...、Disk quota exceeded ...；
         消失 1 类；数量上升超 20% 的有 3 类。

5. 读取压缩日志与标准输入：
   python logstat.py archive/access.log.1.gz --format nginx --group-by path --top 5
   cat app.log | python logstat.py --stdin --format python --errors

6. 异常示例：格式不匹配（提供了错误的正则）
   python logstat.py app.log --format custom --pattern '(?P<level>\w+)'
   输出：警告：解析成功率 3.1% 低于阈值 80%，请检查 --pattern 是否匹配日志格式
         未能解析的样例行（前 2 条）：2025-05-01 10:00:00 INFO start...
         （退出码 0，报告仍生成）

7. 异常示例：文件不存在
   python logstat.py no_such.log
   输出：错误：文件不存在：D:\work\no_such.log（退出码 1）

【六、验收标准】

[ ] --format auto 对 nginx、Python logging、syslog、JSON 四类样例文件都能正确识别。
[ ] 对 10 万行 Nginx 日志，解析成功率为 100%（构造标准格式样本验证）。
[ ] 统计出的行数与 wc -l 输出一致（考虑最后一行无换行的边界情况）。
[ ] Top IP 与 sort | uniq -c | sort -rn 的结果数量一致、计数一致。
[ ] 状态码分布合计等于成功解析的行数。
[ ] ERROR 级别识别覆盖 "ERROR"、"Error"、"level=error"、"Traceback" 四种写法。
[ ] Python 多行 Traceback 被合并为一条记录，不产生 8 条独立错误。
[ ] 消息归一化后，含不同数字/UUID/IP 的同一类错误聚合为一条模板。
[ ] --trend hour 的柱状图总列数不超过 --chart-width，缺失时段补 0 无空洞。
[ ] 突增检测在人为构造的 10 倍增长数据上能标出 [!!]。
[ ] --baseline 对比能准确列出新增与消失的错误模板。
[ ] 处理 1GB 日志时内存占用稳定在 200MB 以内（用 tracemalloc 或任务管理器验证）。
[ ] GBK 编码的中文日志用 --encoding gbk 后正文不乱码。
[ ] 单行 1MB 的超长日志被截断处理，程序不崩溃、不内存暴涨。
[ ] --json 输出可被 json.load 解析，字段完整且时间格式为 ISO8601。
[ ] --follow 追加新行后 5 秒内在刷新摘要中体现；日志被轮转后仍能继续跟踪。

【七、可选扩展】

1. 增加 --rules FILE 支持“告警规则”（某模板 5 分钟内出现超过 N 次则打印告警并返回特殊退出码）。
2. 增加 --export-csv 导出逐条结构化记录，供后续用 Excel 分析。
3. 增加 --geo 用离线 IP 段文件（如 GeoLite2 CSV）统计来源地区（不联网）。
4. 增加正则表达式性能保护：编译前检测嵌套量词，编译后用长行做超时试探。
5. 增加 --merge 合并多个来源的统计结果（用于多台机器分别跑后汇总）。
6. 提供 --html 输出单文件 HTML 报告（内联 CSS，无外部依赖）。

【八、涉及知识点】

- 正则命名捕获组、编译缓存（re.compile 的模块级缓存）、贪婪与回溯控制。
- 时间字符串解析：strptime 的 %b/%z/%f 指令、时区处理与夏令时注意点。
- 流式文件读取、gzip.open、文件偏移量与 tail -f 的实现原理。
- collections.Counter / defaultdict / deque 在统计与滑动窗口中的应用。
- 日志格式的常见变体：Nginx combined、Apache common、syslog RFC3164、Python logging、
  JSON Lines（每行一个 JSON 对象）。
- 文本归一化与模板聚类（占位符替换）在日志聚合中的作用。
- ASCII 图表绘制、终端宽度自适应与等宽排版。
- 内存友好的数据处理：生成器、slots dataclass、限制样例数量。
================================================================================
