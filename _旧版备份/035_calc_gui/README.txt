================================================================================
项目编号：035                    难度等级：★★★☆☆（小型项目）
项目名称：图形计算器
所属分类：图形界面 / 桌面工具
建议工时：6 ~ 8 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库 tkinter）
================================================================================

【一、项目背景与目标】

Python 初学者学完语法后，最缺的就是一个"能看见自己成果"的项目。图形计算器是最合适的
练手对象：它既需要表达式解析这类真正的算法，又需要界面布局、事件绑定、状态机、键盘
交互这些桌面开发的完整技能，而且做完就能天天用。

本项目用 tkinter 实现一个桌面计算器，覆盖标准四则运算、括号与优先级、百分号、正负号、
倒数、平方根等常用功能，并提供科学模式（sin/cos/tan、log/ln、幂、阶乘、常量 π 与 e）、
历史记录面板（可点击回填）、以及完整的键盘支持。

目标用户是学习 GUI 编程的初学者，以及需要在桌面随手算一算的普通用户。整个项目只依赖
标准库，克隆下来即可运行，适合作为第一个"有界面"的完整作品。

【二、功能需求清单】

1. 核心功能
   1.1 表达式输入与求值：支持 + - * / // % **、一元正负号、括号嵌套、
       小数与科学计数法（1.5e3）；遵循数学优先级；不改变用户输入的显示形式。
   1.2 实时预览：每次输入变化后在表达式下方以灰色小字显示"= 结果"预览，
       表达式非法时预览显示为空，不弹错。
   1.3 科学函数：sin、cos、tan、asin、acos、atan、log（以 10 为底）、ln、
       exp、sqrt、fact（阶乘）、abs、pow(x,y)。角度/弧度通过 DEG/RAD 开关切换。
   1.4 常量与内存：π、e 两个常量按钮；MS/MR/M+/MC 四个内存键。
   1.5 历史记录：右侧列表显示最近 50 条"表达式 = 结果"，双击条目把结果回填到输入框，
       Delete 键删除选中条目，菜单提供"清空历史"。
   1.6 结果操作：等号求值后可继续用结果参与下一次运算（连续运算），
       CE 清除当前输入，C 完全复位（但保留历史与内存）。
   1.7 精度显示：结果最多显示 12 位有效数字，去掉尾部多余的 0，
       整数结果不带小数点；极大/极小值自动转科学计数法。
   1.8 复制粘贴：Ctrl+C 复制当前显示，Ctrl+V 粘贴，右键菜单提供复制/粘贴/清空。

2. 输入与交互（控件布局与事件绑定）
   2.1 主窗口：Tk()，标题"图形计算器"，初始 420x520，允许缩放；
       最小尺寸 380x460；使用 grid 布局，columnconfigure(0, weight=1)。
   2.2 上方显示区 Frame（row=0）：包含两个 Label ——
       expr_label（右对齐、字号 12、前景 #666666，显示当前表达式，允许换行最多 2 行）
       与 result_label（右对齐、字号 26、粗体、前景 #111111，显示结果或预览）。
   2.3 模式条 Frame（row=1）：三个 Radiobutton/Button —— DEG/RAD 切换、
       科学模式开关（显示/隐藏科学键区）、历史面板开关。
   2.4 按键区 Frame（row=2）：使用 grid 排列。
       标准模式 4 列 × 5 行：
         行1：C   CE   ←   ÷
         行2：7   8    9   ×
         行3：4   5    6   −
         行4：1   2    3   +
         行5：±   0    .   =
       科学模式在主行区上方插入 5 列 × 2 行：
         行0：sin cos tan π e
         行1：√   x²  xʸ  log ln
         行2：asin acos atan (  )
       所有按钮 width=1、sticky="nsew"，按键区行列 weight 均为 1，缩放时等比例铺满。
   2.5 历史面板 Frame（row=0 column=1，跨行，默认隐藏）：
       由 Listbox + 垂直 Scrollbar 组成，宽 220 像素；显示时主窗口宽度 +220。
   2.6 事件绑定（必须全部实现）：
       - 每个数字/运算符按钮：command=lambda k=text: self.on_key(k)（用默认参数避免闭包陷阱）。
       - 等号按钮：command=self.on_equals；Return 与 KP_Enter 绑定到 on_equals。
       - Escape 绑定到 on_clear（C）；Delete 绑定到 on_clear_entry（CE）；
         BackSpace 绑定到 on_backspace。
       - 数字键 0-9、'.'、'+'、'-'、'*'、'/'、'('、')'、'%'、'^'
         通过 root.bind("<Key>", self.on_key_event) 统一分发。
       - Ctrl+C / Ctrl+V / Ctrl+A 绑定到剪贴板与全选相关方法。
       - 窗口关闭协议 root.protocol("WM_DELETE_WINDOW", self.on_close)：
         若历史非空则询问是否保存到 history.json。
   2.7 交互流程（必须按此描述实现）：
       输入 "12+3" → expr_label 显示 "12+3"，result_label 预览显示 "= 15"
       → 按 Enter → 表达式移入历史列表（"12+3 = 15"），result_label 显示 "15"，
       内部状态 result_shown=True；此时再输入数字键，则清空表达式并以该数字开始新表达式；
       若输入的是运算符，则用当前结果作为新表达式的开头。
   2.8 输入长度限制：表达式超过 200 个字符时忽略后续输入并短暂提示"表达式过长"。

3. 输出与展示
   3.1 结果格式化规则：调用 format(x, ".12g") 得到基础字符串；
       若包含 "e" 则规范为 "1.5e+03" 形式；整数结果去掉 ".0"。
   3.2 错误显示：除零、负数开偶次方、tan(90°)、阶乘非非负整数等情况，
       在 result_label 显示 "错误：<原因>"（红色 #C0392B），表达式保留供修改。
   3.3 状态提示：右下角一个 Label 显示当前模式（DEG/RAD、内存是否有值 M）。
   3.4 历史持久化：保存到 <用户目录>/.calc_gui_history.json，
       结构为 [{"expr": "12+3", "result": "15", "ts": 1716000000.0}, ...]，最多 50 条。

4. 异常与边界处理
   4.1 除以零：显示 "错误：除数不能为零"，不写入历史。
   4.2 括号不匹配：预览为空，等号时显示 "错误：括号不匹配"。
   4.3 表达式以运算符结尾：等号时显示 "错误：表达式不完整"，不抛出异常。
   4.4 非数字字符：键盘输入字母等非法字符直接忽略（不进入表达式），不弹窗。
   4.5 阶乘范围：n 为负或非整数报错；n > 170 时报 "错误：数值过大（上限 170）"，
       因为 171! 超出 float 表示范围。
   4.6 浮点误差：0.1 + 0.2 显示为 0.3（".12g" 已处理），
       自测需覆盖 0.1+0.2、1/3、2**0.5 三个样例。
   4.7 tan 在 DEG 模式下遇到 90、270 等点：预先判断并报错，而不是返回 1.6e16。
   4.8 历史文件损坏（JSON 解析失败）：重命名为 history.json.bak 并以空历史启动，
       界面上提示一次原因。
   4.9 剪贴板无内容或内容非数字：粘贴时过滤非法字符后再插入，不报错。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；必须使用标准库 tkinter（Python 官方发行版自带）。
2. 允许使用的库：仅使用标准库，包括 tkinter、tkinter.ttk、tkinter.messagebox、
   math、json、re、pathlib、dataclasses、logging、typing。
   表达式求值允许使用 ast 模块做安全的语法解析。
3. 禁止事项：绝对禁止使用 eval() 或 exec() 直接对用户输入求值（这是本项目的核心安全
   约束，必须用 ast.parse + 白名单节点访问器实现）；
   禁止在按钮回调中使用未绑定默认参数的 lambda 变量（闭包陷阱）；
   禁止在 UI 线程中做耗时超过 50 毫秒的计算；禁止使用已废弃的 tkinter 写法
   （如 from tkinter import * 通配导入）。
4. 代码组织：至少包含四个模块 ——
   evaluator.py（ast 解析与求值，纯逻辑，无 UI 依赖，可单元测试）
   formatter.py（数值格式化与错误信息）
   history.py（历史记录读写与去重）
   app.py（tkinter 界面与事件绑定）
   求值入口签名固定为 evaluate(expr: str, deg_mode: bool) -> float，
   出错时抛出 CalculatorError（自定义异常，携带中文原因）。
5. 编码规范：类型注解与 docstring 齐全；类命名 CalculatorApp；回调方法统一 on_xxx 前缀；
   颜色与字号集中在模块级常量；evaluator.py 不得 import tkinter（保证逻辑可测）。

【四、设计要点】

1. 数据结构：
   - CalculatorError(Exception)：message: str。
   - HistoryEntry：expr: str，result: str，ts: float。
   - AppState：expr: str（当前表达式），result_shown: bool（是否刚显示过结果），
     memory: float | None，deg_mode: bool，scientific: bool，history_visible: bool。
   - ALLOWED_NODES：ast 白名单集合
     {Expression, BinOp, UnaryOp, Constant, Call, Name, Add, Sub, Mult, Div, FloorDiv,
      Mod, Pow, USub, UAdd}。
2. 关键算法或流程：
   2.1 安全求值流程：
       (a) 预处理：把 "×"→"*"、"÷"→"/"、"−"→"-"、"π"→"pi"、"√"→"sqrt"；
       (b) ast.parse(expr, mode="eval") 解析，语法错误转 CalculatorError("表达式不完整")；
       (c) 自定义 ast.NodeVisitor 遍历：遇到白名单外的节点立即抛错；
       (d) Name 节点只允许 pi、e 与白名单函数名，其余抛 NameError 风格的 CalculatorError；
       (e) 调用节点只允许 FUNCS 字典中的函数（sin/cos/tan/asin/acos/atan/log/ln/exp/
           sqrt/fact/abs/pow），参数个数做检查；
       (f) DEG 模式下，sin/cos/tan 的入参先 math.radians 转换，
           asin/acos/atan 的返回值再 math.degrees 转换。
   2.2 阶乘实现：fact(n) 要求 n 为非负整数（abs(n - round(n)) < 1e-9），
       n <= 170，用 math.factorial 计算后转 float。
   2.3 tan 的奇点判断：DEG 模式下 (deg - 90) % 180 == 0 时抛 "错误：tan 在该角度无定义"。
   2.4 预览求值防抖：输入变化后不在每次按键都求值，使用 after(180, ...) 定时器，
       取消上一次未触发的 after 回调（保存 after_id），避免连续输入时频繁解析。
   2.5 键盘分发流程：on_key_event 先判断 event.state 是否含 Ctrl 修饰位，
       有则走快捷键分支；否则按 event.char 或 event.keysym 映射到按钮文本再走 on_key。
   2.6 窗口自适应：绑定 <Configure> 事件，窗口宽度小于 460 时自动隐藏科学键区，
       恢复到 520 以上时按用户此前的开关状态恢复。
3. 接口或命令设计：
   运行：python app.py [--no-scientific] [--history-file PATH] [--debug]
   纯逻辑调用示例（供测试使用）：
       from evaluator import evaluate
       evaluate("2+3*4", deg_mode=True)      -> 14.0
       evaluate("sin(30)", deg_mode=True)     -> 0.49999999999999994
       evaluate("1/0", deg_mode=True)         -> 抛 CalculatorError("除数不能为零")

【五、运行方式与示例】

安装：无需安装（tkinter 随 Python 提供；Linux 下可能需要 apt install python3-tk）。
运行：
   python app.py
   python app.py --no-scientific --history-file .\my_history.json

示例一（四则运算与预览）：
   操作：依次点击 1、2、+、3
   界面：expr_label 显示 "12+"，result_label 显示 "= 12"；再点 3 后显示 "12+3"，预览 "= 15"
   操作：按 Enter
   界面：result_label 显示 "15"；历史列表新增一行 "12+3 = 15"

示例二（科学函数，DEG 模式）：
   操作：点 √ → 输入 16 → 按 Enter
   界面：expr_label "√16"，result_label "4"
   操作：点 sin，输入 30，按 Enter
   界面：result_label "0.5"；历史列表出现 "sin(30) = 0.5"

示例三（异常输入）：
   操作：输入 5/0 后按 Enter
   界面：result_label 以红色显示 "错误：除数不能为零"；表达式 "5/0" 保留；历史不新增
   操作：把表达式改为 5/0.0001 再按 Enter
   界面：result_label "50000"

示例四（键盘流）：
   操作：直接敲键盘 2 ^ 10 Enter
   界面：result_label "1024"；再敲 * 2 Enter → "2048"（结果参与的连续运算）

【六、验收标准】

[ ] 直接输入 "__import__('os').system('dir')" 不执行任何系统命令，界面显示非法表达式错误。
[ ] 表达式 "2+3*4" 结果为 14（而非 20），乘法优先级正确。
[ ] "(2+3)*4" 结果为 20，括号优先级正确。
[ ] "0.1+0.2" 显示为 0.3，不出现 0.30000000000000004。
[ ] "1/3" 显示为 0.333333333333（12 位有效数字）。
[ ] DEG 模式下 sin(30)=0.5、tan(45)=1；RAD 模式下 sin(pi/2)=1。
[ ] DEG 模式下 tan(90) 报"无定义"错误而不是显示巨大数值。
[ ] "5!" 结果为 120，"200!" 报数值过大错误。
[ ] "5/0" 报"除数不能为零"且不写入历史。
[ ] 键盘 0-9、运算符、Enter、BackSpace、Escape 的效果与对应按钮完全一致。
[ ] 双击历史条目后结果显示在 result_label，可继续参与运算。
[ ] 关闭窗口时若历史非空会询问保存，选择保存后 history.json 内容合法可读。
[ ] 手动破坏 history.json 后重启程序不崩溃，并生成 .bak 备份。
[ ] 窗口从 420 拉大到 900 宽时，按键区等比例铺满，无空白错位。
[ ] evaluator.py 不 import tkinter，可脱离图形环境在命令行中导入并调用。

【七、可选扩展】

1. 增加表达式输入框，允许直接用键盘编辑任意位置的表达式（当前为追加式输入）。
2. 增加单位换算与进制转换标签页（DEC/HEX/OCT/BIN 实时联动）。
3. 增加变量赋值（如 a=3 后可用 2*a），用自建符号表实现。
4. 增加主题切换（浅色/深色），用 ttk.Style 统一配置颜色与字体。

【八、涉及知识点】

- tkinter 窗口、Frame、Label、Button、Listbox、Scrollbar 与 grid 布局权重
- 控件回调与 lambda 默认参数绑定（闭包陷阱）
- bind 事件系统、keysym/char 区分、修饰键 event.state 位判断
- ast 模块的安全表达式求值（白名单 NodeVisitor）与 eval 的风险
- 浮点格式化（格式说明符 .12g）与浮点误差的可见化
- after/after_cancel 实现输入防抖
- JSON 持久化与用户目录定位（pathlib.Path.home()）
================================================================================
