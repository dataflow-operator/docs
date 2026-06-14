# Agent Skills

Agent skills are portable Markdown guides for any AI coding assistant. Published repository:

**https://github.com/dataflow-operator/skills**

Unlike [MCP](mcp.md), skills do not call tools — they provide operational knowledge from documentation and `config/samples`.

## Skills vs MCP

| | **Agent skills** | **MCP** |
|---|------------------|---------|
| Purpose | Deploy, config patterns, resilience checklists | Generate and validate YAML via tools |
| Invocation | IDE-specific or read `AGENTS.md` in skills repo | MCP tools in chat |
| Best for | Helm setup, prod manifests, idempotency review | Draft YAML, Kafka Connect migration |

## Installation

Full instructions: [skills/INSTALL.md](https://github.com/dataflow-operator/skills/blob/main/INSTALL.md)

```bash
git clone https://github.com/dataflow-operator/skills.git /tmp/dataflow-skills
mkdir -p .cursor/skills          # or .claude/skills for Claude Code
cp -r /tmp/dataflow-skills/* .cursor/skills/
```

**Cursor:** `@dataflow`, `@dataflow-config`, …

**Claude Code:** copy to `.claude/skills/` or link `AGENTS.md` in `CLAUDE.md`.

**Copilot:** reference `https://github.com/dataflow-operator/skills` in `.github/copilot-instructions.md`.

**Any agent:** open [AGENTS.md](https://github.com/dataflow-operator/skills/blob/main/AGENTS.md) in the skills repo.

## Available skills

| Skill | Purpose |
|-------|---------|
| `dataflow` | Entry point: DataFlow vs DataFlowCron |
| `dataflow-deploy` | Helm install, CRD, verification |
| `dataflow-config` | Write or review YAML |
| `dataflow-fault-tolerance` | Idempotency, checkpoint, ack |

## Typical workflow

1. `dataflow-deploy` — operator installed
2. `dataflow-config` — draft manifest
3. `dataflow-fault-tolerance` — pre-apply checklist
4. `kubectl apply -f manifest.yaml`

## Maintainer

Skills are developed in the [dataflow](https://github.com/dataflow-operator/dataflow) monorepo under `skills/` and published to **dataflow-operator/skills**. Extensions for operator development: `.cursor/skills/dataflow-*` in the monorepo.

## See also

- [Getting Started](getting-started.md)
- [Fault Tolerance](fault-tolerance.md)
- [MCP](mcp.md)
