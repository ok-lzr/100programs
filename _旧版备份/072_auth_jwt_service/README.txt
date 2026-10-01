================================================================================
项目编号：072                    难度等级：★★★★☆（中型项目）
项目名称：JWT 认证与权限服务
所属分类：Web 后端 / 安全与身份认证
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：fastapi、uvicorn、sqlalchemy、pydantic、passlib[bcrypt] 或 argon2-cffi、python-jose[cryptography]、pyotp、slowapi、redis、pytest、httpx
================================================================================

【一、项目背景与目标】

任何一个稍具规模的后端系统最终都会长出同一套东西：注册、登录、令牌签发、令牌刷新、
角色区分、接口限流、防暴力破解、防重放。如果每个业务系统各写一遍，
就会反复出现"token 永不过期""refresh token 可以无限复用""用 MD5 存密码""接口被刷爆"这类事故。

本项目把这些横切关注点抽成一个可独立部署、可被其它服务复用的认证与权限服务。
它对外提供一组 HTTP 接口和一份可被其它服务引入的权限校验模块，
业务系统只需在请求头里带上本服务签发的 access token，并在本服务里注册自己的角色与权限点即可。

目标用户是自己搭建后端、需要一个可靠身份层但不想踩安全坑的开发者。做成之后可以得到：
一套完整的注册/登录/刷新/登出流程，含 refresh token 轮换与重放检测；
基于 RBAC 的角色与权限模型与接口级声明式鉴权；基于令牌桶的接口限流与登录失败锁定；
以及一份可以照抄到生产项目的安全配置清单（密钥管理、口令策略、日志脱敏、审计）。

本项目属于安全类项目，所有涉及口令与密钥的环节都必须按本说明书的第四节实现，不得简化。

【二、功能需求清单】

1. 核心功能
   1.1 用户注册：用户名 4~32 位（字母数字下划线），邮箱格式校验，密码 >=10 位且含大小写与数字。
   1.2 注册成功返回用户 ID，默认分配 role=user，并从 role_permissions 继承其权限集合。
   1.3 用户登录：校验口令，成功后返回 access_token（15 分钟）与 refresh_token（7 天）。
   1.4 令牌刷新：用 refresh_token 换取新的双 token（轮换），旧 refresh_token 立即失效。
   1.5 重放检测：已使用过的 refresh_token 再次提交时，吊销该用户整个 session family。
   1.6 登出：把当前 access token 的 jti 加入黑名单直至其自然过期，并吊销对应 refresh token。
   1.7 修改密码：校验旧密码，成功后吊销该用户所有 refresh token（强制其它端重新登录）。
   1.8 角色与权限：角色表 + 权限表 + 两张关联表，接口通过 require_permission("book:write") 声明。
   1.9 令牌内省：POST /introspect 供其它服务校验 token 是否有效并返回其权限集合。
   1.10 限流：按 IP、按用户、按接口三个维度限流（默认 60 次/分钟），超限返回 429。
   1.11 登录保护：同一账号连续失败 5 次锁定 15 分钟；同一 IP 连续失败 20 次封禁 1 小时。
   1.12 账号状态管理：管理员可禁用/启用账号，禁用后其已签发 token 在下一次请求即失效。
   1.13 审计日志：记录注册、登录成功/失败、刷新、重放、登出、改密、角色变更、限流事件。
   1.14 二次验证（可选开启）：支持 TOTP，开启后登录需同时提交 6 位动态码。

2. 输入与交互
   2.1 全部通过 JSON 交互；注册与登录接口无需鉴权，其余接口需要 Authorization: Bearer <token>。
   2.2 密码字段在请求日志与错误信息中必须完全脱敏，只记录长度与哈希算法名。
   2.3 时间统一使用 UTC 的 ISO 8601 字符串（如 2024-05-01T09:00:00Z），服务端内部只存 UTC。
   2.4 分页参数统一 page（默认 1）与 page_size（默认 20，最大 100）。
   2.5 写操作支持 Idempotency-Key 请求头，同一 key 在 10 分钟内重复提交返回首次结果。
   2.6 交互方式：REST 接口 + Swagger UI + 一份 CLI 自测脚本（scripts/smoke.py）跑通主流程。

3. 输出与展示
   3.1 统一响应 { "code": 0, "message": "ok", "data": {...} }，错误码为 4 位业务码。
   3.2 登录响应：{"code":0,"data":{"access_token":"...","refresh_token":"...",
       "token_type":"bearer","expires_in":900,"refresh_expires_in":604800}}
   3.3 内省响应：{"active":true,"sub":"12","roles":["admin"],
       "permissions":["user:read","user:write","book:write"],"exp":1714550000}
   3.4 所有响应带 X-Request-Id 与 X-RateLimit-Limit / Remaining / Reset 响应头。
   3.5 401 响应体固定包含 reason 字段（expired / invalid_signature / revoked / missing），
       前端据此判断是否需要静默刷新，避免把所有 401 都当成登录失效。

4. 异常与边界处理
   4.1 用户名或邮箱已存在：409 / 40901，data 中给出冲突字段名。
   4.2 密码强度不足：422 / 42201，返回未通过的规则列表（长度、大写、数字、常见弱口令）。
   4.3 密码错误：401 / 40101，不区分"用户不存在"与"密码错误"，避免用户名枚举。
   4.4 账号锁定：423 / 42301，返回解锁时间戳 locked_until，前端据此倒计时。
   4.5 access token 过期：401 / 40102，reason=expired，前端据此触发刷新而不是跳登录页。
   4.6 token 签名错误或被篡改：401 / 40103，reason=invalid_signature。
   4.7 算法为 none 或声明算法与配置不一致的 token 一律拒绝（防 alg 混淆攻击）。
   4.8 refresh token 已使用过：401 / 40104，同时吊销该用户全部会话并写高危审计日志。
   4.9 权限不足：403 / 40301，响应体含 required_permission 便于排查。
   4.10 账号被禁用：403 / 40302，reason=disabled。
   4.11 触发限流：429 / 42901，带 Retry-After 头与剩余等待秒数。
   4.12 请求体过大（> 64KB）返回 413；Content-Type 非 application/json 返回 415。
   4.13 内省接口缺少或错误 X-Internal-Key 返回 401 / 40107，不泄漏任何 token 信息。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：fastapi、uvicorn[standard]、sqlalchemy 2.0、pydantic v2、pydantic-settings、
   passlib[bcrypt] 或 argon2-cffi、python-jose[cryptography]、pyotp、slowapi、
   redis、alembic、pytest、httpx、python-dotenv。
3. 缓存与黑名单：有 Redis 时用 redis-py 实现限流计数与 jti 黑名单；
   无 Redis 时退化为进程内 TTL 字典，接口保持一致并在启动日志中明确警告"仅适合单实例"。
4. 禁止事项：禁止硬编码 SECRET_KEY、数据库口令、INTERNAL_API_KEY、SMTP 口令。
5. 禁止事项：禁止使用 MD5/SHA1 直接哈希口令；禁止自行实现加密算法或随机数算法。
6. 禁止事项：禁止把明文密码、完整 token、refresh token 明文写入日志或审计表。
7. 禁止事项：禁止关闭 JWT 签名校验、禁止把 verify_exp 设为 False、禁止接受 alg=none。
8. 代码组织（必须有以下模块）：
   app/main.py（应用装配、CORS、异常处理器、限流中间件）
   app/config.py（Settings，启动时校验密钥长度与占位值）
   app/security/passwords.py（哈希、校验、需要重哈希判断）
   app/security/tokens.py（签发 access/refresh、解析、黑名单读写）
   app/security/rbac.py（权限模型与 require_permission 依赖工厂）
   app/security/ratelimit.py（令牌桶/固定窗口与登录失败计数）
   app/models.py、app/schemas.py、app/deps.py
   app/routers/auth.py、users.py、admin.py、internal.py
   app/services/session_service.py（刷新轮换与会话族吊销）
   app/services/audit_service.py（结构化审计落库）
   scripts/smoke.py（注册→登录→访问→刷新→重放→登出 全链路自测）
   tests/test_auth.py、test_refresh.py、test_rbac.py、test_ratelimit.py
9. 编码规范：全部函数带类型注解与 docstring；使用 logging 并配置脱敏 Filter。
10. 编码规范：安全相关函数必须写单元测试；常量集中在 config 中，不散落魔法值。

【四、设计要点】

1. 数据结构（核心表与字段）
   表 users：
     id BIGINT PK
     username VARCHAR(32) UNIQUE NOT NULL
     email VARCHAR(120) UNIQUE NOT NULL
     password_hash VARCHAR(255) NOT NULL
     password_algo VARCHAR(16) DEFAULT 'argon2id'
     password_changed_at DATETIME
     status VARCHAR(16) DEFAULT 'active'（active / locked / disabled）
     totp_secret VARCHAR(64) NULL、totp_enabled BOOLEAN DEFAULT 0
     failed_attempts INTEGER DEFAULT 0
     locked_until DATETIME NULL
     created_at DATETIME、last_login_at DATETIME
   表 roles：
     id PK、code VARCHAR(32) UNIQUE（admin / user / auditor）
     name VARCHAR(50)、description VARCHAR(200)、is_builtin BOOLEAN DEFAULT 0
   表 permissions：
     id PK、code VARCHAR(64) UNIQUE（book:read、book:write、user:manage、audit:read）
     resource VARCHAR(32)、action VARCHAR(16)
   表 user_roles：
     user_id FK、role_id FK，联合主键 (user_id, role_id)，附 created_at
   表 role_permissions：
     role_id FK、permission_id FK，联合主键 (role_id, permission_id)
   表 refresh_tokens（会话表）：
     id BIGINT PK、user_id FK
     jti CHAR(36) UNIQUE NOT NULL
     token_hash CHAR(64) NOT NULL（SHA-256 摘要，库里不存原文）
     family_id CHAR(36) NOT NULL（一次登录产生一个 family，用于整族吊销）
     issued_at DATETIME、expires_at DATETIME
     used_at DATETIME NULL、revoked_at DATETIME NULL
     revoke_reason VARCHAR(32) NULL（logout / rotation_replay / password_change / admin_disable）
     user_agent VARCHAR(255)、ip VARCHAR(45)
     索引：idx_rt_user(user_id)、idx_rt_family(family_id)、idx_rt_expires(expires_at)
   表 token_blacklist：
     jti CHAR(36) PK、user_id BIGINT、expires_at DATETIME、reason VARCHAR(32)、created_at
     索引：idx_bl_expires(expires_at)（供定期清理过期条目）
   表 login_attempts：
     id PK、username VARCHAR(32)、ip VARCHAR(45)、success BOOLEAN、created_at DATETIME
     索引：idx_la_user_time(username, created_at)、idx_la_ip_time(ip, created_at)
   表 audit_logs：
     id PK、actor_id BIGINT NULL、event VARCHAR(32)、ip VARCHAR(45)、
     user_agent VARCHAR(255)、detail JSON、created_at DATETIME
     索引：(event, created_at)、(actor_id, created_at)

2. 关键算法或流程
   口令哈希：
     优先 argon2id（argon2-cffi，time_cost=3、memory_cost=65536、parallelism=4）。
     若用 bcrypt 则 rounds=12，并必须处理 72 字节截断问题（超长先做 SHA-256 再 base64 预哈希）。
     哈希串中保留算法标识（$argon2id$ / $2b$），登录校验时按标识选算法，
     校验成功后若发现算法或参数过旧，则用当前策略重新哈希并更新数据库（平滑升级）。
   access token 签发：
     header {"alg":"HS256","typ":"JWT"}
     payload {"sub":str(user_id),"jti":uuid4,"role":["admin"],"scope":["book:write"],
              "type":"access","iat":now,"exp":now+900,"iss":"auth-service","aud":"api"}
     签名密钥从 JWT_SECRET_KEY 读取，绝不写入代码或镜像。
   refresh token 签发：
     payload {"sub":...,"jti":uuid4,"family":family_id,"type":"refresh","iat":now,"exp":now+7d}
     数据库只存 SHA-256(token) 与 jti，校验时用摘要比对，防止库泄漏即令牌泄漏。
   refresh 轮换与重放检测（必须在一个事务内）：
     步骤 1：解析 refresh token，校验签名、exp、type=refresh。
     步骤 2：UPDATE refresh_tokens SET used_at = now()
             WHERE jti = :jti AND used_at IS NULL AND revoked_at IS NULL AND expires_at > now()
     步骤 3：若 rowcount != 1，说明该 token 已被使用或已吊销 → 判定为重放攻击。
     步骤 4：重放时执行 UPDATE refresh_tokens SET revoked_at = now(),
             revoke_reason='rotation_replay' WHERE family_id = :family，
             写 audit_logs(event='refresh_replay')，返回 401/40104。
     步骤 5：成功则插入新 refresh token（同 family_id），签发新 access token 一并返回。
   登出：
     把 access token 的 jti 写入 token_blacklist（expires_at 与 token 一致），
     同时把该 family 下所有未使用的 refresh token 置为 revoked（reason='logout'）。
   令牌桶限流：
     每个 (scope, key) 维护桶，scope 为 ip / user / route；固定窗口计数 + 窗口内滑动修正。
     超阈值返回 429，并在响应头写 X-RateLimit-Limit / Remaining / Reset。
     登录接口额外用 login_attempts 表统计失败次数，达到阈值写 locked_until。
   权限判定：
     require_permission(code) 依赖先解析 token 得到 scope 集合，
     再查询该用户全部角色对应权限的并集（按 user_id 缓存 5 分钟 TTL，角色变更时主动失效），
     命中则放行，否则 403/40301。
   防重放（写接口）：Idempotency-Key 存储 (key, user_id) → 首次响应体的映射，
     10 分钟内重复提交直接返回缓存结果，并在响应头加 Idempotent-Replayed: true。

3. 接口设计（统一前缀 /api/v1）
   POST /auth/register
     请求：{"username":"alice","email":"a@x.com","password":"Str0ngPassw0rd"}
     响应 201：{"code":0,"data":{"id":12,"username":"alice","roles":["user"]}}
     失败：409/40901、422/42201、429/42901。
   POST /auth/login
     请求：{"username":"alice","password":"Str0ngPassw0rd","totp_code":"123456"（可选）}
     响应 200：access_token / refresh_token / token_type / expires_in / refresh_expires_in
     失败：401/40101、423/42301、401/40105（需要或错误的二次验证码）。
   POST /auth/refresh
     请求：{"refresh_token":"eyJ..."}
     响应 200：新的双 token；失败：401/40102（过期）、401/40104（重放，整族吊销）。
   POST /auth/logout       需 Bearer
     响应 200：{"code":0,"data":{"revoked":true,"blacklist_ttl":480}}
     失败：401/40102、401/40103。
   POST /auth/password     需 Bearer
     请求：{"old_password":"...","new_password":"..."}
     响应 200：{"code":0,"data":{"sessions_revoked":3,"password_algo":"argon2id"}}
     失败：401/40101（旧密码错误）、422/42201、409/40902（新旧密码相同）。
   GET  /users/me          需 Bearer
     响应 200：{"id":12,"username":"alice","roles":["user"],"permissions":["book:read"]}
   GET  /users?page=1&page_size=20     需权限 user:read
     响应 200：用户列表（不含 password_hash），支持按 status、role 过滤。
   GET  /users/{id}        需权限 user:read 或本人
   PATCH /users/{id}/status 需权限 user:manage
     请求：{"status":"disabled"}；响应 200；禁用后其 token 在下一次请求返回 403/40302。
   POST /users/{id}/roles  需权限 user:manage
     请求：{"role_codes":["auditor"]}（覆盖式设置）；响应 200，返回最终角色与权限并集。
   GET  /roles             需权限 user:manage；POST /roles 新建自定义角色。
   POST /roles/{code}/permissions  需权限 user:manage，请求 {"permission_codes":[...]} 覆盖设置。
   POST /introspect         供内部服务调用，需 X-Internal-Key 头
     请求：{"token":"eyJ..."}
     响应 200：{"active":true,"sub":"12","roles":["admin"],"permissions":[...],"exp":1714550000}
     失败：401/40107（内部密钥错误）。
   GET  /admin/audit-logs   需权限 audit:read
     查询参数：event、actor_id、start、end、page、page_size；响应 200 分页列表。
   GET  /admin/sessions/{user_id}   需权限 user:manage
     响应 200：该用户所有有效会话（jti、ip、user_agent、issued_at、expires_at）。
   DELETE /admin/sessions/{jti}     需权限 user:manage
     响应 200：吊销指定会话（写 revoked_at 并把对应 access jti 加入黑名单）。
   GET  /healthz            不鉴权
     响应 200：{"status":"ok","db":"ok","redis":"ok|degraded"}

4. 鉴权方式与安全要求
   - 密钥管理：JWT_SECRET_KEY / INTERNAL_API_KEY / DATABASE_URL / REDIS_URL 只从环境变量或 .env 读取。
   - .env 必须加入 .gitignore；仓库中只保留 .env.example（值为占位符，不含真实密钥）。
   - 启动校验：密钥长度 >= 32 字节，且不等于示例占位值，否则拒绝启动并给出修复提示。
   - 密钥轮换：支持 JWT_SECRET_KEY_PREVIOUS，验签时先试当前密钥再试上一个，实现无感轮换。
   - 令牌存储：refresh token 只存 SHA-256 摘要；access token 不落库，仅黑名单保留 jti。
   - 防重放：refresh token 一次性使用 + family 整族吊销；写接口支持 Idempotency-Key。
   - 防算法混淆：解析时显式指定 algorithms=["HS256"]，并校验 iss 与 aud 与配置一致。
   - 限流阈值：登录 10 次/5 分钟/IP；注册 5 次/小时/IP；普通接口 60 次/分钟/用户；
     内省接口 600 次/分钟/服务标识。超限返回 429 并写审计事件 rate_limited。
   - 口令策略：禁止使用内置常见弱口令表（top-1000）中的口令，命中时返回 422/42201。
   - 日志脱敏：logging.Filter 把 password、token、refresh_token、authorization、secret
     字段统一替换为 ***，并禁止记录请求体原文中的敏感字段。

5. 错误处理与并发事务注意点
   - 刷新轮换必须在事务内以"条件 UPDATE + rowcount 判断"实现，禁止先查询后写入，
     否则并发刷新会产生两个有效 refresh token（经典的令牌泄漏放大问题）。
   - 登录失败计数使用数据库行级原子更新：
     UPDATE users SET failed_attempts = failed_attempts + 1 WHERE id = :id RETURNING failed_attempts，
     达到阈值时在同一事务内写 locked_until，避免并发下计数丢失。
   - 多实例部署时限流与黑名单必须依赖 Redis；进程内实现只在单实例场景可用并在日志中警告。
   - 所有鉴权失败路径不得泄漏用户是否存在；响应时间尽量保持一致以避免时序侧信道。
   - 数据库唯一约束冲突统一由 IntegrityError 处理器映射为 409，避免竞态下重复注册。
   - 黑名单与 refresh_tokens 表需定时清理过期行（每日一次），避免无限增长。

【五、运行方式与示例】

安装与启动：
  python -m venv .venv && .venv\Scripts\activate
  pip install -r requirements.txt
  copy .env.example .env
  在 .env 中填写 JWT_SECRET_KEY=<32 字节以上随机串>、DATABASE_URL、REDIS_URL、INTERNAL_API_KEY
  生成密钥：python -c "import secrets;print(secrets.token_urlsafe(48))"
  alembic upgrade head
  uvicorn app.main:app --reload --port 8100
  python scripts/smoke.py --base-url http://127.0.0.1:8100      # 一键跑通主流程

界面与交互说明：
  Swagger UI（/docs）按 auth / users / roles / admin / internal 五组展示接口。
  Authorize 按钮支持直接粘贴 access_token；每个接口都标注了所需权限点与可能的错误码。
  smoke.py 会依次执行注册、登录、访问 /users/me、刷新、重放旧 refresh、登出，
  并在最后打印每一步的状态码与关键字段，便于人工核对。

示例 1（注册后登录）：
  请求：POST /api/v1/auth/login {"username":"alice","password":"Str0ngPassw0rd"}
  响应：HTTP 200
        {"code":0,"message":"ok","data":{"access_token":"eyJhbGciOiJIUzI1NiJ9...",
         "refresh_token":"eyJhbGciOiJIUzI1NiJ9...","token_type":"bearer",
         "expires_in":900,"refresh_expires_in":604800}}
示例 2（刷新后旧 token 重放）：
  请求：POST /api/v1/auth/refresh {"refresh_token":"<已使用过的 token>"}
  响应：HTTP 401
        {"code":40104,"message":"refresh token 已失效，该会话已被吊销","data":{"family_revoked":true}}
示例 3（权限不足）：
  请求：GET /api/v1/users  带 user 角色 token
  响应：HTTP 403
        {"code":40301,"message":"权限不足","data":{"required_permission":"user:read"}}
示例 4（异常输入 / 弱密码）：
  请求：POST /api/v1/auth/register {"username":"bob","email":"b@x.com","password":"123456"}
  响应：HTTP 422
        {"code":42201,"message":"密码强度不足","data":{"failed_rules":["长度>=10","包含大写字母"]}}
示例 5（触发限流）：
  响应：HTTP 429  Retry-After: 240
        {"code":42901,"message":"请求过于频繁，请稍后再试","data":{"retry_after":240}}
示例 6（令牌过期后访问）：
  请求：GET /api/v1/users/me  （使用已过期 token）
  响应：HTTP 401
        {"code":40102,"message":"token 已过期","data":{"reason":"expired"}}

【六、验收标准】

[ ] SECRET_KEY 未配置或等于示例值时服务拒绝启动，日志给出明确原因与修复建议。
[ ] register 成功后数据库中的 password_hash 以 $argon2id$ 或 $2b$ 开头，全程无明文口令落库或落日志。
[ ] 密码错误的响应与用户不存在的响应完全一致（状态码 401、业务码 40101、消息相同）。
[ ] 连续 5 次密码错误后第 6 次返回 423/42301，且 locked_until 与配置的 15 分钟一致。
[ ] access token 过期后调用受保护接口返回 401/40102 且 reason=expired，用 refresh 换新后可继续访问。
[ ] 同一 refresh token 使用两次，第二次返回 401/40104，且该 family 下所有 token 均被吊销。
[ ] 篡改 token 载荷后返回 401/40103；构造 alg=none 的 token 同样被拒绝。
[ ] 登出后原 access token 立即不可用，且黑名单记录在 token 自然过期后被清理。
[ ] 用户被 admin 置为 disabled 后，其持有 token 的下一次请求返回 403/40302。
[ ] 普通用户调用 GET /users 返回 403/40301 且响应体含 required_permission。
[ ] 登录接口 5 分钟内第 11 次请求返回 429/42901，响应头含 X-RateLimit-Remaining: 0。
[ ] 修改密码成功后该用户全部 refresh token 失效，sessions_revoked 数量与实际一致。
[ ] /introspect 未携带正确 X-Internal-Key 时返回 401/40107，携带时返回正确的角色与权限集合。
[ ] 同一 Idempotency-Key 重复提交写接口，第二次不产生副作用且响应头含 Idempotent-Replayed。
[ ] 日志文件中 grep "password" 与 grep "token" 只能看到脱敏后的 ***。
[ ] pytest 用例覆盖注册、登录、锁定、刷新轮换、重放、限流、RBAC 七类场景并全部通过。

【七、可选扩展】

1. 增加 TOTP 二次验证（pyotp）的完整流程：绑定二维码、动态码校验、恢复码。
2. 增加 OAuth2 授权码模式的授权端点，允许第三方应用接入本服务。
3. 使用 RS256 非对称签名，把公钥以 JWKS 形式暴露在 /.well-known/jwks.json。
4. 增加设备管理接口，列出并单独踢出某个登录会话（已列入基础接口，可扩展推送通知）。
5. 接入结构化审计导出（JSONL），供 SIEM 系统采集与告警。
6. 增加邮件验证与找回密码流程（一次性 token + 15 分钟有效期）。
7. 用 Locust 或 wrk 编写压测脚本，验证限流与刷新接口在并发下的正确性。

【八、涉及知识点】

- 口令哈希算法原理与 argon2id / bcrypt 参数选择、平滑算法升级策略
- JWT 结构、HS256 签名与校验、过期与吊销（黑名单）机制
- refresh token 轮换与重放检测、会话族（family）整族吊销
- RBAC 模型设计：用户、角色、权限三级与接口级声明式鉴权
- 令牌桶 / 固定窗口限流、登录失败锁定与暴力破解防护
- 密钥管理与配置注入、密钥轮换、日志脱敏、时序侧信道等安全编码习惯
- 数据库原子更新与事务隔离在并发鉴权场景中的正确用法
- 幂等键设计与写接口防重放
- OWASP 认证类风险（A01 越权、A02 加密失败、A07 认证失败）的对应防护措施
================================================================================
