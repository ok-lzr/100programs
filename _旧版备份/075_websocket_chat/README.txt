================================================================================
项目编号：075                    难度等级：★★★★☆（中型项目）
项目名称：多人在线聊天室
所属分类：Web 后端 / 实时通信
建议工时：4 ~ 5 天
运行环境：Python 3.10+    第三方依赖：fastapi、uvicorn[standard]（含 websockets）、sqlalchemy、pydantic、passlib[bcrypt]、python-jose[cryptography]、redis、pytest、httpx
================================================================================

【一、项目背景与目标】

团队需要一个内部讨论区时，往往先用微信群顶着，结果消息和文件散落在私人手机里，
新同事看不到历史上下文，项目之间的讨论互相串台。自建聊天室的价值不在"能发消息"，
而在于消息可留存、房间可隔离、成员可控。

本项目实现一个基于 WebSocket 的多人在线聊天室服务：用户可以注册登录、创建或加入房间、
在房间内实时收发消息、查看历史消息、看到当前在线成员列表，并支持简单的私聊与消息撤回。
前端可以用几十行 HTML + 原生 WebSocket 完成，因此项目重点完全落在服务端：
长连接生命周期管理、房间广播、在线状态维护、历史消息分页加载与断线重连补偿。

技术难点主要有四处：一是并发连接下的房间成员表必须线程/协程安全；
二是广播不能因为某个慢客户端阻塞整个房间（需要每连接发送队列与超时丢弃）；
三是历史消息要支持"向上翻页"（按 before_id 游标分页，不用 OFFSET）；
四是断线重连后要能补齐断连期间的消息（按 last_message_id 拉取增量）。

【二、功能需求清单】

1. 核心功能
   1.1 用户注册与登录：用户名唯一，口令 bcrypt 哈希；登录返回 JWT 用于 WebSocket 握手鉴权。
   1.2 房间管理：创建房间（公开/私密）、列出房间、加入房间、退出房间、查看房间成员。
   1.3 私密房间：可设置房间口令（bcrypt 哈希），加入时校验；房主可将成员踢出。
   1.4 实时消息：WebSocket 文本消息广播到房间内所有在线连接（含发送者回显）。
   1.5 消息类型：text（文本）、system（系统提示，如"张三加入了房间"）、image（仅存 URL）。
   1.6 历史消息：HTTP 接口按房间分页拉取历史，支持 before_id 游标；WebSocket 也支持拉取。
   1.7 在线用户：房间内在线成员列表实时更新，成员进出时向房间广播事件。
   1.8 正在输入：发送 typing 事件，服务端转发给同房间其他成员（限频 1 次/2 秒/人）。
   1.9 消息撤回：发送者可在 5 分钟内撤回自己的消息，撤回后广播 recall 事件并把库里内容标记为已撤回。
   1.10 私聊：支持 user:{user_id} 格式的虚拟房间，仅双方可见（本期只做在线私聊，不做离线存储）。
   1.11 心跳保活：服务端每 30 秒发 ping，客户端 10 秒内未回 pong 则判定掉线并清理连接。
   1.12 断线重连补偿：客户端重连后带 last_message_id，服务端返回断连期间的增量消息（最多 200 条）。
   1.13 限流与防刷：每人每 10 秒最多 10 条消息，单条长度 <= 500 字符，超出被拒并回执 error。
   1.14 消息持久化：所有 text 消息落库，包含房间、发送者、内容、时间、客户端消息 ID（幂等）。

2. 输入与交互
   2.1 WebSocket 端点：/ws/{room_id}?token=<JWT>；握手阶段校验 token 与房间成员资格。
   2.2 客户端上行消息统一为 JSON：{"type":"text","client_msg_id":"uuid","content":"大家好"}
   2.3 服务端下行消息统一为 JSON：{"type":"text","id":123,"room_id":7,"user_id":3,
       "username":"张三","content":"大家好","created_at":"2024-05-01T09:12:00Z"}
   2.4 事件类型：hello、text、system、typing、recall、error、pong、presence、history。
   2.5 client_msg_id 由客户端生成（UUID4），服务端用于幂等去重：同一用户同一 ID 只入库一次。
   2.6 HTTP 接口中分页参数 limit（默认 30，最大 100）与 before_id（游标，可选）。
   2.7 交互方式：REST 接口（房间与历史）+ WebSocket（实时）+ 一个内置的调试页面 /chat。

3. 输出与展示
   3.1 HTTP 统一响应 { "code": 0, "message": "ok", "data": {...} }。
   3.2 WebSocket 下行不使用 code 包装，直接是事件对象（type 字段区分），错误事件含 code 与 message。
   3.3 历史消息响应：{"code":0,"data":{"items":[...],"has_more":true,"next_before_id":118}}
   3.4 presence 事件：{"type":"presence","room_id":7,"online":[{"user_id":3,"username":"张三"}],
       "count":2,"joined":"李四","left":null}
   3.5 在线人数在房间列表接口中作为 online_count 字段返回（从内存/Redis 读取，允许 5 秒延迟）。
   3.6 连接建立后服务端首先下发 hello 事件，包含当前用户 ID、房间信息与在线成员列表。

4. 异常与边界处理
   4.1 WebSocket 握手 token 缺失或无效：以 1008（policy violation）关闭，不发送业务错误。
   4.2 非房间成员连接：以 1008 关闭，关闭原因写"not a member of this room"。
   4.3 房间不存在：HTTP 接口返回 404 / 40401；WebSocket 以 1008 关闭。
   4.4 私密房间口令错误：HTTP 返回 401 / 40101；连续 5 次错误锁定该 IP 10 分钟。
   4.5 消息内容为空或超长（> 500 字符）：不入库，回 error 事件 code=42201。
   4.6 消息发送过快（10 秒内第 11 条）：回 error 事件 code=42901 并丢弃该消息。
   4.7 client_msg_id 重复：返回首次入库的消息（幂等），不重复广播。
   4.8 撤回超时（超过 5 分钟）或撤回他人消息：回 error code=40301。
   4.9 慢客户端：单连接发送队列超过 100 条时丢弃最新消息并回 error（避免内存堆积）。
   4.10 重复登录同一账号：允许多端在线，各自独立连接，消息都收到。
   4.11 房间被房主解散：向所有连接广播 system 事件后以 1001 关闭连接。
   4.12 数据库写入失败：回 error code=50001，其他成员不受影响（单条消息失败不中断房间）。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，全面使用 async/await。
2. 允许使用的库：fastapi、uvicorn[standard]（内置 websockets 支持）、sqlalchemy 2.0（异步使用
   aiosqlite / asyncpg，或同步 + 线程池）、pydantic v2、passlib[bcrypt]、
   python-jose[cryptography]、redis（多进程广播与在线状态）、pytest、httpx、pytest-asyncio。
3. 连接管理：单进程内用 ConnectionManager 维护 room_id -> {user_id: set[WebSocket]}；
   多进程部署时通过 Redis Pub/Sub 把消息转发到所有进程，本机连接由本进程直接发送。
4. 禁止事项：禁止在 WebSocket 处理循环中执行阻塞 IO（同步数据库调用需用 run_in_threadpool）；
   禁止把客户端内容直接写回 HTML（前端渲染用 textContent，服务端只存纯文本）。
5. 禁止事项：禁止明文存储用户口令与房间口令；禁止把 JWT 打印到日志。
6. 禁止事项：禁止无限制增长内存队列（必须设定队列上限与丢弃策略）。
7. 代码组织（必须有以下模块）：
   app/main.py（HTTP 路由 + WebSocket 路由装配）
   app/config.py（JWT、Redis、限流参数、心跳间隔）
   app/database.py、app/models.py、app/schemas.py、app/deps.py
   app/ws/manager.py（ConnectionManager：join/leave/broadcast/send_personal）
   app/ws/hub.py（Redis Pub/Sub 订阅循环，跨进程分发）
   app/ws/protocol.py（事件类型常量与消息序列化/校验）
   app/services/room_service.py、app/services/message_service.py、app/services/presence_service.py
   app/routers/auth.py、rooms.py、messages.py（HTTP 部分）
   app/ws/handlers.py（on_text / on_typing / on_recall / on_pong 分发）
   static/chat.html（极简调试页面：登录、房间列表、消息区、在线列表）
   tests/test_ws_text.py、test_history.py、test_presence.py、test_ratelimit.py
8. 编码规范：全部函数带类型注解与 docstring；使用 logging 并记录连接 ID、房间、用户。
9. 编码规范：连接关闭必须在 finally 中统一清理（成员表、在线状态、Redis 订阅）。
10. 编码规范：并发结构只允许在事件循环内访问，禁止跨线程直接修改字典。

【四、设计要点】

1. 数据结构（核心表与字段）
   表 users：
     id BIGINT PK、username VARCHAR(32) UNIQUE NOT NULL、password_hash VARCHAR(128) NOT NULL、
     nickname VARCHAR(32) NULL、avatar_url VARCHAR(255) NULL、
     is_active BOOLEAN DEFAULT 1、created_at DATETIME、last_seen_at DATETIME
   表 rooms：
     id BIGINT PK、name VARCHAR(64) NOT NULL、topic VARCHAR(200) NULL、
     owner_id FK(users.id)、is_private BOOLEAN DEFAULT 0、
     password_hash VARCHAR(128) NULL、max_members INTEGER DEFAULT 200、
     is_archived BOOLEAN DEFAULT 0、created_at DATETIME
     索引：uk_rooms_name(name)（或 (owner_id, name) 唯一，视产品选择）
   表 room_members：
     id BIGINT PK、room_id FK、user_id FK、role VARCHAR(16) DEFAULT 'member'（owner/admin/member）、
     joined_at DATETIME、last_read_message_id BIGINT NULL、is_muted BOOLEAN DEFAULT 0、
     banned_at DATETIME NULL
     约束：UNIQUE(room_id, user_id)
     索引：idx_rm_user(user_id)、idx_rm_room(room_id)
   表 messages：
     id BIGINT PK（自增，天然作为游标）
     room_id FK(rooms.id) NOT NULL
     user_id FK(users.id) NULL（系统消息为 NULL）
     client_msg_id CHAR(36) NULL
     msg_type VARCHAR(16) DEFAULT 'text'（text / image / file / system）
     content TEXT NOT NULL（纯文本，最长 500 字符；image 类型存 URL）
     meta JSON NULL（图片宽高、文件大小等）
     is_recalled BOOLEAN DEFAULT 0
     recalled_at DATETIME NULL
     created_at DATETIME NOT NULL
     约束：UNIQUE(user_id, client_msg_id)（幂等去重，user_id 为 NULL 时不参与）
     索引：idx_msg_room_id(room_id, id DESC)、idx_msg_user_time(user_id, created_at)
   表 message_reads（已读位置，可选用于未读数）：
     id PK、room_id FK、user_id FK、last_read_message_id BIGINT、updated_at DATETIME、
     UNIQUE(room_id, user_id)
   表 session_events（连接审计，用于统计在线时长与排障）：
     id PK、user_id、room_id、connection_id CHAR(36)、event VARCHAR(16)
     （connect / disconnect / kick / timeout）、ip VARCHAR(45)、created_at DATETIME
     索引：idx_se_user_time(user_id, created_at)

2. 关键算法或流程
   WebSocket 连接建立：
     步骤 1：从查询参数取 token，用 python-jose 校验签名与 exp，失败则 close(1008)。
     步骤 2：查询 room_members 确认成员资格；非成员直接 close(1008, "not a member")。
     步骤 3：生成 connection_id（UUID4），调用 manager.join(room_id, user_id, ws)。
     步骤 4：把连接加入本进程的在线集合，并在 Redis 中 HSET presence:{room_id} user_id -> 连接数，
             同时 EXPIRE 90 秒（由心跳续期）。
     步骤 5：下发 hello：{"type":"hello","user_id":3,"room_id":7,"online":[...],
             "last_message_id":118}。
     步骤 6：向房间其他人广播 presence（joined=当前用户）。
     步骤 7：进入接收循环，每 30 秒由独立任务发送 ping。
   接收与广播：
     步骤 1：接收文本帧，解析 JSON；解析失败回 error code=42202 并计数。
     步骤 2：按 type 分发：text / typing / recall / history / pong。
     步骤 3：text 处理：校验长度与空白 → 限流检查（滑动窗口）→ 幂等检查 client_msg_id
             → 入库（run_in_threadpool 或异步会话）→ 组装事件 → manager.broadcast。
     步骤 4：广播实现：遍历房间内所有连接，对每个连接 put_nowait 到其 asyncio.Queue；
             每个连接有独立 sender 协程从队列取消息并 send_text。
             队列满（> 100）时丢弃并记录，避免慢客户端拖垮房间。
     步骤 5：多进程场景：广播前把事件 publish 到 Redis 频道 room:{room_id}；
             其它进程的订阅协程收到后对本进程连接本地广播；发布进程也订阅同一频道，
             通过 connection_id 去重，避免本进程重复发送。
   心跳与掉线检测：
     服务端每 30 秒发送 {"type":"ping","ts":...}；维护 last_pong_at。
     后台巡检任务每 10 秒扫描所有连接，若 now - last_pong_at > 45 秒则 close(1001) 并清理。
     客户端也可主动发 ping，服务端立即回 pong。
   在线状态维护：
     presence:{room_id} 使用 Redis Hash，字段为 user_id，值为该用户在本集群的连接数。
     连接建立 INCR，断开 DECR，值为 0 时 HDEL。
     在线列表 = HKEYS + 批量查 users 表补昵称（缓存 5 秒，避免每次查询）。
   历史消息分页（游标法）：
     SELECT * FROM messages WHERE room_id = :r AND id < :before_id
     ORDER BY id DESC LIMIT :limit+1；多取一条判断 has_more；
     返回时按 id 升序排列；next_before_id = 返回集合中最小的 id。
     禁止使用 OFFSET（大房间下性能会随页数线性下降）。
   断线重连补偿：
     客户端带 last_message_id；服务端查询 id > last_message_id 且 room_id = :r 的消息，
     最多 200 条；若超过 200 条则返回最近 200 条并标记 truncated=true 提示客户端做完整刷新。
   消息撤回：
     校验 msg.user_id == 当前用户 且 now - created_at <= 5 分钟；
     更新 is_recalled = 1、recalled_at、content 置为空字符串（保留行以便统计）；
     广播 {"type":"recall","id":123,"room_id":7,"user_id":3}。
   限流（滑动窗口）：每个用户维护一个 deque 记录最近 10 秒内消息时间戳；
     清理过期时间戳后若长度 >= 10 则拒绝。内存版即可满足单进程，多进程用 Redis ZSET 实现。
   幂等去重：写入时依赖 UNIQUE(user_id, client_msg_id)，捕获 IntegrityError 后
     查出已有记录并返回，不重复广播。

3. 接口设计（HTTP 前缀 /api/v1；WebSocket 端点 /ws/{room_id}）
   POST /api/v1/auth/register
     请求：{"username":"alice","password":"Str0ngPassw0rd","nickname":"小艾"}
     响应 201：{"code":0,"data":{"id":3,"username":"alice","nickname":"小艾"}}
     失败：409/40901（用户名已存在）、422/42201（口令强度不足）。
   POST /api/v1/auth/login
     请求：{"username":"alice","password":"Str0ngPassw0rd"}
     响应 200：{"code":0,"data":{"access_token":"eyJ...","token_type":"bearer","expires_in":7200}}
     失败：401/40102；连续 5 次失败锁定 15 分钟（423/42301）。
   GET /api/v1/rooms?page=1&page_size=20&keyword=python
     响应 200：房间列表，含 id、name、topic、is_private、member_count、online_count。
   POST /api/v1/rooms   需 Bearer
     请求：{"name":"后端讨论","topic":"FastAPI 实践","is_private":false,"password":null}
     响应 201：{"code":0,"data":{"id":7,"name":"后端讨论","owner_id":3,"member_count":1}}
     失败：409/40902（同名房间）、422/42203（房间名长度 2~64）。
   POST /api/v1/rooms/{room_id}/join   需 Bearer
     请求：{"password":"ab12"}（私密房间必填）
     响应 200：{"code":0,"data":{"room_id":7,"role":"member","joined":true}}
     失败：404/40401、401/40101（口令错误）、409/40903（已在房间）、403/40302（被封禁）。
   POST /api/v1/rooms/{room_id}/leave   需 Bearer
     响应 200：{"code":0,"data":{"left":true}}；房主退出前必须转让或解散，否则 409/40904。
   GET /api/v1/rooms/{room_id}/members   需 Bearer 且为成员
     响应 200：成员列表，含 user_id、username、role、joined_at、online（bool）。
   DELETE /api/v1/rooms/{room_id}/members/{user_id}   需房主或管理员
     响应 200：踢出成员并向其连接广播 kicked 后 close(1001)。
   DELETE /api/v1/rooms/{room_id}   需房主
     响应 200：解散房间，广播 system 事件后关闭全部连接。
   GET /api/v1/rooms/{room_id}/messages?limit=30&before_id=118   需 Bearer 且为成员
     响应 200：{"code":0,"data":{"items":[{"id":118,"user_id":3,"username":"小艾",
              "msg_type":"text","content":"大家好","created_at":"2024-05-01T09:12:00Z",
              "is_recalled":false}],"has_more":true,"next_before_id":118}}
     失败：404/40401、403/40303（非成员）。
   POST /api/v1/rooms/{room_id}/messages   需 Bearer 且为成员（HTTP 兜底发送）
     请求：{"client_msg_id":"uuid4","content":"通过 HTTP 发送"}
     响应 201：同 WebSocket 下行 text 事件；失败：422/42201、429/42901。
   POST /api/v1/messages/{message_id}/recall   需 Bearer 且为发送者
     响应 200：{"code":0,"data":{"id":123,"is_recalled":true}}
     失败：403/40301（非本人或超 5 分钟）、404/40405（消息不存在）。
   GET /api/v1/rooms/{room_id}/online   需 Bearer 且为成员
     响应 200：{"code":0,"data":{"count":2,"users":[{"user_id":3,"username":"小艾"}]}}
   WS /ws/{room_id}?token=<JWT>
     上行事件：{"type":"text","client_msg_id":"uuid","content":"hi"}
              {"type":"typing"}、{"type":"recall","id":123}、
              {"type":"history","before_id":118,"limit":30}、{"type":"ping"}
     下行事件：hello / presence / text / system / typing / recall / history / error / pong
     错误示例：{"type":"error","code":42901,"message":"发送过于频繁，请稍后再试"}
     关闭码：1000 正常、1001 服务端主动断开、1008 鉴权或成员资格失败、1011 服务端异常。
   GET /chat   公开
     行为：返回极简 HTML 调试页（原生 WebSocket + fetch），用于手工验证全部流程。

4. 鉴权方式与安全要求
   - 用户口令使用 bcrypt（rounds=12）哈希；房间口令同样 bcrypt 哈希，绝不存明文。
   - JWT：HS256，payload 含 sub、username、exp（2 小时）、iat、jti；
     JWT_SECRET_KEY 从环境变量读取，长度 >= 32，缺失时启动失败。
   - WebSocket 鉴权在握手时完成（查询参数 token），连接建立后不再重复校验；
     服务端在连接对象上记录 user_id，禁止在消息体中信任客户端自报的 user_id。
   - 所有房间操作都要校验成员资格与角色（房主/管理员/成员），禁止仅凭 room_id 操作。
   - 客户端内容按纯文本存储与转发，服务端不做 HTML 拼接；前端必须用 textContent 渲染。
   - 消息长度上限 500 字符（按 Unicode 字符计），图片消息只允许 http/https 的 URL。
   - 限流：消息 10 条/10 秒/人；typing 1 条/2 秒/人；建房 5 次/小时/人；
     连接建立 10 次/分钟/IP（防止连接耗尽）。
   - 封禁与踢出：被封禁用户在握手阶段即被拒绝（1008），无需建立连接。
   - 敏感信息防护：日志中不打印 token；消息内容在日志中只记录长度与前 20 字符摘要。

5. 错误处理与并发事务注意点
   - ConnectionManager 的所有结构只在事件循环内操作（async 方法），
     禁止从线程直接修改；如必须，用 asyncio.run_coroutine_threadsafe 调度到循环。
   - 广播必须"先复制成员快照再遍历"，避免遍历过程中有连接加入/退出导致 RuntimeError。
   - 每个连接一个发送队列 + 一个 sender 协程；send 操作加 try/except，
     捕获 WebSocketDisconnect 与 RuntimeError 后统一走清理流程。
   - 清理流程放在 finally 中，且必须幂等（重复清理不报错、不重复广播 presence）。
   - 消息入库失败只回 error 给发送者，不 raise 到外层导致连接断开。
   - 房间人数上限与 max_members 校验需在事务内完成（SELECT ... FOR UPDATE 或
     条件插入 + 计数校验），避免并发加入突破上限。
   - 多进程广播使用 Redis Pub/Sub：每个进程有唯一 instance_id，
     事件带 origin_instance，收到自己发布的事件直接忽略，防止重复投递。
   - presence 计数使用 Redis HINCRBY/HDECRBY 原子操作，避免多进程计数错乱。
   - 历史分页用 id 游标，消息表自增 id 与 created_at 顺序一致，
     若同一秒多条消息以 id 稳定排序，避免翻页重复或遗漏。

【五、运行方式与示例】

安装与启动：
  python -m venv .venv && .venv\Scripts\activate
  pip install -r requirements.txt
  set JWT_SECRET_KEY=please-change-this-32bytes-minimum
  set DATABASE_URL=sqlite:///./chat.db
  set REDIS_URL=redis://127.0.0.1:6379/1     # 单进程可留空，自动使用内存实现
  alembic upgrade head
  uvicorn app.main:app --reload --port 8400
  浏览器打开 http://127.0.0.1:8400/chat 进入调试页面。

界面与交互说明：
  调试页分三栏：左侧房间列表（含在线人数与"新建房间"按钮），
  中间消息区（顶部"加载更早消息"，底部输入框 + 发送按钮，右上角显示连接状态），
  右侧在线成员列表（实时刷新）。
  页面顶部提供登录框；登录成功后自动连接所选房间的 WebSocket。
  连接断开时页面顶部显示"已断线，正在重连"并每 3 秒重试，重连时带上 last_message_id。

示例 1（握手与首包）：
  连接：ws://127.0.0.1:8400/ws/7?token=eyJ...
  下行：{"type":"hello","user_id":3,"username":"小艾","room_id":7,
        "last_message_id":118,"online":[{"user_id":3,"username":"小艾"}]}
示例 2（发送与广播）：
  上行：{"type":"text","client_msg_id":"8f1c-...","content":"大家好"}
  下行（房间内所有人，含发送者）：
        {"type":"text","id":119,"room_id":7,"user_id":3,"username":"小艾",
         "content":"大家好","msg_type":"text","created_at":"2024-05-01T09:12:00Z"}
  同时其他人收到：{"type":"presence","room_id":7,...} 仅在有人进出时出现。
示例 3（历史翻页）：
  请求：GET /api/v1/rooms/7/messages?limit=30&before_id=118
  响应：HTTP 200
        {"code":0,"data":{"items":[{"id":117,"user_id":5,"username":"老李",
         "msg_type":"text","content":"收到","created_at":"2024-05-01T09:10:11Z",
         "is_recalled":false}],"has_more":true,"next_before_id":88}}
示例 4（发送过快被限流）：
  上行：连续第 11 条消息
  下行：{"type":"error","code":42901,"message":"发送过于频繁，请 10 秒后再试"}
示例 5（撤回消息）：
  上行：{"type":"recall","id":119}
  下行全员：{"type":"recall","id":119,"room_id":7,"user_id":3,"recalled_at":"..."}
示例 6（异常输入）：
  上行：{"type":"text","client_msg_id":"...","content":"<script>alert(1)</script>"}
  行为：内容作为纯文本入库并按文本广播（前端 textContent 渲染，不执行脚本）；
        若内容长度 501 字符则下行 {"type":"error","code":42201,"message":"消息长度不能超过 500 字符"}

【六、验收标准】

[ ] 两个客户端加入同一房间后，A 发送的消息在 1 秒内出现在 B 的界面上，且 A 自己也能看到回显。
[ ] 非房间成员使用有效 token 连接 /ws/{room_id} 被以 1008 关闭。
[ ] token 过期或篡改的连接被立即关闭，服务端不接收其任何消息。
[ ] 在线成员列表在成员进出后 1 秒内刷新，房间列表的 online_count 与之一致（延迟 <= 5 秒）。
[ ] 连续发送 11 条消息时第 11 条被拒并收到 code=42901 的 error 事件。
[ ] 发送 501 字符的消息被拒（code=42201），发送 500 字符的消息成功。
[ ] 相同 client_msg_id 重复发送两次，数据库只有一条记录且房间内只广播一次。
[ ] 5 分钟内撤回自己的消息成功且全员收到 recall 事件；6 分钟前或他人的消息撤回返回 403/40301。
[ ] 历史接口用 before_id 连续翻 5 页，页间无重复消息、无遗漏（相邻页 id 连续且严格递减）。
[ ] 断开一个客户端后其在线状态在 5 秒内被清理，其他人收到 presence 事件。
[ ] 客户端断线 30 秒后重连并带 last_message_id，能补齐断连期间的消息。
[ ] 模拟慢客户端（不读取 socket）不阻塞其他成员收消息，其队列超过 100 条后被丢弃并记录日志。
[ ] 房主踢出成员后该成员的连接被以 1001 关闭，且无法再次连接（被拉黑场景）。
[ ] 私密房间口令错误 5 次后该 IP 被锁 10 分钟，正确口令可正常加入。
[ ] 数据库写入失败时仅发送者收到 error，房间内其他连接保持正常。
[ ] 两个进程（uvicorn --workers 2）部署时跨进程广播生效，两个客户端仍能互通。
[ ] pytest + pytest-asyncio 用例覆盖收发、成员校验、限流、撤回、历史分页五类场景并全部通过。

【七、可选扩展】

1. 增加离线消息：用户重新登录后把离开期间的消息以未读列表形式推送（基于 message_reads）。
2. 增加文件与图片消息：结合上传接口，聊天中发送图片缩略图并点击查看原图。
3. 增加消息搜索：按房间 + 关键词检索历史消息（SQLite FTS5 或 PostgreSQL 全文索引）。
4. 增加 @提及 与未读计数红点，支持消息已读回执。
5. 用 Redis Stream 替代 Pub/Sub，获得消息堆积与断点续读能力。
6. 增加房间管理后台：成员禁言、关键词过滤、消息举报。
7. 增加消息加密（端到端或传输层 TLS + 服务端存储加密）。

【八、涉及知识点】

- WebSocket 协议：握手升级、帧收发、ping/pong 心跳与关闭码语义
- asyncio 并发：Task 生命周期、asyncio.Queue 生产者消费者、异步循环内的竞态防护
- 长连接管理：ConnectionManager 结构设计、慢客户端背压与丢弃策略
- 广播语义：房间隔离、跨进程 Redis Pub/Sub、去重与顺序保证
- 在线状态维护：Redis Hash 原子计数与过期续期
- 游标分页（keyset pagination）与自增 id 排序的稳定性
- 幂等设计：client_msg_id 去重与唯一约束
- 滑动窗口限流与多进程下的 Redis ZSET 实现
- 鉴权与授权在长连接场景中的差异（握手鉴权 + 服务端记录身份）
- 消息内容的 XSS 防护与纯文本渲染约定
================================================================================
