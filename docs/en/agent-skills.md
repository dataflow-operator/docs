# Agent Skills

Agent skills are portable Markdown guides that teach any AI coding assistant how to deploy DataFlow Operator, write production-ready manifests, and configure fault tolerance. They work with **Cursor, Claude Code, GitHub Copilot, Windsurf, Cline**, and other LLM-based tools — not Cursor-only.

Unlike the [MCP server](mcp.md), skills do not call tools; they provide operational knowledge from this documentation and `config/samples`.

## Skills vs MCP

| | **Agent skills** | **MCP** |
|---|------------------|---------|
| Purpose | Deploy, config patterns, resilience checklists | Generate and validate YAML via tools |
| Invocation | IDE-specific (see below) or read `AGENTS.md` | MCP tools in chat |
| Kubernetes access | Not required | Not required |
| Best for | Helm setup, prod manifests, idempotency review | Quick manifest generation, Kafka Connect migration |

Use both: skills for **how to configure correctly**; MCP for **generating draft YAML**.

## Installation

Full instructions: [skills/INSTALL.md](https://github.com/dataflow-operator/dataflow/blob/main/skills/INSTALL.md)

### Cursor

```bash
git clone https://github.com/dataflow-operator/dataflow.git /tmp/dataflow
mkdir -p .cursor/skills
cp -r /tmp/dataflow/skills/* .cursor/skills/
```

Invoke: `@dataflow`, `@dataflow-config`, …

### Claude Code

```bash
mkdir -p .claude/skills
cp -r /tmp/dataflow/skills/* .claude/skills/
```

Or add a pointer in `CLAUDE.md` to [AGENTS.md](https://github.com/dataflow-operator/dataflow/blob/main/AGENTS.md).

### GitHub Copilot

Add to `.github/copilot-instructions.md`:

```markdown
For DataFlow manifests, follow skills/ in the dataflow-operator repo (see AGENTS.md).
```

### Any agent (no install)

Open [AGENTS.md](https://github.com/dataflow-operator/dataflow/blob/main/AGENTS.md) in the repository — index of all guides with links.

## Available skills

| Skill | Purpose |
|-------|---------|
| `dataflow` | Entry point: DataFlow vs DataFlowCron, navigation |
| `dataflow-deploy` | Helm install, CRD, verification |
| `dataflow-config` | Write or review `DataFlow` / `DataFlowCron` YAML |
| `dataflow-fault-tolerance` | Idempotency, checkpoint, ack, error sink |

Source: [skills/](https://github.com/dataflow-operator/dataflow/tree/main/skills) directory in the repository.

## Typical workflow

1. `dataflow-deploy` — confirm operator is installed
2. `dataflow-config` — draft manifest
3. `dataflow-fault-tolerance` — pre-apply checklist
4. `kubectl apply -f manifest.yaml`

## Maintainer note

In the **dataflow-operator** repo, maintainer extensions live under `.cursor/skills/dataflow-*`. Client content stays in `skills/` — see `.cursor/skills/SYNC.md`.

## See also

- [Getting Started](getting-started.md)
- [Fault Tolerance](fault-tolerance.md)
- [MCP](mcp.md)
- [Examples](examples.md)
