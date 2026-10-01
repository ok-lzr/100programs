================================================================================
项目编号：049                    难度等级：★★★☆☆（小型项目）
项目名称：Markdown 实时预览服务器
所属分类：本地 Web 工具 / 文档工具
建议工时：5 ~ 7 小时
运行环境：Python 3.10+    第三方依赖：markdown >= 3.5（pip install markdown）
                         可选：pygments（代码高亮，markdown 的 codehilite 扩展需要）
================================================================================

【一、项目背景与目标】

写 Markdown 的人都有一个共同的痛点：编辑器里看到的是源码，最后排版长什么样只能靠脑补，或者
另开一个重编辑器去看。用 VS Code 有内置预览，但如果文件在远程服务器、在 WSL 里、或者只想用
记事本编辑，就没有顺手的预览方式了。而且很多编辑器预览不支持自定义 CSS，看表格和代码块效果
一般。

本项目做一个极简的本地预览服务器：启动后打开浏览器访问 http://127.0.0.1:8000，浏览器里显示
当前 Markdown 文件渲染后的 HTML，文件内容一变浏览器自动刷新并尽量保持滚动位置。支持多文件
列表、目录浏览、Mermaid 代码块原样保留（前端可选加载脚本渲染）、自定义 CSS 主题、代码块
语法高亮、目录（TOC）侧栏与深色模式。

技术上刻意做成“零额外前端构建”：不需要 Node.js、不需要打包工具，Python 标准库
http.server 起服务，markdown 库做渲染，前端用一个 200 行的 HTML 模板加少量原生 JS 轮询文件
版本号实现自动刷新。目标用户是开发者、技术写作者与需要给同事看文档的人。做成之后可以把它
挂在本地长期运行，编辑任意 Markdown 文件都能秒级看到排版效果。

【二、功能需求清单】

1. 核心功能
   1.1 渲染：用 markdown.Markdown(extensions=[...]) 渲染，默认启用
       extra（含 tables、fenced_code、attr_list）、toc、sane_lists、nl2br、codehilite
       （若 pygments 不可用则自动去掉该扩展并提示）；--no-extra 可精简扩展列表。
   1.2 服务与路由：http.server.ThreadingHTTPServer + BaseHTTPRequestHandler 子类。
       路由包括：GET / 渲染入口文件；GET /view?file=相对路径 渲染指定文件；
       GET /list 返回 JSON 文件树；GET /raw?file=... 返回原始 Markdown 文本；
       GET /version?file=... 返回该文件的 mtime 与大小（供前端轮询）；
       GET /static/* 提供内置 CSS/JS；GET /assets/* 提供文件同目录下的图片资源。
   1.3 自动刷新：前端每 --poll-ms（默认 800）毫秒请求 /version，发现 mtime 或大小变化时
       用 fetch 拉取 /fragment?file=... 更新正文节点（局部刷新），并记住并恢复
       scrollTop 与滚动锚点（用标题 id 定位）。
   1.4 目录导航：GET /list 递归扫描 --root 下的 *.md/*.markdown，返回
       [{path, name, mtime, size, dir}]，前端侧栏点击即切换预览。
   1.5 目录（TOC）：用 toc 扩展生成，[TOC] 标记或自动生成侧栏；标题生成
       永久链接锚点，点击可复制 URL 片段。
   1.6 安全与访问控制：只服务 --root 目录下的文件；每次请求都对解析后的真实路径做
       Path.resolve().is_relative_to(root.resolve()) 校验，禁止 ../ 逃逸与符号链接跳出；
       拒绝 .env、.git 等敏感路径（可配置 --deny 模式）；--token 开启后所有请求需带
       ?token=xxx 或 Cookie，防止同机其他用户或浏览器页面探测。
   1.7 自定义外观：--css 自定义 CSS 文件路径（覆盖内置样式）；内置 light/dark/auto 三套
       主题；--highlight auto|github|monokai 选择代码高亮风格。
   1.8 导出与辅助：GET /export?file=... 返回渲染后的完整 HTML 文件（带内联 CSS，
       可直接发给别人或在浏览器里打印成 PDF）；--open 启动后自动用 webbrowser.open 打开。

2. 输入与交互
   2.1 命令行：python preview.py README.md --port 8000 --root .。
   2.2 无参数时列出当前目录下的 .md 文件并询问选择哪一个（编号输入），回车默认第一个。
   2.3 --watch-dir DIR：同时监控该目录内所有 md 文件的变更并显示“已更新”提示条。
   2.4 --print-url 只输出访问地址（便于脚本调用），--quiet 关闭请求日志。
   2.5 键盘快捷键（前端）：r 手动刷新、d 切换深色、t 显示/隐藏侧栏、Esc 关闭提示。

3. 输出与展示
   3.1 启动输出：预览服务已启动：http://127.0.0.1:8000/?file=README.md
       根目录：D:\work\docs   （Ctrl+C 停止）
   3.2 请求日志：格式为 时间 方法 路径 状态码 耗时ms 客户端地址；--verbose 时打印完整
       请求头（脱敏 Cookie 值）。
   3.3 渲染失败（Markdown 语法导致扩展报错）时降级为纯文本渲染，页面顶部显示错误条与
       异常摘要，服务不退出。
   3.4 /export 输出的 HTML 顶部含标题与生成时间，便于确认版本。

4. 异常与边界处理
   4.1 入口文件不存在：启动时列出根目录下可用的 md 文件并退出码 1。
   4.2 请求不存在的文件：返回 404 并渲染一个友好 HTML 错误页（含可点击的文件列表），
       而不是默认的裸文本。
   4.3 路径逃逸尝试（file=../../etc/passwd）：返回 403，日志记 WARNING，包含原始请求路径。
   4.4 符号链接指向 root 之外：校验 resolve() 后的真实路径，拒绝访问。
   4.5 端口被占用：捕获 OSError errno 98/48/10048，提示“端口 8000 已被占用，可用 --port
       换一个”，并尝试探测 8000-8010 中的可用端口（--port auto 时）。
   4.6 文件编码非 UTF-8：尝试 utf-8 -> utf-8-sig -> gbk -> latin-1 依次回退，
       在页面顶部提示实际编码。
   4.7 超大文件（> --max-size，默认 5MB）：拒绝渲染并提示“文件过大，请用 /raw 查看原文”。
   4.8 图片资源引用本地相对路径：/assets/ 处理器从 md 文件所在目录读取，缺失时返回一个
       占位 SVG 而不是 404 破图。
   4.9 中文文件名：URL 需要 quote/unquote 处理，测试含空格与中文的路径可正常访问。
   4.10 前端轮询失败（服务重启）：显示“连接已断开，正在重试”并进行指数退避重试，
       最多每 5 秒一次。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：markdown（渲染）；可选 pygments（代码高亮）；标准库 argparse、http.server、
   socketserver、pathlib、json、mimetypes、urllib.parse、webbrowser、logging、threading、
   hashlib、time、re、html、os。前端只用原生 HTML/CSS/JS，禁止引入构建工具。
3. 禁止事项：禁止绑定 0.0.0.0（默认只绑 127.0.0.1，若用户显式 --host 才允许并打印安全警告）；
   禁止执行 Markdown 中的任何脚本（渲染后对 <script> 做转义或过滤，禁用 raw HTML 或使用
   safe_mode 等价处理）；禁止把任意本地文件当静态资源返回；禁止用字符串拼接构造 HTML
   （除模板常量），用户内容必须经过渲染器与转义。
4. 代码组织：
   - renderer.py：MarkdownRenderer 类，render(text) -> (html, toc_html, meta)，
     负责扩展装配、异常降级、编码探测与 mtime 缓存。
   - filetree.py：scan_markdown(root, patterns) -> list[FileEntry]、safe_join(root, rel)
     -> Path（含逃逸校验）。
   - server.py：PreviewHandler(BaseHTTPRequestHandler)，do_GET 分发到
     _serve_index/_serve_fragment/_serve_list/_serve_raw/_serve_version/_serve_static/
     _serve_assets/_serve_export；build_server(host, port) 负责端口探测与复用。
   - templates.py：PAGE_TEMPLATE、ERROR_TEMPLATE、CSS_DEFAULT 字符串常量与
     render_page(...) 拼装函数。
   - watch.py：基于 mtime 轮询的文件版本缓存与变更检测（不用 watchdog，保持零额外依赖）。
   - cli.py：参数解析、启动流程、Ctrl+C 处理。
5. 编码规范：类型注解完整；HTTP 响应统一走 _send(status, content_type, body) 辅助方法，
   自动补 Content-Length 与 Cache-Control: no-store；HTML 模板用 str.replace 填占位符并
   对每个插入值做 html.escape；日志用 logging，请求日志与错误日志分级别；docstring 说明
   每个路由的行为与安全约束。

【四、设计要点】

1. 数据结构：
   FileEntry：rel(str)、abs_path(Path)、name(str)、size(int)、mtime(float)、dir(str)。
   RenderResult：html(str)、toc(str)、title(str)、encoding(str)、warnings(list[str])、
   mtime(float)、size(int)、hash(str，前 16 位 md5 用于前端比对)。
   ServerConfig：root(Path)、entry(Path)、host(str)、port(int)、poll_ms(int)、theme(str)、
   css_path(Path|None)、token(str|None)、max_size(int)、deny(list[str])、
   markdown_extensions(list[str])。

2. 关键算法或流程：
   2.1 渲染流程：读文件（带回退编码）-> 若开启缓存且 (mtime, size) 未变则直接返回缓存结果
       -> md = markdown.Markdown(extensions=..., extension_configs={"codehilite":
       {"guess_lang": False, "css_class": "highlight"}}) -> html = md.convert(text) ->
       toc = md.toc -> 抽取第一个 H1 作为 title -> 计算 hash -> 写入缓存（用
       functools.lru_cache(maxsize=32) 或自建 dict）。
   2.2 局部刷新流程：前端轮询 /version 得到 {mtime, size, hash}；与上次不同则
       fetch('/fragment?file=...') 返回正文 HTML 片段；用 container.innerHTML 替换后恢复
       滚动：先记录当前第一个可见标题的 id 与偏移，替换后 scrollIntoView 到同一标题。
   2.3 TOC 生成与锚点：markdown 的 toc 扩展默认 slugify 会丢中文，需要自定义
       slugify 回调：先 unicodedata.normalize("NFKC")，再保留中英数字与连字符，其余替换为
       '-'，重复时追加 -1、-2；同时在渲染时给标题注入 id（用 toc 扩展自带的 id 即可）。
   2.4 安全路径拼接：rel 先 urllib.parse.unquote，再拒绝含空字节与绝对路径的输入；
       p = (root / rel).resolve()；if not p.is_relative_to(root.resolve()): raise Forbidden；
       再检查 p 是否命中 deny 模式（fnmatch）与是否为普通文件。
   2.5 Token 校验：请求参数 token 或 Cookie preview_token 与配置比对，用
       hmac.compare_digest 防时序攻击；失败返回 401 并渲染输入框页面（输入后设置 Cookie）。
   2.6 HTML 净化：默认禁用 raw HTML，改用 markdown 扩展时设置
       extension_configs 或渲染后对 <script>/<iframe>/on* 属性做移除；对标记为“信任模式”
       （--allow-html）时在页面显式警告。
   2.7 端口探测：从 --port 开始依次尝试 bind，最多 10 个；成功即用，全部失败报错退出。
   2.8 优雅关闭：KeyboardInterrupt 捕获后 server.shutdown() + server.server_close()，
       打印“服务已停止”。

3. 接口设计：
   HTTP 路由：
     GET /                     渲染入口文件（?file= 覆盖）
     GET /fragment?file=PATH   返回仅正文 HTML（用于局部刷新）
     GET /list                 返回 JSON 文件树
     GET /raw?file=PATH        返回 text/plain 原文
     GET /version?file=PATH    返回 {mtime,size,hash}
     GET /export?file=PATH     返回完整独立 HTML（内联 CSS）
     GET /assets/PATH          返回 md 文件所在目录的图片等资源
     GET /static/app.css|app.js
   命令行：
   python preview.py [FILE] [--root DIR] [--host 127.0.0.1] [--port 8000|auto]
     [--poll-ms 800] [--theme light|dark|auto] [--css FILE] [--token TOKEN]
     [--allow-html] [--no-extra] [--max-size 5MB] [--deny '.env,.git/*']
     [--open] [--print-url] [--quiet] [--verbose]
   核心函数：render(text: str, cfg: ServerConfig) -> RenderResult
             safe_join(root: Path, rel: str) -> Path

【五、运行方式与示例】

1. 安装依赖：
   pip install "markdown>=3.5"
   pip install pygments        （可选，启用代码高亮）

2. 启动并自动打开浏览器：
   python preview.py README.md --root . --port 8000 --theme auto --open
   输出：预览服务已启动：http://127.0.0.1:8000/?file=README.md
         根目录：D:\work\docs   （Ctrl+C 停止）
         127.0.0.1 - - [06/May/2025 14:32:05] GET / 200 8.2ms

3. 带访问令牌，只允许本机：
   python preview.py docs/guide.md --token k7Qp2 --port auto
   输出：预览服务已启动：http://127.0.0.1:8001/?file=docs/guide.md&token=k7Qp2
   访问 http://127.0.0.1:8001/list 无 token 时返回 401。

4. 文件变更自动刷新（浏览器行为）：
   （在编辑器中保存 guide.md）
   /version 返回的 hash 变化 -> 前端 800ms 内替换正文，滚动位置保持在“## 安装”小节，
   页面右上角出现提示条“已更新 14:36:12”。

5. 导出单文件 HTML 交给同事：
   curl -o guide.html "http://127.0.0.1:8000/export?file=docs/guide.md"
   输出：guide.html（内联 CSS，双击即可在浏览器打开，含生成时间 2025-05-06 14:37:02）

6. 异常示例：路径逃逸
   curl -i "http://127.0.0.1:8000/raw?file=../../../../etc/passwd"
   输出：HTTP/1.1 403 Forbidden；错误页：拒绝访问：路径超出售权根目录（已记录日志）

7. 异常示例：入口文件不存在
   python preview.py missing.md
   输出：错误：文件不存在 D:\work\missing.md
         当前目录可用的 Markdown 文件：README.md, docs/guide.md
         （退出码 1）

【六、验收标准】

[ ] 启动后浏览器访问首页能看到渲染后的 HTML，标题、列表、表格、代码块均正确显示。
[ ] 表格语法渲染为真正的 <table>，围栏代码块渲染为 <pre><code> 并带语言类名。
[ ] 安装 pygments 后代码块有语法高亮；未安装时服务仍能启动并给出提示。
[ ] 保存 Markdown 文件后，页面在 --poll-ms 时间内更新内容，滚动位置大致保持。
[ ] 侧栏文件列表点击任意 md 文件能切换预览，URL 的 file 参数同步变化。
[ ] /version 在文件未变时返回相同 hash，修改后 hash 变化。
[ ] 中文标题生成的锚点可点击跳转，且 URL 中的中文被正确百分号编码。
[ ] 访问 /assets/ 下的图片能显示；图片不存在时返回占位图而不是 404 破图。
[ ] 请求 file=../../etc/passwd 返回 403，且日志中出现 WARNING 记录。
[ ] root 目录内的符号链接指向外部文件时被拒绝（用 mklink 或 ln -s 构造测试）。
[ ] --token 开启后无 token 的请求返回 401，带正确 token 返回 200；错误 token 也返回 401。
[ ] 非 UTF-8（GBK）的 md 文件能正常渲染中文，页面顶部提示实际编码。
[ ] 大于 --max-size 的文件获得明确提示，服务不卡死。
[ ] /export 生成的 HTML 双击打开无外部依赖，样式与在线预览一致。
[ ] 含 <script>alert(1)</script> 的 md 文件渲染后不执行脚本（查看源码确认被转义/移除）。
[ ] 端口被占用时自动改用下一个端口（--port auto），或给出明确错误。
[ ] Ctrl+C 后端口立即释放（再次启动不报“地址已被使用”）。

【七、可选扩展】

1. 增加 SSE（Server-Sent Events）或 WebSocket 推送变更事件，替代轮询，实现毫秒级刷新。
2. 增加 Mermaid/KaTeX 的可选前端资源本地打包（离线可用），渲染流程图与数学公式。
3. 增加“编辑并保存”能力（PUT /save），配合 token 与备份文件实现浏览器内轻量编辑。
4. 增加导出 PDF 的说明（引导用户用浏览器打印）或接入 playwright 做无头导出。
5. 增加多根目录（--root 可重复）与工作区切换，支持同时预览多个项目文档。
6. 增加从 Markdown 生成静态站点（复用本项目的渲染管线，输出整站 HTML）。

【八、涉及知识点】

- markdown 库的扩展体系：extra、toc、tables、fenced_code、codehilite、attr_list、
  sane_lists 与 extension_configs 配置。
- Python 的 http.server / BaseHTTPRequestHandler 与 ThreadingHTTPServer 多线程模型。
- HTTP 基础：状态码、Content-Type、Content-Length、Cache-Control 与查询参数解析。
- 路径安全的根本做法：urllib.parse.unquote + Path.resolve + is_relative_to 三重校验。
- 令牌校验与 hmac.compare_digest 的时序攻击防护。
- HTML 注入风险与对 raw HTML / script 的处理策略。
- 前端原生 JS：fetch、轮询与退避、innerHTML 局部更新、scrollIntoView 恢复滚动。
- 缓存策略：基于 (mtime, size) 的失效判断与 lru_cache 的使用边界。
- 中文 slug 生成：unicodedata 归一化与字符白名单过滤。
================================================================================
