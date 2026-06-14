# DataFlow Operator Documentation

Documentation site for [DataFlow Operator](https://github.com/dataflow-operator/dataflow), built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) and [mkdocs-static-i18n](https://ultrabug.github.io/mkdocs-static-i18n/).

**Live site**: https://dataflow-operator.github.io/docs/en/

Open `/en/` or `/ru/` after `mkdocs serve`.

## Local development

```bash
cd docs
pip install -r requirements.txt
mkdocs serve
```

Open http://127.0.0.1:8000/en/ or http://127.0.0.1:8000/ru/

## Build

```bash
cd docs
mkdocs build
```

Output goes to `site/`.

Verify nav targets exist in both locales:

```bash
cd docs
python3 verify_nav_files.py
```

## Structure

```
docs/
├── mkdocs.yml              # MkDocs + i18n configuration
├── requirements.txt
├── verify_nav_files.py
├── docs/
│   ├── en/                 # English pages
│   │   ├── concepts/       # Workload types, shared concepts
│   │   ├── dataflow/       # DataFlow CRD reference
│   │   └── dataflow-cron/  # DataFlowCron CRD reference
│   ├── ru/                 # Russian mirror (same paths)
│   ├── images/
│   ├── stylesheets/
│   └── javascripts/
└── .github/workflows/
    └── docs.yml
```

## Navigation sections

| Section | Contents |
|---------|----------|
| Concepts | Architecture, DataFlow vs DataFlowCron |
| DataFlow | Overview, spec, lifecycle |
| DataFlowCron | Overview, spec, triggers, examples |
| Pipeline | Connectors, transformations |
| Guides | Examples, errors, fault tolerance, metrics |
| Tools | Web GUI, MCP |
| Development | Developer guide, releases, connector protocol |
