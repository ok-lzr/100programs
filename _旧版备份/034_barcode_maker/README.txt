================================================================================
项目编号：034                    难度等级：★★☆☆☆（小型项目）
项目名称：条形码生成器
所属分类：安全与编码 / 图像生成
建议工时：3 ~ 5 小时
运行环境：Python 3.10+    第三方依赖：python-barcode、Pillow
================================================================================

【一、项目背景与目标】

开小店的要给商品打价签、做仓库的要给货架与货箱贴标签、做活动的要生成一批编号腕带——
这些场景都需要一维条形码。市面上不少在线条码生成站会打水印、限制分辨率，或者导出
的条码在热敏打印机上因为尺寸不足而扫不出来。更麻烦的是校验位算错：EAN-13、UPC-A、
EAN-8 都有校验位，手工算极易出错，导致整批标签作废。

本项目做一个本地条形码生成器：支持 EAN-13、EAN-8、UPC-A、Code128、Code39 五种常见
码制，自动补齐与校验校验位，支持批量导出（PNG/SVG/PDF），并能在生成前先验证编号的
合法性，避免浪费耗材。

目标用户是小型零售商、仓库管理员、活动组织者，以及需要在 Excel 里维护编号再批量出图
的文员。做成之后，从 CSV 到一叠可直接打印的条码标签只需一条命令。

【二、功能需求清单】

1. 核心功能
   1.1 单张生成：--barcode "6901234567892" --type ean13 --output out.png，
       输出图片并打印码制、原始数据、最终编码、校验位、模块数。
   1.2 校验位处理：对 ean13/ean8/upca，若输入长度为 N-1（12/7/11 位），
       自动计算并补上校验位，并在输出中说明"已自动补校验位 X"；
       若输入已含校验位则校验，校验错误时报错并给出正确值。
   1.3 多码制支持：ean13、ean8、upca、code128、code39、isbn13（作为 ean13 的别名）。
   1.4 批量导出：--batch items.csv --outdir out --format png|svg|pdf，
       CSV 列：data、type、name（可选）、text（可选，条码下方显示文字）。
   1.5 图片定制：--module-width 每模块像素宽（默认 2）、--module-height 条高像素
       （默认 60）、--quiet-zone 静区模块数（默认 6.5 由库决定，可覆盖）、
       --font-size 下方文字字号、--dpi 输出 DPI（默认 300，影响打印尺寸）。
   1.6 文本控制：--no-text 隐藏下方数字；--label "自定义说明" 在文字下方加一行说明。
   1.7 校验模式：--validate-only 只做合法性校验，不生成图片，便于批量预检。

2. 输入与交互
   2.1 入口：python cli.py --barcode <数据> --type <码制> [选项] 或 --batch <csv>。
       两者互斥，同时给出时报参数错误。
   2.2 --type 未指定时根据数据长度猜测：13 位数字 → ean13，12 位数字 → ean13（补校验），
       8 位或 7 位数字 → ean8，其余 → code128，并在输出中提示"已推断码制为 X"。
   2.3 --list-types 打印支持的码制、字符集限制与示例编号。
   2.4 --outdir 不存在时自动创建；批量模式下按 name 命名，缺省用序号 001、002。
   2.5 --strict 模式下，任何一条数据非法即整批中止且不写任何文件（先全量校验后统一渲染）。

3. 输出与展示
   3.1 单张模式输出：
       码制：EAN-13
       输入：690123456789
       完整编码：6901234567892（校验位 2）
       图片尺寸：190x92 像素（300 DPI 约 16.1x7.8 mm）
       已保存：C:\out\barcode.png
   3.2 批量模式输出汇总表：序号、name、data、type、图片尺寸、文件大小、状态、错误原因。
   3.3 PDF 模式：将所有条码按每页 4 列 × 12 行排布，A4 尺寸，每个条码下方渲染数字，
       页边距 10 mm，行间距 2 mm。使用 Pillow 的 Image.save(..., save_all=True, append_images=[...])
       生成多页 PDF。
   3.4 结束行：成功 N，失败 M，输出目录 <path>，总耗时 X.XX 秒。

4. 异常与边界处理
   4.1 数据为空：报"错误：条码数据不能为空"，退出码 1。
   4.2 EAN 系列含非数字字符：报"错误：EAN/UPC 码制只接受数字，收到 'ABC123'"，退出码 1。
   4.3 EAN-13 校验位错误：报"校验位错误：期望 2，实际 5"并给出修正后的完整编号，退出码 1。
   4.4 EAN-13 长度不是 12 或 13 位：报"错误：EAN-13 需要 12 或 13 位数字，收到 11 位"。
   4.5 Code39 含小写：按规范自动转大写并在 --verbose 下提示；
       Code39 含不支持的字符（如 @、#）时报错并列出支持的字符集。
   4.6 Code128 含非 ASCII 字符（如中文）：报错并提示"Code128 仅支持 ASCII，
       中文请改用二维码工具"，退出码 1。
   4.7 模块宽度过大导致图片超过 10000 像素：自动限制并警告，或在 --strict 下报错。
   4.8 PDF 模式在未安装对应支持时（Pillow 无法写多页 PDF）给出明确降级提示，
       改为逐张输出 PNG。
   4.9 批量 CSV 缺少 data 列：报错并列出实际列名，退出码 2。
   4.10 输出文件被占用（Windows 下 PermissionError）：重试 3 次（间隔 0.5 秒），
        仍失败则记录为失败并继续处理下一条。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：python-barcode（导入名 barcode，使用 barcode.get_barcode_class）、
   Pillow。其余使用标准库：argparse、csv、pathlib、re、dataclasses、time、sys、typing。
   安装：pip install python-barcode Pillow
3. 禁止事项：禁止自行手写 Code128 编码表（必须使用库提供的码制类，避免编码错误）；
   禁止在循环中重复创建 Writer 对象；禁止在批量模式因单条失败退出（--strict 除外）；
   禁止把生成结果上传到任何在线服务。
4. 代码组织：至少包含 codegen.py（码制选择、校验位计算、条码对象创建）、
   render.py（图片与 PDF 渲染）、batch.py（CSV 驱动与汇总）、cli.py。
   校验位函数签名固定为 calc_ean_check_digit(digits: str) -> int
   与 validate_ean(code: str) -> tuple[bool, str]。
5. 编码规范：类型注解与 docstring 齐全；CSV 以 newline="" 打开并指定 utf-8-sig
   以兼容 Excel 导出的带 BOM 文件；图片保存时显式传 dpi 元组；文件名清洗集中在
   一个 sanitize_filename() 函数中。

【四、设计要点】

1. 数据结构：
   - BarcodeSpec：data: str，symbology: str，full_code: str，check_digit: str | None，
     text: str | None，module_width: float，module_height: float，dpi: int。
   - BatchItem：index: int，name: str，data: str，symbology: str，
     output: Path | None，status: str，error: str。
   - SYMBOLOGY_MAP = {"ean13": EAN13, "ean8": EAN8, "upca": UPCA,
     "code128": CODE128, "code39": CODE39}（来自 barcode 包）。
   - SYMBOLOGY_RULES：每种的合法字符集正则、合法长度集合、是否需要校验位。
2. 关键算法或流程：
   2.1 EAN-13 校验位算法：对前 12 位，从右往左（不含校验位）奇数位权重 3、
       偶数位权重 1，求和后取 (10 - sum % 10) % 10。
       示例：690123456789 → 奇数位和与偶数位和加权后 sum=106，校验位 = 4，
       实现必须用单元测试覆盖 5 组已知样例。
   2.2 UPC-A 校验位算法：与 EAN-13 相同的加权规则，作用于前 11 位（奇数位权重 3）。
   2.3 EAN-8 校验位算法：对前 7 位，奇数位权重 3、偶数位权重 1（从左数）。
   2.4 渲染流程：
       (a) 由 SYMBOLOGY_MAP 取到类 cls；
       (b) obj = cls(data, writer=ImageWriter())（SVG 用 SVGWriter）；
       (c) options = {"module_width": mw, "module_height": mh, "dpi": dpi,
           "write_text": not no_text, "font_size": fs, "text_distance": 3.0,
           "quiet_zone": qz, "background": "white", "foreground": "black"}；
       (d) obj.save(str(target_without_ext), options)；注意库会自动追加扩展名，
           保存后需确认真实文件名并返回。
   2.5 PDF 排版算法：先把每个条码渲染为 PIL Image 并按统一高度缩放到单元格高度，
       再用 Image.new 创建 A4 画布（300 DPI 下 2480x3508 像素），
       用 paste 按 (col, row) 计算坐标逐个贴入，满页后新建下一页，
       最后 images[0].save(pdf_path, save_all=True, append_images=images[1:], resolution=dpi)。
   2.6 码制推断：按数字位数与是否纯数字决定，优先 EAN 系列，否则 Code128。
3. 接口或命令设计：
   python cli.py --barcode 690123456789 --type ean13 -o out.png
   python cli.py --barcode "ABC-1234" --type code128 --module-width 3
   python cli.py --batch items.csv --outdir out --format pdf --dpi 300
   python cli.py --barcode 6901234567895 --type ean13 --validate-only
   退出码：0 成功；1 数据非法或渲染失败；2 参数错误。

【五、运行方式与示例】

安装：
   pip install python-barcode Pillow
运行：
   python cli.py --barcode 690123456789 --type ean13 -o .\out\ean.png
   python cli.py --barcode "SHIP-2024-0001" --type code128 --module-width 3
   python cli.py --batch items.csv --outdir .\out --format pdf

items.csv 示例：
   name,data,type,text
   p001,690123456789,ean13,矿泉水 550ml
   p002,690123456796,ean13,纸巾
   box01,SHIP-2024-0001,code128,货箱 A

示例一（EAN-13 自动补校验位）：
   输入：python cli.py --barcode 690123456789 --type ean13 -o ean.png
   输出：
   码制：EAN-13
   输入：690123456789
   完整编码：6901234567892（校验位 2，已自动补全）
   图片尺寸：190x92 像素（300 DPI 约 16.1x7.8 mm）
   已保存：C:\out\ean.png

示例二（Code128 物流单号）：
   输入：python cli.py --barcode "SHIP-2024-0001" --type code128 --module-width 3 --dpi 300
   输出：
   码制：Code128
   完整编码：SHIP-2024-0001
   图片尺寸：417x104 像素（300 DPI 约 35.3x8.8 mm）
   已保存：barcode.png

示例三（批量出 PDF）：
   输入：python cli.py --batch items.csv --outdir .\out --format pdf
   输出：
   序号  name   data             type     尺寸        状态
   1     p001   6901234567892    ean13    190x92      成功
   2     p002   6901234567965    ean13    190x92      成功
   3     box01  SHIP-2024-0001   code128  417x104     成功
   已生成：C:\out\labels.pdf（3 个条码，1 页）
   成功 3，失败 0，总耗时 0.61 秒

示例四（异常输入）：
   输入：python cli.py --barcode 6901234567895 --type ean13
   输出：
   校验位错误：期望 2，实际 5
   修正后的完整编号：6901234567892
   退出码：1

【六、验收标准】

[ ] EAN-13 校验位算法对 690123456789 算出 2，对 400638133393 算出 1。
[ ] 输入 12 位数字时自动补全校验位，输出中明确说明补了哪一位。
[ ] 输入 13 位且校验位错误时给出期望值与修正编号，退出码为 1。
[ ] EAN-8 与 UPC-A 的校验位计算各通过至少 3 组已知样例。
[ ] Code128 数据含中文时报错并提示改用二维码工具。
[ ] Code39 输入小写字母时自动转大写且生成的条码可被扫码枪识别。
[ ] 生成的 EAN-13 图片用手机扫码 App 识别，结果与完整编码一致。
[ ] --no-text 生成的图片下方无数字，条码高度不变。
[ ] --dpi 300 输出的 PNG 元数据中 DPI 为 300。
[ ] --validate-only 不产生任何图片文件，且对非法数据返回退出码 1。
[ ] 批量模式中某条数据非法时其余条目仍生成，汇总表失败数正确。
[ ] --strict 模式下任一条非法则输出目录中没有任何新文件。
[ ] --format pdf 生成的 PDF 可打开，页面为 A4，每页不超过 48 个条码。
[ ] UTF-8 BOM 的 CSV 能被正确解析，首列名不带多余字符。
[ ] 输出文件被占用时程序重试后给出明确错误而不崩溃。

【七、可选扩展】

1. 增加 ITF-14、GS1-128（带应用标识符 AI）支持，适配物流与零售场景。
2. 增加 --sheet-template 自定义排版模板（JSON 描述列数、行数、间距、边距）。
3. 增加 Excel 输入（openpyxl 读取 xlsx），直接使用现有编号表。
4. 增加条码回读校验：用 pyzbar 或 opencv-python 解码生成的图片，自动确认可识别。

【八、涉及知识点】

- 一维条码的模块、静区、条高与扫码可靠性的关系
- EAN-13/EAN-8/UPC-A 校验位的加权取模算法
- Code128 与 Code39 的字符集差异与适用场景
- python-barcode 的 get_barcode_class 与 ImageWriter/SVGWriter
- Pillow 的多页 PDF 输出（save_all + append_images）与 DPI 元数据
- CSV 编码问题（utf-8-sig 处理 Excel BOM）
- 批量任务中的错误隔离与 --strict 全量预校验模式
================================================================================
