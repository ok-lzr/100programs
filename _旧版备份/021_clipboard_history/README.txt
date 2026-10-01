================================================================================
项目编号：021                    难度等级：★★☆☆☆（小型项目）
项目名称：剪贴板历史管理器
所属分类：文件与文本处理 / 系统小工具
建议工时：3 ~ 5 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】
日常在编辑器、浏览器、终端之间来回切换时，剪贴板只有一份内容：复制了新的地址，
刚才那串订单号就没了，只能翻回去重新复制。系统自带的剪贴板历史在部分环境下不
可用或搜不到内容，也无法按类型过滤、无法导出。本项目做一个跨平台的命令行剪贴
板历史管理器，后台常驻监听剪贴板变化，把每一次复制的内容落盘保存。

目标用户是经常处理文本片段的开发者、客服、运营和写作人员。做出来之后，你可以
用一条命令翻出十分钟前复制的 JSON 片段，用关键字模糊搜到某个订单号，把历史里
的某一条重新放回剪贴板，或者在离开工位前导出这一天的复制记录做归档。

本项目刻意只使用 Python 标准库，剪贴板读写依赖 tkinter 的 clipboard 接口，因此
不需要安装 pyperclip 之类的第三方包，适合用来练习多线程、哈希去重与本地持久化。

【二、功能需求清单】
1. 核心功能
   1.1 剪贴板监听：以固定间隔（默认 0.5 秒）读取剪贴板文本，与上一条记录比较，
       内容有变化才产生新记录，相同内容连续读取不重复入库。
   1.2 去重策略：对内容计算 SHA-256 作为指纹；默认策略为「相邻去重」，即与上一
       条相同则丢弃；开启 --dedup-global 时，若历史中已存在相同指纹，则只更新该
       条记录的 last_seen 时间与出现次数 count，不新增条目。
   1.3 类型识别：对每条内容自动打标签，规则为 URL（以 http:// 或 https:// 开头且
       可被 urllib.parse 解析出 host）、文件路径（Path 存在且为文件）、JSON（能
       json.loads 成功）、代码片段（含 def/class/import/;/{} 等特征且长度大于 40）、
       普通文本；标签写入 kind 字段。
   1.4 历史查询：支持列出最近 N 条、按关键字全文搜索、按类型过滤、按时间范围过滤。
   1.5 一键回填：把指定 id 的内容重新写入系统剪贴板，并打印已回填内容的前 80 个
       字符作为确认。
   1.6 收藏与清理：可把条目标记为星标（starred），清理时默认跳过星标条目。
   1.7 敏感内容保护：内容命中内置敏感词规则（如 password、token、secret、身份证
       号 18 位数字）时，列表展示只显示前 4 位与后 4 位，中间用 * 遮蔽，并标记
       sensitive 为 true，除非显式加 --show-sensitive。

2. 输入与交互
   2.1 子命令共 6 个：watch（前台监听）、list（列表）、search（搜索）、copy（回填）、
       star（收藏）、clear（清理）。
   2.2 watch 默认前台运行，Ctrl+C 退出并打印本次新增记录条数。
   2.3 所有查询子命令支持 --limit 参数，默认 20，取值范围 1 ~ 1000。
   2.4 搜索关键字为空字符串时报错退出，退出码 2。
   2.5 交互式翻页：list 与 search 在开启 --pager 时，每满 20 条暂停并等待回车
       继续，输入 q 提前结束。

3. 输出与展示
   3.1 列表格式为固定列宽文本，列依次为：id（右对齐 6 位）、时间（YYYY-MM-DD
       HH:MM:SS）、类型（左对齐 8 位）、次数（右对齐 3 位）、预览（最多 60 字符，
       超出用省略号截断，内部换行符替换为空格）。
   3.2 搜索结果中用方括号高亮命中片段，例如 [订单号]。
   3.3 空结果显示「没有匹配的剪贴板记录」，退出码 0。
   3.4 每条记录额外提供 --verbose 模式，打印完整内容、指纹前 12 位、首次与最后
       出现时间。

4. 异常与边界处理
   4.1 剪贴板为空或内容不是文本（例如复制了图片）时跳过，不报错。
   4.2 单条内容超过 100 KB 时按 max_chars 配置截断保存，并在记录中标记 truncated。
   4.3 历史文件损坏（JSON 解析失败）时，自动把原文件重命名为 history.bad.<时间戳>
       并新建空文件，同时在日志中给出警告。
   4.4 历史条数超过上限（默认 5000）时，按时间从旧到新淘汰非星标记录。
   4.5 无图形环境（tkinter 初始化失败）时，watch 子命令提示「当前环境不支持剪贴
       板访问」并以退出码 3 结束，其余查询类子命令仍可正常使用。
   4.6 copy 指定的 id 不存在时输出错误并返回退出码 4。

【三、技术要求与约束】
1. 语言与版本：Python 3.10 及以上，使用 match 语句处理子命令分发。
2. 允许使用的库：仅使用标准库。剪贴板用 tkinter（Tk().clipboard_get /
   clipboard_clear / clipboard_append），命令行参数用 argparse，存储用 json，
   哈希用 hashlib，并发状态同步用 threading.Lock，日志用 logging。
3. 禁止事项：禁止引入第三方依赖；禁止把历史文件写到用户目录之外的路径；禁止
   在网络上传送任何剪贴板内容；禁止把完整敏感内容写入日志文件。
4. 代码组织：至少拆分为以下模块——clipboard.py（ClipboardIO 封装读写与可用性
   探测）、store.py（HistoryStore 负责加载、追加、查询、清理、落盘）、classify.py
   （classify_kind 与 is_sensitive）、cli.py（argparse 子命令与输出渲染）。每个函数
   职责单一，单函数不超过 40 行。
5. 编码规范：全部公共函数带类型注解与 docstring；变量命名用英文小写下划线；
   运行日志统一用 logging 输出到 stderr，文件日志写入
   ~/.clipboard_history/app.log，保留最近 3 个轮转文件；禁止用 print 输出调试信息。
6. 数据文件路径：历史文件为 ~/.clipboard_history/history.json，配置文件为
   ~/.clipboard_history/config.json，首次运行时自动创建目录。

【四、设计要点】
1. 数据结构：
   ClipboardEntry = {
       "id": int,            自增主键，从 1 开始
       "text": str,          内容全文（可能被截断）
       "sha256": str,        内容指纹，64 位十六进制
       "kind": str,          url / path / json / code / text
       "created_at": str,    ISO 8601 本地时间，首次入库时间
       "last_seen": str,     最后一次被复制的时间
       "count": int,         被复制的次数，默认 1
       "starred": bool,      是否收藏
       "sensitive": bool,    是否命中敏感规则
       "truncated": bool     是否因超长被截断
   }
   StoreDocument = {"version": 1, "next_id": int, "entries": [ClipboardEntry, ...]}
2. 关键算法或流程：
   2.1 watch 主循环：读取剪贴板 → 若读取失败则 sleep 后重试 → 计算 sha256 → 与
       last_hash 比较 → 相同则仅更新内存计数，每 10 秒落盘一次 → 不同则构造
       ClipboardEntry，按去重策略决定追加或更新 → 落盘。
   2.2 落盘策略：采用「临时文件 + os.replace」的原子写入，先写入 history.json.tmp
       并 flush + fsync，再替换正式文件，避免进程被杀导致文件半截。
   2.3 搜索算法：关键字按空白切分成多个词元，全部词元都命中（AND 语义）才算匹配，
       匹配不区分大小写，命中位置用 str.find 计算用于高亮。
   2.4 淘汰算法：记录数超过上限时，先按 starred 为 false 过滤，再按 created_at 升序
       排序，删除最旧的多余条目；若非星标条目不足以降到上限以下，则停止删除并告警。
3. 接口或命令设计：
   python cli.py watch [--interval 0.5] [--dedup-global]
   python cli.py list [--limit 20] [--kind url] [--since 2024-05-01] [--pager]
   python cli.py search KEYWORD [--limit 50] [--verbose]
   python cli.py copy ID
   python cli.py star ID [--unset]
   python cli.py clear [--keep-starred 100] [--dry-run]
   关键函数签名：
   def read_clipboard() -> str | None
   def write_clipboard(text: str) -> bool
   def classify_kind(text: str) -> str
   def append_entry(store: StoreDocument, text: str, dedup_global: bool) -> tuple[int, bool]

【五、运行方式与示例】
安装与运行（无需 pip 安装任何依赖）：
   python --version                     确认版本不低于 3.10
   python cli.py watch --interval 0.5   前台开始监听剪贴板
   python cli.py list --limit 5         查看最近 5 条
示例一（正常流程）：
   依次复制 "https://docs.python.org/3/" 与 "订单号 A20240512-7788"，然后执行
   python cli.py list --limit 3
   输出：
         3  2024-05-12 10:31:07  url      1  https://docs.python.org/3/
         4  2024-05-12 10:31:22  text     1  订单号 A20240512-7788
示例二（搜索与回填）：
   python cli.py search 订单号
   输出：
         4  2024-05-12 10:31:22  text     1  [订单号] A20240512-7788
   python cli.py copy 4
   输出：已回填到剪贴板：订单号 A20240512-7788
示例三（异常输入）：
   python cli.py copy 99999
   输出：错误：找不到 id 为 99999 的记录
   退出码：4
   python cli.py search ""
   输出：错误：搜索关键字不能为空
   退出码：2

【六、验收标准】
[ ] watch 运行时连续复制同一内容两次，history.json 只新增一条记录，count 变为 2。
[ ] 复制的 URL、存在的文件路径、合法 JSON 分别被识别为 url、path、json 类型。
[ ] search 使用两个关键字时，只有同时包含两个词的记录被返回。
[ ] list --kind json 只列出 json 类型记录。
[ ] copy 4 之后系统剪贴板内容与第 4 条记录的 text 完全一致。
[ ] star 3 之后执行 clear --keep-starred，第 3 条仍然存在。
[ ] 内容含 token=abcd1234efgh 时列表展示被遮蔽为 toke****efgh 且 sensitive 为 true。
[ ] 复制一张图片（非文本）后 watch 不崩溃、不产生空记录。
[ ] 手工把 history.json 改成非法 JSON 后再运行 list，程序自动备份坏文件并输出空列表。
[ ] 历史超过 5000 条时，最旧的非星标记录被删除，星标记录保留。
[ ] 全部源码无第三方 import，python -m py_compile 对所有模块通过。
[ ] 日志文件 app.log 中不出现完整的敏感内容原文。
[ ] list 在无匹配结果时输出提示文案且退出码为 0。

【七、可选扩展】
1. 增加全局热键唤起最近 10 条历史的悬浮列表（Windows 下用 ctypes 调用
   RegisterHotKey，其他平台给出降级提示）。
2. 支持多格式剪贴板（HTML、图片）的落盘与预览，图片按 PNG 存入 blobs 子目录。
3. 增加 history.db 的 SQLite 后端，用 FTS5 做全文索引，替换 JSON 存储。
4. 提供 --sync-dir 参数，把历史文件同步到指定目录，实现多机共享。

【八、涉及知识点】
- tkinter 剪贴板 API 与跨平台差异
- threading 定时轮询、锁与线程安全
- hashlib 内容指纹与去重思路
- json 序列化、原子写入与文件损坏恢复
- argparse 子命令与互斥参数
- 正则表达式做敏感信息识别
- logging 的级别、格式与轮转
- 文本分类的启发式规则设计
- 列表渲染中的列宽对齐与截断处理
================================================================================
