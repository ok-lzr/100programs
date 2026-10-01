================================================================================
项目编号：036                    难度等级：★★★☆☆（小型项目）
项目名称：简易记事本
所属分类：图形界面 / 文本编辑
建议工时：6 ~ 8 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库 tkinter）
================================================================================

【一、项目背景与目标】

随手记点东西时，系统自带记事本要么功能太少（没有查找替换、没有自动备份），要么太重
（启动慢、弹窗多）。写代码草稿或写会议记录时，最怕的是断电、误关窗口导致内容丢失，
而绝大多数轻量编辑器都不做自动备份。

本项目用 tkinter 实现一个"够用就好"的桌面记事本，重点补上三个真实痛点：
一是未保存变更的三重保护（标题星号提示、关闭前询问、定时自动备份到恢复目录）；
二是方便的查找与替换（支持大小写敏感、整词匹配、全部替换）；
三是舒适的阅读体验（字体缩放、等宽/宋体切换、状态栏显示行列号与字符数、换行开关）。

目标用户是需要在 Windows/Linux/macOS 上快速记录文字的学生与办公人员。做成之后，
它就是一个可以日常使用的真实工具，同时覆盖 tkinter 文本组件、菜单、对话框、快捷键、
文件编码处理、定时任务等全部核心知识点。

【二、功能需求清单】

1. 核心功能
   1.1 文件操作：新建、打开、保存、另存为、最近文件列表（最多 10 条，持久化到配置）。
       支持 UTF-8、UTF-8-BOM、GBK、UTF-16 四种编码的读取（自动探测）与保存（可指定）。
   1.2 编辑操作：撤销、重做、剪切、复制、粘贴、删除、全选、时间日期插入。
       Undo/Redo 直接使用 Text 组件的 undo=True 与 edit_undo/edit_redo，并维护栈深度。
   1.3 查找：查找框输入关键词，支持"区分大小写"、"整词匹配"、"循环查找"三个选项；
       查找到的匹配项用 tag 高亮（选中态 sel 样式），按 F3 找下一个、Shift+F3 找上一个。
   1.4 替换：替换当前、全部替换；全部替换后弹出"共替换 N 处"的提示；
       支持"替换后自动继续查找下一处"的选项。
   1.5 字体与显示：Ctrl+加号/Ctrl+减号缩放字号（范围 8~48），Ctrl+0 复位为 12；
       字体在 Consolas（等宽）与微软雅黑（比例）之间切换；自动换行开关；显示/隐藏状态栏。
   1.6 自动备份：内容变更后 30 秒无输入，把当前缓冲区写入 <用户目录>/.notepad_gui/backup/
       <文件名或 untitled>.bak（含原始路径、编码、时间戳的头部注释）；
       程序启动时若发现比源文件更新的备份，弹窗询问是否恢复。
   1.7 状态栏：显示"行 L，列 C"（随光标移动实时更新）、总字符数、总行数、
       当前文件名与编码、是否已修改。
   1.8 编码与换行：保存时可选 CRLF 或 LF 换行；打开时若检测到混合换行给出提示。

2. 输入与交互（控件布局与事件绑定）
   2.1 主窗口：Tk()，标题 "简易记事本 - <文件名>"（未保存时带 * 号），初始 900x620，
       minsize(600, 400)。整体用 grid：row=0 菜单栏（Menu 挂到 root.config(menu=...)），
       row=1 查找条 Frame，row=2 文本区 Frame（weight=1），row=3 状态栏 Frame。
   2.2 菜单栏结构（必须完整实现）：
       文件(F)：新建 Ctrl+N、打开 Ctrl+O、保存 Ctrl+S、另存为 Ctrl+Shift+S、
                最近文件（子菜单，动态生成）、退出 Ctrl+Q
       编辑(E)：撤销 Ctrl+Z、重做 Ctrl+Y、剪切 Ctrl+X、复制 Ctrl+C、粘贴 Ctrl+V、
                全选 Ctrl+A、插入日期时间 F5
       查找(S)：查找 Ctrl+F、查找下一个 F3、查找上一个 Shift+F3、替换 Ctrl+H、转到行 Ctrl+G
       格式(O)：自动换行（勾选项 Checkbutton）、字体（Consolas/微软雅黑/宋体）、
                放大 Ctrl+Plus、缩小 Ctrl+Minus、复位 Ctrl+0
       视图(V)：状态栏（勾选项）、备份目录（在文件管理器中打开）
       帮助(H)：快捷键说明、关于
   2.3 查找条 Frame（row=1，默认隐藏 pack_forget）：
       第一行：Label("查找") + Entry(find_entry, width=30) + Checkbutton(区分大小写)
               + Checkbutton(整词) + Button("下一个") + Button("上一个") + Button("关闭")
       第二行：Label("替换为") + Entry(replace_entry, width=30) + Button("替换")
               + Button("全部替换")
       两行用 Frame + pack(side="left") 排布；打开替换时第二行显示，否则隐藏。
   2.4 文本区：tkinter.scrolledtext.ScrolledText，内含垂直与水平 Scrollbar；
       配置 undo=True、maxundo=200、autoseparators=True、wrap="word"、
       font=("Consolas", 12)、tabs=("1c")、insertwidth=2。
       左右边距通过 padx=6 与内部 -padx 选项设置，行间距用 spacing1=1、spacing3=1。
   2.5 状态栏 Frame（row=3）：三个 Label 分别左、中、右对齐 ——
       左侧显示行/列，中间显示字符数与行数，右侧显示编码与修改标记。
   2.6 事件绑定（必须全部实现）：
       - text.bind("<<Modified>>", self.on_modified)：Tk 的 Modified 虚拟事件只触发一次，
         必须在处理函数开头调用 text.edit_modified(False) 复位，这是本项目的关键细节。
       - text.bind("<KeyRelease>", self.update_status)：更新行列号与统计。
       - text.bind("<ButtonRelease-1>", self.update_status)：鼠标点击后也刷新。
       - root.bind("<Control-f>", ...)、<Control-h>、<Control-s>、<Control-o>、
         <Control-n>、<Control-z>、<Control-y>、<F3>、<Shift-F3>、<F5>、<Control-plus>、
         <Control-minus>、<Control-Key-0>、<Control-g>、<Escape>（关闭查找条）。
       - root.protocol("WM_DELETE_WINDOW", self.on_close)。
       - 打开文件时使用 filedialog.askopenfilename 并把返回路径规范化之后再做最近文件去重。
   2.7 交互流程（必须按此描述实现）：
       (a) 输入文字 → <<Modified>> 触发 → 标题加 *、状态栏"已修改"、启动 30 秒备份定时器；
       (b) 按 Ctrl+F → 查找条显示、焦点进入 find_entry、上次关键词保留并自动选中；
       (c) 输入关键词并回车 → 从当前光标位置向后搜索，命中则 see() 滚动到可见并选中，
           未命中则弹"未找到 'xxx'（已从文档开头重新搜索）"；
       (d) 关闭窗口 → 若已修改则 messagebox.askyesnocancel("保存更改？")，
           选"是"则保存后关闭，选"否"直接关闭，选"取消"停留。
   2.8 拖放（可选但需在文档标注）：若运行环境有 tkinterdnd2 则支持拖入文件，
       否则菜单中该项隐藏；不得因缺少该库而启动失败。

3. 输出与展示
   3.1 所有对话框使用 tkinter.messagebox，标题统一为"简易记事本"。
   3.2 保存成功后在状态栏短暂显示"已保存到 <路径>"，3 秒后恢复常规状态。
   3.3 出错对话框必须给出可操作信息，例如
       "无法以 GBK 编码保存：第 120 行存在无法编码的字符 '𠮷'，请改用 UTF-8。"
   3.4 配置文件保存到 <用户目录>/.notepad_gui/config.json，
       内容包含 font_family、font_size、wrap、show_status、recent_files、
       window_geometry；启动时读取并恢复窗口位置与字号。

4. 异常与边界处理
   4.1 打开不存在的文件：报"文件不存在：<路径>"并清空最近文件中的该条目。
   4.2 打开二进制文件：读取前 8KB 检测是否含 \x00 字节，若有则提示"这似乎是二进制文件，
       确定要打开吗？"。
   4.3 编码探测失败：依次尝试 utf-8-sig、utf-8、gbk、utf-16，
       全部失败则用 utf-8 加 errors="replace" 打开并提示"部分字符已替换显示"。
   4.4 保存时无写权限：捕获 PermissionError，提示改用"另存为"。
   4.5 磁盘满（OSError errno 28）：提示"磁盘空间不足，请清理后重试"，不丢失缓冲区内容。
   4.6 大文件（> 5 MB）：打开前询问，并临时禁用自动换行与撤销以保持流畅。
   4.7 替换全部时关键词为空：报"查找内容不能为空"。
   4.8 备份目录不可写：禁用自动备份并在状态栏提示，不反复弹窗。
   4.9 关闭时若有未完成的备份定时器：先 after_cancel 再退出，避免回调访问已销毁控件。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；使用标准库 tkinter（Linux 下需 python3-tk）。
2. 允许使用的库：仅使用标准库，包括 tkinter、tkinter.scrolledtext、
   tkinter.filedialog、tkinter.messagebox、tkinter.simpledialog、pathlib、json、
   re、time、os、datetime、logging、dataclasses、typing、codecs。
3. 禁止事项：禁止在 <<Modified>> 回调中忘记 edit_modified(False)（会导致状态混乱）；
   禁止在主线程之外操作 Tk 控件；禁止无提示地覆盖用户文件；
   禁止把用户文本内容写入日志（日志只记录操作类型与文件路径）；
   禁止使用 from tkinter import * 通配导入。
4. 代码组织：至少包含 editor_app.py（界面与事件）、fileio.py（编码探测与读写）、
   search.py（查找替换逻辑，纯逻辑可单测）、backup.py（自动备份与恢复检测）、
   config.py（配置读写）。查找逻辑签名固定为
   find_all(text: str, keyword: str, case: bool, whole: bool) -> list[tuple[int, int]]。
5. 编码规范：类型注解与 docstring 齐全；文件读写一律显式 encoding；
   所有 Tk 回调方法以 on_ 开头；界面常量（颜色、字号上下限）集中在文件头部。

【四、设计要点】

1. 数据结构：
   - EditorState：path: Path | None，encoding: str，dirty: bool，wrap: bool，
     font_family: str，font_size: int，last_search: str，last_replace: str。
   - BackupMeta：origin: str，encoding: str，backup_time: str，content: str。
   - 最近文件列表为 list[str]，按最近使用时间排序，上限 10，重复路径去重后置顶。
   - 查找结果使用 Text 的 tag 机制：定义 tag "match"（背景 #FFF3A3）与
     "current"（背景 #FFC107）；每次查找前 text.tag_remove 清空旧标记。
2. 关键算法或流程：
   2.1 编码探测流程：读取原始 bytes → 若前 3 字节为 EF BB BF 则 utf-8-sig；
       BOM 为 FF FE 则 utf-16；否则尝试 utf-8 decode（strict），失败则尝试 gbk，
       再失败则 utf-8 + errors="replace"；把探测结果记录到 EditorState.encoding。
   2.2 查找实现（不使用 Text.search，需自行实现以支持整词与统计）：
       (a) 用 text.get("1.0", "end-1c") 取全文；
       (b) 若 case 为假，在比较时对文本与关键词同时 lower()，但索引用原文；
       (c) 整词匹配用 re.escape(keyword) 加边界 (?<![0-9A-Za-z_]) 与 (?![0-9A-Za-z_])；
       (d) 返回所有 (start_offset, end_offset) 列表，再由调用方转换为
           Tk 的 "1.0+Nc" 索引（用 f"1.0+{off}c" 字符串）。
   2.3 查找下一个：从当前 insert 位置偏移量开始，在结果列表中线性查找第一个 start >
       current_offset 的项；没有则回到第一项并提示已回到开头（循环查找开启时）。
   2.4 全部替换：为避免偏移量失效，必须从后往前替换 ——
       先算出所有匹配区间，按 start 降序逐个 text.delete/text.insert，
       而不是边查边替换。
   2.5 自动备份：使用 root.after(30000, self.do_backup)，每次内容变更时
       先 after_cancel 旧定时器再重新注册（实现"停止输入 30 秒后备份"的防抖语义）；
       备份文件格式：前三行为 "# origin: <路径>"、"# encoding: <编码>"、
       "# time: <ISO 时间>"，第四行起为正文。
   2.6 行列号计算：row, col = text.index("insert").split(".")，
       再把 col 转为 int 后 +1 显示（Tk 列号从 0 开始）。
   2.7 标题与星号：update_title() 统一负责，文件名取 path.name，
       未保存时显示 "未命名"，dirty 时前缀 "简易记事本 - *<名称>"。
3. 接口或命令设计：
   运行：python editor_app.py [文件名] [--encoding utf-8] [--no-backup]
   纯逻辑调用示例（供测试使用）：
       from search import find_all
       find_all("Hello hello HELLO", "hello", case=False, whole=True) -> 3 个区间
       find_all("Hello hello HELLO", "hello", case=True, whole=True)  -> 1 个区间

【五、运行方式与示例】

安装：无需安装（Linux 需要 python3-tk 包）。
运行：
   python editor_app.py
   python editor_app.py .\notes\meeting.txt --encoding gbk

示例一（新建、编辑与保存）：
   操作：启动后输入 "会议记录：1. 需求评审；2. 排期" → 按 Ctrl+S
   界面：弹出保存对话框 → 选择 D:\notes\meeting.txt → 标题变为 "简易记事本 - meeting.txt"
   状态栏：行 1，列 21 | 18 个字符，1 行 | UTF-8

示例二（打开 GBK 文件并按 UTF-8 另存）：
   输入：python editor_app.py .\legacy\old.txt
   输出：状态栏显示 "GBK"；内容中文正常显示
   操作：Ctrl+Shift+S 另存为 new_utf8.txt，编码下拉选 UTF-8
   界面：状态栏变为 "UTF-8"，文件在其它编辑器中打开中文正常

示例三（查找与全部替换）：
   操作：Ctrl+H → 查找框输入 "TODO"、替换框输入 "已完成" → 点"全部替换"
   界面：弹出 "共替换 7 处"；文档中 7 处 TODO 全部变为"已完成"，可 Ctrl+Z 一次撤销

示例四（异常输入）：
   操作：用记事本打开本程序的 .pyc 文件
   界面：弹出 "这似乎是二进制文件，确定要打开吗？" → 选择"否"则取消打开，缓冲区内容不变

示例五（自动备份与恢复）：
   操作：输入一段文字后不保存，等待 30 秒 → 关闭窗口并选"取消"→ 手动结束进程
   重启程序：提示 "发现比源文件更新的自动备份（2024-05-20 10:12），是否恢复？"
   选择"是"：缓冲区内容为上次输入的文字

【六、验收标准】

[ ] 输入文字后标题立即出现 * 号，保存后 * 号消失。
[ ] 关闭有未保存内容的窗口时会弹出三选一对话框，选"取消"后程序不退出。
[ ] 打开 UTF-8、UTF-8-BOM、GBK、UTF-16 四种编码的测试文件，中文均正确显示。
[ ] 保存为 GBK 时遇到无法编码的字符会给出明确提示，且不写坏原文件。
[ ] Ctrl+F 打开查找条，回车查找下一处，F3 与 Shift+F3 可前后循环。
[ ] 查找"大小写敏感"勾选前后，同一关键词的命中数量不同且符合预期。
[ ] 整词匹配搜索 "cat" 不会命中 "category"。
[ ] 全部替换后 Ctrl+Z 可以一次性撤销全部替换结果。
[ ] 连续 30 秒无输入后，备份目录中出现对应 .bak 文件，头部三行元信息正确。
[ ] 备份比源文件更新时，启动会询问恢复。
[ ] 状态栏行列号随光标移动实时更新，列号从 1 开始计数。
[ ] Ctrl+加号把字号从 12 提升到 13，Ctrl+0 复位为 12，字号超限时不再变化。
[ ] 最近文件列表最多 10 条，重复打开同一文件不会产生重复条目。
[ ] 打开超过 5 MB 的文件前会询问，选择继续后界面仍可滚动。
[ ] 关闭程序后重新打开，窗口大小、位置、字体设置与上次一致。
[ ] 日志文件中不含任何用户输入的正文内容。

【七、可选扩展】

1. 增加多标签页编辑（ttk.Notebook），每个标签独立的 EditorState。
2. 增加 Markdown 语法高亮（用 Text 的 tag 对标题、列表、代码块着色）与预览窗口。
3. 增加导出为 HTML/PDF 功能，保留换行与字体。
4. 增加行号栏：用一个同步滚动的 Canvas 或 Text 组件绘制行号。
5. 增加专注模式（隐藏菜单栏与状态栏、居中列宽限制）提升写作体验。

【八、涉及知识点】

- tkinter Text 组件的高级用法：tag、mark、index 表达式、undo/redo 栈
- <<Modified>> 虚拟事件的单次触发语义与 edit_modified(False) 复位
- 菜单（Menu）与快捷键（accelerator + bind）的双重实现
- 文件编码探测（BOM 识别、多编码回退）与 errors 策略
- after/after_cancel 实现防抖定时备份
- 从后往前替换避免索引失效的算法
- JSON 配置持久化与用户目录约定（~/.notepad_gui/）
- 二进制文件检测与用户确认流程
================================================================================
