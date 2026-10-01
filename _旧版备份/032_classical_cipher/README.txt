================================================================================
项目编号：032                    难度等级：★★☆☆☆（小型项目）
项目名称：古典密码工具箱
所属分类：安全与编码 / 密码学入门
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

CTF 入门题、谜题游戏、以及信息安全课堂上，凯撒、维吉尼亚、栅栏、培根这四种古典密码
出现频率极高。初学者往往要临时去网上找在线解密网站，把密文粘来粘去，既不能批量处理，
也看不清破解过程，更学不到"为什么这个密码能被破"。

本项目做的是一个统一的古典密码工具箱：用同一套命令完成加解密、参数控制、以及最关键
的"自动破解"。破解凯撒用频率分析打分，破解维吉尼亚用卡西斯基检验（Kasiski）估算密钥
长度再用重合指数（IC）与频率打分恢复密钥，破解栅栏用遍历栏数并按英文/拼音字母频率
排序，破译培根用两种字符映射还原 5 位分组。

目标用户是信息安全初学者、CTF 参赛者、需要给课件准备演示的教师。做成之后，学习者
可以在本地一次性对比四种密码的加解密结果与破解成功率，直观理解"替换密码为何脆弱"。

【二、功能需求清单】

1. 核心功能
   1.1 凯撒密码：encrypt / decrypt，位移量 k 取整数，可正可负，内部对 26 取模；
       仅对 A-Z、a-z 做位移，其它字符（含数字、标点、中文）原样保留。
   1.2 维吉尼亚密码：密钥为字母串，密钥字符依次循环作用于明文字母；
       非字母字符不消耗密钥下标；要求明文与密钥至少含一个字母。
   1.3 栅栏密码：按栏数 n 做"分栏-逐行读取"加密；提供 rail-fence 两种常见变体，
       默认按行分栏（zigzag 不支持时用简单分组），文档需明确所选变体。
   1.4 培根密码：把 26 个字母编码为 5 位 a/b；支持两种字母表（24 字母经典版与
       26 字母现代版，用 --variant classic|modern 选择）；解密时把输入中的
       任意两种字符规整为 a/b 两个符号。
   1.5 自动破解：--brute 对凯撒穷举 26 种位移并按评分排序取前 5；--crack 对
       维吉尼亚自动估算密钥长度并恢复密钥；--crack 对栅栏遍历 2~20 栏打分排序。
   1.6 批量模式：--input 指定文件，逐行加解密，--output 写回文件；支持 stdin/stdout。

2. 输入与交互
   2.1 统一入口：python cli.py <cipher> <mode> [文本] [选项]，
       cipher ∈ caesar|vigenere|railfence|bacon，mode ∈ encrypt|decrypt|brute|crack。
   2.2 文本来源优先级：位置参数 > --input 文件 > --stdin > 交互式粘贴（读到空行结束）。
   2.3 caesar 必须给 --shift（加解密时）；vigenere 必须给 --key；railfence 必须给
       --rails；bacon 可用 --variant。
   2.4 --keep-case 控制解密输出是否保留原大小写模式；默认保留（按密文大小写还原）。
   2.5 --only-letters 开关：开启后输出只保留字母，去掉空格与标点（便于做频率分析）。

3. 输出与展示
   3.1 普通模式输出两行：RESULT: <结果> 与 STATS: 长度 N，字母 N，匹配度 X.XX。
   3.2 brute/crack 模式输出排行表：RANK、PARAM（位移/密钥/栏数）、SCORE、TEXT（截断到 60 字符）。
   3.3 --verbose 时额外打印频率分析表：字母、出现次数、占比、与标准英语频率的差。
   3.4 输出固定使用 UTF-8；重定向到文件时不加任何颜色控制字符。

4. 异常与边界处理
   4.1 密文含非 ASCII 字符：字母类密码原样保留这些字符，并在 --verbose 下提示被跳过的字符数。
   4.2 空的输入文本：打印"错误：输入文本为空"，退出码 1。
   4.3 维吉尼亚密钥含非字母：打印"错误：密钥只能包含字母"，退出码 2。
   4.4 栅栏栏数非法：栏数小于 2 或大于文本长度时报错，退出码 2，并提示合法范围。
   4.5 培根密文长度不是 5 的倍数：忽略末尾不足 5 位的残组并给出警告。
   4.6 培根解密出现未定义编码（字母表外的 5 位组合）：该组输出 '?' 并在总结中计数。
   4.7 破解维吉尼亚时文本长度小于 100：打印"样本过短，破解结果可能不可靠"的警告。
   4.8 加解密往返自检：提供 --selftest，随机生成 20 组字符串做 encrypt→decrypt，
       全部一致则输出 PASS，否则列出失败样例，退出码 1。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库，包括 argparse、string、re、math、collections、
   dataclasses、random、statistics、sys、pathlib、typing。
   注意：标准库中的 random 只用于 --selftest 造数据，不得用于任何"加密"用途。
3. 禁止事项：禁止把古典密码描述为"安全的加密手段"，README 与 --help 中必须写明
   "本项目仅用于教学与谜题娱乐，不提供任何安全性"；禁止把明文/密钥写入日志文件；
   禁止用 eval 或 exec 处理用户输入。
4. 代码组织：至少包含 ciphers/caesar.py、ciphers/vigenere.py、ciphers/railfence.py、
   ciphers/bacon.py、analysis.py（评分与频率分析）、cli.py。
   每个密码模块必须实现统一的抽象接口
   encrypt(text: str, **params) -> str 与 decrypt(text: str, **params) -> str，
   并提供 crack(text: str) -> list[tuple[str, float]]。
5. 编码规范：类型注解与 docstring 齐全；评分函数必须写明打分依据（公式或参考文献）；
   常量集中在 constants.py（英文字母频率表、培根字母表）。

【四、设计要点】

1. 数据结构：
   - CipherResult：text: str，cipher: str，mode: str，params: dict，score: float。
   - CrackCandidate：param: str，score: float，text: str。
   - 英文单字母频率表 ENGLISH_FREQ：26 项浮点数组
     （E 12.70、T 9.06、A 8.17、O 7.51、I 6.97、N 6.75、S 6.33、H 6.09、R 5.99…，
     合计归一化为 1.0）。
   - 培根字母表 BACON_MODERN：{'AAAAA': 'A', 'AAAAB': 'B', …}，共 26 项；
     BACON_CLASSIC 为 24 字母版本，I/J 与 U/V 合并。
2. 关键算法或流程：
   2.1 凯撒加解密：对每个字符取 ord，判断是否在 a-z / A-Z 区间，
       计算 (ord(c) - base + shift) % 26 + base；shift 可负，取模后自动归一。
   2.2 频率打分（score_text）：把文本转大写只留字母，统计各字母频率，
       计算与 ENGLISH_FREQ 的卡方统计量 χ² = Σ (观测 - 期望)² / 期望，
       χ² 越小说明越像英文；对外统一返回 negative_chi_square 作为"越大越好"的分数，
       避免调用方混淆方向。
   2.3 维吉尼亚破解：
       (a) 用卡西斯基检验：找出所有重复三元组的位置间距，取间距的公约数频次，
           候选密钥长度取频次最高的若干值（2~20 范围内）。
       (b) 对每个候选长度 L，把密文按模 L 分成 L 条子序列，分别做 26 次位移试探，
           取 χ² 最优位移作为该位密钥字母。
       (c) 用整体 χ² 给每个候选长度打分，输出前 5 名。
   2.4 栅栏破解：对 rails = 2..min(20, len-1) 依次解密并打分，按分数降序输出。
   2.5 培根解密：把输入中的字符按出现情况规整为两类（默认 a/b；若不是 a/b
       则按"出现次数多的映射为 a"）；每 5 个一组查表。
   2.6 往返自检：对每种密码随机生成长度 10~200 的字母串，参数随机后加密再解密，
       与原文比较（大小写敏感模式下要求完全相等）。
3. 接口或命令设计：
   python cli.py caesar encrypt "hello world" --shift 3
   python cli.py caesar brute "khoor zruog"
   python cli.py vigenere decrypt "rijvs" --key lemon
   python cli.py vigenere crack --input cipher.txt --verbose
   python cli.py railfence encrypt "wearediscovered" --rails 3
   python cli.py bacon decrypt "AABBA ABBAA ..." --variant modern
   所有子命令共享 --input / --output / --stdin / --verbose / --only-letters。

【五、运行方式与示例】

安装：无需安装，仅需 Python 3.10+。
运行：
   python cli.py caesar encrypt "Attack at dawn!" --shift 3
   python cli.py caesar brute "Dwwdfn dw gdzq!"
   python cli.py vigenere crack --input secret.txt --verbose
   python cli.py --selftest

示例一（凯撒加密）：
   输入：python cli.py caesar encrypt "Attack at dawn!" --shift 3
   输出：
   RESULT: Dwwdfn dw gdzq!
   STATS: 长度 15，字母 11，匹配度 -0.83

示例二（凯撒暴力破解）：
   输入：python cli.py caesar brute "Dwwdfn dw gdzq!"
   输出：
   RANK  PARAM      SCORE     TEXT
   1     shift=3    -0.41     ATTACK AT DAWN
   2     shift=16   -3.92     NDDNRA ND RKDW
   3     shift=9    -5.17     UEEUZH UE UMPE
   ...

示例三（维吉尼亚自动破解）：
   输入：python cli.py vigenere crack --input secret.txt
   输出：
   推断密钥长度：3（卡西斯基支持度 0.62）
   RANK  KEY      SCORE     TEXT
   1     LEMON    -0.28     ATTACKATDAWNATTACKATDAWN
   2     LEMOF    -2.11     ATTACKATDZWNATTACKATDZWN

示例四（异常输入）：
   输入：python cli.py vigenere encrypt "hello" --key "le mon"
   输出：
   错误：密钥只能包含字母，收到 "le mon"
   退出码：2

【六、验收标准】

[ ] --selftest 对四种密码全部 PASS，退出码为 0。
[ ] 凯撒 shift=3 加密 "Attack at dawn!" 得到 "Dwwdfn dw gdzq!"，标点与空格位置不变。
[ ] 凯撒 shift=-3 与 shift=23 结果一致。
[ ] 凯撒 brute 对上面密文的第一名 TEXT 为 "ATTACK AT DAWN"。
[ ] 维吉尼亚 key=LEMON 加密 "ATTACKATDAWN" 得到 "LXFOPVEFRNHR"（教材标准结果）。
[ ] 维吉尼亚 crack 在 500 字符以上的英文密文上能还原出正确密钥。
[ ] 栅栏 rails=3 加密 "WEAREDISCOVEREDFLEEATONCE" 与教材结果一致。
[ ] 培根 modern 字母表解密 "AABBA" 得到 'F'，classic 字母表同码得到不同字母。
[ ] 培根密文长度为 13 时给出残组警告且不崩溃。
[ ] 含中文的明文经凯撒加密后中文字符原样保留。
[ ] --only-letters 输出的结果不含空格与标点。
[ ] 密钥含空格时报错并返回退出码 2。
[ ] --verbose 打印的频率表占比合计在 99.5% ~ 100.5% 之间。
[ ] 所有子命令的 --help 均包含"仅用于教学"的安全声明。

【七、可选扩展】

1. 增加 Playfair、仿射密码（Affine）、自动密钥（Autokey）三种密码，复用同一接口。
2. 增加 n-gram（双字母组、三字母组）评分，替换单字母 χ²，提高维吉尼亚破解准确率。
3. 增加 --batch-crack：扫描目录内所有 .txt，自动识别密码类型并输出破解报告。
4. 增加频率分析图（纯文本柱状图，不依赖第三方库）便于课堂演示。

【八、涉及知识点】

- 字符串与 ASCII 码运算、大小写保持、非字母字符透传
- 卡方统计量与单字母频率分析、重合指数（IC）、卡西斯基检验
- 字典与 Counter 计数、排序与 Top-N 选取
- 列表切片与栅栏/zigzag 的索引构造
- 位模式编码（培根 5 位分组）与查表
- 抽象接口设计（多密码共享 encrypt/decrypt/crack 协议）
- argparse 子命令（add_subparsers）与参数校验
================================================================================
