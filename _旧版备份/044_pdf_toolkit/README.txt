================================================================================
项目编号：044                    难度等级：★★★☆☆（小型项目）
项目名称：PDF 合并拆分工具
所属分类：命令行工具 / 文档处理
建议工时：5 ~ 7 小时
运行环境：Python 3.10+    第三方依赖：pypdf >= 4.0（pip install pypdf）
                         可选：reportlab（生成水印层）
================================================================================

【一、项目背景与目标】

PDF 是最难手工处理的办公文档：把十几份扫描件合成一本、把 200 页的合同拆成按章节的多个文件、
从大文档里抽出指定页码、把扫描歪了的页面旋转摆正、给对外版本盖上“内部资料”水印、给敏感文件
加一个打开口令——这些操作在收费软件里都是单独的功能模块，而用 Python 的 pypdf 大约两三百行
就能全部实现。

本项目的价值在于“批处理 + 可脚本化”：把每月流水账、投标文件、发票合集的整理工作写成命令，
配合系统的定时任务自动完成。另一个重点是安全：所有操作在本地完成，文档不会上传到任何在线
PDF 工具网站，这对财务、法务、医疗类文档是硬性要求。

目标用户是需要反复整理 PDF 的行政、财务、教师与学生。做成之后，一条命令就能把一学期的课件
按周拆分、给交付稿加水印、并给最终版加密，整个流程可复现、可记录。

【二、功能需求清单】

1. 核心功能
   1.1 合并（merge）：--merge a.pdf b.pdf c.pdf -o all.pdf，按命令行给出顺序拼接；支持
       --merge-dir 目录模式，按文件名自然排序（自然排序指 IMG2 排在 IMG10 前面，用
       正则按数字分段排序实现）。每份源文件可带页码范围，如 a.pdf:1-3。
   1.2 拆分（split）：--split 模式支持三种粒度，--mode each（每页一个文件）、
       --mode chunks --size 10（每 10 页一个文件）、--mode ranges --ranges 1-5,6-20,21-
       （按给定范围输出）。输出命名默认 原名_p0001-0010.pdf。
   1.3 抽页（extract）：--extract 1,3,5-8 从单个或多个输入文件抽取指定页，顺序按参数
       给出的顺序，支持重复页（同一页抽两次）。
   1.4 旋转（rotate）：--rotate 90|180|270，可用 --pages 限定范围；每页旋转量是累加的，
       并用 page.rotate(angle) 实现，不改变页面内容尺寸（自动处理 mediabox 交换）。
   1.5 水印（watermark）：--watermark stamp.pdf 用 PdfReader 读入单页水印 PDF，
       对每页执行 page.merge_page(stamp)，叠加到内容之上；--under 开关改为
       merge_transformed_page 或调整顺序实现“垫底”。支持 --pages 限定范围与
       --stamp-first-only 只给首页盖章。
   1.6 加密与解密：--encrypt 用 writer.encrypt(user_password=..., owner_password=...,
       algorithm="AES-256")；--decrypt 用 reader.decrypt(password) 后另存为无密码版本。
       口令来源优先级：命令行 > 环境变量 PDF_PASSWORD > getpass 交互输入，禁止在日志中打印。
   1.7 元数据：--set-title/--set-author/--set-subject/--set-keywords 写入文档信息；
       --strip-metadata 清空全部元数据（含 XMP）；--show-info 打印页数、页面尺寸、加密状态、
       是否线性化、PDF 版本。
   1.8 页面操作：--delete 删除指定页；--insert-after 3 other.pdf 在第 3 页后插入另一份文档；
       --reverse 逆序；--crop 100,100,500,700 设置裁剪框（cropbox）。

2. 输入与交互
   2.1 命令行：python pdf_toolkit.py merge a.pdf b.pdf -o out.pdf。
   2.2 子命令风格：第一位置参数为动作（merge/split/extract/rotate/watermark/encrypt/
       decrypt/info），其余为该动作专属参数，用 argparse 的 subparsers 实现。
   2.3 无参数运行时打印全部子命令与一句示例，退出码 0。
   2.4 --dry-run 打印将要执行的操作与影响页数，不写文件。

3. 输出与展示
   3.1 --info 输出示例：文件 a.pdf；页数 32；页面尺寸 595x842 pt (A4)；PDF 版本 1.7；
       加密 否；已签名 否。
   3.2 每个动作完成打印一行：合并 3 个文件共 96 页 -> out.pdf (2.4 MB, 1.3s)。
   3.3 --verbose 时逐页打印操作日志：第 12 页 旋转 90 度。
   3.4 --json 开关把 info 结果以 JSON 输出，便于脚本消费。

4. 异常与边界处理
   4.1 输入文件不是 PDF 或已损坏：捕获 pypdf.errors.PdfReadError，报告文件名与原因，
       批量模式下跳过并继续，最后汇总失败清单。
   4.2 加密 PDF 未提供口令：提示“文档已加密，请用 --password 或环境变量提供口令”，
       退出码 1；口令错误时明确区分“口令错误”与“操作不被允许”。
   4.3 页码越界（如只有 10 页却请求第 99 页）：报错并列出有效范围 1-10，退出码 1。
   4.4 页码范围语法非法（1-、-5、a-b）：给出中文语法说明与正确示例。
   4.5 输出文件已存在：默认拒绝并提示 --overwrite；--overwrite 时先写临时文件
       out.pdf.tmp，成功后 os.replace 原子替换。
   4.6 合并时页面尺寸不一致：允许合并，但打印提示“存在 3 种页面尺寸，已按原样保留”。
   4.7 输出为 0 页（如 --extract 全部不存在）：不生成文件并报错。
   4.8 水印 PDF 多于 1 页：只用第一页并打印提示。
   4.9 不允许对已数字签名的 PDF 做修改而不提示：检测到 /Sig 字段时打印警告。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：pypdf（PdfReader/PdfWriter/PageObject）；标准库 argparse、pathlib、re、
   getpass、os、json、logging、time、shutil。可选 reportlab 用于生成演示水印 PDF。
3. 禁止事项：禁止调用外部命令（pdftk、qpdf、gs）；禁止在代码或日志中硬编码/打印口令；
   禁止在未确认的情况下覆盖输入文件；禁止把全部页面一次性读入内存后不复用（大文件要分批）。
4. 代码组织：
   - page_range.py：parse_ranges("1-5,8,10-") -> list[int]（1 基，去重或保序按参数决定）、
     format_ranges(pages) -> str。
   - pdf_ops.py：merge_pdfs、split_pdf、extract_pages、rotate_pages、add_watermark、
     encrypt_pdf、decrypt_pdf、set_metadata、show_info，每个函数只做一件事。
   - naming.py：输出文件命名规则与冲突消解。
   - cli.py：subparsers 定义与动作分发。
   - 所有写文件的函数统一返回 Path 与实际页数，便于汇总与测试。
5. 编码规范：完整类型注解；涉及用户口令的变量名统一以 password 结尾且绝不写进日志，
   repr 时用 "***" 遮蔽（自定义 __repr__）；docstring 说明参数单位（页为 1 基、角度为
   顺时针度）；异常统一转成自定义 PdfToolError 后再在 CLI 层格式化为中文。

【四、设计要点】

1. 数据结构：
   PageRange：start(int)、end(int|None)，end 为 None 表示到文档末尾。
   OpResult：action(str)、inputs(list[Path])、output(Path|None)、pages_in(int)、
   pages_out(int)、bytes_out(int)、elapsed_ms(float)、warnings(list[str])。
   InfoDict：path、pages、page_sizes(list[tuple[float,float]])、pdf_version、encrypted、
   signed、metadata(dict)、linearized(bool)。

2. 关键算法或流程：
   2.1 范围解析：用正则 ^(\d+)(?:-(\d*))?$ 匹配每一段；"5" 解析为 5-5；"3-" 解析为 3 到
       max；"3-7" 校验 start <= end。输出统一转成 0 基索引集合，越界检查放在解析之后。
   2.2 合并流程：按顺序对每个输入 PdfReader；若是加密文档先 decrypt；逐个
       writer.add_page(page)；若某输入带 :1-3 后缀则只加对应页；最后
       writer.add_metadata({"/Title": ...}) 后写入。
   2.3 拆分流程：先 clone_document_from_reader 或对每段范围新建 PdfWriter 后
       add_page，避免共享对象导致交叉污染；每个输出文件独立 writer。
   2.4 水印流程：stamp_page = PdfReader(stamp).pages[0]；对目标页
       page.merge_page(stamp_page, over=True)；需要“垫底”时改为
       page.merge_transformed_page(stamp_page, Transformation(), over=False)。
       若水印页尺寸小于目标页，用 Transformation().scale(sx, sy) 铺满。
   2.5 加密流程：writer.encrypt(user_password=u, owner_password=o, algorithm="AES-256")；
       pypdf 的 algorithm 取值含 "RC4-40"、"AES-128"、"AES-256"；加密后校验一次能否用
       给定口令重新打开，避免写出打不开的文件。
   2.6 自然排序：key = [int(t) if t.isdigit() else t.lower() for t in
       re.split(r"(\d+)", name)]，保证 page2 排在 page10 之前。
   2.7 原子写入：先写到同目录的 <name>.tmp，flush + fsync 后 os.replace(tmp, final)。

3. 接口设计：
   python pdf_toolkit.py merge INPUT... [-o OUT] [--overwrite] [--dry-run]
   python pdf_toolkit.py merge-dir DIR [-o OUT] [--pattern '*.pdf']
   python pdf_toolkit.py split INPUT (--mode each|chunks|ranges) [--size N]
     [--ranges R] [--outdir DIR]
   python pdf_toolkit.py extract INPUT --pages R [--out-out OUT]
   python pdf_toolkit.py rotate INPUT --angle 90|180|270 [--pages R] [-o OUT]
   python pdf_toolkit.py watermark INPUT --stamp STAMP.pdf [--pages R] [--under] [-o OUT]
   python pdf_toolkit.py encrypt INPUT --password P [--owner-password P]
     [--algorithm AES-256] [-o OUT]
   python pdf_toolkit.py decrypt INPUT [--password P] [-o OUT]
   python pdf_toolkit.py info INPUT [--json]
   公共参数：--overwrite、--dry-run、--verbose、--log-file FILE、--no-signature-check。

【五、运行方式与示例】

1. 安装依赖：
   pip install "pypdf>=4.0"

2. 合并：
   python pdf_toolkit.py merge ch01.pdf ch02.pdf ch03.pdf -o book.pdf
   输出：合并 3 个文件共 96 页 -> book.pdf (2.4 MB, 1.3s)

3. 拆分每 20 页一份：
   python pdf_toolkit.py split big.pdf --mode chunks --size 20 --outdir parts
   输出：parts/big_p0001-0020.pdf (20 页)
         parts/big_p0021-0040.pdf (20 页)
         parts/big_p0041-0055.pdf (15 页)
         共 3 个文件，55 页

4. 抽页并旋转：
   python pdf_toolkit.py extract scan.pdf --pages 1,3,5-8 -o picked.pdf
   python pdf_toolkit.py rotate picked.pdf --angle 90 --pages 1-4 -o picked_fixed.pdf
   输出：第 1 页 旋转 90 度；... 共 4 页已旋转

5. 加密交付版：
   set PDF_PASSWORD=Deliver#2025
   python pdf_toolkit.py encrypt final.pdf --algorithm AES-256 -o final_secure.pdf
   输出：已用 AES-256 加密 -> final_secure.pdf（口令来源：环境变量 PDF_PASSWORD）

6. 异常示例：页码越界
   python pdf_toolkit.py extract a.pdf --pages 1,99
   输出：错误：第 99 页超出范围，文档 a.pdf 共 10 页，有效范围 1-10（退出码 1）

7. 异常示例：加密文档未给口令
   python pdf_toolkit.py info secret.pdf
   输出：文档已加密，请用 --password 或设置环境变量 PDF_PASSWORD（退出码 1）

【六、验收标准】

[ ] 合并 3 份共 96 页的 PDF 后，输出文档页数为 96，页码顺序与命令行一致。
[ ] 合并 20 份单页扫描件时自然排序生效，page2.pdf 排在 page10.pdf 之前。
[ ] --mode each 拆分 32 页文档得到 32 个文件，每个文件恰好 1 页且可独立打开。
[ ] --mode chunks --size 10 拆 32 页得到 4 个文件，页数依次为 10/10/10/2。
[ ] --extract 允许重复页，出 1,1,2 三页时输出页数为 3。
[ ] --rotate 90 后页面视觉方向改变，页面宽度与高度互换（用 mediabox 断言）。
[ ] 水印叠加后原文字仍清晰可读（over=True），用 --under 时水印被内容遮住。
[ ] AES-256 加密后的 PDF 用 Adobe Acrobat 或浏览器打开需要口令，输入正确口令可正常阅读。
[ ] 加解密往返后页数、页面尺寸与文本抽取结果与原文一致。
[ ] 命令行、环境变量、交互三种口令来源都可用，且 --verbose 日志中搜不到口令明文。
[ ] --strip-metadata 后用 info 查看 Title/Author 为空。
[ ] 输出文件已存在时默认不覆盖并返回退出码 1；加 --overwrite 后成功替换。
[ ] 处理一个损坏的 PDF 时批量任务继续，失败清单准确，退出码按是否全部失败决定。
[ ] 处理 500 页 / 50MB 的 PDF 时内存占用不超过 1GB，耗时在 30 秒内。
[ ] 所有写文件操作在中断后不留下半截的正式文件（只可能残留 .tmp）。

【七、可选扩展】

1. 增加文本抽取与全文搜索（page.extract_text()），支持 --grep 关键字输出命中页码。
2. 增加图片抽取（page.images），把 PDF 里的图片导出为 PNG。
3. 增加二维码骑缝章或时间戳水印，用 reportlab 动态生成水印页。
4. 增加页面拼接（N 页合一，类似讲义 2-up/4-up 排版），用 page.merge_transformed_page
   与 Transformation().scale/translate 实现。
5. 提供 PDF 批量压缩（Pillow 重压图片流），并输出压缩前后对比报告。

【八、涉及知识点】

- pypdf 的核心对象模型：PdfReader、PdfWriter、PageObject、Transformation、PageRange。
- PDF 页面盒模型：mediabox、cropbox、rotation 属性与坐标原点在左下角。
- 文档加密：RC4 与 AES 算法、user password 与 owner password 的权限差异。
- 元数据与 XMP、文档大纲（outline）、注释与表单域的读写。
- 页码范围解析的正则写法与 1 基/0 基索引转换的易错点。
- 原子写入模式（临时文件 + os.replace）与中断安全。
- argparse subparsers 组织多动作 CLI 与公共参数复用。
- 敏感信息处理：环境变量、getpass、日志脱敏与自定义 __repr__。
================================================================================
