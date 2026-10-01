================================================================================
项目编号：029                    难度等级：★★☆☆☆（小型项目）
项目名称：每日一句推送器
所属分类：网络与在线服务 / 桌面小工具
建议工时：3 ~ 5 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】
很多人想在每天早上看到一句有力量的话，但每天手动去网站复制太麻烦，把内容堆在
聊天软件里又会被淹没。本项目做一个「每日一句」命令行推送器：拉取一条随机名言，
在终端排版打印，可通过系统桌面通知弹出一条提醒，并把喜欢的句子收藏到本地。

目标用户是喜欢在终端工作、习惯用计划任务做每日提醒的开发者与学生。做出来之后，
你可以把它挂到「任务计划程序」或 cron 上，每天 8 点自动弹一条通知；看到好句子就
star 收藏，周末用 favorites 子命令导出成 Markdown 清单。

数据来源使用公开的随机名言接口（示例：https://zenquotes.io/api/random 与
https://api.quotable.io/random），并在本地内置一份离线名言库作为兜底。使用前必须
阅读并遵守接口的使用条款与频率限制：免费接口通常限制每日调用次数，禁止高频轮询，
禁止把名言数据整体抓取后二次分发。名言版权归属原作者，展示时应保留作者名。

【二、功能需求清单】
1. 核心功能
   1.1 随机名言获取：默认从在线接口获取一条名言（含正文 text 与作者 author），
       网络不可用时自动回退到本地离线语录库（quotes_offline.json，内置不少于
       30 条中英文名言，含作者与出处），并标注来源为 offline。
   1.2 每日固定：--daily 模式下先按日期生成种子（本地日期 YYYYMMDD 的整数），用
       random.Random(seed) 在离线库中挑选，保证同一天多次运行得到同一条；在线模式
       下若当天已有 today.json 记录，则直接复用而不重复请求。
   1.3 终端排版：输出带有分隔线与居中的名言正文、右对齐的作者署名，宽度按终端
       宽度自适应（用 shutil.get_terminal_size），最小 40 列；中文按 2 列宽度计算。
   1.4 桌面通知：--notify 参数触发系统桌面通知。Windows 上用 PowerShell 的
       Windows.UI.Notifications 或 BurntToast 风格的回退方案（用 toast 脚本或
       msg 命令兜底），macOS 用 osascript display notification，Linux 用 notify-send；
       任一方案不可用时打印提示但不影响终端输出。
   1.5 收藏夹：star 子命令把当前或指定名言加入收藏，写入
       ~/.quoteofday/favorites.jsonl，字段包含收藏时间、正文、作者、来源、标签；
       favorites 子命令列出收藏，支持 --tag 过滤与 --export markdown 导出。
   1.6 标签：--tag 可给收藏打标签（如 励志、英文、写作素材），一条可含多个标签；
       tags 子命令统计各标签条数并按条数降序输出。
   1.7 去重：默认避免与最近 10 次推送重复；在线接口返回重复时最多重新请求 2 次，
       仍重复则接受并标注「近期重复」。
   1.8 每日记录：把当天推送写入 ~/.quoteofday/today.json（含日期、正文、作者、来源、
       是否已通知），crossday 时自动覆盖为新的一天。

2. 输入与交互
   2.1 子命令共 5 个：show（默认，展示一条）、star（收藏）、favorites（列出）、
       tags（标签统计）、history（最近推送记录）。
   2.2 命令形式：
       python quote.py show --notify --tag 励志
       python quote.py show --daily --no-network
       python quote.py star --tag 写作素材 --note "用在周报开头"
       python quote.py favorites --tag 励志 --export markdown --output fav.md
       python quote.py history --limit 15
   2.3 --no-network 强制使用离线库；--source 可指定 zenquotes 或 quotable 或 offline。
   2.4 --lang zh|en|any 控制偏好语言（离线库按 lang 字段过滤，在线接口无法保证时
       在输出中标注实际语言）。
   2.5 无参数直接运行等价于 show --daily。

3. 输出与展示
   3.1 show 输出格式（宽度 W 表示终端列数）：
       ──────────── 每日一句 ────────────
                 （名言正文，超长自动折行）
                           —— 作者《出处》
       来源：zenquotes.io ｜ 2024-05-12 ｜ 标签：励志
   3.2 正文折行规则：按终端宽度减去左右各 4 列留白计算可用宽度，中文按 2 列计，
       优先在标点或空格处断行，超长单词（英文）不做硬切时允许超出一行。
   3.3 favorites 输出每行以序号、收藏日期、作者与正文前 40 字符展示，中文截断按
       显示宽度计算并补省略号。
   3.4 --export markdown 生成的 Markdown 文件用「> 正文」引用块与「—— 作者」署名，
       按标签分组，文件首行写标题与导出时间。
   3.5 --json 输出结构化结果，字段为 text、author、source、fetched_at、tags、cached。
   3.6 全部输出为 UTF-8；在 Windows 终端下若检测到编码不是 utf-8 则提示切换到
       chcp 65001 或改用 Windows Terminal。

4. 异常与边界处理
   4.1 在线接口返回 429 或额度用尽时不再重试，直接使用离线库并提示「接口限流，
       已回退离线库」，退出码仍为 0。
   4.2 接口返回字段名不一致（如 content 而非 text）时按候选字段顺序尝试，全部缺失
       视为无效响应并使用离线库。
   4.3 离线库文件缺失时，使用代码内置的 10 条兜底名言，保证程序永远有内容可输出。
   4.4 桌面通知失败（命令不存在、权限不足、超时 5 秒）时打印一行警告，退出码不变。
   4.5 star 重复收藏同一条（正文与作者相同）时提示「已在收藏夹中」并跳过，除非加
       --force。
   4.6 收藏文件损坏的行被跳过并计数，最后提示跳过条数。
   4.7 --tag 传入空字符串或超长（大于 20 字符）时报参数错误，退出码 2。
   4.8 终端宽度小于 40 列时固定按 40 列排版，避免折行错乱。

【三、技术要求与约束】
1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库 urllib.request、json、random、argparse、datetime、
   pathlib、subprocess、shutil、logging、unicodedata（用于中英文宽度计算）、
   textwrap（仅用于英文折行的辅助）、os、sys。禁止引入第三方库。
3. 网络与并发：单次运行最多发起 3 次网络请求（含重复规避的重新请求），全部串行；
   不使用线程池，也不实现后台常驻或定时轮询。
4. 超时与重试：单次请求超时 6 秒；失败重试 1 次，间隔 2 秒；HTTP 429、4xx 不重试；
   请求被限流后本次运行不再访问在线接口。
5. 限速要求：两次运行之间的建议间隔不少于 1 小时；程序在同一自然日内若 today.json
   已存在且加 --daily，则完全不发起请求；禁止实现循环拉取、禁止在一次运行中拉取
   多条名言用于批量分发。
6. 合规要求：遵守所选名言接口的使用条款与频率限制；输出中保留作者署名与来源标注，
   不修改名言正文；禁止把在线接口数据整体抓取建立本地镜像库用于分发；离线库中的
   名言需注明为学习用途整理。
7. 禁止事项：禁止硬编码任何 API Key（如需鉴权接口，密钥从环境变量 QUOTE_API_KEY
   读取）；禁止在收藏与历史文件中保存任何个人敏感信息；禁止自动发布到社交平台。
8. 代码组织：sources.py（在线接口适配与离线库读取）、offline.py（离线库加载与兜底
   数据）、layout.py（宽度计算与折行排版）、notify.py（跨平台桌面通知）、store.py
   （today.json、favorites.jsonl、history.jsonl 读写）、cli.py（子命令与入口）。
9. 编码规范：类型注解与 docstring 全覆盖；所有文件读写显式指定 encoding="utf-8"；
   通知与网络失败用 logging.warning 记录；主输出统一走 layout 层，禁止散落 print。

【四、设计要点】
1. 数据结构：
   Quote = {text: str, author: str, source: str, lang: str, tags: list[str],
            fetched_at: str, origin: str（online/offline/builtin）, cached: bool}
   Favorite = {starred_at, text, author, source, tags, note}
   HistoryRecord = {shown_at, text, author, origin, duplicate: bool}
   TODAY_FILE = {"date": "2024-05-12", "quote": Quote, "notified": bool}
2. 关键算法或流程：
   2.1 show 主流程：检查是否为 --daily 且 today.json 日期为今天 → 是则直接复用 →
       否则按 --source 选择数据源 → 在线失败或 --no-network 则读离线库 → 语言过滤 →
       重复规避（与最近 10 条 history 比较正文的规范化形式）→ 写 today.json 与
       history.jsonl → 排版输出 → 可选通知。
   2.2 每日固定：seed = int(date.today().strftime("%Y%m%d"))，rng = random.Random(seed)，
       从按 lang 过滤后的候选列表中用 rng.choice 取一条；候选列表先按 text 排序以
       保证跨机器结果稳定。
   2.3 显示宽度计算：中文、日文、韩文与全角标点计 2 列，其余计 1 列；用
       unicodedata.east_asian_width 判断（值为 W 或 F 计 2）。以此实现居中与截断。
   2.4 折行算法：逐字符累加宽度，超过可用宽度时回退到最近的空格或中文标点位置断行；
       无法回退时在当前字符处硬断，避免死循环。
   2.5 桌面通知实现：按平台分派——Windows 先尝试 powershell -Command 调用
       New-BurntToastNotification（存在则用）否则回退到 mshta 或 msg；macOS 用
       osascript -e 'display notification "..." with title "..."'；Linux 用
       notify-send。全部用 subprocess.run 带 timeout=5，失败静默降级。
3. 接口或命令设计（外部 API 与内部命令）：
   GET https://zenquotes.io/api/random     返回 [{"q": "...", "a": "...", "h": "..."}]
   GET https://api.quotable.io/random      返回 {"content": "...", "author": "...", "tags": [...]}
   python quote.py show --daily --notify
   python quote.py star --tag 励志 --note "记在周报里"
   python quote.py favorites --limit 20 --export markdown --output fav.md
   python quote.py tags
   python quote.py history --limit 15
   关键函数签名：
   def fetch_online(source: str, timeout: float, lang: str) -> Quote | None
   def pick_offline(lang: str, seed: int | None) -> Quote
   def wrap_display(text: str, width: int) -> list[str]
   def send_notification(title: str, body: str) -> bool
   def star_quote(quote: Quote, tags: list[str], note: str, force: bool) -> bool

【五、运行方式与示例】
安装与运行（无需第三方依赖）：
   python quote.py show --daily
   python quote.py show --notify --tag 励志
示例一（正常在线获取）：
   ──────────── 每日一句 ────────────
        生活不是等待风暴过去，而是学会在雨中起舞。
                              —— 佚名
   来源：zenquotes.io ｜ 2024-05-12 08:00 ｜ 标签：励志
   退出码：0
示例二（离线回退与每日固定）：
   python quote.py show --daily --no-network
   ──────────── 每日一句 ────────────
        Simplicity is the ultimate sophistication.
                              —— Leonardo da Vinci
   来源：离线语录库（offline）｜ 2024-05-12 ｜ 语种：en
   同一天再次运行，输出的名言与上面完全一致。
示例三（收藏、导出与异常输入）：
   python quote.py star --tag 写作素材 --note "周报开头"
   输出：已收藏：Simplicity is the ultimate sophistication. —— Leonardo da Vinci
   python quote.py favorites --limit 3
   1  2024-05-12  达芬奇      Simplicity is the ultimate sophistica…
   输出：共 1 条收藏，标签：写作素材
   python quote.py show --tag
   输出：错误：--tag 需要一个非空值（长度 1 ~ 20）
   退出码：2
   python quote.py favorites --export markdown --output fav.md（离线库文件被删除时）
   输出：警告：离线库缺失，已使用内置兜底名言
   退出码：0

【六、验收标准】
[ ] show 在联网状态下能输出名言正文、作者与来源标注。
[ ] show --daily 在同一天内多次运行输出完全相同的名言。
[ ] show --no-network 完全不发起网络请求（可用断网或日志验证）。
[ ] 删掉离线库文件后仍能输出内置兜底名言，不崩溃。
[ ] --notify 在支持的平台上弹出桌面通知；不支持时打印警告且退出码为 0。
[ ] 通知命令执行超时（模拟 5 秒无响应）不影响终端输出。
[ ] 输出排版的每行显示宽度不超过终端宽度，中文不被截断成半个字。
[ ] 终端宽度为 30 列时按 40 列排版，输出不错乱。
[ ] star --tag 励志 成功写入 favorites.jsonl 一行，字段完整。
[ ] 重复收藏同一条时提示已在收藏夹中且不新增行；加 --force 后可重复。
[ ] favorites --tag 过滤只返回含该标签的条目。
[ ] tags 输出的各标签条数与收藏内容一致并降序排列。
[ ] favorites --export markdown 生成的文件包含「> 」引用块与作者署名行。
[ ] 收藏文件某行损坏时跳过并提示跳过条数。
[ ] 在线接口返回 429 时回退离线库并给出限流提示，退出码 0。
[ ] 单次运行的外部请求不超过 3 次，且连续两次运行不受限速影响（日志可见）。
[ ] --json 输出可被 json.load 解析，含 text/author/source/fetched_at/tags/cached。
[ ] 源码中无第三方依赖，无硬编码密钥，无循环拉取逻辑。

【七、可选扩展】
1. 增加 --theme 参数按离线库的主题字段（励志、科技、文学、英文经典）挑选，并对
   不在线的主题给出可见主题列表。
2. 增加周报模式：读取 history.jsonl，输出本周 7 条推送与标签分布。
3. 增加图片卡片生成（仅用标准库，不引入 Pillow 时降级为文本卡片），把名言渲染成
   等宽字符画形式的分享卡片文件。
4. 增加多语言翻译字段的本地映射，为英文名言附上一句中文参考译文（需在数据中标明
   译文来源为本地整理）。

【八、涉及知识点】
- urllib.request 调用 JSON 接口与异常处理
- random.Random 指定种子实现可复现的随机选择
- unicodedata 计算东亚字符显示宽度
- 文本折行与居中排版的算法实现
- subprocess 跨平台调用系统通知能力
- JSONL 追加存储与损坏行容错
- 日期驱动的每日固定逻辑与本地缓存
- argparse 子命令与可选参数校验
- 公开接口的调用额度、限速与版权署名要求
================================================================================
