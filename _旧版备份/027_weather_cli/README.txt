================================================================================
项目编号：027                    难度等级：★★☆☆☆（小型项目）
项目名称：天气查询命令行工具
所属分类：网络与在线服务 / 公开 API 调用
建议工时：3 ~ 5 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】
出门前想知道要不要带伞、跑步时想知道当前体感温度和风力，很多人会打开手机 App
看一堆广告和推送。本项目做一个纯命令行的天气查询工具，输入城市名即可打印实况与
未来几天的预报，包括温度、体感温度、湿度、风速风向、降水概率和紫外线指数。

目标用户是习惯在终端工作的开发者与学生。做出来之后，你可以把它写进 shell 别名，
一条 w 北京 就能看到今天的天气；也可以配合计划任务在每天早上输出一份简报。

数据来源选择 Open-Meteo（https://open-meteo.com），它的天气与地理编码接口无需
注册、无需 API Key，便于学习且不涉及密钥管理。使用前必须阅读并遵守该服务的使用
条款：免费额度面向非商业用途，请求需节制，禁止高频轮询与批量抓取，禁止把数据用
于商业分发。若改用其他天气服务，则必须通过环境变量提供密钥，禁止硬编码。

【二、功能需求清单】
1. 核心功能
   1.1 城市地理编码：调用 Open-Meteo 的 geocoding 接口，把城市名解析为经纬度、
       国家、行政区与时区；支持中文与英文城市名；返回多个候选时默认取第一条，并在
       输出中标注匹配到的完整地点名（如「北京市, 中国」）。
   1.2 实况天气：请求 current 字段，展示温度、体感温度、相对湿度、风速与风向（度
       数与八方位文字）、气压、云量、降水量、天气代码对应的中文描述。
   1.3 逐日预报：请求 daily 字段，展示未来 --days 天（默认 3，范围 1 ~ 7）的日期、
       天气描述、最高/最低温、降水概率、降水量、紫外线指数最大值、日出日落时间。
   1.4 逐时预报：--hourly N 展示未来 N 小时（默认 0 表示不展示，范围 0 ~ 24）的
       温度、降水概率与风速。
   1.5 单位与格式：--units metric（摄氏度、km/h、mm）或 imperial（华氏度、mph、
       inch）；--json 输出原始结构化数据；--lang zh 或 en 切换描述语言。
   1.6 多城市对比：一次传入多个城市名，各输出一段报告，并在末尾给出一个简表比较
       当前温度与降水概率。
   1.7 缓存：所有接口响应按「接口 + 参数」为键缓存到 ~/.weathercli/cache/ 下的
       JSON 文件，默认有效期 10 分钟（--cache-ttl 可调，0 表示不使用缓存）；
       缓存命中时在输出中标注（缓存，3 分钟前）。
   1.8 配置文件：位置参数可省略时从 ~/.weathercli/config.json 读取默认城市列表，
       文件不存在时提示如何创建，并支持 --save 把本次查询的城市写入默认列表。

2. 输入与交互
   2.1 命令形式：python weather.py CITY [CITY ...] [--days 3] [--hourly 0]
       [--units metric] [--json] [--lang zh] [--no-cache] [--cache-ttl 10]。
   2.2 未提供城市且无配置文件时报错退出码 2，并给出用法示例。
   2.3 --json 模式下不输出任何装饰性文本，只输出一个 JSON 对象，便于管道处理。
   2.4 所有网络请求统一超时（--timeout 默认 10 秒，范围 3 ~ 30）。

3. 输出与展示
   3.1 报告分段标题：【实况】、【未来 3 天】、【未来 12 小时】、【多城市对比】。
   3.2 实况段落逐行输出「字段名（左对齐 10）：值 单位」，温度保留 1 位小数。
   3.3 天气预报每行一个日期，格式：
       05-13  周一  中雨        18.2°C ~ 24.5°C  降水 80%  紫外线 3  日出 05:12 日落 19:03
   3.4 天气代码映射为中文短语（如 0 晴、1 晴间多云、3 阴、45 雾、61 小雨、63 中雨、
       65 大雨、71 小雪、80 阵雨、95 雷阵雨），未覆盖代码显示「未知天气（代码 N）」。
   3.5 当降水概率大于等于 50% 时，输出末尾追加一行提醒「建议携带雨具」。
   3.6 --json 输出结构固定包含 location、current、daily、hourly、fetched_at、source
       六个顶层字段。

4. 异常与边界处理
   4.1 城市解析不到结果时输出「未找到城市：xxx，请尝试更完整的名称或英文名」，退出
       码 3；多城市时单城市失败不阻断其他城市。
   4.2 网络超时或连接失败时重试 2 次（间隔 1 秒、2 秒），全部失败后若存在过期缓存
       则使用过期缓存并明确标注「使用过期缓存（< 时间 > 获取）」，否则退出码 4。
   4.3 接口返回的 JSON 缺少预期字段时记录警告并把该字段显示为「-」，不抛 KeyError。
   4.4 时区处理：接口返回的 timezone 用于把时间字段标注为当地时间，输出中注明
       「以下时间为当地时间」。
   4.5 --days 超过 7 时截断为 7 并提示；--days 0 报参数错误。
   4.6 缓存文件损坏时删除并按未命中处理，不中断程序。
   4.7 请求被限流（HTTP 429）时停止后续请求，提示稍后重试，退出码 5，不做重试。

【三、技术要求与约束】
1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库 urllib.request、urllib.parse、json、argparse、
   datetime、pathlib、hashlib、logging、time、statistics。若选择使用 requests，
   必须在依赖缺失时给出明确提示，并保持标准库实现可独立运行。
3. 网络与并发：本工具为交互式查询，请求量很小，采用串行请求即可；多城市场景使用
   ThreadPoolExecutor（最多 4 个 worker）并发查询，但必须串行处理同一个城市的
   地理编码与天气两步（后者依赖前者的经纬度）。
4. 超时与重试：单次请求超时默认 10 秒；失败重试 2 次，采用 1 秒与 2 秒的线性退避；
   429 与 4xx 不重试；重试总耗时上限 30 秒。
5. 限速要求：两次外部请求之间的最小间隔为 0.5 秒（含多城市情况下的全局节流）；
   单次运行的外部请求总数不超过 20 次；缓存有效期不小于 10 分钟，禁止在循环中
   反复刷新；不得实现自动轮询或后台定时抓取天气的功能。
6. 合规要求：遵守 Open-Meteo 的免费使用条款与署名要求，输出末尾固定打印数据来源
   一行「数据来源：Open-Meteo.com」；遵守目标服务的 robots.txt 与请求频率建议；
   禁止把本工具用于商业分发或大规模数据抓取。
7. 禁止事项：禁止硬编码任何 API Key；若接入需鉴权的服务，凭据必须从环境变量
   WEATHER_API_KEY 读取并在缺失时给出提示；禁止把用户查询的城市名上传到除天气
   服务之外的任何第三方；禁止在缓存中长期保存超过 24 小时的数据。
8. 代码组织：geocode.py（城市解析与候选处理）、api.py（请求封装、重试、缓存读写）、
   models.py（Location、CurrentWeather、DailyForecast、HourlyForecast 数据类）、
   render.py（文本与 JSON 渲染、天气代码映射）、cli.py（参数与主流程）。
9. 编码规范：类型注解与 docstring 全覆盖；时间统一使用带时区的 datetime；数值
   输出保留位数统一由 render 层负责；日志写 stderr，报告写 stdout。

【四、设计要点】
1. 数据结构：
   Location = {name, latitude, longitude, country, admin1, timezone, source_query}
   CurrentWeather = {time, temperature, apparent_temperature, humidity, wind_speed,
                     wind_direction, wind_dir_text, pressure, cloud_cover,
                     precipitation, weather_code, description}
   DailyForecast = {date, code, description, temp_max, temp_min, precip_probability,
                    precipitation_sum, uv_index_max, sunrise, sunset}
   HourlyForecast = {time, temperature, precip_probability, wind_speed}
   CacheRecord = {key, url, fetched_at, payload}
2. 关键算法或流程：
   2.1 查询主流程：读取参数与配置文件 → 对每个城市生成缓存键（城市名的小写 +
       单位 + 天数 + 时区的 sha256 前 16 位）→ 检查缓存是否在有效期内 → 命中则直接
       使用 → 未命中则先地理编码再请求天气 → 写缓存 → 交给渲染层输出。
   2.2 风向换算：把角度按 22.5 度为一段映射到八方位（北、东北、东、东南、南、
       西南、西、西北），边界值取向下取整后对 8 取模。
   2.3 天气代码映射：内置 WEATHER_CODES 字典覆盖 Open-Meteo 的 WMO 代码常用值，
       未命中时返回「未知天气（代码 N）」，并保证映射表与渲染逻辑分离便于扩展。
   2.4 缓存读写：缓存文件名为 key.json，写入时先写 .tmp 再 os.replace；读取时校验
       fetched_at 是否可解析，异常则视为未命中并删除文件。
   2.5 多城市并发：把所有城市任务提交线程池（最多 4 个）→ 用 as_completed 收集 →
       按输入顺序重排结果 → 单个城市失败只记录错误并在对应段落显示失败原因。
3. 接口或命令设计（外部 API）：
   GET https://geocoding-api.open-meteo.com/v1/search?name=<城市>&count=5&language=zh&format=json
   GET https://api.open-meteo.com/v1/forecast?latitude=<lat>&longitude=<lon>
       &current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,
       wind_direction_10m,surface_pressure,cloud_cover,precipitation,weather_code
       &daily=weather_code,temperature_2m_max,temperature_2m_min,
       precipitation_probability_max,precipitation_sum,uv_index_max,sunrise,sunset
       &hourly=temperature_2m,precipitation_probability,wind_speed_10m
       &timezone=auto&forecast_days=<days>
   关键函数签名：
   def geocode(city: str, lang: str, timeout: float) -> Location | None
   def fetch_weather(loc: Location, days: int, units: str, hourly: int) -> dict
   def read_cache(key: str, ttl_minutes: int) -> dict | None
   def write_cache(key: str, payload: dict) -> None
   def render_report(loc, current, daily, hourly, from_cache: bool) -> str

【五、运行方式与示例】
安装与运行（无需第三方依赖，无需 API Key）：
   python weather.py 北京
   python weather.py Shanghai --days 5 --units metric --hourly 12
示例一（单城市实况与预报）：
   【实况】北京市, 中国（当地时间 2024-05-12 10:31）
   天气      ：小雨
   温度      ：18.4 °C（体感 17.9 °C）
   湿度      ：72 %
   风速      ：12.6 km/h 东南风（135°）
   气压      ：1008.2 hPa
   降水      ：0.4 mm
   【未来 3 天】
   05-12  周日  小雨        16.8°C ~ 23.1°C  降水 70%  紫外线 4  日出 05:05 日落 19:20
   05-13  周一  阴          17.2°C ~ 24.5°C  降水 30%  紫外线 5  日出 05:04 日落 19:21
   05-14  周二  晴          18.0°C ~ 27.3°C  降水 10%  紫外线 7  日出 05:03 日落 19:22
   建议携带雨具
   数据来源：Open-Meteo.com
示例二（多城市对比）：
   python weather.py 北京 上海 广州
   输出三个城市的实况段落后追加：
   【多城市对比】
   北京    18.4 °C   降水 70%
   上海    21.2 °C   降水 40%
   广州    29.7 °C   降水 20%
示例三（异常输入与缓存）：
   python weather.py 不存在的城市名
   输出：未找到城市：不存在的城市名，请尝试更完整的名称或英文名
   退出码：3
   python weather.py 北京 --no-cache（断网状态，且无缓存）
   输出：错误：网络请求失败（超时），已重试 2 次
   退出码：4
   python weather.py 北京（有 25 分钟前的缓存且断网）
   输出：【实况】（使用过期缓存，25 分钟前获取）
   退出码：0

【六、验收标准】
[ ] python weather.py 北京 能输出实况与 3 天预报，地点显示为中文城市名。
[ ] python weather.py Beijing 与中文名查询返回相同的经纬度（允许 0.1 度误差）。
[ ] --days 7 输出 7 行预报；--days 10 截断为 7 并打印提示；--days 0 退出码 2。
[ ] 天气代码 61 显示为「小雨」，95 显示为「雷阵雨」，未覆盖代码显示未知天气加代码。
[ ] 温度、湿度、风速单位在 metric 与 imperial 下分别正确转换。
[ ] --json 输出可被 json.load 解析且包含 location/current/daily/hourly/fetched_at/source。
[ ] 10 分钟内重复执行同一查询时第二次命中缓存并标注缓存时间。
[ ] --no-cache 时每次都发起新请求（可用日志中的请求计数验证）。
[ ] 删除缓存目录后程序自动重建，不报错。
[ ] 手工把缓存文件写坏后再运行，程序删除坏文件并重新请求。
[ ] 断网且存在过期缓存时使用过期缓存并标注获取时间，退出码为 0。
[ ] 断网且无缓存时输出错误并退出码 4。
[ ] 输出末尾固定包含「数据来源：Open-Meteo.com」。
[ ] 多城市查询的外部请求总数不超过 20 次，且相邻请求间隔不小于 0.5 秒。
[ ] 任一城市查询失败时其他城市仍正常输出。
[ ] 源码中无硬编码 API Key，无自动轮询或定时抓取逻辑。

【七、可选扩展】
1. 增加 --compare-yesterday 参数，用 forecast 接口的 past_days 能力展示昨天同时刻
   温度对比。
2. 增加生活指数计算：基于温度、湿度、风速与紫外线，自行计算穿衣建议、是否需要
   防晒与是否适合户外运动（明确说明为估算规则而非官方指数）。
3. 增加 --alert 阈值参数，当预测温度低于或高于阈值时以非零退出码结束，便于脚本中
   做简单提醒。
4. 增加 ASCII 温度折线图，用等宽字符绘制未来 24 小时温度趋势。

【八、涉及知识点】
- urllib.request 发起 HTTPS GET、拼接查询参数与超时处理
- JSON 嵌套结构的解析与字段容错读取
- 本地缓存设计与 TTL 过期判定
- datetime 与时区处理
- 线性退避重试与错误分类（可重试/不可重试）
- argparse 参数范围校验与默认值
- 数据类建模与渲染层分离
- WMO 天气代码到自然语言的映射
- 公开 API 的使用条款、署名与限速要求
================================================================================
