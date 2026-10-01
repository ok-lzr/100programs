================================================================================
项目编号：009                    难度等级：★☆☆☆☆（小型项目）
项目名称：命令行待办清单
所属分类：命令行工具 / 个人数据管理
建议工时：5 ~ 7 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

待办事项 App 很多，但打开手机就是刷半小时；而在终端里写代码的人，最顺手的地方就是
命令行。这个工具用一个 JSON 文件保存待办，支持添加、列出、完成、修改、删除、设置优先级
与截止日期，并且能自动标出今天到期与已逾期的事项。

目标用户是常年在终端工作的开发者、需要轻量清单的学生、以及学习文件持久化与数据建模的
初学者。设计重点是：数据文件必须是可读可手改的 JSON；任何写操作都要先写临时文件再原子
替换，避免中途崩溃把清单写坏。

做完之后应当能拿来干这些事：一条命令加一条 “周五前交周报” 并设高优先级和截止日期；
用 todo ls --today 只看今天要做的；用 todo done 3 完成编号 3 的任务；用 todo stats 看
完成率与逾期数量。

【二、功能需求清单】

1. 核心功能
   1.1 添加（add）：指定标题，可选 --priority high/medium/low、--due 2024-06-01、
       --tag 工作、--note 备注。
   1.2 列出（ls）：按状态、优先级、标签、截止日期筛选，支持排序与分页。
   1.3 完成（done）：按编号把一个或多个任务标记为完成，记录完成时间。
   1.4 撤销（undone）：把已完成任务改回未完成。
   1.5 修改（edit）：修改标题、优先级、截止日期、标签、备注。
   1.6 删除（rm）：删除任务，需 --force 才真正删除，否则先移入回收站字段。
   1.7 清理（clean）：移除已删除任务或已完成超过 N 天的任务。
   1.8 搜索（find）：按关键字在标题与备注中搜索。
   1.9 统计（stats）：未完成数、已完成数、完成率、逾期数、今日到期数、
       按优先级分布。
   1.10 导出（export）：导出为 CSV 或 Markdown 清单。

2. 输入与交互
   2.1 命令形式：python todo.py <子命令> [参数]，例如 python todo.py add "写周报"。
   2.2 数据文件：默认 ./todo.json；--file 指定其它路径；环境变量 TODO_FILE 优先级低于
       --file、高于默认值。
   2.3 编号规则：编号为自增整数，删除后不复用；ls 默认只显示未完成项。
   2.4 筛选参数：--all、--done、--today、--overdue、--tag 工作、--priority high。
   2.5 排序参数：--sort due|priority|created|id，--reverse 反向。
   2.6 分页：--page 2 --size 10。
   2.7 日期格式：--due 支持 2024-06-01、06-01（当年）、today、tomorrow、+3
       （三天后）五种写法。
   2.8 子命令别名：ls/list、add/a、done/d、rm/delete、edit/e、find/f。
   2.9 交互模式：python todo.py 无子命令时进入简易菜单，可连续操作直到输入 q。

3. 输出与展示
   3.1 列表格式（对齐的表格化纯文本）：
       ID  状态  优先级  截止日期    标签   标题
        3  [ ]   high    2024-06-01  工作   写周报
        2  [x]   low     -           生活   买菜
   3.2 逾期项标题后缀标 “（已逾期 2 天）”，今日到期标 “（今天到期）”，
       高优先级用大写 HIGH 表示，不使用颜色转义（保证日志可读）。
   3.3 添加成功：已添加 #4：写周报（high，截止 2024-06-01）
   3.4 完成成功：已完成 #3：写周报（用时 3 天）
   3.5 统计输出：
       未完成 7，已完成 13，完成率 65.0 %
       逾期 2，今日到期 1
       高优先级未完成 3
   3.6 导出 CSV 表头：id,title,status,priority,due,tags,note,created_at,done_at。
   3.7 --json 时所有子命令输出 JSON 对象，便于脚本消费。

4. 异常与边界处理
   4.1 数据文件不存在时首次运行自动创建空结构 {"version":1,"next_id":1,"items":[]}。
   4.2 数据文件 JSON 损坏时打印 “错误：todo.json 解析失败（第 5 行）：……”，
       并提示用 --backup 恢复或手动修复，退出码 3。
   4.3 文件结构缺少必需键时自动补齐缺失键（如 version、next_id），并打印警告。
   4.4 编号不存在时打印 “错误：不存在编号 99 的待办”，退出码 2。
   4.5 编号非数字时打印 “错误：编号必须是整数”。
   4.6 标题为空或全为空白时拒绝添加，打印 “错误：标题不能为空”。
   4.7 标题超过 200 字符时截断并提示。
   4.8 日期格式非法时打印支持的五种写法示例。
   4.9 写入失败（磁盘只读或权限不足）时保留原文件内容不变，退出码 4。
   4.10 同一标题且未完成的项已存在时提示 “已存在相同标题的未完成待办 #3”，
        需加 --force 才重复添加。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库，需要 argparse、json、csv、os、sys、datetime、
   pathlib、tempfile、dataclasses、typing、logging。
3. 禁止事项：禁止用字符串拼接生成 JSON；禁止直接 open(..., "w") 原地覆盖数据文件
   （必须写临时文件后 os.replace 原子替换）；禁止把标题、备注写进日志；
   禁止使用 pickle 等二进制私有格式。
4. 代码组织：
   4.1 模型：TodoItem dataclass，字段 id、title、status（open/done/trash）、
       priority、due（date 或 None）、tags: list[str]、note、created_at、done_at、
       updated_at。所有时间统一为 ISO 8601 字符串。
   4.2 存储层：TodoStore 类，方法 load()、save()、add()、get(id)、update(id, **fields)、
       remove(id)、list(filters, sort, page) -> list[TodoItem]、all()。
   4.3 业务层：纯函数或独立模块函数，如 search_items、compute_stats、
       parse_due(text, today) -> date。
   4.4 视图层：format_table(items)、format_item(item)、to_csv_rows(items)、
       to_markdown(items)。
   4.5 命令分派：build_parser() 用 subparsers 定义 8 个子命令；main() 只做分派。
5. 编码规范：类型注解与 docstring；写入时 json.dump(..., ensure_ascii=False,
   indent=2)；所有路径使用 pathlib.Path；时间比较禁止用字符串比较代替 date 比较。

【四、设计要点】

1. 数据结构：
   1.1 文件顶层：{"version": 1, "next_id": 5, "items": [ {...}, ... ]}。
   1.2 TodoItem 各字段均为可 JSON 序列化基础类型；due 存 "YYYY-MM-DD" 字符串，
       读入时转 datetime.date 便于比较。
   1.3 优先级排序权重：high=0、medium=1、low=2，无优先级排最后。
2. 关键算法或流程：
   2.1 加载流程：读文件 -> json.loads -> 校验顶层类型 -> 补全缺失键 -> 把 items
       转成 TodoItem 列表；失败时抛出 StoreError 并由 main 统一处理。
   2.2 保存流程：在同目录创建 NamedTemporaryFile 写入 -> flush + os.fsync ->
       os.replace 覆盖原文件；异常时删除临时文件并保留原文件。
   2.3 筛选流程：按 status 过滤（默认 open）-> 按 tag、priority 过滤 ->
       按 due 过滤（today 表示 due == 今天；overdue 表示 due < 今天且未完成）->
       排序 -> 分页切片。
   2.4 排序规则：due 排序时 None 排最后；相同 due 时按优先级、再按 id。
   2.5 相对日期解析：today、tomorrow、+N（N 为整数天数）、MM-DD（补当年，
       若已过去则视为明年）、YYYY-MM-DD。
   2.6 统计流程：遍历所有非 trash 项，统计各指标，完成率 = 已完成 / 总数 × 100%，
       总数为 0 时输出 0.0 %。
3. 接口或命令设计：
   3.1 TodoStore.add(title, priority, due, tags, note) -> TodoItem
   3.2 TodoStore.list(status="open", tag=None, priority=None, due_filter=None,
       sort="id", reverse=False, page=1, size=20) -> list[TodoItem]
   3.3 TodoStore.update(item_id: int, **fields) -> TodoItem
   3.4 parse_due(text: str, today: date) -> date
   3.5 compute_stats(items: list[TodoItem]) -> Stats
   3.6 子命令：add、ls、done、undone、edit、rm、clean、find、stats、export。

【五、运行方式与示例】

1. 运行准备：无需安装依赖；可选设置 set TODO_FILE=C:\data\todo.json 指定数据文件位置。
2. 添加任务：
   python todo.py add "写周报" --priority high --due 2024-06-01 --tag 工作
   输出：已添加 #1：写周报（high，截止 2024-06-01）
3. 再添加两条并列出：
   python todo.py add "买菜" --priority low --due today
   python todo.py add "预约体检" --due +3
   python todo.py ls
   输出：
   ID  状态  优先级  截止日期    标签   标题
    1  [ ]   high    2024-06-01  工作   写周报
    2  [ ]   low     2024-05-20  生活   买菜（今天到期）
    3  [ ]   -       2024-05-23  -      预约体检
4. 完成与撤销：
   python todo.py done 2
   输出：已完成 #2：买菜（用时 0 天）
   python todo.py undone 2
   输出：已恢复 #2：买菜
5. 筛选与排序：
   python todo.py ls --today
   输出：只列出今天到期的任务。
   python todo.py ls --all --sort priority --reverse
   输出：按优先级倒序排列的全部任务。
6. 搜索：
   python todo.py find 周报
   输出：包含关键字“周报”的待办 1 条，含匹配位置高亮说明。
7. 统计：
   python todo.py stats
   输出：
   未完成 2，已完成 1，完成率 33.3 %
   逾期 0，今日到期 1
   高优先级未完成 1
8. 导出：
   python todo.py export --format csv --output todo.csv
   输出：已导出 3 条到 todo.csv
9. 删除（需确认）：
   python todo.py rm 3
   输出：已移入回收站 #3：预约体检（使用 --force 可彻底删除）
   python todo.py clean --done-before 30
   输出：已清理 0 条已完成超过 30 天的待办。
10. 异常输入示例：
    python todo.py done 99
    输出：错误：不存在编号 99 的待办
    退出码：2
    python todo.py add "   "
    输出：错误：标题不能为空
    退出码：2
    python todo.py add "写周报" --due 6月1日
    输出：错误：日期格式无法识别，支持 2024-06-01 / 06-01 / today / tomorrow / +3

【六、验收标准】

[ ] 首次运行自动创建 todo.json 且内容为合法 JSON
[ ] add 返回的新编号严格自增且删除后不复用
[ ] ls 默认只显示未完成项，--all 显示全部
[ ] --today 只显示今天到期，--overdue 只显示已逾期且未完成的项
[ ] --tag 与 --priority 可组合筛选
[ ] --sort due 时无截止日期的项排在最后
[ ] --page 与 --size 分页结果正确且不重复
[ ] done 记录完成时间，undone 清除完成时间
[ ] rm 不带 --force 时只移入回收站，不带参数时数据仍在文件中
[ ] clean 能按天数清理已完成项
[ ] 五种日期写法（绝对日期、MM-DD、today、tomorrow、+N）全部被正确解析
[ ] stats 的完成率计算正确，总数为 0 时不出现除零
[ ] export CSV 表头与约定完全一致且中文不乱码
[ ] JSON 文件损坏时给出含行号的错误并返回退出码 3
[ ] 保存过程使用临时文件加 os.replace，中途失败原文件不受损
[ ] 标题重复时需 --force 才允许添加
[ ] 全程仅使用标准库，未使用 pickle

【七、可选扩展】

1. 增加子任务与依赖（--depends 3 表示完成 #3 前提示依赖未完成）。
2. 增加重复任务（--repeat daily/weekly）并在完成时自动生成下一次。
3. 增加 --priority 自动排序与“今日聚焦”模式，只显示最紧急的 3 条。
4. 增加 ICS 导出，把带截止日期的待办导入日历软件。
5. 增加 JSON 与 CSV 双向导入（import 子命令）。
6. 增加文件锁（fcntl 或 msvcrt.locking）避免多个终端同时写坏数据。

【八、涉及知识点】

- JSON 读写与 ensure_ascii=False 的中文处理
- 原子写入：临时文件 + os.replace
- dataclass 与日期时间的序列化、反序列化
- datetime.date 与字符串比较的陷阱
- argparse subparsers 实现多子命令 CLI
- 列表推导、sorted 的 key 函数与多级排序
- 筛选、分页、搜索的常见实现套路
- 文件锁与并发写入的初步认识
- 数据文件版本字段与向前兼容设计
================================================================================
