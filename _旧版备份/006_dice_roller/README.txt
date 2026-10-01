================================================================================
项目编号：006                    难度等级：★☆☆☆☆（小型项目）
项目名称：骰子与随机抽样器
所属分类：命令行工具 / 随机与游戏
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

跑团玩家经常要掷 “3d6+2” “4d6dl1”（掷 4 个六面骰去掉最低一个）这类表达式，手动掷
又慢又容易算错。同时，班级要随机点名、团建要随机分组时，用“第几个到第几个”来分总
让人觉得不公平。这个工具把三件事合到一起：解析并计算骰子表达式、从名单里随机抽签、
把名单随机分成若干组。

目标用户是桌游与跑团玩家、需要随机点名的老师、组织团建或分组的活动组织者。设计重点
是表达式解析（词法切分 + 逐项求值）和可复现的随机（--seed 固定后结果必须完全一致）。

做完之后应当能拿来干这些事：一条命令算出 3d6+2 的点数并显示每个骰子的明细；一次性
掷 5 组属性；从 40 人的名单里抽 3 个不重复的中奖者；把 12 人随机分成 3 组并尽量均匀。

【二、功能需求清单】

1. 核心功能
   1.1 骰子表达式求值：支持 NdM（如 3d6、1d20）、加常数（3d6+2）、减常数（2d10-1）、
       多段相加（2d6+1d8+3）。
   1.2 修饰符：dl1/dh1 去掉最低或最高 1 个骰子；kl1/kh1 只保留最低或最高 1 个；
       r1 表示骰出 1 时重掷一次；e 表示骰出最大值时继续追加（爆炸骰）。
   1.3 骰子面数限制：M 取值 2~1000；骰子个数 N 取值 1~1000；--repeat 最多 10000 次。
   1.4 明细展示：--detail 时列出每个骰子的点数，被丢弃的骰子用方括号标出。
   1.5 随机抽签：--pick 从名单中不重复抽取 K 个，K 大于人数时报错。
   1.6 随机分组：--group N 把名单随机分成 N 组，人数差不超过 1 人。
   1.7 可复现：--seed 40 指定随机种子，同一种子与参数必须产生完全相同的输出。
   1.8 统计模式：--repeat 1000 计算该表达式的均值、最小值、最大值与标准差。

2. 输入与交互
   2.1 掷骰：python diceroll.py "3d6+2"
   2.2 多表达式：python diceroll.py "1d20" "2d6+3" 依次输出。
   2.3 明细：python diceroll.py "4d6dl1" --detail
   2.4 抽签：python diceroll.py --names names.txt --pick 3
   2.5 分组：python diceroll.py --names names.txt --group 4
   2.6 名单来源：--names 文件（每行一个名字，空行与 # 注释跳过）或
       --name-list 参数（逗号分隔，如 --name-list "张三,李四,王五"）。
   2.7 参数：--seed、--repeat、--detail、--json、--sort（分组结果按组内人数排序输出）。
   2.8 交互模式：不带参数运行时提示输入表达式，输入 q 退出。

3. 输出与展示
   3.1 基础输出：3d6+2 = 14
   3.2 --detail 输出：
       3d6+2 = 14
       骰子明细：[5, 4, 3] 常数 +2
   3.3 修饰符明细：
       4d6dl1 = 13
       骰子明细：[6, 4, 2, [1]]（方括号内为被丢弃的骰子）
   3.4 抽签输出：
       抽签结果（3 人）：
         1. 张三
         2. 李四
         3. 王五
   3.5 分组输出：
       第 1 组（3 人）：张三、李四、王五
       第 2 组（3 人）：……
       共 4 组，12 人。
   3.6 统计输出：
       表达式 3d6+2，模拟 1000 次：均值 12.51，最小 7，最大 22，标准差 2.42
   3.7 --json 输出 {"expression":"3d6+2","total":14,"rolls":[5,4,3],"constant":2,
       "dropped":[]}。

4. 异常与边界处理
   4.1 表达式为空时打印 “错误：表达式不能为空”，退出码 2。
   4.2 表达式语法错误（如 3d、d6、3x6、3d6++2）时打印
       “错误：表达式 'xxx' 解析失败，位置 3 附近语法不正确”，退出码 2。
   4.3 骰子个数或面数越界时打印具体范围提示。
   4.4 修饰符丢弃数量大于等于骰子个数时（如 2d6dl2）报错，不允许出现 0 个骰子。
   4.5 抽签人数大于名单人数时打印 “错误：只能从 12 人中抽取，请求 15 人”。
   4.6 分组数大于人数时打印 “错误：4 人无法分成 6 组”。
   4.7 名单中存在重复名字时保留重复（视为不同人）并在 --verbose 中提示。
   4.8 --repeat 超出上限时报错，不静默截断。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库，需要 argparse、random、re、sys、json、statistics、
   dataclasses、typing、pathlib。
3. 禁止事项：禁止用 eval 或 exec 计算表达式；禁止用正则一次性替换后直接算数值；
   必须实现显式的词法与求值流程；禁止在随机抽样中先打乱名单再切片以外的方式造成
   不均匀分布（可用 random.sample 或 Fisher-Yates 洗牌）。
4. 代码组织：
   4.1 Token 与语法：定义 tokenize(expr) -> list[Token] 与 parse(expr) -> DiceExpr。
   4.2 DiceExpr：dataclass，字段 terms: list[Term]、constant: int；Term 含 count、sides、
       modifiers: list[Modifier]。
   4.3 求值：evaluate(expr, rng) -> RollResult，纯逻辑，随机源由参数传入便于测试。
   4.4 抽样：draw_names(names, k, rng)、split_groups(names, groups, rng) 两个函数。
   4.5 main() 分派掷骰、抽签、分组、统计四种模式。
5. 编码规范：类型注解与 docstring；Token 类型用 Enum；解析错误必须带上出错位置；
   随机源统一使用 random.Random(seed) 实例，禁止直接调用模块级 random 函数。

【四、设计要点】

1. 数据结构：
   1.1 Token：dataclass(frozen=True)，字段 kind: TokenKind（NUMBER、DICE、PLUS、
       MINUS、MODIFIER）、text: str、pos: int。
   1.2 Modifier：dataclass，字段 code: str（dl/dh/kl/kh/r/e）、amount: int。
   1.3 RollResult：dataclass，字段 expression: str、rolls: list[int]、
       kept: list[int]、dropped: list[int]、constant: int、total: int。
   1.4 GroupResult：dataclass，字段 index: int、members: list[str]。
2. 关键算法或流程：
   2.1 词法分析：用预编译正则顺序扫描表达式，识别数字、d/D、+、-、修饰符代码，
       跳过空格；遇到无法匹配的字符立即抛出带位置信息的 ParseError。
   2.2 语法分析：按 “项（项）*” 拆分，每个项形如 [N]dM[修饰符]*；缺少 N 时默认 1；
       常数项直接累加到 constant。
   2.3 求值流程：对每个项循环掷 count 个 1..M 的随机数 -> 处理 r（重掷 1）与
       e（掷出 M 时追加一次，最多追加 10 次防止死循环）-> 处理 dl/dh 排序后丢弃
       -> 处理 kl/kh 排序后保留 -> 累加保留值 -> 最后加 constant。
   2.4 抽签：rng.sample(names, k) 保证不放回且均匀。
   2.5 分组：先 rng.shuffle(names)，再按 i % groups 轮流分配，保证组间人数差不超过 1。
   2.6 统计：重复求值 --repeat 次，用 statistics.mean/fmean/stdev 计算指标。
3. 接口或命令设计：
   3.1 tokenize(expr: str) -> list[Token]
   3.2 parse(expr: str) -> DiceExpr
   3.3 evaluate(expr: DiceExpr, rng: random.Random) -> RollResult
   3.4 draw_names(names: list[str], k: int, rng: random.Random) -> list[str]
   3.5 split_groups(names: list[str], groups: int, rng: random.Random)
       -> list[GroupResult]
   3.6 命令行：位置参数 expressions；可选 --names、--name-list、--pick、--group、
       --seed、--repeat、--detail、--json、--sort、--verbose。

【五、运行方式与示例】

1. 运行准备：无需安装依赖。
2. 基础掷骰：
   python diceroll.py "3d6+2"
   输出：3d6+2 = 14
3. 带明细与丢弃：
   python diceroll.py "4d6dl1" --detail
   输出：
   4d6dl1 = 13
   骰子明细：[6, 4, 2, [1]]（方括号内为被丢弃的骰子）
4. 固定种子复现（两次结果完全一致）：
   python diceroll.py "2d20+5" --seed 40
   第一次输出：2d20+5 = 27
   第二次输出：2d20+5 = 27
5. 统计模式：
   python diceroll.py "3d6+2" --repeat 1000 --seed 1
   输出：表达式 3d6+2，模拟 1000 次：均值 12.51，最小 7，最大 22，标准差 2.42
6. 随机抽签：
   python diceroll.py --name-list "张三,李四,王五,赵六,钱七" --pick 2 --seed 7
   输出：
   抽签结果（2 人）：
     1. 王五
     2. 张三
7. 随机分组（names.txt 有 12 行名字）：
   python diceroll.py --names names.txt --group 4 --sort --seed 3
   输出：
   第 1 组（3 人）：张三、李四、王五
   第 2 组（3 人）：赵六、钱七、孙八
   第 3 组（3 人）：……
   第 4 组（3 人）：……
   共 4 组，12 人。
8. 异常输入示例：
   python diceroll.py "3d6++2"
   输出：错误：表达式 '3d6++2' 解析失败，位置 4 附近语法不正确
   退出码：2
   python diceroll.py "2d6dl2"
   输出：错误：丢弃数量 2 不能大于等于骰子个数 2
   python diceroll.py --name-list "甲,乙" --pick 5
   输出：错误：只能从 2 人中抽取，请求 5 人
9. 爆炸骰示例：
   python diceroll.py "1d6e" --detail --seed 12
   输出：1d6e = 11
   骰子明细：[6, 5]（爆炸追加 1 次）

【六、验收标准】

[ ] 3d6 结果在 3~18 之间且 --detail 明细个数等于骰子数
[ ] 3d6+2 的结果等于明细之和加 2
[ ] 4d6dl1 丢弃的恰好是最小值，2d20kh1 保留的恰好是最大值
[ ] 2d10-1 支持负数常数并计算正确
[ ] 多段表达式 2d6+1d8+3 求值正确
[ ] 1d6e 在掷出 6 时追加骰子，且追加次数有上限不会死循环
[ ] 同一 --seed 与参数两次运行输出完全一致
[ ] --repeat 1000 输出的均值接近 (N×(M+1)/2 + 常数)
[ ] --pick K 结果不重复且人数正确
[ ] --group N 的组间人数差不超过 1，组数正确
[ ] 12 人分 4 组时输出总人数为 12
[ ] 表达式语法错误的提示包含出错位置
[ ] 骰子个数、面数、抽取人数越界时都返回退出码 2
[ ] 源码中没有 eval 或 exec
[ ] 名单文件中的空行与 # 注释被正确忽略

【七、可选扩展】

1. 增加优势/劣势掷骰（2d20kh1 / 2d20kl1）的语法糖 --adv 与 --dis。
2. 增加常用表达式预设：--preset dnd-attr 表示 4d6dl1 六次。
3. 支持从 CSV 读取名单并附带权重列，实现加权抽签。
4. 增加 --save 把抽签或分组结果写入文件，便于发到群里。
5. 增加 --histogram 输出点数分布的字符直方图。

【八、涉及知识点】

- 词法分析与递归下降解析的基本思路
- 正则表达式在分词中的应用与位置信息记录
- 随机数种子的作用与可复现性
- random.Random 实例与全局状态的差异
- random.sample 与洗牌算法保证的均匀性
- 修饰符（丢弃、保留、重掷、爆炸）的实现顺序
- statistics 模块计算均值、标准差
- dataclass 与 Enum 描述语法树节点
- 输入校验与防死循环（爆炸骰上限）
================================================================================
