# lessons/ — 實作教訓庫

**一則教訓一個檔**，按模組分目錄，`lessons/INDEX.md` 是索引。
跟專案長期記憶（`memory_index`）的分工：memory 管「怎麼合作、專案做到哪、使用者的硬規則」；
lessons 管「**這段 code 附近會踩什麼**」。

## 誰寫、誰讀

| 入口 | 什麼時候 | 做什麼 |
|---|---|---|
| `/auto-code-review` §7 | 每輪收尾 | 把「值得記住的三件事」寫成檔 |
| `/build-feature` 收尾 | 每個 feature 收尾 | 「踩到的雷」「補的 spec gap 裡有普遍性的」寫成檔 |
| `lessons-recaller` agent | 開工前（plan、build、review） | 先讀 `INDEX.md`，挑相關的打開；再看 memory 的硬規則；lessons 太薄才翻 `code_reviews/` |

這是一個閉環：review 找到的問題 → 寫成教訓 → 下一個 feature 規劃與實作前被召回 → 同一個坑不踩第二次。

## 格式（照這個，`lessons-recaller` 靠 frontmatter 篩）

檔名：`lessons/<area>/<YYYY-MM-DD>-<slug>.md`。area＝模組名；跨模組放 `general/`；測試基礎設施放 `testing/`；migration 放 `migrations/`。

```markdown
---
area: booking                     # 模組；多個用 [booking, auth]，檔案住第一個的目錄
kind: visibility                  # 一個詞：visibility / boundary / ordering / migration / contract / dry / perf / testing …
keywords: [additive field, is_room_admin, member]   # 函式名、表名、業務詞，給 grep 用
source: code_reviews/<file>.md#F3 | features/<name>/plan.md
date: 2026-09-17
status: active                    # active / superseded（被後來的決策推翻時改這個，不刪檔，加 superseded_by）
---

# <一句話教訓，當標題>

**當時怎麼踩到的**（兩三行，具體：哪個 feature、哪個函式、錯在哪、誰會受害）

**為什麼危險**（一行：會不會有人發現、多久）

**下次怎麼避免**（具體到：寫哪種 code 時先看什麼；要補哪種 TC；哪個既有函式是對的範本）
```

範例（虛構的會議室預約系統）：

```markdown
---
area: booking
kind: visibility
keywords: [additive field, is_room_admin, member]
source: code_reviews/add_booking_note.md#F2
date: 2026-09-17
status: active
---

# 回應加新欄位時，先看隔壁欄位掛了什麼權限閘門

**當時怎麼踩到的**：預約回應新增「內部備註」欄位，直接回給所有人；隔壁的「預約人電話」只回給會議室管理員。一般成員因此看得到別人的內部備註。

**為什麼危險**：沒有任何錯誤訊息，測試只驗管理員視角所以全綠，要等使用者截圖回報才會發現。

**下次怎麼避免**：新增 additive 欄位前，先找同一個 schema 裡最像的欄位、照抄它的權限判斷；test.md 補一條「一般成員看不到」的負向 TC。
```

## 跟長篇 gotchas 文件的分工

`gotchas_docs`（例如 ORM、migration 的踩雷文件）是長篇教訓（每條含 What／Why／錯誤修法／正確修法），**不轉成 lessons、不複製**。
`INDEX.md` 末段列它們每一條的標題當入口。新教訓寫哪邊：**說明超過 30 行、需要展示「錯誤修法」的寫 gotchas**，其他寫 lessons；
重疊時 lessons 保留短版、`source` 指向那條 gotcha。

## 規矩

- 一檔一則；一則不超過 30 行。寫不進去就是兩則。
- 必須有 `source`，沒證據的不是教訓是意見。
- 被推翻不刪，改 `status: superseded` 並加 `superseded_by:`；recaller 只回 active。
- 寫完重建索引：`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lessons_index.py --gotchas <gotchas_docs>`。不要手改 INDEX.md。
  `--check` 只檢查格式，可以掛 pre-commit。
- 跟 memory 的硬規則重疊時，lessons 寫技術細節、memory 留一行指過來，不要兩邊各寫一整份。
