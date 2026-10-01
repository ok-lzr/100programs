================================================================================
项目编号：003                    难度等级：★☆☆☆☆（小型项目）
项目名称：强密码生成器
所属分类：命令行工具 / 安全与编码
建议工时：3 ~ 5 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

很多人注册网站时随手敲一个 “abc123456”，或者在多个网站复用同一个密码。这个工具用
密码学安全的随机源生成不易被猜到的密码，同时内置一个强度评估器，可以拿现有密码来打分，
指出它究竟弱在哪里（长度不足、字符种类单一、包含常见弱口令片段等）。

目标用户是普通网民、需要给批量账号设置初始密码的运维人员，以及学习随机数与信息安全
基础的学生。重点是讲清“随机”必须来自 secrets 而不是 random，以及“熵”这个可量化指标。

做完之后应当能拿来干这些事：一条命令生成 20 位含大小写字母数字符号的密码；一次生成
10 个候选密码并从中挑选；对已有密码 abc123 打分得到 30 分并看到改进建议；用
--exclude-similar 去掉容易看错的 0O1lI 字符，方便手抄。

【二、功能需求清单】

1. 核心功能
   1.1 随机生成密码：长度由 --length 指定，默认 16，允许范围 4~128。
   1.2 字符集开关：--upper 大写字母、--lower 小写字母、--digits 数字、
       --symbols 常用符号、--no-similar 排除易混字符。
   1.3 默认字符集为大小写字母加数字；只要显式给出任一字符集开关，就以显式给出的为准。
   1.4 保证每类被启用的字符至少出现一次，其余位置从并集中随机填充。
   1.5 强度评估：对给定密码输出长度、字符种类数、估算熵（比特）、强度等级与改进建议。
   1.6 一次生成多个：--count N 输出 N 条互不相同的密码，默认 1。

2. 输入与交互
   2.1 命令行：python passgen.py --length 16 --upper --lower --digits --symbols
   2.2 交互模式：不带参数运行则逐项询问长度、是否包含各类字符、生成数量。
   2.3 评估模式：python passgen.py --check "MyPass123!"，密码从命令行读入。
   2.4 也支持 --check-stdin，从标准输入读取一行密码，避免密码出现在命令历史里。
   2.5 --symbols 的符号集固定为 !@#$%^&*()-_=+[]{};:,.?/ 共 25 个，
       不含空格、引号与反斜杠，避免粘贴到配置文件时出错。
   2.6 --no-similar 从所有字符集中剔除 0 O o 1 l I | ` 这几个字符。

3. 输出与展示
   3.1 默认输出时只打印密码本身，每行一条，便于管道直接使用。
   3.2 --verbose 时在密码后输出一行统计：
       长度 16，字符集 4 类，估算熵 104.9 比特，强度：很强
   3.3 评估模式输出多行报告：
       长度：8
       字符种类：4（小写、大写、数字、符号）
       估算熵：52.3 比特
       强度等级：中等
       建议：长度达到 12 位以上；避免使用连续键盘序列
   3.4 --json 时输出 {"password": "...", "length": 16, "entropy": 104.9,
       "strength": "很强"}。
   3.5 强度等级划分：熵小于 28 极弱、28~35 弱、36~59 中等、60~127 强、
       128 及以上 很强。

4. 异常与边界处理
   4.1 长度小于 4 时打印 “错误：密码长度至少为 4”，退出码 2。
   4.2 长度超过 128 时打印 “错误：密码长度最多为 128”。
   4.3 长度小于启用字符集类别数时无法保证每类至少一个，打印
       “错误：长度 N 不足以覆盖 M 类字符”，退出码 2。
   4.4 显式指定了字符集开关但全部为假（等价于没有可用字符）时提示至少选择一类。
   4.5 评估模式遇到空密码时输出 “错误：密码不能为空”。
   4.6 --no-similar 后若某类字符被清空（例如只有数字且长度合规），自动跳过该类并
       在 --verbose 中说明。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库，需要 argparse、secrets、string、math、json、
   sys、dataclasses、typing。
3. 禁止事项：禁止使用 random 模块生成密码；禁止使用 time.time() 或 os.urandom
   手写随机索引；禁止把用户密码写入任何日志或文件；禁止在默认输出里附加提示文本。
4. 代码组织：
   4.1 常量：CHAR_SETS 字典（键为 lower/upper/digits/symbols，值为字符集字符串）、
       SIMILAR_CHARS 字符串、STRENGTH_LEVELS 列表。
   4.2 函数：build_charset(options) -> str、generate_password(length, charset,
       required_sets) -> str、estimate_entropy(length, pool_size) -> float、
       classify_strength(entropy) -> str、check_password(pw) -> Report。
   4.3 洗牌必须用 secrets.randbelow 实现 Fisher-Yates，禁止用 random.shuffle。
   4.4 main() 负责参数解析与三种模式（生成、评估、交互）的分派。
5. 编码规范：类型注解与 docstring；docstring 中说明所用随机源；不在异常信息中
   回显用户的原始密码（评估模式只回显长度与种类）。

【四、设计要点】

1. 数据结构：
   1.1 GenOptions：dataclass，字段 length: int、upper/lower/digits/symbols: bool、
       exclude_similar: bool、count: int。
   1.2 StrengthReport：dataclass，字段 length、category_count、categories: list[str]、
       entropy、strength、suggestions: list[str]。
   1.3 CHAR_SETS 中 symbols 使用 string.punctuation 的子集常量，不直接整体使用。
2. 关键算法或流程：
   2.1 生成流程：构建并集池 -> 校验长度是否覆盖类别数 -> 对每个启用类别先取一个字符
       放入结果 -> 剩余长度从并集池用 secrets.choice 填充 -> Fisher-Yates 洗牌。
   2.2 熵计算：entropy = length × log2(pool_size)，pool_size 为实际可用字符数。
   2.3 评估流程：统计密码中命中的字符类别数 -> 推断字符池大小（各类别池之和）
       -> 计算熵 -> 结合长度上限修正（长度小于 8 时降一级）-> 生成建议列表。
   2.4 建议规则：长度小于 12 提示加长；只含单一类别提示混合字符；包含 123、abc、
       password、admin、qwerty 等片段时给出“包含常见弱口令模式”的提示。
3. 接口或命令设计：
   3.1 generate_password(length: int, pool: str, required: list[str]) -> str
   3.2 estimate_entropy(length: int, pool_size: int) -> float
   3.3 check_password(password: str) -> StrengthReport
   3.4 命令行：--length、--upper、--lower、--digits、--symbols、--no-similar、
       --count、--check、--check-stdin、--json、--verbose。
   3.5 退出码约定：0 正常、2 参数或输入错误。

【五、运行方式与示例】

1. 运行准备：无需安装依赖；在共享终端里使用评估模式时建议用 --check-stdin。
2. 默认生成一条：
   python passgen.py
   输出：k7Rq2XmT9pLw4ZaB
3. 生成四条指定字符集的密码：
   python passgen.py --length 20 --upper --lower --digits --symbols --count 4
   输出：
   G7#pLq2!zRw9Kd$mX1aB
   tR4&yU8@nQw3Zc%vB6sM
   ……
4. 排除易混字符：
   python passgen.py --length 12 --upper --digits --no-similar --verbose
   输出：
   T7KQ2XRM9PWY
   长度 12，字符集 2 类，估算熵 58.4 比特，强度：中等
5. 评估已有密码：
   python passgen.py --check "abc123"
   输出：
   长度：6
   字符种类：2（小写、数字）
   估算熵：31.0 比特
   强度等级：弱
   建议：长度达到 12 位以上；混合大写字母与符号；包含常见弱口令模式
6. 通过标准输入评估（不留在命令历史）：
   echo "Tr0ub4dor&3" | python passgen.py --check-stdin
   输出：长度：11 …… 强度等级：强
7. 异常输入示例：
   python passgen.py --length 3
   输出：错误：密码长度至少为 4
   退出码：2
   python passgen.py --length 4 --upper --lower --digits --symbols
   输出：错误：长度 4 不足以覆盖 4 类字符

【六、验收标准】

[ ] 默认长度 16，且包含大写、小写、数字
[ ] --upper --lower --digits --symbols 生成的密码四类字符各至少出现一次
[ ] 生成的密码中不含空格、单引号、双引号与反斜杠
[ ] --no-similar 后结果中不出现 0 O o 1 l I | ` 任一字符
[ ] --count 4 输出 4 条互不相同的密码
[ ] 默认输出模式每行只有密码本身，不夹杂统计文字
[ ] 熵计算使用 log2(pool_size)×length 且结果保留一位小数
[ ] 强度等级在 28、36、60、128 四个阈值处切换正确
[ ] --check 对 abc123 给出包含“常见弱口令模式”的建议
[ ] --check-stdin 能从管道读取密码
[ ] 长度小于 4、大于 128、类别数超长三种情况都返回退出码 2
[ ] 源码中不出现 random 模块的任何调用
[ ] 日志与错误信息中不回显用户原始密码
[ ] --json 输出可被 json.loads 正常解析

【七、可选扩展】

1. 支持生成可发音密码（辅音+元音交替），兼顾强度与记忆性。
2. 支持 --passphrase 用指定词表生成 4~6 个单词的记忆短语密码。
3. 增加 --exclude-chars 自定义排除字符，例如排除所有括号。
4. 增加批量评估模式，读取密码清单文件输出风险排序表。
5. 增加 --clipboard 尝试复制到剪贴板（Windows 用 tkinter 实现，不引入第三方库）。

【八、涉及知识点】

- secrets 模块与密码学安全随机数
- Fisher-Yates 洗牌算法
- 信息熵与 log2 计算在密码强度中的意义
- string 模块常量（ascii_letters、digits、punctuation）
- 布尔开关型命令行参数（argparse store_true）
- 标准输入读取与管道用法
- JSON 序列化与 ensure_ascii 设置
- 安全编码意识：不记录明文密码、最小暴露原则
- dataclass 承载选项与报告对象
================================================================================
