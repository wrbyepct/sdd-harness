"""BACKLOG 單表自我檢查（/ticket 寫完、/user-story 複查收尾、/backlog-align 收尾都要跑）。

用法：python3 ${CLAUDE_PLUGIN_ROOT}/scripts/backlog_check.py [<feature_dir>/BACKLOG.md]   （預設 features/BACKLOG.md）
每一行印「✅／❌ 檢查項：細節」；有任何 ❌ 就以 exit code 1 結束＝還沒對完。
第一行另外印「下一個可用編號 #N」，/ticket 立題時取它。

一項工作一個資料夾 `<N>-<英文名>/`，裡面有 `ticket.md`。資料夾可以直接放在 BACKLOG.md 旁邊，
也可以多包幾層（例如按版本或產品線：`v1.2/<variant>/<N>-<名>/`）；`archive/` 底下的不看。

檢查：
1. 兩張表（未結案／已結案）每列 8 個 `|`、表格中間沒有空行、照編號由小到大、沒有重號
2. 每列的 `#N` 連結指到 `…/N-<名>/ticket.md`，檔案存在
3. 反過來：每個 `<N>-<名>/ticket.md` 都在表上恰好一列
4. 級別 ∈ tiny／small／medium／large；未結案表狀態 ∈ 待開工／進行中；已結案表狀態 ∈ 完成／作廢／收編進 #N
5. ticket 檔頭「級別：…｜狀態：…」與表上一致；第二行是回 BACKLOG 的連結
6. 母題欄不是「—」時：指到的那張級別是 large，子題檔頭有「母題：」行，母題的 ticket 連得到這張子題
7. BACKLOG.md 與所有 ticket.md 裡的相對 .md 連結都連得到
"""
import re
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "features/BACKLOG.md")
root = path.parent
if not path.is_file():
    print(f"❌ 找不到 {path}（還沒有 BACKLOG：照 /ticket 的「BACKLOG 骨架」建一份）")
    sys.exit(1)
s = path.read_text(encoding="utf-8")
fails = 0


def report(name: str, bad: list) -> None:
    global fails
    if bad:
        fails += 1
        print(f"❌ {name}：" + "；".join(str(x) for x in bad[:12]) + (f"…共 {len(bad)}" if len(bad) > 12 else ""))
    else:
        print(f"✅ {name}")


if "## ⬜ 未結案" not in s or "## 🏁 已結案" not in s:
    print("❌ 找不到「## ⬜ 未結案」或「## 🏁 已結案」標題")
    sys.exit(1)
open_sec = s.split("## ⬜ 未結案", 1)[1].split("## 🏁 已結案", 1)[0]
closed_sec = s.split("## 🏁 已結案", 1)[1]

ROW = re.compile(r"^\| \[#(\d+)\]\(([^)]+)\) \| (.*) \| ([^|]*) \| ([^|]*) \| ([^|]*) \| ([^|]*) \| ([^|]*) \|$")
LEVELS = {"tiny", "small", "medium", "large"}


def parse(sec: str, name: str) -> dict[int, dict]:
    rows, bad_cols, bad_shape, order = {}, [], [], []
    for line in sec.split("\n"):
        if not line.startswith("|") or line.startswith("| # |") or line.startswith("|---"):
            continue
        if line.replace("\\|", "").count("|") != 8:
            bad_cols.append(line[:40])
            continue
        m = ROW.match(line)
        if not m:
            bad_shape.append(line[:40])
            continue
        n = int(m.group(1))
        order.append(n)
        rows[n] = dict(link=m.group(2), title=m.group(3), level=m.group(4).strip(), parent=m.group(5).strip(),
                       deps=m.group(6).strip(), status=m.group(7).strip(), memo=m.group(8).strip())
    report(f"{name}表 欄數", bad_cols)
    report(f"{name}表 列的格式（| [#N](路徑) | 標題 | 級別 | 母題 | 依賴 | 狀態 | 備註 |）", bad_shape)
    report(f"{name}表 照編號、無重號", [] if order == sorted(set(order)) else [order])
    return rows


o, c = parse(open_sec, "未結案"), parse(closed_sec, "已結案")
# 封存過舊清單的專案，在 BACKLOG 檔頭寫一句「最後一號是 #N」，封存檔裡的號碼就不會被重用
floor = re.search(r"最後一號是 #(\d+)", s)
print(f"　未結案 {len(o)} 項、已結案 {len(c)} 項；下一個可用編號 #{max([*o, *c, int(floor.group(1)) if floor else 0]) + 1}")
report("兩張表沒有同一號", sorted(set(o) & set(c)))
allrows = {**o, **c}

lines = s.split("\n")
report("表格中間沒有空行（行號）", [i + 1 for i in range(1, len(lines) - 1)
                         if lines[i] == "" and lines[i - 1].startswith("|") and lines[i + 1].startswith("|")])

bad = []
for n, r in allrows.items():
    p = root / r["link"]
    if not re.fullmatch(rf"(?:[^/]+/)*{n}-[a-z0-9-]+/ticket\.md", r["link"]):
        bad.append(f"#{n} 路徑形狀不對 {r['link']}")
    elif not p.exists():
        bad.append(f"#{n} 檔案不存在")
report("每列連到存在的 ticket.md", bad)

on_disk = {p.relative_to(root).as_posix() for p in root.rglob("ticket.md")
           if re.match(r"\d+-", p.parent.name) and "archive" not in p.relative_to(root).parts}
linked = {r["link"] for r in allrows.values()}
report("每張 ticket.md 都在表上", sorted(on_disk - linked))

report("級別值", [f"#{n}={r['level']}" for n, r in allrows.items() if r["level"] not in LEVELS])
report("未結案表狀態值", [f"#{n}={r['status']}" for n, r in o.items() if r["status"] not in {"待開工", "進行中"}])
report("已結案表狀態值", [f"#{n}={r['status']}" for n, r in c.items()
                    if not re.fullmatch(r"完成|作廢|收編進 \[?#\d+.*", r["status"])])

MD_LINK = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")
bad_head, bad_links, bad_parent = [], [], []
texts = {}
for n, r in allrows.items():
    p = root / r["link"]
    if not p.exists():
        continue
    t = texts[n] = p.read_text(encoding="utf-8")
    head = t.split("\n")[:8]
    if not (len(head) > 1 and re.match(r"\[← BACKLOG\]\((\.\./)+BACKLOG\.md\)", head[1])):
        bad_head.append(f"#{n} 第二行不是回 BACKLOG 的連結")
    m = next((re.match(r"級別：(\S+?)｜狀態：(.+?)\s*$", x) for x in head if x.startswith("級別：")), None)
    if not m:
        bad_head.append(f"#{n} 缺「級別：…｜狀態：…」行")
    elif (m.group(1), m.group(2)) != (r["level"], re.sub(r"\[(#\d+)\]\([^)]*\)", r"\1", r["status"])):
        bad_head.append(f"#{n} 檔頭「{m.group(1)}／{m.group(2)}」≠ 表「{r['level']}／{r['status']}」")
    bad_links += [f"#{n}→{m2.group(1)}" for m2 in MD_LINK.finditer(t) if not (p.parent / m2.group(1)).exists()]
for n, r in allrows.items():
    if r["parent"] in {"—", ""}:
        continue
    m = re.match(r"\[#(\d+)\]", r["parent"])
    pn = int(m.group(1)) if m else None
    if pn not in allrows:
        bad_parent.append(f"#{n} 的母題欄讀不出表上的編號")
        continue
    if allrows[pn]["level"] != "large":
        bad_parent.append(f"#{n} 的母題 #{pn} 級別不是 large")
    if n in texts and not re.search(rf"^母題：\[#{pn}\b", texts[n], re.M):
        bad_parent.append(f"#{n} 檔頭缺「母題：[#{pn} …](…)」")
    if pn in texts and f"/{n}-" not in texts[pn] and f"({n}-" not in texts[pn]:
        bad_parent.append(f"母題 #{pn} 沒有連到子題 #{n}")
report("ticket 檔頭與表一致", bad_head)
report("母題／子題互連", bad_parent)
bad_links += [f"BACKLOG→{m.group(1)}" for m in MD_LINK.finditer(s) if not (root / m.group(1)).exists()]
report("相對 .md 連結都連得到", bad_links)

sys.exit(1 if fails else 0)
