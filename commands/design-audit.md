---
description: 嚴格的業務邏輯設計稽核——找出「行為對、但寫法繞／不夠優雅／不夠高效／沒照 best-practice design pattern」的地方，產出排好順序的清單讓使用者逐條拍板，拍了才動工；動工先用行為快照測試鎖住現況（先綠）、再重寫、重寫後原樣綠＋mutation 證明快照真的有咬住。帶參數掃整個模組（`/design-audit <模組路徑>`），不帶參數掃當前 diff。與 /dry-audit 同款三段式，可背靠背跑；`--auto` 或被 /auto-code-review 呼叫時零停頓、只做證據網完整的項、fixup 到目標 commit；DRY 重複交給 /dry-audit，本 skill 不重複抓。
allowed-tools: Bash(git:*), Bash(python3:*), Bash(grep:*), Bash(ls:*), Bash(sed:*), Bash(wc:*), Bash(find:*), Bash(cat:*), Bash(mkdir:*), Read, Edit, Write, WebFetch, WebSearch, AskUserQuestion
---

## Context

- Current branch: !`git rev-parse --abbrev-ref HEAD`
- Working tree status: !`git status -s`
- Latest commit: !`git log -1 --format="%h %s"`
- Diff (working changes; 空的話 fallback 到 HEAD): !`git diff HEAD --stat`
- Harness config: !`grep -A 20 '^## Harness config' CLAUDE.md 2>/dev/null || echo "(CLAUDE.md 沒有 Harness config 段；照 plugin 的 docs/CONFIG.md 補上)"`
- Python / 主要套件版本: !`grep -E '^(requires-python|    "(fastapi|sqlmodel|sqlalchemy|pydantic)[>=~])' pyproject.toml`
- 使用者給的參數（掃描範圍）: `$ARGUMENTS`

下文的 `<test_cmd>`、`<lint_cmd>`、`<test_busy_check>` 等角括號名稱，一律指 CLAUDE.md `Harness config` 段的同名 key。

## Your Role

You are a senior FastAPI backend developer doing a **design & elegance audit of business logic**.
The code you are looking at already passes its tests. That is the entry ticket, not the bar.
The bar, in the user's words:

> 實作的行為是對的，但邏輯有點繞、不夠優雅。要以最 elegant ＋ efficient 的方式寫，並符合 best-practice design pattern。

**優雅的操作型定義（本 skill 唯一的判準）**：
把那段程式碼在回答的業務規則用**一句白話**寫出來；優雅的程式碼讀起來跟那句話**一一對應**——
段落數＝規則的子句數、分支數＝規則真正的例外數、沒有一行是為了「繞過自己前面幾行」而存在。
繞 ＝ 程式碼的形狀跟規則的形狀不一致。

**你跟鄰居 skill 的分工**（不要越界）：
- **/dry-audit**：同一條規則寫了幾份 → 那邊抓。本 skill 看到重複只在報告「另見」節提一行。
- **/code-review**：正確性、測試嚴謹度、Swagger → 那邊。本 skill 不審 bug（看到就記「另見」，不下修）。
- **整檔重構**：使用者指定一個檔整檔重寫，不是本 skill 的事。本 skill 是掃描器＋逐條拍板，施工單位是「一個 finding」不是「一個檔」。

---

## 核心判準：三個問題，每一組候選都要答完

| 問題 | 答「是」的意思 |
|---|---|
| **① 形狀對得上規則嗎？** 一句白話 vs 程式碼段落。 | 對得上 → 不是 finding，不管它長不長 |
| **② 慣例對得上鄰居嗎？** 同模組／同層最相似的既有實作長什麼形狀？ | 對得上 → 不是 finding；偏離但有明列理由（plan.md 決策 D<n>）→ 不是 finding |
| **③ 改法能用既有測試證明行為不變嗎？** | 不能 → 先進 Step 6 的快照流程；補不出快照 → 標「不動」 |

三題都過才是 finding。**「我覺得可以更漂亮」不是 finding**；要指出它違反的是哪個鏡頭、
改了之後少幾個分支／幾趟往返／幾個參數，可量化。

🔴 **不早熟 pattern**：design pattern 是手段。引進一個 Strategy／Registry／基底類別，必須能指出
它**消掉了什麼**（≥2 個同構分支、一張手寫 switch、一組必須同步的觸點）。消不掉東西的 pattern
是 finding 的反面（過度設計），要列在「刻意不動」節。

---

## Step 0 — 決定掃描範圍（與 /dry-audit 同規則）

**模式甲：帶參數** → 整模組。路徑或 feature／模組名，可多個；只掃該模組的 service、repo、
schema（validators）與它在 API 層的 router——**業務邏輯在哪就掃哪**。
`tests/` 不掃。

**模式乙：不帶參數** → diff。從 `git diff HEAD`（空則 `git show HEAD`）抓出被動到的函式，
**整支函式**看，不是只看 hunk——繞常常是 hunk 之外那幾行造成的。

兩種模式都先讀 `<feature_dir>` 底下的 `plan.md` 決策表（D<n>）：spec 明列的取捨（例如「刻意分兩支不合併」、
「順序守門必須先 A 再 B」）是慣例的一部分，不是 finding。

## Step 1 — 前置查證（做完才准寫 finding）

1. **版本**：`pyproject.toml` 的 Python／FastAPI／SQLModel／SQLAlchemy／Pydantic 實際版本。
   引用任何「更 idiomatic 的寫法」前確認該版本真的有（例：`match` 需 3.10+、`itertools.batched` 需 3.12+）。
2. **官方文件**：對每一個你打算主張「這才是 best practice」的第三方 API（`selectinload`、
   `model_validator`、`Annotated` DI、`asyncio.gather`…），WebFetch 該版本的官方文件確認。
   **沒有版本相符來源的主張不准寫進 finding**（只能寫「觀察」）。
3. **鄰居**：對每個目標函式，找出同層最相似的 1–2 支既有實作並讀完（同模組 > 其他模組同類）。
   慣例是從這裡來的，不是從你的品味來的。

## Step 2 — 獵殺鏡頭（十個，逐個跑完不能跳）

對範圍內每支函式主動問，不要等問題跳出來：

1. **控制流形狀**：巢狀 `if` 深度 ≥3？該早退（guard clause）卻往下包？布林旗標一路傳只為了
   最後一個 `if`？`try` 包了整支函式但只有一行會拋？同一個 `None` 檢查做三次？
2. **分支對規則**：`if/elif` 鏈在對 enum 或 code 分派 → 該是 dict dispatch／`match`？分支數 > 規則的
   例外數 → 有分支在處理「自己前面幾行製造的狀態」。
3. **函式高度**：一支函式做幾件事？（讀出來的段落註解就是拆點）超過一屏且段落 ≥3 → 拆；
   參數 ≥6 → 該收成一個 dataclass／既有 schema；**布林參數改變函式行為** → 拆兩支或改 enum。
4. **資料流**：中間變數被覆寫多次？dict 當結構體傳（該是 `NamedTuple`／`dataclass`／既有 schema）？
   平行 list 該 zip 成物件？同一份資料遍歷多次可一次 pass？迴圈內算不變值？
5. **資料庫往返預算**（效率的主戰場）：每個 service 方法數 round trip；N+1；迴圈內 query；
   可合併的兩趟 SELECT（一趟 `IN` 查兩道門）；寫後多餘回讀；該 bulk 的逐筆；
   `await` 串行但彼此獨立（該 `asyncio.gather`）；多餘 `flush`／`refresh`／`commit`。**寫出數字**。
6. **在 Python 做 DB 該做的事**：全撈再篩、Python 排序 DB 該 `ORDER BY`、Python 去重 DB 該 `DISTINCT`；
   反之也算：SQL 裡塞了業務判斷該在 service 講清楚。
7. **分層高度**：router 有邏輯／service 組 SQL／repo 做語意判斷／schema 碰 DB。任何越界都算，即使能跑。
8. **資料結構選型**：list 做 membership（該 set）、多次 `dict` 查同 key、`sorted()[0]` 該 `min()`、
   手寫 groupby 該 `itertools.groupby`／`defaultdict`。有界小 n 只在**有註明上界**時放行。
9. **命名與意圖**：名字說謊（`get_` 會寫、`build_` 會 mutate、`check_` 會 raise 卻沒說）；
   `flag`／`data`／`result` 這種無資訊名；註解在解釋「在做什麼」而不是「為什麼」（= 程式碼本身沒講清楚）。
10. **錯誤處理形狀**：守門順序沒照「便宜的先、貴的後」；raise 前沒 log（若專案慣例要求）；`except Exception` 吞掉再
    包；同一個 409/422 判準寫成兩種形狀。

**「另見」**（記錄不處理）：重複（→ /dry-audit）、疑似 bug（→ /code-review）、測試品質。

## Step 3 — 每條 finding 的必填內容

```
### F<n> — <一句話：哪支函式，哪個鏡頭>   〔嚴重度〕
- **規則一句白話**：這段程式碼在回答什麼業務問題
- **現況形狀**：file:line 起訖；分支數／段落數／往返數／參數數（能數的都數）
- **繞在哪**：哪幾行是在處理「自己製造的狀態」、哪個分支在規則裡不存在、哪一趟往返可省
- **鄰居怎麼寫**：file:line 同層最相似的既有實作；本段偏離它的地方
- **建議形狀**：目標形狀一段（可以是偽碼）；改後的分支數／往返數／參數數
- **來源**：主張用到的第三方 idiom 的官方文件 URL（版本相符）；純結構問題寫「專案慣例：<鄰居>」
- **證據網**：現有哪些 TC 蓋到這支函式（`grep -rl "<function>" tests/`）；缺口在哪一條路徑
- **風險**：重寫最可能改變行為的地方（順序？None 分支？例外類型？）
```

**嚴重度校準**（跟 /code-review 對齊，讀報告的人不用切換腦袋）：
- **High**：每請求多一趟 DB 往返或 N+1 在熱路徑；獨立 `await` 串行等待
- **Medium**：分層越界；未註明上界的 O(n²)；巢狀深度 ≥3 且可早退；布林參數改行為；參數 ≥6
- **Low**：有界 n 低效無註記；函式 ≥3 段落可拆；dict 當結構體；手寫 groupby
- **Nitpick**：命名、註解講 what、多餘中間變數

**排序**＝嚴重度 → 該函式的改動頻率（`git log --oneline -- <file> | wc -l`）→ 證據網完整度
（有測試蓋住的先做，便宜又安全）。

## Step 4 — 報告落地

寫到 `code_reviews/design/<scope>-<YYYY-MM-DD>.md`（建議把 `code_reviews/` 加進 `.gitignore`）：

1. **一行範圍宣告**（模式、掃了哪些檔、幾支函式、前置查證做完）
2. **做得好**（形狀對得上規則、慣例一致、往返精省的地方——點名，讓使用者知道哪裡不用碰，
   也是下次的「鄰居」樣本）
3. **Findings**（Step 3 格式，照排序）
4. **刻意不動**（過了①②但沒過③且補不出快照的；看起來繞但 plan.md 有明列理由的；
   pattern 化會變過度設計的——每條一行理由）
5. **另見**（重複／疑似 bug／測試品質，各指回對應 skill）
6. **建議施工順序與分顆**

報告寫完**停下來**，用 `AskUserQuestion` 逐條（或分批 ≤4）讓使用者拍：**做／不做／改建議**。
三句話格式：問題／建議＋理由／影響。沒拍的不准動。

## Step 5 — 施工前置（每次都查，不憑記憶）

- `<test_busy_check>`：有人在跑就**不起測試、不動產品程式碼**。
- `git status -s`：工作區有別人的未落地改動就先問。
- 若專案有記錄並行工作的地方（backlog、分支約定）：有沒有並行軌。
- 確認 base 分支（`<base_branch>`）與落地方式。

## Step 6 — 施工（一條 finding 一輪；行為不變是硬約束）

1. **證據網盤點**：列出蓋到目標函式的所有 TC（直接呼叫的＋走端點的）。跑一次確認全綠（基線）。
2. **補行為快照（先綠，不是先紅）**：對證據網沒蓋到的每一條路徑（每個分支、每個早退、每種例外），
   寫一條 TC 鎖住**現況**——包含現在的訊息字串、現在的狀態碼、現在的寫入結果。
   這些 TC 命名 `test_snapshot_<function>_<path>`，docstring 寫「行為快照：design-audit F<n>，
   鎖住重寫前的行為」。**寫的時候不准修現況**——覺得現況是 bug 就記「另見」，快照照現況鎖。
   補不出來（需要無法造的前置、或路徑根本不可達）→ 這條 finding 改標「不動」，回報告。
3. **快照有效性 mutation（重寫前）**：對目標函式打一發「會改變行為」的突變（翻一個分支、
   換一個 `<` 成 `<=`、拿掉一個早退），**快照＋既有 TC 必須紅**。不紅 ＝ 證據網有洞，回到 2。
4. **重寫**：照建議形狀寫；照鄰居慣例；第三方 idiom 只用 Step 1 查證過的；docstring 只講「為什麼」。
   不順手改範圍外、不順手修「另見」。
5. **原樣綠**：證據網＋快照**一字不改**全綠。有任何一條要改期望值 → 停，那不是重寫是改行為，
   回報告當「另見」給使用者決定。
6. **重寫後 mutation**：再打一發（不同位置），確認測試網對新形狀仍有咬合。
   還原一律 apply／revert 成對字串反轉，禁 `git checkout`，禁空 pattern。
7. **量化回報**：分支 a→b、往返 x→y、參數 m→n、行數 p→q（至少一項有變，否則這條 finding 不成立）。
8. **全套**：`<test_cmd>`；動到查詢或契約的，補上專案的慢測試開關（例：`--slow`）；`<lint_cmd>`。
9. **commit**：一條一顆（除非使用者拍板合併），格式照專案慣例，例如：
   `refactor(<scope>): Restructure <function> for <what it fixes> & the complete test suite`，
   body 列量化數字、快照 TC 名、兩發 mutation 結果、官方文件來源。快照 TC 留著不刪——它們現在是
   這支函式的規格。

## Step 7 — 收尾回報

- 每條做完：量化前後、快照幾條、mutation 兩發各紅了哪些、來源 URL。
- 每條沒做：使用者拍「不做」、或「不動」的理由。
- 全套前／後 passed 數、lint 綠。
- 回寫報告狀態欄（🏁／⬜／❌）。
- 若專案有 journal，寫 `journal/<YYYY-MM-DD>/design-audit-<scope>.md`：這輪學到的「看起來繞其實有理由」與
  「鄰居慣例其實是錯的」案例——這兩類判例決定下次的校準（有普遍性的也可寫進 `lessons/`）。

---

## 無人值守模式（被 `/auto-code-review` 呼叫、或參數含 `--auto` 時）

同 /dry-audit：**沒有任何 `AskUserQuestion`**，停頓換成更嚴的準入門檻。

| 項目 | 互動模式 | 無人值守模式 |
|---|---|---|
| 範圍 | `$ARGUMENTS` 或 diff | **目標 commit 動到的函式**（整支看）＋ §4 修正後的工作區 |
| 拍板 | Step 4 逐條問 | **不問**。自動施工的條件＝三題全過 **且** 嚴重度 ≥ Low **且** Step 6 第 3 步（重寫前 mutation）實跑有紅；Nitpick（命名、註解）**只列不改**——改名會波及呼叫端，不該在無人時做 |
| 快照補不出 | 標「不動」回報告 | 同，且**不嘗試造複雜前置**——超過三條快照還補不完證據網的 finding 直接列「待拍板」 |
| 期望值要改 | 停下來問 | **一律不改**，該 finding 撤回、寫進「另見」（那是行為改動，不是重寫） |
| 報告 | `code_reviews/design/<scope>-<date>.md` | **附在主 review md 尾端**新增一節 `## 設計稽核（/design-audit）`，同格式 |
| 測試 | `<test_cmd>` | **一律用 `/auto-code-review` §1 的隔離 DB runner**（`<isolated_db_env>=<isolated_db_review>`）；lint 用收窄到自己檔案的 `<lint_cmd>` |
| commit | 一條一顆 refactor commit | **`git commit --fixup=<target>`**（同 §6）；快照 TC 一起進 fixup |
| 官方文件查證 Step 1 | 必做 | 必做（不因無人而省——沒來源的主張仍只能寫「觀察」） |

Hard rules 全部照舊。收尾回報併入 `/auto-code-review` §7。

---

## Hard Rules

- **行為一字不變**。既有 TC 與快照 TC 的期望值不准改；要改就是改行為，交回使用者。
- **沒證據網不重寫**。補不出快照的路徑標「不動」。
- **主張 idiom 必附版本相符的官方來源**；沒來源只能寫「觀察」，不進 finding。
- **pattern 必須消掉東西**。引進抽象卻沒減少分支／觸點／往返 ＝ 過度設計，列「刻意不動」。
- **不審 bug、不抓重複**。記「另見」指回對應 skill。
- **不順手**。範圍外一律「另見」。
- **有測試在飛時產品程式碼一字不動**。
- **使用者沒拍的不動**。

## Language

說明一律台灣繁體中文；程式碼、識別字、commit 標題英文。使用者可見的決策題用三句話格式。
