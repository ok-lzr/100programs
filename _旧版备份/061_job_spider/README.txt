================================================================================
项目编号：061                    难度等级：★★★★☆（中型项目）
项目名称：招聘信息聚合分析器
所属分类：内容采集与数据分析 / 网络爬虫
建议工时：3 ~ 5 天
运行环境：Python 3.10+    第三方依赖：requests、beautifulsoup4、lxml、pandas、matplotlib、jieba
================================================================================

【一、项目背景与目标】

找工作的人普遍会遇到一个问题：同一类岗位在不同招聘网站上的薪资写法、技能要求、城市分布
全都不一样，靠着一个个网页翻，很难判断“我这个方向现在到底值多少钱”。本项目要做的是把公开
的招聘信息抓下来、清洗成统一结构，再用数据说话，输出一份可以自己看、也可以拿去讨论的分析报告。

目标用户是正在求职或准备跳槽的开发者、想了解某城市某岗位薪资水位的人、以及想练爬虫与数据
分析完整链路的 Python 学习者。项目做完之后，输入一个关键词加几个城市，就能得到：岗位数量排行、
薪资区间分布、经验与学历要求分布、高频技能关键词 TOP N、以及一张薪资对比柱状图。

必须强调合规边界：本项目仅抓取目标站点明确允许抓取的公开列表页与公开详情页，抓取前先读取并
遵守 robots.txt；请求间隔不得小于站点要求，本站默认每秒不超过 1 次并且不并发；不登录、不绕过
验证码、不采集任何个人联系方式；抓下来的数据只用于本地学习与统计研究，禁止用于商业倒卖、
二次分发或骚扰候选人。若站点 robots.txt 明确禁止抓取或用例超出学习范围，应停止抓取并只保留
已经获得的公开统计数据。

【二、功能需求清单】

1. 核心功能
   1.1 关键词抓取：输入关键词（如 “Python 后端”）、城市列表（如 北京,上海,深圳）、页数上限，
       输出该关键词在各城市的职位列表，每条包含标题、公司、城市、区域、薪资原文、经验要求、
       学历要求、技能标签、发布时间、来源 URL。
   1.2 翻页与去重：按列表页翻页抓取，遇到重复 URL 或重复（公司 + 标题 + 城市）三元组时跳过，
       去重后写入数据库，并记录“本次抓取、重复命中、新增入库”三个计数。
   1.3 薪资解析：把 “15k-25k·13薪”“8-12万/年”“面议”“200-300元/天” 等写法统一换算成
       月薪下限、月薪上限（单位：元/月）与年薪月数；无法解析的记为 None 并在报告中单独统计数量。
   1.4 城市维度统计：输出每个城市的岗位数量、薪资中位数、薪资四分位、平均经验年限要求。
   1.5 薪资分布统计：按月薪中位数分桶（0-8k、8-15k、15-25k、25-40k、40k 以上），
       输出每桶岗位数与占比，并绘制柱状图。
   1.6 技能关键词统计：用 jieba 对职位标题与技能标签做分词，配合自定义技术词典（如
       “Django”“MySQL”“微服务”“Kubernetes”）统计词频，输出 TOP 30 技能及出现岗位数占比。
   1.7 报告输出：生成 report.md（纯文本表格化排版）与 salary_by_city.png、
       salary_distribution.png、top_skills.png 三张图，图片 DPI 不低于 150。
2. 输入与交互
   2.1 命令行参数：--keyword 必填；--cities 逗号分隔，默认 北京,上海,深圳；--pages 默认 3，
       取值 1~20；--min-interval 默认 1.0 秒；--out 输出目录，默认 ./output。
   2.2 支持 --from-cache 参数，跳过网络请求，直接用本地数据库中的历史数据重新生成报告。
   2.3 抓取过程中每完成一页打印一行进度日志（页码、本页条数、累计条数、耗时）。
3. 输出与展示
   3.1 output/report.md：包含采集概览、城市排名、薪资分桶、技能 TOP 30、异常数据说明五节。
   3.2 output/jobs.csv：UTF-8 with BOM 编码，字段与数据库一致，方便直接用 Excel 打开。
   3.3 控制台结尾打印统计摘要，包括有效薪资样本数、无法解析薪资条数、总耗时。
4. 异常与边界处理
   4.1 robots.txt 禁止抓取目标路径时，直接终止该站点抓取并打印明确原因，不重试。
   4.2 单页请求失败重试 3 次，间隔按 2 秒、4 秒、8 秒指数退避；仍失败则跳过该页并计入失败页数。
   4.3 返回码 403/429 时立即停止该站点抓取，冷却 60 秒后不再继续，避免给站点造成压力。
   4.4 解析不到薪水的记录保留在库中但标记 salary_parsed = 0，不参与薪资统计。
   4.5 数据库文件损坏时提示备份路径并退出，不静默删除用户数据。
   4.6 关键词无结果时，报告仍正常生成，并写明“该关键词在指定城市无公开职位样本”。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上，使用类型注解与 dataclasses。
2. 允许使用的库：requests、beautifulsoup4、lxml、pandas、matplotlib、jieba，其余一律使用标准库
   （sqlite3、argparse、logging、re、time、random、pathlib、csv、urllib.robotparser）。
3. 禁止事项：禁止使用多线程/多进程并发抓取；禁止使用 Selenium 等真实浏览器绕过反爬；禁止
   硬编码任何账号、Cookie、Token；禁止把抓取数据上传到任何第三方服务。
4. 代码组织：至少拆分为 config.py（配置与常量）、fetcher.py（限速与重试）、parser.py（页面解析）、
   salary.py（薪资归一化）、storage.py（SQLite 读写）、analyzer.py（统计与绘图）、report.py
   （报告渲染）、main.py（命令行入口）；每个模块函数职责单一，单函数不超过 60 行。
5. 编码规范：全部公开函数写 docstring（说明参数、返回、异常）；使用 logging 记录而非 print；
   网络相关的魔法数字（超时、重试次数、间隔）集中在 config.py；`if __name__ == "__main__"` 保护入口。
6. 测试要求：salary.py 的解析函数必须有 pytest 单元测试，覆盖至少 8 种薪资写法与 3 种非法写法；
   解析类测试不得访问网络。

【四、设计要点】

1. 数据结构
   1.1 JobPosting（dataclass）：job_id(str，来源站点 + URL 哈希)、title(str)、company(str)、
       city(str)、district(str)、salary_raw(str)、salary_min(int|None)、salary_max(int|None)、
       months_per_year(int，默认 12)、experience(str)、education(str)、skills(list[str])、
       publish_date(str，ISO 格式)、source_url(str)、crawled_at(str)。
   1.2 表结构 jobs：主键 job_id，对 (company, title, city) 建唯一索引，对 city、publish_date 建普通索引；
       表 crawl_log：记录每次抓取的批次号、关键词、城市、页数、成功数、失败数、开始与结束时间。
2. 关键算法或流程
   2.1 抓取流程：读取 robots.txt → 校验目标 URL 是否允许 → sleep 随机抖动（min-interval 的 0.8~1.2 倍）
       → 请求 → 解析列表页 → 逐条解析详情或列表内联信息 → 去重 → 入库 → 打印进度。
   2.2 薪资解析规则（顺序匹配）：先处理“面议/薪资面议”返回 None；匹配 “(\d+)-(\d+)k” 得到月薪区间；
       匹配 “(\d+)-(\d+)万/年” 时先乘 10000 再除 12；匹配 “(\d+)元/天” 时乘 21.75 折算月薪；
       匹配单个 “(\d+)k” 时上下限相同；带 “·13薪” 时 months_per_year = 13；
       月薪下限超过月薪上限时交换两者；结果取整到元。
   2.3 统计流程：从 SQLite 读出 DataFrame → 过滤 salary_parsed = 1 → groupby 城市聚合 →
       用 pandas.cut 分桶 → jieba 分词统计 → 绘图 → 渲染 Markdown。
   2.4 词频口径：同一岗位内同一技能只计一次，统计“出现次数”与“覆盖岗位数”两个指标，
       报告中按覆盖岗位数降序排列，避免大公司批量岗位刷高词频。
3. 接口或命令设计
   3.1 命令行：
       python main.py --keyword "Python 后端" --cities 北京,上海 --pages 3 --min-interval 1.5
   3.2 关键函数签名：
       def can_fetch(url: str, user_agent: str) -> bool
       def fetch_list_page(url: str, retries: int = 3) -> str | None
       def parse_salary(raw: str) -> tuple[int | None, int | None, int]
       def save_jobs(jobs: list[JobPosting]) -> tuple[int, int]
       def build_report(frame: pandas.DataFrame, out_dir: Path) -> Path
   3.3 User-Agent 必须写明项目名称与学习用途，便于站点识别；不得伪装成主流浏览器。

【五、运行方式与示例】

安装依赖：
   pip install requests beautifulsoup4 lxml pandas matplotlib jieba

运行示例一（正常抓取）：
   python main.py --keyword "Python 后端" --cities 北京,上海 --pages 2 --min-interval 1.5
   输出：
   [INFO] robots.txt 校验通过：允许抓取 /list 路径
   [INFO] 第 1 页 北京 抓到 30 条，去重后新增 30 条，耗时 1.8s
   [INFO] 第 2 页 北京 抓到 30 条，去重后新增 28 条（重复 2），耗时 1.9s
   [INFO] 有效薪资样本 56 条，无法解析薪资 4 条
   [INFO] 报告已生成：output/report.md

运行示例二（离线重算）：
   python main.py --keyword "Python 后端" --from-cache --out ./output
   输出：直接读取本地 jobs.db，重新生成 report.md 与三张图，不发起任何网络请求。

运行示例三（薪资解析单测）：
   python -m pytest tests/test_salary.py -q
   输出：12 passed in 0.31s

异常示例：
   python main.py --keyword "Python 后端" --cities 北京 --pages 99
   输出：[ERROR] 参数错误：--pages 取值范围为 1~20，收到 99（退出码 2）

【六、验收标准】

[ ] 抓取前确实读取并校验了 robots.txt，被禁止时程序直接退出且不重试
[ ] 请求间隔不小于 --min-interval，日志中相邻请求时间差可验证
[ ] 数据库中不存在 (company, title, city) 完全重复的记录
[ ] parse_salary 对 “15k-25k·13薪” 返回 (15000, 25000, 13)
[ ] parse_salary 对 “面议” 返回 (None, None, 12) 且不抛异常
[ ] parse_salary 对 “8-12万/年” 折算月薪后落在 6000~11000 区间
[ ] report.md 包含采集概览、城市排名、薪资分桶、技能 TOP 30、异常说明五节
[ ] jobs.csv 用 Excel 打开中文不乱码（UTF-8 with BOM）
[ ] 三张 PNG 图片均生成且可打开，DPI 不低于 150
[ ] 同一关键词同一城市重复抓取时，报告中的岗位总数不出现翻倍
[ ] --from-cache 模式下抓包工具确认无任何网络请求
[ ] 数据库损坏时程序给出明确提示且不删除原文件
[ ] pytest 单测全部通过，且测试过程不访问网络
[ ] 日志中不出现任何真实账号、Cookie 或个人信息

【七、可选扩展】

1. 增加 --compare 参数，输出两次抓取之间的技能需求变化（新增技能、消失技能、占比升降）。
2. 增加公司维度统计：同一公司在招岗位数、平均薪资，输出公司招聘热度 TOP 20。
3. 把报告升级为本地 Flask 页面，支持按城市与薪资区间交互筛选，数据仍读本地 SQLite。
4. 增加经验年限解析（如 “3-5年”）与薪资的联合分布，绘制经验-薪资热力图。

【八、涉及知识点】

- HTTP 请求与请求头设置、响应编码识别、会话复用
- robots.txt 解析（urllib.robotparser）与爬虫合规边界
- 限速、指数退避重试、异常状态码处理
- HTML 解析（BeautifulSoup + lxml）与容错式选择器编写
- 正则表达式处理非结构化文本（薪资、年限、学历）
- SQLite 建表、唯一索引、幂等写入（INSERT OR IGNORE）
- pandas 分组聚合、分位数、cut 分桶
- jieba 中文分词与自定义词典
- matplotlib 中文乱码处理与柱状图绘制
- 命令行参数校验、日志分级、模块化拆分
================================================================================
