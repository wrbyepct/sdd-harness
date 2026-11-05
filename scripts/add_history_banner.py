"""給舊 feature 文件（plan.md／detailed-plan.md／test.md）插入「歷史文件」橫幅（冪等）。

用法：python3 ${CLAUDE_PLUGIN_ROOT}/scripts/add_history_banner.py <feature_dir 的根或單一 feature 目錄> [--dry-run]
      例：python3 …/add_history_banner.py features/            # 全部已完工的 feature
          python3 …/add_history_banner.py features/cancel-booking --dry-run

feature 做完一段時間後，plan／detailed-plan／test 三份文件會跟 code 脫節；橫幅提醒讀者
「行為以 code 和 tests/ 為準，決策紀錄（D 編號＋why）仍有效」。user_story.md 不加（它是活的契約）。
日期取檔案「插入前」的最後修改日；已有橫幅的檔跳過。橫幅放在第一行 H1 之後（無 H1 則放最前）。
"""
import datetime, pathlib, sys

MARK = "⚠️ 歷史文件"
NAMES = {"plan.md", "detailed-plan.md", "test.md"}

def banner(date: str) -> str:
    return (f"> {MARK}：本檔最後修改於 {date}，記錄當時的計畫。行為描述以 code 和 `tests/` 為準；"
            "決策紀錄（D 編號＋why）仍有效。\n")

def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    root = pathlib.Path(args[0]); dry = "--dry-run" in sys.argv
    done = skipped = 0
    for p in sorted(root.rglob("*.md")):
        if p.name not in NAMES:
            continue
        text = p.read_text(encoding="utf-8")
        if MARK in text[:2000]:
            skipped += 1; continue
        date = datetime.date.fromtimestamp(p.stat().st_mtime).isoformat()
        lines = text.splitlines(keepends=True)
        b = banner(date)
        if lines and lines[0].startswith("# "):
            new = lines[0] + "\n" + b + "".join(lines[1:])
        else:
            new = b + "\n" + text
        if not dry:
            p.write_text(new, encoding="utf-8")
        done += 1
        print(("[dry] " if dry else "") + f"{p}  ({date})")
    print(f"加橫幅 {done}、已有跳過 {skipped}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
