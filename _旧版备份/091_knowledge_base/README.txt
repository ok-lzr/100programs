================================================================================
项目编号：091                    难度等级：★★★★★（大型项目）
项目名称：个人知识库与全文检索系统
所属分类：Web 应用 / 内容管理 / 全文检索
建议工时：2 ~ 4 周（约 80 ~ 140 小时）
运行环境：Python 3.10+    第三方依赖：FastAPI、uvicorn、SQLAlchemy、pydantic、jieba、watchdog、pytest、httpx、Jinja2、python-multipart
================================================================================

【一、项目背景与目标】

很多开发者与研究者长期用 Markdown 记录技术笔记、会议纪要、读书摘录，文件散落在十
几个目录里，命名规则不统一。想找“去年讨论过的那段关于幂等设计的笔记”时，只能靠
文件管理器递归搜索文件名或者 grep 全盘，结果是命中一堆噪声，中文分词命不中、大小
写敏感、无法按标签或时间过滤，更没有“这条笔记最近被谁改过”的概念。笔记越写越多，
复用率反而越低，最后变成只写不看的资料坟场。

本项目的目标是做一个可私有部署的个人知识库：以 Markdown 文件为唯一事实来源，服务
端通过 watchdog 监听文件变化，自动增量解析标题、标签、代码块、链接与正文，构建倒排
索引；对外提供 Web 界面，支持中文分词检索、布尔查询、标签过滤、时间范围过滤，并在
结果中高亮命中片段、展示原文上下文与文档元信息。所有数据都在本地，不需要联网，也
不依赖任何云服务。

系统的主要使用者是：个人知识管理者（写笔记、搜笔记）、团队小范围共享（把一个
notes 目录挂成只读知识站）、以及对检索原理感兴趣的学习者（想亲手实现倒排索引、TF-IDF
与 BM25 排序，而不是调一个现成的搜索引擎）。做成之后，它可以当作个人 wiki、技术
博客的草稿池、团队文档站，也可以作为学习信息检索算法的实验床。

与笔记软件相比，本项目的重点不是编辑器，而是索引与检索质量：如何切词（中英文混合）、
如何计算相关性（词频饱和与文档长度归一化）、如何处理增量更新与索引一致性、如何在
只改一个文件时避免全量重建。这些正是搜索引擎的入门核心问题。

本项目全程使用真实的本地文件与真实的中文语料进行开发与验收，不允许出现“假设有一
个搜索引擎已经建好了”这类偷懒的抽象层；索引结构必须由本项目自己实现并可由测试代码
直接断言。

【二、功能需求清单】

本系统按四个子系统拆分：用户端（Web 界面）、管理端（索引与知识库运维）、服务端
（API 与检索内核）、基础设施（存储、监听、配置与部署）。

1. 用户端子系统（Web 界面）
   1.1 首页检索框：输入查询串，回车后跳转 /search?q=...&page=1，展示总命中数、耗时
       毫秒数与结果列表。空查询串返回提示页而不是 500。
   1.2 结果条目展示：每条包含文档标题（链接到文档详情页）、文件相对路径、最后修改
       时间、命中得分、最多 3 段高亮摘要。摘要窗口为命中词前后各 60 个字符，超出部分
       用省略号截断，高亮用 <mark> 包裹并用 HTML 转义防止 XSS。
   1.3 文档详情页：左侧渲染 Markdown 正文（先转 HTML 再输出，服务端渲染），右侧展示
       元信息面板：标题、路径、字数、标签、出链列表、反链列表（哪些文档链接到本篇）、
       最近修改时间。右上角提供“编辑路径提示”（只读展示，不内置编辑器）。
   1.4 标签浏览页：列出全部标签及其文档数量，点击标签进入 /tag/<name>，等价于一次
       带 tag 过滤的检索。
   1.5 目录树导航：按文件夹层级展示全部文档，支持折叠展开，点击文件名直接进入详情。
   1.6 分页与排序：每页默认 20 条，支持 page 参数；支持 sort=relevance|mtime 两种
       排序，非法 sort 值退化为 relevance 并在页面顶部给出提示。
   1.7 搜索建议：输入框失焦时请求 /api/suggest?prefix=xx，返回最多 8 个索引词条，
       供前端做简单补全。
   1.8 错误页：访问不存在的文档路径返回 404 页面，包含返回首页链接与检索入口。

2. 管理端子系统
   2.1 索引状态面板（/admin）：展示已索引文档数、索引词条数、索引占用字节数、最近
       一次重建时间、当前监听状态（running/stopped）、监听目录绝对路径。
   2.2 手动重建：POST /api/admin/reindex 触发全量重建，接口在后台线程执行并立即返回
       202 与任务 id；GET /api/admin/tasks/{id} 查询进度（processed/total、状态）。
   2.3 单文档重索引：PUT /api/admin/documents 传入相对路径，重新解析并替换该文档的
       索引条目，用于监听失效时的手工补救。
   2.4 词典导出：GET /api/admin/terms?limit=500 导出索引中出现频次最高的词条及文档频
       率，用于人工检查分词质量（例如误把代码标识符切碎）。
   2.5 停用词管理：POST /api/admin/stopwords 提交停用词列表并落盘为 stopwords.txt，
       重建后生效；删除停用词同理。文件改动需要记录操作日志。
   2.6 操作日志：管理端所有写操作记录到 logs/admin.log，包含时间、操作类型、参数摘要
       与结果，保留最近 30 天。
   2.7 只读模式开关：POST /api/admin/config 可切换 read_only，开启后所有写接口返回
       403，用于对外只读展示场景。

3. 服务端子系统（API 与检索内核）
   3.1 文档解析：Markdown 文件解析出 title（首个一级标题，缺失时用文件名）、tags
       （front matter 的 tags 字段或正文中的 #标签）、正文纯文本、代码块内容（可选是否
       索引）、内部链接（相对 .md 路径）。
   3.2 分词：正文用 jieba 精确模式切分中文，英文与数字按词边界切分并统一小写，代码
       块默认不参与检索（配置 code_index=true 时可参与）。
   3.3 倒排索引：内存中维护 term -> posting list，posting 项包含 doc_id、词频 tf、字段
       位置列表（标题/正文分别标记）；持久化到磁盘 index/ 目录，采用 JSON 分片 + 二进制
       快照两种格式，启动时优先加载快照，失败则回退到全量重建。
   3.4 查询解析：支持空格分隔的多词查询（默认 AND）、OR（大写 OR 连接）、排除（-词）、
       短语（双引号包裹）、字段限定（tag:python、title:索引、path:notes/）。
   3.5 排序打分：使用 BM25（k1=1.2，b=0.75）计算得分，摘要展示得分保留 3 位小数；
       相同得分时按 mtime 倒序作为次序稳定因子。
   3.6 高亮：对命中词做大小写不敏感匹配并返回带 <mark> 的摘要片段，同时返回未加标记
       的纯文本版本，供 CLI 与测试使用。
   3.7 反链计算：解析所有文档的出链，反向构建 backlink 表，文档详情接口返回反链列表。
   3.8 增量更新：文件新增时解析并追加索引；修改时先删除旧 posting 再插入新 posting；
       删除文件时从索引与反链表移除。使用文件 mtime + size + sha1 前 8 位判断是否需要
       重解析，避免无意义的重建。
   3.9 检索 API：GET /api/search?q=&tag=&path=&from=&to=&page=&size=&sort=，返回
       JSON，字段包括 total、took_ms、page、size、items[]（doc_id、title、path、mtime、
       score、snippet_html、snippet_text、tags）。
   3.10 文档 API：GET /api/documents 列出全部文档元信息；GET /api/documents/{id} 返回
       正文 HTML、元信息与链接关系；DELETE 仅允许在非只读模式且路径在白名单目录内。
   3.11 统一错误模型：所有错误返回 {"code": "...", "message": "...", "detail": {...}}，
       错误码包括 BAD_QUERY、NOT_FOUND、INDEX_NOT_READY、FORBIDDEN、CONFLICT。
   3.12 请求追踪：每个请求分配 request_id（uuid4 前 8 位），写入响应头 X-Request-Id
       并记录到访问日志，便于把界面报错与服务端日志对上。

4. 基础设施子系统
   4.1 配置管理：config.toml 定义 notes_dir、index_dir、host、port、page_size、
       code_index、stopwords_file、log_dir、read_only；支持环境变量 KB_ 前缀覆盖。
   4.2 文件监听：watchdog Observer 监听 notes_dir 递归变化，事件进入有界队列
       （maxsize=10000），由单个消费者线程串行处理，队列满时丢弃最旧事件并记录警告。
   4.3 索引一致性：重建期间使用写时复制（构建新索引对象，完成后原子替换引用），
       保证检索请求永远看到完整索引，不会读到半成品。
   4.4 日志：使用 logging 与 RotatingFileHandler，分 app.log / access.log / admin.log，
       单文件 10 MB，保留 5 个备份；控制台输出与文件输出共享同一 formatter。
   4.5 部署：提供 systemd 单元文件与 Windows 计划任务示例，支持 uvicorn 多 worker
       只读模式部署（写能力集中在单 worker 的索引服务上）。
   4.6 目录约定：notes/ 存放 Markdown，index/ 存放索引文件，logs/ 存放日志，
       static/ 存放前端资源，tests/ 存放测试，任何写操作都不得越出 notes_dir 与
       index_dir。

5. 模块清单（源码结构）
   5.1 app/main.py          FastAPI 应用装配、路由注册、启动/关闭事件。
   5.2 app/config.py        Pydantic Settings 读取 config.toml 与环境变量。
   5.3 app/parser.py        Markdown 解析：标题、标签、正文、代码块、链接抽取。
   5.4 app/tokenizer.py     jieba 分词封装、停用词过滤、大小写与数字归一。
   5.5 app/index_store.py   倒排索引结构、增删改查、快照读写。
   5.6 app/retriever.py     查询解析、布尔求交、BM25 打分、高亮与摘要。
   5.7 app/watcher.py       watchdog 事件监听与队列消费。
   5.8 app/models.py        SQLAlchemy 模型：Document、Term、Posting、Tag、Link、Task。
   5.9 app/repository.py    数据库访问层，隔离 SQL 与业务逻辑。
   5.10 app/api/            docs.py、search.py、admin.py 三组路由。
   5.11 app/templates/      Jinja2 模板：base、index、search、detail、tags、admin。
   5.12 tests/              单元测试、接口测试、索引一致性测试与性能基准脚本。

6. 接口清单（HTTP）
   6.1 GET  /                        首页（HTML）
   6.2 GET  /search?q=&tag=&path=&from=&to=&page=&size=&sort=   检索结果页（HTML）
   6.3 GET  /doc/{doc_id}            文档详情页（HTML）
   6.4 GET  /tags                    标签浏览页（HTML）
   6.5 GET  /api/search              JSON 检索接口
   6.6 GET  /api/suggest?prefix=     前缀补全
   6.7 GET  /api/documents           文档列表
   6.8 GET  /api/documents/{id}      文档详情（含 backlinks）
   6.9 PUT  /api/admin/documents     单文档重索引
   6.10 POST /api/admin/reindex      全量重建（202 + task_id）
   6.11 GET  /api/admin/tasks/{id}   重建进度
   6.12 POST /api/admin/stopwords    更新停用词
   6.13 GET  /api/admin/terms        词条统计导出
   6.14 POST /api/admin/config       运行时配置开关（read_only 等）
   6.15 GET  /healthz                健康检查（索引是否就绪）

7. 数据模型概览
   7.1 documents(id INTEGER PK, rel_path TEXT UNIQUE, title TEXT, word_count INTEGER,
       mtime REAL, content_sha1 TEXT, created_at TEXT, updated_at TEXT)
   7.2 terms(id INTEGER PK, term TEXT UNIQUE, doc_freq INTEGER, collection_freq INTEGER)
   7.3 postings(id INTEGER PK, term_id INTEGER, doc_id INTEGER, tf INTEGER,
       field TEXT, positions TEXT)  索引 (term_id, doc_id) 唯一
   7.4 tags(id INTEGER PK, name TEXT UNIQUE)；document_tags(doc_id, tag_id) 多对多
   7.5 links(id INTEGER PK, src_doc_id INTEGER, dst_path TEXT, dst_doc_id INTEGER NULL)
   7.6 tasks(id TEXT PK, kind TEXT, status TEXT, processed INTEGER, total INTEGER,
       started_at TEXT, finished_at TEXT, message TEXT)
   7.7 说明：postings 只做持久化与调试用途，热路径全部走内存索引；内存索引每 5 分钟
       或每 500 次写操作落一次快照。

【三、里程碑拆解（建议 4 ~ 6 个阶段）】

阶段一：解析、分词与索引内核（约 20 小时）
  产出：Markdown 解析（标题/标签/链接/代码块）、jieba 分词封装与停用词表、倒排索引结构与
       增删改查、SQLite 建模与迁移、索引快照读写。
  验收：单元测试覆盖解析与分词；1000 篇合成文档可在 90 秒内完成全量索引并落盘快照。

阶段二：查询解析与 BM25 排序（约 22 小时）
  产出：查询 AST 解析（AND/OR/排除/短语/字段限定）、集合求交与短语位置校验、BM25 打分、
       高亮摘要生成、分页与排序参数。
  验收：检索内核测试覆盖率 ≥ 90%；标题命中文档排序高于仅正文命中；非法查询返回
       BAD_QUERY。

阶段三：API 与 Web 界面（约 24 小时）
  产出：FastAPI 路由与统一错误模型、请求追踪、检索页、文档详情页（含反链）、标签页、
       目录树导航、分页与排序切换、检索建议接口。
  验收：浏览器完成“搜索 → 打开文档 → 查看反链”的完整流程；分页与排序行为与接口一致。

阶段四：文件监听与增量一致性（约 22 小时）
  产出：watchdog 递归监听、有界事件队列与消费者线程、mtime + size + sha1 去重判断、
       增量增删改索引、写时复制与原子替换、启动时快照校验与后台重建。
  验收：新增、修改、删除文档后索引在 5 秒内一致；重建期间检索请求始终返回完整结果。

阶段五：管理端与运维能力（约 20 小时）
  产出：索引状态面板、手动重建与进度查询、单文档重索引、停用词管理、词条统计导出、
       只读模式开关、操作日志、健康检查。
  验收：管理端统计数字与实际文件一致；read_only 开启后写接口全部返回 403。

阶段六：测试、性能与部署（约 18 小时）
  产出：覆盖率报告、5000 篇文档的性能基准脚本、systemd 与 Windows 计划任务示例、
       多 worker 只读部署说明、备份说明（notes 目录与索引目录的可重建关系）。
  验收：10 万词条的检索 P95 ≤ 120 ms；全量重建 5000 篇 ≤ 180 秒；按文档步骤可在
       重启后直接加载快照并立即提供检索。

【四、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用 match 语句与类型联合语法（str | None）。
2. 允许使用的库：标准库（pathlib、hashlib、re、json、sqlite3、logging、threading、
   queue、tomllib、dataclasses、typing、unittest）；第三方仅限 FastAPI、uvicorn、
   SQLAlchemy、pydantic、jieba、watchdog、Jinja2、python-multipart、httpx、pytest、
   pytest-cov。禁止引入 Elasticsearch、Whoosh、MeiliSearch 等现成搜索引擎，索引必须
   自己实现。
3. 禁止事项：禁止把笔记正文以整段字符串形式塞进 SQL 做 LIKE 检索冒充全文检索；
   禁止在请求线程中做全量重建；禁止硬编码绝对路径；禁止在日志里打印笔记正文全文。
4. 代码组织：分层为 api（路由与校验）→ service（检索与索引业务）→ repository（存储），
   禁止 api 层直接操作 SQLAlchemy Session 或磁盘索引；每个模块必须有模块级 docstring；
   单个函数不超过 60 行，圈复杂度高的分支需拆分为私有方法。
5. 编码规范：全部公共函数与类方法使用类型注解；docstring 采用 Google 风格，写明参数、
   返回值与抛出的异常；命名遵循 PEP 8，私有成员前缀下划线；禁止 print 调试，统一
   logger = logging.getLogger(__name__)。
6. 并发约束：索引写操作必须串行化（单写线程 + 锁），检索为只读并可并发；索引替换采用
   原子引用切换；禁止在检索路径上加全局排他锁。
7. 测试约束：pytest 覆盖率不低于 80%，检索内核（tokenizer、retriever、index_store）
   覆盖率不低于 90%；必须包含一个至少 500 篇合成文档的批量索引与检索基准测试。
8. 安全约束：所有渲染到 HTML 的正文与摘要必须先转义；文件删除接口的路径必须经过
   resolve() 后校验是否位于 notes_dir 之内，防止目录穿越；管理接口预留 Token 校验位
   （配置 admin_token 后需携带 X-Admin-Token 头）。
9. 性能约束：单篇 2000 字文档解析加索引不超过 30 ms；10 万词条的索引在单机 4 核
   8 GB 环境下，单关键词查询 P95 不超过 120 ms；全量重建 5000 篇文档不超过 3 分钟。

【五、设计要点】

1. 数据结构：
   1.1 Posting = (doc_id: int, tf: int, positions: list[int], field: str)。
   1.2 InvertedIndex = dict[str, list[Posting]]，另维护 doc_length: dict[int, int] 与
       avg_length: float，供 BM25 的长度归一化使用。
   1.3 DocumentMeta = (doc_id, rel_path, title, word_count, mtime, sha1, tags: list[str])。
   1.4 Query AST 节点：TermNode(word, field)、PhraseNode(words)、AndNode(children)、
       OrNode(children)、NotNode(child)，先用递归下降解析成 AST 再求值。
2. 关键算法或流程：
   2.1 索引构建：遍历 notes_dir 的 *.md → 计算 sha1 → 与库中记录比对 → 解析 → 分词 →
       统计 tf 与位置 → 写入内存倒排表与 SQLite → 更新 doc_freq 与 avg_length。
   2.2 BM25 打分：score(q, d) = Σ idf(t) * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b *
       len(d) / avg_len))，其中 idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5))。
   2.3 短语查询：先取各词 posting 求交集候选集，再对候选文档检查 positions 是否连续。
   2.4 增量更新：修改文件 → 按 doc_id 取旧 posting 逐词删除对应项 → 重新解析插入 →
       若某词 doc_freq 归零则不删除词条（保留词表稳定性），仅将 df 置零。
   2.5 快照落盘：以文档为单位序列化 index_meta.json 与 postings_<n>.bin，写入临时目录后
       os.replace 原子改名，避免进程中断留下损坏快照。
   2.6 高亮摘要：在原文中定位命中词的所有偏移，按“命中密度最高的窗口”选取 3 段，
       每段做 HTML 转义后再插入 <mark> 标签。
   2.7 启动流程：读配置 → 初始化 SQLite → 尝试加载快照 → 校验快照 sha1 与库中是否一致
       → 不一致则后台异步全量重建并对外返回 INDEX_NOT_READY（健康检查 503）。
3. 接口或命令设计：
   3.1 检索函数签名：def search(query: str, *, tag: str | None = None,
       path_prefix: str | None = None, time_range: tuple[float, float] | None = None,
       page: int = 1, size: int = 20, sort: str = "relevance") -> SearchResult。
   3.2 索引对象签名：class InvertedIndex: add_document(meta, tokens) -> None；
       remove_document(doc_id) -> None；postings(term) -> list[Posting]；
       save(path) -> None；classmethod load(path) -> InvertedIndex。
   3.3 命令行工具：python -m app.cli reindex --notes ./notes；python -m app.cli search
       "幂等 设计" --tag backend --size 5；python -m app.cli stats；python -m app.cli
       serve --host 127.0.0.1 --port 8000。
4. 检索质量细节：
   4.1 停用词默认内置 120 个中文虚词与英文冠词，可通过 stopwords.txt 覆盖。
   4.2 英文词统一小写并做简单词干化（仅去掉常见复数 s/es），不做完整 Porter 词干。
   4.3 单字中文词（如“的”“了”）进入停用词；长度小于 2 的英文 token 直接丢弃。
   4.4 tag 与 path 过滤在打分前完成，避免对不相关文档计算得分。

【六、运行方式与示例】

1. 安装与初始化
   python -m venv .venv
   .venv\Scripts\activate            （Linux/macOS 为 source .venv/bin/activate）
   pip install fastapi uvicorn sqlalchemy pydantic jieba watchdog jinja2
   python -m app.cli init --notes C:\projects\100programs\091_knowledge_base\notes
2. 启动服务
   python -m app.cli serve --host 127.0.0.1 --port 8000
   浏览器访问 http://127.0.0.1:8000
3. 命令行检索
   python -m app.cli search "倒排索引 BM25" --size 3
4. 示例一（正常检索）
   请求：GET /api/search?q=%E5%80%92%E6%8E%92%E7%B4%A2%E5%BC%95&tag=ir&size=2
   响应：
   {
     "total": 7, "took_ms": 18, "page": 1, "size": 2,
     "items": [
       {"doc_id": 12, "title": "倒排索引实现笔记", "path": "ir/inverted-index.md",
        "mtime": 1735689600.0, "score": 6.421, "tags": ["ir", "python"],
        "snippet_html": "...<mark>倒排索引</mark>的核心是 term 到 posting 的映射...",
        "snippet_text": "...倒排索引的核心是 term 到 posting 的映射..."},
       {"doc_id": 31, "title": "检索排序对比", "path": "ir/ranking.md",
        "mtime": 1733011200.0, "score": 4.077, "tags": ["ir"],
        "snippet_html": "...对比 TF-IDF 与 <mark>倒排索引</mark>结合后的效果...",
        "snippet_text": "...对比 TF-IDF 与 倒排索引 结合后的效果..."}
     ]
   }
5. 示例二（短语查询与字段限定）
   请求：GET /api/search?q=%22%E5%86%99%E6%97%B6%E5%A4%8D%E5%88%B6%22%20title%3A%E7%B4%A2%E5%BC%95
   含义：短语“写时复制”并且标题包含“索引”
   响应：{"total": 1, "took_ms": 9, "items": [{"doc_id": 44, "title": "索引重建中的写时复制",
          "score": 8.913, "snippet_html": "...重建时采用<mark>写时复制</mark>避免读到半成品..."}]}
6. 示例三（异常输入）
   请求：GET /api/search?q=%22%E6%9C%AA%E9%97%AD%E5%90%88%E5%BC%95%E5%8F%B7
   含义：只有一个未闭合的双引号
   响应：HTTP 400
   {"code": "BAD_QUERY", "message": "短语引号未闭合", "detail": {"position": 0}}
7. 示例四（索引未就绪）
   请求：GET /api/search?q=test（重建尚未完成）
   响应：HTTP 503
   {"code": "INDEX_NOT_READY", "message": "索引正在重建，请稍后重试",
    "detail": {"task_id": "9f2c1ab3", "processed": 812, "total": 5000}}

【七、验收标准】

[ ] 1. 启动服务后 GET /healthz 返回 200 且 status 为 ready，索引文档数与 notes 目录下
      *.md 文件数量一致。
[ ] 2. 检索“倒排索引”能命中标题含该词的文档，且标题命中文档得分高于仅正文命中的文档。
[ ] 3. 输入未闭合引号、只有运算符（如 "AND OR"）等非法查询返回 400 与 BAD_QUERY，
      服务不崩溃且日志记录 request_id。
[ ] 4. 中文分词结果可通过 GET /api/admin/terms 查看，常见的“的”“了”“是”不在词条列表中。
[ ] 5. 新建一个 .md 文件后 3 秒内该文档可被检索到（watchdog 生效），删除该文件后
      5 秒内检索结果不再包含它。
[ ] 6. 修改某文档正文后，旧关键词不再命中，新关键词立即命中，且文档总数不变。
[ ] 7. 全文重建 5000 篇合成文档耗时不超过 180 秒，期间检索接口返回旧索引结果而非报错。
[ ] 8. tag:xxx 与 path: 前缀过滤生效，结果集合是相应子集，与手工筛选结果一致。
[ ] 9. 文档详情页正确展示反链：A 文档链接 B 时，B 的详情页列出 A。
[ ] 10. 在笔记正文中写入 <script>alert(1)</script>，检索摘要与详情页均按纯文本显示，
      不执行脚本（HTML 转义生效）。
[ ] 11. 尝试 DELETE /api/admin/documents?path=../../etc/passwd 返回 403 或 400，
      不得删除 notes_dir 之外的文件。
[ ] 12. 开启 read_only 后所有写接口返回 403，检索与浏览功能不受影响。
[ ] 13. pytest 全量通过，整体覆盖率 ≥ 80%，检索内核模块覆盖率 ≥ 90%。
[ ] 14. 单关键词查询在 10 万词条索引下 P95 ≤ 120 ms（基准脚本输出可复现数据）。
[ ] 15. 索引快照落盘后重启进程，加载耗时显著小于重建耗时，且检索结果与重启前完全一致。

【八、可选扩展】

1. 增加向量检索通道：用 sentence-transformers 生成句向量，与 BM25 结果做倒数排名融合
   （RRF），提升近义改写查询的召回率。
2. 增加 PDF、docx 文档导入（pypdf、python-docx），统一转成 Markdown 后进入索引。
3. 增加版本历史：每次保存生成差异快照，支持按时间点回看与对比。
4. 增加多用户与共享空间：文档归属、只读分享链接与访问审计。
5. 增加检索质量评估：维护一组查询与期望文档的标注集，计算 Recall@K 与 MRR。
6. 增加前端离线缓存（Service Worker）与键盘快捷检索面板（Ctrl+K）。

【九、涉及知识点】

- 信息检索基础：倒排索引、词频统计、文档频率、TF-IDF 与 BM25 排序原理
- 中文分词：jieba 精确模式、停用词表、中英混排边界处理
- 数据结构与算法：哈希表、集合求交、位置索引、短语匹配、堆取 Top-K
- Web 框架：FastAPI 路由与依赖注入、Pydantic 校验、Jinja2 模板渲染
- 持久化：SQLite 关系建模、多对多关系、事务与索引调优
- 并发模型：文件监听线程与队列、写时复制、原子替换、读写分离
- 工程化：配置管理、结构化日志、请求追踪、pytest 测试金字塔与覆盖率
- 安全：HTML 转义与 XSS、路径穿越防护、管理接口鉴权与只读模式
================================================================================
