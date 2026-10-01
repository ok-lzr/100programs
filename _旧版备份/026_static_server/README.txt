================================================================================
项目编号：026                    难度等级：★★☆☆☆（小型项目）
项目名称：简易静态文件服务器
所属分类：网络与在线服务 / Web 服务基础
建议工时：5 ~ 8 小时
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】
小组内要临时分享一份几十 MB 的安装包、要给手机传几张照片、要在局域网里预览自己
刚生成的静态站点，用网盘要上传等待，用 python -m http.server 又太简陋：不能上传、
不支持断点续传、没有访问日志、目录里还暴露隐藏文件。本项目实现一个功能完整但仍
只依赖标准库的静态文件服务器。

目标用户是在局域网内做临时文件交换的开发者与运维。做出来之后，你在本机运行一条
命令，同事用浏览器打开 http://192.168.1.23:8000 就能看到目录列表、点击下载、用
拖拽上传文件，大文件下载中断后可以续传，服务器端还会把每次请求写进访问日志。

安全边界（必须遵守）：本工具面向可信局域网内的临时共享，默认只监听回环以外的
指定地址且必须显式提供 --bind 才能对外监听。必须实现目录穿越防护，禁止把服务器
根目录之上的任何文件暴露出去。默认不提供任何身份认证，因此严禁直接暴露到公网；
如需公网使用，必须自行加反向代理与认证，并在文档中明确提示风险。上传功能默认
关闭，需显式开启 --enable-upload，并限制允许上传的扩展名与单文件大小。

【二、功能需求清单】
1. 核心功能
   1.1 目录浏览：请求路径为目录时，返回 HTML 列表，包含文件（或子目录）名称、大小
       （人类可读单位）、修改时间；目录排在文件前面，各自按名称升序。列表顶部提供
       面包屑导航，每一级可点击；若存在上级目录则提供「返回上级」链接。
   1.2 文件下载：正确设置 Content-Type（用 mimetypes 推断，未知类型用
       application/octet-stream）、Content-Length、Last-Modified 与 ETag（由 mtime
       与 size 组成）。
   1.3 Range 断点续传：支持单区间 Range 请求（bytes=start-end、bytes=start-、
       bytes=-suffix），返回 206 与 Content-Range；不支持的区间或多区间请求返回 416
       并带 Content-Range: bytes */<total>。
   1.4 条件请求：支持 If-Modified-Since 与 If-None-Match，命中时返回 304 且无正文。
   1.5 上传：--enable-upload 开启后，POST /__upload 接收 multipart/form-data，把文件
       写入当前浏览目录；PUT /path/to/name 接收原始字节流直接写入。上传完成后返回
       201 与 JSON 结果（文件名、字节数、耗时）。同名文件默认拒绝（409），--overwrite
       允许覆盖。
   1.6 新建与删除：--enable-delete 开启后支持 DELETE /path 删除文件、--enable-mkdir
       开启后支持 POST /__mkdir 创建目录；两个开关默认关闭。
   1.7 访问日志：每个请求写一行 combined 风格日志到 stdout 与可选日志文件，字段为
       客户端 IP、时间（CLF 格式）、方法、路径、协议版本、状态码、响应字节数、耗时
       ms、User-Agent。
   1.8 优雅关闭：收到 Ctrl+C 后停止接受新连接，等待正在传输的连接完成（最长 10 秒）
       后退出，输出本次会话统计（请求数、传输总字节、错误数）。

2. 输入与交互
   2.1 命令形式：python server.py [--root DIR] [--bind ADDR] [--port PORT]
       [--enable-upload] [--max-upload-mb 200] [--log-file PATH]。
   2.2 --root 默认当前目录；--bind 默认 127.0.0.1，取值可为具体 IP 或 0.0.0.0（使用
       0.0.0.0 时打印风险提示并要求二次确认参数 --yes-i-know）。
   2.3 --port 默认 8000，范围 1024 ~ 65535，被占用时自动尝试后续端口，最多尝试 10 个。
   2.4 --max-upload-mb 默认 200，范围 1 ~ 4096；请求体超过上限时立即返回 413 并关闭
       连接，不读取剩余数据。
   2.5 --allow-ext 指定允许上传的扩展名白名单，默认为空表示不限制，但始终拒绝 .exe、
       .bat、.cmd、.ps1、.dll、.so 六类可执行扩展名。
   2.6 支持 --index index.html，请求目录时若该文件存在则直接返回它而不是目录列表。

3. 输出与展示
   3.1 启动时打印监听地址、根目录绝对路径、上传/删除/建目录开关状态与局域网访问
       示例地址（从本机网卡地址推断，给出至少一条形如
       http://192.168.1.23:8000 的提示）。
   3.2 目录页面为纯 HTML，内联少量 CSS，不使用外部资源与 JavaScript 框架；文件名
       做 HTML 转义，防止 XSS。
   3.3 错误页为简洁 HTML，包含状态码、原因短语与返回上级的链接；404、403、416、
       413、500 各有一份固定文案。
   3.4 日志中路径按 URL 解码后的原文记录，但控制字符要转义，避免日志注入。

4. 异常与边界处理
   4.1 目录穿越：对路径做 urllib.parse.unquote 后，用 os.path.normpath 规范化，再
       用 Path.resolve() 与根目录比较，若不在根目录之下返回 403；同时拒绝包含
       %2e%2e、..\\、绝对路径（如 C:\\ 或 /etc）的请求。
   4.2 符号链接指向根目录之外时返回 403（解析后用 is_relative_to 判断）。
   4.3 请求不存在的路径返回 404；请求不允许的方法（如未开启上传时的 POST）返回 405
       并在 Allow 头中列出支持的方法。
   4.4 客户端中途断开导致 BrokenPipeError 时，记录日志但不得让服务进程退出。
   4.5 文件在传输过程中被删除或修改，记录警告并尽量发送剩余内容，最终日志状态为
       200 但备注不完整传输。
   4.6 Range 起点大于文件大小时返回 416；Range 语法非法时忽略该头并按 200 返回完整
       文件（符合 RFC 7233 的容错要求）。
   4.7 上传的 multipart 解析失败（边界缺失、字段顺序异常）返回 400，并清理已写入的
       临时文件。
   4.8 磁盘写入失败（空间不足）返回 507 并删除半截文件。

【三、技术要求与约束】
1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库。核心为 http.server（BaseHTTPRequestHandler、
   ThreadingHTTPServer）、socketserver、urllib.parse、mimetypes、email.parser
   （解析 multipart）、pathlib、shutil、hashlib、json、argparse、logging、
   datetime。禁止使用 Flask、FastAPI 等 Web 框架。
3. 并发模型：使用 ThreadingHTTPServer（每连接一个线程），daemon_threads 设为 True；
   文件传输采用 64 KB 分块循环写入，禁止一次性把大文件读进内存；限制同时处理的请求
   数（--max-connections 默认 32），超出时返回 503 而不是无限创建线程。
4. 超时与重试：设置 socket 超时（默认 30 秒）用于读取请求体，传输大文件时按块重置
   超时；本服务不做重试（重试由客户端负责），但需正确处理客户端重试的 Range 请求。
5. 限速要求：--rate-limit 可按客户端 IP 限制每秒请求数（默认 20，范围 1 ~ 200），
   超出时返回 429 并带 Retry-After；上传接口单独限制每秒 2 次。
6. 合规要求：默认仅监听 127.0.0.1；对外监听需显式参数与风险确认；启动时打印
   「本服务不含身份认证，仅限可信局域网内临时使用，请勿暴露到公网」；日志中不记录
   请求体内容与任何敏感查询参数值。
7. 禁止事项：禁止实现目录穿越友好的路径拼接（必须逐个路径段校验）；禁止默认开启
   上传与删除；禁止执行上传的文件（服务器不做任何解释执行）；禁止把根目录设置为
   系统盘根目录（如 C:\\、/），检测到时拒绝启动。
8. 代码组织：handler.py（RequestHandler 与各 HTTP 方法）、fs.py（路径解析与安全
   校验、目录列表数据构造）、transfer.py（Range 解析与分块发送）、upload.py
   （multipart 与 PUT 上传）、logs.py（访问日志格式与统计）、cli.py（参数与启动）。
9. 编码规范：类型注解与 docstring 全覆盖；错误统一经 send_error_response 输出；
   日志用 logging 且格式固定；禁止在请求处理中 print 调试信息。

【四、设计要点】
1. 数据结构：
   FileEntry = {name, is_dir, size, mtime_iso, size_human, url_quoted}
   RangeSpec = {start, end, total, valid}，解析失败时 valid 为 False。
   ServerStats = {requests, bytes_sent, errors, uploads, started_at}
   log_request 的参数：client_ip, method, path, status, size, elapsed_ms, ua。
2. 关键算法或流程：
   2.1 请求处理主流程：解析路径 → 安全校验 → 若为目录则尝试 index 文件，否则生成
       目录列表 → 若为文件则处理条件请求（304 判定）→ 处理 Range → 分块发送 →
       写访问日志 → 更新统计。
   2.2 Range 解析：校验必须以 bytes= 开头；形如 a-b 取闭区间并检查 a<=b；形如 a-
       取 [a, total-1]；形如 -n 取最后 n 字节即 [total-n, total-1]；起点越界返回 416；
       语法异常返回无效并回退为完整响应。
   2.3 安全路径校验：unquote → 拒绝含空字节与反斜杠的输入 → 逐段拆分，遇到 .. 直接
       拒绝 → 拼接根目录 → resolve() → 用 Path.is_relative_to(root) 二次确认 →
       校验通过才继续。
   2.4 multipart 解析：按 Content-Type 的 boundary 切分请求体，遍历各 part 的头部
       与内容，取 name 为 file 的 part 写入目标路径；不依赖 cgi 模块（Python 3.13
       已移除），用 email.parser.BytesParser 构造 Message 后调用 iter_parts 处理。
   2.5 优雅关闭：注册 signal.SIGINT 处理器，置 shutdown 标志 → 调用 server.shutdown()
       → 等待 server.server_close() → 若有活跃传输则最多等待 10 秒 → 打印统计。
3. 接口或命令设计（HTTP 路由）：
   GET  /<path>               文件下载或目录列表，支持 Range 与条件请求
   HEAD /<path>               同 GET 但不返回正文
   POST /__upload             multipart 上传（需 --enable-upload）
   PUT  /<path>               原始字节流上传（需 --enable-upload）
   POST /__mkdir              创建目录（需 --enable-mkdir）
   DELETE /<path>             删除文件（需 --enable-delete）
   关键函数签名：
   def resolve_safe_path(root: Path, url_path: str) -> Path
   def parse_range(header: str, total: int) -> RangeSpec
   def send_file(handler, path: Path, range_spec: RangeSpec) -> int
   def handle_multipart_upload(handler, body: bytes, dest_dir: Path) -> tuple[str, int]

【五、运行方式与示例】
安装与运行（无需第三方依赖）：
   python server.py --root ./share --port 8000
   python server.py --root ./share --bind 192.168.1.23 --enable-upload --max-upload-mb 500
示例一（目录浏览与下载）：
   curl -s http://127.0.0.1:8000/
   返回 HTML 列表，包含 docs/ 目录与 report.pdf（37.4 MB, 2024-05-12 10:31）
   curl -I http://127.0.0.1:8000/report.pdf
   响应头：HTTP/1.1 200 OK / Content-Type: application/pdf /
          Content-Length: 39214567 / ETag: "1715484667-39214567"
   日志行：
   127.0.0.1 - - [12/May/2024:10:33:02 +0800] "GET /report.pdf HTTP/1.1" 200 39214567 8.4ms "curl/8.4.0"
示例二（断点续传与条件请求）：
   curl -r 1000000-1000099 -o part.bin http://127.0.0.1:8000/report.pdf
   响应：HTTP/1.1 206 Partial Content
        Content-Range: bytes 1000000-1000099/39214567
        Content-Length: 100
   curl -H 'If-None-Match: "1715484667-39214567"' -I http://127.0.0.1:8000/report.pdf
   响应：HTTP/1.1 304 Not Modified
示例三（上传与异常输入）：
   curl -F "file=@notes.txt" http://127.0.0.1:8000/__upload
   响应：HTTP/1.1 201 Created  {"name":"notes.txt","bytes":1024,"elapsed_ms":12}
   curl "http://127.0.0.1:8000/../../Windows/win.ini"
   响应：HTTP/1.1 403 Forbidden  （目录穿越请求被拒绝）
   curl -r 99999999- http://127.0.0.1:8000/report.pdf
   响应：HTTP/1.1 416 Range Not Satisfiable  Content-Range: bytes */39214567
   curl -X POST -F "file=@tool.exe" http://127.0.0.1:8000/__upload
   响应：HTTP/1.1 403 Forbidden  （可执行扩展名被拒绝）

【六、验收标准】
[ ] 浏览器打开根路径能看到目录列表，中文文件名正常显示不乱码。
[ ] 目录排在文件之前，且各自按名称升序。
[ ] 下载大文件时用 curl -r 请求局部区间返回 206，Content-Range 数值正确。
[ ] bytes=-100 请求返回最后 100 字节；bytes=0-0 返回 1 字节。
[ ] Range 起点超出文件大小时返回 416 且带 Content-Range: bytes */<total>。
[ ] 带正确 If-None-Match 的请求返回 304 且响应体为空。
[ ] 请求 /../../etc/passwd 或 /..%2f..%2fWindows/win.ini 返回 403。
[ ] 根目录设为 C:\\ 或 / 时程序拒绝启动并说明原因。
[ ] 未开启 --enable-upload 时 POST /__upload 返回 405 且 Allow 头不含 POST。
[ ] 上传成功返回 201，文件内容与源文件 sha256 一致。
[ ] 上传 .exe 文件被拒绝，返回 403。
[ ] 上传超过 --max-upload-mb 的文件返回 413 且未产生残留文件。
[ ] 同名文件存在且未加 --overwrite 时返回 409。
[ ] --bind 0.0.0.0 未加 --yes-i-know 时拒绝启动；加上后打印风险提示。
[ ] 访问日志每行包含客户端 IP、时间、方法、路径、状态码、字节数与耗时。
[ ] 并发 40 个下载请求时不超过 --max-connections 限制，超出部分收到 503。
[ ] 下载过程中客户端强制断开，服务进程继续存活并可继续处理新请求。
[ ] Ctrl+C 后打印本次会话的请求数与传输总字节数。
[ ] 源码中无 Flask/FastAPI 等框架 import，python -m py_compile 通过。
[ ] 目录页面中的特殊字符文件名被 HTML 转义（可用 <script>.txt 验证）。

【七、可选扩展】
1. 增加 HTTP Basic 认证（--auth user:pass，口令从环境变量读取，禁止硬编码），用于
   在受信网络中做最基本的访问控制。
2. 增加上传进度页面与断点续传上传（利用 Content-Range 头支持分片上传）。
3. 增加缩略图预览（仅用标准库生成极简 HTML 图片网格，不做图片处理）。
4. 增加带宽限制 --limit-kbps，用令牌桶控制单连接发送速率，便于弱网环境测试。

【八、涉及知识点】
- http.server 与 ThreadingHTTPServer 的请求处理模型
- HTTP 协议细节点：状态码语义、Range、ETag、Last-Modified、304/416/413
- multipart/form-data 的结构与解析
- 路径规范化与目录穿越防御
- 分块读写提高大文件传输的内存效率
- mimetypes 类型推断与 Content-Type 设置
- CLF 与 combined 访问日志格式
- 信号处理与优雅关闭
- 线程池/连接数上限与 429 限流
- HTML 转义防 XSS 与日志注入防护
================================================================================
