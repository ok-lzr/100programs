================================================================================
项目编号：070                    难度等级：★★★★☆（中型项目）
项目名称：Flask 待办 REST API
所属分类：Web 后端与在线服务 / REST 接口
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：Flask、pydantic、pytest
================================================================================

【一、项目背景与目标】

待办清单谁都会写，但把它写成一个别人也能用的接口服务，就要面对完全不同的问题：请求参数怎么
校验、分页怎么做、没有权限时返回 401 还是 403、出错时错误码怎么保证调用方能程序化处理、
接口改了怎么让调用方知道。本项目用一个待办业务做载体，把 REST API 的工程规范完整走一遍。

目标用户是正在学习 Web 后端开发的 Python 学习者，以及需要给自己多个客户端（网页、命令行、
手机快捷指令）提供统一数据接口的开发者。做成之后，这套 API 支持按用户隔离的待办增删改查、
分页与多条件过滤、Token 鉴权、统一的错误码与错误体、以及一份可以直接对照测试的接口文档
（同时提供 OpenAPI 3.0 JSON 与 docs/api.md 两处）。

安全与工程要求：Token 一律只以哈希形式存储在数据库中，数据库中不保存明文 Token；
接口返回的用户信息与日志中禁止出现完整 Token（日志只打印前 6 位加省略号）；
所有 SQL 必须参数化，禁止字符串拼接（项目提供测试用例用 SQL 注入字符串验证）；
写操作必须校验 Content-Type 与请求体结构，非法输入返回 400 而不是 500；
服务默认只监听 127.0.0.1，调试模式默认关闭，避免把开发接口直接暴露到公网；
本服务不采集任何用户数据，仅存储调用方自己提交的待办内容。

【二、功能需求清单】

1. 核心功能
   1.1 用户与鉴权：注册用户（用户名 + 密码，密码用标准库 hashlib.pbkdf2_hmac 加随机盐存储）；
       登录成功签发 Token（secrets.token_urlsafe(32)），数据库中只存 sha256(Token)；
       Token 可设置过期天数（默认 30 天），支持显式注销使其立即失效。
   1.2 待办 CRUD：创建、查询单条、列表查询、全量更新（PUT）、部分更新（PATCH）、删除；
       每条待办属于创建它的用户，其他用户访问返回 404（不用 403，避免泄露资源是否存在）。
   1.3 分页：列表接口支持 page（从 1 开始）与 per_page（默认 20，最大 100）；
       响应体统一返回 items、page、per_page、total、pages、has_next。
   1.4 过滤与排序：支持按 status（pending/done）、priority（low/medium/high）、
       tag（可多次传参表示 AND）、keyword（在标题与描述中模糊匹配）、
       due_before/due_after（ISO 日期）过滤；排序支持 sort=created_at|due_date|priority、
       order=asc|desc，默认 created_at desc。
   1.5 字段校验：用 pydantic 定义请求模型；title 长度 1~120 且去除首尾空白后非空；
       description 最长 2000；priority 仅允许 low/medium/high；due_date 为 ISO 8601 日期或日期时间；
       tags 为字符串列表且每项长度不超过 24、最多 10 个。
   1.6 统一错误体：任何错误响应均为 {"error": {"code": "字符串错误码", "message": "中文说明",
       "details": [...]}}，HTTP 状态码与错误码一一对应并在文档中列表给出。
   1.7 统计接口：返回当前用户的待办总数、按状态分组计数、逾期未完成数量、今日到期数量。
   1.8 批量操作：支持一次创建多条（最多 50 条）与按 ID 批量标记完成（最多 100 个 ID），
       批量接口采用“逐条独立处理”语义并在响应中返回每条的成功与否。
   1.9 请求追踪：每个响应带 X-Request-Id 头（uuid4），日志中同一请求的所有输出共用该 ID，
       便于排查问题。
2. 输入与交互
   2.1 鉴权方式：请求头 Authorization: Bearer <token>；缺失或格式错误返回 401，
       Token 无效或过期返回 401 且错误码区分 token_invalid 与 token_expired。
   2.2 请求与响应统一使用 JSON（application/json; charset=utf-8）；
       非 JSON 或无法解析时返回 400 invalid_json。
   2.3 时间统一使用 UTC 的 ISO 8601 字符串（如 2024-05-20T09:30:00Z），
       输入允许不带时区（按 UTC 处理）并记录警告字段。
3. 输出与展示
   3.1 GET /healthz 返回服务状态、版本号与数据库可用性（用于健康检查）。
   3.2 docs/api.md 逐一列出每个路由的方法、路径、是否鉴权、请求头、请求体示例、
       成功响应示例、全部可能的错误码与状态码。
   3.3 GET /openapi.json 返回符合 OpenAPI 3.0 的接口描述，字段与 docs/api.md 保持一致。
4. 异常与边界处理
   4.1 资源不存在返回 404 not_found；未鉴权返回 401 unauthorized；
       参数校验失败返回 422 validation_error 且 details 中逐字段给出原因。
   4.2 用户名已存在返回 409 username_taken；密码强度不足（少于 8 位）返回 422。
   4.3 数据库被锁或写入失败时返回 503 storage_unavailable，并记录完整堆栈到日志（不返回给客户端）。
   4.4 未捕获异常统一由错误处理器转换为 500 internal_error，响应体不含堆栈信息。
   4.5 请求体超过 64 KB 时返回 413 payload_too_large。
   4.6 分页参数非法（page < 1、per_page > 100、非整数）返回 422 并说明取值范围。
   4.7 批量操作中存在非法项时不整体回滚，逐条返回结果，整体状态码仍为 200。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：Flask、pydantic、pytest；其余使用标准库（sqlite3、hashlib、secrets、hmac、
   uuid、datetime、json、logging、os、functools、re、pathlib）。不强制使用 ORM，
   SQL 一律使用 sqlite3 参数化查询，便于学习者看清 SQL 执行过程。
3. 禁止事项：禁止明文存储密码与 Token；禁止在响应中返回 password_hash 或 token_hash；
   禁止拼接 SQL 字符串；禁止在代码中硬编码 SECRET 与 Token；禁止开启 debug=True 作为默认配置；
   禁止把 app.run 绑定到 0.0.0.0 作为默认值。
4. 代码组织：app.py（应用工厂 create_app）、config.py（配置项，支持环境变量覆盖）、
   db.py（连接管理、建表、行工厂）、models.py（pydantic 请求与响应模型）、
   auth.py（注册登录、Token 生成校验、装饰器 login_required）、
   routes/auth_routes.py、routes/todo_routes.py、routes/meta_routes.py、
   errors.py（错误码常量与错误处理器）、pagination.py、openapi.py（接口描述生成）、
   tests/（test_auth.py、test_todos.py、test_filters.py、test_errors.py）。
5. 编码规范：使用应用工厂 + 蓝图划分路由；视图函数只做参数绑定与调用服务函数，
   业务逻辑放在 service 层函数中以便单元测试；所有公开函数写 docstring；
   统一使用 logging 并带 request_id；配置从环境变量读取（TODO_DB_PATH、TODO_TOKEN_TTL_DAYS）。
6. 测试要求：使用 pytest 与 Flask 测试客户端，覆盖鉴权失败、CRUD 全流程、分页边界、
   过滤组合、批量部分失败、SQL 注入字符串不生效、错误体结构一致性七类场景；
   测试使用临时 sqlite 文件并在每个用例前后重建，禁止依赖真实数据库。

【四、设计要点】

1. 数据结构
   1.1 表 users：id INTEGER PRIMARY KEY、username TEXT UNIQUE NOT NULL、password_hash TEXT NOT NULL、
       salt TEXT NOT NULL、created_at TEXT NOT NULL。
   1.2 表 tokens：id INTEGER PRIMARY KEY、user_id INTEGER NOT NULL、token_hash TEXT UNIQUE NOT NULL、
       created_at TEXT NOT NULL、expires_at TEXT NOT NULL、revoked INTEGER DEFAULT 0。
   1.3 表 todos：id INTEGER PRIMARY KEY、user_id INTEGER NOT NULL、title TEXT NOT NULL、
       description TEXT、status TEXT NOT NULL DEFAULT 'pending'、
       priority TEXT NOT NULL DEFAULT 'medium'、due_date TEXT、tags TEXT（JSON 数组字符串）、
       created_at TEXT NOT NULL、updated_at TEXT NOT NULL、completed_at TEXT；
       索引：(user_id, status)、(user_id, due_date)。
   1.4 TodoIn（pydantic）：title、description、priority、due_date、tags、status；
       TodoPatch：所有字段可选且不允许空对象（至少提供一个字段）。
   1.5 ApiError：code(str)、message(str)、status(int)、details(list[dict])。
   1.6 错误码表：invalid_json 400、validation_error 422、unauthorized 401、token_invalid 401、
       token_expired 401、forbidden 403、not_found 404、username_taken 409、
       conflict 409、payload_too_large 413、method_not_allowed 405、storage_unavailable 503、
       internal_error 500。
2. 关键算法或流程
   2.1 鉴权流程：读取 Authorization 头 → 校验格式 Bearer <token> → 计算 sha256 →
       查 tokens 表并检查 revoked 与 expires_at → 取出 user_id 注入 g.user_id →
       失败时按原因返回 token_invalid 或 token_expired。
   2.2 密码存储：注册时 secrets.token_bytes(16) 生成盐，pbkdf2_hmac("sha256", password, salt,
       200000) 得到哈希，十六进制存储；登录时用 hmac.compare_digest 比较，避免时序攻击。
   2.3 列表查询构造：以 list[str] 收集 WHERE 条件与参数列表，条件包括 user_id = ?、
       status = ?、priority = ?、due_date <= / >= ?、keyword 用 LIKE ? 且对 % 与 _ 进行转义；
       tags 过滤用 json_each(todos.tags) 与 IN 结合实现 AND 语义；ORDER BY 字段来自白名单映射，
       绝不直接拼接用户输入。
   2.4 分页实现：先执行 COUNT(*) 得到 total，再执行带 LIMIT ? OFFSET ? 的查询；
       pages = ceil(total / per_page)，total 为 0 时 pages = 0。
   2.5 统一响应：成功响应直接返回资源对象或分页对象；错误响应统一由 errors.py 中的
       register_error_handlers 与 ApiError 异常处理器生成，保证结构与文档一致。
3. 接口或命令设计（每个路由的方法、路径、请求体、响应体与状态码）

   3.1 GET /healthz
       鉴权：不需要。请求体：无。
       响应 200：{"status": "ok", "version": "1.0.0", "database": "ok", "time": "2024-05-20T09:30:00Z"}
       响应 503：{"error": {"code": "storage_unavailable", "message": "数据库不可用", "details": []}}

   3.2 POST /api/v1/auth/register
       鉴权：不需要。请求体：{"username": "alice", "password": "StrongPass123"}
       响应 201：{"id": 1, "username": "alice", "created_at": "2024-05-20T09:30:00Z"}
       响应 409：{"error": {"code": "username_taken", "message": "用户名已存在", "details": []}}
       响应 422：{"error": {"code": "validation_error", "message": "请求参数校验失败",
                 "details": [{"field": "password", "reason": "长度至少 8 位"}]}}

   3.3 POST /api/v1/auth/login
       鉴权：不需要。请求体：{"username": "alice", "password": "StrongPass123"}
       响应 200：{"token": "0Xy...（48 字符）", "token_type": "Bearer",
                 "expires_at": "2024-06-19T09:30:00Z"}
       响应 401：{"error": {"code": "unauthorized", "message": "用户名或密码错误", "details": []}}

   3.4 POST /api/v1/auth/logout
       鉴权：需要。请求体：无（可传 {"token": "..."} 指定注销其他 Token，默认注销当前 Token）。
       响应 204：无响应体。
       响应 401：{"error": {"code": "token_invalid", "message": "Token 无效或已注销", "details": []}}

   3.5 POST /api/v1/todos
       鉴权：需要。请求体：
       {"title": "写周报", "description": "总结本周接口开发进度", "priority": "high",
        "due_date": "2024-05-24", "tags": ["工作", "本周"]}
       响应 201：{"id": 12, "title": "写周报", "description": "总结本周接口开发进度",
                 "status": "pending", "priority": "high", "due_date": "2024-05-24",
                 "tags": ["工作", "本周"], "created_at": "2024-05-20T09:30:00Z",
                 "updated_at": "2024-05-20T09:30:00Z", "completed_at": null}
       响应 400：{"error": {"code": "invalid_json", "message": "请求体不是合法 JSON", "details": []}}
       响应 422：{"error": {"code": "validation_error", "message": "请求参数校验失败",
                 "details": [{"field": "title", "reason": "不能为空字符串"}]}}

   3.6 GET /api/v1/todos
       鉴权：需要。查询参数：page=1、per_page=20、status=pending、priority=high、
       tag=工作（可重复）、keyword=周报、due_before=2024-05-31、due_after=2024-05-01、
       sort=created_at、order=desc。
       响应 200：{"items": [ { 待办对象 }, ... ], "page": 1, "per_page": 20, "total": 37,
                 "pages": 2, "has_next": true}
       响应 422：{"error": {"code": "validation_error", "message": "分页参数非法",
                 "details": [{"field": "per_page", "reason": "取值范围 1~100"}]}}

   3.7 GET /api/v1/todos/<int:todo_id>
       鉴权：需要。响应 200：单条待办对象。响应 404：
       {"error": {"code": "not_found", "message": "待办不存在", "details": []}}

   3.8 PUT /api/v1/todos/<int:todo_id>
       鉴权：需要。请求体：与创建一致的全部字段（除 id 与时间字段）。
       响应 200：更新后的待办对象。响应 404：not_found。响应 422：validation_error。

   3.9 PATCH /api/v1/todos/<int:todo_id>
       鉴权：需要。请求体示例：{"status": "done"} 或 {"priority": "low", "tags": ["稍后"]}。
       响应 200：更新后的待办对象；status 由 pending 变 done 时 completed_at 写入当前 UTC 时间，
       由 done 变 pending 时 completed_at 置为 null。
       响应 422：{"error": {"code": "validation_error", "message": "请求参数校验失败",
                 "details": [{"field": "body", "reason": "PATCH 至少需要提供一个可更新字段"}]}}

   3.10 DELETE /api/v1/todos/<int:todo_id>
       鉴权：需要。响应 204：无响应体。响应 404：not_found。

   3.11 GET /api/v1/todos/stats
       鉴权：需要。响应 200：{"total": 37, "pending": 25, "done": 12,
                 "overdue": 3, "due_today": 2, "by_priority": {"high": 8, "medium": 20, "low": 9}}

   3.12 POST /api/v1/todos/batch
       鉴权：需要。请求体：{"items": [ { 创建对象 }, ... ]}（最多 50 条）。
       响应 200（部分成功也返回 200）：
       {"created": 2, "failed": 1,
        "results": [{"index": 0, "id": 13, "ok": true},
                    {"index": 1, "id": 14, "ok": true},
                    {"index": 2, "id": null, "ok": false,
                     "error": {"code": "validation_error", "message": "title 不能为空"}}]}
       响应 413：{"error": {"code": "payload_too_large", "message": "请求体超过 64 KB",
                 "details": []}}

   3.13 POST /api/v1/todos/complete
       鉴权：需要。请求体：{"ids": [12, 13, 14]}（最多 100 个）。
       响应 200：{"completed": 2, "not_found": [14],
                 "results": [{"id": 12, "ok": true}, {"id": 13, "ok": true},
                             {"id": 14, "ok": false, "error": "not_found"}]}

   3.14 GET /openapi.json
       鉴权：不需要。响应 200：OpenAPI 3.0 文档对象；响应 200 的 Content-Type 为
       application/json; charset=utf-8。

【五、运行方式与示例】

安装依赖：
   pip install Flask pydantic pytest

启动服务：
   set TODO_DB_PATH=./data/todo.db
   set TODO_TOKEN_TTL_DAYS=30
   python -m flask --app app:create_app run --host 127.0.0.1 --port 5000

运行示例一（注册并登录）：
   curl -X POST http://127.0.0.1:5000/api/v1/auth/register -H "Content-Type: application/json" -d "{\"username\":\"alice\",\"password\":\"StrongPass123\"}"
   输出：{"id": 1, "username": "alice", "created_at": "2024-05-20T09:30:00Z"}
   curl -X POST http://127.0.0.1:5000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"username\":\"alice\",\"password\":\"StrongPass123\"}"
   输出：{"token": "0Xy7...", "token_type": "Bearer", "expires_at": "2024-06-19T09:30:00Z"}

运行示例二（创建与列表过滤）：
   curl -X POST http://127.0.0.1:5000/api/v1/todos -H "Authorization: Bearer 0Xy7..." -H "Content-Type: application/json" -d "{\"title\":\"写周报\",\"priority\":\"high\",\"due_date\":\"2024-05-24\",\"tags\":[\"工作\"]}"
   输出：{"id": 12, "title": "写周报", ... , "status": "pending"}
   curl "http://127.0.0.1:5000/api/v1/todos?status=pending&priority=high&per_page=10&sort=due_date&order=asc" -H "Authorization: Bearer 0Xy7..."
   输出：{"items": [{"id": 12, "title": "写周报", ...}], "page": 1, "per_page": 10, "total": 1, "pages": 1, "has_next": false}

运行示例三（部分更新与统计）：
   curl -X PATCH http://127.0.0.1:5000/api/v1/todos/12 -H "Authorization: Bearer 0Xy7..." -H "Content-Type: application/json" -d "{\"status\":\"done\"}"
   输出：{"id": 12, "status": "done", "completed_at": "2024-05-20T10:05:00Z", ...}
   curl http://127.0.0.1:5000/api/v1/todos/stats -H "Authorization: Bearer 0Xy7..."
   输出：{"total": 1, "pending": 0, "done": 1, "overdue": 0, "due_today": 0, "by_priority": {"high": 1, "medium": 0, "low": 0}}

异常示例一（无 Token）：
   curl -i http://127.0.0.1:5000/api/v1/todos
   输出：HTTP/1.1 401 UNAUTHORIZED
        {"error": {"code": "unauthorized", "message": "缺少 Authorization 请求头", "details": []}}

异常示例二（非法分页参数）：
   curl -i "http://127.0.0.1:5000/api/v1/todos?per_page=500" -H "Authorization: Bearer 0Xy7..."
   输出：HTTP/1.1 422 UNPROCESSABLE ENTITY
        {"error": {"code": "validation_error", "message": "分页参数非法",
                   "details": [{"field": "per_page", "reason": "取值范围 1~100"}]}}

异常示例三（访问他人资源）：
   curl -i http://127.0.0.1:5000/api/v1/todos/99 -H "Authorization: Bearer <他人 Token>"
   输出：HTTP/1.1 404 NOT FOUND
        {"error": {"code": "not_found", "message": "待办不存在", "details": []}}

【六、验收标准】

[ ] 注册接口对重复用户名返回 409 username_taken，且数据库中不存在该用户
[ ] 数据库中 users.password_hash 与 tokens.token_hash 均为哈希值，无明文密码或明文 Token
[ ] 相同密码两次注册得到不同的 password_hash（盐不同）
[ ] 登录返回的 Token 可用于访问受保护接口，长度不少于 32 字符
[ ] 缺失 Authorization 头返回 401 unauthorized，格式错误返回 401 unauthorized
[ ] 使用已注销的 Token 返回 401 token_invalid，使用过期 Token 返回 401 token_expired
[ ] 创建待办时 title 为空字符串返回 422 且 details 给出字段名与原因
[ ] 用户 A 无法读取、修改、删除用户 B 的待办，全部返回 404
[ ] 列表接口的分页字段 total 与 pages 计算正确（构造 37 条数据、per_page=20 时 pages=2）
[ ] status、priority、tag、keyword、due_before/due_after 组合过滤结果与手工 SQL 查询一致
[ ] sort 传入非白名单字段时不产生 SQL 错误，返回 422 或回退默认排序并在文档中说明
[ ] keyword 中包含 % 或 _ 时按字面匹配，不会匹配到无关记录
[ ] PATCH 空对象返回 422；status 变为 done 时 completed_at 被写入，改回 pending 时置空
[ ] DELETE 已删除的 ID 返回 404，重复删除不产生 500
[ ] 批量创建 51 条时返回 422；50 条中 1 条非法时返回 200 且 results 逐条标注成功与失败
[ ] 所有错误响应体结构一致，均含 error.code、error.message、error.details 三个字段
[ ] 每个响应都带 X-Request-Id 头，且该 ID 出现在对应日志行中
[ ] SQL 注入字符串（如 ' OR 1=1 --）作为 title 或 keyword 传入时不影响查询结果
[ ] 请求体超过 64 KB 返回 413 payload_too_large
[ ] GET /openapi.json 返回合法 JSON 且与 docs/api.md 中的路由、状态码一致
[ ] 未捕获异常返回 500 internal_error，响应体不含堆栈信息
[ ] pytest 全部通过，覆盖鉴权、CRUD、分页、过滤、批量、错误体与注入七类场景

【七、可选扩展】

1. 增加 ETag 与 If-None-Match 支持，让列表查询在无变化时返回 304，减少客户端传输。
2. 增加软删除与回收站：删除写入 deleted_at，列表默认过滤，提供 /todos/trash 恢复接口。
3. 增加限流：基于 IP 与 Token 的滑动窗口限流（标准库即可实现），超限返回 429 并带 Retry-After。
4. 增加待办提醒字段 remind_at 与后台线程扫描，到期时通过 webhook 推送一次提醒。
5. 增加 Alembic 风格的轻量迁移脚本机制（migrations/ 目录 + schema_version 表）。

【八、涉及知识点】

- REST 资源设计、HTTP 方法与状态码语义（200/201/204/400/401/404/409/413/422/500/503）
- Flask 应用工厂、蓝图、before_request 与错误处理器
- pydantic 请求模型校验与自定义校验器
- 标准库密码学用法：pbkdf2_hmac、secrets、hmac.compare_digest
- Token 鉴权与哈希存储（不落明文）
- sqlite3 参数化查询、行工厂、索引设计与连接生命周期
- 分页算法（COUNT + LIMIT/OFFSET）与性能注意事项
- 动态查询构造：条件收集、白名单排序字段、LIKE 转义
- 统一错误体设计与错误码体系
- 日志、请求追踪 ID 与生产环境安全默认值
- OpenAPI 3.0 结构与被测接口的一致性维护
- pytest 与 Flask 测试客户端、临时数据库夹具
================================================================================
