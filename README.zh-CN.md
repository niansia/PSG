<div align="center">

<img src="docs/assets/psg-hero.svg" alt="PSG — project state graph" width="100%">

[English](README.md) · [繁體中文](README.zh-TW.md) · **简体中文** · [日本語](README.ja.md)

</div>

# PSG — 项目状态图

**让 AI coding agent 留在任务范围内、跨工作阶段保留项目决策，并清楚知道工作何时完成。**

PSG 为 coding agent 提供持久的任务边界与项目状态，不再让每个模型重新探索 repository、重新定义工作范围。

## 安装

### Windows

```powershell
python -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.2"; psg setup
```

### macOS / Linux

```bash
python3 -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.2" && psg setup
```

然后在 Git 项目中运行：

```text
psg init
```

就这样。之后照常使用 Codex、Claude Code 或 Gemini CLI。

### 日常控制

```text
psg status
psg on
psg off
```

## PSG 到底在做什么？

没有 PSG 时，coding agent 可能不断发现更多文件、更多重构机会和更多 review 建议，最后让一个小任务变成整个项目的改写。

PSG 为每个任务建立四种边界：

- **Context boundary（上下文边界）** — Agent 需要读取什么。
- **Mutation boundary（修改边界）** — Agent 可以改动什么。
- **Review boundary（审查边界）** — 哪些发现可以阻挡当前任务。
- **Completion boundary（完成边界）** — 任务何时完成、review 何时必须停止。

Reviewer 仍然可以发现无关 bug 或未来可以改进的地方，但 PSG 会把它们记录为 follow-up，而不是悄悄扩大当前任务。

> **Review the task, not the universe. — 审查任务，而不是整个宇宙。**

## 为什么使用 PSG？

### 1. 阻止范围漂移

原本只需要修 A 的任务，不会因为另一个模型又看到 B、C、D 可以改进，就自动变成 A + B + C + D。

### 2. 保留项目决策

已接受的 decision、constraint、frozen boundary 和 known debt，不需要每换一个 Agent 或 session 就重新解释。

### 3. 让 review 收敛

只有当前 patch 造成的 regression、验收条件违规，或项目约束违规可以阻挡当前任务。其他 finding 会保留为 follow-up，不会重新打开任务。

### 4. 知道何时停止

当验收条件、确定性验证、guardrail 和当前任务的 blocker 全部一致时，gate 会返回：

```text
SHIPPABLE
```

一般性 review 到此停止。

## 实测结果：PSG OFF vs ON

10 组配对的 Codex CLI 任务，使用相同模型、prompt 和 repository baseline。这次受控测试早于最新的定位逻辑，因此它展示的是当时测得的取舍，而不是对当前性能的预测。

| 指标 | PSG OFF | PSG ON |
| --- | ---: | ---: |
| **任务成功** | 9 / 10 | **10 / 10** |
| 非目标文件修改 | 10 | **2** |
| Regression | 0 | 0 |
| 错误的 `SHIPPABLE` | 0 | 0 |
| Input token | 1.98M | 3.54M |
| Wall time | 763 秒 | 1,084 秒 |

**PSG 让 Agent 更贴近任务边界，但在这次 benchmark 中并没有节省 token。它多使用了 79% 的 input token，wall time 也增加了 42%。**

### 为什么 PSG 使用更多 token？

这个 benchmark 测量的是小型、相互独立、每次都冷启动的 coding task。每一组都从全新的 worktree 开始，因此 PSG 每次都必须付出 Task Contract、routing、verification 和 ship gate 的成本。

所以它测到了 PSG governance 的成本，却没有测到 PSG 的一项主要长期收益：在连续任务、模型切换和多轮 review 之间复用持久项目状态，而不是反复从 chat history 重建理解。

这次测试中的自然语言定位也过于宽泛。所有正确目标都找到了，但推导出的写入边界中位数为七个文件，导致十个 ON 任务中有九个需要范围批准。这是精确度问题，不是放宽边界的理由；当前版本已将检索相关性与写入权限分离，仍需重新进行公平的 A/B 测试。

因此当前结果应解读为：

> **更好的范围纪律，以及可测量的额外成本。**

**PSG 目前不声称这个 benchmark 证明了端到端 token 节省。**

### 证据状态

已由收录的受控与确定性测试证明：

- ✓ Task boundary enforcement
- ✓ 在这次 A/B 测试中减少非目标文件修改
- ✓ 这个小型测试没有观察到正确性退步
- ✓ 以证据为依据的 ship gate

尚未证明：

- 端到端 token 节省
- 真实世界的长期收益
- 能泛化到大型 repository 和不同模型

完整 protocol、原始结果与限制请见 [Benchmark 文档](benchmarks/README.md)。

## 工作方式

![PSG 流程：从用户需求、Task Contract、相关项目状态、Coding agent、确定性验证与有边界的 review，走到 SHIPPABLE](docs/assets/psg-flow.svg)

Git 仍然是实现内容的 source of truth。PSG 保存持久的决策和任务状态，而不是完整对话。需要时可以扩大 context，但写入权限不会随之悄悄扩张。

## PSG 可以在哪里使用？

| 模式 | Host | 能力 |
| --- | --- | --- |
| **完整执行** | Codex、Claude Code、Gemini CLI | 读取、修改、验证、强制边界与 ship |
| **Review / handoff** | ChatGPT、Claude、Gemini | 按照同一份 Task Contract 进行审查 |

所有 host 都能使用同一份 Task Boundary；完整执行端另外会受到 runtime 强制保护。使用 `psg handoff` 可以为其他模型或协作者建立精简的 review pack。

## 当前限制

- 完整的 symbol indexing 以 Python 为主，其他语言目前以文件层级建立索引。
- 收录的 agentic benchmark 使用小型生成 repository，不是真实生产项目。
- 当前定位行为仍需要一次新的配对 A/B 测试。
- PSG 尚未提供经过身份验证的外部 CI attestation adapter。
- PSG 负责治理和评估变更；实际修改代码的仍是 coding agent。

## 详细文档

- [安装与 host 设置](docs/installation.md)
- [Task Contract 与 review boundary](docs/task-contract.md)
- [信任与安全模型](docs/trust-and-security.md)
- [CLI 与 MCP 参考](docs/cli-and-mcp.md)
- [架构](docs/architecture.md)
- [验收与 release 证据](docs/acceptance.md)
- [Benchmarks](benchmarks/README.md)
- [研究资料](research/README.md)

另一套 [mechanics regression benchmark](benchmarks/README.md#3-mechanics-regression-benchmark) 会在已知相关目标的前提下，验证 routing 是否能减少选取的 context；它不是端到端 Agent token 节省的声明。

PSG 也正在按长期软件 Agent 研究系统的方向进行评估，详见[评估计划](research/evaluation-plan.md)。

## 许可证

[MIT](LICENSE)
