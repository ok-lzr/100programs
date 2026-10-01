# 100 PROGRAMS · 100 个 Python 项目，一步一步来

给初二自学者的分关卡练习库。每个项目拆成 3~5 关，**任务卡只给思路和语法点，一行代码都不给**——代码自己写。

- 📊 **进度网站**：`web/`（未来 HUD 风格，纯原生 HTML / CSS / JS，无依赖）
- 🗺 **路线图与索引**：[项目总览.md](项目总览.md)
- 🚀 **上手说明**：[怎么用.md](怎么用.md)

## 现状

| 项目 | 数量 |
| --- | --- |
| 项目总数 | 100 |
| 任务卡已写好 | 10（001~010，复习型） |
| 已写好的关卡 | 40 |

剩下的 90 个按批次补，路线和难度已经全部排好（难度从 1.0 平滑爬到 5.0，每 10 个项目升半颗星，中途不回落）。

## 快速开始

```bash
# 1. 看自己现在该做哪一关
python tools/checkin.py

# 2. 打开任务卡，开始写代码
#    001_temp_unit_converter/README.md

# 3. 做完一关就打卡
python tools/checkin.py 001 1
```

本地预览网站（`web` 文件夹里）：

```bash
python -m http.server 8000
# 然后浏览器打开 127.0.0.1:8000
```

## 目录结构

```
100programs/
├── 项目总览.md          路线图 + 100 个项目的索引（由 tools/build.py 生成）
├── 怎么用.md            上手说明
├── progress.json        每关做没做完（网站和打卡工具都读它）
├── data/
│   ├── plan.json        100 个项目的元信息：编号、目录、阶段、难度
│   ├── author/*.json    任务卡内容源，一个项目一个文件
│   ├── 写法规范.md       任务卡的写法规矩（补新项目照这个写）
│   └── projects.json    上面几份合并的结果（自动生成）
├── tools/
│   ├── build.py         生成 100 份 README.md + 网站数据 + 项目总览.md
│   ├── lint_author.py   任务卡体检：关卡数、每关六个部分、不许混进代码
│   ├── checkin.py       命令行打卡
│   └── seed_plan.py     一次性脚本（当初生成 plan.json 用，不必再跑）
├── web/                 进度网站，发布这个文件夹
├── NNN_xxx/             每个项目一个文件夹，里面有自动生成的 README.md 任务卡
└── _旧版备份/           最早那 100 份「工程师级需求书」，留档
```

## 内容怎么改

任务卡的正文都在 `data/author/*.json` 里（一个项目一个文件），写法看 [data/写法规范.md](data/写法规范.md)，改完跑：

```bash
python tools/lint_author.py   # 先体检：关卡数、每关六个部分、有没有混进代码
python tools/build.py         # 体检不过关会拒绝生成
```

`build.py` 会重新生成所有 `README.md`、网站数据和 `项目总览.md`，所以网站和任务卡永远不会对不上。

## 部署

推到 GitHub → Settings → Pages → Source 选 **GitHub Actions**。`.github/workflows/pages.yml` 会把 `web/` 自动发布出去，之后每次 `git push` 都会更新。要挂 `ok-lzr.us.ci` 的子域名，在 Pages 里填 Custom domain，再去 DNS 加一条 CNAME。
