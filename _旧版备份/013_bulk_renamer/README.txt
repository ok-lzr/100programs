================================================================================
项目编号：013                    难度等级：★☆☆☆☆（小型项目）
项目名称：批量文件重命名工具
所属分类：命令行工具 / 文件与文本处理
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

从相机、手机、下载工具里导出的文件常常是一堆无意义的名字：DSC_0031.JPG、微信图片_20240301.jpg、
未命名 1 (2).txt、混着空格与全角括号的导出文件。手工一个个改名既费时又容易出错，
在资源管理器里多选重命名又只能生成"新增文件夹 (1)(2)(3)"这种格式，无法按日期或原文件名重组。

本项目提供一个"预览优先、可撤销"的批量重命名命令行工具。它的核心设计原则是：
默认不真正改名，先把完整的"旧名 → 新名"对照表打印出来让人确认；只有显式加 --apply 才执行；
执行过程写入日志文件，出错或者后悔时可以一条命令回滚。

目标用户是经常整理素材的摄影与设计人员、需要规范实验数据命名的学生与科研人员，
以及想把一批文件名按规则统一成"日期_序号"格式的普通用户。

本工具只重命名文件本身，绝不修改文件内容，也不移动文件到其它目录（本项目的移动类需求
由 016 文件自动分类整理器负责）。所有操作均在同一个目录内完成，避免跨盘移动带来的风险。

【二、功能需求清单】

1. 核心功能
   1.1 正则重命名：--regex PATTERN --replacement REPL，支持 Python 正则的分组引用 \1、\g<name>；
       默认只替换第一处，加 --replace-all 替换全部匹配。
   1.2 序号重命名：--template "IMG_{n:04d}{ext}" 配合 --start 1 --step 1 --sort name；
       {n} 支持格式说明符（{n:04d}、{n}），按排序后的顺序递增编号。
   1.3 模板重命名：--template "{date}_{name}{ext}" 中使用占位符 {name}（不含扩展名的原名）、
       {ext}（含点小写扩展名）、{extupper}、{date}（文件修改日期 YYYYMMDD）、
       {time}（HHMMSS）、{mtime}、{size}、{parent}（父目录名）、{n}（序号）、{hash6}（内容哈希前 6 位）。
   1.4 大小写转换：--case lower / upper / title 只作用于文件主名，扩展名统一转小写（可用
       --keep-ext-case 关闭）。
   1.5 名称净化：--sanitize 去掉首尾空白、把连续空白压缩为单个下划线、替换 Windows 非法字符
       （尖括号、冒号、双引号、斜杠、反斜杠、竖线、问号、星号）为下划线、
       用 unicodedata.normalize("NFKC") 做 Unicode 归一化，把全角字母数字转半角。
   1.6 冲突检测：对每个目标名同时检查"磁盘上是否已存在该文件"与"本批次中是否已有其它文件
       计划使用该名字"；任一命中则该条被标记为冲突并跳过，绝不覆盖已有文件。
   1.7 两阶段改名：执行时先把所有待改文件改成一个不会冲突的临时名
       （形如 ".__rn_tmp_0001__"），再统一改成目标名，从而正确处理 A → B、B → A 的互换场景。
   1.8 撤销：本次操作写出日志文件 rename_log_YYYYMMDD_HHMMSS.json，记录每一条的
       old_path、new_path、status；--undo 日志路径 按记录逆序逆向执行；
       回滚前逐条校验"当前磁盘上的名字是否等于记录中的 new_path"，不一致或已不存在则跳过并计入报告。
   1.9 预览输出：默认模式下打印三列表格（序号、旧名、新名），并在末尾统计
       "将重命名 N 个 / 跳过 M 个 / 冲突 K 个 / 未变化 J 个"。

2. 输入与交互
   2.1 位置参数为待处理目录，默认当前目录；--recursive 递归子目录，--max-depth 限制层数。
   2.2 过滤条件：--glob "*.jpg"（可重复）、--ext jpg,png,heic、--exclude "*_thumb*"、
       --min-size / --max-size（带单位 KB/MB）。
   2.3 排序：--sort name / natural / mtime / size / ctime，--reverse 反向；
       natural 表示数字按数值大小排序（IMG_2 排在 IMG_10 之前）。
   2.4 必须显式加 --apply 才会真正改名，否则一律为预览（dry-run）模式，这一点写在 --help 首页。
   2.5 --include-hidden 才会处理以点开头的文件与隐藏属性文件，默认跳过。
   2.6 --yes 用于在 --apply 时跳过交互确认；不给 --yes 时在终端打印前 10 条并要求输入 yes 确认。

3. 输出与展示
   3.1 预览与结果表格使用等宽对齐（按显示宽度计算，中文按 2 列宽），超过终端宽度时截断中间部分。
   3.2 --json 输出结构化预览结果，便于接入其它脚本。
   3.3 --quiet 只输出统计行，不打印逐条明细。
   3.4 日志文件固定写入被处理目录下，命名为 rename_log_YYYYMMDD_HHMMSS.json，内容为
       UTF-8 无 BOM 的 JSON 数组，每条含 old_path、new_path、status、error 四个字段。

4. 异常与边界处理
   4.1 目标名与原名完全相同（考虑大小写敏感性）时标记为"未变化"并跳过，不产生日志噪声。
   4.2 目标名超出文件系统上限（Windows 下完整路径 260 字符）时跳过并给出警告。
   4.3 Windows 保留设备名（CON、PRN、AUX、NUL、COM1 至 COM9、LPT1 至 LPT9，含带扩展名形式）
       一律拒绝并计入跳过。
   4.4 目录、符号链接、正在被其它进程占用的文件默认跳过；跳过原因写入日志。
   4.5 仅大小写不同的改名（readme.txt → README.txt）在 Windows 上必须通过临时名两步完成，
       不能直接 os.rename。
   4.6 执行中途发生权限错误时，立即停止后续操作，写出已完成的日志并提示可用 --undo 回滚。
   4.7 同名模板导致空名字（例如正则把整个主名替换为空）时跳过并提示"结果名为空"。
   4.8 日志文件不可写（目录只读）时在预览阶段就报错并退出，不做任何改名。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库 argparse、os、pathlib、re、json、sys、time、hashlib、unicodedata、
   datetime、logging、dataclasses、typing、shutil、fnmatch；禁止使用任何第三方库，
   禁止调用系统命令行工具（如 ren、mv）完成核心功能。
3. 禁止事项：禁止在未经 --apply 的情况下修改任何文件名；禁止覆盖已存在的文件；
   禁止在 --apply 之前不生成日志文件；禁止对目录本身改名（除非显式开启 --include-dirs）；
   禁止跟随符号链接。
4. 代码组织：至少拆分为 scanner.py（收集文件与过滤排序）、namer.py（按策略生成新名）、
   planner.py（冲突检测与两阶段计划）、executor.py（执行与日志写入）、cli.py（参数与确认交互）。
   生成新名的函数必须是纯函数：输入 Path 与规则，输出新名字符串，不做任何磁盘写入。
5. 编码规范：类型注解与 docstring 齐全，行距与命名遵循 PEP 8；日志使用 logging；
   不允许在 scan、plan 阶段产生任何副作用。
6. 安全约束：所有路径拼接使用 pathlib 而非字符串加法；执行前必须重新扫描一次目录，
   若两次扫描的文件集合不一致（文件被新增或删除）则中止并提示重新运行。

【四、设计要点】

1. 数据结构
   1.1 FileItem：字段 path（Path）、name、stem、ext、size、mtime、ctime、is_hidden、
       sort_key（按 --sort 计算出的元组）。
   1.2 RenamePlan：字段 old_path、new_name、new_path、status（ok / conflict / unchanged /
       invalid / skipped）、reason。
   1.3 RenameLog：字段 started_at、directory、rule_summary（记录本次使用的参数文本）、
       entries（list[RenamePlan]）、applied（bool）。
   1.4 执行结果汇总 ExecutionReport：字段 renamed、skipped、restored、conflict、failed、
       log_path。
   1.5 冲突检测使用两个集合：existing_names（扫描时磁盘上已有的文件名集合）与
       planned_names（本批次计划占用的名字集合）。

2. 关键算法或流程
   2.1 扫描：用 pathlib.Path.rglob 或 os.scandir 递归收集，先按 --ext / --glob / --exclude /
       大小条件过滤，再按 --sort 排序；natural 排序通过 re.split(r"(\d+)", name)
       把名字切成数字段与非数字段，数字段转 int 参与比较。
   2.2 生成新名：按 --regex / --case / --sanitize / --template 的顺序依次施加，
       顺序固定并写进文档；{n} 的取值基于排序后的位置乘以 --step 再加 --start。
   2.3 冲突检测：new_name 为空、等于原名、命中保留名、磁盘已存在、本批次已被占用，
       五种情况分别对应不同的 status 与 reason，输出统计时分开计数。
   2.4 两阶段执行：第一阶段把 status 为 ok 的文件改为 ".__rn_tmp_{i:05d}__"，
       第二阶段改为最终名；任一步失败则立刻停止，把已完成部分写入日志的 applied 字段。
   2.5 撤销流程：读取日志，逆序遍历 entries（只处理 status == ok 且 applied 为真），
       校验 new_path 存在且 old_path 不存在，满足条件才改回；否则计入 skipped 并说明原因。
   2.6 预览对齐：计算每列的最大显示宽度（中文按 2 计算），逐行 format 输出，超宽截断。

3. 接口或命令设计
   3.1 python bulk_renamer.py D:\photos --regex "DSC_(\d+)" --replacement "trip_\1" --ext jpg
   3.2 python bulk_renamer.py . --template "{date}_{n:03d}{ext}" --sort mtime --start 1 --apply
   3.3 python bulk_renamer.py . --sanitize --case lower --glob "*.txt" --recursive
   3.4 python bulk_renamer.py . --undo rename_log_20240301_101500.json
   3.5 核心函数签名：scan(directory: Path, filters: Filters, sort: str) -> list[FileItem]；
       build_plan(items: list[FileItem], rule: Rule) -> list[RenamePlan]；
       apply_plan(plan: list[RenamePlan], log_path: Path, dry_run: bool) -> ExecutionReport。

【五、运行方式与示例】

1. 安装与运行：无需安装依赖，执行 python bulk_renamer.py --help 查看全部参数。
2. 示例一（预览正则重命名）：
   输入：python bulk_renamer.py . --regex "DSC_(\d+)" --replacement "trip_\1" --ext jpg
   输出：001  DSC_0031.JPG  ->  trip_0031.jpg
         002  DSC_0032.JPG  ->  trip_0032.jpg
         将重命名 2 个 / 跳过 0 个 / 冲突 0 个 / 未变化 0 个（预览模式，未做任何修改）
3. 示例二（按修改日期编号并真正执行）：
   输入：python bulk_renamer.py . --template "{date}_{n:03d}{ext}" --sort mtime --apply --yes
   输出：已重命名 12 个文件，日志已写入 rename_log_20240301_101500.json
4. 示例三（冲突保护）：
   输入：python bulk_renamer.py . --regex "^a" --replacement "b" （目录中已存在 b.txt）
   输出：001  a.txt  ->  b.txt  冲突：目标文件已存在
         将重命名 0 个 / 冲突 1 个，程序未做任何修改，退出码 0
5. 示例四（撤销）：
   输入：python bulk_renamer.py . --undo rename_log_20240301_101500.json --apply
   输出：已回滚 12 个文件名，跳过 0 个（其中 0 个因当前名字与记录不一致）
6. 示例五（非法参数）：
   输入：python bulk_renamer.py . --regex "[" --replacement "x"
   输出（stderr）：错误：正则表达式 '[' 无法编译（unterminated character set），退出码 2
7. 示例六（无匹配）：
   输入：python bulk_renamer.py . --glob "*.psd"
   输出：未找到匹配的文件，未做任何修改，退出码 0

【六、验收标准】

[ ] 1. 不加 --apply 时，运行前后目录内文件名完全一致，且不生成日志文件。
[ ] 2. 预览表格中旧名与新名逐行对应正确，--json 输出可被 json.loads 解析。
[ ] 3. 目标名已存在于磁盘时该条被判为冲突，原文件与目标文件内容均未被修改。
[ ] 4. 两个文件互换名字（A 到 B、B 到 A）时两阶段执行成功，无文件丢失。
[ ] 5. readme.txt 改名为 README.txt 在 Windows 与 Linux 上均成功执行。
[ ] 6. CON.txt、NUL、COM1.jpg 等保留名被拒绝并计入跳过统计。
[ ] 7. --undo 能把一次成功执行的改名完整还原，文件名与内容哈希均回到初始状态。
[ ] 8. 手工改动其中一个文件名字后再 --undo，该条被跳过，其余条目仍然回滚成功。
[ ] 9. --sort natural 下 IMG_2.jpg 排在 IMG_10.jpg 之前。
[ ] 10. --sanitize 后文件名不含任何 Windows 非法字符，全角字母被转换为半角。
[ ] 11. 正则把主名替换为空时该条被跳过并给出"结果名为空"的原因。
[ ] 12. 日志文件为 UTF-8 无 BOM，包含 old_path、new_path、status、error 四个字段。
[ ] 13. 隐藏文件在未加 --include-hidden 时不出现在预览列表中。
[ ] 14. 目录只读导致日志无法写入时，程序在预览阶段报错且不产生任何改名。
[ ] 15. 处理 1000 个文件时预览阶段耗时低于 2 秒。

【七、可选扩展】

1. 增加 --from-csv mapping.csv 模式，按外部对照表改名，便于与其它系统对接。
2. 支持根据文件内容生成可读名（例如从 Markdown 首个标题、从 MP3 的 ID3 标签取名）。
3. 增加 --rules rules.json，用配置文件描述多条改名规则与作用范围，避免命令行过长。
4. 提供 --dedupe-suffix 策略，冲突时自动追加 _1、_2 而不是跳过。
5. 增加 --dry-run-diff 输出统一差异格式的文本对比，便于粘贴进工单或提交记录。

【八、涉及知识点】

- pathlib.Path 的 stem、suffix、with_name 与 os.scandir 的性能差异
- 正则表达式分组、反向引用 \1 与 \g<name>、re.compile 复用
- 格式化字符串与格式说明符（{n:04d}）在文件名模板中的应用
- 文件系统大小写敏感性差异、Windows 保留设备名、路径长度上限
- 两阶段改名解决名字互换冲突的思路
- JSON 日志设计、幂等与可回滚操作的设计原则
- unicodedata 归一化（NFKC）与全角半角转换
- argparse 的可重复参数（action="append"）与交互式确认实现
- dry-run 先行、失败即停、副作用最小化的工程习惯
================================================================================
