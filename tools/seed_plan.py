# -*- coding: utf-8 -*-
"""一次性脚本：从旧版总览里抽出 100 个项目的编号 / 目录名 / 标题 / 一句话用途，
补上新的阶段划分与难度，生成 data/plan.json。

之后 plan.json 就是维护对象，这个脚本不用再跑（留着是为了说明 plan.json 从哪来）。
用法：python tools/seed_plan.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD = ROOT / "_旧版备份" / "项目总览.md"
OUT = ROOT / "data" / "plan.json"

# 新的五阶段：编号区间不变（每 20 个一段），难度重排（001 最简单，100 最难）
STAGES = [
    {
        "id": "s1",
        "name": "找回手感",
        "range": "001–020",
        "from": 1,
        "to": 20,
        "oneLine": "前 10 个把 print / input / if / for / while / 列表 / 字典 / 函数 / 读写文件 复习一遍；后 10 个马上用它管自己电脑上的文本和文件",
        "outcome": "能独立写出 100–150 行、跑起来像样的小程序",
        "why": "基础不是忘了，是生锈了。用做小成品的方式复习，比翻课本快得多。",
    },
    {
        "id": "s2",
        "name": "联网与窗口",
        "range": "021–040",
        "from": 21,
        "to": 40,
        "oneLine": "联网取公开数据、哈希与古典密码、二维码条码、Tkinter 窗口与第一个自己的界面",
        "outcome": "做出双击就能打开、能截图发给同学的小程序",
        "why": "程序从「只有你看见」变成「别人也能看见」，这是最容易上瘾的一段。",
    },
    {
        "id": "s3",
        "name": "素材与数据",
        "range": "041–060",
        "from": 41,
        "to": 60,
        "oneLine": "图片/PDF/音频处理、文件监控与系统小工具，再到 SQLite 存自己的记账、习惯、藏书数据",
        "outcome": "能处理真实素材、把数据存下来并且下次还能读出来",
        "why": "真实世界的输入是乱的（图片、PDF、日志），这一阶段专门练「把乱的东西收拾干净」。",
    },
    {
        "id": "s4",
        "name": "采集与网站",
        "range": "061–080",
        "from": 61,
        "to": 80,
        "oneLine": "抓公开数据、做报表与图表、Flask 写自己的网站与接口、让程序定时自己跑",
        "outcome": "做出能发链接给别人看的网页或数据报告",
        "why": "从这里开始，你的程序开始跟外面的世界来回打交道。",
    },
    {
        "id": "s5",
        "name": "完整作品",
        "range": "081–100",
        "from": 81,
        "to": 100,
        "oneLine": "多文件工程、数据库设计、前后端配合、备份与监控，以及一个能拿得出手的完整项目",
        "outcome": "写进作品集、给同学用、拿去比赛或面试都不心虚的作品",
        "why": "不再是单个文件的小脚本，而是别人能装、能用、能给你提意见的成品。",
    },
]

# 每个项目的难度（1.0–5.0，允许 .5），按编号平滑爬升，肉眼不回落
def difficulty_of(idx: int) -> float:
    if idx <= 10:
        return 1.0
    if idx >= 91:
        return 5.0
    raw = 1.0 + 4.0 * (idx - 1) / 99.0
    return round(raw * 2) / 2


ROW = re.compile(r"^\|\s*(\d{3})\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")


def main() -> None:
    rows: dict[str, dict[str, str]] = {}
    for line in OLD.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if m:
            num, folder, title, desc = m.groups()
            rows[num] = {"dir": folder, "title": title, "desc": desc}

    if len(rows) != 100:
        raise SystemExit(f"解析到 {len(rows)} 行项目，期望 100 行，检查旧总览格式")

    projects = []
    for i in range(1, 101):
        num = f"{i:03d}"
        r = rows[num]
        stage = next(s for s in STAGES if s["from"] <= i <= s["to"])
        projects.append(
            {
                "id": num,
                "dir": r["dir"],
                "title": r["title"],
                "stage": stage["id"],
                "difficulty": difficulty_of(i),
                "summary": r["desc"],  # 旧版一句话用途，等正式编写时改写
                "status": "planned",
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "meta": {
            "title": "100 个 Python 项目 · 一步一步来",
            "subtitle": "给初二自学者的分关卡练习库",
            "version": "2.0",
            "stages": STAGES,
        },
        "projects": projects,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成 {OUT}（{len(projects)} 个项目）")


if __name__ == "__main__":
    main()
