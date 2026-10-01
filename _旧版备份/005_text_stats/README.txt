================================================================================
项目编号：005                    难度等级：★☆☆☆☆（小型项目）
项目名称：文本统计器
所属分类：命令行工具 / 文件与文本处理
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

写周报、写论文、翻译文档时经常被问“多少字”，但不同软件给出的答案不一样：Word 按字符
算，编辑器按字节算，英文按单词算，中文又没有空格分词。这个工具一次性把行数、词数、
字符数（含空格与不含空格）、中日韩字符占比、英文单词占比以及词频 TOP N 全部统计出来。

目标用户是写作者与译者（核对字数）、程序员（快速看日志与代码规模）、以及中文 NLP
入门的学习者（理解中英文混排文本的分词难点）。重点是中文字符与英文单词要分开计数，
并说明分词策略是“按空白与标点切分 + 中文按字计数”。

做完之后应当能拿来干这些事：对一份中英混排的 Markdown 统计出中文字数与英文单词数；
对日志文件统计出现最频繁的 20 个词；用 --top 0 只看总览不看词频；把结果输出成 JSON
供其它脚本消费。

【二、功能需求清单】

1. 核心功能
   1.1 基础计数：总行数、非空行数、总字符数、不含空白字符数、总词数。
   1.2 中英文占比：统计 CJK 字符个数与占全部字符的百分比、英文单词数与百分比、
       数字串个数与百分比、其余标点符号数与百分比，四者之和接近 100%。
   1.3 词频统计：输出出现次数最多的 TOP N 个词，默认 N=10，含次数与占比。
   1.4 最长的行：输出最长行的行号与字符长度（截断显示前 60 个字符）。
   1.5 逐文件模式：可一次传入多个文件，逐个输出统计，最后输出合计。
   1.6 预估阅读时间：按中文 400 字/分钟、英文 200 词/分钟估算分钟数，向上取整。

2. 输入与交互
   2.1 命令行：python textstats.py sample.txt
   2.2 多文件：python textstats.py a.txt b.md c.log
   2.3 标准输入：python textstats.py - 从管道读取，如 cat a.txt | python textstats.py -
   2.4 目录模式：--dir docs --ext .md,.txt 递归统计指定扩展名的所有文件。
   2.5 参数：--top N 控制词频条数（默认 10，0 表示不输出词频）。
   2.6 参数：--ignore-case 词频统计忽略大小写，默认开启；--case-sensitive 关闭。
   2.7 参数：--stopwords stop.txt 指定停用词表，每行一个词，# 开头为注释。
   2.8 参数：--min-word-len 过滤长度小于该值的英文词，默认 1。
   2.9 编码：默认按 UTF-8 读取；--encoding gbk 可切换；--errors 指定 ignore/replace。

3. 输出与展示
   3.1 默认输出多行统计报告，字段与数值左对齐，例如：
       文件：sample.txt
       行数：120（非空 98）
       字符数：4321（不含空白 3800）
       词数：512
       中文占比：62.4 %
       英文单词占比：31.2 %
       数字占比：3.1 %
       其它符号占比：3.3 %
       预估阅读时间：7 分钟
       词频 TOP 10：
         1. 数据        24 次  4.7 %
         2. python      18 次  3.5 %
   3.2 --json 输出完整统计对象，键名固定为 file、lines、non_empty_lines、chars、
       chars_no_space、words、cjk_ratio、en_ratio、digit_ratio、other_ratio、
       reading_minutes、top_words（列表，元素含 word、count、ratio）。
   3.3 --quiet 只输出一行摘要，格式为
       sample.txt  行 120  词 512  字 4321  中文 62.4%
   3.4 多文件模式在末尾输出 TOTAL 段落，把各文件数值相加后重新计算占比。

4. 异常与边界处理
   4.1 文件不存在时打印 “错误：找不到文件 xxx.txt”，退出码 2，其余文件继续统计。
   4.2 空文件输出全部计数为 0，占比输出 0.0 %，不抛异常。
   4.3 二进制文件或解码失败时提示 “错误：无法按 UTF-8 解码，可尝试 --encoding gbk”，
       退出码 2，并建议 --errors ignore。
   4.4 空行不计入非空行数，但计入行数；末行无换行符也按一行计。
   4.5 停用词文件不存在时打印警告并继续，不中断统计。
   4.6 --dir 未匹配到任何文件时输出 “未找到匹配的文件” 且退出码为 0。
   4.7 超长行在终端显示截断，但统计值使用完整长度。

5. 分词规则（必须写进实现与文档）
   5.1 英文单词：由字母、数字、下划线、连字符组成的连续串，正则 [A-Za-z0-9_'-]+。
   5.2 中文：每个 CJK 统一表意文字（U+4E00~U+9FFF）算一个字，也计入词数一次。
   5.3 其它语言字母（如日文假名、韩文）归入 “其它” 类，不计入中文占比。
   5.4 标点与空白不计入词数。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库，需要 argparse、re、sys、json、pathlib、collections
   （Counter）、unicodedata、dataclasses、typing。
3. 禁止事项：禁止用 len(text.split()) 作为唯一词数口径（必须说明并同时给出中文字数）；
   禁止引入 jieba 等第三方分词库；禁止把整个大文件一次性读入后再做多轮正则
   （应逐行累加，内存占用与文件大小无关）。
4. 代码组织：
   4.1 正则常量集中在模块顶部：RE_WORD、RE_CJK、RE_DIGIT、RE_SPACE。
   4.2 函数：iter_lines(path, encoding, errors) -> Iterator[str]、
       count_file(...) -> TextStats、merge_stats(stats_list) -> TextStats、
       top_words(counter, n) -> list[tuple[str, int]]、format_report(stats) -> str。
   4.3 Counter 必须在逐行处理中累积，禁止先把所有词存入列表。
   4.4 main() 处理多文件、目录展开与输出格式选择。
5. 编码规范：类型注解与 docstring；统计口径写进函数 docstring；禁止在循环里做重复
   编译正则（用 re.compile 预编译）。

【四、设计要点】

1. 数据结构：
   1.1 TextStats：dataclass，字段 file: str、lines: int、non_empty_lines: int、
       chars: int、chars_no_space: int、words: int、cjk_count: int、en_count: int、
       digit_count: int、other_count: int、longest_line_no: int、
       longest_line_len: int、word_counter: Counter[str]。
   1.2 占比在输出阶段由各类计数除以总字符数计算，避免在累加过程中反复做除法。
   1.3 停用词集合用 set[str] 保存，加载时统一转小写。
2. 关键算法或流程：
   2.1 逐行流程：line = 行文本（去掉行尾 \n）-> lines += 1；若 line.strip() 非空则
       non_empty_lines += 1 -> chars += len(line) -> chars_no_space += 非空白字符数
       -> 用 RE_CJK.findall 计数中文 -> 用 RE_WORD.finditer 提取英文词并累加词数
       与 Counter -> 用 RE_DIGIT 统计独立数字串 -> 更新最长行记录。
   2.2 占比口径：中文占比 = cjk_count / chars（chars 为 0 时输出 0.0）；
       四类占比之和可能因未覆盖字符略小于 100%，文档中需说明。
   2.3 TOP N：Counter.most_common(n)，同频次时按词首次出现顺序稳定排序；
       过滤停用词与长度小于 min-word-len 的词。
   2.4 合并：把所有计数相加，Counter 用 + 运算合并，再重新计算占比。
3. 接口或命令设计：
   3.1 count_file(path: str, *, encoding: str = "utf-8", errors: str = "strict",
       stopwords: set[str] | None = None, min_word_len: int = 1) -> TextStats
   3.2 count_stream(stream: IO[str], name: str, ...) -> TextStats
   3.3 format_report(stats: TextStats, top: int) -> str
   3.4 命令行：位置参数 files（可多个，"-" 表示标准输入）；可选 --dir、--ext、--top、
       --json、--quiet、--stopwords、--min-word-len、--ignore-case/--case-sensitive、
       --encoding、--errors。

【五、运行方式与示例】

1. 运行准备：无需安装依赖。
2. 统计单个文件：
   python textstats.py sample.txt
   输出（sample.txt 为 120 行中英混排文档）：
   文件：sample.txt
   行数：120（非空 98）
   字符数：4321（不含空白 3800）
   词数：512
   中文占比：62.4 %
   英文单词占比：31.2 %
   数字占比：3.1 %
   其它符号占比：3.3 %
   预估阅读时间：7 分钟
   词频 TOP 10：
     1. 数据        24 次  4.7 %
     2. python      18 次  3.5 %
3. 只看摘要（适合放进 shell 提示符）：
   python textstats.py sample.txt --quiet
   输出：sample.txt  行 120  词 512  字 4321  中文 62.4%
4. 从管道读取并输出 JSON：
   type sample.txt | python textstats.py - --json --top 3
   输出：
   {"file": "<stdin>", "lines": 120, "chars": 4321, "words": 512,
    "top_words": [{"word": "数据", "count": 24, "ratio": 0.047}]}
5. 目录递归统计并按停用词过滤：
   python textstats.py --dir docs --ext .md,.txt --top 20 --stopwords stop.txt
   输出：逐个文件报告 + TOTAL 段落。
6. 空文件示例：
   python textstats.py empty.txt
   输出：
   行数：0（非空 0）
   字符数：0（不含空白 0）
   中文占比：0.0 %
7. 异常输入示例：
   python textstats.py nope.txt
   输出：错误：找不到文件 nope.txt
   退出码：2
   python textstats.py image.png
   输出：错误：无法按 UTF-8 解码，可尝试 --encoding gbk
   退出码：2

【六、验收标准】

[ ] 单个 ASCII 文件的行数、词数、字符数三项与编辑器统计一致
[ ] 中文字符按 U+4E00~U+9FFF 逐字计数，一个汉字计 1 个中文与 1 个词
[ ] 英文单词按 RE_WORD 提取，连续字母数字下划线不会被拆开
[ ] 中英混排样例的四类占比之和在 99%~101% 之间
[ ] 空文件不抛异常，所有计数为 0
[ ] 末行无换行符的文件行数统计正确
[ ] --top 0 时不输出词频段落
[ ] --stopwords 生效且文件缺失时只警告不中断
[ ] --min-word-len 能过滤短词
[ ] --json 输出可被 json.loads 解析且键名完全符合约定
[ ] 目录模式能递归匹配 .md 与 .txt 并汇总 TOTAL
[ ] 标准输入模式支持管道且名字显示为 <stdin>
[ ] 解码失败时给出可操作的编码建议且退出码为 2
[ ] 内存占用不随文件大小线性增长（逐行处理，不整文件读入）
[ ] 未引入任何第三方分词库

【七、可选扩展】

1. 增加 TF-IDF 模式，对多文件统计关键词差异。
2. 增加 --heatmap 用字符方块按行输出长度分布直方图。
3. 增加中英文标点符号分别统计。
4. 增加 --compare a.txt b.txt 输出两文件词频差异与新增、消失的词。
5. 增加 --watch 模式，文件变化后自动重新统计。

【八、涉及知识点】

- 正则表达式预编译与 finditer 迭代匹配
- Unicode 码点范围与中文判断（含 unicodedata 的使用）
- collections.Counter 的计数、most_common 与合并运算
- 生成器与逐行流式处理，控制内存占用
- 中英文混排文本的分词难点与口径定义
- 文件编码检测与解码错误策略（strict/ignore/replace）
- pathlib 递归遍历与扩展名过滤
- 命令行多文件参数与 - 表示标准输入的约定
- 数据类组织统计结果与格式化输出
================================================================================
