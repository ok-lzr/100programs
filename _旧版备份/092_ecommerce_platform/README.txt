================================================================================
项目编号：092                    难度等级：★★★★★（大型项目）
项目名称：电商平台系统
所属分类：Web 应用 / 业务系统 / 交易与订单
建议工时：3 ~ 4 周（约 120 ~ 180 小时）
运行环境：Python 3.10+    第三方依赖：FastAPI、uvicorn、SQLAlchemy、alembic、pydantic、redis、APScheduler、passlib、python-jose、pytest、httpx、Jinja2、python-multipart
================================================================================

【一、项目背景与目标】

电商是把“商品信息、库存数量、价格策略、优惠计算、支付状态、物流状态”这几条互相牵制
的数据流串成一条可回溯链路的过程。任何一家年交易量过万的小店，都会遇到同一批问题：
两个用户同时买走最后一件货导致超卖；用户连点两次提交按钮生成两笔订单；支付回调重复
推送把订单金额重复入账；促销规则叠加后订单金额和优惠券台账对不上；客服想查“这单为
什么便宜了 30 元”却没有任何计算痕迹。这些不是界面问题，而是交易系统的一致性设计问题。

本项目的目标是实现一个单商家、多用户的完整电商平台：商品与 SKU 管理、购物车、优惠
券、下单、库存扣减、模拟支付（含回调幂等）、订单状态机、退款、以及运营后台。系统要
在单机部署的前提下，把并发安全、支付幂等、库存一致性和订单可追溯这四件事做扎实，而
不是只把页面点通。

目标用户分两类：买家（浏览、加购、下单、支付、查单、申请退款）和运营人员（上下架、
调价、发券、看订单、处理退款、查库存流水）。系统还需要作为教学范例：演示如何用
Python 实现一个“看起来简单、写起来处处有坑”的交易系统，并把每个坑用测试固化下来。

业务上明确不做的事：不做真实支付渠道对接（用本地模拟支付网关 + 回调签名校验替
代）、不做多商家分账与结算、不做复杂仓储物流路径规划。这些边界必须在设计文档里写清，
避免范围蔓延导致核心链路做不完。

验收以“能复现并发问题的测试”为准：必须能给出在 50 并发下不超卖、重复回调只入账一次
的可重复证据，而不是口头保证。

【二、功能需求清单】

本系统按四个子系统拆分：用户端（买家前台）、管理端（运营后台）、服务端（交易 API 与
领域服务）、基础设施（存储、缓存、任务、部署）。

1. 用户端子系统（买家前台）
   1.1 商品列表页：分页展示在售商品，支持关键词搜索、分类筛选、价格区间筛选与三种排序
       （综合、销量、价格升降）。每页 24 条，返回字段含主图、标题、售价、划线价、销量。
   1.2 商品详情页：展示 SPU 信息、SKU 规格选择（颜色/容量等多维）、每个 SKU 的实时可售
       数量、SKU 价格、图文详情。选择不存在的 SKU 组合时提示“该规格暂不可售”。
   1.3 库存展示规则：可售数量 = 库存数量 - 锁定数量；数量为 0 时按钮置灰，数量少于 10
       时显示“仅剩 N 件”，不显示具体大额库存（防止爬价）。
   1.4 购物车：加入购物车（同 SKU 累加数量）、修改数量、勾选/取消勾选、删除、清空。单次
       加购数量上限 999；加购时校验可售库存但不锁定库存（下单时才锁定）。
   1.5 结算页：按勾选项计算商品总价、优惠券抵扣、运费、应付金额；金额一律用整数分表示，
       页面上再格式化为两位小数。优惠券不可用时给出具体原因（门槛不足/已过期/已用完）。
   1.6 下单：提交收货地址、收货人、手机号、备注；必须携带客户端生成的 request_id 用于
       幂等。下单成功后返回订单号（格式 yyyyMMdd + 12 位随机数字），并跳转收银台。
   1.7 收银台：展示应付金额与 15 分钟支付倒计时；选择“模拟支付”后调用本地支付网关，支付
       网关在 1~3 秒后异步回调服务端；支持用户主动点击“我已完成支付”做一次状态查询。
   1.8 订单中心：按状态（待付款、待发货、待收货、已完成、已关闭、退款中）筛选，列表展示
       商品摘要、金额、下单时间；详情页展示完整状态流转时间轴与金额明细。
   1.9 取消订单：待付款订单可取消，取消后释放锁定库存与优惠券；已支付订单只能发起退款。
   1.10 退款申请：选择整单退款或单品退款、填写原因、上传凭证（可选）；退款单进入待审核。
   1.11 收货地址管理：增删改查、设置默认地址，最多 20 条；下单时快照地址内容写入订单，
       后续修改地址不影响历史订单。
   1.12 个人中心：查看余额/积分（本项目仅作展示与扣减记录，不做充值）、优惠券列表（可用、
       已用、已过期分栏）。

2. 管理端子系统（运营后台）
   2.1 登录与权限：运营账号密码登录（argon2 哈希），角色分 admin（全部权限）与 operator
       （仅订单与客服权限）；登录失败 5 次锁定 10 分钟。
   2.2 商品管理：SPU 与 SKU 的增删改查，支持批量上下架、批量改价（按百分比或绝对值）、
       富文本详情编辑。下架商品在前台立即不可见但历史订单仍可查询。
   2.3 库存管理：手工入库、盘点调整、查看库存流水（每次变动记录来源单据类型与单号）。
       所有调整必须写流水，禁止直接改库存数字而不留痕。
   2.4 订单管理：按订单号/手机号/时间/状态检索；查看订单明细、支付记录、库存扣减记录；
       代客取消、手工发货（填运单号与快递公司）、确认收货。
   2.5 退款审核：查看退款单与原因，通过后走退款流程（调用模拟网关退款接口并置退款成功），
       驳回需填写驳回理由；退款成功后回滚库存（可配置是否回滚）。
   2.6 优惠券管理：创建满减券、折扣券、无门槛券；设置发放总量、每人限领、生效时间、适用
       商品范围（全场/指定分类/指定 SPU）；支持手动发放给指定用户。
   2.7 数据看板：今日 GMV、订单数、支付转化率、退款率、Top 10 热销商品、库存预警列表
       （可售数量低于阈值），数据按自然日聚合。
   2.8 操作审计：后台所有写操作写入 audit_log，包含操作人、IP、接口、参数摘要、变更前后
       关键字段，保留 180 天。

3. 服务端子系统（交易 API 与领域服务）
   3.1 认证：用户注册（手机号 + 密码）、登录签发 JWT（access 2 小时、refresh 7 天）、
       退出将 refresh token 加入黑名单。密码使用 passlib 的 argon2 方案，禁止明文与 MD5。
   3.2 商品服务：SPU/SKU 查询、分类树查询、库存查询；读多写少的部分走 Redis 缓存
       （商品详情缓存 60 秒，库存不做缓存或缓存 1 秒）。
   3.3 购物车服务：以 (user_id, sku_id) 为唯一键；合并同一 SKU；校验上下架状态与限购数。
   3.4 优惠计算服务：按“平台券 → 品类券 → 单品券”顺序依次计算，每步记录计算过程
       （规则名、参与金额、抵扣金额），结果写入订单的 promotion_detail 字段；同一订单最多
       使用 3 张券，互斥规则由券的 stackable 字段控制。
   3.5 下单服务：校验参数 → 幂等检查（request_id）→ 校验商品与库存 → 锁定库存（悲观锁或
       Redis Lua 原子扣减）→ 计算金额 → 生成订单与订单行 → 占用优惠券 → 写库存流水 →
       返回订单号。任一环节失败必须整体回滚到初始状态（数据库事务 + 补偿操作）。
   3.6 支付服务：创建支付单（关联订单号、金额、渠道、过期时间）；接收模拟网关回调，校验
       签名 → 校验金额一致 → 幂等处理（同一支付单号只入账一次）→ 订单状态改为已支付 →
       扣减真实库存并释放锁定 → 通知库存流水。
   3.7 订单状态机：定义状态集合与合法迁移，非法迁移抛出 IllegalTransition 异常并返回 409；
       每次迁移写入 order_status_log（from_state、to_state、operator、reason、时间）。
   3.8 超时关单：每 30 秒扫描创建超过 15 分钟仍未支付的订单，自动关闭并释放库存与优惠券；
       关单操作幂等，重复执行不产生副作用。
   3.9 退款服务：创建退款单 → 审核 → 调用模拟网关退款 → 更新支付记录与订单状态；退款金额
       不得超过实付金额减去已退金额。
   3.10 库存流水：每次变动写入 stock_log（sku_id、change、before、after、type、ref_no、
       created_at），type 包括 PURCHASE_LOCK、LOCK_RELEASE、SALE_DEDUCT、REFUND_RETURN、
       MANUAL_ADJUST、INVENTORY_CHECK。
   3.11 统一错误模型：{"code": "...", "message": "...", "detail": {...}}；错误码含
       STOCK_NOT_ENOUGH、COUPON_INVALID、ORDER_STATE_CONFLICT、PAY_AMOUNT_MISMATCH、
       DUPLICATE_REQUEST、UNAUTHORIZED、FORBIDDEN。
   3.12 限流与防刷：登录与下单接口按用户与 IP 双维度限流（下单 10 次/分钟）；下单接口校验
       request_id 与用户绑定，防止重放。

4. 基础设施子系统
   4.1 数据库：开发用 SQLite，生产用 PostgreSQL；通过 SQLAlchemy 抽象，禁止在业务代码里
       写方言特有 SQL；金额字段统一使用 BIGINT 存分，禁止使用浮点数。
   4.2 迁移：使用 alembic 管理表结构变更，每次变更一个迁移脚本，禁止手改生产表。
   4.3 缓存与原子操作：Redis 存放会话黑名单、商品缓存、库存预占（Lua 脚本保证 check-and-set
       原子性）；Redis 不可用时降级为数据库行锁并在日志中告警。
   4.4 定时任务：APScheduler 管理超时关单、优惠券过期、看板聚合三类任务；任务执行需加
       分布式锁（Redis SETNX + 过期时间）避免多进程重复执行。
   4.5 配置与密钥：支付网关密钥、JWT 密钥、数据库口令全部来自环境变量或 .env 文件，
       .env 不得提交到仓库；启动时若缺少必需变量直接失败退出。
   4.6 日志：分 app.log、access.log、payment.log、audit.log；支付回调与库存变动必须记录
       完整业务标识（订单号、支付单号、SKU），便于对账。
   4.7 数据初始化：提供 seed 脚本生成 20 个分类、200 个 SPU、每个 SPU 2~4 个 SKU、50 个
       用户与 300 笔历史订单，用于开发与性能测试。

5. 模块清单（源码结构）
   5.1 app/main.py            应用装配、路由注册、中间件、启动事件。
   5.2 app/config.py          Pydantic Settings 读取环境变量与 .env。
   5.3 app/db.py              引擎、Session 工厂、事务上下文管理器。
   5.4 app/models/            user.py、product.py、cart.py、order.py、payment.py、
                              coupon.py、stock.py、audit.py。
   5.5 app/schemas/           Pydantic 请求与响应模型，按领域分文件。
   5.6 app/services/          auth_service、catalog_service、cart_service、pricing_service、
                              order_service、payment_service、stock_service、refund_service、
                              coupon_service、report_service。
   5.7 app/api/v1/            用户端路由：auth、products、cart、orders、payment、address。
   5.8 app/api/admin/         后台路由：auth、products、stock、orders、refunds、coupons、
                              dashboard。
   5.9 app/mock_gateway/      本地模拟支付网关（独立小服务 + 签名校验 + 异步回调）。
   5.10 app/tasks/            定时任务定义与调度入口。
   5.11 app/core/             安全、限流、幂等、异常处理、日志配置等横切组件。
   5.12 tests/                单元测试、接口测试、并发测试、支付幂等测试、状态机测试。

6. 接口清单（HTTP，节选核心）
   6.1 POST /api/v1/auth/register            注册
   6.2 POST /api/v1/auth/login               登录（返回 access/refresh）
   6.3 POST /api/v1/auth/refresh             刷新令牌
   6.4 GET  /api/v1/products?kw=&cat=&min=&max=&sort=&page=    商品列表
   6.5 GET  /api/v1/products/{spu_id}        商品详情（含 SKU 与库存）
   6.6 POST /api/v1/cart/items               加购 {sku_id, quantity}
   6.7 PATCH /api/v1/cart/items/{id}         改数量/勾选
   6.8 DELETE /api/v1/cart/items/{id}        删除条目
   6.9 POST /api/v1/orders/preview           试算（金额与优惠明细，不落库）
   6.10 POST /api/v1/orders                  下单（Header: Idempotency-Key）
   6.11 GET  /api/v1/orders?state=&page=     订单列表
   6.12 POST /api/v1/orders/{no}/cancel      取消订单
   6.13 POST /api/v1/payments                创建支付单
   6.14 POST /api/v1/payments/callback       模拟网关回调（内网白名单 + 签名）
   6.15 POST /api/v1/refunds                 申请退款
   6.16 GET  /api/admin/dashboard/summary    看板汇总
   6.17 POST /api/admin/products/{id}/offline 批量下架
   6.18 POST /api/admin/stock/adjust         库存调整（必带原因）
   6.19 POST /api/admin/refunds/{id}/approve 退款审核通过
   6.20 POST /api/admin/coupons              创建优惠券

7. 数据模型概览
   7.1 users(id PK, phone UNIQUE, password_hash, nickname, status, created_at, updated_at)
   7.2 addresses(id PK, user_id FK, receiver, phone, province, city, district, detail,
       is_default, created_at)
   7.3 categories(id PK, parent_id, name, sort, status)
   7.4 spu(id PK, category_id FK, title, subtitle, main_image, detail_html, status,
       created_at, updated_at)
   7.5 sku(id PK, spu_id FK, spec_json, price_cent BIGINT, market_price_cent BIGINT,
       stock INT, locked INT, status, version INT)
   7.6 stock_log(id PK, sku_id FK, change INT, before_qty INT, after_qty INT, type,
       ref_no, operator, created_at)
   7.7 cart_item(id PK, user_id FK, sku_id FK, quantity INT, checked BOOL, created_at,
       updated_at)  唯一键 (user_id, sku_id)
   7.8 orders(id PK, order_no UNIQUE, user_id FK, state, goods_amount_cent BIGINT,
       discount_cent BIGINT, freight_cent BIGINT, pay_amount_cent BIGINT,
       address_snapshot_json, request_id UNIQUE, expire_at, paid_at, closed_at, created_at)
   7.9 order_item(id PK, order_id FK, spu_id, sku_id, title_snapshot, spec_snapshot,
       price_cent, quantity, subtotal_cent)
   7.10 order_status_log(id PK, order_id FK, from_state, to_state, operator, reason,
       created_at)
   7.11 payments(id PK, payment_no UNIQUE, order_no, channel, amount_cent, state,
       gateway_txn_id, paid_at, created_at)  唯一键 (order_no, channel, state=待支付) 逻辑约束
   7.12 coupons(id PK, name, type, threshold_cent, discount_cent, discount_rate,
       total, issued, per_user_limit, start_at, end_at, scope, stackable, status)
   7.13 user_coupons(id PK, user_id, coupon_id, state, order_no, used_at, expire_at)
   7.14 refunds(id PK, refund_no UNIQUE, order_no, user_id, amount_cent, reason, state,
       reviewer, review_reason, gateway_refund_id, created_at)
   7.15 audit_log(id PK, operator, role, ip, method, path, params_digest, before_json,
       after_json, created_at)

【三、里程碑拆解（建议 4 ~ 6 个阶段）】

阶段一：数据建模与只读链路（约 15 小时）
  产出：项目骨架、alembic 首个迁移、商品与分类模型、商品列表与详情接口、seed 脚本。
  验收：能通过接口列出 200 个 SPU 并正确返回 SKU 与可售数量；单元测试覆盖 catalog 服务。

阶段二：购物车与优惠计算（约 18 小时）
  产出：购物车增删改查、优惠券模型与发放、试算接口、金额与优惠明细结构。
  验收：试算接口对 20 组构造用例输出正确金额，含券不可用时的具体原因文案。

阶段三：下单与库存一致性（约 30 小时）
  产出：订单模型与状态机、库存锁定、下单服务、幂等键处理、库存流水、并发测试脚本。
  验收：50 并发抢购 10 件库存的测试稳定通过，幂等下单测试通过，流水与订单可对账。

阶段四：支付、关单与退款（约 25 小时）
  产出：模拟支付网关、支付单与回调幂等、超时关单任务、退款单与审核流。
  验收：回调重放 5 次只入账一次；超时关单释放库存与优惠券；退款金额校验正确。

阶段五：运营后台与看板（约 22 小时）
  产出：后台登录与角色、商品与库存管理、订单与退款处理、优惠券管理、数据看板、
        audit_log 全量留痕。
  验收：operator 角色无法访问商品改价接口；看板数字与数据库聚合查询一致。

阶段六：测试、性能与部署收尾（约 20 小时）
  产出：覆盖率报告、locust 压测脚本与报告、Dockerfile 与 docker-compose、部署文档、
        对账任务与告警配置。
  验收：覆盖率达标、压测指标达标、容器内一键启动成功并跑通全链路冒烟脚本。

【四、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；全量类型注解；关键函数必须标注金额单位（_cent 后缀）。
2. 允许使用的库：标准库（decimal、datetime、hashlib、hmac、secrets、uuid、enum、
   dataclasses）；第三方限 FastAPI、uvicorn、SQLAlchemy、alembic、pydantic、redis、
   APScheduler、passlib、python-jose、Jinja2、python-multipart、httpx、pytest、
   pytest-asyncio、locust（仅压测脚本使用）。禁止引入现成电商 SaaS SDK。
3. 禁止事项：禁止用 float 表示金额；禁止在 SQL 里做金额四舍五入后再比较；禁止把库存
   校验与扣减拆成两步无锁操作；禁止在支付回调里相信客户端传来的金额；禁止把密钥、
   数据库口令写入代码或提交到仓库；禁止在日志中输出用户密码、完整手机号与支付签名。
4. 代码组织：严格分层 api（路由/校验/鉴权）→ service（领域逻辑/事务边界）→ repository
   （数据访问）→ models（映射）；api 层不得出现 SQLAlchemy 查询语句；service 层不得
   依赖 FastAPI 的 Request 对象；跨聚合的一致性通过显式补偿方法实现，禁止隐式魔法。
5. 并发与一致性：库存扣减必须使用“数据库行锁 SELECT ... FOR UPDATE”或 Redis Lua 原子
   脚本二者之一，并在代码注释中说明所选方案的原因；订单创建必须在单个数据库事务内完成
   订单行、库存流水与优惠券占用的写入；任何跨事务步骤必须有补偿路径与超时清理任务。
6. 幂等要求：下单以 Idempotency-Key（Header）为幂等键，重复提交返回同一订单号且 HTTP
   200（而非新建订单）；支付回调以 payment_no 为幂等键，重复回调直接返回 success 且不
   产生第二笔入账；超时关单与退款回调同样必须幂等。
7. 编码规范：PEP 8；模块与公共函数必须有 docstring；日志用 logging 且带业务标识字段；
   异常统一继承 AppError 并携带 code 与 http_status；禁止裸 except。
8. 测试要求：pytest 覆盖率 ≥ 75%，核心交易链路（下单、支付、关单、退款）覆盖率 ≥ 90%；
   必须包含并发测试：50 个线程抢购同一 SKU（库存 10），断言成功订单数为 10 且库存不
   为负；必须包含支付回调重放测试：同一回调连续送 5 次，断言只入账一次。
9. 性能要求：单机 4 核 8 GB，商品列表接口 P95 ≤ 150 ms，下单接口 P95 ≤ 400 ms（不含
   支付），系统在 200 QPS 混合流量下错误率低于 0.5%；数据库连接池大小可配置，默认 20。
10. 安全要求：所有写接口必须鉴权；后台接口校验角色；支付回调校验 HMAC 签名与来源 IP；
    用户只能访问自己的订单与地址（水平越权测试必须覆盖）；敏感字段（手机号）在日志与
    后台列表页脱敏显示为 138****1234。
11. 隐私与合规：仅采集履约必需的个人信息（手机号、收货地址），注册时展示隐私政策并获得
    明示同意；提供账号注销接口，注销后 30 天软删除并清理地址与购物车数据；导出与删除
    个人数据接口必须记录审计日志；不得将用户手机号用于本项目之外的任何用途。

【五、设计要点】

1. 数据结构与状态定义：
   1.1 OrderState 枚举：CREATED（待付款）、PAID（待发货）、SHIPPED（待收货）、
       FINISHED（已完成）、CLOSED（已关闭）、REFUNDING（退款中）、REFUNDED（已退款）。
   1.2 合法迁移：CREATED→PAID/CLOSED；PAID→SHIPPED/REFUNDING；SHIPPED→FINISHED/REFUNDING；
       FINISHED→REFUNDING；REFUNDING→REFUNDED/PAID（驳回回到支付后状态）。
   1.3 金额计算对象 Money(cent: int, currency: str = "CNY")，禁止隐式转换为 float。
   1.4 库存对象 StockSnapshot(sku_id, stock, locked, version)，version 用于乐观锁重试。
2. 关键算法与流程：
   2.1 下单主流程（伪代码步骤）：① 解析 Idempotency-Key 并查重；② 加载勾选购物车项并校验
       上下架；③ 试算金额（含优惠券与运费）；④ 开启事务；⑤ 按 sku_id 升序加行锁（避免死锁）
       并校验 stock - locked >= 购买数量；⑥ 累加 locked；⑦ 写订单、订单行、状态日志；
       ⑧ 标记优惠券已用；⑨ 清空已下单的购物车项；⑩ 提交事务；⑪ 返回订单号。
   2.2 支付回调流程：验签 → 查支付单 → 若已成功则直接返回 success（幂等出口）→ 校验金额等于
       订单 pay_amount_cent → 事务内更新支付单为成功、订单置 PAID、sku.stock -= qty、
       sku.locked -= qty、写 SALE_DEDUCT 流水 → 提交 → 返回 success。
   2.3 超时关单流程：查询 expire_at < now 且 state=CREATED 的订单（每批 200 条）→ 逐单加锁
       → 关闭订单、locked -= qty、优惠券回退为可用、写 LOCK_RELEASE 流水 → 提交；单笔失败
       不影响后续，失败原因写入日志并留待下次重试。
   2.4 优惠计算：先按 scope 过滤可用券，按抵扣金额从大到小贪心选择不超过 3 张且满足互斥
       规则，计算每张券的抵扣明细并累加；折扣券使用 round_half_up 到分，抵扣不超过剩余
       应付金额（不允许出现负数应付）。
   2.5 库存扣减的 Redis 方案：使用 Lua 脚本原子执行 get → 比较 → decrby，返回剩余数量或
       失败标记；脚本执行失败降级为数据库行锁路径。
   2.6 对账流程：每日 02:00 运行对账任务，比对付费订单总额与支付成功总额、库存流水净变
       与库存当前值，差异写入 reconciliation_report 表并在日志中报警。
3. 主要数据库表结构（关键字段与索引）：
   3.1 orders：索引 idx_user_created(user_id, created_at desc)、uniq_order_no(order_no)、
       uniq_request_id(request_id)；金额字段注释写明单位为分。
   3.2 order_item：索引 idx_order(order_id)、idx_sku(sku_id)，用于销量统计与退款按单品计算。
   3.3 sku：唯一键 uniq_spu_spec(spu_id, spec_hash)；version 字段用于乐观锁；检查约束
       stock >= 0 AND locked >= 0 AND locked <= stock。
   3.4 payments：唯一索引 uniq_payment_no；复合索引 idx_order_state(order_no, state)。
   3.5 stock_log：索引 idx_sku_created(sku_id, created_at desc)；只允许 INSERT，禁止 UPDATE
       与 DELETE（权限层面收回）。
   3.6 user_coupons：唯一索引 uniq_user_coupon_order(user_id, coupon_id, order_no)，防止
       同一订单重复占用同一张券。
4. 接口设计要点：
   4.1 幂等键约定：POST /api/v1/orders 必须携带 Idempotency-Key（UUID4），缺失返回 400；
       同一 Key 不同用户视为冲突返回 409。
   4.2 分页约定：统一 page（从 1 开始）与 size（默认 20，最大 100），响应含 total。
   4.3 试算接口不写库、不加锁，只读快照，允许与最终下单金额存在极小的并发差异（库存变化
       不影响价格），但下单时会重新计算并以此为准。
   4.4 后台批量操作返回结构 {"succeeded": [ids], "failed": [{"id": x, "reason": "..."}]}，
       禁止一批失败就整体 500。

【六、运行方式与示例】

1. 安装与初始化
   python -m venv .venv && .venv\Scripts\activate
   pip install fastapi uvicorn sqlalchemy alembic pydantic redis apscheduler passlib
   pip install python-jose[cryptography] jinja2 python-multipart httpx pytest locust
   copy .env.example .env       （填入 DB_URL、REDIS_URL、JWT_SECRET、PAY_SECRET）
   alembic upgrade head
   python -m app.seed           （生成分类、商品、用户与历史订单）
2. 启动
   python -m app.mock_gateway --port 9100      （先起模拟支付网关）
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
   uvicorn app.admin_main:app --host 127.0.0.1 --port 8001
3. 示例一（加购 → 下单）
   请求：POST /api/v1/cart/items
   {"sku_id": 10023, "quantity": 2}
   响应：201 {"cart_item_id": 8831, "sku_id": 10023, "quantity": 2, "checked": true}
   请求：POST /api/v1/orders
   Header: Authorization: Bearer <token>；Idempotency-Key: 5f1c9e2a-...
   {"address_id": 77, "coupon_ids": [12], "remark": "工作日送"}
   响应：201
   {"order_no": "202501151230000042", "pay_amount_cent": 25800,
    "discount_cent": 3000, "freight_cent": 0, "expire_at": "2025-01-15T12:45:00",
    "promotion_detail": [{"coupon_id": 12, "name": "满200减30", "amount_cent": 3000}]}
4. 示例二（幂等：重复下单）
   同一 Idempotency-Key 再次请求 → HTTP 200
   {"order_no": "202501151230000042", "duplicated": true, "pay_amount_cent": 25800}
   说明：不新建订单，库存与优惠券均不再变动。
5. 示例三（并发抢购的期望结果）
   场景：SKU stock=10，50 个用户各买 1 件并发提交
   期望：10 单成功（HTTP 201），40 单失败返回 409
   {"code": "STOCK_NOT_ENOUGH", "message": "库存不足", "detail": {"sku_id": 10023,
    "available": 0, "requested": 1}}
   最终 sku.stock=10、sku.locked=10；未支付订单 15 分钟后关单，locked 回到 0。
6. 示例四（支付回调幂等）
   请求：POST /api/v1/payments/callback
   Header: X-Pay-Sign: 9c1f...（HMAC-SHA256(secret, raw_body)）
   {"payment_no": "P202501151230000042", "gateway_txn_id": "T8891", "amount_cent": 25800,
    "state": "SUCCESS"}
   响应：200 {"result": "success"}
   同一报文连续重放 5 次：均为 200 success，payments 表仍只有一条 SUCCESS，
   stock_log 只增加一条 SALE_DEDUCT。
7. 示例五（异常输入）
   请求：POST /api/v1/orders，Idempotency-Key 缺失
   响应：HTTP 400 {"code": "BAD_REQUEST", "message": "缺少 Idempotency-Key 头"}
   请求：POST /api/v1/payments/callback，签名错误
   响应：HTTP 401 {"code": "SIGN_INVALID", "message": "签名校验失败"}

【七、验收标准】

[ ] 1. 前台可完成“浏览 → 加购 → 结算 → 下单 → 模拟支付 → 订单变已支付 → 后台发货 →
      确认收货 → 已完成”的全链路，状态时间轴记录完整。
[ ] 2. 50 并发抢购库存为 10 的 SKU，成功订单恰好 10 笔，sku.stock 与 sku.locked 均
      不为负，且 stock_log 中 LOCK 记录数与成功订单商品数一致。
[ ] 3. 使用同一 Idempotency-Key 重复下单 5 次，只生成 1 笔订单，返回订单号一致。
[ ] 4. 支付回调重放 5 次只入账一次；篡改金额的回调被拒绝且订单状态不变。
[ ] 5. 待付款订单超过 15 分钟被自动关闭，locked 归零，优惠券回到可用状态且 user_coupons
      记录标记为回退。
[ ] 6. 非法状态迁移（例如对已关闭订单执行发货）返回 409 与 ORDER_STATE_CONFLICT，
      order_status_log 中不出现非法记录。
[ ] 7. 优惠券计算明细可在订单详情中逐条查看，试算金额与最终下单金额在无并发变化时一致。
[ ] 8. 用户 A 无法通过修改 URL 中的 id 访问用户 B 的订单、地址与退款单（水平越权测试）。
[ ] 9. 登录失败 5 次后账号锁定 10 分钟，期间正确密码也返回锁定提示。
[ ] 10. 后台所有写操作在 audit_log 中留痕，包含操作人、IP、接口与前后关键字段。
[ ] 11. 金额计算全部以分为单位，随机生成 1000 笔订单校验“商品金额 - 优惠 + 运费 = 应付
      金额”，无一分钱误差。
[ ] 12. 每日对账任务执行后，付费订单总额与支付成功总额差异为 0，差异不为 0 时产生告警日志。
[ ] 13. 下单接口 P95 ≤ 400 ms，商品列表 P95 ≤ 150 ms（locust 压测报告可复现）。
[ ] 14. pytest 覆盖率 ≥ 75%，交易链路 ≥ 90%，包含并发与幂等专项测试且全部通过。
[ ] 15. 手机号在日志与后台列表中已脱敏，.env 未被提交，仓库中 grep 不到任何明文密钥。

【八、可选扩展】

1. 引入消息队列（RabbitMQ 或 Redis Stream）承载订单事件，实现库存扣减与通知的异步化，
   并演示最终一致性与死信重试。
2. 增加秒杀模块：独立库存桶、答题令牌、队列削峰与限购规则。
3. 增加多商家与分账结算：店铺、佣金规则、结算单与对账单。
4. 增加真实优惠引擎：规则表达式（DSL）驱动，支持叠加、互斥与最优组合求解。
5. 增加搜索服务：接入倒排索引（可复用 091 项目）实现商品全文检索。
6. 增加前端 SPA 与移动端适配，配套接口契约测试（schemathesis）。
7. 增加可观测性：Prometheus 指标、OpenTelemetry 链路追踪与 Grafana 看板。

【九、涉及知识点】

- Web 框架与分层架构：FastAPI 依赖注入、Pydantic 校验、service/repository 分层
- 关系数据库：SQLAlchemy ORM、事务隔离级别、行锁与死锁避免、索引与约束设计
- 并发编程：线程池、乐观锁与悲观锁、Redis Lua 原子脚本、限流与幂等设计
- 领域建模：订单状态机、金额模型、库存流水与不可变台账思想
- 支付与安全：HMAC 签名校验、回调幂等、密钥管理、越权防护与敏感数据脱敏
- 缓存与任务调度：Redis 缓存策略、分布式锁、APScheduler 定时任务与超时补偿
- 测试工程：pytest 夹具、并发测试、幂等测试、覆盖率与压测（locust）
- 运维与合规：alembic 迁移、结构化日志、审计留痕、个人数据最小化与注销流程
================================================================================
