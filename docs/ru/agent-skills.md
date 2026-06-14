# Agent Skills

Agent skills — переносимые Markdown-инструкции для любого AI-ассистента: deploy DataFlow Operator, production manifests, отказоустойчивость. Работают с **Cursor, Claude Code, GitHub Copilot, Windsurf, Cline** и другими LLM-инструментами — не только Cursor.

В отличие от [MCP](mcp.md), skills не вызывают tools — дают операционные знания из документации и `config/samples`.

## Skills vs MCP

| | **Agent skills** | **MCP** |
|---|------------------|---------|
| Назначение | Deploy, паттерны, чеклисты resilience | Генерация и валидация YAML |
| Вызов | Зависит от IDE (ниже) или `AGENTS.md` | MCP tools в чате |
| Доступ к Kubernetes | Не нужен | Не нужен |
| Лучше для | Helm, prod manifests, идемпотентность | Черновики YAML, миграция Kafka Connect |

## Установка

Полная инструкция: [skills/INSTALL.md](https://github.com/dataflow-operator/dataflow/blob/main/skills/INSTALL.md)

### Cursor

```bash
git clone https://github.com/dataflow-operator/dataflow.git /tmp/dataflow
mkdir -p .cursor/skills
cp -r /tmp/dataflow/skills/* .cursor/skills/
```

Вызов: `@dataflow`, `@dataflow-config`, …

### Claude Code

```bash
mkdir -p .claude/skills
cp -r /tmp/dataflow/skills/* .claude/skills/
```

Или ссылка в `CLAUDE.md` на [AGENTS.md](https://github.com/dataflow-operator/dataflow/blob/main/AGENTS.md).

### GitHub Copilot

Добавьте в `.github/copilot-instructions.md`:

```markdown
For DataFlow manifests, follow skills/ in the dataflow-operator repo (see AGENTS.md).
```

### Любой агент (без установки)

Откройте [AGENTS.md](https://github.com/dataflow-operator/dataflow/blob/main/AGENTS.md) — индекс всех guides.

## Доступные skills

| Skill | Назначение |
|-------|------------|
| `dataflow` | Точка входа: DataFlow vs DataFlowCron |
| `dataflow-deploy` | Helm, CRD, verify |
| `dataflow-config` | YAML `DataFlow` / `DataFlowCron` |
| `dataflow-fault-tolerance` | Идемпотентность, checkpoint, ack |

Исходники: [skills/](https://github.com/dataflow-operator/dataflow/tree/main/skills) в репозитории.

## Типичный workflow

1. `dataflow-deploy` — оператор установлен
2. `dataflow-config` — черновик manifest
3. `dataflow-fault-tolerance` — чеклист перед apply
4. `kubectl apply -f manifest.yaml`

## Maintainer

В репозитории **dataflow-operator** maintainer-расширения — `.cursor/skills/dataflow-*`. Клиентский контент — `skills/`; см. `.cursor/skills/SYNC.md`.

## См. также

- [Начало работы](getting-started.md)
- [Отказоустойчивость](fault-tolerance.md)
- [MCP](mcp.md)
- [Примеры](examples.md)
