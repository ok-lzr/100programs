================================================================================
项目编号：098                    难度等级：★★★★★（大型项目）
项目名称：视频转码与流媒体服务
所属分类：多媒体 / 流媒体服务 / 后台任务
建议工时：3 ~ 4 周（约 110 ~ 170 小时）
运行环境：Python 3.10+    第三方依赖：FastAPI、uvicorn、SQLAlchemy、alembic、pydantic、redis、APScheduler、pytest、httpx、python-multipart；外部程序：ffmpeg 与 ffprobe（必须自行安装并在启动时校验）
================================================================================

【一、项目背景与目标】

把一个手机拍的 4K 视频直接丢给浏览器播放，通常会失败或卡顿：文件可能几 GB，边下边播
体验极差；编码是 H.265 或手机特有的封装，浏览器不一定支持；没有多码率，弱网用户只能
干等；播放到一半网络抖动，整个文件要重下。视频服务要解决的正是这些问题：上传后转成
浏览器友好的编码与封装，切成小分片，提供多档码率让播放器按网络状况自适应切换，并用
索引文件（m3u8）驱动播放。同时还需要处理一堆工程问题：转码是重 CPU 任务，必须异步执行
且能查看进度、取消与重试；一次转码产出几十上百个分片，任务编排与产物管理必须有结构。

本项目的目标是实现一个完整的视频转码与流媒体服务：视频上传（分片上传）、元信息探测、
多码率转码（HLS 分片）、封面图与预览雪碧图生成、在线播放（自适应码率）、转码进度与
队列管理、播放统计与断点记忆。系统要在单机部署下用 ffmpeg 完成从上传到可播放的全流程，
并把每个阶段的状态、耗时与产物路径记录清楚，任何一步失败都能定位与重试。

目标用户是：需要给自建站点加视频播放能力的开发者、想学习流媒体基础知识（封装、编码、
分片、m3u8、码率阶梯）的学习者、以及需要一个本地视频库并支持在线播放的个人用户。
项目明确不做：不做直播推流、不做 DRM 版权保护、不做 CDN 调度与边缘分发、不做转码集群
调度（单机多进程即可）、不做视频编辑（剪辑、拼接、特效）。

技术实现上必须以 ffmpeg 为转码核心（Python 侧只做编排、进度解析与产物校验），避免出现
“用 Python 逐帧解码再编码”的做法；同时要支持 ffmpeg 不存在时的优雅降级：启动时检测
ffprobe 与 ffmpeg，不存在则服务可以启动但转码接口返回明确的可操作错误提示，而不是崩溃。

【二、功能需求清单】

本系统按四个子系统拆分：用户端（Web 播放与管理界面）、服务端（上传、转码编排与播放
服务）、管理端（运维与队列）、基础设施（存储、任务、ffmpeg 调用与部署）。

1. 用户端子系统（Web 界面）
   1.1 视频列表页：卡片式展示已上传视频的封面、标题、时长、分辨率、大小、状态（排队中/
       转码中/可播放/失败），支持按上传时间与标题排序、按状态筛选、关键字搜索。
   1.2 上传页：支持选择文件与拖拽；大文件自动分片上传（默认 8 MB 一片），显示总进度、
       上传速度与剩余时间；支持暂停与继续、取消；上传完成后自动进入元信息探测。
   1.3 元信息确认：上传后展示探测结果（时长、分辨率、编码、码率、帧率、音频声道），
       允许用户填写标题、简介、标签，并选择转码档位组合（默认“360p + 720p + 1080p”）。
   1.4 播放页：使用 HLS 播放器（前端引入 hls.js 的 CDN 版本；不支持 MSE 的浏览器提示
       使用 Safari 或下载原片）。功能包括：播放/暂停、进度条拖动、音量、播放速率（0.5x ~
       2x）、画质切换（自动/360p/720p/1080p）、全屏、画中画、键盘快捷键（空格、方向键）。
   1.5 断点记忆：记录每个视频的播放位置（localStorage 与服务端双写，服务端按用户+视频
       保存），下次打开提示“从 12:35 继续播放”。
   1.6 封面与预览：列表使用生成的封面图；鼠标悬停在进度条上显示该时间点的预览缩略图
       （由雪碧图 + WebVTT 描述实现）。
   1.7 分享：生成带令牌的分享链接（可设置有效期），分享页无需登录即可播放，但不提供
       下载；所有者的原生视频下载链接仅对登录用户可用。
   1.8 我的视频管理：修改标题与标签、删除（软删除进回收站）、重新转码（更换档位）、
       查看转码日志摘要与产物清单。
   1.9 播放统计（用户可见部分）：该视频的总播放次数、平均观看时长、完播率粗略估计。
   1.10 异常提示：文件格式不支持、上传超时、转码失败（附失败原因摘要）、存储空间不足、
       分享链接过期等均给出明确文案与建议操作。

2. 服务端子系统（上传、转码与播放）
   2.1 分片上传：POST /api/v1/uploads 创建上传会话（返回 upload_id、chunk_size）；
       PUT /api/v1/uploads/{id}/chunks/{index} 接收分片；POST .../complete 合并并用 sha256
       校验整体一致性；支持查询已收分片与断点续传；上传会话 24 小时过期并清理。
   2.2 类型与体量约束：仅接受视频容器（mp4、mov、mkv、webm、avi、m4v）与常见编码；
       单文件上限默认 10 GB；通过 ffprobe 校验确实含视频流（防止改扩展名绕过）。
   2.3 元信息探测：调用 ffprobe -v quiet -print_format json -show_format -show_streams，
       解析时长、码率、分辨率、帧率、codec_name、pix_fmt、音频采样率与声道、旋转元数据；
       探测超时 30 秒；解析失败时记录原始 JSON 摘要便于排查。
   2.4 转码任务编排：为每个视频创建一个 transcode_job，包含若干 rendition（档位）子任务；
       每个 rendition 独立执行，互不阻塞；同一 job 内多个 rendition 串行执行以控制 CPU
       占用（可按 CPU 核数配置并发 1 ~ 2）。
   2.5 码率阶梯：默认三档——360p（640×360，视频 800 kbps，音频 96 kbps）、720p
       （1280×720，视频 2500 kbps，音频 128 kbps）、1080p（1920×1080，视频 5000 kbps，
       音频 160 kbps）；源分辨率低于档位时不放大（跳过该档并在记录中说明）。
   2.6 HLS 分片：使用 ffmpeg 生成 HLS（-f hls -hls_time 6 -hls_playlist_type vod
       -hls_segment_filename ...），分片时长 6 秒，关键帧对齐（-force_key_frames
       "expr:gte(t,n_forced*6)"），产出 playlist.m3u8 与 seg_%05d.ts；生成 master.m3u8
       汇总各档位（含 BANDWIDTH 与 RESOLUTION）。
   2.7 可选 fMP4 分片：支持 -hls_segment_type fmp4 输出 .m4s 与 init 段，作为可配置选项。
   2.8 封面与雪碧图：使用 ffmpeg 抽取第 10% 时长处的一帧作为封面（720px 宽）；生成
       雪碧图（每 10 秒一帧、160×90、每行 10 帧，组成 JPEG）与对应的 WebVTT 缩略图描述
       文件，供进度条悬停预览。
   2.9 进度解析：转码时读取 ffmpeg stderr 中的 time= 与 speed= 字段（使用 -progress 管道
       更可靠：-progress pipe:1 -nostats），按 duration 计算百分比、已处理时长、转码速度
       与预计剩余时间；进度每 2 秒写入数据库并推送（SSE 或 WebSocket）。
   2.10 任务控制：支持取消（终止 ffmpeg 子进程并清理产物）、重试失败任务（可只重试失败
       的档位）、按队列顺序（FIFO）或手动提升优先级执行；队列管理由 APScheduler 与线程/
       进程池结合，禁止在请求线程中执行转码。
   2.11 失败处理：ffmpeg 返回非零退出码时记录命令、退出码、stderr 末尾 50 行、已产出文件
       清单，并标记该 rendition 失败；整体 job 在至少一个档位成功时标记为“部分可播放”，
       全部失败标记 failed。
   2.12 播放服务：HLS 静态资源由服务端提供，需带正确的 MIME（application/vnd.apple.mpegurl
       与 video/mp2t）、Cache-Control 与 CORS 头；m3u8 不缓存或缓存 1 秒，ts 分片可缓存
       长期（内容寻址路径）。支持 Range 请求（原生 MP4 下载与播放进度拖动）。
   2.13 原片保留策略：可配置保留原片（默认保留 30 天）或转码成功后立即删除以节省空间；
       删除原片不影响已生成的分片与下载（若有代理档）。
   2.14 存储配额与清理：统计原片、分片、封面、雪碧图占用；提供过期转码产物清理任务
       （针对已删除视频的残留目录）与孤立文件扫描。
   2.15 统一错误模型：{"code": "...", "message": "...", "detail": {...}}；错误码含
       UNSUPPORTED_FORMAT、PROBE_FAILED、FFMPEG_MISSING、DISK_FULL、TRANSCODE_FAILED、
       JOB_CANCELLED、QUOTA_EXCEEDED、SHARE_EXPIRED。

3. 管理端子系统
   3.1 队列总览：等待中/进行中/已完成/失败的任务数与预估总耗时；当前正在转码的视频、
       档位与进度。
   3.2 任务详情：单个 job 的每个 rendition 状态、ffmpeg 命令（脱敏后的路径）、耗时、
       产物大小、失败原因与日志尾部。
   3.3 并发与资源设置：转码并发数（默认 1，可调 1 ~ 4）、同时上传数上限、单文件大小上限、
       分片时长与档位组合模板；设置变更需记录审计日志。
   3.4 存储管理：磁盘占用与剩余空间、清理任务手动触发（清理过期上传会话、失败产物、
       回收站视频的物理文件、孤立分片目录）。
   3.5 视频管理：全部视频列表、强制重新转码、下架（不可播放但保留数据）、彻底删除。
   3.6 访问统计：播放次数、观看总时长、热门视频 Top 10、按天播放趋势、分享链接访问量。
   3.7 审计与安全：所有管理写操作写入 audit_log；提供分享令牌失效与批量失效能力。

4. 基础设施子系统
   4.1 外部依赖校验：启动时执行 ffmpeg -version 与 ffprobe -version，缺失则打印安装指引
       （Windows 用 winget 或官网压缩包，Linux 用包管理器）并在 /healthz 中标记 degraded。
   4.2 目录结构：storage/originals/{video_id}/source.mp4；storage/hls/{video_id}/{rendition}/
       playlist.m3u8 与 .ts；storage/images/{video_id}/cover.jpg 与 sprite.jpg、
       thumbs.vtt；storage/tmp/{upload_id}/ 存上传分片；storage/logs/{job_id}/ 存 ffmpeg 日志。
   4.3 数据库：SQLite 开发、PostgreSQL 生产；视频、任务、档位、播放记录、分享、配额分表；
       watch_progress 与 play_events 表按需分区或定期归档。
   4.4 缓存：Redis 缓存视频列表首页（30 秒）、m3u8 内容（1 秒或不缓存）、播放计数（先写
       Redis 再定期汇总落库，避免高并发写库）。
   4.5 任务调度：APScheduler 负责上传会话过期清理（每 10 分钟）、播放计数汇总（每 1 分钟）、
       存储巡检（每小时）、过期分享失效（每 10 分钟）；转码任务由独立的工作线程/进程从
       任务表领取（数据库行锁 + 状态机），保证多进程安全。
   4.6 断点与恢复：服务重启后扫描 state 为 running 的 rendition，标记为 interrupted 并
       重新入队（可配置自动重试次数）；已完成的档位不重做。
   4.7 配置管理：config.toml 定义 storage_root、ffmpeg_path、ffprobe_path、hls_time、
       max_file_bytes、renditions（档位模板）、transcode_concurrency、keep_original_days、
       share_default_days、disk_reserve_bytes；支持环境变量 VID_ 前缀覆盖。
   4.8 日志：app.log（业务）、transcode.log（ffmpeg 调用与进度摘要）、access.log（播放请求
       与字节数）、audit.log；日志不得输出文件绝对路径给最终用户，仅内部记录。
   4.9 部署：Dockerfile（基于含 ffmpeg 的基础镜像）与 docker-compose（挂载 storage 卷）；
       Nginx 配置示例（静态分片直出、gzip、CORS、Range 与 client_max_body_size）；
       部署文档说明 CPU 需求（1080p 转码约需 1 核实时率的 1 ~ 2 倍）。

5. 模块清单（源码结构）
   5.1 app/main.py                FastAPI 应用、生命周期、依赖校验。
   5.2 app/config.py              配置与路径管理（启动时创建目录并校验可写）。
   5.3 app/models/                user、video、rendition、transcode_job、upload、
                                  play_event、watch_progress、share、quota、audit_log。
   5.4 app/services/upload.py     分片上传会话、合并、sha256 校验、断点查询。
   5.5 app/services/probe.py      ffprobe 调用、JSON 解析、旋转与色彩元数据处理。
   5.6 app/services/ffmpeg.py     ffmpeg 命令构建、子进程执行、进度解析、取消与超时。
   5.7 app/services/transcode.py  档位规划、job 编排、状态机、重试与恢复。
   5.8 app/services/hls.py        m3u8 生成与校验、master 播放列表组装、分片清单。
   5.9 app/services/images.py     封面抽取、雪碧图与 WebVTT 生成。
   5.10 app/services/playback.py  播放资源路由、MIME 与缓存头、Range 支持、播放统计。
   5.11 app/services/cleanup.py   上传会话、失败产物、过期原片、孤立目录清理。
   5.12 app/api/                  uploads、videos、transcode、playback、shares、admin 路由。
   5.13 app/worker.py             转码工作进程入口（独立进程启动）。
   5.14 web/                      前端页面与 hls.js 播放器封装、进度条缩略图。
   5.15 tests/                    单元、接口、ffmpeg 命令构建、HLS 校验、进度解析测试。

6. 接口清单（HTTP，节选核心）
   6.1 POST /api/v1/uploads                     创建上传会话 {filename, size, sha256}
   6.2 PUT  /api/v1/uploads/{id}/chunks/{index} 上传分片
   6.3 GET  /api/v1/uploads/{id}                查询已收分片（断点续传）
   6.4 POST /api/v1/uploads/{id}/complete       合并并校验
   6.5 POST /api/v1/videos                      创建视频记录并触发探测 {upload_id, title}
   6.6 GET  /api/v1/videos/{id}/probe           探测结果
   6.7 POST /api/v1/videos/{id}/transcode       提交转码 {renditions: ["360p","720p","1080p"]}
   6.8 GET  /api/v1/videos/{id}                 视频详情与状态
   6.9 GET  /api/v1/transcode/jobs/{job_id}     任务与档位进度
   6.10 GET  /api/v1/transcode/jobs/{job_id}/events  SSE 进度流
   6.11 POST /api/v1/transcode/jobs/{job_id}/cancel  取消任务
   6.12 POST /api/v1/transcode/jobs/{job_id}/retry   重试失败档位
   6.13 GET  /api/v1/videos/{id}/playlist       重定向到 master.m3u8 或返回播放清单信息
   6.14 GET  /media/hls/{video_id}/{rendition}/playlist.m3u8  HLS 清单（正确 MIME）
   6.15 GET  /media/hls/{video_id}/{rendition}/seg_00012.ts   HLS 分片
   6.16 GET  /media/images/{video_id}/cover.jpg 封面
   6.17 GET  /media/images/{video_id}/thumbs.vtt 与 sprite.jpg 缩略图描述
   6.18 GET  /api/v1/videos/{id}/download       下载原片（Range，仅所有者）
   6.19 POST /api/v1/shares                     创建分享链接
   6.20 GET  /s/{token}                         分享播放页
   6.21 POST /api/v1/videos/{id}/progress       上报播放位置
   6.22 GET  /api/v1/videos/{id}/progress       读取播放位置
   6.23 GET  /api/admin/queue                   队列总览
   6.24 PUT  /api/admin/settings/transcode      调整并发与档位模板

7. 数据模型概览
   7.1 users(id TEXT PK, username UNIQUE, password_hash, role TEXT, created_at)
   7.2 uploads(id TEXT PK, user_id FK, filename TEXT, size_bytes BIGINT, sha256 TEXT,
       chunk_size INT, total_chunks INT, received_chunks INT, state TEXT, tmp_dir TEXT,
       created_at, expires_at)
   7.3 videos(id TEXT PK, user_id FK, title TEXT, description TEXT, tags_json TEXT,
       original_path TEXT, original_size BIGINT, sha256 TEXT, duration_ms INT,
       width INT, height INT, fps REAL, video_codec TEXT, audio_codec TEXT,
       bitrate INT, rotation INT, cover_path TEXT, sprite_path TEXT, vtt_path TEXT,
       state TEXT, probe_json TEXT, created_at, updated_at, deleted_at TEXT NULL)
       索引 idx_user_created(user_id, created_at desc)、idx_state(state)
   7.4 transcode_jobs(id TEXT PK, video_id FK, renditions_json TEXT, state TEXT,
       priority INT, progress INT, queued_at, started_at, finished_at, error TEXT,
       requested_by TEXT)
   7.5 renditions(id PK, job_id FK, video_id FK, name TEXT, width INT, height INT,
       video_bitrate INT, audio_bitrate INT, playlist_path TEXT, segment_count INT,
       duration_ms INT, output_bytes BIGINT, state TEXT, progress INT, ffmpeg_cmd TEXT,
       log_path TEXT, elapsed_s REAL, error TEXT)
       唯一键 (job_id, name)
   7.6 play_events(id PK, video_id FK, user_id TEXT NULL, session_id TEXT, event TEXT,
       position_ms INT, rendition TEXT, bytes BIGINT, ip_hash TEXT, created_at)
   7.7 watch_progress(id PK, video_id FK, user_id FK, position_ms INT, updated_at)
       唯一键 (video_id, user_id)
   7.8 shares(id TEXT PK, token TEXT UNIQUE, video_id FK, user_id FK, expires_at TEXT,
       state TEXT, views INT, created_at)
   7.9 audit_log(id PK, user_id, action, target_type, target_id, detail_json, ip,
       created_at)
   7.10 说明：renditions.ffmpeg_cmd 保存实际执行的命令模板（用于复现与排查），但不保存
        用户目录之外的敏感信息；play_events 表按天归档，保留 180 天。

【三、里程碑拆解（建议 4 ~ 6 个阶段）】

阶段一：上传与探测（约 20 小时）
  产出：分片上传会话与断点续传、合并与 sha256 校验、ffprobe 封装与元信息解析、
       上传后确认页面、外部依赖检测与降级提示。
  验收：上传 3 GB 视频可断点续传并校验一致；探测结果与实际一致（含旋转元数据）。

阶段二：ffmpeg 封装与单档位转码（约 24 小时）
  产出：ffmpeg 命令构建、子进程执行与取消、进度解析（-progress 管道）、日志落盘、
       单档位 HLS 输出与产物校验。
  验收：一个 720p 档位转码成功，playlist.m3u8 可被 hls.js 播放；进度百分比与 ffmpeg 输出
       误差小于 2%。

阶段三：多档位与播放服务（约 24 小时）
  产出：码率阶梯与 master.m3u8、档位并发控制、播放资源路由（MIME/CORS/缓存/Range）、
       播放页与画质切换、封面与雪碧图、WebVTT 悬停预览。
  验收：三档位转码完成，播放器可在自动模式下于弱网切换档位；进度条悬停显示预览图。

阶段四：任务编排与容错（约 22 小时）
  产出：任务状态机、队列与优先级、失败档位重试、取消、服务重启后的中断恢复、SSE 进度
       推送、磁盘空间检查与配额。
  验收：kill 转码进程后重启服务，任务自动恢复；取消任务后无残留 ffmpeg 进程与临时文件。

阶段五：管理端与统计（约 20 小时）
  产出：队列总览、任务详情与日志、并发与档位模板设置、存储管理与清理任务、播放统计与
       热门排行、分享管理与失效。
  验收：管理端显示的队列状态与数据库一致；清理任务可释放空间且不误删在用分片。

阶段六：测试、性能与部署（约 18 小时）
  产出：覆盖率报告、转码端到端测试（含失败注入）、并发转码压测、Docker 镜像与 Nginx
       配置、部署与容量规划文档（CPU、磁盘、带宽估算）。
  验收：4 个 1080p 任务按配置并发执行时系统稳定；按文档部署后可用公网地址播放（本地
       环境用局域网验证）。

【四、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；类型注解全覆盖；转码相关代码必须与 Web 层解耦，可被
   命令行与测试直接调用。
2. 允许使用的库：标准库（subprocess、shutil、json、hashlib、os、pathlib、logging、
   threading、queue、sqlite3、secrets）；第三方限 FastAPI、uvicorn、SQLAlchemy、alembic、
   pydantic、redis、APScheduler、httpx、python-multipart、pytest、pytest-asyncio。
   转码必须通过 ffmpeg 与 ffprobe 命令行完成；禁止引入 moviepy、ffmpeg-python、opencv-python
   作为转码实现（可以用它们做帧抽取的替代方案，但不得作为主转码路径），禁止用 Python 逐帧
   编解码视频。
3. 禁止事项：禁止在请求线程中同步执行 ffmpeg；禁止用 shell=True 拼接命令（必须使用参数
   列表避免命令注入）；禁止把用户提供的文件名直接拼进路径或命令；禁止在转码未完成时把
   视频标记为可播放；禁止删除仍被 m3u8 引用的分片；禁止把 ffmpeg 的完整输出无限写入数据库
   （只存末尾 50 行与摘要）。
4. 子进程要求：ffmpeg 调用必须设置超时（默认按 时长 × 5 倍 与 30 分钟取较大者）、限制
   并发数、捕获 stdout 与 stderr、在取消时先 terminate 再 kill；Windows 下需正确处理
   进程树终止；每次调用记录命令行参数列表（避免拼接字符串）与真实耗时。
5. 代码组织：services/ffmpeg.py 是唯一构造与执行 ffmpeg 命令的模块；transcode.py 负责任务
   编排与状态流转；playback.py 只负责资源响应，不做转码判断；worker.py 是独立进程入口，
   与 API 进程通过数据库任务表协作。
6. 状态机约束：video.state ∈ {uploaded, probing, probed, queued, transcoding, ready,
   partial, failed, deleted}；rendition.state ∈ {pending, running, done, failed, cancelled,
   interrupted}；非法迁移必须抛异常并记录日志。
7. 编码规范：PEP 8；公有函数必须有类型注解与 docstring（注明可能抛出的 TranscodeError 等
   自定义异常）；日志使用结构化格式并带 video_id、job_id、rendition；禁止 print。
8. 测试要求：覆盖率 ≥ 75%；必须包含：ffmpeg 命令构建测试（断言参数列表正确，含关键帧
   对齐与 HLS 参数）、进度解析测试（用预置的 -progress 输出样本，包含异常行）、状态机
   测试、取消与超时测试、失败注入测试（构造损坏视频文件）、m3u8 产物校验测试（分片数
   与时长累加一致）、上传断点续传测试、播放接口 MIME 与 Range 测试。CI 环境若无 ffmpeg，
   相关测试必须跳过而不是失败（用 pytest.mark.skipif 明确标注）。
9. 性能要求：单机 4 核 8 GB；1080p 源视频转三档的总耗时不超过源时长的 2.5 倍（不含 I/O
   瓶颈）；HLS 分片静态响应在局域网上支持 50 并发播放而无明显卡顿；列表接口 P95 ≤ 150 ms；
   进度更新写入频率不超过每 2 秒一次，避免写库放大。
10. 存储与容量：磁盘剩余空间低于 disk_reserve_bytes（默认 5 GB）时拒绝新上传与转码并明确
    提示；转码产物大小估算为源文件 60% ~ 110%，文档给出容量规划表（按 100 个 1080p 视频
    估算占用）。
11. 安全与隐私：视频内容属于用户私有数据，播放资源必须校验所有权或有效分享令牌，禁止
    通过可猜测路径直接访问他人视频（路径中使用随机 video_id 并做鉴权）；分享令牌使用
    secrets 生成、可设有效期并可随时失效；上传文件类型按容器与 ffprobe 双重校验；下载与
    播放响应设置 Content-Disposition 与 X-Content-Type-Options；play_events 中的 IP 只保存
    不可逆哈希（合规最小化）；提供视频删除（含物理文件与派生分片清理）与账号注销能力；
    文档明确存储保留策略（原片默认 30 天、播放日志 180 天、删除后 7 天内从备份清除）。

【五、设计要点】

1. 数据结构：
   1.1 RenditionSpec(name, width, height, video_bitrate, audio_bitrate, maxrate, bufsize,
       preset, profile)。默认档位定义在配置文件中，渲染为 ffmpeg 参数。
   1.2 ProbeResult(duration_ms, width, height, fps, video_codec, pix_fmt, audio_codec,
       sample_rate, channels, bitrate, rotation, raw_json)。
   1.3 TranscodePlan(video_id, renditions: list[RenditionSpec], skip_reasons:
       dict[str, str])：源分辨率低于档位时记录跳过原因（如“源 480p 不放大到 720p”）。
   1.4 ProgressSample(out_time_ms, fps, speed, frame, total_size, bitrate)：从 -progress
       管道解析得到。
   1.5 路径约定函数：hls_dir(video_id, rendition)、segment_path(video_id, rendition, i)、
       cover_path(video_id)，集中管理避免路径拼接散落各处。
2. 关键算法与流程：
   2.1 上传流程：创建会话 → 客户端按 chunk_size 切分 → 每片 PUT 并记录 received_chunks 位图
       → complete 时校验分片齐全与整体 sha256 → 移动到 storage/originals/{video_id}/source
       → 触发探测任务。
   2.2 探测流程：ffprobe 输出 JSON → 解析首个视频流与首个音频流 → 提取旋转元数据（手机
       竖屏视频常见 rotate=90，需在转码时用 -vf 旋转或依赖容器 display matrix）→ 计算宽高比
       → 落库并生成封面。
   2.3 转码命令（以 720p 为例）：
       ffmpeg -y -i source.mp4 -vf "scale=-2:720,format=yuv420p" -c:v libx264 -preset medium
       -profile:v main -b:v 2500k -maxrate 2675k -bufsize 3750k -g 48 -keyint_min 48
       -sc_threshold 0 -force_key_frames "expr:gte(t,n_forced*6)" -c:a aac -b:a 128k
       -ac 2 -ar 48000 -f hls -hls_time 6 -hls_playlist_type vod -hls_flags
       independent_segments -hls_segment_filename "seg_%05d.ts" playlist.m3u8
       -progress pipe:1 -nostats
       说明：-g 与关键帧对齐保证分片可独立解码与平滑切换。
   2.4 进度计算：percent = out_time_ms / duration_ms × 100（上限 100）；ETA = (duration_ms -
       out_time_ms) / (speed × 1000) 秒；speed 小于 0.1 时视为异常并记录警告（可能磁盘或
       CPU 瓶颈）。
   2.5 master.m3u8 组装：读取各档位 playlist 的 BANDWIDTH 与分辨率，按码率升序写入
       EXT-X-STREAM-INF，附带 CODECS 与 RESOLUTION 属性；生成后做一次语法自检（必须含
       EXT-X-VERSION、EXT-X-ENDLIST）。
   2.6 雪碧图生成：先用 ffprobe 得到时长 → 每 10 秒抽一帧（fps=1/10）→ scale=160:90 →
       tile=10xN 输出 sprite.jpg；同时生成 thumbs.vtt，格式为
       "00:00:00.000 --> 00:00:10.000" 换行 "sprite.jpg#xywh=0,0,160,90"。
   2.7 取消与清理：取消时先 terminate 子进程，等待 5 秒，未退出则 kill；随后删除该 rendition
       目录下的部分产物（保留其他已完成档位）。
   2.8 重启恢复：worker 启动时把 state='running' 的 rendition 置为 interrupted 并检查产物
       完整性（playlist 是否存在且可解析、分片数是否与时长匹配），完整则直接标记 done，
       否则重新入队。
   2.9 播放鉴权：/media/hls/... 路径带 video_id，服务端在返回 m3u8 前校验所有权或分享
       令牌（令牌可通过 query 参数或 Cookie 传递）；分片请求通过签名的短时 URL 参数校验
       （hmac 签名带过期时间），避免每次分片请求都查库。
3. 数据模型与索引：见功能清单第 7 节；补充：
   3.1 renditions 对 (job_id, name) 建唯一索引，防止重复档位。
   3.2 videos.sha256 建非唯一索引（同一文件可被不同用户上传，用于秒传提示与去重统计）。
   3.3 play_events 按 (video_id, created_at) 建索引用于统计；表按天归档并压缩历史数据。
   3.4 watch_progress 对 (video_id, user_id) 建唯一索引，上报使用 upsert 语义。
4. 接口设计要点：
   4.1 转码提交返回 job_id 与 renditions 计划；客户端通过 SSE 订阅进度，SSE 断线后可用
       轮询兜底。
   4.2 m3u8 响应头：Content-Type: application/vnd.apple.mpegurl，Cache-Control: no-cache；
       ts 响应头：Content-Type: video/mp2t，Cache-Control: public, max-age=31536000,
       immutable（路径含 video_id 与档位，重新转码会生成新 job 目录或新版本号）。
   4.3 播放统计事件采用批量上报（客户端每 15 秒或暂停/结束时上报一次），降低请求量。
   4.4 所有涉及时长的接口统一以毫秒整数返回，避免浮点与格式歧义。

【六、运行方式与示例】

1. 安装前置
   Windows：winget install Gyan.FFmpeg      （或下载官网压缩包并加入 PATH）
   Linux：  sudo apt install ffmpeg
   验证：   ffmpeg -version && ffprobe -version
2. 安装与初始化
   python -m venv .venv && .venv\Scripts\activate
   pip install fastapi uvicorn sqlalchemy alembic pydantic redis apscheduler httpx
   pip install python-multipart pytest pytest-asyncio
   copy .env.example .env      （填写 DB_URL、STORAGE_ROOT、FFMPEG_PATH）
   alembic upgrade head
3. 启动（API 与转码工作进程分开）
   uvicorn app.main:app --host 127.0.0.1 --port 8040
   python -m app.worker --concurrency 1
   浏览器访问 http://127.0.0.1:8040
4. 命令行转码（便于测试）
   python -m app.cli probe --file D:\video\demo.mp4
   python -m app.cli transcode --file D:\video\demo.mp4 --renditions 360p,720p
          --out D:\video\out
5. 示例一（创建上传会话与分片上传）
   请求：POST /api/v1/uploads
   {"filename": "demo.mp4", "size": 734003200, "sha256": "9f1c...", "chunk_size": 8388608}
   响应：201 {"upload_id": "up-7b21", "chunk_size": 8388608, "total_chunks": 88}
   PUT /api/v1/uploads/up-7b21/chunks/0（二进制）
   响应：200 {"received": 1, "total": 88}
   中断后查询：GET /api/v1/uploads/up-7b21
   响应：200 {"received_chunks": 31, "total_chunks": 88, "missing": [31, 32, "..."]}
6. 示例二（探测结果）
   请求：GET /api/v1/videos/vd-33af/probe
   响应：200
   {"duration_ms": 754000, "width": 1920, "height": 1080, "fps": 29.97,
    "video_codec": "h264", "pix_fmt": "yuv420p", "bitrate": 8200000,
    "audio_codec": "aac", "sample_rate": 48000, "channels": 2, "rotation": 0,
    "has_video_stream": true}
7. 示例三（转码进度事件流）
   请求：GET /api/v1/transcode/jobs/jb-51c0/events（SSE）
   事件：
   data: {"job_id":"jb-51c0","rendition":"720p","state":"running","progress":37,
          "out_time_ms":279000,"speed":1.42,"eta_seconds":334}
   data: {"job_id":"jb-51c0","rendition":"720p","state":"done","progress":100,
          "output_bytes":231000000,"elapsed_s":531}
   data: {"job_id":"jb-51c0","state":"ready","playlist":"/media/hls/vd-33af/master.m3u8"}
8. 示例四（播放清单与分片）
   请求：GET /media/hls/vd-33af/master.m3u8
   响应：200 Content-Type: application/vnd.apple.mpegurl
   #EXTM3U
   #EXT-X-VERSION:3
   #EXT-X-STREAM-INF:BANDWIDTH=944000,RESOLUTION=640x360,CODECS="avc1.4d401f,mp4a.40.2"
   360p/playlist.m3u8
   #EXT-X-STREAM-INF:BANDWIDTH=2675000,RESOLUTION=1280x720,CODECS="avc1.4d401f,mp4a.40.2"
   720p/playlist.m3u8
   请求：GET /media/hls/vd-33af/720p/seg_00012.ts
   响应：200 Content-Type: video/mp2t Cache-Control: public, max-age=31536000, immutable
9. 示例五（异常输入）
   上传 .txt 改名为 .mp4 的文件
   响应：400 {"code": "UNSUPPORTED_FORMAT", "message": "文件不包含可识别的视频流"}
   磁盘空间不足（剩余 2 GB，低于保留阈值 5 GB）
   响应：507 {"code": "DISK_FULL", "message": "存储空间不足，请先清理后再上传",
         "detail": {"free_bytes": 2147483648, "reserve_bytes": 5368709120}}
   转码失败（源文件损坏，ffmpeg 退出码 1）
   响应：200（任务创建成功）
   任务状态：{"job_id": "jb-92aa", "state": "failed",
         "renditions": [{"name": "720p", "state": "failed",
         "error": "Invalid data found when processing input",
         "log_tail": ["[h264 @ ...] error while decoding MB 12 3", "..."]}]}

【七、验收标准】

[ ] 1. 上传 3 GB 视频可在中断后继续，最终 sha256 与本地一致，合并后可直接被 ffprobe 读取。
[ ] 2. 探测结果与实际一致（时长误差 ≤ 1 秒、分辨率完全一致、旋转元数据正确识别）。
[ ] 3. 三档位转码产出完整目录结构，master.m3u8 含三个 EXT-X-STREAM-INF 且分辨率与码率
      正确。
[ ] 4. 使用 hls.js 在 Chrome 中可播放并手动切换画质；Safari 中可原生播放同一 m3u8。
[ ] 5. 每个档位的分片总时长与源视频时长差异 ≤ 1%（关键帧对齐校验通过）。
[ ] 6. 转码进度百分比与 ffmpeg 实际输出时间匹配（误差 ≤ 2%），ETA 估算合理。
[ ] 7. 取消任务后 10 秒内无 ffmpeg 残留进程，取消档位的部分产物被清理，其他档位不受影响。
[ ] 8. 转码过程中 kill 工作进程并重启，任务自动恢复且已完成的档位不重做。
[ ] 9. 失败任务可通过接口只重试失败档位，重试成功后视频状态变为 ready 或 partial。
[ ] 10. 封面与雪碧图生成正确，进度条悬停可显示对应时间点预览图（VTT 描述可解析）。
[ ] 11. 播放资源的 MIME 与缓存头正确；ts 分片支持长期缓存，m3u8 不被长期缓存。
[ ] 12. 非所有者未携带分享令牌访问 /media/hls/... 返回 403；分享过期返回 410。
[ ] 13. 磁盘空间低于保留阈值时拒绝上传与转码，返回 DISK_FULL 且不产生残留临时文件。
[ ] 14. pytest 覆盖率 ≥ 75%，含命令构建、进度解析、状态机、取消超时、m3u8 校验五类专项
      测试；无 ffmpeg 环境下相关测试被正确跳过。
[ ] 15. 提供部署文档与容量规划：包含 ffmpeg 安装、Nginx 配置、CPU/磁盘/带宽估算表，且
      按文档可在 4 核机器上稳定运行 1 路 1080p 转码与 20 路并发播放。

【八、可选扩展】

1. 增加 DASH（MPEG-DASH）输出与 fMP4 分片，比较 HLS 与 DASH 的兼容性与切换体验。
2. 增加硬件加速转码（NVENC/QSV/VideoToolbox）的自动探测与回退策略，量化加速比。
3. 增加字幕处理：抽取内嵌字幕、生成 WebVTT、支持多语言字幕切换。
4. 增加自适应码率优化：基于播放统计数据（卡顿率、切换次数）自动调整码率阶梯。
5. 增加弹幕与章节标记（基于 WebVTT chapters），以及播放列表与播放队列。
6. 增加对象存储后端与 CDN 回源配置，比较本地直出与 CDN 分发的差异。
7. 增加视频指纹（感知哈希）用于重复上传检测与版权提示。

【九、涉及知识点】

- 多媒体基础：容器与编码（MP4/H.264/AAC）、码率与分辨率、关键帧与 GOP、像素格式
- HLS 协议：m3u8 清单结构、分片与独立分段、master 播放列表、码率阶梯与自适应切换
- ffmpeg 使用：命令行参数组织、滤镜（scale/format/tile/fps）、HLS 输出、-progress 进度
- 进程管理：subprocess 参数列表调用、超时与进程树终止、并发控制、日志采集与截断
- 后台任务：队列与优先级、状态机、失败重试、服务重启后的任务恢复与幂等
- Web 播放：hls.js 与 MSE、Range 请求、MIME 与缓存策略、CORS、SSE 进度推送
- 存储与容量：大文件分片上传与校验、目录规划、磁盘水位保护、清理与归档策略
- 安全与合规：资源鉴权与签名 URL、分享令牌与失效、IP 哈希化、数据保留与删除流程
================================================================================
