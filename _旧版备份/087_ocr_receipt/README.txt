================================================================================
项目编号：087                    难度等级：★★★★☆（中型项目，偏难）
项目名称：票据 OCR 识别与结构化
所属分类：人工智能入门 / 图像文字识别
建议工时：4 ~ 5 天
运行环境：Python 3.10+    第三方依赖：opencv-python、pytesseract、Pillow、numpy、pandas、openpyxl
================================================================================

【一、项目背景与目标】

小公司或个人做报销、记账时，手里往往攒着一叠纸质发票与收据：要录入金额、日期、发票号码、
开票方名称，纯手工敲几十张就足以让人放弃记账。现有的手机扫描类应用要么把图片上传到云端，
要么只给一个整段文字让你自己复制，无法直接变成可统计的表格。

本项目实现一个本地运行的票据 OCR 识别与结构化工具：输入一张或多张票据照片（手机拍摄的
JPEG、扫描的 PNG、PDF 单页转出的图片），先做图像预处理提高识别率，再调用 OCR 引擎识别
全页文字，然后用规则与正则从文字中抽取关键字段（票据号码、开票日期、价税合计金额、税额、
销售方名称、购买方名称、发票代码、校验码），最后做字段级校验并导出为 CSV、Excel 与 JSON。

目标用户是需要批量录入发票的个人与小微财务人员、想学习“图像预处理 + OCR + 信息抽取”
完整链路的学生。项目完成后，可以对着手机里几十张发票照片批量生成一张汇总表，金额与日期
自动填好，识别不确定的字段被标记出来供人工复核。

数据来源与规模：训练与测试使用的样本来自两类——一是学习者自行拍摄或扫描的自有票据；
二是公开数据集，如 ICDAR 2019 SROIE（Scanned Receipts OCR and Information Extraction，
约 1000 张英文收据，含 company、date、address、total 四个字段的标注）以及国内公开的票据
识别竞赛数据集。本项目以“规则抽取 + 现成 OCR 引擎”为主，不对 OCR 模型本身做训练，但需要
用不少于 200 张标注票据（其中自有拍摄不少于 100 张，覆盖不同光照、角度与票据类型）构成
评估集，按 6:2:2 划分为开发集 120 张、验证集 40 张、测试集 40 张，测试集在调参完成前
不得使用。

隐私与版权声明：票据包含姓名、税号、银行账号等敏感信息，本项目所有图片与识别结果仅在
本地处理与存储，严禁上传到任何第三方服务；用于演示的样例图片必须使用自制或已获得授权的
材料，不得使用他人票据；公开数据集的使用须遵守其原始许可协议，不得再分发；本项目纯属
学习用途，不得用于伪造、篡改票据或规避税务监管等违法活动。

【二、功能需求清单】

1. 核心功能
   1.1 批量输入：支持 --input 指定目录或文件列表；支持 .jpg/.jpeg/.png/.bmp/.tif 与
       .pdf（PDF 通过 pdf2image 或逐页转图，未安装时给出明确提示并跳过）。
   1.2 图像预处理流水线，按顺序执行且每一步可在配置中开关：
       等比缩放——长边超过 2000 px 时缩小，小于 1000 px 时放大，兼顾速度与精度；
       灰度化——cv2.cvtColor 转 GRAY；
       去噪——中值滤波（核 3）或双边滤波，去除手机拍摄的颗粒噪点；
       光照校正——用大核高斯模糊估计背景，做除法归一化，缓解阴影与不均匀照明；
       倾斜校正——边缘检测或霍夫变换求文本行角度，旋转校正（限幅正负 15 度）；
       二值化——Otsu 全局阈值或自适应阈值（blockSize 31、C 10），按对比度自适应选择；
       边缘处理——裁掉扫描件的黑边与桌面背景（连通域面积过滤 + 最小外接矩形裁剪）。
   1.3 OCR 识别：使用 pytesseract 调用 Tesseract，语言配置为 chi_sim+eng，页面分割模式
       默认 --psm 6（按统一文本块处理），票据版式复杂时允许按 ROI 分区识别（如右上角
       票据号码区域单独用 --psm 7 单行模式）。识别结果同时保留带位置信息的词级结果
       （image_to_data 返回的 left/top/width/height/conf），用于后续按位置约束字段。
   1.4 字段抽取：基于关键字定位加正则的组合规则，抽取字段包括：
       票据代码（10 或 12 位数字）、票据号码（8 位数字，关键字“号码”“No”附近）、
       开票日期（支持 2025年03月16日、2025-03-16、2025/03/16 三种格式，统一归一化为
       ISO 日期）、价税合计（关键字“价税合计”“合计金额”“小写”附近的金额，支持
       ¥、￥、大写金额换算）、税额、税率、销售方名称、购买方名称、校验码（后 6 位或 20 位）。
   1.5 金额中文大写解析：把“壹仟贰佰叁拾肆元伍角陆分”解析为 1234.56，用于与阿拉伯数字
       金额交叉校验；两者不一致时字段标记 confidence 为 low 并在复核清单中列出。
   1.6 字段级校验规则：日期必须落在合理区间（2000-01-01 至今后 1 年）且不晚于今天；
       金额必须大于 0 且不超过 100 万元；票据代码与号码位数必须匹配；税额不大于价税合计；
       税率必须属于 {0, 0.01, 0.03, 0.06, 0.09, 0.13} 集合。违反规则的字段置为 null 并
       记录 fail_reason，绝不输出明显错误的数值。
   1.7 结果导出：CSV（UTF-8 with BOM，便于 Excel 直接打开）、Excel（openpyxl，含“识别
       结果”“复核清单”“统计摘要”三个工作表）、JSON（逐张一张记录，含原始 OCR 文本与
       每字段置信度）。
   1.8 复核与人工修正：生成 review.csv，列出所有 low confidence 或校验失败的字段；
       提供 correct 命令接收人工修正后的值并写回数据库，修正记录用于统计各字段的实际
       准确率。
   1.9 统计摘要：总张数、识别成功张数、各字段抽取成功率、平均单张耗时、金额合计、
       需要人工复核的比例。

2. 输入与交互
   2.1 命令：init、preprocess（只做预处理并把中间图存到 debug/ 便于观察）、recognize
       （单张或批量识别）、extract（从已有 OCR 文本重新抽取字段）、export、review、
       correct、stats、bench（在评估集上跑指标）。
   2.2 命令行示例：
       python -m receipt_ocr recognize --input .\samples --lang chi_sim+eng --psm 6 ^
         --preprocess full --export csv,excel,json --out .\out
   2.3 配置文件 config.yaml 控制预处理开关、二值化方法、语言包、字段关键字表、校验规则
       阈值、并发进程数（默认 2，避免 OCR 线程争抢 CPU）。
   2.4 单张图片处理失败不得中断批次，失败原因写入 failures.csv（路径、异常类型、消息）。

3. 输出与展示
   3.1 控制台每张图打印一行：file=IMG_0231.jpg status=OK fields=6/9 amount=128.00
       date=2025-03-11 conf_avg=0.86 ms=1840。
   3.2 进度使用 rich 进度条显示“已完成/总数/预计剩余时间”。
   3.3 对低置信度字段在终端高亮显示，其中 amount 与 date 属于必检字段。
   3.4 debug 模式下把预处理每一步的中间图以及 OCR 词框叠加图输出到 debug/<文件名>/，
       便于定位是图像问题还是规则问题。

4. 异常与边界处理
   4.1 图片无法解码或通道异常（CMYK、16 位、动图首帧）时，先转换为 RGB 8 位再处理。
   4.2 未安装 Tesseract 可执行文件或缺少 chi_sim 语言包时，启动即给出清晰的中文提示
       （含安装地址与语言包放置路径），而不是在识别时报出难懂的异常。
   4.3 OCR 返回空文本时，按“预处理失败”处理：自动改用不二值化的原图重试一次，仍为空
       则记为 FAILED 并进入复核清单。
   4.4 一张图内含多张票据（拼接照片）时不做拆分，但通过连通域数量与文字块面积占比检测
       并提示 possible_multi_receipt。
   4.5 金额出现多个候选（同时有“合计”“价税合计”“实付”）时，按优先级取“价税合计”，
       并在 JSON 中保留全部候选值供人工判断。
   4.6 文件名重复时输出文件自动加序号后缀，不覆盖已有结果。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；全部代码与注释使用中文说明，标识符用英文。
2. 允许使用的库：opencv-python（图像预处理与几何校正）、pytesseract（OCR 调用，需系统安装
   Tesseract-OCR 及 chi_sim 语言包）、Pillow（图片打开与格式转换）、numpy（数组运算与
   阈值统计）、pandas（结果表格与导出）、openpyxl（Excel 写出）、pdf2image（可选，
   PDF 转图，需 poppler）、rich（进度条）、pydantic（结果模型校验）、pytest（测试），
   可选 chinese-calendar 用于工作日判断。金额大写解析、正则抽取、文件读写使用标准库 re、
   pathlib、json、csv、decimal、dataclasses。
3. 禁止事项：禁止把票据图片或识别文本上传到任何在线 API；禁止在代码或仓库中提交真实票据
   与原图；禁止把 OCR 置信度直接当作字段正确率对外宣称；禁止使用 float 表示金额（必须用
   decimal.Decimal 并统一保留两位小数）；禁止用全局变量传递预处理配置。
4. 代码组织：模块划分为 preprocess（全部图像处理函数，每个函数输入输出都是 ndarray）、
   ocr（Tesseract 封装、词级结果解析）、extract（关键字定位与正则抽取）、validate（字段
   校验规则）、export（CSV/Excel/JSON 写出）、metrics（准确率与字段级指标计算）、cli。
5. 编码规范：全部函数带类型注解与 docstring，docstring 中必须写清输入图像假设（灰度还是
   彩色、取值区间）与返回值含义；图像处理函数必须可单独调用并附单元测试（用 3 张合成
   图片验证二值化与旋转校正）；日志使用 logging，记录每张图的耗时与重试次数。

【四、设计要点】

1. 数据结构
   - OcrWord：text、left、top、width、height、conf、line_num、block_num。
   - OcrResult：image_path、full_text、words（list[OcrWord]）、lang、psm、elapsed_ms、
     preprocess_steps（实际执行的步骤名列表）。
   - ReceiptFields：invoice_code、invoice_number、invoice_date、amount_total、tax_amount、
     tax_rate、seller_name、buyer_name、check_code、amount_in_words、amount_candidates
     （dict）、confidences（dict 字段名到 0~1）、status（OK/NEED_REVIEW/FAILED）、
     fail_reasons（list）。
   - FieldRule：name、keywords（list）、regex、validator（callable）、priority、required。
   - 指标记录 MetricRow：field、total、correct、precision、recall、f1（按字段分别统计）。
2. 关键算法或流程
   - 预处理主流程（顺序固定并逐步留证）：读图 → 转 RGB/BGR → 灰度 → 去噪 → 光照校正
     （background = GaussianBlur(gray, (0,0), sigma=25)；norm = cv2.divide(gray, background,
     scale=255)）→ 倾斜校正（Canny 边缘 + HoughLinesP 求角度中位数，只接受绝对值小于
     15 度的角度，用 warpAffine 旋转）→ 二值化（先算图像对比度指标，即灰度标准差/均值，
     低于阈值走自适应阈值，否则走 Otsu）→ 输出。
   - OCR 调用：pytesseract.image_to_string(img, lang=lang, config=f"--oem 3 --psm {psm}")；
     词级结果用 image_to_data(img, output_type=Output.DICT) 获取并按 (block, par, line)
     重建行文本，用于关键字与坐标联合定位。
   - 字段抽取主流程：对每个 FieldRule，先在词级结果中按 keywords 做模糊定位（关键字可
     允许 1 个字符的编辑距离，解决 OCR 把“价税合计”识别为“价税台计”的问题），取得该
     关键字的坐标；然后在该坐标右侧 800 px、下方 200 px 的区域内搜索匹配 regex 的词；
     区域内多个候选时按距离关键字最近者优先；若关键字定位失败，退化为在全文中用 regex
     全局匹配并按优先级取第一个。
   - 金额抽取：正则 r"(?:¥|￥)?\s*([0-9][0-9,]*\.?[0-9]{0,2})"，先清洗千分位逗号，再用
     Decimal 构造，最后做范围校验；同时用大写金额解析结果做交叉校验。
   - 大写金额解析：按“亿、万、仟、佰、拾、元、角、分”分节解析，逐字符维护当前数字与
     单位权重，处理“零”的跳过规则；解析失败返回 None 而不是抛异常。
   - 评价指标：字符级准确率按 1 - CER 计算，CER = 编辑距离(预测, 标注) / 标注长度；
     字段级准确率 = 完全匹配张数 / 总张数；精确率 = 正确抽取数 / 抽取出的总数；
     召回率 = 正确抽取数 / 应抽取的总数（标注中存在的字段数）；F1 = 2PR/(P+R)。
3. 接口或命令设计
   - 核心签名：preprocess_image(path: Path, cfg: PreprocessConfig) -> np.ndarray；
     run_ocr(img: np.ndarray, lang: str, psm: int) -> OcrResult；
     extract_fields(ocr: OcrResult, rules: list[FieldRule]) -> ReceiptFields；
     validate_fields(f: ReceiptFields) -> ReceiptFields；bench(gt_csv, pred_csv) -> MetricReport。
   - CLI：python -m receipt_ocr bench --gt data/gt_test.csv --pred out/result.csv --report out/bench.json

【五、运行方式与示例】

安装与运行：
    pip install opencv-python pytesseract Pillow numpy pandas openpyxl rich pydantic pytest
    另需安装 Tesseract-OCR（Windows 版安装包地址见官方仓库），并把 chi_sim.traineddata
    放入 Tesseract 的 tessdata 目录，确认 tesseract --list-langs 输出包含 chi_sim。
    python -m receipt_ocr init --db data/receipts.db
    python -m receipt_ocr recognize --input .\samples --export csv,excel,json --out .\out

示例一（单张识别）：
    输入：python -m receipt_ocr recognize --input samples\inv_001.jpg --debug
    输出：
      file=inv_001.jpg status=OK fields=8/9 amount=128.00 date=2025-03-11 conf_avg=0.87 ms=1840
      已导出 out/result.csv、out/result.xlsx、out/result.json
      提示：字段 seller_name 置信度 0.42，已加入复核清单 out/review.csv

示例二（批量与统计）：
    输入：python -m receipt_ocr recognize --input .\samples --workers 2 --export excel
    输出：处理 126 张，成功 118，需复核 21，失败 8（详见 out/failures.csv）
          字段抽取成功率：invoice_date 95.2%，amount_total 92.1%，invoice_number 89.7%
          耗时合计 232 秒，平均 1.84 秒/张

示例三（评估集指标）：
    输入：python -m receipt_ocr bench --gt data\gt_test.csv --pred out\result.csv
    输出：
      field              precision  recall  f1     accuracy
      amount_total       0.941      0.932   0.936  0.930
      invoice_date       0.968      0.961   0.964  0.960
      invoice_number     0.912      0.905   0.908  0.902
      字符级准确率 1-CER = 0.912（测试集 40 张，未参与任何调参）

示例四（异常输入）：
    输入：python -m receipt_ocr recognize --input .\samples\blank.jpg
    输出：警告：blank.jpg OCR 结果为空，已自动用未二值化原图重试一次，仍为空。
          该文件记为 FAILED 并进入复核清单，批次继续执行，退出码 0

示例五（环境缺失）：
    输入：python -m receipt_ocr recognize --input .\samples\inv_001.jpg
    输出：错误：未找到 Tesseract 可执行文件。请安装 Tesseract-OCR 并设置环境变量
          TESSDATA_PREFIX，或使用 --tesseract-cmd 指定完整路径。退出码 2

【六、验收标准】

[ ] 预处理流水线每一步可单独开关，debug 目录中能看到每步的中间图
[ ] 倾斜不超过 15 度的票据被校正到接近水平（用 3 张人为旋转的样例验证）
[ ] 光照不均的样例经光照校正后二值化结果不再出现大面积全黑或全白
[ ] 未安装 Tesseract 或缺少 chi_sim 时给出可操作的中文提示与退出码 2
[ ] 数据类型为 CMYK/16 位/带 alpha 的图片能正常识别，不抛异常
[ ] 三种日期格式均可抽取并统一归一化为 ISO 日期
[ ] 中文大写金额能正确解析并与阿拉伯数字金额交叉校验（构造 20 组样例全部通过）
[ ] 金额使用 Decimal 计算，输出始终保留两位小数，无浮点误差
[ ] 违反校验规则（金额为负、税额大于合计、税率不在集合内）的字段被置空并记录原因
[ ] OCR 空结果会自动不带二值化重试一次，仍失败则记 FAILED 且不影响整批
[ ] 导出 CSV 带 BOM 可被 Excel 正确打开中文，Excel 含三个工作表，JSON 含每字段置信度
[ ] review.csv 列出所有低置信度与校验失败字段，correct 命令能写回修正值
[ ] bench 命令输出的精确率、召回率、F1 与人工按定义手算结果一致
[ ] 测试集 40 张在调参阶段从未被读取（有代码层面隔离或记录可查）
[ ] 代码中不存在任何把图片或识别文本上传网络的调用

【七、可选扩展】

1. 接入 PaddleOCR 或 EasyOCR 作为第二识别引擎，对低置信度字段做双引擎投票，提升金额与
   号码字段准确率。
2. 版式模板库：为几种常见票据（增值税电子普通发票、出租车票、定额发票）分别配置 ROI 区域
   模板，识别时先分类版式再按区域识别，显著降低串行错位。
3. 增加字段抽取的序列标注模型（如基于字符级 BiLSTM-CRF 或微调小型预训练模型），与规则
   抽取做对比实验，评估在未见版式上的泛化能力。
4. 与记账本联动：识别结果直接写入 051 项目的 SQLite 数据库，形成“拍照即记账”的闭环。

【八、涉及知识点】

- OpenCV 图像预处理：灰度、滤波去噪、光照校正、形态学、几何变换与倾斜校正
- 阈值分割（Otsu 与自适应阈值）的适用场景与参数含义
- pytesseract 的 psm/oem 参数、词级输出结构与置信度语义
- 正则抽取与关键字邻近区域约束的信息抽取思路
- 中文大写金额解析与 Decimal 精确金额计算
- 数据校验规则设计、字段级置信度与人工复核流程
- OCR 与信息抽取的评价指标：CER、字段级精确率/召回率/F1
- 数据集划分规范（开发/验证/测试隔离）与公开数据集许可合规
- 隐私保护：票据敏感信息本地化处理、样例授权与脱敏
================================================================================
