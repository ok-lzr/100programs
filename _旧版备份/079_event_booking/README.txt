================================================================================
项目编号：079                    难度等级：★★★★☆（中型项目，偏难）
项目名称：会议室预约系统
所属分类：Web 后端 / 企业办公系统
建议工时：5 ~ 7 天
运行环境：Python 3.10+    第三方依赖：fastapi、uvicorn、sqlalchemy、pydantic、passlib[bcrypt]、python-jose[cryptography]、apscheduler、jinja2、openpyxl、pytest、httpx
================================================================================

【一、项目背景与目标】

公司里三间会议室门口的纸质登记表永远靠不住：有人写着"10:00-11:00"却开到 11:40，
有人在群里说一声就占用，行政要统计"会议室到底紧不紧张"只能靠猜。
更常见的是重复预约：两个人同时提交同一时段的申请，谁先谁后没个说法。

本项目实现一套会议室预约系统，核心能力是：
会议室与开放时间管理 → 按时间段预约 → 时段冲突检测（同一会议室不可重叠）→
审批流（提交 / 通过 / 驳回 / 取消）→ 日历视图（按房间或按我的预约）→
会前提醒（邮件或站内信）→ 使用统计（房间利用率、按时段热度）。

技术上最关键的一点是冲突检测：必须在数据库层面保证同一会议室同一时段只有一条有效预约，
应用层的"先查询再插入"在并发下必然出现问题。因此本项目要求使用条件插入 + 唯一约束
或 PostgreSQL 的排他约束（EXCLUDE USING gist）来彻底杜绝双重预约，
并在文档中写清每种数据库下的实现方案。第二难点是时间语义：
所有时间以 UTC 存储，业务时间按会议室所在时区展示，跨天与跨时区都要正确处理。

【二、功能需求清单】

1. 核心功能
   1.1 会议室管理：管理员维护会议室（名称、位置、容纳人数、设备清单、是否启用）。
   1.2 开放时间：每个会议室可配置可预约时段（如工作日 08:00-20:00、周末不开放），
       以及最长预约时长（默认 4 小时）与最小预约时长（默认 30 分钟）。
   1.3 预约创建：选择会议室、日期、开始与结束时间、主题、参会人数、参会人列表、备注。
   1.4 冲突检测：同一会议室时间段重叠的预约必须被拒绝（含审批中与已通过的预约）。
   1.5 审批流：需要审批的会议室提交后状态为 pending，管理员审批；
       不需要审批的会议室提交后直接 approved。
   1.6 取消与驳回：发起人可取消自己的预约（开始前 30 分钟内不可取消），
       管理员可驳回 pending 预约并填写原因。
   1.7 修改预约：仅允许 pending 状态的预约修改时间（修改后重新走冲突检测）。
   1.8 日历视图：按会议室显示某周的预约块；按用户显示"我的预约"日历。
   1.9 可用时段查询：给定房间与日期，返回该日的空闲时段列表（按 30 分钟粒度切分）。
   1.10 提醒：会前 15 分钟向参会人与发起人发送提醒（邮件或站内信），避免漏会。
   1.11 超时释放：会议结束时间已过但状态仍为 approved 的记录标记为 finished。
   1.12 统计：房间利用率（已预约时长 / 开放时长）、按小时的预约热度、
       按部门或人员的使用排名、审批通过率。
   1.13 权限：admin（管理会议室、审批全部）、manager（审批本部门）、user（预约自己的会议）。
   1.14 黑名单：连续 3 次预约后未到场（由管理员标记 no_show）的用户限制预约 7 天。

2. 输入与交互
   2.1 全部通过 JSON 交互（日历视图与统计页为 HTML）。
   2.2 创建预约请求：{"room_id":3,"subject":"周会","start_at":"2024-05-10T09:00:00+08:00",
       "end_at":"2024-05-10T10:00:00+08:00","attendee_count":8,
       "attendee_ids":[5,8,12],"external_attendees":["client@example.com"],"note":"讨论排期"}
   2.3 时间必须携带时区偏移（ISO 8601），服务端统一转换为 UTC 存储；
       不带时区的字符串返回 422，避免歧义。
   2.4 时间粒度：开始与结束时间必须落在 15 分钟网格上（如 09:00、09:15），
       否则返回 422 并提示最近的合法时间。
   2.5 查询参数：room_id、date（YYYY-MM-DD）、week（YYYY-Www）、status、page、page_size。
   2.6 交互方式：REST 接口 + 日历页 /calendar?room_id=3 + Swagger UI。

3. 输出与展示
   3.1 统一响应 { "code": 0, "message": "ok", "data": {...} }。
   3.2 预约响应：{"id":88,"room_id":3,"room_name":"A 会议室","subject":"周会",
       "start_at":"2024-05-10T01:00:00Z","end_at":"2024-05-10T02:00:00Z",
       "local_start":"2024-05-10T09:00:00+08:00","local_end":"2024-05-10T10:00:00+08:00",
       "status":"pending","organizer":{"id":5,"name":"张三"},
       "attendee_count":8,"attendees":[...],"need_approval":true,"created_at":"..."}
       说明：同时返回 UTC 与本地时间字段，前端直接使用 local_* 展示，避免时区换算错误。
   3.3 日历响应：{"room_id":3,"week":"2024-W19","days":[{"date":"2024-05-06",
       "slots":[{"start":"09:00","end":"10:00","booking_id":88,"subject":"周会",
       "status":"approved","organizer":"张三"}]}]}
   3.4 空闲时段响应：{"room_id":3,"date":"2024-05-10","open":"08:00-20:00",
       "busy":[{"start":"09:00","end":"10:00"}],
       "free":[{"start":"08:00","end":"09:00"},{"start":"10:00","end":"20:00"}]}
   3.5 统计响应：{"room_id":3,"range":"2024-05-01~2024-05-31",
       "open_hours":240,"booked_hours":126,"utilization":0.525,
       "hourly":[{"hour":9,"bookings":22},{"hour":10,"bookings":26}],
       "top_organizers":[{"user_id":5,"name":"张三","bookings":12,"hours":18.5}],
       "approval_rate":0.87}
   3.6 Excel 导出预约明细（含房间、时间、发起人、状态、是否 no_show）。

4. 异常与边界处理
   4.1 会议室不存在或已停用：404 / 40401；已停用返回 409 / 40901。
   4.2 结束时间早于或等于开始时间：422 / 42201。
   4.3 预约时长小于最小或大于最大时长：422 / 42202，data 返回允许区间。
   4.4 时间不在开放时段内（早于开放、晚于关闭、非工作日、落在午休禁约时段）：422 / 42203。
   4.5 时间未落在 15 分钟网格：422 / 42204，data 返回建议时间。
   4.6 时间段与已有预约重叠：409 / 40902，data 返回冲突的预约 id、时间段与发起人。
   4.7 参会人数超过会议室容量：422 / 42205，data 返回容量。
   4.8 开始时间早于当前时间（不允许预约过去）：422 / 42206。
   4.9 超过提前预约天数上限（默认 30 天）：422 / 42207。
   4.10 同一发起人在同一时段已有其它会议：409 / 40903（避免自己撞会）。
   4.11 取消已开始的预约：409 / 40904；取消开始前 30 分钟内的预约：409 / 40905。
   4.12 修改非 pending 预约的时间：409 / 40906。
   4.13 无审批权限的人调用审批接口：403 / 40301；审批自己的预约：403 / 40302。
   4.14 驳回未填写原因：422 / 42208（原因必填，长度 >= 5）。
   4.15 被限制预约的用户提交：403 / 40303，data 返回解禁时间。
   4.16 时间带时区缺失：422 / 42209，提示必须携带时区偏移。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：fastapi、uvicorn[standard]、sqlalchemy 2.0、pydantic v2、
   passlib[bcrypt]、python-jose[cryptography]、APScheduler（提醒与超时释放）、
   jinja2（日历页与统计页）、openpyxl（导出）、smtplib（标准库，邮件提醒）、
   pytest、httpx、alembic。
3. 时间处理：所有 datetime 必须为带时区的 aware 对象；数据库存储 UTC（TIMESTAMP WITH TIME ZONE）；
   配置项 DEFAULT_TIMEZONE（如 Asia/Shanghai）用于展示与开放时间判定。
   禁止使用 datetime.now()（无时区），统一使用 datetime.now(timezone.utc)。
4. 冲突检测（本项目的技术核心，必须实现第一或第二种）：
   方案一（推荐，PostgreSQL）：使用范围类型 + 排他约束
     CREATE EXTENSION IF NOT EXISTS btree_gist;
     ALTER TABLE bookings ADD CONSTRAINT no_overlap
       EXCLUDE USING gist (room_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&)
       WHERE (status IN ('pending','approved'));
     这是数据库级保证，任何并发路径都无法插入重叠预约。
   方案二（通用，SQLite 可用）：应用层条件插入 + 事务串行化
     在 BEGIN IMMEDIATE / SERIALIZABLE 事务内执行冲突查询并插入，
     同时为 (room_id, start_at) 建普通索引减少扫描；
     SQLite 场景必须设置 isolation_level=None 并手动 BEGIN IMMEDIATE，
     或用文件锁保证同一会议室同时只有一个写入者。
   无论采用哪种方案，都必须写一个并发测试用例（20 个线程抢同一时段）验证只成功 1 条。
5. 禁止事项：禁止仅用"先 SELECT 判断有没有冲突，再 INSERT"而不加事务与约束，
   这在本项目中属于不合格实现。
6. 禁止事项：禁止把时间当字符串比较（必须用 datetime 或数据库时间类型）。
7. 禁止事项：禁止在提醒任务中重复发送（必须有 sent 标记或独立提醒记录表）。
8. 代码组织（必须有以下模块）：
   app/main.py、app/config.py（时区、开放时间、网格粒度、提醒提前量、审批策略）
   app/database.py、app/models.py、app/schemas.py、app/deps.py
   app/core/timeslot.py（时间解析、网格对齐、开放时段判定、时长校验）
   app/core/conflict.py(冲突检测 SQL 构造与冲突信息查询，纯函数 + 仓储函数)
   app/services/room_service.py、booking_service.py、approval_service.py、
   availability_service.py、stats_service.py、notify_service.py
   app/core/scheduler.py（APScheduler：提醒任务、超时释放任务、no_show 统计）
   app/routers/auth.py、rooms.py、bookings.py、approvals.py、calendar.py、stats.py
   app/templates/calendar.html、booking_form.html、stats.html
   tests/test_timeslot.py、test_conflict.py、test_concurrency.py、
   test_approval.py、test_availability.py
9. 编码规范：所有函数带类型注解与 docstring；时间相关函数的 docstring 必须写明时区约定。
10. 编码规范：日志记录 booking_id、room_id、时间区间与操作人，禁止记录邮件正文。

【四、设计要点】

1. 数据结构（核心表与字段）
   表 users：
     id BIGINT PK、username VARCHAR(32) UNIQUE、password_hash VARCHAR(128)、
     real_name VARCHAR(32)、email VARCHAR(120)、department VARCHAR(64)、
     role VARCHAR(16)（admin / manager / user）、is_active BOOLEAN、created_at DATETIME
   表 rooms：
     id BIGINT PK、name VARCHAR(64) UNIQUE NOT NULL、location VARCHAR(120)、
     capacity INTEGER NOT NULL、equipment JSON NULL（["投影仪","白板","视频会议"]）、
     timezone VARCHAR(64) DEFAULT 'Asia/Shanghai'、
     need_approval BOOLEAN DEFAULT 0、approver_role VARCHAR(16) DEFAULT 'admin'、
     min_duration_minutes INTEGER DEFAULT 30、max_duration_minutes INTEGER DEFAULT 240、
     advance_days INTEGER DEFAULT 30、is_active BOOLEAN DEFAULT 1、created_at DATETIME
     约束：capacity > 0；min_duration < max_duration
   表 room_open_hours（开放时段，可多条表达午休禁约）：
     id BIGINT PK、room_id FK、weekday SMALLINT（0=周一 … 6=周日）、
     open_time TIME NOT NULL、close_time TIME NOT NULL、is_active BOOLEAN DEFAULT 1
     约束：open_time < close_time；UNIQUE(room_id, weekday, open_time, close_time)
     说明：一个工作日可配两条（08:00-12:00 与 13:30-20:00），中间即为午休不可约时段
   表 bookings：
     id BIGINT PK
     room_id FK(rooms.id) NOT NULL
     organizer_id FK(users.id) NOT NULL
     subject VARCHAR(200) NOT NULL
     note TEXT NULL
     start_at TIMESTAMPTZ NOT NULL（UTC）
     end_at TIMESTAMPTZ NOT NULL（UTC）
     local_date DATE NOT NULL（按房间时区计算的日期，便于按天查询与日历渲染）
     attendee_count INTEGER NOT NULL
     status VARCHAR(16) NOT NULL DEFAULT 'pending'
       （pending / approved / rejected / cancelled / finished / no_show）
     need_approval BOOLEAN NOT NULL
     approved_by FK(users.id) NULL、approved_at DATETIME NULL
     reject_reason VARCHAR(300) NULL
     cancelled_by FK(users.id) NULL、cancelled_at DATETIME NULL
     reminded_at DATETIME NULL（提醒已发送标记）
     no_show_marked_at DATETIME NULL
     created_at DATETIME、updated_at DATETIME
     约束：end_at > start_at
     索引：idx_bk_room_time(room_id, start_at, end_at)
           idx_bk_organizer(organizer_id, start_at)
           idx_bk_status_time(status, start_at)
           idx_bk_local_date(local_date)
     排他约束（PostgreSQL）：
           EXCLUDE USING gist (room_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&)
           WHERE (status IN ('pending','approved'))
   表 booking_attendees：
     id BIGINT PK、booking_id FK ON DELETE CASCADE、user_id FK NULL、
     external_email VARCHAR(120) NULL、is_required BOOLEAN DEFAULT 1、
     attended BOOLEAN NULL（会后由发起人确认签到）
     约束：user_id 与 external_email 至少有一个非空
     索引：idx_ba_user(user_id)、idx_ba_booking(booking_id)
   表 booking_logs（审计流水）：
     id BIGINT PK、booking_id FK、action VARCHAR(16)
       （create / update / approve / reject / cancel / finish / no_show / remind）、
     actor_id FK NULL、detail JSON NULL、created_at DATETIME
     索引：idx_bl_booking(booking_id, created_at)
   表 booking_restrictions（限制预约）：
     id PK、user_id FK、reason VARCHAR(200)、restricted_until DATETIME、
     created_at DATETIME、UNIQUE(user_id, restricted_until)
     表 notifications（站内信，邮件为可选通道）：
     id PK、user_id FK、booking_id FK NULL、title VARCHAR(200)、body TEXT、
     channel VARCHAR(16)（inapp / email）、is_sent BOOLEAN DEFAULT 0、
     sent_at DATETIME NULL、read_at DATETIME NULL、created_at DATETIME
     索引：idx_nt_user(user_id, is_sent, created_at)

2. 关键算法或流程
   时间解析与规范化：
     步骤 1：Pydantic 校验字符串必须能被 datetime.fromisoformat 解析且 tzinfo 不为 None，
             否则 422/42209。
     步骤 2：转换为 UTC：start_utc = start.astimezone(timezone.utc)。
     步骤 3：校验 15 分钟网格：分钟数 % 15 == 0 且秒与微秒为 0，否则 422/42204
             并在 data 中给出 floor/ceil 后的建议时间。
     步骤 4：计算 local_date = start_utc.astimezone(ZoneInfo(room.timezone)).date()。
   开放时段校验：
     步骤 1：取该房间该 weekday 的全部 room_open_hours（可能有两条）。
     步骤 2：把 start/end 转换为房间本地时间（Time 对象）。
     步骤 3：要求 [start_time, end_time] 完整落在同一条开放时段内
             （不允许跨午休，若需要跨午休请分两次预约）。
     步骤 4：时长 = (end_utc - start_utc).total_seconds() / 60，
             校验 min_duration <= 时长 <= max_duration。
     步骤 5：校验 start_utc > now_utc（允许最多 1 分钟的时钟偏差）且
             start_utc <= now_utc + advance_days 天。
   冲突检测（方案二通用实现，配合排他约束双保险）：
     步骤 1：开启事务（SQLite: BEGIN IMMEDIATE；PostgreSQL: 默认即可，靠约束兜底）。
     步骤 2：执行冲突查询（半开区间 [start, end) 重叠判定）：
       SELECT id, organizer_id, start_at, end_at, status, subject
       FROM bookings
       WHERE room_id = :room_id
         AND status IN ('pending','approved')
         AND start_at < :new_end AND end_at > :new_start
       LIMIT 5;
       注意区间语义：09:00-10:00 与 10:00-11:00 不冲突（半开区间），
       这正是采用 [start, end) 的原因，必须在文档与测试中明确。
     步骤 3：若查到记录，构造 409/40902，data 包含冲突列表（id、时间段、发起人、状态）。
     步骤 4：插入 bookings；若数据库返回排他约束冲突（PostgreSQL 的 23P01），
             同样映射为 409/40902（这是并发兜底路径）。
     步骤 5：同一发起人撞会检测：查询该 organizer 在同一时段 status IN ('pending','approved')
             的其它预约（不限房间），命中返回 409/40903。
     步骤 6：写入 booking_logs(action='create')，提交事务。
     步骤 7：若 need_approval=false，状态直接 approved 并发送确认通知；
             否则通知审批人。
   空闲时段计算（availability）：
     步骤 1：取该房间该日期的开放时段列表（可能多段）。
     步骤 2：查询该日 status IN ('pending','approved') 的预约，按 start_at 排序。
     步骤 3：对每一段开放时段，用"扫描线"扣除忙时段，得到空闲区间。
     步骤 4：把空闲区间按 15 分钟（可配置 30 分钟）网格切分成可预约槽位，
             丢弃时长小于 min_duration 的尾部碎片。
     步骤 5：返回 busy 与 free 两个数组（本地时间的 HH:MM 字符串），
             便于前端渲染时间轴。
   审批流：
     提交（create）→ need_approval ? pending : approved
     pending → approve（管理员/经理，写 approved_by、approved_at）→ approved
     pending → reject（原因必填）→ rejected
     pending/approved → cancel（发起人或管理员）→ cancelled
     approved → 时间已过（定时任务）→ finished
     approved → 管理员标记未到场 → no_show
     状态机变更必须校验当前状态（条件 UPDATE ... WHERE id=? AND status=?），
     例如审批只能对 pending 生效：
       UPDATE bookings SET status='approved', approved_by=:uid, approved_at=now()
       WHERE id=:id AND status='pending'；rowcount=0 时返回 409/40907（状态已变更）。
   提醒任务（APScheduler，每 5 分钟执行一次）：
     SELECT id, organizer_id, subject, start_at, local_date
     FROM bookings
     WHERE status='approved' AND reminded_at IS NULL
       AND start_at BETWEEN now() AND now() + INTERVAL '15 minutes'
       AND start_at > now();
     对每条：为发起人与全部内部参会人创建 notifications（channel='inapp'），
     若配置了 SMTP 则同时发送邮件（smtplib + EmailMessage，UTF-8 编码）。
     发送成功或失败都要写 reminded_at（避免重复轰炸），失败写 booking_logs 便于重试；
     邮件发送必须放在线程池中，禁止阻塞事件循环。
   超时释放任务（每小时）：
     把 status='approved' 且 end_at < now() 的记录置为 finished（条件 UPDATE，批量 500 条）。
     把 status='pending' 且 start_at < now() 的记录置为 rejected（原因自动填"超时未审批"）。
   no_show 判定：
     管理员在会议结束后 24 小时内标记 no_show；定时任务统计每个用户
     最近 30 天内 no_show 次数 >= 3 则插入 booking_restrictions（限制 7 天），
     并发送站内信告知；预约时校验 restrictions 未过期，命中返回 403/40303。
   统计计算：
     利用率 = sum(预约时长) / sum(开放时长)，仅统计 status IN ('approved','finished')；
     开放时长按 room_open_hours 与日期区间计算（排除周末与非开放时段）。
     按小时热度：SELECT EXTRACT(HOUR FROM start_at AT TIME ZONE :tz) AS h, COUNT(*)
     GROUP BY h（用房间时区换算，保证"9 点最忙"的口径正确）。
     审批通过率 = approved 数 / (approved + rejected) 数，pending 不计入分母。

3. 接口设计（HTTP 前缀 /api/v1；日历页在 /calendar）
   POST /api/v1/auth/register、POST /api/v1/auth/login
     返回 JWT（HS256，含 sub、role、department、exp），密钥读 JWT_SECRET_KEY（>= 32 字节）。
   POST /api/v1/rooms   需 admin
     请求：{"name":"A 会议室","location":"3F-东","capacity":12,
           "equipment":["投影仪","白板","视频会议"],"need_approval":true,
           "min_duration_minutes":30,"max_duration_minutes":240,
           "open_hours":[{"weekday":0,"open":"08:00","close":"12:00"},
                         {"weekday":0,"open":"13:30","close":"20:00"}]}
     响应 201：{"code":0,"data":{"room_id":3,"name":"A 会议室","capacity":12}}
     失败：409/40908（名称重复）、422/42210（开放时段非法，open >= close）。
   GET /api/v1/rooms?active=true   需登录
     响应 200：会议室列表（含容量、设备、是否需要审批、今日剩余可约时段数）。
   GET /api/v1/rooms/{room_id}   需登录
     响应 200：详情 + 完整开放时段配置；404/40401。
   PATCH /api/v1/rooms/{room_id}   需 admin
     请求：{"capacity":16,"need_approval":false,"is_active":false}
     行为：停用会议室时若存在未来的有效预约，返回 409/40909 并列出预约 id。
   PUT /api/v1/rooms/{room_id}/open-hours   需 admin
     请求：{"open_hours":[...]}（全量覆盖）；响应 200；422/42210。
   GET /api/v1/rooms/{room_id}/availability?date=2024-05-10   需登录
     响应 200：{"room_id":3,"date":"2024-05-10","timezone":"Asia/Shanghai",
              "open":[{"start":"08:00","end":"12:00"},{"start":"13:30","end":"20:00"}],
              "busy":[{"start":"09:00","end":"10:00","booking_id":88}],
              "free":[{"start":"08:00","end":"09:00"},{"start":"10:00","end":"12:00"},
                      {"start":"13:30","end":"20:00"}],"slot_minutes":15}
     失败：404/40401、422/42211（date 格式错误或超出可预约范围）。
   POST /api/v1/bookings   需登录
     请求：{"room_id":3,"subject":"周会","start_at":"2024-05-10T09:00:00+08:00",
           "end_at":"2024-05-10T10:00:00+08:00","attendee_count":8,
           "attendee_ids":[5,8,12],"external_attendees":["client@example.com"],
           "note":"讨论排期"}
     响应 201：{"code":0,"message":"预约已提交，等待审批","data":{...预约对象...}}
     失败：409/40902（时段冲突，data 含冲突列表）、409/40903（自己撞会）、
           422/42202（时长超限）、422/42203（不在开放时段）、422/42204（非 15 分钟网格）、
           422/42205（超容量）、422/42206（过去时间）、422/42207（超过提前预约上限）、
           403/40303（被限制预约）。
   GET /api/v1/bookings?room_id=3&date=2024-05-10&status=approved&page=1&page_size=20
     需登录
     响应 200：预约分页列表；普通用户默认只看到自己有权限查看的（自己发起或被邀请的），
             管理员可看全部。
   GET /api/v1/bookings/{booking_id}   需登录（发起人、参会人、管理员可看）
     响应 200：完整预约详情 + 审批记录；404/40401、403/40304。
   PATCH /api/v1/bookings/{booking_id}   需发起人
     请求：{"subject":"新主题","start_at":"...","end_at":"...","attendee_count":10,"note":"..."}
     行为：仅 status='pending' 可改时间（改后重新冲突检测）；approved 只允许改
           subject/note/参会人；修改写 booking_logs(action='update')。
     失败：409/40906（状态不允许修改时间）、409/40902（新时段冲突）。
   POST /api/v1/bookings/{booking_id}/cancel   需发起人或 admin
     请求：{"reason":"会议改期"}
     响应 200：{"code":0,"data":{"id":88,"status":"cancelled"}}
     失败：409/40904（会议已开始）、409/40905（开始前 30 分钟内不可取消，管理员可强制 force=true）、
           409/40907（状态已变更）。
   POST /api/v1/bookings/{booking_id}/approve   需 manager/admin
     请求：{"comment":"同意"}（可选）
     响应 200：{"code":0,"data":{"id":88,"status":"approved","approved_by":2}}
     失败：403/40301（无权限）、403/40302（审批自己的预约）、409/40907（状态已变更）、
           409/40902（审批时该时段已被其它预约占用，需人工介入）。
   POST /api/v1/bookings/{booking_id}/reject   需 manager/admin
     请求：{"reason":"该时段已安排全员大会"}
     响应 200：{"code":0,"data":{"id":88,"status":"rejected"}}
     失败：422/42208（原因缺失或过短）、409/40907。
   POST /api/v1/bookings/{booking_id}/no-show   需 admin
     请求：{"no_show":true}；响应 200；用于统计与限制策略。
   GET /api/v1/approvals/pending?page=1   需 manager/admin
     响应 200：待审批列表（按 start_at 升序，含冲突提示标记）。
   GET /api/v1/calendar?room_id=3&week=2024-W19   需登录
     响应 200：日历数据（见 3.3），含每天的预约块与状态色标。
   GET /api/v1/calendar/mine?week=2024-W19   需登录
     响应 200：我的预约日历（跨房间汇总）。
   GET /api/v1/stats/rooms?room_id=3&start=2024-05-01&end=2024-05-31   需 manager/admin
     响应 200：见 3.5 的统计结构。
   GET /api/v1/stats/export?start=2024-05-01&end=2024-05-31   需 manager/admin
     响应 200：xlsx 附件（预约明细 + 各房间利用率两个 Sheet）。
   GET /calendar   需登录
     行为：返回周视图日历 HTML（左侧会议室筛选，顶部上一周/下一周，点击空白时段弹出预约表单）。
   GET /api/v1/healthz   公开
     响应 200：{"status":"ok","db":"ok","scheduler":"running","timezone":"Asia/Shanghai"}

4. 鉴权方式与安全要求
   - 口令使用 bcrypt（rounds=12）；JWT HS256，JWT_SECRET_KEY 从环境变量读取且 >= 32 字节，
     缺失或为占位值时服务启动失败。
   - 角色权限：admin 管理会议室、审批全部、标记 no_show；
     manager 只审批本部门（校验 user.department 与被审批人部门关系，或审批人白名单）；
     user 只能创建/取消自己的预约并查看自己参与或本房间公开的预约。
   - 数据归属校验：取消、修改接口必须比对 organizer_id；审批接口必须校验审批人不等于发起人
     （自审自批是最常见的管理漏洞）。
   - 日历与列表接口不返回参会人的邮箱明文（只有管理员和发起人可见外部邮箱）。
   - 站内信与邮件发送必须做频率控制（同一预约同一通道只发一次，靠 reminded_at 与
     notifications.is_sent 双重保障）。
   - 邮件发送使用 smtplib + EmailMessage，SMTP 口令从环境变量读取；
     禁止在日志中打印 SMTP 口令与完整邮件正文。
   - 限流：创建预约 20 次/小时/用户；审批 200 次/小时/用户；
     可用时段查询 120 次/分钟/用户；统计与导出 10 次/小时/用户。
   - 预约主题与备注做长度限制与 HTML 转义（日历页渲染时），防止存储型 XSS。
   - 审计：所有状态变更写入 booking_logs，包含操作人、时间与变更详情（禁止只记状态）。

5. 错误处理与并发事务注意点
   - 冲突检测必须与插入在同一事务内完成，并配合数据库级约束（PostgreSQL 排他约束）
     或事务串行化（SQLite BEGIN IMMEDIATE），否则并发下必然出现双重预约。
   - 排他约束只作用于 status IN ('pending','approved')，因此取消/驳回后该时段立即可复用
     （部分索引条件必须与业务状态集合严格一致，新增状态时需同步修改约束）。
   - 区间采用半开 [start, end)，使 09:00-10:00 与 10:00-11:00 相邻而不冲突；
     所有冲突查询必须使用 start_at < new_end AND end_at > new_start 的写法，
     禁止使用 <= 或 >=（会产生"背靠背被判定为冲突"的错误）。
   - 状态变更一律用条件 UPDATE + rowcount 判定，避免"并发审批与取消"导致状态错乱；
     例如审批时若 rowcount=0 则说明已被取消，返回 409/40907。
   - 审批通过时如果该时段已过期（now > start_at），直接返回 409/40910 提示"该时段已过"。
   - 修改预约时间时：先校验 original status == 'pending'（条件锁定），
     再做冲突检测与更新，全在同一事务，避免"检查通过后被别人抢走"。
   - 提醒任务与超时任务必须加分布式锁（Redis SETNX 或数据库锁表），
     多实例部署时同一预约只被提醒一次；任务失败写入 booking_logs 供人工补偿。
   - 大范围统计（跨月、多房间）使用单条聚合 SQL，按需要为 (room_id, status, start_at)
     建索引；禁止把全部预约加载到内存计算。
   - 删除房间采用停用（is_active=0）而非物理删除，历史预约与统计仍可追溯。

【五、运行方式与示例】

安装与启动：
  python -m venv .venv && .venv\Scripts\activate
  pip install -r requirements.txt
  set JWT_SECRET_KEY=please-change-this-32bytes-minimum
  set DATABASE_URL=postgresql+psycopg://user:pwd@127.0.0.1:5432/booking
  set DEFAULT_TIMEZONE=Asia/Shanghai
  set SLOT_MINUTES=15
  set REMIND_BEFORE_MINUTES=15
  set SMTP_HOST=smtp.example.com  （不配置则只发站内信）
  alembic upgrade head              # 迁移中包含 btree_gist 扩展与排他约束
  uvicorn app.main:app --reload --port 8800
  python -m app.scripts.seed_demo   # 生成 4 间会议室与 30 个用户

  SQLite 快速体验（无排他约束，走事务串行化方案）：
  set DATABASE_URL=sqlite:///./booking.db
  alembic upgrade head && uvicorn app.main:app --port 8800

界面与交互说明：
  日历页 /calendar 为周视图：横轴为周一至周日，纵轴为 08:00-20:00 的半小时刻度；
  已通过的预约显示为绿色块，待审批为黄色，已驳回不显示。
  点击空白格自动填充起止时间并弹出预约表单；点击已有块显示详情与"取消/审批"按钮。
  页面上方有会议室筛选下拉与"本周/上周/下周"切换，右上角提供"导出本月明细"。

示例 1（查询可用时段）：
  请求：GET /api/v1/rooms/3/availability?date=2024-05-10
  响应：HTTP 200
        {"code":0,"data":{"room_id":3,"date":"2024-05-10","timezone":"Asia/Shanghai",
         "open":[{"start":"08:00","end":"12:00"},{"start":"13:30","end":"20:00"}],
         "busy":[{"start":"09:00","end":"10:00","booking_id":88}],
         "free":[{"start":"08:00","end":"09:00"},{"start":"10:00","end":"12:00"},
                 {"start":"13:30","end":"20:00"}],"slot_minutes":15}}
示例 2（正常预约）：
  请求：POST /api/v1/bookings
        {"room_id":3,"subject":"周会","start_at":"2024-05-10T10:00:00+08:00",
         "end_at":"2024-05-10T11:00:00+08:00","attendee_count":8,"attendee_ids":[5,8,12]}
  响应：HTTP 201
        {"code":0,"message":"预约已提交，等待审批","data":{"id":89,"room_id":3,
         "room_name":"A 会议室","subject":"周会","start_at":"2024-05-10T02:00:00Z",
         "end_at":"2024-05-10T03:00:00Z","local_start":"2024-05-10T10:00:00+08:00",
         "local_end":"2024-05-10T11:00:00+08:00","status":"pending","need_approval":true}}
示例 3（时段冲突）：
  请求：POST /api/v1/bookings  {"room_id":3,"start_at":"2024-05-10T09:30:00+08:00",
        "end_at":"2024-05-10T10:30:00+08:00", ...}
  响应：HTTP 409
        {"code":40902,"message":"该时段与已有预约冲突，请另选时间",
         "data":{"conflicts":[{"booking_id":89,"start_at":"2024-05-10T09:00:00+08:00",
         "end_at":"2024-05-10T10:00:00+08:00","organizer":"张三","status":"pending",
         "subject":"周会"}]}}
示例 4（不在开放时段）：
  请求：POST /api/v1/bookings  {"room_id":3,"start_at":"2024-05-10T12:30:00+08:00",
        "end_at":"2024-05-10T13:00:00+08:00", ...}
  响应：HTTP 422
        {"code":42203,"message":"所选时间不在该会议室的开放时段内",
         "data":{"open":[{"start":"08:00","end":"12:00"},{"start":"13:30","end":"20:00"}]}}
示例 5（时长超限与网格不合法）：
  请求：POST /api/v1/bookings  {"room_id":3,"start_at":"2024-05-10T09:07:00+08:00",
        "end_at":"2024-05-10T14:00:00+08:00", ...}
  响应：HTTP 422
        {"code":42204,"message":"时间必须落在 15 分钟网格上，最长预约 240 分钟",
         "data":{"suggested_start":"2024-05-10T09:15:00+08:00","duration_minutes":293,
         "max_duration_minutes":240}}
示例 6（审批）：
  请求：POST /api/v1/bookings/89/approve  {"comment":"同意"}
  响应：HTTP 200 {"code":0,"data":{"id":89,"status":"approved","approved_by":2,
        "approved_at":"2024-05-09T17:20:00Z"}}
  同一预约再次审批：
  响应：HTTP 409 {"code":40907,"message":"预约状态已变更，当前状态 approved","data":{"status":"approved"}}
示例 7（并发抢订，测试用例场景）：
  20 个线程同时提交 2024-05-10 14:00-15:00 的预约
  结果：1 个返回 201，19 个返回 409/40902；数据库中该时段仅 1 条记录。

【六、验收标准】

[ ] 20 个并发请求抢订同一会议室同一时段，最终只有 1 条记录成功，其余返回 409/40902。
[ ] 09:00-10:00 与 10:00-11:00 可以相邻预约（半开区间语义正确）；09:30-10:30 与 09:00-10:00 冲突。
[ ] 取消（cancelled）与驳回（rejected）的预约不再占用时段，同一时段可被重新预约。
[ ] 时间未落在 15 分钟网格时返回 422/42204 并给出建议时间。
[ ] 预约时长小于最小或大于最大值时返回 422/42202，data 含允许区间。
[ ] 落在午休（12:00-13:30）的时间段返回 422/42203；跨越午休的连续预约同样被拒。
[ ] 结束时间等于或早于开始时间返回 422/42201。
[ ] 参会人数超过容量返回 422/42205，data 返回 capacity。
[ ] 预约过去的时刻返回 422/42206；超过 advance_days 返回 422/42207。
[ ] 同一发起人在同一时段预约另一个会议室返回 409/40903。
[ ] 不带时区的时间字符串返回 422/42209（例如 "2024-05-10T09:00:00"）。
[ ] 审批自己的预约返回 403/40302；普通 user 调用审批接口返回 403/40301。
[ ] 审批已被取消的预约返回 409/40907，且状态不被改写（条件 UPDATE 生效）。
[ ] 驳回未填写原因（或原因少于 5 字符）返回 422/42208。
[ ] 开始前 20 分钟取消返回 409/40905；加 force=true 由管理员可取消。
[ ] 修改 approved 预约的时间返回 409/40906；修改 pending 预约时间会重新做冲突检测。
[ ] 可用时段接口返回的 free 与 busy 之和等于开放时段总长（无重叠、无遗漏）。
[ ] 日历接口一周数据中每天的预约块与数据库按房间过滤后的记录完全一致。
[ ] 提醒任务对同一预约只发送一次（reminded_at 生效），会议时间前 15 分钟内触发。
[ ] 超时释放任务把结束时间已过的 approved 预约置为 finished；超时未审批的置为 rejected。
[ ] no_show 累计 3 次的用户再次预约返回 403/40303 并给出解禁时间。
[ ] 统计的利用率与手工计算一致（approved + finished 时长 / 开放时长）。
[ ] 停用仍有未来预约的会议室返回 409/40909，data 列出冲突预约 id。
[ ] pytest 用例覆盖时间校验、冲突检测、并发、审批状态机、可用时段五类场景并全部通过。

【七、可选扩展】

1. 增加周期会议（每周重复 N 次），创建时批量做冲突检测并给出冲突清单供选择跳过。
2. 增加会议室签到二维码，会前 5 分钟扫码签到，未签到自动标记 no_show。
3. 增加与企业日历（如 iCal/ICS 订阅）互通，输出 /calendar.ics 供 Outlook 订阅。
4. 增加候补机制：时段冲突时允许排队，前序预约取消后自动通知并限时确认。
5. 增加设备与茶水服务预约（投影仪、白板笔等资源同样按时段占用）。
6. 增加会议室推荐：按参会人数与设备需求自动推荐可用房间。
7. 增加 Slack/企业微信 webhook 提醒通道（当前为站内信与邮件）。

【八、涉及知识点】

- 时间与日期处理：aware datetime、UTC 存储与本地展示、ZoneInfo 时区转换
- 区间重叠判定与半开区间 [start, end) 语义
- 数据库并发控制：PostgreSQL 排他约束（EXCLUDE USING gist）、事务隔离与 BEGIN IMMEDIATE
- 状态机设计：预约状态流转与条件 UPDATE + rowcount 校验
- 审批流建模：审批人策略、自审自批防护、权限与部门维度
- 日历与时间轴渲染：按周聚合、空闲时段扫描线算法与网格切分
- APScheduler 定时任务：提醒、超时释放、批量处理与分布式锁
- 通知渠道抽象：站内信与邮件（smtplib + EmailMessage）的可靠投递与去重
- 统计口径设计：利用率、按小时热度、审批通过率的分母定义
- 审计日志设计：状态变更的完整留痕与可追溯
- SQL 聚合与索引优化：范围查询索引 (room_id, start_at, end_at) 的选择性
================================================================================
