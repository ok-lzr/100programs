================================================================================
项目编号：068                    难度等级：★★★★☆（中型项目）
项目名称：PDF 发票与证书批量生成
所属分类：自动化与报表 / 文档批量生成
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：reportlab、openpyxl、jinja2、requests
================================================================================

【一、项目背景与目标】

培训机构要给 200 名学员发结业证书、小公司要给 30 个客户开对账单式发票、社团要给志愿者发服务
证明——这些文档内容大同小异，但每份的姓名、编号、金额、日期都不同。用 Word 手工改一百遍，
不仅慢，还一定会出现编号重复、金额和明细不一致、文件命名混乱的问题。

本项目做一套批量文档生成流水线：从 Excel 或 CSV 读取一份数据清单，校验必填字段与金额一致性，
按编号规则分配唯一编号，用模板渲染每份 PDF，按规则命名输出，可选地通过邮件分别发送给对应收件人，
并生成一份生成台账供核对。

目标用户是需要批量出证、出票、出证明的行政、教务、财务人员，以及想学习 PDF 生成与模板化文档
渲染的开发者。做成之后，输入一份 Excel 加一个模板配置，一条命令产出百份格式统一、编号连续的
PDF 文件；重复运行不会产生重复编号。

安全与合规要求：清单中可能包含真实姓名、手机号、金额等敏感个人信息，程序默认只在本机处理，
禁止把清单与生成的 PDF 上传到任何第三方服务或云端接口；日志中禁止打印完整姓名与手机号
（姓名只保留首字加星号，手机号只保留后 4 位）；邮件发送必须使用配置中显式列明的收件人，
并遵守邮箱服务商频率限制（默认每分钟不超过 20 封）；测试与演示必须使用伪造数据，
禁止把真实客户清单提交到公共仓库；所有邮箱凭据通过环境变量或本地未提交的 config.ini 提供。

【二、功能需求清单】

1. 核心功能
   1.1 数据读取：从 xlsx 或 csv 读取生成清单，支持 --sheet 指定工作表、--header-row 指定表头行；
       每行代表一份文档，字段由模板配置声明（如 name、id_card_tail、course、amount、date、email）。
   1.2 字段校验：按模板配置的 required 列表检查必填字段；校验日期格式、金额为数字且非负、
       邮箱格式；校验失败的行不生成文档并汇总到错误报告 errors.md，其他行继续处理。
   1.3 编号规则：支持 prefix + 年份 + 流水号（如 CERT-2024-0001）与纯流水号两种；
       流水号位数可配置（默认 4 位，超出自动加宽）；起始序号可配置；编号在生成台账中唯一。
   1.4 幂等生成：以“业务键”（默认 name + 日期 + 模板名）判断该份文档是否已生成过，
       默认跳过已生成的并输出“已存在”状态，--regenerate 可强制覆盖重新生成。
   1.5 模板渲染：用 jinja2 渲染文本内容，再把渲染结果交给 reportlab 排版；
       支持正文段落、明细列表（表格）、签章区（姓名与日期的下划线区）、页脚编号与二维码占位。
   1.6 中文排版：使用 reportlab 内置 CID 字体 STSong-Light（无需额外字体文件）；
       若配置了 ttf_font_path 则注册并优先使用该字体；字体缺失时给出明确错误而不是输出乱码文档。
   1.7 表格与金额：支持明细表格渲染（列宽按配置比例分配，表头底色可配），金额列右对齐并保留
       两位小数，大写金额（人民币）自动生成，小写与大写不一致时校验失败。
   1.8 批量导出：输出到 output/pdf/<批次号>/ 目录，文件名模板如
       {编号}_{姓名}_{文档类型}.pdf；同时生成 manifest.csv（编号、姓名脱敏、文件名、页数、生成时间、状态）。
   1.9 邮件发送（可选）：若清单行含 email 字段且启用 --send-mail，则把该行生成的 PDF 作为附件
       单独发送；发送失败重试 2 次（5 秒、30 秒），失败记录到 manifest.csv 并在批次汇总中报告。
   1.10 合并导出：--merge 参数把本批次所有 PDF 用 pypdf 合并为一个总文件（可选依赖），
       并插入封面页（批次号、文档数量、生成时间）。
2. 输入与交互
   2.1 命令行：--data 数据文件；--template 模板配置 JSON；--sheet 工作表名；--out 输出目录；
       --batch 批次号（默认日期时间）；--limit 只处理前 N 行（调试用）；--dry-run 只校验不生成；
       --regenerate；--send-mail；--merge。
   2.2 模板配置文件 template.json 描述字段、编号规则、正文结构块与样式，不改代码即可调整版式。
   2.3 支持 --only 编号列表（逗号分隔）只重新生成指定编号的文档。
3. 输出与展示
   3.1 output/pdf/<批次号>/*.pdf：生成的文档。
   3.2 output/pdf/<批次号>/manifest.csv：生成台账（UTF-8 with BOM）。
   3.3 output/errors.md：校验与生成失败清单，含行号、字段名与原因。
   3.4 控制台汇总：总行数、成功数、跳过数、失败数、总页数、耗时、批次号。
4. 异常与边界处理
   4.1 数据文件不存在或工作表中无数据行时，直接报错退出（退出码 2），不生成空目录。
   4.2 模板配置缺少必填键（如 number_rule）时校验阶段报错并指明字段名。
   4.3 单份文档渲染异常（如模板变量类型不支持）时捕获该行异常，记录 errors.md 后继续下一行，
       最终若失败率超过 20% 则整体退出码为 7，提醒人工介入。
   4.4 编号冲突（台账中已存在同一编号但业务键不同）时拒绝生成并记录冲突详情，避免一证两用。
   4.5 输出目录已存在同名文件且未加 --regenerate 时跳过，不覆盖用户已有文件。
   4.6 邮件附件超过 5 MB 时给出警告；超过 10 MB 时该行不发送并记录原因。
   4.7 磁盘写入失败（空间不足或权限不足）时立即停止批次并保留已生成的文件与台账。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用类型注解与 dataclass。
2. 允许使用的库：reportlab、openpyxl、jinja2、requests，可选 pypdf（合并 PDF）；
   其余使用标准库（smtplib、email.message、csv、json、sqlite3、argparse、logging、datetime、
   pathlib、re、decimal、os、time）。
3. 禁止事项：禁止硬编码邮箱口令；禁止把数据清单或生成的 PDF 上传到任何云服务；
   禁止在日志中打印完整姓名、手机号、身份证号与金额明细；禁止生成不含业务依据的空白证书；
   禁止在测试中使用真实客户数据。
4. 代码组织：config.py（模板配置加载与校验）、models.py（DocumentRecord、GenResult、
   NumberRule）、datasource.py（Excel/CSV 读取）、validator.py（字段与金额校验）、
   numbering.py（编号分配与冲突检测）、renderer.py（jinja2 渲染）、pdf_writer.py（reportlab 排版）、
   ledger.py（SQLite 台账与 manifest 输出）、mailer.py（可选邮件发送）、cli.py。
5. 编码规范：金额一律使用 decimal.Decimal 计算，禁止用 float 做金额求和；
   所有公开函数写 docstring；中文金额大写转换需单独函数并附单元测试；
   文件命名不得包含 Windows 非法字符（\ / : * ? " < > |），生成前必须做替换；
   日志中对个人信息做脱敏（姓名首字 + 星号，手机号后 4 位）。
6. 测试要求：numbering.py 的编号连续性与冲突检测、validator.py 的金额校验、
   大写金额转换、文件名非法字符清理四部分需有 pytest 用例；
   PDF 生成测试使用 3 行伪造数据，断言输出的文件存在且能被 reportlab/pypdf 读回页数；
   不得在测试中真实发送邮件。

【四、设计要点】

1. 数据结构
   1.1 DocumentRecord：row_index(int)、biz_key(str)、name(str)、fields(dict[str, str])、
       amount(Decimal|None)、doc_date(date)、email(str|None)、number(str|None)。
   1.2 NumberRule：prefix(str)、use_year(bool)、digits(int，默认 4)、start(int，默认 1)、
       separator(str，默认 "-")。
   1.3 GenResult：number(str)、file_name(str)、path(str)、pages(int)、status(str，
       generated/skipped/failed)、error(str|None)、generated_at(str)、mail_sent(bool)。
   1.4 台账表 documents：主键数号 number，唯一索引 (biz_key, template_id)，
       字段包含 biz_key、name_masked、file_name、pages、batch_id、status、generated_at；
       表 batches：batch_id、template_id、total、success、skipped、failed、started_at、finished_at。
   1.5 模板配置片段：
       {"template_id": "cert_v1", "title": "结业证书",
        "fields": ["name", "course", "date", "amount"],
        "required": ["name", "course", "date"],
        "number_rule": {"prefix": "CERT", "use_year": true, "digits": 4, "start": 1},
        "filename": "{number}_{name}_{title}.pdf",
        "blocks": [{"kind": "paragraph", "text": "兹证明 {{ name }} 已完成 {{ course }} 课程学习。"},
                   {"kind": "table", "columns": ["项目", "金额"], "rows": [["培训费", "{{ amount }}"]]},
                   {"kind": "signature", "name": "{{ name }}", "date": "{{ date }}"}]}
2. 关键算法或流程
   2.1 主流程：加载并校验模板配置 → 读取数据 → 逐行校验 → 分配编号（查台账去重）→
       渲染文本内容 → reportlab 排版输出 PDF → 记录 manifest 与台账 → 可选发送邮件 → 汇总统计。
   2.2 编号分配：查询台账中该 template_id 与 prefix 的最大序号 → 序号 = max(起始序号, 最大序号 + 1)
       → 逐行递增 → 格式化 f"{prefix}-{year}-{seq:0{digits}d}"；同一批次内先全部分配再统一写入，
       避免中途失败造成断号（断号情况在台账中标注 skipped 行）。
   2.3 金额大写转换：按人民币规则处理，整数部分以四位分组（万、亿），逐组转换“零壹贰叁肆伍陆柒捌玖”
       与“拾佰仟”，处理连续零只保留一个“零”、末尾零省略、整数部分为 0 时取“零元”，
       角分为零时写“整”；转换后的小写与大写需在报告中同时给出以便核对。
   2.4 PDF 排版：使用 reportlab 的 platypus（SimpleDocTemplate + Paragraph + Table + Spacer）；
       页面 A4，四边距 2.5 厘米；正文行距 18；表格列宽按配置比例乘以可用宽度；
       页脚显示编号与页码（onPage 回调中绘制）。
   2.5 幂等判定：biz_key = sha256(template_id + name + doc_date) 的前 16 位；
       台账中存在相同 biz_key 且 status 为 generated 时跳过，除非 --regenerate。
3. 接口或命令设计
   3.1 命令行：
       python main.py --data 学员名单.xlsx --template cert.json --out ./output --limit 10
       python main.py --data 客户账单.csv --template invoice.json --send-mail --merge
       python main.py --data 学员名单.xlsx --template cert.json --only CERT-2024-0003,CERT-2024-0005 --regenerate
   3.2 关键函数签名：
       def load_records(path: Path, sheet: str | None, header_row: int, fields: list[str]) -> list[DocumentRecord]
       def validate_record(rec: DocumentRecord, spec: TemplateSpec) -> list[str]
       def next_numbers(rule: NumberRule, count: int, ledger: Ledger) -> list[str]
       def render_blocks(spec: TemplateSpec, rec: DocumentRecord) -> list[dict]
       def build_pdf(blocks: list[dict], out_path: Path, spec: TemplateSpec) -> int
       def amount_to_chinese(amount: Decimal) -> str
   3.3 邮件正文固定包含：文档名称、编号、收件人称呼、一句说明与附件；附件名为生成的 PDF 文件名。

【五、运行方式与示例】

安装依赖：
   pip install reportlab openpyxl jinja2 pypdf requests

数据示例（学员名单.xlsx）：
   姓名 | 课程 | 结业日期 | 金额 | 邮箱
   张三 | Python 基础 | 2024-05-18 | 1980.00 | zhangsan@example.com
   李四 | Python 基础 | 2024-05-18 | 1980.00 | lisi@example.com

运行示例一（试运行校验）：
   python main.py --data 学员名单.xlsx --template cert.json --dry-run
   输出：
   [INFO] 读取 2 行，字段映射完成：name, course, date, amount
   [INFO] 校验通过 2 行，失败 0 行
   [INFO] 试运行：未生成文件，编号预览 CERT-2024-0001 ~ CERT-2024-0002

运行示例二（批量生成）：
   python main.py --data 学员名单.xlsx --template cert.json --out ./output
   输出：
   [INFO] 批次号 20240520-0930-7c21
   [INFO] 编号分配：CERT-2024-0001、CERT-2024-0002
   [INFO] 已生成 CERT-2024-0001_张三_结业证书.pdf（1 页）
   [INFO] 已生成 CERT-2024-0002_李四_结业证书.pdf（1 页）
   [INFO] 汇总：总数 2，成功 2，跳过 0，失败 0，总页数 2，耗时 1.6s
   [INFO] 台账：output/pdf/20240520-0930-7c21/manifest.csv

运行示例三（重复运行 + 邮件发送）：
   python main.py --data 学员名单.xlsx --template cert.json --out ./output --send-mail
   输出：
   [INFO] CERT-2024-0001 已存在（业务键命中），跳过
   [INFO] CERT-2024-0002 已存在，跳过
   [INFO] 邮件发送：成功 0 封，跳过 2 封（文档未重新生成），失败 0 封

异常示例：
   python main.py --data 客户账单.csv --template invoice.json --dry-run
   输出（金额大小写不一致）：
   [ERROR] 第 4 行校验失败：amount_small 1280.00 与 amount_large 壹仟贰佰捌拾元整 不一致
   [ERROR] 失败 1 行，errors.md 已生成（退出码 7，失败率 25% 超过阈值）

【六、验收标准】

[ ] 输出目录中确实生成与有效数据行数相同的 PDF 文件，文件名符合配置模板
[ ] 打开 PDF 中文显示正常，无方框乱码（使用 STSong-Light 或配置的 TTF 字体）
[ ] 编号连续且格式为 CERT-2024-0001 形式，位数不足时前补零
[ ] 同一数据重复运行时不产生重复编号，默认跳过已生成的文档
[ ] --regenerate 时覆盖原文件且台账记录新生成时间
[ ] 编号冲突（同编号不同业务键）时拒绝生成并写入 errors.md
[ ] 必填字段缺失的行不生成 PDF 且被计入 failures
[ ] 金额使用 Decimal 计算，100 份文档金额求和与 Excel 手工求和完全一致
[ ] 大写到金额转换对 0.00、10.05、1001.10、20000.00 四个样例均正确
[ ] PDF 页脚包含编号与页码，页码从 1 开始
[ ] manifest.csv 中的编号、文件名、状态与实际输出文件一一对应
[ ] --dry-run 时不产生任何 PDF 文件
[ ] 日志与 manifest 中姓名与手机号已脱敏
[ ] 邮件发送失败按 5 秒、30 秒重试两次并记录到 manifest
[ ] 文件名中的非法字符被替换，Windows 下可正常创建
[ ] --merge 生成的总文件页数等于各单份页数之和加封面 1 页
[ ] 磁盘或权限错误时程序明确报错且已生成文件不被删除

【七、可选扩展】

1. 增加二维码：用 qrcode 库在证书右下角生成校验二维码，扫码后显示编号与校验入口。
2. 增加 PDF 加密：用 pypdf 为含敏感信息的文档设置口令与权限位。
3. 增加模板版本管理：同一模板保留多个版本，台账记录使用的模板版本号以便追溯。
4. 增加批量盖章图片叠加：把透明 PNG 印章按配置坐标叠加到每页指定位置。

【八、涉及知识点】

- reportlab platypus 文档构建：Paragraph、Table、Spacer、PageTemplate 与 onPage 回调
- reportlab 中文 CID 字体（STSong-Light）与 TTF 字体注册
- jinja2 在非 HTML 场景下的文本模板渲染
- decimal.Decimal 金额精确计算与人民币大写转换算法
- Excel/CSV 数据读取与行级错误隔离
- 编号分配、唯一性约束与断号处理
- 幂等设计：业务键哈希与台账判重
- SQLite 台账与 CSV 清单输出
- smtplib 发送带附件邮件与失败重试
- 个人信息脱敏、文件命名安全与本地化处理原则
================================================================================
