================================================================================
项目编号：030                    难度等级：★★☆☆☆（小型项目）
项目名称：单词记忆卡片
所属分类：网络与在线服务 / 学习工具（间隔重复）
建议工时：5 ~ 8 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】
背单词最大的问题不是记不住，而是把时间浪费在已经会的词上，又反复忘记那些总是记
不住的词。解决这个问题的经典方法是间隔重复：记住的词下次隔得更久再问，忘掉的词
很快再出现。本项目实现一个命令行背单词程序，用简化版 SM-2 算法安排每天的复习队列，
并把学习进度存进本地 SQLite 数据库。

目标用户是准备考试或想扩充词汇量的学习者。做出来之后，你每天运行一次 review，
程序按到期时间抽出该复习的卡片，你按键评价自己记得多熟，程序据此调整下次复习的
间隔与难度因子；答错的卡片会自动回到当天的队列末尾再问一遍。

本工具完全离线运行，不抓取任何在线词库，也不上传学习记录。词库由用户自己导入
（支持 CSV 与 JSON），因此不涉及任何第三方接口的 robots.txt 或频率限制问题；如果
你后续从网络获取词库数据，必须自行确认该数据源的使用许可，禁止抓取受版权保护的
词典内容并二次分发。

【二、功能需求清单】
1. 核心功能
   1.1 卡片管理：支持新增单词卡片，字段为 word（单词或短语）、meaning（释义）、
       phonetic（音标，可选）、example（例句，可选）、tags（标签，逗号分隔）、
       deck（牌组名，默认 default）。
   1.2 词库导入：import 子命令支持 CSV（表头 word,meaning,phonetic,example,tags）
       与 JSON（对象数组）两种格式；导入时按 word + deck 去重，重复项默认跳过并
       计数，--update 表示用新数据覆盖已有释义。
   1.3 复习队列：review 子命令按 due_date 小于等于今天的条件抽卡，排序规则为
       到期时间升序、其次按熟练度（ease_factor）升序，默认每次最多 --limit 20 张
       （默认 20，范围 1 ~ 200），--all 表示不限量。
   1.4 SM-2 简化算法：每次回答后用户输入评价等级 0 ~ 5，程序按等级更新间隔
       interval、难度因子 ease_factor 与复习次数 repetition，并计算下次复习日期。
   1.5 当日循环：一次 review 会话中答错（等级小于 3）的卡片立即重新排入本次队列
       末尾，最多重复出现 2 次；重复出题时界面标注「（重问 1/2）」。
   1.6 学习统计：stats 子命令展示总卡片数、各牌组卡片数、今日到期数、今日已复习
       数、已掌握数（间隔大于等于 21 天）、平均难度因子、未来 7 天的到期分布。
   1.7 掌握度浏览：list 子命令按牌组或标签列出卡片，显示下次到期日期与当前间隔，
       支持 --due-only（只看今天该复习的）与 --search 模糊搜索。
   1.8 数据持久化：全部数据存于 ~/.flashcard/cards.db（SQLite），支持 --db PATH
       指定其他位置；数据库首次运行时自动建表，并用 user_version 记录结构版本。

2. 输入与交互
   2.1 子命令共 6 个：add、import、review、list、stats、reset。
   2.2 review 交互方式：显示卡片的正面（word 与音标）→ 等待回车翻面 → 显示释义与
       例句 → 要求输入 0 ~ 5 的等级 → 输入 q 可随时结束本次会话并保存进度。
   2.3 review 支持非交互模式：--grade N 表示对所有抽到的卡片统一按等级 N 处理，用于
       脚本化测试与批量调整。
   2.4 命令形式：
       python flashcard.py add --word ubiquitous --meaning "无处不在的" --tags CET6
       python flashcard.py import words.csv --deck CET6 --update
       python flashcard.py review --deck CET6 --limit 20
       python flashcard.py list --due-only --search ubi
       python flashcard.py stats
       python flashcard.py reset --deck CET6 --confirm
   2.5 所有交互提示写入 stdout，用户输入从 stdin 读取；在非交互环境（stdin 不是
       tty）且未提供 --grade 时，提示需要使用非交互模式并以退出码 3 结束。

3. 输出与展示
   3.1 review 界面使用固定分隔线，正面显示：
       ──────────── 第 3/20 张（牌组 CET6）────────────
       word：ubiquitous   [juːˈbɪkwɪtəs]
       按回车查看释义，输入 q 结束
   3.2 背面显示释义、例句与当前进度：难度因子 2.50，当前间隔 6 天，下次 2024-05-18。
   3.3 等级提示行固定为：
       0 完全忘记 / 1 想不起来 / 2 想起来很难 / 3 想起来有困难 / 4 稍作犹豫 / 5 立刻想起
   3.4 会话结束时输出小结：本次复习 20 张、答对 16 张、正确率 80.0%、新增到期
       卡片 3 张、用时 6 分 12 秒。
   3.5 stats 的到期分布用固定宽度的文本条形（每 5 张一个 # 字符），例如
       05-13  8 张 ########
   3.6 list 输出列：id（右对齐 5）、word（左对齐 24）、释义（左对齐 30，超长截断）、
       间隔（右对齐 5 天）、到期日、牌组。

4. 异常与边界处理
   4.1 单词已存在于同一牌组时 add 报错并提示使用 --update，退出码 2。
   4.2 导入文件缺少必需的 word 或 meaning 字段时报错并指出第几行，退出码 2；
       部分行非法时跳过非法行、导入合法行，最后汇总跳过数量。
   4.3 导入文件编码不是 UTF-8 时，尝试 utf-8-sig，再失败则提示用户转换编码。
   4.4 复习等级输入非法（非 0 ~ 5 的整数、空输入、含字母）时提示重新输入，连续
       3 次非法输入则按等级 0 处理并继续，避免卡死。
   4.5 无到期卡片时输出「今天没有需要复习的卡片」并给出最近一张的到期日期，退出码 0。
   4.6 数据库文件被占用或损坏时给出明确错误（含 sqlite3 异常信息），非损坏情况下
       使用重试 2 次、间隔 0.5 秒的策略；损坏时提示可用 --db 指向其他文件重建。
   4.7 reset 必须带 --confirm 才执行，未带时只打印将要删除的卡片数量并要求确认，
       退出码 2。
   4.8 间隔上限为 365 天，超过时截断为 365 并在卡片备注中说明已进入长期记忆档。
   4.9 系统日期被回拨导致 due_date 在未来很远时，list --due-only 仍能正确工作，
       stats 提示可能存在日期异常（未来到期卡片占比超过 90%）。

【三、技术要求与约束】
1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库 sqlite3、csv、json、argparse、datetime、pathlib、
   math、random、logging、unicodedata（显示宽度）。禁止引入第三方库（包括
   supermemo、fsrs 等现成算法库），算法必须自行实现以便理解原理。
3. 并发与性能：单用户本地程序，采用单线程串行执行；数据库开启 WAL 模式以提高
   写入可靠性；批量导入使用单事务提交，1 万条导入耗时应低于 3 秒。
4. 超时与重试：本程序不访问网络，因此不存在网络超时；数据库忙等采用
   sqlite3.connect(timeout=5) 并在 sqlite3.OperationalError 时重试 2 次。
5. 限速与资源约束：单次 review 默认最多 20 张，防止一次复习过载；单次导入文件
   大小上限 20 MB，超过时拒绝并提示分批导入。
6. 合规要求：本工具不抓取、不上传任何数据；不内置受版权保护的词库；示例词库仅为
   少量教学用词；若用户自行从网络获取词库，须自行确认授权与许可，遵守数据源的
   robots.txt 与使用条款，禁止把整本词典批量抓取后分发。
7. 禁止事项：禁止联网；禁止在数据库中保存任何个人身份信息；禁止把学习记录用于
   任何形式的统计上报；禁止实现自动打卡到第三方平台的逻辑。
8. 代码组织：db.py（连接管理、建表与迁移、卡片 CRUD）、scheduler.py（SM-2 计算
   calculate_next_review 与队列生成）、importer.py（CSV/JSON 解析与校验）、
   session.py（交互式复习会话状态机）、report.py（stats 与 list 渲染）、cli.py
   （子命令分发）。每个模块只暴露少量公共函数，内部细节私有化。
9. 编码规范：类型注解与 docstring 全覆盖；日期一律用 datetime.date 并与数据库以
   ISO 字符串（YYYY-MM-DD）互转；SQL 必须使用参数化占位符，禁止字符串拼接；
   交互输出与日志分离，日志写 stderr。

【四、设计要点】
1. 数据结构：
   表 cards：
     id INTEGER PRIMARY KEY AUTOINCREMENT
     word TEXT NOT NULL
     meaning TEXT NOT NULL
     phonetic TEXT
     example TEXT
     tags TEXT                 逗号分隔的标签串
     deck TEXT NOT NULL DEFAULT 'default'
     created_at TEXT NOT NULL
     due_date TEXT NOT NULL    下次复习日期 YYYY-MM-DD
     interval INTEGER NOT NULL DEFAULT 0        当前间隔天数
     repetition INTEGER NOT NULL DEFAULT 0      成功复习次数
     ease_factor REAL NOT NULL DEFAULT 2.5      难度因子，范围 1.3 ~ 2.8
     lapses INTEGER NOT NULL DEFAULT 0          遗忘次数
     last_reviewed_at TEXT
     UNIQUE(word, deck)
   表 reviews（复习流水）：
     id INTEGER PRIMARY KEY AUTOINCREMENT
     card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE
     reviewed_at TEXT NOT NULL
     grade INTEGER NOT NULL
     prev_interval INTEGER NOT NULL
     next_interval INTEGER NOT NULL
     ease_factor_after REAL NOT NULL
   ReviewOutcome = {card_id, grade, prev_interval, next_interval, ease_factor_after,
                    due_date}
2. 关键算法或流程：
   2.1 SM-2 简化算法（calculate_next_review(interval, repetition, ease_factor, grade)）：
       第一步，按等级调整难度因子：
         EF' = EF + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
         EF' 下限 1.3，上限 2.8。
       第二步，按等级决定间隔：
         若 grade < 3（忘记）：repetition 归零，interval 置为 1 天（若为学习中的新卡
         则置为 0 天，即当天再次出现），lapses 加 1，EF 额外减 0.2（不低于 1.3）。
         若 grade >= 3：repetition 加 1；
           repetition 为 1 时 interval = 1；
           repetition 为 2 时 interval = 6；
           repetition 大于等于 3 时 interval = round(interval * EF')。
         最终 interval 取整并限制在 1 ~ 365 之间，interval 为 0 时 due_date 为今天。
       第三步，计算 due_date = 今天 + interval 天，返回新的三元组与 due_date。
   2.2 队列生成：SELECT ... WHERE deck = ? AND due_date <= today ORDER BY due_date ASC,
       ease_factor ASC, id ASC LIMIT ?；答错卡片重新入队时记录其重问次数，超过 2 次
       则不再入队。
   2.3 会话状态机：状态依次为 SHOW_FRONT、SHOW_BACK、WAIT_GRADE；每张卡片处理完
       写入 reviews 与更新 cards（同一事务提交）；会话结束或用 q 中断都要 flush
       未提交的进度并打印小结。
   2.4 导入去重：先按 (word, deck) 查询是否存在；不存在则 INSERT；存在且未加
       --update 则计入 skipped 并继续；存在且加 --update 则 UPDATE 释义等字段但保留
       复习进度，避免覆盖用户的学习历史。
   2.5 统计计算：今日已复习数来自 reviews 表中 reviewed_at 为今天的去重 card_id 数；
       已掌握数为 interval >= 21 的卡片数；未来 7 天到期分布用一条按 due_date 分组
       的查询得到，缺失的日期补 0。
3. 接口或命令设计：
   python flashcard.py add --word ubiquitous --meaning "无处不在的" --phonetic "juːˈbɪkwɪtəs" --tags CET6
   python flashcard.py import words.csv --deck CET6 --update
   python flashcard.py review --deck CET6 --limit 20 --grade 4
   python flashcard.py list --deck CET6 --due-only --search ubi
   python flashcard.py stats --deck CET6
   python flashcard.py reset --deck CET6 --confirm
   关键函数签名：
   def init_db(path: Path) -> sqlite3.Connection
   def add_card(conn, word: str, meaning: str, deck: str, **extra) -> int
   def import_cards(conn, path: Path, deck: str, update: bool) -> tuple[int, int, int]
   def calculate_next_review(interval: int, repetition: int, ease_factor: float,
                             grade: int) -> tuple[int, int, float]
   def build_queue(conn, deck: str | None, limit: int, today: date) -> list[Card]
   def run_session(conn, cards: list[Card], grade_override: int | None) -> dict

【五、运行方式与示例】
安装与运行（无需第三方依赖，数据库自动创建）：
   python flashcard.py add --word ubiquitous --meaning "无处不在的" --tags CET6
   python flashcard.py import sample_words.csv --deck CET6
   python flashcard.py review --deck CET6 --limit 20
示例一（交互式复习）：
   ──────────── 第 1/3 张（牌组 CET6）────────────
   word：ubiquitous   [juːˈbɪkwɪtəs]
   按回车查看释义，输入 q 结束
   （回车）
   释义：无处不在的
   例句：Smartphones have become ubiquitous in modern life.
   难度因子 2.50，当前间隔 0 天，下次 2024-05-12
   0 完全忘记 / 1 想不起来 / 2 想起来很难 / 3 想起来有困难 / 4 稍作犹豫 / 5 立刻想起
   > 5
   会话结束：本次复习 3 张、答对 3 张、正确率 100.0%、用时 1 分 08 秒
   退出码：0
示例二（非交互与统计）：
   python flashcard.py review --deck CET6 --limit 10 --grade 2
   输出：已按等级 2 处理 10 张卡片（其中 2 张已重新入队） 
   python flashcard.py stats
   输出：
   总卡片 128 张，牌组：CET6 100、default 28
   今日到期 12 张，今日已复习 10 张，已掌握 34 张
   平均难度因子 2.42
   未来 7 天到期分布：
   05-13  8 张 ########
   05-14  3 张 ###
   05-15  0 张
   05-16  5 张 #####
   退出码：0
示例三（异常输入）：
   python flashcard.py add --word ubiquitous --meaning "无处不在的"
   输出：错误：单词 ubiquitous 已存在于牌组 default，使用 --update 可覆盖释义
   退出码：2
   python flashcard.py reset --deck CET6
   输出：将删除牌组 CET6 的 100 张卡片及其复习记录，请加 --confirm 确认
   退出码：2
   python flashcard.py review（stdin 非终端且未指定 --grade）
   输出：错误：当前环境不支持交互输入，请使用 --grade N 非交互模式
   退出码：3

【六、验收标准】
[ ] 首次运行 review 时自动创建 cards.db 与两张表，user_version 为 1。
[ ] add 添加的卡片 due_date 为当天，interval 为 0，ease_factor 为 2.5。
[ ] 同一牌组重复 add 同一单词报错退出码 2；加 --update 后成功且复习进度不变。
[ ] 等级 5 连续三次复习后的间隔依次为 1、6、约 15 天（按 EF 计算，允许取整误差 1 天）。
[ ] 等级 0 的卡片 repetition 归零、lapses 加 1、EF 减少、当天再次出现在队列中。
[ ] 同一张卡片在一次会话中最多被重问 2 次，之后不再出现。
[ ] 会话中输入 q 后立即结束，已评价的卡片进度已写入数据库。
[ ] 输入非法等级 9 或 abc 时提示重新输入，连续 3 次非法后按 0 处理。
[ ] 交互环境下等级输入为空时视为非法输入而不是当作 0。
[ ] import 导入 CSV 与 JSON 均成功，重复行被跳过并打印跳过数量。
[ ] import 遇到缺少 meaning 的行时指出行号并跳过该行，其他行正常导入。
[ ] import --update 覆盖释义但不修改 interval、ease_factor、due_date。
[ ] list --due-only 只显示今天及之前到期的卡片。
[ ] stats 的今日到期数与 list --due-only 的条数一致。
[ ] stats 的到期分布总数与未来 7 天内 due_date 的卡片总数一致。
[ ] 无到期卡片时输出提示并给出最近一张的到期日期，退出码 0。
[ ] reset 未加 --confirm 时不删除任何数据。
[ ] 数据库路径不存在时能自动创建父目录；--db 指向只读位置时报出清晰错误。
[ ] 10000 条批量导入在 3 秒内完成且使用单事务。
[ ] SQL 全部使用参数化查询（代码中不存在 f-string 拼接的 SQL）。
[ ] 源码中无网络相关 import，无第三方依赖。

【七、可选扩展】
1. 增加 cli 拼写测试模式：给出中文释义，让用户输入单词，按是否拼对（允许 1 个字符
   编辑距离）折算为 0 ~ 5 的等级后交给 SM-2 处理。
2. 增加 FSRS 风格的记忆稳定性模型作为可切换调度器（--scheduler sm2|fsrs），并在
   stats 中对比两种调度器的预计复习量。
3. 增加导出功能：把牌组导出为 CSV 或 Anki 可导入的制表符分隔文本，便于迁移。
4. 增加每日目标与连续打卡天数统计，读取 reviews 表按日期聚合，输出最近 30 天的
   打卡热力文本图。

【八、涉及知识点】
- sqlite3 参数化查询、事务、WAL 模式与表结构版本管理
- SM-2 间隔重复算法的公式推导与边界处理
- 命令行交互式状态机与输入校验
- csv 与 json 模块的读写与编码处理
- datetime.date 与 ISO 字符串互转、日期加减
- argparse 子命令、互斥参数与必填校验
- 数据建模中的唯一约束与幂等导入
- 统计聚合 SQL（GROUP BY、COUNT、DISTINCT）与结果补全
- 文本宽度对齐与进度可视化
- 学习工具的数据隐私边界与离线设计
================================================================================
