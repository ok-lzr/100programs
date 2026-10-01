================================================================================
项目编号：094                    难度等级：★★★★★（大型项目）
项目名称：即时通讯平台
所属分类：网络编程 / 长连接服务 / 桌面客户端
建议工时：3 ~ 4 周（约 110 ~ 170 小时）
运行环境：Python 3.10+    第三方依赖：FastAPI、uvicorn、websockets、SQLAlchemy、pydantic、redis、passlib、python-jose、Pillow、pytest、pytest-asyncio、websocket-client（客户端）
================================================================================

【一、项目背景与目标】

即时通讯的界面看起来只是“发一条消息、对面收到一条消息”，但服务端要做的事情远不止转
发：用户可能在弱网下反复重连，消息必须不丢；同一个人可能同时用两台设备登录，消息要在
多端之间同步与去重；大群里一条消息要扇出给几百个在线成员，还得控制带宽；对方离线时
消息要落库并在其上线后按序补发；用户发出的消息本地已显示，但因为网络中断其实没到服务
端，需要一个确认与重传机制。这些正是“长连接 + 可靠投递”要解决的核心问题。

本项目要实现一个自用的即时通讯平台：服务端提供 WebSocket 长连接接入、单聊与群聊、消息
持久化、离线消息、已读回执、在线状态与多端同步；客户端是一个 Tkinter 桌面程序，支持
登录、会话列表、聊天窗口、输入状态提示、断线自动重连与未读数。整套系统只使用 Python
实现（含客户端），不引入任何 IM 云服务，便于完整理解消息从输入框到对方屏幕的全过程。

可靠性目标必须量化：消息采用客户端生成的全局唯一 client_msg_id，服务端按会话维护单调
递增的 seq；客户端本地保存已确认的最大 seq，重连后按 seq 拉取缺口消息；服务端对每个
接收方维护送达确认，未确认的消息进入离线队列。任何一条已发出的消息，最终必须满足
“要么被对方看到，要么出现在离线队列并在对方上线后送达”，不允许静默丢失。

目标用户是：想学习长连接服务与协议设计的开发者、需要一个局域网内部聊天工具的小团队、
以及研究消息可靠性（ACK、重传、去重、顺序保证）的学习者。项目明确不追求音视频通话、
不追求端到端加密的生产级实现（仅做传输加密与存储加密的演示）、不做大群（>1000 人）
的极致优化，但要把 500 人以下的群聊做稳。

【二、功能需求清单】

本系统按四个子系统拆分：服务端（连接网关与消息服务）、客户端（桌面程序）、管理端（运维
控制台）、基础设施（存储、会话、配置与部署）。

1. 服务端子系统
   1.1 连接接入：WebSocket 端点 /ws?token=<JWT>；握手时校验令牌，失败返回 4001 关闭码；
       同一账号允许最多 5 个并发连接（多端），超出按最旧连接被踢下线（关闭码 4002）。
   1.2 连接注册表：内存维护 user_id → set[connection] 映射，进程内单机运行；连接建立时
       订阅该用户的 Redis 频道，保证多进程部署时也能定向推送。
   1.3 心跳与保活：服务端每 25 秒发送 ping 帧，60 秒未收到 pong 则判定连接失效并清理；
       客户端每 20 秒发送应用层心跳（{"type":"ping","ts":...}），服务端回 {"type":"pong"}。
   1.4 消息发送：客户端发送 send 帧，包含 client_msg_id、conversation_id（单聊为
       peer 用户 id，群聊为 group_id）、msg_type（text/image/file）、content、reply_to。
       服务端校验成员资格与内容长度（文本 ≤ 4000 字符），分配 seq 并持久化。
   1.5 会话 seq 生成：每个会话维护单调递增 seq（Redis INCR 或数据库序列），保证同一会话内
       所有消息有序；seq 一经分配不可回退，回滚事务时跳过该号（允许空洞）。
   1.6 投递与确认：服务端把消息推给在线接收方，等待客户端回 ack 帧（含 client_msg_id）；
       收到 ack 后标记该接收方送达；30 秒未收到 ack 则重试推送（最多 3 次），仍失败则写入
       离线队列。
   1.7 离线消息：接收方不在线时消息写入 offline_messages 表；用户上线后客户端发送 sync
       请求（携带各会话最后收到的 seq），服务端按会话返回缺失消息（单次最多 200 条，超过
       则分页并在响应中带 has_more）。
   1.8 多端同步：同一用户的其他在线端通过 Redis 频道收到该用户所有会话的消息副本（含自己
       发送的），并带 origin_device_id 便于客户端跳过回显。
   1.9 已读回执：客户端发送 read 帧（conversation_id + last_read_seq），服务端更新未读数并
       向对端推送 receipt 帧；群聊的已读只统计“已读人数”，不暴露具体名单（隐私考虑）。
   1.10 在线状态：用户上线/下线时向其联系人推送 presence 帧；状态变更做 3 秒去抖（防止
       频繁上下线造成风暴）；支持客户端查询批量在线状态接口。
   1.11 输入状态：客户端发送 typing 帧（会话 id + 状态），服务端转发给对端，5 秒未更新
       自动过期；群聊中 typing 仅转发不投递给离线用户、不落库。
   1.12 消息撤回：发送后 2 分钟内可撤回；撤回后消息内容替换为“对方撤回了一条消息”，
       通过 recall 帧广播给会话成员并落库为 msg_type=recall。
   1.13 历史消息：按会话与 seq 范围查询，默认返回最近 50 条，支持向上翻页；服务端只允许
       会话成员查询。
   1.14 会话与好友：好友申请、同意/拒绝、好友列表、删除好友；创建单聊会话时自动建立
       conversation 记录；群聊支持创建、拉人、踢人、退群、改群名、设置群主转让。
   1.15 文件与图片消息：客户端先把文件上传到 HTTP 上传接口（分片可选），返回 file_id 与
       缩略图地址，message 中只传 file_id 与元信息；服务端校验大小上限（20 MB）与类型
       白名单；图片自动生成 256px 缩略图。
   1.16 消息搜索：按关键字搜索本人在某会话内的文本消息（服务端返回匹配片段与 seq），
       最多返回 50 条。
   1.17 反垃圾与限流：单用户发送频率限制（20 条/10 秒），超限返回 error 帧并短暂禁言
       10 秒；连续发送完全相同内容 5 次以上判定为刷屏并拒绝发送。
   1.18 统一错误帧：{"type":"error","code":"...","message":"...","ref_client_msg_id":"..."}，
       错误码含 NOT_MEMBER、TOO_LONG、RATE_LIMITED、CONVERSATION_NOT_FOUND、
       TOKEN_EXPIRED、DEVICE_LIMIT。

2. 客户端子系统（Tkinter 桌面程序）
   2.1 登录窗口：服务器地址、用户名、密码、记住用户名（仅存用户名不存密码）、自动登录
       复选框（令牌存本地 keyring 或加密文件，不存明文）。
   2.2 主窗口布局：左侧会话列表（头像占位、名称、最后一条消息摘要、未读红点计数）、
       右上消息区（气泡式消息、时间分隔、对方头像、发送者名称）、右下输入区（多行文本、
       Enter 发送、Shift+Enter 换行、表情标记、图片按钮、文件按钮）。
   2.3 连接管理：登录后建立 WebSocket 连接，断线后按 1s、2s、4s、8s、最大 30s 退避重连，
       重连成功后自动执行 sync 拉取离线消息；界面顶部显示连接状态（已连接/重连中/已断开）。
   2.4 消息发送与本地显示：发送时先生成 client_msg_id（uuid4）并在界面显示“发送中”状态，
       收到服务端 ack（含 seq）后标记为“已发送”，超时 10 秒未确认显示重发按钮。
   2.5 消息状态显示：每条自己发出的消息展示状态图标（发送中/已发送/已送达/已读）。
   2.6 未读与提醒：未读会话在列表中置顶并显示计数；窗口不在前台时弹出系统托盘提示
       （实现方式：Tkinter 的 deiconify + bell，或调用系统通知命令，二者择一并在文档说明）。
   2.7 本地缓存：会话与最近 200 条消息写入本地 SQLite（路径为用户目录下的 .imclient），
       下次启动先渲染缓存再增量同步；缓存中的消息按 (conversation_id, seq) 去重。
   2.8 搜索与跳转：会话内关键字搜索，命中的消息在列表中高亮并滚动定位。
   2.9 群聊界面：显示群名与成员数，点击查看成员列表；群主可执行踢人与改群名操作。
   2.10 设置页：消息字体大小、是否显示已读回执、是否开启输入状态、通知开关、清空本地缓存。
   2.11 异常提示：网络不可用、令牌过期、被踢下线（如异地登录）均给出明确的中文提示，
       被踢下线时禁止自动重连并要求重新登录。
   2.12 图片与文件：图片在消息流内按宽度等比例缩放显示（Pillow 处理），点击可另存；
       文件消息显示文件名与大小，点击可下载到本地指定目录。

3. 管理端子系统（运维控制台，Web）
   3.1 概览：在线连接数、今日消息数、活跃用户数、平均消息投递时延、重连次数、离线消息
       积压量，每 5 秒刷新。
   3.2 连接列表：展示 user_id、设备 id、连接建立时间、最后心跳、IP、客户端版本；支持强制
       断开某连接（需填写原因，并推送给被断开用户一条系统提示）。
   3.3 消息审计（默认关闭）：开启后可按时间段与用户查询消息元数据（不含正文），用于排查
       投递故障；开启状态在控制台顶部显著提示，且所有查询写入 audit_log。
   3.4 用户管理：查看用户列表、禁用/启用账号、重置密码（生成一次性随机密码）；
       禁用账号时立即断开其所有连接。
   3.5 群组管理：查看群列表与成员数、解散群、转移群主、查看群操作日志。
   3.6 投递质量报表：按小时统计投递成功率、平均 ack 时延、重传次数、离线补发条数，
       导出 CSV。
   3.7 系统公告：向全体在线用户推送公告消息（系统会话），可设置过期时间。

4. 基础设施子系统
   4.1 存储：SQLite 开发环境、PostgreSQL 生产环境；消息表按月分区（PostgreSQL 使用分区
       表，SQLite 用 msg_YYYYMM 分表）；通过 SQLAlchemy 统一访问。
   4.2 会话与推送：Redis 用于在线状态缓存、会话 seq 生成（INCR）、跨进程消息广播
       （Pub/Sub）与限流计数；Redis 不可用时降级为单进程内存实现并在日志中告警。
   4.3 文件存储：上传文件保存在 storage/files/YYYY/MM/ 下，文件名使用 file_id（sha1 内容
       前 24 字节 + 随机后缀），缩略图存 storage/thumbs/；下载接口校验会话成员身份。
   4.4 配置管理：config.toml 定义 host、port、db_url、redis_url、jwt_secret（可由环境变量
       覆盖）、max_connections_per_user、msg_max_len、file_max_mb、offline_batch_size、
       recall_window_seconds。
   4.5 日志：app.log（服务端业务）、ws.log（连接与帧收发，仅记录帧类型与大小，不记录正文）、
       access.log（HTTP）、audit.log（管理操作）；日志按天滚动保留 30 天。
   4.6 部署：单机部署（1 个 uvicorn 进程）与多进程部署（N 个进程 + Redis Pub/Sub 广播）；
       Nginx 反向代理 WebSocket 的配置示例（含 Upgrade 头与超时设置）。
   4.7 数据保留策略：消息默认保留 24 个月，超期归档到压缩文件；离线消息在投递成功后
       立即删除；用户注销时删除其私聊消息正文（保留元数据用于统计）。

5. 模块清单（源码结构）
   5.1 server/main.py            FastAPI 应用、WebSocket 端点、生命周期。
   5.2 server/connection.py      连接注册表、心跳、连接上限与踢下线。
   5.3 server/protocol.py        帧模型（pydantic）：send/ack/read/typing/presence/recall/
                                 error/ping/pong/sync 的校验与序列化。
   5.4 server/message_service.py 发送、seq 分配、持久化、投递与重试。
   5.5 server/offline.py         离线队列写入、sync 补发与分页。
   5.6 server/conversation.py    会话与群组、成员校验、成员变更广播。
   5.7 server/presence.py        在线状态、Redis 频道订阅、去抖与广播。
   5.8 server/files.py           文件上传、校验、缩略图生成与下载鉴权。
   5.9 server/models/            user、conversation、member、message、receipt、
                                 offline_message、friend、device。
   5.10 server/api/              auth、users、friends、conversations、messages、files、admin。
   5.11 client/ws_client.py      连接、重连退避、帧收发与本地队列。
   5.12 client/ui/               login_window、main_window、chat_view、settings_window。
   5.13 client/store.py          本地 SQLite 缓存与去重。
   5.14 console/                 管理端页面与接口。
   5.15 tests/                   协议测试、可靠性测试、群聊扇出测试、客户端连接测试。

6. 接口清单（HTTP 与 WebSocket）
   6.1 POST /api/v1/auth/register              注册
   6.2 POST /api/v1/auth/login                 登录（返回 access/refresh 令牌与 user_id）
   6.3 POST /api/v1/auth/refresh               刷新令牌
   6.4 GET  /api/v1/users/me                   当前用户资料
   6.5 GET  /api/v1/friends                    好友列表（含在线状态）
   6.6 POST /api/v1/friends/requests           发起好友申请
   6.7 POST /api/v1/friends/requests/{id}/accept 同意好友申请
   6.8 GET  /api/v1/conversations              会话列表（含最后一条消息与未读数）
   6.9 POST /api/v1/conversations              创建单聊或群聊
   6.10 POST /api/v1/conversations/{id}/members 添加成员
   6.11 DELETE /api/v1/conversations/{id}/members/{uid}  移除成员
   6.12 GET  /api/v1/conversations/{id}/messages?before_seq=&limit=50  历史消息
   6.13 GET  /api/v1/conversations/{id}/search?kw=      会话内搜索
   6.14 POST /api/v1/files                     上传文件（multipart）
   6.15 GET  /api/v1/files/{file_id}           下载文件（校验成员身份）
   6.16 WS   /ws?token=                        WebSocket 长连接
   6.17 GET  /api/admin/overview               管理端概览
   6.18 POST /api/admin/connections/{id}/kick  强制断开连接

7. WebSocket 帧类型与数据模型概览
   7.1 客户端 → 服务端帧：auth（可选二次认证）、send、ack、read、typing、recall、sync、
       ping。
   7.2 服务端 → 客户端帧：ack（服务端确认，含 seq）、message（新消息）、receipt（已读）、
       presence（在线状态）、typing、recall、sync_result、error、pong、kick。
   7.3 关键帧示例：send = {"type":"send","client_msg_id":"c-8f21","conversation_id":"g-1024",
       "msg_type":"text","content":"部署脚本我改好了","reply_to":null,"ts":1736900000123}
   7.4 users(id TEXT PK, username UNIQUE, password_hash, nickname, avatar_file_id,
       status, created_at, disabled INT)
   7.5 devices(id TEXT PK, user_id FK, platform, client_version, last_login_at,
       last_ip TEXT)
   7.6 friends(id PK, user_id, friend_id, state, remark, created_at)
      唯一键 (user_id, friend_id)
   7.7 conversations(id TEXT PK, type TEXT CHECK(type in ('single','group')), title,
       owner_id, last_seq INT, created_at, updated_at)
   7.8 members(id PK, conversation_id FK, user_id FK, role TEXT, joined_at,
       last_read_seq INT, muted INT)  唯一键 (conversation_id, user_id)
   7.9 messages(id PK, conversation_id FK, seq INT, sender_id, client_msg_id TEXT,
       msg_type, content TEXT, file_id TEXT, reply_to INT, state, created_at)
      唯一键 (conversation_id, seq) 与 (conversation_id, client_msg_id) 双唯一约束保证
       消息不重不乱
   7.10 receipts(id PK, message_id FK, conversation_id, user_id, state TEXT,
       updated_at)  唯一键 (message_id, user_id)；state 取值 delivered / read
   7.11 offline_messages(id PK, user_id FK, conversation_id, message_id, seq,
       created_at)  唯一键 (user_id, message_id)
   7.12 索引：messages 建 (conversation_id, seq desc)、idx_sender(sender_id, created_at)；
       offline_messages 建 (user_id, conversation_id, seq)；receipts 建 (user_id, state)。

【三、里程碑拆解（建议 4 ~ 6 个阶段）】

阶段一：协议与单机消息收发（约 18 小时）
  产出：帧模型与校验、WebSocket 端点、连接注册表、登录鉴权、内存版消息转发、简易 CLI
       测试客户端。
  验收：两个终端用户可互发文本消息，错误帧格式统一，非法帧被拒绝且不断开连接。

阶段二：持久化、seq 与离线消息（约 25 小时）
  产出：数据库模型与迁移、会话 seq 生成、消息落库、离线队列、sync 补发与分页、历史消息
       接口。
  验收：接收方离线时消息入库；上线后 sync 能按序取回全部缺失消息；重复 sync 不重复返回。

阶段三：可靠投递与多端同步（约 24 小时）
  产出：ack 确认与重传、送达/已读回执、客户端重连退避与本地缓存、Redis Pub/Sub 多进程
       广播、设备上限与踢下线。
  验收：模拟网络中断后重连，消息不丢不重（对比双方数据库中的 client_msg_id 集合完全一致）。

阶段四：群聊与好友体系（约 22 小时）
  产出：群创建与成员管理、群消息扇出（在线全推、离线落队列）、未读数统计、好友申请流、
       在线状态与输入状态、撤回。
  验收：500 人群发消息，在线成员 1 秒内收到，离线成员上线后补齐；撤回在两端同步生效。

阶段五：桌面客户端完善（约 25 小时）
  产出：会话列表、聊天气泡、发送状态、未读提醒、本地缓存、搜索定位、图片与文件消息、
       设置页、异常提示。
  验收：客户端在断网重连后自动补历史；发送中/已送达/已读状态显示正确；图片缩略图显示。

阶段六：管理端、测试与部署（约 20 小时）
  产出：管理控制台、投递质量报表、限流与反刷屏、覆盖率报告、并发连接压测脚本、部署
       文档与 Nginx WebSocket 配置示例、隐私与数据保留说明。
  验收：单机 2000 并发连接下消息投递成功率 ≥ 99.9%，P95 端到端时延 ≤ 300 ms（局域网）。

【四、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；服务端使用 asyncio 与 FastAPI；客户端仅使用标准库
   Tkinter 与 websocket-client，禁止使用 PyQt 等重型 GUI 依赖。
2. 允许使用的库：标准库（asyncio、json、sqlite3、uuid、threading、queue、tkinter、hashlib、
   datetime、logging）；第三方限 FastAPI、uvicorn、websockets、SQLAlchemy、alembic、
   pydantic、redis、passlib、python-jose、Pillow、websocket-client、httpx、pytest、
   pytest-asyncio。禁止引入任何第三方 IM SDK 或云推送服务。
3. 禁止事项：禁止在客户端本地明文保存密码；禁止把消息正文写入日志文件；禁止使用
   pickle 序列化网络帧（存在反序列化风险，统一使用 JSON）；禁止在未校验会话成员身份时
   返回消息内容；禁止用轮询 HTTP 冒充长连接（必须真实使用 WebSocket）。
4. 代码组织：服务端分层 ws（帧接收与校验）→ service（消息与会话业务）→ repository（数据
   访问）；协议的帧结构集中定义在 server/protocol.py，客户端与服务端共享字段含义说明；
   客户端 UI 与网络层分离（UI 不直接收发帧，通过事件队列交互）。
5. 可靠性要求：消息持久化必须先落库再推送（保证宕机不丢）；推送失败必须进入离线队列；
   ack 机制必须能容忍重复帧（幂等）；seq 分配必须原子；任何重试都不得产生重复消息
   （由 (conversation_id, client_msg_id) 唯一约束兜底）。
6. 编码规范：PEP 8；所有帧处理函数必须有类型注解与 docstring；服务端不得阻塞事件循环
   （数据库与文件操作使用线程池或异步驱动）；客户端耗时操作（文件上传）必须在子线程中
   执行并回调主线程更新 UI（Tkinter 非线程安全）。
7. 测试要求：覆盖率 ≥ 70%；必须包含：协议校验测试（合法/非法帧各 20 例）、seq 单调性测试、
   ack 重传与幂等测试、离线补发完整性测试（构造 300 条离线消息分页校验）、群聊扇出测试、
   客户端重连测试、并发连接压测脚本。
8. 性能要求：单机 4 核 8 GB，2000 并发在线连接；单聊文本消息端到端 P95 ≤ 200 ms（局域网）；
   500 人群发一条消息的扇出完成时间 ≤ 1 秒；单机消息写入 ≥ 2000 条/秒（批量提交）。
9. 安全要求：传输层要求 TLS（部署文档给出 wss 配置），本地开发允许 ws；JWT 有效期短
   （access 2 小时）并支持刷新；文件下载必须校验会话成员身份，防止通过 file_id 猜测下载
   他人文件；上传文件按扩展名与 MIME 双白名单校验，重命名后存储，禁止可执行后缀。
10. 隐私与合规：消息内容属于用户隐私，默认不提供任何后台查看正文的能力；管理端的消息
    审计默认关闭，开启需二次确认并在控制台显著提示，所有查询留痕；提供聊天记录导出（本人）
    与账号注销（删除消息正文）功能；不得将用户消息或联系人数据用于任何分析或第三方用途；
    数据保留期与删除策略必须在客户端与文档中明确告知用户。

【五、设计要点】

1. 数据结构：
   1.1 Frame = {"type": str, "ts": int, ...}，所有帧必须带 type 与 ts；服务端对未知 type
       返回 UNSUPPORTED_TYPE 错误帧而不关闭连接。
   1.2 MessageRef = (conversation_id, seq)，作为客户端去重与排序的唯一依据。
   1.3 连接对象 Connection(user_id, device_id, ws, last_pong_at, subscribed_channels)。
   1.4 投递任务 DeliveryTask(message_id, conversation_id, target_user_id, attempts,
       next_retry_at)。
2. 关键算法与流程：
   2.1 发送链路：客户端生成 client_msg_id → 服务端校验成员与内容 → 幂等检查（同
       client_msg_id 已存在时直接返回上一次的 seq）→ 分配 seq → 事务内写 messages →
       推送给在线接收方（含自己其他端）→ 离线接收方写 offline_messages → 回 ack 给发送方。
   2.2 重传与离线：投递任务表驱动重试；未收到 ack 的任务按 5s/15s/45s 重试，超限后
       写离线队列并标记 failure_reason=NO_ACK；接收方上线后 sync 优先返回离线队列内容。
   2.3 sync 算法：客户端提交 {conversation_id: last_seq} 映射 → 服务端对每个会话查询
       seq > last_seq 的消息 → 合并离线队列 → 按会话分别限流返回（每会话最多 200 条）→
       响应含 has_more 与各会话最新 seq，便于客户端继续拉取。
   2.4 群聊扇出：读取会话成员列表 → 按在线/离线分组 → 在线成员并行推送（asyncio.gather
       带并发上限 50，避免瞬时连接风暴）→ 离线成员批量写 offline_messages（单条 SQL 批量
       插入）→ 更新 last_seq。
   2.5 未读数计算：未读数 = 会话最新 seq 区间内不属于自己的消息数 - 已读数；为性能考虑，
       服务端维护 members.unread_count，在消息落库时对离线成员自增，在 read 帧到达时清零。
   2.6 撤回：校验发送者身份与时间窗口 → 更新 messages.state=recalled、content 清空 →
       广播 recall 帧 → 客户端用系统提示替换气泡内容。
   2.7 重连流程：客户端连接 → 鉴权 → 发送 sync → 收到 sync_result 后按 seq 补齐 → 更新
       本地最大 seq → 恢复正常收发。
   2.8 幂等保障点清单：发送（client_msg_id 唯一约束）、ack（重复 ack 只更新一次）、
       sync（只读，天然幂等）、撤回（重复撤回返回相同结果）、离线投递（唯一约束防重）。
3. 数据库主要表结构与约束：见功能清单第 7 节；补充：
   3.1 messages 表按 (conversation_id, seq) 唯一索引，seq 空洞允许存在（事务回滚导致）。
   3.2 大表按月分区或分表，查询必须带 conversation_id 以避免全表扫描。
   3.3 offline_messages 在成功投递并收到 ack 后立即删除，避免表膨胀；删除操作幂等。
   3.4 receipts 表只在状态变化时写入（delivered → read），避免每条消息多行冗余。
4. 帧协议设计要点：
   4.1 所有上行帧必须带 seq=0 以外的可选字段校验：未知字段忽略而非报错（向后兼容）。
   4.2 服务端下行 message 帧包含：conversation_id、seq、sender_id、msg_type、content、
       file_meta、reply_to、ts、origin_device_id。
   4.3 错误帧必须携带 ref_client_msg_id（若可关联），便于客户端把失败提示挂到具体气泡。
   4.4 协议版本号放在握手 URL 参数（v=1），服务端对不支持的版本返回 4003 关闭码。

【六、运行方式与示例】

1. 安装与初始化
   python -m venv .venv && .venv\Scripts\activate
   pip install fastapi uvicorn websockets sqlalchemy alembic pydantic redis passlib
   pip install python-jose[cryptography] pillow websocket-client httpx pytest pytest-asyncio
   copy .env.example .env      （填写 JWT_SECRET、DB_URL、REDIS_URL）
   alembic upgrade head
2. 启动
   uvicorn server.main:app --host 0.0.0.0 --port 8080
   python -m client.main --server ws://127.0.0.1:8080/ws --user alice
   python -m client.main --server ws://127.0.0.1:8080/ws --user bob
3. 服务端调试客户端（命令行，便于自动化测试）
   python -m tools.wscli --token <JWT> --send "g-1024:你好"
4. 示例一（登录与握手）
   请求：POST /api/v1/auth/login {"username": "alice", "password": "******"}
   响应：200 {"user_id": "u-1001", "access_token": "eyJ...", "refresh_token": "eyJ...",
         "expires_in": 7200}
   连接：ws://127.0.0.1:8080/ws?token=eyJ...&v=1&device_id=d-a1
   服务端首帧：{"type":"ready","user_id":"u-1001","server_time":1736900000000,
              "max_frame_bytes":65536}
5. 示例二（发送 → 确认 → 送达）
   客户端发送：
   {"type":"send","client_msg_id":"c-8f21","conversation_id":"c-u1001-u1002",
    "msg_type":"text","content":"今天的会议改到三点","ts":1736900000123}
   服务端回 ack：
   {"type":"ack","client_msg_id":"c-8f21","conversation_id":"c-u1001-u1002","seq":87,
    "ts":1736900000150}
   对端在线时收到 message 帧；对端回 ack 后发送方收到：
   {"type":"receipt","conversation_id":"c-u1001-u1002","seq":87,"state":"delivered",
    "user_id":"u-1002"}
6. 示例三（离线后补发）
   场景：bob 离线期间 alice 发送 3 条消息
   bob 上线后发送：{"type":"sync","cursors":{"c-u1001-u1002":84},"ts":...}
   服务端回：
   {"type":"sync_result","items":{"c-u1001-u1002":[
     {"seq":85,"sender_id":"u-1001","msg_type":"text","content":"在吗","ts":...},
     {"seq":86,"sender_id":"u-1001","msg_type":"text","content":"文档我发你邮箱了","ts":...},
     {"seq":87,"sender_id":"u-1001","msg_type":"text","content":"今天的会议改到三点","ts":...}
   ]},"has_more":false,"latest_seq":{"c-u1001-u1002":87}}
7. 示例四（重复发送的幂等结果）
   客户端因超时重发同一个 client_msg_id=c-8f21
   服务端回：{"type":"ack","client_msg_id":"c-8f21","seq":87,"duplicated":true}
   数据库 messages 中该会话仍只有一条 seq=87 的记录。
8. 示例五（异常与限流）
   场景 A：向非成员群发消息
   响应：{"type":"error","code":"NOT_MEMBER","message":"你不是该会话成员",
         "ref_client_msg_id":"c-9a01"}
   场景 B：10 秒内发送第 21 条消息
   响应：{"type":"error","code":"RATE_LIMITED","message":"发送过于频繁，请 10 秒后重试",
         "retry_after_ms":4200}

【七、验收标准】

[ ] 1. 两个客户端可完成注册、登录、互加好友、单聊文本与图片消息的完整流程。
[ ] 2. 接收方离线时发送的 50 条消息，在其上线后全部按 seq 顺序补发，且无重复。
[ ] 3. 断网 30 秒后恢复，客户端自动重连并补齐缺失消息；双方 messages 表的 client_msg_id
      集合完全一致（无丢失、无重复）。
[ ] 4. 同一 client_msg_id 重复发送 5 次，数据库只有一条记录，seq 一致。
[ ] 5. 同一账号登录 6 个客户端时第 6 个被拒绝或最旧连接被踢下线，被踢端收到明确提示且
      不再自动重连（除非重新登录）。
[ ] 6. 500 人群聊发送一条消息，所有在线成员在 1 秒内收到，离线成员上线后补齐。
[ ] 7. 已读回执正确：bob 读取后 alice 的消息状态变为已读；群聊只显示已读人数。
[ ] 8. 2 分钟内撤回成功且双方同步替换为提示文本；超过 2 分钟撤回返回
      RECALL_EXPIRED 错误。
[ ] 9. 单用户 10 秒内发送超过 20 条消息被限流，返回 RATE_LIMITED 与重试时间。
[ ] 10. 非会话成员查询历史消息返回 403/NOT_MEMBER，无法通过构造请求读取他人聊天记录。
[ ] 11. 上传超过 20 MB 的文件被拒绝；上传 .exe 等非白名单类型被拒绝；通过 file_id 猜测
      下载他人文件返回 403。
[ ] 12. 日志文件中 grep 不到任何消息正文；数据库中密码字段为哈希且非明文。
[ ] 13. 2000 并发连接压测下，消息投递成功率 ≥ 99.9%，端到端 P95 ≤ 300 ms。
[ ] 14. 客户端界面在 1366×768 与 1920×1080 分辨率下布局正常，长消息自动换行，图片按比例
      缩放显示。
[ ] 15. pytest 覆盖率 ≥ 70%，协议、可靠性、群聊扇出三类专项测试全部通过；管理端审计
      默认关闭且开启后所有查询有留痕。

【八、可选扩展】

1. 端到端加密：使用 X25519 密钥交换与 AES-GCM 会话密钥，服务端只转发密文（需说明密钥
   管理与多端同步的难度）。
2. 消息漫游与多端已读同步：把已读状态提升为用户的全局状态，实现“一处已读、处处已读”。
3. 引入 MQTT 或自研二进制协议对比帧大小与解析开销，量化 JSON 与二进制协议的差异。
4. 支持消息编辑、引用回复线程与表情回应（reaction）。
5. 增加语音消息（录音 + 波形展示 + 时长）与视频消息缩略图。
6. 多进程部署与 Redis Stream 替代 Pub/Sub，实现断线期间的广播补投。
7. 增加灰度与限流治理：按用户等级设置不同发送配额与文件大小上限。

【九、涉及知识点】

- 网络编程：WebSocket 握手与帧协议、心跳保活、断线重连与指数退避、TLS/wss 配置
- 可靠性设计：至少一次投递、ACK 确认、重传与幂等、消息去重与顺序保证（seq）
- 并发模型：asyncio 事件循环、协程并发限流、线程池执行阻塞 IO、Tkinter 主线程安全
- 数据建模：会话/成员/消息/回执多表关系、唯一约束兜底、按月分区与索引优化
- 分布式协作：Redis Pub/Sub 跨进程广播、状态缓存、跨进程踢下线与在线状态维护
- 客户端工程：GUI 布局与事件绑定、本地 SQLite 缓存、图片缩放、网络层与 UI 解耦
- 安全与隐私：JWT 鉴权、密码哈希、成员鉴权防越权、消息隐私与审计合规
- 测试与压测：pytest-asyncio、协议边界测试、可靠性对比测试、并发连接压测方法
================================================================================
