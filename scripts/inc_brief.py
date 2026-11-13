#!/usr/bin/env python3
"""從 feature 三文件機械抽出一個 Inc 的 implementer brief（/build-feature「派工流程」第 1、2 步）。

用法：python3 ${CLAUDE_PLUGIN_ROOT}/scripts/inc_brief.py <feature_dir> C<n>
輸出：<feature_dir>/briefs/C<n>-brief.md（已存在則覆寫 ①②④，保留 ③ 主 agent 手寫段），印出路徑。

抽法（依現行文件慣例）：
- detailed-plan.md：標題含「（C<n>；plan …；US …）」的 `## ` 段整段
- test.md：標題含 C<n> 的 `## ` 段整段（如「C1 起、C7 補」兩個 Inc 都抽）
- plan.md：detailed-plan 標題列出的決策編號（D0、D2b、D-R5…）在決策表的那一列
- user_story.md：detailed-plan 標題列出的 US 編號的 `### <n>.` 段
抽不到的項目會在 brief 開頭列「⚠️ 抽不到」，主 agent 補手寫。
"""
import re
import sys
from pathlib import Path

MANUAL_START = "<!-- ③ 主 agent 手寫：開始 -->"
MANUAL_END = "<!-- ③ 主 agent 手寫：結束 -->"


def headings(text: str) -> list[tuple[int, int]]:
    """所有 markdown 標題的 (位置, 級數)，略過 ``` 程式碼區塊內的 # 註解。"""
    out, pos, in_fence = [], 0, False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            m = re.match(r"(#{1,6}) ", line)
            if m:
                out.append((pos, len(m.group(1))))
        pos += len(line)
    return out


def sections(text: str, level: str) -> list[tuple[str, str]]:
    """切成 (標題行, 整段含標題) ；level='## ' 或 '### '。段落結束＝下一個同級或更高級標題。"""
    n = len(level.strip())
    hs = headings(text)
    out = []
    for i, (s, lv) in enumerate(hs):
        if lv != n:
            continue
        e = next((p for p, l in hs[i + 1 :] if l <= n), len(text))
        body = text[s:e].rstrip()
        out.append((body.splitlines()[0], body))
    return out


def has_inc(heading: str, inc: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(inc)}(?![0-9])", heading) is not None


def split_refs(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[／/、,，\s]+", s) if x.strip()]


OTHER_DOCS = r"(?:plan(?:\.md)?|decisions-pending(?:\.md)?|user_story(?:\.md)?|BACKLOG(?:\.md)?|CONVENTIONS(?:\.md)?|PRODUCT_PRINCIPLES(?:\.md)?|research(?:\.md)?|proposal(?:\.md)?)"


def named_sections(manual: str, tm: str, dp: str, already: set[str]) -> list[str]:
    """③ 點名的 test.md `§<節>` 與 detailed-plan `D<n>.<m>` 小節原文。

    `§X` 前面緊接別份文件名（plan §13、decisions-pending §5…）的不算；`detailed-plan §X` 也不算（它的節是 D 編號）。
    已在 ① 的段（或包在 ① 段裡的）不重抄。
    """
    text = re.sub(r"<!--.*?-->", "", manual, flags=re.S)
    tm_ids: list[str] = []
    for m in re.finditer(rf"(?:({OTHER_DOCS}|detailed-plan(?:\.md)?)\s*)?§\s*([0-9]+[a-z]?|[A-Z])(?![0-9A-Za-z])", text):
        if m.group(1) is None and m.group(2) not in tm_ids:
            tm_ids.append(m.group(2))
    if "M" not in tm_ids and re.search(r"(?<![A-Za-z0-9-])M-\d+", text):
        tm_ids.append("M")  # 點名 M-<n> 突變 ⇒ 整節 §M（mutation 方案表，通常幾 KB）
    dp_ids: list[str] = []
    for m in re.finditer(r"(?<![A-Za-z0-9-])D(\d+)\.(\d+)(?![0-9])", text):
        i = f"D{m.group(1)}.{m.group(2)}"
        if i not in dp_ids:
            dp_ids.append(i)

    def covered(body: str) -> bool:
        return any(body in a for a in already)

    out: list[str] = []
    tm_secs = sections(tm, "## ")
    for sid in tm_ids:
        hit = [b for h, b in tm_secs if re.match(rf"^## {re.escape(sid)}[.\s]", h)]
        out += [f"<!-- test.md §{sid} -->\n{b}" for b in hit if not covered(b)]
    dp_secs = sections(dp, "### ")
    for did in dp_ids:
        hit = [b for h, b in dp_secs if re.match(rf"^### {re.escape(did)}(?![0-9])", h)]
        out += [f"<!-- detailed-plan {did} -->\n{b}" for b in hit if not covered(b)]
    return out


def main() -> None:
    fdir, inc = Path(sys.argv[1]), sys.argv[2].upper()
    missing: list[str] = []

    dp = (fdir / "detailed-plan.md").read_text()
    dp_secs = [(h, b) for h, b in sections(dp, "## ") if has_inc(h, inc)]
    if not dp_secs:
        missing.append(f"detailed-plan.md 沒有標題含 {inc} 的 ## 段")
    plan_ids: list[str] = []
    us_ids: list[str] = []
    for h, _ in dp_secs:
        m = re.search(r"plan\s*([^；;）)]+)", h)
        if m:
            plan_ids += split_refs(m.group(1))
        m = re.search(r"US\s*([^；;）)]+)", h)
        if m:
            us_ids += split_refs(m.group(1))

    tm = (fdir / "test.md").read_text()
    tm_secs = [b for h, b in sections(tm, "## ") if has_inc(h, inc)]
    if not tm_secs:
        missing.append(f"test.md 沒有標題含 {inc} 的 ## 段")

    plan = (fdir / "plan.md").read_text()
    plan_rows = []
    for pid in plan_ids:
        row = re.search(rf"^\| {re.escape(pid)} \|.*$", plan, re.M)
        if row:
            plan_rows.append(row.group(0))
        else:
            missing.append(f"plan.md 決策表沒有 {pid} 那列")

    us_secs = []
    us_path = fdir / "user_story.md"
    if us_path.exists() and us_ids:
        us_all = sections(us_path.read_text(), "### ")
        for uid in us_ids:
            hit = [b for h, b in us_all if re.match(rf"^### {re.escape(uid)}\.", h)]
            if hit:
                us_secs += hit
            else:
                missing.append(f"user_story.md 沒有 ### {uid}. 段")

    out_dir = fdir / "briefs"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{inc}-brief.md"
    manual = f"{MANUAL_START}\n（主 agent 填：前面 Inc 新增／改掉的介面——函式名＋簽名＋檔:行；decisions-pending 裡跟這段有關的暫定決策題號＋一句話；你看出 brief 的模糊處與你的解讀。不貼前面 Inc 的過程或摘要。第一個 Inc 寫「無」。）\n{MANUAL_END}"
    if out.exists():
        old = out.read_text()
        m = re.search(rf"{re.escape(MANUAL_START)}.*?{re.escape(MANUAL_END)}", old, re.S)
        if m:
            manual = m.group(0)

    parts = [f"# {inc} brief — {fdir.name}", ""]
    parts.append("> 讀這份就是你的需求；具體數值、簽名、TC 以這裡為準。規則照 implementer agent 本文。")
    if missing:
        parts += ["", "⚠️ 抽不到（主 agent 已在 ③ 補或確認不需要）："] + [f"- {x}" for x in missing]
    parts += ["", "## ① 規格（detailed-plan）", ""] + [b for _, b in dp_secs]
    parts += ["", "## ① 規格（test.md 本 Inc 的 TC）", ""] + tm_secs
    parts += ["", "## ② 為什麼（plan 決策列）", ""]
    if plan_rows:
        parts += ["| 編號 | 決策 | why |", "|---|---|---|"] + plan_rows
    parts += ["", "## ② 為什麼（user story 原文）", ""] + us_secs
    parts += ["", "## ③ 前面留下的（主 agent 手寫）", "", manual]
    named = named_sections(manual, tm, dp, already=set(tm_secs) | {b for _, b in dp_secs})
    if named:
        parts += ["", "## ③' 點名原文（腳本依 ③ 自動抽，①已有的不重抄）", ""] + named
    parts += [
        "",
        "## ④ 規矩（自己讀，不貼內容）",
        "",
        "- `conventions_doc`（CLAUDE.md `Harness config`；開寫前 Read 對應黃金樣本）",
        "- `/build-feature` command 的「品質條款」、Step 1「發現 gap 時的處理順序」、Step 2～5",
        f"- 本 feature 的 `decisions-pending.md`（新決策點寫這裡）、`plan.md` §落地紀錄",
        "",
    ]
    out.write_text("\n".join(parts))
    print(out)
    if missing:
        print("⚠️ 抽不到：" + "；".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()
