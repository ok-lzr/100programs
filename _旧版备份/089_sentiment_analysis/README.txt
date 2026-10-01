================================================================================
项目编号：089                    难度等级：★★★★☆（中型项目收尾，偏难）
项目名称：中文情感分析器
所属分类：人工智能入门 / 自然语言处理
建议工时：4 ~ 6 天
运行环境：Python 3.10+    第三方依赖：jieba、scikit-learn、pandas、numpy、joblib、matplotlib、pytest
================================================================================

【一、项目背景与目标】

电商运营想知道新品评论里“差评集中在哪个点”，产品经理想在一天之内看完一千条用户反馈的
情绪倾向，个人开发者想给自己做的小工具加一个“自动判断这条反馈是不是在骂人”的能力。人工
读一千条评论至少两小时，而训练一个可复用的中文情感分类器，一次投入可以长期使用。

本项目实现一个完整的中文情感分析器：从公开语料出发，完成文本清洗、中文分词、停用词过滤、
否定词与程度副词处理、特征工程（词级与字级 TF-IDF、n-gram）、多模型训练与对比、超参数
搜索、模型持久化，以及面向实际使用的批量预测命令与预测结果导出。项目还包含一套可复现的
评估流程，输出准确率、精确率、召回率、F1 与混淆矩阵，便于判断模型是否真的可用。

目标用户是学习自然语言处理入门流程的学生、需要快速给评论打标签的运营与产品人员。项目完成
后，把一份 CSV 丢进去，就能得到每条文本的情感标签、置信度与关键贡献词（用的哪个模型取哪个
解释方式需在文档中说明），并能看到模型在测试集上的真实表现。

数据来源与规模：使用公开的中文情感语料，主要包括——ChnSentiCorp 中文情感分析语料
（酒店与商品评论，约 7000 至 10000 条，正负两类）、谭松波中文酒店评论语料（约 10000 条，
正负各半）、以及公开的微博情感标注语料（约 10 万条，含正负两类）。实践中任选一到两份，
合并去重后总规模控制在 2 万至 12 万条，并在 README 引用处记录数据来源与许可。若使用自有
数据，须为已获得授权的公开评论，且必须先做匿名化处理。

数据划分：采用分层抽样按 8:1:1 划分训练集、验证集、测试集（保证正负比例一致），
同时在训练集内部做 5 折交叉验证用于选择超参数；测试集只在最终评估时使用一次，调参期间
严禁读取（代码层面把测试集读取封装在 evaluate 子命令中）。若使用多份语料，必须按来源
划分或做去重并检查跨语料重复，避免同一句同时出现在训练集与测试集造成指标虚高。

隐私与版权声明：所有语料仅用于学习与研究，不得用于商业发布或对外服务；使用公开语料必须
遵守其原始许可协议与引用要求，不得再分发原始数据文件；自有文本数据在入库前必须去除用户名、
手机号、邮箱、身份证号与地址等个人信息；模型文件与预测结果不得包含可回溯到具体个人的原文；
严禁使用本工具进行舆情操纵、批量刷评或对特定个人进行攻击。

【二、功能需求清单】

1. 核心功能
   1.1 数据加载与清洗：支持从 CSV（列名可配置：text、label）或纯文本目录（pos/ 与 neg/
       两个子目录）读取语料。清洗步骤包括：去除 HTML 标签与转义实体、去除 URL 与 @用户
       名、统一全角半角、去除表情符号（可选保留并映射为情感标记）、去除多余空白与重复
       标点（如“！！！”压缩为“！”）、繁简统一（可用 opencc 可选，未安装时跳过并提示）。
   1.2 标签规范化与去重：标签统一为 0（负向）与 1（正向），其他取值按配置映射或丢弃并
       计数；对清洗后完全相同的文本做去重（保留首次出现），并统计去重前后数量。
   1.3 中文分词与过滤：使用 jieba 精确模式分词，加载自定义词典（含领域词与网络新词）；
       过滤停用词表（内置常用中文停用词表，可外部替换）；过滤单字（可配置）与纯数字；
       记录分词后平均词数与词表大小。
   1.4 否定与程度处理：识别否定词表（不、没、无、非、别、未、毫无等）与程度副词表
       （很、非常、极其、稍微、有点等），把“不好”处理为“好”加否定前缀标记
       （生成 not_好 词元）或按规则做情感翻转标记，避免“好”与“不好”被当作同一特征。
   1.5 特征工程：
       词级特征——TF-IDF（TfidfVectorizer，tokenizer 用 jieba，ngram_range=(1,2)，
       sublinear_tf=True，min_df=2，max_features 可配）；
       字级特征——字符 n-gram（analyzer="char_wb"，ngram_range=(1,3)）作为对比方案；
       联合特征——用 FeatureUnion 拼接词级与字级特征并在验证集上比较效果；
       情感词典特征——统计情感词典命中次数、否定词数量、程度副词数量、感叹号与问号数量，
       作为额外数值特征与 TF-IDF 稀疏矩阵拼接。
   1.6 模型训练与对比：至少训练并对比五类模型——MultinomialNB、ComplementNB、
       LogisticRegression、LinearSVC、RandomForest，统一在验证集上评估；用
       GridSearchCV 对最优候选做超参数搜索（如 LogisticRegression 的 C 与 penalty、
       LinearSVC 的 C、TF-IDF 的 min_df 与 max_features），搜索使用 5 折交叉验证并以
       F1（macro）为评分。
   1.7 概率输出：LinearSVC 没有 predict_proba，需要说明处理方式——要么改用
       CalibratedClassifierCV 做概率校准（推荐），要么用 decision_function 的归一化分数
       作为“置信度”并在文档中明确其不是概率。
   1.8 模型持久化：用 joblib 保存最优 pipeline（含向量化器与分类器）到 models/
       sentiment-<版本>-<时间戳>.joblib，同时写出 model_card.json 记录训练数据来源、
       样本数、划分方式、特征配置、超参数、验证集与测试集全部指标、训练耗时与环境版本。
   1.9 批量预测：predict 命令读取 CSV 或文本文件，输出原始文本、预测标签、置信度、
       正向概率与负向概率；支持 --threshold 调整判定阈值（默认 0.5），并给出在该阈值下
       验证集上的精确率与召回率，便于按业务诉求选择（如宁可漏判不可误判时提高阈值）。
   1.10 可解释性：对预测结果输出对判定贡献最大的前 5 个词元（LogisticRegression 使用
       系数乘以特征值；朴素贝叶斯使用对数概率差），写入 CSV 的 top_tokens 列，便于人工
       抽查模型是否学偏（如把“快递”学成情感词）。

2. 输入与交互
   2.1 命令：init、prepare（清洗与划分）、train（训练与对比）、tune（网格搜索）、
       evaluate（在测试集上出报告）、predict（批量预测）、serve（可选，提供简单预测接口）、
       explain（单条文本的贡献词分析）、stats（语料统计）。
   2.2 典型调用：
       python -m sentiment prepare --input data\reviews.csv --text-col text --label-col label ^
         --out data\prepared --seed 42
       python -m sentiment train --features word+char --models nb,cnb,lr,svc,rf --cv 5
       python -m sentiment evaluate --model models\best.joblib --test data\prepared\test.csv
       python -m sentiment predict --model models\best.joblib --input data\new_reviews.csv ^
         --out out\pred.csv --threshold 0.6
   2.3 固定随机种子（默认 42），所有随机过程（划分、交叉验证、RandomForest）均使用同一
       种子，保证结果可复现；报告中记录 Python 与依赖库版本。
   2.4 prepare 命令输出 splits 目录：train.csv、val.csv、test.csv 与 split_meta.json
       （记录各集合条数、正负比例、去重数量、随机种子）。

3. 输出与展示
   3.1 train 输出模型对比表（纯文本对齐表格）：模型名、验证集准确率、精确率、召回率、
       F1（macro）、训练耗时秒数，按 F1 降序排列。
   3.2 evaluate 输出：测试集准确率、正类与负类各自的精确率/召回率/F1、macro 与 weighted
       平均、混淆矩阵（2x2 文本形式）、以及最常见的 20 个误判样例（附贡献词）。
   3.3 可选图表：用 matplotlib 输出混淆矩阵热力图、五模型 F1 对比柱状图与特征重要度前
       30 词条形图，保存到 reports/ 目录（中文字体需显式设置，否则乱码需给出提示）。
   3.4 predict 输出 CSV 列：text、pred_label、pred_name（正向/负向）、confidence、
       prob_positive、prob_negative、top_tokens、model_version。

4. 异常与边界处理
   4.1 空文本、仅标点、仅表情、超长文本（超过 5000 字）分别处理：前两类标记为
       undecidable 并输出 neutral/unknown，超长文本截断到前 2000 字并提示。
   4.2 反讽与混合情感（如“质量很好，就是太贵了”）不做专门建模，但在文档中明确说明模型
       局限，并在测试集报告里给出这类样例的实际表现。
   4.3 类别不平衡：若正负比例超出 6:4，训练时启用 class_weight="balanced"，并在报告中
       记录启用情况与对 F1 的影响。
   4.4 分词把关键情感词切碎（如“不开心”被切成“不/开心”）时，用自定义词典纠正，并把
       纠正前后的验证集 F1 对比写入报告。
   4.5 模型文件与数据版本不匹配（特征维度不同）时报错并提示需重新训练，不静默给出错误
       结果。
   4.6 测试集被意外用于调参：在 split_meta.json 中记录测试集的哈希，evaluate 时校验哈希
       未变，并在报告中标注测试集访问次数。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；数值与矩阵运算使用 numpy，表格处理使用 pandas，
   文本处理使用 jieba 与标准库 re、unicodedata、collections。
2. 允许使用的库：jieba（中文分词与自定义词典）、scikit-learn（TF-IDF、特征联合、五类
   分类器、GridSearchCV、CalibratedClassifierCV、指标计算）、pandas（语料与结果表格）、
   numpy（数组与词典特征）、joblib（模型持久化）、matplotlib（图表，可选）、pytest
   （测试）。数据划分与统计可用 sklearn.model_selection.train_test_split 并指定
   stratify 与 random_state。
3. 禁止事项：禁止把测试集用于任何超参数选择；禁止在代码或报告中输出语料原文中的个人
   信息；禁止把下载的语料文件与训练好的模型提交到公开仓库；禁止把人工构造的“完美样例”
   计入测试指标；禁止在预测阶段重新拟合向量化器（必须复用训练时的 pipeline）。
4. 代码组织：模块划分为 preprocess（清洗、全半角、去噪）、segment（jieba 封装、词典与
   停用词、否定词与程度副词处理）、features（词级/字级/联合特征与词典特征构造）、
   models（模型工厂、训练、搜索、校准）、evaluate（指标、混淆矩阵、误判分析）、
   predict（批量预测与解释）、report（模型卡与图表）、cli。
5. 编码规范：全部函数带类型注解与 docstring；对语料字段与标签的取值假设写清；所有随机
   过程必须显式传 random_state；日志使用 logging 记录各阶段耗时与样本数；禁止在训练脚本
   中写 print 调试代码。

【四、设计要点】

1. 数据结构
   - RawSample：text、label、source（语料来源标识）、raw_id。
   - CleanSample：text_clean、tokens（list[str]）、label、length、has_negation、degree_count、
     punct_count。
   - FeatureConfig：mode（word/char/word+char）、ngram_range、min_df、max_features、
     sublinear_tf、use_lexicon_features、stopwords_path、userdict_path。
   - TrainResult：model_name、params、cv_scores（list[float]）、val_metrics（dict）、
     train_seconds、model_path、feature_count。
   - MetricBundle：accuracy、precision_pos、recall_pos、f1_pos、precision_neg、recall_neg、
     f1_neg、macro_f1、weighted_f1、confusion（2x2）、support（dict）。
   - ModelCard：version、trained_at、data_sources（list）、sample_counts（dict）、
     feature_config（dict）、best_params（dict）、metrics（dict）、env（python 与库版本）、
     test_set_hash。
2. 关键算法或流程
   - 清洗流程：去 HTML → 去 URL 与 @名 → 全角转半角（用 unicodedata.normalize("NFKC")
     再处理中文标点）→ 表情处理 → 重复标点压缩 → 空白规整 → 长度过滤（默认保留 4 至
     2000 字，超出范围记入统计并丢弃）。
   - 分词与词元增强：jieba.lcut(text, cut_all=False) → 去停用词与单字 → 否定词处理：
     若词元前一个词是否定词，则输出 not_<词元> 并把否定词本身也保留为特征；程度副词
     处理：若前一个词是程度副词，输出 <程度词>_<词元> 组合特征（如 非常_好）。
   - 特征构造：word 模式用 TfidfVectorizer(tokenizer=lambda x: x, preprocessor=None)
     接收已分好词的列表；char 模式用 analyzer="char_wb"；联合模式用
     FeatureUnion([("word", ...), ("char", ...)])；词典特征用自实现 Transformer
     （继承 BaseEstimator 与 TransformerMixin，实现 fit/transform）输出 6 维稠密特征，
     再用 scipy.sparse.hstack 与稀疏矩阵拼接（注意先做 MinMax 归一化）。
   - 训练与选择：对每个候选模型在训练集上 fit，在验证集上计算 macro F1；取验证集 F1
     最高的模型作为候选，再对该模型做 GridSearchCV（scoring="f1_macro"，cv=5）得到最优
     超参数；用训练集加验证集重新拟合最优参数模型，最后在测试集上做一次评估。
   - 评估指标定义：准确率 = 预测正确数 / 总数；精确率（正类）= 预测为正且正确数 /
     预测为正总数；召回率（正类）= 预测为正且正确数 / 实际为正总数；F1 = 2PR/(P+R)；
     macro F1 为两类 F1 的算术平均；同时给出混淆矩阵 TP、FP、FN、TN 四个计数以便核对。
   - 阈值调优：在验证集上遍历 0.30 至 0.70 的阈值步长 0.02，输出精确率与召回率曲线数据，
     供 predict 的 --threshold 选择依据；报告中同时给出默认 0.5 阈值下的完整指标。
3. 接口或命令设计
   - 核心签名：clean_text(text: str) -> str；tokenize(text: str) -> list[str]；
     build_features(config: FeatureConfig) -> Pipeline；
     train_and_select(samples, config, seed) -> TrainResult；
     evaluate_model(model, test_csv) -> MetricBundle；
     predict_batch(model, texts: list[str], threshold: float) -> list[PredictionRow]；
     explain_tokens(model, text: str, top_k: int = 5) -> list[tuple[str, float]]。
   - 可选 HTTP 接口（serve 命令）：POST /predict 请求 {"texts": ["这个质量很好"]}，
     响应 {"results": [{"label": 1, "confidence": 0.93, "top_tokens": ["很好", "质量"]}]}；
     GET /model/info 返回模型卡摘要。

【五、运行方式与示例】

安装与运行：
    pip install jieba scikit-learn pandas numpy joblib matplotlib pytest
    python -m sentiment init --workspace .\work
    python -m sentiment prepare --input data\chnsenticorp.csv --text-col text --label-col label
    python -m sentiment train --features word+char --models nb,cnb,lr,svc,rf --cv 5
    python -m sentiment evaluate --model models\best.joblib --test work\splits\test.csv
    python -m sentiment predict --model models\best.joblib --input data\new.csv --out out\pred.csv

示例一（语料准备）：
    输入：python -m sentiment prepare --input data\chnsenticorp.csv --seed 42
    输出：读取 7766 条，清洗后 7702 条（丢弃 64 条空文本，去重 118 条）
          正负比例 1.00:1.00，分层划分 train=6161 val=770 test=771
          平均词数 24.6，词表大小 41233，已写入 work/splits/ 与 split_meta.json

示例二（模型对比）：
    输入：python -m sentiment train --features word+char --models nb,cnb,lr,svc,rf --cv 5
    输出：
      MODEL                 ACC     PREC    REC     F1_MACRO  SECONDS
      lr (C=4, l2)          0.941   0.938   0.944   0.941     18.4
      svc (C=1, calibrated) 0.938   0.936   0.939   0.938     21.7
      cnb                   0.921   0.918   0.925   0.921     2.1
      nb                    0.908   0.905   0.913   0.908     1.6
      rf (n=300)            0.903   0.899   0.907   0.903     142.8
      最优模型已保存 models/sentiment-v1-20250316T1042.joblib（特征维度 186420）

示例三（测试集评估）：
    输入：python -m sentiment evaluate --model models\best.joblib --test work\splits\test.csv
    输出：
      测试集 771 条：准确率 0.936，macro F1 0.935，weighted F1 0.935
      正类：精确率 0.930 召回率 0.944 F1 0.937（TP=364 FP=27 FN=22 TN=358）
      负类：精确率 0.943 召回率 0.928 F1 0.935
      典型误判：「价格便宜但做工很差」预测为正向（贡献词：便宜 +0.82，差 -0.41）
      阈值曲线：threshold=0.6 时精确率 0.951、召回率 0.912（验证集）

示例四（批量预测）：
    输入：python -m sentiment predict --model models\best.joblib --input data\new.csv --threshold 0.6
    输出：已预测 1200 条：正向 742，负向 431，无法判定 27
          结果写入 out/pred.csv（含置信度与贡献词），耗时 3.2 秒

示例五（异常输入）：
    输入：python -m sentiment predict --model models\best.joblib --input data\empty.csv
    输出：错误：data\empty.csv 缺少必需列（需要 text 列，实际列：id,content）。
          请用 --text-col content 指定文本列。未产生任何输出文件，退出码 1

【六、验收标准】

[ ] prepare 完成清洗、去重、标签规范化并输出 train/val/test 三个文件与划分元信息
[ ] 划分采用分层抽样，三集合的正负比例与整体比例偏差不超过 2 个百分点
[ ] 随机种子固定后重复运行两次得到完全相同的划分与指标
[ ] 停用词表与自定义词典可替换并生效（用“不开心”样例验证分词修正）
[ ] 否定词与程度副词处理生效，且处理前后验证集 F1 变化被记录在报告中
[ ] 词级、字级、联合三种特征模式均可训练，且报告中给出三者对比结果
[ ] 至少对比五种模型并在验证集上按 F1 排序输出对比表
[ ] 网格搜索使用 5 折交叉验证且评分口径为 f1_macro
[ ] 概率输出来源明确：SVC 使用概率校准或被标注为“非概率分数”
[ ] evaluate 输出准确率、精确率、召回率、F1（含两类与 macro/weighted）与混淆矩阵四个计数
[ ] 混淆矩阵计数满足 TP+FP+FN+TN 等于测试集样本数
[ ] 测试集只在 evaluate 中读取一次，split_meta.json 的哈希校验通过
[ ] 空文本、仅标点、超长文本被正确标记或截断，不抛异常
[ ] 批量预测复用训练时的 pipeline，不重新拟合向量化器（用固定输出验证）
[ ] 模型卡记录数据来源、划分方式、特征配置、超参数与全部指标，可据此复现
[ ] 代码与输出中未出现可识别个人的原始文本信息，未提交语料与模型到仓库

【七、可选扩展】

1. 增加细粒度情感：把二分类扩展为 5 级评分（1 至 5 星）预测，或增加方面级情感
   （对“物流”“质量”“价格”分别判断倾向）。
2. 对比深度学习方案：用小型预训练模型（如中文 BERT 的轻量版本）微调，与本项目的
   TF-IDF 线性模型在同样划分下对比 F1 与推理耗时，分析收益与成本。
3. 增加主动学习：对置信度接近阈值的样本优先交给人工标注，用最小标注量提升模型。
4. 增加领域自适应实验：在酒店评论上训练、在电子产品评论上测试，评估跨领域性能下降幅度
   并尝试用少量目标领域标注做微调。

【八、涉及知识点】

- 中文文本清洗、全半角与繁简统一、表情与标点处理
- jieba 分词、自定义词典、停用词表与分词粒度对分类的影响
- 否定词与程度副词处理、情感词典特征、领域词表建设
- TF-IDF 与 n-gram 特征、词级与字级特征差异、稀疏矩阵拼接
- 朴素贝叶斯、逻辑回归、线性 SVM、随机森林的原理与适用场景
- 概率校准（CalibratedClassifierCV）与 decision_function 的区别
- 评估指标：准确率、精确率、召回率、F1、macro 与 weighted 平均、混淆矩阵
- 数据划分规范、分层抽样、交叉验证、测试集隔离与可复现实验
- 类别不平衡处理（class_weight）、阈值调优与业务代价权衡
- 模型可解释性（线性模型系数）与模型卡（Model Card）文档实践
- 语料版权与个人信息保护：许可遵守、匿名化与不可再分发
================================================================================
