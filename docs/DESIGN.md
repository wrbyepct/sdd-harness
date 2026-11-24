# 為什麼這樣設計

[← 回 README](../README.md)

## 權威順序與人工關卡

**權威順序：產品原則 > user story > plan 三文件。** user story 是規劃的**輸入**，不是輸出；
實作與審查全程不停，碰到的決策先選最好的做下去、記成一題，集中到下一個 session 拍板。

**所有工作從 `/ticket` 進**：一項工作一個資料夾 `features/<N>-<name>/`（`ticket.md`＋之後的四文件），`features/BACKLOG.md` 是單表索引，
之後每支指令都收 `#N`。級別分 tiny／small／medium／large：tiny 直接修、small 走精簡規劃、large 拆成母題＋子題。

**五個人工關卡**（其他全部無人值守）：

| 關卡 | 人做什麼 |
|---|---|
| ticket 定稿 | 給一到三個具體例子、拍級別、看整張 ticket（只寫要什麼與從哪接，不寫解法） |
| user story 拍板 | 先看一則範例、確認格式與用詞，再看整份；每則對照產品原則 |
| 架構 A/B 裁決 | `/plan-feature` 先出兩個正交的架構方案（`proposal.md`），你看對照表選一個，選完清 context |
| plan 決策點 | 每個決策看 A/B/C 比較表後選一個，決策編號 `D<n>`、附 why |
| 拍板 session | build 與 review 期間 agent 自己選的決策都寫在 `decisions-pending.md`；你開新 session 一題一題拍，翻案當場 fixup |

agent **仍然會停下來問**的只剩不可逆的事：刪欄位／刪資料的 migration、push、動到別人的在製品。

## 五條設計理念

### 1. 文件是決策紀錄，測試是行為的保證
plan 記「為什麼」（D 編號），user story 記「做出來會怎樣」（給不寫程式的人看），test.md 把每一則 user story
變成可執行的鎖。三者用 `[US n]` 標記串起來，`scripts/story_lock_check.py` 機械對帳，`story-lock-auditor`
再逐則確認 assert 真的咬住預期行為。

### 2. 子 agent 的價值是隔離，不是分工
pytest 幾百行輸出、幾千行的 diff、翻遍兩百則記憶找教訓——這些都交給子 agent，主 context 只收一張表。
每個 agent 的 `tools:` 只給它需要的（純讀的不給寫入工具），審查與修 code 分開：
**找問題的 agent 不改 code，改 code 的主 agent 不審自己。**

### 3. 不相信推論，只相信實跑
- `finding-verifier`：對每條 Critical／High finding 做對抗式驗證，**給不出具體重現輸入就降級**。
  錯的 finding 代價很高：改 code、補測試、再被 mutation 打，整串白做。
- `mutation-prover`：每一條修正與鎖，都實際把原始碼改壞、跑測試、確認變紅、再還原。
  早期用「讀 code 推論哪些測試會紅」，結果漏掉分支，而且錯的方向永遠是高估自己的測試。

### 4. 教訓要能被召回，不然只是日記
review 收尾把「值得記住的事」寫成 `lessons/<area>/` 一則一檔（格式見 `docs/LESSONS.md`），
`lessons-recaller` 在 plan、build、review 開工前依模組與關鍵字撈出最相關的十條，
落到該用的地方（某個決策的比較表、某條要補的 TC）。

### 5. 文件有權威順序，衝突時不用猜

```text
產品原則  >  user story  >  plan.md / detailed-plan.md / test.md  >  code
```

| 層 | 回答什麼 | 誰讀、什麼時候 |
|---|---|---|
| `docs/PRODUCT_PRINCIPLES.md` | 這個產品**怎麼做決定**（編號＝優先序，每條附裁決過的例子與何時反過來） | `/user-story` 逐則對照；`/plan-feature` 兩案對照表的常駐第一 driver |
| `user_story.md` | 做出來**會怎樣**，給不寫程式的人看 | 規劃的輸入；`story-lock-auditor` 拿它當靶；實作後複查定稿 |
| plan 三文件 | **為什麼這樣做**（D 編號）、落在哪支函式、哪條測試鎖住 | `/build-feature` 照它寫；`reviewer` 對它審 |
| `research.md` | 開工時系統**現在**怎麼做（一次性快照，有編號） | 上面三層引用它的編號，不憑印象描述現況 |

上層與下層衝突時，下層錯：plan 跟 story 不一致就改 plan；story 違反原則就改 story，或明寫一條例外。
agent 在實作中發現 spec 漏寫而自己做了決定，不能改上層文件，只能寫進 `decisions-pending.md` 等人拍板。
這條鏈讓「這個行為到底該是什麼」永遠有一個地方可以查，而不是翻對話紀錄。
