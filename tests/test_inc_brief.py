"""inc_brief.py 的行為測試：用虛構的「會議室預約系統」feature 抽一個 Inc 的 brief。

跑法：python3 -m unittest discover -s tests
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "inc_brief.py"

DETAILED = """# detailed-plan — cancel-booking

## 1. 資料模型（C1；plan D1；US 1）

`Booking.cancelled_at: datetime | None`

## 2. 取消守門（C2；plan D2、D3；US 2, 3）

`BookingService.cancel(booking_id, actor)`：開始前才能取消。

### D2.1 已開始的預約

回 409 `BookingAlreadyStarted`。

```python
# 這行不是標題
```
"""

TEST = """# test.md

## 0. 共用 fixture

`room_a`、`alice`。

## 1. 資料模型（`test_booking_model.py`；C1）

| TC | 內容 |
|---|---|
| TC-BK01 | [US 1] 新欄位預設 null |

## 2. 取消守門（`test_cancel_booking.py`；C2）

| TC | 內容 |
|---|---|
| TC-BK05 | [US 2] 開始前可取消 |
| TC-BK07 | [US 3] 已開始回 409 |

## 10. 刻意不測

不測時區轉換。
"""

PLAN = """# plan

| 編號 | 決策 | why |
|---|---|---|
| D1 | 用 cancelled_at 而非刪除 | 保留稽核 |
| D2 | 開始前才能取消 | 已用過的時段不能退 |
| D3 | 已開始回 409 | 要查 server 狀態才知道 |
"""

STORY = """# user story

### 1. 取消後紀錄還在

管理員查得到誰取消了。

### 2. 開始前可取消

Alice 在會議開始前取消。

### 3. 已開始不能取消

Bob 開會到一半想取消，被擋。
"""


def run(fdir: pathlib.Path, inc: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), str(fdir), inc], capture_output=True, text=True, check=True)


class IncBriefTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.fdir = pathlib.Path(self.tmp.name) / "cancel-booking"
        self.fdir.mkdir()
        for name, body in {
            "detailed-plan.md": DETAILED,
            "test.md": TEST,
            "plan.md": PLAN,
            "user_story.md": STORY,
        }.items():
            (self.fdir / name).write_text(body)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def brief(self) -> str:
        return (self.fdir / "briefs" / "C2-brief.md").read_text()

    def test_extracts_only_the_inc_sections(self) -> None:
        run(self.fdir, "c2")
        b = self.brief()
        self.assertIn("## 2. 取消守門（C2", b)
        self.assertNotIn("## 1. 資料模型", b)
        self.assertIn("TC-BK07", b)
        self.assertNotIn("TC-BK01", b)
        self.assertIn("| D2 | 開始前才能取消", b)
        self.assertIn("| D3 | 已開始回 409", b)
        self.assertNotIn("| D1 |", b)
        self.assertIn("### 3. 已開始不能取消", b)
        self.assertNotIn("### 1. 取消後紀錄還在", b)
        self.assertNotIn("⚠️ 抽不到", b)

    def test_rerun_keeps_manual_section_and_pulls_named_sections(self) -> None:
        run(self.fdir, "C2")
        path = self.fdir / "briefs" / "C2-brief.md"
        manual = "C1 新增 `Booking.cancelled_at`（src/booking/models.py:12）。fixture 照 §0；plan §10 不用抽；D2.1 要回 409。"
        text = path.read_text().replace("（主 agent 填：", manual + "\n（主 agent 填：", 1)
        path.write_text(text)

        run(self.fdir, "C2")
        b = self.brief()
        self.assertIn(manual, b)  # ③ 手寫段保留
        named = b.split("## ③' 點名原文", 1)[1]
        self.assertIn("## 0. 共用 fixture", named)  # test.md §0 被點名 → 抽原文
        self.assertNotIn("## 10. 刻意不測", named)  # 前綴 plan 的 §10 不算
        self.assertNotIn("### D2.1", named)  # 已在 ① 的段裡，不重抄

    def test_reports_missing_pieces(self) -> None:
        r = run(self.fdir, "C9")
        self.assertIn("⚠️ 抽不到", r.stderr)
        self.assertIn("detailed-plan.md 沒有標題含 C9", (self.fdir / "briefs" / "C9-brief.md").read_text())


if __name__ == "__main__":
    unittest.main()
