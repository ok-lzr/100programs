================================================================================
项目编号：082                    难度等级：★★★★☆（中型项目，偏难）
项目名称：增量备份与恢复工具
所属分类：业务管理系统 / 数据保护
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：click、rich、pytest（可选：zstandard）
================================================================================

【一、项目背景与目标】

个人和小团队的数据保护通常停留在“每周手动拷一份到移动硬盘”的阶段。真正需要恢复时才会
发现问题：拷过去的文件是三天前的、目录结构对不上、某个重要子目录被漏掉了、压缩包解压
报校验错误。更现实的问题是，全量拷贝几百 GB 数据每次都要几个小时，于是备份频率越来越低，
最终形同虚设。

本项目实现一个可脚本化调用的增量备份与恢复工具。核心思路是：第一次做全量备份，之后每次
只备份相对上一次快照发生变化的文件；每个快照附带一份清单（manifest），逐文件记录相对
路径、大小、修改时间、内容哈希与归档位置；恢复时可以整体还原到某个时间点，也可以只挑
某几个文件还原。因为清单里存了内容哈希，所以“备份是否可用”这件事可以在不恢复的情况下
通过校验命令提前发现。

目标用户是用命令行管理文件的开发者、把家里 NAS 当资料库的个人用户，以及需要给客户做一个
可交付备份脚本的外包开发者。工具设计成单文件命令即可跑，支持 Windows 与 Linux 双平台，
备份目标可以是本地另一个磁盘，也可以是以 UNC 路径或挂载点形式出现的网络位置。

安全性要求：工具只做文件复制与校验，不修改源文件；恢复时必须支持“先预览再写入”的
dry-run 模式，避免误覆盖现有数据；所有涉及凭据的操作（例如后续接入对象存储）都从环境变量
读取，不落盘、不硬编码。

【二、功能需求清单】

1. 核心功能
   1.1 全量备份：命令 backup --full 把源目录完整写入新快照，快照目录命名形如
       snapshot-20250316T091203，内部包含 data/（数据文件）、manifest.json（清单）、
       meta.json（元信息）。
   1.2 增量备份：命令 backup --incremental 读取上一次快照的清单，仅归档“新增、被修改、
       被删除”三类变化。判定修改的依据依次为：文件大小变化、mtime 变化、内容哈希变化
       （哈希只在大小与 mtime 都相同时作为补充判定，避免全量重算拖慢速度）。
   1.3 删除追踪：被删除的文件不在新快照里存数据，但在清单的 deleted 列表中登记，恢复时
       依据快照链判定该文件在某时间点已不存在。
   1.4 快照链：meta.json 记录 parent_snapshot 字段，形成链式结构；list 命令可打印完整链条
       与每层的文件数、占用空间。
   1.5 清单校验：verify 命令重新计算快照内每个文件的实际哈希并与清单比对，输出通过数量、
       损坏数量与缺失数量；支持 --deep 参数强制全量重算（默认只校验大小与抽样哈希）。
   1.6 一键恢复：restore 命令接受快照 ID 与目标目录。默认恢复“该快照对应的完整时间点视图”，
       即沿快照链依次叠加全量与增量，得到逻辑完整目录树，而不是只还原增量那部分文件。
   1.7 选择性恢复：restore --only "docs/*.md" --only "config/*.yaml" 支持按 glob 过滤；
       restore --file-list list.txt 支持从文本文件读取待恢复路径清单。
   1.8 保留策略：prune 命令按 keep_last（保留最近 N 个）、keep_daily（保留最近 N 天每天
       最新一个）、max_total_size（总大小上限）三条规则清理旧快照。清理时若发现某个增量
       快照被更晚的快照依赖，必须先合并或提升其为全量，禁止留下断链。
   1.9 告警与记录：每次备份结束写入 history.jsonl，含快照 ID、类型、耗时、新增/修改/删除
       文件数、总字节数、状态。失败时（源目录不存在、磁盘剩余空间不足、校验失败）写
       ERROR 级日志并以非零退出码结束。

2. 输入与交互
   2.1 CLI 子命令：init、backup、list、verify、restore、prune、compare、config。
   2.2 配置来源优先级：命令行参数 > 环境变量（BACKUP_SOURCE、BACKUP_DEST）> 仓库内
       config.json > 内置默认值，合并后的最终配置在启动时打印一次。
   2.3 首次运行 init 在目标位置创建仓库结构：snapshots/、index.db（SQLite 索引）、
       config.json、history.jsonl。
   2.4 交互式确认：restore 与 prune 默认在执行前打印影响面摘要（将覆盖多少文件、将删除
       哪些快照）并要求输入 yes 确认；加 --yes 参数可跳过。

3. 输出与展示
   3.1 backup 过程用 rich 进度条展示已处理文件数与字节数，结束时打印统计表格。
   3.2 list --detail 输出每个快照的 ID、类型、父快照、创建时间、文件数、大小、状态
       （OK/INCOMPLETE/BROKEN_CHAIN）。
   3.3 compare 命令比较两个快照或“快照与当前目录”，输出 A 独有、B 独有、内容不同的
       文件清单，形如 diff 的三段式输出。
   3.4 verify 结束打印：总计 N 个文件，通过 N1，损坏 N2（附首个损坏文件路径），缺失 N3。

4. 异常与边界处理
   4.1 备份中途被 Ctrl+C 中断时，当前快照目录标记为 INCOMPLETE 并写入 meta.json，
       list 能识别；恢复时拒绝使用 INCOMPLETE 快照。
   4.2 磁盘剩余空间不足时提前用 shutil.disk_usage 检查，按“待备份总大小 * 1.15”预估，
       不足则中止并提示需要多少空间。
   4.3 文件在备份过程中被其他进程修改：先记录开始时的 (size, mtime)，写完后重新 stat，
       不一致则把该文件记入 unstable_files 列表并在结束时告警，不静默放过。
   4.4 路径超长（Windows 260 字符限制）：自动为归档文件名生成短哈希别名，原始路径存于
       清单 mapping 字段中。
   4.5 空目录、空文件、只有一层目录的源、源与目标为同一目录（必须拒绝）等情况均有明确
       处理与提示。
   4.6 符号链接默认跳过并计数，加 --follow-symlinks 才跟随，且必须检测循环引用。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，路径操作全部使用 pathlib，禁止字符串拼接路径。
2. 允许使用的库：click（CLI）、rich（进度条与表格）、zstandard（可选压缩，未安装时回退到
   tarfile 的 gzip 模式）、pytest（测试）。核心能力必须仅用标准库实现：hashlib（blake2b 或
   sha256 分块读取，块大小 1 MiB）、tarfile/zipfile（归档）、sqlite3（快照索引）、
   shutil（复制与磁盘空间）、json、os、argparse（如需无依赖版本）。
3. 禁止事项：禁止把源目录内容读入内存后整体写出；禁止使用 os.system 调用系统 tar/rsync；
   禁止在清单中写入用户口令或网络凭据；禁止在恢复时不做 dry-run 直接覆盖非空目录。
4. 代码组织：模块划分为 hashing（分块哈希与哈希缓存）、manifest（清单读写与版本兼容）、
   storage（归档读写、压缩、短路径映射）、diff（目录比对与变化分类）、snapshot（快照链
   管理）、restore（叠加恢复与 glob 过滤）、prune（保留策略与链合并）、cli。
5. 编码规范：全部公开函数有类型注解与 docstring；清单文件 version 字段从 1 开始，读取旧
   版本必须向后兼容；日志使用 logging 输出到控制台与 logs/backup.log；禁止 print 输出
   除用户交互提示外的调试信息。

【四、设计要点】

1. 数据结构
   - manifest.json：
     {"version": 1, "snapshot_id": "...", "type": "full|incremental", "parent": "..."|null,
      "created_at": "...", "source_root": "...", "files": [FileEntry...],
      "deleted": ["相对路径"...], "mapping": {"短名": "原相对路径"}, "unstable_files": []}
   - FileEntry：path（相对路径，统一用正斜杠）、size、mtime（ISO8601）、hash（blake2b-256
     十六进制）、archive（归档文件名）、archive_offset（可选，便于单文件抽取）、mode。
   - meta.json：快照级元信息，含状态、耗时、统计计数、工具版本、主机名。
   - SQLite 索引表 snapshots(snapshot_id PK, parent, type, created_at, status, file_count,
     total_bytes) 与 files(snapshot_id, path, hash, size, archive, PRIMARY KEY(snapshot_id, path))。
2. 关键算法或流程
   - 变化判定：对源目录 os.scandir 递归收集候选 → 与上一快照清单按相对路径建字典 →
     分类为 added / modified / deleted / unchanged。modified 判定：size 不同为 modified；
     size 相同且 mtime 不同，则计算哈希，哈希不同才算 modified（避免仅触碰文件导致重复备份）。
   - 增量归档：只把 added 与 modified 文件写入本次 tar 归档，归档内路径使用短名映射。
   - 恢复叠加：从目标快照沿 parent 回溯到全量快照，得到快照序列 [full, inc1, inc2, ...]，
     正序应用：先解出 full 全部文件，再依次用后续快照覆盖，最后从最新快照的 deleted 列表
     中删除对应文件，得到时间点视图。
   - 哈希缓存：index.db 中按 (path, size, mtime) 缓存哈希，缓存命中则跳过读取。
   - 链合并：prune 删除中间快照前，把该快照的文件条目合并进其子快照清单，并把子快照的
     type 提升为 full（或标记为 synthesized），保证任何快照都能独立还原。
3. 接口或命令设计
   - python -m backup init --dest D:\backup_repo
   - python -m backup backup --source C:\work --full --compress zstd
   - python -m backup backup --source C:\work --incremental --exclude "*.tmp" --exclude node_modules
   - python -m backup verify --snapshot latest --deep
   - python -m backup restore --snapshot 20250316T091203 --target C:\restore --only "docs/*.md" --dry-run
   - python -m backup prune --keep-last 5 --keep-daily 14 --max-total-size 200GB
   - 核心函数：hash_file(path, block=1MiB) -> str；build_manifest(...) -> Manifest；
     apply_to_view(chain, target_dir, filters) -> RestoreReport。

【五、运行方式与示例】

安装与运行：
    pip install click rich zstandard pytest
    python -m backup init --dest D:\backup_repo
    python -m backup backup --source C:\projects\100programs --full
    python -m backup backup --source C:\projects\100programs --incremental
    python -m backup list --detail

示例一（首次全量）：
    输入：python -m backup backup --source C:\photos --full
    输出：快照 20250316T091203 创建完成（全量）
          文件 12480 个，新增 12480，修改 0，删除 0，共 8.6 GB，压缩后 8.1 GB，耗时 312 秒

示例二（第二次增量）：
    输入：python -m backup backup --source C:\photos --incremental
    输出：快照 20250317T090011 创建完成（增量，父快照 20250316T091203）
          新增 12，修改 3，删除 1，共 46.2 MB，耗时 4 秒
          警告：1 个文件在备份期间被修改，已记入 unstable_files（photos/2025/trip.jpg）

示例三（校验）：
    输入：python -m backup verify --snapshot 20250317T090011
    输出：校验完成：总计 12492，通过 12491，损坏 1（photos/raw/corrupt.cr2），缺失 0
          存在损坏文件，退出码 2

示例四（恢复）：
    输入：python -m backup restore --snapshot 20250317T090011 --target D:\restore --only "docs/*.md"
    输出：将恢复 37 个文件到 D:\restore（覆盖 2 个已存在文件），是否继续？yes
          恢复完成：写入 37，跳过 0，删除 0，耗时 1.2 秒

示例五（异常输入）：
    输入：python -m backup backup --source C:\not_exist --full
    输出：错误：源目录不存在或不是目录：C:\not_exist，备份未开始，退出码 1

【六、验收标准】

[ ] 首次全量备份后 manifest.json 中每个文件都有路径、大小、mtime、哈希四项
[ ] 第二次增量备份只归档新增与修改文件，未变文件不进入归档（用归档内文件数核对）
[ ] 删除文件在增量快照的 deleted 列表中登记，恢复后该文件确实不存在
[ ] 对某个快照做恢复，得到的目录树与该时间点的源目录内容逐文件哈希一致
[ ] restore --dry-run 不写入任何文件，只输出将发生的动作
[ ] --only 与 --file-list 两种过滤方式均生效，未匹配路径不写入目标
[ ] verify 能检出被手工篡改内容的文件，退出码与报告数量一致
[ ] Ctrl+C 中断后快照状态为 INCOMPLETE，且该快照无法被 restore 使用
[ ] prune 删除中间快照后，剩余任意快照仍可独立完整恢复（回归测一遍）
[ ] 磁盘空间不足时在开始前中止，不产生半成品快照
[ ] 路径超长场景下归档不报错，清单 mapping 能还原出原始相对路径
[ ] 备份期间被修改的文件被记入 unstable_files 并在控制台告警
[ ] 全部哈希分块读取，处理 1 GB 以上文件时内存占用低于 100 MB
[ ] 恢复非空目录必须经过确认或 --yes，不存在静默覆盖路径

【七、可选扩展】

1. 接入对象存储（S3 兼容接口），把快照归档上传到远端，实现 3-2-1 备份策略中的异地一份。
2. 增加加密备份：用 cryptography 库的 AES-GCM 对归档加密，密钥由用户口令经 PBKDF2 派生，
   密钥不落盘。
3. 增加 Windows 卷影副本（VSS）或 Linux LVM 快照的调用封装，解决打开中文件无法一致备份
   的问题。
4. 增加备份健康度报表：按周统计备份成功率、平均耗时、增长速率，输出 HTML 报告。

【八、涉及知识点】

- 分块文件哈希、哈希缓存与增量变化检测算法
- tarfile/zipfile 归档格式、流式读写与单文件抽取
- 快照链（全量 + 增量）模型、恢复时的叠加算法与断链处理
- SQLite 索引表设计与大批量插入优化
- 磁盘空间预估、文件并发修改检测、符号链接循环检测
- click 子命令与参数校验、rich 进度条与表格渲染
- 备份保留策略（GFS 思路）与链合并的工程取舍
- 数据完整性校验（离线校验与恢复校验的区别）、退出码约定
================================================================================
