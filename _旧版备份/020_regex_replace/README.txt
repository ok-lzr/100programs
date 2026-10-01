================================================================================
项目编号：020                    难度等级：★★☆☆☆（小型项目）
项目名称：正则批量替换工具
所属分类：命令行工具 / 文件与文本处理
建议工时：6 ~ 8 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

临时写一段脚本对几十个文件做查找替换，是很多开发者的共同经历：写完还要担心
"万一替换错了怎么办"。编辑器自带的替换通常只作用于当前打开的文件；
命令行工具又很少有预览与回滚能力。一次不小心的正则替换，可能把整个目录的代码改坏，
而版本控制并不总是可用（配置文件、数据文件、他人交付的目录常常不在 Git 里）。

本项目实现一个"默认预览、可预览不可逆操作、出错能回滚"的批量正则替换工具。
它先扫描文件生成每处匹配的行号与上下文，打印出统一差异格式（unified diff）供确认；
加 --apply 执行时先把原文件备份到指定的备份目录并写出清单 JSON；
一旦结果不对，一条 --rollback 命令即可按清单逐文件还原。

目标用户是需要跨文件重构（改名、调整导入路径、统一 API 调用）的开发者，
以及需要批量清洗文本数据、修正编码混乱文案的数据处理人员。
工具处理的是文本文件，遇到二进制文件一律跳过，绝不尝试解码改写。

【二、功能需求清单】

1. 核心功能
   1.1 正则查找：--pattern 指定 Python 正则表达式，支持命名分组 (?P<name>...)、
       非贪婪匹配、前瞻后顾、^ 与 $ 锚点；--ignore-case 等价于 re.IGNORECASE，
       --multiline 等价于 re.MULTILINE，--dotall 等价于 re.DOTALL，
       --verbose-regex 等价于 re.VERBOSE；可多个标志叠加。
   1.2 替换：--replacement 支持反向引用 \1、\g<name> 与 \g<1> 形式，
       默认按 re.sub 的语义处理未匹配的可选分组（替换为空字符串）。
       默认替换全部匹配，--max-count N 限制每个文件最多替换 N 处。
   1.3 预览（dry-run）：默认行为即预览，不写任何文件；对每个有匹配的文件输出
       文件名、匹配处数，并用 difflib.unified_diff 打印差异（可用 --context 控制上下文行数，
       默认 3；--max-diff-lines 限制最多打印行数，默认 200，超出时提示被截断）。
   1.4 只列出匹配文件：--files-with-matches 只输出包含匹配的文件路径，
       不打印差异，适合管道接入其它工具；--count 只输出每个文件的匹配处数。
   1.5 备份：--apply 时默认把每个被修改的原文件复制到备份目录
       （默认在被处理目录下创建 .regex_replace_backup_YYYYMMDD_HHMMSS），
       保持相对路径结构；--backup-suffix .bak 可改为在原文件旁生成同名副本；
       --no-backup 关闭备份，必须与 --apply 及 --force 同时使用。
   1.6 清单与回滚：备份目录内写出 manifest.json，逐条记录 relative_path、
       backup_path、original_sha256、replaced_sha256、replacements、mtime、mode；
       --rollback 清单路径 校验当前文件哈希是否等于 replaced_sha256，
       相等才还原，否则跳过并计入报告，避免覆盖用户在替换后手工做的修改。
   1.7 过滤：--glob "**/*.py"（可重复）、--exclude "*/node_modules/*"、
       --ext py,js,ts、--min-size 与 --max-size；默认只处理普通文件，
       跳过目录、符号链接、隐藏文件（加 --include-hidden 才处理）。
   1.8 大文件处理：默认一次性读取（每文件大小上限由 --max-file-size 控制，默认 10 MB）；
       超过上限的文件跳过并提示可用 --chunk 模式，--chunk 模式下按行流式处理，
       代价是不支持跨行的多行匹配（此时若使用 --multiline 则直接报参数冲突）。
   1.9 统计：处理文件数、匹配文件数、替换处数、跳过文件数（按原因分类：
       二进制、编码不可识别、只读、超过大小上限、无权限）、耗时。

2. 输入与交互
   2.1 位置参数为待处理文件或目录；目录默认递归处理，--no-recursive 只看当前层。
   2.2 --dry-run 是默认值；--apply 才真正写入。两者同时给出时以 --apply 为准并提示。
   2.3 交互确认：--apply 时若未加 --yes，先打印将被修改的文件数并要求输入 yes，
       输入其它内容即中止且不写入任何文件。
   2.4 输入源：--pattern-file patterns.txt 从文件读取多组"正则制表符替换文本"规则，
       按顺序依次作用于每个文件（前一条规则的输出作为后一条的输入）。
   2.5 编码：--encoding 强制输入编码；默认按 BOM 识别 utf-8-sig 与 utf-16，
       无 BOM 时依次尝试 utf-8、gb18030；文件无法用任何候选编码解码时跳过并计入跳过统计。
       输出编码与输入编码保持一致（含 BOM 的有无），避免把 GBK 文件写成 UTF-8。

3. 输出与展示
   3.1 差异输出使用标准统一差异格式（以三个连字符、三个加号和两个 at 符号开头的行），
       与常见版本控制工具的 diff 输出习惯一致，便于粘贴进工单。
   3.2 每处匹配在差异中显示行号；--show-match 额外打印匹配文本与其正则分组内容。
   3.3 --json 输出结构化预览结果：文件、匹配数、替换数、差异行数、跳过原因。
   3.4 结果与差异写标准输出，进度与统计写标准错误流。

4. 异常与边界处理
   4.1 正则表达式无法编译时报错并退出码 2，错误信息包含 re.error 的原始描述与位置。
   4.2 二进制文件保护：读取时检测前 8 KB 是否含 NUL 字节，含则跳过并标注"二进制文件"；
       同时按扩展名黑名单（exe、dll、so、zip、png、jpg、pdf、woff、pyc 等）提前跳过。
   4.3 文件为只读属性或无写权限时跳过并记录，不尝试修改权限。
   4.4 替换结果与原文完全相同时不写文件、不备份、不计入替换数（保持幂等）。
   4.5 写入过程必须先写同目录临时文件再 os.replace 原子替换，
       保留原文件的权限位与换行风格（CRLF 与 LF 不变），写完校验字节数变化是否符合预期。
   4.6 写入中途失败（磁盘满或无权限）时立即停止剩余文件，已完成的记录保留在清单中，
       提示可执行回滚命令。
   4.7 备份目录不可创建时在预览结束、写入开始前报错退出，不执行任何替换。
   4.8 同一批次中若某个文件被两条规则先后修改，清单中要合并记录为一条并累计替换处数。
   4.9 --multiline 与 --chunk 同时使用时参数校验失败并说明原因，退出码 2。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库 argparse、re、os、sys、io、json、time、hashlib、logging、
   pathlib、difflib、shutil、tempfile、stat、fnmatch、dataclasses、typing、collections；
   禁止使用任何第三方库（包括 regex、click、rich）。
3. 禁止事项：禁止在未加 --apply 时写文件或创建备份目录；禁止直接覆盖原文件
   （必须走临时文件加 os.replace）；禁止修改文件权限与所有者；
   禁止把无法解码的文件按错误策略强行解码后写回（无法解码即跳过）；
   禁止在 --no-backup 时缺少 --force 的情况下执行替换。
4. 代码组织：至少拆分为 scan.py（文件发现与过滤）、engine.py（正则规则与替换执行）、
   differ.py（差异渲染）、backup.py（备份与清单）、rollback.py（回滚校验与执行）、
   cli.py（参数与确认交互）。engine 中的单文件处理函数必须是纯函数：
   输入原文本与规则列表，输出新文本与替换处数，不做任何 I/O。
5. 编码规范：类型注解与 docstring 齐全；规则列表用 dataclass 描述并支持命名；
   日志使用 logging，--debug 时打印每个文件的编码探测结果与读取字节数；
   异常处理必须包含文件路径与规则名称上下文。
6. 性能约束：处理 2000 个、每个不超过 100 KB 的文件时应在 10 秒内完成预览；
   正则对象必须只编译一次并在所有文件上复用。

【四、设计要点】

1. 数据结构
   1.1 ReplaceRule：字段 name（str）、pattern（已编译的正则）、replacement（str）、
       max_count（int）、enabled（bool）。
   1.2 FileTarget：字段 path（Path）、relative_path（Path）、size、encoding、has_bom、
       newline（"\\n" 或 "\\r\\n"）、is_readonly、skipped_reason。
   1.3 MatchReport：字段 path、match_count、replace_count、diff_lines、
       original_sha256、replaced_sha256、encoding。
   1.4 BackupEntry：字段 relative_path、backup_path、original_sha256、replaced_sha256、
       replacements、mtime、mode、rules_applied。
   1.5 Manifest：字段 started_at、root、backup_dir、rules（规则的文本描述）、
       entries（list[BackupEntry]）、finished。

2. 关键算法或流程
   2.1 文件发现：用 os.walk 遍历（可剪枝排除目录），对每个文件依次判断
       glob 白名单、扩展名、排除模式、大小范围、隐藏属性、符号链接、二进制特征与编码可解码性。
   2.2 编码与换行探测：二进制读取整个文件；有 BOM 则记录并按对应编码解码；
       否则依次尝试候选编码（严格模式）；换行风格通过统计 "\\r\\n" 与 "\\n" 出现次数判断，
       写入时统一按检测结果输出，避免把 CRLF 文件整体改写为 LF。
   2.3 替换执行：按规则顺序对文本调用 pattern.subn(replacement, text, count=max_count)，
       累计替换数；所有规则执行完毕后再与原文比较，相同则视为无变化。
   2.4 差异渲染：用 text.splitlines(keepends=True) 保留换行，
       调用 difflib.unified_diff(old_lines, new_lines, fromfile=相对路径, tofile=相对路径,
       n=context)，逐行输出并累计行数，超过 --max-diff-lines 时截断并提示。
   2.5 备份：为每个待修改文件在备份目录下按相对路径创建父目录并复制原文件（shutil.copy2
       保留时间与权限），计算原文与替换后文本的 SHA-256 写入清单；
       清单在写入过程完成后一次性落盘，并在每条动作后更新内存中的 finished 标记。
   2.6 原子写入：在同目录用 tempfile.NamedTemporaryFile(delete=False) 写新内容，
       用 shutil.copystat 复制原文件权限与时间，再用 os.replace 覆盖原文件，
       最后删除临时文件残留。
   2.7 回滚：读取清单，逐条计算当前文件 SHA-256，与 replaced_sha256 相等才用
       shutil.copy2 把备份覆盖回去；不相等或文件已不存在则记为跳过并说明原因；
       全部完成后把清单重命名为 .rolled_back.json。

3. 接口或命令设计
   3.1 python regex_replace.py src/ --pattern "old_api\\(" --replacement "new_api(" --ext py
   3.2 python regex_replace.py . --pattern "(?P<k>\\w+)_v1" --replacement "\\g<k>_v2" --glob "**/*.md" --json
   3.3 python regex_replace.py docs/ --pattern "\\s+$" --replacement "" --multiline --apply --yes
   3.4 python regex_replace.py . --rollback .regex_replace_backup_20240301_101500/manifest.json --apply
   3.5 核心函数签名：apply_rules(text: str, rules: list[ReplaceRule]) -> tuple[str, int]；
       render_diff(old: str, new: str, name: str, context: int) -> list[str]；
       create_backup(targets: list[FileTarget], backup_dir: Path) -> Manifest；
       rollback(manifest_path: Path, dry_run: bool) -> RollbackReport。

【五、运行方式与示例】

1. 安装与运行：无需安装依赖，执行 python regex_replace.py --help 查看全部参数。
2. 示例一（预览替换效果）：
   输入：python regex_replace.py src/ --pattern "old_api\\(" --replacement "new_api(" --ext py
   输出：--- src/main.py
         +++ src/main.py
         @@ -12,3 +12,3 @@
         -result = old_api(1, 2)
         +result = new_api(1, 2)
         （stderr）预览：1 个文件将被修改，共 1 处替换，未写入任何文件
3. 示例二（命名分组替换）：
   输入：python regex_replace.py . --pattern "(?P<k>\\w+)_v1" --replacement "\\g<k>_v2" --glob "**/*.md"
   输出（stderr）：已列出 3 个文件共 7 处替换（预览模式）
4. 示例三（真正执行并备份）：
   输入：python regex_replace.py src/ --pattern "FIXME" --replacement "NOTE" --apply --yes
   输出：已修改 6 个文件，替换 9 处，备份目录 .regex_replace_backup_20240301_101500，
         清单 manifest.json 已写入
5. 示例四（回滚）：
   输入：python regex_replace.py . --rollback .regex_replace_backup_20240301_101500/manifest.json --apply
   输出：已还原 6 个文件，跳过 1 个（文件在替换后被手工修改，哈希不一致）
6. 示例五（二进制文件跳过）：
   输入：python regex_replace.py assets/ --pattern "a" --replacement "b"
   输出（stderr）：跳过 assets/logo.png（二进制文件）、跳过 assets/app.exe（扩展名黑名单），
         处理文本文件 4 个
7. 示例六（非法正则）：
   输入：python regex_replace.py . --pattern "([a-z" --replacement "x"
   输出（stderr）：错误：正则表达式无法编译（missing ), unterminated subpattern at position 0），
         退出码 2，未处理任何文件
8. 示例七（参数冲突）：
   输入：python regex_replace.py . --pattern "a$" --multiline --chunk
   输出（stderr）：错误：--chunk 模式下不支持 --multiline，请去掉其中一个参数，退出码 2

【六、验收标准】

[ ] 1. 不加 --apply 时所有文件内容与修改时间均不变，且不创建备份目录。
[ ] 2. 预览差异为标准统一差异格式，行号与上下文行数符合 --context 设置。
[ ] 3. --pattern "old_api\\(" 只替换带左括号的调用，不误伤 old_api_v2 这类标识符。
[ ] 4. 命名分组 \\g<name> 与数字引用 \\1 均能正确展开。
[ ] 5. --max-count 1 时每个文件只替换第一处匹配。
[ ] 6. --ignore-case、--multiline、--dotall 三个标志的行为与 re 模块语义一致。
[ ] 7. 含 NUL 字节的文件被跳过，且其字节内容与修改时间完全不变。
[ ] 8. PNG、EXE、PDF 等扩展名文件在扫描阶段即被跳过，不出现在预览结果中。
[ ] 9. GBK 编码文件被替换后仍为 GBK，用 GBK 解码器可正常读取且中文不乱码。
[ ] 10. CRLF 文件在替换后仍为 CRLF，行尾不变成 LF。
[ ] 11. 替换后文件权限位与替换前一致，未被改成默认权限。
[ ] 12. --apply 生成的备份目录结构与原目录一致，manifest.json 可被 json.loads 解析。
[ ] 13. --rollback 能完整还原全部文件（用 SHA-256 逐文件比对验证）。
[ ] 14. 手工修改过某个文件后回滚，该文件被跳过并计入跳过统计，其它文件正常还原。
[ ] 15. 只读文件被跳过，程序不尝试修改其权限。
[ ] 16. --no-backup 缺少 --force 时拒绝执行，退出码 2。
[ ] 17. 批量处理 2000 个文件的预览耗时低于 10 秒。

【七、可选扩展】

1. 增加 --rule-file rules.json，用配置文件描述多条规则、作用文件范围与顺序。
2. 增加 --git-aware 选项，替换前检查工作区是否干净，避免与版本控制冲突。
3. 增加 --report report.md，把预览差异汇总为一份可评审的报告文件。
4. 增加 --dry-run-exit-code，只要存在匹配就返回退出码 1，便于在持续集成中阻止残留旧 API 调用。
5. 增加 --regex-timeout（基于信号或分段执行）防止灾难性回溯导致长时间卡死。

【八、涉及知识点】

- re 模块：compile、subn、分组与反向引用、命名分组、IGNORECASE/MULTILINE/DOTALL/VERBOSE 标志
- 正则设计中的精确性问题（左括号锚定避免误伤相似标识符）
- difflib.unified_diff 的差异渲染与上下文行控制
- 文件编码探测、BOM 处理与新旧编码一致性
- 换行风格（CRLF 与 LF）检测与保留
- 二进制文件判定（NUL 字节检测与扩展名黑名单）
- 原子写入（临时文件加 os.replace）与权限、时间戳保留
- 备份清单、SHA-256 校验与可回滚设计
- dry-run 默认、交互确认与幂等（无变化不写入）的工程原则
- argparse 参数冲突校验与退出码约定
================================================================================
