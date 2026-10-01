================================================================================
项目编号：033                    难度等级：★★☆☆☆（小型项目）
项目名称：二维码生成器
所属分类：安全与编码 / 图像生成
建议工时：4 ~ 6 小时
运行环境：Python 3.10+    第三方依赖：qrcode、Pillow
================================================================================

【一、项目背景与目标】

做活动海报要放报名二维码、给路由器贴纸要做 WiFi 一键连接码、给名片加联系方式码、
给一批设备编号各生成一张二维码——这些需求如果都去在线网站生成，既要联网、又会把
内容（尤其是 WiFi 密码）上传到第三方服务器，还有广告与水印。

本项目做一个纯本地运行的二维码生成器：支持纯文本、URL、WiFi 配置、vCard 名片四类
内容模板，一次生成单张或按 CSV 批量生成，并提供样式选项（尺寸、边框留白、前后景色、
圆角/圆点模块风格）。所有数据只在本机处理，WiFi 密码不会离开用户电脑。

目标用户是运营与设计同学、小型店主、嵌入式/网络工程师，以及需要给几十台设备批量
打印二维码标签的运维人员。做成之后，一条命令即可得到可直接印刷的高分辨率 PNG 或 SVG。

【二、功能需求清单】

1. 核心功能
   1.1 文本模式：--text "任意文本"，直接编码为二维码。
   1.2 URL 模式：--url "https://example.com"，做基本校验（scheme 为 http/https，
       域名非空），并提示最终编码内容。
   1.3 WiFi 模式：--wifi-ssid、--wifi-password、--wifi-security（WPA/WEP/nopass）、
       --wifi-hidden，按标准格式生成：
       WIFI:T:WPA;S:<ssid>;P:<password>;H:true;;
       其中特殊字符 \ ; , : " 必须按规范转义（反斜杠转义）。
   1.4 名片模式：--vcard-name、--vcard-org、--vcard-title、--vcard-tel、
       --vcard-email、--vcard-url，生成 vCard 3.0 文本（BEGIN:VCARD / VERSION:3.0 /
       N / FN / ORG / TITLE / TEL / EMAIL / URL / END:VCARD），行尾统一 CRLF。
   1.5 批量生成：--batch data.csv --outdir out，CSV 至少包含 name 与 content 两列；
       也支持 type 列（text/url/wifi/vcard）与各模板专有列。
       name 用作输出文件名，非法文件名字符替换为下划线。
   1.6 样式美化：--size 像素边长（默认 512）、--border 静区模块数（默认 4）、
       --fg / --bg 颜色（支持 #RRGGBB 与英文色名）、--style square|rounded|dots、
       --logo logo.png 在中心叠加带白底圆角的 Logo。

2. 输入与交互
   2.1 入口：python cli.py [--text ... | --url ... | --wifi-ssid ... | --vcard-name ...]
       [选项]；四种内容来源互斥，同时给多个时报错退出码 2。
   2.2 纠错等级：--ec L|M|Q|H，默认 M；叠加 Logo 时若等级低于 Q，
       自动提示"建议使用 --ec H 以保证可识别"（不强制）。
   2.3 输出：--output path（单张默认 qrcode.png），--format png|svg|jpg，
       由扩展名或 --format 决定。
   2.4 --quiet 关闭所有提示，只输出最终文件路径；未指定时打印生成摘要
       （内容类型、字符数、纠错等级、版本号、文件大小）。
   2.5 --list-encodings 打印当前已注册的中文编码与支持的格式列表。

3. 输出与展示
   3.1 PNG/JPG：由 qrcode.make 得到 PIL Image 后 resize 到目标边长，
       使用 Image.NEAREST 保持模块边缘锐利（--smooth 时改用 LANCZOS）。
   3.2 SVG：使用 qrcode.image.svg.SvgPathImage（或 SvgImage），矢量输出不做缩放。
   3.3 批量模式输出汇总表：序号、name、类型、输出路径、大小（字节）、状态。
   3.4 结束时打印 "成功 N，失败 M，总耗时 X.XX 秒"。

4. 异常与边界处理
   4.1 内容为空或全空白：打印"错误：编码内容不能为空"，退出码 1。
   4.2 内容超长：捕获 qrcode.exceptions.DataOverflowError，
       提示"内容超过纠错等级 H 的容量上限，请降低纠错等级或缩短内容"，退出码 1。
   4.3 中文字符：显式设置二维码的编码为 UTF-8，并在摘要中提示
       "含非 ASCII 字符，部分老旧扫码器可能乱码"。
   4.4 颜色非法：--fg "#GGGGGG" 报"颜色格式错误，应为 #RRGGBB"，退出码 2。
   4.5 颜色对比度过低：当 fg 与 bg 的亮度差小于 30% 时给出警告但仍生成。
   4.6 WiFi 密码含分号或引号：按规范转义，生成的字符串在日志中回显时
       密码用 *** 遮蔽（仅 --show-secret 时明文显示）。
   4.7 CSV 缺少必需列：打印缺少的列名与退出码 2；单行数据非法时跳过该行并计数。
   4.8 输出目录不存在：自动创建（parents=True, exist_ok=True）；
       同名文件默认覆盖，--no-overwrite 时改为追加序号 _2、_3。
   4.9 Logo 过大：Logo 边长超过二维码边长 25% 时自动缩小到 25% 并提示。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：qrcode（含 qrcode.image.svg 子模块）、Pillow（PIL）。
   其余功能使用标准库：argparse、csv、pathlib、re、json、hashlib、dataclasses、typing。
   安装：pip install "qrcode[pil]" Pillow
3. 禁止事项：禁止把 WiFi 密码或 vCard 私密字段写入任何日志文件；
   禁止调用任何在线二维码 API；禁止硬编码 Logo 路径；禁止在批量模式下因单行失败而中断。
4. 代码组织：至少包含 content.py（四类内容模板的构造与校验）、render.py
   （二维码矩阵到图像的渲染与样式）、batch.py（CSV 批量驱动）、cli.py。
   内容构造函数签名固定为 build_wifi_payload(ssid, password, security, hidden) -> str
   与 build_vcard(fields: dict[str, str]) -> str。
5. 编码规范：类型注解与 docstring 齐全；所有文件读写显式指定 encoding="utf-8"；
   CSV 使用 newline="" 打开避免空行；输出路径统一用 pathlib.Path 处理。

【四、设计要点】

1. 数据结构：
   - QrSpec：kind: str，payload: str，ec_level: str，size: int，border: int，
     fg: str，bg: str，style: str，logo: Path | None。
   - BatchRow：index: int，name: str，kind: str，payload: str，status: str，error: str。
   - WIFI_SECURITY_MAP = {"wpa": "WPA", "wep": "WEP", "nopass": "nopass"}。
   - VCARD_FIELD_ORDER = ["N", "FN", "ORG", "TITLE", "TEL", "EMAIL", "URL", "NOTE"]。
2. 关键算法或流程：
   2.1 WiFi 载荷转义规则：对 ssid、password 中的 \ ; , : " 五个字符前加反斜杠；
       hidden 为真时追加 H:true；nopass 时省略 P 字段。
   2.2 vCard 生成：逐字段写入，值中的换行替换为空格，逗号与分号按 vCard 规则转义；
       超过 75 字节的行做折叠（续行以单个空格开头）。TEL 统一转成 +国家码 形式不做强校验。
   2.3 渲染流程：
       (a) qr = qrcode.QRCode(version=None, error_correction=..., box_size=10, border=border)；
       (b) qr.add_data(payload, optimize=0)；qr.make(fit=True)；
       (c) img = qr.make_image(fill_color=fg, back_color=bg).convert("RGB")；
       (d) 按 --size 计算 box_size 后重建，或对结果做 NEAREST 缩放，
           保证最终边长严格等于 --size（允许 ±1 像素误差并在日志说明）。
   2.4 圆点/圆角样式：直接用 PIL ImageDraw 读取 qr.get_matrix() 的布尔矩阵，
       对每个 True 模块绘制矩形（square）、圆角矩形（rounded，半径 = 模块边长 × 0.35）
       或椭圆（dots），逐模块绘制以保证边缘质量。
   2.5 Logo 叠加：Logo 缩放到二维码边长的 22%，加 8 像素白色圆角底衬，
       居中粘贴 到目标图上，粘贴位置必须覆盖奇数个模块宽以减少对定位图案的破坏。
   2.6 批量流程：csv.DictReader 逐行读取 → 按 type 选模板 → build payload →
       渲染 → 写文件 → 记录 BatchRow → 最后统一打印汇总。
3. 接口或命令设计：
   python cli.py --text "hello" -o hello.png --size 512 --ec H
   python cli.py --url "https://example.com" --format svg -o site.svg
   python cli.py --wifi-ssid "MyWiFi" --wifi-password "p@ss;word" --wifi-security WPA
   python cli.py --vcard-name "张三" --vcard-tel "+8613800138000" --vcard-email a@b.com
   python cli.py --batch contacts.csv --outdir out --style rounded --logo logo.png
   退出码：0 全成功；1 内容或渲染失败；2 参数错误。

【五、运行方式与示例】

安装：
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install "qrcode[pil]" Pillow
运行：
   python cli.py --text "Hello QR" -o .\out\hello.png --size 512
   python cli.py --wifi-ssid "Office-5G" --wifi-password "Abc12345" --wifi-security WPA
   python cli.py --batch data.csv --outdir .\out --ec H --style dots

data.csv 示例：
   name,type,content
   site,url,https://example.com
   wifi,wifi,WIFI:T:WPA;S:Office-5G;P:Abc12345;;
   card,vcard,BEGIN:VCARD|VERSION:3.0|FN:张三|END:VCARD

示例一（文本生成）：
   输入：python cli.py --text "Hello QR" -o hello.png --size 512 --ec M
   输出：
   类型：text    内容长度：8    纠错等级：M    版本：1    尺寸：512x512
   已生成：C:\out\hello.png（1,428 字节）

示例二（WiFi 二维码）：
   输入：python cli.py --wifi-ssid "Office-5G" --wifi-password "Abc12345" --wifi-security WPA
   输出：
   类型：wifi    载荷：WIFI:T:WPA;S:Office-5G;P:***;;
   纠错等级：M    版本：2    尺寸：512x512
   已生成：qrcode.png（1,655 字节）

示例三（批量 + 汇总）：
   输入：python cli.py --batch data.csv --outdir .\out --style rounded
   输出：
   序号  name   类型    输出路径            大小      状态
   1     site   url     out\site.png        1,712     成功
   2     wifi   wifi    out\wifi.png        1,689     成功
   3     card   vcard   out\card.png        2,043     成功
   成功 3，失败 0，总耗时 0.42 秒

示例四（异常输入）：
   输入：python cli.py --text "" --size 512
   输出：
   错误：编码内容不能为空
   退出码：1

【六、验收标准】

[ ] --text "Hello QR" 生成的 PNG 用手机扫码，识别结果与输入完全一致。
[ ] 指定 --size 512 时输出图片实际像素为 512x512（容差 ±1）。
[ ] 中文内容（如"你好世界"）扫码结果正确显示中文。
[ ] WiFi 密码含分号时，生成的载荷中分号被转义为 \;，扫码后可正常连接。
[ ] WiFi 密码在默认输出的日志中被遮蔽为 ***。
[ ] vCard 输出的行尾为 CRLF，可被手机通讯录正确导入为联系人。
[ ] 超过纠错等级容量上限的内容触发 DataOverflowError 分支并给出可操作提示。
[ ] --ec 取值非 L/M/Q/H 时报参数错误，退出码为 2。
[ ] --fg "#GGGGGG" 报颜色格式错误，退出码为 2。
[ ] --style dots 生成的点阵二维码仍可被扫码器识别。
[ ] 叠加 Logo 后（--ec H）二维码仍可识别，Logo 位于正中心。
[ ] 批量 CSV 中一行内容为空时其余行仍成功，汇总表中失败数为 1。
[ ] --format svg 输出为文本格式的 SVG，缩放后不失真。
[ ] --no-overwrite 时同名文件自动改名为 name_2.png，不覆盖原文件。
[ ] 全程无网络请求（可用抓包或断网测试验证）。

【七、可选扩展】

1. 增加地理位置（geo:lat,lon）、短信（SMSTO:）、邮件（MATMSG:）三种模板。
2. 增加 --sheet A4 排版：把多张二维码拼成 A4 网格 PDF 便于整版打印。
3. 增加解码校验：生成后用 pyzbar 或 opencv-python 回读，自动验证可识别性。
4. 增加渐变前景色与自定义模块形状插件机制，支持更丰富的视觉设计。

【八、涉及知识点】

- qrcode 库的 QRCode 对象、纠错等级与版本自动选择
- 二维码容量与纠错等级的关系、静区（quiet zone）作用
- Pillow 图像创建、缩放、绘图（ImageDraw）与粘贴合成
- vCard 与 WiFi 配置字符串的转义规范
- CSV 批量读写（csv.DictReader）与错误隔离
- 命令行互斥参数组（argparse mutually exclusive group）
- 敏感信息遮蔽与本地化处理的安全意识
================================================================================
