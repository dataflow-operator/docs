# Automatic Versioning (Semver)

The project uses automatic versioning based on [Semantic Versioning](https://semver.org/) principles using [Conventional Commits](https://www.conventionalcommits.org/).

## How it works

1. **On push to `main`** the `Release (Semver)` workflow is triggered
2. **semantic-release** analyzes commits since the last tag
3. The next version is determined by commit types:
   - `fix:` or `fix(scope):` → **patch** (1.0.0 → 1.0.1)
   - `feat:` or `feat(scope):` → **minor** (1.0.0 → 1.1.0)
   - `BREAKING CHANGE:` in footer or `!` after type → **major** (1.0.0 → 2.0.0)
4. `Chart.yaml`, `package.json` are updated, `CHANGELOG.md` is created
5. A git tag `vX.Y.Z` and GitHub Release are created
6. Build workflows build images with the new version

## Commit format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat` — new functionality (minor)
- `fix` — bug fix (patch)
- `docs` — documentation (no release)
- `style` — formatting (no release)
- `refactor` — refactoring (no release)
- `test` — tests (no release)
- `chore` — maintenance changes (no release)

**Examples:**
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

## Configuration files

- `.github/workflows/release.yml` — main release workflow
- `.releaserc.json` — semantic-release configuration (plugins, Chart.yaml and package.json updates)

## Manual release

To manually create a release, create a tag:

```bash
git tag v1.2.3
git push origin v1.2.3
```

Build workflows will build artifacts for this tag. For automatic Chart.yaml and package.json updates, use conventional commits and merge into main.
