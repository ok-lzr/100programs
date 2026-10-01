================================================================================
项目编号：076                    难度等级：★★★★☆（中型项目）
项目名称：代码片段分享服务
所属分类：Web 后端 / 开发者工具服务
建议工时：4 ~ 5 天
运行环境：Python 3.10+    第三方依赖：fastapi、uvicorn、sqlalchemy、pydantic、pygments、passlib[bcrypt]、python-jose[cryptography]、markupsafe、bleach、redis、pytest、httpx
================================================================================

【一、项目背景与目标】

团队里经常出现这样的情形：一段报错日志要发给同事看，直接贴进 IM 会丢格式、被表情打断；
一段配置要跨网络传，用邮件又太长；临时给外部同学看一段代码，希望三天后自动失效，
并且不希望被搜索引擎索引到。市面上的 pastebin 站点要么不能自建、要么默认公开可被爬虫抓取。

本项目实现一套自建代码片段分享服务，核心能力是：粘贴任意文本或代码 → 分配一个短链接 → 
任何人（或仅持有私有链接的人）通过该链接查看带语法高亮的渲染结果 → 
支持设置过期时间（10 分钟 / 1 小时 / 1 天 / 7 天 / 30 天 / 永久）、
访问密码、私有链接（不可枚举的随机 token）、以及创建时的可选"阅后即焚"。
服务记录每次访问的计数与时间，创建者可随时删除。

技术重点在于：内容与元数据分离存储（大文本不宜放数据库行内）、
语法高亮的服务端渲染与 XSS 防护（高亮结果必须经过白名单清洗）、
私有 token 的不可枚举性（至少 128 位熵）、
过期策略的两种口径（滑动过期 vs 绝对过期）以及匿名创建的限流与滥用防护。

【二、功能需求清单】

1. 核心功能
   1.1 创建片段：提交标题、内容、语言（可选）、过期策略、可见性、可选密码，返回短链接。
   1.2 语言自动识别：未指定语言时用 Pygments 的 guess_lexer 猜测，猜测失败按纯文本处理。
   1.3 语法高亮渲染：服务端用 Pygments 把代码渲染为 HTML（含行号），
       渲染结果经白名单清洗后输出，禁止直接透传内容中的 HTML。
   1.4 短 ID：默认 8 位 Base62 随机 ID（secrets.choice），可用作公开链接。
   1.5 私有链接：额外生成 32 位私有 token，只有带 token 的链接可访问；
       私有片段不出现在任何列表与公开接口中。
   1.6 过期策略：burn_after_read（阅后即焚）、10m、1h、1d、7d、30d、never 七种。
   1.7 访问密码：可选，bcrypt 哈希存储，查看时需 POST 密码换取短期访问票据。
   1.8 原始内容接口：提供 /raw 返回 text/plain 原文，便于 curl 与脚本消费。
   1.9 下载接口：提供 /download 以附件形式下载，文件名按 title 与语言推断扩展名。
   1.10 访问计数：记录 view_count 与最近若干次访问的摘要（时间、IP 摘要、UA 类型）。
   1.11 管理：创建者（登录用户）可查看自己创建的片段列表、删除片段、修改过期时间。
   1.12 匿名创建：允许不登录创建，但读取内容不超过 64KB、过期时间最长 1 天，并按 IP 限流。
   1.13 滥用防护：内容中若包含大量 URL（> 20 个）标记为可疑并限制其可访问性（仅创建者可看）。
   1.14 清理任务：定时删除过期片段及其内容文件、访问记录。

2. 输入与交互
   2.1 创建接口接受 JSON 或 application/x-www-form-urlencoded（便于命令行与网页表单共用）。
   2.2 请求字段：{"title":"报错日志","content":"...","language":"python","expire":"1d",
       "visibility":"private","password":null,"burn_after_read":false}
   2.3 内容上限：匿名 64KB、登录用户 512KB；超出返回 413 / 41301。
   2.4 标题长度 1~120 字符，可为空（为空时显示"未命名片段"并尝试从首行注释推断）。
   2.5 language 必须是 Pygments 支持的语言别名（用 get_lexer_by_name 校验），非法值返回 422。
   2.6 查看接口支持查询参数 ?format=html|raw|text，默认 html（带高亮与行号）。
   2.7 交互方式：REST 接口 + 网页查看页 /p/{paste_id} + 命令行示例（curl）。

3. 输出与展示
   3.1 统一响应 { "code": 0, "message": "ok", "data": {...} }（查看页与 /raw 除外）。
   3.2 创建响应：{"code":0,"data":{"paste_id":"aB3xK9zQ","url":"https://p.example.com/p/aB3xK9zQ",
       "private_token":null,"expire_at":"2024-05-02T09:12:00Z","language":"python",
       "size":1842,"burn_after_read":false}}
   3.3 查看页为完整 HTML：包含标题、语言标签、创建时间、剩余有效期、行号代码块、
       "复制""下载""查看原文"三个按钮、以及页脚的"此内容由用户生成"声明。
   3.4 查看页响应头带 X-Paste-Id、X-Paste-Expire-At、X-Robots-Tag: noindex, nofollow。
   3.5 /raw 返回 Content-Type: text/plain; charset=utf-8，不带任何 HTML 包装。
   3.6 访问计数接口（创建者可见）：{"view_count":128,"first_viewed_at":"...","last_viewed_at":"...",
       "recent":[{"at":"2024-05-01T09:00:00Z","ip_prefix":"203.0.113.0","ua_type":"desktop"}]}

4. 异常与边界处理
   4.1 内容为空或全为空白字符：422 / 42201。
   4.2 内容超过大小上限：413 / 41301，data 返回 limit 与实际大小。
   4.3 非法语言：422 / 42202，data 返回可用语言示例列表（前 10 个）。
   4.4 非法过期策略值：422 / 42203，列出允许的取值。
   4.5 匿名用户设置 expire=never 或 30d：422 / 42204，提示匿名最长 1 天。
   4.6 密码长度不在 4~64：422 / 42205。
   4.7 paste_id 不存在或格式非法（非 8 位 Base62）：404 / 40401，返回友好提示页。
   4.8 片段已过期：410 / 41001，提示过期时间；同时触发异步删除。
   4.9 阅后即焚片段已被读过：410 / 41002，提示"该片段已被读取并销毁"。
   4.10 私有片段未带正确 token：404 / 40401（不返回 403，避免暴露存在性）。
   4.11 需要密码但未提供：401 / 40102，返回密码输入表单；密码错误：401 / 40103。
   4.12 非创建者删除或查看他人私有片段统计：404 / 40401。
   4.13 限流触发：429 / 42901（匿名创建 5 次/小时/IP，查看 120 次/分钟/IP）。
   4.14 可疑内容（URL 数量 > 20 或含大量重复行）：创建成功但标记 suspicious=1，
       仅创建者可查看，并返回提示 message="内容被标记为可疑，仅创建者可访问"。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：fastapi、uvicorn[standard]、sqlalchemy 2.0、pydantic v2、
   pygments（语法高亮与语言识别）、markupsafe（HTML 转义）、bleach（高亮结果白名单清洗）、
   passlib[bcrypt]（访问密码）、python-jose[cryptography]（用户 JWT）、
   redis（限流与票据，可降级为内存实现）、jinja2（查看页模板）、pytest、httpx、alembic。
3. 内容存储：内容默认写入文件系统（STORAGE_ROOT/pastes/ab/cd/<paste_id>.txt），
   数据库只存元数据与内容摘要；内容 < 4KB 时允许内联在数据库 content_inline 字段以提升性能。
4. 禁止事项：禁止把用户内容直接插入 HTML 模板（必须经 markupsafe 转义或 bleach 清洗）。
5. 禁止事项：禁止使用自增 ID 或可预测序列作为 paste_id（会导致全站内容被爬取枚举）。
6. 禁止事项：禁止在未校验 token 的情况下返回私有片段内容，包括 /raw 与 /download。
7. 禁止事项：禁止记录完整 IP 明文；访问记录只保留 /24（IPv4）或 /48（IPv6）网段前缀与哈希。
8. 代码组织（必须有以下模块）：
   app/main.py、app/config.py（STORAGE_ROOT、大小限制、过期档位、限流参数）
   app/database.py、app/models.py、app/schemas.py、app/deps.py
   app/core/ids.py（Base62 生成、token 生成、格式校验）
   app/core/expiry.py（过期档位解析、过期判定、剩余时间格式化）
   app/core/highlight.py（Pygments 渲染、行号、样式表生成、语言猜测）
   app/core/sanitize.py（bleach 白名单配置与清洗函数）
   app/storage/content_store.py（内容读写、原子写入、删除、大小校验）
   app/services/paste_service.py（创建、读取、计数、删除、可疑判定）
   app/services/access_service.py（密码校验、票据签发、访问记录）
   app/templates/view.html、password.html、error.html（jinja2）
   app/routers/pastes.py、auth.py、admin.py
   app/tasks/purge.py（过期清理）
   tests/test_create.py、test_expiry.py、test_highlight_xss.py、test_private.py、test_ratelimit.py
9. 编码规范：所有函数带类型注解与 docstring；使用 logging 记录 paste_id 与操作类型。
10. 编码规范：渲染函数必须是纯函数（输入内容 + 语言 → HTML 字符串），便于单测覆盖 XSS 用例。

【四、设计要点】

1. 数据结构（核心表与字段）
   表 users（可选登录，用于管理自己的片段）：
     id BIGINT PK、username VARCHAR(32) UNIQUE、password_hash VARCHAR(128)、
     role VARCHAR(16) DEFAULT 'user'、is_active BOOLEAN、created_at DATETIME
   表 pastes：
     id BIGINT PK
     paste_id CHAR(8) UNIQUE NOT NULL（公开 ID，Base62）
     private_token CHAR(32) NULL UNIQUE（私有 token，仅私有片段有值）
     owner_id FK(users.id) NULL（匿名为 NULL）
     title VARCHAR(120) NULL
     language VARCHAR(32) NOT NULL DEFAULT 'text'
     size INTEGER NOT NULL（内容字节数）
     line_count INTEGER NOT NULL
     content_sha256 CHAR(64) NOT NULL
     content_inline TEXT NULL（小于 4KB 时内联）
     content_path VARCHAR(512) NULL（大于等于 4KB 时指向文件）
     visibility VARCHAR(16) NOT NULL DEFAULT 'public'（public / private）
     password_hash VARCHAR(128) NULL
     expire_policy VARCHAR(16) NOT NULL（burn / 10m / 1h / 1d / 7d / 30d / never）
     expire_at DATETIME NULL（never 时为 NULL）
     burn_after_read BOOLEAN DEFAULT 0
     is_burned BOOLEAN DEFAULT 0
     view_count INTEGER NOT NULL DEFAULT 0
     suspicious BOOLEAN DEFAULT 0
     created_ip_prefix VARCHAR(45) NULL
     created_at DATETIME、last_viewed_at DATETIME、deleted_at DATETIME NULL
     索引：uk_pastes_paste_id(paste_id) 唯一、idx_pastes_owner(owner_id, created_at)、
           idx_pastes_expire(expire_at)（供清理任务扫描）
   表 paste_views（访问记录，保留 30 天）：
     id BIGINT PK
     paste_id CHAR(8) NOT NULL
     viewed_at DATETIME NOT NULL
     ip_hash CHAR(64) NULL（IP + 每日盐的 SHA-256）
     ip_prefix VARCHAR(45) NULL
     ua_type VARCHAR(16) NULL（desktop / mobile / bot / cli / other）
     referer_host VARCHAR(255) NULL
     is_owner BOOLEAN DEFAULT 0
     索引：idx_pv_paste_time(paste_id, viewed_at)
   表 access_tickets（密码验证后的短期票据）：
     ticket CHAR(32) PK、paste_id CHAR(8)、
     issued_at DATETIME、expires_at DATETIME（5 分钟）、
     used_count INTEGER DEFAULT 0、max_uses INTEGER DEFAULT 200
   表 rate_limits（无 Redis 时的降级方案）：
     bucket_key VARCHAR(128) PK、window_start DATETIME、counter INTEGER、
     说明：有 Redis 时该表不使用，全部走 Redis 原子计数。

2. 关键算法或流程
   paste_id 生成：
     步骤 1：定义 Base62 字符表 "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"。
     步骤 2：用 secrets.choice 随机取 8 位，得到候选 ID（约 2.18e14 组合，8 位下枚举不现实）。
     步骤 3：插入数据库并依赖唯一索引兜底；IntegrityError 时重试，最多 5 次。
     步骤 4：为避免"看起来像单词"的歧义，可选用去掉易混字符的 58 字符表（去掉 0O1lI）。
   private_token 生成：
     使用 secrets.token_urlsafe(24) 得到 32 字符（192 位熵），存入 pastes.private_token（唯一索引）。
     访问私有片段必须 URL 中带 ?t=<private_token>；校验用 hmac.compare_digest 防时序侧信道。
   过期判定（每次读取时执行，同时由定时任务兜底清理）：
     步骤 1：若 burn_after_read 且 is_burned → 410/41002。
     步骤 2：若 expire_at 不为 NULL 且 expire_at <= now → 触发异步删除并返回 410/41001。
     步骤 3：never 策略 expire_at 为 NULL，永不判定过期。
     说明：采用"绝对过期"口径（从创建时间起算），不做滑动续期，
     这样创建者能明确知道链接何时失效，也便于清理任务批量删除。
   阅后即焚流程：
     读取时用条件更新抢占：UPDATE pastes SET is_burned = 1, view_count = view_count + 1
     WHERE paste_id = :id AND is_burned = 0 且未过期；rowcount = 1 时返回内容，
     并立即安排异步删除任务（延迟 5 秒执行，保证响应先返回）。
     rowcount = 0 说明已被别人抢先读取，直接返回 410/41002。
   语法高亮渲染：
     步骤 1：语言解析：优先用请求指定的别名；否则用 guess_lexer_for_filename(title, content)，
             再退化为 guess_lexer(content)，最后 fallback 到 TextLexer。
     步骤 2：用 pygments.highlight(content, lexer, HtmlFormatter(linenos='table',
             cssclass='hl', nowrap=False, encoding='utf-8')) 生成 HTML。
     步骤 3：对生成结果执行 bleach.clean，允许标签集合为
             ["span","pre","div","table","tbody","tr","td","code","br"]，
             允许属性 {"span":["class"],"td":["class"],"div":["class"],"table":["class"]}，
             strip=True 去掉其它标签，属性白名单只保留 class。
     步骤 4：把清洗后的 HTML 插入模板（模板中该变量标记为安全）。
     步骤 5：样式表由 HtmlFormatter.get_style_defs('.hl') 生成并缓存（进程内一次性生成）。
     XSS 校验用例必须包含：<script>、<img onerror=>、<a href="javascript:...">、
     <style> 注入等，全部应被清洗或转义，渲染结果中不得出现 on* 事件属性。
   访问计数与记录：
     读取成功时执行原子 UPDATE pastes SET view_count = view_count + 1,
     last_viewed_at = now() WHERE paste_id = :id（禁止读改写）。
     访问记录异步写入 paste_views（批量 50 条或每 2 秒 flush）；
     bot 类型（UA 含 bot/spider/crawler）不计入 view_count，只记录明细并标记 ua_type='bot'。
   可疑内容判定：
     规则 1：内容中 http(s) 链接数量 > 20 → suspicious。
     规则 2：内容行数 > 5000 且平均行长 < 8（疑似刷量）→ suspicious。
     规则 3：相同行重复率 > 80% 且行数 > 100 → suspicious。
     命中后 visibility 强制为 private 且 suspicious = 1，创建响应中给出提示。
   密码校验与票据：
     bcrypt 校验通过后生成 ticket（32 字符），写入 access_tickets（过期 5 分钟、
     最多 200 次使用），响应返回 {"url": "/p/aB3xK9zQ?ticket=..."}。
     后续访问校验 ticket 存在、未过期、used_count < max_uses，并原子递增 used_count。
     密码错误按 (paste_id, ip_prefix) 限流：5 次/10 分钟。

3. 接口设计（HTTP 前缀 /api/v1；查看页在根路径 /p/{paste_id}）
   POST /api/v1/pastes   可匿名；带 Bearer 则归属该用户
     请求：{"title":"报错日志","content":"Traceback ...","language":"python",
           "expire":"1d","visibility":"private","password":"ab12","burn_after_read":false}
     响应 201：{"code":0,"message":"创建成功","data":{"paste_id":"aB3xK9zQ",
              "url":"https://p.example.com/p/aB3xK9zQ","private_token":"Xk9fQ2mZ...",
              "language":"python","size":1842,"line_count":46,
              "expire_at":"2024-05-02T09:12:00Z","burn_after_read":false,"suspicious":false}}
     失败：413/41301（超限）、422/42201（内容为空）、422/42202（语言非法）、
           422/42203（过期策略非法）、422/42204（匿名过期过长）、429/42901（限流）。
   GET /api/v1/pastes/{paste_id}   公开（私有需 ?t=token）
     查询参数：format=html|text|json（json 返回内容原文与元数据）
     响应 200：format=json 时 {"code":0,"data":{"paste_id":"aB3xK9zQ","title":null,
              "language":"python","content":"Traceback ...","size":1842,
              "created_at":"2024-05-01T09:12:00Z","expire_at":"2024-05-02T09:12:00Z",
              "view_count":12}}
     失败：404/40401（不存在或私有 token 错误）、410/41001（过期）、410/41002（已焚毁）、
           401/40102（需要密码，json 请求返回 code 而非表单）。
   GET /p/{paste_id}   公开
     行为：返回渲染后的 HTML 查看页；需要密码时返回密码表单页（200，不是 401，
           便于浏览器直接展示）；私有片段 token 错误返回 404 提示页。
     响应头：X-Robots-Tag: noindex, nofollow；Cache-Control: private, max-age=0, no-store。
   POST /api/v1/pastes/{paste_id}/unlock   公开
     请求：{"password":"ab12"}（支持表单）
     响应 200：{"code":0,"data":{"ticket":"...","expires_in":300,
              "access_url":"/p/aB3xK9zQ?ticket=..."}}
     失败：401/40103（密码错误）、429/42901（尝试过多）。
   GET /p/{paste_id}/raw   公开（私有需 token，密码保护需 ticket）
     响应 200：Content-Type: text/plain; charset=utf-8，内容为原文；
              Content-Disposition 不带 attachment（便于浏览器直接显示）。
     失败：404/40401、410/41001、410/41002、401/40102。
   GET /p/{paste_id}/download   公开（同上）
     响应 200：Content-Type: application/octet-stream，
              Content-Disposition: attachment; filename*=UTF-8''<title>.<ext>。
     扩展名映射：python→py、javascript→js、typescript→ts、go→go、rust→rs、
              java→java、sql→sql、bash→sh、json→json、yaml→yaml、text→txt。
   GET /api/v1/pastes/{paste_id}/stats   需 Bearer 且为所有者
     响应 200：{"code":0,"data":{"view_count":128,"first_viewed_at":"...",
              "last_viewed_at":"...","recent":[{"at":"...","ip_prefix":"203.0.113.0",
              "ua_type":"desktop","referer_host":"news.ycombinator.com"}]}}
     失败：404/40401（不存在或非本人）。
   GET /api/v1/pastes?page=1&page_size=20&expired=false   需 Bearer
     响应 200：当前用户的片段分页列表（含 view_count、expire_at、状态 status：
              active / expired / burned / deleted）。
   PATCH /api/v1/pastes/{paste_id}   需 Bearer 且为所有者
     请求：{"title":"新标题","expire":"7d","visibility":"public"}
     行为：只能延长到期时间（新 expire_at 必须晚于当前值），缩短需显式传 force=true。
     失败：404/40401、422/42203。
   DELETE /api/v1/pastes/{paste_id}   需 Bearer 且为所有者
     响应 200：软删除并立即删除内容文件；私有片段删除后 token 立即失效。
   GET /api/v1/languages   公开
     响应 200：Pygments 支持的语言别名列表（用于前端下拉框，含 alias 与 title）。
   GET /api/v1/healthz   公开
     响应 200：{"status":"ok","db":"ok","storage":"ok","redis":"ok|degraded"}

4. 鉴权方式与安全要求
   - 查看接口默认完全公开；私有片段通过 32 字符高熵 token 保护（192 位熵，不可枚举）。
   - token 比较使用 hmac.compare_digest，避免逐字符比较带来的时序信息泄漏。
   - 访问密码 bcrypt 哈希存储；验证成功后签发 5 分钟票据，避免密码出现在 URL 中。
   - 登录用户口令同样 bcrypt（rounds=12）；JWT HS256，密钥从 JWT_SECRET_KEY 读取（>= 32 字节）。
   - 全部输出经 HTML 转义或 bleach 白名单清洗；渲染函数必须通过 XSS 单测用例。
   - 响应头统一加 X-Robots-Tag: noindex, nofollow 与
     Content-Security-Policy: default-src 'none'; style-src 'self' 'unsafe-inline'，
     防止片段内容被搜索引擎收录或被外部脚本利用。
   - 限流：匿名创建 5 次/小时/IP；登录创建 60 次/小时/用户；
     查看 120 次/分钟/IP；解锁尝试 5 次/10 分钟/(paste_id + IP 网段)。
   - 记录创建者与访问者的 IP 只保留哈希与网段前缀，保留 30 天后清理。
   - 内容文件权限仅服务进程可读；通过应用层提供 /raw 与 /download，不暴露静态目录。
   - 禁止把 suspicious 片段公开展示；即使有链接也仅创建者可读。

5. 错误处理与并发事务注意点
   - 大内容写入使用"临时文件 + os.replace"原子落位，数据库写入失败时删除已落盘文件。
   - 内容与元数据的一致性：先写文件再写库；读取时若文件缺失，返回 500/50002 并记录告警，
     同时把该片段标记为损坏（deleted_at 置位）避免反复报错。
   - view_count 使用原子累加，禁止先查后写；热点片段（每秒数百访问）可先在 Redis 计数，
     每分钟批量回写数据库。
   - 阅后即焚必须用条件 UPDATE 抢占（is_burned = 0 → 1），保证同一片段只被一个人读到内容。
   - 清理任务每分钟扫描 expire_at < now 的记录（每次最多 500 条），
     删除内容文件、写审计、把 deleted_at 置位；同时清理过期的 access_tickets 与 rate_limits。
   - 数据库唯一约束（paste_id、private_token）是最终防线，应用层重试仅用于减少失败率。
   - PATCH 延长过期时间时使用条件 UPDATE：
     UPDATE pastes SET expire_at = :new WHERE paste_id = :id AND (expire_at IS NULL OR expire_at < :new)，
     避免并发修改导致有效期被意外缩短。
   - 内容清洗函数不得访问数据库或网络（纯函数），保证在渲染路径上无阻塞。

【五、运行方式与示例】

安装与启动：
  python -m venv .venv && .venv\Scripts\activate
  pip install -r requirements.txt
  set JWT_SECRET_KEY=please-change-this-32bytes-minimum
  set DATABASE_URL=sqlite:///./paste.db
  set STORAGE_ROOT=D:\paste_storage
  set MAX_SIZE_ANON=65536
  set MAX_SIZE_USER=524288
  alembic upgrade head
  uvicorn app.main:app --reload --port 8500
  python -m app.tasks.purge --once     # 手动执行一次过期清理

界面与交互说明：
  查看页 /p/{paste_id} 顶部显示标题（或"未命名片段"）、语言徽章、创建时间、
  剩余有效期倒计时；主体为带行号的代码块；右上角三个按钮：
  "复制"（复制原文）、"下载"（/download）、"查看原文"（/raw）。
  需要密码时页面只显示一个密码输入框与提交按钮；
  私有片段使用错误 token 时显示统一的"片段不存在或已失效"页面，不区分原因。

示例 1（创建公开片段）：
  请求：POST /api/v1/pastes
        {"title":"快速排序","content":"def qsort(a):\n    ...","language":"python","expire":"7d"}
  响应：HTTP 201
        {"code":0,"message":"创建成功","data":{"paste_id":"aB3xK9zQ",
         "url":"http://127.0.0.1:8500/p/aB3xK9zQ","private_token":null,
         "language":"python","size":312,"line_count":12,
         "expire_at":"2024-05-08T09:12:00Z","burn_after_read":false,"suspicious":false}}
示例 2（查看 JSON 原文）：
  请求：GET /api/v1/pastes/aB3xK9zQ?format=json
  响应：HTTP 200
        {"code":0,"data":{"paste_id":"aB3xK9zQ","language":"python",
         "content":"def qsort(a):\n    ...","size":312,"view_count":13}}
示例 3（阅后即焚）：
  第一次 GET /p/burn1234 → HTTP 200 返回内容，响应头 X-Paste-Burned: true
  第二次 GET /p/burn1234 → HTTP 410
        {"code":41002,"message":"该片段已被读取并销毁","data":{"burned_at":"2024-05-01T09:20:00Z"}}
示例 4（私有片段 token 错误）：
  请求：GET /p/aB3xK9zQ?t=wrong-token-value
  响应：HTTP 404
        {"code":40401,"message":"片段不存在或无权访问","data":null}
示例 5（密码保护）：
  请求：POST /api/v1/pastes/aB3xK9zQ/unlock  {"password":"ab12"}
  响应：HTTP 200
        {"code":0,"data":{"ticket":"7f3c9a2b...","expires_in":300,
         "access_url":"/p/aB3xK9zQ?ticket=7f3c9a2b..."}}
示例 6（异常输入 / XSS 内容）：
  请求：POST /api/v1/pastes {"content":"<script>alert(document.cookie)</script>",
        "language":"html","expire":"1d"}
  响应：HTTP 201（内容按纯文本/高亮文本展示）
        查看页渲染结果中只有被转义的文本与 <span class="..."> 高亮标签，
        不含 <script>、不含 onerror=、不执行任何脚本。
示例 7（超限与限流）：
  请求：匿名 POST /api/v1/pastes  {"content":"<70000 字节>","expire":"1d"}
  响应：HTTP 413
        {"code":41301,"message":"匿名用户内容上限 65536 字节","data":{"limit":65536,"size":70000}}
  第 6 次匿名创建（1 小时内）：
  响应：HTTP 429  Retry-After: 1800
        {"code":42901,"message":"创建过于频繁，请稍后再试","data":{"retry_after":1800}}

【六、验收标准】

[ ] 连续创建 1000 个片段，paste_id 无重复且全部为 8 位 Base62 字符。
[ ] paste_id 不呈现可枚举规律：按创建顺序连续取样，相邻 ID 无递增或可推断关系。
[ ] 私有片段的 private_token 为 32 字符且随机分布，未带正确 token 访问返回 404/40401。
[ ] 私有片段不出现在创建者的公开列表与任何他人可见的接口中。
[ ] 内容含 <script>alert(1)</script> 时创建成功，查看页源码中不含可执行 script 标签。
[ ] 内容含 <img src=x onerror=alert(1)> 与 javascript: 链接时同样被清洗，渲染结果无 on* 属性。
[ ] 语言留空时 python 内容被正确猜测为 python；指定非法语言返回 422/42202。
[ ] expire=10m 的片段在 11 分钟后访问返回 410/41001，清理任务已删除其内容文件。
[ ] burn_after_read 片段的第二次访问返回 410/41002，view_count 恰好为 1。
[ ] 并发两次读取同一阅后即焚片段，只有一次返回内容，另一次返回 410/41002。
[ ] 密码保护的片段未解锁访问返回 401/40102，正确密码换取票据后可读，票据 5 分钟后失效。
[ ] 匿名用户设置 expire=never 返回 422/42204；匿名内容超过 64KB 返回 413/41301。
[ ] 匿名创建第 6 次（1 小时内同一 IP）返回 429/42901。
[ ] /raw 返回 text/plain 且内容与原始提交逐字节一致（含换行与缩进）。
[ ] /download 的 Content-Disposition 含按语言推断的扩展名，中文标题使用 RFC 5987 编码。
[ ] 非创建者访问 /stats 与 DELETE 均返回 404/40401，片段仍可正常访问。
[ ] 含 21 个 URL 的内容被标记 suspicious 且仅创建者可读。
[ ] 所有查看响应都带 X-Robots-Tag: noindex, nofollow 与 CSP 响应头。
[ ] pytest 用例覆盖创建、过期、XSS 清洗、私有访问、限流五类场景并全部通过。

【七、可选扩展】

1. 增加片段编辑历史（每次修改存一个版本，支持 diff 对比）。
2. 增加团队空间：同一团队的成员共享可见列表与统计。
3. 增加 CLI 客户端（click 实现 `paste new file.py --expire 1d` 并回显短链）。
4. 增加图片/二进制粘贴：转存到对象存储并在查看页内嵌预览。
5. 增加代码执行沙箱演示（明确标注仅用于学习且必须容器隔离，默认关闭）。
6. 增加嵌入（embed）模式：/embed/{paste_id} 输出可 iframe 引入的仅代码块页面。
7. 用 Redis 缓存热点片段的高亮 HTML（键为 paste_id + 内容摘要，TTL 10 分钟）。

【八、涉及知识点】

- Pygments 词法分析、语言猜测、HTML 渲染与行号表格
- XSS 防护：HTML 转义、bleach 白名单清洗、CSP 响应头
- 不可枚举 ID 设计：Base62 随机 ID 与高熵 token、hmac.compare_digest 定时比较
- 过期策略设计：绝对过期 vs 滑动过期、惰性删除与定时清理的结合
- 阅后即焚的并发抢占（条件 UPDATE 与 rowcount 判定）
- 内容与元数据分离存储、原子文件写入与一致性补偿
- 原子计数、热点数据缓存与批量回写
- 限流与滥用防护（可疑内容识别、匿名配额）
- 隐私合规：IP 哈希加盐与网段化、访问记录保留期限
- Jinja2 模板渲染与"标记安全"变量的风险边界
- HTTP 内容类型与 Content-Disposition（RFC 5987）实践
================================================================================
