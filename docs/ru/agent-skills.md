# Agent Skills

Переносимые Markdown-инструкции для любого AI-ассистента. Публикуемый репозиторий:

**https://github.com/dataflow-operator/skills**

В отличие от [MCP](mcp.md), skills не вызывают tools — дают операционные знания из документации и `config/samples`.

## Skills vs MCP

| | **Agent skills** | **MCP** |
|---|------------------|---------|
| Назначение | Deploy, паттерны, resilience | Генерация и валидация YAML |
| Вызов | IDE или `AGENTS.md` в skills repo | MCP tools |
| Лучше для | Helm, prod manifests | Черновики YAML, Kafka Connect |

## Установка

Полная инструкция: [skills/INSTALL.md](https://github.com/dataflow-operator/skills/blob/main/INSTALL.md)

```bash
git clone https://github.com/dataflow-operator/skills.git /tmp/dataflow-skills
mkdir -p .cursor/skills          # или .claude/skills для Claude Code
cp -r /tmp/dataflow-skills/* .cursor/skills/
```

**Cursor:** `@dataflow`, `@dataflow-config`, …

**Claude Code:** копия в `.claude/skills/` или ссылка на `AGENTS.md` в `CLAUDE.md`.

**Copilot:** ссылка на `https://github.com/dataflow-operator/skills` в `.github/copilot-instructions.md`.

**Любой агент:** [AGENTS.md](https://github.com/dataflow-operator/skills/blob/main/AGENTS.md) в skills repo.

## Skills

| Skill | Назначение |
|-------|------------|
| `dataflow` | DataFlow vs DataFlowCron |
| `dataflow-deploy` | Helm, CRD, verify |
| `dataflow-config` | YAML manifests |
| `dataflow-fault-tolerance` | Идемпотентность, checkpoint |

Сопутствующие файлы: [anti-patterns.md](https://github.com/dataflow-operator/skills/blob/main/dataflow-config/anti-patterns.md), [samples-index.md](https://github.com/dataflow-operator/skills/blob/main/dataflow-config/samples-index.md).

## Типичный workflow (skills → validate → apply)

1. **`dataflow-deploy`** — оператор установлен (Helm/CRD, webhook в prod).
2. **`dataflow` / `dataflow-config`** — выбор kind, черновик из skills + [samples](https://github.com/dataflow-operator/dataflow/tree/main/config/samples); проверить [anti-patterns](https://github.com/dataflow-operator/skills/blob/main/dataflow-config/anti-patterns.md).
3. **`dataflow-fault-tolerance`** — pre-apply checklist (upsert, checkpoint, replicas, ack).
4. **Опционально MCP** — `generate_dataflow_manifest` / `validate_dataflow_manifest` для черновика.

    !!! warning "MCP validate — поверхностный"
        MCP проверяет apiVersion/kind и наличие `type` + `config` у source/sink. Это **не** замена validating webhook. См. [MCP](mcp.md).

5. **Server dry-run (admission)** — перед созданием ресурса:

    ```bash
    kubectl apply --dry-run=server -f manifest.yaml
    ```

6. **Apply и проверка**

    ```bash
    kubectl apply -f manifest.yaml
    kubectl get dataflow,dataflowcron -n <namespace>
    kubectl describe dataflow <name>
    ```

## LLM crawlers

Машиночитаемая карта документации: [llms.txt](https://dataflow-operator.github.io/docs/llms.txt).

## JSON Schema (машиночитаемый контракт)

Стабильные URL: [`/schemas/`](https://dataflow-operator.github.io/docs/schemas/):

| Артефакт | Назначение |
|----------|------------|
| [`catalog.json`](https://dataflow-operator.github.io/docs/schemas/catalog.json) | Allow-list типов; pin `operatorVersion` |
| [`dataflow.json`](https://dataflow-operator.github.io/docs/schemas/dataflow.json) / [`dataflowcron.json`](https://dataflow-operator.github.io/docs/schemas/dataflowcron.json) | CRD envelope |
| `connectors/sources|sinks/<type>.json` | Типизированный `config` коннектора |
| `transforms/<type>.json` | Типизированные конфиги трансформаций |

Workflow: skills → опционально MCP (shallow) → schemas / `kubectl apply --dry-run=server`.

## Maintainer

Разработка в monorepo [dataflow](https://github.com/dataflow-operator/dataflow) (`skills/`), публикация в **dataflow-operator/skills**. Расширения: `.cursor/skills/dataflow-*` (stubs + maintainer-only — см. `SYNC.md`).

## См. также

- [Начало работы](getting-started.md)
- [Отказоустойчивость](fault-tolerance.md)
- [MCP](mcp.md)
- [Best Practices](best-practices.md)
