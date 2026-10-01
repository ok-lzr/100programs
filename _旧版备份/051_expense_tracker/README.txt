================================================================================
项目编号：051                    难度等级：★★★☆☆（中型项目）
项目名称：个人记账本
所属分类：个人数据管理 / 命令行 + SQLite 应用
建议工时：2 ~ 4 天
运行环境：Python 3.10+    第三方依赖：openpyxl（可选，用于导出 Excel）
================================================================================

【一、项目背景与目标】

多数人记账失败不是因为不想记，而是因为记一笔太麻烦、看报表太麻烦。手机记账
App 往往强制注册账号、上传数据、塞满广告，还要把消费明细交给第三方服务器。
本项目的目标是用一个本地 SQLite 数据库 + 命令行交互，把“记一笔”压缩到一行
命令，把“看这个月花了多少”压缩到一行命令，数据完全留在自己电脑上。

目标用户是愿意用键盘记账的开发者、学生和自由职业者：他们希望月底能导出 CSV
丢进 Excel 自己再加工，也希望给餐饮、交通、购物分别设置预算，超支时被提醒。

做成之后可以拿到的能力：随时用 `add` 记录一笔支出或收入；用 `report` 查看任意
月份的收支总额、分类占比与预算执行情况；用 `budget` 设定每类月度额度；用
`export` 把任意时间区间导出为 CSV 或 Excel 交给会计或家人核对。

项目难点不在语法，而在数据建模与统计口径：金额必须用整数分存储避免浮点误差，
分类与账户要能改名而不破坏历史数据，跨月查询要处理时区与月初月末边界。

【二、功能需求清单】

1. 核心功能
   1.1 记账（add）：输入金额、类型（expense/income）、分类、账户、日期、备注，
       写入 transactions 表并返回新记录 ID；金额支持 “35”、“35.5”、“35.50”
       三种写法，内部统一转为整数分（3500 / 3550）。
   1.2 查询明细（list）：按时间区间、分类、账户、类型、关键词组合过滤，默认
       显示最近 20 条，支持 --limit/--offset 分页，输出表格化对齐文本。
   1.3 修改与删除（edit/remove）：edit 按 ID 局部更新字段；remove 按 ID 删除，
       删除前打印待删记录并要求 --yes 确认，避免误删。
   1.4 分类管理（category）：新增、改名、停用、列出分类；停用（active=0）的
       分类不出现在下拉提示中，但历史记录仍保留原分类名。
   1.5 预算管理（budget）：为“分类 + 年月”设置额度，支持全局默认额度；
       预算表独立于交易表，删除分类不影响已有预算记录。
   1.6 统计报表（report）：按月或按自定义区间输出总收入、总支出、净结余、
       各分类金额与占比、日均支出、预算剩余与超支标记。
   1.7 导出（export）：导出 CSV（UTF-8 with BOM，Excel 直接可读）或 XLSX
       （openpyxl，含表头加粗、冻结首行、金额列数字格式）。
   1.8 导入（import）：从 CSV 批量导入历史账单，按“日期+金额+分类+备注”判定
       重复，重复行写入跳过日志而非直接报错中止。

2. 输入与交互
   2.1 全部命令通过 argparse 子命令实现，形如
       `python -m expense add -a 35.5 -c 餐饮 --account 微信 -d 2024-05-03 -n 午饭`。
   2.2 日期参数支持 `2024-05-03`、`2024/5/3`、`today`、`yesterday`，
       统一解析为 ISO 日期字符串后入库。
   2.3 金额、日期、类型、分类名缺失时给出明确错误并退出码 2；分类不存在时
       提示最接近的候选（基于 difflib.get_close_matches）。
   2.4 支持 `--db PATH` 覆盖默认数据库路径，默认位于
       `~/.expense_tracker/expense.db`，首次运行自动建库建表。
   2.5 交互模式（`python -m expense shell`）逐行读取命令，支持上下文的
       “再记一笔”快捷输入与 `exit` 退出，避免反复启动解释器。

3. 输出与展示
   3.1 明细列表按列对齐输出：ID、日期、类型、分类、账户、金额、备注；
       中文列宽按显示宽度（East Asian Width）计算，避免表格错位。
   3.2 报表输出含：区间、收入合计、支出合计、结余、记录数、日均支出、
       分类明细表（金额 / 占比 / 笔数 / 预算 / 剩余 / 是否超支）。
   3.3 超支时在报表末尾输出醒目提示行，如
       `[超支] 餐饮 预算 1500.00 实际 1720.50 超出 220.50`。
   3.4 所有金额对用户展示时保留两位小数，内部一律整数分。

4. 异常与边界处理
   4.1 金额为 0 或负数：拒绝，提示“金额必须大于 0，方向请用 --type 指定”。
   4.2 金额超过两位小数：截断还是报错需明确——本项目选择报错，提示精度限制。
   4.3 日期晚于今天：允许（用于补记未来计划支出），但在 list 中以 “[未来]” 标记。
   4.4 区间反转（start > end）：自动交换并给出提示，不报错。
   4.5 数据库被占用或只读：捕获 sqlite3.OperationalError，输出可读建议后退出码 3。
   4.6 导出路径已存在：默认覆盖，`--no-clobber` 时改为报错退出。
   4.7 空数据月份报表：输出“该区间无记录”，退出码 0，不得抛异常。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用 `X | None` 类型注解写法。
2. 允许使用的库：
   2.1 标准库：sqlite3、argparse、csv、datetime、decimal、pathlib、logging、
       dataclasses、typing、unicodedata（用于中文列宽）、difflib、json。
   2.2 第三方：openpyxl（仅用于 XLSX 导出，可选依赖，缺失时 export --format xlsx
       给出安装提示并降级为 CSV）。
   2.3 禁止引入 ORM 框架，本项目要求手写 SQL 以练习索引与事务。
3. 禁止事项：禁止用 float 存储金额；禁止在 SQL 中使用字符串拼接参数
   （必须用占位符 `?`）；禁止把数据库提交藏在循环里逐条 commit。
4. 代码组织：
   - `db.py`：连接管理、建表迁移（schema_version 表）、事务封装。
   - `models.py`：dataclass 定义 Transaction、Category、Account、Budget。
   - `repository.py`：全部 SQL 语句集中于此，返回 dataclass，不返回裸 tuple。
   - `services.py`：业务规则（预算校验、去重判定、统计口径）。
   - `cli.py`：argparse 定义与命令分发，不含 SQL。
   - `report.py`：报表与表格渲染。
   - `exporters.py`：CSV / XLSX 导出与 CSV 导入。
5. 编码规范：全部公开函数带类型注解与 docstring；使用 logging 输出调试信息，
   用户可见结果用 print；常量单独定义（如 DB_PATH、SCHEMA_VERSION）；禁止
   使用裸 except；每个模块 `if __name__ == "__main__"` 仅出现在入口。

【四、设计要点】

1. 数据结构（SQLite 表结构，全部字段非空约束按需设置）

   1.1 accounts（账户表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       name          TEXT NOT NULL UNIQUE          -- 如 微信 / 支付宝 / 现金 / 招行卡
       kind          TEXT NOT NULL DEFAULT 'cash'  -- cash / debit / credit / virtual
       initial_balance_cents INTEGER NOT NULL DEFAULT 0
       active        INTEGER NOT NULL DEFAULT 1    -- 0 表示停用
       created_at    TEXT NOT NULL                 -- ISO8601 字符串

   1.2 categories（分类表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       name          TEXT NOT NULL
       parent_id     INTEGER NULL REFERENCES categories(id) ON DELETE SET NULL
       kind          TEXT NOT NULL DEFAULT 'expense' -- expense / income
       active        INTEGER NOT NULL DEFAULT 1
       sort_order    INTEGER NOT NULL DEFAULT 0
       约束：UNIQUE(name, kind)

   1.3 transactions（交易表，核心表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       occurred_on   TEXT NOT NULL     -- 'YYYY-MM-DD'
       type          TEXT NOT NULL     -- 'expense' | 'income'
       amount_cents  INTEGER NOT NULL CHECK (amount_cents > 0)
       category_id   INTEGER NOT NULL REFERENCES categories(id)
       account_id    INTEGER NOT NULL REFERENCES accounts(id)
       note          TEXT NOT NULL DEFAULT ''
       created_at    TEXT NOT NULL
       updated_at    TEXT NOT NULL
       索引：idx_tx_date(occurred_on)、idx_tx_cat(category_id, occurred_on)、
             idx_tx_acct(account_id, occurred_on)、idx_tx_type(type, occurred_on)
       说明：type 用 CHECK(type IN ('expense','income')) 约束；
             amount_cents 恒为正数，收支方向由 type 决定，避免正负号混乱。

   1.4 budgets（预算表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       category_id   INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE
       period        TEXT NOT NULL     -- 'YYYY-MM' 或 'default' 表示每月默认
       limit_cents   INTEGER NOT NULL CHECK (limit_cents >= 0)
       约束：UNIQUE(category_id, period)

   1.5 import_log（导入日志表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       source_file   TEXT NOT NULL
       imported_at   TEXT NOT NULL
       total_rows    INTEGER NOT NULL
       inserted_rows INTEGER NOT NULL
       skipped_rows  INTEGER NOT NULL
       detail        TEXT NOT NULL DEFAULT ''   -- JSON：跳过行号与原因

   1.6 schema_version（迁移版本表）
       version       INTEGER PRIMARY KEY
       applied_at    TEXT NOT NULL

2. 关键算法或流程
   2.1 金额解析：`parse_amount("35.5")` → 校验正则 `^\d+(\.\d{1,2})?$`
       → Decimal 乘 100 → int；拒绝负数、科学计数法与超两位小数。
   2.2 月度报表：
       步骤一，解析 period 为 [first_day, next_month_first_day) 半开区间；
       步骤二，一次 SQL 聚合出 SUM(CASE WHEN type='expense' ...) 得到收支合计；
       步骤三，按 category_id 分组聚合出各分类金额与笔数，再 JOIN categories；
       步骤四，LEFT JOIN budgets 取本期额度（无本期则取 period='default'）；
       步骤五，占比 = 分类金额 / 支出合计，四舍五入到 0.1%；
       步骤六，日均支出 = 支出合计 / 区间内实际天数（含首尾）。
   2.3 去重导入：把 (occurred_on, amount_cents, category_name, note) 归一化后
       计算 sha256 前 16 位作为 fingerprint 存入内存集合，逐行比对；同一文件
       内部也去重。
   2.4 事务边界：一次 add 操作提交一次；import 每 200 行提交一次并记录检查点，
       中途失败时已提交批次保留，日志写明处理到第几行。

3. 命令行接口设计（子命令与关键参数）

   add     -a/--amount 必填  -c/--category 必填  -t/--type 默认 expense
           --account 默认“现金”  -d/--date 默认 today  -n/--note 可选
   list    --from --to --category --account --type -k/--keyword
           --limit 默认 20  --offset 默认 0  --format {table,csv,json}
   edit    ID  --amount --category --account --date --note  （至少给一个）
   remove  ID [ID ...]  --yes
   category 子命令：add / rename / disable / enable / list [--tree]
   account  子命令：add / rename / disable / list
   budget   子命令：set -c CAT -p YYYY-MM -l 1500 / list -p YYYY-MM / remove
   report   子命令：month -p YYYY-MM / range --from --to / year -y 2024
   export   --from --to --format {csv,xlsx} -o PATH [--no-clobber]
   import   PATH --format csv --encoding utf-8-sig [--dry-run]

   函数签名示例：
   def add_transaction(conn, occurred_on: str, type_: str, amount_cents: int,
                       category_id: int, account_id: int, note: str) -> int
   def month_report(conn, period: str) -> MonthReport
   def export_csv(conn, start: str, end: str, path: Path) -> int

【五、运行方式与示例】

安装与初始化：
  cd C:\projects\100programs\051_expense_tracker
  python -m venv .venv && .venv\Scripts\activate
  pip install openpyxl            （可选，仅 XLSX 导出需要）
  python -m expense init          （创建数据库与默认分类：餐饮/交通/购物/居住/医疗）

示例一（记一笔并查看本月报表）：
  输入：python -m expense add -a 35.5 -c 餐饮 --account 微信 -d today -n "公司楼下快餐"
  输出：已记录 #1  2024-05-03  支出  餐饮  微信  35.50  公司楼下快餐
  输入：python -m expense report month -p 2024-05
  输出：
        区间：2024-05-01 ~ 2024-05-31（31 天）
        收入合计：12000.00    支出合计：35.50    净结余：11964.50
        日均支出：1.15        记录数：1
        分类      金额      占比    笔数   预算      剩余      状态
        餐饮      35.50    100.0%    1    1500.00   1464.50   正常

示例二（设预算后超支提醒）：
  输入：python -m expense budget set -c 餐饮 -p 2024-05 -l 30
  输出：已设置 餐饮 2024-05 预算 30.00
  输入：python -m expense add -a 12.00 -c 餐饮 -d 2024-05-04 -n 早餐
  输入：python -m expense report month -p 2024-05
  输出末尾：[超支] 餐饮  预算 30.00  实际 47.50  超出 17.50

示例三（导出与异常输入）：
  输入：python -m expense export --from 2024-05-01 --to 2024-05-31 --format csv -o may.csv
  输出：已导出 2 条记录到 may.csv（UTF-8 BOM）
  输入：python -m expense add -a 35.555 -c 餐饮
  输出：错误：金额最多支持两位小数，收到 “35.555”          （退出码 2）
  输入：python -m expense add -a 20 -c 餐钦
  输出：错误：分类 “餐钦” 不存在，是否想输入 “餐饮”？      （退出码 2）
  输入：python -m expense remove 1
  输出：待删除：#1 2024-05-03 支出 餐饮 微信 35.50；加 --yes 确认删除（退出码 1）

【六、验收标准】

[ ] 首次运行 `python -m expense init` 能自动创建数据库、6 张表与默认分类，重复执行不报错。
[ ] `add` 写入后 `list` 能查到该记录，金额显示为两位小数，数据库内为整数分。
[ ] 浮点陷阱自测：连续 add 0.1、0.2、0.3 三笔后报表支出合计精确等于 0.60。
[ ] `list` 的组合过滤（区间 + 分类 + 类型）返回结果与手写 SQL 结果一致。
[ ] 中文备注与中文分类名在明细列表中列宽对齐，无错位。
[ ] `budget set` 后报表能显示预算、剩余与超支标记；未设预算的分类显示“未设置”。
[ ] 预算为 0 时任何一笔支出都判定为超支，且不出现除零错误。
[ ] `report range --from 2024-05-31 --to 2024-05-01` 自动交换区间并正常出报表。
[ ] 空区间报表输出“该区间无记录”，退出码 0。
[ ] 导出 CSV 用 Excel 打开中文不乱码；导出 XLSX 首行冻结且金额为数值格式。
[ ] 重复导入同一份 CSV 两次，第二次 inserted_rows 为 0 且 skipped_rows 等于总行数。
[ ] `remove` 未加 --yes 时不删除任何数据，退出码为 1。
[ ] 删除被引用的分类时报错而非产生孤儿记录（外键约束生效）。
[ ] 单元测试覆盖金额解析、区间解析、月报聚合三类核心逻辑，pytest 全部通过。
[ ] `python -m expense --help` 与每个子命令 `-h` 均有可读中文说明。

【七、可选扩展】

1. 增加周期性账单（房租、订阅）模板，每月 1 日自动生成待确认记录。
2. 增加多币种支持：transactions 增加 currency 与 rate_to_cny 字段，报表按汇率折算。
3. 用 rich 渲染带颜色和进度条的预算看板。
4. 增加 `stats trend` 输出最近 12 个月收支柱状趋势（matplotlib 或纯文本条形图）。
5. 支持 SQLCipher 或对数据库文件做 AES 加密，保护隐私。

【八、涉及知识点】

- sqlite3 模块：连接、游标、事务提交、外键 `PRAGMA foreign_keys=ON`、索引与 EXPLAIN。
- 金额精度：Decimal 与整数分存储，浮点误差的来源与规避。
- 数据库设计：范式化、外键、CHECK 约束、唯一约束、半开区间查询。
- argparse 子命令（add_subparsers）与参数校验。
- dataclass、类型注解、模块分层（repository / service / cli）。
- 文本表格对齐：unicodedata.east_asian_width 计算中文显示宽度。
- CSV 编码问题：UTF-8 BOM 与 utf-8-sig、Excel 打开乱码的原因。
- openpyxl 基础：写入单元格、设置数字格式、冻结窗格。
- 日志与错误处理：自定义异常、退出码约定、logging 分级。
================================================================================
