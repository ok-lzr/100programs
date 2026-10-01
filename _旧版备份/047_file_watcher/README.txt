================================================================================
项目编号：047                    难度等级：★★★☆☆（小型项目）
项目名称：文件夹变更监控器
所属分类：命令行工具 / 系统编程
建议工时：5 ~ 7 小时
运行环境：Python 3.10+    第三方依赖：watchdog >= 4.0（pip install watchdog）
                         可选：rich（美化输出）、plyer 或 win10toast（桌面通知）
================================================================================

【一、项目背景与目标】

有一类需求反复出现：某个目录一有新文件就想立刻做点什么。设计稿导出目录一有新图就自动压缩
并同步到共享盘；服务器日志目录一有异常写入就发通知；扫描仪输出目录一有新 PDF 就按日期归档；
代码仓库里某个配置被修改就重启本地服务。每次都要人盯着，既费时间又容易漏。

本项目实现一个本地文件夹监控器：基于操作系统的文件系统事件（Windows 的 ReadDirectoryChangesW、
macOS 的 FSEvents、Linux 的 inotify），实时捕获创建、修改、删除、移动、重命名五类事件，把事件
按统一格式写入日志（可读文本或 JSON Lines），并在命中规则时执行外部命令或调用内置动作。

关键在于“可用”而不是“能跑”：真实的文件系统事件会重复触发（编辑器保存一次可能产生 3~5 个
事件）、会在大文件复制到一半时提前触发、会因为临时文件（.swp、.tmp、~$）产生噪音。程序必须
用去抖动（debounce）、稳定期检测（文件大小连续两次不变才算完成）、忽略规则来应对，否则下游
动作会被触发十几次。

目标用户是开发者、运维和需要做本地自动化的办公用户。做成之后，它可以替代“目录监控+批处理”
这类零散脚本，成为本机自动化流水线的触发层。

【二、功能需求清单】

1. 核心功能
   1.1 事件监控：用 watchdog.observers.Observer 监听一个或多个路径（--path 可重复），
       FileSystemEventHandler 的 on_created/on_modified/on_deleted/on_moved 四个回调统一
       转成内部事件对象。--recursive 控制是否监听子目录。
   1.2 事件规范化：内部事件字段为 ts（ISO8601 本地时间）、event（created/modified/deleted/
       moved）、src（相对被监控根目录的路径）、dest（仅 moved 有）、is_dir、size、ext（小写）。
       路径统一用正斜杠输出，保证跨平台日志可对比。
   1.3 去抖动与稳定检测：同一路径在 --debounce（默认 1.0 秒）内的重复事件只保留最后一次；
       created/modified 事件在触发动作前进入稳定检测：每隔 --settle-interval（默认 0.5 秒）
       读取 st_size，连续两次相同且文件可独占打开（Windows 用 os.open + os.O_RDWR 测试）
       才认为写入完成，最多等待 --settle-timeout（默认 30 秒）。
   1.4 过滤规则：--include '*.pdf,*.jpg' 与 --exclude '*.tmp,~$*,*.swp,.git/*' 通配符匹配
       （用 fnmatch 与 pathlib.PurePath.match 组合）；--min-size 与 --max-size 按字节过滤；
       --ignore-hidden 忽略以 . 开头的文件；--events created,deleted 只关心指定事件类型。
   1.5 动作执行：--exec 模板命令，支持占位符 {path} {relpath} {event} {ext} {name} {dir}
       {size}；多个 --exec 按顺序执行；--exec-on created 限定事件类型；命令用
       subprocess.run(args_list, shell=False) 执行，模板先用 shlex.split(..., posix=False 时
       自行处理) 拆成参数列表，避免文件名注入。--timeout 限制单条命令执行时间。
   1.6 内置动作：--copy-to DIR（复制新文件到目标目录）、--move-to DIR（移动并保持相对结构）、
       --archive-by-date（按 YYYY-MM-DD 归档）、--log-only（只记日志，默认行为）。
   1.7 输出：--log-file events.log 写文本行；--jsonl events.jsonl 写 JSON Lines（每行一个
       事件对象，便于后续用 jq 或 Python 分析）；--stdout 实时打印彩色行。
   1.8 运行控制：--duration 2h 或 --count 100 后退出；--pid-file monitor.pid 写入进程号；
       Ctrl+C 优雅停止并打印统计；--stats 输出各事件类型计数与处理耗时。

2. 输入与交互
   2.1 命令行：python watcher.py --path ./inbox --recursive --include '*.csv'
       --exec "python import.py {path}" --log-file events.log。
   2.2 配置文件 watch.toml：[[watchers]] 段落定义多组监控（每组含 path、include、exec 列表、
       动作），--config 加载后各组分别启动，互不影响。
   2.3 --dry-run 只打印将要执行的动作与命令内容，不真正调用外部命令。
   2.4 --replay events.jsonl 读取历史事件日志并重新执行匹配规则，用于测试规则而不必反复造文件。
   2.5 --once 配合 --replay 或首次全量扫描（--initial-scan）后退出，适合放进 cron。

3. 输出与展示
   3.1 控制台行：2025-05-06 14:32:05  created  inbox/report.csv        12.4KB  -> 执行 import.py
   3.2 动作结果跟随一行：-> ok  退出码 0  耗时 812ms；失败时输出 -> failed 退出码 1 与 stderr 末段。
   3.3 退出汇总：运行 1h02m；事件 148 个（created 96 / modified 40 / deleted 8 / moved 4）；
       命中规则 96 次；动作成功 94，失败 2；去抖动合并 213 次。
   3.4 --stats 额外输出耗时分布：动作平均 812ms，最慢 4.2s（文件 report_big.csv）。

4. 异常与边界处理
   4.1 被监控路径不存在：启动即报错并退出码 1；--create-if-missing 时自动创建目录。
   4.2 监控路径不可读或无权限：捕获 PermissionError，报告并跳过该路径（多路径时不影响其他）。
   4.3 事件风暴（如解压上万文件的压缩包）：当 1 秒内事件数超过 --max-events-per-sec
       （默认 200）时进入“洪泛模式”，只记录汇总不逐条执行动作，并打印警告；洪泛结束后
       可选执行一次 --exec-on-flood-end 命令。
   4.4 稳定检测超时（文件一直在写）：记 warning，按 --on-settle-timeout skip|run 决定跳过
       还是强行执行动作。
   4.5 去抖缓存无限增长：缓存按路径字典实现，超过 10000 条或每 60 秒清理一次已过期的键。
   4.6 外部命令失败或超时：捕获 subprocess.TimeoutExpired 与 CalledProcessError，记 failed，
       不中断监控；--max-failures 达到上限后退出。
   4.7 文件在动作执行前被删除：捕获 FileNotFoundError，记为 skipped-deleted。
   4.8 符号链接：默认不跟随（follow_symlinks=False），--follow-symlinks 开启并提示可能的循环
       风险。
   4.9 网络盘与虚拟文件系统：文档中说明 Windows 映射盘、Docker 挂载卷、macOS /Volumes 上的
       inotify/FSEvents 可能不产生事件，建议用 --poll-fallback。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：watchdog（事件监控）；标准库 argparse、pathlib、fnmatch、subprocess、shlex、
   logging、json、time、datetime、hashlib、tomllib、signal、threading、queue、stat、os。
   可选：rich（彩色表格输出）。平台降级方案：watchdog.observers.polling.PollingObserver。
3. 禁止事项：禁止用 while True + os.listdir 轮询作为默认实现（会漏事件且吃 CPU），轮询仅作为
   --poll-fallback 的备选；禁止用 shell=True 执行外部命令；禁止在未加 --dry-run 时先打印后
   执行造成日志与行为不一致；禁止修改被监控目录中的文件内容（除非 --move-to/--copy-to）。
4. 代码组织：
   - events.py：@dataclass FileEvent 与 from_watchdog_event() 转换、to_jsonl()、to_text()。
   - filters.py：FilterSet 类，load_include/load_exclude、match(path) -> bool、
     以及 min/max size 与 hidden 判断。
   - debounce.py：Debouncer 类（按路径合并事件）与 SettleChecker 类（稳定性轮询）。
   - actions.py：Action 抽象基类，子类 RunCommand、CopyTo、MoveTo、ArchiveByDate、
     LogOnly，统一 execute(event) -> ActionResult。
   - watcher.py：Handler(FileSystemEventHandler) 把 watchdog 事件投递到内部 queue.Queue。
   - cli.py：参数、配置加载、主消费者循环与统计输出。
5. 编码规范：类型注解完整；Handler 回调内只做最轻的工作（放入队列），耗时逻辑全在消费者
   线程，避免阻塞 watchdog 的事件线程；时间戳统一带毫秒；日志同时支持人读与机读两种格式；
   docstring 说明每个参数的单位与平台差异；异常不得静默吞掉，至少记 DEBUG。

【四、设计要点】

1. 数据结构：
   FileEvent：ts(datetime)、event(str)、root(Path)、src(Path)、dest(Path|None)、
   is_dir(bool)、size(int|None)、ext(str)、seq(int 自增序号)。
   派生属性：relpath（相对 root 的 posix 风格路径）、name、dir。
   ActionResult：event(FileEvent)、action(str)、status(ok|failed|skipped|timeout|dry-run)、
   exit_code(int|None)、elapsed_ms(float)、stderr_tail(str|None)。
   Stats：counts(dict[str,int])、debounced(int)、actions_ok(int)、actions_failed(int)、
   floods(int)、started_at(datetime)。

2. 关键算法或流程：
   2.1 事件流：watchdog 线程回调 -> 规范化 FileEvent -> 放入 queue.Queue(maxsize=10000)
       -> 主循环 get(timeout=0.5) -> 过滤 -> 去抖 -> 稳定检测 -> 执行动作 -> 记录结果。
       queue 满时丢弃并计数（记 warning），绝不阻塞 watchdog 线程。
   2.2 去抖动：维护 dict[Path, FileEvent]；新事件到来时写入 pending[path] = event 并记录
       due = now + debounce；主循环每轮扫描 pending，把 due <= now 的条目取出处理并删除。
       这样无需为每个文件起定时器线程。
   2.3 稳定检测：check(path) 记录 (size, mtime) 两次采样；相同则视为稳定。为了兼容
       “先创建后写入”的场景，created 事件也走同一流程。大文件复制时可观察到 size 递增，
       每次变化都重置采样。
   2.4 外部命令构造：模板先做占位符替换（str.format_map，值为经过 posix 路径转换的字符串），
       再用自定义 split_args() 拆分：按空格切分但保留引号内内容（用 shlex.shlex 处理，
       posix=False 以适配 Windows 反斜杠路径）。构造好的参数列表在 --verbose 时打印。
   2.5 复制/移动的目录结构保持：dst = target_dir / rel.src；用 shutil.copy2 或 shutil.move，
       dst.parent.mkdir(parents=True, exist_ok=True)；同名冲突加 _1、_2。
   2.6 洪泛检测：用一个长度为 1 秒的滑动窗口计数（collections.deque 记录时间戳），
       超过阈值则设置 flood_until = now + 5 秒，期间只记汇总。
   2.7 优雅退出：signal 设置 stop_event；主循环结束时 observer.stop() + observer.join()，
       再把 pending 中剩余事件处理完（或按 --flush-pending 决定丢弃）。

3. 接口设计：
   python watcher.py --path DIR [--path DIR2] [--recursive]
     [--include '*.pdf,*.jpg'] [--exclude '*.tmp,~$*'] [--min-size N] [--max-size N]
     [--ignore-hidden] [--events created,modified,deleted,moved]
     [--debounce 1.0] [--settle-interval 0.5] [--settle-timeout 30]
     [--exec 'CMD {path}'] [--exec-on created] [--timeout 60]
     [--copy-to DIR] [--move-to DIR] [--archive-by-date] [--log-only]
     [--log-file events.log] [--jsonl events.jsonl] [--stdout]
     [--config watch.toml] [--dry-run] [--initial-scan]
     [--replay events.jsonl] [--once] [--duration 2h] [--count N]
     [--max-events-per-sec 200] [--max-failures 10] [--poll-fallback]
     [--pid-file monitor.pid] [--stats] [--verbose]
   核心函数：handle_event(ev: FileEvent, filters: FilterSet, actions: list[Action]) -> list[ActionResult]
             wait_until_stable(path: Path, interval: float, timeout: float) -> bool

【五、运行方式与示例】

1. 安装依赖：
   pip install "watchdog>=4.0"

2. 监控收件目录，新 CSV 自动入库：
   python watcher.py --path ./inbox --recursive --include '*.csv' --events created
     --exec "python import_data.py {path}" --log-file events.log
   输出：2025-05-06 14:32:05  created  inbox/2025-05.csv  12.4KB  -> 执行 import_data.py
         -> ok  退出码 0  耗时 812ms
         2025-05-06 14:32:06  created  inbox/~$2025-05.csv  -> 被 --exclude 规则忽略

3. 设计稿自动归档：
   python watcher.py --path D:\design --recursive --include '*.png,*.jpg'
     --archive-by-date --copy-to E:\backup --debounce 2.0 --settle-timeout 60
   输出：2025-05-06 15:01:12  created  design/banner_v2.png  2.1MB  -> archive-by-date
         -> ok  D:\design\2025-05-06\banner_v2.png  耗时 12ms

4. 用配置文件启动多组监控：
   python watcher.py --config watch.toml --stdout --log-file all.log
   （watch.toml 内定义 [[watchers]]：日志目录只记 JSONL，素材目录执行压缩命令）

5. 预演规则（不执行外部命令）：
   python watcher.py --path ./inbox --include '*.csv' --exec "python import.py {path}" --dry-run
   输出：dry-run 2025-05-06 14:32:05 created inbox/a.csv -> 将执行：python import.py inbox/a.csv

6. 异常示例：监控路径不存在
   python watcher.py --path ./not_exist --exec "echo {path}"
   输出：错误：被监控路径不存在：D:\work\not_exist（提示：加 --create-if-missing 可自动创建）
         （退出码 1）

7. 异常示例：外部命令失败
   python watcher.py --path ./inbox --exec "python missing_script.py {path}"
   输出：2025-05-06 14:40:00  created  inbox/b.csv  -> failed 退出码 2
         stderr: python: can't open file 'missing_script.py': [Errno 2] No such file or directory
         （监控继续，失败计数 1/10）

【六、验收标准】

[ ] 在监控目录中新建文件，1~2 秒内捕获 created 事件并打印正确的大小与相对路径。
[ ] 用记事本保存一个已存在文件，只产生一条 modified 逻辑事件（去抖动生效）。
[ ] 复制一个 500MB 文件到监控目录，动作在复制完成后才执行（稳定检测生效），且只执行一次。
[ ] 删除文件产生 deleted 事件；重命名文件产生 moved 事件且 src/dest 都正确。
[ ] --include 与 --exclude 组合过滤准确，被排除的文件不产生任何动作。
[ ] --min-size 1024 时 500 字节的新文件不触发动作。
[ ] 解压一个含 5000 个文件的压缩包时程序不崩溃、内存不暴涨，日志出现“洪泛模式”提示。
[ ] --copy-to 后目标目录结构与源一致，源文件保持不变。
[ ] --move-to 后源文件消失、目标文件存在且内容 SHA-256 与源一致。
[ ] --archive-by-date 按文件的本地日期归档，跨午夜测试目录正确。
[ ] 带空格与中文的文件名通过 {path} 传给外部命令时不出现参数截断（验证未用 shell=True）。
[ ] 外部命令超时（--timeout 2 加一个 sleep 10 的命令）被杀死并记为 timeout。
[ ] --dry-run 全程不产生任何子进程、不复制任何文件（用日志与目录对比验证）。
[ ] Ctrl+C 后进程在 2 秒内退出，日志与 stats 完整，无残留线程。
[ ] --jsonl 输出的每行都能被 json.loads 解析，字段固定。
[ ] Windows 与 Linux 上各跑通一次基本用例（路径分隔符与事件类型差异不导致失败）。

【七、可选扩展】

1. 增加 --webhook URL，把事件以 JSON POST 到本地服务或企业微信/钉钉机器人（离线可用）。
2. 增加规则 DSL：按扩展名与正则匹配后执行不同动作，避免写多条命令行。
3. 增加 SQLite 事件库（标准库 sqlite3），支持按时间范围与路径查询历史事件。
4. 增加文件指纹（SHA-256）计算并写入日志，用于检测“内容未变的重写”。
5. 增加 --sync-to 结合校验和的增量同步能力，作为轻量级双向同步的触发端。
6. 在 Windows 上注册为系统服务（用 pywin32 或 nssm），在 Linux 上生成 systemd unit 模板。

【八、涉及知识点】

- 文件系统事件机制：inotify、FSEvents、ReadDirectoryChangesW 与轮询的差异。
- watchdog 的 Observer、FileSystemEventHandler、PollingObserver 与事件对象属性。
- 生产者-消费者模型：queue.Queue 解耦事件回调与耗时处理。
- 去抖动（debounce）与稳定检测（settle）两种处理“写一半”的策略及其适用场景。
- fnmatch / PurePath.match 通配符匹配与 glob 的差异。
- subprocess 参数列表执行、超时控制与输出捕获，shell 注入风险。
- 信号处理与多线程优雅退出（stop_event + observer.join）。
- 日志设计：人读文本与 JSON Lines 机读格式的取舍与字段规范。
================================================================================
