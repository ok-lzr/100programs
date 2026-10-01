================================================================================
项目编号：088                    难度等级：★★★★☆（中型项目，偏难）
项目名称：人脸相册自动分类
所属分类：人工智能入门 / 计算机视觉
建议工时：4 ~ 6 天
运行环境：Python 3.10+    第三方依赖：face_recognition（或 dlib）、opencv-python、numpy、scikit-learn、Pillow、exifread、tqdm
================================================================================

【一、项目背景与目标】

十年积累的手机相册里往往有几万张照片，想找出某个人的所有照片，只能靠翻年份、靠记忆，或者
用需要把照片上传到云端的产品。家庭场景下，照片里同时有家人、朋友和陌生人，人工归档几千张
照片是不现实的。

本项目实现一个纯本地运行的人脸相册自动分类工具。它扫描指定目录下的全部照片，对每张照片做
人脸检测，为检测到的每张人脸提取 128 维特征向量，然后用基于密度的聚类算法把相似的人脸聚成
一类，每个类对应一个“未知人物”，最后由用户为每个类命名（或合并被拆开的类），工具再按人物
建立归档目录，把照片以硬链接或复制的方式整理进对应人物的相册；同时生成人物封面拼图、人物
出现次数统计与照片时间线。

目标用户是希望整理家庭照片、又在意隐私不愿上传云端的个人用户，以及想学习“检测—特征—
聚类”完整链路的学习者。项目完成后，可以得到一份按人物组织的相册目录，以及一份“哪个类需要
人工确认”的清单。

数据来源与规模：评估与开发使用公开数据集 LFW（Labeled Faces in the Wild，约 13233 张
人脸、5749 人，其中不少于 1680 人有两张以上照片）作为算法验证数据；实际使用数据为
用户自有的家庭照片目录（建议不少于 800 张、覆盖不少于 15 个不同人物）。按使用规范划分：
LFW 中取 4000 对同人/异人样本作为验证集用于选择聚类阈值，另取 2000 对作为测试集；
自有照片目录中人工标注 300 张照片的人脸身份作为测试集，评估聚类纯度与检测召回。
所有数据集仅用于学习与研究，不得用于人脸识别门禁、身份核验、监控追踪等任何实际身份
认定场景。

隐私与伦理声明：照片涉及本人及家人的生物特征信息，属于敏感个人信息，处理必须取得被拍摄者
同意；全部计算在本机完成，工具不得包含任何上传网络、遥测或云端 API 调用；人脸特征向量文件
必须可一键删除，删除后不保留任何派生数据；不得把分类结果、人物命名或封面拼图公开发布；
不得将本工具用于识别未授权人员、跟踪他人或任何侵犯隐私的用途。

【二、功能需求清单】

1. 核心功能
   1.1 照片扫描：递归扫描输入目录，支持 .jpg/.jpeg/.png/.bmp/.webp/.heic（HEIC 通过
       pillow-heif 可选支持，未安装时跳过并提示）；按文件大小与 mtime 建立缓存，第二次
       运行只处理新增或修改过的图片，缓存存于 index.json 或 SQLite。
   1.2 EXIF 读取：解析拍摄时间（DateTimeOriginal，缺失时回退到文件 mtime）、相机型号、
       图像方向并做像素级旋转纠正（处理手机竖拍的 Orientation 标记）、GPS 经纬度（仅
       本地保存，默认不在报告中输出）。
   1.3 人脸检测：优先使用 face_recognition 的 HOG 模型（速度快、CPU 友好），可通过
       --model cnn 切换到 CNN 模型（精度更高，建议有 GPU 时使用）。检测结果包含人脸框
       (top, right, bottom, left) 与 68 点关键点；对小于 40x40 像素的人脸可选择跳过
       （--min-face-size）以减少误检。
   1.4 特征提取：对每张人脸提取 128 维编码向量（face_encodings），与人脸框、所属图片
       路径、拍摄时间一起入库；同一张照片中检测到多张人脸时分别入库，并记录 face_index。
   1.5 图像质量过滤：计算人脸区域的清晰度（拉普拉斯方差）、亮度均值、遮挡比例（关键点
       置信度），对模糊或过暗的人脸标记 low_quality，默认不参与聚类但保留记录。
   1.6 聚类：使用 scikit-learn 的 DBSCAN，距离度量用欧氏距离，默认 eps=0.45、
       min_samples=2（两个阈值均可在配置中调整并用验证集选择）；DBSCAN 的噪声点
       （label 为 -1）单独归入“未分组/陌生人”集合，不强行分配到某个人物。
   1.7 聚类后处理：支持 merge（把两个类合并）、rename（给类命名）、move（把某张人脸移到
       另一个类）、split（按子聚类把一个大类拆开，使用 eps 更小的二次 DBSCAN）、
       exclude（把误检的非人脸剔除）四类人工操作，全部记入 labels.json，重跑时标签
       优先于自动聚类结果。
   1.8 归档输出：对每个命名人物创建目录，目录内可用 --mode hardlink（默认，节省空间）
       或 copy 或 move 整理照片；一张照片含多个人物时，在每个相关人物目录中都出现一次；
       文件名保持原文件名，重名时追加 序号。同时生成 contact_sheet_<人物>.jpg 封面拼图
       （最多 20 张，按清晰度与正脸程度排序取前若干张）与 report.html 统计报告。
   1.9 增量更新：新增照片时只对新增人脸做特征提取，并把新向量分配给已有类（计算与各类
       质心的距离，小于 eps 则归入最近的类，否则作为噪声等待下一轮整体重聚类）。
   1.10 人物统计：每个人物的人脸数、照片数、时间跨度（首末拍摄时间）、平均人脸质量分，
       以及“同一天出现最多的人物组合”等基础统计。

2. 输入与交互
   2.1 命令：init、scan（扫描与检测）、embed（特征提取）、cluster（聚类）、review
       （生成待确认清单与封面，输出到 review/ 目录）、label（交互式命名与合并）、
       organize（归档出片）、stats、export、clean（清理缓存与特征文件）。
   2.2 典型调用：
       python -m facealbum scan --input D:\Photos --recursive --model hog --min-face-size 48
       python -m facealbum cluster --eps 0.45 --min-samples 2 --min-quality 0.35
       python -m facealbum label --interactive
       python -m facealbum organize --output D:\Albums --mode hardlink
   2.3 交互式命名：对每个类显示一张由该类前 9 张人脸组成的九宫格拼图（保存为
       review/cluster_<id>.jpg 并在终端打印路径），提示输入姓名、输入 m 合并到已有类、
       输入 s 拆分、输入 n 标记为无需分类、输入 d 删除该类（误检）。
   2.4 配置文件 config.yaml 保存模型选择、聚类阈值、最小人脸尺寸、质量阈值、归档模式与
       排除目录。

3. 输出与展示
   3.1 扫描阶段用 tqdm 显示进度：已处理/总数、命中人脸数、跳过数。
   3.2 cluster 命令输出：参与聚类的人脸 N 张，聚成 K 个类，噪声点 M 个；各类大小分布
       （前 10 大类的 id 与人数）。
   3.3 review 命令输出待确认清单 review/todo.csv，含 cluster_id、人脸数、示例图片路径、
       建议动作（新命名/合并/剔除）。
   3.4 report.html 显示人物卡片网格（封面、姓名、照片数、时间跨度），并给出质量统计与
       未分组人脸数量；页面所有资源内嵌，可离线打开。
   3.5 organize 结束打印：归档 3120 张照片到 18 个人物目录，硬链接创建 3105 个，
       空间增量约 220 MB（其余为硬链接不占额外空间）。

4. 异常与边界处理
   4.1 HEIC/RAW 等不支持的格式：跳过并计入 skipped.csv，不报错中断。
   4.2 图片损坏或只有部分数据时，Pillow 抛 UnidentifiedImageError，捕获后记录并继续。
   4.3 人脸检测未命中任何脸的照片（风景照）正常跳过，不做任何标记。
   4.4 一张照片中出现超过 10 张人脸（合影）时正常处理，但归档时提示该照片属于多人。
   4.5 聚类结果全为噪声（阈值过严）或只有一个类包含全部人脸（阈值过松）时，给出明确的
       阈值建议：前者提示增大 eps，后者提示减小 eps 或提高 min_samples。
   4.6 硬链接跨盘符不可用时自动回退为复制并提示；move 模式必须二次确认。
   4.7 特征文件被删除后 organize 仍需可用（从 index 中重新计算或提示先执行 embed）。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上；数值计算使用 numpy；不引入深度学习框架训练，仅使用
   预训练的人脸编码模型。
2. 允许使用的库：face_recognition（基于 dlib 的 128 维人脸编码与 HOG/CNN 检测；若安装
   困难可改用 dlib 直接调用 dlib.get_frontal_face_detector 与
   dlib.face_recognition_model_v1 并自行实现检测与编码流程）、opencv-python（图像读写、
   清晰度计算、拼图绘制）、numpy（向量运算与距离矩阵）、scikit-learn（DBSCAN 聚类、
   轮廓系数评估）、Pillow（EXIF 与图像处理）、exifread（可选，EXIF 读取）、tqdm（进度条）、
   pandas（统计与导出）、pytest（测试）。缓存与索引使用标准库 sqlite3 或 json、pathlib、
   hashlib、shutil、dataclasses。
3. 禁止事项：禁止任何形式的上传、联网识别或调用云端人脸 API；禁止把特征向量与真实身份
   信息（身份证号、电话）关联存储；禁止在未获得同意的情况下处理他人照片；禁止把
   labels.json 与特征文件提交到任何代码仓库；禁止在归档时静默删除原照片（move 必须显式
   指定并确认）。
4. 代码组织：模块划分为 scanner（目录遍历与缓存）、exif（元数据解析与方向纠正）、
   detector（人脸检测与关键点）、encoder（128 维特征提取与质量评分）、clusterer
   （DBSCAN、二次聚类、增量分配）、labelstore（人工标签的读写与优先级）、organizer
   （归档、硬链接、拼图、报告）、cli。
5. 编码规范：全部函数带类型注解与 docstring；对 numpy 数组的维度与取值范围必须在
   docstring 中写清（如 encoding 为 shape=(128,) 的 float64，欧氏距离阈值典型范围
   0.4~0.6）；批处理函数必须支持分批读取以避免全部图片同时驻留内存；日志使用 logging，
   记录每阶段耗时。

【四、设计要点】

1. 数据结构
   - Photo：photo_id、path、size、mtime、taken_at、width、height、orientation、
     camera、gps（可选）。
   - FaceRecord：face_id、photo_id、box（top/right/bottom/left）、landmarks（68 点）、
     encoding（128 维 float64，存为 BLOB 或 JSON）、quality_score、blur_score、
     brightness、low_quality（bool）、cluster_id、person_name。
   - ClusterInfo：cluster_id、size、centroid（128 维均值向量）、representative_faces
     （list[face_id]）、person_name、merged_from（list[cluster_id]）、source
     （auto/manual）。
   - LabelOverride：face_id 或 cluster_id、action（name/merge/move/split/exclude）、
     value、updated_at。
   - 数据库表：photos、faces、clusters、overrides、scan_cache，faces 表对 cluster_id 与
     photo_id 建索引，encoding 存 BLOB（numpy tobytes）以节省空间。
2. 关键算法或流程
   - 扫描与检测流程：遍历目录并按 (size, mtime) 查缓存 → 读取图片并纠正方向 → 缩放到
     长边不超过 1200 px 以加速检测 → face_locations(img, model="hog") 得到人脸框 →
     对每个框计算质量（拉普拉斯方差、亮度均值、框面积占比）→ face_encodings(img, boxes)
     得到 128 维向量 → 落库。
   - 距离与聚类：构造 N×N 的欧氏距离矩阵（可用 numpy 广播或 sklearn.metrics.
     pairwise_distances，N 超过 20000 时分块计算），DBSCAN(eps=0.45, min_samples=2,
     metric="precomputed") 得到标签；随后计算每个类的质心与类内最大距离，把类内最大
     距离大于 0.6 的类标记为“可能包含两个人物”，提示人工拆分。
   - 阈值选择：在 LFW 验证集上计算同人/异人距离分布，绘制（或打印）直方图统计，选择使
     假阳性率低于 0.1% 的阈值作为 eps 上限，使召回尽量高的值作为 eps 下限，取区间中点
     作为默认值；该过程写成 tune 命令并在报告中记录选择依据。
   - 二次拆分：对指定类取出其成员向量，用更小的 eps（如 0.35）再跑一次 DBSCAN，若得到
     两个以上子类且子类规模均不小于 2，则按子类拆分并保留原类名给最大子类。
   - 增量分配：新向量与每个已命名类质心计算距离，取最小者；若距离小于 eps 则分配，否则
     记为噪声；当噪声累积超过 20 个时提示重新整体聚类。
   - 归档：按人物分组照片，使用 os.link 创建硬链接（同一文件系统内），失败则
     shutil.copy2；封面拼图按 quality_score 排序取前 20 张，用 OpenCV 拼 4 列网格并
     在每格下方写序号。
3. 接口或命令设计
   - 核心签名：detect_faces(img: np.ndarray, model: str, min_size: int) -> list[Box]；
     encode_faces(img: np.ndarray, boxes: list[Box]) -> np.ndarray（shape=(n,128)）；
     cluster_faces(encodings: np.ndarray, eps: float, min_samples: int) -> np.ndarray；
     assign_incremental(new_vec, centroids: dict[str, np.ndarray], eps: float) -> str | None；
     organize(albums: dict[str, list[Path]], output: Path, mode: str) -> OrganizeReport。
   - CLI：python -m facealbum cluster --eps 0.45 --min-samples 2 --tune-report out/tune.json
   - CLI：python -m facealbum label --merge 4 11 --name "妈妈"（非交互式批量操作，便于脚本化）

【五、运行方式与示例】

安装与运行：
    pip install face_recognition opencv-python numpy scikit-learn Pillow tqdm pandas exifread pytest
    （face_recognition 依赖 dlib，Windows 上建议先安装 CMake 与 Visual Studio Build Tools，
     或使用预编译 wheel；也可改用 dlib 直接调用）
    python -m facealbum init --db data/facealbum.db
    python -m facealbum scan --input D:\Photos --recursive
    python -m facealbum embed
    python -m facealbum cluster --eps 0.45 --min-samples 2
    python -m facealbum review
    python -m facealbum label --interactive
    python -m facealbum organize --output D:\Albums --mode hardlink

示例一（扫描与检测）：
    输入：python -m facealbum scan --input D:\Photos --recursive --min-face-size 48
    输出：扫描 8421 张照片（跳过 12 张不支持的格式，2 张损坏）
          检测到 9210 张人脸，其中 312 张因模糊或过暗标记为 low_quality
          耗时 486 秒，缓存已写入（下次运行只处理新增照片）

示例二（聚类）：
    输入：python -m facealbum cluster --eps 0.45 --min-samples 2
    输出：参与聚类 8898 张人脸，聚成 27 个类，噪声点（未分组）162 张
          类大小分布：C3=1841 C7=1203 C1=980 C12=641 C5=402 ...（前 10 个）
          提示：类 C9 类内最大距离 0.71，可能包含两个人物，建议执行 split 拆分

示例三（阈值调优报告）：
    输入：python -m facealbum cluster --tune --lfw-pairs data\lfw_pairs_val.txt
    输出：同人距离均值 0.36（P95=0.52），异人距离均值 0.91（P5=0.61）
          取假阳性率小于 0.1% 的阈值 0.50 与高召回阈值 0.42，默认 eps 取 0.45
          验证集 4000 对：准确率 0.978，精确率 0.965，召回率 0.991，F1 0.978
          测试集 2000 对：准确率 0.974，精确率 0.960，召回率 0.988，F1 0.974

示例四（聚类质量评估）：
    输入：python -m facealbum stats --gt data\gt_faces_300.csv
    输出：测试集 300 张人脸：检测召回 0.983，聚类纯度 0.941
          成对精确率 0.962，成对召回率 0.938，成对 F1 0.950
          未命名人物类 3 个（建议人工确认）

示例五（异常输入）：
    输入：python -m facealbum organize --output D:\Albums --mode move
    输出：警告：move 模式将把原照片移动到目标目录（不可逆）。
          请加 --yes 确认，或改用 --mode hardlink / copy。已中止，未移动任何文件，退出码 1

【六、验收标准】

[ ] 扫描目录支持递归与多格式，损坏图片与 HEIC 被跳过且记录在 skipped.csv
[ ] EXIF 拍摄时间被正确解析，缺失时回退到文件 mtime，手机竖拍照片方向被纠正
[ ] 人脸检测在测试集上召回不低于 0.95（受控件清晰度影响，需在报告中记录实测值）
[ ] 每张人脸都保存 128 维特征向量，维度与取值范围校验通过
[ ] low_quality 人脸默认不参与聚类但记录保留，可在配置中开启参与
[ ] DBSCAN 聚类在 eps 与 min_samples 变化时结果符合预期（阈值越大人脸越少类）
[ ] 聚类质量在标注测试集上输出纯度、成对精确率/召回率/F1，且口径与手算一致
[ ] 噪声点被归入未分组集合，不会被强行分配给人名
[ ] label 的 rename/merge/move/split/exclude 五类操作均生效且重跑后仍保持
[ ] 一张含多人的照片会出现在每个相关人物目录中，且不重复计数统计
[ ] 硬链接模式在本盘生效（空间增量远小于照片总大小），跨盘时自动回退为复制并提示
[ ] 封面拼图按质量排序取图，review 目录下能看到每个类的九宫格
[ ] reindex/report.html 可离线打开且显示真实统计（人物数、照片数、时间跨度）
[ ] 删除特征文件后工具不会崩溃，organize 会提示先执行 embed
[ ] 代码中不存在任何网络请求调用（可用依赖静态检查确认），无遥测

【七、可选扩展】

1. 增加视频帧人脸提取：对家庭视频按关键帧抽帧后检测人脸，把视频也纳入人物相册。
2. 增加人脸质量自动优选：为每个人物自动挑出最佳合影（人脸数量达到阈值且平均质量最高）。
3. 引入更强的人脸嵌入模型（如 ArcFace 的 ONNX 推理版），与 128 维 dlib 编码做对比实验，
   评估在同人异人距离分布与聚类纯度上的差异。
4. 增加时间轴视图：按年/月聚合人物出现次数，生成 HTML 时间轴，便于回顾家庭照片变化。

【八、涉及知识点】

- 人脸检测（HOG 与 CNN）、关键点定位与人脸对齐的基本原理
- 人脸嵌入向量、欧氏距离阈值与同人/异人判定
- DBSCAN 密度聚类、噪声点概念、eps 与 min_samples 的影响与调参方法
- 聚类质量评价：纯度、成对精确率/召回率/F1、轮廓系数
- numpy 向量化距离计算、分块处理大矩阵以控制内存
- 图像质量评估：拉普拉斯方差、亮度统计、EXIF 方向处理
- 硬链接与复制的差异、文件系统限制与空间核算
- sklearn 与 OpenCV 在批处理管道中的协作、缓存与增量更新设计
- 人脸数据隐私保护、知情同意、本地处理与数据删除权
================================================================================
