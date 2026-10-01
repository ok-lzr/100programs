================================================================================
项目编号：039                    难度等级：★★★☆☆（小型项目）
项目名称：文件加解密工具
所属分类：本地加密与凭据 / 命令行工具
建议工时：7 ~ 10 小时
运行环境：Python 3.10+    第三方依赖：cryptography
================================================================================

【一、项目背景与目标】

把合同、身份证照片、财务报表放进网盘或 U 盘之前，很多人只是简单打个 zip 加个密码。
但 zip 传统加密（ZipCrypto）早已可被已知明文攻击破解，7z 的 AES 加密在不同客户端上
兼容性参差，而且加完密之后文件名、目录结构往往仍然可见，暴露了内容性质。

本项目做一个文件与目录级的加解密工具：用口令派生密钥（PBKDF2-HMAC-SHA256 或
scrypt），以 AES-256-GCM 认证加密任意文件，加密后连文件名一起打包进密文容器，
输出为单一 .enc 文件；解密时可原样还原文件名与目录结构。支持目录递归、多文件批量、
流式处理大文件（不把整个文件读进内存）、以及完整性校验（篡改必然解密失败）。

目标用户是需要给敏感文件做离线保护的普通用户、需要把资料交给外部时的企业员工、
以及需要定期归档加密备份的运维人员。

【二、功能需求清单】

1. 核心功能
   1.1 加密单个文件：encrypt <input> -o <output.enc>，
       输出容器内含原始文件名、大小、修改时间、内容。
   1.2 加密目录：encrypt <dir> -o <archive.enc>，递归打包目录内所有文件，
       保留相对路径；支持 --exclude 与 --max-size 过滤。
   1.3 解密：decrypt <archive.enc> -o <outdir 或 outfile>，
       还原文件名与目录结构，并恢复修改时间（os.utime）。
   1.4 查看信息：info <archive.enc> 在不提供口令的情况下显示容器公开头部
       （版本、KDF 类型与参数、salt、nonce、文件数量、总大小、创建时间、注释）；
       提供口令时额外校验并列出内部文件清单（文件名、原始大小）。
   1.5 完整性校验：verify <archive.enc> 用口令解密并逐块校验 GCM 认证标签与
       每个文件的 SHA256 记录，输出"完整/被篡改（第 N 个文件）"。
   1.6 口令来源：交互式输入（getpass，两次确认）为主；
       也支持 --password-file <path>（读取首行并立即提示该文件本身应妥善保管）；
       严禁通过 --password 直接传口令。
   1.7 KDF 选择：--kdf pbkdf2|scrypt（默认 scrypt），
       pbkdf2 参数 --iterations（默认 600000），
       scrypt 参数 --n 2**15 --r 8 --p 1（默认值，须在头部记录）。
   1.8 分块流式加解密：大文件按 1 MiB 分块加密，每块独立 nonce
       （由主 nonce 与块序号通过 HMAC 派生），支持断点续解压时按块校验。
   1.9 口令更换：rekey <archive.enc> --output new.enc 用新口令重新加密，
       不改变内部文件内容。
   1.10 明文管道模式：支持 stdin/stdout（--stdin --stdout），便于和其它命令行工具组合，
       此时不写入文件名元数据，输出纯密文流。

2. 输入与交互
   2.1 入口：python cli.py <子命令> <路径> [选项]，
       子命令为 encrypt、decrypt、info、verify、rekey、list-kdf。
   2.2 --overwrite 允许覆盖已存在的输出文件；默认遇到同名输出时
       自动追加序号 _1、_2，并在输出中说明。
   2.3 输出文件扩展名默认 .enc；解密时若输出路径省略，
       则使用容器内保存的原始文件名，还原到当前目录或 -o 指定的目录下。
   2.4 --progress 显示进度（已处理字节/总字节、速度 MB/s、预计剩余时间），
       每 0.5 秒刷新一次，输出到 stderr；--quiet 时完全静默。
   2.5 --comment "备注" 在容器头部写入一段 UTF-8 明文注释（长度上限 1024 字节），
       info 命令可读；注释不加密，必须在文档中明确提示不要写入敏感信息。

3. 输出与展示
   3.1 encrypt 成功输出：
       已加密：C:\data\report.xlsx（1.8 MB）
       输出：C:\data\report.xlsx.enc（1.8 MB，含 1 个文件）
       KDF：scrypt（n=32768, r=8, p=1，salt 16 字节）
       耗时：1.24 秒（平均 1.45 MB/s）
   3.2 info 输出字段：格式版本、创建时间、KDF 类型与参数、salt（base64，前 8 字节）、
       nonce（base64）、文件条数、总大小、注释、每个文件的路径与大小。
   3.3 verify 输出：逐文件 OK/FAILED，最后一行
       "校验完成：N 个文件，通过 N，失败 M"。
   3.4 所有输出不含口令；错误信息不含口令；--debug 日志同样脱敏。

4. 异常与边界处理
   4.1 输入不存在：报"错误：文件不存在 - <path>"，退出码 1。
   4.2 口令为空：报"错误：口令不能为空"，退出码 2；加密时两次输入不一致同样报错。
   4.3 口令过短（< 8 位）：报错；8~11 位给出强度警告并要求输入 yes 确认。
   4.4 解密口令错误或文件被篡改：捕获 InvalidTag，统一提示
       "解密失败：口令错误或文件已损坏（无法通过认证校验）"，退出码 3。
   4.5 容器格式非法：magic 不匹配报"不是本工具生成的加密文件"；
       版本高于支持版本报"容器版本 N 不受支持，请升级工具"，退出码 1。
   4.6 输出已存在：默认改名，--overwrite 时覆盖，并提示"已覆盖 <path>"。
   4.7 磁盘空间不足：加密前检查目标盘剩余空间是否大于预估大小（输入大小 + 1 MB 开销），
       不足则拒绝并给出所需空间提示。
   4.8 输入文件在处理期间被修改：记录前后 size 与 mtime，不一致时警告
       "文件在处理期间发生变化，输出可能不一致"。
   4.9 目标目录内已有同名解密文件：默认不覆盖，报"目标文件已存在：<path>，
       使用 --overwrite 覆盖"。
   4.10 解密时遇到路径穿越（容器内文件名含 .. 或绝对路径）：
       必须拒绝并报"检测到不安全的路径：<name>"，退出码 1（防止恶意容器覆盖系统文件）。
   4.11 中断（Ctrl+C）：删除写入中的临时文件，保留原有文件不变，退出码 130。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：cryptography（AESGCM、PBKDF2HMAC、Scrypt、
   cryptography.hazmat.primitives.hashes）。其余使用标准库：argparse、getpass、secrets、
   os、sys、json、struct、hashlib、hmac、base64、pathlib、time、datetime、shutil、
   dataclasses、logging、typing。
   安装：pip install cryptography
3. 安全红线：
   3.1 口令绝不落盘：口令只保存在局部变量中，不写日志、不写配置、不进入异常消息；
       禁止 --password 命令行参数（只能交互式或从 --password-file 读取）。
   3.2 随机数来源：salt、nonce 一律使用 secrets.token_bytes（内部基于 os.urandom）；
       严禁使用 random 模块产生任何密钥相关随机值。
   3.3 salt 长度 16 字节，主 nonce 长度 12 字节，每次加密全部重新生成。
   3.4 KDF 参数必须写入容器头部，解密时以头部参数为准（保证向前兼容）；
       但对参数设下限校验：iterations >= 100000、scrypt n >= 2**14，
       低于下限拒绝解密并提示可能是降级攻击。
   3.5 AES-256-GCM 的 AAD 使用容器固定头部字节，头部一旦被改，解密即失败。
   3.6 每个文件的 SHA256 明文摘要写入元数据，用于 verify 的二次确认
       （GCM 已保证完整性，SHA256 用于交叉验证与部分恢复检查）。
   3.7 原子写入：先写 <目标>.tmp，成功后 os.replace；失败或中断时删除临时文件。
   3.8 Linux/macOS 下输出文件 chmod 0600；Windows 下不额外处理但提示建议使用 NTFS 加密。
4. 代码组织：至少包含 container.py（容器格式读写）、kdf.py（PBKDF2/scrypt 封装）、
   streamcipher.py（分块加解密）、walker.py（目录遍历与路径安全校验）、cli.py。
   关键签名固定为
   derive_key(password: str, salt: bytes, params: KdfParams) -> bytes
   encrypt_file(src: Path, dst: Path, key: bytes, comment: str) -> None
   decrypt_file(src: Path, dst_dir: Path, key: bytes) -> list[Path]
5. 编码规范：类型注解与 docstring 齐全；异常体系 EncryptionError / DecryptionError /
   ContainerFormatError；所有文件读写使用二进制模式（"rb"/"wb"）；
   不使用 print 输出调试信息，统一走 logging。

【四、设计要点】

1. 数据结构与容器格式：
   1.1 容器整体布局（小端）：
       [0:8]     magic = b"PYCRYPT1"
       [8:12]    version = 1（uint32）
       [12:13]   kdf_id（1=pbkdf2，2=scrypt）
       [13:17]   kdf_param_a（uint32，pbkdf2 为 iterations；scrypt 为 n）
       [17:21]   kdf_param_b（uint32，scrypt 的 r；pbkdf2 为 0）
       [21:25]   kdf_param_c（uint32，scrypt 的 p；pbkdf2 为 0）
       [25:41]   salt（16 字节）
       [41:53]   base_nonce（12 字节）
       [53:57]   header_len（uint32，加密后的头部长度）
       [57:61]   comment_len（uint32）
       [61:61+clen] comment（UTF-8 明文）
       [..]      encrypted_header（AES-GCM 加密的 JSON 元数据，AAD = 前面所有头部字节）
       [..]      数据块序列：每块 [4 字节长度][密文]
   1.2 元数据 JSON（加密后放在 encrypted_header 中）：
       {"version":1, "created":"...", "files":[{"path":"a/b.txt","size":1234,
        "mtime":1716000000.0,"sha256":"..."}], "total_size": 12345,
        "chunk_size": 1048576}
   1.3 KdfParams 数据类：kind: str，iterations: int | None，n: int | None，
       r: int | None，p: int | None；提供 to_bytes() / from_bytes() 与
       describe() -> str（用于 info 输出）。
   1.4 FileEntry 数据类：path: str（POSIX 风格相对路径），size: int，
       mtime: float，sha256: str。
2. 关键算法或流程：
   2.1 密钥派生：
       - scrypt：Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(pw.encode("utf-8"))
       - pbkdf2：PBKDF2HMAC(algorithm=SHA256(), length=32, salt=salt,
         iterations=600000).derive(pw.encode("utf-8"))
       派生出的 32 字节既作为 AES-256 密钥，也作为头部 HMAC 与块 nonce 派生的密钥材料。
   2.2 分块 nonce 派生（关键设计，避免 GCM nonce 复用）：
       对第 i 块（从 0 开始），
       block_nonce = HMAC-SHA256(key, base_nonce + struct.pack("<Q", i))[:12]
       因为 base_nonce 每次加密都随机，密钥每次也随机，所以 nonce 不会重复；
       最后一字节用作"是否最后一块"的标志位时需另行设计，本项目改为在每块明文前
       加 1 字节标志（0=中间块，1=最后块），该标志包含在 AAD 之外的明文中，
       由 GCM 的认证标签保护。
   2.3 加密流程：
       (a) 校验输入与磁盘空间 → (b) 生成 salt、base_nonce，派生 key →
       (c) 遍历输入构建 FileEntry 列表（若为目录则递归，跳过符号链接，
           应用 --exclude 与 --max-size）→ (d) 序列化元数据 JSON，
           encrypt(key, base_nonce, meta, aad=header) 得到 encrypted_header →
       (e) 写容器头部 → (f) 逐文件、逐块读取并加密写出，同时更新 SHA256 →
       (g) 若 SHA256 与元数据不一致（文件被改），抛错并删除临时文件 →
       (h) os.replace 原子替换 → chmod 0600。
       注意：元数据必须在文件内容之前写入，因此 SHA256 需要先扫描一遍计算，
       或者写两遍元数据。本项目采用"先扫描计算 SHA256 与大小，再写头部，再写内容"，
       并对扫描与写入之间的文件变化做 size/mtime 复核。
   2.4 解密流程：读头部 → 校验 magic/version/KDF 参数下限 →
       派生 key → AESGCM.decrypt 解出元数据（InvalidTag → DecryptionError）→
       校验每个 path 的安全性（见 2.5）→ 创建目录 →
       逐块解密并写入目标文件，每块解密成功后更新 SHA256 →
       全文件完成后比对 SHA256，不一致则标记该文件 FAILED →
       用 os.utime 恢复 mtime。
   2.5 路径安全校验（必须实现）：对元数据中的每个 path，
       拒绝绝对路径（含盘符如 C:\ 与 /开头）、拒绝包含 ".." 的任一段、
       拒绝包含 ":" 的段（Windows 备用数据流）、
       规范化后必须仍位于目标目录之内（用 Path.resolve() 与 os.path.commonpath 校验）。
   2.6 进度计算：总字节数 = 元数据 total_size；每处理完一块更新已处理字节，
       速度 = 已处理 / 已耗时，剩余时间 = (总 - 已处理) / 速度。
3. 接口或命令设计：
   python cli.py encrypt <输入> [-o 输出] [--kdf scrypt] [--iterations 600000]
                                [--exclude PATTERN]... [--max-size 100MB]
                                [--comment "备注"] [--progress] [--overwrite]
   python cli.py decrypt <容器> [-o 目录] [--password-file PATH] [--overwrite] [--progress]
   python cli.py info <容器> [--with-password]
   python cli.py verify <容器> [--password-file PATH]
   python cli.py rekey <容器> -o <新容器>
   退出码：0 成功；1 一般错误（含格式非法）；2 参数或口令错误；3 认证失败；130 中断。

【五、运行方式与示例】

安装：
   pip install cryptography
运行：
   python cli.py encrypt .\report.xlsx -o .\report.xlsx.enc --progress
   python cli.py info .\report.xlsx.enc
   python cli.py decrypt .\report.xlsx.enc -o .\restore
   python cli.py verify .\report.xlsx.enc

示例一（加密单个文件）：
   输入：python cli.py encrypt .\report.xlsx -o .\report.xlsx.enc
   输出：
   请输入口令：
   请再次输入口令：
   已加密：C:\data\report.xlsx（1.8 MB）
   输出：C:\data\report.xlsx.enc（1.8 MB，含 1 个文件）
   KDF：scrypt（n=32768, r=8, p=1，salt 16 字节）
   耗时：1.24 秒（平均 1.45 MB/s）

示例二（查看容器信息，无需口令）：
   输入：python cli.py info .\report.xlsx.enc
   输出：
   格式版本：1
   创建时间：2024-05-20T10:12:33
   KDF：scrypt（n=32768, r=8, p=1）
   salt：3QmZ0k8f...（base64，前 8 字节）
   nonce：aB3xY9...
   文件条数：1
   总大小：1,887,436 字节
   注释：（无）
   使用 --with-password 查看内部文件清单

示例三（解密目录容器）：
   输入：python cli.py encrypt .\projects -o .\projects.enc --exclude "*.tmp" --max-size 50MB
   输出：输出：C:\data\projects.enc（12.4 MB，含 37 个文件）
   输入：python cli.py decrypt .\projects.enc -o .\restore --progress
   输出：
   请输入口令：
   进度：12.4 MB / 12.4 MB  100%  速度 45.2 MB/s  剩余 0s
   已解密：37 个文件 → C:\data\restore\projects
   校验：全部通过

示例四（异常输入一：口令错误）：
   输入：python cli.py decrypt .\projects.enc -o .\restore
   输出：
   请输入口令：
   错误：解密失败：口令错误或文件已损坏（无法通过认证校验）
   退出码：3

示例五（异常输入二：被篡改的容器）：
   操作：用十六进制编辑器修改 report.xlsx.enc 中间的一个字节
   输入：python cli.py verify .\report.xlsx.enc
   输出：
   错误：解密失败：口令错误或文件已损坏（无法通过认证校验）
   退出码：3
   说明：GCM 认证标签检测到数据被修改，程序不会输出任何解密后的内容。

示例六（异常输入三：恶意路径）：
   输入：python cli.py decrypt .\evil.enc -o .\out
   输出：
   错误：检测到不安全的路径：..\..\Windows\System32\drivers\etc\hosts
   退出码：1

【六、验收标准】

[ ] 加密后对 .enc 文件执行 strings，找不到原始文件名与文件内容的可读片段。
[ ] 加密前后文件大小差异小于 8 KB（元数据与认证标签开销）。
[ ] 解密还原的文件与原始文件用 SHA256 比对完全一致（覆盖二进制大文件）。
[ ] 解密还原的目录结构与原目录一致，且修改时间被恢复（误差 < 2 秒）。
[ ] 修改 .enc 任意一个字节后 decrypt 与 verify 都报认证失败，退出码为 3。
[ ] 修改容器头部的 kdf_param_a（iterations）后解密失败（AAD 生效）。
[ ] 头部迭代次数被改成低于 100000 时拒绝解密并提示可能的降级攻击。
[ ] 连续两次加密相同文件，salt、base_nonce 与密文全部不同。
[ ] 1 GB 文件加密过程中内存占用稳定（RSS 增长 < 100 MB）。
[ ] --exclude "*.tmp" 生效，容器内的文件清单中不含 .tmp 文件。
[ ] info 命令在不提供口令时也能正常输出头部信息。
[ ] --with-password 的 info 会校验口令，口令错误时返回退出码 3。
[ ] 手工构造含 "..\..\" 路径的容器被拒绝解密，退出码为 1。
[ ] rekey 之后旧口令无法解密、新口令可以正常解密。
[ ] 命令行传入 --password 参数会报错退出，退出码为 2。
[ ] 全程日志与异常输出中不含口令明文字符串。
[ ] Ctrl+C 中断后没有残留 .tmp 文件，原文件未受影响。

【七、可选扩展】

1. 增加数字签名模式：用 Ed25519 私钥对容器签名，接收方用公钥验证来源。
2. 增加"口令 + 密钥文件"双因子（HKDF 混合两个秘密后再派生 AES 密钥）。
3. 增加分卷输出（--split 100MB），便于通过邮件或聊天工具分批传输。
4. 增加 GUI 拖放界面（tkinter），复用同一 container/streamcipher 后端。
5. 增加"安全删除原文件"选项（多次覆写后再删除），并明确说明 SSD 上的局限性。

【八、涉及知识点】

- PBKDF2-HMAC-SHA256 与 scrypt 的参数含义与内存/时间成本权衡
- AES-256-GCM 分块加密中的 nonce 管理策略（HMAC 派生块 nonce）
- 认证加密的 AAD 用法、InvalidTag 异常与"不区分密码错误与篡改"的安全考量
- 二进制容器格式设计（magic、版本、长度前缀字段）
- secrets.token_bytes 作为密码学安全随机源
- 流式处理大文件（分块读写）与常量内存占用
- 路径穿越漏洞的成因与防护（规范化 + 前缀校验）
- 原子写入、文件权限、异常清理与中断恢复
- 进度计算与速率估算
================================================================================
