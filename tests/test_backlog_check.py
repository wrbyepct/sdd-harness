"""backlog_check.py 的行為測試：用虛構的「會議室預約系統」BACKLOG（一張母題＋兩張子題＋一張已結案）。

跑法：python3 -m unittest discover -s tests
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "backlog_check.py"

BACKLOG = """# Backlog

## ⬜ 未結案

| # | 標題 | 級別 | 母題 | 依賴 | 狀態 | 備註 |
|---|---|---|---|---|---|---|
| [#2]({p}2-recurring-booking-epic/ticket.md) | 員工可以訂每週固定的會議 | large | — | — | 待開工 |  |
| [#3]({p}3-recurring-rule/ticket.md) | 員工可以設定重複規則 | medium | [#2]({p}2-recurring-booking-epic/ticket.md) | — | 進行中 |  |
| [#4]({p}4-recurring-conflict/ticket.md) | 重複預約撞期時逐筆提示 | small | [#2]({p}2-recurring-booking-epic/ticket.md) | [#3]({p}3-recurring-rule/ticket.md) | 待開工 | 等 #3 |

## 🏁 已結案

| # | 標題 | 級別 | 母題 | 依賴 | 狀態 | 備註 |
|---|---|---|---|---|---|---|
| [#1]({p}1-cancel-booking/ticket.md) | 員工可以取消自己的預約 | medium | — | — | 完成 | PR #7 |
"""


def ticket(title: str, level: str, status: str, up: str, extra: str = "") -> str:
    return f"# {title}\n[← BACKLOG]({up}BACKLOG.md)\n級別：{level}｜狀態：{status}\n{extra}\n## 現況\n無\n"


def build(root: pathlib.Path, prefix: str = "") -> None:
    """prefix＝BACKLOG.md 到各資料夾中間多包的層（"" 或 "v1.2/room/"）。"""
    up = "../" * (prefix.count("/") + 1)
    files = {
        "1-cancel-booking": ticket("1-取消預約", "medium", "完成", up),
        "2-recurring-booking-epic": ticket(
            "2-週期性預約（epic）", "large", "待開工", up,
            "\n## 子題與順序\n- [#3](../3-recurring-rule/ticket.md)\n- [#4](../4-recurring-conflict/ticket.md)\n"),
        "3-recurring-rule": ticket(
            "3-重複規則", "medium", "進行中", up, "母題：[#2 週期性預約](../2-recurring-booking-epic/ticket.md)"),
        "4-recurring-conflict": ticket(
            "4-撞期提示", "small", "待開工", up, "母題：[#2 週期性預約](../2-recurring-booking-epic/ticket.md)"),
    }
    for name, text in files.items():
        d = root / prefix / name
        d.mkdir(parents=True)
        (d / "ticket.md").write_text(text, encoding="utf-8")
    (root / "BACKLOG.md").write_text(BACKLOG.format(p=prefix), encoding="utf-8")


def run(root: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), str(root / "BACKLOG.md")], capture_output=True, text=True)


class BacklogCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "features"
        self.root.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_flat_layout_passes_and_prints_next_number(self) -> None:
        build(self.root)
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("❌", r.stdout)
        self.assertIn("下一個可用編號 #5", r.stdout)

    def test_nested_layout_passes(self) -> None:
        build(self.root, "v1.2/room/")
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_status_mismatch_between_table_and_ticket_fails(self) -> None:
        build(self.root)
        t = self.root / "3-recurring-rule" / "ticket.md"
        t.write_text(t.read_text(encoding="utf-8").replace("狀態：進行中", "狀態：待開工"), encoding="utf-8")
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("❌ ticket 檔頭與表一致", r.stdout)

    def test_ticket_missing_from_table_fails(self) -> None:
        build(self.root)
        d = self.root / "5-room-photo"
        d.mkdir()
        (d / "ticket.md").write_text(ticket("5-會議室照片", "tiny", "待開工", "../"), encoding="utf-8")
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("❌ 每張 ticket.md 都在表上", r.stdout)

    def test_child_without_parent_line_fails(self) -> None:
        build(self.root)
        t = self.root / "4-recurring-conflict" / "ticket.md"
        t.write_text(t.read_text(encoding="utf-8").replace("母題：", "上層："), encoding="utf-8")
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("❌ 母題／子題互連", r.stdout)

    def test_archived_tickets_are_ignored_and_floor_number_is_respected(self) -> None:
        build(self.root)
        d = self.root / "archive" / "7-old-item"
        d.mkdir(parents=True)
        (d / "ticket.md").write_text("舊的", encoding="utf-8")
        b = self.root / "BACKLOG.md"
        b.write_text(b.read_text(encoding="utf-8").replace("# Backlog\n", "# Backlog\n\n> 上一版最後一號是 #7\n"), encoding="utf-8")
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("下一個可用編號 #8", r.stdout)


if __name__ == "__main__":
    unittest.main()
