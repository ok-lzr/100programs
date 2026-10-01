================================================================================
项目编号：042                    难度等级：★★★☆☆（小型项目）
项目名称：图片格式批量转换
所属分类：命令行工具 / 图像处理
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：Pillow >= 10.0（pip install Pillow）
================================================================================

【一、项目背景与目标】

PNG/JPG/WebP/BMP/TIFF 这些格式各有各的脾气：PNG 支持透明但不支持有损压缩，一张截图动辄几
兆；JPG 体积小但没有透明通道，直接把带透明的 PNG 存成 JPG 会出现黑底或杂色边；WebP 体积最
优但某些老软件打不开；BMP 几乎不压缩，只适合特殊场景。很多人转换格式时用在线网站，把公司
的宣传图、含人脸的照片上传到别人的服务器，存在隐私风险。

本项目做一个完全本地的批量格式转换器，核心难点不是“换个后缀名”，而是处理三种真实的坑：
一是透明通道在转 JPG/BMP 时如何用指定颜色（默认白色）填底；二是转 WebP 时是有损还是无损、
质量取多少；三是色彩模式、ICC 配置文件与 EXIF 信息在转换后是否保留。程序要给出转换前后体积
对比报告，让人一眼看出省了多少空间。

目标用户是运营、设计助理和需要整理素材库的开发者。做成之后可以一条命令把整个素材目录统一
为 WebP，体积通常能降到 JPEG 的 60%~80%，同时保持视觉质量；也可以把一堆手机拍的 HEIC 转成
兼容性更好的 JPG（HEIC 需借助 pillow-heif，作为可选扩展）。

【二、功能需求清单】

1. 核心功能
   1.1 目标格式转换：--to 支持 png、jpg、webp、bmp、tiff、gif 六种。映射关系为
       PNG -> image.save(..., format="PNG")，jpg/jpeg -> "JPEG"，webp -> "WEBP"，
       bmp -> "BMP"，tiff/tif -> "TIFF"，gif -> "GIF"，用字典做大小写归一化。
   1.2 透明背景处理：源图有 Alpha 通道且目标格式不支持透明（JPG/BMP）时，先创建
       Image.new("RGB", size, bg_color) 纯色底图，再用 alpha 通道作 mask paste 上去。
       --bg-color 接受 #RRGGBB，默认 #FFFFFF；--bg-color none 表示直接丢弃 Alpha。
   1.3 质量与压缩参数：JPEG 用 --quality（1~100，默认 90）+ optimize=True；
       WebP 支持 --webp-mode lossy|lossless，lossy 用 quality，lossless 用
       lossless=True 且 method=6；PNG 用 --png-compress 0~9（默认 6）+ optimize=True。
   1.4 尺寸约束：--max-size 2048 表示长边超过 2048 时等比缩小；--min-size 用于防止误缩；
       两者都不给则保持原尺寸。缩放用 Image.LANCZOS 重采样。
   1.5 色彩模式规范化：自动处理 P 模式（调色板）转 RGBA / RGB、CMYK 转 RGB（用
       ImageCms 或 convert("RGB")）、LA 模式补 alpha、16 位灰度 I;16 转 8 位 L。
   1.6 元数据保留：--keep-exif 保留 EXIF（JPEG/WebP 支持），--strip-gps 在保留时清除
       0x8825 GPSInfo 标签；--keep-icc 保留 ICC 配置文件（Image.info.get("icc_profile")）。
   1.7 批量与目录结构：递归收集源目录所有图片，输出目录中按相对路径重建目录树；
       --flatten 开关则不建子目录，同名冲突自动追加 _1、_2 序号。
   1.8 对比报告：--report 生成 JSON 与可读文本两份报告，含每张图的原格式、新格式、原体积、
       新体积、压缩率、尺寸变化，以及整体合计（总原体积、总新体积、节省百分比）。

2. 输入与交互
   2.1 命令行单目标：python convert.py --input src --output dst --to webp --quality 82。
   2.2 多目标批量：--to jpg,webp 一次生成两种格式，输出分别落在 dst/jpg 与 dst/webp。
   2.3 交互模式：无参数运行时进入问答流程，依次询问输入目录、输出目录、目标格式、质量，
       每步给出默认值（直接回车使用默认），最后打印等价命令行便于复制。
   2.4 --list 只列出将要处理的文件与目标格式，不执行转换。

3. 输出与展示
   3.1 控制台逐行输出：a.png [PNG 1.8MB] -> a.webp [WEBP 420KB] (-76.7%, 640x480)。
   3.2 结束时输出表格状对齐的汇总行：共 24 张，合计 82.3MB -> 21.7MB，节省 73.6%。
   3.3 报告文本文件中用等宽列对齐（不用 Markdown 表格），列宽按最长文件名动态计算。
   3.4 失败清单单独一段，包含文件路径与失败原因（无法识别、权限不足、磁盘写入失败）。

4. 异常与边界处理
   4.1 源目录不存在或不是目录：中文报错 + 退出码 1，不做任何写入。
   4.2 输出目录与输入目录相同且格式未变时，拒绝执行并提示“输入输出相同会造成覆盖”，
       除非加 --force。
   4.3 目标格式与源格式相同时默认跳过（记 skipped），--recompress 开关可强制重压。
   4.4 无法识别的文件（PIL.UnidentifiedImageError）记 ERROR 并继续，最后在报告里列出。
   4.5 单张图解码后像素数超过 --max-pixels（默认 8000 万）时拒绝处理，防止内存爆炸。
   4.6 磁盘空间不足（OSError errno 28）时立即停止整批任务，保留已完成文件，退出码 1。
   4.7 GIF 动图：默认只处理第一帧并提示“动图已取首帧”；--gif-all-frames 时不支持转 JPG，
       给出明确错误。
   4.8 空目录：提示“未找到可转换的图片”，退出码 0，不生成空报告文件。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：Pillow；标准库 argparse、pathlib、logging、json、dataclasses、shutil、
   datetime、sys。可选：pillow-heif（读 HEIC/HEIF，需在文档中说明是额外依赖）。
3. 禁止事项：禁止只改扩展名而不真正重编码；禁止用 try/except: pass 吞掉异常；禁止在转换
   过程中修改或删除原始文件；禁止把用户目录硬编码进代码。
4. 代码组织：
   - formats.py：FORMAT_MAP 字典、resolve_format(name) 归一化函数、扩展名与格式互查。
   - image_ops.py：normalize_mode(im, target_fmt, bg_color)、resize_if_needed(im, max_size)、
     strip_gps(exif)、save_with_options(im, path, fmt, opts)。
   - convert.py：convert_one(src, dst, opts) -> ConvertResult、build_output_path()。
   - report.py：render_text_report(results)、write_json_report(results, path)。
   - cli.py：参数解析与交互问答 main()。
   每个函数 ≤ 40 行，参数对象统一用 @dataclass ConvertOptions 传递。
5. 编码规范：全量类型注解；docstring 说明参数、返回与可能抛出的异常；日志用 logging，
   格式 '%(asctime)s %(levelname)s %(message)s'，默认 INFO，--verbose 提到 DEBUG；
   关键词参数一律显式传参，禁止位置参数超过三个。

【四、设计要点】

1. 数据结构：
   ConvertOptions：src_dir(Path)、dst_dir(Path)、targets(list[str])、quality(int)、
   webp_mode(str)、png_compress(int)、bg_color(tuple|None)、keep_exif(bool)、
   keep_icc(bool)、strip_gps(bool)、max_size(int|None)、max_pixels(int)、
   flatten(bool)、overwrite(bool)、recompress(bool)、force(bool)、quality_gif(bool)。
   ConvertResult：src(Path)、dst(Path)、src_fmt(str)、dst_fmt(str)、src_bytes(int)、
   dst_bytes(int)、src_size(tuple)、dst_size(tuple)、status(str)、reason(str)、
   elapsed_ms(float)；派生属性 ratio = dst_bytes / src_bytes。

2. 关键算法或流程：
   2.1 预处理链：Image.open -> 读取 im.info 里的 exif 与 icc_profile -> 按 exif 的
       Orientation 摆正（ImageOps.exif_transpose）-> normalize_mode -> resize_if_needed。
   2.2 模式规范化规则表：目标 JPG/BMP -> 允许 RGB/L，其余先转 RGB 并按需铺底色；
       目标 PNG/WebP -> 允许 RGBA/RGB/L/LA/P，保留 Alpha；P 模式带 transparency 信息时
       先 convert("RGBA") 再走后续逻辑；CMYK 统一 convert("RGB")。
   2.3 保存参数装配：先构造空 dict，再按目标格式追加键值（quality/subsampling/
       optimize/progressive/lossless/method/compression），最后统一
       im.save(dst, format=fmt, **params)。JPEG 不支持 Alpha，保存前断言 mode in ("RGB","L")。
   2.4 输出路径计算：rel = src.relative_to(src_dir)；base = rel.with_suffix(新后缀)；
       未 flatten 时 dst = dst_dir / base，flatten 时用 base.name 并做冲突重命名。
   2.5 报告聚合：遍历 results，用 sum 累加 src_bytes 与 dst_bytes；跳过 status != ok 的项；
       压缩率 = (1 - 总新体积/总原体积) * 100，保留一位小数。

3. 接口设计：
   python convert.py --input DIR --output DIR --to FORMAT[,FORMAT...]
     [--quality 90] [--webp-mode lossy|lossless] [--png-compress 6]
     [--bg-color '#FFFFFF'|none] [--max-size N] [--max-pixels N]
     [--keep-exif] [--strip-gps] [--keep-icc] [--flatten] [--overwrite]
     [--recompress] [--force] [--list] [--report FILE] [--verbose]
   核心函数：convert_one(src: Path, dst: Path, opts: ConvertOptions) -> ConvertResult
             normalize_mode(im: Image.Image, fmt: str, bg: tuple|None) -> Image.Image

【五、运行方式与示例】

1. 安装与确认 Pillow 支持的目标格式：
   pip install "Pillow>=10.0"
   python -c "from PIL import features; features.pilinfo()"

2. PNG 转 WebP（有损，质量 82），生成报告：
   python convert.py --input ./png --output ./webp --to webp --quality 82
     --report convert_report
   输出：logo.png [PNG 1.8MB] -> webp/logo.webp [WEBP 420KB] (-76.7%, 640x480)
         共 24 张，合计 82.3MB -> 21.7MB，节省 73.6%；文本报告：convert_report.txt

3. 带透明的 PNG 转 JPG，用浅灰底：
   python convert.py --input ./icons --output ./jpg --to jpg --bg-color '#F2F2F2'
   输出：icon_03.png [PNG 24KB 含透明] -> jpg/icon_03.jpg [JPEG 9KB] (底色 #F2F2F2)

4. 一次生成两种格式并保留 EXIF、去掉 GPS：
   python convert.py --input ./photos --output ./out --to jpg,webp --keep-exif --strip-gps

5. 异常示例：输入输出目录相同
   python convert.py --input ./photos --output ./photos --to jpg
   输出：错误：输入目录与输出目录相同且目标格式可能覆盖原图，请改用 --force（退出码 1）

6. 异常示例：目录里没有图片
   python convert.py --input ./empty --output ./out --to png
   输出：未找到可转换的图片（支持：.jpg .jpeg .png .bmp .webp .tif .tiff .gif），退出码 0

【六、验收标准】

[ ] --to 的六种格式两两互转（含同格式）共 36 种组合均能完成，输出文件可被 Pillow 重新打开。
[ ] 带 Alpha 的 PNG 转 JPG 后无黑边，边缘像素颜色与 --bg-color 设置一致。
[ ] --quality 取 1/50/100 时文件体积单调递增，且 quality=100 时不报错。
[ ] WebP 无损模式输出可逐像素无损还原（用 ImageChops.difference 校验全黑）。
[ ] --max-size 2048 处理 6000x4000 的图后长边恰为 2048，宽高比误差小于 1 像素。
[ ] CMYK 模式 JPEG 转 PNG 后色彩无明显偏差，且再次打开 mode 为 RGB。
[ ] 16 位灰度 TIFF 转 PNG 后能正常打开，bit depth 降为 8 位并在日志中提示。
[ ] --keep-exif 输出的 JPEG 保留 DateTimeOriginal；加 --strip-gps 后 GPSInfo 标签消失。
[ ] --flatten 下两张同名不同目录的图输出为 a.jpg 与 a_1.jpg，无覆盖。
[ ] 目录结构（含两层子目录）在输出侧完整保留，相对路径与源一致。
[ ] 报告中单张与合计的字节数、压缩率计算正确（与 os.path.getsize 对比误差为 0）。
[ ] 混入一个 200KB 的文本文件改名为 .jpg 后，程序报告失败但不中断，退出码仍为 0。
[ ] 输入目录不存在时退出码为 1 且不创建输出目录。
[ ] 转换全过程中用文件系统时间戳或哈希校验确认原图未被修改。

【七、可选扩展】

1. 集成 pillow-heif 支持 iPhone 的 HEIC/HEIF 输入，用 --heic 开关启用。
2. 增加 --threads 参数用 concurrent.futures.ThreadPoolExecutor 并行转换（Pillow 释放 GIL
   的解码阶段可获益），并保证报告顺序稳定。
3. 支持 AVIF 输出（Pillow 11.3+ 内置 Pillow-AVIF 插件），与 WebP 对比体积。
4. 增加“只减小体积”策略：自动尝试多档质量，选出满足目标体积的最大质量。

【八、涉及知识点】

- Pillow 的格式注册表、Image.open 的惰性解码与 im.format / im.mode / im.size 属性。
- RGBA 与 RGB 的差异、Alpha 通道作为 paste mask 的用法、透明图转不透明格式的铺底技巧。
- 各格式的编码参数：JPEG quality/subsampling/progressive，PNG compress_level，
  WebP quality/lossless/method，GIF 调色板量化。
- 色彩模式转换（P/L/LA/RGB/RGBA/CMYK/I;16）与调色板透明信息处理。
- ICC 配置文件与 EXIF 在 Image.info 中的存储形式，以及跨格式保留的限制。
- pathlib 的 relative_to、with_suffix、mkdir(parents=True) 与跨平台路径拼接。
- dataclass 组织配置对象、JSON 报告序列化与动态列宽文本对齐。
================================================================================
