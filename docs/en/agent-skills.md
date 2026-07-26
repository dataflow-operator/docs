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

Companion files in the skills repo: [anti-patterns.md](https://github.com/dataflow-operator/skills/blob/main/dataflow-config/anti-patterns.md), [samples-index.md](https://github.com/dataflow-operator/skills/blob/main/dataflow-config/samples-index.md).

## Typical workflow (skills → validate → apply)

1. **`dataflow-deploy`** — operator installed (Helm/CRD, webhook enabled in prod).
2. **`dataflow` / `dataflow-config`** — choose kind, draft manifest from skills + [samples](https://github.com/dataflow-operator/dataflow/tree/main/config/samples); check [anti-patterns](https://github.com/dataflow-operator/skills/blob/main/dataflow-config/anti-patterns.md).
3. **`dataflow-fault-tolerance`** — pre-apply checklist (upsert, checkpoint, replicas, ack).
4. **Optional MCP** — `generate_dataflow_manifest` / `validate_dataflow_manifest` for a quick draft.

    !!! warning "MCP validate is shallow"
        MCP checks apiVersion/kind and that source/sink have `type` + `config`. It does **not** replace the operator validating webhook. See [MCP](mcp.md).

5. **Server dry-run (admission)** — before creating the resource:

    ```bash
    kubectl apply --dry-run=server -f manifest.yaml
    ```

6. **Apply and verify**

    ```bash
    kubectl apply -f manifest.yaml
    kubectl get dataflow,dataflowcron -n <namespace>
    kubectl describe dataflow <name>
    ```

## LLM crawlers

Machine-readable map of docs and agent entry points: [llms.txt](llms.txt) (served at the site root `/llms.txt`).

## JSON Schemas (machine-readable contract)

Stable URLs under [`/schemas/`](https://dataflow-operator.github.io/docs/schemas/):

| Artifact | Use |
|----------|-----|
| [`catalog.json`](https://dataflow-operator.github.io/docs/schemas/catalog.json) | Allow-list of source/sink/transform types; `operatorVersion` pin |
| [`dataflow.json`](https://dataflow-operator.github.io/docs/schemas/dataflow.json) / [`dataflowcron.json`](https://dataflow-operator.github.io/docs/schemas/dataflowcron.json) | CRD envelope (top-level spec) |
| `connectors/sources|sinks/<type>.json` | Typed connector `config` (CRD stores it as opaque `RawExtension`) |
| `transforms/<type>.json` | Typed transformation configs |

Workflow: draft from skills → optional MCP (shallow) → validate against schemas / `kubectl apply --dry-run=server`.

## Maintainer

Skills are developed in the [dataflow](https://github.com/dataflow-operator/dataflow) monorepo under `skills/` and published to **dataflow-operator/skills**. Extensions for operator development: `.cursor/skills/dataflow-*` in the monorepo (stubs + maintainer-only files — see `SYNC.md`).

## See also

- [Getting Started](getting-started.md)
- [Fault Tolerance](fault-tolerance.md)
- [MCP](mcp.md)
- [Best Practices](best-practices.md)
