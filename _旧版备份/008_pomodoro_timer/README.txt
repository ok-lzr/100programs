================================================================================
项目编号：008                    难度等级：★☆☆☆☆（小型项目）
项目名称：番茄钟计时器
所属分类：命令行工具 / 时间管理与系统提醒
建议工时：5 ~ 7 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

番茄工作法的关键是“到点必须停”，但手机上计时很容易被消息打断，浏览器标签页也不会
真的提醒你休息。这个纯命令行番茄钟跑在终端里，专注 25 分钟、休息 5 分钟自动循环，
到点时用终端响铃加桌面通知告知，并把每天完成的番茄数与专注时长记录到本地文件。

目标用户是长时间在终端里工作的开发者、需要被强制打断的学生、以及想统计自己真实专注
时长的自由职业者。设计重点有两个：一是计时精度不能靠 sleep 累加漂移，必须用
time.monotonic() 校准；二是必须能优雅处理 Ctrl+C，中途退出也要把已完成的番茄记账。

做完之后应当能拿来干这些事：输入 pomodoro 开始标准的 25/5 循环；用 --rounds 4 做完
四轮后自动进入长休息 15 分钟；用 --stats 查看本周每天完成了几个番茄、总共专注多少分钟。

【二、功能需求清单】

1. 核心功能
   1.1 标准循环：专注 25 分钟 + 短休息 5 分钟为一轮，默认做完 4 轮后进入长休息 15 分钟。
   1.2 参数化时长：--focus 25 --short 5 --long 15 --rounds 4，单位均为分钟，
       允许小数（如 --focus 0.1 用于测试）。
   1.3 倒计时显示：终端同一行刷新剩余时间，格式 25:00 → 24:59 …… 00:00，
       并显示当前阶段与轮次，例如 “[专注 1/4] 剩余 24:35”。
   1.4 自动循环：专注结束自动进入休息并提示，休息结束自动开始下一个专注；
       --no-auto 时每阶段结束需按回车继续。
   1.5 桌面提醒：到点时输出响铃字符 \a 并打印大字提示；Windows 下额外尝试用
       winsound.Beep 播放提示音（失败时静默降级）。
   1.6 统计记录：每完成一个专注阶段，把记录追加写入 ~/.pomodoro/history.jsonl，
       每行一个 JSON，包含日期、开始时间、结束时间、时长分钟、是否完成。
   1.7 统计查询：--stats 输出今日、近 7 天、累计的番茄数与专注分钟数，以及最专注的一天。
   1.8 中断处理：Ctrl+C 时打印 “已中断，本轮专注未完成”，退出码 0，并且不记为完成。

2. 输入与交互
   2.1 启动：python pomodoro.py 或 python pomodoro.py --focus 50 --short 10。
   2.2 运行中按键：s 跳过当前阶段、p 暂停与继续、q 退出、回车无操作。
       Linux/macOS 用 termios 读取单键；Windows 用 msvcrt.kbhit/getch；
       两者都不可用时降级为每阶段结束才响应。
   2.3 --task 写一段任务名，记录进统计文件，例如 --task "写周报"。
   2.4 --stats 查看统计；--stats --days 30 查看最近 30 天。
   2.5 --clear-stats 清空历史（执行前必须二次确认输入 yes）。
   2.6 --quiet 静默模式不响铃，只打印文字提示。
   2.7 --json 让 --stats 输出 JSON 格式。

3. 输出与展示
   3.1 阶段切换横幅：
       ==========================================
         专注开始（第 1/4 轮）  时长 25 分钟
         任务：写周报
       ==========================================
   3.2 倒计时行每秒刷新一次，不产生滚动刷屏。
   3.3 阶段结束提示：
       *** 专注结束，休息 5 分钟，起来活动一下 ***
   3.4 全部完成提示：已完成 4 个番茄，累计专注 100 分钟，干得漂亮。
   3.5 --stats 输出：
       今日：3 个番茄，75 分钟
       近 7 天：14 个番茄，350 分钟
       累计：126 个番茄，3150 分钟
       最专注的一天：2024-05-11（6 个番茄）
   3.6 涉及的所有时间戳输出使用本地时间，ISO 8601 格式。

4. 异常与边界处理
   4.1 --focus 小于等于 0 或大于 180 时打印 “错误：专注时长需在 0.1 ~ 180 分钟之间”。
   4.2 --rounds 小于 1 或大于 20 时报错。
   4.3 历史文件不存在时 --stats 输出全 0 而不是报错。
   4.4 历史文件某行 JSON 损坏时跳过该行，继续统计，并在 --verbose 下打印跳过的行号。
   4.5 历史文件无法写入（权限不足）时打印警告并继续计时，不中断番茄钟。
   4.6 暂停状态不计入专注时长；暂停超过 60 分钟自动结束本轮并记为未完成。
   4.7 系统时钟被向后调整不影响倒计时（使用 time.monotonic()）。
   4.8 终端不支持 ANSI 光标控制时（如重定向到文件）改用每 60 秒打印一行的降级模式。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库，需要 argparse、time、json、datetime、pathlib、
   os、sys、threading（或 select）、logging、platform。
   平台相关模块按需导入：Windows 用 msvcrt、winsound；POSIX 用 termios、tty、select。
3. 禁止事项：禁止用 time.sleep(1) 循环累加来计时（会产生漂移），必须用
   end_time = time.monotonic() + duration 与剩余时间计算；禁止在计时循环里频繁写
   磁盘（只在阶段结束时写一次）；禁止把历史文件放在项目目录里（必须放用户主目录）。
4. 代码组织：
   4.1 阶段模型：Phase 枚举（FOCUS、SHORT_BREAK、LONG_BREAK）、
       SessionConfig dataclass（focus_min、short_min、long_min、rounds、task）。
   4.2 计时核心：run_phase(phase, minutes, allow_keys) -> PhaseOutcome，
       内部按 0.2 秒粒度检查剩余时间与按键状态。
   4.3 历史存储：HistoryStore 类，方法 append(record)、load(days=None)、clear()、
       summarize(days) -> StatsSummary。
   4.4 键盘处理：get_key_nonblocking() -> str | None，按平台分派实现，
       找不到实现时返回 None。
   4.5 通知：notify(title, message) 打印横幅并按平台尝试响铃；--quiet 时跳过响铃。
   4.6 main() 分派计时模式与统计模式。
5. 编码规范：类型注解与 docstring；时间计算相关的变量名带单位后缀（_seconds、
   _minutes）；平台差异集中在单独函数中，禁止在业务逻辑里写 if platform.system()。

【四、设计要点】

1. 数据结构：
   1.1 SessionRecord：dataclass，字段 date: str（YYYY-MM-DD）、start: str（ISO）、
       end: str、minutes: float、phase: str、task: str、completed: bool。
   1.2 StatsSummary：dataclass，字段 today_count、today_minutes、week_count、
       week_minutes、total_count、total_minutes、best_day、best_day_count。
   1.3 历史文件位于 Path.home() / ".pomodoro" / "history.jsonl"，采用 JSON Lines，
       追加写入，天然容忍并发与损坏行。
2. 关键算法或流程：
   2.1 计时流程：deadline = time.monotonic() + minutes × 60；循环中
       remaining = deadline - time.monotonic()；每隔 1 秒重绘一行；
       remaining <= 0 时退出循环并返回完成结果。
   2.2 暂停：记录 pause_started，恢复时 deadline += 恢复时刻 - pause_started，
       保证暂停不消耗专注时间。
   2.3 轮次编排：for round in 1..rounds: 专注 -> 若 round == rounds 则长休息
       否则短休息；--no-auto 时在每个阶段后等待回车。
   2.4 统计流程：按行读取 JSONL -> 损坏行计数跳过 -> 过滤 completed 为真的记录
       -> 按 date 聚合 -> 计算 today/week/total 与 best_day。
   2.5 显示降级：用 sys.stdout.isatty() 判断是否支持原地刷新；不支持时改为每 60 秒
       打印一行进度。
3. 接口或命令设计：
   3.1 run_phase(phase: Phase, minutes: float, allow_keys: bool) -> PhaseOutcome
   3.2 HistoryStore.append(record: SessionRecord) -> None
   3.3 HistoryStore.summarize(days: int = 7) -> StatsSummary
   3.4 notify(title: str, message: str, quiet: bool = False) -> None
   3.5 命令行：--focus、--short、--long、--rounds、--task、--no-auto、--quiet、
       --stats、--days、--json、--clear-stats、--verbose。

【五、运行方式与示例】

1. 运行准备：无需安装依赖；Windows 提示音依赖内置 winsound，缺失时自动静默降级。
2. 标准番茄钟：
   python pomodoro.py
   输出（每秒原地刷新）：
   ==========================================
     专注开始（第 1/4 轮）  时长 25 分钟
   ==========================================
   [专注 1/4] 剩余 24:35
   到点后：
   *** 专注结束，休息 5 分钟，起来活动一下 ***
3. 自定义时长并指定任务：
   python pomodoro.py --focus 50 --short 10 --long 20 --rounds 2 --task "重构模块"
   输出：专注 50 分钟与休息 10 分钟交替两轮，第二轮后长休息 20 分钟。
4. 快速自测（把专注设成 6 秒）：
   python pomodoro.py --focus 0.1 --short 0.05 --rounds 1
   输出：6 秒后提示专注结束，3 秒后提示休息结束，最后打印完成统计。
5. 查看统计：
   python pomodoro.py --stats --days 30
   输出：
   今日：3 个番茄，75 分钟
   近 7 天：14 个番茄，350 分钟
   累计：126 个番茄，3150 分钟
   最专注的一天：2024-05-11（6 个番茄）
6. 静默模式（会议中不想响铃）：
   python pomodoro.py --quiet --focus 0.1 --rounds 1
   输出：仅有文字提示，无响铃字符。
7. 异常输入示例：
   python pomodoro.py --focus 0
   输出：错误：专注时长需在 0.1 ~ 180 分钟之间
   退出码：2
   python pomodoro.py --rounds 50
   输出：错误：轮次需在 1 ~ 20 之间
   退出码：2
8. 首次运行无历史时的统计：
   python pomodoro.py --stats
   输出：今日：0 个番茄，0 分钟 …… 不报错。

【六、验收标准】

[ ] 默认配置为专注 25 分钟、短休息 5 分钟、长休息 15 分钟、4 轮
[ ] 倒计时在同一行原地刷新，不产生大量滚动输出
[ ] 倒计时基于 time.monotonic()，把系统时间前调 1 小时不影响剩余时间
[ ] --focus 0.1 约 6 秒后结束，误差小于 0.5 秒
[ ] 第 4 轮结束后进入长休息而不是短休息
[ ] Ctrl+C 中断时打印提示并返回退出码 0，历史文件中不产生完成记录
[ ] 暂停期间倒计时不减少，恢复后剩余时间与暂停前一致
[ ] 每个完成的专注阶段在 history.jsonl 中追加一行 JSON
[ ] --stats 正确聚合今日、7 天、累计三个口径
[ ] 历史文件含损坏行时统计仍能完成并跳过该行
[ ] 历史文件不存在时 --stats 输出全 0
[ ] --quiet 时不输出响铃字符
[ ] 输出被重定向到文件时自动降级为逐分钟打印
[ ] --clear-stats 需要输入 yes 确认后才执行
[ ] 全程仅使用标准库

【七、可选扩展】

1. 增加 --long-every N 自定义每几轮进入长休息。
2. 增加干扰记录：按键 d 记录一次走神，统计里输出“专注被中断次数”。
3. 增加 --report week 生成一周专注时长字符柱状图。
4. 增加 Windows 托盘气泡或 macOS osascript 通知（仍不引入第三方库）。
5. 增加与 todo 清单联动：从 009 项目的 JSON 文件里挑一个待办作为本轮任务。

【八、涉及知识点】

- time.monotonic() 与 time.time() 的区别
- 单调时钟避免计时漂移的原理
- 终端 ANSI 转义序列实现原地刷新（\r、清行）
- 跨平台键盘输入：msvcrt 与 termios 的差异
- 信号与 KeyboardInterrupt 的捕获与清理
- JSON Lines 格式与追加写入
- pathlib 与用户主目录路径构造
- dataclass 与 Enum 组织会话配置与阶段
- 命令行程序的优雅降级设计
================================================================================
