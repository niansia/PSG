<div align="center">

<img src="docs/assets/psg-concept.png" alt="PSG — 项目状态图" width="100%">

# PSG

### project state graph／项目状态图

**安装一次。初始化一次。然后照常写代码。**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-6EAEDB?style=flat-square)](https://www.python.org/)
[![CI](https://github.com/niansia/PSG/actions/workflows/ci.yml/badge.svg)](https://github.com/niansia/PSG/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v1.1.1-F3B557?style=flat-square)](https://github.com/niansia/PSG/releases/tag/v1.1.1)
[![Status](https://img.shields.io/badge/status-complete%20MVP-FF9364?style=flat-square)](docs/acceptance.md)

[English](README.md) · [繁體中文](README.zh-TW.md) · **简体中文** · [日本語](README.ja.md)

</div>

PSG 是一组 Skill bundle 加上本地 runtime，它给你的 coding agent 三样东西：对项目的持久记忆、明确的可改动边界，以及以证据为准的"完成"定义。它与 Git 和你已有的 Skill 并存；它不取代你的 coding agent，也不会自己改动源代码。

> 你照常用日常语言提需求。PSG 在背后取出相关上下文、保护锁定的决策与文件、执行你授权的检查、把 review 限制在你真正要求的任务范围内，并阻止过期或缺乏支撑的证据被当成"做完了"。

## 安装

安装一次即可。这条命令会安装 runtime、完整的 Skill bundle，并为每个检测到的 Codex、Claude Code 或 Gemini CLI host 配置 MCP 集成。

### Windows

```powershell
python -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.1"; psg setup
```

### macOS / Linux

```bash
python3 -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.1" && psg setup
```

然后为每个 Git 项目启用一次：

```text
cd your-project
psg init
```

## 照常使用

就这样。之后照常跟你的 coding agent 对话：

```text
购物车为空时显示一段友好提示，完成后帮我验证。
```

PSG Skill 启用后，它会开启并跟踪任务、取出有边界的上下文、验证真实的最终 diff、记录可信的验证结果、把 review 限制在任务内，并评估 ship gate。日常工作不需要你手动操作它的图。

日常只有这几个控制项：

```powershell
psg status       # 查看 PSG 是否启用，以及它知道些什么
psg off          # 临时停用自动治理
psg on           # 重新启用
psg handoff      # 生成给其他模型或同事的 review pack
```

`psg off --global` 与 `psg on --global` 会暂停或恢复所有已初始化项目的自动治理。`psg update` 安装最新的稳定 `vX.Y.Z` release；除非你显式指定 `psg update --channel dev`，否则它永远不会跟随 `main`。`psg doctor` 与 `psg uninstall` 负责健康检查与卸载；卸载会保留每个项目持久的 `.psg/` 状态。

### 两种使用模式

| 模式 | Host | 你得到什么 |
| --- | --- | --- |
| **完整执行** | Codex · Claude Code · Gemini CLI | Skill 加上本地 runtime 与 MCP server。边界是**被强制执行**的：mutation policy 针对真实 diff 检查、验证由 runtime 背书、ship gate 由机器评估。 |
| **Review／交接** | ChatGPT · Claude · Gemini | 上传 `psg handoff` 生成的 review pack。审查者读到的是同一份 Task Contract 与同一套 review 边界。 |

六者共用同一份 Task Contract。只有执行端具备 runtime 强制力 —— 聊天端的审查者是"遵循"契约，而不是"执行"契约。

```powershell
psg handoff
```

Review pack 会写到 `.psg/local/handoffs/<task>.md`，这个路径 Git 会忽略。这点很重要：写进工作目录的 review 文件会变成未跟踪的项目变更，反而挡住它本来要协助通过的 ship gate。`--output` 可以写到别处，若路径落在工作目录内会发出警告。

`psg handoff` 严格只读：它不会改变任务状态，也不会写入事件日志。

## 支持的 agent

| Agent | PSG Skill | PSG runtime | 自动安装 |
| --- | ---: | ---: | ---: |
| Codex | ✓ | ✓ | ✓ |
| Claude Code | ✓ | ✓ | ✓ |
| Gemini CLI | ✓ | ✓ | ✓ |
| 通用 Agent Skills + MCP | ✓ | ✓ | 手动 |

`psg setup` 会自动检测已安装的 host、复制整个目录 bundle、通过每个 host 原生的 CLI 注册 `psg-mcp`，并记录集成状态。`psg setup --all` 是"安装到所有检测到的 host"的显式别名。wheel／源码安装与高级兜底方式见[安装与 host 配置](docs/installation.md)。

## 为什么需要 PSG

PSG 针对的是让 agent 辅助开发变得令人沮丧的那些日常问题：

- 每开一个新对话就要重读同一个 repository；
- 重要的约束在不同 session 之间消失；
- 一个小需求动到不相关的文件；
- "测试通过了"指的是早就被改掉的代码；
- 一个两行的修复，review 回来一份"这个项目所有问题"的清单；
- 反复 review 一再推翻已经接受的取舍；或
- 没有人说得出为什么这件工作算完成了。

PSG 把这些问题变成五个具体的保护机制：

| 你需要 | PSG 提供 |
| --- | --- |
| 正确的上下文 | 由文件、Python 符号、依赖关系、任务、决策与约束构建的 token 预算内工作集。 |
| 安全的改动 | 针对最终 Git 状态的策略检查，涵盖已暂存、未暂存、重命名、删除与未跟踪的文件。 |
| 可信的证明 | 验证与验收证据绑定到确切的工作树及其真实来源。 |
| 有边界的 review | 由 Task Contract 决定哪些发现属于**这个**任务，哪些是后续事项。 |
| 真正的完成线 | 只有当范围、检查、验收条件、review、当前代码与风险要求全部一致时，才会是 `SHIPPABLE`。 |

## Task Boundary（任务边界）

> **严重度不等于任务范围。**
> **更多上下文不等于更多权限。**
> **每个任务都有边界。每次 review 都留在边界内。**
> **Review 这个任务，不是整个宇宙。**

`blocker` 陈述的是"这件事有多严重"，而不是"这件事属不属于你要求的任务"。把两者当成同一件事，正是一行修复变成一周工程的起点。

`psg task open` 记录一份正式的 **Task Contract**：目标、上下文、mutation、范围、review、完成与风险边界。`review_record` 会校验它的 hash，所以一轮 review 永远无法扩大它正在 review 的那个任务。

### 更多上下文不等于更多权限

任务开启时是 **DRAFT**。它陈述意图、请求范围，但完全不持有写入权限 —— 此时尝试改文件，gate 会告诉你契约尚未封存。

接着首次定位会将它 **SEAL（封存）**：PSG 推导出的 mutation 边界成为 `authorized_write`、`authorized_read_only` 与 `authorized_forbidden`，而契约 hash 承诺的正是**这一组**。

```text
用户需求 → DRAFT（没有写入权限）
               ↓  定位
            SEALED → authorized_write 进入 hash
               ↓
            builder 此时才能改动文件
```

这个区分很容易被丢失：

| | 随工作推进而增长 | 作为权限被强制执行 |
| --- | ---: | ---: |
| **Working set** — 该读什么 | 是 | 否 |
| **Task Contract** — 可以改什么 | 否 | 是 |

上下文扩张、重新索引、重新路由，都可以扩大任务**读取**的范围。它们都无法扩大任务**写入**的范围。封存之后才被发现的文件，成为上下文，永远不会变成许可。如果工作确实需要边界外的文件，那是一个新任务 —— 而不是对这个任务的一次无声修改。

当边界是从单纯的意图推导出来、而非被显式声明时 —— 例如通配符写入范围、高风险任务，或过于庞大的写入集合 —— PSG 会标记 `requires_scope_approval`，ship gate 会保持阻挡，直到有人执行 `psg task approve-scope`。该批准绑定它所批准的那个 hash，因此不会沿用到另一组边界。MCP 无法触及这条命令。

每个发现都必须声明它与任务的唯一一种关系。这个集合是封闭的：

| 关系 | 能挡住这个任务吗？ |
| --- | --- |
| `caused_by_patch` | 可以，需有证据 |
| `violates_acceptance` | 可以，需有证据 |
| `violates_project_constraint` | 可以，需有证据 |
| `pre_existing` | 不行 —— 后续事项 |
| `unrelated` | 不行 —— 后续事项 |
| `future_improvement` | 不行 —— 后续事项 |

一个发现**只有**在四个条件同时成立时才会挡住当前任务：它是 open、它是 `blocker` 或 `major`、它的关系属于前三种，且它的证据充分。"充分"由 runtime 检查，不是由 agent 声称：

- 验收违规必须指明一个真实存在的验收条件 ID；
- 项目约束违规必须指出真实的 Constraint、已接受的 Decision、策略引用，或受影响的 frozen／locked 节点；
- caused-by-patch 的发现需要有变更节点、具体的 diff／runtime 证据，或一个失败的验证。

**Agent 不能自行设置 `blocks_current_task`。** 它提出的是带有关系与证据的主张；由 runtime 推导该主张是否构成阻挡。后续事项在 ship gate 与 handoff pack 中完全可见 —— 它们从不被丢弃，只是不会绑架任务。Review 轮次与针对性修复循环硬性上限为 2。

### 它真的分类正确吗？

确定性的 Task-Boundary benchmark 针对真实 runtime 执行 10 个固定场景：

| 指标 | PSG v1.1 |
| --- | ---: |
| 分类正确数 | **10 / 10** |
| 阻挡精确率 | **1.0** |
| 阻挡召回率 | **1.0** |
| 误重开率 | **0.0** |

```powershell
python benchmarks/task_boundary_benchmark.py --output benchmarks/results/task-boundary-latest.json
```

参见[原始结果](benchmarks/results/task-boundary-latest.json)与 [review 边界说明](skills/psg/references/review-boundary.md)。

## PSG 关闭 vs 开启

真正重要的问题是：真实的 coding agent 在 PSG 开启时，是否比关闭时做得更好。`benchmarks/agentic_ab.py` 以受控实验所能达到的最直接方式回答这个问题：

- 10 组配对的 Python coding 任务；
- 两边使用**同一个** Codex CLI、同一个模型、同样的 reasoning effort；
- 同样的 prompt、同样的 baseline commit、各自独立的干净 Git worktree；
- 相同的 sandbox 权限与相同的 MCP 配置；
- **OFF** = PSG 已安装但停用；**ON** = PSG 启用；
- 成功与否由 agent 从未见过的**隐藏测试**判定，另外跑已有的可见测试以检测回归。

任务成功率是首要指标。没有它，token 与耗时数字毫无意义。

两边知道的信息必须完全一样，因此 benchmark 有两个明确模式：

| 模式 | 谁被告知目标文件 | 它测量什么 |
| --- | --- | --- |
| `end_to_end` **（头条）** | 两边都不告知 | PSG 在一个单纯需求上是否有帮助，包含定位能力 |
| `controlled_routing` | 两边都告知 | 在定位条件相同下，治理本身的价值 |

只告诉 ON 这一侧改动该落在哪里，等于直接把答案交给 PSG，任何上下文节省都会失去意义，所以这个 harness 绝不这么做。

```powershell
python benchmarks/agentic_ab.py --output benchmarks/results/agentic-ab-latest.json --traces benchmarks/results/agentic-ab-traces
```

### 结果

10 组配对、`end_to_end` 模式、Codex CLI 搭配 `gpt-5.5` low reasoning effort，2026-09-01。
20 次运行全部完成，没有任何一次 timeout。

| | PSG 关闭 | PSG 开启 |
| --- | ---: | ---: |
| **任务成功** | 9 / 10 | **10 / 10** |
| 回归 | 0 | 0 |
| 范围外编辑 | 10 | **2** |
| Input tokens | 1,984,624 | 3,543,483 |
| Output tokens | 17,840 | 24,627 |
| 运行时间 | 763 秒 | 1,084 秒 |
| 错误的 `SHIPPABLE` | 0 | 0 |
| 报告成本 | CLI 未提供 | CLI 未提供 |

**PSG 把 agent 留在任务内，代价是多花 79% 的 input token。** 这句话的两半都是结果。

范围效应是最干净的信号。OFF 那 10 次范围外编辑全部是同一个文件：`tests/test_existing.py`。十个任务里，agent 每一次都去改写已有的共用测试套件来配合自己的改动。PSG 开启时只发生两次 —— 而那两次，正是 PSG 自己把该测试文件封存进了写入边界。

成本差距不是误差范围：input token +79%、output token +38%、运行时间 +42%，十组之间介于 +14% 到 +198%。

### 这个结果没有证明什么

- **十组是小样本。** 这些是次数，不是统计显著的效应。
- **PSG 自己的定位很宽。** 封存的写入边界含 1～8 个文件（中位数 7）。十组都包含正确的目标文件，所以召回率是完美的 —— 但精确度不是，而且其中九组被标记 `requires_scope_approval`。那是 PSG 正确地报告"我推导出的边界太宽，不该无声封存"，同时也正是那两个 ON 任务让测试文件进入范围的原因。
- **`unique_file_reads` 无法区分两组** —— 两边都是 4。它是从命令事件中出现的路径推得的下界，在这个 repository 上没有鉴别力。
- 这个 repository 是 harness 自己生成的。这是一个**受控配对 agentic benchmark**，不是真实世界 benchmark，把它说成真实世界 benchmark 是不诚实的。

参见[原始结果](benchmarks/results/agentic-ab-latest.json)、[已脱敏的 traces](benchmarks/results/agentic-ab-traces)，以及 [benchmark 方法与限制](benchmarks/README.md) —— 包括为什么 `reported_cost_usd` 是 `null`，而不是从 token 数推算出来的价格。

## 它会在你的项目里加什么？

`psg init` 会创建一个很小的 `.psg/` 目录并执行首次索引：

```text
.psg/
├── config.yaml          # 可提交的项目设置与实际配置项
├── policies.yaml        # 可提交的 mutation 策略
├── state/project.yaml   # 可提交的决策、任务、约束与证据
└── local/               # 被忽略的 SQLite、事件日志、缓存与原始检查输出
```

YAML 状态可在不同 clone 与团队成员之间携带。它存储精简的证据元数据与 hash，绝不存储完整的命令输出。原始验证日志、SQLite 与事件都留在被忽略的 `.psg/local/` 下。源代码与 Git 仍然是权威来源。

启动时，PSG 只在治理状态与上次 runtime 导出相符、或 Git 报告它是干净的情况下才导入变更，这涵盖了 pull 或 checkout 到已提交状态的情形。`project.yaml` 或 `config.yaml` 出现"已修改且 hash 不符"时，会在配置定义的命令执行前被挡下，直到有人查看并显式接受为止。

## 它与你其他的 Skill 并存

PSG 是治理层，不是排他的工作流。测试 Skill 仍然可以测试、设计 Skill 仍然可以设计、框架 Skill 仍然可以实现。PSG 提供项目上下文，并在它们的工作周围强制执行已接受的边界。

它的权威顺序是明确的：host 规则与你当前的指示优先；已接受的项目决策与 repository 规则优先于任务专属或通用的 Skill 偏好。其他 Skill 可以提出变更，但不能在没有记录触发条件与批准的情况下，无声地解锁 frozen 节点、扩大任务范围、削弱必要验证，或重开已接受的技术债。

确切规则见[兼容性契约](skills/psg/references/compatibility-contract.md)。

## 工作原理

```text
一般需求
      │
      ▼
Task ──requires──▶ Requirement
 │                    │
 ├──targets────────▶ 代码图 ◀──constrained-by── Decision / Constraint
 │                    │
 ├──bounded-by─────▶ Task Contract ──▶ review 边界 ──▶ 后续事项
 │                    │
 └──verified-by────▶ Verification
                           │
                           ▼
                    以证据为准的 ship gate
```

- indexer 映射文件、Python 符号、import，以及结构化的 `psg-debt` 注释。
- router 选出有边界的工作集，并在置信度不足时自动扩张一次。
- policy engine 针对实际的 Git hunk 检查文件、符号、决策、架构、范围与依赖规则。
- verification engine 通过 MCP 只接受已配置的检查名称，原始输出留在本地。
- trust layer 区分 Agent 主张、runtime 背书的证据，以及显式的用户批准；调用方无法把自己的字符串提升成权威。
- Task Contract 以 draft 开启、由首次定位封存，并对封存的权限取 hash，因此 routing 与 review 都无法扩大可写入的范围。
- convergence engine 由 Issue 状态与关系推导阻挡、强制 runtime 计数的预算，并拒绝自我声称的高风险自审。
- portable state layer 通过 `.psg/state/project.yaml` 同步持久图状态；本地 SQLite 可按需重建。

## 信任模型

PSG v1 刻意使用一个很小的信任模型：

| 层级 | 含义 | 普通 MCP 能创建吗？ |
| --- | --- | ---: |
| `CLAIMED` | Agent、审查者标签、外部工具标签、提案，或调用方提供的陈述 | ✓ |
| `RUNTIME_ATTESTED` | PSG 自己执行了配置好的检查 | 否 |
| `USER_APPROVED` | 有人使用了独立的本地批准动作 | 否 |
| `EXTERNAL_ATTESTED` | 保留给未来经过认证的 CI／connector adapter | 否 |

因此 MCP 的 `decision_record` 与 `debt_record` 创建的是提案。解锁 frozen、豁免、接受技术债、接受治理状态，以及高风险独立 review，刻意设计成无法通过普通 MCP 自我授权。本地 CLI 是 v1 的显式批准边界；Skill 契约要求 Agent 提出提案并等待用户，而不是自己执行批准命令。

同样的原则支配 review：agent 提供主张与证据，由 runtime —— 而非 agent —— 决定什么构成阻挡。

它同样支配任务如何被记录。`task_open` 通常是通过 agent 转述需求而执行的，因此产生的 Task、Requirement 与 Constraint 节点标记为 `agent_interpreted_user_intent`，而不是 `user_explicit`。这是对实际发生的事情诚实的标签，也是为什么"由 agent 推导而非用户声明"的边界，在出货前可能需要显式批准。

## 内含的接口

- [`skills/psg/`](skills/psg/) — 完整的 Skill bundle：入口 playbook、agent 元数据与支持参考。
- [`artifacts/psg-skill-v1.1.1.zip`](artifacts/psg-skill-v1.1.1.zip) — 可分发的 Skill bundle。
- `psg` — 对人友好的产品命令，加上 `--json` 与高级／调试 API。
- `psg-mcp` — 本地 MCP server，提供相同的图、索引、校验、verification、handoff、技术债、冲突与出货操作。

如果 MCP 在目标 repository 之外启动，请在运行 `psg-mcp` 前把 `PSG_PROJECT_ROOT` 设为该 repository。

## 机制回归 benchmark

这个合成 benchmark 在一个生成出来的 38 文件 Python repository 上执行 12 个连续任务。每个任务都会提供目标路径，因此它测量的是**定位之后**的路由效率。

| 结果 | PSG |
| --- | ---: |
| 达到 `SHIPPABLE` 的任务 | **12 / 12** |
| 相对全文件基准的文件读取 | **少 89.69%** |
| 相对全文件基准的估计上下文 token | **少 32.41%** |
| 未授权的 frozen mutation | **已阻挡** |
| Review 在配置的预算处停止 | **是** |

这是一个**机制回归 benchmark**。它证明 routing、policy 与 gate 机制相对于一个公开披露的全文件基准仍然正常工作。它**不是** PSG 让真实 coding agent 更高效的证据 —— 那个问题属于上面的 OFF vs ON benchmark。

```powershell
python benchmarks/sequential_benchmark.py --output benchmarks/results/latest.json
```

参见[原始结果](benchmarks/results/latest.json)与 [benchmark 方法](benchmarks/README.md)。

## 研究

- [评估计划](research/evaluation-plan.md) — PSG 应该如何在留出的真实 repository 上被测量。
- [文献地图与引用](research/README.md)。
- [架构](docs/architecture.md)与[验收追溯](docs/acceptance.md)。
- [Runtime 操作](skills/psg/references/runtime-operations.md)与 [review 边界](skills/psg/references/review-boundary.md)。

## 项目地图

```text
PSG/
├── src/psg/          # Runtime、store、router、policy、verification、contract、ship gate
├── skills/psg/       # 可安装的 Skill bundle 与支持资源
├── tests/            # 自动化行为、打包与对抗性测试
├── benchmarks/       # Agentic A/B、Task Boundary 与机制 benchmark
├── scripts/          # Release 构建、校验与安装 smoke
├── research/         # 文献地图、引用与评估计划
├── docs/             # 架构、验收报告、视觉识别
├── artifacts/        # 可安装的 wheel 与 Skill 归档
└── .psg/             # 本 repository 自己的可移植 PSG 配置／状态
```

## 当前的边界

PSG v1.1 是一个完整的、Python 优先的研究型 MVP：

- Python 有丰富的符号抽取；其他文件按文件级索引。
- 两个 benchmark 都跑在生成出来的 repository 上，并且都明说了这一点。两者都不是真实世界 benchmark。
- PSG 治理并评估工作；实际的源代码编辑仍由 coding agent 执行。
- 快照还原只还原 PSG 图状态。它绝不重置 Git，也不覆盖源代码文件。
- `EXTERNAL_ATTESTED` 在经过认证的 CI／connector adapter 出现前保持保留状态；仅靠 `source="external_tool"` 仍然只是主张。
- 使用 handoff pack 的聊天端审查者是遵循 Task Contract；它无法强制执行契约。
- 扩大已封存的边界刻意不自动化。v1 没有 task-amendment engine：对"这需要再多改一个文件"的答案是"开一个新任务"。

下一个有意义的步骤是在真实 repository 上做留出评估 —— 而不是在治理契约被证明之前，先加上 UI、向量数据库或更多语言支持。
