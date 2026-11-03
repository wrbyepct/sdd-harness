#!/usr/bin/env python3
"""重建 lessons/INDEX.md，並檢查每則教訓的 frontmatter。

用法：
    python3 lessons_index.py [--lessons-dir lessons] [--gotchas docs/A.md docs/B.md] [--check]

一則教訓＝一個 md 檔，住在「第一個 area」的子目錄：lessons/<area>/<slug>.md

    ---
    area: [testing, auth]          # 第一個決定檔案放哪個目錄；多 area 會在每節都列一行
    kind: pitfall                  # pitfall／pattern／gotcha…
    keywords: [mock, token, 時區]   # lessons-recaller 用來 grep
    source: code_reviews/xxx.md    # 從哪一份 review／哪一次 build 學到的
    date: 2026-10-29
    status: active                 # 只有 active 會進索引；被推翻改 superseded（加 superseded_by）
    ---

    # 一句話教訓（INDEX 用這行當標題）

--gotchas：長篇踩雷文件（例如 ORM／migration 的 gotchas），把它們的 `##` 標題也列進索引，
          讓 lessons-recaller 一份 INDEX 就看得到全部。
--check：只檢查、不寫檔；有問題時 exit 1（適合掛 pre-commit）。
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

REQUIRED = ("area", "kind", "keywords", "source", "date", "status")
FIRST_AREAS = ("general", "testing")  # 其餘 area 依字母排
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
TITLE = re.compile(r"^# (.+)$", re.M)


def parse_frontmatter(text: str) -> dict[str, str]:
    m = FRONTMATTER.match(text)
    if not m:
        return {}
    data = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            data[key.strip()] = value.split("#", 1)[0].strip()
    return data


def as_list(value: str) -> list[str]:
    return [x.strip() for x in value.strip("[]").split(",") if x.strip()]


def collect(lessons_dir: pathlib.Path):
    by_area: dict[str, list[tuple[str, str, str, str, list[str]]]] = collections.defaultdict(list)
    problems: list[str] = []
    files = sorted(p for p in lessons_dir.rglob("*.md") if p.name not in ("INDEX.md", "README.md"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        missing = [k for k in REQUIRED if not as_list(meta.get(k, ""))]
        if missing:
            problems.append(f"{path}: 缺 {', '.join(missing)}")
            continue
        title = TITLE.search(text)
        if not title:
            problems.append(f"{path}: 沒有 `# 標題` 行")
            continue
        areas = as_list(meta["area"])
        if path.parent.name != areas[0]:
            problems.append(f"{path}: 目錄 {path.parent.name} ≠ 第一個 area {areas[0]}")
        if meta["status"] != "active":
            continue  # superseded 的不進索引，但仍檢查格式
        entry = (
            meta["date"],
            title.group(1).strip(),
            path.relative_to(lessons_dir).as_posix(),
            meta["kind"],
            as_list(meta["keywords"])[:3],
        )
        for area in areas:
            by_area[area].append(entry)
    return files, by_area, problems


def gotcha_headings(path: pathlib.Path) -> list[str]:
    text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
    return re.findall(r"^## (.+)$", text, re.M)


def render(by_area, gotchas: list[pathlib.Path], lessons_dir: pathlib.Path) -> str:
    out = [
        "# lessons 索引",
        "",
        "按 area 分節；多 area 的教訓在每個 area 都列一行（檔案只住第一個 area 的目錄）。每節內日期新→舊。",
        "本檔由 `lessons_index.py` 產生，不要手改。",
    ]
    order = [a for a in FIRST_AREAS if a in by_area] + sorted(a for a in by_area if a not in FIRST_AREAS)
    for area in order:
        out += ["", f"## {area}", ""]
        for date, title, rel, kind, kws in sorted(by_area[area], key=lambda e: (e[0], e[2]), reverse=True):
            out.append(f"- [{title}]({rel}) — {kind}｜{', '.join(kws)}")
    if gotchas:
        out += ["", "## 長篇 Gotchas", ""]
        for g in gotchas:
            rel = pathlib.Path("..", g) if not g.is_absolute() else g
            out += [f"### {g.name}", ""]
            out += [f"- [{h}]({rel.as_posix()})" for h in gotcha_headings(g)]
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lessons-dir", type=pathlib.Path, default=pathlib.Path("lessons"))
    ap.add_argument("--gotchas", type=pathlib.Path, nargs="*", default=[])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    if not args.lessons_dir.is_dir():
        print(f"找不到 {args.lessons_dir}/", file=sys.stderr)
        return 2
    missing_gotchas = [g for g in args.gotchas if not g.is_file()]
    if missing_gotchas:
        print(f"找不到 gotchas 檔：{', '.join(map(str, missing_gotchas))}", file=sys.stderr)
        return 2

    files, by_area, problems = collect(args.lessons_dir)
    print(f"教訓檔 {len(files)} 則；各 area：{dict(collections.Counter(p.parent.name for p in files))}")
    for p in problems:
        print(f"  ⚠️ {p}")

    if args.check:
        return 1 if problems else 0
    (args.lessons_dir / "INDEX.md").write_text(render(by_area, args.gotchas, args.lessons_dir), encoding="utf-8")
    print(f"已寫入 {args.lessons_dir / 'INDEX.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
