================================================================================
项目编号：077                    难度等级：★★★★☆（中型项目，偏难）
项目名称：在线答题考试系统
所属分类：Web 后端 / 教育与考核系统
建议工时：5 ~ 7 天
运行环境：Python 3.10+    第三方依赖：fastapi、uvicorn、sqlalchemy、pydantic、passlib[bcrypt]、python-jose[cryptography]、openpyxl、apscheduler、redis、pytest、httpx
================================================================================

【一、项目背景与目标】

培训考核、入职测评、课堂小测目前大多靠"发 Word 卷子 + 收邮件 + 手工批改"完成，
流程长、易作弊、统计难。教师最痛的三件事是：组卷靠手工挑题、判卷靠红笔、讲评时不知道哪道题错得最多。
学生最痛的是：做错的题过两天就找不到了，复习没有抓手。

本项目实现一套在线答题考试系统，覆盖"题库建设 → 自动/手动组卷 → 定时开考 → 
限时答题（含每场独立倒计时与自动交卷）→ 客观题自动评分 → 错题本 →
成绩统计与讲评"的完整闭环。它面向培训机构、企业内训与学校课堂，可同时支撑数百人同场考试。

技术难点集中在四处：一是考试会话的状态机（未开始 / 进行中 / 已交卷 / 已判分 / 已过期），
以及"服务端时间是唯一权威"的倒计时校验；二是自动交卷的并发触发
（客户端提交与服务端定时任务可能同时触发，必须幂等）；三是组卷算法
（按知识点与难度配比抽题，且同一份卷内不重复）；四是错题本与统计的聚合口径
（得分率、题目区分度都不能在应用层用循环硬算）。

【二、功能需求清单】

1. 核心功能
   1.1 题库管理：题目支持单选、多选、判断、填空、简答五种题型；
       字段含题干、选项、答案、解析、知识点、难度（1~5）、分值。
   1.2 题目导入导出：支持用 openpyxl 从 Excel 批量导入（含错误行报告）与导出。
   1.3 组卷：支持手动选题组卷与按规则自动组卷（指定知识点与难度的题目数量与分值）。
   1.4 试卷管理：试卷可复用，支持设置总分、及格分、时长、是否乱序、是否公布答案。
   1.5 考试场次：为试卷安排场次（开始时间、结束时间、允许参加的人员名单或部门）。
   1.6 开考：考生进入场次后创建答题会话，服务端记录 started_at 并下发不含答案的题目。
   1.7 限时答题：每场考试有独立时长；剩余时间以服务端为准，客户端倒计时仅为展示。
   1.8 自动保存：答题过程中答案可随时保存（单题保存与批量保存），支持断线重连继续答题。
   1.9 交卷：支持手动交卷、超时自动交卷、管理员强制收卷三种方式，且必须幂等。
   1.10 自动评分：单选、多选、判断、填空自动评分；简答题按关键词命中给分并标记待人工复核。
   1.11 成绩查询：考生可查自己的成绩与逐题得分；管理员可查全部成绩与排名。
   1.12 错题本：自动汇总考生做错的题目，支持按知识点筛选与重做。
   1.13 统计：试卷层面的平均分、及格率、每题正确率、选项分布（用于讲评）。
   1.14 防作弊基础措施：禁止同账号多场并发答题、切屏次数记录、答案提交时间戳留痕。
   1.15 鉴权与角色：admin（全部权限）、teacher（题库与组卷、查看统计）、student（参加考试）。

2. 输入与交互
   2.1 全部通过 JSON；题目批量导入使用 multipart/form-data 上传 .xlsx 文件。
   2.2 保存答案请求：{"question_id":12,"answer":["A","C"]}，answer 类型按题型约定：
       单选为字符串、多选为字符串数组、判断为 "true"/"false"、填空为字符串数组（按空顺序）、
       简答为字符串。
   2.3 批量保存：{"answers":[{"question_id":12,"answer":["A"]},{"question_id":13,"answer":"..."}]}
       单词最多 100 题，超出返回 422。
   2.4 组卷请求示例：{"title":"Python 基础测验","duration_minutes":60,
       "rules":[{"knowledge_point":"循环","difficulty":[1,2],"count":5,"score":4},
                {"knowledge_point":"函数","difficulty":[3,4],"count":3,"score":8}]}
   2.5 分页参数统一 page（默认 1）与 page_size（默认 20，最大 100）。
   2.6 交互方式：REST 接口 + Swagger UI 文档 + 一个内置的答题页 /exam/{session_id}（极简 HTML）。

3. 输出与展示
   3.1 统一响应 { "code": 0, "message": "ok", "data": {...} }。
   3.2 开考响应：{"session_id":"...","paper_title":"Python 基础测验","total_score":100,
       "pass_score":60,"started_at":"...","deadline_at":"...","server_time":"...",
       "questions":[{"id":12,"type":"single","stem":"...","options":[{"key":"A","text":"..."}],
       "score":4,"saved_answer":["A"]}]}
       注意：题目中绝不包含 correct_answer 与 analysis 字段。
   3.3 交卷响应：{"session_id":"...","status":"graded","objective_score":76,"subjective_score":null,
       "total_score":100,"score":76,"passed":true,"correct_count":19,"wrong_count":3,
       "pending_review":1,"used_seconds":1840}
   3.4 成绩详情：逐题返回 obtained_score、is_correct、correct_answer、analysis（仅当试卷允许公布答案）。
   3.5 统计响应：{"paper_id":3,"attempt_count":128,"avg_score":72.4,"pass_rate":0.68,
       "max_score":98,"min_score":31,
       "questions":[{"question_id":12,"correct_rate":0.42,
       "option_distribution":{"A":30,"B":52,"C":40,"D":6}}]}
   3.6 错题本响应：按知识点分组的错题列表，每题含错误次数与最近一次错误时间。

4. 异常与边界处理
   4.1 场次未开始：409 / 40901，data 返回 start_at；场次已结束：409 / 40902。
   4.2 考生不在允许名单内：403 / 40301。
   4.3 同一考生重复开考（已有进行中的会话）：409 / 40903，data 返回已有 session_id
       （支持断线重连，前端据此恢复）。
   4.4 同一账号在另一设备开考：按策略处理——reject（默认拒绝）或 kick（踢掉旧会话），
       配置项 SINGLE_DEVICE=true 时启用，冲突返回 409 / 40904。
   4.5 会话不存在或不属于当前考生：404 / 40401。
   4.6 会话已交卷后再保存答案：409 / 40905（幂等：已交卷时保存接口返回 409 而非报错堆栈）。
   4.7 超过 deadline_at 后提交：服务端仍接收但按超时处理，越界时间不超过 30 秒的答案计入，
       超过 30 秒的作废并在结果中标记 late_submit=true。
   4.8 自动交卷与手动交卷并发：只产生一条成绩记录（幂等），第二次返回已有的成绩结果。
   4.9 题目不存在于本试卷：422 / 42201（防止考生提交任意题目 ID 刷分）。
   4.10 答案类型与题型不匹配（如单选题提交数组）：422 / 42202，data 指明期望类型。
   4.11 组卷规则抽不出足够题目：409 / 40906，data 返回每个知识点的需求量与实际可用量。
   4.12 Excel 导入格式错误：422 / 42203，data 返回逐行错误（行号、列名、原因）。
   4.13 试卷被删除但存在历史会话：历史成绩保留，题目以快照形式读取（见第四节）。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：fastapi、uvicorn[standard]、sqlalchemy 2.0、pydantic v2、
   passlib[bcrypt]、python-jose[cryptography]、openpyxl（Excel 导入导出）、
   apscheduler（自动交卷与场次状态扫描）、redis（会话缓存与限流，可选）、
   pytest、httpx、alembic。
3. 时间权威性：所有倒计时与超时判定以数据库服务器时间为准，
   接口响应必须返回 server_time，客户端据此校正本地时钟偏差。
4. 禁止事项：禁止在开考接口中返回任何答案字段（correct_answer、analysis、keywords）。
5. 禁止事项：禁止依赖客户端提交的时间戳做超时判定；客户端时间只作为留痕信息记录。
6. 禁止事项：禁止用 Python 循环逐题查询（必须批量查询与批量写入），
   单场 100 题的判分必须在 1 秒内完成。
7. 代码组织（必须有以下模块）：
   app/main.py、app/config.py（单设备策略、超时宽限、评分参数）
   app/database.py、app/models.py、app/schemas.py、app/deps.py
   app/core/answers.py（答案规范类型、比较与判分函数，纯函数）
   app/core/paper_builder.py（自动组卷算法与校验）
   app/core/scheduler.py（APScheduler 任务：自动交卷、场次状态推进）
   app/services/question_service.py、paper_service.py、exam_service.py、
   grading_service.py、stats_service.py、wrongbook_service.py
   app/importers/excel_questions.py（Excel 导入与导出行级错误）
   app/routers/auth.py、questions.py、papers.py、exams.py、grading.py、stats.py
   app/templates/exam.html（极简答题页）
   tests/test_grading.py、test_exam_flow.py、test_timeout.py、test_stats.py、test_wrongbook.py
8. 编码规范：所有函数带类型注解与 docstring；判分函数必须是纯函数并单独测试。
9. 编码规范：日志中不打印考生答案原文（只记录题目 ID 与得分），保护隐私。
10. 编码规范：所有金额/分值使用 Decimal，禁用 float 累加分数。

【四、设计要点】

1. 数据结构（核心表与字段）
   表 users：
     id BIGINT PK、username VARCHAR(32) UNIQUE、password_hash VARCHAR(128)、
     real_name VARCHAR(32)、role VARCHAR(16)（admin / teacher / student）、
     department VARCHAR(64)、is_active BOOLEAN、created_at DATETIME
   表 questions：
     id BIGINT PK、type VARCHAR(16) NOT NULL（single / multiple / judge / fill / essay）
     stem TEXT NOT NULL
     options JSON NULL（[{"key":"A","text":"..."},...]，判断题可为空）
     correct_answer JSON NOT NULL（single: "A"；multiple: ["A","C"]；
       judge: "true"；fill: ["答案1","答案2"]；essay: {"keywords":["事务","隔离"],"min_hits":1}）
     analysis TEXT NULL、knowledge_point VARCHAR(64) NULL、difficulty SMALLINT DEFAULT 3
     default_score NUMERIC(6,2) DEFAULT 5
     created_by FK(users.id)、is_active BOOLEAN DEFAULT 1、created_at DATETIME
     索引：idx_q_kp_diff(knowledge_point, difficulty)、idx_q_type(type)
   表 papers：
     id BIGINT PK、title VARCHAR(120) NOT NULL、description TEXT NULL
     total_score NUMERIC(6,2) NOT NULL、pass_score NUMERIC(6,2) NOT NULL
     duration_minutes INTEGER NOT NULL、shuffle_questions BOOLEAN DEFAULT 0
     shuffle_options BOOLEAN DEFAULT 0、publish_answer BOOLEAN DEFAULT 1
     allow_review BOOLEAN DEFAULT 1（是否允许考后查看解析）
     created_by FK、is_active BOOLEAN、created_at DATETIME
     约束：0 <= pass_score <= total_score
   表 paper_questions（试卷明细，含快照）：
     id BIGINT PK、paper_id FK、question_id FK、seq INTEGER NOT NULL（题号顺序）
     score NUMERIC(6,2) NOT NULL
     question_snapshot JSON NOT NULL（题干、选项、正确答案、解析的完整副本）
     说明：快照保证试卷被引用后题库修改不影响历史考试的可复现性
     约束：UNIQUE(paper_id, question_id)（同一份卷不重复出题）
     索引：idx_pq_paper_seq(paper_id, seq)
   表 exam_sessions（考试场次）：
     id BIGINT PK、paper_id FK、title VARCHAR(120)
     start_at DATETIME NOT NULL、end_at DATETIME NOT NULL
     status VARCHAR(16) DEFAULT 'scheduled'（scheduled / running / finished / cancelled）
     allowed_departments JSON NULL、created_by FK、created_at DATETIME
     索引：idx_es_time(start_at, end_at)、idx_es_status(status)
   表 exam_candidates（考生名单，空表示放开给全部学生）：
     id PK、session_id FK、user_id FK、UNIQUE(session_id, user_id)
   表 answer_sessions（答题会话）：
     id CHAR(36) PK（UUID，避免被猜测他人会话）
     session_id FK(exam_sessions.id)、user_id FK(users.id)
     paper_id FK(papers.id)
     started_at DATETIME NOT NULL
     deadline_at DATETIME NOT NULL（= started_at + duration，且不超过场次 end_at）
     submitted_at DATETIME NULL
     status VARCHAR(16) DEFAULT 'in_progress'
       （in_progress / submitted / graded / expired / force_submitted）
     objective_score NUMERIC(6,2) NULL、subjective_score NUMERIC(6,2) NULL
     score NUMERIC(6,2) NULL、passed BOOLEAN NULL
     used_seconds INTEGER NULL
     late_submit BOOLEAN DEFAULT 0、switch_count INTEGER DEFAULT 0
     reviewed_by FK NULL、reviewed_at DATETIME NULL
     约束：UNIQUE(session_id, user_id, status) 不适用；改用部分唯一索引
           UNIQUE(session_id, user_id) WHERE status = 'in_progress'（PostgreSQL）
           SQLite 场景用应用层 + 事务保证（同事务内先查后插并依赖串行化）
     索引：idx_as_user(user_id, status)、idx_as_session(session_id, status)、
           idx_as_deadline(deadline_at)（供自动交卷扫描）
   表 exam_answers：
     id BIGINT PK、answer_session_id CHAR(36) FK
     question_id FK、seq INTEGER
     answer JSON NULL（未作答为 NULL）
     is_correct BOOLEAN NULL、obtained_score NUMERIC(6,2) NULL
     needs_review BOOLEAN DEFAULT 0
     answered_at DATETIME、saved_at DATETIME
     UNIQUE(answer_session_id, question_id)（保证一题一行，重复保存走 UPSERT）
     索引：idx_ea_session(answer_session_id)
   表 wrong_book（错题本）：
     id PK、user_id FK、question_id FK
     wrong_count INTEGER DEFAULT 1、last_wrong_at DATETIME、last_session_id CHAR(36)
     mastered BOOLEAN DEFAULT 0、mastered_at DATETIME NULL
     UNIQUE(user_id, question_id)
     索引：idx_wb_user(user_id, mastered)
   表 paper_stats_daily（预聚合统计）：
     id PK、paper_id FK、stat_date DATE、attempt_count INTEGER、score_sum NUMERIC(12,2)、
     pass_count INTEGER、UNIQUE(paper_id, stat_date)

2. 关键算法或流程
   自动组卷：
     步骤 1：校验所有规则（知识点、难度区间、数量、分值），难度区间必须 1 <= min <= max <= 5。
     步骤 2：对每条规则执行候选查询：
             SELECT id FROM questions WHERE knowledge_point = :kp AND difficulty BETWEEN :a AND :b
             AND is_active = 1 ORDER BY RANDOM() LIMIT :count * 3
             （先取 3 倍候选，便于处理与其他规则的重叠去重）。
     步骤 3：从候选池中排除已被前面规则选中的题目，取够 count 条；不足则收集缺口。
     步骤 4：所有规则处理完后，若存在缺口则回滚并返回 409/40906 与缺口明细。
     步骤 5：计算 total_score = sum(count * score)；若传入 expected_total 则必须相等，否则 422。
     步骤 6：写入 papers 与 paper_questions（含 question_snapshot 快照），同一事务提交。
     说明：ORDER BY RANDOM() 在小题库（< 10 万题）下可接受；更大题库改用
     按 id 随机区间抽样（随机起点 + id 范围查询）以避免全表排序。
   开考流程：
     步骤 1：校验场次状态与时间窗口：now < start_at → 40901；now > end_at → 40902。
     步骤 2：若 exam_candidates 非空，校验当前用户在其中，否则 40301。
     步骤 3：查询是否已有 status='in_progress' 的会话：
             有则直接返回该会话（断线重连语义），并附 server_time 与 deadline_at。
     步骤 4：若 SINGLE_DEVICE=true 且存在其它设备的活跃连接记录（Redis key
             active:{session_id}:{user_id}），则按策略返回 40904 或先强制旧会话交卷（kick）。
     步骤 5：计算 deadline_at = min(started_at + duration_minutes, session_end_at)。
     步骤 6：创建 answer_sessions，并为每题插入一条空白 exam_answers（answer 为 NULL），
             这样后续保存只需 UPDATE，避免"有没有这行"的判断分支。
     步骤 7：下发题目列表：从 paper_questions 读快照，剔除 correct_answer 与 analysis，
             若 shuffle_questions 为真则按会话 ID 作为随机种子打乱顺序（保证同一会话每次顺序一致）。
   保存答案：
     校验会话状态为 in_progress，且 now <= deadline_at + 30 秒宽限。
     执行 UPSERT：
       INSERT INTO exam_answers (answer_session_id, question_id, answer, saved_at)
       VALUES (...) ON CONFLICT(answer_session_id, question_id)
       DO UPDATE SET answer = excluded.answer, saved_at = excluded.saved_at
     （SQLite 3.24+ 与 PostgreSQL 均支持 ON CONFLICT；MySQL 用 ON DUPLICATE KEY UPDATE）
     单题保存与批量保存在同一实现上，批量走 executemany 以减少往返。
   自动评分：
     步骤 1：加载该会话的全部 exam_answers 与对应 paper_questions 快照（一次查询，用 IN 批量）。
     步骤 2：对每题按题型判分（纯函数 grade_one(question_type, correct, answer, score)）：
             单选/判断：完全相等得满分，否则 0 分（判断的字符串 "true"/"false" 统一小写比对）。
             多选：集合完全相等得满分；有漏选得一半分（向下取整到 0.5）；
                   有错选得 0 分；漏选且错选得 0 分。策略写在配置中可切换全对才给分。
             填空：每个空独立判分，每空分值 = 总分 / 空数（保留 2 位小数），
                   比对前统一处理：去首尾空白、全角转半角、大小写不敏感（可配置）。
             简答：命中 keywords 的数量 >= min_hits 时给该题 60% 基础分，
                   命中率超过 80% 给满分；否则 0 分；无论得分高低都置 needs_review=1
                   供教师复核（复核可改分并记录 reviewed_by）。
     步骤 3：objective_score = sum(客观题得分)，subjective_score = sum(简答题得分)，
             score = objective_score + subjective_score（Decimal 累加，最后量化到 0.01）。
     步骤 4：更新 answer_sessions（status='graded'、三项分数、used_seconds、passed），
             批量更新 exam_answers 的 is_correct 与 obtained_score。
     步骤 5：把错题写入 wrong_book（UPSERT，wrong_count = wrong_count + 1），
             已掌握（mastered=1）的题再次做错时重置 mastered=0。
     步骤 6：更新 paper_stats_daily（UPSERT 累加 attempt_count、score_sum、pass_count）。
     全部数据库操作在一个事务内完成，保证"要么都写，要么都不写"。
   交卷（幂等）：
     条件更新抢占：
       UPDATE answer_sessions SET submitted_at = now(), status = 'submitted'
       WHERE id = :sid AND status = 'in_progress'
     rowcount = 1 → 本次是首次交卷，继续执行评分；
     rowcount = 0 → 已被（自动交卷任务或另一次点击）处理，直接返回当前成绩，不重复评分。
     超时判定：若 now > deadline_at + 30 秒，则 late_submit = 1，并把该时间点之后保存的
     答案视为无效（比较 exam_answers.saved_at 与 deadline_at，无效答案按未作答处理）。
   自动交卷任务（APScheduler）：
     每 30 秒执行一次：SELECT id FROM answer_sessions
     WHERE status = 'in_progress' AND deadline_at < now() - INTERVAL '30 seconds' LIMIT 200，
     逐个调用与手动交卷相同的 submit(session_id, auto=True) 函数（复用同一幂等逻辑）。
     任务需加分布式锁（Redis SETNX 或数据库标记），避免多实例重复执行。

3. 接口设计（HTTP 前缀 /api/v1；答题页在 /exam/{answer_session_id}）
   POST /api/v1/auth/register、POST /api/v1/auth/login
     返回 JWT（HS256，含 sub、role、exp），密钥读 JWT_SECRET_KEY（>= 32 字节）。
   POST /api/v1/questions   需 teacher/admin
     请求：{"type":"single","stem":"以下哪个是事务特性？","options":[{"key":"A","text":"原子性"},...],
           "correct_answer":"A","analysis":"事务具备 ACID 四大特性","knowledge_point":"事务",
           "difficulty":2,"default_score":4}
     响应 201：{"code":0,"data":{"id":12,"type":"single","score":4}}
     失败：422/42204（题型与答案结构不匹配）、403/40304（学生角色）。
   GET /api/v1/questions?knowledge_point=事务&difficulty=2&type=single&keyword=事务&page=1
     响应 200：分页题目列表（含 correct_answer，仅教师可见）；学生访问返回 403。
   POST /api/v1/questions/import   需 teacher/admin
     请求：multipart/form-data，file=questions.xlsx（表头：题型、题干、选项A~选项F、
           正确答案、解析、知识点、难度、分值）
     响应 200：{"code":0,"data":{"imported":118,"failed":2,
              "errors":[{"row":37,"column":"正确答案","reason":"单选题答案必须为 A~F 之一"}]}}
     失败：422/42203（缺少必需表头或文件非 xlsx）。
   GET /api/v1/questions/export?knowledge_point=事务   需 teacher/admin
     响应 200：application/vnd.openxmlformats-officedocument.spreadsheetml.sheet 附件。
   POST /api/v1/papers   需 teacher/admin
     请求：{"title":"Python 基础测验","duration_minutes":60,"pass_score":60,
           "shuffle_questions":true,"publish_answer":true,
           "rules":[{"knowledge_point":"循环","difficulty":[1,2],"count":5,"score":4},
                    {"knowledge_point":"函数","difficulty":[3,4],"count":3,"score":8}]}
     响应 201：{"code":0,"data":{"paper_id":3,"total_score":44,"question_count":8,
              "breakdown":[{"knowledge_point":"循环","picked":5,"score_each":4}]}}
     失败：409/40906（题目不足，data 含缺口）、422/42205（规则参数非法）。
   POST /api/v1/papers/{paper_id}/questions   需 teacher/admin
     请求：{"items":[{"question_id":12,"seq":1,"score":4},{"question_id":15,"seq":2,"score":6}]}
     响应 200：手动组卷结果；同一 paper 内 question_id 重复返回 409/40907。
   GET /api/v1/papers/{paper_id}   需 teacher/admin
     响应 200：试卷详情与题目清单（含答案与解析）。
   POST /api/v1/exam-sessions   需 teacher/admin
     请求：{"paper_id":3,"title":"5 月月考","start_at":"2024-05-10T09:00:00+08:00",
           "end_at":"2024-05-10T11:00:00+08:00","allowed_departments":["研发部"]}
     响应 201：{"code":0,"data":{"session_id":5,"status":"scheduled","candidate_count":42}}
     失败：422/42206（end_at 早于 start_at 或时间格式错误）。
   POST /api/v1/exam-sessions/{session_id}/candidates   需 teacher/admin
     请求：{"user_ids":[3,5,8]} 或 {"departments":["研发部"]}
     响应 200：{"code":0,"data":{"added":3,"skipped":1}}（已存在的跳过）。
   GET /api/v1/exam-sessions?status=running&page=1   需登录
     响应 200：场次列表（学生只看自己可参加的）。
   GET /api/v1/exam-sessions/{session_id}   需登录
     响应 200：场次详情；学生视角不含试卷题目，只含时长、总分、及格分、我的会话状态。
   POST /api/v1/exam-sessions/{session_id}/start   需 student
     响应 201：开考响应（含 session_id、deadline_at、server_time、题目列表，不含答案）
     失败：409/40901（未开始）、409/40902（已结束）、403/40301（不在名单）、
           409/40903（已有进行中会话，data 含已有 session_id）、409/40904（单设备策略冲突）。
   GET /api/v1/answer-sessions/{sid}   需本人
     响应 200：{"session_id":"...","status":"in_progress","server_time":"...",
              "deadline_at":"...","remaining_seconds":1520,"switch_count":1,
              "questions":[...],"saved_answers":{"12":["A"],"13":["A","C"]}}
     行为：断线重连后按此接口恢复答题状态；已交卷时返回成绩摘要而非题目。
     失败：404/40401。
   PUT /api/v1/answer-sessions/{sid}/answers   需本人
     请求：{"answers":[{"question_id":12,"answer":["A"]}]}
     响应 200：{"code":0,"data":{"saved":2,"remaining_seconds":1502}}
     失败：409/40905（已交卷）、422/42202（答案类型不匹配）、422/42201（题目不属于本卷）。
   POST /api/v1/answer-sessions/{sid}/submit   需本人
     请求：{"auto":false}（auto=true 表示客户端自检超时后主动提交，仍以服务端时间为准）
     响应 200：成绩摘要（见 3.3）；重复提交返回同样的成绩（幂等）。
     失败：404/40401。
   POST /api/v1/answer-sessions/{sid}/heartbeat   需本人
     请求：{"switch_count":1}（前端在 window blur 时累加并上报）
     响应 200：{"code":0,"data":{"remaining_seconds":1480,"server_time":"...",
              "expired":false}}；expired 为 true 时前端应立即跳转成绩页。
   GET /api/v1/answer-sessions/{sid}/result   需本人或 teacher/admin
     响应 200：逐题结果（含 correct_answer 与 analysis，仅当 publish_answer=true 或角色为教师）。
     失败：404/40401、403/40302（他人成绩且非教师）。
   POST /api/v1/answer-sessions/{sid}/review   需 teacher/admin
     请求：{"items":[{"question_id":33,"obtained_score":8}]}
     响应 200：人工复核后重算总分并更新 passed、wrong_book；写 reviewed_by/reviewed_at。
   GET /api/v1/exam-sessions/{session_id}/scores   需 teacher/admin
     查询参数：page、page_size、order_by=score|used_seconds|submitted_at
     响应 200：成绩列表（含排名 rank、real_name、score、used_seconds、late_submit）。
   GET /api/v1/exam-sessions/{session_id}/stats   需 teacher/admin
     响应 200：见 3.5 的统计结构。
   GET /api/v1/wrong-book?knowledge_point=事务&mastered=false   需 student
     响应 200：错题列表（含题干、我的答案、正确答案、解析、wrong_count）。
   POST /api/v1/wrong-book/{question_id}/master   需 student
     响应 200：标记为已掌握（mastered=1）；再次做错时自动重置。
   GET /exam/{sid}   需本人（带 token 查询参数）
     行为：返回极简答题页 HTML（原生 fetch 轮询 heartbeat，倒计时归零自动交卷）。
   GET /api/v1/healthz   公开
     响应 200：{"status":"ok","scheduler":"running","db":"ok"}

4. 鉴权方式与安全要求
   - 口令使用 bcrypt（rounds=12）；JWT HS256，JWT_SECRET_KEY 从环境变量读取且 >= 32 字节。
   - 角色矩阵：student 只能访问自己的会话与错题本；teacher 可管理题库、组卷、看统计；
     admin 额外可删除场次、强制收卷、修改角色。
   - 所有学生侧接口必须校验 answer_sessions.user_id == 当前用户，
     禁止仅凭 session_id 读写他人答卷（这是本系统最关键的越权面）。
   - 考试期间接口返回的所有数据必须经过"去答案"过滤函数，
     该函数用白名单构造响应字典（而非黑名单 pop），避免新增字段时意外泄漏答案。
   - 答案保存接口校验 question_id 属于本试卷（基于 paper_questions 查询），防止跨卷刷分。
   - 限流：登录 10 次/5 分钟/IP；开考 10 次/分钟/用户；保存答案 60 次/分钟/用户；
     心跳 30 次/分钟/用户；导出与导入 5 次/小时/用户。
   - 答题会话 ID 使用 UUID4（122 位熵），不使用自增 ID，避免被枚举。
   - 日志中不记录考生答案内容与正确答案，只记录 session_id、question_id 与得分。
   - 强制收卷（教师操作）需二次确认参数 confirm=true，并写审计日志。

5. 错误处理与并发事务注意点
   - 交卷必须用条件 UPDATE（status='in_progress' → 'submitted'）保证幂等；
     自动交卷任务与考生点击提交并发时，只有一方拿到 rowcount=1，另一方直接读成绩。
   - 评分在同一事务内完成分数写入与错题本写入；如评分过程抛异常则整体回滚，
     会话状态回退为 submitted（可重试），绝不能出现"有分数无明细"的中间态。
   - 开考防重复：在事务内查询活跃会话并插入；PostgreSQL 用部分唯一索引
     UNIQUE(session_id, user_id) WHERE status='in_progress' 兜底，
     SQLite 用 BEGIN IMMEDIATE 事务串行化 + 唯一约束 (session_id, user_id, status) 的替代方案。
   - 答案保存使用 UPSERT，避免"先查后插"的竞态；同一会话的多次保存天然以最后写入为准。
   - 自动交卷任务必须加锁（Redis SETNX 或数据库 advisory lock），
     多实例部署时同一会话只被处理一次；处理失败进入重试队列（最多 3 次）。
   - 场次状态推进任务每 1 分钟把 start_at <= now 的 scheduled 置为 running、
     end_at < now 的 running 置为 finished，用于列表展示（不依赖该状态做权限判定）。
   - 统计查询使用预聚合表 + 当日明细合并；每题正确率用一次 GROUP BY 查询得到，
     禁止在 Python 里循环统计。
   - 试卷快照（question_snapshot）保证题库修改后历史成绩可复现，
     评分永远读取快照而不是当前题库。

【五、运行方式与示例】

安装与启动：
  python -m venv .venv && .venv\Scripts\activate
  pip install -r requirements.txt
  set JWT_SECRET_KEY=please-change-this-32bytes-minimum
  set DATABASE_URL=sqlite:///./quiz.db
  set SINGLE_DEVICE=true
  set LATE_SUBMIT_GRACE_SECONDS=30
  alembic upgrade head
  uvicorn app.main:app --reload --port 8600
  python -m app.scripts.seed_demo    # 生成 2 名教师、20 名学生、100 道演示题

界面与交互说明：
  答题页 /exam/{sid}?token=... 只有三块区域：顶部倒计时与题号进度、
  中间题目卡片（单选为 radio、多选为 checkbox、判断为两个按钮、填空为输入框、简答为文本域）、
  底部"上一题/下一题/交卷"按钮与保存状态提示。
  页面每 20 秒调用一次 heartbeat；倒计时归零时自动调用 submit 并跳转成绩页。
  窗口失焦时累加 switch_count 并随心跳上报，教师端统计页可看到异常切屏考生。

示例 1（自动组卷）：
  请求：POST /api/v1/papers
        {"title":"Python 基础测验","duration_minutes":60,"pass_score":60,
         "rules":[{"knowledge_point":"循环","difficulty":[1,2],"count":5,"score":4},
                  {"knowledge_point":"函数","difficulty":[3,4],"count":3,"score":8}]}
  响应：HTTP 201
        {"code":0,"message":"组卷成功","data":{"paper_id":3,"total_score":44,
         "question_count":8,"breakdown":[{"knowledge_point":"循环","picked":5,"score_each":4},
         {"knowledge_point":"函数","picked":3,"score_each":8}]}}
示例 2（题目不足）：
  请求：POST /api/v1/papers  规则要求"装饰器"难度 5 的题 4 道，题库只有 2 道
  响应：HTTP 409
        {"code":40906,"message":"题库题目不足，无法组卷",
         "data":{"shortage":[{"knowledge_point":"装饰器","difficulty":[5,5],"need":4,"available":2}]}}
示例 3（开考）：
  请求：POST /api/v1/exam-sessions/5/start
  响应：HTTP 201
        {"code":0,"data":{"session_id":"7f3c9a2b-...","paper_title":"Python 基础测验",
         "total_score":44,"pass_score":26,"server_time":"2024-05-10T09:00:03+08:00",
         "started_at":"2024-05-10T09:00:03+08:00","deadline_at":"2024-05-10T10:00:03+08:00",
         "questions":[{"id":12,"type":"single","stem":"...","options":[{"key":"A","text":"..."}],
         "score":4,"saved_answer":null}]}}
示例 4（重复开考 / 断线重连）：
  请求：再次 POST /api/v1/exam-sessions/5/start
  响应：HTTP 409
        {"code":40903,"message":"你有一场进行中的考试","data":{"session_id":"7f3c9a2b-...",
         "deadline_at":"2024-05-10T10:00:03+08:00"}}
        前端据此直接跳回 /exam/7f3c9a2b-... 继续答题。
示例 5（交卷与评分）：
  请求：POST /api/v1/answer-sessions/7f3c9a2b-.../submit  {"auto":false}
  响应：HTTP 200
        {"code":0,"message":"交卷成功",
         "data":{"status":"graded","objective_score":36,"subjective_score":6,
         "total_score":44,"score":42,"passed":true,"correct_count":6,"wrong_count":2,
         "pending_review":1,"used_seconds":1840,"late_submit":false}}
  再次提交同一会话（幂等）：
  响应：HTTP 200，返回与上面完全一致的分数。
示例 6（超时后提交）：
  请求：在 deadline_at 之后 45 秒提交
  响应：HTTP 200
        {"code":0,"data":{"late_submit":true,"ignored_answers":2,"score":40,
         "message":"超过截止时间 45 秒，截止后保存的 2 道答案未计入"}}
示例 7（异常输入）：
  请求：PUT /api/v1/answer-sessions/xxx/answers  {"answers":[{"question_id":999,"answer":["A"]}]}
  响应：HTTP 422
        {"code":42201,"message":"题目 999 不属于本试卷","data":{"question_id":999}}

【六、验收标准】

[ ] 学生调用开考接口返回的题目 JSON 中不存在 correct_answer、analysis、keywords 三个字段（用 grep 验证）。
[ ] 场次未开始时开考返回 409/40901，场次结束后返回 409/40902。
[ ] 不在考生名单的学生开考返回 403/40301。
[ ] 同一学生重复开考返回 409/40903 与已有 session_id，用该 ID 拉取可恢复全部已保存答案。
[ ] SINGLE_DEVICE=true 时第二设备开考按配置返回 409/40904 或踢掉旧会话。
[ ] 单选、多选、判断、填空的判分结果与手工计算完全一致（含多选漏选得半分、错选 0 分用例）。
[ ] 简答题命中关键词数量达标时按规则给分并置 needs_review=1，教师复核改分后总分与及格状态同步更新。
[ ] 交卷后立即返回成绩；重复调用 submit 返回同一结果，数据库只有一条成绩（无重复记录）。
[ ] 超时 45 秒提交时 late_submit=true，截止后保存的答案不计入分数并在响应中说明数量。
[ ] 自动交卷任务在 deadline 过后 60 秒内把未交卷会话置为 graded，成绩与手动交卷逻辑一致。
[ ] question_snapshot 生效：修改题库中某题答案后，历史会话的成绩与解析不发生变化。
[ ] 保存答案接口对不属于本试卷的 question_id 返回 422/42201，考生分数不受影响。
[ ] 组卷规则无法满足时返回 409/40906 且 data 中缺口明细准确（need 与 available 与实际相符）。
[ ] 自动组卷结果中同一 paper 内无重复题目，且各规则的知识点与难度分布符合要求。
[ ] Excel 导入 120 行含 2 行错误时返回 imported=118、failed=2 与逐行错误说明。
[ ] 错题本在交卷后包含全部错题，同一题再次做错时 wrong_count 递增为 2。
[ ] 统计接口的每题正确率与手工用明细数据核对一致，选项分布之和等于作答人数。
[ ] 学生 A 用学生 B 的 session_id 拉取或提交答案，均返回 404/40401。
[ ] pytest 用例覆盖判分、考试流程、超时、统计、错题本五类场景并全部通过。

【七、可选扩展】

1. 增加防作弊增强：离开页面次数阈值自动警告/收卷、题目乱序 + 选项乱序、随机抽题。
2. 增加考试预约与准考提醒（APScheduler + 邮件或站内信）。
3. 增加主观题批量批改界面与评分标准（rubric）配置，支持双人评卷。
4. 增加试卷难度与区分度分析（按高分组/低分组通过率差计算区分度）。
5. 增加证书生成：及格后生成 PDF 证书（配合 pypdf 或 reportlab）。
6. 增加题库版本管理，支持同一知识点历史题目的替换与弃用。
7. 增加成绩导出 Excel（openpyxl）与班级维度对比分析。

【八、涉及知识点】

- 关系建模：题库、试卷（含快照）、场次、会话、答案、错题本的表设计与索引策略
- 考试会话状态机与"服务端时间为唯一权威"的限时设计
- 交卷幂等：条件 UPDATE + rowcount 判定，处理手动与自动并发的重复触发
- 判分算法：集合比较（多选）、文本规范化（填空）、关键词命中（简答）
- 组卷算法：按知识点与难度的约束抽取、去重与缺口检测
- JSON 字段建模（选项、答案、快照）与规范化取舍
- 数据快照思想：保证历史结果可复现、业务可审计
- 预聚合统计表与 GROUP BY 聚合查询（正确率、选项分布、及格率）
- APScheduler 定时任务与分布式锁、批处理与重试
- openpyxl 批量导入导出与行级错误报告
- 面向角色与数据归属的越权防护（answer_session 归属校验）
- 响应白名单构造（去答案）以避免敏感字段泄漏
================================================================================
