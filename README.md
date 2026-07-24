# Local research digest

This is a small local project designed to make the research-digest workflow
visible:

    config/topics.json → fetch → data/raw/papers-YYYY-MM-DD.json → build → outputs/digest-YYYY-MM-DD.md

It uses public arXiv and Crossref APIs, but stores the retrieved records and
renders the report on your computer. There are no packages to install; Python
3 and curl are sufficient.

## Run it

From this folder:

    python3 src/research_digest.py fetch
    python3 src/research_digest.py build

Or run both stages at once:

    python3 src/research_digest.py run

## VS Code setup

Open the local-research-digest folder in VS Code, then install the recommended
extensions when prompted. The Run and Debug panel includes three launch targets:
Run all, Fetch papers, and Build from saved data. You can set a breakpoint in
src/research_digest.py, choose a target, and press F5 to inspect each stage.

The same commands are also available via Terminal > Run Task.

## Understand and adapt it

- Edit config/topics.json to change the topic, source queries, or result count.
- fetch creates an inspectable JSON snapshot in data/raw/. This is the
  normalized data coming from the sources.
- build reads the JSON snapshot and renders a Markdown digest in outputs/.
  This works offline after a snapshot exists.
- run combines both commands for convenience.

The implementation is intentionally contained in src/research_digest.py:

- fetch_arxiv and fetch_crossref retrieve and normalize source data.
- fetch writes the raw local snapshot.
- generate transforms that snapshot into Markdown.

## Useful experiments

1. Disable one source in config/topics.json and see how the report changes.
2. Change a query, run fetch, and inspect the raw JSON before using build.
3. Rebuild an existing snapshot with build --input data/raw/papers-YYYY-MM-DD.json.
