================================================================================
项目编号：014                    难度等级：★☆☆☆☆（小型项目）
项目名称：目录树导出器
所属分类：命令行工具 / 文件与文本处理
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

写项目文档、交课程作业、给同事说明代码结构时，经常需要把某个目录的层级结构贴进文档里。
手工敲缩进极容易错层，用系统命令导出的结果又常常把 node_modules、__pycache__、.git
这些噪声目录一并带上，导致几十万行输出无法阅读。另一个常见需求是"这个盘里到底有哪些
大文件、总共有多少空间"，用资源管理器一层层点开效率很低。

本项目实现一个目录树导出器：扫描指定目录，按层级生成可读的树形文本，或输出 Markdown
格式以便直接贴进说明文档。它支持深度限制、模式白名单与黑名单、只看目录、是否显示文件大小
与修改时间、排序方式等参数，并在结尾给出目录数、文件数、总大小与最深层级等统计。

目标用户是写技术文档的开发与运维人员、整理交付材料的项目成员、需要清点磁盘占用的普通用户。
在安全方面，本工具是只读的：它只扫描目录并生成一份新的报告文件，
不会修改、移动或删除任何已有文件。

【二、功能需求清单】

1. 核心功能
   1.1 递归扫描：从根目录出发逐层遍历，输出标准树形结构，分支符号使用 "├──"、"└──"，
       层级缩进使用 "│   " 与 "    " 两种前缀，保证对齐正确。
   1.2 ASCII 模式：--ascii 时改用 "|--"、"`--" 与 "|   "，便于在不支持 UTF-8 的终端或
       老旧系统中查看。
   1.3 深度限制：--max-depth N 只展开到第 N 层（根目录记为第 1 层），超过深度的目录在
       名字后追加 "..."，并在统计中说明被截断的层级数。
   1.4 模式过滤：--include "*.py,*.md"（白名单，目录始终保留以便展示层级）与
       --exclude ".git,__pycache__,node_modules,*.log"（黑名单，匹配目录时整棵跳过）。
   1.5 只看目录：--dirs-only 只输出目录节点，适合快速绘制结构骨架。
   1.6 附加信息列：--size 在文件名后输出人类可读大小（1.2 KB / 3.4 MB），
       --mtime 输出修改时间（YYYY-MM-DD HH:MM），--perms 输出权限标记。
   1.7 排序：--sort name / size / mtime / count，--dirs-first 保证目录排在文件前面，--reverse 反向。
   1.8 输出格式：--format text（默认树形）、--format markdown（缩进列表，每层两个空格加短横线）、
       --format markdown-code（把树形文本包裹进代码块，代码块围栏长度按内容自动调整，
       内容中出现连续反引号时围栏加长）、--format json（层级化的嵌套对象）。
   1.9 统计信息：末尾输出根路径、目录数、文件数、符号链接数、跳过数、总大小、
       最深层级、最大文件（路径与大小）。
   1.10 报告落盘：--output tree.md 把结果写入文件；若目标文件已存在，必须加 --force 才允许覆盖，
       默认改名为 tree.md.new 并提示。

2. 输入与交互
   2.1 位置参数为根目录，默认当前目录；同时接受多个根目录并按顺序依次输出。
   2.2 --follow-symlinks 才跟随符号链接，默认不跟随，只把链接本身作为一行列出并标注指向。
   2.3 --include-hidden 才会列出以点开头的隐藏文件与目录。
   2.4 --show-empty-dirs 控制是否显示空目录（默认显示，便于确认目录确实为空）。
   2.5 --max-entries N 限制单个目录下最多展示的条目数（默认 200），超出时输出
       "... 其余 K 项已省略"。

3. 输出与展示
   3.1 树形文本默认输出到标准输出；管道场景下自动关闭颜色，避免污染日志。
   3.2 输出到 Windows 控制台时通过 sys.stdout.reconfigure(encoding="utf-8") 保证
       ├ └ │ 等线框字符正常显示；若失败则自动降级为 ASCII 模式并提示。
   3.3 写文件时默认使用 UTF-8 无 BOM 编码，可用 --encoding utf-8-sig 指定 BOM，
       可用 gbk 兼容老工具；无法用目标编码表示的字符替换为问号并累计警告。
   3.4 --quiet 只输出统计块，不输出树形结构。

4. 异常与边界处理
   4.1 根目录不存在或指向普通文件时报错并退出，退出码 2。
   4.2 扫描过程中遇到权限不足的目录时跳过该目录，输出一行 "（无权限，已跳过）"，
       并把数量计入统计的跳过数，不中断整体导出。
   4.3 遇到无法读取的目录项（文件已被删除、文件名编码异常）时用 repr 形式输出文件名，
       保证不抛异常。
   4.4 符号链接形成环时（A 指向祖先目录）必须能检测到并停止递归，输出 "（检测到链接环，已停止）"。
   4.5 目录规模极大（超过 10 万个条目）时输出进度提示到标准错误流，并按 --max-entries 截断。
   4.6 输出路径位于被扫描目录内部时提示"输出文件可能出现在结果中"，并在生成完成后说明。
   4.7 目标输出文件被其它进程占用时捕获异常，提示可改用 --output 其它路径。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库 argparse、os、sys、json、time、datetime、pathlib、logging、
   fnmatch、stat、typing、dataclasses、collections；禁止使用任何第三方库
   （包括 rich、click、pathspec），禁止调用系统 tree 命令。
3. 禁止事项：禁止修改、删除、重命名任何已有文件（本工具是纯只读扫描器）；
   禁止默认跟随符号链接；禁止在扫描阶段把整个目录树一次性读进内存后再输出，
   必须使用生成器逐层产出。
4. 代码组织：至少拆分为 walker.py（生成器式遍历）、formatter.py（四种输出格式）、
   filters.py（包含与排除规则编译）、stats.py（统计累计）、cli.py（参数与输出入口）。
   walker 必须是生成器函数，formatter 必须与文件系统解耦（只接收节点数据）。
5. 编码规范：类型注解与 docstring 齐全；节点数据使用 dataclass；异常处理必须记录
   logging.warning 并携带路径；不吞掉 OSError 的原始信息。
6. 性能约束：扫描 50000 个条目的目录树应在 5 秒内完成；--dirs-only 模式不得对文件名做
   超过必要次数的 stat 调用（只在需要大小时才 stat）。

【四、设计要点】

1. 数据结构
   1.1 Node：字段 path（Path）、name（str）、depth（int）、is_dir（bool）、is_symlink（bool）、
       link_target（str | None）、size（int | None）、mtime（float | None）、
       children_count（int | None）、skipped_reason（str | None）。
   1.2 WalkConfig：字段 root（Path）、max_depth、include_patterns、exclude_patterns、
       dirs_only、follow_symlinks、include_hidden、max_entries。
   1.3 TreeStats：字段 dirs、files、symlinks、skipped、total_size、max_depth、
       largest_file（路径与大小）、truncated_dirs。
   1.4 排除规则编译为两个列表：目录名精确匹配集合与 fnmatch 模式列表，
       匹配时先看名字再看相对路径，两者都命中才算排除。

2. 关键算法或流程
   2.1 遍历：使用 os.scandir 递归生成，进入目录前先判断是否命中 exclude；
       DirEntry 自带 is_dir(follow_symlinks=False) 与 stat(follow_symlinks=False)，
       避免额外的系统调用。
   2.2 前缀绘制：为每个节点维护一个布尔列表 prefix_flags 表示祖先是否为最后一个子项；
       绘制时对前 n-1 位输出 "│   " 或 "    "，最后一位输出 "├── " 或 "└── "。
   2.3 排序：先按 dirs_first 分组，再按 --sort 计算键；size 排序时目录大小取其子树汇总
       （只在 --sort size 时才做汇总，其它情况不做全树 stat 以避免慢）。
   2.4 环检测：维护当前递归路径上已访问目录的 (st_dev, st_ino) 集合，
       跟随链接时命中集合即判定成环。
   2.5 统计汇总：遍历结束时输出 TreeStats；总大小在未开启 --size 时也按需统计，
       由 --no-size-scan 关闭以进一步提升速度。
   2.6 人类可读大小：按 1024 进制换算并保留一位小数，单位序列为 B、KB、MB、GB、TB。

3. 接口或命令设计
   3.1 python dir_tree.py C:\projects\100programs --max-depth 2 --exclude ".git,__pycache__"
   3.2 python dir_tree.py . --format markdown --output tree.md --include "*.py,*.md"
   3.3 python dir_tree.py D:\photos --sort size --size --dirs-only --max-entries 50
   3.4 python dir_tree.py . --format json --ascii --quiet
   3.5 核心函数签名：walk(config: WalkConfig) -> Iterator[Node]；
       render_text(nodes: Iterable[Node], stats: TreeStats, ascii_mode: bool) -> str；
       render_markdown(nodes, stats, as_code_block: bool) -> str。

【五、运行方式与示例】

1. 安装与运行：无需安装依赖，执行 python dir_tree.py --help 查看全部参数。
2. 示例一（基本树形输出）：
   输入：python dir_tree.py C:\projects\100programs\011_prime_tool
   输出：011_prime_tool
         ├── README.txt
         └── prime_tool.py
3. 示例二（深度与排除）：
   输入：python dir_tree.py C:\projects\100programs --max-depth 2 --exclude ".git,__pycache__,*.pyc"
   输出：100programs
         ├── 011_prime_tool
         │   └── README.txt
         ├── 012_date_calculator
         │   └── README.txt
         └── 项目总览.md
         统计：目录 3 个，文件 3 个，总大小 42.1 KB，最深 2 层
4. 示例三（Markdown 输出并落盘）：
   输入：python dir_tree.py . --format markdown --include "*.py,*.md" --output tree.md
   输出：已写入 tree.md（UTF-8，共 128 行，目录 6 个，文件 21 个）
5. 示例四（大小排序）：
   输入：python dir_tree.py . --sort size --size --max-entries 3
   输出：.
         ├── data（12.4 MB）
         ├── build（3.2 MB）
         ├── src（512.0 KB）
         └── ... 其余 8 项已省略
6. 示例五（异常输入）：
   输入：python dir_tree.py D:\not_exist
   输出（stderr）：错误：根目录不存在：D:\not_exist，退出码 2
7. 示例六（权限不足）：
   输入：python dir_tree.py C:\Windows\System32\config --max-depth 1
   输出：config
         ├── （无权限，已跳过）
         统计：跳过 1 个目录（权限不足）

【六、验收标准】

[ ] 1. 对只含三个文件的目录，树形输出的分支符号与缩进层级完全正确，最后一项使用 └──。
[ ] 2. --max-depth 2 时第 3 层及其以下的条目不再出现，且被截断目录名字后带省略标记。
[ ] 3. --exclude "__pycache__" 后该目录及其全部子项都不出现在输出中。
[ ] 4. --include "*.py" 时非 Python 文件不显示，但目录层级仍然完整保留。
[ ] 5. --format markdown 输出每层缩进规则一致，可直接粘贴到 Markdown 文档中正常渲染。
[ ] 6. --format json 输出可被 json.loads 解析，且嵌套结构与目录层级一致。
[ ] 7. --ascii 模式下输出中不含 ├、└、│ 等字符。
[ ] 8. 对包含符号链接环的目录，程序在有限时间内结束并输出环检测提示，不无限递归。
[ ] 9. 无权限目录被跳过时统计中的跳过数加一，且不影响其它目录正常输出。
[ ] 10. --output 指向已存在文件且未加 --force 时不覆盖，改为写入 .new 文件并提示。
[ ] 11. --size 输出的大小与实际文件大小一致（误差小于 0.1 KB），单位换算符合 1024 进制。
[ ] 12. --max-entries 3 时每个目录最多展示 3 条并给出"其余 K 项已省略"。
[ ] 13. 输出文件默认 UTF-8 无 BOM，用 --encoding gbk 时文件可被 GBK 解码器正确读取。
[ ] 14. 扫描 50000 个条目的目录树耗时低于 5 秒，且内存占用不随条目数线性暴涨
       （通过分批产出验证）。
[ ] 15. 本工具运行前后被扫描目录内所有文件的大小与修改时间均未发生变化。

【七、可选扩展】

1. 增加 --depth-colors 用 ANSI 颜色区分目录、可执行文件与链接（仅在终端输出时启用）。
2. 增加 --compare other_tree.json，对比两次导出的结构差异，输出新增与删除的节点。
3. 增加 --dot 输出 Graphviz DOT 描述，用于生成可视化目录图（不引入第三方库，只生成文本）。
4. 增加 --summary-only 输出按扩展名分组的文件数与占用空间排行榜。
5. 增加 --exclude-from ignore.txt，兼容 .gitignore 风格的模式列表。

【八、涉及知识点】

- os.scandir 与 DirEntry 的高效用法、递归遍历与生成器惰性求值
- fnmatch 通配符匹配、白名单与黑名单规则的组合
- 树形绘制的最后一项判断与前缀累积算法
- 符号链接、硬链接、st_dev 与 st_ino 判环
- 文件大小的人类可读格式化与 1024 进制换算
- 标准输出编码问题：sys.stdout.reconfigure 与控制台代码页
- Markdown 缩进列表与代码块围栏的生成规则
- 只读工具的工程约束：无副作用、可重入、异常隔离
- argparse 参数分组与互斥选项
================================================================================
