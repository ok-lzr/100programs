================================================================================
项目编号：055                    难度等级：★★★☆☆（中型项目）
项目名称：个人藏书管理系统
所属分类：个人数据管理 / 信息检索
建议工时：2 ~ 4 天
运行环境：Python 3.10+    第三方依赖：requests（可选，仅 ISBN 联网查询）
================================================================================

【一、项目背景与目标】

藏书一旦超过两三百本，就会出现三个具体问题：想找某本书时记不清放在哪个书架；
买书时忘记自己已经买过而重复购买；朋友借走一本书，半年后连借给谁都忘了。
Excel 能凑合，但多条件检索、借阅状态跟踪和去重都很别扭。

本项目用 SQLite 建立个人藏书库，支持录入图书（书名、作者、出版社、ISBN、
出版年、页数、定价、分类、位置、状态、评分、读后感），支持从 ISBN 自动补全
书目信息，支持借出与归还登记，支持按任意字段组合的高级检索与全文模糊搜索。

目标用户是有实体书架的个人读者、小型读书会和班级图书角管理者。项目难点在于
“多值属性”（一本书可有多个作者、多个标签）的建模取舍、ISBN 校验位的正确算法、
以及借阅历史的时间线表达（一本书多次借出归还）。

【二、功能需求清单】

1. 核心功能
   1.1 图书录入（add）：必填书名与至少一个作者；可只给 ISBN 让程序联网补全
       书名、作者、出版社、出版年、页数；也可完全离线手工录入。
   1.2 ISBN 查询（isbn）：对 ISBN-10 与 ISBN-13 做格式校验与校验位验证，
       通过公开接口（如 Open Library / Google Books）查询书目，输出候选结果
       供用户确认后写入数据库；支持批量查询（--file isbn_list.txt）。
   1.3 图书修改与删除（edit/remove）：支持修改任意字段；删除时若该书当前
       处于借出状态则拒绝，提示先办理归还。
   1.4 高级检索（search）：支持按书名/作者关键词、出版社、分类、标签、
       出版年区间、评分区间、阅读状态、存放位置、是否在馆任意组合过滤；
       支持 --sort year|title|rating|added 与 --limit/--offset 分页。
   1.5 借出与归还（lend/return）：登记借阅人姓名、联系方式、借出日期、
       应还日期；归还时记录归还日期并计算逾期天数；支持查看当前全部外借清单。
   1.6 阅读状态管理（read）：状态取值 未读 / 在读 / 已读 / 弃读 / 想读，
       可记录开始与读完日期、评分（1~5 星）、读后感。
   1.7 统计报表（stats）：藏书总量、按分类/出版社/年代分布、已读比例、
       平均评分、外借中数量、逾期数量、入藏速度（按年月）。
   1.8 导入导出（export/import）：导出 CSV（UTF-8 BOM，Excel 可读）与 JSON
       （含借阅历史，可完整恢复）；从 CSV 导入时按 ISBN 优先、否则按
       “书名+第一作者”判定重复并跳过。

2. 输入与交互
   2.1 命令形如：
       `python -m library add --isbn 9787115428028 --location A3-2 --tags 计算机`
       `python -m library search --author 费曼 --status 已读 --rating-min 4`
   2.2 支持多作者写法 `--author "作者1;作者2"`，内部分隔符同时接受 `;`、`、`、`,`。
   2.3 交互录入模式（`add --interactive`）逐字段询问，可为空回车跳过，
       结束后显示整条记录要求确认。
   2.4 `--db PATH` 指定数据库；`--offline` 强制不联网，只用本地数据。
   2.5 `--json` 输出机器可读结果，便于生成书架清单页面。

3. 输出与展示
   3.1 search 结果以对齐表格输出：ID、书名、作者、出版年、分类、位置、状态、评分。
   3.2 单本书详情（show ID）按字段逐行展示，并附借阅历史时间线（借出/归还日期、
       借阅人、逾期天数）与标签列表。
   3.3 stats 用文字条形图展示分类分布，条形长度按比例缩放，比例用百分比标注。
   3.4 位置字段排序时按“书架号-层号-序号”的自然序排列，而非字符串序
       （A10 排在 A2 之后而不是之前）。

4. 异常与边界处理
   4.1 ISBN 校验失败：拒绝写入，指出错误类型（长度不对 / 含非法字符 /
       校验位应为 X 实际为 Y），并允许 `--force` 跳过校验仅保存原始字符串。
   4.2 相同 ISBN 已存在：提示已存在的书目 ID 与书名，询问是否合并或跳过。
   4.3 联网查询超时或接口返回空：不阻塞录入，提示“未查到书目信息，请手工补充”，
       并允许 `--keep-partial` 保存已填字段。
   4.4 同一本书借出给同一人两次：允许，形成两条借阅记录，当前外借状态以
       未归还的最新一条为准；若该书已有未归还记录，再次 lend 时报错。
   4.5 归还日期早于借出日期：拒绝并提示。
   4.6 空数据库 search：输出“未找到匹配图书”，退出码 0。
   4.7 分页超出范围：返回空列表而非报错。
   4.8 导入 CSV 缺少必需列：报错并列出缺失列名与文件实际表头。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：
   2.1 标准库：sqlite3、argparse、csv、json、re、unicodedata、pathlib、datetime、
       dataclasses、logging、urllib.request（HTTP 请求也可用它，避免额外依赖）、
       functools、collections。
   2.2 第三方：requests（可选，仅在需要更方便的超时与重试控制时使用）；
       若使用则版本需在 requirements.txt 中声明。
   2.3 明确要求：ISBN 校验、自然序排序、去重判定必须自己实现，不许依赖第三方
       工具库。
3. 禁止事项：禁止把图书的多个作者存成“用逗号拼接的单字符串”后靠 LIKE 模糊匹配
   当作多值查询的正解（必须建关联表）；禁止在查询中拼 SQL 字符串；
   禁止在未确认的情况下覆盖已有记录。
4. 代码组织：
   - `isbn.py`：ISBN-10/13 校验与归一化（去连字符、大小写 X）。
   - `metadata_api.py`：外部书目查询（Open Library / Google Books），
     含超时、重试、限速与响应解析，仅返回标准化 dict。
   - `db.py` / `repository.py`：建表与 SQL 层。
   - `models.py`：Book、Author、Tag、Loan、StatsResult。
   - `search.py`：查询构造器（把过滤条件编译为参数化 SQL 与排序）。
   - `natural_sort.py`：位置字段自然序键函数。
   - `stats.py`、`exporters.py`、`cli.py`。
5. 编码规范：全部函数带类型注解；网络请求统一封装并设置 timeout=10 与最多
   2 次重试（指数退避）；日志记录每次外部查询的 URL、状态码与耗时；
   用户可见输出用 print，调试信息用 logging。

【四、设计要点】

1. 数据结构（SQLite 表结构）

   1.1 books（图书主表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       title         TEXT NOT NULL
       subtitle      TEXT NOT NULL DEFAULT ''
       isbn13        TEXT NULL UNIQUE     -- 归一化后的 13 位
       isbn10        TEXT NULL            -- 归一化后的 10 位（可能为空）
       publisher     TEXT NOT NULL DEFAULT ''
       publish_year  INTEGER NULL CHECK (publish_year BETWEEN 1000 AND 2999)
       pages         INTEGER NULL CHECK (pages > 0)
       price_cents   INTEGER NULL         -- 定价（分）
       language      TEXT NOT NULL DEFAULT 'zh'
       category_id   INTEGER NULL REFERENCES categories(id) ON DELETE SET NULL
       location      TEXT NOT NULL DEFAULT ''   -- 如 A3-2（书架A 第3层 第2位）
       status        TEXT NOT NULL DEFAULT '未读'
                     CHECK (status IN ('想读','未读','在读','已读','弃读'))
       rating        INTEGER NULL CHECK (rating BETWEEN 1 AND 5)
       started_on    TEXT NULL            -- 'YYYY-MM-DD'
       finished_on   TEXT NULL
       review_note   TEXT NOT NULL DEFAULT ''   -- 读后感
       cover_url     TEXT NOT NULL DEFAULT ''
       source        TEXT NOT NULL DEFAULT 'manual'  -- manual / isbn_api / csv
       added_at      TEXT NOT NULL
       updated_at    TEXT NOT NULL
       索引：idx_books_title(title)、idx_books_status(status)、
             idx_books_category(category_id)、idx_books_year(publish_year)

   1.2 authors（作者表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       name          TEXT NOT NULL UNIQUE
       name_en       TEXT NOT NULL DEFAULT ''
       country       TEXT NOT NULL DEFAULT ''

   1.3 book_authors（图书-作者关联表，处理多作者）
       book_id       INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE
       author_id     INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE
       role          TEXT NOT NULL DEFAULT 'author'  -- author / translator / editor
       ord           INTEGER NOT NULL DEFAULT 0      -- 署名顺序
       PRIMARY KEY (book_id, author_id, role)

   1.4 categories（分类表，支持层级）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       name          TEXT NOT NULL UNIQUE
       parent_id     INTEGER NULL REFERENCES categories(id) ON DELETE SET NULL

   1.5 tags（标签表）与 book_tags（关联表）
       tags: id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, color TEXT DEFAULT ''
       book_tags: book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
                  tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                  PRIMARY KEY (book_id, tag_id)

   1.6 loans（借阅记录表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       book_id       INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE
       borrower      TEXT NOT NULL          -- 借阅人姓名
       contact       TEXT NOT NULL DEFAULT ''  -- 手机/邮箱，用于催还
       lent_on       TEXT NOT NULL          -- 'YYYY-MM-DD'
       due_on        TEXT NOT NULL          -- 应还日期
       returned_on   TEXT NULL              -- 为空表示未归还
       overdue_days  INTEGER NULL           -- 归还时计算并固化
       note          TEXT NOT NULL DEFAULT ''
       created_at    TEXT NOT NULL
       索引：idx_loans_book(book_id, returned_on)、idx_loans_open(returned_on, due_on)
       业务约束：同一 book_id 至多一条 returned_on IS NULL 的记录
                 （用部分唯一索引实现：
                  CREATE UNIQUE INDEX idx_loans_current ON loans(book_id)
                  WHERE returned_on IS NULL;）

   1.7 import_log（导入日志表）
       id / source_file / imported_at / total_rows / inserted_rows /
       skipped_rows / detail(TEXT JSON)

   1.8 schema_version（迁移版本表）
       version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL

2. 关键算法或流程

   2.1 ISBN 归一化与校验：
       归一化：删除所有 `-` 与空格，字母统一大写。
       ISBN-10 校验：加权和 sum(i=1..10) of i * value(digit_i)（X 记 10）
       需满足 % 11 == 0。
       ISBN-13 校验：sum(奇数位 * 1 + 偶数位 * 3) % 10 == 0。
       若输入是 10 位且合法，可换算为 13 位：前缀 978 + 前 9 位，重新计算校验位。
       示例：9787115428028 → 合法；9787115428020 → 报“校验位应为 8，实际 0”。

   2.2 外部书目查询流程：
       步骤一，优先查 Open Library 的 ISBN 接口
       `https://openlibrary.org/isbn/{isbn}.json`，解析 title、authors（可能需
       二次请求 authors 键）、publishers、publish_date、number_of_pages；
       步骤二，若无结果再查 Google Books 的 volumes?q=isbn:{isbn}；
       步骤三，两次都失败则返回 None；
       步骤四，任何请求设置 timeout=10 秒、最多 2 次重试、每次间隔 1 秒与 2 秒；
       步骤五，请求头设置可识别的 User-Agent（含项目名与联系邮箱占位）；
       步骤六，所有网络失败都被吞掉并降级为手工录入，不使程序崩溃；
       步骤七，整个批量查询两本书之间强制 sleep 1 秒，避免给对方服务器压力。

   2.3 高级检索编译：把 SearchQuery dataclass 编译为
       `WHERE 1=1 [AND ...]` 加参数列表；作者条件走 EXISTS 子查询关联
       book_authors/authors；标签条件同样走 EXISTS；关键词条件对
       title/subtitle/publisher/review_note 做 LIKE '%kw%'（明确说明这是
       简易方案，数据量超过 5 万条时改用 FTS5）。
       排序白名单映射：year → publish_year DESC, title；title → title COLLATE
       NOCASE；rating → rating DESC NULLS LAST；added → added_at DESC。
       禁止把用户输入直接拼进 ORDER BY（必须查表映射）。

   2.4 自然序排序键：
       用 `re.split(r'(\d+)', location)` 切分，数字段转 int，其余转小写字符串，
       生成混合元组作为排序键，保证 A2 < A10。

   2.5 借阅时间线：
       对一个 book_id 取 loans 按 lent_on 升序；对每条计算
       若已归还则用固化 overdue_days；未归还则用今天与 due_on 的差值
       作为“当前逾期天数”，在展示时标注“（未归还）”。

3. 接口或命令设计

   add [-t/--title] [-a/--author] [--isbn] [--publisher] [--year] [--pages]
       [--price] [--category] [--tags] [--location] [--status] [--interactive]
   isbn ISBN [ISBN ...] [--file PATH] [--add-first] [--json]
   show ID            edit ID [字段参数...]            remove ID --yes
   search [--keyword] [--author] [--publisher] [--category] [--tag]
          [--year-from] [--year-to] [--rating-min] [--status]
          [--location] [--available] [--sort] [--limit] [--offset]
   lend ID --borrower 张三 [--contact 138...] [--due 2024-06-01]
   return ID [--on 2024-05-20]
   loans [--overdue] [--borrower 张三]
   read ID --status 在读 [--rating 4] [--note "..."] [--started D] [--finished D]
   stats [--by category|publisher|year|status]
   export --format csv|json -o PATH [--include-loans]
   import PATH --format csv|json [--dry-run]

   函数签名：
   def isbn13_check_digit(first12: str) -> str
   def validate_isbn(raw: str) -> tuple[str | None, str | None, str | None]
       # 返回 (isbn13, isbn10, error_message)
   def fetch_metadata(isbn13: str, timeout: float = 10.0) -> dict | None
   def search_books(repo, query: SearchQuery) -> list[Book]
   def natural_key(text: str) -> tuple

【五、运行方式与示例】

安装：
  cd C:\projects\100programs\055_book_library
  pip install requests            （可选）
  python -m library init

示例一（ISBN 联网补全录入）：
  输入：python -m library add --isbn 9787115428028 --location A3-2 --tags 计算机,经典
  输出：
        已校验 ISBN-13：9787115428028（合法）
        查询到书目：代码大全（第2版） / Steve McConnell / 电子工业出版社 / 2016
        已保存 #1 代码大全（第2版）  位置 A3-2  状态 未读

示例二（多条件检索与借阅）：
  输入：python -m library search --author 费曼 --status 已读 --rating-min 4 --sort rating
  输出：
        ID  书名                 作者        出版年  分类     位置   状态  评分
        7   费曼物理学讲义        R.费曼      2013    物理     B1-1   已读   5
  输入：python -m library lend 7 --borrower 张三 --contact 138****0000 --due 2024-06-01
  输出：已登记借出：费曼物理学讲义 → 张三（应还 2024-06-01，剩余 29 天）
  输入：python -m library lend 7 --borrower 李四
  输出：错误：该书尚未归还，当前借阅人为 张三（借出 2024-05-03）  （退出码 2）

示例三（逾期查看与异常输入）：
  输入：python -m library loans --overdue
  输出：ID 7  费曼物理学讲义  借阅人 张三  借出 2024-05-03  应还 2024-06-01  逾期 3 天
  输入：python -m library add -t 测试书 -a 某人 --isbn 9787115428020
  输出：错误：ISBN-13 校验位应为 8，实际 0（如确需保存请加 --force）（退出码 2）
  输入：python -m library return 7 --on 2024-04-01
  输出：错误：归还日期 2024-04-01 早于借出日期 2024-05-03      （退出码 2）

【六、验收标准】

[ ] ISBN-10 与 ISBN-13 的合法样例全部通过校验，各准备 3 个非法样例全部被拒。
[ ] 含连字符与空格的 ISBN 输入能正确归一化（如 978-7-115-42802-8）。
[ ] ISBN-10 能正确换算为 ISBN-13，且换算结果再次通过 13 位校验。
[ ] 关闭网络（--offline）时 add 仍可手工录入，程序不因网络异常崩溃。
[ ] 外部查询失败时打印明确提示，且不产生半截脏数据。
[ ] 一本书录两个作者后，按任一作者都能检索到该书。
[ ] 同一本书打多个标签后，按任一标签都能检索到该书。
[ ] 借出后该书在 --available 检索中不出现，归还后重新出现。
[ ] 同一本书在未归还状态下再次 lend 被拒绝，且数据库无第二条未归还记录。
[ ] 部分唯一索引直接 INSERT 第二条未归还记录时报 IntegrityError。
[ ] 归还时 overdue_days 正确固化，逾期 3 天的样例验证通过。
[ ] 位置自然序：A2 排在 A10 之前（用 search --sort location 验证）。
[ ] 出版社含中文与英文混合时检索不漏结果。
[ ] 导出 CSV 用 Excel 打开中文不乱码，列顺序与本说明一致。
[ ] stats 分类分布条形图长度比例与数据库实际计数一致（误差不超过 1%）。
[ ] 导入含重复 ISBN 的 CSV 时，插入行数与跳过行数之和等于文件总行数。

【七、可选扩展】

1. 从豆瓣/图书馆 API 补充封面与简介（注意遵守其服务条款与限速要求）。
2. 生成可打印的书架标签（结合 033 二维码项目，扫码直达图书详情）。
3. 增加“购书清单”模块：想读 + 价格 + 电商链接，导出为采购表。
4. 增加借阅催还提醒：逾期时生成邮件正文或 webhook 推送。
5. 增加藏书 Excel 报表：分类分布、年度入藏、已读比例图表（openpyxl + 图表）。
6. 数据量大时迁移到 SQLite FTS5 全文索引，支持书名与读后感的全文检索。

【八、涉及知识点】

- 数据库多值属性建模：一对多关联表、复合主键、外键级联删除。
- 部分唯一索引（partial index）表达“至多一条未归还记录”的业务约束。
- 校验位算法：ISBN-10 的加权模 11 与 ISBN-13 的模 10；Luhn 类算法思想。
- HTTP 客户端基础：urllib.request / requests、timeout、重试与指数退避、
  User-Agent 与 JSON 响应解析。
- 动态查询构造：参数化 SQL、条件拼接、排序白名单与 SQL 注入防御。
- 自然排序：正则切分数字段生成混合排序键。
- 数据导入导出：CSV 编码（utf-8-sig）、列映射、去重与幂等。
- 统计聚合：GROUP BY 计数、百分比换算、文本条形图渲染。
- 命令行工具工程化：子命令划分、--json 输出、日志与错误码约定。
================================================================================
