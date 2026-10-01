================================================================================
项目编号：054                    难度等级：★★★☆☆（中型项目）
项目名称：学习计划与复习调度器
所属分类：个人数据管理 / 学习工具
建议工时：3 ~ 4 天
运行环境：Python 3.10+    第三方依赖：无（仅标准库；可选 rich 用于美化输出）
================================================================================

【一、项目背景与目标】

背单词、背概念、记法规，最常见的问题是“背完就忘”。艾宾浩斯遗忘曲线告诉我们，
新学内容在 20 分钟、1 小时、9 小时、1 天、2 天、6 天、31 天这些时间点复习，
记忆保持率最高。手动排复习计划几乎不可行：内容一多，哪条今天该复习就算不清了。

本项目把“学习内容 → 复习任务 → 掌握度追踪”做成一个本地调度器。用户录入要学
的知识点（单词、公式、概念、错题），程序自动在遗忘曲线的节点生成复习任务；
用户每天运行 `python -m planner today` 就能看到今天必须复习哪些内容，逐条标记
“记住了 / 模糊 / 忘了”，程序据此调整该内容的复习阶段与下次复习日期。

目标用户是备考学生、语言学习者和需要长期记忆专业知识的从业者。项目难点在于
调度算法：如何根据作答质量动态调整间隔（类似 SM-2 算法）、如何处理积压任务、
如何定义“掌握度”并在报表中体现。

【二、功能需求清单】

1. 核心功能
   1.1 内容管理（item add/list/edit/remove）：录入学习内容，字段包含标题、
       正文/答案、所属科目、标签、难度、初始阶段；支持批量导入 CSV。
   1.2 自动排程（schedule）：内容创建时按遗忘曲线生成首个复习计划；
       默认间隔序列为 [0, 1, 2, 4, 7, 15, 30, 60, 120] 天，可配置。
   1.3 每日任务（today / due）：列出今天到期与逾期未复习的内容，
       按“逾期天数降序 + 难度升序”排序；支持 --limit 与 --subject 过滤。
   1.4 复习作答（review）：对内容标记 quality（0=忘了 / 1=模糊 / 2=勉强 / 3=记住了
       / 4=很轻松），程序更新阶段、下次复习日期与掌握度。
   1.5 掌握度追踪（mastery）：掌握度 = 加权得分，随质量与阶段增长、随“忘了”
       回落；输出 0~100 的数值与掌握等级（陌生/初识/熟悉/牢固）。
   1.6 学习计划（plan）：按截止日期与每日可用时长反推每天需要新学多少条、
       复习多少条，输出日程表（含每日预计用时）。
   1.7 统计报表（stats）：今日/本周/本月复习量、平均质量、按时复习率、
       逾期率、各科目掌握度分布、阶段分布直方图。
   1.8 导出（export）：导出复习记录 CSV（可做遗忘曲线拟合）与 JSON 全量备份。

2. 输入与交互
   2.1 命令形如：
       `python -m planner item add -t "photosynthesis" -a "光合作用" -s 生物 -d 2`
       `python -m planner review 12 -q 3 --time 25`
   2.2 交互复习模式（`review --interactive`）：逐条显示题目，先让用户按回车看答案，
       再输入 0~4 评价，避免一次性看到答案影响自测。
   2.3 today 支持 `--count-only` 只输出待复习数量，便于放入 shell 提示符。
   2.4 支持 `--db PATH`、`--json` 全局参数；`--today 2024-05-03` 可覆盖“今天”
       用于测试与补做计划。
   2.5 时间输入支持 `--minutes 30` 声明今天可用时长，plan 据此调整推荐量。

3. 输出与展示
   3.1 today 输出格式：编号、科目、标题、阶段、逾期天数、上次质量、下次日期。
   3.2 复习完成后输出该内容的阶段变化与新增/推迟的下次复习日期，
       例如 `阶段 3 → 4，下次复习 2024-05-10（+7 天）`。
   3.3 stats 输出文字条形图表示阶段分布（用 # 号数量表示计数）。
   3.4 掌握度以百分比加等级显示，如 `掌握度 72%（熟悉）`。

4. 异常与边界处理
   4.1 quality 超出 0~4：报错并列出合法取值。
   4.2 已到最终阶段仍标记“很轻松”：下次复习间隔按序列上限延长一档或封顶，
       在说明中明确“封顶为 365 天，不无限增长”。
   4.3 标记“忘了”（q=0）：阶段回退到 0 或 1（可配置 reset_to），
       下次复习日期设为明天，掌握度按公式下调。
   4.4 同一天重复复习同一内容：允许，但记录多条 review_log，
       调度只以最后一条为准，并在报表中提示“今日重复复习 N 条”。
   4.5 补做逾期任务：逾期不影响阶段，仅记录 overdue_days 用于统计。
   4.6 空题库运行 today：输出“今日无待复习内容”，退出码 0。
   4.7 删除内容：级联删除其复习记录，删除前显示记录条数并要求确认。
   4.8 时间字段异常（如 Excel 导出的 2024/5/3 格式）：统一解析并归一化为 ISO。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：
   2.1 标准库：sqlite3、argparse、datetime、json、csv、pathlib、math、random
       （用于同一批任务内的轻微打散）、dataclasses、enum、logging、statistics。
   2.2 可选第三方：rich（仅用于交互复习时的着色与进度条，缺失时自动降级为纯文本）。
   2.3 禁止引入任何在线服务依赖；本项目离线可用。
3. 禁止事项：禁止把调度间隔硬编码在函数内部（必须来自配置且有默认值）；
   禁止直接修改 review_log 历史记录（只能追加，保证可回溯）；禁止用
   `datetime.now()` 散落在多处（统一 `today()` 出口）。
4. 代码组织：
   - `db.py`：建表、迁移、连接与事务。
   - `models.py`：Item、ReviewLog、Schedule、Mastery dataclass 与枚举 Quality。
   - `repository.py`：SQL 层。
   - `scheduler.py`：间隔计算、下次复习日期、阶段推进与回退（核心）。
   - `mastery.py`：掌握度公式与等级映射。
   - `planner.py`：学习计划反推与日程生成。
   - `stats.py`：统计聚合。
   - `cli.py`：命令行入口与交互复习。
5. 编码规范：调度与掌握度公式必须有 docstring 写明公式与参数含义；
   Random 使用固定种子以便测试；所有日期以 date 对象在内部流转，仅在
   存储与展示时转字符串。

【四、设计要点】

1. 数据结构（SQLite 表结构）

   1.1 subjects（科目表，可选但建议）
       id           INTEGER PRIMARY KEY AUTOINCREMENT
       name         TEXT NOT NULL UNIQUE
       daily_minutes INTEGER NOT NULL DEFAULT 30   -- 每日计划投入分钟

   1.2 items（学习内容表）
       id           INTEGER PRIMARY KEY AUTOINCREMENT
       title        TEXT NOT NULL           -- 题面/单词/概念名
       answer       TEXT NOT NULL DEFAULT ''-- 答案/释义/正文
       subject_id   INTEGER NULL REFERENCES subjects(id) ON DELETE SET NULL
       tags         TEXT NOT NULL DEFAULT ''-- 逗号分隔，如 “考研,高频”
       difficulty   INTEGER NOT NULL DEFAULT 2 CHECK (difficulty BETWEEN 1 AND 5)
       stage        INTEGER NOT NULL DEFAULT 0   -- 当前复习阶段索引
       mastery      REAL NOT NULL DEFAULT 0.0    -- 0~100
       ease_factor  REAL NOT NULL DEFAULT 2.5    -- SM-2 难度因子，下限 1.3
       interval_days INTEGER NOT NULL DEFAULT 0  -- 当前阶段间隔
       due_date     TEXT NOT NULL           -- 'YYYY-MM-DD' 下次复习日期
       last_review  TEXT NULL               -- 最近一次复习日期
       review_count INTEGER NOT NULL DEFAULT 0
       lapse_count  INTEGER NOT NULL DEFAULT 0   -- “忘了”的次数
       created_at   TEXT NOT NULL
       archived     INTEGER NOT NULL DEFAULT 0
       约束：CHECK (mastery BETWEEN 0 AND 100)
       索引：idx_items_due(due_date, archived)、idx_items_subject(subject_id)、
             idx_items_stage(stage)

   1.3 review_log（复习记录表，只追加）
       id           INTEGER PRIMARY KEY AUTOINCREMENT
       item_id      INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE
       reviewed_on  TEXT NOT NULL      -- 'YYYY-MM-DD'
       quality      INTEGER NOT NULL CHECK (quality BETWEEN 0 AND 4)
       stage_before INTEGER NOT NULL
       stage_after  INTEGER NOT NULL
       interval_before INTEGER NOT NULL
       interval_after  INTEGER NOT NULL
       overdue_days INTEGER NOT NULL DEFAULT 0
       elapsed_ms   INTEGER NULL       -- 作答耗时（交互模式记录）
       created_at   TEXT NOT NULL
       索引：idx_log_item(item_id, reviewed_on)、idx_log_date(reviewed_on)

   1.4 plans（学习计划表）
       id           INTEGER PRIMARY KEY AUTOINCREMENT
       subject_id   INTEGER NULL REFERENCES subjects(id) ON DELETE CASCADE
       deadline     TEXT NOT NULL      -- 'YYYY-MM-DD'
       total_items  INTEGER NOT NULL
       daily_minutes INTEGER NOT NULL
       created_at   TEXT NOT NULL
       config       TEXT NOT NULL DEFAULT '{}'   -- JSON：间隔序列等快照

   1.5 settings（键值配置表）
       key          TEXT PRIMARY KEY
       value        TEXT NOT NULL
       -- 默认含 intervals=[0,1,2,4,7,15,30,60,120,240]、max_interval=365、
       -- reset_to=0、mastery_gain 系数等

   1.6 schema_version（迁移版本表）
       version      INTEGER PRIMARY KEY
       applied_at   TEXT NOT NULL

2. 关键算法或流程

   2.1 间隔序列与阶段推进：
       设 intervals = [0, 1, 2, 4, 7, 15, 30, 60, 120, 240]（单位天）。
       质量映射：q=0 → 阶段回落至 reset_to（默认 0），lapse_count +1；
                 q=1 → 阶段不变，interval = max(1, interval // 2)；
                 q=2 → 阶段 +1，interval = intervals[min(stage, len-1)]；
                 q=3 → 阶段 +1，interval = intervals[min(stage, len-1)]；
                 q=4 → 阶段 +2（不超过上限），interval = intervals[min(stage, len-1)]
                       再乘 ease_factor 的增益系数 1.3，取整并封顶 max_interval。
       下次复习日期 = 复习当日 + interval 天；interval=0 表示当天再复习一次
       （首次录入的即时应答），实现上使用 “当日 + 0 天” = 当天，并要求
       用户当天完成一次回顾后才进入阶段 1。

   2.2 SM-2 风格 ease_factor 更新（简化版，写死在文档里以便验收）：
       ef' = ef + (0.1 - (4 - q) * (0.08 + (4 - q) * 0.02))
       约束 ef' >= 1.3；q=0 或 1 时 ef' 额外减 0.2。
       该因子仅在 q>=2 时参与 interval 的放大计算，避免答错反而拉长间隔。

   2.3 掌握度公式：
       base = 100 * (1 - exp(-stage_index / 4.0))      -- 阶段越多越接近 100
       penalty = min(30, lapse_count * 3)              -- 每次遗忘扣分，封顶 30
       bonus = (avg_quality_last5 - 2) * 5             -- 近 5 次平均质量修正
       mastery = clamp(base - penalty + bonus, 0, 100)
       等级映射：<25 陌生；25~49 初识；50~74 熟悉；>=75 牢固。
       每次 review 后重算并写回 items.mastery。

   2.4 学习计划反推（plan 命令）：
       输入：某科目待学总量 N、截止日期 D、每日可用分钟 M、平均每条首次学习
       耗时 t_new（默认 1.5 分钟）、平均每条复习耗时 t_rev（默认 0.5 分钟）。
       步骤一，计算剩余天数 days = (D - today).days + 1；
       步骤二，计算每天的复习负担：既有 items 的 due_date 落在该天的数量 × t_rev；
       步骤三，剩余可分配给新学的分钟 = max(0, M - 复习负担)；
       步骤四，每天新学量 = floor(剩余分钟 / t_new)，且不超过 ceil(N / 剩余天数)；
       步骤五，输出日程表并提示“按此进度预计 D 日完成 / 或将延期 K 天”。

   2.5 积压处理：
       当逾期条目超过阈值（默认 50）时，today 输出分组提示，
       建议按 --subject 分批处理，并提供 `review --batch 20` 只复习前 20 条。

3. 接口或命令设计

   item add -t TITLE -a ANSWER [-s 科目] [--tags a,b] [-d 1..5] [--due DATE]
   item list [--subject S] [--stage N] [--tag T] [--due-before D] [--limit N]
   item edit ID [--title --answer --subject --tags --difficulty]
   item remove ID [ID ...] --yes
   item import CSV_PATH [--dry-run]
   today [--subject S] [--limit N] [--count-only] [--json]
   review ID -q 0..4 [--minutes M] [--json]
   review --interactive [--subject S] [--limit N]
   plan --subject S --deadline 2024-06-30 --minutes 60 [--total N]
   mastery [--subject S] [--low] [--json]
   stats [--period week|month|all] [--subject S]
   export --format csv|json -o PATH [--from D --to D]
   config set KEY VALUE / config show

   函数签名：
   def next_schedule(item: Item, q: Quality, today: date,
                     cfg: SchedulerConfig) -> ScheduleResult
   def compute_mastery(stage: int, lapse_count: int,
                       recent_qualities: list[int]) -> float
   def build_plan(items: list[Item], deadline: date, daily_minutes: int,
                  today: date) -> list[PlanDay]

【五、运行方式与示例】

安装（标准库即可运行）：
  cd C:\projects\100programs\054_study_planner
  pip install rich          （可选）
  python -m planner init

示例一（录入与今日任务）：
  输入：python -m planner item add -t "photosynthesis" -a "光合作用：植物利用光能
        将 CO2 和 H2O 合成有机物并释放 O2" -s 生物 -d 3 --tags 高频
  输出：已录入 #1 photosynthesis（科目：生物，难度 3），首次复习 2024-05-03
  输入：python -m planner today
  输出：
        #1  生物  photosynthesis  阶段 0  逾期 0 天  上次质量 -  下次 2024-05-03

示例二（复习并观察阶段推进）：
  输入：python -m planner review 1 -q 3 --minutes 2
  输出：已复习 #1 photosynthesis  阶段 0 → 1  下次复习 2024-05-04（+1 天）
        掌握度 21%（陌生）
  输入：python -m planner review 1 -q 0
  输出：已复习 #1 photosynthesis  阶段 1 → 0（遗忘，重置）  下次复习 2024-05-04（+1 天）
        掌握度 8%（陌生，累计遗忘 1 次）

示例三（计划反推与异常输入）：
  输入：python -m planner plan --subject 生物 --deadline 2024-06-30 --minutes 60 --total 600
  输出：
        剩余 59 天，待学 600 条
        每日复习负担约 40 条 / 20 分钟
        每日新学 26 条 / 约 39 分钟，预计 59 天完成
        提示：前期复习负担较轻，可提前至 45 天完成
  输入：python -m planner review 1 -q 7
  输出：错误：quality 只能是 0~4（0忘了 1模糊 2勉强 3记住 4轻松），收到 7（退出码 2）
  输入：python -m planner review 999 -q 3
  输出：错误：内容 #999 不存在                                （退出码 2）

【六、验收标准】

[ ] `planner init` 可重复执行，默认 settings 写入 intervals 等初始配置。
[ ] 新录入内容当天即出现在 today 列表中（interval=0 的即时回顾口径）。
[ ] q=3 一次后阶段从 0 变为 1，due_date 为次日；q=0 后阶段回落且 lapse_count 加 1。
[ ] 连续三次 q=4 后 interval 单调递增且不超过 max_interval(365)。
[ ] ease_factor 在任何 quality 下都不低于 1.3。
[ ] mastery 恒在 0~100 之间；对同一内容反复标记 q=0，mastery 单调不增。
[ ] 掌握等级映射与文档一致（<25 陌生、25~49 初识、50~74 熟悉、>=75 牢固）。
[ ] today 列表按逾期天数降序排列，逾期天数用今天减 due_date 计算正确。
[ ] 跨月逾期正确（如 due=2024-04-28，today=2024-05-03，逾期 5 天）。
[ ] --count-only 输出纯数字，可直接用于 shell 判断。
[ ] --interactive 模式下先显示题面、回车后显示答案，评价输入非法时重新询问。
[ ] plan 输出的每日新学量 × 剩余天数 + 已有到期复习量 与总时长约束不冲突。
[ ] stats 的阶段分布条形图长度与数据库实际计数一致。
[ ] 导出 JSON 后清库再导入，items、review_log、settings 全部可还原。
[ ] scheduler.py 与 mastery.py 的单元测试覆盖 q=0~4 全部分支，pytest 全绿。

【七、可选扩展】

1. 接入 030 单词记忆卡片项目，共享同一套调度内核。
2. 增加语音朗读与听力模式（pyttsx3 或调用系统 TTS）。
3. 增加导出 Anki 兼容的 CSV/APKG 字段格式，便于迁移。
4. 增加遗忘曲线拟合：用 review_log 数据估计个人记忆保持率曲线并画图。
5. 增加间隔序列自适应：根据个人数据自动调优 intervals（简单网格搜索）。
6. 增加提醒推送：到期未复习时通过邮件或 webhook 提醒。

【八、涉及知识点】

- 间隔重复算法：艾宾浩斯遗忘曲线、SM-2 的 ease_factor、阶段与间隔映射。
- sqlite3 数据库设计与只追加日志表（事件溯源思想）。
- 数学建模：指数衰减函数、clamp、加权评分公式、参数标定与验证。
- datetime：日期加减、逾期天数计算、跨月跨年与测试替身（注入 today）。
- 优先级排序与积压处理：多键排序、分批处理策略。
- 资源约束下的计划反推：线性规划思想的朴素实现。
- 命令行交互设计：交互式问答、输入校验循环、进度提示。
- 数据可迁移性：JSON 全量备份、CSV 导出、导入去重与幂等。
- 单元测试：时间与随机性解耦、分支覆盖率、属性测试思路（掌握度不越界）。
================================================================================
