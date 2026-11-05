# CONVENTIONS.md — 寫法慣例（範本）

這份是**範本**：複製到你的專案（預設 `docs/CONVENTIONS.md`，路徑寫在 `## Harness config` 的 `conventions_doc`），
填上自己 codebase 的慣例。它解決的問題：**同一件事在 codebase 裡有五種寫法，agent 每次「照隔壁抄」抄到的都不一樣。**

harness 在哪裡讀它：

| 入口 | 做什麼 |
|---|---|
| `/build-feature` Step 3 | 動筆前先讀對應條目的黃金樣本，照形狀寫；舊 code 跟這份不一致時**以這份為準** |
| `/build-feature` Step 5 | Swagger／API 文件的「長相」照這份，機制照 `api_doc_guide` |
| `neighbor-finder` | 只在這份**沒涵蓋**的東西才派（例：某種特殊的 batch 流程、SSE、檔案上傳）；它回報時會建議該補哪一條 |
| `reviewer` | 違反這份 ＝ Low finding，類別「慣例」 |
| `design-auditor` | 新 code 跟黃金樣本比形狀 |

## 怎麼定規則（先盤點，再定）

1. **先盤點再定規**：派一個只讀子 agent 掃路由檔與各模組 service／repo，把寫法分群（Swagger 幾種、exception 幾種、logging 幾種）列表，
   **每項你選一個 canonical**，不要憑印象訂。
2. **每條規則四件事**：一句規則 ＋ **黃金樣本指標**（`檔::常數或函式`，agent 真的會去讀那一支）＋ 一個反例 ＋ 為什麼。
3. **條數壓在一頁內**，長了就是另一份文件。
4. **舊 code 不一致另開 backlog 分批對齊，不混進 feature commit。**
5. **能機械化的不靠 agent 自律**：能用 lint 規則或 pre-commit 腳本擋的（例：每支 route 必有 `responses=`），寫進最後一節並真的做成檢查；
   判斷型的（命名、docstring 語氣）才交給 reviewer／design-auditor。

---

## 第一部分　API 文件（Swagger）的長相

黃金樣本：`app/api/v1/<module>.py::_CREATE_DESC`（description 的節與語氣）＋ `…::_<ACTION>_RESPONSES`（responses 機制）

### S1　summary：動詞開頭，不帶角色後綴
- 規則：
- 樣本：
- 反例：
- 為什麼：

### S2　description 的節：固定順序
- 規則：例如 `## Auth` → `## 用途` → `## 語意` → `## 守門` → `## 回應`；守門表的順序以 service 的 code 為準、每列附函式名。
- 樣本／反例／為什麼：

### S3　request 範例常數命名、key 用情境
### S4　responses：模組級常數、狀態碼常數、成功也列變體
### S5　共用的 401／403／404 entry 模組級一份
### S6　錯誤變體名：純粹的觸發條件
### S7　範例常數命名
### S8　假資料：固定的 uid 常數、人名、日期
### S9　系統常數引用唯一定義（f-string），不抄字面值

## 第二部分　程式慣例

### C1　分層檔名與 DI 位置
- 規則：例如每個模組固定 `models.py / schemas.py / repo.py / services.py / dependencies.py / exceptions.py`；router 只 import `dependencies.py` 的 `XxxServiceDep`，不直接組 repo。
- 樣本：`app/booking/`

### C2　例外：只 raise 專案例外基底的子類，全放 `exceptions.py`
- 規則：每類必有 `error`（snake_case）＋`message`（給前端直接顯示的原句）＋docstring；內建 `ValueError` 只准在純函式內部。

### C3　logger：raise 前必有，等級定死
- 規則：使用者可自行修正的（403／404／409／422）→ `warning`；500 類、外部系統失敗、資料不一致 → `error`。

### C4　docstring／註解：public 函式必有
- 規則：第一行一句「做什麼」，有守門的接一段守門順序。測試 docstring 第一行固定 `TC-XXnn [US n]：<一句>`。

### C5　守門函式前綴
- 規則：service 層 `_guard_<條件>`；FastAPI 依賴 `require_<角色或條件>`；Pydantic validator `validate_<欄位>`。

### C6　決策標籤：`決策 <feature> D<n>`
- 規則：新 code 在 docstring 或註解記決策時寫 `決策 <feature 路徑> D<n>`（與 plan.md §4 編號一致；D0 是架構）；一條決策的「核心載體」必掛。
  舊格式不回填，但 `codebase-researcher` 會一併 grep。

### C7　repo：過濾用共用 helper、方法名固定、必繼承基底
- 規則：例如可見性過濾一律 `scope_to_<scope>(query, Model, …)`，不手寫 where；動詞前綴只用 `get_／list_／count_／add_／update_／delete_`。

## 機械化（哪些不靠自律）

| 規則 | 怎麼擋 | 狀態 |
|---|---|---|
| 每支 route 必有 `responses=` | pre-commit 腳本 | ⬜ |
| 狀態碼用常數不用 int | lint 自訂規則 | ⬜ |
| service 不 raise 內建例外 | lint 自訂規則 | ⬜ |
