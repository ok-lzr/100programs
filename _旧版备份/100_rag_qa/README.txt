================================================================================
项目编号：100                    难度等级：★★★★★（大型项目）
项目名称：企业知识库 RAG 问答系统
所属分类：人工智能应用 / 信息检索 / 大模型工程
建议工时：3 ~ 4 周（约 120 ~ 180 小时）
运行环境：Python 3.10+    第三方依赖：FastAPI、uvicorn、SQLAlchemy、alembic、pydantic、pypdf、python-docx、openpyxl、sentence-transformers 或 OpenAI 兼容 Embedding 接口、numpy、redis、APScheduler、pytest、httpx、python-multipart
================================================================================

【一、项目背景与目标】

企业内部的制度、产品手册、技术文档、会议纪要通常散落在共享盘、Wiki、邮件附件里。员工
想确认“差旅报销标准是多少”时，只能靠搜索关键词然后翻十几个文件；如果去问大模型，得到
的答案往往语气笃定但内容是编造的，最危险的是它会把三个不同文档的数字混成一句看起来
很专业的话。企业场景对答案的要求不是“像人话”，而是“可核实”：每一句结论都要能追溯到
原文的具体段落，找不到依据就必须承认不知道。

本项目的目标是实现一个面向企业文档的 RAG（检索增强生成）问答系统：上传企业文档（PDF、
Word、Excel、Markdown、纯文本），系统完成解析、清洗、按语义切块、向量化与索引；用户
提问时先做混合检索（向量检索 + 关键词检索），再让大模型基于检索到的片段生成带引用编号
的回答；每条引用都能点击跳转到原文的具体位置（文档 + 页码 + 字符偏移），并展示原文片段；
检索不到足够依据时，系统必须回答“知识库中没有找到依据”而不是编造。

系统必须把四件事做扎实：一是解析质量（PDF 双栏、表格、扫描件的处理策略与失败标记）；
二是检索质量（切块策略、混合检索、重排序、召回评估）；三是答案可信（强制引用、引用
校验、无依据拒答、幻觉抑制）；四是成本与安全（API Key 管理、缓存、Token 预算、限流、
权限过滤与隐私合规）。

目标用户是：需要内部知识助手的团队、想掌握 RAG 全链路（解析 → 切块 → 向量化 → 检索 →
重排 → 生成 → 评估）的工程师、以及希望理解“为什么 RAG 会答错”的学习者。项目明确不做：
不做模型训练与微调、不做多模态（图片内容理解，仅做 OCR 占位提示）、不做跨企业多租户
SaaS、不做实时协同编辑。

本项目特别强调两个红线：一是 API Key 只能来自环境变量或加密存储，禁止硬编码、禁止提交
到仓库、禁止在日志与前端暴露；二是成本可控，必须给出单次问答的检索与生成 Token 消耗
统计、每日预算上限与超限行为（降级到只返回检索片段而不调用大模型）。

【二、功能需求清单】

本系统按四个子系统拆分：文档子系统（上传、解析与索引）、检索子系统（切块、向量化、混合
检索与重排）、问答子系统（生成、引用与拒答）、平台端（Web 界面、权限、成本与运维）。

1. 文档子系统
   1.1 文档上传：支持 PDF、DOCX、XLSX、MD、TXT、CSV 六类；单文件上限 100 MB；上传后
       计算 sha256，命中已有文档则秒传（复用解析结果）并记录引用关系。
   1.2 解析器分发：按扩展名与 MIME 选择解析器；pypdf 处理 PDF，python-docx 处理 DOCX
       （含标题层级与表格），openpyxl 处理 XLSX（每个工作表转为表格文本并保留表头），
       纯文本类按编码探测读取（UTF-8/GBK）；解析失败记录失败阶段与原因，标记文档状态
       parse_failed 并允许人工重试。
   1.3 PDF 特例处理：抽取文本时保留页码；检测“文本层几乎为空”（页均字符数 < 50）判定为
       扫描件，标记 needs_ocr 并不进入索引（提示用户先做 OCR，本项目不内置 OCR 引擎）；
       双栏 PDF 按文本框 x 坐标聚类排序（按列切分再按 y 排序），无法判定时按字符流顺序
       并在质量报告中标注“可能存在阅读顺序问题”。
   1.4 清洗规则：统一全角/半角标点、去掉页眉页脚重复行（连续页出现 ≥ 60% 的相同行判定为
       页眉页脚）、合并被硬换行拆断的段落、保留原始偏移映射（清洗后文本片段能映射回原文
       页码与字符区间，用于引用定位）。
   1.5 元数据与标签：文档名称、类型、版本、所属部门、生效日期、密级（public/internal/
       confidential）、上传人、标签；密级与部门用于检索时的权限过滤。
   1.6 文档版本：同一逻辑文档（按名称 + 部门）多次上传视为版本序列；检索默认只用最新有效
       版本，可配置为同时检索历史版本并在引用中标明版本与生效日期。
   1.7 解析质量报告：每份文档解析后生成报告（页数、字符数、空页数、表格数、疑似问题列表、
       切块数、平均块长度），在界面上可查看。
   1.8 文档删除与重建索引：删除为软删除（30 天可恢复），删除后其向量与关键词索引立即
       失效；支持整库重建索引（异步任务 + 进度）。
   1.9 增量更新：定期扫描指定目录（可选配置）导入新文件；重复文件按 sha256 去重，内容
       变更生成新版本。

2. 检索子系统
   2.1 切块策略：默认“标题感知 + 递归切分”——按 Markdown/Word 标题层级切分，再按长度
       递归切分（目标 800 字符、重叠 120 字符），尽量在段落与句子边界断开；表格整体成块
       （不跨表切分，超长表格按行分组并重复表头）；列表项保持同组不拆散。
   2.2 块元数据：块 id、文档 id、版本、页码、字符起始与结束偏移、标题路径（如“第三章 >
       3.2 报销标准”）、块类型（正文/表格/列表/代码）、字符数、token 估算。
   2.3 向量化：支持两种后端——本地 sentence-transformers（默认模型为中文友好的较小模型，
       如 paraphrase-multilingual-MiniLM-L12-v2；允许用户在配置中替换为自有 Embedding
       HTTP 接口）；批量向量化（默认批 32），带失败重试与断点续做；向量以 float32 存储。
   2.4 向量存储：本项目自行实现向量索引（numpy 矩阵 + 归一化后点积相似度），同时支持
       Redis 或本地文件持久化；数据量超过 50 万块时使用分片加载与 Top-K 预筛（先按文档
       过滤再算相似度），并在文档中说明何时应改用专用向量库。
   2.5 关键词检索：基于倒排索引（jieba 分词 + 位置信息）实现 BM25 检索，用于精确匹配
       术语、编号、专有名词（这类词向量检索经常失手）。
   2.6 混合检索与融合：向量检索与 BM25 各取 Top 30，使用 RRF（Reciprocal Rank Fusion，
       k=60）融合，得到候选 50 条；再按元数据过滤（部门、密级、版本、时间范围）。
   2.7 重排序：可选的重排阶段——使用交叉编码器（cross-encoder）或轻量打分函数（关键
       词命中数 + 标题路径匹配 + 位置先验 + 块长度惩罚）对候选重排，取 Top 8 作为生成
       上下文；重排耗时与收益必须在评估报告中量化。
   2.8 去重与多样性：相近块（余弦相似度 > 0.95 或文本重叠 > 70%）合并保留高分者；同一
       文档最多贡献 3 块，避免上下文被单一文档占满。
   2.9 检索评估：提供评估脚本与标注集（问题 + 期望命中文档/块），计算 Recall@5、Recall@10、
       MRR、nDCG@10，用于比较切块参数与检索策略；评估集默认内置 50 条示例问答。
   2.10 查询改写（可选）：对含指代或口语化的问题（如“那它多久到账”）用规则 + 大模型做
       一次查询扩展（生成 2 ~ 3 个检索式），扩展结果与原查询分别检索后融合；该功能默认
       关闭并计入成本统计。

3. 问答子系统
   3.1 生成接口：把检索到的 Top N 块作为上下文，按固定模板拼装 Prompt，要求模型“只依据
       给定材料回答、每个结论后标注引用编号、材料不足时必须回答不知道”。
   3.2 引用溯源：模型输出的引用编号形如 [1][2]，服务端解析编号并映射回块，返回结构化引用
       列表（文档名、版本、页码、标题路径、原文片段、跳转链接、相似度分数）；引用编号
       越界或缺失时标记该句为“无依据”并在响应中提示。
   3.3 引用校验：对生成答案中的每个引用，校验其块确实出现在本次上下文中；再对答案句子与
       引用块做词面重合度检查（重合度过低时降低引用可信度标记），并把校验结果随答案返回
       （verified / weak / missing）。
   3.4 无依据拒答：当最高融合分数低于阈值（可配置，默认按评估集校准）或重排后 Top 块与
       问题相似度低于阈值时，不调用大模型，直接返回“知识库中未找到足够依据”并附上最相关
       的 3 条片段供用户自行判断。
   3.5 会话与多轮：支持多轮对话，历史问题用于查询改写；历史答案中的引用不会跨轮继承；
       会话保留最近 6 轮，超过后对更早轮次做摘要（摘要也计入 Token 统计）。
   3.6 流式输出：支持 SSE 流式返回生成内容（逐段返回），引用信息在流结束后以单独事件返回；
       流式中途断开时保留已生成内容并标注“生成中断”。
   3.7 答案缓存：对规范化后的问题（去空白、统一标点、同义问法不合并）做 SHA1 键缓存，
       命中则直接返回上次结果并标注“来自缓存”；缓存默认 TTL 24 小时，可按文档变更失效
       （文档更新时清除相关缓存）。
   3.8 反馈机制：用户对答案点赞/点踩并可选择原因（答非所问、引用错误、信息过期、内容
       不完整），反馈写入 feedback 表用于后续评估；点踩记录出现在管理端。
   3.9 兜底与降级：大模型接口不可用或超出预算时，降级为返回检索片段摘要（抽取式：取
       最相关块的前 3 句 + 引用），明确提示“当前为检索模式，未经过大模型生成”。
   3.10 拒答话术分级：无检索结果、结果相关度低、结果相互矛盾（不同文档给出冲突数值）、
       问题超出知识库范围（如询问个人信息）四种情形给出不同的提示语与建议。

4. 平台端子系统（Web 界面、权限与运维）
   4.1 问答页：对话框式界面，支持流式输出、引用编号可点击展开原文、显示本次检索到的片段
       列表与分数（可折叠）、显示耗时分解（检索耗时、重排耗时、生成耗时、Token 消耗）。
   4.2 文档管理页：上传、列表（状态：待解析/解析中/已索引/解析失败/扫描件待 OCR）、解析
       质量报告、切块预览（查看每块内容与元数据）、删除与恢复、重建索引。
   4.3 检索调试页：输入问题查看完整的检索链路中间结果（BM25 Top 30、向量 Top 30、融合
       结果、重排结果、最终上下文），便于调整参数与排查“为什么没检索到”。
   4.4 评估页：上传或选择评估集运行评估，展示 Recall@K、MRR、nDCG 与不同配置的对比表。
   4.5 参数配置页：切块大小与重叠、Top K 与融合参数、相似度阈值、重排开关、模型选择、
       温度、最大输出 Token、是否启用查询改写、预算上限；配置变更记录版本与操作人。
   4.6 成本与用量：按天统计问答次数、Embedding Token、生成 Token、缓存命中率、平均耗时、
       平均成本（按配置的单价估算）；接近预算时告警，超预算时自动降级为检索模式。
   4.7 权限管理：用户与角色（admin、editor、viewer）；文档密级与部门用于检索过滤：viewer
       只能检索 public 与自身部门的 internal 文档，confidential 需显式授权；所有问答请求
       记录 user_id 与命中的文档 id，用于审计。
   4.8 审计与安全：上传、删除、导出、配置变更、密钥变更写入 audit_log；提供“查看某次问答
       用了哪些文档”的审计视图；导出文档原文需要 editor 以上权限并留痕。
   4.9 系统状态：索引块总数、向量维度、索引内存占用、解析队列长度、失败文档数、最近错误。

5. 模块清单（源码结构）
   5.1 app/main.py                 FastAPI 应用与生命周期（加载索引、校验密钥）。
   5.2 app/config.py               配置与密钥读取（环境变量优先，禁止默认弱值）。
   5.3 ingest/parsers.py           按类型分发的解析器（pdf/docx/xlsx/md/txt/csv）。
   5.4 ingest/clean.py             文本清洗、页眉页脚去除、段落合并与偏移映射。
   5.5 ingest/chunker.py           标题感知递归切块、表格成块、块元数据生成。
   5.6 ingest/pipeline.py          解析 → 清洗 → 切块 → 向量化 → 入库的编排与状态机。
   5.7 index/embedder.py           Embedding 后端（本地模型 / HTTP 接口）、批处理与重试。
   5.8 index/vector_store.py       numpy 向量矩阵、分片与持久化、Top-K 检索。
   5.9 index/keyword_index.py      jieba 分词、倒排索引与 BM25。
   5.10 retrieve/fusion.py         RRF 融合、元数据过滤、去重与多样性控制。
   5.11 retrieve/rerank.py         轻量打分与可选交叉编码器重排。
   5.12 retrieve/query_rewrite.py  规则 + 模型的查询改写（可选）。
   5.13 llm/client.py              大模型客户端（OpenAI 兼容接口）、超时重试、Token 统计、
                                    成本计算与预算控制。
   5.14 llm/prompt.py              Prompt 模板（含强制引用与拒答指令）与上下文拼装。
   5.15 llm/citation.py            引用解析、映射与校验。
   5.16 qa/service.py              问答编排：检索 → 重排 → 生成 → 引用校验 → 缓存与反馈。
   5.17 eval/dataset.py            评估集加载与指标计算（Recall@K、MRR、nDCG）。
   5.18 app/api/                   documents、search、qa、config、eval、admin 路由。
   5.19 app/tasks/                 索引重建、缓存失效、用量汇总、目录扫描任务。
   5.20 web/                       Web 界面（原生 JS + fetch + EventSource 流式）。
   5.21 tests/                     单元、接口、解析、切块、检索、引用校验与降级测试。

6. 接口清单（HTTP，节选核心）
   6.1 POST /api/v1/documents                 上传文档（multipart）
   6.2 GET  /api/v1/documents?state=&dept=&page=  文档列表
   6.3 GET  /api/v1/documents/{id}            文档详情与解析质量报告
   6.4 GET  /api/v1/documents/{id}/chunks?page=   切块预览
   6.5 DELETE /api/v1/documents/{id}          软删除
   6.6 POST /api/v1/documents/{id}/reindex    单文档重建索引
   6.7 POST /api/v1/index/rebuild             整库重建（202 + task_id）
   6.8 GET  /api/v1/index/status              索引状态与统计
   6.9 POST /api/v1/search                    纯检索调试 {query, filters, top_k}
   6.10 POST /api/v1/qa/ask                   问答（非流式）{question, filters, session_id}
   6.11 POST /api/v1/qa/stream                问答（SSE 流式）
   6.12 GET  /api/v1/qa/sessions/{id}         会话历史
   6.13 POST /api/v1/qa/feedback              反馈 {answer_id, rating, reason}
   6.14 GET  /api/v1/chunks/{chunk_id}/source 引用跳转：返回文档名、页码、原文片段与高亮
   6.15 POST /api/v1/eval/run                 运行评估 {dataset_id, config}
   6.16 GET  /api/v1/eval/results/{id}        评估结果与对比
   6.17 GET  /api/v1/config                   当前配置
   6.18 PUT  /api/v1/config                   更新配置（需 admin，写入审计）
   6.19 GET  /api/v1/usage?from=&to=          用量与成本统计
   6.20 GET  /api/v1/admin/audit?from=&to=    审计日志
   6.21 GET  /healthz                         健康检查（含 Embedding 模型与索引就绪状态）

7. 数据模型概览
   7.1 documents(id TEXT PK, name TEXT, dept TEXT, doc_type TEXT, version INT,
       sha256 TEXT, size_bytes BIGINT, security_level TEXT, effective_date TEXT,
       uploader_id TEXT, state TEXT, page_count INT, char_count INT, chunk_count INT,
       parse_report_json TEXT, storage_path TEXT, deleted_at TEXT NULL, created_at,
       updated_at)  索引 uniq_sha256(sha256)、idx_state(state)、idx_dept(dept)
   7.2 chunks(id TEXT PK, document_id FK, version INT, chunk_index INT, content TEXT,
       char_start INT, char_end INT, page_no INT, title_path TEXT, chunk_type TEXT,
       char_count INT, token_estimate INT, vec_offset INT, content_sha1 TEXT)
       索引 (document_id, chunk_index)、idx_content_sha1(content_sha1) 用于去重
   7.3 embeddings(id PK, chunk_id FK UNIQUE, dim INT, vector_path TEXT, vec_offset INT,
       model_name TEXT, created_at)  说明：向量本体存二进制文件，表中只存定位信息
   7.4 index_meta(key TEXT PK, value TEXT)  记录模型名、维度、块总数、构建时间、索引版本
   7.5 qa_sessions(id TEXT PK, user_id FK, title TEXT, created_at, updated_at)
   7.6 qa_messages(id PK, session_id FK, role TEXT, content TEXT, question_hash TEXT,
       retrieved_json TEXT, citations_json TEXT, tokens_in INT, tokens_out INT,
       cost_micro BIGINT, latency_ms INT, cache_hit INT, fallback INT, created_at)
   7.7 feedback(id PK, message_id FK, user_id, rating TEXT, reason TEXT, comment TEXT,
       created_at)
   7.8 eval_datasets(id TEXT PK, name TEXT, created_by, created_at)
   7.9 eval_items(id PK, dataset_id FK, question TEXT, expected_doc_ids_json TEXT,
       expected_chunk_ids_json TEXT, answer_hint TEXT)
   7.10 eval_runs(id TEXT PK, dataset_id FK, config_json TEXT, recall_at_5 REAL,
       recall_at_10 REAL, mrr REAL, ndcg_at_10 REAL, details_json TEXT, created_at)
   7.11 usage_daily(id PK, day TEXT, qa_count INT, embed_tokens BIGINT, gen_tokens BIGINT,
       cache_hits INT, fallback_count INT, cost_micro BIGINT)  唯一键 (day)
   7.12 audit_log(id PK, user_id, action, target_type, target_id, detail_json, ip,
       created_at)
   7.13 文件布局：storage/docs/{sha256前2位}/{sha256}.原扩展名（原文）、
       storage/vectors/{index_version}/{shard}.f32（向量分片，float32 小端）、
       storage/clean/{document_id}.jsonl（清洗后文本与偏移映射，供引用定位）、
       storage/models/（本地 Embedding 模型缓存）。

【三、里程碑拆解（建议 4 ~ 6 个阶段）】

阶段一：文档解析与清洗（约 24 小时）
  产出：六类解析器、页码与偏移映射、页眉页脚去除、扫描件检测、解析质量报告、上传与去重、
       文档状态机与失败重试。
  验收：一份 80 页含表格与双栏的 PDF 能正确解析，偏移映射能把任意片段定位回页码与字符
       区间；扫描件被正确标记为 needs_ocr 且不进入索引。

阶段二：切块与索引构建（约 22 小时）
  产出：标题感知递归切块、表格成块、块元数据、Embedding 后端封装与批处理、向量存储、
       BM25 关键词索引、索引持久化与加载、整库重建任务与进度。
  验收：1 万块文档的索引构建在 10 分钟内完成；重启服务后索引可直接加载无需重建；块预览
       可见标题路径与页码。

阶段三：检索与重排（约 26 小时）
  产出：向量检索、BM25 检索、RRF 融合、元数据过滤、去重与多样性、轻量重排、检索调试页、
       评估脚本与指标计算。
  验收：内置 50 条评估集上混合检索 Recall@10 ≥ 0.85，优于单独向量或单独 BM25；重排后
       nDCG@10 提升 ≥ 5%。

阶段四：生成、引用与拒答（约 26 小时）
  产出：Prompt 模板、大模型客户端（超时重试与 Token 统计）、SSE 流式、引用解析与校验、
       四级拒答策略、答案缓存、反馈收集、降级为检索模式。
  验收：答案中每个结论都带引用编号且可跳转原文；对知识库外问题回答“未找到依据”且不
       编造；接口不可用时自动降级并明确提示。

阶段五：平台界面与权限成本（约 22 小时）
  产出：问答页、文档管理与切块预览、检索调试、评估页、参数配置、权限过滤、用量与成本
       看板、预算控制与告警、审计日志。
  验收：viewer 用户无法检索到 confidential 文档（含通过构造 filters 绕过测试）；超预算时
       自动降级；看板数字与 usage_daily 一致。

阶段六：测试、调优与部署（约 20 小时）
  产出：覆盖率报告、RAG 全链路端到端测试、评估报告（不同切块与检索策略对比）、成本报告、
       Dockerfile 与部署文档、密钥管理与运维手册（含模型离线下载与磁盘规划）。
  验收：端到端问答在 3 秒内返回首字（本地模型）或 2 秒内（远程接口）；评估与成本报告可
       复现；按文档部署后全流程可用。

【四、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；类型注解全覆盖；数组计算统一使用 numpy。
2. 允许使用的库：标准库（hashlib、json、re、math、sqlite3、subprocess、logging、
   dataclasses、secrets、datetime）；第三方限 FastAPI、uvicorn、SQLAlchemy、alembic、
   pydantic、pypdf、python-docx、openpyxl、numpy、jieba、sentence-transformers（或仅用
   HTTP 接口替代）、redis、APScheduler、httpx、python-multipart、pytest、pytest-asyncio。
   禁止引入 LangChain、LlamaIndex、Haystack 等 RAG 框架（全链路必须自行实现，包括切块、
   融合、Prompt 拼装与引用解析）；禁止引入 FAISS、Milvus、Qdrant 作为必需依赖（向量检索
   自行实现；如作为可选扩展需在文档中说明取舍）。
3. 禁止事项：禁止硬编码 API Key、数据库口令或任何密钥（必须来自环境变量或平台加密存储，
   启动时校验缺失则拒绝启动并给出配置指引）；禁止把文档原文与用户问题写入普通日志（只
   记录 hash、长度与文档 id）；禁止把检索到的整篇文档塞进 Prompt（必须控制上下文预算）；
   禁止在无检索依据时让模型自由发挥（必须走拒答分支）；禁止把未经校验的引用编号直接
   展示给用户而不做映射。
4. 幻觉抑制的硬性要求：Prompt 必须包含“只依据材料回答、每条结论标注引用编号、材料不足
   时明确回答不知道”的指令；服务端必须做引用存在性校验与词面重合度校验；低于相似度阈值
   必须拒答；回答中出现的数字、日期、金额要额外做一次“是否在检索材料中出现”的检查，未
   出现的数字要求标注为“材料中未提及”并降低答案置信标记；所有校验结果随答案返回，前端
   必须展示。
5. 成本控制要求：统计并落库每次问答的输入/输出 Token 与估算成本（单价可配置）；设置
   日预算与月预算（默认日预算按 1000 次问答估算）；达到 80% 告警、100% 自动降级为检索
   模式；Embedding 结果按内容 sha1 去重缓存，重复内容不重复调用；相同问题命中答案缓存
   不调用模型；批量向量化按 32 条一批并在文档中说明批大小与延迟的取舍。
6. 代码组织：ingest（解析清洗切块）、index（向量化与索引）、retrieve（检索与重排）、
   llm（模型调用与引用）、qa（编排）、eval（评估）六个包必须可独立调用与测试；大模型
   客户端是唯一允许发起外部 HTTP 请求的模块；索引读写集中在 index 包，禁止在 API 层直接
   操作向量文件。
7. 编码规范：PEP 8；公有函数必须有类型注解与 docstring（注明输入长度约束与异常）；日志
   使用结构化 JSON 并含 request_id、document_id、chunk_count、tokens；禁止 print 调试；
   配置项集中在 config.py 并带默认值与校验。
8. 测试要求：覆盖率 ≥ 75%；必须包含：解析器测试（用小型样例 PDF/DOCX/XLSX）、清洗规则
   测试（页眉页脚去除与偏移映射正确性）、切块测试（边界：超长段落、表格、空文档）、
   检索测试（构造已知语料断言 Top 1 命中）、融合与重排测试、引用解析与校验测试（含越界
   编号、无引用、错误引用三类）、拒答测试（知识库外问题必须拒答）、缓存与降级测试、
   权限过滤测试、成本统计测试。大模型调用在测试中必须使用可注入的假客户端（禁止测试
   依赖真实 API）。
9. 性能要求：单机 4 核 8 GB；10 万块的向量检索（numpy 全量点积 + Top-K）≤ 200 ms；
   BM25 检索 ≤ 100 ms；端到端问答（本地 Embedding + 远程生成）首字延迟 ≤ 3 秒；整库重建
   1 万块 ≤ 10 分钟；解析 100 页 PDF ≤ 20 秒；索引内存占用按 10 万块 × 384 维 float32
   约 150 MB，文档给出容量估算表与分片建议。
10. 安全与隐私：文档内容属企业敏感数据，本地 Embedding 模式不产生外部网络调用（必须在
    配置中可验证）；使用远程接口时必须在界面与文档中明确告知数据会发送到第三方，并提供
    开关与脱敏选项（默认关闭）；API Key 只从环境变量读取、在界面只显示掩码、变更需
    admin 权限并写入审计；检索结果按用户权限过滤（在检索阶段过滤而不是生成后过滤）；
    账号注销时删除其会话与反馈记录；文档与向量数据保留策略、删除后从备份清除的时间窗
    （7 天）必须在文档中写明；禁止把用户问题与文档内容用于模型训练或任何二次用途。

【五、设计要点】

1. 数据结构：
   1.1 Chunk(id, document_id, version, index, content, page_no, char_start, char_end,
       title_path, chunk_type, token_estimate)。
   1.2 RetrievedChunk(chunk, vector_score, bm25_score, rrf_score, rerank_score, rank)。
   1.3 AnswerPayload(answer_text, citations: list[Citation], retrieved: list[RetrievedChunk],
       verified_ratio, fallback, tokens_in, tokens_out, cost_micro, latency_breakdown)。
   1.4 Citation(index_no, chunk_id, document_name, version, page_no, title_path, snippet,
       confidence: verified|weak|missing)。
   1.5 VectorIndex(matrix: np.ndarray (N×D) float32 已 L2 归一化, ids: list[str],
       shard_size, meta)。
   1.6 预算对象 Budget(daily_limit_micro, used_micro, warn_ratio=0.8, hard_stop=True)。
2. 关键算法与流程：
   2.1 解析与偏移映射：解析器输出 [(page_no, text)] → 清洗时对每页维护 (清洗后起始偏移 →
       原文页码与偏移) 的映射表 → 切块时记录块的 char_start/char_end → 引用跳转时用映射
       表反查页码与原文位置，返回原文前后各 200 字的上下文。
   2.2 切块算法：按标题层级递归（识别 Markdown 的 #、Word 的 Heading 样式、PDF 的
       字号启发式）→ 若段落组超过 target_size 则按句子边界贪心二分 → 相邻块保留 overlap
       字符（overlap 取自上一块结尾的完整句子）→ 表格整体成块，超长表格按表头 + 每 N 行
       分组并每块重复表头。
   2.3 向量检索：查询向量归一化 → scores = matrix @ query（一次 BLAS 矩阵乘）→ 用
       np.argpartition 取 Top-K 再排序；元数据过滤在检索前通过块 id 白名单（按文档过滤后的
       行索引子集）实现，避免全量计算后的无效过滤。
   2.4 BM25：score = Σ idf(t) × (tf × (k1+1)) / (tf + k1 × (1 - b + b × len/avg_len))，
       k1=1.2、b=0.75；中文用 jieba 精确模式分词，英文小写并去停用词；编号与术语（含数字
       或大写的 token）在融合时给予 1.2 倍加权。
   2.5 RRF 融合：score(d) = Σ_r 1 / (k + rank_r(d))，k=60；两路结果合并后按融合分排序；
       同一块在两路都命中时自然获得更高分。
   2.6 重排打分（轻量版）：final = 0.5 × 归一化融合分 + 0.2 × 查询词命中率 + 0.15 ×
       标题路径匹配度 + 0.1 × 位置先验（文档开头权重更高）+ 0.05 × 长度适配度（越接近
       target_size 越高）；权重集中定义并可通过配置调整。
   2.7 上下文拼装：按最终顺序取 Top 8 块，每块加编号与来源标注（文档名 + 页码 + 标题路径），
       总 Token 预算默认 3000（超出时按分数从低到高裁剪），并在日志记录实际使用量。
   2.8 引用校验：从答案中正则提取 [n] → 校验 n 在上文编号范围内 → 对每个引用计算答案
       句子与该块内容的词面重合度（中文按 2-gram，英文按词），重合度 ≥ 0.35 标记 verified，
       0.15 ~ 0.35 标记 weak，< 0.15 标记 missing；答案中未标注引用的句子计入
       unverified_sentence_count 并在前端提示。
   2.9 数值一致性检查：用正则抽取答案中的数字/金额/日期，检查是否在任一引用块中出现
       （允许格式差异，如 1,000 与 1000、2025-01-15 与 2025年1月15日）；未出现的数字列出
       清单并提示用户核对。
   2.10 拒答判定：融合最高分 < threshold_low 或重排最高分 < 0.25 时拒答；若最高与次高分
       差距极小（< 0.02）且来自不同文档，提示“材料可能存在冲突，请人工确认”并同时列出。
   2.11 缓存键与失效：question_hash = sha1(规范化问题 + 过滤器 + 配置版本)；文档更新或
       删除时按受影响的块 id 反查缓存记录并失效（qa_messages.retrieved_json 中记录块 id
       列表，失效时按块 id 匹配删除或标记 stale）。
3. 数据库主要表结构：见功能清单第 7 节；补充：
   3.1 chunks.content 建议使用数据库的 TEXT 类型；大文本查询只在需要展示时读取，检索只
       用向量与倒排索引，避免全表扫描。
   3.2 embeddings 表与向量文件的对应关系必须可由 index_meta.index_version 唯一确定；
       重建索引时写入新版本目录，切换后旧版本保留 24 小时再删除，保证切换期间可回滚。
   3.3 qa_messages 记录 retrieved_json 与 citations_json 便于审计与缓存失效；表按天归档，
       明细保留 90 天，聚合数据长期保留。
   3.4 usage_daily 由定时任务汇总写入，问答热路径只更新 Redis 计数，避免每次问答写库。
4. 接口设计要点：
   4.1 /api/v1/qa/ask 与 /qa/stream 的过滤器字段包含 dept、security_level、doc_ids、
       date_from、date_to，服务端必须把用户权限与请求过滤取交集（不能只信任请求参数）。
   4.2 流式响应事件类型：event: token（增量文本）、event: citation（引用列表）、
       event: usage（Token 与耗时）、event: done（结束）；异常时发送 event: error 并结束。
   4.3 引用跳转接口返回 {document_id, document_name, page_no, title_path, snippet,
       highlights: [[start, end], ...]}，前端可据此高亮。
   4.4 检索调试接口返回各阶段中间结果与耗时，仅在开发模式或 admin 角色下开放。
   4.5 所有响应中的文档内容片段长度受限（默认 500 字符），避免通过问答接口批量导出原文。

【六、运行方式与示例】

1. 安装与初始化
   python -m venv .venv && .venv\Scripts\activate
   pip install fastapi uvicorn sqlalchemy alembic pydantic pypdf python-docx openpyxl
   pip install numpy jieba sentence-transformers redis apscheduler httpx python-multipart
   pip install pytest pytest-asyncio
   copy .env.example .env
   在 .env 中填写（示例键名，值为占位）：
     LLM_API_BASE=https://your-llm-endpoint/v1
     LLM_API_KEY=（仅本地环境变量注入，禁止提交到仓库）
     LLM_MODEL=your-chat-model
     EMBEDDING_BACKEND=local            （local 或 http）
     EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
     DB_URL=sqlite:///./data/kb.db
     DAILY_BUDGET_MICRO=5000000         （即 5 元，按配置单价估算）
   alembic upgrade head
2. 启动
   uvicorn app.main:app --host 127.0.0.1 --port 8060
   浏览器访问 http://127.0.0.1:8060
   首次启动会加载本地 Embedding 模型（首次需联网下载，之后离线可用）。
3. 命令行工具
   python -m app.cli ingest --dir D:\docs --dept 财务部 --security internal
   python -m app.cli search --query "差旅报销标准" --top-k 5 --debug
   python -m app.cli ask --query "出差住宿费上限是多少" --filters dept=财务部
   python -m app.cli eval --dataset eval/finance_qa.jsonl --top-k 10
4. 示例一（上传文档与解析报告）
   请求：POST /api/v1/documents（multipart：file=差旅管理制度_v3.pdf，dept=财务部，
        security_level=internal）
   响应：201
   {"document_id": "doc-71af", "sha256": "4c8a...", "state": "indexed", "page_count": 42,
    "char_count": 61320, "chunk_count": 96, "parse_report": {
      "empty_pages": 1, "tables": 7, "needs_ocr": false, "layout": "single_column",
      "issues": ["第 12 页存在疑似表格跨页，已按表头重复处理"]}}
5. 示例二（问答与引用）
   请求：POST /api/v1/qa/ask
   {"question": "出差住宿费的标准上限是多少？", "filters": {"dept": "财务部"},
    "session_id": "s-32ba"}
   响应：200
   {
     "answer": "依据《差旅管理制度 v3》，一线城市住宿费标准上限为每人每晚 600 元[1]，
       二线及其他城市为 450 元[1]。超出标准部分需由个人承担[2]。",
     "citations": [
       {"no": 1, "chunk_id": "ck-9f21", "document_name": "差旅管理制度_v3.pdf",
        "version": 3, "page_no": 14, "title_path": "第三章 费用标准 > 3.2 住宿费",
        "snippet": "一线城市每人每晚不超过 600 元，二线及其他城市不超过 450 元……",
        "confidence": "verified"},
       {"no": 2, "chunk_id": "ck-9f44", "document_name": "差旅管理制度_v3.pdf",
        "version": 3, "page_no": 16, "title_path": "第三章 费用标准 > 3.5 超标准处理",
        "snippet": "超过标准部分由出差人自行承担……", "confidence": "verified"}
     ],
     "verified_ratio": 1.0, "unverified_sentences": 0, "numeric_check": {"checked": 3,
       "missing": []},
     "retrieved": [
       {"chunk_id": "ck-9f21", "vector_score": 0.812, "bm25_score": 7.42,
        "rrf_score": 0.0328, "rerank_score": 0.91, "page_no": 14},
       {"chunk_id": "ck-9f44", "vector_score": 0.766, "bm25_score": 5.10,
        "rrf_score": 0.0291, "rerank_score": 0.83, "page_no": 16}
     ],
     "fallback": false, "cache_hit": false,
     "usage": {"tokens_in": 2184, "tokens_out": 176, "cost_micro": 4120,
               "latency_ms": {"retrieve": 63, "rerank": 41, "generate": 1620}}
   }
6. 示例三（无依据拒答）
   请求：POST /api/v1/qa/ask {"question": "公司今年的股权激励计划具体条款是什么？"}
   响应：200
   {"answer": "知识库中没有找到与该问题相关的依据，因此无法回答。以下是检索到的相关度
      最高的片段，供你自行判断：[片段 1] 《员工手册 v5》第 3 页 提到“激励计划另行规定”……",
    "citations": [], "refusal_reason": "NO_RELEVANT_CONTEXT",
    "retrieved": [{"chunk_id": "ck-31aa", "rerank_score": 0.18, "page_no": 3}],
    "fallback": true, "usage": {"tokens_in": 0, "tokens_out": 0, "cost_micro": 0,
    "latency_ms": {"retrieve": 58, "rerank": 22, "generate": 0}}}
   说明：未触发大模型调用，成本为 0。
7. 示例四（预算耗尽后的降级）
   请求：POST /api/v1/qa/stream（当日预算已用 100%）
   SSE 事件：
   event: warning
   data: {"message": "今日大模型预算已用尽，已切换为检索模式，仅返回原文片段"}
   event: token
   data: {"text": "一线城市住宿费上限为每人每晚 600 元（《差旅管理制度 v3》第 14 页）"}
   event: usage
   data: {"fallback": true, "tokens_in": 0, "tokens_out": 0, "cost_micro": 0}
   event: done
   data: {"ok": true}
8. 示例五（异常输入）
   上传扫描件 PDF（无文本层）
   响应：201 {"document_id": "doc-90ff", "state": "needs_ocr",
         "parse_report": {"avg_chars_per_page": 3.1,
         "issues": ["检测到扫描件，需先进行 OCR 处理后再上传文本版"]}}
   问题为空字符串
   响应：400 {"code": "BAD_QUESTION", "message": "问题不能为空"}
   模型接口超时（重试 2 次后仍失败）
   响应：200 {"answer": "大模型服务暂时不可用，已为你返回检索到的原文片段：……",
         "fallback": true, "error_detail": "LLM_TIMEOUT"}

【七、验收标准】

[ ] 1. 六类文档（PDF/DOCX/XLSX/MD/TXT/CSV）均可上传、解析、切块并进入索引，状态正确流转。
[ ] 2. 80 页含表格与标题的 PDF 解析后，任意引用片段能准确定位到页码与原文偏移（误差为 0）。
[ ] 3. 扫描件被识别为 needs_ocr，不进入索引，界面给出明确提示。
[ ] 4. 重复上传同一文件（同 sha256）实现秒传，不重复解析与向量化。
[ ] 5. 内置 50 条评估集上混合检索 Recall@10 ≥ 0.85，且优于单独向量检索与单独 BM25。
[ ] 6. 开启重排后 nDCG@10 相比未重排提升 ≥ 5%，耗时增加不超过 200 ms。
[ ] 7. 答案中每个结论都带引用编号，点击可查看原文片段与页码；引用越界或缺失被标记为
      missing 并在界面提示。
[ ] 8. 对知识库中不存在答案的问题（如询问未收录的激励计划），系统拒答且不调用大模型
      （tokens_in = 0，cost_micro = 0）。
[ ] 9. 答案中的数字与日期全部在引用材料中出现；构造含幻觉数字的答案时 numeric_check
      能列出缺失项。
[ ] 10. 引用校验生效：答案句子与引用块词面重合度过低时标记为 weak，前端显示可信度提示。
[ ] 11. viewer 角色无法检索到 confidential 文档（含构造 filters 尝试绕过的测试）；
       internal 文档对非本部门用户不可见。
[ ] 12. 成本统计准确：usage_daily 的 Token 与成本与逐条 qa_messages 汇总一致（误差 0）；
      达到 80% 预算告警、100% 自动降级。
[ ] 13. 答案缓存生效：相同问题第二次提问 cache_hit=true 且不调用模型；文档更新后相关
      缓存失效。
[ ] 14. 10 万块索引下向量检索 ≤ 200 ms，端到端首字延迟 ≤ 3 秒（本地 Embedding）。
[ ] 15. pytest 覆盖率 ≥ 75%，含解析、清洗偏移映射、切块、检索、引用校验、拒答、缓存、
      权限过滤、成本统计九类专项测试；测试中无真实大模型调用（使用注入的假客户端）。
[ ] 16. 环境变量缺失（LLM_API_KEY 或 EMBEDDING 配置）时服务拒绝启动并给出可操作的
      配置指引；日志与前端均不出现密钥明文。

【八、可选扩展】

1. 接入 OCR（如 PaddleOCR 或 Tesseract）处理扫描件，把图片 PDF 转为可检索文本。
2. 使用专用向量库（FAISS、Qdrant、pgvector）替换自研 numpy 索引，比较召回、延迟与运维
   成本，并说明切换条件。
3. 增加交叉编码器重排模型（bge-reranker 类），量化其对 nDCG 的提升与延迟代价。
4. 增加 GraphRAG 思路：抽取实体与关系构建知识图谱，回答“A 与 B 的关系”这类跨文档问题。
5. 增加答案引用高亮跳转的前端 PDF.js 预览，直接定位到页码与文本位置。
6. 增加多租户与部门级索引隔离、文档权限审批流与到期自动回收。
7. 增加答案质量自动评估（用大模型做裁判打分）与人工标注闭环，持续优化检索参数。

【九、涉及知识点】

- 文档解析：PDF 文本层与页码、DOCX 样式与表格、XLSX 表头处理、编码探测、偏移映射
- 文本处理：清洗规则、页眉页脚识别、句子边界、中文分词（jieba）、2-gram 重合度
- 向量检索：Embedding 原理与批处理、L2 归一化与点积、Top-K 的 argpartition、分片与内存
- 关键词检索：倒排索引、BM25 参数、术语与编号的精确匹配价值
- 混合检索与重排：RRF 融合、特征加权打分、数据多样性与去重
- 大模型工程：Prompt 设计与指令约束、流式输出（SSE）、Token 统计与成本模型、超时重试与
  降级、答案缓存与失效
- 幻觉抑制：强制引用、引用存在性与词面校验、数值一致性检查、阈值拒答与冲突提示
- 评估与实验：Recall@K、MRR、nDCG、评估集构建、参数对比与可复现实验记录
- 安全与合规：密钥管理（环境变量与掩码展示）、权限过滤与越权防护、数据最小化与保留
  策略、审计留痕与第三方数据外发告知
================================================================================
