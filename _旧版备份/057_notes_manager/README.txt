================================================================================
项目编号：057                    难度等级：★★★☆☆（中型项目）
项目名称：本地笔记管理器
所属分类：个人数据管理 / 全文检索
建议工时：3 ~ 4 天
运行环境：Python 3.10+    第三方依赖：无（仅标准库，SQLite FTS5）
================================================================================

【一、项目背景与目标】

笔记软件最大的风险是“数据在别人的服务器上、格式是私有格式”。用纯 Markdown
文件加一个能搜索的工具，可以同时获得可读性、可迁移性和搜索能力：文件随时能
用任何编辑器打开，笔记之间能互相链接，搜索由本地索引完成，速度接近瞬时。

本项目实现一个本地 Markdown 笔记管理器：笔记以 .md 文件形式存放在笔记库目录，
元数据（标题、标签、创建与修改时间、链接关系）存入 SQLite，正文用 SQLite FTS5
建立全文索引以支持中文分词与高级查询；提供命令行完成新建、编辑、搜索、标签
管理与导出。

目标用户是需要在几秒内找回“三个月前记的那段关于 SQLite WAL 的笔记”的开发者
与写作者。项目难点在于中文全文检索：FTS5 默认分词器对中文按整串处理，检索
“数据库”匹配不到“数据库索引设计”，需要使用 unicode61 分词器加自定义处理，
或采用二元切分（bigram）预处理策略，本说明书给出明确的落地方案。

【二、功能需求清单】

1. 核心功能
   1.1 笔记创建（new）：按模板创建 .md 文件，自动写入 YAML 风格的头部元数据
       （title、tags、created、updated），文件名由标题生成安全 slug
       （中文保留、空格转连字符、去掉文件系统非法字符）。
   1.2 编辑（edit）：调用 --editor 指定的编辑器（默认读取环境变量 EDITOR，
       否则用 notepad/vi），编辑完成后自动更新头部 updated 字段并重建索引。
   1.3 删除（remove）：默认软删除（移动到 .trash/ 并记录元数据），
       --hard 才真正删除文件；删除前需 --yes。
   1.4 全文搜索（search）：支持关键词、短语、布尔（AND/OR/NOT）、字段限定
       （title:、tag:、path:）、时间范围（--since/--until）；输出命中摘要
       （命中词前后各 30 字）并按相关度（BM25）排序。
   1.5 标签体系（tag）：列出全部标签及计数、按标签筛选笔记、重命名标签、
       删除标签（仅解除关联，不删笔记）；支持层级标签（父/子，如 dev/python）。
   1.6 双链与反向链接（links）：解析 Markdown 中的 [[笔记名]] 与
       [文字](相对路径.md) 语法建立链接表；`backlinks` 命令列出指向某笔记的
       全部笔记。
   1.7 索引维护（index）：全量重建（reindex）、增量更新（只处理 mtime 变化的
       文件）、索引状态查看（笔记数、索引数、最后索引时间、孤立标签数）。
   1.8 导出（export）：导出笔记列表 CSV（标题、路径、标签、词数、时间）、
       单篇笔记的纯文本或 HTML（用标准库 markdown 替代方案：内置极简转换器，
       仅处理标题、列表、粗体、代码块、链接），以及全库的 JSON 备份。

2. 输入与交互
   2.1 命令形如：
       `python -m notes new "SQLite WAL 模式笔记" --tags dev,db --dir db`
       `python -m notes search "WAL 并发" --tag db --since 2024-01-01`
   2.2 笔记通过“标题精确匹配 / 标题前缀 / slug 前缀 / 路径”四种方式定位，
       存在多个匹配时列出候选并要求 --pick ID。
   2.3 `--vault PATH` 指定笔记库根目录，默认 `~/notes`；`--db PATH` 指定索引库，
       默认 `<vault>/.notes_index.db`。
   2.4 支持 `search --count-only`、`--limit`、`--offset` 与 `--json`。
   2.5 支持 `index --watch`（可选扩展，用轮询实现，不引入 watchdog 时以
       `--interval 5` 每 5 秒扫描一次 mtime）。

3. 输出与展示
   3.1 search 结果输出：序号、相关度分数、标题、路径、标签、修改日期、
       命中摘要（命中词用方括号包裹，如 “…关于 [WAL] 模式的并发…”）。
   3.2 摘要生成规则：取第一个命中位置，前后各截取 30 个字符，首尾加省略号；
       多个命中时最多展示 3 段，用 “…” 分隔。
   3.3 单篇查看（show）输出元数据头 + 正文纯文本渲染 + 出链与反链列表。
   3.4 tag --list 输出按计数降序排列的标签表，含百分比条（# 号长度按比例）。

4. 异常与边界处理
   4.1 标题为空或仅空白：拒绝。
   4.2 同名笔记已存在：拒绝并提示已存在路径；--force 时在文件名后追加序号。
   4.3 文件名非法字符（`\ / : * ? " < > |`）：替换为下划线并在输出中说明。
   4.4 笔记库目录不存在：自动创建（含子目录）并提示；权限不足时报错退出码 3。
   4.5 非 UTF-8 编码的 .md 文件：尝试 utf-8-sig、gbk、gb18030，全部失败则
       跳过该文件、计入 skipped，并在 index 报告中列出文件名。
   4.6 文件在索引之后被外部修改：search 前检查 mtime，若发现变更则自动
       增量重建相关文件并提示“已自动更新 N 篇”。
   4.7 笔记被外部删除但索引仍存在：查询时校验文件存在性，缺失则标记为
       孤儿记录并提示运行 reindex。
   4.8 搜索关键词为空字符串：报错提示；`search "*"` 表示列出全部笔记（按修改时间）。
   4.9 FTS 查询语法错误（如未闭合的引号）：捕获 OperationalError，提示语法
       问题并给出转义建议，不崩溃。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。SQLite 需支持 FTS5（Python 3.10 自带的
   sqlite3 通常已启用，程序启动时用 `PRAGMA compile_options` 检测，
   不支持时降级为 LIKE 检索并在日志中告警）。
2. 允许使用的库：仅使用标准库——sqlite3、argparse、os、re、json、csv、
   hashlib、datetime、pathlib、subprocess（调用外部编辑器）、difflib、
   unicodedata、logging、textwrap、shutil、unicodedata.normalize。
   不引入 markdown、jieba 等第三方库；中文分词策略见第四部分。
3. 禁止事项：禁止把笔记正文存入 SQLite 作为唯一副本（文件才是真相来源，
   数据库只是索引，任何时刻删除索引库都能通过 reindex 恢复）；
   禁止在 FTS 查询中直接拼接用户输入（必须用 MATCH 参数绑定）；
   禁止对每次搜索做全库文件扫描（必须走索引）。
4. 代码组织：
   - `vault.py`：笔记库目录管理、slug 生成、文件读写、路径安全校验。
   - `frontmatter.py`：头部元数据解析与生成（自实现简易 YAML 子集）。
   - `db.py` / `repository.py`：SQLite 与 FTS5 建表、索引操作。
   - `segmenter.py`：中文 bigram 切分与查询词切分（核心）。
   - `indexer.py`：全量与增量索引、mtime 比对、孤儿清理。
   - `search.py`：查询解析（布尔与字段限定）、BM25 排序、摘要生成。
   - `links.py`：双链解析与反向链接维护。
   - `render.py`：极简 Markdown → 纯文本/HTML 转换。
   - `cli.py`：命令行入口。
5. 编码规范：文件读写统一 UTF-8；路径操作统一用 pathlib；所有对文件的
   写操作先写临时文件再原子替换（os.replace），避免中断导致半截文件；
   日志记录索引耗时与文件数。

【四、设计要点】

1. 数据结构

   1.1 文件层（真相来源）
       笔记库目录结构示例：
         ~/notes/
           inbox/                 （未分类笔记）
           db/sqlite-wal-模式笔记.md
           dev/python/装饰器笔记.md
           .trash/                （软删除区）
           .notes_index.db        （索引库，可安全删除后重建）
       单篇笔记文件格式（自实现 frontmatter 子集，仅支持字符串、标签数组、
       日期三类值，避免引入 YAML 库）：
         ---
         title: SQLite WAL 模式笔记
         tags: [dev, db, sqlite]
         created: 2024-05-03 10:12:00
         updated: 2024-05-03 11:40:00
         ---
         （空行后为正文，Markdown 语法）

   1.2 SQLite 表结构（索引库）

       1.2.1 notes（笔记元数据表）
             id           INTEGER PRIMARY KEY AUTOINCREMENT
             rel_path     TEXT NOT NULL UNIQUE   -- 相对笔记库根目录的 POSIX 路径
             slug         TEXT NOT NULL          -- 文件名去扩展名部分
             title        TEXT NOT NULL
             dir_path     TEXT NOT NULL DEFAULT ''  -- 相对目录，用于 --dir 过滤
             word_count   INTEGER NOT NULL DEFAULT 0
             char_count   INTEGER NOT NULL DEFAULT 0
             body_hash    TEXT NOT NULL          -- sha256 前 16 位，用于判断内容变更
             mtime        REAL NOT NULL          -- 文件修改时间戳
             created_at   TEXT NOT NULL
             updated_at   TEXT NOT NULL
             missing      INTEGER NOT NULL DEFAULT 0  -- 1 表示文件已不存在（孤儿）
             索引：idx_notes_dir(dir_path)、idx_notes_mtime(mtime)、
                   idx_notes_missing(missing)

       1.2.2 notes_fts（FTS5 虚拟表，正文全文索引）
             CREATE VIRTUAL TABLE notes_fts USING fts5(
                 title, body_tokens, tags_text,
                 content='',            -- 外部内容表模式，节省空间
                 tokenize='unicode61 remove_diacritics 2'
             );
             说明：body_tokens 存的不是原始正文，而是经过 segmenter 处理的
             分词结果（中文按 bigram 切分为“数据 据库 库索 索引 …”，
             英文按单词小写化），标题同样处理。这样 FTS5 的 unicode61
             分词器就能对中文生效。写入时同步维护 rowid = notes.id。

       1.2.3 tags（标签表）与 note_tags（关联表）
             tags: id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                   parent_id INTEGER NULL REFERENCES tags(id), note_count INTEGER
             note_tags: note_id REFERENCES notes(id) ON DELETE CASCADE,
                        tag_id REFERENCES tags(id) ON DELETE CASCADE,
                        PRIMARY KEY (note_id, tag_id)

       1.2.4 links（链接表，解析 [[笔记]] 与 相对路径链接）
             id           INTEGER PRIMARY KEY AUTOINCREMENT
             src_note_id  INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE
             dst_title    TEXT NOT NULL      -- 原始链接目标文本
             dst_note_id  INTEGER NULL REFERENCES notes(id) ON DELETE SET NULL
             link_type    TEXT NOT NULL      -- 'wiki' | 'md'
             line_no      INTEGER NOT NULL
             索引：idx_links_src(src_note_id)、idx_links_dst(dst_note_id)、
                   idx_links_title(dst_title)

       1.2.5 index_meta（索引状态表）
             key          TEXT PRIMARY KEY
             value        TEXT NOT NULL
             -- 含 last_full_index、last_incremental、vault_root、schema 版本

       1.2.6 schema_version（迁移版本表）
             version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL

2. 关键算法或流程

   2.1 中文分词策略（segmenter.py，本项目核心）：
       segment_text(text) -> str：
       步骤一，用正则把文本切成“连续 CJK 段”“连续 ASCII 词”“其他符号”
       三类片段；
       步骤二，ASCII 词：转小写，长度 >= 2 才保留（去掉 a、of 之类的噪声词
       为可选配置，默认保留）；
       步骤三，CJK 段：生成所有相邻二元组（bigram），如“数据库索引” →
       “数据 据库 库索 索引”；同时保留整段长度 <= 4 的原串，便于精确短语匹配；
       步骤四，把结果用空格连接成可被 FTS5 unicode61 正确分词的字符串。
       查询侧用同一函数处理 query_text，保证索引与查询的切分口径一致。
       局限说明：bigram 会导致“库索”这类跨词组合也能命中，属于可接受的
       召回优先策略；如需精确短语，使用引号包裹的短语查询并在结果中标注。

   2.2 增量索引流程：
       步骤一，扫描 vault 下全部 .md 文件，得到 {rel_path: (mtime, size)}；
       步骤二，与 notes 表比对，得到三类：新增、mtime 或 size 变化、已删除；
       步骤三，对新增与变化文件：读取、解析 frontmatter、计算 body_hash，
       若 hash 未变则只更新 mtime 与 updated_at（避免无意义重建）；
       步骤四，更新 notes 行，删除该 note_id 的 notes_fts 旧行并插入新行
       （FTS5 外部内容表模式下用 DELETE + INSERT 显式维护）；
       步骤五，重建该笔记的 tags 与 links（先删后插）；
       步骤六，对已删除文件：设置 missing=1 并写入 index_meta 待清理计数，
       `reindex --purge` 时真正删除元数据；
       步骤七，单个文件解析失败不影响其他文件，错误写入索引报告。

   2.3 查询解析与执行（search.py）：
       支持的查询语法：
         keyword            单词或中文词，走 bigram 切分
         "exact phrase"     短语查询，FTS5 中使用双引号
         a AND b / a OR b / NOT a   布尔运算
         title:xxx          限定标题
         tag:dev            限定标签（先查 tags 得到 note_id 集合，再与 FTS 结果交集）
         path:dev/python    限定目录前缀
       实现方式：先做一次轻量词法分析把输入拆成 (field, op, term) 三元组；
       构建 FTS5 MATCH 表达式（仅允许白名单列与运算符），其余条件（tag、路径、
       时间范围）作为 SQL 附加条件与 FTS 结果 JOIN。
       排序：优先 order by bm25(notes_fts) 升序（FTS5 的 bm25 函数值越小越相关）；
       相同分数时按 updated_at 降序。

   2.4 摘要生成 make_snippet(body, terms, width=30)：
       步骤一，在原始正文中查找第一个命中 term（大小写不敏感，中文按原串匹配）；
       步骤二，无命中（可能是 bigram 命中）时退化为按 bigram 任一段匹配定位；
       步骤三，截取前后 width 个字符，避免截断 UTF-8 字符与 Markdown 链接
       的中间位置（用 re 回退到最近的空白或标点）；
       步骤四，把命中词用 [] 包裹，最多生成 3 段并去重。

   2.5 slug 生成 make_slug(title)：
       全角转半角（unicodedata.normalize('NFKC')）→ 去首尾空白 →
       空白与下划线转 `-` → 删除 `\ / : * ? " < > |` 与 ASCII 控制字符 →
       连续 `-` 合并 → 长度截断到 80 字符（按字符数而非字节数）→
       结果为空则使用 `note-{YYYYMMDD-HHMMSS}`。

3. 接口或命令设计

   new TITLE [--tags a,b] [--dir db] [--template daily|meeting|note] [--open]
   list [--tag T] [--dir D] [--sort updated|created|title|words] [--limit N]
   show NOTE [--raw] [--html]
   edit NOTE [--editor CMD]
   remove NOTE [--hard] --yes
   search QUERY [--tag T] [--dir D] [--since D] [--until D] [--limit N]
          [--offset M] [--count-only] [--json] [--exact]
   tag list | tag rename OLD NEW | tag remove T | tag add NOTE T
   backlinks NOTE [--json] | links NOTE
   index [--rebuild] [--purge] [--watch --interval 5] [--status]
   export --format csv|json|html -o PATH [--tag T]
   open NOTE      （用系统默认程序打开笔记文件）

   函数签名：
   def segment_text(text: str) -> str
   def make_slug(title: str) -> str
   def parse_query(raw: str) -> Query
   def build_fts_match(query: Query) -> tuple[str, list[str]]
   def make_snippet(body: str, terms: list[str], width: int = 30) -> str
   def index_vault(vault: Path, repo, full: bool = False) -> IndexReport

【五、运行方式与示例】

安装（仅标准库，需 SQLite 支持 FTS5）：
  cd C:\projects\100programs\057_notes_manager
  python -m notes index --rebuild --vault C:\Users\me\notes

示例一（新建、搜索与查看）：
  输入：python -m notes new "SQLite WAL 模式笔记" --tags dev,db --dir db
  输出：已创建 db\sqlite-wal-模式笔记.md
  输入：python -m notes search "数据库 并发"
  输出：
        1) 0.83  SQLite WAL 模式笔记  db/sqlite-wal-模式笔记.md  [dev,db]  2024-05-03
           摘要：…关于 [数据库] 在 [并发] 读写下的表现，WAL 模式允许…
        共 1 条命中，耗时 6 ms

示例二（标签筛选与反向链接）：
  输入：python -m notes search "*" --tag db --sort updated --limit 5
  输出：列出 db 标签下按修改时间倒序的 5 篇笔记
  输入：python -m notes backlinks "SQLite WAL 模式笔记"
  输出：
        #12  索引与查询优化笔记   dev/sqlite-索引优化.md   第 8 行  [[SQLite WAL 模式笔记]]
        #31  每周复盘 2024-05     inbox/2024-05-复盘.md     第 22 行  [[SQLite WAL 模式笔记]]

示例三（增量索引与异常输入）：
  输入：python -m notes index --status
  输出：笔记 214 篇（缺失 2，跳过 1），标签 46 个，链接 380 条，最后全量索引 2024-05-01
  输入：python -m notes index
  输出：增量索引完成：新增 3，更新 5，删除 0，跳过 1，耗时 412 ms
  输入：python -m notes search "WAL AND"
  输出：错误：FTS 查询语法错误（查询不能以 AND 结尾），请检查布尔表达式（退出码 2）
  输入：python -m notes new "   "
  输出：错误：标题不能为空                                        （退出码 2）

【六、验收标准】

[ ] `notes index --rebuild` 后 notes 行数等于 vault 下 .md 文件数（排除 .trash）。
[ ] 搜索“数据库”能命中正文含“数据库索引设计”的笔记（bigram 召回生效）。
[ ] 搜索英文关键词大小写不敏感，`SQLite` 与 `sqlite` 返回同一结果集。
[ ] 短语查询 "WAL 模式" 只返回连续出现该短语的笔记。
[ ] title: 限定检索只在标题命中时返回结果。
[ ] tag: 与普通关键词组合查询的结果等于两者的交集（用样例数据人工验证）。
[ ] --since/--until 时间过滤与笔记 updated 时间口径一致。
[ ] 摘要中命中词被 [] 包裹，且不出现半个汉字或截断的 Markdown 链接。
[ ] 外部修改笔记文件后直接 search，能自动增量更新并出现在结果中。
[ ] 增量索引对未变化文件不重新解析（日志中“更新 0”且耗时明显低于全量）。
[ ] 删除索引库文件后重新 reindex，搜索结果与删除前完全一致（可重建性）。
[ ] 双链 [[标题]] 与 [文字](路径.md) 两种语法都能建立链接记录。
[ ] backlinks 列出的来源笔记与手工检查一致，含行号。
[ ] 软删除的笔记进入 .trash 且不再出现在 list 与 search 中；--hard 才真删文件。
[ ] 标签重命名后所有关联笔记的标签同步更新，note_count 重新统计正确。
[ ] 非法 FTS 查询（未闭合引号、结尾 AND）给出可读错误而非堆栈。

【七、可选扩展】

1. 增加 `index --watch`：用 watchdog 或轮询实时维护索引。
2. 增加极简 TUI（curses）浏览与搜索笔记。
3. 增加本地 HTTP 只读浏览界面（http.server），支持站内搜索。
4. 增加笔记图谱：把链接关系导出为 Graphviz DOT 或用文本画布呈现。
5. 增加拼写与术语一致性检查（同义词表：如“索引/index”统一）。
6. 增加加密笔记（单篇口令加密，用 hashlib.scrypt + 标准库 AES 替代方案需谨慎选型）。

【八、涉及知识点】

- SQLite FTS5：虚拟表、外部内容表、unicode61 分词器、bm25() 排序函数、
  MATCH 查询语法与布尔运算。
- 中文全文检索：bigram 切分原理、召回与精度的权衡、索引与查询口径一致性。
- 文件与数据库的职责划分：文件为真相来源、索引可重建的架构思想。
- 增量索引：mtime/size/hash 三重比对、变更集计算、孤儿记录处理。
- Markdown 解析：frontmatter 子集、链接与双链语法、极简渲染器实现。
- 文本处理：正则分段、全角半角归一化、UTF-8 安全截断、摘要生成。
- 事务与原子写：os.replace 原子替换、批量索引的事务边界。
- 命令行工程化：子命令、查询语法解析、--json 输出、耗时统计。
- 标签体系建模：多对多关联、层级标签、计数维护与冗余字段的一致性。
================================================================================
