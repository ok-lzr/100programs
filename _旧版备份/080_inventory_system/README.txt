================================================================================
项目编号：080                    难度等级：★★★★☆（中型项目，偏难）
项目名称：库存进销存系统
所属分类：Web 后端 / 业务管理系统
建议工时：5 ~ 7 天
运行环境：Python 3.10+    第三方依赖：fastapi、uvicorn、sqlalchemy、pydantic、passlib[bcrypt]、python-jose[cryptography]、openpyxl、pytest、httpx
================================================================================

【一、项目背景与目标】

小型贸易公司、餐饮供应链、生产车间的仓库管理普遍停留在"Excel + 微信群"阶段：
采购到货后在群里说一声，出库时凭记忆，月底盘点总对不上账，
老板问"这个月 A 商品还有多少库存、值多少钱"没人答得上来。
更麻烦的是负库存：账面显示 -3 件，说明之前的出库或入库记错了，但已经无从追溯。

本项目实现一套单仓（可扩展多仓）进销存系统，覆盖：
商品与供应商主数据 → 采购入库（含退货）→ 销售出库（含退货）→
库存实时数量与成本 → 库存预警（低于安全库存/高于上限/临近保质期）→
流水台账（每一笔数量变动都能追溯到单据）→ 报表（进销存汇总、毛利、库存周转）。

技术核心有三处：一是库存扣减的并发安全（条件 UPDATE 保证不出现负库存）；
二是成本核算方法（本项目默认移动加权平均，每次入库重新计算平均成本，
出库按当时平均成本结转，禁止用 float 计算金额）；
三是台账完整性（任何数量变动都必须同时写 stock_ledger，
库存表与台账表的对账结果必须永远一致，这条要写成自动校验任务）。

【二、功能需求清单】

1. 核心功能
   1.1 商品管理：SKU 编码、名称、规格、单位、分类、条码、安全库存、最高库存、
       保质期天数、默认供应商、参考进价与售价。
   1.2 供应商管理：名称、联系人、电话、地址、结算方式（现结/月结）、账期天数、启用状态。
   1.3 客户管理：名称、联系人、电话、信用额度、启用状态（用于销售出库）。
   1.4 采购入库：一张入库单可含多个商品行，支持分批到货（一次采购对应多张入库单）。
   1.5 采购退货：对已入库的采购单发起退货，生成负向入库（数量减少），成本按原入库成本冲回。
   1.6 销售出库：一张出库单可含多个商品行，出库时校验库存充足，按移动加权平均成本结转。
   1.7 销售退货：对已出库的销售单发起退货，生成正向入库，成本按原出库成本冲回。
   1.8 库存调整：盘点差异、报损、赠品等场景走调整单（必须填写调整原因）。
   1.9 库存查询：按商品查当前数量、可用数量（扣除已占用）、平均成本、库存金额、最近变动时间。
   1.10 批次与保质期（可选开启）：入库记录生产日期与到期日，出库按先进先出（FIFO）扣批次。
   1.11 库存预警：低于安全库存、高于最高库存、30 天内到期、长期无动销（90 天）四类预警。
   1.12 流水台账：按商品与时间区间查询每一笔变动（单据号、类型、数量、结存、成本）。
   1.13 报表：进销存汇总（期初 + 入库 - 出库 = 期末）、商品毛利表、库存金额排行、
       供应商采购排行、库存周转天数。
   1.14 Excel 导入导出：商品与供应商批量导入（含行级错误报告），库存与台账导出。
   1.15 权限：admin（全部）、purchaser（采购单与供应商）、sales（出库单与客户）、
       viewer（只读查询与报表）。
   1.16 对账自检：定时任务校验 stock 表的 quantity 与 ledger 汇总是否一致，不一致则告警。

2. 输入与交互
   2.1 全部通过 JSON；批量导入使用 multipart/form-data 上传 .xlsx。
   2.2 入库单请求：{"supplier_id":5,"warehouse_id":1,"biz_date":"2024-05-10",
       "items":[{"sku":"SKU001","qty":100,"unit_cost":12.50,"batch_no":"B240510",
       "production_date":"2024-05-01","expire_date":"2024-11-01"}],"remark":"首次到货"}
   2.3 出库单请求：{"customer_id":8,"biz_date":"2024-05-11","items":[
       {"sku":"SKU001","qty":30,"unit_price":19.90}],"remark":"客户自提"}
   2.4 数量单位：入库为正数（退货单为负数），出库为正数（退货单为负数），
       接口层面由单据类型决定方向，客户端始终提交正数，方向由服务端确定。
   2.5 金额精度：单价与金额使用 Decimal，数据库用 NUMERIC(14,4) 存单价、NUMERIC(16,2) 存金额，
       数量用 NUMERIC(16,3)（支持 0.5kg 这类小数单位）。
   2.6 单据编号：规则为 前缀 + YYYYMMDD + 4 位当日流水，如 IN202405100001；
       由数据库序号表或 Redis INCR 生成，禁止用时间戳拼接（会重复）。
   2.7 分页参数统一 page（默认 1）与 page_size（默认 20，最大 200）。
   2.8 交互方式：REST 接口 + Swagger UI + 内置的库存看板页 /dashboard。

3. 输出与展示
   3.1 统一响应 { "code": 0, "message": "ok", "data": {...} }。
   3.2 入库单响应：{"doc_no":"IN202405100001","type":"purchase_in","biz_date":"2024-05-10",
       "supplier":{"id":5,"name":"杭州某供应商"},"status":"confirmed","total_qty":100,
       "total_amount":"1250.00","items":[{"sku":"SKU001","name":"A 商品","qty":100,
       "unit_cost":"12.5000","amount":"1250.00","stock_after":"180.000",
       "avg_cost_after":"12.3000"}]}
   3.3 出库单响应：含每行的出库成本（"cost_amount"）与毛利（"gross_profit"）。
   3.4 库存查询响应：{"sku":"SKU001","name":"A 商品","unit":"个","quantity":"180.000",
       "locked_qty":"0.000","available_qty":"180.000","avg_cost":"12.3000",
       "stock_amount":"2214.00","safety_stock":"50.000","is_low":false,
       "last_moved_at":"2024-05-10T02:00:00Z"}
   3.5 台账响应：{"id":3301,"sku":"SKU001","doc_no":"OUT202405110001","biz_type":"sale_out",
       "qty":"-30.000","balance_qty":"150.000","unit_cost":"12.3000",
       "amount":"-369.00","balance_amount":"1845.00","biz_date":"2024-05-11"}
   3.6 汇总报表：{"period":"2024-05","opening":{"qty":"100.000","amount":"1230.00"},
       "in":{"qty":"100.000","amount":"1250.00"},"out":{"qty":"50.000","amount":"615.00"},
       "closing":{"qty":"150.000","amount":"1845.00"},
       "check":{"opening_plus_in_minus_out":"150.000","match":true}}
   3.7 看板页展示：库存总金额、预警商品数、今日出入库单据数、近 30 天出库趋势（简易条形）。

4. 异常与边界处理
   4.1 商品 SKU 不存在：404 / 40401；已停用商品参与出入库返回 409 / 40901。
   4.2 供应商不存在或已停用：404 / 40402、409 / 40902；客户同理。
   4.3 单据明细为空：422 / 42201；同一单据内 SKU 重复：422 / 42202（应先合并行）。
   4.4 数量为 0 或负数：422 / 42203（数量字段只接受正数，方向由单据类型决定）。
   4.5 数量精度超过 3 位小数：422 / 42204。
   4.6 单价为负或超过 6 位小数：422 / 42205。
   4.7 出库数量超过可用库存：409 / 40903，data 返回 sku、可用数量与需求量。
   4.8 采购退货数量超过原入库数量（累计退货 > 入库）：409 / 40904，data 返回可退数量。
   4.9 销售退货数量超过原出库数量：409 / 40905，data 返回可退数量。
   4.10 单据已确认后修改明细：409 / 40906（需先红冲）；删除已确认单据：409 / 40907。
   4.11 调整单未填写原因：422 / 42206（原因必填，长度 >= 5）。
   4.12 保质期早于生产日期或早于业务日期：422 / 42207。
   4.13 批次出库时指定批次库存不足：409 / 40908，data 返回该批次可用量。
   4.14 单据编号生成冲突（极端并发）：服务端自动重试 3 次，仍失败返回 500 / 50001。
   4.15 库存查询的 SKU 不存在：404 / 40401。
   4.16 Excel 导入缺少必需列或数据类型错误：422 / 42208，data 返回逐行错误。
   4.17 商品为负库存状态时（历史脏数据）任何出库都返回 409 / 40909 并提示先做盘点调整。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：fastapi、uvicorn[standard]、sqlalchemy 2.0、pydantic v2、
   passlib[bcrypt]、python-jose[cryptography]、openpyxl（导入导出）、
   APScheduler（对账与预警任务）、pytest、httpx、alembic。
   数据库默认 SQLite（开发），生产建议 PostgreSQL；数量与金额计算只用 Decimal。
3. 禁止事项：禁止使用 float 做任何数量、单价、金额的运算与存储。
4. 禁止事项：禁止直接 UPDATE stock 表的 quantity 而不写 stock_ledger
   （两者必须在同一事务内成对出现）。
5. 禁止事项：禁止用"先查库存再更新"的两步写法处理出库；必须用条件 UPDATE 判断 rowcount。
6. 禁止事项：禁止硬编码数据库口令与 JWT 密钥，必须读环境变量；
   禁止在日志中打印供应商银行账号等敏感字段。
7. 代码组织（必须有以下模块）：
   app/main.py、app/config.py（仓库配置、精度、编号前缀、预警阈值）
   app/database.py、app/models.py、app/schemas.py、app/deps.py
   app/core/money.py（Decimal 量化与四舍五入策略）
   app/core/docno.py（单据编号生成，基于序号表 + 行锁）
   app/services/product_service.py、supplier_service.py、customer_service.py
   app/services/stock_service.py（入库、出库、调整、成本计算，核心）
   app/services/ledger_service.py（台账写入与查询、对账）
   app/services/report_service.py（进销存汇总、毛利、周转率）
   app/services/alert_service.py（四类预警计算）
   app/importers/excel_master.py（商品与供应商导入）
   app/exporters/inventory_export.py（库存与台账导出 xlsx）
   app/core/scheduler.py（每日对账、每日预警快照）
   app/routers/auth.py、products.py、partners.py、inbound.py、outbound.py、
   adjust.py、stock.py、reports.py
   app/templates/dashboard.html
   tests/test_stock_in_out.py、test_concurrency.py、test_cost.py、
   test_ledger_balance.py、test_reports.py
8. 编码规范：所有函数带类型注解与 docstring；金额相关 docstring 必须写明精度与舍入规则。
9. 编码规范：使用 logging 记录 doc_no、sku、qty、结存，禁止 print。
10. 编码规范：所有单据的写入方法必须以事务为最小单位（一个单据 = 一个事务）。

【四、设计要点】

1. 数据结构（核心表与字段）
   表 users：
     id BIGINT PK、username VARCHAR(32) UNIQUE、password_hash VARCHAR(128)、
     real_name VARCHAR(32)、role VARCHAR(16)（admin / purchaser / sales / viewer）、
     is_active BOOLEAN、created_at DATETIME
   表 warehouses：
     id BIGINT PK、code VARCHAR(16) UNIQUE、name VARCHAR(64)、
     address VARCHAR(200)、is_active BOOLEAN DEFAULT 1、created_at DATETIME
   表 products：
     id BIGINT PK、sku VARCHAR(32) UNIQUE NOT NULL、name VARCHAR(120) NOT NULL、
     spec VARCHAR(64) NULL、unit VARCHAR(16) NOT NULL、category VARCHAR(64) NULL、
     barcode VARCHAR(32) NULL、safety_stock NUMERIC(16,3) DEFAULT 0、
     max_stock NUMERIC(16,3) NULL、shelf_life_days INTEGER NULL、
     default_supplier_id FK(suppliers.id) NULL、
     ref_purchase_price NUMERIC(14,4) NULL、ref_sale_price NUMERIC(14,4) NULL、
     is_batch_managed BOOLEAN DEFAULT 0（是否启用批次管理）、
     is_active BOOLEAN DEFAULT 1、created_at DATETIME、updated_at DATETIME
     索引：uk_products_sku 唯一、idx_products_category(category)、idx_products_barcode(barcode)
   表 suppliers：
     id BIGINT PK、code VARCHAR(32) UNIQUE、name VARCHAR(120) NOT NULL、
     contact VARCHAR(32)、phone VARCHAR(20)、address VARCHAR(200)、
     settle_type VARCHAR(16)（cash / monthly）、credit_days INTEGER DEFAULT 0、
     is_active BOOLEAN DEFAULT 1、created_at DATETIME
   表 customers：
     id BIGINT PK、code VARCHAR(32) UNIQUE、name VARCHAR(120) NOT NULL、
     contact VARCHAR(32)、phone VARCHAR(20)、address VARCHAR(200)、
     credit_limit NUMERIC(16,2) DEFAULT 0、is_active BOOLEAN DEFAULT 1、created_at DATETIME
   表 stock（库存主表，一个 SKU + 仓库一行）：
     id BIGINT PK、warehouse_id FK、product_id FK
     quantity NUMERIC(16,3) NOT NULL DEFAULT 0（当前数量，可为 0，不允许为负）
     locked_qty NUMERIC(16,3) NOT NULL DEFAULT 0（已占用，如已开单未出库）
     avg_cost NUMERIC(14,4) NOT NULL DEFAULT 0（移动加权平均成本）
     stock_amount NUMERIC(16,2) NOT NULL DEFAULT 0（= quantity * avg_cost 的量化结果）
     last_moved_at DATETIME NULL、updated_at DATETIME
     约束：CHECK (quantity >= 0)；CHECK (locked_qty >= 0)；UNIQUE(warehouse_id, product_id)
     索引：idx_stock_product(product_id)
   表 stock_batches（批次库存，启用批次管理的商品使用）：
     id BIGINT PK、warehouse_id FK、product_id FK、batch_no VARCHAR(32) NOT NULL
     production_date DATE NULL、expire_date DATE NULL
     quantity NUMERIC(16,3) NOT NULL DEFAULT 0
     unit_cost NUMERIC(14,4) NOT NULL、created_at DATETIME、updated_at DATETIME
     约束：UNIQUE(warehouse_id, product_id, batch_no)；CHECK (quantity >= 0)
     索引：idx_batch_expire(expire_date)（先进先出与临期预警用）
   表 stock_docs（单据主表，四种类型共用）：
     id BIGINT PK
     doc_no VARCHAR(24) UNIQUE NOT NULL
     doc_type VARCHAR(16) NOT NULL
       （purchase_in 采购入库 / purchase_return 采购退货 /
         sale_out 销售出库 / sale_return 销售退货 / adjust 库存调整）
     warehouse_id FK、supplier_id FK NULL、customer_id FK NULL
     biz_date DATE NOT NULL、status VARCHAR(16) DEFAULT 'confirmed'
       （draft / confirmed / void）
     total_qty NUMERIC(16,3) NOT NULL、total_amount NUMERIC(16,2) NOT NULL
     src_doc_id BIGINT NULL（退货单指向原单）
     reason VARCHAR(200) NULL（调整单必填）
     remark VARCHAR(300) NULL
     created_by FK(users.id)、created_at DATETIME、voided_by FK NULL、voided_at DATETIME NULL
     索引：idx_doc_type_date(doc_type, biz_date)、idx_doc_supplier(supplier_id, biz_date)、
           idx_doc_customer(customer_id, biz_date)、idx_doc_src(src_doc_id)
   表 stock_doc_items（单据明细）：
     id BIGINT PK、doc_id FK(stock_docs.id) ON DELETE CASCADE、seq INTEGER NOT NULL
     product_id FK、sku VARCHAR(32) NOT NULL（冗余，便于导出与排障）
     qty NUMERIC(16,3) NOT NULL（始终为正数）
     unit_cost NUMERIC(14,4) NOT NULL（入库为进价；出库为结转成本）
     unit_price NUMERIC(14,4) NULL（销售单价，出库与销售退货使用）
     amount NUMERIC(16,2) NOT NULL（系统计算，= qty * unit_cost，量化到分）
     cost_amount NUMERIC(16,2) NULL（出库成本金额）
     gross_profit NUMERIC(16,2) NULL（销售出库 = amount - cost_amount）
     batch_no VARCHAR(32) NULL、production_date DATE NULL、expire_date DATE NULL
     UNIQUE(doc_id, seq)
     索引：idx_item_product(product_id, doc_id)
   表 stock_ledger（流水台账，只增不改，审计核心）：
     id BIGINT PK
     warehouse_id FK、product_id FK、sku VARCHAR(32) NOT NULL
     doc_id FK、doc_no VARCHAR(24) NOT NULL、doc_type VARCHAR(16) NOT NULL
     biz_type VARCHAR(24) NOT NULL（purchase_in / purchase_return / sale_out /
       sale_return / adjust_in / adjust_out / void_reverse）
     qty NUMERIC(16,3) NOT NULL（正数入库，负数出库）
     unit_cost NUMERIC(14,4) NOT NULL
     amount NUMERIC(16,2) NOT NULL（= qty * unit_cost）
     balance_qty NUMERIC(16,3) NOT NULL（本笔之后的结存数量）
     balance_amount NUMERIC(16,2) NOT NULL（本笔之后的结存金额）
     batch_no VARCHAR(32) NULL
     biz_date DATE NOT NULL、created_at DATETIME NOT NULL、created_by FK
     索引：idx_ledger_product_time(product_id, id)、idx_ledger_doc(doc_id)、
           idx_ledger_biz_date(biz_date)
   表 doc_sequences（单据编号序号表）：
     id PK、prefix VARCHAR(8) NOT NULL、seq_date DATE NOT NULL、current_seq INTEGER NOT NULL
     UNIQUE(prefix, seq_date)
     用法：UPDATE doc_sequences SET current_seq = current_seq + 1
           WHERE prefix = :p AND seq_date = :d RETURNING current_seq
           （PostgreSQL 行锁；SQLite 用 BEGIN IMMEDIATE + 先 UPSERT 再 UPDATE）
   表 stock_alerts（预警快照，每日生成，便于看板与历史回溯）：
     id PK、alert_date DATE NOT NULL、product_id FK、warehouse_id FK
     alert_type VARCHAR(16)（low_stock / over_stock / near_expiry / no_movement）
     current_qty NUMERIC(16,3)、threshold NUMERIC(16,3) NULL、detail VARCHAR(200) NULL
     UNIQUE(alert_date, product_id, warehouse_id, alert_type)

2. 关键算法或流程
   单据编号生成（并发安全）：
     步骤 1：计算当日日期串 YYYYMMDD 与类型前缀（IN / PRT / OUT / SRT / ADJ）。
     步骤 2：INSERT INTO doc_sequences(prefix, seq_date, current_seq) VALUES (:p, :d, 0)
             ON CONFLICT(prefix, seq_date) DO NOTHING（保证行存在）。
     步骤 3：UPDATE doc_sequences SET current_seq = current_seq + 1
             WHERE prefix = :p AND seq_date = :d RETURNING current_seq
             （PostgreSQL 该 UPDATE 自带行锁，天然串行化）。
     步骤 4：doc_no = prefix + YYYYMMDD + str(seq).zfill(4)。
     步骤 5：插入 stock_docs，若唯一键冲突（极端情况）则重试最多 3 次。
     禁止用"查询最大编号 + 1"的写法（并发下会重复）。
   采购入库（一个事务）：
     步骤 1：校验单据头（供应商启用、仓库启用、biz_date 合法、明细非空且 SKU 不重复）。
     步骤 2：批量加载全部 product（一次 IN 查询），校验存在、启用、单价与数量格式。
     步骤 3：计算行金额：amount = (qty * unit_cost).quantize(Decimal("0.01"), ROUND_HALF_UP)。
     步骤 4：生成 doc_no，插入 stock_docs（status='confirmed'）。
     步骤 5：逐行处理库存（同一事务内）：
             a) 锁定/读取当前库存行：SELECT ... FROM stock
                WHERE warehouse_id=:w AND product_id=:p（PostgreSQL 加 FOR UPDATE）。
             b) 计算新平均成本（移动加权平均）：
                新数量 = 旧数量 + qty
                新金额 = 旧金额 + amount
                若新数量 == 0 → 新平均成本保持不变（避免除零）
                否则 新平均成本 = (新金额 / 新数量).quantize(Decimal("0.0001"), ROUND_HALF_UP)
             c) UPDATE stock SET quantity = quantity + :qty,
                avg_cost = :new_avg, stock_amount = :new_amount, last_moved_at = now()
                WHERE warehouse_id=:w AND product_id=:p
                （入库为增量操作，不存在负库存风险，但仍要走同一原子语句）。
             d) 若该商品启用批次管理，则 UPSERT stock_batches（同批次数量累加，
                单位成本取该批次自身的入库成本，不参与移动平均）。
             e) 写入 stock_ledger：qty = +qty，balance_qty = 新数量，
                balance_amount = 新金额，unit_cost 为该行入库成本。
     步骤 6：更新 stock_docs 的 total_qty、total_amount，提交事务。
     步骤 7：若任一行的新平均成本导致 stock_amount 与 quantity*avg_cost 的量化结果不一致，
             以 stock_amount 为准（保证金额账与数量账各自自洽），并在日志中记录差异。
   销售出库（一个事务，本项目最关键的并发路径）：
     步骤 1：校验单据头（客户启用、明细非空、数量为正）。
     步骤 2：读取每行的当前库存与平均成本：
             SELECT product_id, quantity, avg_cost FROM stock
             WHERE warehouse_id=:w AND product_id IN (...) ORDER BY product_id
             （PostgreSQL 加 FOR UPDATE 并按 product_id 排序，避免死锁）。
     步骤 3：逐行校验 quantity >= 出库数量，不足则收集全部缺口后一次性返回 409/40903。
     步骤 4：对每一行执行条件 UPDATE 扣减：
             UPDATE stock SET quantity = quantity - :qty,
                    stock_amount = stock_amount - :cost_amount, last_moved_at = now()
             WHERE warehouse_id = :w AND product_id = :p AND quantity >= :qty;
             若 rowcount = 0 → 抛 409/40903 并回滚整个单据（这是防负库存的最后防线）。
     步骤 5：成本结转：unit_cost = 该商品出库前的 avg_cost（移动加权平均下，
             出库不改变平均成本，只减少数量与金额）；
             cost_amount = (qty * avg_cost).quantize(Decimal("0.01"), ROUND_HALF_UP)。
     步骤 6：毛利计算：gross_profit = sale_amount - cost_amount
             （sale_amount = (qty * unit_price).quantize(0.01)）。
     步骤 7：写入 stock_ledger：qty = -qty，unit_cost = avg_cost，
             balance_qty 与 balance_amount 为该笔之后的结存（必须由同一事务内计算）。
     步骤 8：若启用批次管理，按 expire_date 升序（FIFO）从批次表扣减，
             同一行拆成多条台账（每条带 batch_no），数量不足时回滚。
     步骤 9：更新单据合计，提交；返回含成本与毛利的明细。
   退货处理：
     采购退货（purchase_return）：方向为出库（qty 为负），
       必须校验累计退货量 <= 原入库量（按 product 汇总 src_doc_id 相同的退货单）；
       成本取原入库单该行的 unit_cost（不是当前平均值），并相应减少库存金额。
     销售退货（sale_return）：方向为入库（qty 为正），
       必须校验累计退货量 <= 原出库量；成本取原出库单该行的 unit_cost（结转成本），
       入库后按移动加权平均重算 avg_cost（与普通入库一致）。
   红冲（void）：
     仅允许对 confirmed 单据红冲；生成一张反向单据（doc_type 相同、qty 取反、
     doc_no 加 "-V" 后缀或独立 VOID 前缀），并写 ledger 的 biz_type = 'void_reverse'。
     原单状态置为 void（不删除，保留审计）。已红冲的单据不可再次红冲。
   库存调整：
     调整单每行指定目标数量或差异数量（本项目采用差异数量，正为盘盈、负为盘亏）。
     盘亏时走与出库相同的条件 UPDATE；盘盈时按当前 avg_cost 增加金额（不改变平均成本）。
     reason 字段必填。
   库存查询与可用量：
     available_qty = quantity - locked_qty。
     locked_qty 在"已创建未确认的出库单"场景中由业务写入（本项目把 draft 单的数量计入锁定）。
   对账自检任务（每日 02:00 执行）：
     步骤 1：按 (warehouse_id, product_id) 汇总台账：
             SELECT product_id, SUM(qty) AS ledger_qty, SUM(amount) AS ledger_amount
             FROM stock_ledger GROUP BY product_id（可按仓库维度过滤）。
     步骤 2：与 stock 逐行比对 quantity 与 quantity*avg_cost（允许 0.01 的金额舍入误差，
             即 abs(diff) <= 0.01 视为通过；数量必须精确相等）。
     步骤 3：输出差异清单到日志与 stock_alerts（alert_type='ledger_mismatch'），
             管理员通过接口可视化查看；严重不一致时按配置发送告警。
   报表计算：
     进销存汇总（按商品或按期间）：
       期初数量 = 该期间之前所有台账 qty 之和；
       入库 = 期间内 qty > 0 的合计；出库 = 期间内 qty < 0 的绝对值合计；
       期末 = 期初 + 入库 - 出库；必须与直接汇总的台账期末一致（接口返回 check 字段做自校验）。
     商品毛利表：按销售出库单汇总 sale_amount、cost_amount、gross_profit 与毛利率，
       退货单独列示为负数。
     库存周转天数 = 期间平均库存金额 / 期间出库成本金额 * 期间天数
       （平均库存金额 = (期初 + 期末) / 2；出库成本为 0 时返回 null）。
   预警计算：
     low_stock：quantity < safety_stock；over_stock：max_stock 非空且 quantity > max_stock；
     near_expiry：存在批次 expire_date <= today + 30 且 quantity > 0；
     no_movement：近 90 天无任何台账记录且 quantity > 0。
     每日生成快照写入 stock_alerts，看板读取当日快照（避免每次查询都全表扫描）。

3. 接口设计（HTTP 前缀 /api/v1，全部需 Authorization: Bearer <token>，除登录与 healthz）
   POST /api/v1/auth/login
     请求：{"username":"admin","password":"***"}
     响应 200：{"code":0,"data":{"access_token":"eyJ...","token_type":"bearer","expires_in":28800}}
     失败：401/40101、423/42301（连续 5 次失败锁定 15 分钟）。
   POST /api/v1/products   需 admin/purchaser
     请求：{"sku":"SKU001","name":"A 商品","spec":"500ml","unit":"瓶","category":"饮料",
           "barcode":"6901234567890","safety_stock":50,"max_stock":2000,
           "shelf_life_days":180,"is_batch_managed":true,"ref_purchase_price":12.5}
     响应 201：{"code":0,"data":{"product_id":11,"sku":"SKU001"}}
     失败：409/40901（SKU 已存在）、422/42209（安全库存大于最高库存）。
   GET /api/v1/products?keyword=饮料&category=饮料&low_stock=true&page=1&page_size=20
     响应 200：商品列表（含当前库存、可用量、平均成本、是否低库存）。
   PATCH /api/v1/products/{product_id}   需 admin/purchaser
     请求：{"safety_stock":80,"ref_sale_price":19.9}；响应 200。
     失败：404/40401、409/40901（停用商品不允许改动批次管理开关且有库存时）。
   POST /api/v1/products/import   需 admin
     请求：multipart/form-data，file=products.xlsx
            （表头：SKU、名称、规格、单位、分类、条码、安全库存、最高库存、保质期天数）
     响应 200：{"code":0,"data":{"imported":98,"failed":2,
              "errors":[{"row":37,"column":"SKU","reason":"SKU 已存在（与第 12 行重复）"}]}}
     失败：422/42208（缺少必需表头或文件格式错误）。
   GET /api/v1/products/export   需 admin/purchaser/viewer
     响应 200：xlsx 附件（含当前库存列）。
   POST /api/v1/suppliers、GET /api/v1/suppliers、PATCH /api/v1/suppliers/{id}   需 admin/purchaser
     请求/响应同商品模式；失败：409/40902（编码重复）。
   POST /api/v1/customers、GET /api/v1/customers、PATCH /api/v1/customers/{id}   需 admin/sales
   POST /api/v1/inbound   需 admin/purchaser
     请求：{"supplier_id":5,"warehouse_id":1,"biz_date":"2024-05-10","status":"confirmed",
           "items":[{"sku":"SKU001","qty":100,"unit_cost":12.5,"batch_no":"B240510",
           "production_date":"2024-05-01","expire_date":"2024-11-01"}],"remark":"首次到货"}
     响应 201：见 3.2（含每行的 stock_after 与 avg_cost_after）。
     失败：404/40401（SKU 不存在）、409/40901（商品停用）、422/42201（明细为空）、
           422/42202（SKU 重复）、422/42203（数量非正）、422/42204（精度超限）、
           422/42205（单价非法）、422/42207（保质期非法）、409/40902（供应商停用）。
   POST /api/v1/inbound/{doc_id}/return   需 admin/purchaser
     请求：{"biz_date":"2024-05-12","items":[{"product_id":11,"qty":10,"batch_no":"B240510"}]}
     响应 201：退货单（成本取原入库成本）；失败：409/40904（超可退数量）、409/40906（原单非 confirmed）。
   GET /api/v1/inbound?start=2024-05-01&end=2024-05-31&supplier_id=5&page=1
     响应 200：入库单分页列表；GET /api/v1/inbound/{doc_id} 返回详情（含明细与台账行）。
   POST /api/v1/inbound/{doc_id}/void   需 admin
     请求：{"reason":"录错供应商"}；响应 200：红冲成功并生成反向台账；
     失败：409/40907（已红冲或存在下游退货）。
   POST /api/v1/outbound   需 admin/sales
     请求：{"customer_id":8,"warehouse_id":1,"biz_date":"2024-05-11","status":"confirmed",
           "items":[{"sku":"SKU001","qty":30,"unit_price":19.9}],"remark":"客户自提"}
     响应 201：{"code":0,"data":{"doc_no":"OUT202405110001","total_amount":"597.00",
              "total_cost":"369.00","total_profit":"228.00",
              "items":[{"sku":"SKU001","qty":30,"unit_price":"19.9000",
              "cost_amount":"369.00","gross_profit":"228.00","stock_after":"150.000"}]}}
     失败：409/40903（库存不足，data 含缺口明细）、409/40909（负库存脏数据）、
           404/40401、422/42201、422/42203、409/40908（指定批次不足）。
   POST /api/v1/outbound/{doc_id}/return   需 admin/sales
     请求：{"biz_date":"2024-05-15","items":[{"product_id":11,"qty":5,"unit_price":19.9}]}
     响应 201：销售退货单（成本按原出库成本冲回，库存数量增加）；
     失败：409/40905（超可退数量）。
   GET /api/v1/outbound?start=...&end=...&customer_id=8&page=1   需登录
     响应 200：出库单列表；GET /api/v1/outbound/{doc_id} 返回详情（含成本与毛利）。
   POST /api/v1/outbound/{doc_id}/void   需 admin
     请求：{"reason":"客户撤单"}；响应 200：红冲并回补库存。
   POST /api/v1/adjust   需 admin
     请求：{"warehouse_id":1,"biz_date":"2024-05-31","reason":"月末盘点差异",
           "items":[{"product_id":11,"qty_diff":-3,"unit_cost":12.5},
                    {"product_id":12,"qty_diff":5}]}
     响应 201：{"code":0,"data":{"doc_no":"ADJ202405310001","total_qty":"2.000",
              "items":[{"sku":"SKU001","qty_diff":"-3.000","stock_after":"147.000"}]}}
     失败：422/42206（原因为空或过短）、409/40903（盘亏超过现有库存）。
   GET /api/v1/stock?warehouse_id=1&keyword=SKU0&category=饮料&low_stock=true&page=1
     响应 200：库存列表（见 3.4 字段），支持按 SKU/名称/分类过滤与低库存筛选。
   GET /api/v1/stock/{sku}?warehouse_id=1   需登录
     响应 200：单品库存详情 + 最近 10 笔台账；404/40401。
   GET /api/v1/stock/{sku}/ledger?start=2024-05-01&end=2024-05-31&page=1&page_size=50
     响应 200：台账分页（见 3.5 字段），字段含结存数量与结存金额；
     失败：404/40401。
   GET /api/v1/stock/ledger?doc_no=OUT202405110001   需登录
     响应 200：按单据查询台账（用于排障与审计）。
   GET /api/v1/stock/batches?sku=SKU001&expire_before=2024-11-01   需登录
     响应 200：批次库存列表（按到期日升序），含临期标记。
   GET /api/v1/alerts?date=2024-05-31&type=low_stock&page=1   需登录
     响应 200：预警列表（含 alert_type、当前数量、阈值、建议动作）。
   POST /api/v1/alerts/refresh   需 admin
     响应 200：{"code":0,"data":{"low_stock":12,"over_stock":3,
              "near_expiry":5,"no_movement":8,"ledger_mismatch":0}}
   GET /api/v1/reports/inout?start=2024-05-01&end=2024-05-31&group_by=product   需登录
     响应 200：进销存汇总（见 3.6，含 check.match 自校验字段）。
   GET /api/v1/reports/profit?start=2024-05-01&end=2024-05-31&group_by=product|customer
     需 admin/sales
     响应 200：{"rows":[{"key":"SKU001","sale_amount":"1791.00","cost_amount":"1107.00",
              "gross_profit":"684.00","gross_margin":0.3819,"return_amount":"-99.50"}],
              "summary":{"sale_amount":"...","gross_profit":"...","gross_margin":0.36}}
   GET /api/v1/reports/turnover?start=...&end=...   需登录
     响应 200：{"rows":[{"sku":"SKU001","avg_stock_amount":"1845.00",
              "out_cost_amount":"1107.00","turnover_days":49.9,"turnover_times":0.60}]}
   GET /api/v1/reports/reconcile?warehouse_id=1   需 admin
     响应 200：{"checked":180,"mismatched":[]}（对账自检结果，mismatched 为空表示一致）
   GET /api/v1/export/stock?warehouse_id=1   需登录
     响应 200：库存 xlsx 附件（含数量、平均成本、金额、安全库存、是否预警）。
   GET /api/v1/export/ledger?start=...&end=...   需 admin
     响应 200：台账 xlsx 附件（单据号、类型、SKU、数量、单价、金额、结存）。
   GET /dashboard   需登录
     行为：返回库存看板 HTML（总金额、预警数、今日单据数、Top10 库存金额、近 30 天出库柱状图）。
   GET /api/v1/healthz   公开
     响应 200：{"status":"ok","db":"ok","ledger_check":"ok|mismatch"}

4. 鉴权方式与安全要求
   - 口令使用 bcrypt（rounds=12）；JWT HS256，JWT_SECRET_KEY 从环境变量读取且 >= 32 字节。
   - 角色权限矩阵：viewer 只能查询与看报表；sales 可创建出库与客户；
     purchaser 可创建入库与供应商；admin 额外可红冲、调整库存、导入、查看对账。
   - 所有写接口都必须校验操作人角色，红冲与调整必须写审计日志（含原因与操作人）。
   - 金额与成本字段对 viewer 角色可见（这是内部系统），但对外接口（如未来开放给客户）
     必须单独设计视图，禁止复用内部响应模型。
   - 禁止在日志中记录供应商银行账号、客户信用额度等敏感信息。
   - 单据编号、SKU 等业务标识不承载敏感信息；导出文件按用户角色过滤字段。
   - 限流：单据创建 120 次/小时/用户；导入 5 次/小时/用户；报表与导出 30 次/小时/用户；
     登录 10 次/5 分钟/IP。
   - Excel 导入必须校验文件类型与大小（<= 5MB），并对每个单元格做类型转换与范围校验，
     禁止把解析异常直接抛给用户（返回逐行错误）。
   - 数据库口令、JWT 密钥、备份路径全部走环境变量；.env 加入 .gitignore。

5. 错误处理与并发事务注意点
   - 出库必须使用条件 UPDATE（WHERE quantity >= :qty）并检查 rowcount，
     这是防止负库存的唯一可靠手段；应用层的库存校验只用于给出友好错误信息。
   - 同一张单据内的多行必须在一个事务内完成；任何一行失败整体回滚（禁止部分成功）。
   - 为避免死锁，多行更新时按 product_id 升序处理（顺序一致可消除循环等待）。
   - PostgreSQL 下对 stock 行的读取使用 SELECT ... FOR UPDATE 并按 product_id 排序；
     SQLite 下用 BEGIN IMMEDIATE 获取写锁（配合 busy_timeout=5000）。
   - stock.quantity 上有 CHECK (quantity >= 0) 约束作为最后防线；
     若数据库抛约束错误，映射为 409/40903 而不是 500。
   - 台账的 balance_qty 与 balance_amount 必须在同一事务内、按处理顺序计算并写入，
     禁止事后异步补算（延迟会导致结存错乱）。同一商品的并发更新通过行锁串行化，
     因此结存顺序与 id 顺序一致。
   - 对账任务发现数量不一致时只告警不自动改数；
     修正必须通过调整单（有原因、有审计），保证任何变化都可追溯。
   - 红冲必须幂等：条件 UPDATE stock_docs SET status='void' WHERE id=? AND status='confirmed'，
     rowcount=0 时返回 409/40907，避免重复红冲导致库存被多次回补。
   - 采购/销售退货的可退数量校验要按产品汇总历史退货（含红冲状态判断），
     并在事务内用条件判断，防止并发退货超过原单数量。
   - 报表查询在数据量大时使用 INDEX 覆盖 + 按 biz_date 过滤；
     禁止无时间范围的台账全表导出（必须限制区间，最长 1 年）。

【五、运行方式与示例】

安装与启动：
  python -m venv .venv && .venv\Scripts\activate
  pip install -r requirements.txt
  set JWT_SECRET_KEY=please-change-this-32bytes-minimum
  set DATABASE_URL=sqlite:///./inventory.db
  set DEFAULT_WAREHOUSE_ID=1
  set STOCK_PRECISION=3
  alembic upgrade head
  python -m app.scripts.seed_demo    # 生成 1 个仓库、5 个供应商、30 个商品、200 笔示例单据
  uvicorn app.main:app --reload --port 8900
  浏览器打开 http://127.0.0.1:8900/dashboard 查看库存看板。

界面与交互说明：
  看板页 /dashboard 顶部四个数字卡片（库存总金额、低库存商品数、今日入库单数、今日出库单数）；
  中部是"Top10 库存金额"横向条形图与"近 30 天出库金额"柱状图（用内联 SVG 或简单的 CSS 条绘制，
  不引入前端框架）；底部是预警清单表格（点击 SKU 跳转到该商品的台账页）。
  所有写操作通过 /docs 的 Swagger UI 完成，方便逐步验证入库、出库、调整、红冲流程。

示例 1（采购入库）：
  请求：POST /api/v1/inbound
        {"supplier_id":5,"warehouse_id":1,"biz_date":"2024-05-10",
         "items":[{"sku":"SKU001","qty":100,"unit_cost":12.5,"batch_no":"B240510",
                   "production_date":"2024-05-01","expire_date":"2024-11-01"}]}
  响应：HTTP 201
        {"code":0,"message":"入库成功","data":{"doc_no":"IN202405100001",
         "doc_type":"purchase_in","total_qty":"100.000","total_amount":"1250.00",
         "items":[{"sku":"SKU001","name":"A 商品","qty":"100.000",
         "unit_cost":"12.5000","amount":"1250.00","stock_after":"180.000",
         "avg_cost_after":"12.3000"}]}}
示例 2（销售出库与成本毛利）：
  请求：POST /api/v1/outbound
        {"customer_id":8,"warehouse_id":1,"biz_date":"2024-05-11",
         "items":[{"sku":"SKU001","qty":30,"unit_price":19.9}]}
  响应：HTTP 201
        {"code":0,"data":{"doc_no":"OUT202405110001","total_amount":"597.00",
         "total_cost":"369.00","total_profit":"228.00",
         "items":[{"sku":"SKU001","qty":"30.000","unit_price":"19.9000",
         "cost_amount":"369.00","gross_profit":"228.00","stock_after":"150.000",
         "avg_cost_after":"12.3000"}]}}
示例 3（库存不足）：
  请求：POST /api/v1/outbound  {"customer_id":8,"warehouse_id":1,
        "biz_date":"2024-05-11","items":[{"sku":"SKU001","qty":500,"unit_price":19.9}]}
  响应：HTTP 409
        {"code":40903,"message":"库存不足，无法出库","data":{"shortages":[
         {"sku":"SKU001","name":"A 商品","available":"150.000","required":"500.000",
         "shortage":"350.000"}]}}
示例 4（并发出库，测试用例场景）：
  库存 150，20 个请求各出库 10
  结果：15 个请求成功（库存精确归零），5 个返回 409/40903；stock.quantity 恰为 0，
        台账 SUM(qty) 与 stock.quantity 一致。
示例 5（采购退货超量）：
  请求：POST /api/v1/inbound/12/return  {"items":[{"product_id":11,"qty":200}]}
        （原入库 100，已退货 0）
  响应：HTTP 409
        {"code":40904,"message":"退货数量超过可退数量","data":[
         {"sku":"SKU001","returnable":"100.000","requested":"200.000"}]}
示例 6（库存调整）：
  请求：POST /api/v1/adjust  {"warehouse_id":1,"biz_date":"2024-05-31",
        "reason":"月末盘点差异","items":[{"product_id":11,"qty_diff":-3}]}
  响应：HTTP 201
        {"code":0,"data":{"doc_no":"ADJ202405310001","total_qty":"-3.000",
         "items":[{"sku":"SKU001","qty_diff":"-3.000","stock_after":"147.000",
         "avg_cost_after":"12.3000"}]}}
示例 7（台账查询）：
  请求：GET /api/v1/stock/SKU001/ledger?start=2024-05-01&end=2024-05-31&page=1
  响应：HTTP 200
        {"code":0,"data":{"items":[{"biz_date":"2024-05-10","doc_no":"IN202405100001",
         "biz_type":"purchase_in","qty":"100.000","unit_cost":"12.5000",
         "amount":"1250.00","balance_qty":"180.000","balance_amount":"2214.00"},
         {"biz_date":"2024-05-11","doc_no":"OUT202405110001","biz_type":"sale_out",
         "qty":"-30.000","unit_cost":"12.3000","amount":"-369.00",
         "balance_qty":"150.000","balance_amount":"1845.00"}],
         "total":2,"page":1,"page_size":50,"pages":1}}
示例 8（异常输入）：
  请求：POST /api/v1/inbound  {"supplier_id":5,"warehouse_id":1,"biz_date":"2024-05-10",
        "items":[{"sku":"SKU001","qty":-5,"unit_cost":12.5},
                 {"sku":"SKU001","qty":10,"unit_cost":12.5}]}
  响应：HTTP 422
        {"code":42202,"message":"校验失败","data":{"errors":[
         {"index":0,"reason":"数量必须大于 0"},
         {"index":1,"reason":"SKU001 在同一单据中重复出现"}]}}

【六、验收标准】

[ ] 采购入库 100 件单价 12.5 后，stock.quantity=100、avg_cost=12.5000、stock_amount=1250.00。
[ ] 再次入库 100 件单价 12.1 后，avg_cost 按移动加权平均为 12.3000（保留 4 位小数）。
[ ] 出库 30 件后 avg_cost 不变（仍为 12.3000），quantity 减少 30，stock_amount 减少 369.00。
[ ] 出库数量超过库存时返回 409/40903 且 data 准确列出每个 SKU 的可用量与缺口。
[ ] 20 个并发出库请求抢 150 件库存（每次 10 件），最终成功 15 次、库存精确为 0，无负库存。
[ ] 数据库 CHECK 约束生效：手工 UPDATE 把 quantity 置为负数时被数据库拒绝。
[ ] 每一笔单据在 stock_ledger 中都有对应记录，数量方向正确（入库为正、出库为负）。
[ ] 台账的 balance_qty 连续：按 id 排序后，每一行的 balance_qty 等于上一行 balance_qty 加本行 qty。
[ ] 对账接口 /reports/reconcile 在所有测试场景（含红冲、退货、调整）后 mismatched 为空。
[ ] 采购退货超过原入库数量返回 409/40904，可退数量计算包含历史退货单。
[ ] 销售退货按原出库成本冲回，退货后 avg_cost 按移动加权平均重算且库存金额自洽。
[ ] 红冲入库单后库存与台账均正确回退；重复红冲返回 409/40907 且库存不被二次回补。
[ ] 调整单未填写原因或原因少于 5 字符返回 422/42206。
[ ] 启用批次管理的商品出库按到期日升序扣减（FIFO），台账中每条记录带正确的 batch_no。
[ ] 临期预警准确列出 30 天内到期的批次，数量为 0 的批次不出现在预警中。
[ ] 低库存预警在 quantity < safety_stock 时出现，等于安全库存时不预警（边界正确）。
[ ] 进销存汇总满足 期初 + 入库 - 出库 = 期末，接口返回的 check.match 为 true。
[ ] 毛利表金额与手工核对一致（sale_amount - cost_amount = gross_profit，误差为 0）。
[ ] 库存周转天数在出库成本为 0 时返回 null 而非除零错误。
[ ] Excel 导入 100 行含 2 行错误时返回 imported=98、failed=2 与逐行错误原因。
[ ] viewer 角色调用入库、出库、红冲、调整接口均返回 403。
[ ] 单据编号在 50 个并发创建请求下无重复，且当日流水连续（无跳号断档）。
[ ] 同一单据内 SKU 重复时返回 422/42202，不产生任何库存变动。
[ ] pytest 用例覆盖入库出库成本、并发扣减、台账平衡、红冲退货、报表汇总五类场景并全部通过。

【七、可选扩展】

1. 多仓库调拨（transfer）：一张调拨单同时减源仓与增目标仓，写两条台账并保证事务一致。
2. 批次成本法切换：支持 FIFO 计价（按批次成本逐笔结转）并与移动加权平均做对比报表。
3. 采购订单与到货流程：订单 → 收货 → 入库三步，支持部分到货与未到货追踪。
4. 供应商对账单：按供应商与账期生成本期采购与退货金额，导出对账函。
5. 库存占用与预留：销售订单确认后锁定库存（locked_qty），超时自动释放。
6. 条码扫描快速出入库（配合 python-barcode 生成条码标签）。
7. 数据备份与导出：每日全量导出 Excel 或 SQLite 备份文件到指定目录并保留 30 天。
8. 接入 APScheduler 每日 08:00 发送低库存预警邮件给采购负责人。

【八、涉及知识点】

- 进销存业务模型：单据（入库/出库/退货/调整）与台账（只增不改）的双表设计
- 移动加权平均成本算法与成本结转、毛利的正确计算
- Decimal 精确计算与量化（ROUND_HALF_UP）、数量与金额的精度设计
- 并发控制与防负库存：条件 UPDATE + rowcount、行锁、CHECK 约束兜底
- 事务边界：一张单据一个事务、多表写入的原子性与失败回滚
- 死锁避免：按 product_id 排序更新、缩短事务持有时间
- 单据编号的并发安全生成（序号表 + 行锁 / RETURNING）
- 库存对账思想：数量账与金额账的自校验与差异告警
- 批次管理与 FIFO 出库、保质期预警
- SQL 聚合报表：期初/期末、周转率、毛利汇总与索引优化
- 幂等与红冲设计：状态条件更新、反向单据、审计留痕
- openpyxl 批量导入导出的行级校验与错误报告
- 权限矩阵设计（采购、销售、查看、管理）与敏感字段保护
================================================================================
