================================================================================
项目编号：046                    难度等级：★★★☆☆（小型项目）
项目名称：定时屏幕截图工具
所属分类：桌面小工具 / 系统编程
建议工时：5 ~ 7 小时
运行环境：Python 3.10+    第三方依赖：mss >= 9.0（pip install mss）
                         可选：Pillow（生成缩略图与加水印）、keyboard 或 pynput（全局热键）
================================================================================

【一、项目背景与目标】

远程办公、做教程、写周报的人经常需要一件小事：每隔一段时间自动截一张屏，留下“我这一天都在
干什么”的证据链。手工截图既打断注意力又容易忘记，而市面上的定时截图软件要么带广告，要么
把图片传到云端。本项目做一个纯本地的截图守护进程：按固定间隔自动截图，按日期分目录归档，
超过保留期的旧图自动清理，还可以配置成只截取某个窗口区域、只在检测到画面变化时保存。

除了定时，还需要热键截图：任何时候按下 Ctrl+Alt+S 立刻截一张并保存，不打断当前操作。程序
在系统托盘或后台静默运行，日志记录每次截图的文件路径与耗时，方便排查“为什么少了几张”。

目标用户是远程工作者、在线教学老师、需要记录操作过程的技术支持人员。做成之后可以把它做成
开机自启的小工具，用一周时间自动积累一份完整的工作过程影像档案；程序只在本地写文件，不上传
任何数据，截图目录可以自行加密或同步到私有云。

【二、功能需求清单】

1. 核心功能
   1.1 全屏截图：用 mss 的 mss() 上下文管理器，mon = sct.monitors[1] 取主显示器，
       sct.grab(mon) 得到 BGRA 原始画面，再用 mss.tools.to_png(raw.rgb, raw.size, output=path)
       落盘。多显示器时 --monitor N 选择第 N 块（0 表示全部显示器拼合的大画布）。
   1.2 区域截图：--region x,y,w,h 或 --region-monitor 2 只截取指定区域/指定显示器；
       配置文件中可保存多组命名区域，用 --profile code 调用。
   1.3 定时模式：--interval 300 表示每 300 秒一张；--interval 支持 30s/5m/1h 之类带单位写法；
       使用 time.monotonic() 计算下一次触发时间，避免因单次截图耗时而逐渐漂移。
   1.4 热键模式：--hotkey "ctrl+alt+s" 注册全局热键立即截图；Windows 用 keyboard 或
       win32 API，macOS 用 pynput（需要授予“辅助功能”权限），Linux X11 用 pynput，
       Wayland 下全局热键通常不可用，需在文档中说明限制。
   1.5 变化检测：--only-on-change 计算当前帧与上一帧的差异（Pillow 转灰度后
       ImageChops.difference 求均值），低于 --change-threshold（默认 2.0）时跳过保存，
       避免整夜无人时产生大量重复图。
   1.6 归档规则：--outdir ./shots，目录结构 {outdir}/{YYYY-MM-DD}/{HHMMSS}_mon1.png；
       --thumb 额外生成 320 像素宽的缩略图存到 thumbs 子目录（Pillow thumbnail）。
   1.7 过期清理：--keep-days 7 删除修改时间早于 7 天的截图；--keep-max-mb 2048 时按最旧优先
       删除直到目录总量达标；清理动作必须写日志并支持 --dry-run 预览。
   1.8 运行时控制：--count 100 张后退出；--duration 8h 到达时长后退出；--start-at 09:00
       --stop-at 18:00 只在工作时段截图；Ctrl+C 优雅退出（保存状态、打印统计）。

2. 输入与交互
   2.1 命令行：python snip.py --interval 5m --outdir D:\shots --keep-days 7。
   2.2 配置文件 shots.toml（标准库 tomllib 读取）保存 outdir、interval、region、
       hotkey、keep_days 等默认值，命令行参数优先级高于配置文件。
   2.3 托盘/最小化提示：Windows 下用 ctypes 调用 MessageBoxW 弹一次“已开始截图”提示；
       macOS 用 osascript 发通知；Linux 用 notify-send，任一不可用时降级为控制台输出。
   2.4 --pause-file pause.flag：该文件存在时暂停截图，删除后恢复，方便临时停止。
   2.5 --list-monitors 打印每块显示器的序号、分辨率与是否主屏。

3. 输出与展示
   3.1 每次截图打印一行：14:32:05 已保存 shots/2025-05-06/143205_mon1.png (1920x1080, 268KB,
       0.08s)。
   3.2 退出时汇总：运行 2h13m，截图 27 张，跳过 4 张（画面未变化），清理 12 张（超期），
       合计占用 48.2MB。
   3.3 --log-file shots.log 记录每次截图（含跳过的原因）与清理细节。
   3.4 --status 打印当前配置摘要与目录占用，不启动截图循环。

4. 异常与边界处理
   4.1 无图形界面环境（SSH、无 DISPLAY）：捕获 mss.exception.ScreenShotError 并给出
       “当前环境没有可用显示器”的中文提示，退出码 1，不进入死循环。
   4.2 磁盘空间不足：写文件前用 shutil.disk_usage 检查，低于 --min-free-mb（默认 500）时
       暂停截图并告警，恢复后继续。
   4.3 输出目录不可写：启动时做一次写测试（写一个 .write_test 文件再删除），失败即报错退出。
   4.4 热键被占用或注册失败：打印警告并继续以定时模式运行，不崩溃。
   4.5 时间跨越午夜：日期目录按每次截图的实际本地日期计算，--keep-days 清理时以文件名中的
       日期优先、文件 mtime 兜底。
   4.6 系统休眠/挂起后恢复：检测到两次循环间隔远大于 interval（超过 3 倍）时，跳过补拍并记
       一条日志“疑似系统休眠，已跳过 N 次”。
   4.7 截图文件名冲突（同一秒截两张）：追加 _1、_2。
   4.8 单次截图异常：捕获后记录，连续失败超过 --max-failures（默认 5）次则退出并给出提示。
   4.9 时区/夏令时：一律使用本地时间，文件名不带时区后缀，文档中说明。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：mss（跨平台截图，必须用它而不是 PIL.ImageGrab，因为 mss 更快且支持多屏）；
   Pillow（缩略图、变化检测、可选水印）；标准库 argparse、pathlib、time、datetime、tomllib、
   logging、shutil、signal、ctypes（Windows 提示）、subprocess（macOS/Linux 通知）。
   可选：pynput（全局热键，跨平台但需权限）、keyboard（Windows 更简单）。
3. 禁止事项：禁止上传任何截图数据；禁止使用 pyautogui 等会移动鼠标/键盘的库；禁止在无参
   情况下无限截图而不给任何提示；禁止用 while True + time.sleep 造成时间漂移；禁止吞掉
   KeyboardInterrupt。
4. 代码组织：
   - capture.py：ScreenCapturer 类，封装 mss 实例、显示器枚举、单次截图返回 PIL.Image 与
     原始尺寸。
   - storage.py：build_path(ts, monitor, outdir) -> Path、save_png(image, path)、
     make_thumb(image, path, width)、cleanup(outdir, keep_days, keep_max_mb, dry_run)。
   - scheduler.py：定时循环、工作时段判断、休眠检测、暂停文件检测。
   - hotkey.py：热键注册与回调（按平台选择实现，全部失败时降级并告警）。
   - notify.py：跨平台桌面通知的三种实现与统一接口 notify(title, message)。
   - cli.py：参数、配置合并、信号处理与主循环。
5. 编码规范：类型注解完整；所有时间计算用 time.monotonic()（展示用 datetime.now()）；
   循环内禁止捕获 BaseException；日志格式含时间戳与级别，文件日志与屏幕日志级别可分开设置；
   docstring 说明每个平台的能力差异与所需权限。

【四、设计要点】

1. 数据结构：
   SnipConfig：outdir(Path)、interval(float)、region(tuple[int,int,int,int]|None)、
   monitor(int)、hotkey(str|None)、only_on_change(bool)、change_threshold(float)、
   thumb(bool)、thumb_width(int)、keep_days(int|None)、keep_max_mb(int|None)、
   min_free_mb(int)、start_at(time|None)、stop_at(time|None)、count(int|None)、
   duration(float|None)、max_failures(int)、dry_run(bool)。
   SnipRecord：taken_at(datetime)、path(Path)、width(int)、height(int)、bytes(int)、
   elapsed_ms(float)、saved(bool)、reason(str)。
   RunStats：started_at、shots(int)、skipped(int)、purged(int)、purged_bytes(int)、
   failures(int)、paused_seconds(float)。

2. 关键算法或流程：
   2.1 主循环（防漂移）：next_at = monotonic() + interval；循环内先算出 wait = next_at -
       monotonic()，用 signal.setitimer 或 time.sleep(max(wait, 0))；截图完成后
       next_at += interval；若 monotonic() - next_at > 3 * interval 则判定休眠，重置
       next_at = monotonic() + interval。
   2.2 单次截图流程：检查暂停文件与工作时段 -> 检查磁盘空间 -> 抓屏得到 BGRA -> 用
       frombuffer("RGB", size, raw.rgb) 构造 PIL.Image -> 变化检测 -> 生成目标路径 ->
       to_png 或 image.save -> 生成缩略图 -> 记录 SnipRecord。
   2.3 变化检测：cur_gray = image.convert("L").resize((160, 90))；diff =
       ImageChops.difference(prev_gray, cur_gray)；mean = sum(diff.getdata()) / 面积；
       若 mean < threshold 则跳过。上一帧只在内存保留，避免读取历史文件。
   2.4 清理策略：先按 --keep-days 收集超期文件删除；再按 --keep-max-mb 计算目录总大小，
       按 mtime 从旧到新逐个删除直到低于上限；每次删除都检查路径确实位于 outdir 之内
       （用 Path.resolve().is_relative_to(outdir.resolve())），防止误删。
   2.5 工作时段：把 start_at/stop_at 转成分钟数，若 stop_at < start_at 视为跨午夜区间；
       当前时间不在区间内则 sleep 60 秒后重新判断（不消耗截图次数）。
   2.6 优雅退出：signal.signal(signal.SIGINT, handler) 与 SIGTERM 设置 threading.Event，
       主循环每轮检查该事件，退出前打印 RunStats 并 flush 日志。

3. 接口设计：
   python snip.py [--outdir DIR] [--interval 5m] [--region x,y,w,h] [--monitor N]
     [--hotkey 'ctrl+alt+s'] [--only-on-change] [--change-threshold 2.0]
     [--thumb] [--keep-days 7] [--keep-max-mb 2048] [--min-free-mb 500]
     [--start-at 09:00] [--stop-at 18:00] [--count N] [--duration 8h]
     [--config shots.toml] [--pause-file pause.flag] [--log-file shots.log]
     [--dry-run] [--status] [--list-monitors] [--verbose]
   核心函数：capture_once() -> tuple[Image.Image, int, int]
             cleanup(outdir: Path, keep_days: int|None, keep_max_mb: int|None,
                     dry_run: bool) -> tuple[int, int]

【五、运行方式与示例】

1. 安装依赖：
   pip install "mss>=9.0" Pillow
   pip install pynput        （可选，启用全局热键）

2. 每 5 分钟截一张，保留 7 天，带缩略图：
   python snip.py --interval 5m --outdir D:\shots --keep-days 7 --thumb
   输出：14:32:05 已保存 D:\shots\2025-05-06\143205_mon1.png (1920x1080, 268KB, 0.08s)
         14:37:05 已保存 D:\shots\2025-05-06\143705_mon1.png (1920x1080, 266KB, 0.07s)
         14:42:05 跳过（画面未变化，差异 0.61 < 2.0）

3. 只在工作时间、只在画面变化时截图：
   python snip.py --interval 2m --only-on-change --change-threshold 3.0
     --start-at 09:00 --stop-at 18:00 --count 200

4. 热键随手截：
   python snip.py --hotkey "ctrl+alt+s" --outdir ./shots --log-file shots.log
   输出：已注册全局热键 ctrl+alt+s（Windows 生效）
         14:55:12 已保存 ./shots/2025-05-06/145512_mon1.png (2560x1440, 412KB, 0.09s)

5. 清理预览（不删除）：
   python snip.py --outdir D:\shots --keep-days 3 --dry-run --status
   输出：当前配置：间隔 300s，保留 3 天，目录占用 1.8GB，文件 412 个
         将删除 96 个文件（合计 512.4MB），--dry-run 未执行删除

6. 异常示例：无图形界面
   python snip.py --interval 60
   输出：错误：当前环境没有可用的图形显示器（mss 初始化失败）
         Linux 请确认 DISPLAY/WAYLAND_DISPLAY 已设置，或在图形会话中运行（退出码 1）

【六、验收标准】

[ ] --interval 60 连续运行 10 分钟，实际间隔误差不超过 1 秒（用文件名时间戳校验）。
[ ] 主显示器截图的宽高与系统设置的分辨率完全一致。
[ ] --monitor 0/1/2 在多屏环境下分别截到拼合画布/主屏/副屏，内容正确。
[ ] --region 100,100,800,600 生成的图片尺寸恰为 800x600。
[ ] --only-on-change 在静态桌面（打开一个不动的窗口）下连续 5 次全部跳过。
[ ] 截图输出目录按 YYYY-MM-DD 自动分目录，跨午夜运行时两个日期目录都存在。
[ ] --keep-days 3 执行后 4 天前的文件全部消失，3 天内的一个不少。
[ ] --keep-max-mb 100 执行后目录总大小不超过 100MB（允许最后一个文件略超）。
[ ] --dry-run 的删除预览数量与实际不加 --dry-run 时的删除数量一致。
[ ] Ctrl+C 后进程立即退出（1 秒内），日志包含汇总统计，无残留 .tmp 文件。
[ ] Windows 热键可用，按一次生成一张图；macOS 上未授权辅助功能时给出明确提示而不崩溃。
[ ] --count 5 恰好生成 5 张后自动退出，退出码 0。
[ ] --start-at 09:00 --stop-at 18:00 在 20:00 启动时不产生任何截图，日志显示等待时段。
[ ] 磁盘剩余空间低于 --min-free-mb 时暂停并在日志中给出警告。
[ ] 手动创建 pause.flag 后不再产生新截图，删除后自动恢复。

【七、可选扩展】

1. 增加键盘/鼠标空闲检测（Windows GetLastInputInfo、Linux xprintidle），仅在用户活动时截图。
2. 增加 OCR 或窗口标题记录（Windows GetForegroundWindow + GetWindowText），让截图附带上下文。
3. 生成每日缩略图联系表（contact sheet）与时间轴 HTML 页面，方便回顾。
4. 增加自动上传到本地 NAS 或 WebDAV 的可选模块（默认关闭，需显式配置）。
5. 打包成单文件可执行程序（PyInstaller），支持 --install-autostart 写入开机启动项。

【八、涉及知识点】

- mss 的跨平台截屏原理、monitors 列表语义与 BGRA 原始缓冲区处理。
- PIL.Image.frombuffer / frombytes 与 BGRA 到 RGB 的通道顺序转换。
- Pillow 的 ImageChops.difference、convert("L")、resize 与变化检测阈值调优。
- 定时循环的防漂移设计与 time.monotonic() 相对 time.time() 的优势。
- signal 模块处理 SIGINT/SIGTERM 与 threading.Event 协作优雅退出。
- 跨平台通知与热键的实现差异、权限要求（macOS 辅助功能、Linux Wayland 限制）。
- 文件归档命名规范、保留策略与安全的递归删除（路径前缀校验）。
- 磁盘空间监控与守护进程的常见健壮性设计（失败计数、暂停标志、写测试）。
================================================================================
