<div align="center">

<img src="docs/assets/psg-hero.svg" alt="PSG — project state graph" width="100%">

[English](README.md) · **繁體中文** · [简体中文](README.zh-CN.md) · [日本語](README.ja.md)

</div>

# PSG — 專案狀態圖

**讓 AI coding agent 留在任務範圍內、跨工作階段保留專案決策，並清楚知道工作何時完成。**

PSG 為 coding agent 提供持久的任務邊界與專案狀態，不必讓每個模型重新探索 repository、重新定義工作範圍。

## 安裝

### Windows

```powershell
python -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.4"; psg setup
```

### macOS / Linux

```bash
python3 -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.4" && psg setup
```

接著在 Git 專案內執行：

```text
psg init
```

就這樣。之後照常使用 Codex、Claude Code 或 Gemini CLI。

### 日常控制

```text
psg status
psg on
psg off
```

## PSG 到底在做什麼？

沒有 PSG 時，coding agent 可能不斷發現更多檔案、更多重構機會與更多 review 建議，最後讓一個小任務變成整個專案的改寫。

PSG 為每個任務建立四種邊界：

- **Context boundary（上下文邊界）** — Agent 需要讀取什麼。
- **Mutation boundary（修改邊界）** — Agent 可以改動什麼。
- **Review boundary（審查邊界）** — 哪些發現可以阻擋目前任務。
- **Completion boundary（完成邊界）** — 任務何時完成、review 何時必須停止。

Reviewer 仍然可以發現無關的 bug 或未來可改善的地方，但 PSG 會把它們記成 follow-up，而不是默默擴大目前任務。

> **Review the task, not the universe. — 審查任務，不是整個宇宙。**

## 為什麼使用 PSG？

### 1. 阻止範圍漂移

原本只需要修 A 的任務，不會因為另一個模型又看見 B、C、D 可以改善，就自動變成 A + B + C + D。

### 2. 保留專案決策

已接受的 decision、constraint、frozen boundary 與 known debt，不需要每換一個 Agent 或 session 就重新解釋。

### 3. 讓 review 收斂

只有目前 patch 造成的 regression、驗收條件違規，或專案約束違規可以阻擋目前任務。其他 finding 會保留為 follow-up，不會重新打開任務。

### 4. 知道何時停止

當驗收條件、確定性驗證、guardrail 與目前任務的 blocker 全部一致時，gate 會回傳：

```text
SHIPPABLE
```

一般性 review 到此停止。

## 歷史 A/B 結果（已被取代）

> **證據狀態：Superseded。**

**保留這次測試是為了透明揭露，但它不是目前版本效能的證據。當時 Codex 載入的 PSG Skill 比受測 Runtime 更舊，檢索整合之後也已改變。**

這次歷史測試包含 10 組配對的 Codex CLI 任務，使用相同模型、prompt 與 repository baseline。

| 指標 | PSG OFF | PSG ON |
| --- | ---: | ---: |
| **任務成功** | 9 / 10 | **10 / 10** |
| 非目標檔案修改 | 10 | **2** |
| Regression | 0 | 0 |
| 錯誤的 `SHIPPABLE` | 0 | 0 |

這次歷史測試顯示出**更好的任務邊界紀律，但伴隨可量測的 token 與延遲成本**。由於它已被取代，因此不構成目前版本的效能證據；PSG 目前不據此宣稱能節省 token 或時間。

完整 protocol、原始結果與限制請見[Benchmark 文件](benchmarks/README.md)。

## 運作方式

![PSG 流程：從使用者需求、Task Contract、相關專案狀態、Coding agent、確定性驗證與有邊界的 review，走到 SHIPPABLE](docs/assets/psg-flow.svg)

Git 仍然是實作內容的 source of truth。PSG 保存持久的決策與任務狀態，而不是完整對話。需要時可以擴大 context，但寫入權限不會跟著默默擴張。

## PSG 可以在哪裡使用？

| 模式 | Host | 能力 |
| --- | --- | --- |
| **完整執行** | Codex、Claude Code、Gemini CLI | 讀取、修改、驗證、強制邊界與 ship |
| **Review / handoff** | ChatGPT、Claude、Gemini | 依同一份 Task Contract 進行審查 |

所有 host 都能使用同一份 Task Boundary；完整執行端另外會受到 runtime 強制保護。使用 `psg handoff` 可為其他模型或協作者建立精簡的 review pack。

## 目前限制

- 完整的 symbol indexing 以 Python 為主，其他語言目前以檔案層級建立索引。
- 收錄的 agentic benchmark 使用小型生成 repository，不是真實生產專案。
- 目前定位行為仍需要一次新的配對 A/B 測試。
- PSG 尚未提供已驗證身分的外部 CI attestation adapter。
- PSG 負責治理與評估變更；實際修改程式碼的仍是 coding agent。

## 詳細文件

- [安裝與 host 設定](docs/installation.md)
- [Task Contract 與 review boundary](docs/task-contract.md)
- [信任與安全模型](docs/trust-and-security.md)
- [CLI 與 MCP 參考](docs/cli-and-mcp.md)
- [架構](docs/architecture.md)
- [驗收與 release 證據](docs/acceptance.md)
- [Benchmarks](benchmarks/README.md)
- [研究資料](research/README.md)

另一套 [mechanics regression benchmark](benchmarks/README.md#3-mechanics-regression-benchmark) 會在已知相關目標的前提下，驗證 routing 是否能減少選取的 context；它不是端到端 Agent token 節省的主張。

PSG 也正以長期軟體 Agent 研究系統的方向進行評估，詳見[評估計畫](research/evaluation-plan.md)。

## 授權

[MIT](LICENSE)
