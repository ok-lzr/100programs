# -*- coding: utf-8 -*-
"""打卡工具：在命令行里勾掉某一关，并把结果同步给网站。

用法：
    python tools/checkin.py              # 看总进度
    python tools/checkin.py 001          # 看 001 的四关分别是完成还是没完成
    python tools/checkin.py 001 2        # 把 001 的第 2 关翻一下（没完成 -> 完成，完成 -> 没完成）
    python tools/checkin.py 001 2 3      # 一次翻两关
    python tools/checkin.py 001 --all    # 001 全部标成已完成
    python tools/checkin.py 001 --reset  # 001 全部清空

每勾上一关都会记下完成时间，网站上的时间线就是从这里来的。
改完之后刷新网页即可看到（本地打开时按 Ctrl+F5）。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRESS = ROOT / "progress.json"
WEB_DIR = ROOT / "web"
MERGED = ROOT / "data" / "projects.json"

NOTE = "每关做没做完 + 完成时间。levels 里第 1 个是第 1 关；times 跟它一一对应，没做完就是空字符串。"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def load_projects() -> dict:
    if not MERGED.exists():
        sys.exit("找不到 data/projects.json，先运行：python tools/build.py")
    data = json.loads(MERGED.read_text(encoding="utf-8"))
    return {p["id"]: p for p in data["projects"]}


def entry_of(raw, n: int) -> dict:
    """把某一项记录统一成 {"levels": [...], "times": [...]}，兼容旧的纯数组写法。"""
    levels: list[bool] = []
    times: list[str] = []
    if isinstance(raw, list):
        levels = [bool(x) for x in raw]
    elif isinstance(raw, dict):
        levels = [bool(x) for x in raw.get("levels", [])]
        times = [str(x) for x in raw.get("times", [])]
    levels = (levels + [False] * n)[:n]
    times = (times + [""] * n)[:n]
    for i, ok in enumerate(levels):
        if not ok:
            times[i] = ""
    return {"levels": levels, "times": times}


def load_progress() -> dict:
    if PROGRESS.exists():
        d = json.loads(PROGRESS.read_text(encoding="utf-8"))
        d.setdefault("progress", {})
        d["version"] = 2
        return d
    return {"version": 2, "updated": "", "note": NOTE, "progress": {}}


def save_progress(d: dict) -> None:
    d["version"] = 2
    d["updated"] = now()
    d["note"] = NOTE
    text = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
    PROGRESS.write_text(text, encoding="utf-8", newline="\n")
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    (WEB_DIR / "progress.json").write_text(text, encoding="utf-8", newline="\n")
    payload = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    (WEB_DIR / "data").mkdir(parents=True, exist_ok=True)
    (WEB_DIR / "data" / "progress.js").write_text(
        "// 这个文件由 tools/build.py 自动生成，不要手改（源头是 progress.json）。\n"
        f"window.DECK_PROGRESS = {payload};\n",
        encoding="utf-8",
        newline="\n",
    )


def flag(ok: bool) -> str:
    return "✅" if ok else "⬜"


def show_all(projects: dict, d: dict) -> None:
    total = done = 0
    print("编号  进度                 状态      项目")
    print("-" * 66)
    for pid, p in projects.items():
        n = p.get("levelCount", 0)
        if n == 0:
            print(f"{pid}  {'任务卡待编写':<18} {'—':<8} {p['title']}")
            continue
        e = entry_of(d["progress"].get(pid), n)
        done += sum(e["levels"])
        total += n
        marks = "".join(flag(x) for x in e["levels"])
        state = "已完成" if all(e["levels"]) else ("进行中" if any(e["levels"]) else "没开始")
        print(f"{pid}  {marks}  {state:<8} {p['title']}")
    print("-" * 66)
    print(f"总进度：{done} / {total} 关")
    lasts = [t for pid in d["progress"] for t in entry_of(d["progress"][pid], 99)["times"] if t]
    if lasts:
        print(f"最近一次打卡：{max(lasts)}")


def show_one(projects: dict, d: dict, pid: str) -> None:
    p = projects[pid]
    n = p.get("levelCount", 0)
    print(f"{pid} · {p['title']}　（{n} 关，难度 {p['difficulty']} / 5）")
    if n == 0:
        print("  任务卡还没写。")
        return
    e = entry_of(d["progress"].get(pid), n)
    for i in range(n):
        name = p["levels"][i]["name"]
        when = f"　{e['times'][i]}" if e["times"][i] else ""
        print(f"  {flag(e['levels'][i])} 第 {i + 1} 关 · {name}{when}")


def main() -> None:
    args = list(sys.argv[1:])
    projects = load_projects()
    d = load_progress()

    if not args:
        show_all(projects, d)
        return

    pid = args[0].zfill(3)
    if pid not in projects:
        sys.exit(f"没有编号为 {pid} 的项目。用 python tools/checkin.py 看全部编号。")

    n = projects[pid].get("levelCount", 0)
    if n == 0:
        sys.exit(f"{pid} 的任务卡还没写，没法打卡。")

    rest = args[1:]
    if not rest:
        show_one(projects, d, pid)
        return

    e = entry_of(d["progress"].get(pid), n)

    if "--all" in rest:
        e = {"levels": [True] * n, "times": [(e["times"][i] or now()) for i in range(n)]}
    elif "--reset" in rest:
        e = {"levels": [False] * n, "times": [""] * n}
    else:
        for token in rest:
            if not token.isdigit():
                sys.exit(f"不认识参数 {token}（关卡号应该是数字，比如 1）")
            idx = int(token) - 1
            if not 0 <= idx < n:
                sys.exit(f"{pid} 只有 {n} 关，没有第 {token} 关。")
            if e["levels"][idx]:
                e["levels"][idx] = False
                e["times"][idx] = ""
            else:
                e["levels"][idx] = True
                e["times"][idx] = now()

    d["progress"][pid] = e
    save_progress(d)
    show_one(projects, d, pid)
    print("\n已保存。网站刷新一下就能看到。")


if __name__ == "__main__":
    main()
