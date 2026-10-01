================================================================================
项目编号：090                    难度等级：★★★★☆（中型项目收尾，偏难）
项目名称：垃圾短信与邮件分类器
所属分类：人工智能入门 / 文本分类与在线服务
建议工时：4 ~ 6 天
运行环境：Python 3.10+    第三方依赖：scikit-learn、pandas、numpy、jieba、joblib、FastAPI、uvicorn、pytest
================================================================================

【一、项目背景与目标】

垃圾短信与钓鱼邮件的共同特点是量大、变体快、内容短。它们会故意插入空格、用同音字替换、
把网址拆开写（如 “http:// a.b-c .cn”），也会不断更换关键词来绕过固定规则。用正则关键词
列表封堵的办法维护成本极高：运营人员今天加一条规则，明天发件人换个说法就失效了。

本项目实现一个垃圾信息分类器，覆盖从语料预处理、特征工程、多模型对比、评估指标到在线
预测接口的完整流程。与单纯调用现成库不同，本项目强调三件事：一是针对短文本与规避手段做
专门的归一化与特征设计；二是用严格的评估方法（分层交叉验证、独立测试集、ROC-AUC 与
PR-AUC、阈值分析）给出可信的性能结论；三是把最优模型封装成可被其他程序调用的 HTTP 接口，
支持单条与批量预测，并带有输入限长、限流与不落库原文的隐私约束。

目标用户是需要给自家应用加一道反垃圾防线的开发者、想做文本分类工程化练习的学生。项目完成
后，可以得到一个可在本机启动的预测服务、一份多模型对比报告、一份阈值选择建议（在不同误报
率下的召回率），以及一个可解释的判定依据（哪些词元促成了“垃圾”的判定）。

数据来源与规模：使用公开的垃圾信息语料，主要包括——SMS Spam Collection（英文短信语料，
共 5574 条，其中 spam 747 条、ham 4827 条，来自 UCI 机器学习仓库）、TREC 2006 与
2007 Spam Track 公开邮件语料（英文邮件，数十万封，需按官方说明使用）、公开的中文垃圾短信
语料（常见规模 5 万至 10 万条，含正常与垃圾两类）。教学中建议以 SMS Spam Collection 为
主数据集（规模小、类别不平衡特征明显，适合讲清楚指标口径），另选一份中文短信语料做跨语种
或跨语言的第二实验，总规模控制在 5 万条以内以保证本机可训练。

数据划分：先按文本内容去重并去除训练语料中的占位符；采用分层抽样按 7:1.5:1.5 划分训练集、
验证集、测试集，且按语料来源分层，避免同一来源的相似模板集中落到某一侧。训练集内部用
5 折分层交叉验证做模型选择与超参数搜索；测试集仅在最终评估时使用一次。数据量说明：若使用
SMS Spam Collection，测试集约 836 条，其中 spam 约 112 条，因此报告中必须同时给出
spam 类的精确率/召回率，而不能只报准确率（全判为正常也能得到 86.6% 的准确率，必须写清
这一点作为教学要点）。

隐私与版权声明：语料仅用于学习与研究，使用前须确认其许可协议并按要求引用来源，不得再分发
原始数据文件，不得用于任何商业服务；如使用自有的真实短信或邮件数据，必须先脱敏（去除手机
号、邮箱地址、姓名、验证码、订单号等），并取得数据所有者同意；预测服务不得持久化用户提交
的原文，日志只记录字符数与判定结果；严禁使用本工具拦截、篡改他人通信或从事任何违法活动。

【二、功能需求清单】

1. 核心功能
   1.1 语料加载：支持 CSV（列名可配置）与目录结构（spam/ 与 ham/ 两个子目录）；支持
       多语料合并并保留 source 字段用于分层划分与分组评估。
   1.2 文本归一化（针对规避手段）：统一转小写；全角转半角；去除零宽字符与不可见控制符；
       还原被拆分的 URL（把 “http:// a.b-c .cn” 这类被空格打断的域名重组，规则为先标记
       疑似协议头，再贪婪拼接后续非空格片段直到遇到明显分隔）；压缩连续空白；
       把常见同音或形近替换还原（如把数字 0 与字母 o 的混用按上下文归一，提供可配置的
       替换表）；去除 HTML 标签与邮件头（From、Subject 中的 MIME 编码串先解码）。
   1.3 中文与英文混合处理：中文用 jieba 分词，英文与数字按词切分并统一小写，二者分别
       统计后拼接为词元序列；对中文额外生成字级 n-gram；对英文使用字符 n-gram 以捕捉
       被拆分的规避形态。
   1.4 特征工程：
       词元级 TF-IDF（ngram_range=(1,2)，sublinear_tf=True，min_df=2，max_features 可配）；
       字符级 TF-IDF（analyzer="char_wb"，ngram_range=(2,4)）；
       结构特征（稠密向量，8 维）——文本长度、大写字母比例、数字个数、感叹号个数、
       是否存在 URL、是否存在电话号码样式串、特殊字符比例、是否包含“免费/中奖/退订/
       验证码”等敏感词命中数；
       两类特征用 FeatureUnion 与稀疏拼接组合，并在验证集上比较“仅词元”“仅字符”
       “词元加字符加结构”三种方案的效果差异。
   1.5 类别不平衡处理：统计 spam 与 ham 比例；训练时统一使用 class_weight="balanced"
       或不平衡专用模型 ComplementNB，并在报告中对比启用前后的 spam 类召回率变化。
   1.6 多模型对比：至少训练并对比六类模型——MultinomialNB、ComplementNB、
       LogisticRegression、LinearSVC（配合概率校准）、RandomForest、GradientBoosting
       （样本量大时可换用 HistGradientBoostingClassifier 以提速）。对每个模型输出
       准确率、spam 类的精确率/召回率/F1、macro F1、ROC-AUC 与 PR-AUC、训练与推理耗时。
   1.7 超参数搜索：对验证集表现最好的两类模型做 GridSearchCV（5 折分层交叉验证，评分用
       f1 且限定 pos_label 为 spam 类），搜索空间包括 TF-IDF 的 min_df 与 max_features、
       线性模型的 C、朴素贝叶斯的 alpha。
   1.8 阈值选择：输出验证集上的阈值扫描结果，给出“误报率（ham 被判为 spam 的比例）分别
       不超过 0.1%、0.5%、1% 时能达到的最大召回率”，让使用者按业务容忍度选择阈值；
       默认阈值 0.5，并在模型卡中记录推荐阈值与选择理由。
   1.9 在线预测接口（FastAPI）：
       POST /predict 接收 {"text": "..."}，返回 {"label": "spam"|"ham", "score": 0.97,
       "threshold": 0.6, "top_tokens": ["免费", "中奖", "点击"]}；
       POST /predict/batch 接收 {"texts": [...]}，单次最多 100 条，返回逐条结果与汇总计数；
       GET /health 返回 {"status":"ok","model_version":"..."};
       GET /model/info 返回模型卡摘要（数据来源、划分、指标、推荐阈值）；
       POST /feedback 接收人工纠正 {"text_hash": "...", "true_label": "spam"}，
       只记录文本哈希与标签用于后续再训练，不保存原文。
   1.10 服务约束：单条文本长度上限 2000 字符（超出返回 413）；简单令牌桶限流（默认
       每 IP 每分钟 60 次，超出返回 429）；请求日志只记录时间、字符数、判定结果与耗时，
       不记录原文；模型在启动时一次性加载到内存（joblib.load），支持通过
       POST /admin/reload 热加载新模型（需携带环境变量中配置的管理令牌）。

2. 输入与交互
   2.1 命令：init、prepare、train、tune、evaluate、predict（离线批量）、serve（启动
       HTTP 服务）、explain、thresholds、stats、export-model-card。
   2.2 典型调用：
       python -m spamfilter prepare --input data\sms_spam.csv --text-col text --label-col label
       python -m spamfilter train --features all --models nb,cnb,lr,svc,rf,hgb --cv 5
       python -m spamfilter thresholds --model models\best.joblib --max-fpr 0.005
       python -m spamfilter predict --model models\best.joblib --input data\holdout.csv --out out\pred.csv
       python -m spamfilter serve --host 127.0.0.1 --port 8100 --workers 2
   2.3 serve 的管理令牌从环境变量 SPAM_ADMIN_TOKEN 读取，配置文件中只写变量名；若环境
       变量未设置则 /admin/reload 直接返回 503 并提示配置方法，不允许匿名热加载。
   2.4 全部随机过程固定种子（默认 42），报告中记录依赖版本与训练时间，保证可复现。

3. 输出与展示
   3.1 train 输出模型对比表：模型、准确率、spam 精确率、spam 召回率、spam F1、macro F1、
       ROC-AUC、PR-AUC、训练秒数、单条推理毫秒。
   3.2 evaluate 输出测试集完整指标、混淆矩阵四个计数、以及被误判的 20 条样例（原文只显示
       前 80 字符并做敏感信息掩码）、误判类型分类统计（把 ham 判 spam 记为误报、把 spam
       判 ham 记为漏报）。
   3.3 thresholds 输出阈值扫描表：阈值、spam 召回率、spam 精确率、ham 误报率、F1，
       并按给定的 max-fpr 给出推荐阈值。
   3.4 接口响应示例（HTTP）：
       请求：POST /predict {"text": "恭喜您中奖！点击 http://a.b-c.cn 领取 免费大礼"}
       响应：{"label":"spam","score":0.984,"threshold":0.6,
             "top_tokens":["中奖","免费","点击","领取"],"model_version":"spam-v1"}

4. 异常与边界处理
   4.1 空文本、纯空白、纯表情分别处理：返回 label 为 ham 且 score 为 0.5，
       note 字段标注 undecidable，不计入评估统计。
   4.2 超长文本按 2000 字符截断并返回 truncated 标记；批量接口超过 100 条返回 400 并提示
       分批调用。
   4.3 模型文件缺失或版本与特征不匹配时，服务启动失败并打印明确日志，不以默认模型兜底。
   4.4 输入包含大量非 UTF-8 字符或二进制内容时，先按 UTF-8 解码并按 errors=replace 处理，
       解码替换比例超过 20% 时返回 422 并说明原因。
   4.5 训练语料中出现的语料占位符（如 “XXXX”“您的验证码是 123456” 之类模板句）必须
       在训练前统一替换，否则模型会学到占位符而不是真实特征；该步骤写入 prepare 输出统计。
   4.6 评估时必须报告 spam 类指标而不能只报准确率：文档、CLI 输出与模型卡中都要明确提示
       “在 86.6% 正类占比的数据上，全判 ham 的准确率为 0.866，因此准确率不足以说明性能”。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；文本处理使用标准库 re、unicodedata、html、email
   （解码 MIME 邮件头）、hashlib（生成文本哈希），数值计算使用 numpy，表格使用 pandas。
2. 允许使用的库：scikit-learn（TF-IDF、FeatureUnion、六类分类器、GridSearchCV、
   CalibratedClassifierCV、StratifiedKFold、全部指标）、pandas（语料与结果）、numpy
   （结构特征）、jieba（中文分词）、joblib（模型持久化）、FastAPI + uvicorn（在线预测
   服务）、pydantic（请求响应模型校验，随 FastAPI 安装）、pytest 与 httpx（接口测试）。
   若允许使用深度学习方案需在扩展章节说明，核心实现不得依赖它。
3. 禁止事项：禁止把用户提交的短信或邮件原文写入日志、数据库或磁盘；禁止在代码中硬编码
   管理令牌（必须从环境变量读取）；禁止把语料与训练模型提交到公开仓库；禁止用测试集参与
   阈值选择或模型选择；禁止只报告准确率而不报告 spam 类精确率与召回率；禁止对同一个样本
   同时出现在训练集与测试集的情况视而不见（必须去重并校验）。
4. 代码组织：模块划分为 preprocess（归一化、URL 还原、占位符替换、去重）、features
   （词元特征、字符特征、结构特征与联合构造）、models（分类器工厂、训练、搜索、校准）、
   metrics_ext（指标计算、阈值扫描、误判分析）、service（FastAPI 应用、限流中间件、
   模型加载与热加载）、cli。
5. 编码规范：全部函数带类型注解与 docstring；pydantic 模型为每个请求响应字段写清类型、
   长度限制与示例；FastAPI 路由函数必须显式声明 response_model；日志使用 logging 且
   严禁在日志中拼接原文；异常处理区分请求错误（4xx）与服务错误（5xx）。

【四、设计要点】

1. 数据结构
   - RawSample：raw_id、text、label（spam/ham）、source。
   - CleanSample：text_clean、tokens（list[str]）、char_len、label、source、text_hash
     （sha256 前 16 位，用于去重与反馈关联）。
   - StructFeatures：length、upper_ratio、digit_count、exclam_count、has_url、has_phone、
     special_ratio、sensitive_hits（共 8 维）。
   - FeatureConfig：use_word、use_char、use_struct、ngram_word、ngram_char、min_df、
     max_features、sublinear_tf。
   - ModelResult：name、params、val_metrics、cv_scores、train_seconds、infer_ms、
     model_path、calibrated（bool）。
   - MetricBundle：accuracy、spam_precision、spam_recall、spam_f1、macro_f1、roc_auc、
     pr_auc、confusion（tp/fp/fn/tn）、support（spam/ham）。
   - ThresholdRow：threshold、spam_recall、spam_precision、ham_fpr、spam_f1。
   - PredictRequest/PredictResponse：pydantic 模型，text 限制 1 至 2000 字符，
     响应含 label、score、threshold、top_tokens、model_version、note（可选）。
2. 关键算法或流程
   - 归一化流程：MIME 头解码（若为邮件）→ 去 HTML → 全角转半角（NFKC）→ 去零宽与控制符
     → URL 重组（正则匹配疑似协议头，再把后续由字母数字点连字符组成、允许中间存在空格的
     片段拼接，直到遇到中文或标点）→ 敏感数字串处理（手机号、验证码样式替换为 <PHONE>
     <CODE> 占位符）→ 空白压缩 → 转小写。
   - 特征构造：中文 jieba.lcut 后与英文按正则 \w+ 切分的结果合并 → TfidfVectorizer(tokenizer
     恒等) 得到词元矩阵；char_wb 2 至 4 gram 得到字符矩阵；结构特征用自实现 Transformer
     计算 8 维并做 MinMax 归一化；三者用 FeatureUnion 或 scipy.sparse.hstack 拼接。
   - 训练与选择：对六个模型在训练集上拟合，在验证集计算 spam F1 与 PR-AUC；取前两名做
     GridSearchCV(scoring="f1", cv=StratifiedKFold(5))；用训练加验证重新拟合最优参数模型，
     在测试集上评估一次。
   - 指标计算：以 spam 为正类，TP 为正确判定的垃圾，FP 为正常被判垃圾（误报），
     FN 为垃圾被判正常（漏报），TN 为正确判定的正常。准确率 = (TP+TN)/总数；
     精确率 = TP/(TP+FP)；召回率 = TP/(TP+FN)；F1 = 2PR/(P+R)；ROC-AUC 用
     roc_auc_score，PR-AUC 用 average_precision_score；ham 误报率 = FP/(FP+TN)。
   - 阈值扫描：对验证集概率输出按 0.05 至 0.95 步长 0.01 遍历，计算每档的召回率与误报率，
     按 max_fpr 约束取召回率最高的阈值作为推荐值。
   - 限流：进程内维护 dict[ip] = (tokens, last_refill_ts)，采用令牌桶，每次请求补充
     elapsed * rate 个令牌并扣减 1，桶空则返回 429 与 Retry-After 头。
   - 热加载：/admin/reload 校验请求头 X-Admin-Token 与环境变量一致后，重新 joblib.load
     模型文件并原子替换内存中的全局模型引用（用 threading.Lock 保护），返回新版本号。
3. 接口或命令设计
   - 核心签名：normalize_text(raw: str) -> str；restore_urls(text: str) -> str；
     build_features(cfg: FeatureConfig) -> Pipeline；
     train_and_select(samples, cfg, seed) -> list[ModelResult]；
     evaluate(model, test_df, threshold: float) -> MetricBundle；
     scan_thresholds(model, val_df, max_fpr: float) -> tuple[list[ThresholdRow], float]；
     explain(model, text: str, k: int = 4) -> list[tuple[str, float]]。
   - HTTP 路由：POST /predict、POST /predict/batch、GET /health、GET /model/info、
     POST /feedback、POST /admin/reload（需 X-Admin-Token）。
   - CLI：python -m spamfilter serve --port 8100；python -m spamfilter evaluate --model
     models\best.joblib --test work\splits\test.csv --threshold 0.6

【五、运行方式与示例】

安装与运行：
    pip install scikit-learn pandas numpy jieba joblib fastapi uvicorn pytest httpx
    python -m spamfilter init --workspace .\work
    python -m spamfilter prepare --input data\sms_spam.csv --text-col text --label-col label
    python -m spamfilter train --features all --models nb,cnb,lr,svc,rf,hgb --cv 5
    python -m spamfilter thresholds --model models\best.joblib --max-fpr 0.005
    python -m spamfilter serve --host 127.0.0.1 --port 8100
    浏览器或 curl 访问 http://127.0.0.1:8100/docs 查看接口文档

示例一（语料准备）：
    输入：python -m spamfilter prepare --input data\sms_spam.csv --seed 42
    输出：读取 5574 条，清洗后 5549 条（去重 25 条）
          spam 747（13.5%），ham 4802（86.5%），已启用 class_weight=balanced
          模板句替换 118 条（如 “您的验证码是 <CODE>”），分层划分 train=3884 val=832 test=833

示例二（模型对比）：
    输入：python -m spamfilter train --features all --models nb,cnb,lr,svc,rf,hgb --cv 5
    输出：
      MODEL        ACC    SPAM_P  SPAM_R  SPAM_F1  MACRO_F1  ROC_AUC  PR_AUC  SEC   MS
      cnb          0.981  0.942   0.927   0.934    0.958     0.991    0.957   0.9   0.4
      lr (C=8)     0.988  0.968   0.955   0.961    0.975     0.995    0.978   6.2   0.5
      svc (C=2)    0.987  0.964   0.951   0.957    0.972     0.994    0.974   8.4   0.5
      nb           0.976  0.918   0.936   0.927    0.951     0.988    0.944   0.6   0.4
      rf (n=500)   0.982  0.951   0.918   0.934    0.960     0.992    0.961   64.1  3.8
      hgb          0.985  0.958   0.936   0.947    0.967     0.993    0.968   22.7  1.2
      最优模型：lr(C=8, l2, class_weight=balanced)，已保存 models/spam-v1-20250316T1110.joblib

示例三（阈值选择）：
    输入：python -m spamfilter thresholds --model models\best.joblib --max-fpr 0.005
    输出：
      THRESHOLD  SPAM_RECALL  SPAM_PRECISION  HAM_FPR  SPAM_F1
      0.30       0.991        0.812          0.0312   0.893
      0.50       0.955        0.968          0.0041   0.961
      0.60       0.929        0.984          0.0018   0.956
      0.70       0.884        0.993          0.0008   0.935
      在 ham 误报率不超过 0.5% 的约束下，推荐阈值 0.60（spam 召回 0.929，精确率 0.984）

示例四（测试集评估，强调指标口径）：
    输入：python -m spamfilter evaluate --model models\best.joblib --test work\splits\test.csv --threshold 0.6
    输出：
      测试集 833 条（spam 112，ham 721）
      准确率 0.988，macro F1 0.966
      spam：精确率 0.981 召回率 0.929 F1 0.954（TP=104 FP=2 FN=8 TN=719）
      ham 误报率 0.28%
      提示：全判为 ham 的基线准确率为 0.865，因此必须结合 spam 类召回率判断模型价值
      漏报样例（前 3 条，已掩码）："Urgent! Your account will be closed, call <PHONE> now"

示例五（在线预测与异常输入）：
    输入：curl -X POST http://127.0.0.1:8100/predict ^
          -H "Content-Type: application/json" ^
          -d "{\"text\":\"恭喜您中奖！点击 http://a.b-c.cn 领取 免费大礼\"}"
    输出：{"label":"spam","score":0.984,"threshold":0.6,
          "top_tokens":["中奖","免费","点击","领取"],"model_version":"spam-v1"}

    输入：curl -X POST http://127.0.0.1:8100/predict -d "{\"text\":\"\"}"
    输出：{"label":"ham","score":0.5,"note":"undecidable","model_version":"spam-v1"}

    输入：连续第 61 次请求（限流 60 次/分钟）
    输出：HTTP 429 {"detail":"rate limit exceeded"}，响应头 Retry-After: 12

    输入：POST /admin/reload 未携带 X-Admin-Token
    输出：HTTP 503 {"detail":"SPAM_ADMIN_TOKEN 未配置，热加载已禁用"}

【六、验收标准】

[ ] prepare 完成归一化、URL 重组、占位符替换与去重，并输出各步骤的条数统计
[ ] 被空格拆分的 URL 能重组为完整域名（用 10 条构造样例验证）
[ ] 全角字符、零宽字符、HTML 标签、MIME 编码头均被正确清洗
[ ] 中文与英文混合文本能被正确分词并生成词元序列
[ ] 三种特征方案（仅词元、仅字符、词元加字符加结构）均有对比结果且差异被记录
[ ] 六个模型全部训练完成并输出准确率、spam 精确率/召回率/F1、macro F1、ROC-AUC、PR-AUC
[ ] 报告明确写出“全判 ham 的基线准确率”，不以准确率单独宣称性能
[ ] 混淆矩阵四个计数之和等于测试集样本数，spam 类 F1 与手算一致
[ ] 网格搜索使用 5 折分层交叉验证且评分针对 spam 类
[ ] 阈值扫描输出召回率、精确率与误报率三者曲线，并按 max-fpr 给出推荐阈值
[ ] class_weight 启用前后的 spam 召回率对比被记录在报告中
[ ] 测试集未被用于模型选择或阈值选择（可用代码检查与模型卡记录验证）
[ ] /predict 单条预测返回 label、score、threshold 与贡献词元，响应结构符合 pydantic 模型
[ ] /predict/batch 单次超过 100 条返回 400；单条超过 2000 字符返回 413
[ ] 限流生效：超过每分钟 60 次返回 429 且带 Retry-After 头
[ ] /admin/reload 在未配置或令牌错误时拒绝，配置正确时能热加载新模型
[ ] 服务日志中不含任何提交文本的原文（可用关键字检索验证）
[ ] 空文本输入返回 ham 且带 undecidable 标记，不抛异常
[ ] 模型卡记录数据来源、划分方式、指标、推荐阈值与依赖版本，可用于复现
[ ] httpx 编写的接口测试全部通过，语料与模型文件未提交到仓库

【七、可选扩展】

1. 增加字符级规避鲁棒性实验：构造插入空格、同音字替换、Unicode 混淆字符三类对抗样本，
   对比归一化前后的召回率下降幅度，输出鲁棒性报告。
2. 增加在线学习闭环：把 /feedback 收集的纠正样本按周汇入再训练集，用时间切分验证模型
   是否随时间衰减，并记录每轮再训练后的指标变化。
3. 增加多语言与跨域泛化评估：在英文短信上训练、中文短信上测试，或短信训练邮件测试，
   量化跨域性能下降并尝试用少量目标域样本做微调。
4. 增加解释与误报自助工具：把高置信度误报样本自动聚类成若干“误报模式”，帮助使用者快速
   发现特征设计缺陷（如把某个正常词学成垃圾信号）。
5. 增加部署实践：提供 Dockerfile、多进程 uvicorn 启动脚本与模型版本目录规范，说明灰度
   切换与回滚流程。

【八、涉及知识点】

- 垃圾文本的常见规避手法与文本归一化、URL 重组、混淆字符还原
- 中文分词与英文词切分的混合处理，字级 n-gram 对短文本的作用
- TF-IDF、结构特征工程、FeatureUnion 与稀疏矩阵拼接
- 朴素贝叶斯族、逻辑回归、线性 SVM、随机森林、梯度提升的原理与适用场景
- 类别不平衡处理（class_weight、ComplementNB）与评估陷阱（准确率悖论）
- 评估指标：精确率、召回率、F1、macro 平均、ROC-AUC、PR-AUC、ham 误报率
- 分层交叉验证、分层数据划分与测试集隔离、可复现实验
- 概率校准、阈值选择与业务代价权衡（漏报与误报的不同损失）
- FastAPI 请求响应模型、路由设计、限流中间件、异常与状态码语义
- 模型持久化与热加载、线程安全、服务启动与健康检查
- 隐私工程：不落库原文、日志脱敏、文本哈希反馈与最小化收集
- 语料版权与许可遵守、数据匿名化与合法使用边界
================================================================================
