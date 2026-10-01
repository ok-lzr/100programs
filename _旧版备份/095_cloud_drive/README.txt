================================================================================
项目编号：095                    难度等级：★★★★★（大型项目）
项目名称：个人云盘系统
所属分类：Web 应用 / 文件存储 / 云服务
建议工时：3 ~ 4 周（约 110 ~ 160 小时）
运行环境：Python 3.10+    第三方依赖：FastAPI、uvicorn、SQLAlchemy、alembic、pydantic、redis、Pillow、passlib、python-jose、pytest、httpx、python-multipart
================================================================================

【一、项目背景与目标】

把文件放到网盘，看起来只是“上传、下载”两个动作，实际使用一年后就会碰到一堆具体问题：
一个 4 GB 的视频传了一半断网，只能从头再来；同一个文件在多台设备上重复上传，浪费带宽
和空间；几千张照片上传后想找“上个月拍的那张合同照片”只能一张张翻；把文件分享给朋友
后无法收回权限；误删文件要么立刻消失，要么占着空间又不敢清。这些问题的根源是：文件存
储缺少分片与校验、缺少内容寻址与去重、缺少元数据与缩略图、缺少细粒度的权限模型、缺少
可恢复的删除语义。

本项目的目标是实现一个单用户（可扩展为多用户）的个人云盘：支持分片上传、断点续传、
秒传（内容哈希命中即复用）、目录树管理、缩略图与预览、分享链接与权限控制、回收站与
彻底删除、存储配额统计与重复文件清理建议。系统要在单机部署下把大文件传输的可靠性做
扎实，并给出可验证的秒传与去重收益数据。

技术重点在四条链路：一是上传链路的幂等与断点恢复（分片编号、分片哈希、合并校验）；
二是存储链路的内容寻址（sha256 寻址 + 引用计数，相同内容只存一份）；三是访问链路的
权限校验（所有者、分享令牌、过期与下载次数限制）；四是删除链路的软删除与延迟清理
（回收站保留 30 天，彻底删除时按引用计数决定是否真正删物理文件）。

目标用户是：想自建私有云盘的开发者、需要理解大文件传输与内容寻址存储的技术学习者、
以及把本系统当作对象存储前置练习的工程师。项目明确不做：不做客户端同步盘（只做 Web 与
HTTP API）、不做跨机房复制、不做视频在线转码（缩略图只处理图片）、不做公开注册（默认
单管理员账号，可配置多用户）。

【二、功能需求清单】

本系统按四个子系统拆分：用户端（Web 界面）、服务端（上传下载与文件管理 API）、管理端
（运维与配额）、基础设施（存储、缓存、任务与部署）。

1. 用户端子系统（Web 界面）
   1.1 登录页：账号密码登录（argon2 哈希校验），支持“记住我 7 天”（refresh 令牌放在
       HttpOnly Cookie）；连续失败 5 次锁定 10 分钟。
   1.2 文件浏览：面包屑导航 + 列表/网格两种视图切换；列表视图展示名称、大小、类型、
       修改时间、操作按钮；网格视图展示缩略图（图片与视频首帧）。
   1.3 目录操作：新建文件夹、重命名、移动到指定目录（树形选择器）、复制、删除（进回收站）。
       重名校验：同目录下同名文件返回 409 并提示自动重命名建议（如 report(1).pdf）。
   1.4 上传：支持点击选择与拖拽上传；大文件自动切分（默认 4 MB 一片，可在设置中调为
       1/4/8 MB）；显示总进度、当前分片、实时速度、剩余时间。
   1.5 断点续传：上传中断后重新选择同一文件，服务端按 file_key（sha256 + 大小）返回已
       收到的分片编号列表，客户端只补传缺失分片；进度条从断点继续。
   1.6 秒传提示：上传前先请求 /api/v1/files/precheck 计算是否已存在相同内容；命中则直接
       在用户空间建立引用并提示“已秒传”，不传任何分片。
   1.7 下载与打包：单文件下载支持 Range 断点续传与浏览器直下；多选文件可打包为 ZIP 下载
       （打包任务在后台执行，提供进度与完成后下载链接）。
   1.8 图片预览：点击图片打开预览浮层，支持上一张/下一张、缩放、旋转、下载原图；预览
       使用 1280px 的中间尺寸以节省带宽。
   1.9 分享：生成分享链接（/s/{token}），可设置有效期（1 天/7 天/30 天/永久）与提取码
       （4 位，可留空）、下载次数上限；分享页支持预览与下载，超过限制返回明确提示。
   1.10 回收站：展示已删除文件与剩余保留天数（默认 30 天）；支持还原（回到原目录，若原
       目录不存在则回到根目录）与彻底删除（二次确认，输入文件名确认）。
   1.11 搜索：按文件名关键字、类型（图片/文档/视频/音频/压缩包/其他）、时间范围、大小
       区间检索；支持仅搜索当前目录或全部目录；结果高亮关键字。
   1.12 个人空间：展示已用空间/配额（进度条）、文件数量分类统计（按类型与大小 Top 10）、
       重复文件清理建议（相同内容多份引用的列表，可一键只保留最新一份）。
   1.13 上传记录页：展示近期上传任务状态（成功/失败/已取消），失败任务可一键重试。
   1.14 异常提示：空间不足、文件类型被禁、单个文件超过上限（默认 5 GB）、分片编号非法、
       分享过期等均给出具体的错误文案与建议动作。

2. 服务端子系统（API 与存储）
   2.1 认证与授权：JWT（access 2 小时、refresh 7 天）；所有文件接口校验资源所有权；
       分享访问走独立令牌校验，不要求登录。
   2.2 虚拟文件系统：数据库维护 nodes 表（文件与目录统一建模），parent_id 组织树结构；
       物理文件与逻辑节点分离，多节点可指向同一 physical_file（引用计数）。
   2.3 预检与秒传：POST /api/v1/files/precheck 接收 {name, size, sha256}，返回
       {exists: true, physical_id, seconds_upload: true} 或 {exists: false, upload_id}。
       sha256 由客户端分片并行计算（Web 端使用 Web Crypto 或分片上传后由服务端校验）。
   2.4 分片上传：POST /api/v1/uploads 创建上传会话（返回 upload_id 与分片大小）；
       PUT /api/v1/uploads/{id}/chunks/{index} 上传分片（服务端对每片计算 sha256 并比对
       客户端声明值）；POST /api/v1/uploads/{id}/complete 触发合并与整体校验。
   2.5 上传会话管理：上传会话记录在 uploads 与 upload_chunks 表，支持查询已完成分片、
       取消上传（清理临时分片）、过期清理（24 小时未完成自动清理并释放临时空间）。
   2.6 合并与校验：按分片序号顺序写入最终文件（流式合并，避免全量载入内存），合并后计算
       整体 sha256 与客户端声明值比对；不一致则删除临时文件并返回 CHECKSUM_MISMATCH。
   2.7 内容寻址存储：物理文件路径为 storage/objects/{sha256前2位}/{sha256第3-4位}/{sha256}；
       写入采用“先写临时文件 + fsync + os.replace 原子改名”；相同 sha256 只存一份，
       physical_files 表维护 ref_count。
   2.8 缩略图生成：图片用 Pillow 生成 256px（网格）与 1280px（预览）两级；EXIF 方向自动
       纠正；HEIC 等不支持的格式记录失败但不阻塞上传；缩略图同样按 sha256 存储并去重。
   2.9 下载与 Range：GET /api/v1/files/{id}/download 支持 Range 请求（206），正确返回
       Content-Range、Accept-Ranges、ETag（用 sha256 前 16 位）与 Last-Modified；支持
       HEAD 探测文件大小。
   2.10 打包下载：创建 zip 任务 → 后台线程流式写入 ZIP（使用 zipfile 的 ZIP_STORED 或
       ZIP_DEFLATED，按内容类型选择）→ 进度写入任务表 → 完成后返回一次性下载链接。
   2.11 分享服务：创建分享记录（token 用 secrets.token_urlsafe(16)）、可选提取码（哈希
       存储）、有效期与下载上限；访问分享时校验过期与次数，校验成功后签发短期访问令牌。
   2.12 回收站服务：删除文件只设置 deleted_at（软删除），不立即减少物理引用；还原清空
       deleted_at 并校验原目录；彻底删除按引用计数递减，归零时删除物理文件与缩略图。
   2.13 配额与统计：用户配额（默认 50 GB，可配置），上传前校验 已用 + 新文件大小 ≤ 配额；
       统计接口返回按类型/时间维度的空间占用。
   2.14 重复文件检测：按 sha256 分组找出同一用户下内容相同但多个节点的文件，输出可释放
       空间估算，供用户决定是否清理。
   2.15 统一错误模型：{"code": "...", "message": "...", "detail": {...}}；错误码含
       QUOTA_EXCEEDED、CHUNK_MISMATCH、CHECKSUM_MISMATCH、NAME_CONFLICT、
       SHARE_EXPIRED、SHARE_LIMIT_REACHED、NOT_OWNER、UPLOAD_NOT_FOUND。

3. 管理端子系统
   3.1 存储总览：物理对象数、逻辑节点数、去重节省空间、回收站占用、上传临时空间占用、
       各类文件占比，数据每 10 秒刷新。
   3.2 用户与配额管理：用户列表、调整配额、禁用账号、查看用户空间构成。
   3.3 上传任务监控：查看进行中上传会话（用户、文件名、大小、已完成分片、最后活动时间），
       支持强制取消并清理临时文件。
   3.4 分享管理：列出全部有效分享（创建者、目标、过期时间、下载次数/上限），支持提前
       失效；统计被高频访问的分享。
   3.5 物理对象校验：后台任务抽样校验物理对象哈希（每月全量、每日增量），发现损坏对象
       记录到 corrupt_objects 并在界面告警。
   3.6 清理任务：过期上传会话清理、回收站超期清理、ZIP 临时包清理、孤立物理对象（引用
       计数为 0 且无节点引用）清理；所有清理任务记录执行日志与释放空间。
   3.7 操作审计：登录、删除、分享创建、配额调整、物理删除等敏感操作写入 audit_log，
       保留 180 天。

4. 基础设施子系统
   4.1 存储分层：对象目录用两级哈希前缀分散；临时分片存 storage/tmp/{upload_id}/；
       缩略图存 storage/thumbs/{sha256前2位}/；ZIP 临时包存 storage/packages/ 并在 24 小时
       后清理。
   4.2 数据库：SQLite 开发、PostgreSQL 生产；nodes 表自引用外键 + 物化路径字段（path）
       便于按前缀查询；所有时间字段使用 UTC 存储并在展示层转换。
   4.3 缓存：Redis 缓存分享令牌校验结果（60 秒）、用户配额使用量（写时更新 + 定时校准）、
       目录列表首页（30 秒）；缓存失效策略为写操作主动删除。
   4.4 后台任务：APScheduler 管理上传会话过期清理（每 10 分钟）、回收站清理（每天 03:00）、
       孤立对象扫描（每周日 04:00）、配额校准（每小时）、对象完整性抽样（每天 05:00）。
   4.5 配置管理：config.toml 定义 storage_root、quota_bytes、chunk_size、max_file_bytes、
       trash_retention_days、share_default_days、thumbnail_sizes、allowed_types、
       blocked_extensions；敏感项由环境变量覆盖。
   4.6 日志：app.log、upload.log（记录 upload_id、分片、耗时、大小）、access.log、audit.log；
       日志不得记录文件内容，只记录元数据与哈希。
   4.7 部署：支持本机目录与挂载盘；提供 Dockerfile 与 docker-compose（挂载 volume）；
       支持 Nginx 反向代理大文件上传的 client_max_body_size 与超时配置示例。
   4.8 备份策略：数据库每日备份，物理对象按增量（rsync 或 restic）备份；文档提供恢复
       演练步骤（含只恢复数据库与物理对象的顺序说明）。

5. 模块清单（源码结构）
   5.1 app/main.py            应用装配、路由注册、静态资源与中间件。
   5.2 app/config.py          Pydantic Settings 与配置校验（启动时校验 storage_root 可写）。
   5.3 app/db.py              引擎与 Session 管理、事务工具。
   5.4 app/auth.py            登录、令牌签发刷新、密码哈希与登录锁定。
   5.5 app/models/            user、node、physical_file、upload、upload_chunk、share、
                              trash_entry、zip_task、audit_log。
   5.6 app/services/storage.py 内容寻址写入、读取、引用计数与物理删除。
   5.7 app/services/upload.py 预检、分片接收、合并、整体校验与断点续传查询。
   5.8 app/services/vfs.py    目录树操作、移动复制、重名处理、路径维护。
   5.9 app/services/thumb.py  Pillow 缩略图生成、EXIF 纠正、失败降级。
   5.10 app/services/share.py 分享创建、令牌校验、提取码与次数限制。
   5.11 app/services/trash.py 软删除、还原、彻底删除与引用计数递减。
   5.12 app/services/package.py ZIP 打包任务与进度。
   5.13 app/api/              auth、files、uploads、shares、trash、search、admin 路由。
   5.14 app/tasks/            定时清理与校验任务。
   5.15 web/                  前端页面（原生 JS + fetch，含分片上传与进度实现）。
   5.16 tests/                单元、接口、上传中断恢复、秒传、Range、权限与清理测试。

6. 接口清单（HTTP，节选核心）
   6.1 POST /api/v1/auth/login                登录
   6.2 POST /api/v1/auth/refresh              刷新令牌
   6.3 GET  /api/v1/nodes?parent_id=&page=    列目录
   6.4 POST /api/v1/nodes/folder              新建文件夹 {parent_id, name}
   6.5 PATCH /api/v1/nodes/{id}               重命名/移动 {name, parent_id}
   6.6 DELETE /api/v1/nodes/{id}              移入回收站
   6.7 GET  /api/v1/nodes/{id}/download       下载（支持 Range）
   6.8 HEAD /api/v1/nodes/{id}/download       探测大小与 ETag
   6.9 POST /api/v1/files/precheck            秒传预检
   6.10 POST /api/v1/uploads                  创建上传会话
   6.11 GET  /api/v1/uploads/{id}             查询已接收分片
   6.12 PUT  /api/v1/uploads/{id}/chunks/{i}  上传单个分片
   6.13 POST /api/v1/uploads/{id}/complete    合并并校验
   6.14 DELETE /api/v1/uploads/{id}           取消上传并清理
   6.15 GET  /api/v1/thumbnails/{node_id}?size=256|1280  缩略图
   6.16 POST /api/v1/packages                 创建 ZIP 打包任务
   6.17 GET  /api/v1/packages/{id}            查询打包进度
   6.18 POST /api/v1/shares                   创建分享
   6.19 GET  /s/{token}?code=1234             分享访问（HTML 或 JSON）
   6.20 GET  /api/v1/trash                    回收站列表
   6.21 POST /api/v1/trash/{id}/restore       还原
   6.22 DELETE /api/v1/trash/{id}             彻底删除
   6.23 GET  /api/v1/search?kw=&type=&from=&to=&min=&max=  搜索
   6.24 GET  /api/v1/usage                    空间使用与统计
   6.25 GET  /api/v1/duplicates               重复文件列表
   6.26 GET  /api/admin/overview              管理端概览

7. 数据模型概览
   7.1 users(id TEXT PK, username UNIQUE, password_hash, quota_bytes BIGINT,
       used_bytes BIGINT, status, created_at)
   7.2 physical_files(id TEXT PK, sha256 TEXT UNIQUE, size BIGINT, mime TEXT,
       ref_count INT, created_at, last_access_at)
   7.3 nodes(id TEXT PK, user_id FK, parent_id TEXT NULL, name TEXT, type TEXT
       CHECK(type in ('file','dir')), size BIGINT, mime TEXT, physical_id TEXT NULL,
       path TEXT, deleted_at TEXT NULL, created_at, updated_at)
       索引：idx_parent(user_id, parent_id, name)（未删除时唯一）、idx_path(user_id, path)、
       idx_sha(physical_id)
   7.4 uploads(id TEXT PK, user_id FK, file_key TEXT, name TEXT, size BIGINT,
       sha256 TEXT, chunk_size INT, total_chunks INT, received_chunks INT,
       state TEXT, tmp_dir TEXT, created_at, expires_at)
       唯一键 (user_id, file_key)（未完成时）
   7.5 upload_chunks(id PK, upload_id FK, chunk_index INT, size INT, sha256 TEXT,
       received_at) 唯一键 (upload_id, chunk_index)
   7.6 shares(id TEXT PK, token TEXT UNIQUE, user_id FK, node_id FK, code_hash TEXT NULL,
       expires_at TEXT NULL, max_downloads INT NULL, download_count INT, state,
       created_at)
   7.7 zip_tasks(id TEXT PK, user_id FK, node_ids_json TEXT, state TEXT, progress INT,
       total_bytes BIGINT, archive_path TEXT, expire_at TEXT, created_at)
   7.8 audit_log(id PK, user_id, action, target_type, target_id, ip, detail_json,
       created_at)
   7.9 物理布局：objects/{p1}/{p2}/{sha256}（p1=sha256[0:2]，p2=sha256[2:4]）；
       thumbs/{p1}/{sha256}_{size}.jpg；tmp/{upload_id}/chunk_{index}.part。
   7.10 引用计数规则：物理对象创建时 ref_count=1；建立新节点引用时 +1；彻底删除节点
       时 -1；归零后由清理任务删除文件与缩略图，并在日志记录释放空间。

【三、里程碑拆解（建议 4 ~ 6 个阶段）】

阶段一：认证与基础文件管理（约 16 小时）
  产出：登录与令牌、nodes 虚拟文件系统、目录操作、小文件直传、Range 下载、前端基础页面。
  验收：可建目录、上传 10 MB 文件、下载校验 sha256 一致、重名返回 409。

阶段二：分片上传与秒传（约 26 小时）
  产出：上传会话与分片表、分片接收与校验、断点续传查询、流式合并与整体校验、预检秒传、
       内容寻址存储与引用计数。
  验收：上传 2 GB 文件中途断开，重新上传只补缺失分片且最终哈希一致；第二次上传同一文件
       实现秒传（上传字节数为 0）。

阶段三：缩略图、预览与搜索（约 20 小时）
  产出：Pillow 缩略图（256/1280 两级，EXIF 纠正）、图片预览浮层、缩略图接口与缓存、
       多维搜索、空间统计与重复文件检测。
  验收：1000 张图片上传后缩略图生成成功率 ≥ 99%，网格页面首屏加载 ≤ 1.5 秒。

阶段四：分享、回收站与打包（约 24 小时）
  产出：分享令牌与提取码、过期与次数限制、软删除与还原、彻底删除与引用计数递减、
       ZIP 后台打包任务与进度。
  验收：分享过期后访问被拒；回收站还原到原目录；彻底删除后物理对象仅在引用归零时才消失。

阶段五：管理端与后台任务（约 20 小时）
  产出：管理端概览与用户配额、上传任务监控、分享管理、定时清理任务（上传会话、回收站、
       孤立对象、ZIP 临时包）、对象完整性抽样校验、审计日志。
  验收：构造孤立对象后清理任务能回收；损坏对象能被抽样发现并告警。

阶段六：测试、性能与部署（约 20 小时）
  产出：覆盖率报告、并发上传压测脚本、部署文档（Docker 与 Nginx 配置）、备份与恢复演练
       文档、隐私与数据保留说明。
  验收：8 个并发的 1 GB 上传稳定完成；删除操作后磁盘空间在清理任务后正确回收；按下文档
       步骤能恢复数据库与物理对象。

【四、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；全量类型注解；IO 密集路径使用异步或线程池。
2. 允许使用的库：标准库（hashlib、os、shutil、zipfile、secrets、tempfile、pathlib、json、
   sqlite3、logging、concurrent.futures）；第三方限 FastAPI、uvicorn、SQLAlchemy、alembic、
   pydantic、redis、Pillow、passlib、python-jose、httpx、python-multipart、pytest、
   pytest-asyncio。禁止引入现成对象存储 SDK 或云盘服务。
3. 禁止事项：禁止把整个大文件读入内存再处理（必须流式分块读写，单次读不超过 8 MB）；
   禁止在没有校验分片哈希的情况下拼接；禁止用文件名或用户输入直接拼路径（必须用 sha256
   与内部 id）；禁止物理删除仍在被引用的对象；禁止把文件内容写入日志；禁止硬编码存储根
   路径与配额。
4. 代码组织：分层 api → service → repository；存储层（storage.py）是唯一允许直接操作文件
   系统路径的模块，其他模块必须通过它访问磁盘；缩略图、打包、清理任务与请求处理分离，
   不得在请求线程里做超过 2 秒的磁盘重活（改为后台任务 + 轮询/回调）。
5. 一致性要求：创建节点与递增引用计数必须在同一数据库事务内；物理文件先写完并 fsync 再
   写数据库引用；删除顺序为先标记数据库再删物理文件（失败可重试）；合并上传必须使用
   临时文件 + 原子改名，任何中断都不产生半成品对象。
6. 幂等与并发：同一 upload_id 重复上传同一分片必须覆盖写入且返回 200（不报 409）；
   complete 接口重复调用返回相同结果（已完成的返回值）；precheck 与 create upload 在并发
   下通过唯一键 (user_id, file_key) 兜底。
7. 编码规范：PEP 8；公有函数必须有类型注解与 docstring；异常统一继承 AppError 并携带
   code/http_status；禁止裸 except；所有磁盘操作必须有 try/except 并在失败时清理临时文件。
8. 测试要求：覆盖率 ≥ 75%；必须包含：分片上传中断恢复测试、哈希不匹配测试、秒传测试
   （断言零字节传输）、Range 下载正确性测试（多区间）、引用计数递减与孤立对象清理测试、
   分享过期与次数上限测试、路径穿越防护测试（构造 name=../../etc/passwd 必须被拒绝）。
9. 性能要求：单机 4 核 8 GB，单文件上传吞吐 ≥ 80 MB/s（本地磁盘）、下载 ≥ 120 MB/s；
   目录列表接口在 10 万节点下单页 P95 ≤ 200 ms；缩略图生成 500 KB 图片 ≤ 300 ms；
   支持 20 个并发上传会话而不显著降速。
10. 安全要求：所有节点接口必须校验所有权（水平越权测试必须覆盖）；分享令牌使用
    secrets 生成且不可预测；提取码哈希存储（不可反推）；上传类型按 MIME 与扩展名双白名单
    校验并禁止 .exe/.bat/.sh 等可执行后缀；文件名中的路径分隔符与控制字符必须清理；
    下载响应设置 Content-Disposition: attachment（图片预览除外）与
    X-Content-Type-Options: nosniff，防止 XSS 与内容嗅探。
11. 隐私与合规：云盘存储内容属于用户私有数据，管理员默认无法查看文件内容，管理端只
    展示元数据与哈希；若提供管理端内容查询能力必须在文档与界面中明确披露并获得用户
    同意；提供账号注销（删除全部节点、引用递减并清理物理对象）与全量数据导出（打包
    ZIP）功能；明确数据保留策略：回收站 30 天、上传临时分片 24 小时、日志 30 天、
    审计日志 180 天；备份数据同样适用删除请求（删除后 7 天内从备份中清除）。

【五、设计要点】

1. 数据结构：
   1.1 Node 统一建模文件与目录，type 字段区分；path 字段存储从根到该节点的物化路径
       （如 /照片/2025/），便于按前缀模糊查询与移动时批量更新（移动使用 path 前缀替换）。
   1.2 PhysicalFile(sha256, size, mime, ref_count) 与 Node 解耦，实现去重与引用计数。
   1.3 UploadSession(upload_id, file_key, chunk_size, total_chunks, received_bitmap)：
       received_bitmap 用位图（bytes）表示分片接收情况，1 万片仅需 1.25 KB。
   1.4 ChunkPlan(total_size, chunk_size) → [(index, start, end)]，客户端与服务端使用同一
       切分函数，保证边界一致（最后一片可小于 chunk_size，但不得为 0）。
2. 关键算法与流程：
   2.1 秒传流程：客户端计算 sha256（分片读取流式计算）→ precheck → 服务端查
       physical_files.sha256 → 命中则创建 node 并 ref_count+1 → 返回 seconds_upload=true；
       未命中返回 upload_id 与已存在的分片（若 file_key 已有会话则续传）。
   2.2 分片上传流程：PUT 分片 → 校验 upload_id 属于当前用户且未过期 → 校验 chunk_index
       范围 → 流式写入 tmp/{upload_id}/chunk_{index}.part（同时计算 sha256）→ 与声明值比对
       → 落库 upload_chunks → 更新 received_bitmap 与 received_chunks。
   2.3 合并流程：校验 received_chunks == total_chunks → 按 index 顺序流式追加写入
       objects 下的临时文件 → 每写入 8 MB 更新进度 → 完成后计算整体 sha256 → 与声明值比对
       → fsync → os.replace 到最终路径 → 事务内写 physical_files 与 node → 删除临时分片。
   2.4 引用计数递减：彻底删除 node → ref_count-1 → 若为 0 则标记 physical_files.state=
       pending_delete → 清理任务删除物理文件与缩略图 → 删除 physical_files 行；任何一步
       失败可通过重试恢复（先删文件后删记录，或先标记后删除）。
   2.5 Range 解析：解析 "bytes=start-end" → 校验范围（start ≤ end < size）→ 返回 206 与
       Content-Range；非法范围返回 416 并带 Content-Range: bytes */size；多区间请求
       （含逗号）本项目只支持返回第一个区间并在日志记录。
   2.6 ZIP 打包：创建任务 → 后台线程按节点列表逐个流式写入 zipfile（使用 zipfile.ZipFile
       的 open('w') 与 write 逐块读写）→ 每完成一个文件更新进度 → 写完后校验条目数 →
       返回一次性下载令牌，24 小时后删除。
   2.7 目录树移动：校验目标不是自身或子孙（用 path 前缀判断）→ 事务内更新 path 前缀与
       parent_id → 唯一约束冲突时整体回滚并返回 NAME_CONFLICT。
   2.8 路径穿越防护：所有 name 输入过滤 "/"、"\"、".."、控制字符与首尾空白；物理路径
       一律由 sha256 与内部 id 生成，绝不使用用户输入拼接。
3. 数据库主要表结构已在功能清单第 7 节列出；补充约束与索引：
   3.1 nodes 对 (user_id, parent_id, name) 建部分唯一索引（WHERE deleted_at IS NULL），
       保证同目录不重名但允许回收站内重名。
   3.2 physical_files.sha256 唯一索引；ref_count 使用 CHECK(ref_count >= 0)。
   3.3 uploads 对 (user_id, file_key) 建部分唯一索引（WHERE state IN ('pending','uploading')）。
   3.4 大表 nodes 按 user_id 建索引，配合 (user_id, deleted_at) 建回收站查询索引。
4. 接口设计要点：
   4.1 分片上传使用 PUT 语义（幂等），响应体含 {"received": 12, "total": 250}；分片大小
       不足时返回 400 CHUNK_SIZE_INVALID。
   4.2 所有列表接口统一分页（page/size，size 最大 200）与排序参数（name/size/mtime）。
   4.3 上传与打包这类长任务统一返回 task 语义：{id, state, progress}，前端轮询间隔 1 秒。
   4.4 分享访问支持 ?code= 参数与 POST 表单两种方式；错误响应区分“分享不存在”“已过期”
       “提取码错误”“下载次数已用完”，便于前端给出准确文案。

【六、运行方式与示例】

1. 安装与初始化
   python -m venv .venv && .venv\Scripts\activate
   pip install fastapi uvicorn sqlalchemy alembic pydantic redis pillow passlib
   pip install python-jose[cryptography] httpx python-multipart pytest pytest-asyncio
   copy .env.example .env      （填写 JWT_SECRET、DB_URL、STORAGE_ROOT、QUOTA_BYTES）
   alembic upgrade head
   python -m app.cli init-admin --username admin --password ******
2. 启动
   uvicorn app.main:app --host 127.0.0.1 --port 8010
   浏览器访问 http://127.0.0.1:8010
3. 命令行上传（便于自动化测试）
   python -m app.cli upload --file D:\video\big.mp4 --chunk-size 4194304 --api
   http://127.0.0.1:8010
4. 示例一（秒传预检命中）
   请求：POST /api/v1/files/precheck
   {"name": "报告.pdf", "size": 10485760,
    "sha256": "3f2a9c...e1"}
   响应：200 {"exists": true, "physical_id": "pf-77a1", "seconds_upload": true,
         "saved_bytes": 10485760}
   说明：客户端不上传任何分片，直接获得该文件的下载地址与节点 id。
5. 示例二（分片上传与断点续传）
   创建会话：POST /api/v1/uploads
   {"name": "big.mp4", "size": 2147483648, "sha256": "8b1d...", "file_key": "8b1d...-2147483648"}
   响应：201 {"upload_id": "up-91c2", "chunk_size": 4194304, "total_chunks": 512}
   上传第 0 片：PUT /api/v1/uploads/up-91c2/chunks/0（二进制体）
   响应：200 {"received": 1, "total": 512, "chunk_sha256": "a11c..."}
   中断后查询：GET /api/v1/uploads/up-91c2
   响应：200 {"received_chunks": 137, "total_chunks": 512,
         "missing": [137, 138, 139, "..."]}
   说明：客户端只需补传 138 到 511 号分片。
   完成后：POST /api/v1/uploads/up-91c2/complete
   响应：200 {"node_id": "nd-5521", "size": 2147483648, "sha256": "8b1d...",
         "deduplicated": false, "elapsed_ms": 41230}
6. 示例三（Range 下载）
   请求：GET /api/v1/nodes/nd-5521/download
   Header: Range: bytes=0-1048575
   响应：206 Partial Content
   Content-Range: bytes 0-1048575/2147483648
   Accept-Ranges: bytes
   ETag: "8b1d9f2c4e7a0135"
7. 示例四（分享）
   请求：POST /api/v1/shares
   {"node_id": "nd-5521", "expire_days": 7, "code": "8421", "max_downloads": 20}
   响应：201 {"share_url": "http://127.0.0.1:8010/s/kQ7fQ2xL9mR4tA",
         "expires_at": "2025-01-22T10:00:00Z", "has_code": true, "max_downloads": 20}
   访问：GET /s/kQ7fQ2xL9mR4tA?code=8421 → 200 HTML 分享页
   到期后：GET /s/kQ7fQ2xL9mR4tA?code=8421 → 410
   {"code": "SHARE_EXPIRED", "message": "该分享链接已于 2025-01-22 10:00 过期"}
8. 示例五（异常输入）
   上传超出配额：POST /api/v1/uploads，size = 60 GB（配额 50 GB 且已用 5 GB）
   响应：413 {"code": "QUOTA_EXCEEDED", "message": "剩余空间不足",
         "detail": {"quota": 53687091200, "used": 5368709120, "remaining": 48318382080}}
   分片哈希不符：PUT 分片但 sha256 声明值与实际不符
   响应：400 {"code": "CHUNK_MISMATCH", "message": "分片校验失败，请重传",
         "detail": {"chunk_index": 12, "expected": "a11c...", "actual": "b22d..."}}
   非法文件名：新建文件夹名为 "../etc"
   响应：400 {"code": "NAME_CONFLICT", "message": "名称包含非法字符"}

【七、验收标准】

[ ] 1. 上传 2 GB 文件，中断后重新上传只补传缺失分片，最终 sha256 与本地一致。
[ ] 2. 同一文件第二次上传（同 sha256）实现秒传，服务端记录的上传字节数为 0，
      storage/objects 下只存在一份物理文件。
[ ] 3. 通过文件 id 猜测下载他人文件返回 403；分享链接过期后返回 410 且不可下载。
[ ] 4. Range 请求返回 206 与正确的 Content-Range；非法范围返回 416。
[ ] 5. 删除文件进入回收站，物理对象仍存在；还原后节点恢复且仍指向同一物理对象。
[ ] 6. 彻底删除最后一个引用后，物理对象与缩略图在清理任务执行后被删除，磁盘空间可
      通过管理端看到释放。
[ ] 7. 1000 张图片上传后缩略图生成成功率 ≥ 99%，网格视图首屏加载 ≤ 1.5 秒。
[ ] 8. 上传 20 个并发会话时无数据损坏，所有文件 sha256 校验通过。
[ ] 9. 上传 .exe 文件被拒绝；文件名含 ".." 或路径分隔符被拒绝并记录日志。
[ ] 10. 提取码错误、下载次数用尽、分享被提前失效三种情况均返回准确的错误码与文案。
[ ] 11. ZIP 打包 500 个文件（共 2 GB）能完成并返回可下载链接，任务进度可见，
      24 小时后临时包被清理。
[ ] 12. 配额校验准确：已用空间统计与 storage/objects 实际占用差值小于 1%（软链接与
      硬链接情况除外，需在文档中说明统计口径）。
[ ] 13. 重复文件检测能找出内容相同的多个节点并给出可释放空间估算，且估算值与实际
      引用计数一致。
[ ] 14. pytest 覆盖率 ≥ 75%，含上传中断、幂等分片、引用计数、路径穿越四类专项测试。
[ ] 15. 备份与恢复演练：按文档步骤可从备份恢复数据库与物理对象，恢复后所有文件可下载
      且哈希一致。

【八、可选扩展】

1. 增加桌面同步客户端（watchdog 监听本地目录 + 增量差异同步 + 冲突解决策略）。
2. 增加对象存储后端（S3 兼容接口）作为可选存储驱动，对比本地磁盘与对象存储的差异。
3. 增加客户端加密：文件在客户端加密后上传，服务端只存密文（需说明密钥管理与分享难题）。
4. 增加视频转码与在线播放（可与 098 项目联动），支持 HLS 播放与进度记忆。
5. 增加文件版本历史：同名覆盖保留历史版本，可回滚到任意版本。
6. 增加多用户与协作空间：共享目录、成员权限（只读/可写）、操作通知。
7. 增加智能相册：按时间与地点聚类、基于 EXIF 的地图展示、简单人脸分组（可选）。

【九、涉及知识点】

- 大文件传输：分片切分与顺序合并、断点续传、分片级与整体级哈希校验、流式读写
- 内容寻址存储：sha256 寻址、引用计数、去重收益量化、原子写入（临时文件 + os.replace）
- HTTP 协议细节：Range/206/416、Content-Range、ETag 与 Last-Modified、断点下载
- 文件系统操作：路径安全、磁盘空间查询、临时目录管理、ZIP 流式打包
- 图像处理：Pillow 缩放与裁剪、EXIF 方向纠正、缩略图分级与缓存
- 数据库设计：虚拟文件系统建模、物化路径、部分唯一索引、软删除与回收站
- 安全：水平越权防护、分享令牌与提取码、路径穿越、MIME 白名单与响应头安全
- 工程与运维：后台任务与清理策略、配额与统计口径、备份恢复演练、Docker 部署
================================================================================
