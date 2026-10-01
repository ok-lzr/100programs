================================================================================
项目编号：031                    难度等级：★★☆☆☆（小型项目）
项目名称：哈希校验工具
所属分类：安全与编码 / 命令行工具
建议工时：3 ~ 5 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

从网盘下载一个 4 GB 的系统镜像，或者从同事手里拷来一份数据库备份，最让人不放心的
就是文件到底有没有在传输过程中损坏、有没有被人替换过。发布方通常会在下载页旁边放一
行 MD5 或 SHA256 摘要，用户需要自己算一遍再逐字符比对。手动比对既费眼又容易出错，
而 Windows 自带的 certutil 只支持单文件、输出格式零散，也没有目录批量能力。

本项目的目标就是做一个开箱即用的哈希校验工具：给定一个文件或一整棵目录，批量算出
MD5、SHA1、SHA256 摘要，既能输出成标准校验文件（GNU coreutils 风格的 sum 文件），
也能反过来读取校验文件逐个验证，并清晰地报告哪一个文件不匹配。

目标用户是需要验证下载包完整性的运维人员、需要给交付物出哈希清单的开发者，以及需要
为大量文件建立指纹记录、日后检测是否被篡改的普通用户。做成之后，一条命令即可完成
"生成清单 → 传输 → 校验清单"的完整闭环。

【二、功能需求清单】

1. 核心功能
   1.1 计算摘要：对单个文件计算 MD5、SHA1、SHA256 三种摘要，默认三种全算，
       可用 --algo 参数只算其中一种或多种（可重复传入或逗号分隔）。
   1.2 目录批量：输入为目录时递归遍历，默认只处理普通文件，跳过目录、符号链接
       （除非显式给出 --follow-symlinks）、以及所有非普通文件类型。
   1.3 生成校验清单：把"摘要 + 两个空格 + 相对路径"按行写入清单文件，格式与
       GNU coreutils 的 sha256sum 输出兼容，默认文件名 <目录名>.sha256，
       可用 -o 指定；清单头部以 # 注释行记录生成时间与工具版本。
   1.4 校验清单：读取清单文件，逐行解析，重新计算并比对。输出四类结果：
       OK、FAILED（摘要不一致）、MISSING（清单里有但磁盘上没有）、
       EXTRA（可选，--report-extra 时报告磁盘上存在但清单里没有的文件）。
   1.5 单文件快速比对：提供 --check-value <期望摘要> 参数，直接把计算结果与
       用户给出的字符串比对，输出"匹配/不匹配"并以退出码区分。

2. 输入与交互
   2.1 目标参数为位置参数，接受一个文件路径、一个目录路径，或 --files 后跟多个
       路径（通配符由 shell 展开）。
   2.2 --algo 取值限定为 md5、sha1、sha256，非法取值立即报错退出码 2。
   2.3 --exclude 接受可重复的 glob 模式（如 "*.tmp"、"node_modules/*"），
       在遍历阶段过滤；--min-size / --max-size 按字节过滤。
   2.4 --workers N 指定并发线程数，默认 4，取值 1~32，超出范围报错。
   2.5 无任何位置参数时进入交互模式：循环提示输入路径，输入 q 退出，
       每次输入后立即打印结果，便于手工逐个检查。

3. 输出与展示
   3.1 默认表格化文本输出，列为：ALGO、SIZE、DIGEST、PATH，
       摘要列不截断，路径显示为相对于当前输入根目录的形式。
   3.2 --format 支持 text、sum、json 三种。text 为人读表格；sum 为
       coreutils 兼容行；json 为数组，每项含 path、size、mtime、md5、sha1、sha256。
   3.3 进度显示：处理文件数超过 20 时，向 stderr 输出 "已完成 n/N"，
       每个文件完成即刷新一行；--quiet 关闭进度，只保留最终结果。
   3.4 校验总结行固定为 "校验完成：总计 N，通过 N，失败 N，缺失 N，耗时 X.XX 秒"。

4. 异常与边界处理
   4.1 路径不存在：打印 "错误：路径不存在 - <path>"，退出码 1，不继续处理其它路径。
   4.2 权限不足：捕获 PermissionError，把该文件记入 SKIPPED 列表并继续，
       结束时统一打印被跳过的文件与原因，退出码为 1（若有任何跳过或失败）。
   4.3 空文件：仍计算摘要，MD5 为 d41d8cd98f00b204e9800998ecf8427e，
       不得因 size 为 0 而跳过。
   4.4 空目录：打印 "未找到可处理的文件"，退出码 1。
   4.5 清单文件格式错误：行不含两个空格分隔符、摘要长度与算法不符、
       或摘要含非十六进制字符时，打印 "清单第 N 行格式错误：<原文>"，
       继续解析其余行，最终退出码 1。
   4.6 读取过程中文件被修改：记录的 size/mtime 与计算前后不一致时，
       标记为 UNSTABLE 并提示"文件在处理期间被修改，建议重算"。
   4.7 中断处理：捕获 KeyboardInterrupt，打印已完成的结果并退出码 130。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库，包括 argparse、hashlib、pathlib、os、sys、
   json、time、concurrent.futures、fnmatch、dataclasses、logging、typing。
   不引入任何第三方依赖。
3. 禁止事项：禁止把整个文件一次性 read() 进内存；禁止使用已破解的 MD5/SHA1
   作为安全用途宣传（文档中必须注明"MD5/SHA1 仅用于完整性校验，不用于安全对抗"）；
   禁止跳过异常静默失败；禁止在输出中硬编码本机绝对路径。
4. 代码组织：至少包含四个模块 —— hasher.py（摘要计算）、walker.py（目录遍历与
   过滤）、manifest.py（清单读写与解析）、cli.py（参数解析与主流程）。
   摘要计算函数签名固定为
   compute_digest(path: Path, algo: str, chunk_size: int = 1 << 20) -> str。
5. 编码规范：全部公开函数带类型注解与 docstring；使用 logging 输出调试信息，
   面向用户的结果走 stdout，进度与警告走 stderr；常量大写；路径处理统一用 pathlib。

【四、设计要点】

1. 数据结构：
   - FileRecord：path: Path，size: int，mtime: float，digests: dict[str, str]，
     status: str（OK/FAILED/MISSING/SKIPPED/UNSTABLE）。
   - ManifestEntry：digest: str，algo: str，rel_path: str，lineno: int。
   - VerifyReport：total、passed、failed、missing、extra、skipped，
     以及 failed_items: list[tuple[str, str, str]]（路径、期望、实际）。
2. 关键算法或流程：
   2.1 摘要计算采用流式分块读取，块大小 1 MiB，循环 hash_obj.update(chunk)，
       最后 hexdigest()；同一遍读取同时喂给多个 hashlib 对象，
       避免为了三种算法把文件读三遍。
   2.2 目录遍历使用 os.scandir 递归，收集到列表后按路径排序，保证输出稳定可复现。
   2.3 并发策略：concurrent.futures.ThreadPoolExecutor 提交每个文件的摘要任务，
       因为 hashlib 计算时释放 GIL，线程池对 I/O + 哈希场景有效；
       结果用 as_completed 收集，按原顺序回填。
   2.4 清单元素格式：<digest><两个空格><相对路径>，相对路径中的换行与反斜杠
       需要转义（coreutils 风格为行首加 "\" 并把路径中的 \n 写成 "\n" 两字符）。
   2.5 比对时不区分大小写，期望摘要统一 lower() 后比较。
3. 接口或命令设计：
   python cli.py <path> [--algo md5,sha256] [--format text|sum|json]
                 [--workers 4] [--exclude PATTERN]... [--follow-symlinks]
                 [--quiet] [--check-value HEX]
   python cli.py --verify <manifest.sha256> [--report-extra] [--quiet]
   python cli.py -i
   退出码约定：0 全部通过；1 有失败/缺失/跳过；2 参数错误；130 用户中断。

【五、运行方式与示例】

安装：无需安装，直接运行；可选 python -m venv .venv 建立虚拟环境。
运行：
   python cli.py .\downloads\ubuntu.iso --algo sha256 --format text
   python cli.py .\release --format sum -o release.sha256 --workers 8
   python cli.py --verify release.sha256 --report-extra
   python cli.py .\downloads\ubuntu.iso --check-value 3b1f...a92c

示例一（单文件）：
   输入：python cli.py sample.bin --algo md5,sha256
   输出：
   ALGO    SIZE      DIGEST                                                            PATH
   md5     1048576   f47b0e6c8f2d1a3b5c7e9f0a1b2c3d4e                                  sample.bin
   sha256  1048576   9c56cc51b374c3ba189210d5b6d4bf57790d351c96c47c02190ecf1e430635ab  sample.bin

示例二（目录生成清单并校验）：
   输入：python cli.py .\release --format sum -o release.sha256
   输出：清单文件 release.sha256 内容（节选）
   # generated by hash_checker 1.0 at 2024-05-20T10:12:33
   9c56cc51b374c3ba189210d5b6d4bf57790d351c96c47c02190ecf1e430635ab  app.exe
   a3f5d8e1c07b42f6901d2e3f4a5b6c7d8e9f0a1b2c3d4e5f60718293a4b5c6d7  data.zip
   然后：python cli.py --verify release.sha256
   输出：
   OK      app.exe
   FAILED  data.zip   期望 a3f5d8...  实际 1b2c3d...
   校验完成：总计 2，通过 1，失败 1，缺失 0，耗时 0.87 秒

示例三（异常输入）：
   输入：python cli.py .\not_exist_dir --algo sha512
   输出：
   错误：--algo 不支持 sha512，可选 md5 / sha1 / sha256
   退出码：2

【六、验收标准】

[ ] 对同一文件分别用本工具与系统 certutil 计算 SHA256，摘要完全一致。
[ ] 1 GiB 以上文件处理时内存占用稳定，RSS 增长不超过 50 MB。
[ ] --algo 只给 sha1 时，输出中不出现 md5 与 sha256 列。
[ ] 目录模式下输出的路径全部为相对路径，且不含 "./" 前缀混乱。
[ ] 生成的 sum 清单可直接被 GNU coreutils 的 sha256sum -c 通过（在 Linux 上验证）。
[ ] 清单中存在一行被篡改的摘要时，程序报告 FAILED 并给出期望值与实际值。
[ ] 清单中存在不存在于磁盘的文件时，报告 MISSING 且退出码为 1。
[ ] --exclude "*.tmp" 生效，被排除文件既不出现在输出也不出现在清单中。
[ ] 空文件摘要与标准值一致，不被跳过。
[ ] 无权限读取的文件被记为 SKIPPED 且程序不崩溃。
[ ] --workers 33 报参数错误，退出码为 2。
[ ] Ctrl+C 中断时打印已完成部分并返回 130。
[ ] --format json 输出可被 json.load 解析，字段名与文档一致。
[ ] 日志中不含任何硬编码的本机绝对路径。

【七、可选扩展】

1. 增加 BLAKE2b / SHA3-256 支持（hashlib 内置），并允许 --algo all。
2. 增加 --db sqlite 模式，把历史摘要存入 SQLite，支持"和上次比是否变化"的快速审计。
3. 支持从 HTTP 链接直读哈希（Range 分块下载后计算），避免先落盘再验。
4. 增加 --threads 自动调优：根据磁盘类型（SSD/HDD）与文件平均大小自动选并发度。

【八、涉及知识点】

- hashlib 流式更新与多算法复用同一次文件读取
- os.scandir 递归遍历、pathlib.Path 的相对路径计算（relative_to）
- concurrent.futures 线程池与 GIL 释放型任务的并行收益
- argparse 的子命令/互斥参数设计与退出码约定
- 文本清单格式的转义规则与 coreutils 兼容性
- dataclasses 建模、logging 分级输出、异常分类处理
- 文件变更检测（size + mtime + 前后一致性校验）
================================================================================
