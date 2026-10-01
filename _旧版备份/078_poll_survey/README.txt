================================================================================
项目编号：078                    难度等级：★★★★☆（中型项目，偏难）
项目名称：问卷调查与统计系统
所属分类：Web 后端 / 数据采集与统计
建议工时：5 ~ 7 天
运行环境：Python 3.10+    第三方依赖：fastapi、uvicorn、sqlalchemy、pydantic、jinja2、openpyxl、matplotlib、passlib[bcrypt]、python-jose[cryptography]、pytest、httpx
================================================================================

【一、项目背景与目标】

做一次用户调研、员工满意度调查或活动报名，最麻烦的从来不是发问卷，而是收上来的数据：
Excel 附件各填各的格式、多选题被填成一句话、开放式问题散落在几百行文本里、
想画个图表还得手工透视。问卷工具要收费，或者强制绑定账号、把数据存在别人服务器上。

本项目实现一套可自建的问卷调查与统计系统，覆盖完整链路：
设计问卷（支持单选、多选、填空、评分、下拉、矩阵五种题型）→ 设置逻辑与必填 →
发布（获取分享链接与二维码）→ 回收答卷（匿名或实名、同一人限填一次）→
实时统计（每题选项分布、填空词云数据、评分均值与分布）→ 导出 Excel 与生成图表。

技术难点主要在四处：一是题型与选项的建模（既要灵活可扩展，又要能高效聚合）；
二是统计口径的严谨性（多选题的分母是答卷数还是选项被选次数，必须写清楚）；
三是匿名答卷与"一人一次"限制的平衡（匿名又要防重复刷，只能靠设备指纹与 IP 限制）；
四是答卷数据的存储结构（明细行 vs JSON 列）对统计查询性能的影响。

【二、功能需求清单】

1. 核心功能
   1.1 问卷管理：创建问卷（标题、说明、开始/结束时间、匿名与否、是否允许修改答案），
       复制问卷、归档问卷、删除问卷（软删除）。
   1.2 题目管理：支持单选、多选、填空、评分（1~5 或 1~10）、下拉、矩阵六种题型，
       每题可设标题、说明、是否必填、选项列表、最大选择数、填空长度上限。
   1.3 题目排序：支持上移/下移/拖拽调整顺序，顺序字段 step 以 10 递增便于插入。
   1.4 逻辑跳转（可选开启）：题 A 选择某选项后跳转到指定题号，形成简单分支问卷。
   1.5 问卷发布：状态 draft → published → closed；发布后题目不可修改（保证数据可解释）。
   1.6 回收答卷：匿名或实名（需登录）提交，服务端校验必填、题型匹配、选项合法性。
   1.7 防重复：实名问卷按 user_id 唯一；匿名问卷按设备指纹（前端生成的 UUID）+ IP 限制，
       同一指纹只允许提交一次（可配置为"允许覆盖上次答案"）。
   1.8 我的答卷：实名用户可查看与修改自己已提交的答卷（仅当问卷允许修改且未关闭）。
   1.9 实时统计：每题选项计数与百分比、填空题原始列表与词频 TopN、评分均值/中位数/分布。
   1.10 图表导出：用 matplotlib 生成柱状图、饼图、评分分布直方图，返回 PNG。
   1.11 数据导出：导出 Excel（openpyxl，一份明细表 + 一份统计表）与 CSV。
   1.12 交叉分析：按某个单选/下拉题分组，统计另一个题目的选项分布（用于差异化分析）。
   1.13 权限：owner 可编辑问卷并查看全部数据；协作者只能查看统计不能导出原始明细。
   1.14 回收上限：问卷可设置最大回收份数，达到上限自动停止接收并提示。

2. 输入与交互
   2.1 设计侧与答题侧均通过 JSON 交互；答题页为服务端渲染的 HTML（jinja2）。
   2.2 提交答卷请求：{"device_id":"uuid","answers":[{"question_id":12,"value":["A"]},
       {"question_id":13,"value":"建议增加夜间模式"},{"question_id":14,"value":4},
       {"question_id":15,"value":{"row":"服务","col":"满意"}}]}
   2.3 value 类型约定：单选/下拉为字符串、多选为字符串数组、填空为字符串、
       评分为整数、矩阵为 {"row": "...","col": "..."} 或数组形式的成对选择。
   2.4 分页参数统一 page（默认 1）与 page_size（默认 20，最大 200）。
   2.5 统计接口参数：question_id 指定题目，bucket 指定填空词频的分词方式（默认按标点与空格切分）。
   2.6 交互方式：REST 接口 + 答题页 /s/{share_code} + 统计页 /stats/{survey_id}（内置极简 HTML）。

3. 输出与展示
   3.1 统一响应 { "code": 0, "message": "ok", "data": {...} }（答题页与图表接口除外）。
   3.2 发布响应：{"code":0,"data":{"survey_id":7,"share_code":"aB3xK9zQ",
       "share_url":"https://s.example.com/s/aB3xK9zQ","status":"published",
       "start_at":"...","end_at":"..."}}
   3.3 统计响应（选择题）：{"question_id":12,"type":"single","answered_count":186,
       "total_responses":200,"options":[{"key":"A","text":"非常满意","count":96,
       "percent":0.5161},{"key":"B","text":"满意","count":62,"percent":0.3333}],
       "skipped_count":14}
   3.4 统计响应（填空题）：{"question_id":13,"type":"text","answered_count":151,
       "top_words":[{"word":"价格","count":38},{"word":"客服","count":21}],
       "samples":["希望价格更优惠","客服响应快"]}（samples 最多返回 50 条，避免大响应）
   3.5 统计响应（评分题）：{"question_id":14,"type":"rating","answered_count":190,
       "average":4.12,"median":4,"distribution":[{"score":1,"count":3},...,{"score":5,"count":88}]}
   3.6 Excel 导出包含两个 Sheet：明细（每行一份答卷，每题一列）与统计（每题一行，含各选项占比）。
   3.7 图表接口返回 image/png，响应头带 X-Chart-Type 与 Content-Disposition: inline。

4. 异常与边界处理
   4.1 问卷不存在或已删除：404 / 40401。
   4.2 问卷未开始（now < start_at）：403 / 40301；已结束或已关闭：403 / 40302。
   4.3 问卷为草稿状态不接收提交：403 / 40303。
   4.4 匿名问卷未提供 device_id：422 / 42201（前端必须生成并持久化 UUID）。
   4.5 必填题未作答：422 / 42202，data 返回缺失的 question_id 列表。
   4.6 单选提交多个值：422 / 42203；多选超出 max_choices：422 / 42204。
   4.7 选项 key 不在题目选项内：422 / 42205（防止篡改提交）。
   4.8 填空题超过长度上限：422 / 42206，data 返回 limit。
   4.9 评分值超出范围：422 / 42207，data 返回允许区间。
   4.10 实名问卷重复提交且不允许修改：409 / 40901；匿名问卷同一设备重复提交：409 / 40902。
   4.11 回收份数已达上限：409 / 40903，答题页显示"问卷已收集足够的答卷"。
   4.12 已发布问卷尝试修改题目：409 / 40904，提示需先复制为新问卷。
   4.13 统计接口在答卷数为 0 时返回空结构而非报错（percent 全为 0，average 为 null）。
   4.14 导出接口无权限（非 owner 且非 admin）：403 / 40304。
   4.15 交叉分析的分组题非单选/下拉类型：422 / 42208。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：fastapi、uvicorn[standard]、sqlalchemy 2.0、pydantic v2、
   jinja2（答题页与统计页模板）、openpyxl（Excel 导出）、matplotlib（图表，无界面后端 Agg）、
   passlib[bcrypt]、python-jose[cryptography]、pytest、httpx、alembic。
   中文分词不引入第三方库：填空词频用正则切分 + 停用词表（内置小词表）实现，
   并在文档中标明这是"近似词频"，如需分词可扩展 jieba（可选依赖）。
3. 图表渲染：必须设置 matplotlib.use("Agg")，禁止依赖图形界面；
   中文字体需显式指定（如 SimHei 或 Microsoft YaHei），找不到字体时回退为不显示中文并记录警告。
4. 禁止事项：禁止把 JSON 提交的原始答案直接存入数据库而不校验选项合法性。
5. 禁止事项：禁止在统计接口里把全部答卷加载到内存后循环统计（必须用 SQL 聚合）。
6. 禁止事项：禁止在模板中直接输出用户填写的 HTML（jinja2 自动转义必须开启）。
7. 代码组织（必须有以下模块）：
   app/main.py、app/config.py（上传/导出目录、字体路径、限流参数）
   app/database.py、app/models.py、app/schemas.py、app/deps.py
   app/core/validators.py（按题型校验答案，纯函数）
   app/core/token.py（share_code 生成、设备指纹哈希）
   app/core/words.py（填空分词、停用词、词频统计）
   app/services/survey_service.py、question_service.py、response_service.py
   app/services/stats_service.py（各题型聚合 SQL）、cross_service.py（交叉分析）
   app/exporters/excel_export.py、csv_export.py
   app/charts/render.py（柱状图、饼图、直方图生成 PNG BytesIO）
   app/routers/auth.py、surveys.py、questions.py、responses.py、stats.py、export.py
   app/templates/survey.html、thanks.html、stats.html、error.html
   tests/test_validate.py、test_submit_flow.py、test_stats.py、test_export.py、test_dedup.py
8. 编码规范：所有函数带类型注解与 docstring；统计口径必须在 docstring 中写明（分母是什么）。
9. 编码规范：所有时间以 UTC 存储，展示按配置时区转换；日志不记录匿名答卷内容原文。
10. 编码规范：涉及用户输入的查询必须参数化，导出文件名需清洗（禁止路径分隔符）。

【四、设计要点】

1. 数据结构（核心表与字段）
   表 users：
     id BIGINT PK、username VARCHAR(32) UNIQUE、password_hash VARCHAR(128)、
     real_name VARCHAR(32) NULL、is_active BOOLEAN、created_at DATETIME
   表 surveys：
     id BIGINT PK
     share_code CHAR(8) UNIQUE NOT NULL（发布链接用，Base62 随机）
     title VARCHAR(200) NOT NULL、description TEXT NULL
     status VARCHAR(16) NOT NULL DEFAULT 'draft'（draft / published / closed）
     is_anonymous BOOLEAN DEFAULT 1
     allow_edit BOOLEAN DEFAULT 0（允许提交者修改答案）
     allow_multiple_devices BOOLEAN DEFAULT 0
     max_responses INTEGER NULL
     response_count INTEGER NOT NULL DEFAULT 0（冗余计数，用于上限判断）
     start_at DATETIME NULL、end_at DATETIME NULL
     owner_id FK(users.id)、created_at DATETIME、updated_at DATETIME、deleted_at DATETIME NULL
     索引：uk_surveys_share_code(share_code) 唯一、idx_surveys_owner(owner_id, status)
   表 questions：
     id BIGINT PK、survey_id FK
     qtype VARCHAR(16) NOT NULL（single / multiple / text / rating / select / matrix）
     title VARCHAR(300) NOT NULL、hint VARCHAR(300) NULL
     is_required BOOLEAN DEFAULT 0
     step INTEGER NOT NULL（排序，10/20/30...）
     min_choices INTEGER NULL、max_choices INTEGER NULL（多选限制）
     text_max_length INTEGER DEFAULT 500
     rating_min SMALLINT DEFAULT 1、rating_max SMALLINT DEFAULT 5
     matrix_rows JSON NULL、matrix_cols JSON NULL（矩阵题的行列定义）
     jump_rules JSON NULL（[{"option":"A","goto_step":3},...] 逻辑跳转）
     is_active BOOLEAN DEFAULT 1
     UNIQUE(survey_id, step)
     索引：idx_q_survey(survey_id, step)
   表 options：
     id BIGINT PK、question_id FK、key VARCHAR(8) NOT NULL（A/B/C/1/2/3）、
     text VARCHAR(300) NOT NULL、step INTEGER NOT NULL、is_active BOOLEAN DEFAULT 1
     UNIQUE(question_id, key)
     索引：idx_opt_question(question_id, step)
   表 responses（一份答卷）：
     id BIGINT PK
     survey_id FK、user_id FK NULL（匿名为 NULL）
     device_id_hash CHAR(64) NULL（前端 UUID + 服务端盐的 SHA-256）
     ip_prefix VARCHAR(45) NULL（/24 或 /48 网段，用于粗粒度分析）
     is_complete BOOLEAN DEFAULT 1
     submitted_at DATETIME NOT NULL
     duration_seconds INTEGER NULL（前端上报的填写时长，仅统计参考）
     ua_type VARCHAR(16) NULL
     is_test BOOLEAN DEFAULT 0（创建者自测数据，统计时默认剔除）
     索引：idx_resp_survey_time(survey_id, submitted_at)、
           idx_resp_user(survey_id, user_id)、idx_resp_device(survey_id, device_id_hash)
     防重约束：UNIQUE(survey_id, user_id)（仅实名，user_id 为 NULL 不参与，用部分唯一索引表达）
   表 answers（答案明细，一行一题一答卷）：
     id BIGINT PK
     response_id FK(responses.id) ON DELETE CASCADE
     survey_id BIGINT NOT NULL（冗余，便于单表聚合）
     question_id FK(questions.id)
     option_ids JSON NULL（选择类题选中项的 option_id 数组，便于 join 统计）
     text_value TEXT NULL（填空题原文）
     rating_value SMALLINT NULL（评分题分值）
     matrix_value JSON NULL（[{"row":"服务","col":"满意"},...]）
     answered_at DATETIME
     UNIQUE(response_id, question_id)
     索引：idx_ans_survey_question(survey_id, question_id)、idx_ans_question(question_id)
     说明：选项既存 option_ids（JSON，便于还原答案）又通过 answer_options 关联表统计，
     是"写入简单 + 查询高效"的折中；若追求纯规范化可去掉 option_ids，只保留关联表。
   表 answer_options（选择类答案与选项的关联，用于高效聚合）：
     id BIGINT PK、answer_id FK、question_id BIGINT NOT NULL、option_id FK、survey_id BIGINT NOT NULL
     UNIQUE(answer_id, option_id)
     索引：idx_ao_option(option_id)、idx_ao_question(question_id)
   表 survey_stats_cache（统计缓存，可选）：
     id PK、survey_id FK、question_id FK、stat_key VARCHAR(64)、value JSON、
     updated_at DATETIME、UNIQUE(survey_id, question_id, stat_key)
     说明：答卷量 > 5000 时启用缓存（TTL 60 秒），否则实时聚合。

2. 关键算法或流程
   创建与发布问卷：
     步骤 1：创建 survey（status=draft），owner_id 为当前用户。
     步骤 2：逐题创建 question 与 options；step 以 10 递增。
     步骤 3：发布时校验：至少 1 道题；单选/多选/下拉题至少有 2 个选项；
             评分题 rating_min < rating_max；矩阵题行列均非空；逻辑跳转目标存在。
     步骤 4：生成 share_code（8 位 Base62，唯一索引兜底，冲突重试 5 次）。
     步骤 5：status 置为 published，记录 published_at；此后题目字段禁止修改
             （只允许改标题、说明、结束时间、回收上限）。
   提交答卷（一个事务）：
     步骤 1：按 share_code 取问卷，校验 status == 'published'、时间窗口、回收上限。
     步骤 2：实名问卷校验登录；匿名问卷校验 device_id 非空并计算 device_id_hash。
     步骤 3：防重：实名按 (survey_id, user_id) 查询；匿名按 (survey_id, device_id_hash) 查询。
             命中且 allow_edit=0 → 40901/40902；命中且 allow_edit=1 → 走"更新答卷"分支。
     步骤 4：逐个答案按题型校验（core/validators.py）：
             单选：value 为字符串且属于该题 option.key 集合；
             多选/下拉多选：value 为数组，长度在 [min_choices, max_choices] 内，元素均合法且不重复；
             填空：字符串，去首尾空白后非空（必填时），长度 <= text_max_length；
             评分：整数且在 [rating_min, rating_max]；
             矩阵：数组，每行的列值均合法，且必填时所有行都要有值。
             校验失败收集全部错误后一次性返回（不逐条中断），便于前端一次性标红。
     步骤 5：insert responses；批量 insert answers（用 executemany / bulk_insert_mappings）；
             对选择类答案同时批量 insert answer_options。
     步骤 6：UPDATE surveys SET response_count = response_count + 1 WHERE id = :id
             AND (max_responses IS NULL OR response_count < max_responses)；
             rowcount = 0 时说明已达上限 → 回滚并返回 40903（并发下防止超额回收）。
     步骤 7：提交；失效该问卷的统计缓存。
   逻辑跳转：
     按 step 升序遍历题目；若当前题命中 jump_rules（选中了某选项），
     则跳过 step 介于当前题与 goto_step 之间的题目（这些题不计入必填校验，也不落库）。
     跳转规则最多支持两级嵌套，禁止形成环（发布时用深度优先检测环并拒绝发布）。
   统计口径（必须在接口文档与 docstring 中写明）：
     选择题的 percent 分母 = 该题的 answered_count（作答人数），不是总答卷数；
     同时返回 total_responses（问卷总答卷数）与 skipped_count（未答该题人数），
     让使用者能自行换算。多选题的 percent 之和会大于 1，这是正确行为（可多选）。
     评分题 average 的分母同样是 answered_count；median 用 SQL 的窗口函数或
     在 Python 中对已排序的分值数组取中位数（数据量大时用 SQL 近似法）。
   选择题聚合 SQL（一次查询完成，禁止循环）：
     SELECT o.id, o.key, o.text,
            COUNT(ao.id) AS cnt,
            (SELECT COUNT(*) FROM answers a2 WHERE a2.question_id = :qid) AS answered_count
     FROM options o LEFT JOIN answer_options ao ON ao.option_id = o.id
     WHERE o.question_id = :qid AND o.is_active = 1
     GROUP BY o.id, o.key, o.text ORDER BY o.step;
     百分比在 Python 中一次算出（cnt / answered_count），零除时取 0。
   填空题词频：
     步骤 1：取该题全部 text_value（只取 text_value 与问卷过滤条件，不取其它列）。
     步骤 2：对每条文本用正则 [\u4e00-\u9fa5]+|[A-Za-z0-9]+ 切分为词。
     步骤 3：过滤停用词表（的、了、是、我、你、和、就、都、很、想要…约 100 个）。
     步骤 4：过滤长度 1 的单字（除专有名词场景，可通过参数 include_single=true 保留）。
     步骤 5：Counter 统计后取 TopN（默认 50）。
     说明：这是"近似词频"，不引入分词库也能给出可用的关键词热度；文档中明确该口径。
   交叉分析：
     输入：group_question_id（必须为 single / select 题）、metric_question_id。
     实现：一次 JOIN 查询返回 (group_option, metric_option, count) 三元组，
     在 Python 中组装成二维表，每个分组内的百分比分母为该分组的答卷数。
     禁止对每一组单独发一条 SQL（会产生 N+1 查询）。
   图表渲染：
     matplotlib.use("Agg")；中文用 FontProperties 指定字体文件（配置项 CHART_FONT_PATH）。
     柱状图：每个选项一根柱，柱顶标注数量与百分比；
     饼图：选项数 <= 8 时使用，否则自动降级为柱状图（避免标签重叠）；
     评分直方图：x 轴为分值区间，y 轴为人数，并画一条均值的虚线。
     输出到 io.BytesIO，response 直接返回 media_type="image/png"。
   导出 Excel（openpyxl）：
     Sheet1 "明细"：第一行表头（答卷编号、提交时间、答题用时、每道题的列，
       多选答案用逗号拼接、矩阵用"行=列;行=列"拼接）；每份答卷一行。
     Sheet2 "统计"：每题一行，列为题目、题型、作答人数、各选项数量与占比
       （选项数不同的题按最多选项数展开，其余留空）；评分题附均值。
     Sheet3 "说明"：导出时间、问卷标题、统计口径说明、答卷总数。
     写入使用 write_only 模式（大答卷量时内存占用可控）。

3. 接口设计（HTTP 前缀 /api/v1；答题页在 /s/{share_code}）
   POST /api/v1/auth/register、POST /api/v1/auth/login
     返回 JWT（HS256），密钥读 JWT_SECRET_KEY（>= 32 字节）。
   POST /api/v1/surveys   需登录
     请求：{"title":"2024 客户满意度调查","description":"约 3 分钟","is_anonymous":true,
           "allow_edit":false,"start_at":null,"end_at":null,"max_responses":1000}
     响应 201：{"code":0,"data":{"survey_id":7,"status":"draft","share_code":null}}
     失败：422/42209（标题为空或超长）。
   GET /api/v1/surveys?status=published&page=1&page_size=20   需登录
     响应 200：我创建的问卷列表，含 response_count、题目数、状态。
   GET /api/v1/surveys/{survey_id}   需登录（owner 或协作者）
     响应 200：问卷详情 + 题目与选项（设计视图，含 is_required 等全部配置）。
   PATCH /api/v1/surveys/{survey_id}   需 owner
     请求：{"title":"新标题","end_at":"2024-06-30T00:00:00Z","max_responses":2000}
     行为：已发布问卷只允许改标题、说明、结束时间、回收上限；其它字段返回 409/40904。
   DELETE /api/v1/surveys/{survey_id}   需 owner
     响应 200：软删除；已有答卷时需 confirm=true，否则 409/40905。
   POST /api/v1/surveys/{survey_id}/duplicate   需 owner
     响应 201：复制问卷（含题目与选项），status=draft，新的 survey_id。
   POST /api/v1/surveys/{survey_id}/publish   需 owner
     响应 200：{"code":0,"data":{"share_code":"aB3xK9zQ","share_url":"https://s.example.com/s/aB3xK9zQ",
              "status":"published"}}
     失败：422/42210（题目配置不完整，data 含具体原因列表）、409/40904（已发布）。
   POST /api/v1/surveys/{survey_id}/close   需 owner
     响应 200：status=closed，后续提交返回 403/40302。
   POST /api/v1/surveys/{survey_id}/questions   需 owner（仅 draft）
     请求：{"qtype":"multiple","title":"您使用过哪些功能？","is_required":true,
           "min_choices":1,"max_choices":3,
           "options":[{"key":"A","text":"报表导出"},{"key":"B","text":"批量导入"}]}
     响应 201：{"code":0,"data":{"question_id":12,"step":10,"option_count":2}}
     失败：422/42211（选项不足两个）、409/40904（已发布不可增删题）。
   PATCH /api/v1/questions/{question_id}   需 owner（仅 draft）
     请求：{"title":"新题目标题","is_required":false,"min_choices":2,"max_choices":4,
           "options":[{"key":"A","text":"..."},{"key":"B","text":"..."}]}
     行为：options 传全量覆盖，已存在的 key 做更新，缺失的做软删除（保留历史答案引用）。
   DELETE /api/v1/questions/{question_id}   需 owner（仅 draft），软删除。
   PUT /api/v1/surveys/{survey_id}/questions/order   需 owner（仅 draft）
     请求：{"order":[15,12,18]}；响应 200，step 依数组顺序重排为 10/20/30。
   GET /s/{share_code}   公开
     行为：返回答题页 HTML（服务端渲染题目与选项）；草稿返回 404 提示页；
           已结束返回"问卷已结束"页；达到回收上限返回提示页。
     响应头：Cache-Control: no-store；X-Robots-Tag: noindex, nofollow。
   POST /api/v1/surveys/{share_code}/responses   公开（实名需登录）
     请求：{"device_id":"3f9a...","duration_seconds":142,
           "answers":[{"question_id":12,"value":["A","B"]},
                      {"question_id":13,"value":"建议增加夜间模式"},
                      {"question_id":14,"value":4}]}
     响应 201：{"code":0,"message":"提交成功","data":{"response_id":3301,
              "thank_you":"感谢您的参与","can_edit":false}}
     失败：422/42202（必填缺失，data 列缺失 question_id）、422/42203（单选多值）、
           422/42205（选项非法）、409/40901（重复提交）、409/40903（已达回收上限）、
           403/40302（已结束）。
   PUT /api/v1/surveys/{share_code}/responses/mine   公开/需登录
     行为：当 allow_edit=true 时覆盖更新自己的答卷（按 user_id 或 device_id_hash 定位），
           删除旧 answers/answer_options 后重新写入，同一事务内完成。
     响应 200；失败：409/40906（问卷不允许修改）。
   GET /api/v1/surveys/{survey_id}/responses?page=1&page_size=20&include_test=false   需 owner
     响应 200：答卷明细分页列表（每题一行展开为对象），字段含 response_id、submitted_at、
              duration_seconds、ip_prefix、answers 数组。
     失败：403/40304（协作者无原始明细权限）。
   GET /api/v1/surveys/{survey_id}/stats?question_id=12   需 owner 或协作者
     响应 200：按题型返回 3.3 / 3.4 / 3.5 中对应的结构；
             question_id 省略时返回所有题目的统计数组。
   GET /api/v1/surveys/{survey_id}/cross?group_question_id=10&metric_question_id=12
     需 owner 或协作者
     响应 200：{"groups":[{"key":"A","text":"研发","base":82,
              "options":[{"key":"A","text":"非常满意","count":40,"percent":0.4878}]}]}
     失败：422/42208（分组题不是单选或下拉类型）。
   GET /api/v1/surveys/{survey_id}/charts?question_id=12&chart=bar|pie
     需 owner 或协作者
     响应 200：image/png；失败：422/42212（chart 取值非法）、404/40401。
   GET /api/v1/surveys/{survey_id}/export?format=xlsx|csv&include_test=false   需 owner
     响应 200：附件下载（xlsx 或 csv，UTF-8 with BOM 保证 Excel 正确识别中文）。
   GET /api/v1/surveys/{survey_id}/qr   需 owner
     响应 200：image/png 分享二维码（可选用 qrcode 库；本期可用 matplotlib 简化实现或
              明确标注为可选扩展）。
   GET /stats/{survey_id}   需 owner 或协作者
     行为：返回极简统计页 HTML（题目列表 + 每题图表与数字 + 导出按钮）。
   GET /api/v1/healthz   公开
     响应 200：{"status":"ok","db":"ok"}

4. 鉴权方式与安全要求
   - 口令使用 bcrypt（rounds=12）；JWT HS256，JWT_SECRET_KEY 从环境变量读取，>= 32 字节。
   - 匿名问卷不要求登录，但必须提供 device_id；device_id 在服务端加盐哈希后存储，
     数据库不保存原始 UUID 与完整 IP（只保留网段前缀）。
   - 分享链接使用 8 位 Base62 随机 share_code（约 2.18e14 组合），不可枚举；
     若需要更强保护可开启"访问口令"（可选扩展）。
   - 管理侧接口（明细、导出、删除、发布）必须校验 owner_id == 当前用户或 admin 角色，
     禁止仅凭 survey_id 访问他人问卷数据。
   - 统计接口对协作者开放但不返回原始明细；导出与明细接口仅 owner 可用。
   - jinja2 模板自动转义必须开启；用户填写的文本在页面中只作为文本输出。
   - 导出的文件名与服务端生成的文件路径都要清洗（去掉 \ / : * ? " < > | 与 ..）。
   - 限流：提交答卷 30 次/分钟/设备；创建问卷 20 次/小时/用户；
     导出 5 次/小时/用户；统计查询 120 次/分钟/用户。
   - 问卷可设置 is_test 标记的数据默认不计入统计与导出（创建者自测用），
     查询时通过 include_test 显式包含。
   - 日志不记录填空题的答案原文（只记录长度），避免个人信息泄漏。

5. 错误处理与并发事务注意点
   - 回收上限必须用条件 UPDATE 保证：
     UPDATE surveys SET response_count = response_count + 1
     WHERE id = :id AND (max_responses IS NULL OR response_count < max_responses)，
     rowcount = 0 时回滚整个答卷插入，避免并发下超过上限。
   - 实名防重依赖部分唯一索引 UNIQUE(survey_id, user_id)；
     匿名防重依赖 (survey_id, device_id_hash) 唯一索引（允许覆盖时先删后插）。
     PostgreSQL 用部分唯一索引；SQLite 用普通唯一索引 + 在匿名场景把 user_id 存为特殊值。
   - 答卷写入必须在一个事务内完成 responses + answers + answer_options 三张表的写入，
     任何一步失败整体回滚，避免"有答卷无答案"的脏数据。
   - 修改答卷（allow_edit）时先 DELETE answer_options → answers，再重新批量插入，
     全过程同一事务，避免中途失败导致答案缺失。
   - 统计查询必须用 SQL 聚合（GROUP BY / COUNT），禁止把 10 万行答案读进 Python 循环；
     必要时为 (survey_id, question_id) 建覆盖索引。
   - 统计结果可缓存（survey_stats_cache 或 Redis，TTL 60 秒），
     提交新答卷时删除对应缓存键；缓存未命中时回源聚合。
   - 导出大问卷（> 5 万份答卷）时使用流式写入 + 分页查询（keyset 分页，按 responses.id 递增），
     避免一次性加载全部数据。
   - matplotlib 在 Web 服务中是全局状态，渲染必须加线程锁或使用独立 Figure 对象，
     多线程下每次新建 Figure 并显式 close，防止内存泄漏与图表串色。
   - 删除问卷为软删除；物理清理任务每天删除 deleted_at 超过 30 天的问卷及其答卷
     （answers/answer_options 通过外键 ON DELETE CASCADE 清理）。

【五、运行方式与示例】

安装与启动：
  python -m venv .venv && .venv\Scripts\activate
  pip install -r requirements.txt
  set JWT_SECRET_KEY=please-change-this-32bytes-minimum
  set DATABASE_URL=sqlite:///./survey.db
  set CHART_FONT_PATH=C:\Windows\Fonts\msyh.ttc
  set EXPORT_DIR=D:\survey_export
  alembic upgrade head
  uvicorn app.main:app --reload --port 8700
  python -m app.scripts.seed_demo    # 生成一份 8 题的示例问卷与 200 份模拟答卷

界面与交互说明：
  答题页 /s/{share_code} 为单页滚动表单：顶部标题与说明，中部逐题渲染
  （单选 radio、多选 checkbox、填空 input/textarea、评分五颗星按钮、下拉 select、矩阵表格），
  底部"提交"按钮；必填未答时页面滚动到第一处错误并标红。
  统计页 /stats/{survey_id} 每题一张卡片：左侧数字摘要（作答人数、占比最高选项），
  右侧图表（柱状/饼图）与"导出 Excel"按钮。

示例 1（创建并发布问卷）：
  请求：POST /api/v1/surveys {"title":"2024 客户满意度调查","is_anonymous":true,"max_responses":1000}
  响应：HTTP 201 {"code":0,"data":{"survey_id":7,"status":"draft","share_code":null}}
  请求：POST /api/v1/surveys/7/questions
        {"qtype":"single","title":"您对我们的整体服务是否满意？","is_required":true,
         "options":[{"key":"A","text":"非常满意"},{"key":"B","text":"满意"},
                    {"key":"C","text":"一般"},{"key":"D","text":"不满意"}]}
  响应：HTTP 201 {"code":0,"data":{"question_id":12,"step":10,"option_count":4}}
  请求：POST /api/v1/surveys/7/publish
  响应：HTTP 200 {"code":0,"data":{"share_code":"aB3xK9zQ",
        "share_url":"http://127.0.0.1:8700/s/aB3xK9zQ","status":"published"}}
示例 2（提交答卷）：
  请求：POST /api/v1/surveys/aB3xK9zQ/responses
        {"device_id":"3f9a2c7e-...","duration_seconds":142,
         "answers":[{"question_id":12,"value":"A"},{"question_id":13,"value":"建议增加夜间模式"}]}
  响应：HTTP 201
        {"code":0,"message":"提交成功","data":{"response_id":3301,
         "thank_you":"感谢您的参与","can_edit":false}}
示例 3（必填缺失与非法选项）：
  请求：POST /api/v1/surveys/aB3xK9zQ/responses
        {"device_id":"3f9a2c7e-...","answers":[{"question_id":12,"value":"Z"}]}
  响应：HTTP 422
        {"code":42205,"message":"答案校验未通过","data":{"errors":[
         {"question_id":12,"reason":"选项 Z 不属于该题"}]}}
示例 4（重复提交）：
  同一 device_id 再次提交（allow_edit=false）
  响应：HTTP 409
        {"code":40902,"message":"您已提交过该问卷，不能重复提交","data":{"response_id":3301}}
示例 5（统计与交叉分析）：
  请求：GET /api/v1/surveys/7/stats?question_id=12
  响应：HTTP 200
        {"code":0,"data":{"question_id":12,"type":"single","answered_count":186,
         "total_responses":200,"skipped_count":14,
         "options":[{"key":"A","text":"非常满意","count":96,"percent":0.5161},
                    {"key":"B","text":"满意","count":62,"percent":0.3333},
                    {"key":"C","text":"一般","count":20,"percent":0.1075},
                    {"key":"D","text":"不满意","count":8,"percent":0.0430}]}}
  请求：GET /api/v1/surveys/7/cross?group_question_id=10&metric_question_id=12
  响应：HTTP 200
        {"code":0,"data":{"groups":[{"key":"A","text":"研发部","base":82,
         "options":[{"key":"A","text":"非常满意","count":40,"percent":0.4878}]}]}}
示例 6（异常输入 / 未发布）：
  请求：POST /api/v1/surveys/DRAFT123/responses  （share_code 属于草稿问卷）
  响应：HTTP 403
        {"code":40303,"message":"该问卷尚未发布","data":{"survey_id":8,"status":"draft"}}
示例 7（导出）：
  请求：GET /api/v1/surveys/7/export?format=xlsx
  响应：HTTP 200  Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
        Content-Disposition: attachment; filename*=UTF-8''2024客户满意度调查_20240501.xlsx
        内容含"明细""统计""说明"三个 Sheet。

【六、验收标准】

[ ] 创建问卷并添加 6 种题型全部成功，单选题少于 2 个选项时返回 422/42211。
[ ] 未发布（draft）问卷提交答卷返回 403/40303；已关闭问卷返回 403/40302。
[ ] 必填题缺失时返回 422/42202 且 data 准确列出所有缺失的 question_id。
[ ] 单选提交数组、多选提交字符串、评分超出范围、选项 key 非法分别返回对应的 422 业务码。
[ ] 匿名问卷缺少 device_id 返回 422/42201；同一 device_id 重复提交返回 409/40902。
[ ] 实名问卷同一用户重复提交返回 409/40901；allow_edit=true 时可覆盖更新且答案表无重复行。
[ ] max_responses=1 时并发提交 20 份答卷，最终 response_count 恰为 1（条件 UPDATE 生效）。
[ ] 提交后 response_count、answers、answer_options 三处数据条数自洽（无孤立记录）。
[ ] 选择题统计的 answered_count 与明细中该题非空答案数一致，percent 之和（单选）等于 1。
[ ] 多选题统计的 percent 之和大于 1，且每个选项 count 与明细核对一致。
[ ] 填空题词频 TopN 结果可复现，停用词不出现在结果中；samples 最多 50 条。
[ ] 评分题 average 与手工计算一致，中位数正确，distribution 各分值人数之和等于 answered_count。
[ ] 答卷数为 0 的题目统计返回空结构且 average 为 null，不报 500。
[ ] 交叉分析结果中每个分组内 percent 之和为 1，分组 base 之和等于总答卷数（不含跳题缺失）。
[ ] 图表接口返回 PNG 且中文不乱码（配置字体后标题显示正常），饼图选项超过 8 个时自动降级为柱状图。
[ ] Excel 导出含明细、统计、说明三个 Sheet，明细行数等于答卷数（不含 is_test 数据）。
[ ] CSV 导出带 UTF-8 BOM，用 Excel 打开中文不乱码。
[ ] 非 owner 用户导出明细返回 403/40304；协作者可看统计但看明细返回 403。
[ ] 已发布问卷修改题目返回 409/40904；复制问卷后新问卷为 draft 且题目完整。
[ ] 逻辑跳转生效：选中触发选项后被跳过的题目不参与必填校验且不落库。
[ ] pytest 用例覆盖校验、提交流程、防重、统计、导出五类场景并全部通过。

【七、可选扩展】

1. 增加问卷模板库（满意度、NPS、活动报名、课程评价四个预设模板一键创建）。
2. 增加访问口令与白名单，限制问卷只在指定人群中传播。
3. 引入 jieba 分词提升中文词频质量，并支持自定义词表。
4. 增加答题进度保存（草稿答案暂存，30 分钟后过期）。
5. 增加 NPS 净推荐值自动计算（推荐者比例 - 贬损者比例）与趋势对比。
6. 增加问卷结果分享页（隐藏明细、只显示图表，可设访问密码）。
7. 增加答卷异常检测：填写时长过短（< 10 秒）或全部选同一选项的答卷标记为可疑。
8. 增加多问卷对比分析：同标题不同批次的统计结果并列展示。

【八、涉及知识点】

- 问卷与题型的可扩展建模：questions + options 一对多 + 答案明细行设计
- 答案存储结构权衡：JSON 列（写入简单）与关联表（聚合高效）的结合使用
- 按题型的校验逻辑组织与纯函数化，一次性返回全部校验错误
- SQL 聚合统计：COUNT、GROUP BY、LEFT JOIN 保证零作答选项也出现在结果中
- 统计口径的定义与文档化（分母是谁、百分比之和为什么可能大于 1）
- 字段级冗余（survey_id 冗余到 answers）对查询性能的影响
- 匿名标识与防重复：设备指纹哈希、加盐、IP 网段化与隐私取舍
- 并发控制：条件 UPDATE 保证回收上限不被突破、事务内多表写入的一致性
- jinja2 模板渲染与自动转义、服务端渲染表单回填
- matplotlib Agg 后端、中文字体处理、图表在 Web 服务中的线程安全
- openpyxl write_only 模式与大数据量导出、CSV BOM 与编码问题
- 统计结果缓存与失效策略、keyset 分页导出
================================================================================
