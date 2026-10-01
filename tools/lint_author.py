# -*- coding: utf-8 -*-
"""任务卡体检：把「这套练习的规矩」变成能跑的断言。

规矩来自用户的要求：
  · 每个项目 3~5 个关卡
  · 每关必须有：做出什么样才算过 / 怎么想 / 语法点 / 自检 / 卡住看这里 / 常见坑
  · 任务卡里不能出现能直接跑的代码（只给思路和语法点）
  · 难度曲线不回落，100 个项目编号连续

用法：
    python tools/lint_author.py            # 检查全部
    python tools/lint_author.py 001 002    # 只查指定项目
    python tools/lint_author.py --quiet    # 只报问题

build.py 会调用它：有错误就拒绝生成，避免坏内容流进 100 份 README 和网站。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "data" / "plan.json"
AUTHOR_DIR = ROOT / "data" / "author"

PROJECT_REQUIRED = [
    "id", "title", "summary", "why", "finish", "skills",
    "filesLine", "hoursLine", "libsLine", "levels", "extend", "status",
]
LEVEL_REQUIRED = ["n", "name", "time", "goal", "steps", "syntax", "check", "stuck", "pitfalls"]

MIN_LEVELS, MAX_LEVELS = 3, 5
MIN_STEPS, MAX_STEPS = 3, 8
MIN_SYNTAX, MAX_SYNTAX = 2, 7
MIN_CHECK = 3
MIN_STUCK = 2
MIN_PITFALLS = 1
MIN_SKILLS, MAX_SKILLS = 3, 14
MIN_TOTAL_CHARS, MAX_TOTAL_CHARS = 2500, 9000
MIN_GOAL_CHARS = 20
OBSERVABLE_WORDS = ("运行", "输出", "屏幕", "得到", "显示", "程序", "打印")

# 看起来就是一行能跑的代码 —— 这些是硬错误
# 注意：像 `100.00°C = 212.00°F`、`150 厘米 = 1.5 米` 这种是「演示输出」，
# 不是代码，所以赋值那条要求等号左边是个正经的英文变量名。
CODE_ERROR_PATTERNS: list[tuple[str, str]] = [
    (r"(?<![\d\w°℃℉])[a-z_][a-z_0-9]*\s*=\s*[\"'\[0-9]", "赋值语句（像 x = 5 这种）"),
    (r"\b(?:print|input|len|int|float|str|open|range|round|sum|sorted|reversed|join|append|"
     r"sleep|randint|choice|shuffle|format|split|strip|upper|lower|keys|items|get)"
     r"\s*\(\s*[^)\s]", "函数调用里带了参数（像 print(x) 这种）"),
    (r"(?:^|[。；;\n]|\s)(?:for|if|while|def|class|elif|else|try|except|return|import|from|with|lambda)"
     r"\b[^\n]{0,60}:\s", "一整行语句（关键字开头、冒号结尾）"),
    (r"\bf[\"']", "f-string 字面量"),
    (r"```", "代码块围栏"),
    (r"\bself\.", "self 调用"),
    (r"->\s*[A-Za-z\[]", "类型注解箭头"),
]

# 需要人看一眼的 —— 警告
CODE_WARN_PATTERNS: list[tuple[str, str]] = [
    (r"==", "出现了两个等号（如果是在解释语法就没问题）"),
    (r"\b[a-z_]+\.[a-z_]+\(", "链式调用（确认只是提到 API 名字）"),
    (r"\b0x[0-9a-fA-F]+|\b0b[01]+", "写死的进制字面量"),
]

# 整条字符串就是一个 API 名字（time.time()、.strip() 这种），属于「语法点」的正常写法
API_NAME_ONLY = re.compile(r"^[.]?[A-Za-z_][\w.]*\(\)$")


def walk_strings(node, path="$"):
    """把 JSON 里所有字符串连同它的位置掏出来，方便定位问题。"""
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, f"{path}[{i}]")


def check_plan(errors: list[str], warns: list[str]) -> dict:
    data = json.loads(PLAN.read_text(encoding="utf-8"))
    projects = data["projects"]
    stages = data["meta"]["stages"]

    if len(projects) != 100:
        errors.append(f"plan.json：项目数是 {len(projects)}，应该是 100")

    ids = [p["id"] for p in projects]
    if ids != [f"{i:03d}" for i in range(1, 101)]:
        errors.append("plan.json：编号不是从 001 连续到 100")

    last = 0.0
    for p in projects:
        if p["difficulty"] < last:
            errors.append(f"plan.json：{p['id']} 的难度 {p['difficulty']} 比上一个（{last}）低，难度曲线回落了")
        last = p["difficulty"]
        if not p["dir"].startswith(p["id"]):
            errors.append(f"plan.json：{p['id']} 的目录名 {p['dir']} 不是以编号开头")

    covered = sorted(int(x) for st in stages for x in re.findall(r"\d+", st["range"]))
    if covered[:1] != [1] or covered[-1:] != [100]:
        errors.append("plan.json：阶段区间没有覆盖 001~100")

    return {p["id"]: p for p in projects}


def check_author(path: Path, plan: dict, errors: list[str], warns: list[str]) -> dict | None:
    name = path.name
    raw = path.read_text(encoding="utf-8")
    try:
        d = json.loads(raw)
    except Exception as e:  # JSON 写坏了要立刻知道，并指出坏在哪
        detail = ""
        m = re.search(r"char (\d+)", str(e))
        if m:
            i = int(m.group(1))
            detail = f"　附近内容：…{raw[max(0, i - 50):i + 15]!r}"
        errors.append(f"{name}：JSON 解析失败 —— {e}{detail}")
        return None

    for key in PROJECT_REQUIRED:
        if key not in d or d[key] in ("", [], None):
            errors.append(f"{name}：缺字段 {key}")

    pid = d.get("id", "")
    if path.stem != pid:
        errors.append(f"{name}：文件名和 id（{pid}）不一致")
    if pid and pid not in plan:
        errors.append(f"{name}：id {pid} 在 plan.json 里找不到")
    elif pid and plan[pid]["dir"] != d.get("_dir", plan[pid]["dir"]):
        pass  # 目录名以 plan 为准，author 里不写

    levels = d.get("levels", [])
    if not MIN_LEVELS <= len(levels) <= MAX_LEVELS:
        errors.append(f"{name}：关卡数是 {len(levels)}，要求 {MIN_LEVELS}~{MAX_LEVELS}")

    for i, lv in enumerate(levels, 1):
        tag = f"{name} 关卡{i}"
        for key in LEVEL_REQUIRED:
            if key not in lv or lv[key] in ("", [], None):
                errors.append(f"{tag}：缺字段 {key}")
        if lv.get("n") != i:
            errors.append(f"{tag}：n 字段是 {lv.get('n')}，应该是 {i}")

        n_steps = len(lv.get("steps", []))
        if not MIN_STEPS <= n_steps <= MAX_STEPS:
            errors.append(f"{tag}：怎么想有 {n_steps} 步，要求 {MIN_STEPS}~{MAX_STEPS} 步")

        n_syntax = len(lv.get("syntax", []))
        if not MIN_SYNTAX <= n_syntax <= MAX_SYNTAX:
            errors.append(f"{tag}：语法点有 {n_syntax} 条，要求 {MIN_SYNTAX}~{MAX_SYNTAX} 条")
        for s in lv.get("syntax", []):
            if not isinstance(s, dict) or not s.get("name") or not s.get("hint"):
                errors.append(f"{tag}：有个语法点没写全（要有 name 和 hint）")

        if len(lv.get("check", [])) < MIN_CHECK:
            errors.append(f"{tag}：自检少于 {MIN_CHECK} 条")
        if len(lv.get("stuck", [])) < MIN_STUCK:
            errors.append(f"{tag}：卡住提示少于 {MIN_STUCK} 条")
        if len(lv.get("pitfalls", [])) < MIN_PITFALLS:
            errors.append(f"{tag}：常见坑少于 {MIN_PITFALLS} 条")

        goal = lv.get("goal", "")
        if len(goal) < MIN_GOAL_CHARS:
            errors.append(f"{tag}：目标写得太短（{len(goal)} 字），要说清楚做出来是什么样")
        elif not any(w in goal for w in OBSERVABLE_WORDS):
            warns.append(f"{tag}：目标里没有「运行/输出/显示」这类可观察的词，可能不够具体")

    skills = d.get("skills", [])
    if not MIN_SKILLS <= len(skills) <= MAX_SKILLS:
        errors.append(f"{name}：语法清单有 {len(skills)} 项，要求 {MIN_SKILLS}~{MAX_SKILLS} 项")
    if not d.get("extend"):
        errors.append(f"{name}：没写「做完之后可以再试」")

    total = len(json.dumps(d, ensure_ascii=False))
    if not MIN_TOTAL_CHARS <= total <= MAX_TOTAL_CHARS:
        warns.append(f"{name}：全文 {total} 字符，超出 {MIN_TOTAL_CHARS}~{MAX_TOTAL_CHARS} 的舒适区间")

    # 扫代码
    for loc, text in walk_strings(d):
        short = loc.replace("$.", "")
        for pat, why in CODE_ERROR_PATTERNS:
            m = re.search(pat, text)
            if m:
                errors.append(f"{name} {short}：出现像代码的内容「{m.group(0).strip()}」（{why}）")
        for pat, why in CODE_WARN_PATTERNS:
            if API_NAME_ONLY.match(text.strip()):
                continue
            m = re.search(pat, text)
            if m:
                warns.append(f"{name} {short}：{why}（「{m.group(0).strip()}」）")

    return d


def lint_all(only: set[str] | None = None) -> tuple[list[str], list[str]]:
    """给 build.py 用的入口：返回 (错误列表, 警告列表)。"""
    errors: list[str] = []
    warns: list[str] = []
    plan = check_plan(errors, warns)
    files = sorted(AUTHOR_DIR.glob("*.json"))
    if only:
        files = [f for f in files if f.stem in only]
    for f in files:
        check_author(f, plan, errors, warns)
    return errors, warns


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in sys.argv

    want = {a.zfill(3) for a in args} if args else None
    errors, warns = lint_all(want)

    written = {f.stem for f in AUTHOR_DIR.glob("*.json")}
    all_ids = [p["id"] for p in json.loads(PLAN.read_text(encoding="utf-8"))["projects"]]
    missing = [pid for pid in all_ids if pid not in written]
    if not quiet:
        checked = len(want) if want else len(written)
        print(f"检查了 {checked} 份任务卡；已写好 {len(written)} / 100；待编写 {len(missing)} 个")
        if missing:
            nxt = ", ".join(missing[:12])
            print(f"下一批可以写：{nxt}{' …' if len(missing) > 12 else ''}")

    if warns:
        print(f"\n警告 {len(warns)} 条（不拦，但值得看一眼）：")
        for w in warns:
            print("  · " + w)

    if errors:
        print(f"\n错误 {len(errors)} 条（必须修）：")
        for e in errors:
            print("  ✗ " + e)
        sys.exit(1)

    if not quiet:
        print("\n体检通过：关卡数、每关六个部分、无代码、难度曲线都没问题。")
    sys.exit(0)


if __name__ == "__main__":
    main()
