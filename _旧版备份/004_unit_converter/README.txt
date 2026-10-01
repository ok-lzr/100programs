================================================================================
项目编号：004                    难度等级：★☆☆☆☆（小型项目）
项目名称：通用单位换算器
所属分类：命令行工具 / 单位换算
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

写文档时要换算英寸、买家具要比对平方米、下电影要看 GB 和 MiB 的区别、跑步要看配速
对应的公里与英里。这些换算单独查一次不难，难的是随手可用且不出错。这个工具用一个
“基准单位”模型把长度、重量、面积、体积、速度、数据容量六大类单位统一起来，任意两个
同类单位都能互转。

目标用户是需要频繁做工程换算的开发者、做跨境购物比价的消费者、以及把课程作业里的
单位理清的学生。设计重点是数据驱动的单位表：新增一个单位只需在表里加一行，不改任何
逻辑代码。

做完之后应当能拿来干这些事：一条命令把 12 inch 转成 cm；查看数据容量里 GB 与 GiB
的差别；列出某个类别下所有可用单位与别名；用 --list-categories 先看有哪些类别。

【二、功能需求清单】

1. 核心功能
   1.1 六大类别：length 长度、mass 重量、area 面积、volume 体积、speed 速度、
       data 数据容量。
   1.2 每个类别内任意两单位互转，共支持不少于 45 个单位。
   1.3 长度：m、km、cm、mm、um（微米）、in、ft、yd、mi、nmi（海里）。
   1.4 重量：kg、g、mg、t（吨）、lb、oz、st（英石）。
   1.5 面积：m2、km2、cm2、ha（公顷）、acre、ft2、in2、mu（亩）。
   1.6 体积：l、ml、m3、cm3、gal（美制加仑）、qt、pt、cup、floz。
   1.7 速度：mps、kmph、mph、kn（节）、fps。
   1.8 数据容量：B、KB、MB、GB、TB、KiB、MiB、GiB、TiB。十进制前缀按 1000，
       二进制前缀按 1024，两者必须区分对待。
   1.9 别名支持：meter/metre/米、kilogram/kg/公斤、inch/in/英寸 等中英文写法。

2. 输入与交互
   2.1 转换形式：python convert.py 12 inch cm
   2.2 指定类别形式：python convert.py 1 GB GiB --category data
   2.3 不指定类别时按目标单位自动推断类别；若源与目标不在同一类别则报错。
   2.4 列出单位：python convert.py --list length 输出该类别所有单位与别名。
   2.5 列出类别：python convert.py --list-categories。
   2.6 批量：python convert.py --file in.txt --from km --to mi，文件每行一个数值，
       允许空行与 # 开头的注释行。
   2.7 交互模式：不带参数运行时进入问答式换算。
   2.8 --precision 控制小数位数，默认 6，输出时去掉多余的尾随零。

3. 输出与展示
   3.1 单次换算：12 in = 30.48 cm
   3.2 --verbose 时额外输出：类别 length，换算系数 2.54，公式 in -> m -> cm。
   3.3 列表输出按字母顺序排列，格式为 “单位符号（标准名）: 别名1, 别名2”。
   3.4 批量模式逐行输出结果，末尾输出 “共 12 行，成功 12 行”。
   3.5 --json 输出 {"value":12,"from":"in","to":"cm","category":"length",
       "result":30.48}。

4. 异常与边界处理
   4.1 数值非数字时打印 “错误：无法解析的数值 'abc'”，退出码 2。
   4.2 单位无法识别时打印 “错误：未知单位 'xyz'，用 --list-categories 查看支持的类别”。
   4.3 源与目标跨类别（如 kg -> km）时打印
       “错误：kg 属于 mass，km 属于 length，不能直接换算”，退出码 2。
   4.4 同类别同一单位时原样返回，不做多余格式化。
   4.5 负数值允许（如温差、海拔），但数据容量类别不允许负数，出现时提示
       “错误：数据容量不能为负数”。
   4.6 极大或极小结果（绝对值大于 1e15 或小于 1e-9）时改用科学计数法显示，
       例如 1e-09。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库，需要 argparse、json、math、dataclasses、typing、
   pathlib、logging。
3. 禁止事项：禁止为每个单位对写一条 if 分支；禁止把换算系数散落在函数内部，
   必须集中在一张表里；禁止用字符串拼接浮点数导致精度显示失控。
4. 代码组织：
   4.1 UnitDef：dataclass(frozen=True)，字段 symbol、name、factor（相对基准单位的
       系数）、aliases: tuple[str, ...]。
   4.2 CATEGORIES：dict[str, Category]，Category 含 key、display_name、base_unit、
       units: dict[str, UnitDef]。
   4.3 基准单位：length 用 m，mass 用 kg，area 用 m2，volume 用 l，speed 用 mps，
       data 用 B。
   4.4 函数：normalize_unit(text, category=None) -> tuple[str, str]（返回类别与符号）、
       convert(value, src, dst, category=None) -> float、list_units(category)、
       format_number(value, precision) -> str。
   4.5 别名查表必须在启动时构建小写别名到 (category, symbol) 的索引字典。
5. 编码规范：类型注解与 docstring；单位表用整齐的每行一条形式书写并加注释说明系数
   的来源（如 1 in = 0.0254 m）；禁止在输出中使用未定义精度。

【四、设计要点】

1. 数据结构：
   1.1 UnitDef 的 factor 统一表示“1 个该单位等于多少个基准单位”。
       例如 in 的 factor 为 0.0254，ft 的 factor 为 0.3048，mi 的 factor 为 1609.344。
   1.2 数据容量基准取 B：KB=1000、MB=1e6、GB=1e9、TB=1e12；
       KiB=1024、MiB=1048576、GiB=1073741824、TiB=1099511627776。
   1.3 AliasIndex：dict[str, tuple[str, str]]，键为小写别名。
2. 关键算法或流程：
   2.1 换算公式：result = value × factor(src) / factor(dst)。
   2.2 单位解析流程：先查别名索引得到 (category, symbol)；未命中时若给了 --category
       则只在该类别内按符号与小写名匹配；仍失败则给出错误。
   2.3 类别一致性校验：若源与目标解析出的类别不同即报错并说明双方类别。
   2.4 数字格式化：先用 round(value, precision) 再转字符串，若结果不含小数点且
       绝对值小于 1e15 则不加小数点；超出阈值改用 "%.6g" 格式。
   2.5 批量流程：逐行 strip -> 跳过空行与 # 注释 -> 解析 -> 换算 -> 输出，
       统计成功与失败行数。
3. 接口或命令设计：
   3.1 convert(value: float, src: str, dst: str, category: str | None = None)
       -> tuple[float, str]（返回结果与类别）
   3.2 normalize_unit(text: str, category: str | None = None) -> tuple[str, str]
   3.3 list_units(category: str) -> list[str]
   3.4 命令行：位置参数 value、src、dst；可选 --category、--list、--list-categories、
       --file、--from、--to、--precision、--json、--verbose。

【五、运行方式与示例】

1. 运行准备：无需安装依赖，直接运行脚本。
2. 长度换算：
   python convert.py 12 inch cm
   输出：12 in = 30.48 cm
3. 数据容量换算（区分十进制与二进制）：
   python convert.py 1 GB GiB
   输出：1 GB = 0.931323 GiB
4. 重量换算（中文别名）：
   python convert.py 5 公斤 磅
   输出：5 kg = 11.023113 lb
5. 查看类别下单位：
   python convert.py --list data
   输出：
   B（byte）: b, byte, 字节
   GB（gigabyte）: gb, 吉字节
   GiB（gibibyte）: gib
   ……
6. 批量换算（in.txt 每行一个数值）：
   python convert.py --file in.txt --from km --to mi
   输出：
   1 -> 0.621371
   5 -> 3.106856
   共 2 行，成功 2 行
7. 异常输入示例：
   python convert.py 10 kg km
   输出：错误：kg 属于 mass，km 属于 length，不能直接换算
   退出码：2
   python convert.py abc m ft
   输出：错误：无法解析的数值 'abc'
   python convert.py -1 MB GB
   输出：错误：数据容量不能为负数
8. 科学计数法示例：
   python convert.py 0.000000001 m nm
   输出：1 nm = 1e-09 m 形式的结果会使用科学计数法显示

【六、验收标准】

[ ] 六大类别共支持不少于 45 个单位且都能互转
[ ] 12 inch cm 精确输出 30.48
[ ] 1 GB GiB 输出 0.931323（保留 6 位小数并去除尾零）
[ ] 1 GiB GB 输出 1.073742
[ ] 1 mi km 输出 1.609344，1 nmi km 输出 1.852
[ ] 1 acre m2 输出 4046.856422，1 mu m2 输出 666.666667 附近
[ ] 1 美制加仑约等于 3.785412 升
[ ] 中英文别名（inch/英寸、kg/公斤/千克）都能被识别
[ ] 跨类别换算报错信息中同时给出两个类别名
[ ] --list 输出的单位按字母顺序且包含别名
[ ] --precision 能改变输出小数位数
[ ] 批量模式正确跳过空行与 # 注释行
[ ] 数据容量负数输入被拒绝
[ ] 全程仅使用标准库，未对每个单位对写独立分支

【七、可选扩展】

1. 增加 temperature 类别，但需支持偏移量而不只是比例系数（可作为进阶练习）。
2. 增加 pressure 压强与 energy 能量类别（Pa、bar、psi、J、cal、kWh）。
3. 增加 --table 参数按表格对齐输出多组换算结果。
4. 支持自定义单位文件 units.json，运行时合并进内置单位表。
5. 增加 “反查” 功能：给出两个数值与单位，反推换算系数。

【八、涉及知识点】

- 数据驱动设计：用表结构替代分支逻辑
- dataclass(frozen=True) 与不可变配置对象
- 浮点数格式化：round、format、%g 的差异
- 十进制与二进制数据容量前缀的区别
- 别名索引与大小写不敏感查找
- 字典嵌套结构与启动期预处理
- 文件逐行读取与注释行过滤
- argparse 子功能与互斥参数设计
- 单位制的历史与常用换算系数的记忆方法
================================================================================
