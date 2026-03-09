# Автоматическое версионирование (Semver)

Проект использует автоматическое версионирование по принципу [Semantic Versioning](https://semver.org/) на основе [Conventional Commits](https://www.conventionalcommits.org/).

## Как это работает

1. **При push в `main`** запускается workflow `Release (Semver)`
2. **semantic-release** анализирует коммиты с последнего тега
3. По типу коммитов определяется следующая версия:
   - `fix:` или `fix(scope):` → **patch** (1.0.0 → 1.0.1)
   - `feat:` или `feat(scope):` → **minor** (1.0.0 → 1.1.0)
   - `BREAKING CHANGE:` в footer или `!` после типа → **major** (1.0.0 → 2.0.0)
4. Обновляются `Chart.yaml`, `package.json`, создаётся `CHANGELOG.md`
5. Создаётся git-тег `vX.Y.Z` и GitHub Release
6. Build workflows собирают образы с новой версией

## Формат коммитов

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Типы:**
- `feat` — новая функциональность (minor)
- `fix` — исправление бага (patch)
- `docs` — документация (без релиза)
- `style` — форматирование (без релиза)
- `refactor` — рефакторинг (без релиза)
- `test` — тесты (без релиза)
- `chore` — служебные изменения (без релиза)

**Примеры:**
```
feat(api): add new endpoint for health check
fix(processor): resolve memory leak in Kafka consumer
docs: update installation guide
```

**Breaking change:**
```
feat(api)!: remove deprecated endpoint

BREAKING CHANGE: /v1/legacy endpoint has been removed
```

## Файлы конфигурации

- `.github/workflows/release.yml` — основной release workflow
- `.releaserc.json` — конфигурация semantic-release (плагины, обновление Chart.yaml, package.json)

## Ручной релиз

Для ручного создания релиза создайте тег:

```bash
git tag v1.2.3
git push origin v1.2.3
```

Build workflows соберут артефакты для этого тега. Для автоматического обновления Chart.yaml и package.json используйте conventional commits и merge в main.
