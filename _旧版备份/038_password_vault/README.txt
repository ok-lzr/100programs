================================================================================
项目编号：038                    难度等级：★★★☆☆（小型项目）
项目名称：本地密码保险箱
所属分类：本地加密与凭据 / 命令行工具
建议工时：6 ~ 9 小时
运行环境：Python 3.10+    第三方依赖：cryptography
================================================================================

【一、项目背景与目标】

每个人手上都有几十个账号：邮箱、银行、论坛、内网系统。用同一个密码到处注册是灾难，
写在明文 txt 或 Excel 里同样危险——一旦文件被同步到网盘或被他人拷走，所有账号沦陷。
浏览器自带的密码管理器又常常与设备绑定，换机迁移麻烦，且无法离线管理。

本项目做一个纯本地的密码保险箱：所有凭据存放在一个加密的 vault 文件里，
主密码通过 PBKDF2-HMAC-SHA256 派生密钥，用 AES-256-GCM 认证加密整个凭据库。
口令只在内存中存在，绝不落盘；每次写入都重新生成随机 salt 与 nonce；
解密失败（篡改或密码错误）时通过 GCM 的认证标签检测并明确报错，而不是静默返回垃圾数据。

目标用户是需要管理几十个账号的个人用户、需要给客户现场保存少量凭据的运维人员。
做成之后，用户只需要记住一个足够强的主密码，其余复杂度由工具承担。

【二、功能需求清单】

1. 核心功能
   1.1 初始化：vault init，创建 vault 文件，要求用户两次输入主密码，
       密码强度不足时给出警告并要求确认。
   1.2 新增凭据：vault add --site github.com --username me@example.com
       --password 从提示输入（不回显）或 --generate 自动生成 20 位强密码，
       可附 --url、--note、--tags。
   1.3 查询：vault get <site> 显示单条（密码默认遮蔽为 ******，--show 明文显示）；
       vault list 列出所有条目的 site、username、tags、更新时间（不含密码）；
       vault search <关键字> 在 site/username/note/tags 中模糊匹配。
   1.4 修改与删除：vault set <site> [--username ...] [--password ...] [--note ...]
       只更新传入的字段；vault rm <site> 删除并要求二次确认（--yes 跳过）。
   1.5 密码生成：vault gen --length 24 --symbols --no-ambiguous，
       使用 secrets 模块生成；排除易混字符 0/O/1/l/I。
   1.6 完整性校验：vault check 校验文件头、版本、HMAC 与 GCM 认证标签是否一致，
       并用 PBKDF2 参数重新派生密钥验证主密码是否正确。
   1.7 主密码修改：vault passwd 要求输入旧密码解密，再用新密码重新加密整个库；
       必须重新生成 salt 与 nonce。
   1.8 导入导出：vault export --format json/csv（默认明文导出并强提示风险，
       要求输入主密码二次确认）；vault import 从 CSV 批量导入。

2. 输入与交互
   2.1 主密码输入统一使用 getpass.getpass，绝不通过命令行参数传递（避免进入历史记录）。
       若检测到用户试图用 --password 传主密码，直接报错并退出码 2。
   2.2 vault 文件路径默认 ./vault.dat，可用环境变量 VAULT_PATH 或 --vault 覆盖。
   2.3 所有子命令支持 --json 输出结构化结果，便于脚本调用。
   2.4 vault list 支持 --tag 过滤与 --sort updated|site 排序。
   2.5 交互式模式：vault shell 进入 REPL，提示符 vault>，
       支持 get/list/add/rm/exit，命令历史不落盘。
   2.6 剪贴板：vault get <site> --copy 把密码复制到剪贴板（Windows 用 ctypes 调
       user32 的剪贴板 API，其它平台可选 tkinter），并在 20 秒后自动清空
       （仅当剪贴板内容仍是本次写入的值时才清空）。

3. 输出与展示
   3.1 列表输出固定列：SITE、USERNAME、TAGS、UPDATED（ISO 8601 本地时间）。
   3.2 单条输出格式：
       站点：github.com
       用户名：me@example.com
       密码：************（--show 显示明文）
       网址：https://github.com
       备注：<多行时按 --- 分隔显示>
       更新：2024-05-20T10:12:33
   3.3 任何日志、错误信息、异常堆栈中都不得出现明文密码或主密码。
   3.4 运行结束后不留临时文件；如需导出，明确告知导出文件的落盘位置与风险。

4. 异常与边界处理
   4.1 vault 文件不存在：提示"未找到保险箱文件，请先执行 vault init"，退出码 1。
   4.2 主密码错误：GCM 解密抛 InvalidTag，统一显示"主密码错误或文件已损坏"，
       退出码 3（不区分二者，避免泄露信息）。
   4.3 文件被篡改：同样由 InvalidTag 捕获；vault check 额外比对头部 HMAC 并指出
       "文件头校验失败，疑似被修改"。
   4.4 站点重复：add 同一 site 时提示已存在，建议用 set 或加 --force 覆盖。
   4.5 站点不存在：get/set/rm 报"未找到站点：<name>"，退出码 1。
   4.6 主密码过短（< 10 位）：报错并要求重输；过弱（仅小写或纯数字）给出警告，
       要求输入 "yes" 确认。
   4.7 写入失败（磁盘满、权限）：捕获 OSError 并保持原文件不变（先写临时文件再原子替换）。
   4.8 并发访问：使用一个 lock 文件（vault.dat.lock，含 PID 与时间戳），
       若锁存在且进程仍存活则拒绝操作；锁超过 10 分钟视为陈旧锁并自动清理。
   4.9 空库（0 条记录）：list 输出"保险箱为空"，退出码 0。
   4.10 主密码输入空字符串：报"主密码不能为空"并允许重试 3 次，
        3 次失败退出码 1。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：cryptography（使用 cryptography.hazmat.primitives.ciphers.aead.AESGCM
   与 cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC）。
   其余使用标准库：argparse、getpass、secrets、os、json、csv、base64、hashlib、hmac、
   pathlib、time、datetime、dataclasses、logging、typing、ctypes（仅 Windows 剪贴板）。
   安装：pip install cryptography
3. 安全红线（必须逐条在代码中落实，并在 README 与本文件中显式声明）：
   3.1 口令绝不落盘：主密码只作为局部变量存在，不写入任何文件、日志、配置、历史记录、
       异常消息；不在命令行参数中传递主密码。
   3.2 随机数来源：salt、nonce、生成的密码一律使用 secrets.token_bytes / secrets.choice。
       严禁使用 random 模块产生任何安全用途的随机值。
   3.3 密钥派生参数：PBKDF2-HMAC-SHA256，salt 长度 16 字节（随机），
       迭代次数 600000（可配置但默认取此值），派生密钥长度 32 字节。
   3.4 加密参数：AES-256-GCM，nonce 长度 12 字节，每次加密重新随机生成，
       且必须保证同一密钥下 nonce 绝不重复（每次写库都换 salt + 换密钥 + 换 nonce）。
   3.5 认证关联数据（AAD）：使用文件头字节（magic + version + kdf params + salt）
       作为 AAD，保证头部被篡改时解密失败。
   3.6 常量时间比较：头部 HMAC 校验使用 hmac.compare_digest，不用 ==。
   3.7 内存卫生：解密后的明文只在需要时存在于内存，操作完成后显式 del 引用；
       不在 __repr__ 中暴露密码字段（数据类的 password 字段设 repr=False）。
   3.8 文件权限：Linux/macOS 下创建 vault 文件后 os.chmod(path, 0o600)。
   3.9 不硬编码任何密钥、salt 或默认主密码；不提供"找回密码"后门。
4. 代码组织：至少包含 crypto.py（KDF、AEAD、文件头读写）、vault.py（凭据 CRUD 与
   序列化）、clipboard.py（剪贴板复制与定时清空）、cli.py（子命令与交互）。
   关键函数签名固定为
   derive_key(master: str, salt: bytes, iterations: int) -> bytes
   encrypt_vault(plaintext: bytes, master: str) -> bytes
   decrypt_vault(blob: bytes, master: str) -> bytes
5. 编码规范：类型注解与 docstring 齐全；异常体系自定义 VaultError 基类与
   VaultFormatError、VaultAuthError 子类；日志默认写到 stderr 且级别为 WARNING，
   --debug 才输出 DEBUG（内容仍然只含路径与操作名，不含秘密）。

【四、设计要点】

1. 数据结构与文件格式：
   1.1 vault.dat 二进制布局（小端）：
       [0:8]    magic  = b"PYVAULT1"
       [8:12]   version = 1（uint32）
       [12:16]  iterations（uint32，PBKDF2 迭代次数）
       [16:32]  salt（16 字节）
       [32:44]  nonce（12 字节）
       [44:48]  ciphertext_len（uint32）
       [48:48+n] ciphertext（AES-GCM 输出，含 16 字节 tag）
       [末尾 32 字节] header_hmac = HMAC-SHA256(前 44 字节, key=派生密钥)
   1.2 明文为 UTF-8 编码的 JSON：
       {"version": 1, "created": "...", "updated": "...",
        "entries": [{"site": "...", "username": "...", "password": "...",
                     "url": "...", "note": "...", "tags": ["..."],
                     "created": "...", "updated": "..."}]}
   1.3 Entry 数据类：site、username、password（repr=False）、url、note、
       tags: list[str]、created、updated（ISO 8601 字符串）。
2. 关键算法或流程：
   2.1 写库流程（必须分步说明以实现正确的原子性与随机性）：
       (a) 生成新 salt = secrets.token_bytes(16)；
       (b) key = PBKDF2HMAC(SHA256, length=32, salt=salt, iterations=N).derive(master.encode("utf-8"))；
       (c) nonce = secrets.token_bytes(12)；
       (d) header = magic + version + iterations + salt（44 字节），作为 AAD；
       (e) ct = AESGCM(key).encrypt(nonce, json_bytes, header)；
       (f) 组装整体，追加 HMAC-SHA256(header, key)；
       (g) 写入同目录临时文件 vault.dat.tmp → os.replace 原子替换 → chmod 0600。
   2.2 读库流程：长度校验（文件至少 80 字节）→ 校验 magic 与 version →
       解析 iterations/salt/nonce → 派生 key → hmac.compare_digest 校验尾部 HMAC
       （不一致抛 VaultFormatError）→ AESGCM.decrypt（InvalidTag 抛 VaultAuthError）
       → json.loads → Entry 列表。
   2.3 密码生成器：字符池 = 小写 + 大写 + 数字 [+ 符号]；--no-ambiguous 时移除
       0O1lI|；保证每类字符至少出现一次（先各取一个再打乱，
       打乱用 secrets.SystemRandom().shuffle）；长度范围 8~128。
   2.4 主密码强度评估：长度、字符类别数、是否为常见弱口令（内置一个 200 词的小词表）、
       是否包含用户名片段；返回 weak/medium/strong 三档。
   2.5 剪贴板清空：复制后 root.after 或 threading.Timer 20 秒后读取当前剪贴板内容，
       若与写入值相同则清空，否则放弃（避免清掉用户后来复制的东西）。
3. 接口或命令设计：
   python cli.py init [--vault PATH]
   python cli.py add --site github.com [--username U] [--password | --generate] [--tags a,b]
   python cli.py get github.com [--show] [--copy] [--json]
   python cli.py list [--tag TAG] [--sort updated]
   python cli.py set github.com --password --generate
   python cli.py rm github.com [--yes]
   python cli.py gen --length 24 --symbols --no-ambiguous
   python cli.py passwd
   python cli.py check [--json]
   python cli.py export --format csv --output out.csv
   退出码：0 成功；1 一般错误；2 参数错误；3 认证失败/文件损坏。

【五、运行方式与示例】

安装：
   pip install cryptography
运行：
   python cli.py init
   python cli.py add --site github.com --username me@example.com
   python cli.py list
   python cli.py get github.com --copy

示例一（初始化）：
   输入：python cli.py init
   输出：
   请输入主密码：
   请再次输入主密码：
   主密码强度：strong
   已创建保险箱：C:\work\vault.dat（权限 0600）

示例二（新增并查看）：
   输入：python cli.py add --site github.com --username me@example.com
   输出：
   请输入主密码：
   站点 github.com 的密码（回车则自动生成）：
   已保存：github.com（共 1 条记录）
   输入：python cli.py get github.com
   输出：
   站点：github.com
   用户名：me@example.com
   密码：************
   更新：2024-05-20T10:12:33

示例三（列表与检查）：
   输入：python cli.py list --sort site
   输出：
   SITE          USERNAME           TAGS        UPDATED
   github.com    me@example.com     work,dev    2024-05-20T10:12:33
   mail.qq.com   me@qq.com          mail        2024-05-18T09:01:02
   输入：python cli.py check
   输出：
   文件头校验：通过
   主密码验证：通过
   记录数：2
   完整性：OK

示例四（异常输入）：
   输入：python cli.py get github.com  （输入了错误的主密码）
   输出：
   请输入主密码：
   错误：主密码错误或文件已损坏
   退出码：3
   说明：程序不区分"密码错误"与"文件被篡改"，也不输出任何密文细节。

示例五（安全拒绝）：
   输入：python cli.py add --site x.com --master mypass123
   输出：
   错误：禁止通过命令行参数传递主密码（会进入 shell 历史记录），请使用交互式输入
   退出码：2

【六、验收标准】

[ ] init 创建的 vault.dat 中不含任何明文密码或站点名的可打印字符串（用 strings 检查）。
[ ] 用错误主密码解密时返回退出码 3，且不产生任何 Traceback 泄露内部信息。
[ ] 手工改动 vault.dat 任意一个字节后 check 报告失败。
[ ] 手工改动文件头（如 iterations）后解密失败（AAD 与 HMAC 双重保护生效）。
[ ] 连续两次保存同一内容，vault.dat 的 salt、nonce 与密文三者都不同。
[ ] vault.dat 中记录的 iterations 为 600000（或用户配置值）。
[ ] 用 grep/strings 搜索整个程序目录与日志文件，找不到明文主密码或站点密码。
[ ] 命令行中传入主密码参数会立即报错，退出码为 2。
[ ] gen --length 24 --symbols 生成的密码长度恰为 24 且四类字符均出现。
[ ] gen --no-ambiguous 生成的密码不含 0、O、1、l、I。
[ ] passwd 修改主密码后，旧密码无法解密，新密码可以正常 list。
[ ] add 同一站点会提示已存在，--force 可覆盖且记录数不变。
[ ] 写入失败（模拟只读目录）时原 vault.dat 内容不变。
[ ] rm 未加 --yes 时会要求二次确认，输入 n 则取消删除。
[ ] get --copy 复制的密码 20 秒后剪贴板被清空。
[ ] Linux/macOS 下 vault.dat 权限为 600。

【七、可选扩展】

1. 增加 TOTP（两步验证码）字段，用标准库 hmac + struct 实现 RFC 6238，实时显示 6 位验证码。
2. 增加 Argon2id KDF（cryptography 提供）作为 PBKDF2 的可选替代，并提供参数迁移命令。
3. 增加密码健康报告：统计重复使用的密码、超过 180 天未改的密码、强度过低的密码。
4. 增加基于文件的密钥文件（keyfile）作为第二因子（主密码 + 密钥文件双因素）。
5. 增加 GUI 界面（tkinter），保持同一加密后端。

【八、涉及知识点】

- PBKDF2-HMAC-SHA256 密钥派生、迭代次数与暴力破解成本的关系
- AES-GCM 认证加密、nonce 唯一性要求、AAD 的用途与 InvalidTag 异常语义
- secrets 模块与 os.urandom 作为密码学安全随机源（对比 random 的不适用性）
- hmac.compare_digest 常量时间比较、防时序攻击
- 二进制文件格式设计（magic/version/长度前缀）与版本兼容
- 原子写入（临时文件 + os.replace）与文件权限 chmod 0600
- getpass 无回显输入、敏感数据不落盘与日志脱敏
- 数据类 repr=False 与内存中秘密的生命周期管理
================================================================================
