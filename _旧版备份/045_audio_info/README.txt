================================================================================
项目编号：045                    难度等级：★★★☆☆（小型项目）
项目名称：音频信息与转码助手
所属分类：命令行工具 / 音视频处理
建议工时：5 ~ 7 小时
运行环境：Python 3.10+    第三方依赖：mutagen >= 1.47（pip install mutagen）
                         外部程序：ffmpeg（转码功能需要，需在 PATH 中）
================================================================================

【一、项目背景与目标】

攒了几年的音乐库、播客录音、会议录音，往往是一团乱：文件名是 01.mp3、录音(1).m4a，
标签信息空白或写着乱码，比特率从 64kbps 到 320kbps 混杂，时长参差不齐。想在车上或播放器里
按“艺术家 - 标题”的顺序听，几乎得手工改上百个文件名。

本项目先解决“看得见”的问题：扫描一个目录，读出每个音频文件的时长、采样率、声道数、比特率、
编码格式以及 ID3/Vorbis/MP4 标签，输出成表格或 CSV，让整个音乐库的质量一目了然。再解决
“改得动”的问题：按标签规范化重命名文件（001 - 艺术家 - 标题.mp3），批量写入统一的公共标签，
以及调用 ffmpeg 批量转码为 mp3/m4a/ogg/flac 并控制码率。

目标用户是喜欢本地音乐库的人、播客剪辑者和需要归档会议录音的职场人。做成之后，可以用一条
命令把 500 个文件的标签导出成 CSV 在 Excel 里批量编辑，再导回写入文件，实现“表格化整理音乐
库”的工作流。程序本身不下载任何音频，也不绕过版权保护，仅处理用户自己的本地文件。

【二、功能需求清单】

1. 核心功能
   1.1 音频信息读取：用 mutagen.File(path) 自动识别格式，读取 info.length（秒）、
       info.sample_rate（Hz）、info.channels、info.bitrate（bps）、info.codec（m4a/aac 有）、
       info.bits_per_sample（flac/wav 有）。时长格式化为 mm:ss 或 h:mm:ss。
   1.2 标签读取：统一映射为规范键 title、artist、album、albumartist、tracknumber、discnumber、
       date、genre、comment、composer。MP3 走 ID3 帧（TIT2/TPE1/TALB/TRCK/TDRC/TCON），
       FLAC/OGG 走 Vorbis Comment 小写键，M4A 走 MP4 原子（\xa9nam/\xa9ART/\xa9alb/trkn），
       WAV 走 ID3 或 INFO 块，WMA 走 ASF。用 hasattr 与 try/except 做能力探测，缺失返回 None。
   1.3 内嵌封面检测：--cover 输出是否有 APIC/PICTURE/covr 封面、封面 MIME 与字节大小；
       --extract-cover 把封面导出为 cover_<文件名>.jpg。
   1.4 目录扫描与筛选：递归扫描 .mp3/.m4a/.aac/.flac/.ogg/.opus/.wav/.wma/.aiff；
       --min-duration 60 --max-duration 3600 按时长过滤；--no-tags 只列出没有标题或艺术家的文件。
   1.5 转码：调用 ffmpeg 子进程，--to mp3|m4a|ogg|opus|flac|wav，--bitrate 320k（对 mp3/m4a/
       ogg/opus 生效），--sample-rate 44100，--channels 2，--keep-tags 让 ffmpeg 的
       -map_metadata 0 保留标签，--copy-cover 保留内嵌封面（mp3 用 -c:v copy）。
   1.6 规范化重命名：--rename --pattern '{track:02d} - {artist} - {title}'，
       非法字符（\ / : * ? " < > | 与控制字符）替换为下划线，Windows 保留名（CON、PRN、AUX、
       NUL、COM1~9、LPT1~9）自动加前缀 _，长度截断到 200 字节以内。
   1.7 批量写标签：--set artist=张三 --set album=播客合集 --from-csv meta.csv
       （CSV 首列匹配文件名，其余列为要写入的键值）。
   1.8 音量规范化：--normalize 调用 ffmpeg 的 loudnorm 滤镜（I=-16 LUFS, TP=-1.5, LRA=11），
       两遍分析模式可选（--two-pass），输出日志中给出测得响度。

2. 输入与交互
   2.1 命令行：python audio_tool.py info ./music --recursive --format table。
   2.2 目录模式与文件列表模式均支持：可传目录（递归/不递归）或直接传多个文件路径。
   2.3 --interactive 逐条确认写标签与重命名，显示“旧值 -> 新值”并等待 y/n/q。
   2.4 未安装 ffmpeg 时运行 info 功能仍正常，执行转码时给出明确安装提示与各平台安装命令。

3. 输出与展示
   3.1 表格模式列：文件名、格式、时长、码率、采样率、声道、标题、艺术家、专辑。
       列宽按内容自适应（用 unicodedata.east_asian_width 计算中文显示宽度，保证对齐）。
   3.2 CSV 模式列固定并附文件绝对路径，编码 utf-8-sig。
   3.3 汇总行：共 386 个文件，总时长 27:14:06，平均码率 218 kbps，其中 42 个文件缺少标题标签。
   3.4 转码进度：每个文件一行，末尾输出“成功 40，跳过 3，失败 2，总耗时 5m12s”。
   3.5 --log-file run.log 记录全部操作（写标签、重命名、转码命令行），便于回溯。

4. 异常与边界处理
   4.1 文件无法被 mutagen 识别（MutagenError 或返回 None）：记为 unsupported，
       在汇总中单列，不中断整批。
   4.2 时长信息缺失（部分 WAV 或流式文件）：显示“未知”并排除在总时长统计外。
   4.3 标签值为非 ASCII 的 ID3v1 乱码：检测到解码错误时用 latin-1 回退并提示“疑似编码错误”。
   4.4 ffmpeg 不存在：--to 时检查 shutil.which("ffmpeg")，缺失则报错并给出安装说明，退出码 1。
   4.5 ffmpeg 返回非 0：捕获 CalledProcessError，输出 stderr 的最后 20 行，记为该文件失败。
   4.6 目标文件已存在：默认跳过；--overwrite 覆盖；--suffix _converted 追加后缀避免冲突。
   4.7 重命名后文件名与原文件相同（标签未变）：跳过并计数，不产生无意义操作。
   4.8 文件名含 emoji 或特殊符号：重命名后仍可被 mutagen 正常读取，否则回滚并记录。
   4.9 目标格式与源格式相同且无参数变更：提示“无需转码”并跳过，除非加 --force-reencode。

【三、技术要求与约束】

1. 语言与版本：Python 3.10 及以上。
2. 允许使用的库：mutagen（音频元数据）；标准库 argparse、pathlib、subprocess、shutil、csv、
   json、logging、re、unicodedata、dataclasses、time、os。
3. 外部依赖：ffmpeg（转码与响度规范化必需，不在 Python 依赖内），需在 README 给出
   Windows（winget install Gyan.FFmpeg / scoop install ffmpeg）、macOS（brew install ffmpeg）、
   Linux（apt install ffmpeg）的安装方式，并说明 ffprobe 随包提供。
4. 禁止事项：禁止使用 youtube-dl 等下载工具；禁止绕过 DRM；禁止 shell=True 拼接命令
   （必须用参数列表调用 subprocess.run，避免文件名注入）；禁止丢弃用户的原始文件；禁止在
   未给 --apply 时执行重命名或写标签（默认 dry-run 预览）。
5. 代码组织：
   - tags_map.py：规范键与各格式原生键的映射表，get_tag(tags, key, fmt) 读取适配器。
   - audio_info.py：read_info(path) -> AudioMeta，含标签与封面探测。
   - transcode.py：build_ffmpeg_args(meta, opts) -> list[str]、run_transcode(...) -> TranscodeResult。
   - rename.py：sanitize(name, platform) -> str、build_new_name(meta, pattern) -> str。
   - report.py：终端表格渲染、CSV/JSON 导出、汇总统计。
   - cli.py：参数与动作分发。
6. 编码规范：类型注解完整；ffmpeg 命令行在 --verbose 时以列表形式打印（便于复制复现）；
   所有时长内部以 float 秒存储，只在渲染时格式化；日志中不记录文件内容，仅记录路径与操作。

【四、设计要点】

1. 数据结构：
   AudioMeta：path(Path)、format(str)、codec(str|None)、duration(float|None)、
   bitrate(int|None)、sample_rate(int|None)、channels(int|None)、bits_per_sample(int|None)、
   tags(dict[str, str])、track(int|None)、disc(int|None)、has_cover(bool)、
   cover_mime(str|None)、cover_bytes(int)、size_bytes(int)、mtime(float)。
   TranscodeOptions：target(str)、bitrate(str)、sample_rate(int|None)、channels(int|None)、
   keep_tags(bool)、copy_cover(bool)、overwrite(bool)、suffix(str)、normalize(bool)、
   two_pass(bool)、extra_args(list[str])。
   TranscodeResult：src、dst、status(ok|skip|failed)、reason、elapsed_ms、cmd(list[str])。

2. 关键算法或流程：
   2.1 标签读取适配：先 f = mutagen.File(p)（easy=True 可简化，但会丢帧信息，本项目用
       easy=False 自己映射）；按 isinstance 判断类型：
       ID3 -> tags.get("TIT2")，取值用 str(frame) 或 frame.text[0]；
       VCFLACDict / VComment -> tags.get("title")；
       MP4Tags -> tags.get("\xa9nam")，trkn 是 [(号, 总数)] 元组；
       ASFTags -> tags.get("Title")。
       统一在 get_tag() 内 try/except (KeyError, IndexError, UnicodeDecodeError)。
   2.2 时长格式化：total = int(round(seconds))；若 total >= 3600 输出 H:MM:SS，否则 MM:SS。
   2.3 中英文对齐：显示宽度 = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1
       for c in text)，补齐空格时按该宽度计算，避免中文列错位。
   2.4 ffmpeg 参数装配：基础 ["ffmpeg", "-hide_banner", "-nostdin", "-y" or "-n",
       "-i", src]；音频编码按目标格式选择 -c:a libmp3lame / aac / libvorbis / libopus /
       flac / pcm_s16le；码率 -b:a；采样率 -ar；声道 -ac；标签 -map_metadata 0；
       封面 -map 0:v -c:v copy（仅在源有封面且目标支持时）；响度 loudnorm=I=-16:TP=-1.5:LRA=11。
       输出路径放在参数最后。
   2.5 转码执行：subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
       errors="replace", timeout=1800)；返回码非 0 时取 stderr 末段作为 reason；
       用 time.perf_counter() 计时。
   2.6 两遍响度：第一遍跑 -af loudnorm=print_format=json -f null - 解析 stderr 中的 JSON
       得到 measured_I 等值，第二遍用 measured_* 参数重跑，实测值写入日志。
   2.7 重命名占位符：用 string.Formatter().parse 解析 pattern 中的字段名，只允许白名单
       {track} {disc} {artist} {album} {title} {date} {genre} {ext} {seq}，未知字段报错并
       给出可用字段列表；格式化时对缺失值用“未知”填充或按 --skip-missing 跳过该文件。

3. 接口设计：
   python audio_tool.py info PATH... [--recursive] [--format table|csv|json]
     [--output FILE] [--cover] [--extract-cover] [--min-duration N] [--max-duration N]
     [--no-tags] [--all]
   python audio_tool.py rename PATH... [--pattern '...'] [--recursive] [--apply]
     [--skip-missing] [--platform auto|windows|posix]
   python audio_tool.py tag PATH... [--set key=value]... [--from-csv FILE] [--apply]
   python audio_tool.py convert PATH... --to mp3 [--bitrate 320k] [--sample-rate 44100]
     [--channels 2] [--keep-tags] [--copy-cover] [--normalize] [--two-pass]
     [--suffix _converted] [--overwrite] [--force-reencode] [--outdir DIR] [--jobs 1]
   核心函数：read_info(path: Path) -> AudioMeta
             build_ffmpeg_args(src: Path, dst: Path, opts: TranscodeOptions) -> list[str]

【五、运行方式与示例】

1. 安装依赖与检查 ffmpeg：
   pip install "mutagen>=1.47"
   ffmpeg -version
   Windows: winget install Gyan.FFmpeg    macOS: brew install ffmpeg
   Linux:   sudo apt update && sudo apt install -y ffmpeg

2. 扫描音乐库并导出 CSV：
   python audio_tool.py info D:\Music --recursive --format csv --output library.csv
   输出：已扫描 386 个文件，不支持 2 个；总时长 27:14:06；平均码率 218 kbps；
         42 个文件缺少标题标签；已写入 library.csv

3. 规范化重命名（先预览后执行）：
   python audio_tool.py rename ./podcast --pattern '{track:02d} - {artist} - {title}' --recursive
   输出：录音(1).m4a -> 01 - 张三 - 第 1 期 什么是复利.m4a
         录音(2).m4a -> 02 - 张三 - 第 2 期 通胀与利率.m4a
         预览完成 2 个，加 --apply 执行
   python audio_tool.py rename ./podcast --pattern '{track:02d} - {artist} - {title}' \
     --recursive --apply
   输出：已重命名 2 个文件，跳过 0 个，失败 0 个（日志：run.log）

4. 批量转码为 192k 的 m4a 并规范化音量：
   python audio_tool.py convert ./meetings --recursive --to m4a --bitrate 192k
     --normalize --keep-tags --outdir ./normalized
   输出：[1/12] ok  会议0812.wav -> normalized/会议0812.m4a (48.2 MB -> 5.9 MB, 42.1s)
         [2/12] skip 会议0813.m4a 目标已存在
         成功 10，跳过 1，失败 1，总耗时 5m12s

5. 异常示例：未安装 ffmpeg
   python audio_tool.py convert ./a.mp3 --to flac
   输出：错误：未找到 ffmpeg，请先安装后重试：
         Windows: winget install Gyan.FFmpeg   macOS: brew install ffmpeg
         Linux: sudo apt install ffmpeg（退出码 1）

6. 异常示例：pattern 含未知字段
   python audio_tool.py rename ./music --pattern '{artist} - {titel}'
   输出：错误：未知占位符 {titel}，可用字段：track disc artist album title date genre ext seq
         （退出码 2）

【六、验收标准】

[ ] info 对 mp3/flac/m4a/ogg/wav 五种格式都能读出时长，与播放器显示误差不超过 0.5 秒。
[ ] 码率、采样率、声道数三项数值与 ffprobe 输出一致（抽样 10 个文件比对）。
[ ] ID3 中文标签（TIT2/TPE1）在表格中正确显示，不出现乱码或问号。
[ ] 含内嵌封面的 MP3，--cover 报告封面 MIME 与字节大小；--extract-cover 导出的 JPG 可打开。
[ ] 表格模式下中文标题与英文标题混排时列仍对齐（每列起始位置一致）。
[ ] CSV 导出可用 Excel 打开且列内容无错位。
[ ] rename 不带 --apply 时文件系统完全不变（比对目录快照）。
[ ] rename 遇到 CON、a:b?c 等非法名能正确替换，生成的文件在 Windows 上可创建。
[ ] 转码 mp3 -> m4a 后时长误差 < 1 秒，标签（标题/艺术家）保留完整。
[ ] --copy-cover 转码后新文件仍带封面（用 mutagen 读 APIC/covr 验证）。
[ ] --normalize 后测得整体响度在 -16 ± 1 LUFS 区间内（用 ffmpeg loudnorm 复测）。
[ ] 目标文件存在且未加 --overwrite 时全部跳过，源文件未被修改。
[ ] ffmpeg 对某个文件报错时其余文件继续处理，失败原因写入日志并可读。
[ ] 无 ffmpeg 环境下 info/rename 功能全部正常，只有 convert 报错。
[ ] 处理文件名含空格、中文、emoji 的文件不出现 shell 解析错误（验证未使用 shell=True）。

【七、可选扩展】

1. 增加 --jobs N 用 ThreadPoolExecutor 并行转码（ffmpeg 是外部进程，IO 与 CPU 都有收益）。
2. 增加 --from-csv 回写标签，形成“导出-表格编辑-导入”的完整工作流。
3. 增加静音检测（ffmpeg silencedetect）与自动切分长录音为多段。
4. 生成音乐库 HTML 报告：按时长/码率分布绘制纯 CSS 条形图，点击数可跳转本地文件。
5. 支持 ReplayGain 标签写入（用 mutagen 的 ID3 TXXX:replaygain_track_gain）。

【八、涉及知识点】

- mutagen 的格式抽象：File() 自动探测、ID3、Vorbis Comment、MP4、ASF、WAVE 标签类差异。
- 音频基础参数：采样率、位深、声道、比特率、CBR/VBR 与有损/无损格式的区别。
- subprocess.run 的参数列表调用、stdout/stderr 捕获、超时与编码处理。
- ffmpeg 常用参数：-c:a、-b:a、-ar、-ac、-map_metadata、-map 0:v、loudnorm 滤镜。
- 文件名合法性：各操作系统保留字符与 Windows 保留设备名。
- Unicode 东亚字符宽度计算与终端等宽对齐技巧。
- string.Formatter 自定义占位符解析与白名单校验。
- 批处理任务的状态机设计（ok/skip/failed）与可回溯日志。
================================================================================
