================================================================================
项目编号：056                    难度等级：★★★☆☆（中型项目）
项目名称：通讯录管理系统
所属分类：个人数据管理 / 数据导入导出
建议工时：2 ~ 3 天
运行环境：Python 3.10+    第三方依赖：无（仅标准库）
================================================================================

【一、项目背景与目标】

通讯录迁移是每个人都遇到过的麻烦：手机里一份、微信里一份、公司邮箱里一份，
想合并成一份干净的联系人表，结果到处是重复项、缺字段、格式不一。手工合并
几百条联系人几乎不可能，而云端通讯录又意味着把全部社交关系交给第三方。

本项目做一个纯本地的通讯录管理器：支持联系人增删改查、分组与多标签、电话与
邮箱的多值存储（一个人三个手机号是常态）、vCard(.vcf) 与 CSV 双向导入导出，
并提供实用的查重与合并功能（按姓名+电话、按邮箱、按姓名拼音相似度）。

目标用户是需要整理个人人脉的知识工作者、需要批量导入名片数据的行政人员。
项目难点在于：多值字段的建模、vCard 3.0 规范的解析与生成、中文姓名的查重
判定（“张三”与“张 三”与“zhang san”应该被视为同一人候选项）。

【二、功能需求清单】

1. 核心功能
   1.1 联系人新增（add）：姓名必填；支持多个电话（类型：手机/家庭/工作）、
       多个邮箱（类型：个人/工作）、公司、职位、部门、生日、地址、网址、
       备注、头像路径、分组。
   1.2 联系人查询（show/list）：show 展示完整详情含全部多值字段；
       list 支持按姓名、拼音首字母、分组、标签、公司、电话尾号过滤。
   1.3 修改与删除（edit/remove）：edit 支持替换、追加、删除指定的某个电话或
       邮箱（用 --add-phone / --del-phone 指定索引或值）；remove 需 --yes 确认。
   1.4 分组与标签（group/tag）：分组为单值（一个联系人归属一个分组，如 家人/
       同事/客户/同学）；标签为多值（可加多个，如 球友、读书会、前同事）。
   1.5 查重（dedupe）：输出重复候选组及判定依据与相似度分数；
       支持 --merge 交互式合并（选择主记录、字段级取优、保留合并日志）。
   1.6 vCard 导入导出（vcard）：解析 vCard 3.0（含换行折行、BASE64 照片、
       quoted-printable 编码的中文姓名）；导出时生成兼容 iOS 与安卓的 .vcf。
   1.7 CSV 导入导出（csv）：模板化列定义，导入时列名容错（支持常见别名如
       “手机/手机号/mobile/电话”），导出 UTF-8 BOM 便于 Excel 打开。
   1.8 生日提醒（birthday）：列出未来 30 天内过生日的联系人，按剩余天数排序，
       同一人一年只提醒一次（记录提醒状态）。
   1.9 统计（stats）：联系人数、分组分布、标签 Top10、缺失字段比例
       （无电话/无邮箱/无生日的占比）、近 30 天新增数。

2. 输入与交互
   2.1 命令形如：
       `python -m contacts add -n 张三 --phone 13800138000:手机
        --phone 010-12345678:工作 --email zhang@x.com:工作 -g 同事 --tags 球友`
   2.2 电话与邮箱用“值:类型”形式传入，类型省略时默认“手机”/“个人”。
   2.3 电话归一化：去除空格、括号、连字符；中国手机号统一为 11 位；
       带国际区号的保留 `+86` 前缀；归一化后仍存一份原始输入便于核对。
   2.4 支持 `--db PATH`；支持 `--json` 输出；支持 `import --dry-run` 只预览不写库。
   2.5 支持通过 stdin 批量粘贴（`add --bulk -`），每行一个联系人简写格式
       `姓名,电话,分组,备注`。

3. 输出与展示
   3.1 list 输出：ID、姓名、分组、主电话、主邮箱、公司、标签（截断到 3 个）。
   3.2 show 输出分块：基本信息 / 电话 / 邮箱 / 分组标签 / 生日与提醒 / 时间戳。
   3.3 dedupe 输出：候选组编号、成员（ID + 姓名 + 电话 + 邮箱）、
       判定规则（如“电话相同”“邮箱相同”“姓名拼音相同且首字相同”）、
       相似度 0~1 的分数。
   3.4 中文姓名在列表中按拼音排序（不依赖第三方库，使用内置的汉字拼音表
       或按 Unicode 码位排序并明确说明局限）。

4. 异常与边界处理
   4.1 姓名为空或仅空白：拒绝写入。
   4.2 电话格式非法（含字母、长度不足 5 位）：默认拒绝并提示；--force 允许保存。
   4.3 同一联系人重复添加同一电话：拒绝该条电话，但联系人本身正常保存，
       并在输出中提示“已存在该号码，跳过”。
   4.4 vCard 文件含语法错误：跳过该条记录并计入 errors，输出错误行号与内容，
       其余记录继续导入；全部失败时退出码 1。
   4.5 vCard 编码为 quoted-printable 或 UTF-8 混合：按 CHARSET 参数与内容
       特征判断，解码失败时回退为原字符串并记录告警。
   4.6 CSV 缺少姓名列：直接报错；缺少其他列则留空并在导入报告中列出。
   4.7 删除分组：分组内联系人自动转为“未分组”，不删除联系人。
   4.8 合并两个联系人：被合并方的电话/邮箱并入主记录，重复值去重；
       写入 merge_log 记录可追溯。
   4.9 空数据库 list：输出“通讯录为空”，退出码 0。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：仅使用标准库——sqlite3、argparse、csv、json、re、quopri、
   base64、codecs、datetime、pathlib、dataclasses、difflib、unicodedata、
   logging、hashlib、textwrap。明确禁止为拼音排序引入第三方库；
   若需要拼音，必须自带一份精简映射表（放在 pinyin.py 中，覆盖常用姓与
   一级汉字）并在文档中说明覆盖范围的局限。
3. 禁止事项：禁止把多个电话拼接成一个字符串存在联系人表里（必须用
   phones 子表）；禁止在导入 vCard 时对折行规则做简化假设（必须实现
   RFC 2426 的续行规则：以空格或制表符开头的行是上一行的续行）；
   禁止使用 eval 解析 vCard 参数。
4. 代码组织：
   - `db.py` / `repository.py`：建表与 SQL 层。
   - `models.py`：Contact、Phone、Email、Group、Tag、MergeLog。
   - `norm.py`：电话、邮箱、姓名归一化与拼音首字母。
   - `vcard.py`：vCard 3.0 解析器与生成器（本项目重点，需独立测试）。
   - `csvio.py`：CSV 列名映射、导入导出。
   - `dedupe.py`：查重规则与相似度计算。
   - `merge.py`：合并逻辑与日志。
   - `cli.py`：命令行入口。
5. 编码规范：解析器函数必须对非法输入返回错误信息而不是抛异常到顶层；
   所有写库操作走事务；导入过程每 200 条提交一次并输出进度。

【四、设计要点】

1. 数据结构（SQLite 表结构）

   1.1 contacts（联系人主表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       display_name  TEXT NOT NULL          -- 展示名（如 “张三”）
       family_name   TEXT NOT NULL DEFAULT ''
       given_name    TEXT NOT NULL DEFAULT ''
       name_pinyin   TEXT NOT NULL DEFAULT ''  -- 如 'zhangsan'
       name_initial  TEXT NOT NULL DEFAULT ''  -- 如 'Z'
       nickname      TEXT NOT NULL DEFAULT ''
       company       TEXT NOT NULL DEFAULT ''
       department    TEXT NOT NULL DEFAULT ''
       job_title     TEXT NOT NULL DEFAULT ''
       birthday      TEXT NULL              -- 'YYYY-MM-DD'（年份可为 '0000' 表示未知年）
       address       TEXT NOT NULL DEFAULT ''
       website       TEXT NOT NULL DEFAULT ''
       note          TEXT NOT NULL DEFAULT ''
       avatar_path   TEXT NOT NULL DEFAULT ''
       group_id      INTEGER NULL REFERENCES groups(id) ON DELETE SET NULL
       is_favorite   INTEGER NOT NULL DEFAULT 0
       last_reminded_year INTEGER NULL      -- 生日提醒去重（记录提醒过的年份）
       created_at    TEXT NOT NULL
       updated_at    TEXT NOT NULL
       索引：idx_contacts_name(display_name)、idx_contacts_pinyin(name_pinyin)、
             idx_contacts_group(group_id)、idx_contacts_company(company)、
             idx_contacts_birthday(birthday)

   1.2 phones（电话多值表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       contact_id    INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE
       number_raw    TEXT NOT NULL          -- 用户原始输入
       number_norm   TEXT NOT NULL          -- 归一化结果（用于查重）
       type          TEXT NOT NULL DEFAULT '手机'
                     CHECK (type IN ('手机','家庭','工作','传真','其他'))
       is_primary    INTEGER NOT NULL DEFAULT 0
       label         TEXT NOT NULL DEFAULT ''
       约束：UNIQUE(contact_id, number_norm)
       索引：idx_phones_norm(number_norm)   -- 查重关键索引

   1.3 emails（邮箱多值表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       contact_id    INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE
       address       TEXT NOT NULL
       type          TEXT NOT NULL DEFAULT '个人'
                     CHECK (type IN ('个人','工作','其他'))
       is_primary    INTEGER NOT NULL DEFAULT 0
       约束：UNIQUE(contact_id, address)
       索引：idx_emails_addr(address)

   1.4 groups（分组表，单值归属）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       name          TEXT NOT NULL UNIQUE
       color         TEXT NOT NULL DEFAULT ''
       sort_order    INTEGER NOT NULL DEFAULT 0

   1.5 tags（标签表）与 contact_tags（关联表）
       tags: id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE
       contact_tags: contact_id REFERENCES contacts(id) ON DELETE CASCADE,
                     tag_id REFERENCES tags(id) ON DELETE CASCADE,
                     PRIMARY KEY (contact_id, tag_id)

   1.6 merge_log（合并日志表）
       id            INTEGER PRIMARY KEY AUTOINCREMENT
       primary_id    INTEGER NOT NULL       -- 保留的记录
       merged_id     INTEGER NOT NULL       -- 被合并删除的记录
       snapshot      TEXT NOT NULL          -- JSON：被合并记录的完整快照
       rule          TEXT NOT NULL          -- 触发合并的规则名
       score         REAL NOT NULL
       merged_at     TEXT NOT NULL

   1.7 import_log（导入日志表）
       id / source_file / source_type(vcard|csv) / imported_at /
       total_rows / inserted_rows / merged_rows / skipped_rows / errors(JSON)

   1.8 schema_version（迁移版本表）
       version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL

2. 关键算法或流程

   2.1 电话归一化 normalize_phone(raw, default_region='+86')：
       步骤一，去除所有非 `[0-9+#*]` 字符；
       步骤二，若以 `+` 开头保留国际格式；若以 `00` 开头转为 `+`；
       步骤三，长度为 11 且以 1[3-9] 开头 → 中国手机号，规范为 `+86` + 号码；
       步骤四，长度为 7~8 且无区号 → 视为本地号码，保持原样；
       步骤五，其余保留清洗后的字符串；
       步骤六，同时把 `number_raw` 原样入库，便于展示用户输入的样子。

   2.2 姓名归一化与拼音：
       归一化：去除首尾空白、全角空格与中间多余空格，得到 `display_name`。
       拼音：查 pinyin.py 中的汉字→拼音映射，首字母大写拼成 `name_pinyin`
       （如 张三 → zhangsan，name_initial = Z）。映射表未覆盖的字符跳过，
       并在 name_pinyin 末尾追加 `?` 以标识不完整，避免误判为完全相同。

   2.3 vCard 3.0 解析流程：
       步骤一，读文件并按字符集解码（优先按文件头/CHARSET 参数，
       其次尝试 utf-8、utf-8-sig、gbk）；
       步骤二，按 CRLF 或 LF 拆行，处理续行：若某行以空格或制表符开头，
       则去掉首个空白字符并拼接到上一行（RFC 2426 折行规则）；
       步骤三，定位 `BEGIN:VCARD` 与 `END:VCARD` 之间的块，忽略块外内容；
       步骤四，对每行按第一个 `:` 拆分为 名称参数 与 值，名称部分再按 `;`
       拆分为字段名与参数（TYPE、CHARSET、ENCODING）；
       步骤五，处理 ENCODING=QUOTED-PRINTABLE 用 quopri.decodestring，
       处理 ENCODING=BASE64 的 PHOTO 用 base64 解码并按需写入 avatars 目录；
       步骤六，映射字段：N/FN → 姓名，TEL → 电话（带 TYPE），EMAIL → 邮箱，
       ORG/TITLE → 公司职位，BDAY → 生日，ADR → 地址，NOTE → 备注，
       CATEGORIES → 标签；
       步骤七，N 字段按 `;` 拆为 姓;名;中间名;前缀;后缀，中文常见为
       `N:张三;;;;` 或 `N:张;三;;;`，两种都要能正确得到 display_name；
       步骤八，每条记录独立提交，失败则记录行号与原因并继续下一条。

   2.4 查重规则（按优先级执行，输出全部命中）：
       规则 R1 电话相同：phones.number_norm 完全相同，分数 1.0。
       规则 R2 邮箱相同：emails.address 小写后完全相同，分数 0.95。
       规则 R3 姓名 + 首字相同：display_name 完全相同，或 name_pinyin
       完全相同（两者其一），分数 0.85。
       规则 R4 拼音相似：difflib.SequenceMatcher 对 name_pinyin 求比值，
       比值 >= 0.85 且 name_initial 相同，分数 = 比值 * 0.8。
       规则 R5 公司 + 职位相同且姓名相似度 >= 0.6，分数 0.6。
       聚合方式：用并查集把命中的联系人合并为候选组，组内分数取最大值；
       输出时按分数降序，并在每条依据里写明是哪条规则与具体匹配值。

   2.5 合并流程 merge(primary_id, merged_id)：
       步骤一，校验两个 ID 存在且不同；
       步骤二，把被合并方的 phones/emails 逐条尝试插入主记录，
       冲突（UNIQUE 命中）则跳过并计入 duplicates_removed；
       步骤三，标签取并集；分组保留主记录的，若主记录无分组则采用被合并方的；
       步骤四，标量字段取优：空值被非空值填充（如公司、生日、备注）；
       步骤五，把被合并记录及其多值字段的完整快照写入 merge_log；
       步骤六，删除被合并记录（级联删除其多值字段）；
       步骤七，整个流程在单个事务中完成，失败全部回滚。

3. 接口或命令设计

   add -n NAME [--phone V:T ...] [--email A:T ...] [-g 分组] [--tags a,b]
       [--company] [--title] [--birthday D] [--note] [--bulk -]
   list [--group G] [--tag T] [--company C] [--initial Z] [--phone-tail 0000]
        [--limit N] [--offset M] [--json]
   show ID [ID ...] [--json]
   edit ID [--name] [--add-phone V:T] [--del-phone V] [--add-email A:T]
           [--del-email A] [--group] [--tags] [--company] [--birthday] [--note]
   remove ID [ID ...] --yes
   group add|rename|remove|list        tag add|remove|list|rename
   dedupe [--rule R1,R2] [--min-score 0.6] [--merge] [--json]
   vcard import PATH [--dry-run] [--group 导入] / vcard export PATH [--ids 1,2,3]
   csv import PATH [--dry-run] [--encoding auto] / csv export PATH [--fields ...]
   birthday [--days 30] [--mark-reminded]
   stats [--json]

   函数签名：
   def normalize_phone(raw: str) -> str
   def to_pinyin(name: str) -> tuple[str, str]
   def parse_vcard(text: str) -> tuple[list[VCardRecord], list[VCardError]]
   def render_vcard(contact: Contact, phones: list[Phone],
                    emails: list[Email]) -> str
   def find_duplicates(repo, rules: list[str], min_score: float) -> list[DupGroup]
   def merge_contacts(repo, primary_id: int, merged_id: int) -> MergeResult

【五、运行方式与示例】

安装（仅标准库）：
  cd C:\projects\100programs\056_contact_manager
  python -m contacts init

示例一（新增与查询）：
  输入：python -m contacts add -n 张三 --phone 138-0013-8000:手机
        --phone 010 1234 5678:工作 --email zhang@example.com:工作 -g 同事 --tags 球友
  输出：已新增 #1 张三（电话 2 个，邮箱 1 个，分组 同事，标签 球友）
        归一化：13800138000 → +8613800138000；010 1234 5678 → 01012345678
  输入：python -m contacts list --company 示例科技
  输出：
        ID  姓名   分组   主电话           主邮箱              公司       标签
        1   张三   同事   +8613800138000   zhang@example.com   示例科技   球友

示例二（vCard 导入与查重）：
  输入：python -m contacts vcard import contacts.vcf --dry-run
  输出：解析 128 条，可导入 120 条，疑似重复 6 条，错误 2 条
        错误示例：第 47 行 缺少 FN 与 N 字段；第 91 行 BASE64 照片解码失败
  输入：python -m contacts dedupe --min-score 0.85
  输出：
        候选组 1（分数 1.00，规则 R1 电话相同）
          #1 张三  +8613800138000  zhang@example.com
          #7 张三  +8613800138000  zs@work.com
  输入：python -m contacts dedupe --merge
  输出：交互选择主记录 [1/7] → 1；合并完成：电话 2→1（去重 1），标签 1→2，已写合并日志

示例三（CSV 导出与异常输入）：
  输入：python -m contacts csv export out\contacts.csv
  输出：已导出 120 条到 out\contacts.csv（UTF-8 BOM，18 列）
  输入：python -m contacts add -n "   "
  输出：错误：姓名不能为空                                  （退出码 2）
  输入：python -m contacts add -n 李四 --phone abc-def
  输出：错误：电话 “abc-def” 格式非法（如需强制保存请加 --force）（退出码 2）
  输入：python -m contacts csv import bad.csv
  输出：错误：缺少必需列“姓名”（文件表头：电话,备注,分组）  （退出码 2）

【六、验收标准】

[ ] 含连字符、空格、括号的电话号码归一化结果一致（138-0013-8000 与
    (138) 0013 8000 得到同一 number_norm）。
[ ] 同一联系人重复添加同一号码被 UNIQUE 约束拦住并给出明确提示。
[ ] 中文姓名能生成 name_pinyin 与首字母；映射表未覆盖字符时标注 `?` 而非静默错误。
[ ] vCard 折行（以空格开头的续行）能被正确拼接，用真实手机导出的 .vcf 验证。
[ ] quoted-printable 编码的中文姓名（如 =E5=BC=A0=E4=B8=89）能解码为“张三”。
[ ] BASE64 内嵌照片能解码并落盘，文件可正常打开。
[ ] N 字段两种常见写法（N:张三;;;; 与 N:张;三;;;）都能得到正确 display_name。
[ ] vCard 中语法错误的记录被跳过，其余记录正常导入，错误行号写入 import_log。
[ ] 导出的 .vcf 能被手机或邮件客户端成功导入（人工验证至少一次）。
[ ] CSV 导入支持列名别名（手机/手机号/mobile 均能识别为电话列）。
[ ] CSV 导出用 Excel 打开中文不乱码，列顺序稳定。
[ ] 查重规则 R1/R2/R3 分别构造样例数据，全部能被正确识别并给出正确分数。
[ ] 合并后主记录的字段取优正确（空值被填充、非空不被覆盖）。
[ ] 合并日志中的快照可完整还原被合并记录（含全部电话与邮箱）。
[ ] 删除分组后组内联系人变为“未分组”，联系人数不减少。
[ ] birthday 能列出未来 30 天内生日，且同一人同一年的重复提醒被抑制。

【七、可选扩展】

1. 支持 vCard 4.0（含 KIND、GENDER、IMPP 等字段）与 vCard 2.1 的兼容解析。
2. 增加名片二维码生成（结合 033 项目），扫码即可导入联系方式。
3. 增加“人脉地图”：按公司/城市聚合的可视化分布图。
4. 增加加密存储：用标准库 hashlib + 口令派生对数据库文件做加密备份。
5. 增加与 051 记账本联动：给“人情”分类自动关联联系人。
6. 增加 Web 只读界面（http.server 即可），局域网内在手机浏览器查看通讯录。

【八、涉及知识点】

- 关系型建模：多值属性拆表、复合唯一约束、级联删除、并查集聚合重复组。
- vCard / RFC 2426：折行续行规则、参数与值的分隔、quoted-printable 与 BASE64。
- 字符编码：UTF-8、GBK、quopri 解码、编码探测与容错策略。
- 文本归一化与模糊匹配：difflib.SequenceMatcher、相似度阈值与误报权衡。
- 拼音处理：汉字到拼音的映射表与首字母提取的局限。
- 事务与数据安全：合并操作的原子性、快照日志与可回滚设计。
- 导入导出工程化：列名别名映射、dry-run 预览、错误行隔离与报告。
- CSV 与 Excel 兼容：utf-8-sig、分隔符与引号转义规则。
- 排序与检索：索引设计、前缀查询、多条件过滤与分页。
================================================================================
