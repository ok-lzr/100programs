================================================================================
项目编号：041                    难度等级：★★★☆☆（小型项目）
项目名称：图片批量加水印
所属分类：命令行工具 / 图像处理
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：Pillow >= 10.0（pip install Pillow）
================================================================================

【一、项目背景与目标】

做自媒体、开网店、给客户交付效果图的人，几乎都会遇到同一件事：手里有几十上百张图，需要在
每张图上盖一个自己的店名、署名或 logo，防止被别人直接拿去用。用图像软件一张张手动加，一张
图三十秒，一百张就是一个多小时，而且每张图的水印位置很难对齐，交付时看起来不专业。

这个项目要做的就是把这件事变成一条命令：指定一个目录、一段文字或一张 logo PNG，程序自动
给目录里所有图片打上位置统一、透明度可控的水印，输出到另一个目录，原图不动。除了常规的单
点水印，还要支持“平铺防伪水印”——把文字以固定间距铺满整张图，这种水印即使被裁掉一个角也很
难完全去除，适合给证件照、合同扫描件、设计稿预览图做防泄露标记。

目标用户是不会写代码的普通办公用户，所以除了命令行参数，还要提供一个“输入目录、输出目录、
水印文字”三个字段的简易图形界面，双击就能跑。做成之后，它可以直接替代商业批量加水印软件的
基础功能，并且可以放进定时任务里，每天自动给当天新增的素材打标。

【二、功能需求清单】

1. 核心功能
   1.1 文字水印：支持任意 UTF-8 文本，可指定字体文件、字号、颜色（#RRGGBB 或 RGB 三元组）、
       是否加描边。描边用 ImageDraw.text 的 stroke_width 与 stroke_fill 参数实现。
   1.2 图片水印：支持加载带 Alpha 通道的 logo（PNG/WebP），按原图宽度的百分比缩放
       （--logo-scale 0.15 表示占原图宽度 15%），缩放后叠加到主图。
   1.3 九宫格定位：--position 接受 9 个取值 top-left、top-center、top-right、middle-left、
       center、middle-right、bottom-left、bottom-center、bottom-right，配合 --margin 像素
       边距计算落点。默认 bottom-right，边距 20 像素。
   1.4 透明度控制：--opacity 取 0.0 ~ 1.0，默认 0.35。实现方式是给水印单独建一张 RGBA
       图层，把水印像素的 alpha 通道乘以该系数，再与原图 Image.alpha_composite 合成。
   1.5 平铺防伪水印：--tile 开关 + --tile-gap 间距（默认 150 像素）+ --angle 旋转角
       （默认 30 度）。先把水印文字渲染到一张带边距的小图上，rotate(expand=True) 旋转后用
       双重循环铺满画布，形成对角密排效果。
   1.6 批量处理：--input 目录递归收集 *.jpg/*.jpeg/*.png/*.bmp/*.webp/*.tiff，--output
       指定输出目录，保持相对目录结构；不指定 --output 时默认写入 输入目录/watermarked。
   1.7 预演模式：--dry-run 只打印将要处理的文件清单与预估输出路径，不写任何文件。
   1.8 EXIF 方向校正：先读 Image.getexif() 的 0x0112（Orientation）标签，用
       ImageOps.exif_transpose 摆正图像再加水印，避免手机竖拍照片水印方向颠倒。

2. 输入与交互
   2.1 命令行：python watermark.py --input photos --output out --text "© 2025 张三"
       --position bottom-right --opacity 0.4 --font-size 48。
   2.2 图形界面：tkinter 三个 Entry（输入目录、输出目录、水印文字）+ 九宫格单选框 +
       透明度 Scale 滑块 + “开始处理”按钮 + 进度条 ttk.Progressbar。处理放在子线程，
       通过 queue.Queue 回传进度，避免主窗口卡死。
   2.3 无参数直接运行时若未提供 --text 也未提供 --logo，提示“必须提供 --text 或 --logo
       之一”并以退出码 2 结束。

3. 输出与展示
   3.1 输出文件默认沿用原扩展名；--convert-to webp 时统一转为 WebP 并追加 .webp 后缀。
   3.2 控制台按行输出：处理中 3/50  IMG_0003.JPG -> out/IMG_0003.JPG，末尾汇总
       “成功 48，跳过 1（已存在），失败 1”。
   3.3 --report report.json 输出统计：每个文件的输入路径、输出路径、尺寸、状态、耗时毫秒。
   3.4 JPEG 输出默认 quality=92、subsampling=0、optimize=True、keep EXIF（exif=原 EXIF
       字节），PNG 输出默认 optimize=True 保留 Alpha。

4. 异常与边界处理
   4.1 字体文件缺失或无法解析（TTF 损坏）时，回退到 ImageFont.load_default()，并在日志中
       以 WARNING 说明“已回退默认字体，中文可能显示为方块”。
   4.2 未提供 --font 时按平台搜索候选字体：Windows 用 C:/Windows/Fonts/msyh.ttc；
       macOS 用 /System/Library/Fonts/PingFang.ttc；Linux 用
       /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf，逐个 os.path.exists 探测。
   4.3 水印尺寸超过原图（图很小而字号很大）时，自动按 0.9 比例迭代缩放水印图层直到能放下，
       最多迭代 10 次；仍放不下则跳过该文件并记为失败。
   4.4 输出目录已存在同名文件时，默认跳过并计数；加 --overwrite 才覆盖。
   4.5 遇到截断/损坏图片时捕获 PIL.UnidentifiedImageError 与 OSError，记 ERROR 后继续处理
       下一张，不中断整批任务。
   4.6 输出路径不存在时用 os.makedirs(exist_ok=True) 创建；无写入权限时报告具体路径与
       errno，进程退出码为 1。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用 X | None 联合类型注解。
2. 允许使用的库：Pillow（图像读写、绘制、旋转、合成）；标准库 argparse、pathlib、logging、
   json、time、tkinter（仅 GUI 模式需要，缺失时给出提示并退回命令行模式）。
3. 禁止事项：禁止用 os.system 调用 ImageMagick 等外部程序；禁止把水印位置写死在代码里；
   禁止在没有变换的情况下原地覆盖用户原图；禁止使用 eval 解析颜色参数。
4. 代码组织：
   - config.py：@dataclass WatermarkConfig，集中存放所有参数与默认值。
   - font_utils.py：find_font(path)、load_font(path, size) 两个函数。
   - watermark.py：build_text_layer()、build_logo_layer()、place_layer()、tile_layer()、
     process_image()、process_batch()。
   - cli.py：build_parser()、main()。
   - gui.py：WatermarkApp 类，按钮回调只负责收集参数并起线程。
   - 每个函数只做一件事，图像对象的打开与关闭都用 with Image.open(...) as im。
5. 编码规范：所有公开函数写类型注解与中文 docstring（说明参数、返回、抛出异常）；变量名
   用 snake_case，类名用 PascalCase；运行时信息用 logging 输出，级别由 --verbose 控制，
   禁止散落的 print；文件头写统一的模块说明注释。

【四、设计要点】

1. 数据结构：
   WatermarkConfig 字段：input_dir(Path)、output_dir(Path)、text(str|None)、logo_path
   (Path|None)、position(str)、margin(int)、opacity(float)、font_path(str|None)、
   font_size(int)、color(tuple[int,int,int])、stroke_width(int)、tile(bool)、tile_gap(int)、
   angle(float)、logo_scale(float)、quality(int)、overwrite(bool)、dry_run(bool)、
   convert_to(str|None)。
   ProcessResult 字段：src(str)、dst(str)、status(str: ok|skip|failed)、reason(str)、
   width(int)、height(int)、elapsed_ms(float)。

2. 关键算法或流程：
   2.1 单张处理流程：打开图像 -> exif_transpose -> 转 RGBA 基底 base -> 按配置生成水印图层
       layer -> 若 tile 则平铺整张画布，否则按九宫格算 xy 并 paste -> alpha_composite 合成
       -> 按目标格式保存 -> 记录 ProcessResult。
   2.2 九宫格坐标：设水印宽 w、高 h，画布宽 W、高 H，边距 m。水平方向 x 取 m、
       (W-w)//2、W-w-m；垂直方向 y 取 m、(H-h)//2、H-h-m。用位置字符串拆成
       (vertical, horizontal) 两段映射，避免九条 if 分支。
   2.3 平铺算法：把水印先渲染成尺寸 (w+gap, h+gap) 的 RGBA 小图并 rotate(angle,
       expand=True, resample=Image.BICUBIC)，得到 tile 图；用 for y in range(-th, H+th, th)
       与 for x in range(-tx, W+tx, tx) 逐点 paste(tile, (x, y), tile)，越界部分由 Pillow
       自动裁掉。起始坐标取负值保证四角都铺满。
   2.4 透明度实现：绘制水印时用 fill=(r, g, b, int(255*opacity))；logo 模式则拆出 alpha
       通道，用 Image.eval(alpha, lambda a: int(a*opacity)) 后重新合并。
   2.5 自动缩小：while 水印宽 > 0.9*W or 水印高 > 0.9*H and tries < 10 时，把字号乘以 0.8
       重新渲染。

3. 接口设计：
   python watermark.py --input DIR [--output DIR] [--text TXT | --logo FILE.png]
     [--position bottom-right] [--margin 20] [--opacity 0.35]
     [--font FONT.ttf] [--font-size 48] [--color '#FFFFFF']
     [--stroke-width 2] [--tile] [--tile-gap 150] [--angle 30]
     [--logo-scale 0.15] [--quality 92] [--convert-to webp]
     [--overwrite] [--dry-run] [--report report.json] [--verbose] [--gui]
   函数签名：process_image(src: Path, cfg: WatermarkConfig) -> ProcessResult
             process_batch(cfg: WatermarkConfig) -> list[ProcessResult]

【五、运行方式与示例】

1. 安装依赖并查看帮助：
   pip install "Pillow>=10.0"
   python watermark.py --help

2. 右下角白色半透明文字水印，批量处理：
   python watermark.py --input D:\photos --output D:\out --text "© 2025 张三"
     --position bottom-right --opacity 0.4 --font-size 48
   输出：[3/12] ok  D:\photos\a.jpg -> D:\out\a.jpg (4032x3024, 118ms)
         [4/12] skip D:\out\b.jpg 已存在，跳过
         完成：成功 10，跳过 1，失败 1；明细见 report.json

3. LOGO 水印铺满整图：
   python watermark.py --input ./design --logo brand.png --tile --tile-gap 120
     --angle 45 --opacity 0.2 --logo-scale 0.12

4. 预演（不写文件）：
   python watermark.py --input ./photos --text "内部资料" --dry-run
   输出：将处理 8 个文件，输出目录 ./photos/watermarked（未写入任何文件）

5. 异常示例：水印参数缺失
   python watermark.py --input ./photos --opacity 0.5
   输出：错误：必须提供 --text 或 --logo 之一（退出码 2）

6. 异常示例：字体路径不存在
   python watermark.py --input ./photos --text "测试" --font ./nofont.ttf
   输出：WARNING 字体 ./nofont.ttf 不存在，已回退 C:/Windows/Fonts/msyh.ttc；
         若仍失败则使用默认位图字体，中文可能显示为方块（退出码 0，任务继续）

【六、验收标准】

[ ] 不带任何参数运行时打印清晰的中文帮助并返回退出码 0；--help 中每个参数有中文说明。
[ ] 单个目录内 10 张不同尺寸（含 1x1 与 8000x6000）的图片全部处理成功，无崩溃。
[ ] --position 九个取值分别执行一次，水印落点肉眼校验符合九宫格定义，边距等于 --margin。
[ ] --opacity 取 0.0 时输出图与原图像素级一致（用 Pillow 逐像素比对差值全为 0）。
[ ] --opacity 取 1.0 时水印完全不透明，边缘无灰边。
[ ] --tile 开启后四个角与中心区域均有水印，旋转角度与 --angle 一致。
[ ] 给一张带 Orientation=6 的竖拍照片加水印，输出方向正确、水印不被旋转 90 度。
[ ] 输入目录不存在时给出中文错误并返回退出码 1，不产生任何输出目录。
[ ] 混入一个损坏的 .jpg 后，其余文件仍全部处理完成，失败清单在 report.json 中可见。
[ ] 重复执行同一命令时全部报告 skip，加 --overwrite 后全部重新生成。
[ ] 输出 JPEG 用 Pillow 重新打开可读到原 EXIF 的 Make/DateTimeOriginal 字段。
[ ] --dry-run 执行前后输出目录的 mtime 与文件数量都不变。
[ ] GUI 模式下选目录、输入文字、点“开始处理”，进度条从 0% 走到 100%，窗口全程不卡死。
[ ] 中文字符水印在 Windows 与 Linux 上都能正常显示，不出现方块或问号。

【七、可选扩展】

1. 增加“水印模板”功能：把常用配置存成 JSON 预设，用 --preset shop 一键调用。
2. 支持按文件名或 EXIF 拍摄日期动态生成水印文字，例如自动加上拍摄年月。
3. 接入 multiprocessing.Pool 做并行处理，进程数由 --workers 控制。
4. 增加裁剪与缩放后自动重建水印的“缩略图流水线”，一次生成三种尺寸的交付图。

【八、涉及知识点】

- Pillow 的 Image、ImageDraw、ImageFont、ImageOps、ImageChops 模块与 RGBA 通道操作。
- alpha 合成原理与 Image.alpha_composite、Image.paste 的 mask 参数区别。
- 图像旋转与 expand 参数、双三次重采样对边缘质量的影响。
- EXIF 元数据的读取、保留与 Orientation 校正。
- pathlib.Path 递归遍历、rglob 与相对路径计算。
- argparse 子命令与互斥参数（add_mutually_exclusive_group）。
- tkinter 线程安全：子线程只往 Queue 写，主线程用 after() 轮询刷新界面。
- 跨平台字体发现与路径分隔符差异（os.sep、Path 对象优于字符串拼接）。
================================================================================
