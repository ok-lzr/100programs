================================================================================
项目编号：083                    难度等级：★★★★☆（中型项目，偏难）
项目名称：双向文件同步工具
所属分类：业务管理系统 / 文件协同
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：watchdog、click、rich、paramiko（远程同步时）
================================================================================

【一、项目背景与目标】

“笔记本和台式机上各改了一版代码，回家发现两边文件都不一样了”——这是双向同步最典型的
使用场景。简单粗暴的整目录覆盖会丢数据，而成熟的同步工具（如 rsync 单向、Syncthing 后台
常驻）对学习和可控性来说都不够透明：出了问题不知道哪台机器上的哪一版被保留、被覆盖的版本
去哪里找。

本项目实现一个命令行驱动的双向文件同步工具：给定两个目录（或本地目录与一台远程主机上的
目录），先做完整比对，把每个文件的变化分成“只有 A 有”“只有 B 有”“两边都有但内容不同”
“两边都有且内容相同”四类；对“两边都有但不同”的情况按用户选定的冲突策略处理，并在处理前
保留被覆盖版本的副本；同步以增量方式只传输发生变化的文件；传输中断后可以从断点继续，不必
从头再来。

目标用户是需要在两三台设备之间保持资料一致的个人用户、需要在测试机与开发机之间同步配置的
开发者。工具的核心价值是“可见”与“可回退”：每一次同步前都打印完整计划，每一次覆盖都把旧
版本入库，任何一次同步都能通过日志和版本库还原回去。

安全与合规要求：涉及远程同步时，凭据（私钥路径、口令）只从环境变量或 SSH agent 读取，
不写入配置文件；不扫描与同步系统敏感目录（如 C:\Windows、/etc、/proc），对用户指定的路径
做白名单校验；工具只处理用户明确给出的目录，不做任何后台常驻的隐式上传。

【二、功能需求清单】

1. 核心功能
   1.1 目录比对：递归扫描两侧目录，输出四类文件清单；比对依据依次为文件大小、mtime，
       最后用内容哈希（blake2b）确认；支持 --fast 模式跳过哈希，仅凭大小与 mtime 判定。
   1.2 冲突策略：命令行参数 --conflict 取值为 newer（保留较新侧，默认）、larger、left、
       right、rename（两边都保留，冲突侧改名为 文件名.conflict-主机名-时间戳）、skip
       （跳过冲突文件并列出）、ask（逐个询问）。必须在计划阶段就展示每个冲突将如何解决。
   1.3 版本库：所有被覆盖或被删除的文件，同步前先复制到 .sync_vault/<时间戳>/ 下，
       保留相对路径与原始 mtime，并写一条 vault.jsonl 记录来源、原因、目标侧。
   1.4 增量同步：只传输变化文件；大文件按固定块大小（默认 4 MiB）切块计算块哈希，
       与对端已有文件的分块哈希对比，只传差值块（rsync 弱校验和思路的简化版），
       并在同步完成后做全文件哈希校验。
   1.5 断点续传：传输过程中每完成一个块就写一条进度记录到 .sync_state/<session_id>.json
       （含文件相对路径、总块数、已完成块索引、临时文件名）；命令中断后再次执行同一
       目录对时，检测到未完成会话则提示续传，续传只补传缺失块并重新计算整文件哈希。
   1.6 归档式同步：可选 --archive 参数使删除也参与同步（默认单向删除不传播，避免误删），
       开启后某侧删除的文件会在另一侧删除，但删除前同样进入版本库。
   1.7 远程同步：支持 local（本地到本地）、sftp（通过 paramiko 连接远程主机）两种后端，
       两者共用同一套比对与计划逻辑；后端抽象成 Backend 接口，实现 list_files、
       read_chunk、write_chunk、stat、delete 五个方法。
   1.8 同步计划与执行分离：plan 命令只输出计划不落地，sync 命令先调 plan 再执行；
       --dry-run 等价于 plan --format json。
   1.9 记录与统计：每次同步写 reports/sync-<时间戳>.json，含耗时、传输字节数、四类文件
       数量、冲突解决明细、峰位速度；控制台打印一行汇总。

2. 输入与交互
   2.1 CLI 子命令：init、plan、sync、resume、check（只校验两侧是否一致）、vault-list、
       vault-restore、status。
   2.2 路径书写规则：本地路径直接写；远程路径写 user@host:/path，并支持 --port、
       --identity 参数；远程路径解析失败时给出明确错误。
   2.3 过滤规则：--include 与 --exclude 支持 glob，且遵循“先排除后包含”的顺序；
       默认排除 .git、node_modules、*.tmp、Thumbs.db、.sync_vault、.sync_state。
   2.4 vault-restore 支持 --file 与 --timestamp 两个维度还原被覆盖的单个文件。
   2.5 冲突策略为 ask 时，逐条提示：文件路径、左侧大小与时间、右侧大小与时间，输入
       L/R/S 选择保留哪侧或跳过，输入 A 表示全部跳过后续冲突。

3. 输出与展示
   3.1 plan 输出示例：
       目录比对完成：A=C:\work，B=D:\mirror
       A 独有 12 个（3.4 MB），B 独有 3 个（120 KB）
       内容不同 5 个（冲突），完全相同 8421 个
       冲突处理计划：
         src/app.py          newer  -> 用 A 覆盖 B（已备份到 vault）
         docs/spec.md        rename -> B 侧版本改名为 spec.conflict-PC2-20250316T0931.md
   3.2 sync 过程用 rich 显示总体进度条与当前文件速度，结束打印传输速率与校验结果。
   3.3 status 显示当前未完成会话、版本库占用空间、上次同步时间与结果。
   3.4 check 命令返回退出码：0 表示两侧一致，3 表示存在差异，便于脚本集成。

4. 异常与边界处理
   4.1 传输中断（网络断开、Ctrl+C、磁盘写满）时必须保住已传的临时文件与进度记录，
       临时文件命名统一为 <文件名>.<session_id>.part，避免污染目标目录。
   4.2 同一目录对禁止并发运行两个 sync 进程：用 .sync_state/lock 文件加进程 ID 与时间戳
       做互斥，检测到陈旧锁（进程已退出）时提示可加 --force-unlock。
   4.3 文件名大小写差异：Windows 与 Linux 互同步时出现 Readme.md 与 README.md 视为
       不同文件并给出告警，不得静默合并。
   4.4 权限不足、文件被占用、目标只读目录等情况逐文件记录失败原因，不中断整体同步，最后
       汇总失败清单并返回非零退出码。
   4.5 符号链接与目录联接默认不跟随，避免同步出无限展开的目录树。
   4.6 两侧目录之一为空目录时，若加 --archive 需二次确认，防止把整目录清空。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；路径统一使用 pathlib，跨平台路径分隔符不得出现在
   比对键中（比对键统一用相对路径的正斜杠形式）。
2. 允许使用的库：watchdog（可选，实现 sync --watch 实时同步）、click（CLI）、rich
   （进度与表格）、paramiko（SFTP 远程后端）、pytest（测试）。本地比对、哈希、块切分、
   文件复制、JSON 状态机一律使用标准库 hashlib、shutil、os、json、threading、
   concurrent.futures、fnmatch。
3. 禁止事项：禁止把整个大文件读入内存做哈希（必须分块流式处理）；禁止在配置文件中保存
   SSH 口令或私钥内容；禁止删除未进入版本库的文件；禁止对同一目录树的两侧做嵌套同步
   （如 A 是 B 的父目录），启动时必须检测并拒绝。
4. 代码组织：模块划分为 backend（本地与 SFTP 两套实现）、scanner（递归扫描与规则过滤）、
   comparator（四类分类与冲突判定）、diffsync（块级差异计算）、transfer（传输、续传、
   临时文件管理）、vault（版本库写入与还原）、report（报告输出）、cli。
5. 编码规范：全部函数有类型注解与 docstring；Backend 抽象基类用 abc.ABC 定义并写清每个
   方法的契约；所有文件操作使用 with 上下文；日志写入 logs/sync.log 并用 logging 分级。

【四、设计要点】

1. 数据结构
   - FileMeta：rel_path、size、mtime_ns、hash（可选）、is_dir、mode。
   - CompareResult：only_left、only_right、differ、same，每项为 list[FileMeta]。
   - ConflictPlan：rel_path、left_meta、right_meta、strategy、action、vault_path。
   - TransferState：session_id、pair_key（左右根目录哈希）、file_rel_path、total_blocks、
     done_blocks、block_size、temp_path、updated_at。
   - BlockIndex：file_hash、block_size、blocks: list[str]（每块哈希），存于对端
     .sync_state/index/<rel_path 哈希>.json，用于块级差量传输。
   - Backend 抽象接口：list_files(root, rules) -> list[FileMeta]、stat(rel) -> FileMeta、
     read_chunk(rel, offset, size) -> bytes、write_chunk(rel, offset, data, temp=True)、
     commit_temp(rel, temp_path)、delete(rel)、mkdirs(rel)。
2. 关键算法或流程
   - 比对流程：两侧并行扫描生成 FileMeta 字典 → 按 rel_path 求并集 → 对同时存在的条目
     依次比较 size、mtime、hash（--fast 时跳过 hash）→ 得到四类结果。
   - 块级差量：目标侧若已存在同名文件且大小接近，读取其 BlockIndex；对源文件按块计算
     强哈希（blake2b），逐块比对，命中则不传、缺失则传；传输完成后对整文件做一次哈希
     校验，不一致则回滚为整文件重传。
   - 续传流程：写 .part 文件 → 每块写完后原子更新 state.json（先写 .tmp 再 os.replace）
     → 全部完成时 commit_temp 原子重命名到最终路径 → 删除 state 记录。
   - 版本库：覆盖或删除前，把原文件复制到 .sync_vault/<UTC 时间戳>/<相对路径>，复制时
     保留 mtime（shutil.copy2），并追加一行 vault.jsonl。
   - 冲突判定：newer 比较 mtime，若 mtime 相同则比较哈希（不同则视为真冲突，按较大文件
     处理并告警）；rename 时冲突文件名格式为 stem.conflict-host-yyyymmddTHHMMSS.ext。
3. 接口或命令设计
   - python -m filesync plan C:\work D:\mirror --exclude "*.log" --conflict rename
   - python -m filesync sync C:\work user@10.0.0.8:/data/mirror --identity %USERPROFILE%\.ssh\id_ed25519
   - python -m filesync resume --session 8f2a1c
   - python -m filesync vault-restore --file src/app.py --timestamp 20250316T093102 --to C:\work
   - 核心函数：compare(left: Backend, right: Backend, rules) -> CompareResult；
     plan_conflicts(result, strategy) -> list[ConflictPlan]；transfer_file(src, dst, state)。

【五、运行方式与示例】

安装与运行：
    pip install watchdog click rich paramiko pytest
    python -m filesync init C:\work D:\mirror
    python -m filesync plan C:\work D:\mirror --conflict newer
    python -m filesync sync C:\work D:\mirror --conflict newer

示例一（首次比对与同步）：
    输入：python -m filesync sync C:\work D:\mirror --conflict newer
    输出：A 独有 41，B 独有 2，内容不同 3，相同 1902
          冲突：src/main.py A 较新 -> 覆盖 B（已备份 .sync_vault/20250316T101500/src/main.py）
          传输 3.6 MB，用时 4.1 秒，校验通过，退出码 0

示例二（只出计划不落地）：
    输入：python -m filesync plan C:\work D:\mirror --format json --dry-run
    输出：{"only_left": 41, "only_right": 2, "differ": 3, "same": 1902,
           "actions": [{"path": "src/main.py", "strategy": "newer", "action": "left_to_right"}]}
          未写入任何文件，退出码 3（存在差异）

示例三（断点续传）：
    输入：python -m filesync sync C:\work D:\mirror --block-size 4M
    （中途 Ctrl+C，再执行）
    输出：检测到未完成会话 8f2a1c（video/demo.mp4，已完成 812/2048 块）
          是否续传？（y/n）y
          续传完成，补传 1236 块（4.7 GB），整文件哈希校验通过

示例四（异常输入）：
    输入：python -m filesync sync C:\work C:\work\sub --archive
    输出：错误：两侧目录存在嵌套关系（C:\work\sub 位于 C:\work 之内），
          拒绝同步以避免递归复制，退出码 1

【六、验收标准】

[ ] plan 能把两侧文件准确分为独有、不同、相同三类，计数与手工统计一致
[ ] 六种冲突策略（newer/larger/left/right/rename/skip/ask）行为均与文档描述一致
[ ] 被覆盖与被删除的文件都能在 .sync_vault 中找到，且能按路径与时间戳还原
[ ] 默认模式不传播删除，加 --archive 后才传播，且删除前进入版本库
[ ] 块级传输只传变化块：对 100 MB 文件中改动 1 MB，实际传输量明显小于 100 MB
[ ] 传输中断后 part 文件与 state.json 保留，可续传并最终校验通过
[ ] 续传完成后目标文件哈希与源文件哈希一致
[ ] 断网、只读目标、文件被占用等失败场景被逐文件记录且不计入成功数
[ ] 同一目录对不允许并发运行，重复执行第二个进程被锁拒绝
[ ] 嵌套目录同步被拒绝，退出码非零
[ ] 大小写差异文件被识别并告警，不会静默覆盖
[ ] 远程 SFTP 后端能完成与本地后端相同的比对与同步流程
[ ] 报告中传输字节数、耗时、四类计数与实际情况一致
[ ] 全部大文件操作内存占用平稳，无一次性读入整个文件的代码路径

【七、可选扩展】

1. 增加 sync --watch 常驻模式，基于 watchdog 监听文件事件，静默期 2 秒后自动增量同步。
2. 增加三方同步：以中间目录为中转，协调三台设备的版本，做拓扑式冲突收敛。
3. 增加内容感知的合并：对文本文件冲突尝试三方合并（based on difflib），无法自动合并时
   生成带冲突标记的文件。
4. 增加同步策略模板文件（.filesync.yaml），支持为不同目录设置不同冲突策略与过滤规则。

【八、涉及知识点】

- 目录树递归扫描、glob 过滤规则与跨平台路径处理
- 文件哈希（分块流式计算）与弱校验和（块级 rsync 思路）
- 三向比对与冲突解决策略设计，版本库与回滚机制
- 原子文件操作（写临时文件后 os.replace）与断点续传状态机
- 并发传输、线程池与进度汇总
- paramiko 的 SFTP 协议、SSH 密钥认证与连接复用
- click 参数校验、rich 进度渲染、结构化 JSON 报告设计
- 锁文件、互斥与进程幂等性保障
================================================================================
