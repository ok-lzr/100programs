================================================================================
项目编号：099                    难度等级：★★★★★（大型项目）
项目名称：轻量 CI/CD 流水线与代码托管
所属分类：DevOps 工具 / 平台工程 / 版本控制
建议工时：3 ~ 4 周（约 120 ~ 180 小时）
运行环境：Python 3.10+    第三方依赖：FastAPI、uvicorn、SQLAlchemy、alembic、pydantic、dulwich、APScheduler、Jinja2、pytest、httpx、python-multipart、passlib、python-jose
================================================================================

【一、项目背景与目标】

小团队自建 Git 服务后往往只解决了“代码放哪里”，却没有解决“提交之后自动跑什么”。手工
部署的典型流程是：有人推代码 → 在群里喊一声 → 另一个人登录服务器 git pull → 跑测试 →
手工重启服务 → 出问题回滚靠记忆。这个流程的问题不是慢，而是不可追溯：没人知道线上跑
的是哪个提交、那次构建用了什么参数、失败时日志在哪、回滚到哪个版本是安全的。持续集成
的价值就在于把这条链路固化成可重复、可审计的流水线。

本项目的目标是实现一个轻量的代码托管与 CI/CD 平台：提供 Git 仓库托管（HTTP 智能协议：
clone、fetch、push）、仓库与成员管理、以 YAML 定义的流水线、触发器（push、tag、手动、
定时）、隔离的构建执行器、日志实时查看、制品归档与下载、构建历史与状态徽章。系统要在
单机部署下完成“push 代码 → 自动触发构建 → 执行测试 → 归档制品 → 通知结果”的闭环，并
保证构建过程可复现（同一提交与同一流水线定义产出相同结果）与可追溯（每个构建绑定提交
哈希、触发人、流水线版本与执行环境快照）。

安全是本项目的重中之重：CI 系统本质上是“让别人在你的机器上执行代码”，因此本项目对
构建隔离提出明确要求：构建在受限工作目录内执行，禁止访问外部网络（可配置白名单）、
禁止读取平台自身的密钥文件、限制执行时间与磁盘占用，所有流水线引用的密钥（如部署
Token）必须以加密形式存储、在日志中自动脱敏、且默认不注入到拉取请求类构建中。

目标用户是：需要自建代码托管与自动化流程的小团队、想理解 Git 协议与 CI 执行器原理的
开发者、以及把本项目当作部署自动化练习的学习者。项目明确不做：不做分布式构建集群
（单机多执行器）、不做容器镜像仓库（制品为文件归档）、不做代码审查工作流（合并请求的
评论与审批）、不做企业级权限矩阵（角色只分 owner、maintainer、developer、reporter）。

【二、功能需求清单】

本系统按四个子系统拆分：代码托管（Git 服务）、流水线引擎（定义、触发与执行）、用户端
（Web 界面）、管理端与基础设施（存储、任务、安全与部署）。

1. 代码托管子系统（Git 服务）
   1.1 仓库管理：创建（可选初始化 README 与 .gitignore 模板）、重命名、归档（只读）、
       删除（二次确认，软删除保留 7 天）、转移所有者。
   1.2 HTTP 智能协议：实现 /{owner}/{repo}.git/info/refs?service=git-upload-pack 与
       git-receive-pack，以及 /{owner}/{repo}.git/git-upload-pack 与 git-receive-pack
       两个 POST 端点，使用 dulwich 处理 pkt-line 与包协商，使标准 git 客户端可直接
       clone、fetch、push。
   1.3 认证与授权：clone/fetch 支持匿名（公开仓库）与 HTTP Basic（私有仓库，用户名 +
       访问令牌）；push 必须认证且需要 developer 及以上角色；令牌可创建、命名、设置
       有效期与权限范围（只读/读写）、可随时吊销；密码登录仅用于 Web，Git 操作一律用令牌。
   1.4 推送校验：接收推送前校验对象完整性与大小（单仓库默认上限 2 GB）；拒绝非快进推送
       到受保护分支（除非有强制推送权限）；默认保护 main 与 release/* 分支。
   1.5 引用与提交浏览：Web 展示分支列表、标签列表、提交历史（分页，含作者、时间、消息
       首行）、单提交差异（diff 统计与逐文件补丁）、文件树浏览与单文件内容查看（带高亮
       提示但不做完整语法高亮）、raw 下载与单文件历史。
   1.6 推送事件：receive-pack 成功后触发 post-receive 处理：解析新旧引用 → 记录 push_event
       → 匹配流水线触发器 → 入队构建；同一推送包含多个分支更新时按分支分别触发。
   1.7 仓库统计：提交数、贡献者列表与提交分布、代码行数按扩展名统计、最近活动时间。
   1.8 大文件与钩子：单文件超过 50 MB 时提示使用制品而非仓库（不强制拒绝但记录告警）；
       不实现服务端钩子脚本（避免执行仓库内容），改用平台内置的流水线定义。

2. 流水线引擎子系统
   2.1 流水线定义：仓库根目录的 .ci/pipeline.yml（YAML）定义，字段包含 version、stages
       （阶段列表）、每个 stage 的 name、image_or_env（本平台使用 runtimes 声明，如
       python:3.10 表示使用本地 Python 3.10 解释器）、steps（脚本列表）、artifacts、cache、
       env、timeout、continue_on_error。
   2.2 变量与密钥：支持仓库级变量（明文，适用于非敏感配置）与密钥（加密存储，仅在运行时
       解密并注入环境变量）；支持在流水线中引用 ${VAR}；日志输出自动脱敏密钥值（替换为
       ***）；密钥默认不注入 pull_request 类触发（可显式允许）。
   2.3 触发器：push（指定分支模式，如 main 与 feature/*）、tag（如 v*）、手动触发（可传
       参数）、定时（cron 表达式，最小粒度 5 分钟，基于 APScheduler 实现）、以及上游构建
       成功后触发（depends_on）。
   2.4 条件执行：stage 级 when 条件支持 branch、tag、event、文件变更路径（paths 匹配，
       用于“仅在前端目录变更时构建前端”）。
   2.5 执行器：内置两种执行模式——local（在受限工作目录内以子进程执行，Windows 与 Linux
       均可运行）与 container（调用 docker run 在容器内执行，可选，Docker 不可用时提示）；
       执行器从构建任务表领取任务，支持并发（默认 2，可配置）。
   2.6 工作区：每个构建分配独立工作目录 workspaces/{build_id}/，先克隆仓库到指定提交
       （用 dulwich 本地克隆，避免网络往返），然后依次执行 steps；构建结束后按配置保留
       或清理（默认保留失败构建的工作区 3 天便于排查）。
   2.7 步骤执行：每一步在子进程中执行（Windows 用 cmd 或 pwsh，Linux 用 bash -e），设置
       工作目录、环境变量、超时（默认单步 30 分钟、整构建 2 小时）、输出流式写入日志文件
       并按行推送到 SSE；退出码非 0 视为失败并停止后续步骤（continue_on_error 除外）。
   2.8 阶段与并行：同一 stage 内步骤串行；不同 stage 默认串行且前一阶段失败则终止；支持
       在 stage 上声明 parallel: true 使其内部步骤并行（最多 4 个），并正确聚合日志前缀。
   2.9 缓存：支持缓存目录声明（如 .venv、node_modules），以 cache_key（分支 + 锁文件哈希）
       为键在 builds_cache/{key}.tar 存储，构建开始时解包、结束时打包；缓存命中率在构建
       详情中展示。
   2.10 制品：steps 完成后按 artifacts 声明的通配路径收集文件，打包为 zip 存入
       artifacts/{build_id}/，记录文件清单与总大小（单构建默认上限 500 MB）；提供下载与
       过期清理（默认 30 天）。
   2.11 失败与重试：构建失败保留完整日志与失败步骤标记；支持“重跑同一构建”（同提交同
       流水线版本）与“仅重跑失败阶段”（从失败阶段继续，工作区复用）。
   2.12 取消：支持取消排队中与运行中的构建；取消时终止当前步骤进程树并标记状态
       cancelled，已产出的日志与部分制品按配置保留。
   2.13 状态与通知：构建状态包括 queued、running、success、failed、cancelled、timeout；
       支持 webhook 通知（POST JSON 到配置的地址，含仓库、构建号、状态、提交、耗时）与
       站内通知列表；构建状态徽章接口返回 SVG（成功/失败/进行中）。
   2.14 可复现与追溯：构建记录提交哈希、流水线文件哈希、触发器、触发人、执行器类型、
       运行时版本、环境变量键名（不含值）、开始与结束时间、各步骤耗时。

3. 用户端子系统（Web 界面）
   3.1 登录注册：注册（可配置是否开放）、登录、令牌管理（创建/吊销）、个人资料。
   3.2 仓库列表页：我的仓库与参与的仓库，展示最近提交、分支数、最近构建状态徽章；
       支持搜索与按最近推送排序。
   3.3 仓库首页：README 渲染（Markdown 转 HTML，转义后渲染）、文件树、最近提交列表、
       分支与标签切换、克隆地址（HTTP 与令牌提示）。
   3.4 提交详情页：提交元信息、逐文件 diff（新增/删除行着色）、父提交跳转。
   3.5 流水线页：展示当前 .ci/pipeline.yml 解析结果（阶段与步骤树）、最近构建列表（状态、
       耗时、提交、触发人）、变量与密钥管理入口（密钥只显示名称与创建时间）。
   3.6 构建详情页：实时日志（SSE 流式，自动滚动，支持按步骤折叠与关键字搜索）、步骤耗时
       瀑布、制品列表与下载、缓存命中情况、重跑与取消按钮。
   3.7 触发器管理：可视化配置 push/tag/cron/manual 触发器，cron 用表达式输入并显示下次
       执行时间与最近 5 次执行记录。
   3.8 成员与权限：邀请成员、设置角色（owner/maintainer/developer/reporter）、移除成员、
       查看操作日志。
   3.9 徽章：为每个仓库的指定分支提供 /badge/{repo}/{branch}.svg 徽章，可嵌入 README。
   3.10 异常提示：流水线文件语法错误（给出错误行号与原因）、引用了未定义的变量、超时、
       磁盘不足、Docker 未安装等给出准确提示与建议。

4. 管理端与基础设施子系统
   4.1 平台总览：仓库数、用户数、构建总数与成功率、平均构建耗时、执行器占用率、磁盘
       占用（仓库、工作区、缓存、制品分项统计）。
   4.2 执行器管理：在线执行器列表、当前任务、心跳时间；支持停用某执行器（不再领取任务）
       与强制终止任务。
   4.3 磁盘与清理：工作区清理（按构建状态与保留策略）、过期制品清理、过期缓存清理、
       软删除仓库物理清理（7 天后）；清理任务记录释放空间。
   4.4 配额：单用户仓库数、单仓库大小、并发构建数、制品总量上限；超限时拒绝并提示。
   4.5 密钥安全：平台级密钥（webhook 签名密钥、数据库口令）来源为环境变量；检查并拒绝
       启动时存在默认弱口令；提供密钥轮换说明。
   4.6 审计：仓库创建删除、成员变更、密钥创建吊销、构建取消、强制推送、执行器停用等
       敏感操作写入 audit_log，保留 180 天。
   4.7 配置管理：config.toml 定义 data_root、db_url、max_repo_bytes、max_build_concurrency、
       workspace_retention_days、artifact_retention_days、cache_max_bytes、
       executor_mode、sandbox_allow_network、step_timeout_s、build_timeout_s。
   4.8 部署：Dockerfile 与 docker-compose（挂载 data 卷）；systemd 单元示例；镜像内需预装
       Python 运行时（供流水线使用）；文档说明执行器与 API 分离部署的方式。

5. 模块清单（源码结构）
   5.1 app/main.py                FastAPI 应用与生命周期、Git 协议端点挂载。
   5.2 app/config.py              配置与目录初始化、启动自检（弱口令、目录可写、磁盘余量）。
   5.3 app/models/                user、token、repository、member、push_event、pipeline、
                                  build、build_step、artifact、cache_entry、variable、
                                  secret、trigger、audit_log。
   5.4 git/handler.py             dulwich 封装：仓库初始化、引用读写、提交与 diff 读取。
   5.5 git/http.py                HTTP 智能协议的 info/refs 与 upload-pack/receive-pack 端点。
   5.6 git/hooks.py               推送后处理、引用解析、触发器匹配与构建入队。
   5.7 pipeline/parser.py         pipeline.yml 解析、模式校验、错误定位（行号与字段路径）。
   5.8 pipeline/model.py          Pipeline、Stage、Step、Trigger、Artifact、Cache 数据类。
   5.9 pipeline/executor.py       执行器主循环：领取任务、准备工作区、逐步执行、日志流。
   5.10 pipeline/runtime.py       子进程执行、流式日志、超时与进程树终止、环境变量注入与
                                  脱敏。
   5.11 pipeline/sandbox.py       受限执行策略：环境变量白名单、工作目录限制、可选网络
                                  禁用的实现与说明。
   5.12 pipeline/artifacts.py     制品收集、打包、清单与过期清理。
   5.13 pipeline/cache.py         缓存打包与解包、键计算与容量控制。
   5.14 app/api/                  auth、repos、commits、builds、triggers、secrets、admin。
   5.15 app/scheduler.py          cron 触发器与清理任务的 APScheduler 集成。
   5.16 web/                      Web 界面（原生 JS + fetch + EventSource 日志流）。
   5.17 tests/                    单元、接口、Git 协议、流水线解析、执行器与安全测试。

6. 接口清单（HTTP，节选核心）
   6.1 POST /api/v1/auth/register                注册
   6.2 POST /api/v1/auth/login                   登录
   6.3 POST /api/v1/tokens                       创建访问令牌
   6.4 DELETE /api/v1/tokens/{id}                吊销令牌
   6.5 POST /api/v1/repos                        创建仓库 {name, private, init_readme}
   6.6 GET  /api/v1/repos                        仓库列表
   6.7 GET  /api/v1/repos/{owner}/{repo}         仓库详情
   6.8 GET  /api/v1/repos/{owner}/{repo}/commits?ref=&page=  提交列表
   6.9 GET  /api/v1/repos/{owner}/{repo}/commits/{sha}       提交详情与 diff
   6.10 GET  /api/v1/repos/{owner}/{repo}/tree?ref=&path=    文件树
   6.11 GET  /api/v1/repos/{owner}/{repo}/raw/{ref}/{path}   原始文件
   6.12 GET  /{owner}/{repo}.git/info/refs?service=git-upload-pack    Git 协议
   6.13 POST /{owner}/{repo}.git/git-upload-pack                Git 协议
   6.14 POST /{owner}/{repo}.git/git-receive-pack               Git 协议（推送）
   6.15 GET  /api/v1/repos/{owner}/{repo}/pipeline             当前流水线解析结果
   6.16 PUT  /api/v1/repos/{owner}/{repo}/triggers             配置触发器
   6.17 POST /api/v1/repos/{owner}/{repo}/builds               手动触发构建
   6.18 GET  /api/v1/repos/{owner}/{repo}/builds?page=         构建列表
   6.19 GET  /api/v1/builds/{id}                               构建详情
   6.20 GET  /api/v1/builds/{id}/logs                          日志全文
   6.21 GET  /api/v1/builds/{id}/logs/stream                   SSE 实时日志
   6.22 POST /api/v1/builds/{id}/cancel                        取消构建
   6.23 POST /api/v1/builds/{id}/rerun                         重跑（可选 only_failed=true）
   6.24 GET  /api/v1/builds/{id}/artifacts                     制品列表
   6.25 GET  /api/v1/artifacts/{id}/download                   下载制品
   6.26 GET  /badge/{owner}/{repo}/{branch}.svg                状态徽章
   6.27 POST /api/v1/repos/{owner}/{repo}/secrets              创建密钥
   6.28 GET  /api/admin/overview                               平台总览
   6.29 GET  /api/admin/executors                              执行器列表

7. 数据模型概览
   7.1 users(id TEXT PK, username UNIQUE, email TEXT, password_hash, created_at, disabled INT)
   7.2 tokens(id TEXT PK, user_id FK, name TEXT, token_hash TEXT UNIQUE, scopes TEXT,
       expires_at TEXT NULL, last_used_at TEXT, revoked INT, created_at)
       （令牌只存哈希，前缀 8 位用于界面识别）
   7.3 repositories(id TEXT PK, owner_id FK, name TEXT, slug TEXT, private INT,
       description TEXT, default_branch TEXT, disk_bytes BIGINT, archived INT,
       deleted_at TEXT NULL, created_at, updated_at)  唯一键 (owner_id, slug)
   7.4 members(id PK, repo_id FK, user_id FK, role TEXT, created_at)
       唯一键 (repo_id, user_id)；role ∈ owner/maintainer/developer/reporter
   7.5 push_events(id PK, repo_id FK, user_id, ref TEXT, old_sha TEXT, new_sha TEXT,
       commit_count INT, created_at)  索引 (repo_id, created_at desc)
   7.6 pipelines(id PK, repo_id FK, file_sha TEXT, parsed_json TEXT, valid INT,
       error_json TEXT, created_at)  唯一键 (repo_id, file_sha)
   7.7 builds(id TEXT PK, repo_id FK, number INT, pipeline_id FK, trigger_type TEXT,
       trigger_user_id TEXT NULL, ref TEXT, sha TEXT, state TEXT, executor TEXT,
       env_keys_json TEXT, queued_at, started_at, finished_at, duration_ms INT,
       cache_hit INT, artifact_bytes BIGINT, error TEXT, rerun_of TEXT NULL)
       唯一键 (repo_id, number)；索引 (repo_id, created_at desc)、idx_state(state)
   7.8 build_steps(id PK, build_id FK, stage TEXT, name TEXT, step_index INT,
       state TEXT, exit_code INT NULL, started_at, finished_at, duration_ms INT,
       log_path TEXT, log_bytes BIGINT)  索引 (build_id, step_index)
   7.9 artifacts(id TEXT PK, build_id FK, name TEXT, path TEXT, size_bytes BIGINT,
       file_count INT, manifest_json TEXT, expires_at TEXT, download_count INT)
   7.10 cache_entries(id PK, repo_id FK, cache_key TEXT, path TEXT, size_bytes BIGINT,
       last_used_at TEXT, hits INT)  唯一键 (repo_id, cache_key)
   7.11 variables(id PK, repo_id FK, key TEXT, value TEXT, is_secret INT,
       created_at, updated_at)  唯一键 (repo_id, key)
       （is_secret=1 时 value 使用平台密钥加密存储，界面只显示名称）
   7.12 triggers(id PK, repo_id FK, type TEXT, config_json TEXT, enabled INT,
       last_fired_at TEXT)
   7.13 audit_log(id PK, user_id, repo_id TEXT NULL, action TEXT, target TEXT,
       detail_json TEXT, ip TEXT, created_at)
   7.14 磁盘布局：data/repos/{repo_id}.git（裸库）、data/workspaces/{build_id}/、
       data/artifacts/{build_id}/、data/cache/{repo_id}/{key}.tar、
       data/logs/{build_id}/{step_index}.log。

【三、里程碑拆解（建议 4 ~ 6 个阶段）】

阶段一：用户、仓库与 Git 协议（约 24 小时）
  产出：注册登录与令牌、仓库 CRUD、dulwich 裸库管理、HTTP 智能协议（clone/fetch/push）、
       私有仓库鉴权、受保护分支的非快进推送拒绝。
  验收：标准 git 客户端可 clone、commit、push、fetch；令牌权限与过期校验正确；无权用户
       推送被拒绝并给出明确错误。

阶段二：提交浏览与 Web 基础（约 20 小时）
  产出：分支与标签列表、提交历史分页、单提交 diff、文件树与 raw 下载、README 渲染、
       仓库统计。
  验收：一个含 200 次提交的仓库可在 1 秒内打开提交列表首页；diff 显示与 git 命令行一致。

阶段三：流水线解析与执行器（约 28 小时）
  产出：pipeline.yml 解析与校验（含错误行号）、工作区准备、步骤子进程执行与流式日志、
       超时与取消、执行器主循环与并发控制、手动触发构建。
  验收：一个含 3 阶段 6 步骤的流水线可完整执行；某步骤返回退出码 1 时后续步骤不再执行且
       构建状态为 failed；取消后 10 秒内无残留进程。

阶段四：触发器、密钥与制品缓存（约 24 小时）
  产出：push/tag/cron/manual 触发器、路径条件与分支模式、仓库变量与加密密钥、日志脱敏、
       缓存打包解包、制品收集与下载、webhook 通知与徽章。
  验收：push 到 main 自动触发构建；密钥值不出现在日志中；缓存命中时构建耗时明显下降；
       制品可下载且清单与实际文件一致。

阶段五：管理端、配额与清理（约 20 小时）
  产出：平台总览、执行器管理、配额校验、工作区/制品/缓存/软删除仓库清理任务、审计日志、
       启动自检（弱口令与目录权限）。
  验收：清理任务能正确释放空间且不删除未过期制品；配额超限时创建仓库或触发构建被拒绝。

阶段六：测试、安全加固与部署（约 22 小时）
  产出：覆盖率报告、Git 协议与流水线专项测试、安全测试（命令注入、路径穿越、密钥泄漏、
       越权）、并发构建压测、Docker 镜像与部署文档、执行器隔离说明与风险清单。
  验收：安全测试全部通过；2 个并发构建稳定运行；按文档部署后可用真实 git 客户端完成
       全流程。

【四、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；类型注解全覆盖；Git 操作统一通过 dulwich，禁止在
   业务代码中调用 git 命令行（便于在无 git 二进制的环境运行与测试）。
2. 允许使用的库：标准库（subprocess、shutil、tarfile、zipfile、hashlib、hmac、secrets、
   json、fnmatch、threading、queue、logging、sqlite3、signal、os）；第三方限 FastAPI、
   uvicorn、SQLAlchemy、alembic、pydantic、dulwich、APScheduler、Jinja2、passlib、
   python-jose、httpx、python-multipart、pytest、pytest-asyncio、PyYAML（解析 pipeline.yml）。
   禁止引入 GitLab、Gitea、Drone、Jenkins 等现成 CI 平台或其 SDK。
3. 禁止事项：禁止使用 shell=True 执行用户脚本（必须用参数列表或明确的语言解释器调用脚本
   文件）；禁止把用户提交的脚本内容拼进平台自身的命令字符串；禁止在日志中输出密钥值、
   令牌、密码（必须脱敏）；禁止把工作区路径与用户输入直接拼接（必须使用内部 build_id）；
   禁止在构建中默认注入平台级环境变量（只注入白名单与仓库声明的变量）；禁止执行仓库中的
   任意脚本作为服务端钩子（只允许流水线定义中声明的步骤）。
4. 流水线安全约束：密钥默认不注入 pull_request 类触发与来自 fork 的构建；构建执行器的
   环境变量白名单必须显式枚举（PATH、HOME、LANG、PYTHONPATH 等，不含平台的 DB_URL、
   JWT_SECRET 等敏感项）；单步与整构建必须有超时；工作区磁盘占用超过上限（默认 5 GB）时
   终止构建并标记 failed；可选开启网络禁用（Linux 下用 unshare 或容器模式实现，Windows
   下不支持的场景必须在文档中明确说明并给出替代建议）。
5. 代码组织：git/ 负责协议与仓库读写；pipeline/ 负责解析与执行，二者不互相依赖；执行器
   （executor）与 API 进程分离，通过数据库任务表与状态机协作；所有跨模块结构使用
   dataclass 或 pydantic 模型；单个模块不超过 500 行。
6. 状态机约束：build.state ∈ {queued, running, success, failed, cancelled, timeout}；
   build_step.state ∈ {pending, running, success, failed, skipped, cancelled, timeout}；
   非法迁移（如对 success 的构建再次标记 running）必须抛异常并记录告警。
7. 编码规范：PEP 8；公有函数必须有类型注解与 docstring；日志使用结构化格式并带 repo_id、
   build_id、step_index；执行器与 API 使用同一日志配置但输出到不同文件；禁止 print 调试。
8. 测试要求：覆盖率 ≥ 75%；必须包含：Git 协议测试（用 dulwich 客户端做 clone/push 往返）、
   pipeline.yml 解析测试（合法与 10 类错误定义）、步骤执行与超时/取消测试、日志脱敏测试
   （断言密钥值不出现在日志文件中）、命令注入测试（构造含分号与反引号的变量值，断言不会
   被执行）、路径穿越测试（变量值为 ../../ 时不得越出工作区）、并发领取任务测试（同一
   构建不被两个执行器执行）、制品与缓存测试。
9. 性能要求：单机 4 核 8 GB；100 MB 仓库的 clone ≤ 20 秒（本地回环）、push ≤ 30 秒；
   提交列表页 P95 ≤ 300 ms；日志流式推送延迟 ≤ 500 ms；支持 2 个并发构建与 5 个排队构建；
   单仓库默认上限 2 GB、平台数据目录默认上限 200 GB。
10. 隐私与合规：仓库内容与构建日志属于用户数据，平台默认不可读；管理员查看仓库文件需
    显式启用并在界面提示（默认关闭），所有查看行为记录审计日志；用户数据导出（仓库打包
    下载）与账号注销（删除其仓库、构建记录、制品与缓存）必须提供；日志与制品保留策略
    需明确（日志 90 天、制品 30 天、审计 180 天），删除后 7 天内从备份清除；不得把用户
    代码用于任何分析、训练或第三方用途。

【五、设计要点】

1. 数据结构：
   1.1 Pipeline(version, stages: list[Stage], triggers: list[Trigger], variables: dict)。
   1.2 Stage(name, steps: list[Step], parallel: bool, when: Condition | None, timeout_s)。
   1.3 Step(name, run: str, continue_on_error: bool, timeout_s, env: dict)。
   1.4 Condition(kind: branch|tag|event|paths, pattern: str | list[str])。
   1.5 BuildContext(build_id, repo_id, sha, ref, workspace: Path, env: dict, artifacts:
       list[Path], cache_dir: Path, logger)。
   1.6 RefUpdate(ref: str, old_sha: str, new_sha: str, deleted: bool, created: bool)。
2. 关键算法与流程：
   2.1 推送处理：receive-pack 完成 → 读取被更新的引用（dulwich 提供 get_refs 与对象访问）
       → 对每个非删除引用生成 RefUpdate → 判断是否受保护分支的非快进（old_sha 不是
       new_sha 的祖先）→ 记录 push_event → 匹配触发器（分支模式用 fnmatch）→ 创建 build
       记录（number 由仓库内计数器原子递增）→ 入队。
   2.2 构建执行：执行器轮询领取 queued 任务（UPDATE ... WHERE state='queued' LIMIT 1 并
       检查影响行数实现原子领取）→ 置 running → 准备工作区（dulwich 本地克隆 + checkout 到
       sha）→ 注入环境变量（仓库变量 + 密钥解密 + 平台白名单）→ 按 stage/step 顺序执行 →
       每一步写入 logs/{build_id}/{index}.log 并广播到内存中的 SSE 订阅者 → 收集制品 →
       打包缓存 → 汇总状态 → 触发 webhook。
   2.3 变量替换与脱敏：执行前对 run 脚本文本做 ${VAR} 替换（仅替换声明的变量，未声明变量
       保留原样并记录警告）；日志写入前对每个密钥值做字符串替换为 ***，同时替换其 base64
       与 urlencode 变体，避免通过编码绕过。
   2.4 进程树终止：记录子进程 pid，取消时先向进程组发送终止信号（Windows 用
       taskkill /T /F 或 psutil；无 psutil 时使用 subprocess 的 terminate + 轮询），等待
       5 秒后强制结束；确保不留孤儿进程占住工作区文件。
   2.5 缓存键计算：cache_key = sha1(branch + ':' + sha1(锁文件内容列表))，锁文件集合由
       pipeline 声明（如 requirements.txt、poetry.lock、package-lock.json）；缓存容量超限时
       按 last_used_at 淘汰最旧条目。
   2.6 重跑失败阶段：读取上次构建的 build_steps，跳过已 success 的步骤的前提是工作区可
       复用（保留策略命中）；若工作区已清理则退化为全量重跑并提示原因。
   2.7 cron 触发：APScheduler 为每个启用的 cron 触发器注册任务；调度时以触发器 id 与分钟
       时间戳做幂等键，避免多进程重复触发。
   2.8 徽章生成：查询分支最近一次构建状态 → 生成固定模板 SVG（文字与颜色随状态变化）→
       返回 Content-Type: image/svg+xml 与短缓存（60 秒）。
3. 数据库主要表结构：见功能清单第 7 节；补充约束与索引：
   3.1 builds 对 (repo_id, number) 唯一；number 使用仓库级计数器（在事务内 SELECT ... 
       FOR UPDATE 或 UPDATE ... RETURNING 递增）。
   3.2 原子领取任务的 SQL 必须带状态条件并使用 UPDATE 的返回行数判断，禁止“先查后改”。
   3.3 audit_log 建 (created_at) 索引用于按时间查询；构建日志不存数据库，只存文件与大小。
   3.4 软删除仓库的 deleted_at 与物理清理任务配合；清理前校验是否仍有 running 构建。
4. 接口与命令行设计要点：
   4.1 Git 协议端点必须返回正确的 Content-Type（application/x-git-upload-pack-advertisement
       等）与 Cache-Control: no-cache，否则 git 客户端会报 “invalid content-type”。
   4.2 SSE 日志流按 build_id 与 step_index 过滤；连接断开时停止推送并在客户端重连后按
       offset 续传（支持 ?offset= 参数）。
   4.3 命令行工具：python -m app.cli executor --mode local --concurrency 2；
       python -m app.cli run-pipeline --repo demo --sha HEAD --pipeline .ci/pipeline.yml
       （用于本地调试，不写数据库）。
   4.4 所有写接口需要鉴权并校验角色；令牌作用域（read/write）必须被执行器之外的接口尊重。

【六、运行方式与示例】

1. 安装与初始化
   python -m venv .venv && .venv\Scripts\activate
   pip install fastapi uvicorn sqlalchemy alembic pydantic dulwich apscheduler jinja2
   pip install passlib python-jose[cryptography] httpx python-multipart pyyaml pytest
   copy .env.example .env      （填写 DB_URL、JWT_SECRET、DATA_ROOT、WEBHOOK_SECRET）
   alembic upgrade head
   python -m app.cli init-admin --username admin --password ******
2. 启动
   uvicorn app.main:app --host 127.0.0.1 --port 8050
   python -m app.cli executor --mode local --concurrency 2
   浏览器访问 http://127.0.0.1:8050
3. 真实 git 客户端使用
   git clone http://127.0.0.1:8050/alice/demo.git
   cd demo
   （写入 .ci/pipeline.yml 后）
   git add . && git commit -m "add pipeline" && git push origin main
   推送后平台自动创建构建，可在 Web 界面查看实时日志。
4. 示例一（流水线定义 .ci/pipeline.yml）
   version: 1
   stages:
     - name: check
       steps:
         - name: lint
           run: python -m compileall -q src
         - name: unit-test
           run: python -m pytest -q tests
     - name: package
       steps:
         - name: build
           run: python -m build --wheel --outdir dist
       artifacts:
         - dist/*.whl
       cache:
         - .venv
   triggers:
     - type: push
       branches: [main, "feature/*"]
     - type: cron
       schedule: "0 3 * * *"
   timeout: 3600
5. 示例二（构建详情与实时日志）
   请求：GET /api/v1/builds/9f21c0
   响应：200
   {"build_id": "9f21c0", "repo": "alice/demo", "number": 42, "sha": "3f9a1c7",
    "ref": "refs/heads/main", "trigger_type": "push", "trigger_user": "alice",
    "state": "running", "executor": "local@host-34721", "started_at":
    "2025-01-15T10:02:11+08:00",
    "steps": [
      {"stage": "check", "name": "lint", "state": "success", "duration_ms": 4120,
       "exit_code": 0},
      {"stage": "check", "name": "unit-test", "state": "running", "duration_ms": 18300},
      {"stage": "package", "name": "build", "state": "pending"}
    ], "cache_hit": true}
   日志流：GET /api/v1/builds/9f21c0/logs/stream
   event: log
   data: {"stage":"check","step":"unit-test","line":"tests/test_api.py ....... [ 70%]"}
6. 示例三（构建成功与制品）
   请求：GET /api/v1/builds/9f21c0/artifacts
   响应：200
   {"items": [{"artifact_id": "af-31b2", "name": "dist/*.whl",
     "size_bytes": 4128896, "file_count": 1, "expires_at": "2025-02-14T10:05:00+08:00"}]}
   下载：GET /api/v1/artifacts/af-31b2/download → 200（application/zip）
7. 示例四（密钥与脱敏）
   创建密钥：POST /api/v1/repos/alice/demo/secrets
   {"key": "DEPLOY_TOKEN", "value": "s3cr3t-value-9f21"}
   响应：201 {"key": "DEPLOY_TOKEN", "created_at": "2025-01-15T09:00:00+08:00"}
   （响应中不返回 value，后续查询也只显示名称）
   流水线中 echo $DEPLOY_TOKEN 的日志实际内容：
   + echo ***
   ***
8. 示例五（异常输入与失败处理）
   场景 A：pipeline.yml 缩进错误
   GET /api/v1/repos/alice/demo/pipeline → 200
   {"valid": false, "error": {"line": 7, "column": 5,
    "message": "stages[0].steps[1] 缺少必填字段 run"}}
   场景 B：步骤超时（单步 30 分钟上限）
   构建状态：{"state": "failed", "steps": [{"name": "unit-test", "state": "timeout",
    "exit_code": null, "duration_ms": 1800000}]}
   场景 C：无权限推送受保护分支
   git push 输出：remote: pre-receive hook declined（平台返回 403 并附带原因：
   "main 为受保护分支，禁止强制推送"）

【七、验收标准】

[ ] 1. 标准 git 客户端可对平台仓库完成 clone、commit、push、fetch、pull，二进制文件
      （如 PNG）往返后哈希一致。
[ ] 2. 私有仓库匿名 clone 被拒绝；无效令牌返回 401；只读令牌 push 返回 403。
[ ] 3. 向受保护分支 main 强制推送被拒绝并给出明确原因；普通快进推送成功。
[ ] 4. push 到 main 后 10 秒内自动创建构建并进入 running 状态；分支模式匹配准确
      （feature/x 触发、featurex 不触发）。
[ ] 5. 三阶段流水线按顺序执行；某步骤失败后后续步骤被跳过并标记 skipped。
[ ] 6. pipeline.yml 语法错误时给出准确的行号与字段路径，且不创建构建。
[ ] 7. 密钥值在日志、数据库查询接口、错误信息中均不出现（仅显示 *** 与名称）。
[ ] 8. 构造变量值包含 ";"、"&&"、"$(echo x)" 时不会被当作命令执行（命令注入测试通过）。
[ ] 9. 取消运行中的构建后 10 秒内进程被终止、状态为 cancelled、工作区无被占用文件。
[ ] 10. 单步超时与整构建超时均生效并正确标记 timeout。
[ ] 11. 缓存命中时构建耗时相较未命中降低 ≥ 30%，缓存条目按容量上限淘汰最旧项。
[ ] 12. 制品打包清单与实际文件一致，下载后解压内容完整；过期制品被清理任务删除。
[ ] 13. 同一构建不会被两个执行器同时领取（并发领取测试 100 次无重复执行）。
[ ] 14. 提交列表页在含 5000 次提交的仓库上 P95 ≤ 300 ms；日志流式推送延迟 ≤ 500 ms。
[ ] 15. pytest 覆盖率 ≥ 75%，含 Git 协议、流水线解析、执行器、脱敏、注入、并发领取
      六类专项测试；清理任务与配额校验有独立测试。

【八、可选扩展】

1. 增加 Docker 执行器：在容器内执行流水线，实现更强的隔离与依赖一致性（含镜像缓存）。
2. 增加合并请求（Pull Request）：分支对比、评论、审批与“合并前必须通过检查”。
3. 增加构建矩阵：同一流水线按多组变量（Python 版本 × 操作系统）并行执行并汇总。
4. 增加部署阶段与制品发布：把制品推送到目标目录或远程主机（SSH/HTTP），支持灰度与回滚。
5. 增加依赖缓存代理与私有包索引，加速流水线安装依赖。
6. 增加代码质量门禁：集成覆盖率阈值、静态检查（ruff、mypy）结果作为阶段成败条件。
7. 增加构建性能分析：缓存命中率、步骤耗时趋势、失败原因分类统计与告警。

【九、涉及知识点】

- Git 内部原理：对象模型（blob/tree/commit）、引用与打包、pkt-line 协议、智能 HTTP 传输
- dulwich 使用：裸库初始化、引用读写、提交遍历、diff 生成、对象完整性与性能取舍
- 流水线设计：YAML 定义与校验、阶段与步骤模型、条件执行、缓存与制品、可复现性
- 进程与并发：子进程执行与流式输出、进程树终止、超时控制、原子领取任务与状态机
- 安全工程：命令注入防护、路径穿越防护、密钥加密存储与日志脱敏、最小权限注入、隔离
- Web 工程：FastAPI 流式响应（SSE）、大文件上传下载、鉴权与角色、Markdown 渲染与转义
- 运维实践：磁盘配额与清理策略、审计日志、备份与恢复、容量规划与部署文档
================================================================================
