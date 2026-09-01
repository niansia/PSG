<div align="center">

<img src="docs/assets/psg-concept.png" alt="PSG — 專案狀態圖" width="100%">

# PSG

### project state graph／專案狀態圖

**安裝一次。初始化一次。然後照常寫程式。**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-6EAEDB?style=flat-square)](https://www.python.org/)
[![CI](https://github.com/niansia/PSG/actions/workflows/ci.yml/badge.svg)](https://github.com/niansia/PSG/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v1.1.1-F3B557?style=flat-square)](https://github.com/niansia/PSG/releases/tag/v1.1.1)
[![Status](https://img.shields.io/badge/status-complete%20MVP-FF9364?style=flat-square)](docs/acceptance.md)

[English](README.md) · **繁體中文** · [简体中文](README.zh-CN.md) · [日本語](README.ja.md)

</div>

PSG 是一組 Skill bundle 加上本機 runtime，它給你的 coding agent 三樣東西：對專案的持久記憶、明確的可改動邊界，以及以證據為準的「完成」定義。它與 Git 和你既有的 Skill 並存；它不取代你的 coding agent，也不會自己改動原始碼。

> 你照常用日常語言提出需求。PSG 在背後取出相關脈絡、保護鎖定的決策與檔案、執行你授權的檢查、把 review 限制在你真正要求的任務範圍內，並阻止過期或缺乏支持的證據被當成「做完了」。

## 安裝

安裝一次即可。這個指令會安裝 runtime、完整的 Skill bundle，以及為每個偵測到的 Codex、Claude Code 或 Gemini CLI host 設定 MCP 整合。

### Windows

```powershell
python -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.1"; psg setup
```

### macOS / Linux

```bash
python3 -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.1" && psg setup
```

然後為每個 Git 專案啟用一次：

```text
cd your-project
psg init
```

## 照常使用

就這樣。之後照常跟你的 coding agent 對話：

```text
幫我在購物車是空的時候顯示一段友善提示，完成後幫我驗證。
```

PSG Skill 啟用後，它會開啟並追蹤任務、取出有邊界的脈絡、驗證真實的最終 diff、記錄可信的驗證結果、把 review 限制在任務內，並評估 ship gate。日常工作不需要你手動操作它的圖。

日常只有這幾個控制項：

```powershell
psg status       # 查看 PSG 是否啟用，以及它知道些什麼
psg off          # 暫時停用自動治理
psg on           # 重新啟用
psg handoff      # 產生給其他模型或同事的 review pack
```

`psg off --global` 與 `psg on --global` 會暫停或恢復所有已初始化專案的自動治理。`psg update` 安裝最新的穩定 `vX.Y.Z` release；除非你明確指定 `psg update --channel dev`，否則它永遠不會跟隨 `main`。`psg doctor` 與 `psg uninstall` 負責健康檢查與移除；解除安裝會保留每個專案持久的 `.psg/` 狀態。

### 兩種使用模式

| 模式 | Host | 你得到什麼 |
| --- | --- | --- |
| **完整執行** | Codex · Claude Code · Gemini CLI | Skill 加上本機 runtime 與 MCP server。邊界是**被強制執行**的：mutation policy 針對真實 diff 檢查、驗證由 runtime 背書、ship gate 由機器評估。 |
| **Review／交接** | ChatGPT · Claude · Gemini | 上傳 `psg handoff` 產生的 review pack。審查者讀到的是同一份 Task Contract 與同一套 review 邊界。 |

六者共用同一份 Task Contract。只有執行端具備 runtime 強制力 —— 聊天端的審查者是「遵循」契約，而不是「執行」契約。

```powershell
psg handoff
```

Review pack 會寫到 `.psg/local/handoffs/<task>.md`，這個路徑 Git 會忽略。這點很重要：寫進工作目錄的 review 檔會變成未追蹤的專案變更，反而擋住它本來要協助通過的 ship gate。`--output` 可以寫到別處，若路徑落在工作目錄內會發出警告。

`psg handoff` 嚴格唯讀：它不會改變任務狀態，也不會寫入事件記錄。

## 支援的 agent

| Agent | PSG Skill | PSG runtime | 自動安裝 |
| --- | ---: | ---: | ---: |
| Codex | ✓ | ✓ | ✓ |
| Claude Code | ✓ | ✓ | ✓ |
| Gemini CLI | ✓ | ✓ | ✓ |
| 泛用 Agent Skills + MCP | ✓ | ✓ | 手動 |

`psg setup` 會自動偵測已安裝的 host、複製整個資料夾 bundle、透過每個 host 原生的 CLI 註冊 `psg-mcp`，並記錄整合狀態。`psg setup --all` 是「安裝到所有偵測到的 host」的明確別名。wheel／原始碼安裝與進階備援方式請見[安裝與 host 設定](docs/installation.md)。

## 為什麼需要 PSG

PSG 針對的是讓 agent 輔助開發變得令人挫折的那些日常問題：

- 每開一個新對話就要重讀同一個 repository；
- 重要的約束在不同 session 之間消失；
- 一個小需求動到不相關的檔案；
- 「測試通過了」指的是早就被改掉的程式碼；
- 一個兩行的修正，review 回來一份「這個專案所有問題」的清單；
- 反覆 review 一再翻案已經接受的取捨；或
- 沒有人說得出為什麼這件工作算完成了。

PSG 把這些問題變成五個具體的保護機制：

| 你需要 | PSG 提供 |
| --- | --- |
| 正確的脈絡 | 由檔案、Python 符號、相依關係、任務、決策與約束建出的 token 預算內工作集。 |
| 安全的改動 | 針對最終 Git 狀態的政策檢查，涵蓋已暫存、未暫存、重新命名、刪除與未追蹤的檔案。 |
| 可信的證明 | 驗證與驗收證據綁定到確切的工作樹與其真實來源。 |
| 有邊界的 review | 由 Task Contract 決定哪些發現屬於**這個**任務，哪些是後續事項。 |
| 真正的完成線 | 只有當範圍、檢查、驗收條件、review、當前程式碼與風險要求全部一致時，才會是 `SHIPPABLE`。 |

## Task Boundary（任務邊界）

> **嚴重度不等於任務範圍。**
> **更多脈絡不等於更多權限。**
> **每個任務都有邊界。每次 review 都留在邊界內。**
> **Review 這個任務，不是整個宇宙。**

`blocker` 陳述的是「這件事有多嚴重」，而不是「這件事屬不屬於你要求的任務」。把兩者當成同一件事，正是一行修正變成一週工程的起點。

`psg task open` 記錄一份正式的 **Task Contract**：目標、脈絡、mutation、範圍、review、完成與風險邊界。`review_record` 會驗證它的 hash，所以一輪 review 永遠無法擴大它正在 review 的那個任務。

### 更多脈絡不等於更多權限

任務開啟時是 **DRAFT**。它陳述意圖、請求範圍，但完全不持有寫入權限 —— 此時嘗試改檔案，gate 會告訴你契約尚未封存。

接著初次定位會將它 **SEAL（封存）**：PSG 推導出的 mutation 邊界成為 `authorized_write`、`authorized_read_only` 與 `authorized_forbidden`，而契約 hash 承諾的正是**這一組**。

```text
使用者需求 → DRAFT（沒有寫入權限）
                 ↓  定位
              SEALED → authorized_write 進入 hash
                 ↓
              builder 此時才能改動檔案
```

這個區分很容易被弄丟：

| | 隨工作推進而成長 | 作為權限被強制執行 |
| --- | ---: | ---: |
| **Working set** — 該讀什麼 | 是 | 否 |
| **Task Contract** — 可以改什麼 | 否 | 是 |

脈絡擴張、重新索引、重新路由，都可以擴大任務**讀取**的範圍。它們都無法擴大任務**寫入**的範圍。封存之後才被發現的檔案，成為脈絡，永遠不會變成許可。如果工作真的需要邊界外的檔案，那是一個新任務 —— 而不是對這個任務的一次無聲修改。

當邊界是從單純的意圖推導出來、而非被明確宣告時 —— 例如萬用字元寫入範圍、高風險任務，或過於龐大的寫入集合 —— PSG 會標記 `requires_scope_approval`，ship gate 會保持阻擋，直到有人執行 `psg task approve-scope`。該核准綁定它所核准的那個 hash，因此不會延用到另一組邊界。MCP 無法觸及這個指令。

每個發現都必須宣告它與任務的唯一一種關係。這個集合是封閉的：

| 關係 | 能阻擋這個任務嗎？ |
| --- | --- |
| `caused_by_patch` | 可以，需有證據 |
| `violates_acceptance` | 可以，需有證據 |
| `violates_project_constraint` | 可以，需有證據 |
| `pre_existing` | 不行 —— 後續事項 |
| `unrelated` | 不行 —— 後續事項 |
| `future_improvement` | 不行 —— 後續事項 |

一個發現**只有**在四個條件同時成立時才會阻擋當前任務：它是 open、它是 `blocker` 或 `major`、它的關係屬於前三種，且它的證據充分。「充分」由 runtime 檢查，不是由 agent 宣稱：

- 驗收違規必須指名一個真實存在的驗收條件 ID；
- 專案約束違規必須指出真實的 Constraint、已接受的 Decision、政策參照，或受影響的 frozen／locked 節點；
- caused-by-patch 的發現需要有變更節點、具體的 diff／runtime 證據，或一個失敗的驗證。

**Agent 不能自行設定 `blocks_current_task`。** 它提出的是帶有關係與證據的主張；由 runtime 推導該主張是否構成阻擋。後續事項在 ship gate 與 handoff pack 中完全可見 —— 它們從不被丟棄，只是不會綁架任務。Review 輪次與針對性修正循環硬性上限為 2。

### 它真的分類正確嗎？

確定性的 Task-Boundary benchmark 針對真實 runtime 執行 10 個固定情境：

| 指標 | PSG v1.1 |
| --- | ---: |
| 分類正確數 | **10 / 10** |
| 阻擋精確率 | **1.0** |
| 阻擋召回率 | **1.0** |
| 誤重啟率 | **0.0** |

```powershell
python benchmarks/task_boundary_benchmark.py --output benchmarks/results/task-boundary-latest.json
```

參見[原始結果](benchmarks/results/task-boundary-latest.json)與 [review 邊界說明](skills/psg/references/review-boundary.md)。

## PSG 關閉 vs 開啟

真正重要的問題是：真實的 coding agent 在 PSG 開啟時，是否比關閉時做得更好。`benchmarks/agentic_ab.py` 以受控實驗所能達到的最直接方式回答這個問題：

- 10 組配對的 Python coding 任務；
- 兩邊使用**同一個** Codex CLI、同一個模型、同樣的 reasoning effort；
- 同樣的 prompt、同樣的 baseline commit、各自獨立的乾淨 Git worktree；
- 相同的 sandbox 權限與相同的 MCP 設定；
- **OFF** = PSG 已安裝但停用；**ON** = PSG 啟用；
- 成功與否由 agent 從未見過的**隱藏測試**判定，另外跑既有的可見測試以偵測退化。

任務成功率是首要指標。沒有它，token 與時間數字毫無意義。

兩邊知道的資訊必須完全一樣，因此 benchmark 有兩個明確模式：

| 模式 | 誰被告知目標檔案 | 它測量什麼 |
| --- | --- | --- |
| `end_to_end` **（頭條）** | 兩邊都不告知 | PSG 在一個單純需求上是否有幫助，包含定位能力 |
| `controlled_routing` | 兩邊都告知 | 在定位條件相同下，治理本身的價值 |

只告訴 ON 這一側改動該落在哪裡，等於直接把答案交給 PSG，任何脈絡節省都會失去意義，所以這個 harness 絕不這麼做。

```powershell
python benchmarks/agentic_ab.py --output benchmarks/results/agentic-ab-latest.json --traces benchmarks/results/agentic-ab-traces
```

### 結果

10 組配對、`end_to_end` 模式、Codex CLI 搭配 `gpt-5.5` low reasoning effort，2026-09-01。
20 次執行全部完成，沒有任何一次 timeout。

| | PSG 關閉 | PSG 開啟 |
| --- | ---: | ---: |
| **任務成功** | 9 / 10 | **10 / 10** |
| 退化 | 0 | 0 |
| 範圍外編輯 | 10 | **2** |
| Input tokens | 1,984,624 | 3,543,483 |
| Output tokens | 17,840 | 24,627 |
| 執行時間 | 763 秒 | 1,084 秒 |
| 錯誤的 `SHIPPABLE` | 0 | 0 |
| 回報成本 | CLI 未提供 | CLI 未提供 |

**PSG 把 agent 留在任務內，代價是多花 79% 的 input token。** 這句話的兩半都是結果。

範圍效應是最乾淨的訊號。OFF 那 10 次範圍外編輯全部是同一個檔案：`tests/test_existing.py`。十個任務裡，agent 每一次都去改寫既有的共用測試套件來配合自己的改動。PSG 開啟時只發生兩次 —— 而那兩次，正是 PSG 自己把該測試檔封存進了寫入邊界。

成本差距不是誤差範圍：input token +79%、output token +38%、執行時間 +42%，十組之間介於 +14% 到 +198%。

### 這個結果沒有證明什麼

- **十組是小樣本。** 這些是次數，不是統計顯著的效應。
- **PSG 自己的定位很寬。** 封存的寫入邊界含 1～8 個檔案（中位數 7）。十組都包含正確的目標檔，所以召回率是完美的 —— 但精確度不是，而且其中九組被標記 `requires_scope_approval`。那是 PSG 正確地回報「我推導出的邊界太寬，不該無聲封存」，同時也正是那兩個 ON 任務讓測試檔進入範圍的原因。
- **`unique_file_reads` 無法區分兩組** —— 兩邊都是 4。它是從指令事件中出現的路徑推得的下界，在這個 repository 上沒有鑑別力。
- 這個 repository 是 harness 自己產生的。這是一個**受控配對 agentic benchmark**，不是真實世界 benchmark，把它說成真實世界 benchmark 是不誠實的。

參見[原始結果](benchmarks/results/agentic-ab-latest.json)、[已脫敏的 traces](benchmarks/results/agentic-ab-traces)，以及 [benchmark 方法與限制](benchmarks/README.md) —— 包含為什麼 `reported_cost_usd` 是 `null`，而不是從 token 數推算出來的價格。

## 它會在你的專案裡加什麼？

`psg init` 會建立一個小小的 `.psg/` 資料夾並執行首次索引：

```text
.psg/
├── config.yaml          # 可提交的專案設定與實際設定選項
├── policies.yaml        # 可提交的 mutation 政策
├── state/project.yaml   # 可提交的決策、任務、約束與證據
└── local/               # 被忽略的 SQLite、事件記錄、快取與原始檢查輸出
```

YAML 狀態可在不同 clone 與team成員之間攜帶。它儲存精簡的證據中繼資料與 hash，絕不儲存完整的指令輸出。原始驗證日誌、SQLite 與事件都留在被忽略的 `.psg/local/` 底下。原始碼與 Git 仍然是權威來源。

啟動時，PSG 只在治理狀態與上次 runtime 匯出相符、或 Git 回報它是乾淨的情況下才匯入變更，這涵蓋了 pull 或 checkout 到已提交狀態的情形。`project.yaml` 或 `config.yaml` 出現「已修改且 hash 不符」時，會在設定定義的指令執行前被擋下，直到有人檢視並明確接受為止。

## 它與你其他的 Skill 並存

PSG 是治理層，不是排他的工作流程。測試 Skill 仍然可以測試、設計 Skill 仍然可以設計、框架 Skill 仍然可以實作。PSG 提供專案脈絡，並在它們的工作周圍強制執行已接受的邊界。

它的權威順序是明確的：host 規則與你當前的指示優先；已接受的專案決策與 repository 規則優先於任務專屬或一般性的 Skill 偏好。其他 Skill 可以提出變更，但不能在沒有記錄觸發條件與核准的情況下，無聲地解鎖 frozen 節點、擴大任務範圍、削弱必要驗證，或重啟已接受的技術債。

確切規則請見[相容性契約](skills/psg/references/compatibility-contract.md)。

## 運作方式

```text
一般需求
      │
      ▼
Task ──requires──▶ Requirement
 │                    │
 ├──targets────────▶ 程式碼圖 ◀──constrained-by── Decision / Constraint
 │                    │
 ├──bounded-by─────▶ Task Contract ──▶ review 邊界 ──▶ 後續事項
 │                    │
 └──verified-by────▶ Verification
                           │
                           ▼
                    以證據為準的 ship gate
```

- indexer 對應檔案、Python 符號、import，以及結構化的 `psg-debt` 註記。
- router 選出有邊界的工作集，並在信心不足時自動擴張一次。
- policy engine 針對實際的 Git hunk 檢查檔案、符號、決策、架構、範圍與相依規則。
- verification engine 透過 MCP 只接受已設定的檢查名稱，原始輸出留在本機。
- trust layer 區分 Agent 主張、runtime 背書的證據，以及明確的使用者核准；呼叫端無法把自己的字串提升成權威。
- Task Contract 以 draft 開啟、由初次定位封存，並對封存的權限取 hash，因此 routing 與 review 都無法擴大可寫入的範圍。
- convergence engine 由 Issue 狀態與關係推導阻擋、強制 runtime 計數的預算，並拒絕自我宣稱的高風險自審。
- portable state layer 透過 `.psg/state/project.yaml` 同步持久圖狀態；本機 SQLite 可依需要重建。

## 信任模型

PSG v1 刻意使用一個很小的信任模型：

| 層級 | 意義 | 一般 MCP 能建立嗎？ |
| --- | --- | ---: |
| `CLAIMED` | Agent、審查者標籤、外部工具標籤、提案，或呼叫端提供的陳述 | ✓ |
| `RUNTIME_ATTESTED` | PSG 自己執行了設定好的檢查 | 否 |
| `USER_APPROVED` | 有人使用了獨立的本機核准動作 | 否 |
| `EXTERNAL_ATTESTED` | 保留給未來經過認證的 CI／connector adapter | 否 |

因此 MCP 的 `decision_record` 與 `debt_record` 建立的是提案。解鎖 frozen、豁免、接受技術債、接受治理狀態，以及高風險獨立 review，刻意設計成無法透過一般 MCP 自我授權。本機 CLI 是 v1 的明確核准邊界；Skill 契約要求 Agent 提出提案並等待使用者，而不是自己執行核准指令。

同樣的原則支配 review：agent 提供主張與證據，由 runtime —— 而非 agent —— 決定什麼構成阻擋。

它同樣支配任務如何被記錄。`task_open` 通常是透過 agent 轉述需求而執行的，因此產生的 Task、Requirement 與 Constraint 節點標記為 `agent_interpreted_user_intent`，而不是 `user_explicit`。這是對實際發生的事情誠實的標籤，也是為什麼「由 agent 推導而非使用者宣告」的邊界，在出貨前可能需要明確核准。

## 內含的介面

- [`skills/psg/`](skills/psg/) — 完整的 Skill bundle：入口 playbook、agent 中繼資料與支援參考。
- [`artifacts/psg-skill-v1.1.1.zip`](artifacts/psg-skill-v1.1.1.zip) — 可散布的 Skill bundle。
- `psg` — 對人友善的產品指令，加上 `--json` 與進階／除錯 API。
- `psg-mcp` — 本機 MCP server，提供相同的圖、索引、驗證、verification、handoff、技術債、衝突與出貨操作。

如果 MCP 在目標 repository 之外啟動，請在執行 `psg-mcp` 前把 `PSG_PROJECT_ROOT` 設為該 repository。

## 機制回歸 benchmark

這個合成 benchmark 在一個產生出來的 38 檔案 Python repository 上執行 12 個連續任務。每個任務都會提供目標路徑，因此它測量的是**定位之後**的路由效率。

| 結果 | PSG |
| --- | ---: |
| 達到 `SHIPPABLE` 的任務 | **12 / 12** |
| 相對全檔案基準的檔案讀取 | **少 89.69%** |
| 相對全檔案基準的估計脈絡 token | **少 32.41%** |
| 未授權的 frozen mutation | **已阻擋** |
| Review 在設定的預算處停止 | **是** |

這是一個**機制回歸 benchmark**。它證明 routing、policy 與 gate 機制相對於一個公開揭露的全檔案基準仍然正常運作。它**不是** PSG 讓真實 coding agent 更有效率的證據 —— 那個問題屬於上面的 OFF vs ON benchmark。

```powershell
python benchmarks/sequential_benchmark.py --output benchmarks/results/latest.json
```

參見[原始結果](benchmarks/results/latest.json)與 [benchmark 方法](benchmarks/README.md)。

## 研究

- [評估計畫](research/evaluation-plan.md) — PSG 應該如何在保留的真實 repository 上被測量。
- [文獻地圖與引用](research/README.md)。
- [架構](docs/architecture.md)與[驗收追溯](docs/acceptance.md)。
- [Runtime 操作](skills/psg/references/runtime-operations.md)與 [review 邊界](skills/psg/references/review-boundary.md)。

## 專案地圖

```text
PSG/
├── src/psg/          # Runtime、store、router、policy、verification、contract、ship gate
├── skills/psg/       # 可安裝的 Skill bundle 與支援資源
├── tests/            # 自動化行為、封裝與對抗性測試
├── benchmarks/       # Agentic A/B、Task Boundary 與機制 benchmark
├── scripts/          # Release 建置、驗證與安裝 smoke
├── research/         # 文獻地圖、引用與評估計畫
├── docs/             # 架構、驗收報告、視覺識別
├── artifacts/        # 可安裝的 wheel 與 Skill 封存
└── .psg/             # 本 repository 自己的可攜 PSG 設定／狀態
```

## 目前的邊界

PSG v1.1 是一個完整的、Python 優先的研究型 MVP：

- Python 有豐富的符號抽取；其他檔案以檔案層級索引。
- 兩個 benchmark 都跑在產生出來的 repository 上，並且都明說了這一點。兩者都不是真實世界 benchmark。
- PSG 治理並評估工作；實際的原始碼編輯仍由 coding agent 執行。
- 快照還原只還原 PSG 圖狀態。它絕不重設 Git，也不覆寫原始碼檔案。
- `EXTERNAL_ATTESTED` 在經過認證的 CI／connector adapter 出現前保持保留狀態；單靠 `source="external_tool"` 仍然只是主張。
- 使用 handoff pack 的聊天端審查者是遵循 Task Contract；它無法強制執行契約。
- 擴大已封存的邊界刻意不自動化。v1 沒有 task-amendment engine：對「這需要再多改一個檔案」的答案是「開一個新任務」。

下一個有意義的步驟是在真實 repository 上做保留評估 —— 而不是在治理契約被證明之前，先加上 UI、向量資料庫或更多語言支援。
