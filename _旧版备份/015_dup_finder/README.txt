================================================================================
项目编号：015                    难度等级：★★☆☆☆（小型项目）
项目名称：重复文件查找器
所属分类：命令行工具 / 文件与文本处理
建议工时：5 ~ 7 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

磁盘里的重复文件往往来自这些场景：手机导照片时同一张图存了两三份；下载目录里
"报告.pdf""报告 (1).pdf""报告-最终版.pdf"其实是同一份文件；不同项目目录里各留了一份相同的
第三方库压缩包。逐个人工比对文件名不可靠（名字不同内容可能相同，名字相同内容可能已改），
按大小找又会把大量不相关文件列在一起。

本项目实现一个分级比对的重复文件查找器：先用文件大小把不可能重复的文件排除掉，
再比对文件首尾各 4 KB 的指纹做快速筛选，最后只对通过前两级的候选计算完整 SHA-256 哈希。
这样能在保证判断准确的前提下，把磁盘读取量降到最低——1 万个文件里真正需要全量读哈希的
通常只有几十个。

目标用户是磁盘空间紧张的普通用户、整理素材库的摄影爱好者、维护构建产物目录的开发者。
工具默认只输出报告，不做任何删除；即使显式要求清理，也会先把文件移动到隔离目录而不是
直接删除，并生成可回滚的清单。

【二、功能需求清单】

1. 核心功能
   1.1 扫描阶段：递归遍历根目录，收集每个文件的路径、大小、修改时间、inode 标识
       （st_dev 与 st_ino），跳过目录、符号链接、套接字与设备文件。
   1.2 一级筛选：按文件大小分组，只保留数量大于 1 的大小分组；
       大小唯一的文件直接判定为不重复，不参与后续任何读取。
   1.3 二级筛选：对同大小分组内的文件读取首 4 KB 与末 4 KB（文件小于 8 KB 时读全部），
       拼接后计算 SHA-256 作为"快速指纹"；指纹不同的文件被排除。
   1.4 三级确认：对通过二级筛选的文件分块读取（默认 1 MB）计算完整 SHA-256，
       分块大小可用 --chunk-size 调整；相同哈希的文件归为同一重复组。
   1.5 硬链接识别：同一 (st_dev, st_ino) 的文件属于同一份数据的多个名字，
       默认不视为重复（不重复占用空间），但在报告中单列"硬链接组"并给出说明；
       可用 --count-hardlinks 改变这一行为。
   1.6 空文件处理：0 字节文件默认单独归类为"空文件"并只给出数量提示，
       加 --include-empty 时才当作重复处理。
   1.7 清理建议：每个重复组按 --keep 策略推荐保留哪一个文件，其余标记为可清理；
       策略包括 oldest（最早修改）、newest（最新修改）、shortest-path（路径最短）、
       first-scanned（扫描顺序第一个）、top-level（层级最浅）。
   1.8 空间统计：输出重复组数、冗余文件数、可回收总空间，并按扩展名给出冗余空间排行榜。
   1.9 报告导出：--json 输出机器可读结果，--csv 输出逐文件表格，--report report.txt
       输出人类可读报告并落盘。
   1.10 清理执行：--move-to-trash DIR 把建议清理的文件移动到隔离目录（保持相对路径结构，
       同名冲突加序号）；--delete 是危险选项，必须同时给出 --yes 才生效，
       否则打印警告并退出；所有清理动作默认只在 --apply 时执行，否则一律为预览。

2. 输入与交互
   2.1 位置参数可给多个根目录，各目录内分别分组，跨目录的相同文件也算重复（用 --per-directory 关闭）。
   2.2 过滤条件：--min-size 1KB 忽略小文件、--max-size 500MB 忽略超大文件、
       --ext jpg,png,pdf 只看指定扩展名、--exclude "*/node_modules/*" 排除路径模式。
   2.3 --include-hidden 才会处理隐藏文件，默认跳过；--one-file-system 不跨盘符或挂载点。
   2.4 扫描时向标准错误流打印进度（已扫描文件数、已读字节数），--quiet 关闭进度。
   2.5 交互确认：--apply 时列出前 10 条待处理动作并要求输入 yes；整个流程可用 --yes 跳过确认。

3. 输出与展示
   3.1 默认文本报告按重复组输出，每组形如：
       组 1（3 个文件，每个 2.4 MB，可回收 4.8 MB）
         [保留] D:\photos\2024\trip.jpg（2024-03-01 10:20）
         [清理] D:\backup\trip.jpg（2023-01-11 08:02）
         SHA-256 前 16 位：9f2c1a...
   3.2 组间按可回收空间从大到小排序，便于优先处理大头。
   3.3 末尾汇总：扫描文件数、读取字节数、压缩率（实际读取字节数占全部文件大小的比例）、
       重复组数、可回收空间、耗时。
   3.4 所有输出写标准输出，警告与错误写标准错误，进度信息不得混入标准输出。

4. 异常与边界处理
   4.1 文件在扫描与读取之间被删除或改名时捕获 FileNotFoundError，从分组中移除并计入跳过数。
   4.2 文件被其它进程独占（PermissionError）时跳过该文件并记录路径，不中断整体流程。
   4.3 文件在读取过程中被修改（读取前后 stat 的大小或 mtime 不一致）时丢弃该文件哈希并给出警告，
       避免得出错误结论。
   4.4 根目录不存在或不可读时报错并以退出码 2 结束。
   4.5 隔离目录位于被扫描目录内部时给出提示，并自动排除隔离目录本身，防止自我吞噬。
   4.6 --delete 未同时提供 --yes 时拒绝执行，退出码 2，且不删除任何文件。
   4.7 待清理文件与保留文件位于同一硬链接组时给出提醒，说明删除后空间可能并未释放。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库 argparse、os、sys、hashlib、json、csv、time、logging、
   pathlib、collections、dataclasses、typing、shutil、fnmatch、stat；禁止使用任何第三方库，
   禁止借助外部命令（如 fc、dupeGuru）完成比对。
3. 禁止事项：禁止把整个文件读入内存计算哈希（必须分块读取，单次读取量由 --chunk-size 控制）；
   禁止在未加 --apply 的情况下修改文件系统；禁止直接删除文件（除 --delete --yes 组合外）；
   禁止读取文件内容以外的元数据用途滥用（例如不得修改文件访问时间之外的任何属性）。
4. 代码组织：至少拆分为 scan.py（遍历与元数据收集）、pipeline.py（三级筛选流程）、
   grouper.py（分组与保留策略）、reporter.py（文本、JSON、CSV 输出）、
   cleaner.py（隔离与删除）、cli.py（参数与确认）。pipeline 的每一级都必须是
   输入可分组的迭代器，便于观察各级筛选效果。
5. 编码规范：类型注解与 docstring 齐全；哈希函数统一封装为 hash_file(path, chunk_size)
   与 hash_head_tail(path)；日志使用 logging，默认 INFO，--debug 输出每级筛选的剩余文件数。
6. 安全约束：隔离目录必须与源目录不同的父层级推荐放置；写入隔离清单 JSON
   （含 source、target、hash、moved_at）以便原样还原；还原命令为 --restore 清单路径。

【四、设计要点】

1. 数据结构
   1.1 FileMeta：字段 path（Path）、size（int）、mtime（float）、dev、ino、ext、hidden。
   1.2 HashCache：字典 key 为 (size, mtime) 或路径，value 为计算过的哈希，
       避免同一文件被重复读取；--cache 文件可把结果持久化到 JSON 以便二次运行加速。
   1.3 DupGroup：字段 group_id、size、file_count、wasted_bytes、keep_path、
       members（list[FileMeta]）、full_hash。
   1.4 CleanupPlan：字段 action（keep / move / delete）、source、target、reason。
   1.5 ScanStats：字段 files_seen、files_hashed、bytes_read、bytes_total、
       skipped、groups、wasted_bytes、elapsed_ms。

2. 关键算法或流程
   2.1 三级筛选顺序固定：size 分组 → 首尾指纹分组 → 全量 SHA-256 分组。
       每一级都只对上一级的候选集继续处理，任何一级分组后只剩一个成员的分组立即淘汰。
   2.2 首尾指纹：文件小于 8 KB 时直接整体读取；否则读前 4096 字节与后 4096 字节，
       中间插入文件大小与 mtime 的十进制字符串，再计算 SHA-256；
       设计上只求快速区分，不做安全用途，文档中必须写明这一点。
   2.3 分块读取：循环 read(chunk_size) 直到返回空 bytes，每块 update 到哈希对象；
       每处理 64 MB 检查一次文件当前的 stat 是否与开始时一致。
   2.4 保留策略：oldest 取 mtime 最小者（并列时取路径最短者）；newest 反之；
       shortest-path 取 len(str(path)) 最小者；策略实现为独立的可比较键函数，便于扩展。
   2.5 隔离移动：按源路径相对于根目录的相对路径在隔离目录下重建子目录，
       目标已存在时追加 _1、_2 直到不冲突；移动使用 shutil.move 以支持跨盘。
   2.6 回滚：读取隔离清单，逐条校验 source 位置当前为空且 target 存在，再把文件移回。

3. 接口或命令设计
   3.1 python dup_finder.py D:\photos E:\backup --min-size 64KB --keep oldest --json
   3.2 python dup_finder.py . --ext jpg,png,heic --exclude "*/node_modules/*" --report dup.txt
   3.3 python dup_finder.py D:\data --move-to-trash D:\dup_trash --apply --yes
   3.4 python dup_finder.py --restore D:\dup_trash\trash_manifest.json --apply
   3.5 核心函数签名：scan(roots: list[Path], filters: Filters) -> Iterator[FileMeta]；
       find_duplicates(files: Iterable[FileMeta], keep: str) -> list[DupGroup]；
       execute(plan: list[CleanupPlan], mode: str, dry_run: bool) -> CleanupReport。

【五、运行方式与示例】

1. 安装与运行：无需安装依赖，执行 python dup_finder.py --help 查看全部参数。
2. 示例一（只报告不清理）：
   输入：python dup_finder.py D:\photos --min-size 100KB
   输出：组 1（3 个文件，每个 2.4 MB，可回收 4.8 MB）
         [保留] D:\photos\2024\trip.jpg（2024-03-01 10:20）
         [清理] D:\backup\trip.jpg（2023-01-11 08:02）
         汇总：扫描 8123 个文件，实际读取 96.4 MB（占总量 3.1%），重复组 17 个，可回收 213.6 MB
3. 示例二（导出 JSON）：
   输入：python dup_finder.py . --json > dup.json
   输出：dup.json 中每个组含 group_id、size、full_hash、keep_path 与 members 数组，
         可被 json.loads 解析
4. 示例三（隔离清理，预览）：
   输入：python dup_finder.py D:\data --move-to-trash D:\dup_trash
   输出：预览：将移动 42 个文件到 D:\dup_trash（可回收 1.2 GB），未做任何修改，
         重新运行时加 --apply 才会执行
5. 示例四（真实清理）：
   输入：python dup_finder.py D:\data --move-to-trash D:\dup_trash --apply --yes
   输出：已移动 42 个文件，清单写入 D:\dup_trash\trash_manifest.json，
         可用 --restore 该清单还原
6. 示例五（危险选项缺少确认）：
   输入：python dup_finder.py D:\data --delete
   输出（stderr）：错误：--delete 必须与 --yes 同时使用，已终止，未删除任何文件，退出码 2
7. 示例六（文件被占用）：
   输入：python dup_finder.py D:\data
   输出（stderr）：警告：无法读取 D:\data\locked.db（文件被占用），已跳过该文件，
         其余 3 个同大小文件继续比对

【六、验收标准】

[ ] 1. 构造三个内容完全相同的文件与两个内容不同但大小相同的文件，只有前者被判为重复。
[ ] 2. 一级筛选后大小唯一的文件不再被打开读取（用 --debug 输出的读取文件数验证）。
[ ] 3. 首尾指纹相同的文件才进入全量哈希阶段，全量哈希不同的文件不会误判为重复。
[ ] 4. 内容相同但文件名、扩展名、修改时间均不同的文件能正确归入同一组。
[ ] 5. 内容不同但大小相同的两个 txt 文件不被判为重复（验证三级筛选有效）。
[ ] 6. 硬链接组在默认模式下不计入可回收空间，报告中单列并给出说明。
[ ] 7. --keep newest 时被标记为保留的是组内 mtime 最大的那个文件。
[ ] 8. 0 字节文件在未加 --include-empty 时只统计数量，不进入重复组。
[ ] 9. 未加 --apply 时运行前后文件系统完全一致，无任何文件被移动或删除。
[ ] 10. --move-to-trash 后隔离目录内文件内容哈希与源文件一致，清单 JSON 可被解析。
[ ] 11. --restore 清单后所有文件回到原始相对路径，目录结构完整。
[ ] 12. --delete 缺少 --yes 时退出码为 2 且文件总数不变。
[ ] 13. 扫描过程中被删除的文件不会导致程序崩溃，跳过数正确累计。
[ ] 14. 处理 10 GB 目录时进程内存占用稳定在 100 MB 以内（验证分块读取有效）。
[ ] 15. --csv 输出的行数等于所有重复组内成员数之和，字段顺序与文档一致。

【七、可选扩展】

1. 增加 --similar-name 模式，用 difflib.SequenceMatcher 找出文件名高度相近的疑似重复对。
2. 增加 --perceptual 模式，对图片先缩放为 8x8 灰度再比对哈希，识别内容相近但不完全相同的图。
3. 增加持久化哈希缓存（--cache dup_cache.json），二次运行时按 (size, mtime) 直接复用。
4. 增加 --du 输出各子目录占用空间排行榜，与重复清理报告合并展示。
5. 增加 --link-instead 把冗余文件替换为指向保留文件的硬链接，兼顾保留与省空间。

【八、涉及知识点】

- 分级筛选思想：用便宜的判据先淘汰大多数候选，再对少量候选做昂贵计算
- hashlib 分块哈希、增量 update、SHA-256 与 MD5 的取舍
- os.stat 的 st_dev、st_ino、st_size、st_mtime 与硬链接、符号链接的区别
- 大文件 I/O 的分块读取与内存控制
- 字典分组与 collections.defaultdict 的聚合技巧
- JSON 与 csv 模块的结构化输出
- 文件系统变更竞态（TOCTOU）与读取前后 stat 校验
- 安全删除的设计：隔离目录、清单文件、可回滚操作
- 内置比较键函数与策略模式（保持策略可插拔）
================================================================================
