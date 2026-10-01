================================================================================
项目编号：073                    难度等级：★★★★☆（中型项目）
项目名称：短链接服务
所属分类：Web 后端 / 在线服务
建议工时：3 ~ 4 天
运行环境：Python 3.10+    第三方依赖：fastapi、uvicorn、sqlalchemy、pydantic、redis、passlib[bcrypt]、python-jose[cryptography]、qrcode、pytest、httpx
================================================================================

【一、项目背景与目标】

运营同学在微信、短信、印刷物料里发长链接时经常遇到三个问题：链接太长被截断、
同一个活动链接没法区分是哪个渠道带来的点击、链接发出去之后想停也停不掉。
市面上的短链服务要么收费、要么不能自建、要么把跳转日志全部留在别人服务器上。

本项目实现一套可自建的短链接服务：把任意长链接压缩成 7 位短码，
访问短链时以 HTTP 302 跳转到原始地址，并同步记录每一次点击的时间、来源、UA、地区（可选）。
它支持自定义短码、有效期、访问上限、密码保护，并提供点击统计接口。

做成之后你可以：给每个渠道生成不同短码来区分投放效果；给活动链接设置 7 天有效期到期自动失效；
给内部资料链接设置访问密码；查看某个短链的总点击、独立访客与按小时/按天的趋势。
本项目的技术难点集中在三处：短码的唯一性与生成效率、跳转接口的高并发读写、
状态码选择与缓存语义（302 与 301 的区别会直接影响统计准确性）。

【二、功能需求清单】

1. 核心功能
   1.1 创建短链：提交原始 URL，系统生成短码并返回完整短链与二维码图片地址。
   1.2 自定义短码：允许用户指定 4~16 位短码（字母数字下划线连字符），已被占用则返回冲突。
   1.3 URL 规范化：跳转前不做改写，但入库前统一处理：补全缺失的 scheme（默认 https）、
       去掉首尾空白、拒绝 javascript: 与 data: 等危险 scheme、长度上限 2048。
   1.4 302 跳转：GET /{code} 返回 302 与 Location 头（不用 301，避免浏览器永久缓存导致统计失真）。
   1.5 点击统计：每次跳转异步记录一条点击（时间、IP 摘要、UA、Referer、国家/地区可空）。
   1.6 短链过期策略：支持 expires_at（绝对时间）与 max_clicks（最大点击次数），二者任一满足即失效。
   1.7 密码保护：短链可设置访问密码（bcrypt 哈希存储），访问时需带 ?pwd=xxx 或 POST 校验。
   1.8 短链管理：列出当前用户创建的短链、查看详情、修改目标地址、启用/停用、删除（软删除）。
   1.9 统计接口：总点击、独立 IP 数、按天/按小时趋势、Top Referer、Top UA 类型。
   1.10 二维码：为短链生成 PNG 二维码（qrcode 库），支持指定尺寸与容错级别。
   1.11 鉴权：创建与管理短链需要登录（JWT）；跳转接口完全公开且不做鉴权。
   1.12 限流：创建接口 10 次/分钟/用户；跳转接口 600 次/分钟/IP，防刷。

2. 输入与交互
   2.1 请求与响应均为 JSON（二维码接口返回 image/png）。
   2.2 创建请求字段：{"url":"https://example.com/a/very/long/path?x=1",
       "custom_code":null,"expires_at":null,"max_clicks":null,"password":null,"title":"双十一活动"}
   2.3 短码规范：正则 [A-Za-z0-9_-]{4,16}，保留字（api、admin、static、docs、healthz）不可占用。
   2.4 分页参数统一 page（默认 1）与 page_size（默认 20，最大 100）。
   2.5 统计接口时间参数 granularity 取值 hour / day，range 取值 7d / 30d / 90d。
   2.6 跳转接口支持 HEAD 请求（只返回 Location 不返回 body），便于监控系统探活。

3. 输出与展示
   3.1 统一响应 { "code": 0, "message": "ok", "data": {...} }，跳转接口除外（返回 302 重定向）。
   3.2 创建响应：{"code":0,"data":{"code":"aB3xK9z","short_url":"https://s.example.com/aB3xK9z",
       "target_url":"https://...","expires_at":null,"max_clicks":null,"qr_url":"/api/v1/links/aB3xK9z/qr"}}
   3.3 列表响应 data 含 items、total、page、page_size、pages。
   3.4 统计响应的每个数据点形如 {"bucket":"2024-05-01","clicks":128,"unique_ips":93}。
   3.5 跳转失败时返回一个内置的提示页（HTML），页面上写明失效原因，不再暴露原始地址。

4. 异常与边界处理
   4.1 原始 URL 非法（无 scheme、scheme 为 javascript/data、长度 > 2048）：422 / 42201。
   4.2 自定义短码格式非法或为保留字：422 / 42202；已被占用：409 / 40901。
   4.3 系统短码连续碰撞超过 5 次：返回 500 / 50001 并记录告警日志（提示容量需要扩容）。
   4.4 短码不存在：404 / 40401，返回提示页。
   4.5 短链已过期（expires_at < now）：410 / 41001，提示页写明"链接已过期"。
   4.6 短链点击次数耗尽（clicks >= max_clicks）：410 / 41002，提示"访问次数已达上限"。
   4.7 短链被停用（is_active=False）：403 / 40301，提示"链接已被停用"。
   4.8 需要密码但未提供：401 / 40101，提示页含密码输入表单；密码错误：401 / 40102。
   4.9 修改或删除他人的短链：404 / 40401（不返回 403，避免暴露短码存在性）。
   4.10 超限：429 / 42901，带 Retry-After。
   4.11 目标地址返回 4xx/5xx 与本服务无关（本服务只负责跳转），但统计中记录该短链的真实点击。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：fastapi、uvicorn[standard]、sqlalchemy 2.0、pydantic v2、
   redis（跳转缓存、计数、限流）、passlib[bcrypt]（短链密码）、
   python-jose[cryptography]（用户 JWT）、qrcode[pil]、Pillow、
   user-agents 或自写解析函数（UA 归类）、pytest、httpx、alembic。
3. 缓存策略：短码 → 目标地址的映射放在 Redis（TTL 1 小时），命中缓存不查库；
   创建/修改/停用/删除时主动删除对应缓存键，保证强一致。
4. 禁止事项：禁止把用户提交的 URL 直接拼进 HTML 或用 eval/exec 处理。
5. 禁止事项：禁止在短码生成中使用可预测的自增 ID 直接转进制（会被遍历枚举），
   必须使用随机安全短码或"自增 ID + 混淆密钥"的方式。
6. 禁止事项：禁止记录完整 IP 明文超过 90 天；统计用哈希摘要或截断后的网段（隐私合规）。
7. 代码组织（必须有以下模块）：
   app/main.py（应用装配与路由注册）
   app/config.py（BASE_URL、短码长度、Redis、JWT 配置）
   app/database.py、app/models.py、app/schemas.py、app/deps.py
   app/core/codegen.py（短码生成与碰撞重试）
   app/core/url_rules.py（URL 校验与规范化、危险 scheme 黑名单）
   app/core/ua.py（User-Agent 归类为 desktop/mobile/bot/other）
   app/services/link_service.py（创建、校验、失效判断、软删除）
   app/services/stats_service.py（点击落库、聚合查询、趋势计算）
   app/cache.py（Redis 封装，含降级为进程内字典的逻辑）
   app/routers/links.py、redirect.py、stats.py、auth.py
   tests/test_codegen.py、test_redirect.py、test_expiry.py、test_stats.py
8. 编码规范：全部函数带类型注解与 docstring；使用 logging，禁止 print。
9. 编码规范：跳转路径上的代码必须尽量短小（目标 < 5ms 完成缓存命中路径），
   禁止在跳转主流程中做同步数据库写入，点击记录走后台任务或队列。
10. 编码规范：所有时间字段以 UTC 存储，展示时转换为配置的本地时区。

【四、设计要点】

1. 数据结构（核心表与字段）
   表 users：
     id PK、username VARCHAR(32) UNIQUE、password_hash VARCHAR(128)、
     role VARCHAR(16) DEFAULT 'user'、is_active BOOLEAN、created_at DATETIME
   表 short_links：
     id BIGINT PK
     code VARCHAR(16) UNIQUE NOT NULL
     target_url VARCHAR(2048) NOT NULL
     title VARCHAR(120) NULL
     owner_id FK(users.id) NULL（匿名创建的短链允许 owner_id 为空）
     is_custom BOOLEAN DEFAULT 0
     is_active BOOLEAN DEFAULT 1
     password_hash VARCHAR(128) NULL
     expires_at DATETIME NULL
     max_clicks INTEGER NULL
     click_count INTEGER NOT NULL DEFAULT 0（冗余计数，异步与明细表校准）
     created_at DATETIME、updated_at DATETIME、deleted_at DATETIME NULL
     索引：uk_short_links_code(code) 唯一、idx_short_links_owner(owner_id, created_at)、
           idx_short_links_expires(expires_at)
   表 click_events：
     id BIGINT PK
     link_id FK(short_links.id)
     code VARCHAR(16) NOT NULL（冗余，便于按短码直接查询）
     clicked_at DATETIME NOT NULL
     ip_hash CHAR(64)（IP + 每日盐的 SHA-256，用于统计独立访客且不存明文）
     ip_prefix VARCHAR(45) NULL（保留 /24 或 /48 网段用于粗粒度分析）
     user_agent VARCHAR(512) NULL、ua_type VARCHAR(16)（desktop/mobile/bot/other）
     referer VARCHAR(1024) NULL、referer_host VARCHAR(255) NULL
     country VARCHAR(64) NULL、accept_language VARCHAR(64) NULL
     索引：idx_click_link_time(link_id, clicked_at)、idx_click_code_time(code, clicked_at)
     说明：该表按周分区或按月归档（PostgreSQL 分区表；SQLite 场景按月份建表 click_events_202405）
   表 link_stats_daily（预聚合，避免统计接口全表扫描）：
     id PK、link_id FK、stat_date DATE、clicks INTEGER、unique_ips INTEGER、
     UNIQUE(link_id, stat_date)
   表 short_code_pool（可选，用于"预生成短码池"方案）：
     code VARCHAR(16) PK、reserved_at DATETIME、used_by_link_id BIGINT NULL

2. 关键算法或流程
   短码生成（方案 A：随机短码，推荐默认使用）：
     步骤 1：定义字符表 62 个字符（a-z A-Z 0-9）加 - 与 _ 共 64 个字符。
     步骤 2：用 secrets.choice 从字符表随机取 7 位，得到候选码。
     步骤 3：先查 Redis SETNX（key=code:lock:<code>，TTL 10 秒）占位，再尝试插入数据库。
     步骤 4：插入捕获 IntegrityError；若冲突则重试，最多 5 次。
     步骤 5：5 次全冲突则返回 500/50001 并告警（说明短码空间或索引异常）。
     容量说明：7 位 64 字符约 4.4 万亿组合，1 万条数据下碰撞概率可忽略。
   短码生成（方案 B：自增 ID + 混淆，适合需要短码更短或有序的场景）：
     取数据库自增 ID（如 100023），用 Feistel 或乘法取模（id * A + B mod 2^32）
     变换后转 62 进制输出 5~6 位；A 必须与 2^32 互质，且 A、B 从环境变量读取保密，
     避免外人根据短码推算出创建顺序与总量。
   跳转流程（GET /{code}，目标 < 5ms）：
     步骤 1：规范化 code，长度不在 4~16 直接 404。
     步骤 2：读 Redis 缓存（结构 hash：target、active、expires_at、max_clicks、pwd_hash）。
     步骤 3：缓存未命中则查数据库，写入缓存（TTL 1 小时，匿名为 5 分钟）。
     步骤 4：按顺序校验：存在性 → is_active → 过期 → 点击数上限 → 密码。
     步骤 5：任一校验失败，返回对应状态码与提示页。
     步骤 6：校验通过，把点击事件放入内存队列 / Redis Stream，由后台协程批量落库。
     步骤 7：对 click_count 做 Redis INCR，定期（每 30 秒）批量回写数据库。
     步骤 8：返回 302，Location 为目标地址，Cache-Control: no-store 防止中间层缓存统计失真。
   过期与上限判定：以服务器 UTC 时间为准；max_clicks 判定使用 Redis 计数器的原子 INCR 结果，
     超过上限时立即把短链在缓存中标记为 exhausted 并拒绝后续请求。
   统计聚合：
     原始明细按天聚合到 link_stats_daily（定时任务每小时重算最近 2 天）。
     趋势接口优先读预聚合表，只有当天数据才查明细表并合并，保证 90 天查询仍在 200ms 内。
     unique_ips 计算：COUNT(DISTINCT ip_hash)（ip_hash 的盐每日轮换，跨天不串联个人轨迹）。
   UA 归类规则：含 bot/spider/crawler/slurp 关键字归为 bot；
     含 Mobile/Android/iPhone 归为 mobile；含 Windows/Macintosh/Linux 归为 desktop；其余为 other。

3. 接口设计（统一前缀 /api/v1；跳转接口位于根路径 /{code}）
   POST /api/v1/auth/register、POST /api/v1/auth/login
     与认证服务一致，返回 JWT（本服务内自签，HS256，密钥读 JWT_SECRET_KEY）。
   POST /api/v1/links   需 Bearer
     请求：{"url":"https://example.com/path?a=1","custom_code":"promo2024",
           "expires_at":"2024-12-31T23:59:59Z","max_clicks":1000,"password":"open123456","title":"活动"}
     响应 201：{"code":0,"data":{"code":"promo2024","short_url":"https://s.example.com/promo2024",
              "target_url":"https://example.com/path?a=1","expires_at":"2024-12-31T23:59:59Z",
              "max_clicks":1000,"has_password":true,"qr_url":"/api/v1/links/promo2024/qr"}}
     失败：422/42201（URL 非法）、422/42202（自定义短码非法）、409/40901（短码已占用）、
           429/42901（限流）。
   GET /api/v1/links?page=1&page_size=20&keyword=promo&active=true   需 Bearer
     响应 200：当前用户短链分页列表（含 click_count 与状态字段 status：
       active / expired / exhausted / disabled）。
   GET /api/v1/links/{code}   需 Bearer 且为所有者
     响应 200：短链详情；404/40401（不存在或不属于当前用户）。
   PATCH /api/v1/links/{code}   需 Bearer 且为所有者
     请求：{"target_url":"https://new.example.com","expires_at":"2025-01-31T00:00:00Z","is_active":true}
     响应 200：更新后的详情；行为：同步删除 Redis 缓存键。
     失败：422/42201、404/40401。
   DELETE /api/v1/links/{code}   需 Bearer 且为所有者
     响应 200：{"code":0,"data":{"code":"promo2024","deleted":true}}（软删除 deleted_at）
   GET /api/v1/links/{code}/qr?size=256&box_size=10   需 Bearer 且为所有者
     响应 200：image/png 二进制；size 范围 128~1024，超出返回 422/42203。
     失败：404/40401。
   GET /api/v1/links/{code}/stats?range=30d&granularity=day   需 Bearer 且为所有者
     响应 200：{"code":0,"data":{"total_clicks":5321,"unique_ips":1804,
       "series":[{"bucket":"2024-05-01","clicks":128,"unique_ips":93}, ...],
       "top_referers":[{"host":"mp.weixin.qq.com","clicks":2100}, ...],
       "ua_types":{"mobile":3800,"desktop":1400,"bot":121,"other":0},
       "max_clicks":1000,"remaining_clicks":null}}
     失败：404/40401、422/42204（range 或 granularity 非法）。
   GET /{code}   公开，无鉴权
     成功：HTTP 302，Location: https://example.com/path?a=1，Cache-Control: no-store，
           响应头 X-Link-Code: promo2024。
     失败：404/40401（不存在）、410/41001（过期）、410/41002（次数耗尽）、
           403/40301（停用）、401/40101（需要密码，返回 HTML 密码表单）。
   POST /{code}/unlock   公开
     请求：表单或 JSON {"password":"open123456"}
     成功：302 跳转（并写点击）；失败：401/40102，5 次失败后该 IP 锁定 10 分钟。
   GET /healthz   公开
     响应 200：{"status":"ok","db":"ok","redis":"ok|degraded"}

4. 鉴权方式与安全要求
   - 用户口令使用 bcrypt（rounds=12）哈希；短链访问密码同样使用 bcrypt，绝不存明文。
   - JWT_SECRET_KEY 从环境变量读取，长度 >= 32，缺失或为占位值时启动失败。
   - 跳转接口不做鉴权但做限流与异常检测：同一 IP 1 分钟内请求 > 200 个不同短码，
     判定为枚举扫描，返回 429 并在审计日志中记录。
   - 短码不可用自增序号直接暴露；使用随机短码或混淆变换，防止批量遍历。
   - 危险 scheme 黑名单（javascript、data、vbscript、file）一律拒绝；URL 允许 http/https 两种。
   - 跳转直接使用 302 与 Location 头，禁止把 URL 写入 HTML 的 href 之外的位置，
     禁止在响应中回显用户提交的未转义内容（防 XSS）。
   - 提示页为静态模板（jinja2 或字符串常量），所有插入内容经过 HTML 转义。
   - IP 只保留哈希与网段；点击明细保留期限 90 天，过期由定时任务清理。
   - 密码错误的短链解锁尝试按 IP + code 限流（5 次/10 分钟），防止口令爆破。

5. 错误处理与并发事务注意点
   - 短码唯一性依赖数据库唯一索引（uk_short_links_code）作为最终防线，
     应用层的 Redis 占位只是减少冲突概率，不能替代唯一索引。
   - click_count 是冗余计数，更新使用原子语句
     UPDATE short_links SET click_count = click_count + 1 WHERE id = :id，禁止读改写。
   - 跳转主流程不写数据库：点击明细走内存队列批处理（每 200 条或每 1 秒 flush 一次），
     进程退出时尝试 flush，失败则写入本地 WAL 文件下次补偿。
   - max_clicks 判定以 Redis 原子计数器为准；数据库 click_count 可能存在秒级延迟，
     统计接口需向用户说明"实时性约 1 秒"。
   - 缓存与数据库一致性：修改、停用、删除短链时先写库再删缓存（Cache-Aside），
     若删缓存失败则记录待重试任务，最多重试 3 次。
   - 过期短链不主动物理删除，由每日任务把 deleted_at 超过 30 天的记录归档到历史表并清理。
   - 高并发下 302 响应不做任何阻塞 IO；Redis 不可用时降级为直接查库，
     并在响应头加 X-Cache: bypass，同时日志告警。

【五、运行方式与示例】

安装与启动：
  python -m venv .venv && .venv\Scripts\activate
  pip install -r requirements.txt
  set JWT_SECRET_KEY=please-change-this-32bytes-minimum
  set DATABASE_URL=sqlite:///./shortlink.db
  set REDIS_URL=redis://127.0.0.1:6379/0
  set BASE_URL=http://127.0.0.1:8200
  alembic upgrade head
  uvicorn app.main:app --reload --port 8200

界面与交互说明：
  没有独立前端，交互全部通过 HTTP 完成，/docs 提供 Swagger UI。
  跳转接口在根路径（如 http://127.0.0.1:8200/promo2024），
  用浏览器直接访问即可看到 302 跳转效果；失效短链会看到一个说明页面。
  统计接口返回的 series 数组可直接交给前端绘制折线图。

示例 1（创建短链）：
  请求：POST /api/v1/links
        Authorization: Bearer eyJ...
        {"url":"https://example.com/a/very/long/path?utm_source=wechat","title":"微信投放"}
  响应：HTTP 201
        {"code":0,"message":"创建成功","data":{"code":"aB3xK9z",
         "short_url":"http://127.0.0.1:8200/aB3xK9z",
         "target_url":"https://example.com/a/very/long/path?utm_source=wechat",
         "status":"active","click_count":0}}
示例 2（正常跳转）：
  请求：GET /aB3xK9z
  响应：HTTP 302  Location: https://example.com/a/very/long/path?utm_source=wechat
        Cache-Control: no-store   X-Link-Code: aB3xK9z
示例 3（过期短链）：
  请求：GET /promo2024   （expires_at 为昨天）
  响应：HTTP 410
        {"code":41001,"message":"该链接已于 2024-12-31 过期","data":{"expired_at":"2024-12-31T23:59:59Z"}}
        浏览器中展示为友好提示页。
示例 4（自定义短码冲突）：
  请求：POST /api/v1/links  {"url":"https://a.example.com","custom_code":"promo2024"}
  响应：HTTP 409
        {"code":40901,"message":"短码已被占用，请更换","data":{"code":"promo2024"}}
示例 5（统计查询）：
  请求：GET /api/v1/links/aB3xK9z/stats?range=7d&granularity=day
  响应：HTTP 200
        {"code":0,"data":{"total_clicks":128,"unique_ips":93,
         "series":[{"bucket":"2024-05-01","clicks":40,"unique_ips":31},
                   {"bucket":"2024-05-02","clicks":88,"unique_ips":62}],
         "top_referers":[{"host":"mp.weixin.qq.com","clicks":96}],
         "ua_types":{"mobile":110,"desktop":12,"bot":6,"other":0}}}
示例 6（异常输入）：
  请求：POST /api/v1/links  {"url":"javascript:alert(1)"}
  响应：HTTP 422
        {"code":42201,"message":"URL 非法：不允许的协议 javascript","data":{"field":"url"}}

【六、验收标准】

[ ] 创建短链后数据库 short_links 中 code 唯一，重复创建 1 万条无主键冲突异常。
[ ] 自定义短码与已有短码冲突时返回 409/40901，且不产生脏数据。
[ ] 自定义短码使用 a-z A-Z 0-9 _ - 之外的字符时返回 422/42202。
[ ] GET /{code} 返回 302 且 Location 与创建时提交的 URL 完全一致（含查询参数与锚点）。
[ ] 短链可用 HEAD 请求得到 302，且不返回响应体。
[ ] expires_at 设为过去时间后访问返回 410/41001，Redis 中也无该短链的有效缓存。
[ ] max_clicks=3 的短链第 4 次访问返回 410/41002，click_count 恰为 3。
[ ] is_active=False 的短链访问返回 403/40301。
[ ] 带密码的短链未提供密码访问返回 401/40101 与密码表单，正确密码可跳转，错误密码返回 401/40102。
[ ] 用户 A 无法查看或删除用户 B 的短链（均返回 404/40401）。
[ ] 点击明细在 3 秒内落库，统计接口的 total_clicks 与实际访问次数一致。
[ ] 同一 IP 重复访问 10 次时 unique_ips 为 1，不同 IP 访问时正确累加。
[ ] 枚举扫描（1 分钟内请求 200 个不同短码）触发 429 并写审计日志。
[ ] 提交 javascript: 与实际长度 3000 的 URL 均返回 422/42201 且不写库。
[ ] 修改短链目标地址后，下一次访问立即跳转到新地址（缓存已失效）。
[ ] pytest 用例覆盖短码生成、跳转状态码、过期与上限、密码、统计五类场景并全部通过。

【七、可选扩展】

1. 增加批量创建接口（一次提交 500 条 URL，返回 CSV 与二维码打包 ZIP）。
2. 接入 IP 地理位置库（GeoLite2 或离线 CSV）补充 country / city 维度统计。
3. 增加渠道 UTM 参数自动附加功能，为同一目标地址批量生成多平台短码。
4. 使用 PostgreSQL 分区表 + 物化视图重做统计层，支持千万级点击明细。
5. 增加短链防钓鱼：接入威胁情报黑名单，命中时拒绝创建并提示风险。
6. 增加 Webhook：短链首次被点击、达到点击数上限时回调通知所有者。

【八、涉及知识点】

- 短码生成策略：随机字符表、碰撞重试、自增 ID 混淆（Feistel / 乘法取模）
- HTTP 状态码语义：301 与 302 的区别、410 与 404 的选择、缓存头对统计的影响
- 唯一性保证：数据库唯一索引 + Redis 占位锁的双层设计
- 高并发读写分离：缓存旁路（Cache-Aside）、异步批量落库、原子计数
- Redis 数据结构应用：String 计数、Hash 缓存对象、Stream 队列、SETNX 锁
- URL 校验与安全：scheme 白名单、长度限制、XSS 转义、短码枚举防护
- 数据聚合与预计算：按天预聚合表、分区/归档策略、DISTINCT 统计
- 隐私合规：IP 哈希加盐、保留期限与自动清理
- 二维码生成与图片响应（qrcode + Pillow）
================================================================================
