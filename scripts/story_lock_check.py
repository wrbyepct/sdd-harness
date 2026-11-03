#!/usr/bin/env python3
"""story-lock 機械對帳：user_story.md 每一則 ↔ test.md 的 TC 回指 ↔ tests/ 裡實際存在的 TC。

用法：
    python3 story_lock_check.py <feature_dir> [--tests-dir tests] [--json] [--strict]

回指格式：
    test.md 每條 TC 的「內容」欄開頭、以及 tests/ 裡該測試 docstring 的第一行，用 `[US n]`
    標出這條 TC 鎖住 user_story 的哪幾則；多則寫 `[US 3, 4]`；結構鎖／DRY 鎖等
    不對應任何一則的寫 `[US —]`。TC 編號格式：`TC-12`、`TC-AUTH-3`、`TC-12b` 都認得。

每一則的狀態：
    mapped     test.md 有 TC 回指它，且 tests/ 找得到那條 TC
    spec-only  test.md 有回指，但 tests/ 找不到（還沒寫或編號打錯）
    unmapped   沒有任何 TC 回指它

這是「機械」對帳：只看標記連不連得起來。assert 有沒有真的鎖住預期行為，
是 story-lock-auditor 的語意工作，本腳本不判斷。

--strict：有 unmapped／spec-only 的則、或有沒標 [US] 的 TC 時 exit 1（給 CI／收尾檢查用）。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field

TC_ID = re.compile(r"\bTC-(?:[A-Z]+-?)?\d+[a-z]?\b")
US_TAG = re.compile(r"\[US\s*(—|-|\d+[a-z]?(?:\s*[,，]\s*\d+[a-z]?)*)\]")
STORY_HEADING = re.compile(r"^###\s+(\d+[a-z]?)[.、．]\s*(.+)$", re.M)
NO_STORY = "—"


def parse_us_tags(text: str) -> set[str]:
    """`[US 3, 4b]` → {"3", "4b"}；`[US —]` → {"—"}。"""
    refs: set[str] = set()
    for m in US_TAG.finditer(text):
        body = m.group(1)
        if body in ("—", "-"):
            refs.add(NO_STORY)
        else:
            refs.update(part.strip() for part in re.split(r"[,，]", body))
    return refs


@dataclass
class TestHit:
    where: list[str] = field(default_factory=list)
    refs: set[str] = field(default_factory=set)


def scan_spec(test_md: str) -> dict[str, set[str]]:
    """test.md：每一行抓 TC 編號與同一行的 [US] 回指。"""
    spec: dict[str, set[str]] = {}
    for line in test_md.splitlines():
        ids = TC_ID.findall(line)
        if not ids:
            continue
        refs = parse_us_tags(line)
        for tc in ids:
            spec.setdefault(tc, set()).update(refs)
    return spec


def scan_tests(tests_dir: pathlib.Path, wanted: set[str]) -> dict[str, TestHit]:
    """tests/：逐檔逐行找 test.md 列過的 TC 編號，記落點與同一行的 [US] 回指。"""
    hits: dict[str, TestHit] = {}
    if not tests_dir.is_dir():
        return hits
    for path in sorted(tests_dir.rglob("*.py")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(lines, 1):
            for tc in TC_ID.findall(line):
                if tc not in wanted:
                    continue
                hit = hits.setdefault(tc, TestHit())
                hit.where.append(f"{path.as_posix()}:{lineno}")
                hit.refs.update(parse_us_tags(line))
    return hits


def build_report(feature_dir: pathlib.Path, tests_dir: pathlib.Path) -> dict:
    stories = {
        m.group(1): m.group(2).strip()
        for m in STORY_HEADING.finditer(
            (feature_dir / "user_story.md").read_text(encoding="utf-8")
        )
    }
    spec = scan_spec((feature_dir / "test.md").read_text(encoding="utf-8"))
    tests = scan_tests(tests_dir, set(spec))

    rows = []
    for sid, title in stories.items():
        in_spec = sorted(tc for tc, refs in spec.items() if sid in refs)
        in_tests = [tc for tc in in_spec if tc in tests]
        only_in_tests = sorted(
            tc for tc, hit in tests.items() if sid in hit.refs and tc not in in_spec
        )
        status = "mapped" if in_tests else "spec-only" if in_spec else "unmapped"
        rows.append(
            {
                "story": sid,
                "title": title,
                "status": status,
                "tc_in_test_md": in_spec,
                "tc_found_in_tests": in_tests,
                "tc_only_in_tests": only_in_tests,
            }
        )

    return {
        "feature": feature_dir.as_posix(),
        "stories": rows,
        "tc_without_us_tag": sorted(tc for tc, refs in spec.items() if not refs),
        "tc_in_spec_not_in_tests": sorted(tc for tc in spec if tc not in tests),
        "counts": {"stories": len(stories), "tc_in_spec": len(spec), "tc_in_tests": len(tests)},
    }


def print_markdown(report: dict) -> None:
    c = report["counts"]
    print(f"# story-lock 機械對帳：{report['feature']}\n")
    print(
        f"則數 {c['stories']}｜test.md TC {c['tc_in_spec']}｜tests/ 找到 {c['tc_in_tests']}｜"
        f"沒標 [US] 的 TC {len(report['tc_without_us_tag'])}｜"
        f"test.md 有但 tests/ 沒有 {len(report['tc_in_spec_not_in_tests'])}\n"
    )
    print("| 則 | 狀態 | test.md 回指的 TC | tests/ 找得到 | 標題 |")
    print("|---|---|---|---|---|")
    marks = {"mapped": "✅", "spec-only": "⚠️ spec-only", "unmapped": "❌ unmapped"}
    for r in report["stories"]:
        extra = f"（tests/ 另有 {', '.join(r['tc_only_in_tests'])}）" if r["tc_only_in_tests"] else ""
        print(
            f"| {r['story']} | {marks[r['status']]} | {', '.join(r['tc_in_test_md']) or '—'} | "
            f"{', '.join(r['tc_found_in_tests']) or '—'}{extra} | {r['title'][:40]} |"
        )
    if report["tc_without_us_tag"]:
        print(f"\n**沒標 [US] 的 TC**：{', '.join(report['tc_without_us_tag'])}")
    if report["tc_in_spec_not_in_tests"]:
        print(f"\n**test.md 有、tests/ 找不到的 TC**：{', '.join(report['tc_in_spec_not_in_tests'])}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("feature_dir", type=pathlib.Path)
    ap.add_argument("--tests-dir", type=pathlib.Path, default=pathlib.Path("tests"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)

    for name in ("user_story.md", "test.md"):
        if not (args.feature_dir / name).is_file():
            print(f"找不到 {args.feature_dir / name}", file=sys.stderr)
            return 2

    report = build_report(args.feature_dir, args.tests_dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print_markdown(report)

    if args.strict:
        bad = [r for r in report["stories"] if r["status"] != "mapped"]
        if bad or report["tc_without_us_tag"]:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
