# DataFlow Operator Documentation

Documentation site for [DataFlow Operator](https://github.com/dataflow-operator/dataflow), built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

**Live site**: https://dataflow-operator.github.io/docs/

## Languages

- English (`docs/en/`)
- Russian (`docs/ru/`)

## Local development

```bash
pip install -r requirements.txt
mkdocs serve
```

Open http://localhost:8000.

## Build

```bash
mkdocs build
```

Output goes to `site/`.

## Structure

```
docs/
├── mkdocs.yml              # MkDocs configuration
├── requirements.txt        # Python dependencies
├── docs/
│   ├── en/                 # English documentation
│   ├── ru/                 # Russian documentation
│   ├── images/             # Logo, favicon
│   ├── stylesheets/        # Custom CSS
│   └── javascripts/        # Custom JS
└── .github/workflows/
    └── docs.yml            # CI: deploy to GitHub Pages
```

## Topics covered

- Getting Started
- Architecture
- Connectors (Kafka, PostgreSQL, ClickHouse, Trino, Nessie)
- Transformations
- Configuration examples
- Error handling and fault tolerance
- Prometheus metrics
- Web GUI
- MCP server
- Development guide
- Connector development
- Semantic versioning and releases
