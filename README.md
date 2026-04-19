# DataFlow Operator Documentation

Documentation site for [DataFlow Operator](https://github.com/dataflow-operator/dataflow), built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

**Live site**: https://dataflow-operator.github.io/docs/

## Languages

- English ([`docs/docs/en/`](docs/docs/en/)) — primary technical reference
- Russian ([`docs/docs/ru/`](docs/docs/ru/)) — mirror where maintained; substantive protocol and API details may lag English slightly

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

Quick check (no MkDocs run) that every `nav` target exists on disk:

```bash
python3 verify_nav_files.py
```

## Structure

```
docs/
├── mkdocs.yml              # MkDocs configuration
├── requirements.txt        # Python dependencies
├── docs/
│   ├── en/                 # English pages (MkDocs docs_dir)
│   ├── ru/                 # Russian pages
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
