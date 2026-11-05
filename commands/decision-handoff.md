---
description: 收工交接——把一個 feature「還要 user 拍板的事」連同施工現況與重要 context 寫成 <feature_dir>/<name>/decisions-pending.md（每題 user story 格式＋翻案要動哪裡），更新記憶，最後印出下個 session 的開工指令（逐題拍板用）。常接在 /build-and-review 或 /auto-code-review 收尾之後。只寫文件、不改程式、不 commit。
argument-hint: [feature 目錄（<feature_dir>/<name>）；不帶＝由目前分支推]
allowed-tools: Bash(git:*), Bash(docker:*), Bash(python3:*), Bash(ls:*), Bash(grep:*), Bash(cat:*), Bash(sed:*), Bash(wc:*), Read, Write, Edit, Grep, Glob
---

## Context

- Current branch: !`git rev-parse --abbrev-ref HEAD`
- Working tree: !`git status --porcelain | head -20`
- 使用者給的參數：`$ARGUMENTS`
- 專案設定：從專案 `CLAUDE.md` 的 `## Harness config` 段讀 `base_branch`、`feature_dir`、`test_busy_check`、
  `isolated_db_env`、`isolated_db_review`、`test_workers_env`、`memory_index`（下文的 `<key>` 指那一格的值）。

## 這支指令是什麼

一輪施工／review 做完、還剩一串「要 user 拍板」的題目時，把它們**落成檔**，下個 session 才能乾淨地接著一題一題拍。
三個產出：① `decisions-pending.md` ② 記憶更新 ③ 開工指令（印在最後，給 user 貼到新 session）。

規則來源不重抄：拍板題怎麼問是固定的——**一次一題、user story 格式（角色／情境／動作／預期行為／為什麼＋另一個選項＋建議）、不彈選項框**；
施工／fixup／autosquash 的規矩在 `build-feature.md`、`auto-code-review.md`。

## Step 1 — 定位與現況（全部用指令實查，不憑對話記憶）

1. feature 目錄：`$ARGUMENTS` 有給就用；沒給就把分支名去掉 `feat-` 前綴，在 `<feature_dir>` 找同名目錄，找不到就問。
2. base：`origin/<base_branch>`。
3. 實查並記下：
   ```bash
   git log --oneline --reverse <base>..HEAD          # 範圍、每顆一句話
   git log --oneline <base>..HEAD | grep -c 'fixup!' # 必須 0，否則現況寫「有未 autosquash 的 fixup」
   git rev-parse --short HEAD; git rev-parse --short HEAD^{tree}
   git branch -r --contains HEAD | head -3            # 推了沒
   git status --porcelain
   git tag -l 'backup-before-autosquash*'
   <test_busy_check>                                  # 有設才跑：現在有沒有測試在飛
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/story_lock_check.py <feature 目錄> | sed -n 1,4p
   ```
4. 測試、mutation、review 評分：**只抄來源裡寫明的數字**（plan 落地紀錄、test.md 的統計節、`code_reviews/<name>.md`、本 session 的 test-runner／review 回報），沒有來源就寫「未記錄」，不要估。

## Step 2 — 蒐集待拍板題（來源逐一讀，不漏）

| 來源 | 找什麼 |
|---|---|
| **既有的 `decisions-pending.md`**（2026-11-05 起 `/build-feature` 新決策點當下即時寫、`/auto-code-review` §7 追加） | 已經在 §2／§3 的題：**保留編號與已填的拍板結果**，只核對每題「翻案要動哪裡」仍對得上現在的 code（函式／TC 名 grep 得到）、缺欄的補齊 |
| `plan.md` 落地紀錄（「暫定拍板」表／指到 decisions-pending 的題號） | 舊流程留下的、或 build-feature 漏寫進檔的決策（T1…）——漏的補進檔 |
| `code_reviews/<name>.md` 與 review §7 回報 | 「請你拍板的題」、DRY／設計稽核「待拍板」；對照檔裡 review 來源的題，漏的補 |
| `user_story.md` | `⚠️ 暫定改寫` 標記（對應到哪題） |
| 本 session 對話 | user 還沒回答、但說過「下次再討論」的題 |

每題要能回答：現在的做法、為什麼、另一個選項、**翻案要動哪裡**（檔:函式、哪些 TC 翻向、哪則 user_story 要改）、推薦。
「翻案要動哪裡」要用 grep 確認函式／TC 名字真的存在——檔案會被下個 session 直接當施工清單。

## Step 3 — 寫 `<feature 目錄>/decisions-pending.md`（固定骨架）

```markdown
# <feature> 待拍板清單＋施工現況（<日期> <哪個指令>收尾）

> 下個 session 照本檔一題一題拍（user story 格式、一次一題、不彈選項框）。
> 每題拍完在「拍板結果」欄填 ✅ 維持／🔄 翻案（＋一句理由），翻案的照「翻案要動哪裡」施工。
> 全部拍完 ⇒ <下一個里程碑，例如 push／PR／合回 <base_branch>>。

## 0. 現況快照
| 項目 | 狀態 |   ← 分支、commit（hash＋一句話）、tree、push 與否、測試、mutation、story-lock、review、備份 tag、隔離庫、場外異狀
## 1. 實作中重要的 context（拍板時會用到）
   ← 5–8 條：最終形狀、刻意不做的、spec 與現實的落差、會影響拍板的測試／fixture 事實、合流要做的事
## 2. 待拍板總表
| # | 來源 | 一句話 | 推薦 | 拍板結果 |   ← 拍板結果欄留空
## 3. 逐題（user story 格式）
### <#>　<標題>
- **角色**／**情境**／**動作**／**預期行為（現在）**／**為什麼**／**另一個選項**／**翻案要動哪裡**（＋必要時 **附帶**）
## 4. 拍完之後
   ← 編號步驟：翻案施工方式、清備份 tag、push／PR、合流、backlog 對齊
```

寫法：角色與情境用具體人物與日期（同 user_story 的人物，例：行政人員小美、預約者阿明、管理員）、白話、不寫函式名進「預期行為」；
技術細節只放在「翻案要動哪裡」。
檔案已存在 ⇒ 讀它，保留已填的「拍板結果」，只增補新題與更新 §0。

## Step 4 — 記憶（`memory_index` 有設才做）

1. 找專案記憶裡這個 feature 的那一則（檔名含 feature 名）；有就改寫成現況（description 一句話含「下一步逐題拍 decisions-pending.md」），沒有就新建（frontmatter 照專案記憶規範）。
2. `memory_index` 對應那一行改成一句現況＋下一步；不新增重複行。

## Step 5 — 印出開工指令（固定格式，user 原樣貼到新 session）

```
<feature> 拍板 session。開工前置（先做、逐項回報）：① git checkout <分支>，確認 HEAD=<短 hash>、tree=<短 tree>、工作區乾淨、git log <base>..HEAD 共 <N> 顆且零 fixup!；<base> 若前進了先報告、不要自己 rebase；② 跑 <test_busy_check> 確認沒有測試在跑。
然後讀 <feature 目錄>/decisions-pending.md（先 §0／§1 現況與 context，細節要查再看 <列出 plan 落地紀錄節號、test.md 統計節、code_reviews/<name>.md 等實際存在的檔>），照 §2 總表順序 <題號以 → 串起>，一次只講一題、用 user story 格式（角色／情境／動作／預期行為／為什麼＋另一個選項＋你的建議），講完就停、等我回覆再下一題，不要彈選項框。<有附帶題就寫「X 的附帶題（…）跟 X 一起問。」>
每題拍完當下把結果填進 decisions-pending.md 的「拍板結果」欄（✅ 維持／🔄 翻案＋一句理由）。全部拍完先列翻案清單給我看，我說動工才照「翻案要動哪裡」施工（fixup! 到對應 commit → autosquash → 全套，測試一律 <isolated_db_env>=<isolated_db_review> <test_workers_env>=1）。不 push、不開 PR、不刪備份 tag，等我指示。
```

印完補一句：指令假設那時分支還停在 `<短 hash>`；中間有動過，第一步會對不上、它會先報告。

## 禁止事項

- ⛔ 不改任何程式、不 commit、不 push、不刪 tag／分支／隔離庫。
- ⛔ 不在檔案或開工指令裡寫來源沒有的數字（測試數、mutation 數、評分）。
- ⛔ 不替 user 拍：推薦欄寫建議，「拍板結果」欄一律留空（或保留既有已填的）。
- ⛔ 開工指令不重抄規則全文——只放這一輪的事實（hash、題號順序、檔名）和「一次一題、user story 格式」那一句。
