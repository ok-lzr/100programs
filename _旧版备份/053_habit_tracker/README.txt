================================================================================
项目编号：053                    难度等级：★★★☆☆（中型项目）
项目名称：习惯打卡追踪器
所属分类：个人数据管理 / 命令行 + 数据统计
建议工时：2 ~ 3 天
运行环境：Python 3.10+    第三方依赖：无（仅标准库，热力图输出 ANSI 颜色块）
================================================================================

【一、项目背景与目标】

习惯类 App 最容易被放弃的原因有两个：一是每天要打开手机点好几下，二是打卡
数据锁在别人的服务器上，换 App 就全部丢失。本项目把打卡压缩成一条命令
`python -m habit check 跑步`，把统计压缩成一条命令 `python -m habit stats`，
数据存在本地 SQLite 文件里，随时可备份、可导出。

目标用户是希望用键盘快速记录习惯的开发者与自律型学习者。典型场景：早上跑完
步在终端敲一行命令完成打卡；月底想看“跑步这个月完成了几次、最长连续多少天、
哪几天漏了”；年底想看一张全年热力图，直观看到断档出现在哪段时间。

项目的真正难点是“连续天数（streak）”的定义与边界：一周只要求 3 次的目标该怎么
算连续？目标是每天，昨天没打卡但今天补卡算不算连续？跨月、跨年、补卡、时区
与夏令时如何处理？本说明书把这些口径全部写死，避免实现时含糊。

【二、功能需求清单】

1. 核心功能
   1.1 习惯管理（habit add/list/edit/archive）：创建习惯时指定名称、频率
       （daily / weekly:N / custom:1,3,5，即每周指定星期几）、目标次数、
       起始日期、颜色标签、备注。
   1.2 打卡（check）：`habit check 跑步` 记为今天；`--date 2024-05-01` 补卡；
       `--count 2` 支持同一天多次计数型习惯（如喝水 8 杯）。
   1.3 撤销打卡（uncheck）：删除指定日期（或指定次数）的打卡记录，
       删除不存在的记录时给出提示且不报错。
   1.4 备注打卡（check -n "跑了 5 公里"）：同一次打卡可附文字备注与数值
       （--value 5.0，用于里程、页数等可量化习惯）。
   1.5 连续天数（streak）：计算当前连续天数与历史最长连续天数，口径见第四部分。
   1.6 完成率（rate）：按周期计算完成率，支持 week / month / year 三个粒度，
       输出目标次数、实际次数、完成率、达标与否。
   1.7 热力图（heatmap）：按 GitHub 贡献图风格打印一整年（或指定区间）的
       星期 × 周 网格，用不同 ANSI 背景色表示打卡强度等级。
   1.8 统计报表（stats）：单习惯详情与全部习惯总览，含近 7 天/30 天完成率、
       当前连续、最长连续、总打卡次数、首次打卡日期。
   1.9 导出（export）：导出 JSON（完整备份，可再导入）与 CSV（打卡流水，
       便于在 Excel 中透视）。

2. 输入与交互
   2.1 命令形如 `python -m habit check 跑步 -d today -n "5 公里" --value 5`。
   2.2 习惯名支持前缀唯一匹配：若只有一个习惯以“跑”开头，`check 跑` 即可；
       存在多个匹配时列出候选并要求输入完整名称。
   2.3 无参数运行进入交互模式，显示今日待打卡习惯与快捷编号，输入编号即可打卡。
   2.4 `--db PATH` 指定数据库文件，默认 `~/.habit_tracker/habits.db`。
   2.5 支持 `--json` 全局开关，把命令结果以 JSON 输出到 stdout，便于脚本集成。

3. 输出与展示
   3.1 打卡成功后输出：习惯名、日期、当前连续天数、本期进度（如 3/5）。
   3.2 stats 总览输出对齐表格：习惯、频率、本期、目标、完成率、当前连续、
       最长连续、近 30 天完成率。
   3.3 热力图使用 ANSI 背景色分级：无记录为暗灰，1 次为浅绿，2 次为中绿，
       3 次及以上为深绿；不支持颜色的终端自动降级为字符分级（. : + #）。
   3.4 所有日期以 ISO 格式（YYYY-MM-DD）展示，星期用中文简称（一~日）。

4. 异常与边界处理
   4.1 重复打卡同一天（daily 习惯）：默认视为幂等，提示“今日已打卡，未重复记录”，
       退出码 0；加 --force 则累加次数。
   4.2 补卡日期早于习惯起始日期：拒绝并提示起始日期。
   4.3 补卡日期在未来：拒绝，提示“不能为未来日期打卡”。
   4.4 补卡日期早于 7 天前：允许，但输出二次确认提示（--yes 跳过），
       防止误操作把历史连续天数改乱。
   4.5 习惯已归档：check 报错提示“习惯已归档，请先 enable”。
   4.6 streak 计算遇到“每周 3 次”这类非每日频率：按周期达标口径计算（见第四部分）。
   4.7 数据库不存在：首次运行自动初始化；数据库文件损坏（SQLite 报
       DatabaseError）时输出备份建议与退出码 3，不静默重建。
   4.8 空数据习惯：stats 正常输出零值，不抛异常，treak 显示 0。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库——sqlite3、argparse、datetime、calendar、
   dataclasses、enum、json、csv、pathlib、logging、statistics、typing、
   unicodedata、shutil（备份）。禁止引入任何图形或 Web 依赖。
3. 禁止事项：禁止用字符串拼接 SQL；禁止用本地时区的 datetime.now() 直接取
   “今天”而不封装（必须经 `today_local()` 单一出口，便于测试注入假日期）；
   禁止把统计逻辑写在 CLI 层。
4. 代码组织：
   - `db.py`：建表、迁移、连接工厂、事务上下文管理器。
   - `models.py`：Habit、CheckIn、StreakResult、RateResult 等 dataclass。
   - `repository.py`：SQL 集中管理。
   - `streak.py`：连续天数算法（本项目核心，必须有独立单元测试）。
   - `stats.py`：完成率、周期统计。
   - `heatmap.py`：网格渲染与 ANSI 降级。
   - `cli.py`：参数解析与命令分发。
5. 编码规范：所有函数带类型注解与 docstring，公开算法函数必须写明口径；
   日期参数统一在 CLI 层解析为 `datetime.date`；用 logging 记录写操作。

【四、设计要点】

1. 数据结构（SQLite 表结构）

   1.1 habits（习惯定义表）
       id           INTEGER PRIMARY KEY AUTOINCREMENT
       name         TEXT NOT NULL UNIQUE
       freq_type    TEXT NOT NULL     -- 'daily' | 'weekly' | 'weekdays'
       freq_config  TEXT NOT NULL DEFAULT '{}'
                    -- daily 时 '{}'；
                    -- weekly 时 '{"times":3}' 表示每周 3 次；
                    -- weekdays 时 '{"days":[1,3,5]}' 表示每周一三五
       target_count INTEGER NOT NULL DEFAULT 1   -- 单日目标次数（饮水 8 杯则填 8）
       unit         TEXT NOT NULL DEFAULT '次'
       start_date   TEXT NOT NULL    -- 'YYYY-MM-DD'
       color        TEXT NOT NULL DEFAULT 'green'
       note         TEXT NOT NULL DEFAULT ''
       archived     INTEGER NOT NULL DEFAULT 0
       created_at   TEXT NOT NULL
       索引：idx_habits_archived(archived, name)

   1.2 checkins（打卡记录表）
       id           INTEGER PRIMARY KEY AUTOINCREMENT
       habit_id     INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE
       check_date   TEXT NOT NULL    -- 'YYYY-MM-DD'
       count        INTEGER NOT NULL DEFAULT 1 CHECK (count > 0)
       value        REAL NULL        -- 可量化数值：里程、页数、分钟
       note         TEXT NOT NULL DEFAULT ''
       created_at   TEXT NOT NULL
       约束：UNIQUE(habit_id, check_date)   -- 一天一条，多次打卡累加 count
       索引：idx_check_habit_date(habit_id, check_date)、idx_check_date(check_date)

   1.3 habit_log（操作日志表，用于审计与撤销）
       id           INTEGER PRIMARY KEY AUTOINCREMENT
       habit_id     INTEGER NOT NULL
       action       TEXT NOT NULL    -- check / uncheck / edit / archive
       payload      TEXT NOT NULL    -- JSON 快照
       created_at   TEXT NOT NULL

   1.4 schema_version（迁移版本表）
       version      INTEGER PRIMARY KEY
       applied_at   TEXT NOT NULL

2. 关键算法或流程（连续天数口径，必须严格按此实现）

   2.1 daily（每天）口径：
       当前连续 = 从今天向前逐日检查，若今天已打卡则计入并从昨天继续；
       若今天未打卡但昨天已打卡，则允许“今天尚未打卡”的宽限，从昨天起算
       （即今天不影响已获得的连续）；若昨天与今天都未打卡，当前连续为 0。
       历史最长连续 = 对全部已打卡日期升序排列，连续相邻差为 1 天的片段长度
       的最大值。

   2.2 weekdays（每周固定几天）口径：
       只统计 freq_config.days 中的星期；非目标星期直接跳过，不计入分母。
       当前连续 = 从最近一个目标星期向前，每个目标星期都有打卡才算连续；
       允许当前周期尚未结束（如目标是周三，今天周二）时从上一个目标星期起算。

   2.3 weekly:N（每周 N 次）口径：
       以自然周（周一为起点，calendar.MONDAY）为单位。某周达标定义为
       该周打卡天数 ≥ N。
       当前连续周 = 从本周向前，本周若已达标则计入；若本周未达标但未结束，
       则从上周开始计数（不打断）；一旦出现“已结束且未达标”的周，连续终止。
       对外展示时同时给出“连续周数”和换算的“连续天数”
       （连续天数 = 连续周数 × 7 + 当前周已打卡天数）。

   2.4 完成率口径：
       period=week：分母为目标次数（daily=7，weekdays=len(days)，
       weekly=times），分子为区间内打卡天数（同一天多次只算一天）。
       period=month：分母按该月自然周与频率类型折算，不足整周的按比例取整。
       period=year：分母 = 12 个月分母之和。
       完成率 = min(实际 / 目标, 1.0)，展示为百分比保留一位小数；
       目标为 0 时输出 N/A 以避免除零。

   2.5 热力图渲染：
       步骤一，取区间（默认最近 365 天），对齐到周日为一行的起点；
       步骤二，把区间按周切分为列，每列 7 行（周一~周日）；
       步骤三，每天强度 = count / target_count，映射到 5 个等级；
       步骤四，按 ANSI 256 色背景输出，每格用两个空格宽度保证接近正方形；
       步骤五，输出底部月份标签行与图例行。

3. 接口或命令设计

   habit add NAME --freq daily|weekly:N|weekdays:1,3,5 --target 1
         --unit 次 --start 2024-01-01 --color green --note "晨跑"
   habit list [--all] [--json]
   habit edit NAME [--freq ...] [--target N] [--unit ...] [--note ...]
   habit archive NAME / habit unarchive NAME / habit remove NAME --yes
   check NAME [-d/--date today|yesterday|YYYY-MM-DD] [--count N] [--value F]
         [-n/--note TEXT] [--force] [--yes]
   uncheck NAME [-d DATE] [--all]
   stats [NAME] [--period week|month|year] [--from D] [--to D] [--json]
   streak NAME [--json]
   heatmap [NAME] [--year 2024] [--from D --to D] [--no-color] [--legend]
   export --format json|csv -o PATH [--habit NAME] [--from D] [--to D]
   import PATH   （仅支持本项目 export 产生的 JSON，做合并去重）

   函数签名：
   def current_streak(check_dates: set[date], habit: Habit, today: date) -> int
   def longest_streak(check_dates: set[date], habit: Habit) -> int
   def completion_rate(check_dates: set[date], habit: Habit,
                       start: date, end: date) -> RateResult
   def render_heatmap(days: dict[date, int], start: date, end: date,
                      color: bool) -> str

【五、运行方式与示例】

安装（无第三方依赖）：
  cd C:\projects\100programs\053_habit_tracker
  python -m habit init

示例一（创建习惯并打卡）：
  输入：python -m habit habit add 跑步 --freq daily --unit 公里 --start 2024-05-01
  输出：已创建习惯 #1 跑步（每天，起始 2024-05-01）
  输入：python -m habit check 跑步 -n "晨跑 5 公里" --value 5
  输出：打卡成功  跑步  2024-05-03(五)  当前连续 1 天  本期 1/1
  输入：python -m habit check 跑步
  输出：今日已打卡，未重复记录（如需累加请加 --force）

示例二（每周三次习惯的统计）：
  输入：python -m habit habit add 健身 --freq weekly:3 --start 2024-05-01
  输入：python -m habit check 健身 -d 2024-05-06
  输入：python -m habit check 健身 -d 2024-05-08
  输入：python -m habit check 健身 -d 2024-05-10
  输入：python -m habit stats 健身 --period week
  输出：
        习惯：健身（每周 3 次）  区间：2024-05-06 ~ 2024-05-12
        目标 3 次，实际 3 次，完成率 100.0%，本周已达标
        当前连续：1 周（折合 7 天）  历史最长：1 周

示例三（热力图与异常输入）：
  输入：python -m habit heatmap 跑步 --year 2024 --legend
  输出：按周排列的 53 列 × 7 行色块网格，底部为 1 月~12 月标签与强度图例。
  输入：python -m habit check 跑步 -d 2030-01-01
  输出：错误：不能为未来日期打卡（今天为 2024-05-03）      （退出码 2）
  输入：python -m habit check 游
  输出：错误：未找到习惯 “游”；是否想输入 “游泳”？        （退出码 2）
  输入：python -m habit habit add 跑步
  输出：错误：习惯 “跑步” 已存在                            （退出码 2）

【六、验收标准】

[ ] `habit init` 可重复执行，不重复建表、不清空数据。
[ ] 同一天对 daily 习惯重复 check 不新增行，加 --force 后 count 累加为 2。
[ ] checkins 表的 UNIQUE(habit_id, check_date) 约束在直接 INSERT 时同样生效。
[ ] 连续 3 天打卡后 current_streak 返回 3；跳过一天后返回 0（昨天也未打卡）。
[ ] 今天未打卡但昨天打卡时，current_streak 仍返回昨天的连续值（宽限口径）。
[ ] weekdays 习惯在非目标星期打卡不计入连续，且在 stats 中给出提示。
[ ] weekly:3 习惯在连续两周达标时 streak 为 2 周，出现一个空周后归零。
[ ] longest_streak 在“中间断档”的数据上取到正确片段（含首尾片段比较）。
[ ] 完成率在目标为 0 时输出 N/A，不出现 ZeroDivisionError。
[ ] 跨月、跨年区间（如 2023-12-20 ~ 2024-01-10）的统计结果与手工计算一致。
[ ] 热力图在 80 列终端下不换行错乱，在 --no-color 下输出可读的字符分级。
[ ] 补卡未来日期被拒绝，补卡 7 天前触发确认，加 --yes 后成功。
[ ] export json 后再 import 到空库，全部习惯与打卡记录可完整还原。
[ ] streak.py 的单元测试覆盖 daily / weekdays / weekly 三类口径，pytest 全绿。
[ ] 所有命令在 --json 下输出合法 JSON（用 json.loads 解析不报错）。

【七、可选扩展】

1. 增加习惯提醒：结合 schedule 或系统计划任务，在未打卡时弹桌面通知。
2. 增加习惯间的相关性分析（如“跑步的次日早睡完成率更高”）。
3. 增加周报邮件：把本周完成率与热力图以文本表格发送到邮箱。
4. 增加 CSV 批量补卡（支持从其他 App 导出的记录迁移）。
5. 增加“习惯模板”一键创建一组常见习惯（早起、阅读、锻炼、喝水）。
6. 增加同步到 051 记账本的能力（如“咖啡”习惯自动记一笔支出）作为综合练习。

【八、涉及知识点】

- sqlite3：唯一约束、ON DELETE CASCADE、事务上下文管理、索引与查询计划。
- datetime 与 calendar：date 与 timedelta 运算、isocalendar、weekday、
  monthrange、跨月跨年边界。
- 集合与排序算法：打卡日期集合、连续片段扫描、最长片段统计。
- 频率模型设计：把“每天/每周几天/每周 N 次”抽象为统一数据模型。
- 终端渲染：ANSI 转义序列、256 色、Unicode 宽度、无颜色降级。
- CLI 设计：子命令、前缀匹配、交互模式、--json 机器可读输出。
- 单元测试：用固定“今天”注入方式让时间相关逻辑可测。
- JSON/CSV 导入导出与幂等合并去重。
- 日志与审计：操作日志表与可回溯的撤销设计。
================================================================================
