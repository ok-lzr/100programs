================================================================================
项目编号：097                    难度等级：★★★★★（大型项目）
项目名称：自动化机器学习平台
所属分类：机器学习 / 数据科学 / 平台工程
建议工时：3 ~ 4 周（约 120 ~ 180 小时）
运行环境：Python 3.10+    第三方依赖：FastAPI、uvicorn、pandas、numpy、scikit-learn、SQLAlchemy、pydantic、joblib、matplotlib、APScheduler、pytest、httpx、openpyxl、xgboost 或 lightgbm（可选）
================================================================================

【一、项目背景与目标】

一个完整的机器学习项目里，真正花在“选模型”上的时间往往不到两成，其余都消耗在重复劳动
上：看一眼数据分布、判断缺失值怎么填、试试不同的编码方式、跑几个基线模型、随手调几组
超参、把结果记在表格里、过两周又想不起来当时用的是哪个预处理版本。更糟的是，手工流程
极易产生数据泄漏：在划分训练集之前就做了标准化、用全量数据拟合了编码器、把测试集混进
了特征选择——这些错误会让线下指标虚高，上线后立刻露馅。

本项目的目标是实现一个自动化机器学习（AutoML）平台：用户上传一份结构化数据并指定目标
列，平台自动完成数据探查、数据质量诊断、特征工程候选生成、训练/验证划分（严格防泄漏）、
多模型搜索、超参数调优、模型评估与解释、最终模型导出与一键预测，并生成可复现的实验报告。
平台把每一次实验的完整配置（数据哈希、划分策略、特征处理管道、模型与超参、随机种子、
指标）记录在案，任何一个历史实验都能被完整重现。

平台必须把“防泄漏”做成机制而不是口号：所有特征变换必须在 sklearn Pipeline 中声明，只
允许在训练折上 fit，验证折只 transform；时间序列任务必须使用按时间切分（TimeSeriesSplit）
并禁止随机打乱；对目标编码这类高风险变换，平台要给出显式警告并要求用户确认。这些约束
由测试用例固化。

目标用户是：想快速获得基线结果的数据分析入门者、希望把重复建模流程标准化的工程师、以及
需要理解 AutoML 内部机制（搜索空间、调参算法、评估协议）的学习者。项目明确不做：不做
深度学习与图像/文本/语音任务（只做结构化表格数据）、不提供分布式训练、不做在线推理集群、
不做数据标注。本平台只处理用户自己拥有合法使用权的数据，并在界面中提示不得上传个人敏感
信息与受限数据。

【二、功能需求清单】

本系统按四个子系统拆分：数据子系统（上传与探查）、建模子系统（特征工程、搜索与调优）、
结果子系统（评估、解释与报告）、平台端（Web 界面、任务与资源管理）。

1. 数据子系统
   1.1 数据上传：支持 CSV、Excel（xlsx）、Parquet 上传（单文件 ≤ 500 MB，行数 ≤ 500 万），
       上传后计算文件 sha256 作为数据集版本标识；同名不同内容视为新版本。
   1.2 数据探查：自动输出字段列表、推断类型（数值/类别/日期/文本/布尔）、缺失率、唯一值
       数、最小值/最大值/均值/中位数/标准差、分位数（1/25/50/75/99）、Top 10 高频取值。
   1.3 质量诊断：识别常量列、近似常量列（唯一值占比 < 0.1%）、高缺失列（> 60%）、高基数
       类别列（唯一值 > 1000）、高度相关特征对（|r| > 0.95）、疑似 ID 列（唯一值占比 > 95%
       且为字符串）、疑似泄漏列（与目标相关性 > 0.98 且非目标本身）并给出处理建议。
   1.4 目标列指定：分类任务要求目标列唯一值 ≤ 50 且每类样本 ≥ 20；回归任务要求目标列为
       数值型；不满足时给出明确错误与建议。
   1.5 数据划分：支持随机划分（默认 8:2）、分层划分（分类任务默认）、K 折交叉验证（默认
       5 折）、时间序列划分（需指定时间列，按时间升序切分）。划分索引必须记录到实验记录中。
   1.6 数据画像图：数值列直方图、类别列条形图、缺失矩阵图、目标分布图（分类为计数、
       回归为直方图）、相关性热力图，输出 PNG。
   1.7 数据版本与复用：数据集可命名、加标签、删除（软删除）；建模时按 data_version 引用，
       保证实验可复现。

2. 建模子系统
   2.1 任务类型识别：根据目标列与用户选择确定 classification（二分类/多分类）或 regression；
       评估指标随之切换。
   2.2 特征工程管道：由平台自动生成候选预处理步骤并组装为 sklearn Pipeline/ColumnTransformer：
       数值列——中位数/均值填充、缺失指示列、标准化/归一化/不处理、异常值截断（分位数）；
       类别列——众数填充、OneHot（低基数）/ 目标编码（中基数，带交叉验证）/ 频次编码（高
       基数）、有序类别序数编码；
       日期列——拆分为年/月/日/星期/是否月末/季度、可选的“距今天数”；
       文本列——字符长度、词数统计（不做深度文本建模）。
   2.3 自动特征选择：支持基于模型重要性（树模型）、方差阈值、相关系数阈值、递归特征消除
       （RFE）四种候选；特征选择必须在训练折内进行。
   2.4 模型候选集：分类——LogisticRegression、DecisionTree、RandomForest、ExtraTrees、
       GradientBoosting、HistGradientBoosting、KNN、SVC（小数据）、GaussianNB、
       XGBoost/LightGBM（若已安装）；
       回归——LinearRegression、Ridge、Lasso、ElasticNet、DecisionTree、RandomForest、
       ExtraTrees、GradientBoosting、HistGradientBoosting、KNN、SVR、
       XGBoost/LightGBM（若已安装）。
   2.5 搜索策略：支持三种模式——快速（每个模型默认参数，跑一遍基线）、标准（每个模型
       10 ~ 20 组随机搜索）、深度（随机搜索 + 贝叶斯优化式自适应采样，基于历史结果的
       探索/利用权衡）；搜索预算以“试验次数上限”和“总时长上限”双约束表达。
   2.6 超参调优：默认使用 RandomizedSearchCV（scoring 统一，cv=5，n_jobs 受控）；对深度
       模式实现一个轻量的序贯采样器（用历史得分拟合高斯过程代理或采用 TPE 风格的采样），
       不引入额外的 AutoML 框架。
   2.7 搜索空间定义：每个模型自带默认搜索空间字典（明确列出参数的取值范围与分布类型，
       如 uniform、log-uniform、int、categorical），用户可覆盖部分参数。
   2.8 训练与资源控制：并行度可配置（默认 n_jobs=2，避免打满 CPU）；单任务总超时（默认
       30 分钟）与单次试验超时；内存占用超限时任务失败并保留日志；任务在子进程中执行。
   2.9 早停与剪枝：对迭代型模型（梯度提升）支持 early_stopping；对明显劣于当前最优的
       参数组合提前终止（基于已完成的 CV 折均值与最优值的差距阈值）。
   2.10 集成与后处理：可选“取 Top 3 模型做软投票/平均”的集成；分类任务支持概率校准
       （CalibratedClassifierCV）与阈值调优（在验证集上最大化 F1 或满足目标召回率）。
   2.11 类别不平衡处理：支持 class_weight 自动、过采样（RandomOverSampler 的手写简化版，
      禁止在验证折上采样）、阈值移动；并在报告中说明所采用策略。
   2.12 模型导出：最优管道用 joblib 导出（含预处理与模型），同时写出 metadata.json
       （字段清单、类型、类别取值顺序、依赖版本、指标），保证跨进程可加载预测。

3. 结果子系统
   3.1 分类指标：accuracy、precision/recall/F1（macro 与 weighted）、ROC-AUC、PR-AUC、
       混淆矩阵、分类报告（每类 precision/recall/f1/support）；多分类 AUC 使用 one-vs-rest。
   3.2 回归指标：MAE、MSE、RMSE、R²、MAPE、中位数绝对误差、分位数损失（P50/P90）。
   3.3 交叉验证结果：每折得分、均值与标准差、折间差异最大的样本数（稳定性提示）。
   3.4 曲线图：分类——ROC 曲线、PR 曲线、混淆矩阵热力图、概率分布图；回归——预测值 vs
       真实值散点、残差图、残差分布。
   3.5 模型解释：树模型的特征重要性、线性模型的系数、置换重要性（permutation importance，
       在验证集上计算，避免泄漏）；可选 SHAP 风格的近似贡献（仅使用 sklearn 自带的
       partial dependence 与 permutation，不强制引入额外依赖）。
   3.6 学习曲线：训练集大小 vs 得分（判断高偏差/高方差）、验证曲线（单一超参 vs 得分）。
   3.7 排行榜：所有试验按主指标排序，展示模型、关键超参、CV 均值与标准差、训练耗时；
       支持按模型筛选。
   3.8 实验报告：生成 HTML 报告（含数据探查、搜索过程、排行榜、最优模型评估、解释、
       结论与限制说明）与 Excel 报告（数据画像页、排行榜页、指标页、特征重要性页）。
   3.9 一键预测：上传与训练数据字段一致的新数据（CSV），平台用最优管道预测并返回结果
       CSV（分类含预测类别与各类概率，回归含预测值），字段缺失或类型不符时给出逐行错误。
   3.10 实验对比：可选择最多 5 个历史实验对比指标与最优参数，输出对比图与表格。
   3.11 可复现性：实验记录 data_version、code_version（平台版本）、pipeline_spec_json、
       best_params、random_seed、包版本；提供“重跑此实验”按钮，重跑结果必须与原始指标
       完全一致（浮点允许 1e-9 误差）。

4. 平台端子系统（Web 界面与任务管理）
   4.1 概览页：数据集数、实验数、运行中任务、失败任务、CPU/内存占用（psutil 或其他可用
       方式，或仅展示任务并发数）、最近实验列表。
   4.2 数据集页：上传、列表、预览前 100 行、数据画像图、质量诊断报告、删除。
   4.3 新建实验页：选择数据集与目标列、任务类型、划分方式、搜索模式、试验次数上限、
       时间上限、随机种子、启用的模型集合、特征选择方式、类别不平衡策略。
   4.4 实验详情页：进度（已完成试验数/总数）、当前最优模型与指标、实时排行榜（每次试验
       完成即追加）、日志查看（最近 200 行）、取消任务按钮。
   4.5 结果页：指标卡片、曲线图、混淆矩阵/残差图、特征重要性、学习曲线、报告下载、
       模型下载、一键预测入口。
   4.6 历史与对比页：实验列表（按时间/指标排序）、筛选、多选对比。
   4.7 任务管理：任务队列状态、并发上限设置、取消/重试任务、失败原因查看。
   4.8 资源与配额：单个用户最大并发任务数、最大数据集数、最大磁盘占用；超限时拒绝并
       给出明确提示。
   4.9 审计与隐私：上传数据集需勾选“我确认拥有该数据的使用权且不含个人敏感信息”；
       所有上传、导出、删除操作写入 audit_log；数据集软删除后 7 天内可恢复，之后物理删除。

5. 模块清单（源码结构）
   5.1 app/main.py                FastAPI 应用与生命周期。
   5.2 app/config.py              配置（数据目录、模型目录、报告目录、并发、超时、上限）。
   5.3 data/ingest.py             文件读取（CSV/Excel/Parquet）、编码探测、sha256 计算。
   5.4 data/profile.py            数据探查与统计、类型推断、画像图。
   5.5 data/quality.py            质量诊断规则与建议生成。
   5.6 data/split.py              随机/分层/K 折/时间序列划分（返回索引）。
   5.7 features/pipeline.py       自动预处理管道构建（ColumnTransformer 组装）。
   5.8 features/selection.py      特征选择策略实现。
   5.9 features/encoders.py       目标编码（带内部 CV）、频次编码等自定义 Transformer
                                  （必须实现 fit/transform 且只在训练折 fit）。
   5.10 search/spaces.py          各模型默认搜索空间定义。
   5.11 search/sampler.py         随机采样器与序贯采样器（TPE 风格简化实现）。
   5.12 search/engine.py          搜索主循环、剪枝、超时控制、结果汇总。
   5.13 eval/metrics.py           分类与回归指标计算与曲线数据生成。
   5.14 eval/plots.py             matplotlib 图表生成（Agg 后端）。
   5.15 eval/explain.py           特征重要性与置换重要性、学习曲线。
   5.16 report/builder.py         HTML 与 Excel 报告生成。
   5.17 app/runner.py             子进程任务执行、进度回传、取消与超时。
   5.18 app/api/                  datasets、experiments、models、predict、reports 路由。
   5.19 predict/service.py        模型加载、字段校验、批量预测与结果导出。
   5.20 tests/                    单元、集成、防泄漏、可复现性、API 测试。

6. 接口清单（HTTP，节选核心）
   6.1 POST /api/v1/datasets                  上传数据集（multipart，含 confirm_rights 勾选）
   6.2 GET  /api/v1/datasets                  数据集列表
   6.3 GET  /api/v1/datasets/{id}/profile     数据探查结果
   6.4 GET  /api/v1/datasets/{id}/quality     质量诊断报告
   6.5 GET  /api/v1/datasets/{id}/preview?rows=100  预览数据
   6.6 DELETE /api/v1/datasets/{id}           软删除数据集
   6.7 POST /api/v1/experiments               创建实验 {dataset_id, target, task_type,
       split, search_mode, max_trials, time_budget, seed, models, feature_selection,
       imbalance}
   6.8 GET  /api/v1/experiments/{id}          实验状态与进度
   6.9 GET  /api/v1/experiments/{id}/leaderboard  排行榜
   6.10 GET  /api/v1/experiments/{id}/logs?tail=200  任务日志
   6.11 POST /api/v1/experiments/{id}/cancel  取消实验
   6.12 POST /api/v1/experiments/{id}/rerun   重跑实验
   6.13 GET  /api/v1/experiments/{id}/metrics 最优模型指标
   6.14 GET  /api/v1/experiments/{id}/charts/{name}  图表（roc/pr/confusion/residual/
       importance/learning）
   6.15 POST /api/v1/experiments/{id}/report  生成报告并返回下载链接
   6.16 GET  /api/v1/models/{experiment_id}/download  下载 joblib 模型包
   6.17 POST /api/v1/predict                  一键预测（上传 CSV + model_id）
   6.18 POST /api/v1/experiments/compare      多实验对比
   6.19 GET  /api/v1/system/status            队列与并发状态

7. 数据模型概览
   7.1 datasets(id TEXT PK, name TEXT, filename TEXT, sha256 TEXT, size_bytes BIGINT,
       rows INT, columns INT, storage_path TEXT, deleted_at TEXT NULL, created_by TEXT,
       created_at TEXT)  索引 uniq_sha256(sha256)
   7.2 dataset_columns(id PK, dataset_id FK, name TEXT, dtype TEXT, inferred_type TEXT,
       missing_rate REAL, unique_count INT, stats_json TEXT)
   7.3 experiments(id TEXT PK, dataset_id FK, target TEXT, task_type TEXT, split_json TEXT,
       search_mode TEXT, max_trials INT, time_budget_s INT, seed INT, models_json TEXT,
       feature_selection TEXT, imbalance TEXT, state TEXT, progress INT, total_trials INT,
       done_trials INT, best_model TEXT, best_params_json TEXT, metrics_json TEXT,
       pipeline_spec_json TEXT, data_version TEXT, code_version TEXT, started_at TEXT,
       finished_at TEXT, error TEXT, created_by TEXT)
   7.4 trials(id PK, experiment_id FK, trial_no INT, model TEXT, params_json TEXT,
       cv_scores_json TEXT, mean_score REAL, std_score REAL, fit_seconds REAL,
       state TEXT, pruned INT)
       索引 idx_exp_mean(experiment_id, mean_score desc)
   7.5 metrics_detail(id PK, experiment_id FK, scope TEXT, name TEXT, value REAL,
       extra_json TEXT)  用于存每折得分、每类指标、曲线点数据
   7.6 models(id TEXT PK, experiment_id FK, model_path TEXT, metadata_json TEXT,
       size_bytes BIGINT, created_at TEXT)
   7.7 predictions(id TEXT PK, model_id FK, source_file TEXT, rows INT, output_path TEXT,
       error_rows INT, created_at TEXT)
   7.8 reports(id TEXT PK, experiment_id FK, html_path TEXT, xlsx_path TEXT,
       created_at TEXT)
   7.9 audit_log(id PK, user_id, action, target_type, target_id, detail_json, ip,
       created_at)
   7.10 说明：曲线点（ROC/PR/学习曲线）数据量较大，单独写入 metrics_detail 并用
        scope='curve:roc' 区分；排行榜查询只依赖 trials 表，避免扫描大表。

【三、里程碑拆解（建议 4 ~ 6 个阶段）】

阶段一：数据上传、探查与质量诊断（约 20 小时）
  产出：文件读取与编码处理、sha256 版本、类型推断、统计画像、质量诊断规则、画像图生成、
       数据集页面与预览接口。
  验收：上传 100 万行 × 40 列 CSV 后探查结果正确；构造含常量列、高缺失列、疑似泄漏列的
       数据能被准确识别。

阶段二：划分与特征工程管道（约 26 小时）
  产出：四种划分策略（含时间序列）、自动 ColumnTransformer 构建、自定义编码器（目标编码
       带内部 CV、频次编码）、特征选择四种策略、管道序列化保存。
  验收：特征处理全部在 Pipeline 内完成，测试证明验证折未参与任何 fit；时间序列划分不
       打乱顺序。

阶段三：搜索空间与调优引擎（约 28 小时）
  产出：各模型搜索空间、随机采样器、序贯采样器、搜索主循环、剪枝与超时控制、试次记录、
       排行榜实时更新、子进程执行与取消。
  验收：标准模式 10 个模型共 150 次试验能按时完成；取消任务后子进程被正确终止且无残留。

阶段四：评估、解释与报告（约 22 小时）
  产出：分类与回归全套指标、曲线数据与图表、置换重要性与学习曲线、阈值调优与概率校准、
       HTML/Excel 报告生成。
  验收：指标与 sklearn 官方实现对照一致（误差 < 1e-9）；报告在浏览器可正常打开且图表完整。

阶段五：Web 平台完善（约 22 小时）
  产出：新建实验表单、进度与日志实时查看、结果页、历史与对比、一键预测、模型下载、
       配额与审计、隐私确认勾选。
  验收：从上传数据到下载模型的全流程可在界面上完成；预测接口对字段缺失给出逐行错误。

阶段六：测试、性能与部署（约 18 小时）
  产出：覆盖率报告、防泄漏专项测试、可复现性测试、大数据集性能基准、Dockerfile 与部署
       文档、使用手册与指标口径说明。
  验收：100 万行 × 50 列数据集的“快速模式”实验在 10 分钟内完成；同一实验重跑指标一致。

【四、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；类型注解全覆盖；所有自定义 Transformer 必须遵守
   sklearn 的 fit/transform 契约（继承 BaseEstimator、TransformerMixin）。
2. 允许使用的库：标准库（hashlib、json、subprocess、multiprocessing、time、logging、
   dataclasses、enum）；第三方限 FastAPI、uvicorn、pandas、numpy、scikit-learn、
   SQLAlchemy、pydantic、joblib、matplotlib、APScheduler、openpyxl、httpx、pytest、
   pytest-asyncio；可选 xgboost 或 lightgbm（缺失时平台自动跳过并在界面提示）。
   禁止引入 auto-sklearn、TPOT、FLAML、PyCaret、Optuna、hyperopt 等现成 AutoML/调参
   框架（调优算法必须自行实现），禁止引入 SHAP 作为硬依赖。
3. 禁止事项：禁止在任何划分之外的数据上 fit 预处理器；禁止在划分前做缺失值填充、标准化
   或编码（必须全部在 Pipeline 内）；禁止时间序列任务随机打乱；禁止伪造或补全缺失指标
   （指标无法计算时必须显示“不适用”并说明原因，例如单类数据无法计算 AUC）；禁止把用户
   上传的原始数据写入日志；禁止在报告中删除不利于结论的信息（如折间方差过大）。
4. 防泄漏硬性要求：所有特征变换必须在 Pipeline 中声明；自定义编码器的内部 CV 必须使用
   训练折内部的划分；置换重要性与特征选择使用验证折或交叉验证折；目标编码必须带平滑
   与内部 CV，并在文档中说明其风险；实验创建时若检出与目标相关性 > 0.98 的特征列，必须
   弹出确认并在报告中标注。
5. 代码组织：data（读取与探查）、features（变换）、search（调优）、eval（评估与解释）、
   report（报告）五个包必须与 Web 层解耦，可被命令行直接调用；任务执行通过 runner 统一
   入口，禁止在请求线程内运行训练；自定义 Transformer 集中在 features/encoders.py 并各自
   有单元测试。
6. 可复现性：所有随机过程必须使用显式 seed（numpy、random、sklearn 的 random_state 都要
   设置）；实验记录完整配置；相同配置重跑结果一致；包的版本号写入 metadata.json 并在
   报告中展示。
7. 编码规范：PEP 8；公有函数必须有类型注解与 docstring（说明输入形状、返回结构与可能抛出
   的异常）；训练日志使用结构化 JSON 行并包含 experiment_id 与 trial_no；禁止 print 调试。
8. 测试要求：覆盖率 ≥ 75%；必须包含：防泄漏测试（构造“目标泄漏特征”，断言加入后验证集
   指标的提升符合预期且平台给出泄漏警告）、时间序列划分测试、目标编码内部 CV 测试、
   指标与 sklearn 对照测试、可复现性测试（两次重跑指标一致）、自定义 Transformer 的
   fit/transform 契约测试、API 与任务取消测试。
9. 性能要求：单机 4 核 8 GB；100 万行 × 50 列的“快速模式”（10 个模型基线）≤ 10 分钟；
   标准模式 150 次试验 ≤ 40 分钟（n_jobs=2）；数据探查 100 万行 ≤ 60 秒；预测 10 万行
   ≤ 20 秒；内存峰值不超过 6 GB。
10. 隐私与合规：上传数据前必须由用户确认“拥有合法使用权且不含个人敏感信息（身份证号、
    手机号、银行卡号、医疗记录等）”；平台不得把数据用于训练以外的任何用途、不得外传；
    数据集软删除后 7 天内可恢复，之后物理删除文件与派生模型（用户可选择保留模型）；
    审计日志记录上传、下载、删除、预测操作；文档需说明平台的数据保留策略与删除方式；
    若数据含个人信息的匿名化处理说明必须由用户负责完成。

【五、设计要点】

1. 数据结构：
   1.1 DatasetMeta(id, name, sha256, rows, cols, columns: list[ColumnMeta], path)。
   1.2 ColumnMeta(name, dtype, inferred_type, missing_rate, unique_count, stats)。
   1.3 SplitSpec(strategy, test_size, n_splits, time_column, stratify, seed) → 产生
       train_idx / valid_idx / folds: list[(train_idx, valid_idx)]。
   1.4 TrialRecord(trial_no, model, params, cv_scores, mean, std, fit_seconds, state)。
   1.5 PipelineSpec(steps: list[StepSpec]，每个 StepSpec 含 name、transformer 类型、作用
       列集合、参数) —— 序列化为 JSON 存放，可由 builder 重建管道。
   1.6 SearchSpace(param_name → Distribution(type, low, high, choices, log))。
2. 关键算法与流程：
   2.1 实验主流程：读取数据 → 计算 sha256 与版本 → 质量诊断 → 划分（记录索引）→ 构建候选
       模型与搜索空间 → 对每个试验：构建管道 → 在训练折 fit → 在验证折 evaluate → 记录
       得分（若失败则记录异常与参数）→ 更新排行榜与剪枝阈值 → 达到预算后选最优 → 用全部
       训练数据重训最优配置（保持 Pipeline 结构）→ 在保留测试集上最终评估 → 生成解释与
       报告 → 导出模型。
   2.2 目标编码实现：fit 时对训练折做内部 K 折（默认 5），对每折用其余折统计类别均值并
       映射，避免用自身样本的均值编码自己；对未见类别使用全局均值；加入平滑
       (n × mean + m × prior) / (n + m)，m 默认 10。
   2.3 序贯采样（深模式）：前 30% 试验使用随机采样建立初始分布 → 之后使用 TPE 风格采样：
       把历史参数按得分分为“好组”（前 25%）与“差组”，对每组参数维度估计核密度（高斯或
       分类分布），以“好组密度 / 差组密度”作为采样目标，用拒绝采样生成候选；每轮只采样
       一个候选以避免过拟合历史。
   2.4 剪枝：若某试验在已完成折上的均值已经比当前最优低出 (1.5 × 当前最优标准差) 且完成
       折数 ≥ 3，则提前终止该试验并标记 pruned=1。
   2.5 阈值调优：分类任务在验证集上遍历阈值（0.01 ~ 0.99，步长 0.01），按目标指标（默认
       F1，可选“召回 ≥ x”约束下最大化精确率）选择最优阈值并写入模型 metadata。
   2.6 最终评估：使用保留测试集（若用户选择交叉验证则使用折外预测拼接的 OOF 结果）计算
       最终指标，避免用训练数据报告成绩；报告中必须同时给出交叉验证指标与保留集指标。
   2.7 预测流程：加载 joblib 管道与 metadata → 校验输入列（缺失列报错、多余列警告并忽略）
       → 按 metadata 中的类型转换（日期解析、类别对齐）→ 批量 predict/predict_proba →
       输出 CSV（原数据 + 预测列），失败行记录原因并统计。
3. 数据库主要表结构已在功能清单第 7 节列出；补充说明：
   3.1 trials 表按 experiment_id 建索引，排行榜用一条 SQL 取 Top 20，禁止在 Python 中全量
       排序；曲线数据单独存放避免排行榜查询变慢。
   3.2 大字段（pipeline_spec_json、metrics_json）使用 JSON 类型；实验删除时级联删除
       trials、metrics_detail、reports 记录，但模型文件可选择保留。
   3.3 数据集文件按 sha256 存于 storage/datasets/{前2位}/{sha256}.parquet（上传后统一转为
       Parquet 加速后续读取），原始文件可保留 7 天后删除。
   3.4 模型文件存 storage/models/{experiment_id}/model.joblib 与 metadata.json。
4. 接口设计要点：
   4.1 实验创建为异步：返回 202 与 experiment_id，前端轮询进度（1 秒）或用 Server-Sent
       Events 推送试验完成事件。
   4.2 进度字段包含 done_trials、total_trials、当前模型、ETA 秒数（基于已完成试验平均
       耗时估算）。
   4.3 所有图表接口返回 PNG（Agg 后端），文件名带实验 id 与图类型，便于浏览器缓存。
   4.4 参数校验严格：max_trials ≤ 500、time_budget ≤ 4 小时、n_jobs ≤ CPU 核数、seed 必须
       为整数；非法组合返回 400 并说明具体原因。

【六、运行方式与示例】

1. 安装与初始化
   python -m venv .venv && .venv\Scripts\activate
   pip install fastapi uvicorn pandas numpy scikit-learn sqlalchemy pydantic joblib
   pip install matplotlib apscheduler openpyxl httpx pytest pytest-asyncio
   pip install xgboost          （可选，未安装则自动跳过对应模型）
   copy .env.example .env       （填写 DB_URL、STORAGE_ROOT、MAX_CONCURRENT_JOBS）
   python -m app.cli initdb
2. 启动
   uvicorn app.main:app --host 127.0.0.1 --port 8030
   浏览器访问 http://127.0.0.1:8030
3. 命令行运行实验（便于自动化测试与批量作业）
   python -m app.cli run --data D:\data\titanic.csv --target Survived --task classification
          --mode quick --trials 40 --seed 42 --out reports/local_run
4. 示例一（上传数据集）
   请求：POST /api/v1/datasets（multipart：file=sales_2023.csv，confirm_rights=true）
   响应：201
   {"dataset_id": "ds-4a91", "sha256": "c7f1...", "rows": 482113, "columns": 27,
    "inferred": {"numeric": 15, "categorical": 8, "datetime": 3, "text": 1},
    "missing_overall": 0.041}
5. 示例二（质量诊断节选）
   请求：GET /api/v1/datasets/ds-4a91/quality
   响应：200
   {
     "constant_columns": ["currency"],
     "high_missing": [{"name": "promo_code", "missing_rate": 0.72}],
     "high_cardinality": [{"name": "order_id", "unique": 482113}],
     "suspected_id": ["order_id", "customer_uuid"],
     "suspected_leak": [{"name": "refund_amount", "corr_with_target": 0.991}],
     "correlated_pairs": [{"a": "gross_sales", "b": "net_sales", "r": 0.987}],
     "advice": ["order_id 建议作为 ID 列排除", "refund_amount 与目标高度相关，请确认
                是否为泄漏特征"]
   }
6. 示例三（创建实验并轮询）
   请求：POST /api/v1/experiments
   {"dataset_id": "ds-4a91", "target": "is_churn", "task_type": "classification",
    "split": {"strategy": "stratified", "test_size": 0.2, "seed": 42},
    "search_mode": "standard", "max_trials": 120, "time_budget_s": 1800,
    "models": ["logistic", "random_forest", "hist_gbdt", "xgboost"],
    "feature_selection": "model_importance", "imbalance": "class_weight"}
   响应：202 {"experiment_id": "exp-2f77b1", "state": "queued", "total_trials": 120}
   轮询：GET /api/v1/experiments/exp-2f77b1
   响应：200 {"state": "running", "done_trials": 63, "total_trials": 120,
         "current_model": "hist_gbdt", "eta_seconds": 412,
         "best": {"model": "hist_gbdt", "mean_cv_f1": 0.8412,
                  "params": {"learning_rate": 0.06, "max_depth": 6, "max_iter": 300}}}
7. 示例四（排行榜与最终指标）
   请求：GET /api/v1/experiments/exp-2f77b1/leaderboard?top=3
   响应：200
   {"items": [
     {"rank": 1, "model": "hist_gbdt", "mean_cv_f1": 0.8412, "std_cv_f1": 0.0091,
      "fit_seconds": 38.2, "params": {"learning_rate": 0.06, "max_depth": 6}},
     {"rank": 2, "model": "xgboost", "mean_cv_f1": 0.8389, "std_cv_f1": 0.0114,
      "fit_seconds": 52.7, "params": {"eta": 0.08, "max_depth": 5, "n_estimators": 400}},
     {"rank": 3, "model": "random_forest", "mean_cv_f1": 0.8201, "std_cv_f1": 0.0133,
      "fit_seconds": 21.4, "params": {"n_estimators": 500, "max_depth": 12}}
   ]}
   最终指标（保留测试集）：{"roc_auc": 0.8971, "f1": 0.8344, "precision": 0.8512,
    "recall": 0.8183, "accuracy": 0.8802, "threshold": 0.47}
8. 示例五（一键预测与异常输入）
   请求：POST /api/v1/predict（multipart：file=new_customers.csv，model_id="md-9c13"）
   响应：200 {"rows": 5000, "predictions": 412, "output_url":
         "/api/v1/predictions/pd-31af/download", "error_rows": 3,
         "errors": [{"line_no": 88, "reason": "MISSING_COLUMN: tenure_months"},
                    {"line_no": 412, "reason": "INVALID_DATE: signup_date='2023-13-40'"},
                    {"line_no": 1503, "reason": "UNKNOWN_CATEGORY_FILLED_PRIOR:
                     plan_type='enterprise_plus'"}]}
   字段全部缺失时：响应 400
   {"code": "SCHEMA_MISMATCH", "message": "缺少 12 个必需列，请检查文件表头",
    "detail": {"missing": ["tenure_months", "monthly_charge", "..."]}}

【七、验收标准】

[ ] 1. 上传 500 MB 以内 CSV/Excel/Parquet 均能正确读取，编码（UTF-8/GBK）自动识别无误。
[ ] 2. 数据探查输出完整：类型、缺失率、唯一值、分位数、Top 10 取值，与 pandas 手工计算
      一致。
[ ] 3. 质量诊断能识别常量列、高缺失列、高基数列、疑似 ID 列、疑似泄漏列与高相关列对，
      并给出可执行建议。
[ ] 4. 所有预处理步骤均在 Pipeline 内完成：测试用例证明验证折数据在 fit 阶段未被使用
      （通过记录 fit 调用时的数据索引断言）。
[ ] 5. 时间序列划分严格按时间升序，训练集所有日期早于验证集，且不打乱。
[ ] 6. 目标编码带内部 CV 与平滑：与“直接用全量标签均值编码”相比，验证集 F1 提升且无
      泄漏（对照测试通过）。
[ ] 7. 标准模式（4 个模型、120 次试验）在规定预算内完成，排行榜按 CV 均值正确排序。
[ ] 8. 剪枝生效：构造一批劣质参数，pruned 试验数 > 0 且总耗时低于不剪枝的对照组。
[ ] 9. 指标与 sklearn 官方实现对照一致（accuracy、f1、roc_auc、rmse、r2 误差 < 1e-9）；
      单类数据时 AUC 显示“不适用”并说明原因。
[ ] 10. 重跑实验的指标与原始一致（浮点误差 < 1e-9），且使用相同的划分索引。
[ ] 11. 模型导出后可在新进程中加载并对同一样本给出相同预测；metadata 中的列顺序与
      类别映射完整。
[ ] 12. 预测接口对缺失列、非法日期、未知类别分别给出准确的行号与原因，合法行正常预测。
[ ] 13. HTML 与 Excel 报告完整包含数据画像、排行榜、最优模型评估、特征重要性与限制说明。
[ ] 14. 取消运行中的实验后子进程被终止、状态为 cancelled、无残留进程与临时文件。
[ ] 15. pytest 覆盖率 ≥ 75%，含防泄漏、时间序列划分、目标编码、指标对照、可复现性五类
      专项测试；上传接口在未勾选数据权利确认时返回 400。

【八、可选扩展】

1. 增加特征自动衍生：数值列两两加减乘除、日期差值、类别交叉组合，并做有效性筛选。
2. 增加多目标与多标签分类支持，评估指标扩展为 Hamming Loss、子集准确率。
3. 增加模型蒸馏与轻量化：用最优模型蒸馏出小模型，比较精度与推理耗时。
4. 增加在线推理服务：把最优管道包装为独立 HTTP 服务（可与 100 项目共用部署设施）。
5. 增加实验追踪集成（本地实现 MLflow 风格的 run 记录）与实验标签体系。
6. 增加数据漂移检测：对新数据与训练数据做分布对比（PSI、KS 检验），超阈值告警。
7. 增加 GPU 支持与分布式调优（需扩展依赖与资源调度，属进阶方向）。

【九、涉及知识点】

- 机器学习流程：数据探查、划分协议、交叉验证、基线模型、评估指标与选择偏差
- 数据泄漏：预处理泄漏、目标编码泄漏、时间序列泄漏、泄漏特征识别与防护机制
- scikit-learn 进阶：Pipeline 与 ColumnTransformer、自定义 Transformer 契约、
  cross_validate、HalvingSearch 的思想与手写实现
- 超参调优：网格/随机/序贯搜索、TPE 风格采样的直觉、剪枝与预算控制
- 特征工程：缺失值策略、编码方式（OneHot/目标/频次/序数）、缩放、异常值处理、特征选择
- 评估与解释：ROC/PR 与阈值选择、混淆矩阵、置换重要性、学习曲线与偏差方差诊断
- 工程化：子进程任务执行与取消、超时与资源限制、可复现性（种子与版本记录）、
  joblib 模型持久化与跨进程加载
- 平台与合规：异步任务与进度上报、报告生成、数据权利确认、隐私与数据删除策略
================================================================================
