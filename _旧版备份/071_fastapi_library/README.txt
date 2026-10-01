================================================================================
项目编号：071                    难度等级：★★★★☆（中型项目）
项目名称：FastAPI 图书借阅系统
所属分类：Web 后端 / 业务管理系统
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：fastapi、uvicorn、sqlalchemy、pydantic、passlib[bcrypt]、python-jose[cryptography]、alembic、pytest、httpx
================================================================================

【一、项目背景与目标】

学校图书馆、社区图书室、公司内部资料室都存在同样的困境：借还记录写在 Excel 里，
谁借了哪本书靠翻表格找，超期了没人提醒，一本书到底在架上还是在外借说不清。
管理员最常被问的三个问题是"这本书还有吗""我借的书什么时候到期""上个月谁借走了这本书"，
而这些问题在纸质台账上都要靠人工翻找，效率极低。

本项目实现一套面向中小型图书室的借阅管理系统。它不做花哨的推荐算法，
而是把"藏书建档、读者建档、借书、还书、续借、超期处理"这条主线做扎实，
并用 FastAPI 自动生成可交互的 Swagger 文档，让前端同学或非技术管理员都能自助查阅接口。

做成之后，管理员可以通过 HTTP 接口或 Swagger UI 完成日常全部操作：
录入 ISBN 建档、给读者办证、扫码借书、归还并自动计算超期罚金、
查看某读者当前的借阅清单、统计热门图书与滞销图书。

系统强调三点：库存一致性（同一册书不能被两个人同时借走）、操作可追溯（每次借还都写流水）、
状态可校验（借出中的书不允许删除或再次借出）。这三点也是验收时的重点检查项。

【二、功能需求清单】

1. 核心功能
   1.1 图书管理：新增图书，字段包含书名、作者、ISBN、出版社、分类、馆藏总量 total_copies。
   1.2 图书检索：支持按书名、作者、ISBN、分类模糊检索，支持分页与按创建时间/书名排序。
   1.3 图书软删除：is_active 置为 False，检索默认过滤已下架图书，管理员可用 include_inactive=true 查看。
   1.4 图书修改：可改书名、作者、出版社、分类与馆藏总量；总量不得小于已借出数量。
   1.5 读者管理：新增读者，字段包含姓名、证件号 card_no、手机号、邮箱、读者类型。
   1.6 读者类型规则：student 可借 5 本、借期 30 天；teacher 可借 10 本、借期 60 天；
       guest 可借 2 本、借期 15 天。三类额度写在配置表中而不是散落在代码里。
   1.7 读者状态：active 正常、blocked 冻结（禁止借书，允许还书）、inactive 注销（不可登录）。
   1.8 借书：依次校验读者状态、可借额度、图书库存，成功后生成借阅记录并占用一册库存。
   1.9 还书：按借阅记录 ID 归还，计算是否超期与罚金，释放库存并写审计日志。
   1.10 续借：未超期且续借次数为 0 的记录可续借一次，续借期等于该读者类型的借期。
   1.11 超期处理：定时或手动触发扫描，把 due_date 已过的在借记录标记为 overdue 并生成罚金。
   1.12 查询统计：读者当前借阅清单、图书借阅历史、热门图书 TopN、当前超期清单、读者累计罚金。
   1.13 鉴权：管理员登录获取 JWT，写操作需要 admin 角色，读者只能查询自己的借阅记录。

2. 输入与交互
   2.1 所有输入通过 JSON 请求体或查询参数传入，由 Pydantic 模型做类型与范围校验。
   2.2 分页参数统一为 page（默认 1，>=1）与 page_size（默认 20，1~100），超范围返回 422。
   2.3 排序参数 sort 取值 created_at、-created_at、title、-title，非法值返回 422/42203。
   2.4 ISBN 接受 10 位或 13 位（允许含连字符），入库前统一去除连字符后校验校验位。
   2.5 total_copies 取值范围 1~9999，非整数或负数返回 422/42204。
   2.6 交互方式：REST 接口 + Swagger UI（/docs）+ ReDoc（/redoc）+ 内置 /healthz 探活。

3. 输出与展示
   3.1 所有响应统一为 { "code": 0, "message": "ok", "data": {...} } 结构。
   3.2 错误时 code 为非 0 业务码，message 为可读中文提示，data 保留上下文（如可用库存、当前已借数）。
   3.3 借阅记录响应含 borrow_date、due_date、return_date、status、overdue_days、fine_amount。
   3.4 列表响应 data 含 items、total、page、page_size、pages 五个字段。
   3.5 图书响应含 total_copies 与 available_copies，前端据此显示"可借 2 / 共 5"。
   3.6 时间统一输出为本地时区的 ISO 8601 字符串（如 2024-05-01T09:12:00+08:00）。

4. 异常与边界处理
   4.1 图书不存在返回 404 与业务码 40401；读者不存在返回 404 与业务码 40402。
   4.2 图书已下架返回 409 与 40901，提示"该图书已下架，无法借阅"。
   4.3 无可借库存（available_copies <= 0）返回 409 与 40902，提示"该图书已全部借出"。
   4.4 读者被冻结返回 403 与 40301；读者超期未还记录达到 3 条同样禁止借书。
   4.5 超出可借额度返回 409 与 40903，data 中含已借数量与上限。
   4.6 同一读者重复借同一本未归还的书返回 409 与 40904。
   4.7 重复 ISBN 建书返回 409 与 40905；重复证件号建读者返回 409 与 40906。
   4.8 归还不属于该读者的记录返回 403 与 40302（读者 token 场景）。
   4.9 已归还的记录再次归还返回 409 与 40907；库存已满时不重复增加。
   4.10 续借超期图书返回 409 与 40908；续借次数已达上限返回 409 与 40909。
   4.11 total_copies 调小到小于已借出数量返回 409 与 40910。
   4.12 删除仍有未归还记录的图书返回 409 与 40911。
   4.13 请求体超过 64KB 返回 413；Content-Type 非 application/json 返回 415。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用 typing 的 list[dict] 等新语法。
2. 允许使用的库：fastapi、uvicorn[standard]、sqlalchemy 2.0、pydantic v2、alembic、
   passlib[bcrypt]、python-jose[cryptography]、python-dotenv、pytest、httpx。
3. 数据库：开发默认 SQLite，生产可切换 PostgreSQL，仅通过 DATABASE_URL 控制，
   代码中不得出现数据库方言相关的硬编码分支（除 SQLite 的 WAL 与线程参数）。
4. 禁止事项：禁止把数据库口令、JWT 密钥硬编码在源码里（必须读环境变量）。
5. 禁止事项：禁止在 SQLAlchemy 中使用字符串拼接 SQL，全部用 ORM 表达式或参数绑定。
6. 禁止事项：禁止在路由函数里写业务规则，禁止在接口中做同步阻塞的重计算。
7. 代码组织（必须有以下模块）：
   app/main.py（应用装配与路由注册）
   app/config.py（Settings 类读环境变量并校验必填项）
   app/database.py（engine、SessionLocal、get_db 依赖）
   app/models.py（ORM 模型与索引定义）
   app/schemas.py（Pydantic v2 请求与响应模型）
   app/security.py（bcrypt 哈希与 JWT 签发校验）
   app/deps.py（get_current_user、require_admin、get_current_reader）
   app/routers/books.py、readers.py、borrows.py、auth.py、stats.py
   app/services/borrow_service.py（借还与超期业务逻辑，与路由解耦）
   app/exceptions.py（业务异常类与全局异常处理器）
   tests/test_borrow.py、test_concurrency.py、test_permissions.py
8. 编码规范：所有函数写类型注解与 docstring；使用 logging 输出日志，禁止 print。
9. 编码规范：路由函数只做参数解析与调用 service，业务规则全部写在 service 层。
10. 编码规范：金额计算使用 Decimal，禁止用 float 累加罚金。

【四、设计要点】

1. 数据结构（核心表与字段）
   表 books：
     id INTEGER PK
     isbn VARCHAR(20) UNIQUE NOT NULL
     title VARCHAR(200) NOT NULL
     author VARCHAR(100)
     publisher VARCHAR(100)
     category VARCHAR(50)
     total_copies INTEGER NOT NULL DEFAULT 1
     available_copies INTEGER NOT NULL DEFAULT 1
     is_active BOOLEAN DEFAULT 1
     created_at DATETIME、updated_at DATETIME
     约束：total_copies >= 0；0 <= available_copies <= total_copies（用 CHECK 约束表达）
     索引：idx_books_title(title)、idx_books_category(category)
   表 readers：
     id INTEGER PK
     card_no VARCHAR(32) UNIQUE NOT NULL
     name VARCHAR(50) NOT NULL
     phone VARCHAR(20)、email VARCHAR(120)
     reader_type VARCHAR(16) NOT NULL
     status VARCHAR(16) DEFAULT 'active'
     max_borrow INTEGER、borrow_days INTEGER（建读者时按类型快照写入，避免规则变更影响历史）
     created_at DATETIME
   表 borrow_records：
     id INTEGER PK
     book_id FK(books.id)、reader_id FK(readers.id)
     borrow_date DATETIME NOT NULL、due_date DATETIME NOT NULL
     return_date DATETIME NULL
     renew_count INTEGER DEFAULT 0
     status VARCHAR(16) DEFAULT 'borrowed'（borrowed / returned / overdue）
     fine_amount NUMERIC(10,2) DEFAULT 0
     operator_id INTEGER（办理人）
     索引：idx_borrow_reader_status(reader_id, status)、idx_borrow_book(book_id)、
           idx_borrow_due(due_date)
     兜底约束：UNIQUE(reader_id, book_id) WHERE status != 'returned'（部分唯一索引，
     仅 PostgreSQL 支持；SQLite 场景改用借书前的应用层校验 + 事务串行化）
   表 users（管理员与读者登录账号）：
     id INTEGER PK、username VARCHAR(50) UNIQUE、password_hash VARCHAR(128)
     role VARCHAR(16)（admin / reader）、reader_id FK NULL、is_active BOOLEAN、created_at
   表 audit_logs：
     id PK、user_id、action VARCHAR(32)、target_type、target_id、detail TEXT、created_at
     索引：idx_audit_target(target_type, target_id)

2. 关键算法或流程
   借书流程（单个数据库事务内完成，任一步失败整体回滚）：
     步骤 1：按 book_id 取图书，校验存在、is_active、available_copies > 0。
     步骤 2：执行 UPDATE books SET available_copies = available_copies - 1,
             updated_at = now() WHERE id = :id AND available_copies > 0，检查 rowcount。
     步骤 3：若 rowcount == 0，回滚并抛 40902，这是防超卖的关键一步。
     步骤 4：统计该读者 status IN ('borrowed','overdue') 的记录数与 max_borrow 比较。
     步骤 5：检查是否已有同一本书未归还的记录，有则抛 40904。
     步骤 6：计算 due_date = borrow_date + borrow_days 天，截止时刻取当日 23:59:59。
     步骤 7：插入 borrow_records 并写 audit_logs（action='borrow'），提交事务。
   还书流程：
     步骤 1：取记录并校验 status != 'returned'，否则抛 40907。
     步骤 2：执行 UPDATE books SET available_copies = available_copies + 1
             WHERE id = :id AND available_copies < total_copies，rowcount=0 时记警告日志但仍完成归还。
     步骤 3：计算 overdue_days = max(0, (return_time - due_date) 的自然日差)。
     步骤 4：罚金 = overdue_days * 0.5 元/天，单册上限 50 元，使用 Decimal 计算并量化到分。
     步骤 5：更新 status='returned'、return_date、fine_amount，写审计日志，提交。
   续借流程：
     校验 status 属于 borrowed/overdue 且 overdue_days == 0 且 renew_count == 0，
     更新 due_date = 当前 due_date + borrow_days、renew_count = 1。
   超期扫描：
     查询 status IN ('borrowed','overdue') AND due_date < now() 的记录，
     每批 200 条在一个事务里更新 status='overdue' 并重算 fine_amount，避免长事务锁表。
   ISBN 校验位算法：
     13 位按权重 1/3 交替对前 12 位求和，校验位 = (10 - sum % 10) % 10。
     10 位按权重 10~2 对前 9 位求和，校验位规则：sum % 11，0 表示 0，1 表示 X，其余为 11 - r。

3. 接口设计（统一前缀 /api/v1，除登录与 healthz 外均需 Authorization: Bearer <token>）
   POST /auth/token
     请求：{"username": "admin", "password": "***"}
     响应 200：{"code":0,"data":{"access_token":"eyJ...","token_type":"bearer","expires_in":3600}}
     失败：401/40101（用户名或密码错误）、423/42301（连续 5 次失败锁定 15 分钟）。
   POST /books   需 admin
     请求：{"isbn":"9787115428028","title":"Python编程","author":"Eric","total_copies":5}
     响应 201：{"code":0,"data":{"id":1,"available_copies":5,"total_copies":5,...}}
     失败：422/42201（ISBN 校验位错误）、409/40905（ISBN 重复）。
   GET /books?keyword=python&category=计算机&available=true&page=1&page_size=20
     响应 200：{"code":0,"data":{"items":[...],"total":37,"page":1,"page_size":20,"pages":2}}
   GET /books/{book_id}
     响应 200 单本详情；404/40401。
   PATCH /books/{book_id}   需 admin
     请求：{"title":"新书名","total_copies":8}
     响应 200：更新后的图书；409/40910（总量小于已借出数）。
   DELETE /books/{book_id}  需 admin
     响应 200：{"code":0,"data":{"id":1,"is_active":false}}；409/40911（仍有未归还记录）。
   POST /readers   需 admin
     请求：{"card_no":"R2024001","name":"张三","reader_type":"student","phone":"13800000000"}
     响应 201：{"code":0,"data":{"id":3,"max_borrow":5,"borrow_days":30}}
     失败：409/40906、422/42202（reader_type 非法）。
   GET /readers/{reader_id}/borrows?status=borrowed
     响应 200：该读者借阅清单，每条含 overdue_days 与剩余可借数量。
     失败：404/40402、403/40302（读者 token 查询他人）。
   POST /borrows   需 admin
     请求：{"book_id":1,"reader_id":3}
     响应 201：完整借阅记录（含 due_date）
     失败：409/40902、409/40903、409/40904、403/40301、409/40901。
   POST /borrows/{record_id}/return   需 admin
     请求：{"return_date":"2024-06-01T10:00:00"}（可省略，默认服务器时间）
     响应 200：{"code":0,"message":"归还成功，超期 3 天","data":{"overdue_days":3,"fine_amount":"1.50"}}
     失败：409/40907、403/40302、404/40403（记录不存在）。
   POST /borrows/{record_id}/renew   需 admin
     响应 200：{"code":0,"data":{"due_date":"2024-06-30T23:59:59","renew_count":1}}
     失败：409/40908（已超期）、409/40909（已续借过）。
   GET /borrows/overdue   需 admin
     响应 200：全部超期记录，按超期天数倒序。
   GET /stats/popular?limit=10   需 admin
     响应 200：按借阅次数排序的图书 TopN，含 borrow_count 与当前可借数。
   GET /stats/reader/{reader_id}   需 admin 或本人
     响应 200：借阅总数、当前在借、历史超期次数、累计罚金。
   GET /healthz   不鉴权
     响应 200：{"status":"ok","db":"ok"}

4. 鉴权方式
   - 密码哈希使用 passlib 的 bcrypt（rounds=12），数据库中只存 password_hash，绝不存明文。
   - 登录成功后签发 JWT：HS256 签名，payload 含 sub（用户 ID）、role、exp（1 小时）、iat、jti。
   - JWT_SECRET_KEY 从环境变量读取，长度不少于 32 字节，缺失时启动即报错退出。
   - get_current_user 依赖解析 token：签名错误或过期返回 401/40102；被禁用账号返回 403/40303。
   - require_admin 依赖在 get_current_user 之上校验 role，非 admin 返回 403/40304。
   - 读者角色访问他人借阅记录返回 403/40302（横向越权防护，必须显式比对 reader_id）。
   - 登录接口按 IP + 用户名做限流：15 分钟内最多 10 次，超出返回 429/42901。
   - 所有写接口在审计日志中记录操作人 user_id，保证借还操作可追溯到具体账号。

5. 错误处理与并发事务注意点
   - 全局异常处理器把 SQLAlchemy IntegrityError 映射为 409/40999，避免泄漏堆栈给客户端。
   - 借书必须用"条件 UPDATE 判断 rowcount"或行级锁（SELECT FOR UPDATE）保证不超卖，
     不允许先 SELECT 再 UPDATE 的两步写法。
   - 事务边界放在 service 层，一个请求一个 Session，异常时回滚，finally 关闭。
   - SQLite 开发环境需开启 WAL 与 busy_timeout=5000，并设置 connect_args={"check_same_thread": False}。
   - 罚金计算使用 Decimal，避免浮点误差；金额字段用 NUMERIC(10,2)、Python 侧 Decimal(str(x))。
   - 超期扫描必须分批提交；同时最多允许一个扫描任务运行（用数据库标记或文件锁防重入）。
   - 归还与借出并发时，扣减与回补顺序不影响最终一致性，但都要通过条件 UPDATE 保证不越界。

【五、运行方式与示例】

安装与启动：
  python -m venv .venv && .venv\Scripts\activate
  pip install -r requirements.txt
  set JWT_SECRET_KEY=please-change-this-to-a-32byte-random-string
  set DATABASE_URL=sqlite:///./library.db
  alembic upgrade head
  uvicorn app.main:app --reload --port 8000
  打开 http://127.0.0.1:8000/docs 查看自动生成的接口文档。

界面与交互说明：
  Swagger UI 左侧按 tags 分组（books、readers、borrows、auth、stats）。
  右上角 Authorize 按钮填入 "Bearer <token>" 后可调用受保护接口。
  每个接口的 Responses 区域展示本节第四部分定义的状态码与示例响应体。
  ReDoc（/redoc）适合阅读字段说明；/openapi.json 可供前端生成 SDK。

示例 1（正常借书）：
  请求：POST /api/v1/borrows   {"book_id": 1, "reader_id": 3}
  响应：HTTP 201
        {"code":0,"message":"借阅成功","data":{"id":9,"book_id":1,"reader_id":3,
         "borrow_date":"2024-05-01T09:12:00","due_date":"2024-05-31T23:59:59",
         "status":"borrowed","renew_count":0,"fine_amount":"0.00"}}
示例 2（并发借最后一本）：
  两个请求同时 POST /api/v1/borrows 借同一本 available_copies=1 的书
  响应：一个 201 成功；另一个 409
        {"code":40902,"message":"该图书已全部借出","data":{"book_id":1,"available_copies":0}}
示例 3（超期归还）：
  请求：POST /api/v1/borrows/9/return  {"return_date":"2024-06-03T10:00:00"}
  响应：HTTP 200
        {"code":0,"message":"归还成功，超期 3 天",
         "data":{"record_id":9,"overdue_days":3,"fine_amount":"1.50","available_copies":3}}
示例 4（超出额度）：
  请求：POST /api/v1/borrows  {"book_id":7,"reader_id":3}（该 student 已借 5 本）
  响应：HTTP 409
        {"code":40903,"message":"超出可借额度","data":{"borrowed":5,"max_borrow":5}}
示例 5（异常输入）：
  请求：POST /api/v1/books  {"isbn":"9787115428020","title":"X","total_copies":-1}
  响应：HTTP 422
        {"code":42201,"message":"isbn 校验位错误；total_copies 必须大于等于 0","data":null}
示例 6（鉴权失败）：
  请求：GET /api/v1/borrows/overdue  （无 Authorization 头）
  响应：HTTP 401
        {"code":40100,"message":"未提供认证信息","data":null}

【六、验收标准】

[ ] 未设置 JWT_SECRET_KEY 时启动直接失败并给出明确报错，源码中 grep 不到任何密钥明文。
[ ] 管理员登录成功返回 JWT；错误密码返回 401/40101；连续 5 次失败触发 423 锁定。
[ ] 普通读者角色调用 POST /books 返回 403/40304。
[ ] 借出最后一本书后 available_copies 正确变为 0，再次借阅返回 409/40902。
[ ] 用 50 个并发请求借同一本只有 1 册库存的书，最终成功数恰为 1，available_copies 为 0。
[ ] 读者超出 reader_type 对应额度借书返回 409/40903，data 含已借数量与上限。
[ ] 归还超期图书时 overdue_days 与 fine_amount 计算正确（构造 due_date 在 3 天前，罚金 1.50）。
[ ] 归还跨多本图书后 available_copies 逐次加 1，且从不超过 total_copies。
[ ] 同一记录重复归还返回 409/40907，且库存不被二次增加。
[ ] 续借一次后 due_date 顺延 borrow_days 天；再续借返回 409/40909；超期图书续借返回 409/40908。
[ ] 读者 A 的 token 查询读者 B 的借阅记录返回 403/40302。
[ ] DELETE /books/{id} 对存在未归还记录的图书返回 409/40911，对空闲图书软删除成功。
[ ] total_copies 调小到小于已借出数量时返回 409/40910，数据库值不变。
[ ] GET /books 支持 keyword + category + available 过滤与分页，返回体含 total 与 pages。
[ ] /docs 可正常打开并能对 /books 与 /borrows 发起真实调用。
[ ] pytest 全部用例通过，覆盖借书、还书、超期、并发超卖、权限五类场景。

【七、可选扩展】

1. 增加预约（hold）功能：库存为 0 时读者可排队，归还后按顺序自动通知并保留 24 小时。
2. 引入 APScheduler 每日 00:05 自动扫描超期并生成提醒邮件。
3. 用 Redis + Lua 脚本实现分布式环境下的库存扣减，替代数据库条件更新。
4. 增加罚款缴纳记录表与缴费接口，支持部分缴纳与欠款封禁。
5. 用 Alembic 建种子数据脚本，一键生成 200 本测试图书与 50 个读者。
6. 增加图书封面上传与静态文件访问，配合 Pillow 生成缩略图。

【八、涉及知识点】

- FastAPI 依赖注入、Pydantic v2 校验、自动 OpenAPI 文档生成
- SQLAlchemy 2.0 ORM 声明式建模、关系映射、CHECK 约束与部分唯一索引
- 事务边界与并发控制：条件 UPDATE、行级锁、防超卖与幂等
- 密码哈希（bcrypt）与 JWT 签发校验、基于角色的访问控制
- 分层架构：router / service / model 三层职责划分与依赖倒置
- 分页查询、模糊检索、聚合统计的 SQL 表达
- 统一响应结构与全局异常处理、业务错误码设计
- 使用 Decimal 处理金额、自然日与时间区间计算
- pytest + httpx 的接口测试与并发测试写法
================================================================================
