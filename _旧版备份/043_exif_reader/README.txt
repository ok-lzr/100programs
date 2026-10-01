================================================================================
项目编号：043                    难度等级：★★★☆☆（小型项目）
项目名称：照片 EXIF 读取器
所属分类：命令行工具 / 图像元数据
建议工时：5 ~ 7 小时
运行环境：Python 3.10+    第三方依赖：Pillow >= 10.0（pip install Pillow）
================================================================================

【一、项目背景与目标】

手机和相机拍出来的每张照片都埋着一份“拍摄档案”：什么时候拍的、用什么机型、什么镜头、光圈
快门 ISO 多少、有没有开闪光灯、在哪个经纬度拍的。这些信息平时看不见，但一旦需要就非常关键：
按拍摄日期给几百张旅行照片分组归档、统计自己最常用的焦段和光圈、确认某张照片是不是自己拍
的（含机身序列号）、把带 GPS 的照片批量清理后再发到社交平台。

市面上现成的工具要么收费，要么只能一次看一张，要么导出格式混乱。本项目做一个本地批量
EXIF 读取器，一条命令把整个目录（含子目录）的元数据导出成 CSV 或 JSON，并支持直接把文件按
拍摄时间重命名成 2024-05-01_143022_001.jpg 这种可排序的名字。整个程序不联网、不上传，照片
不会离开本机，处理私密照片时更放心。

目标用户是摄影爱好者、需要整理素材库的设计师、以及做作品集归档的普通用户。做成之后，一份
CSV 可以直接扔进 Excel 筛选“2024 年 8 月 用 iPhone 拍的所有照片”，也可以配合重命名功能把
相机与手机混拍的目录整理得井井有条。

【二、功能需求清单】

1. 核心功能
   1.1 基础信息读取：文件名、文件大小、像素尺寸（Image.size）、色彩模式、格式（im.format）、
       修改时间；对 EXIF 缺失的照片也要正常输出并标记“无 EXIF”。
   1.2 拍摄时间：优先 DateTimeOriginal(36867)，缺失时退回 DateTimeDigitized(36868)，
       再退回 DateTime(306)，最后退回文件系统 mtime。统一解析为 datetime 对象，
       EXIF 时间格式为 "YYYY:MM:DD HH:MM:SS"，用 datetime.strptime(s, "%Y:%m:%d %H:%M:%S")。
   1.3 设备信息：Make(271)、Model(272)、LensModel(42036)、Software(305)、
       BodySerialNumber(42033)、Orientation(274) 的数值与中文含义（如 6 = 顺时针旋转 90 度）。
   1.4 拍摄参数：ExposureTime(33434) 显示为 1/250 s（用 IFDRational 取倒数）、
       FNumber(33437) 显示为 f/2.8、ISOSpeedRatings(34855)、FocalLength(37386) 显示为
       24 mm、FocalLengthIn35mmFilm(41989)、ExposureProgram(34850) 与 Flash(37385) 按
       对照表翻译成中文。
   1.5 GPS 信息：GPSInfo(34853) 子 IFD 中的 GPSLatitudeRef(1)、GPSLatitude(2)、
       GPSLongitudeRef(3)、GPSLongitude(4)、GPSAltitudeRef(5)、GPSAltitude(6)。度分秒
       （IFDRational 三元组）换算为十进制度并保留 6 位小数，南纬西经取负值。
   1.6 导出：--format table|csv|json，table 为终端对齐输出，csv 用 csv.DictWriter
       （utf-8-sig 编码方便 Excel 打开），json 用 ensure_ascii=False, indent=2。
   1.7 按时间重命名：--rename 开关，格式由 --pattern 控制，默认
       "{date}_{time}_{seq:03d}"；支持 {date}/{time}/{seq}/{model}/{ext} 占位符。
       --apply 才真正改文件名，不加 --apply 只打印预览（默认安全模式）。
   1.8 目录与筛选：--recursive 递归子目录；--start 2024-01-01 --end 2024-12-31 按拍摄
       时间过滤；--has-gps 只保留含 GPS 的照片；--min-width 只保留长边达标的照片。

2. 输入与交互
   2.1 单文件模式：python exif_reader.py photo.jpg，直接打印该照片的完整信息卡片。
   2.2 目录模式：python exif_reader.py ./photos --recursive --format csv --output meta.csv。
   2.3 --summary 汇总模式：打印分辨率分布、机型 Top5、月份分布、镜头 Top5、光圈分布直方图
       （用字符 # 绘制横向条形，不依赖第三方绘图库）。
   2.4 询问式：--interactive 时逐个询问是否对某张照片执行重命名，回答 y/n/s（s 跳过剩余）。

3. 输出与展示
   3.1 单文件卡片示例：分行显示“拍摄时间 / 相机 / 镜头 / 参数 / GPS / 其他”，每行左对齐标签。
   3.2 目录模式默认只打印一行摘要 + 前 20 行的表格，加 --all 打印全部。
   3.3 GPS 除十进制度外，附带一句可点击的坐标描述文本（不联网查询地名）。
   3.4 重命名预览输出：“即将重命名：IMG_0231.JPG -> 2024-05-01_143022_001.JPG”。

4. 异常与边界处理
   4.1 图片没有 EXIF、或 EXIF 为空字典：不报错，各字段填“未知”，在末尾统计“N 张无 EXIF”。
   4.2 时间字段存在但格式非法（如 "0000:00:00 00:00:00"）：判定为无效时间并退回 mtime，
       记录一条 DEBUG 日志。
   4.3 GPS 坐标含 0/0 的 IFDRational：捕获 ZeroDivisionError，该字段输出“无效坐标”。
   4.4 非图片文件（.txt、无扩展名）默认忽略并计数；--strict 时视为错误并计入失败列表。
   4.5 重命名时目标文件名已存在：自动在序号后追加 _1、_2，或在 --force 时覆盖。
   4.6 重命名失败（文件被占用、只读属性）：捕获 PermissionError，记录并在末尾给出
       “成功重命名 N 张，失败 M 张”的明细。
   4.7 相机时间未设置时区：一律按“本地时间”处理，不做 UTC 换算；在表头说明这一点。
   4.8 文件名含中文或 emoji：CSV 用 utf-8-sig，JSON 用 ensure_ascii=False，确保不出现乱码。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：Pillow（仅用 Image.open 与 Image.Exif，不做任何像素级处理）；标准库
   argparse、pathlib、csv、json、datetime、logging、collections、dataclasses、re。
   不引入 pandas，统计用 collections.Counter 完成。
3. 禁止事项：禁止联网（含 requests、urllib 访问外网）；禁止修改图片像素内容；
   禁止在没有 --apply 的情况下改动任何文件名；禁止用字符串切割硬编码解析 EXIF 二进制。
4. 代码组织：
   - exif_tags.py：标签号到中文名的映射字典、Orientation/Flash/ExposureProgram 对照表。
   - reader.py：read_exif(path) -> PhotoMeta，内部完成标签取值、时间解析、GPS 换算。
   - gps.py：to_decimal(rationals, ref) -> float|None，处理 DMS 与南北东西符号。
   - rename.py：build_new_name(meta, pattern, seq) -> str、plan_renames(metas, pattern)
     -> list[tuple[Path, Path]]、apply_renames(plan)。
   - report.py：render_table(metas)、write_csv(metas, path)、write_json(metas, path)、
     render_summary(metas)。
   - cli.py：参数解析与主流程。
5. 编码规范：PhotoMeta 用 @dataclass(slots=True) 定义并写清每个字段单位；所有时间字段一律
   是 datetime 对象而非字符串，只在渲染阶段格式化；类型注解完整；日志分级，重命名操作
   必须写 INFO 级日志留痕；docstring 用中文说明取值优先级。

【四、设计要点】

1. 数据结构：
   PhotoMeta 字段：path(Path)、file_bytes(int)、width(int)、height(int)、mode(str)、
   format(str)、has_exif(bool)、taken_at(datetime|None)、time_source(str)、
   make/model/lens/software/serial(str|None)、orientation(int|None)、
   exposure_time(str|None)、f_number(float|None)、iso(int|None)、
   focal_length(float|None)、focal_35mm(int|None)、exposure_program(str|None)、
   flash(str|None)、gps_lat(float|None)、gps_lon(float|None)、gps_alt(float|None)、
   gps_text(str|None)、extra(dict[str, str])。
   四个派生属性：megapixels、aspect_ratio（最简整数比）、is_rotated、age_days。

2. 关键算法或流程：
   2.1 读取流程：with Image.open(p) as im 取 size/mode/format -> exif = im.getexif()
       -> 若为空则 has_exif=False -> 逐字段用 exif.get(tag) 取值，取值失败返回 None 而不是
       抛异常 -> get_ifd(ExifTags.IFD.Exif) 取拍摄参数子 IFD -> get_ifd(ExifTags.IFD.GPSInfo)
       取 GPS 子 IFD -> 构造 PhotoMeta。
   2.2 Pillow 10+ 用 exif.get_ifd(0x8769) 取 Exif 子 IFD，用 exif.get_ifd(0x8825) 取 GPS
       子 IFD；Pillow 9 及更早需用 exif.get(0x8769) 取嵌套字典，代码里用 try/except
       AttributeError 做兼容并在文档中写明版本差异。
   2.3 曝光时间格式化：t = float(value)；若 t < 1 且 t > 0 则输出 f"1/{round(1/t)} s"，
       否则输出 f"{t:g} s"；大于 1 秒时提示“长曝光”。
   2.4 GPS 十进制度：d, m, s = [float(x) for x in rationals]；
       dec = d + m/60 + s/3600；若 ref in ("S", "W") 则 dec = -dec。浮点比较用
       round(dec, 6)。
   2.5 概览直方图：Counter 统计后用 max_count 归一化，每个条目输出 int(count/max*40) 个
       '#' 字符，保证最长的条刚好 40 列。
   2.6 重命名冲突消解：先收集所有目标名放入集合 seen；若冲突，在 {seq} 上自增，
       或在扩展名前追加 _1；最终产出 (old, new) 二元组列表，先全部规划再统一执行，
       保证同一批次内不会互相覆盖。
   2.7 两步重命名防止 A->B、B->C 的链式覆盖：先把所有源文件的计划写入列表，再检查目标名
       是否与某个源名相同，若相同则改走临时名（加 .tmpren 后缀）再改成最终名。

3. 接口设计：
   python exif_reader.py PATH [PATH...] [--recursive] [--format table|csv|json]
     [--output FILE] [--summary] [--all] [--rename] [--apply]
     [--pattern '{date}_{time}_{seq:03d}'] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
     [--has-gps] [--min-width N] [--strict] [--force] [--verbose]
   核心函数：read_exif(path: Path) -> PhotoMeta
             to_decimal(values: Sequence[IFDRational], ref: str) -> float | None
             plan_renames(metas: list[PhotoMeta], pattern: str) -> list[tuple[Path, Path]]

【五、运行方式与示例】

1. 安装依赖与查看帮助：
   pip install "Pillow>=10.0"
   python exif_reader.py --help

2. 单张照片信息卡片：
   python exif_reader.py ./IMG_0231.JPG
   输出：文件名    : IMG_0231.JPG
         像素尺寸  : 4032 x 3024 (12.2 MP)
         拍摄时间  : 2024-05-01 14:30:22（来源 EXIF DateTimeOriginal）
         相机      : Apple iPhone 14 Pro
         镜头      : iPhone 14 Pro back camera 6.86mm f/1.78
         拍摄参数  : 1/250 s  f/1.78  ISO 64  24 mm  (自动曝光)  未闪光
         GPS       : 39.904200, 116.407400  海拔 44.5 m
         其他      : 方向 6（顺时针旋转 90 度）  软件 iOS 17.4.1

3. 批量导出 CSV 并按时间过滤：
   python exif_reader.py D:\photos --recursive --format csv --output meta.csv
     --start 2024-01-01 --end 2024-06-30
   输出：已扫描 512 个文件，符合时间条件 128 个，无 EXIF 3 个；已写入 meta.csv

4. 重命名预览（不落地）：
   python exif_reader.py ./trip --recursive --rename --pattern '{date}_{time}_{seq:03d}'
   输出：即将重命名：IMG_0231.JPG -> 2024-05-01_143022_001.JPG
         即将重命名：IMG_0232.JPG -> 2024-05-01_143355_002.JPG
         预览完成，共 2 个文件；加 --apply 才会真正改名。

5. 异常示例：目录中混入非图片文件且开启 strict
   python exif_reader.py ./mixed --recursive --strict
   输出：错误：无法识别的文件 ./mixed/notes.txt（--strict 模式下计为失败）
         完成：成功 10，失败 1，无 EXIF 2（退出码 1）

6. 异常示例：文件路径不存在
   python exif_reader.py ./not_here.jpg
   输出：错误：路径不存在 D:\work\not_here.jpg（退出码 1）

【六、验收标准】

[ ] 对同一张照片，本程序读出的 DateTimeOriginal 与系统看图软件属性页显示的时间一致。
[ ] 对无 EXIF 的 PNG 截图，程序正常输出并把时间来源标为“文件修改时间”。
[ ] 曝光时间 1/8 秒显示为 “1/8 s”，30 秒显示为 “30 s”，不出现 0.125 或科学计数法。
[ ] 焦距与 35mm 等效焦距分别取自 FocalLength 与 FocalLengthIn35mmFilm，单位标注为 mm。
[ ] 含 GPS 的照片换算出的十进制度与在线地图坐标一致（误差 < 0.0001 度）。
[ ] 南纬/西经照片的纬经度为负值（用一张南半球样例照片验证）。
[ ] 时间戳为 0000:00:00 的照片回退到文件 mtime，并在表格中标注来源。
[ ] CSV 用 Excel 直接双击打开无乱码，列顺序固定且表头为其中文名。
[ ] JSON 输出的中文相机名不乱码，缩进为 2 空格，可被 json.load 正常解析。
[ ] --rename 不带 --apply 时目录内文件名与 mtime 完全不变。
[ ] --apply 重命名后所有文件仍能被 Pillow 打开，且 EXIF 内容与重命名前一致。
[ ] 构造 A/B 两个文件互相交换名字的场景，执行后内容未丢失（验证 .tmpren 两步法）。
[ ] --summary 的机型 Top5 与用 Excel 数据透视表统计的结果一致。
[ ] 处理 1000 张照片时内存占用稳定，不随文件数线性增长（元数据对象用完即释放）。
[ ] 空目录或全部过滤掉时输出“无匹配文件”，退出码为 0，不生成空 CSV。

【七、可选扩展】

1. 增加 --geo-group 把含 GPS 的照片按网格（如 0.01 度）分到不同子目录，快速归类旅行照片。
2. 增加 --fix-time 批量修正相机时钟偏差（如 --offset -1h）。
3. 支持 MP4/MOV 的拍摄时间（用标准库解析 moov/mvhd 盒），与照片统一排序输出。
4. 增加 --merge-csv 把新扫描结果与历史 CSV 合并去重，形成长期照片索引。
5. 生成简易 HTML 索引页，按月份分组展示缩略图与参数（用 Pillow 生成缩略图）。

【八、涉及知识点】

- EXIF 结构：主 IFD、Exif 子 IFD、GPS 子 IFD、Interoperability IFD 的分层组织。
- Pillow 的 Image.Exif、get、get_ifd、ExifTags.Base 与 ExifTags.IFD 枚举。
- 常见标签号与含义：271 Make、272 Model、306 DateTime、33434 ExposureTime、
  33437 FNumber、34855 ISO、34853 GPSInfo、37386 FocalLength、274 Orientation。
- ifd_rational / IFDRational 类型与 float 转换、度分秒到十进制度的换算。
- datetime.strptime / strftime 格式化、timezone-naive 时间的处理约定。
- csv.DictWriter、utf-8-sig BOM 与 Excel 兼容性；json 的中文编码策略。
- collections.Counter 做频次统计与字符直方图绘制。
- 文件重命名的原子性与冲突消解（先规划后执行、临时名中转）。
================================================================================
