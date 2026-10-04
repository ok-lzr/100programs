# -*- coding: utf-8 -*-
"""把 data/plan.json（100 个项目的元信息）+ data/author/*.json（已编写的关卡内容）
合并，生成三样东西：

1. data/projects.json         —— 合并后的完整数据（网站的真相层）
2. 每个项目文件夹里的 README.md —— 你在写代码时要看的任务卡
3. web/data/projects.js       —— 网站直接读的数据（用 JS 变量包着，双击本地打开也能用）

用法：python tools/build.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lint_author import lint_all  # noqa: E402  任务卡体检，不过关就不生成

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "data" / "plan.json"
AUTHOR_DIR = ROOT / "data" / "author"
MERGED = ROOT / "data" / "projects.json"
WEB_DATA = ROOT / "web" / "data" / "projects.js"
PROGRESS = ROOT / "progress.json"
WEB_PROGRESS = ROOT / "web" / "progress.json"

STAR_FULL = "★"
STAR_EMPTY = "☆"


def stars(difficulty: float) -> str:
    """1.0–5.0 的难度转成五星表示，支持半星（用 ½ 表示）。"""
    full = int(difficulty)
    half = difficulty - full >= 0.5
    return STAR_FULL * full + ("½" if half else "") + STAR_EMPTY * (5 - full - (1 if half else 0))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def merge_projects() -> dict:
    plan = load_json(PLAN)
    stages = {s["id"]: s for s in plan["meta"]["stages"]}

    authors: dict[str, dict] = {}
    if AUTHOR_DIR.exists():
        for f in sorted(AUTHOR_DIR.glob("*.json")):
            d = load_json(f)
            authors[d["id"]] = d

    projects = []
    for p in plan["projects"]:
        item = dict(p)
        item["stageName"] = stages[item["stage"]]["name"]
        item["stageRange"] = stages[item["stage"]]["range"]
        a = authors.get(item["id"])
        if a:
            levels = a.get("levels", [])
            item.update({k: v for k, v in a.items() if k not in ("id",)})
            item["levelCount"] = len(levels)
            item["status"] = a.get("status", "ready")
        else:
            item["levelCount"] = 0
        projects.append(item)

    meta = dict(plan["meta"])
    meta["builtAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta["totalProjects"] = len(projects)
    meta["writtenProjects"] = sum(1 for p in projects if p["status"] == "ready")
    meta["totalLevels"] = sum(p["levelCount"] for p in projects)
    return {"meta": meta, "projects": projects}


def readme_text(p: dict) -> str:
    L: list[str] = []
    stage_line = f"{p['stageRange']} · {p['stageName']}"

    L.append(f"# {p['id']} · {p['title']}")
    L.append("")
    if p["status"] != "ready":
        L.append(f"> **任务卡还没写**（{stars(p['difficulty'])} 难度 {p['difficulty']} / 5 · {stage_line}）")
        L.append(">")
        L.append(f"> 一句话：{p.get('summary', '')}")
        L.append(">")
        L.append("> 这套练习是一个一个补的，先做已经写好的那些。网站上看得到全部 100 个的路线。")
        L.append("")
        return "\n".join(L) + "\n"

    L.append(f"> {stars(p['difficulty'])}　难度 {p['difficulty']} / 5　·　{stage_line}")
    L.append(f"> {p['hoursLine']}　·　{p['filesLine']}　·　{p['libsLine']}")
    L.append(">")
    L.append("> **规矩：这份任务卡只给思路和语法点，一行代码都没有。代码由你自己写。**")
    L.append("")
    L.append(f"**一句话**：{p['summary']}")
    L.append("")
    L.append("## 为什么做它")
    L.append("")
    L.append(p["why"])
    L.append("")
    L.append("## 做完是什么样")
    L.append("")
    L.append(p["finish"])
    L.append("")
    L.append("## 会练到的语法")
    L.append("")
    L.append("　".join(f"`{s}`" for s in p["skills"]))
    L.append("")
    if p.get("newStuff"):
        L.append(f"> {p['newStuff']}")
        L.append("")
    L.append("---")
    L.append("")
    for lv in p["levels"]:
        L.append(f"## 关卡 {lv['n']} · {lv['name']}")
        L.append("")
        L.append(f"**建议用时**：{lv['time']}")
        L.append("")
        L.append("### 做出这样就算过")
        L.append("")
        L.append(lv["goal"])
        L.append("")
        L.append("### 怎么想（步骤）")
        L.append("")
        for i, s in enumerate(lv["steps"], 1):
            L.append(f"{i}. {s}")
        L.append("")
        L.append("### 要用到的语法点")
        L.append("")
        for s in lv["syntax"]:
            L.append(f"- **{s['name']}**：{s['hint']}")
        L.append("")
        L.append("### 做完了自己检查")
        L.append("")
        for c in lv["check"]:
            L.append(f"- [ ] {c}")
        L.append("")
        if lv.get("stuck"):
            L.append("### 卡住看这里")
            L.append("")
            for s in lv["stuck"]:
                L.append(f"- {s}")
            L.append("")
        if lv.get("pitfalls"):
            L.append("### 常见坑")
            L.append("")
            for s in lv["pitfalls"]:
                L.append(f"- {s}")
            L.append("")
        L.append("---")
        L.append("")
    L.append("## 做完之后可以再试")
    L.append("")
    for i, e in enumerate(p.get("extend", []), 1):
        L.append(f"{i}. {e}")
    L.append("")
    L.append("## 打卡")
    L.append("")
    L.append(f"做完这一关，在命令行里打卡：`python tools/checkin.py {p['id']} 1`（数字是关卡号）")
    L.append("")
    L.append("打卡记录写在 `progress.json` 里，提交到仓库后网站会自动更新。网站是**只读**的，只用来给大家（包括你自己）看进度，打卡只有命令行一种方式。")
    L.append("")
    return "\n".join(L) + "\n"


def overview_text(merged: dict) -> str:
    m = merged["meta"]
    L: list[str] = []
    L.append("# 100 个 Python 项目 · 一步一步来")
    L.append("")
    L.append(f"> 给初二自学者的分关卡练习库。最后生成时间：{m['builtAt']}")
    L.append(">")
    L.append(f"> 任务卡已写好 **{m['writtenProjects']} / {m['totalProjects']}** 个，共 **{m['totalLevels']} 关**。")
    L.append("> 这份文件由 `tools/build.py` 自动生成，不要手改（要改内容就改 `data/author/*.json`）。")
    L.append("")
    L.append("## 三条规矩")
    L.append("")
    L.append("1. **任务卡只给思路，不给代码。**「语法点」是告诉你该用哪个语法，怎么写由你自己决定。")
    L.append("2. **一个项目 3~5 关，每关都能单独跑出效果。** 一关 20~40 分钟，做完一关就停下也不亏。")
    L.append("3. **单个文件不超过 300 行，一个项目最多 6 个文件。** 这是死规矩，防止又变成看不懂的大工程。")
    L.append("")
    L.append("## 五个阶段")
    L.append("")
    L.append("| 阶段 | 区间 | 这一段在练什么 | 做完能做出什么 |")
    L.append("| --- | --- | --- | --- |")
    for st in m["stages"]:
        L.append(f"| {st['name']} | {st['range']} | {st['oneLine']} | {st['outcome']} |")
    L.append("")
    L.append("难度从 1.0 平滑爬到 5.0（每 10 个项目升半颗星），中途没有回落。")
    L.append("")
    L.append("## 全部 100 个（★ = 难度，进度看网站或 `python tools/checkin.py`）")
    L.append("")
    cur_stage = None
    for p in merged["projects"]:
        if p["stage"] != cur_stage:
            cur_stage = p["stage"]
            st = next(s for s in m["stages"] if s["id"] == cur_stage)
            L.append("")
            L.append(f"### {st['name']}（{st['range']}）")
            L.append("")
            L.append("| 编号 | 难度 | 关卡 | 项目 | 一句话 |")
            L.append("| --- | --- | --- | --- | --- |")
        state = "待编写" if p["status"] != "ready" else f"{p['levelCount']} 关"
        L.append(f"| {p['id']} | {stars(p['difficulty'])} | {state} | {p['title']} | {p['summary']} |")
    L.append("")
    L.append("## 目录结构")
    L.append("")
    L.append("```")
    L.append("100programs/")
    L.append("├── 项目总览.md              # 本文件：路线图 + 100 个项目的索引（自动生成）")
    L.append("├── 怎么用.md                # 上手说明：每天怎么开始、怎么打卡、怎么上线")
    L.append("├── progress.json            # 每关做没做完（网站和打卡工具都读它）")
    L.append("├── data/")
    L.append("│   ├── plan.json            # 100 个项目的元信息：编号、目录、阶段、难度")
    L.append("│   ├── author/*.json        # 每个项目任务卡的内容源（一个项目一个文件）")
    L.append("│   └── projects.json        # 上面两份合并的结果（自动生成）")
    L.append("├── tools/")
    L.append("│   ├── build.py             # 生成 README.md、网站数据、这份总览")
    L.append("│   ├── checkin.py           # 命令行打卡")
    L.append("│   └── seed_plan.py         # 一次性脚本：当初从旧版总览生成 plan.json（不用再跑）")
    L.append("├── web/                     # 进度网站（纯原生 HTML/CSS/JS，发布这个文件夹）")
    L.append("├── 001_temp_unit_converter/")
    L.append("│   └── README.md            # 任务卡（自动生成）")
    L.append("├── ...")
    L.append("└── _旧版备份/               # 旧的那 100 份工程师级需求书，留着以防你想回头看看")
    L.append("```")
    L.append("")
    L.append("## 改了内容之后")
    L.append("")
    L.append("```")
    L.append("python tools/build.py      # 重新生成所有 README.md + 网站数据 + 这份总览")
    L.append("python tools/checkin.py    # 看当前进度")
    L.append("```")
    L.append("")
    return "\n".join(L) + "\n"


def main() -> None:
    errors, warns = lint_all()
    if warns:
        print(f"任务卡体检：{len(warns)} 条警告（不拦）")
    if errors:
        print(f"\n任务卡体检没通过，先修这些再来生成（共 {len(errors)} 条）：")
        for e in errors[:25]:
            print("  ✗ " + e)
        if len(errors) > 25:
            print(f"  …还有 {len(errors) - 25} 条，跑 python tools/lint_author.py 看全部")
        sys.exit(1)

    merged = merge_projects()

    MERGED.parent.mkdir(parents=True, exist_ok=True)
    MERGED.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (ROOT / "项目总览.md").write_text(overview_text(merged), encoding="utf-8", newline="\n")

    written = 0
    for p in merged["projects"]:
        d = ROOT / p["dir"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "README.md").write_text(readme_text(p), encoding="utf-8", newline="\n")
        if p["status"] == "ready":
            written += 1

    WEB_DATA.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
    WEB_DATA.write_text(
        "// 这个文件由 tools/build.py 自动生成，不要手改。\n"
        "// 数据源头是 data/plan.json 和 data/author/*.json\n"
        f"window.DECK_DATA = {payload};\n",
        encoding="utf-8",
        newline="\n",
    )

    if PROGRESS.exists():
        WEB_PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        text = PROGRESS.read_text(encoding="utf-8")
        WEB_PROGRESS.write_text(text, encoding="utf-8", newline="\n")
        # 一份包成 JS 变量的副本：直接双击 index.html 打开时浏览器不允许读本地文件，
        # 有这份内置副本，页面至少能显示上次生成的进度。
        payload = json.dumps(json.loads(text), ensure_ascii=False, separators=(",", ":"))
        (WEB_DATA.parent / "progress.js").write_text(
            "// 这个文件由 tools/build.py 自动生成，不要手改（源头是 progress.json）。\n"
            f"window.DECK_PROGRESS = {payload};\n",
            encoding="utf-8",
            newline="\n",
        )

    m = merged["meta"]
    print(f"已生成 data/projects.json     ：{m['totalProjects']} 个项目，其中 {m['writtenProjects']} 个任务卡已写好")
    print(f"已生成 web/data/projects.js   ：网站数据")
    print(f"已刷新 100 个项目文件夹里的 README.md")
    if PROGRESS.exists():
        print(f"已同步 progress.json -> web/progress.json")


if __name__ == "__main__":
    main()
