================================================================================
项目编号：040                    难度等级：★★★☆☆（小型项目）
项目名称：图片批量压缩与缩放
所属分类：图像、PDF 与音视频 / 命令行工具
建议工时：5 ~ 8 小时
运行环境：Python 3.10+    第三方依赖：Pillow
================================================================================

【一、项目背景与目标】

手机随手拍一张照片就是 4~6 MB，一次活动拍几百张，想要发给同事或上传到有大小限制的
系统时，就得一张张手动另存、调质量、改尺寸。用在线压缩网站又要上传原图，涉及隐私；
Photoshop 的批处理脚本门槛太高。更麻烦的是手机照片带有 EXIF 方向标记（Orientation），
处理不当会变成横着的图；PNG 截图带 Alpha 通道，转成 JPEG 时会出现黑底；CMYK 模式的
印刷图直接转存还可能偏色。

本项目做一个命令行批量图片压缩与缩放工具，重点解决三件事：
一是正确处理 EXIF 方向与色彩模式（RGB/RGBA/CMYK/调色板/P 模式）；
二是灵活的质量与尺寸控制（长边限制、百分比缩放、目标体积压缩）；
三是输出一份压缩前后体积对比报告（含压缩率与预计节省空间）。

目标用户是需要整理照片的自媒体作者、要做产品图上架的电商运营、要给课件瘦身的教师。

【二、功能需求清单】

1. 核心功能
   1.1 批量缩放：--max-long 1600 表示把长边限制到 1600 像素（短边等比缩放，只缩不放）；
       --scale 0.5 表示按百分比缩放；--width / --height 指定精确尺寸；
       同时给出 --width 与 --height 时默认保持比例（取较小缩放比），
       --stretch 时才强制拉伸到精确尺寸。
   1.2 质量控制：--quality 1~100（默认 82，仅对 JPEG/WEBP 有效）；
       --png-optimize 启用 PNG 优化压缩；--webp-method 0~6 设置 WebP 编码努力等级。
   1.3 目标体积模式：--target-size 500KB 自动二分搜索合适的 quality（1~95），
       在不超过目标体积的前提下取最高质量，最多尝试 7 次，结果记录实际质量。
   1.4 格式转换：--to jpeg|png|webp|same（默认 same）；
       --to jpeg 时把 RGBA 合成到指定背景色（--bg-color #FFFFFF，默认白色），
       避免透明区域变黑。
   1.5 元数据处理：默认保留 EXIF 中的拍摄时间与设备信息但移除 GPS 与缩略图
       （--strip-gps 默认开启）；--strip-all 移除全部元数据；--keep-exif 全部保留。
       无论哪种模式，都必须先按 Orientation 把图像"物理摆正"再保存，
       并把 Orientation 写回为 1。
   1.6 批量与递归：接受多个路径或一个目录（--recursive 递归），
       支持 --exclude 与 --min-size / --max-size 过滤；
       --skip-smaller 跳过压缩后反而变大的文件（保留原文件）。
   1.7 输出方式：--outdir 指定输出目录（保持相对目录结构）；
       --inplace 原地替换（先写 .tmp 再原子替换，并可选 --backup 备份原文件到 .bak）；
       --suffix _min 在文件名后追加后缀（默认 _min，避免与源文件冲突）。
   1.8 对比报告：--report 输出 CSV/JSON，列含原路径、新路径、原宽高、新宽高、
       原大小、新大小、压缩率、原格式、新格式、实际质量、耗时；并在终端打印汇总表。
   1.9 干跑模式：--dry-run 只扫描并打印将要执行的操作与预计结果，不写任何文件。
   1.10 并发：--workers N（默认 4）使用 ProcessPoolExecutor 并行处理（图像处理是 CPU 密集，
        多进程比多线程有效）。

2. 输入与交互
   2.1 入口：python cli.py <路径>... [选项]；至少需要一个路径。
   2.2 支持的输入扩展名：.jpg .jpeg .png .webp .bmp .tif .tiff .gif（仅取第一帧）；
       其它扩展名默认跳过并计入"跳过"数，--all-files 时尝试打开并给出失败原因。
   2.3 尺寸参数互斥检查：--scale 与 --width/--height 同时给出时报参数错误；
       --max-long 可与之共存（先按比例缩放再限制长边，取更严格的约束）。
   2.4 --target-size 与 --quality 同时给出时以 --target-size 为准并提示已忽略 --quality。
   2.5 遇到同名输出：默认追加序号 _1、_2；--overwrite 覆盖；--skip-existing 跳过。
   2.6 --list-formats 打印 Pillow 当前支持的可读写格式清单。

3. 输出与展示
   3.1 单文件处理输出（--verbose 时）：
       处理：IMG_2031.JPG → out\IMG_2031_min.jpg
       尺寸：4032x3024 → 1600x1200（比例 0.397）
       体积：5,241,088 → 412,673 字节（压缩 92.1%）
       质量：82（JPEG）  耗时：0.34 秒
   3.2 汇总表：
       总计 128 张，成功 124，跳过 3，失败 1
       原始总体积 612.4 MB → 输出总体积 48.7 MB（压缩 92.0%，节省 563.7 MB）
       平均耗时 0.31 秒/张，总耗时 9.6 秒
   3.3 报告文件：--report report.csv 写入 utf-8-sig 编码的 CSV；
       --report report.json 时写 JSON（顶层含 summary 与 items）。
   3.4 失败与跳过统一在结束前列出，每条含文件路径与原因。

4. 异常与边界处理
   4.1 输入不是图片或已损坏：捕获 PIL.UnidentifiedImageError，
       记入失败列表并给出"无法识别的图像格式或文件已损坏"。
   4.2 极窄/极小图片（任一边 < 16 像素）：不做放缩，只做压缩，并提示"图像过小"。
   4.3 缩放后边长为 0：强制最小为 1 像素，并提示"目标尺寸过小已调整为 1 像素"。
   4.4 EXIF 方向：Orientation 为 3/6/8 时分别旋转 180/90/270 度；
       必须调用 ImageOps.exif_transpose 或等价逻辑，且处理后写回 Orientation=1。
   4.5 色彩模式：
       - RGBA/LA/P 模式转 JPEG 时必须先用 --bg-color 合成到 RGB，
         用 Image.alpha_composite 在纯色底图上合成，不能用 convert("RGB") 直接转（会丢背景变黑）。
       - CMYK 转 RGB 时使用 PIL 内置转换并在报告中标注"色彩模式已转换 CMYK→RGB"。
       - 灰度图（L 模式）保持灰度输出，不强制转彩色。
   4.6 动画 GIF/WebP：默认只处理第一帧并提示"检测到 N 帧动画，仅处理第一帧"；
       --skip-animated 时直接跳过。
   4.7 ICC 配置文件：默认保留源 ICC profile；--strip-icc 时移除并提示可能轻微偏色。
   4.8 文件无写权限或目标目录不可写：捕获 PermissionError 并记入失败列表，继续处理其它文件。
   4.9 --target-size 无法达到（最小质量仍然超过目标）：输出实际最小体积，
       说明"已使用最低质量 1，体积 780 KB 仍超过目标 500 KB"，不算失败但计入警告。
   4.10 大图内存：单张图片像素数超过 1 亿时提示"图片过大，可能占用大量内存"，
        并设置 Image.MAX_IMAGE_PIXELS = None 前先要求确认（--allow-huge）。
   4.11 --inplace 时若写临时文件失败，原文件必须完好无损。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：Pillow（PIL：Image、ImageOps、ImageFile、ImageDraw、ImageChops、
   features）。其余使用标准库：argparse、pathlib、os、sys、time、csv、json、
   concurrent.futures、shutil、dataclasses、logging、typing、hashlib。
   安装：pip install Pillow
   不允许引入 numpy、opencv-python 等额外依赖（本项目要求纯 Pillow 实现）。
3. 禁止事项：禁止在 --inplace 模式下直接以原文件为输出目标打开写入（必须先写临时文件）；
   禁止用 convert("RGB") 处理带透明通道的图并保存为 JPEG（必须走 alpha_composite）；
   禁止忽略 EXIF Orientation（导致图片方向错误）；
   禁止在 multiprocessing 中传递 PIL Image 对象（应传递路径，在子进程内部打开）；
   禁止处理过程中上传任何图片到网络。
4. 代码组织：至少包含 scan.py（文件扫描与过滤）、transform.py（方向矫正、缩放、
   模式转换）、encode.py（质量选择与保存）、report.py（统计与报告输出）、cli.py。
   核心函数签名固定为
   load_and_orient(path: Path) -> tuple[Image.Image, dict]（返回图像与 EXIF 字典）
   resize_to(img: Image.Image, max_long: int | None, scale: float | None,
             width: int | None, height: int | None, stretch: bool) -> Image.Image
   save_with_target(img: Image.Image, dst: Path, target_bytes: int | None,
                    quality: int, fmt: str) -> tuple[int, int]
   （返回实际字节数与实际质量）
5. 编码规范：类型注解与 docstring 齐全；所有 PIL 对象在处理后调用 close() 或使用
   with 语义释放；日志只记录路径与统计，不打印像素数据；
   multiprocessing 的 worker 函数必须是模块级函数（可 pickle）。

【四、设计要点】

1. 数据结构：
   - Options：max_long、scale、width、height、stretch、quality、target_size、
     to_format、outdir、suffix、inplace、overwrite、skip_existing、recursive、
     strip_gps、strip_all、keep_exif、bg_color、workers、report_path、dry_run、
     skip_smaller、allow_huge。
   - ItemResult：src: Path，dst: Path | None，src_size: int，dst_size: int，
     src_dim: tuple[int, int]，dst_dim: tuple[int, int]，src_mode: str，
     src_format: str，dst_format: str，quality: int，elapsed: float，
     status: str（ok/skipped/failed），reason: str。
   - Summary：total、ok、skipped、failed、src_bytes、dst_bytes、saved_bytes、
     ratio、elapsed；方法 add(result) 与 to_dict()。
   - 格式与扩展名映射：{"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp",
     "BMP": ".bmp", "TIFF": ".tif", "GIF": ".gif"}。
2. 关键算法或流程：
   2.1 加载与方向矫正流程（关键，必须按顺序）：
       (a) with Image.open(path) as im: im.load()（此时才真正解码，便于捕获截断文件）；
       (b) exif = im.getexif()，orientation = exif.get(0x0112, 1)；
       (c) 用 ImageOps.exif_transpose(im) 得到摆正后的图像（Pillow 会自动处理
           翻转与 90/180/270 旋转）；
       (d) 在返回的 exif 中把 0x0112 置为 1（因为像素已摆正，再标记方向会导致二次旋转）；
       (e) 根据 --strip-* 选项删除 GPS IFD（exif.pop(0x8825, None) 并清理
           GPSInfo）与缩略图（exif.pop(0x0201/0x0202)）。
   2.2 缩放尺寸计算：
       - 只给 max_long：若 max(w, h) <= max_long 则不缩放；否则 ratio = max_long / max(w, h)。
       - 只给 scale：ratio = scale。
       - 只给 width：ratio = width / w。只给 height：ratio = height / h。
       - 同时给 width 与 height：等比模式 ratio = min(width/w, height/h)；
         stretch 模式直接 resize 到 (width, height)。
       - 多条件共存时取最小 ratio（保证不超过任何限制）。
       - 计算后 new_w = max(1, round(w * ratio))，new_h = max(1, round(h * ratio))。
   2.3 重采样滤波器选择（必须写清并实现）：
       - 缩小（ratio < 1）用 Image.Resampling.LANCZOS（质量最好，适合照片）。
       - 放大（ratio > 1，仅在明确指定更大尺寸时发生）用 Image.Resampling.BICUBIC。
       - 缩略图/像素画风格可用 --filter nearest，映射到 Image.Resampling.NEAREST。
   2.4 色彩模式转换规则表：
       - RGBA/LA/P（含透明）→ JPEG：新建一张 bg 色 RGB 图 →
         Image.alpha_composite(bg.convert("RGBA"), im.convert("RGBA")).convert("RGB")。
       - RGBA → PNG/WEBP：保留透明通道，不合成。
       - CMYK → 任意：im.convert("RGB")，并在报告中记录模式变化。
       - P（调色板）→ 需要缩放时先 convert("RGBA")（避免调色板缩放失真）。
       - L（灰度）→ JPEG/PNG：保持 "L"，不转 RGB（节省体积）。
   2.5 目标体积二分搜索：
       lo, hi = 1, 95；best = None；
       循环最多 7 次：mid = (lo + hi) // 2 → 保存到内存缓冲（io.BytesIO）→
       若 size <= target 则 best = (mid, data)，lo = mid + 1；否则 hi = mid - 1；
       循环结束若 best 为 None，则用最低质量 1 保存结果并记为警告。
       注意：必须保存到 BytesIO 而不是反复写磁盘；最终把选中的字节写入目标文件。
   2.6 保存参数：
       JPEG：quality=q, optimize=True, progressive=True, subsampling="4:2:0"（q<90 时），
             exif=exif_bytes, icc_profile=icc。
       PNG：optimize=True, compress_level=9；若需要透明则保持 RGBA。
       WEBP：quality=q, method=4, lossless=False, exif=exif_bytes。
       BMP：无质量参数（体积几乎不会变小，若 --to bmp 则给出"BMP 不支持有损压缩"的警告）。
   2.7 原地替换流程：dst_tmp = src.with_suffix(src.suffix + ".tmp") →
       保存到 tmp → 若 --backup 则 shutil.copy2(src, src.with_suffix(src.suffix + ".bak")) →
       os.replace(tmp, src) → 保留原文件的 mtime（用 os.utime 恢复为处理前的时间）。
   2.8 并发策略：主进程扫描得到路径列表 → ProcessPoolExecutor(max_workers=N) →
       submit(process_one, path, options_dict) → as_completed 收集 ItemResult →
       主进程统一刷新进度与汇总（子进程不做任何终端输出）。
3. 接口或命令设计：
   python cli.py <路径>... [--outdir DIR | --inplace] [--suffix _min]
                 [--max-long 1600 | --scale 0.5 | --width W --height H [--stretch]]
                 [--quality 82 | --target-size 500KB] [--to jpeg|png|webp|same]
                 [--bg-color #FFFFFF] [--filter lanczos|bicubic|nearest]
                 [--strip-all | --keep-exif] [--strip-icc]
                 [--recursive] [--exclude PATTERN]... [--min-size 1KB] [--max-size 50MB]
                 [--skip-smaller] [--skip-existing | --overwrite] [--backup]
                 [--workers 4] [--report report.csv] [--dry-run] [--verbose]
   退出码：0 全部成功（跳过不算失败）；1 有失败项；2 参数错误。

【五、运行方式与示例】

安装：
   pip install Pillow
运行：
   python cli.py .\photos --outdir .\out --max-long 1600 --quality 80 --recursive
   python cli.py .\photos\*.jpg --inplace --target-size 500KB --backup
   python cli.py .\shop --outdir .\web --to webp --max-long 1200 --report report.csv

示例一（批量缩放并压缩）：
   输入：python cli.py .\photos --outdir .\out --max-long 1600 --quality 80
   输出（--verbose 时逐张）：
   处理：photos\IMG_2031.JPG → out\IMG_2031_min.jpg
   尺寸：4032x3024 → 1600x1200（比例 0.397）
   体积：5,241,088 → 412,673 字节（压缩 92.1%）
   质量：82（JPEG）  耗时：0.34 秒
   汇总：
   总计 128 张，成功 124，跳过 3，失败 1
   原始总体积 612.4 MB → 输出总体积 48.7 MB（压缩 92.0%，节省 563.7 MB）
   平均耗时 0.31 秒/张，总耗时 9.6 秒

示例二（PNG 截图转 JPEG，处理透明通道）：
   输入：python cli.py .\shots\ui.png --to jpeg --bg-color "#FFFFFF" --quality 90
   输出：
   处理：shots\ui.png → ui_min.jpg
   色彩模式：RGBA → RGB（已按 #FFFFFF 合成背景）
   体积：183,204 → 46,882 字节（压缩 74.4%）

示例三（目标体积模式）：
   输入：python cli.py .\card.jpg --inplace --target-size 200KB --backup
   输出：
   处理：card.jpg → card.jpg（原地替换，已备份为 card.jpg.bak）
   尺寸：3000x2000（未缩放）
   体积：1,842,113 → 198,540 字节（压缩 89.2%）
   目标体积：204,800 字节，实际质量：61

示例四（异常输入一：损坏文件）：
   输入：python cli.py .\broken.jpg --outdir .\out
   输出：
   失败：broken.jpg  原因：无法识别的图像格式或文件已损坏
   总计 1 张，成功 0，跳过 0，失败 1
   退出码：1

示例五（异常输入二：参数冲突）：
   输入：python cli.py .\photos --scale 0.5 --width 800
   输出：
   错误：--scale 与 --width/--height 不能同时使用
   退出码：2

示例六（干跑）：
   输入：python cli.py .\photos --outdir .\out --max-long 1200 --dry-run
   输出：
   [dry-run] 将处理 128 个文件
   [dry-run] photos\IMG_2031.JPG 4032x3024 → 1200x900（预计约 300 KB）
   [dry-run] photos\IMG_2032.JPG 3024x4032 → 900x1200（预计约 280 KB）
   [dry-run] 未写入任何文件

【六、验收标准】

[ ] 一张 Orientation=6 的手机竖拍照片，处理后显示方向正确（不再横躺）。
[ ] PNG 透明图转 JPEG 后透明区域为指定背景色，不出现黑块。
[ ] CMYK 的测试图转 JPEG 后颜色无异常，报告中标注了模式转换。
[ ] 灰度图输出仍为灰度（用 PIL 读取 mode 为 "L"）。
[ ] --max-long 1600 对一张 4000x3000 的图输出 1600x1200，且长宽比误差小于 1 像素。
[ ] --max-long 2000 对一张 800x600 的图不放大，输出仍为 800x600。
[ ] --scale 0.5 输出尺寸为原尺寸的一半（四舍五入到整数）。
[ ] --target-size 200KB 输出的文件不超过 204800 字节，并报告实际质量。
[ ] --skip-smaller 生效：压缩后变大的文件不写入输出目录。
[ ] --report report.csv 的列与规范一致且可被 Excel 正确打开（中文不乱码）。
[ ] --inplace --backup 处理后原文件被替换且存在 .bak 备份，内容与处理前一致。
[ ] --dry-run 不产生任何输出文件。
[ ] 损坏的 JPEG 被记入失败列表，程序继续处理其余文件，退出码为 1。
[ ] --scale 与 --width 同时给出时报参数错误，退出码为 2。
[ ] 128 张照片批量处理时，--workers 4 的总耗时明显低于 --workers 1。
[ ] 处理 100 张图后内存占用不随时间持续增长（无 PIL 对象泄漏）。
[ ] --strip-gps 后输出的 EXIF 中不含 GPS 信息，Orientation 值为 1。

【七、可选扩展】

1. 增加 --smart-crop：按指定长宽比（如 1:1、16:9）居中裁剪而不是留边缩放。
2. 增加自动旋转误差校正：读取 EXIF 中的方向之外，结合亮度分布检测是否需要额外旋转 90 度。
3. 增加 AVIF 支持（Pillow 11+ 内置），并给出与 WebP 的体积对比。
4. 增加"相似图片去重"：对每张图算 dHash 感知哈希，输出重复组建议只保留一张。
5. 增加简单的 tkinter 拖放界面，实时显示压缩前后对比预览。

【八、涉及知识点】

- Pillow Image 对象的加载、模式（RGB/RGBA/L/P/CMYK）与转换陷阱
- EXIF 读取写入（getexif、ImageOps.exif_transpose、0x0112 方向标记）
- 图像重采样滤波器（LANCZOS/BICUBIC/NEAREST）的适用场景
- 有损压缩质量参数与文件体积的非线性关系
- 目标体积二分搜索与 io.BytesIO 内存缓冲
- 透明通道合成（alpha_composite）与背景色处理
- ProcessPoolExecutor 并行处理 CPU 密集任务与可 pickle 的 worker
- 原子文件替换（os.replace）、备份与 mtime 保留
- CSV/JSON 报告生成与单位换算（KB/MB、压缩率、节省空间）
================================================================================
