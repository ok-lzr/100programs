================================================================================
项目编号：016                    难度等级：★★☆☆☆（小型项目）
项目名称：文件自动分类整理器
所属分类：命令行工具 / 文件与文本处理
建议工时：5 ~ 8 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）；可选 Pillow 用于读取照片 EXIF
================================================================================

【一、项目背景与目标】

下载目录、桌面、手机导出的照片目录，往往是几百上千个文件堆在一起：安装包、文档、图片、
压缩包、音视频混杂，想找某个文件全靠搜索。手工按类型建文件夹再一个个拖动，
大概整理到第三十个文件就放弃了，而且下次下载又会堆满。

本项目把"整理"这件事变成一条可重复执行的命令：按扩展名映射表归类、
按拍摄或修改日期归档到年与月子目录、按文件名关键词匹配规则归入指定文件夹，
三条策略可按优先级叠加使用。整理的规则来自一份 JSON 配置文件，因此第二个月再跑一次时，
新文件会自动进入同样的目录结构。

工具沿用"预览优先"的做法：默认只打印移动计划，加 --apply 才真正移动，同时写出操作日志，
配合 --undo 可以整体回滚。目标用户是希望一次性把混乱目录整理干净的普通用户，
以及需要批量归档实验数据、日志与报表的开发者。

安全底线有三条：只移动不删除；二进制文件不会被当作文本解析；任何一步失败都记录下来，
绝不静默丢文件。

【二、功能需求清单】

1. 核心功能
   1.1 扩展名分类：内置默认映射表（图片 jpg/png/heic/webp、文档 pdf/docx/txt/md/xlsx、
       压缩包 zip/rar/7z、音视频 mp4/mp3/mov、安装包 exe/msi/dmg、代码 py/js/java 等），
       可通过 --rules rules.json 覆盖或扩展；未命中任何类别的文件进入 other 目录。
   1.2 日期归档：--by-date 时在类别下继续按日期分子目录，层级由 --date-format 决定，
       默认 {category}/{YYYY}/{MM}；--flat-date 去掉年份只留月份。
   1.3 日期来源优先级：照片类且开启 --use-exif 时优先读取 EXIF 的拍摄时间，
       读不到再退回文件的修改时间；--date-source mtime/ctime/exif 可强制指定。
   1.4 关键词规则：rules.json 中的 keywords 段定义"正则 → 目标子目录"列表，
       按顺序匹配文件名（不含路径），第一个命中者生效；
       命中结果可以覆盖扩展名类别（由规则里的 priority 字段控制）。
   1.5 冲突处理：目标路径已存在同名文件时，自动追加 _1、_2……直到不冲突，
       并在报告中标注为重命名；--on-conflict skip 则改为跳过并记录。
   1.6 空文件与零长度文件单独归入 _empty 目录，避免与正常文件混淆。
   1.7 未知与无扩展名文件归入 _noext 目录，并按文件头前 4 字节给出粗略类型猜测
       （仅作提示，不影响归类结果）。
   1.8 操作日志：每次 --apply 写出 organize_log_YYYYMMDD_HHMMSS.json，
       逐条记录 source、target、rule（命中规则名称）、status、reason。
   1.9 撤销：--undo 日志路径 逆序把文件移回原路径；移动前校验目标位置存在且原位置为空，
       不满足则跳过并计入报告；若原目录已被删除则自动重建。
   1.10 统计报告：处理文件数、各类别数量、跳过数、重命名数、失败数、
       移动前后目录的文件数对比，以及耗时。

2. 输入与交互
   2.1 位置参数为待整理目录，默认当前目录；--recursive 递归处理子目录
       （默认只处理根目录下的文件，避免把已经整理好的子目录再搅乱）。
   2.2 --target DIR 指定归档根目录，默认在被整理目录内创建分类子目录；
       --dry-run 为默认行为，--apply 才执行。
   2.3 --include-ext 与 --exclude-ext 用于临时收窄处理范围；
       --exclude-pattern "*.tmp,~$*" 跳过临时文件；隐藏文件与系统文件默认跳过，
       加 --include-hidden 才处理。
   2.4 --tree 在预览后额外打印目标目录的预计结构树，便于确认分类效果。
   2.5 交互确认：--apply 时列出动作条数并要求输入 yes，--yes 可跳过。

3. 输出与展示
   3.1 预览表格：序号、源文件名、目标相对路径、命中规则、状态（含冲突改名标记）。
   3.2 --json 输出结构化计划；--quiet 只输出汇总行。
   3.3 文件写操作使用 shutil.move，同盘时底层为 os.replace（原子），跨盘时自动退化为复制加删除；
       移动后必须保留原文件的修改时间与访问时间（依赖 shutil.move 的 copy2 语义）。
   3.4 日志与报告均为 UTF-8 无 BOM 编码。

4. 异常与边界处理
   4.1 源目录不存在或不是目录时报错并以退出码 2 结束。
   4.2 文件被占用（PermissionError）时跳过并记录，不中断整体流程。
   4.3 目标目录不可创建（磁盘满、无权限）时立即停止剩余动作，写出已完成部分的日志并提示可 --undo。
   4.4 rules.json 缺失、JSON 语法错误或字段类型错误时给出具体原因与出错位置，退出码 2。
   4.5 关键词匹配只对文本类扩展名进行：读取前 8 KB，若发现 NUL 字节则判定为二进制并跳过匹配，
       直接走扩展名规则，避免把二进制文件按文本解码导致乱码或异常。
   4.6 文本文件编码探测顺序为 utf-8-sig、utf-8、gb18030、utf-16，探测失败则跳过关键词匹配，
       不做任何强制解码，也不修改文件内容。
   4.7 --use-exif 时若未安装 Pillow，打印一次性提示"未安装 Pillow，EXIF 时间不可用，
       已回退到修改时间"并继续执行，不视为错误。
   4.8 目标目录位于被整理目录内部时，把目标目录加入排除集合，防止把文件移进自己内部造成递归搬家。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：标准库 argparse、os、sys、re、json、time、logging、pathlib、shutil、
   datetime、dataclasses、typing、collections；可选第三方库仅限 Pillow（用于 EXIF），
   且必须在未安装时优雅降级；禁止使用 send2trash、filetype、python-magic 等库。
3. 禁止事项：禁止删除任何文件（本项目只移动与创建目录）；禁止覆盖已存在的文件；
   禁止在未加 --apply 时调用任何写操作（含创建目录）；禁止修改文件内容
   （读取文本仅用于关键词匹配，且以只读方式打开）。
4. 代码组织：至少拆分为 rules.py（配置加载与校验、内置映射表）、classifier.py
   （纯函数式分类决策）、planner.py（目标路径计算与冲突解决）、executor.py
   （执行移动与日志）、report.py（预览与统计输出）、cli.py（参数与确认）。
   classifier 必须是无副作用的纯函数：输入 FileMeta 与 Rules，输出目标类别与命中规则名。
5. 编码规范：类型注解与 docstring 齐全；配置结构用 dataclass 描述并在加载时做完整校验；
   日志记录相对路径而非绝对路径以便分享；异常处理必须带文件路径上下文。
6. 幂等性要求：对同一个目录连续运行两次，第二次的预览结果中应全部标记为"已在目标位置"
   并产生零个移动动作。

【四、设计要点】

1. 数据结构
   1.1 Rules：字段 categories（dict[str, list[str]]，类别名到扩展名列表）、
       keywords（list[KeywordRule]）、date_format（str）、unknown_category、
       empty_category、noext_category。
   1.2 KeywordRule：字段 name、pattern（已编译的正则）、target（相对子目录）、
       priority（int，数值大的优先于扩展名类别）。
   1.3 FileMeta：字段 path、name、stem、ext（小写不含点）、size、mtime、ctime、is_hidden。
   1.4 MovePlan：字段 index、source、target、category、rule_name、status
       （move / rename / skip / in-place / failed）、reason。
   1.5 OrganizeLog：字段 started_at、root、target_root、rules_file、entries、finished。

2. 关键算法或流程
   2.1 分类决策顺序：0 字节判定 → 关键词规则（仅文本类，priority 降序）→ 扩展名映射 →
       无扩展名兜底 → other 兜底。每一步命中即返回，文档中固定该顺序并写进自测用例。
   2.2 日期子目录：读取 EXIF 或 stat 得到 datetime，用 strftime 按 --date-format 格式化；
       无法解析日期时归入 {category}/_undated。
   2.3 目标路径计算：target_root / 类别 / 日期段 / 文件名；用 pathlib 拼接，
       每一步都做路径规范化，避免出现 ".." 片段。
   2.4 冲突解决：目标存在时在 stem 后追加 _N（N 从 1 开始），保留原扩展名；
       追加后的名字仍需参与冲突检查，直到找到空位；同一批次内部也要维护已占用名字集合。
   2.5 批量执行：先计算完整计划再统一执行，执行期间不重新扫描目录；
       每个动作完成后立即向日志文件追加一条记录（便于中途崩溃后仍能回滚）。
   2.6 撤销：读取日志逆序处理，只有 status 为 move 或 rename 且 target 存在才回滚；
       回滚完成后把日志文件重命名为 .undone.json 防止重复回滚。

3. 接口或命令设计
   3.1 python file_organizer.py D:\Downloads --rules rules.json --by-date
   3.2 python file_organizer.py D:\Downloads --apply --yes --use-exif --tree
   3.3 python file_organizer.py . --undo organize_log_20240301_101500.json --apply
   3.4 python file_organizer.py D:\data --include-ext csv,json --target D:\archive --json
   3.5 核心函数签名：load_rules(path: Path | None) -> Rules；
       classify(meta: FileMeta, rules: Rules) -> tuple[str, str]；
       plan_moves(files: list[FileMeta], rules: Rules, target_root: Path) -> list[MovePlan]。

【五、运行方式与示例】

1. 安装与运行：无需安装依赖；如需读取照片拍摄时间，可选执行 pip install Pillow。
2. 示例一（预览整理结果）：
   输入：python file_organizer.py D:\Downloads --rules rules.json --by-date
   输出：001  报告.pdf        -> 文档/2024/03/报告.pdf        规则：扩展名映射
         002  安装程序.exe    -> 安装包/2024/03/安装程序.exe    规则：扩展名映射
         003  发票_2024.pdf   -> 财务/2024/03/发票_2024.pdf    规则：关键词（财务）
         共 3 个动作，未做任何修改（预览模式）
3. 示例二（真实执行并保留时间戳）：
   输入：python file_organizer.py D:\Downloads --apply --yes
   输出：已移动 128 个文件到 9 个类别目录，重命名 4 个，跳过 2 个（文件被占用），
         日志：organize_log_20240301_101500.json
4. 示例三（撤销）：
   输入：python file_organizer.py D:\Downloads --undo organize_log_20240301_101500.json --apply
   输出：已回滚 128 个文件，跳过 0 个，日志已标记为 .undone.json
5. 示例四（JSON 计划）：
   输入：python file_organizer.py . --json
   输出：[{"index":1,"source":"a.txt","target":"文档/_undated/a.txt","category":"文档",
         "rule_name":"扩展名映射","status":"move"}]
6. 示例五（二进制文件跳过关键词匹配）：
   输入：python file_organizer.py . --rules rules.json --debug
   输出（stderr）：debug：sample.bin 含 NUL 字节，跳过关键词匹配，改用扩展名规则
7. 示例六（非法规则文件）：
   输入：python file_organizer.py . --rules broken.json
   输出（stderr）：错误：rules.json 第 12 行 JSON 解析失败（Expecting ',' delimiter），退出码 2

【六、验收标准】

[ ] 1. 不加 --apply 时运行前后目录结构完全一致，且未创建任何新目录。
[ ] 2. jpg、pdf、zip、mp4 分别被归入图片、文档、压缩包、音视频类别目录。
[ ] 3. 无扩展名文件进入 _noext，0 字节文件进入 _empty，两者不参与关键词匹配。
[ ] 4. --by-date 下文件进入 类别/年/月 三级目录，月份补零为两位。
[ ] 5. 文件名命中关键词规则时目标目录由关键词规则决定，并能在报告中显示规则名称。
[ ] 6. 目标已存在同名文件时自动改名为 名字_1.ext，原目标文件未被覆盖。
[ ] 7. 含 NUL 字节的文件不参与文本解码，程序不抛 UnicodeDecodeError。
[ ] 8. GB18030 编码的中文文件名文本能被正确探测并匹配关键词。
[ ] 9. 移动后文件的修改时间与源文件一致（误差小于 1 秒）。
[ ] 10. --undo 能把全部已移动文件还原到原路径，且目录结构恢复原状。
[ ] 11. 对同一目录连续执行两次，第二次预览中移动动作为 0（幂等）。
[ ] 12. 目标目录位于被整理目录内部时，目标目录自身不被扫描与移动。
[ ] 13. 未安装 Pillow 时 --use-exif 只打印一次提示并回退到修改时间，退出码为 0。
[ ] 14. rules.json 缺少 categories 字段时报错并退出码为 2。
[ ] 15. 处理 5000 个文件的预览阶段耗时低于 5 秒。

【七、可选扩展】

1. 增加 --duplicate-first 选项，整理前先调用重复文件查找逻辑，把冗余文件先归入 _duplicates。
2. 增加 --watch 模式，结合 watchdog 或轮询实现下载目录自动整理。
3. 增加 --unpack-archives，把 zip 压缩包解压到同名目录后再归档（需注意解压失败的处理）。
4. 增加 --rename-template，在归档的同时按 日期_类别_序号 批量改名。
5. 增加 --simulate-report html，输出带目录结构的 HTML 报告，便于向他人展示整理结果。

【八、涉及知识点】

- 文件扩展名与 MIME 类型的对应关系、文件头魔数识别
- 文本编码探测策略与二进制判定（NUL 字节检测）
- shutil.move 与 os.replace 的差异、跨盘移动时的元数据保留
- 正则关键词规则引擎与优先级排序
- pathlib 路径拼接、相对路径计算与路径安全校验
- EXIF 拍摄时间读取与可选依赖的优雅降级
- 冲突改名算法与批次内名字占用管理
- 先计划后执行的幂等设计与可回滚日志
- dataclass 配置建模与 JSON 配置校验
================================================================================
