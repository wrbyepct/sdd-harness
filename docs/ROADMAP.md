# 目前的限制與接下來要做的事

[← 回 README](../README.md)

## 目前的限制

- 2026-11-24 這批改版（`/ticket` 入口、BACKLOG 單表、一項一資料夾、指令改收 `#N`、small 精簡規劃）**還沒用真實工作跑過一輪**。
- 2026-11-04／05 這批改版（user story 前置、兩案架構、全程不停＋`decisions-pending`、慣例文件、產品原則）**還沒用真實 feature 跑過一輪**；
  規則都寫進 command 了，但「無人值守下 agent 選的決策會不會系統性偏保守」這類問題要看第一次的翻案率。
- 子 agent 的 Bash／寫檔限制現在由 `hooks/agent_bash_guard.py` 依 `agent_type` 分流（純讀／寫報告／跑測試三種 profile）；
  plugin 裡的子 agent 仍不吃 frontmatter 的 `hooks:`，所以是用 plugin 層級的 PreToolUse hook 做的。
- `mutation-prover` 單路模式直接在工作區改壞再還原（精準字串替換＋grep＋`git diff --quiet` 雙重確認）；有設 `test_tree_env` 才會在拋棄式 worktree 裡打。
- build 改成「主 agent 協調＋每個 Inc 一個 implementer」後跑了四場真實 feature：主 agent 峰值 24～27 萬 token、0 次 auto-compact，每顆 commit 的 token 約為改版前一半。
  implementer 之間不平行（一次一個），因為後一個 Inc 要用前一個新增的介面。
- 例子用的是虛構的會議室預約系統；command 的規則本身來自真實專案的踩雷紀錄。

## 未來優化

這套 harness 不是定稿：每一輪真實的 build／review transcript 都會被拿來檢討，踩到的坑會回寫成規則；
我也正在自學 Stanford CS146S（The Modern Software Developer），把課程內容對照到這套流程上持續改進。
下面是目前排定的優化項目，做完會更新到這裡。

| # | 項目 | 要解決的問題 | 狀態 |
|---|---|---|---|
| 1 | **Research 階段獨立** | 做成 `codebase-researcher` agent（只讀、只記現況、不提方案），由 `/user-story` 需求模式派出，產出 `research.md` 供後面所有文件引用編號 | ✅ 完成（待真實驗證） |
| 2 | **plan 先出兩個正交的架構方案** | `/plan-feature` S0.5：每次兩案、對照表勝平負、選定記 `D0`、清 context 再往下走（`proposal.md`） | ✅ 完成（待真實驗證） |
| 3 | **需求 ↔ 測試追溯強制化** | `[US n]` 標記與對帳腳本已上線；下一步是舊 feature 回填，並用 hook 在 commit 時擋下沒標記的 TC | 進行中 |
| 4 | **用 hooks 把流程紀律變成機制** | 「先改 spec 再改 code」這類規則目前寫在 prompt 裡，是請求不是保證；逐條評估能否改成 hook 擋下 | 規劃中 |
| 5 | **品質判斷交給專責的 review agent** | 6 個 review agent 已上線；持續用真實 transcript 校準每個 agent 的判準與回報格式 | 進行中 |
| 6 | **context 瘦身** | 主 agent 與每個子 agent 都要載入專案規則；不需要的子 agent 用 `omitClaudeMd` 跳過，記憶索引改成按需讀取 | 規劃中 |
| 7 | **背景化與 worktree 隔離** | build → review 已能背景串接；下一步用 worktree 隔離取代「同一工作區並行」的各種防護 | 進行中 |
| 8 | **教訓庫回填** | 把歷史 code review 的 Critical／High 蒸餾成可召回的教訓檔 | ✅ 完成 |
| 9 | **子 agent 硬限制** | `hooks/agent_bash_guard.py` 依 `agent_type` 三種 profile 擋 Bash 與寫檔；會改 code 的放進 worktree 還沒做 | 進行中（hook 已上線） |
| 12 | **流程規則寫進 command，不只放 memory** | 「每次跑都要照做」的規則一律寫進 command 本文；memory 只留為什麼。順手把 148 則 memory 掃過一遍，7 處搬進 command | ✅ 完成 |
| 13 | **實作到 review 全程不停** | 新決策點不停：當下寫進 `decisions-pending.md`、選最好的做；只在不可逆的事停。收尾自動接 `/decision-handoff`，拍板集中到下一個 session | ✅ 完成（待真實驗證） |
| 14 | **寫法慣例文件＋黃金樣本** | `docs/CONVENTIONS.md`：先盤點 codebase 寫法分群、每項挑一個 canonical、每條規則指一支真的去讀的樣本；reviewer 違反算 Low。能機械化的（route 必有 responses、不用 int 狀態碼）改 lint 規則 | 文件完成，機械化規劃中 |
| 15 | **產品原則文件** | `docs/PRODUCT_PRINCIPLES.md`：編號＝優先序，每條一句立場＋裁決過的例子＋何時反過來；`/user-story` 逐則對照、`/plan-feature` 當常駐第一 driver | ✅ 完成 |
| 16 | **無人值守真的不停** | 實查 transcript：會停的只有「寫 `.claude/`」與「Bash heredoc 寫檔」兩種內建安全確認。教訓庫搬出 `.claude/`、寫檔一律 Write／Edit（見 `docs/CONFIG.md`） | ✅ 完成（待真實驗證） |
| 17 | **build 主 agent 只協調** | 主 agent 自己做完 7 個 Inc 時 context 漲到 97 萬、auto-compact 兩次、cache_read 佔全部 token 3/4。改成每個 Inc 派一個 `implementer`（`inc_brief.py` 抽規格、主 agent 只手寫「前面留下的」一段、四狀態回報） | ✅ 完成（四場真實驗證） |
| 18 | **子 agent 分模型** | 判準是「做錯會不會被下一步自動抓到」：`test-runner` 用 haiku、`mutation-prover` 用 sonnet（主 agent 驗回報完整）；判斷類的留跟主 agent 同模型 | ✅ 完成（真實驗證） |
| 19 | **立題入口與任務分級** | `/ticket`：一句需求 → 一張只寫「要什麼、從哪接」的 ticket；tiny／small／medium／large 四級，large 拆母題＋子題（上游複查時回填下游的入口、跨張決定寫回母題）；BACKLOG 改成可機械檢查的單表 | ✅ 完成（待真實驗證） |
| 10 | **agent 查書** | 測試經典（Khorikov《Unit Testing》、Freeman & Pryce《GOOS》）已轉成可檢索的切片；讓 reviewer 在判斷 mock 用法、over-specification 時引用章節 | 規劃中 |
| 11 | **舊文件不再誤導 agent** | feature 文件按時間分資料夾，同一個行為的最新版散在多份文件裡。做法：舊文件加「歷史文件」橫幅、code 裡用 `決策 <feature> D<n>` 標籤指回決策、research 依「API 文件 → 測試 → code → 決策」順序讀、腳本檢查標籤沒有斷指標 | 設計定案 |
