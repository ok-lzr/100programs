================================================================================
项目编号：074                    难度等级：★★★★☆（中型项目）
项目名称：文件上传下载网盘
所属分类：Web 后端 / 文件与存储服务
建议工时：4 ~ 5 天
运行环境：Python 3.10+    第三方依赖：fastapi、uvicorn、sqlalchemy、pydantic、python-multipart、passlib[bcrypt]、python-jose[cryptography]、aiofiles、Pillow、pytest、httpx
================================================================================

【一、项目背景与目标】

网盘类功能的核心难点从来不是"把字节写到磁盘"，而是"怎么把一个 2GB 的文件在网络抖动、
浏览器崩溃、用户关电脑之后还能接着传完"，以及"同一个文件被十个人上传时怎么只存一份"。
很多自研文件服务一遇到大文件就只能干等超时，遇到中断就只能从头重传。

本项目实现一套完整的文件上传下载网盘服务，围绕四个真实需求展开：
分片上传（把大文件切成 5MB 小块，逐块上传，最后合并）、
秒传（按文件 SHA-256 判断服务端是否已有相同文件，已有则直接建立引用，不再传输字节）、
断点续传（客户端查询已上传分片列表，只补传缺失分片）、
分享链接（生成带有效期与提取码的分享，可限制下载次数）。

做成之后，它可以直接作为后台管理系统的附件中心，也可以作为独立网盘服务使用。
技术重点在于：分片状态的一致管理、合并过程的原子性与清理、物理文件与逻辑文件的多对多引用、
以及下载接口的 Range 支持与权限校验。

【二、功能需求清单】

1. 核心功能
   1.1 单文件直传：小文件（< 5MB）提供一次性上传接口，返回文件 ID 与元信息。
   1.2 分片上传初始化：提交文件名、总大小、分片大小、文件 SHA-256，返回 upload_id。
   1.3 秒传判定：初始化时按文件 SHA-256 查询物理文件表，命中则直接创建用户文件记录，
       返回 instant=true，不产生任何上传。
   1.4 分片上传：按 upload_id + chunk_index 上传单个分片，支持乱序上传与重复上传覆盖。
   1.5 断点续传：提供查询接口返回已上传分片索引列表与缺失分片索引列表。
   1.6 合并：所有分片就绪后触发合并，按 index 顺序拼接，校验合并后 SHA-256 与声明值一致。
   1.7 文件列表：列出当前用户文件，支持按名称模糊、类型、时间范围过滤与分页。
   1.8 下载：支持 Range 请求实现断点下载与视频拖动播放，返回正确的 Content-Range 与 206。
   1.9 分享：生成分享链接（可带提取码、有效期、最大下载次数），可取消分享。
   1.10 重命名 / 移动 / 删除：删除为软删除，进入回收站，30 天后由定时任务物理清理。
   1.11 配额管理：每个用户有总容量配额，上传前校验剩余空间，超限拒绝。
   1.12 鉴权：上传与管理接口需 JWT；分享下载可匿名访问但需校验提取码与次数。
   1.13 缩略图（可选）：图片文件上传后自动生成 256px 缩略图，列表页展示。

2. 输入与交互
   2.1 元信息用 JSON；分片用 multipart/form-data（字段名 file）。
   2.2 分片大小默认 5MB（5242880 字节），允许 1MB ~ 32MB，最小分片数 1，最大 10000。
   2.3 文件总大小上限 5GB；文件名长度 <= 255，必须过滤路径分隔符与 ../ 防止目录穿越。
   2.4 客户端 SHA-256 计算方式：完整文件流式计算十六进制小写摘要，服务端同样算法比对。
   2.5 上传使用 content-type 为 application/octet-stream 的二进制体，服务端流式落盘，
       禁止把整个分片读进内存（使用 aiofiles 或 shutil.copyfileobj 分块读写，块大小 1MB）。
   2.6 分页参数统一 page（默认 1）与 page_size（默认 20，最大 100）。

3. 输出与展示
   3.1 统一响应 { "code": 0, "message": "ok", "data": {...} }（下载接口除外，返回二进制流）。
   3.2 文件记录响应字段：id、name、size、mime_type、sha256、created_at、download_url、share_status。
   3.3 初始化响应：{"upload_id":"...","instant":false,"chunk_size":5242880,
       "total_chunks":420,"uploaded_chunks":[]}
   3.4 合并响应：{"file_id":88,"name":"video.mp4","size":2199023255,"sha256":"...","dedup":true}
   3.5 列表响应 data 含 items、total、page、page_size、pages、used_quota、total_quota。
   3.6 下载响应头：Content-Length、Content-Disposition（RFC 5987 编码中文名）、
       Accept-Ranges: bytes；Range 请求返回 206 与 Content-Range。

4. 异常与边界处理
   4.1 未登录或 token 失效：401 / 40102。
   4.2 文件不存在或不属于当前用户：404 / 40401（不区分，避免探测）。
   4.3 上传会话不存在或已过期（超过 24 小时未完成）：404 / 40402，客户端需重新初始化。
   4.4 分片索引越界（< 0 或 >= total_chunks）：422 / 42201。
   4.5 分片内容与预期大小不符（服务端按 Content-Length 校验）：400 / 40001。
   4.6 重复上传同一分片：允许覆盖，返回 200 并更新该分片记录与时间戳。
   4.7 未上传完所有分片就调用合并：409 / 40901，data 返回缺失分片索引。
   4.8 合并后 SHA-256 与声明不一致：409 / 40902，删除已合并的临时文件，保留分片供重传。
   4.9 上传超出配额：413 / 41301，data 返回 used、quota、need 三个数值。
   4.10 单文件超过 5GB 或分片数超过 10000：422 / 42202。
   4.11 分享链接过期：410 / 41001；下载次数用尽：410 / 41002；提取码错误：401 / 40103。
   4.12 分享的文件已被删除：404 / 40403。
   4.13 文件名含非法字符（\ / : * ? " < > |）：422 / 42203。
   4.14 Range 头非法（如 bytes=abc）：416，返回 Content-Range: bytes */<total>。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：fastapi、uvicorn[standard]、sqlalchemy 2.0、pydantic v2、
   python-multipart、aiofiles、passlib[bcrypt]、python-jose[cryptography]、
   Pillow（缩略图）、pytest、httpx、alembic。
3. 存储布局（必须遵循）：
   STORAGE_ROOT/
     objects/ab/cd/<sha256>         物理文件（按 SHA-256 前 4 位分两级目录，避免单目录文件过多）
     chunks/<upload_id>/<index>.part  上传中的分片
     thumbs/ab/cd/<sha256>.jpg      缩略图
     trash/                         软删除文件的临时区（可选）
4. 禁止事项：禁止把上传内容一次性读入内存（必须流式写入）。
5. 禁止事项：禁止使用用户提供的文件名拼接服务器路径；物理文件一律以 SHA-256 命名。
6. 禁止事项：禁止信任客户端提交的 MIME 类型做安全判断，服务端用 python-magic 或
   扩展名映射再校验；禁止对 .php/.exe 等可执行类型开放直接执行路径。
7. 禁止事项：禁止硬编码 JWT 密钥与存储根目录，必须读环境变量。
8. 代码组织（必须有以下模块）：
   app/main.py、app/config.py（STORAGE_ROOT、配额、分片限制、JWT）
   app/database.py、app/models.py、app/schemas.py、app/deps.py
   app/storage/paths.py（物理路径计算与目录初始化）
   app/storage/chunk_store.py（分片写入、读取、删除、磁盘空间检查）
   app/storage/merge.py（顺序合并、SHA-256 校验、原子改名）
   app/storage/dedup.py（秒传查询与引用计数维护）
   app/services/file_service.py（用户文件增删改查、配额计算）
   app/services/share_service.py（分享创建、提取码校验、次数扣减）
   app/routers/files.py、upload.py、download.py、share.py、auth.py
   app/tasks/cleanup.py（过期上传会话与回收站清理）
   tests/test_upload.py、test_resume.py、test_dedup.py、test_range.py、test_share.py
9. 编码规范：所有 IO 函数带类型注解与 docstring；使用 logging 记录 upload_id 与耗时。
10. 编码规范：文件 IO 的异常必须捕获并映射为业务错误码，禁止把 OSError 直接抛给客户端。

【四、设计要点】

1. 数据结构（核心表与字段）
   表 users：
     id PK、username VARCHAR(32) UNIQUE、password_hash VARCHAR(128)、
     quota_bytes BIGINT DEFAULT 10737418240（10GB）、used_bytes BIGINT DEFAULT 0、
     is_active BOOLEAN、created_at DATETIME
   表 objects（物理文件，按内容去重，一份内容一行）：
     id BIGINT PK
     sha256 CHAR(64) UNIQUE NOT NULL
     size BIGINT NOT NULL
     storage_path VARCHAR(512) NOT NULL（相对 STORAGE_ROOT 的路径）
     mime_type VARCHAR(128)
     ref_count INTEGER NOT NULL DEFAULT 0（被多少条用户文件引用）
     created_at DATETIME、last_access_at DATETIME
     索引：uk_objects_sha256(sha256)
   表 files（用户逻辑文件）：
     id BIGINT PK
     owner_id FK(users.id)、object_id FK(objects.id)
     name VARCHAR(255) NOT NULL
     parent_id BIGINT NULL（预留目录树，根目录为 NULL）
     size BIGINT NOT NULL
     mime_type VARCHAR(128)
     is_image BOOLEAN DEFAULT 0
     thumb_path VARCHAR(512) NULL
     deleted_at DATETIME NULL（软删除）
     created_at DATETIME、updated_at DATETIME
     索引：idx_files_owner(owner_id, deleted_at, created_at)、idx_files_object(object_id)
   表 upload_sessions（分片上传会话）：
     id CHAR(36) PK（upload_id，UUID4）
     owner_id FK(users.id)
     file_name VARCHAR(255) NOT NULL
     total_size BIGINT NOT NULL
     chunk_size INTEGER NOT NULL
     total_chunks INTEGER NOT NULL
     file_sha256 CHAR(64) NOT NULL
     uploaded_chunks INTEGER NOT NULL DEFAULT 0
     status VARCHAR(16) DEFAULT 'uploading'（uploading / merging / done / failed / expired）
     target_object_id BIGINT NULL（秒传时直接指向已有物理文件）
     created_at DATETIME、updated_at DATETIME、expires_at DATETIME
     索引：idx_us_owner(owner_id, status)、idx_us_expires(expires_at)
   表 upload_chunks（分片状态）：
     id BIGINT PK
     upload_id CHAR(36) FK(upload_sessions.id)
     chunk_index INTEGER NOT NULL
     chunk_size INTEGER NOT NULL
     chunk_sha256 CHAR(64) NULL
     storage_path VARCHAR(512) NOT NULL
     created_at DATETIME
     UNIQUE(upload_id, chunk_index)   ← 保证同一分片只有一行，重复上传走 UPSERT
   表 shares（分享）：
     id BIGINT PK
     token CHAR(22) UNIQUE NOT NULL（secrets.token_urlsafe(16) 生成）
     file_id FK(files.id)、owner_id FK(users.id)
     password_hash VARCHAR(128) NULL
     expires_at DATETIME NULL
     max_downloads INTEGER NULL、download_count INTEGER DEFAULT 0
     is_active BOOLEAN DEFAULT 1
     created_at DATETIME、revoked_at DATETIME NULL
     索引：uk_shares_token(token)、idx_shares_owner(owner_id, is_active)

2. 关键算法或流程
   分片上传初始化：
     步骤 1：校验 fileName / totalSize / chunkSize / sha256 格式与范围。
     步骤 2：按 sha256 查 objects 表；命中则执行秒传：
             写 files 记录并 object.ref_count += 1、user.used_bytes 按逻辑大小累计，
             返回 {"instant": true, "file_id": ...}，会话表不写或写为 done 状态。
     步骤 3：未命中则检查配额（used_bytes + total_size <= quota_bytes），不足返回 41301。
     步骤 4：total_chunks = ceil(total_size / chunk_size)；
             若 total_size == 0 则 total_chunks = 1（空文件也走一片）。
     步骤 5：生成 upload_id，插入 upload_sessions（expires_at = now + 24h），
             创建 chunks/<upload_id>/ 目录。
     步骤 6：返回 upload_id、chunk_size、total_chunks 与 uploaded_chunks（空数组）。
   分片上传（PUT /uploads/{upload_id}/chunks/{index}）：
     步骤 1：校验会话存在、未过期、status='uploading'。
     步骤 2：校验 index 在 [0, total_chunks) 内。
     步骤 3：流式写入 chunks/<upload_id>/<index>.part.tmp，边写边累计字节数与 SHA-256。
     步骤 4：写完后与 Content-Length 比对；不等则删除临时文件并返回 40001。
     步骤 5：os.replace 原子改名为 <index>.part（避免半截文件被误认为已完成）。
     步骤 6：UPSERT upload_chunks（存在则更新 chunk_size、chunk_sha256、created_at）。
     步骤 7：更新会话 uploaded_chunks = (SELECT COUNT(*) FROM upload_chunks WHERE upload_id=?)。
   断点续传查询（GET /uploads/{upload_id}）：
     返回 {"upload_id":..., "total_chunks":420, "uploaded_chunks":[0,1,2,5,...],
           "missing_chunks":[3,4,6,...], "expires_at":..., "status":"uploading"}
     客户端据此只补传 missing_chunks。
   合并（POST /uploads/{upload_id}/complete）：
     步骤 1：校验会话状态为 uploading，且 uploaded_chunks == total_chunks，否则 40901。
     步骤 2：把会话状态原子置为 merging（条件 UPDATE，防并发重复合并）。
     步骤 3：按 index 升序以 1MB 缓冲流式追加写入 objects/tmp/<upload_id>.merged，同时计算 SHA-256。
     步骤 4：合并完成，比对服务端计算值与声明的 file_sha256：
             不一致 → 删除合并文件，状态回置 uploading，返回 40902（保留分片供重传）。
     步骤 5：按 sha256 计算目标物理路径 objects/ab/cd/<sha256>；
             若该路径已存在（并发上传同一文件）则删除刚合并的文件并复用已有文件。
     步骤 6：os.replace(merged, target) 原子落位；UPSERT objects（ref_count += 1）。
     步骤 7：写 files 记录，更新 user.used_bytes，删除 chunks/<upload_id>/ 目录，
             会话状态置为 done，写审计日志（含 upload_id、大小、耗时）。
     步骤 8：整个数据库部分放在一个事务内；磁盘操作不可回滚，
             因此顺序是"先落物理文件、再写数据库"，数据库失败时删除孤立物理文件。
   下载（GET /files/{file_id}/download）：
     校验归属 → 解析 Range 头 → 用 open + seek 打开物理文件 →
     分块 yield（每块 1MB）返回 StreamingResponse 或 FileResponse（带 range 支持）。
     Range 存在时返回 206 与 Content-Range: bytes start-end/total。
     并发下载只读打开文件，天然安全；不修改文件，不加锁。
   引用计数与删除：
     删除用户文件为软删除（deleted_at = now），user.used_bytes 立即扣减，
     objects.ref_count -= 1；当 ref_count 降为 0 时进入待清理队列，
     由每日清理任务确认 24 小时内无新引用后物理删除文件。
   秒传的并发安全：
     使用 INSERT ... ON CONFLICT(sha256) DO UPDATE SET ref_count = objects.ref_count + 1
     RETURNING id 实现原子 upsert，避免两个请求同时插入同一 sha256 导致唯一键冲突。

3. 接口设计（统一前缀 /api/v1，除分享下载与 login 外均需 Authorization: Bearer <token>）
   POST /api/v1/auth/register、POST /api/v1/auth/login
     返回 JWT（HS256，1 小时），密钥读 JWT_SECRET_KEY。
   POST /api/v1/files/simple   需 Bearer
     请求：multipart/form-data，字段 file，可选 name。
     行为：适用于 <= 5MB 的文件，服务端计算 sha256 并按秒传逻辑处理。
     响应 201：{"code":0,"data":{"file_id":88,"name":"a.png","size":20480,
              "sha256":"...","instant":false}}
     失败：413/41301、422/42203（文件名非法）、401/40102。
   POST /api/v1/uploads   需 Bearer
     请求：{"file_name":"video.mp4","total_size":2199023255,"chunk_size":5242880,
           "file_sha256":"e3b0c442...","mime_type":"video/mp4"}
     响应 201：{"code":0,"data":{"upload_id":"9f1c...","instant":false,
              "chunk_size":5242880,"total_chunks":420,"uploaded_chunks":[]}}
     秒传时：{"code":0,"data":{"upload_id":null,"instant":true,"file_id":88}}
     失败：413/41301（配额不足）、422/42202（大小或分片数超限）、409/40902（已存在同名未完成会话）。
   GET /api/v1/uploads/{upload_id}   需 Bearer 且为所有者
     响应 200：会话详情 + uploaded_chunks + missing_chunks + expires_at。
     失败：404/40402（不存在或过期）。
   PUT /api/v1/uploads/{upload_id}/chunks/{index}   需 Bearer 且为所有者
     请求：application/octet-stream 二进制分片体（Content-Length 必须等于该分片预期大小）。
     响应 200：{"code":0,"data":{"index":12,"received":5242880,"uploaded_chunks":58,
              "total_chunks":420}}
     失败：400/40001（大小不符）、404/40402、409/40903（会话已在合并中）。
   POST /api/v1/uploads/{upload_id}/complete   需 Bearer 且为所有者
     请求：{"file_sha256":"e3b0c442..."}（可选，覆盖初始化时声明的值）
     响应 200：{"code":0,"data":{"file_id":88,"name":"video.mp4","size":2199023255,
              "sha256":"e3b0c442...","dedup":true,"elapsed_ms":1840}}
     失败：409/40901（分片未齐，data 含 missing_chunks）、409/40902（校验失败）。
   DELETE /api/v1/uploads/{upload_id}   需 Bearer 且为所有者
     响应 200：取消上传并删除已落盘分片。
   GET /api/v1/files?keyword=report&mime=image&page=1&page_size=20&trash=false   需 Bearer
     响应 200：{"code":0,"data":{"items":[...],"total":37,"page":1,"page_size":20,"pages":2,
              "used_quota":12345678,"total_quota":10737418240}}
   GET /api/v1/files/{file_id}   需 Bearer 且为所有者
     响应 200：文件详情；404/40401。
   PATCH /api/v1/files/{file_id}   需 Bearer 且为所有者
     请求：{"name":"新名字.mp4"}；响应 200；422/42203（非法字符）。
   DELETE /api/v1/files/{file_id}   需 Bearer 且为所有者
     响应 200：软删除，返回 {"in_trash":true,"purge_at":"2024-06-30T00:00:00Z"}。
   POST /api/v1/files/{file_id}/restore   需 Bearer 且为所有者
     响应 200：从回收站恢复；若配额不足返回 413/41301。
   GET /api/v1/files/{file_id}/download   需 Bearer 且为所有者
     响应 200（完整）或 206（Range）；带 Content-Disposition 与 Accept-Ranges。
     失败：404/40401、416（Range 非法）。
   GET /api/v1/files/{file_id}/thumb   需 Bearer 且为所有者
     响应 200：image/jpeg 缩略图；非图片文件返回 404/40404。
   POST /api/v1/shares   需 Bearer 且为所有者
     请求：{"file_id":88,"expires_at":"2024-06-30T00:00:00Z","max_downloads":10,"password":"ab12"}
     响应 201：{"code":0,"data":{"token":"Xk9fQ2mZ...","share_url":"https://pan.example.com/s/Xk9fQ2mZ",
              "has_password":true,"expires_at":"2024-06-30T00:00:00Z","max_downloads":10}}
     失败：404/40401、422/42204（密码格式或时间非法）。
   GET /api/v1/shares   需 Bearer
     响应 200：当前用户的有效分享列表（含 download_count）。
   DELETE /api/v1/shares/{token}   需 Bearer 且为所有者
     响应 200：撤销分享（revoked_at = now）。
   GET /s/{token}   公开
     行为：无密码且未过期则 302 跳转到 /s/{token}/download；
           需要密码则返回 401/40103 与提示页。
   POST /s/{token}/verify   公开
     请求：{"password":"ab12"}；成功返回 {"download_url":"/s/{token}/download?ticket=..."}。
     失败：401/40103，5 次失败后该 IP 锁 10 分钟。
   GET /s/{token}/download   公开（需校验 ticket 或密码）
     行为：校验过期、次数上限、文件是否已删除；成功后原子递增 download_count，
           返回 200/206 二进制流。次数用尽返回 410/41002。
   GET /api/v1/healthz   公开
     响应 200：{"status":"ok","db":"ok","disk_free":53687091200}

4. 鉴权方式与安全要求
   - 用户口令使用 bcrypt（rounds=12）；JWT_SECRET_KEY 从环境变量读取，长度 >= 32。
   - 所有文件访问接口必须显式比对 owner_id，禁止仅凭 file_id 返回内容（横向越权防护）。
   - 分享 token 使用 secrets.token_urlsafe(16)（约 22 字符、128 位熵），
     分享提取码使用 4~8 位随机字符串并 bcrypt 哈希存储。
   - 分享下载使用 ticket 机制：验证密码成功后签发 5 分钟有效的短期票据，
     下载接口校验票据，避免密码在 URL 中长期暴露。
   - 文件名清洗：去掉路径分隔符、控制字符、前后空白，拒绝 "." 与 ".."，
     长度截断到 255 字节（按 UTF-8 计算），响应下载时用 RFC 5987 编码。
   - 磁盘写入路径全部由服务端计算（sha256 / upload_id 派生），
     绝不使用用户输入拼接路径（防目录穿越）。
   - 上传接口按用户限流：初始化 30 次/分钟，分片上传 600 次/分钟；
     分享下载按 IP 限流 60 次/分钟。
   - 存储根目录权限设置为仅服务进程可读写；对外不提供静态目录直读。

5. 错误处理与并发事务注意点
   - 合并操作必须用条件 UPDATE 抢占状态：
     UPDATE upload_sessions SET status='merging' WHERE id=:id AND status='uploading'，
     rowcount=0 时返回 409/40903，防止并发重复合并产生两个物理文件。
   - 分片写入使用临时文件 + os.replace 原子改名，避免进程崩溃留下半截分片被判为完成。
   - 磁盘与数据库不可能同一事务，采用"先落盘后写库"+"失败补偿删除"的顺序，
     并由每日对账任务扫描 objects 表中不存在物理文件的记录并标记异常。
   - 秒传的 ref_count 更新必须用原子 SQL（ref_count = ref_count + 1），
     删除时用 UPDATE ... SET ref_count = ref_count - 1 WHERE ref_count > 0 防止负值。
   - 配额扣减在初始化时预占（reserve），取消或失败时释放；
     使用 users.used_bytes = used_bytes + :size WHERE used_bytes + :size <= quota_bytes
     的条件更新来避免并发上传突破配额。
   - 分享下载次数使用条件更新：
     UPDATE shares SET download_count = download_count + 1
     WHERE token = :t AND (max_downloads IS NULL OR download_count < max_downloads)，
     rowcount=0 时返回 410/41002，杜绝超额下载。
   - 上传会话与分片目录由清理任务处理：每小时扫描 expires_at < now 且 status='uploading' 的会话，
     删除目录并把状态置为 expired；回收站文件超过 30 天物理删除。
   - 大文件合并时使用 readinto 与固定缓冲，禁止 read() 无参调用导致内存暴涨。

【五、运行方式与示例】

安装与启动：
  python -m venv .venv && .venv\Scripts\activate
  pip install -r requirements.txt
  set JWT_SECRET_KEY=please-change-this-32bytes-minimum
  set DATABASE_URL=sqlite:///./pan.db
  set STORAGE_ROOT=D:\pan_storage
  set MAX_FILE_SIZE=5368709120
  alembic upgrade head
  uvicorn app.main:app --reload --port 8300
  python -m app.tasks.cleanup --once     # 手动执行一次清理

界面与交互说明：
  服务本身只提供 HTTP 接口，/docs 提供 Swagger UI。
  Swagger 中可直接选择文件上传（simple 接口）验证小文件流程；
  大文件分片流程建议用 tests/ 里的脚本或 curl 演示（见示例 2）。
  下载接口在 Swagger 中会以二进制响应呈现，建议用浏览器直接打开下载 URL。

示例 1（小文件直传）：
  请求：POST /api/v1/files/simple   multipart: file=@logo.png
  响应：HTTP 201
        {"code":0,"message":"上传成功","data":{"file_id":88,"name":"logo.png",
         "size":20480,"sha256":"3f786850e387550fdab836ed7e6dc881de23001b",
         "mime_type":"image/png","instant":false}}
示例 2（大文件分片 + 断点续传）：
  步骤一：POST /api/v1/uploads
          {"file_name":"demo.mp4","total_size":10485760,"chunk_size":5242880,
           "file_sha256":"<完整文件摘要>"}
          响应：{"upload_id":"9f1c2a...","instant":false,"chunk_size":5242880,"total_chunks":2}
  步骤二：PUT /api/v1/uploads/9f1c2a.../chunks/0   （5MB 二进制）
          响应：{"index":0,"received":5242880,"uploaded_chunks":1,"total_chunks":2}
  步骤三：GET /api/v1/uploads/9f1c2a...
          响应：{"uploaded_chunks":[0],"missing_chunks":[1],"status":"uploading"}
  步骤四：PUT /api/v1/uploads/9f1c2a.../chunks/1
  步骤五：POST /api/v1/uploads/9f1c2a.../complete  {"file_sha256":"<完整文件摘要>"}
          响应：{"file_id":91,"name":"demo.mp4","size":10485760,"dedup":false,"elapsed_ms":412}
示例 3（秒传）：
  再次 POST /api/v1/uploads 提交与上面完全相同的 file_sha256
  响应：HTTP 201
        {"code":0,"message":"秒传成功","data":{"upload_id":null,"instant":true,"file_id":92}}
示例 4（Range 断点下载）：
  请求：GET /api/v1/files/91/download   Range: bytes=5242880-5242879
  响应：HTTP 206
        Content-Range: bytes 5242880-5242879/10485760
        Content-Length: 5242880
        Accept-Ranges: bytes
示例 5（分片未齐就合并）：
  请求：POST /api/v1/uploads/9f1c2a.../complete
  响应：HTTP 409
        {"code":40901,"message":"分片未上传完整","data":{"missing_chunks":[1]}}
示例 6（异常输入）：
  请求：POST /api/v1/uploads  {"file_name":"../../etc/passwd","total_size":999999999999,
        "chunk_size":100,"file_sha256":"abc"}
  响应：HTTP 422
        {"code":42202,"message":"文件名非法且分片数量超过上限 10000",
         "data":{"file_name":"../etc/passwd","chunk_size":"100 不在 1MB~32MB 之间"}}

【六、验收标准】

[ ] 上传 6MB 文件使用 5MB 分片时 total_chunks 为 2，分片乱序上传后合并结果与源文件 SHA-256 一致。
[ ] 中断后重新查询上传会话，missing_chunks 准确列出未上传分片，补传后合并成功。
[ ] 同一文件再次上传返回 instant=true，服务端未产生新的物理文件，objects 表只有一行。
[ ] 两个不同用户上传同一文件后 objects.ref_count 为 2，其中一个删除后为 1，全部删除后文件可被清理。
[ ] 未传完分片调用 complete 返回 409/40901 且 data 中含缺失分片索引列表。
[ ] 上传过程中篡改分片内容导致 SHA-256 不符时返回 409/40902，且不产生 files 记录。
[ ] 上传 5GB+1 字节的文件在初始化阶段即返回 422/42202，不落盘。
[ ] 配额用尽时初始化返回 413/41301，data 中 used、quota、need 三个数值自洽。
[ ] 下载时带 Range: bytes=0-1023 返回 206 与正确的 Content-Range，内容与源文件对应字节一致。
[ ] 非法 Range（bytes=abc）返回 416 与 Content-Range: bytes */<total>。
[ ] 中文文件名的 Content-Disposition 使用 filename*=UTF-8'' 编码且浏览器显示正常。
[ ] 用户 A 无法下载、重命名、删除用户 B 的文件（均返回 404/40401）。
[ ] 分享链接设置 max_downloads=2 后第 3 次下载返回 410/41002，download_count 恰为 2。
[ ] 带提取码的分享未验证直接下载返回 401/40103，验证后可下载且票据 5 分钟有效。
[ ] 分享过期后访问返回 410/41001；文件被删除后访问返回 404/40403。
[ ] 上传 24 小时未完成的会话被清理任务置为 expired 且分片目录被删除。
[ ] pytest 用例覆盖分片、续传、秒传、Range、分享五类场景并全部通过。

【七、可选扩展】

1. 增加目录树（parent_id 递归）与批量移动、拖拽排序接口。
2. 接入 S3 / MinIO 作为对象存储后端，通过 storage backend 抽象切换本地与远端。
3. 增加多线程并发分片上传客户端示例脚本（concurrent.futures + httpx）。
4. 增加在线预览：图片直接展示、PDF 用 pypdf 渲染首页、文本文件转码展示。
5. 增加文件版本管理，同一逻辑文件保留最近 5 个历史版本。
6. 增加病毒扫描钩子（调用 clamd）在合并完成后扫描，命中则隔离文件。
7. 增加分享下载的防盗链（Referer 校验）与一次性下载链接。

【八、涉及知识点】

- HTTP 分片上传协议设计与幂等分片写入（临时文件 + 原子改名）
- 断点续传的状态管理：会话、分片索引、缺失分片计算
- 内容寻址存储与秒传：SHA-256 摘要、引用计数、原子 upsert
- 流式 IO：aiofiles / readinto 固定缓冲，避免大文件内存膨胀
- HTTP Range 语义：Accept-Ranges、Content-Range、206 与 416
- 磁盘与数据库一致性：先落盘后写库、失败补偿、对账清理
- 并发控制：条件 UPDATE 抢占状态、配额预占、分享下载次数原子扣减
- 文件安全：路径穿越防护、文件名清洗、MIME 校验、short-lived ticket
- 对象存储目录分片策略（按哈希前缀两级目录）与清理任务设计
- RFC 5987 文件名编码与 Content-Disposition 实践
================================================================================
