================================================================================
项目编号：002                    难度等级：★☆☆☆☆（小型项目）
项目名称：BMI 与健康指标计算器
所属分类：命令行工具 / 健康计算
建议工时：3 ~ 5 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

不少人每年体检都会看到一个 BMI 数字，但不知道它处在什么区间、和自己身高相比合理体重
是多少、每天应该吃多少热量才不至于长胖。这个工具把身高体重输入进去，一次算出 BMI、
中国成人 BMI 分级、标准体重范围、体脂率估算区间、基础代谢率（BMR）和按活动强度
折算的每日建议热量（TDEE）。

目标用户是想减脂或增肌的普通人、健身房教练做初步评估、以及好奇自己每日热量需求的
学生。工具只做公式计算与区间对照，不做医学诊断，输出中必须带免责提示。

做完之后应当能拿来干这些事：输入 170cm / 65kg，得到 BMI 22.5、属于正常范围、
理想体重区间 53.5~69.4kg、BMR 约 1500 kcal、久坐人群每日建议 1800 kcal；把
一周的体重记录批量读入并输出趋势表；把结果导出为 CSV 交给教练。

【二、功能需求清单】

1. 核心功能
   1.1 计算 BMI：BMI = 体重(kg) / 身高(m)²，保留一位小数。
   1.2 中国成人 BMI 分级：低于 18.5 偏瘦；18.5~23.9 正常；24.0~27.9 超重；
       28.0 及以上 肥胖。分级边界必须含下不含上，避免 24.0 被算成正常。
   1.3 标准体重：成人男性 (身高cm - 80) × 0.7，女性 (身高cm - 70) × 0.6，
       并给出 ±10% 的合理体重区间。
   1.4 体脂率估算：使用 Deurenberg 公式，体脂率 = 1.2 × BMI + 0.23 × 年龄
       - 10.8 × 性别系数 - 5.4（男性 1、女性 0），保留一位小数。
   1.5 BMR：使用 Mifflin-St Jeor 公式。男性 10×体重 + 6.25×身高 - 5×年龄 + 5；
       女性 10×体重 + 6.25×身高 - 5×年龄 - 161，单位 kcal/天，取整。
   1.6 TDEE：BMR 乘以活动系数，系数表为 sed=1.2、light=1.375、mod=1.55、
       heavy=1.725、athlete=1.9，结果为整数。

2. 输入与交互
   2.1 命令行：python bmi.py --height 170 --weight 65 --age 28 --gender male
       --activity light
   2.2 --height 单位固定为厘米，接受 80~250 之间的值；--weight 单位固定为公斤，
       接受 20~300 之间的值；--age 接受 10~120 之间的整数。
   2.3 --gender 接受 male/female/m/f/男/女，内部统一存为 "male" 或 "female"。
   2.4 缺少必填参数时以交互问答方式补齐，逐项提示并校验。
   2.5 支持 --batch data.csv，CSV 表头需包含 height_cm、weight_kg、age、gender 四列，
       activity 列可选，缺失时按 sed 处理。

3. 输出与展示
   3.1 交互与单次模式输出对齐的多行报告，字段名后接数值与单位，例如：
       BMI：22.5（正常）
       标准体重范围：53.5 ~ 65.4 kg
       体脂率估算：17.8 %
       基础代谢率 BMR：1518 kcal/天
       每日建议热量 TDEE：1822 kcal（活动强度：light）
   3.2 报告末尾固定输出一行提示：
       本结果为公式估算，仅供健康参考，不能替代医生诊断。
   3.3 --json 时输出单行 JSON，键为 bmi、bmi_level、ideal_min、ideal_max、
       body_fat、bmr、tdee、activity。
   3.4 批量模式输出表格，每行一个人，末行输出各指标平均值。

4. 异常与边界处理
   4.1 身高或体重非数字时打印 “错误：身高必须是数字”，退出码 2。
   4.2 数值超出允许范围时打印具体范围，如 “错误：身高需在 80 ~ 250 厘米之间”。
   4.3 性别不在识别表中时列出可接受写法后退出，退出码 2。
   4.4 年龄小于 18 时额外打印 “注意：该公式面向成年人，未成年人结果仅供参考”。
   4.5 批量文件中某行缺列或数值非法时跳过该行，记录行号，最后汇总 “跳过 3 行”。
   4.6 计算结果出现除零或非有限值时兜底输出 “无法计算，请检查输入”。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库，需要 argparse、csv、json、math、dataclasses、
   typing、logging。
3. 禁止事项：禁止把 BMI 分级的阈值写死在 if 语句里，必须定义为模块级常量表；
   禁止用浮点相等比较判断区间边界；禁止在没有单位换算的情况下混用米与厘米。
4. 代码组织：
   4.1 常量区：BMI_LEVELS（列表，元素为 (下限, 名称)）、ACTIVITY_FACTORS 字典、
       GENDER_ALIASES 字典。
   4.2 纯计算函数：calc_bmi、calc_ideal_weight、calc_body_fat、calc_bmr、calc_tdee。
   4.3 展示函数：format_report(result) -> str、format_table(rows) -> str。
   4.4 校验函数：validate_height、validate_weight、validate_age、normalize_gender。
   4.5 main() 只负责解析参数、调用校验、分派到单次或批量流程。
5. 编码规范：类型注解 + docstring；数值输出统一走格式化函数，禁止在计算函数里
   拼接中文；常量命名全大写。

【四、设计要点】

1. 数据结构：
   1.1 HealthInput：dataclass，字段 height_cm: float、weight_kg: float、age: int、
       gender: str、activity: str。
   1.2 HealthResult：dataclass，字段 bmi、bmi_level、ideal_min、ideal_max、
       body_fat、bmr、tdee、activity、warnings: list[str]。
   1.3 BMI_LEVELS 顺序必须从高到低或从低到高严格排列，查找函数按顺序扫描并返回首个
       命中的名称。
2. 关键算法或流程：
   2.1 BMI 计算前先把厘米转米：height_m = height_cm / 100。
   2.2 分级查找：从低到高遍历 BMI_LEVELS，取最后一个 lower <= bmi 的项；
       若 bmi 小于首个下限则返回首个级别的名称。
   2.3 BMR 计算按性别分支，Mifflin-St Jeor 的性别常数放在常量表中。
   2.4 TDEE = round(bmr * ACTIVITY_FACTORS[activity])。
   2.5 批量流程：逐行构造 HealthInput -> 校验 -> 计算 -> 收集 HealthResult
       -> 计算平均值 -> 输出表格与平均值行。
3. 接口或命令设计：
   3.1 calc_bmi(height_cm: float, weight_kg: float) -> float
   3.2 classify_bmi(bmi: float) -> str
   3.3 calc_ideal_weight(height_cm: float, gender: str) -> tuple[float, float]
   3.4 calc_bmr(inp: HealthInput) -> int
   3.5 calc_tdee(bmr: int, activity: str) -> int
   3.6 命令行参数：--height、--weight、--age、--gender、--activity、--batch、--json。

【五、运行方式与示例】

1. 运行准备：python --version 确认 3.10 以上，无需安装任何依赖。
2. 完整单次计算：
   python bmi.py --height 170 --weight 65 --age 28 --gender male --activity light
   输出：
   BMI：22.5（正常）
   标准体重范围：53.5 ~ 65.4 kg
   体脂率估算：17.8 %
   基础代谢率 BMR：1518 kcal/天
   每日建议热量 TDEE：2087 kcal（活动强度：light）
   本结果为公式估算，仅供健康参考，不能替代医生诊断。
3. 交互补齐模式：
   python bmi.py --height 160 --weight 55
   输出：
   请输入年龄：26
   请输入性别（male/female）：女
   BMI：21.5（正常）
   ……
4. JSON 输出：
   python bmi.py --height 175 --weight 82 --age 40 --gender male --activity sed --json
   输出：
   {"bmi": 26.8, "bmi_level": "超重", "ideal_min": 59.9, "ideal_max": 73.2,
    "body_fat": 28.1, "bmr": 1731, "tdee": 2077, "activity": "sed"}
5. 批量模式（data.csv 含表头 height_cm,weight_kg,age,gender）：
   python bmi.py --batch data.csv
   输出：
   第 1 行：BMI 22.5 正常 BMR 1518 TDEE 1822
   第 2 行：BMI 26.8 超重 BMR 1731 TDEE 2077
   平均 BMI：24.7
6. 异常输入示例：
   python bmi.py --height 300 --weight 65 --age 28 --gender male
   输出：错误：身高需在 80 ~ 250 厘米之间
   退出码：2
   python bmi.py --height 170 --weight 65 --age 28 --gender 未知
   输出：错误：性别无法识别，可写 male / female / m / f / 男 / 女
7. 未成年人提示示例：
   python bmi.py --height 150 --weight 40 --age 15 --gender female
   输出首行：注意：该公式面向成年人，未成年人结果仅供参考

【六、验收标准】

[ ] 170cm / 65kg 的 BMI 输出为 22.5
[ ] BMI 24.0 被判定为超重而不是正常，23.9 被判定为正常
[ ] 男性的标准体重区间按 (身高-80)×0.7 上下浮动 10% 计算正确
[ ] 女性 BMR 使用 -161 常数，男性使用 +5 常数，误差在 1 kcal 内
[ ] 五种活动系数都能被识别，大小写不敏感
[ ] 身高、体重、年龄的越界输入均返回退出码 2 并带范围提示
[ ] 性别支持 male/female/m/f/男/女 六种写法
[ ] --json 输出的键名与要求完全一致
[ ] 批量模式能跳过非法行并汇总跳过数量
[ ] 批量模式输出平均值行
[ ] 报告中包含“不能替代医生诊断”的提示语
[ ] 年龄小于 18 时打印额外提示
[ ] 全程仅使用标准库
[ ] 所有计算函数可被单独导入调用且无副作用

【七、可选扩展】

1. 增加腰围与体脂公式（如美国海军法）并用两者做对比输出。
2. 增加 --target-weight 参数，反推达成目标 BMI 需要减少或增加多少公斤。
3. 支持读取 JSON 或 YAML 格式的个人档案，减少每次重复输入参数。
4. 增加简单位置图：用字符条展示 BMI 落在分级刻度的哪个位置。
5. 把结果追加写入本地 history.csv，并用 --history 查看历史变化。

【八、涉及知识点】

- 数学公式的代码化与浮点数四舍五入
- 区间分级的边界处理（含下不含上）
- dataclass 组织输入与输出模型
- argparse required 参数与交互补齐的混合模式
- json.dumps 的 ensure_ascii 与中文输出
- csv 批量读取与脏数据跳过
- 常量表驱动设计，避免魔法数字
- 输入校验与友好错误提示的编写方法
- 健康指标的适用人群与免责声明意识
================================================================================
