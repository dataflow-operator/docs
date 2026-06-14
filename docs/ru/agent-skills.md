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

## Workflow

1. `dataflow-deploy` → 2. `dataflow-config` → 3. `dataflow-fault-tolerance` → 4. `kubectl apply`

## Maintainer

Разработка в monorepo [dataflow](https://github.com/dataflow-operator/dataflow) (`skills/`), публикация в **dataflow-operator/skills**. Расширения: `.cursor/skills/dataflow-*`.

## См. также

- [Начало работы](getting-started.md)
- [Отказоустойчивость](fault-tolerance.md)
- [MCP](mcp.md)
