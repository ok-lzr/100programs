================================================================================
项目编号：025                    难度等级：★★☆☆☆（小型项目）
项目名称：批量 URL 状态检查器
所属分类：网络与在线服务 / 站点运维
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库；requests 为可选替换方案）
================================================================================

【一、项目背景与目标】
维护一个文档站或博客时，最头疼的是外链失效：文章里引用的工具官网换域名了、GitHub
仓库归档了、图片 404 了。一条条点开检查不现实，用浏览器插件又只能看当前页面。本
项目从一份 URL 清单出发，并发检查每个地址的状态码、重定向链和响应时间，产出一张
可直接照着修的报表。

目标用户是写技术文档、维护导航站、做 SEO 自查的开发者。做出来之后，把一个
urls.txt 丢给它，几分钟内就能拿到「哪些链接 404、哪些跳了三次、哪些慢到 3 秒」的
清单，并导出 CSV 归档。

爬取与请求的合规声明：本工具只对用户自己拥有、自己维护或已获得明确授权的 URL 做
检查；检查前会读取目标站点的 robots.txt，若目标路径被 Disallow 覆盖则默认跳过并在
报表中标记 skipped-by-robots。必须遵守目标站点的服务条款与访问频率限制，默认并发
不超过 8、单域名串行间隔不低于 0.5 秒，禁止把它当作压测或爬虫工具使用，禁止用于
探测他人站点的目录结构或漏洞。

【二、功能需求清单】
1. 核心功能
   1.1 输入来源：支持三种输入——命令行直接给出 URL、--file 指定文本文件（每行一个
       URL，允许以 # 开头的注释行与空行）、--stdin 从标准输入读取。
   1.2 请求方式：默认使用 HEAD 请求以节省流量；当 HEAD 返回 405、403、501 或连接
       异常时自动回退为 GET，并在结果中标注 method 字段。
   1.3 状态判定：2xx 记为 ok，3xx 记为 redirect，4xx 记为 client_error，
       5xx 记为 server_error，超时记为 timeout，DNS 失败记为 dns_error，其余记为
       error；每条给出 status_code 与 reason。
   1.4 重定向链：默认不自动跟随，手工逐跳跟随，最多 --max-redirects（默认 5）跳，
       记录每一跳的 (status, location) 序列与最终 URL；超过上限标记 too_many_redirects。
   1.5 响应时间：记录 DNS 解析耗时、连接耗时、首字节耗时（TTFB）与总耗时，四项
       均以毫秒为单位（urllib 下用 hook 分段计时，无法拆分时仅给出总耗时并在字段中
       标注 unavailable）。
   1.6 内容校验：--expect-status 可指定期望状态码集合（如 200,301），--expect-in
       指定响应正文中必须出现的字符串，用于检查页面是否真的可用而不是返回了错误页。
   1.7 robots.txt：--respect-robots 默认开启，按 scheme + host 缓存 robots.txt 解析
       结果（每个域名只请求一次），被禁止的 URL 不发送请求，结果标记 skipped。
   1.8 报表与导出：文本表格输出 + --csv PATH 导出明细 + --summary 打印统计摘要
       （总数、各状态数量、平均响应时间、最慢的 5 条、重定向最多的 5 条）。

2. 输入与交互
   2.1 命令形式：python urlcheck.py URL [URL ...] [--file FILE] [--workers 8]
       [--timeout 10] [--max-redirects 5] [--user-agent UA] [--csv out.csv]。
   2.2 --workers 默认 8，范围 1 ~ 16；--timeout 默认 10 秒，范围 1 ~ 60。
   2.3 --per-host-delay 单域名两次请求之间的最小间隔，默认 0.5 秒，范围 0 ~ 10。
   2.4 支持 --retry 参数，默认 1 次，仅对 timeout 与 5xx 生效，重试间隔 1 秒。
   2.5 --user-agent 默认形如 URLChecker/1.0 (+local educational tool)，禁止伪装成
       主流浏览器以规避防护。
   2.6 Ctrl+C 中断时输出已完成部分的结果与统计，退出码 130。

3. 输出与展示
   3.1 表格列：序号（右对齐 4）、状态（左对齐 14）、码（右对齐 4）、跳数（右对齐
       3）、耗时 ms（右对齐 8）、URL（左对齐，超长截断到 70 字符）。
   3.2 重定向详情在 --verbose 下逐跳打印，格式为「第 N 跳 301 -> https://...」。
   3.3 摘要段落包含：总数、ok 数、redirect 数、client_error 数、server_error 数、
       skipped 数、超时数、平均耗时、P95 耗时。
   3.4 失败项单独汇总在末尾「需要处理的链接」段落中，按状态分组。
   3.5 退出码约定：全部 ok 为 0，存在 4xx/5xx 为 1，存在 timeout/dns_error 为 2，
       参数错误为 3。

4. 异常与边界处理
   4.1 URL 缺少协议时自动补 https://，补全后仍无法解析出 host 则记为 invalid 并跳过。
   4.2 非 http/https 协议（ftp、file、javascript）直接标记 unsupported，不发请求。
   4.3 同一 URL 重复出现时只检查一次，报表中合并计数并注明重复次数。
   4.4 单域名并发被限制为 2，超出部分在同域名队列中等待，避免对同一站点造成压力。
   4.5 遇到 429 时尊重 Retry-After 头，若等待时间超过 60 秒则该 URL 标记
       rate_limited 并不再重试。
   4.6 响应正文只在 --expect-in 指定时才读取，且最多读取 512 KB，避免大文件下载。
   4.7 SSL 证书验证失败记为 ssl_error，并提示可能是自签证书；不提供跳过证书校验的
       默认选项，--insecure 需显式开启且在报表中注明风险。
   4.8 输出中的 URL 若含查询串参数，按 --mask-query 决定是否把敏感参数值替换为 ***。

【三、技术要求与约束】
1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库 urllib.request、http.client、ssl、socket、
   urllib.robotparser、concurrent.futures、queue、threading、time、csv、json、
   argparse、logging。若选择使用第三方 requests，必须先确认已安装，并在依赖缺失时
   给出清晰的安装提示，同时保留标准库实现路径。
3. 并发模型：使用 ThreadPoolExecutor 实现全局并发（--workers），并在其内部用「按
   域名」的锁与时间戳记录实现单域名串行与延迟控制；不允许为每个 URL 创建一个线程，
   也不允许用 asyncio 与线程池混用造成语义混乱，本版本统一用线程池。
4. 超时与重试：DNS 解析、连接、读取三段分别设置超时（urllib 通过自定义 opener 或
   socket 默认超时统一控制），整体不超过 --timeout；重试只针对超时与 5xx，最多
   --retry 次，禁止对 4xx 重试。
5. 限速要求：全局并发上限 16；单域名并发上限 2；单域名请求间隔不低于
   --per-host-delay（默认 0.5 秒）；单次运行总计请求数上限 2000，超出需分批执行。
6. 合规要求：默认遵守 robots.txt；默认使用标识自身用途的 User-Agent 并附上联系
   方式的说明性后缀；发现 429 或 503 时主动降速并停止该域名的后续请求；文档与
   --help 中均写明「仅用于检查自有或已授权链接，禁止用于压力测试、漏洞扫描或规避
   目标站点的访问控制」。
7. 禁止事项：禁止绕过 robots.txt 与访问控制；禁止并发爆破式重试；禁止把检查结果
   与目标站点数据上传到第三方；禁止在导出文件中保存响应正文原文（只保存命中结果
   的布尔值与片段长度）。
8. 代码组织：fetcher.py（HttpResult 与单次请求实现）、redirects.py（逐跳跟随）、
   robots.py（RobotsCache）、checker.py（批量调度与限速）、report.py（表格、摘要、
   CSV 导出）、cli.py（参数与入口）。
9. 编码规范：类型注解与 docstring 全覆盖；时间统计用 time.perf_counter；失败必须
   携带异常类型与消息；日志写 stderr，报表写 stdout；禁止裸 print 调试。

【四、设计要点】
1. 数据结构：
   UrlResult = {
       "url": str,              原始 URL
       "normalized_url": str,   补全协议并规范化后的 URL
       "status": str,           ok/redirect/client_error/server_error/timeout/
                                dns_error/ssl_error/invalid/unsupported/skipped/
                                rate_limited/too_many_redirects
       "status_code": int|None,
       "reason": str,
       "method": str,           HEAD 或 GET
       "redirect_chain": list[dict],  [{"status":301,"location":"..."}]
       "final_url": str|None,
       "elapsed_ms": float,
       "ttfb_ms": float|None,
       "duplicate_count": int,
       "note": str              robots 或被限速等说明
   }
   HostLimiter：{host: {"lock": Lock, "last_ts": float}}，用于单域名串行与延迟。
2. 关键算法或流程：
   2.1 批量调度：把去重后的 URL 列表提交线程池 → 每个任务先过 RobotsCache 检查 →
       通过后经 HostLimiter 等待该域名允许的时间点 → 发送请求 → 若为 3xx 且跳数未
       超限则解析 Location 并循环 → 汇总为 UrlResult → 主线程按完成顺序收集并渲染。
   2.2 单域名限速：acquire(host, delay)：加锁 → 计算 now 与 last_ts 的差值 → 不足
       delay 则 sleep 补足 → 更新 last_ts → 释放锁。锁只保护时间戳与等待计算，网络
       请求在锁外执行，保证同域名不会并发但不同域名可并行。
   2.3 重定向处理：不依赖 urllib 的自动跟随（构建不跟随重定向的 opener），手工取
       Location；相对路径用 urllib.parse.urljoin 拼接；检测到 A→B→A 的环时立即
       标记 redirect_loop 并停止。
   2.4 robots 判定：用 urllib.robotparser.RobotFileParser 抓取 /robots.txt，失败时
       按「允许」处理但记录 note；缓存以 scheme://host 为键；对 allow 判定使用
       完整的 path + query。
   2.5 摘要统计：对所有结果按 status 分组计数；耗时列表排序后取 P95（索引为
       int(len*0.95) 位置的值）；最慢 5 条按 elapsed_ms 降序取前 5。
3. 接口或命令设计：
   python urlcheck.py --file urls.txt --workers 8 --csv report.csv --verbose
   python urlcheck.py https://example.com/a https://example.com/b --expect-status 200
   关键函数签名：
   def check_one(url: str, cfg: CheckConfig) -> UrlResult
   def follow_redirects(url: str, cfg: CheckConfig) -> UrlResult
   def build_opener(no_redirect: bool, insecure: bool) -> urllib.request.OpenerDirector
   def render_table(results: list[UrlResult]) -> str
   def export_csv(results: list[UrlResult], path: str) -> int

【五、运行方式与示例】
安装与运行（默认仅用标准库）：
   python urlcheck.py --file urls.txt --workers 8
   pip install requests        可选，若希望用 requests 后端
示例一（正常检查）：
   urls.txt 内容：
   https://example.com
   https://example.com/not-exist-page
   https://httpbin.org/status/500
   运行输出：
      1  ok              200   0     412.5  https://example.com
      2  client_error    404   0     388.1  https://example.com/not-exist-page
      3  server_error    500   0     690.2  https://httpbin.org/status/500
   摘要：总数 3  ok 1  client_error 1  server_error 1  平均耗时 496.9 ms  P95 690.2 ms
   退出码：1
示例二（重定向链与 robots 跳过）：
   python urlcheck.py http://example.com http://example.com/admin --verbose
   输出：
      1  redirect        301   1     205.7  http://example.com
         第 1 跳 301 -> https://example.com/
      2  skipped        None   0       0.0  http://example.com/admin
         说明：被 robots.txt 的 Disallow 规则覆盖，已跳过
   退出码：0
示例三（异常输入）：
   python urlcheck.py "ht!tp://bad url"
   输出：错误：无法解析 URL（invalid），已跳过：ht!tp://bad url
   退出码：3
   python urlcheck.py https://nonexistent-host-xyz.invalid --timeout 5
   输出：
      1  dns_error    None   0    5003.1  https://nonexistent-host-xyz.invalid
   退出码：2

【六、验收标准】
[ ] --file 读取的注释行与空行被忽略，实际检查数量与有效行数一致。
[ ] HEAD 请求返回 405 时自动改用 GET，结果中的 method 字段为 GET。
[ ] 3xx 链接的 redirect_chain 记录了每一跳的状态码与 Location，最终 URL 正确。
[ ] 重定向超过 --max-redirects 时状态为 too_many_redirects。
[ ] A→B→A 的循环重定向被识别为 redirect_loop，且不会陷入死循环。
[ ] https://httpbin.org/status/500 被归类为 server_error 并触发 1 次重试。
[ ] 404 不触发重试（可通过日志中的请求计数验证）。
[ ] 同一 URL 重复出现 3 次时只发起 1 次请求，duplicate_count 显示为 3。
[ ] 单域名并发不超过 2，且相邻两次请求时间差不小于 --per-host-delay。
[ ] --workers 32 被拒绝或收敛到 16 并提示。
[ ] 目标 robots.txt 中 Disallow 的路径被标记为 skipped 且未发出请求。
[ ] 返回 429 且 Retry-After 为 120 时该 URL 标记 rate_limited 且不再重试。
[ ] --expect-in "登录" 在页面不含该词时该条结果为 client_error 或 note 中明确说明
    内容校验失败。
[ ] --csv 导出的文件包含 url、status、status_code、elapsed_ms、redirect_count 列。
[ ] --summary 输出的 P95 数值与手工排序计算一致。
[ ] 源码中不存在绕过 robots.txt 或禁用证书校验的默认路径。
[ ] python -m py_compile 通过，日志中不出现响应正文原文。

【七、可选扩展】
1. 增加并发健康检查模式：对同一 URL 用不同 User-Agent 与 Accept-Encoding 各请求
   一次，用于测试站点在不同客户端下的表现（仍受单域名限速约束）。
2. 增加书签文件（HTML 导出的浏览器书签）解析，自动提取其中的 URL 并批量检查。
3. 增加结果对比功能，与上一次运行的 CSV 对比，只输出新增的失效链接。
4. 增加邮件或 webhook 通知，把「需要处理的链接」段落推送到指定地址。

【八、涉及知识点】
- urllib.request 构建 opener、自定义 Handler 与禁止自动重定向
- HTTP 状态码语义与 HEAD/GET 差异
- urllib.robotparser 解析 robots.txt 与访问路径判定
- concurrent.futures 线程池与按域名限速的锁设计
- urllib.parse 的 urljoin、urlsplit 与查询串处理
- ssl 模块与证书验证失败的处理
- Retry-After 头与 429 限流的正确应对
- 统计口径：平均耗时、P95 与排序取值
- CSV 导出与报表可读性设计
- 网络请求的合规边界、限速与用户代理规范
================================================================================
