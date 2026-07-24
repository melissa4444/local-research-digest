#!/usr/bin/env python3
"""A small local research-digest pipeline using only Python's standard library."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT / "config" / "topics.json"
RAW_DIR = PROJECT / "data" / "raw"
OUTPUT_DIR = PROJECT / "outputs"
USER_AGENT = "LocalResearchDigest/1.0"


def clean(text: str) -> str:
    """Make source text safe and readable in Markdown."""
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def request(url: str) -> bytes:
    """Fetch an HTTPS URL with curl, using the local operating-system CA store."""
    result = subprocess.run(
        ["curl", "--location", "--fail", "--silent", "--show-error",
         "--max-time", "30", "--user-agent", USER_AGENT, url],
        check=True,
        capture_output=True,
    )
    return result.stdout


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def fetch_arxiv(query: str, limit: int) -> list[dict]:
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": limit,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    root = ET.fromstring(request("https://export.arxiv.org/api/query?" + params))
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    papers = []
    for entry in root.findall("atom:entry", namespace):
        papers.append({
            "source": "arXiv",
            "title": clean(entry.findtext("atom:title", default="", namespaces=namespace)),
            "authors": ", ".join(
                clean(author.findtext("atom:name", default="", namespaces=namespace))
                for author in entry.findall("atom:author", namespace)
            ),
            "published": clean(entry.findtext("atom:published", default="", namespaces=namespace))[:10],
            "url": clean(entry.findtext("atom:id", default="", namespaces=namespace)),
            "abstract": clean(entry.findtext("atom:summary", default="", namespaces=namespace)),
        })
    return papers


def fetch_crossref(query: str, limit: int) -> list[dict]:
    params = urllib.parse.urlencode({
        "query.bibliographic": query,
        "rows": limit,
        "select": "title,author,published,DOI,abstract,container-title",
    })
    response = json.loads(request("https://api.crossref.org/works?" + params))
    papers = []
    for item in response["message"]["items"]:
        date_parts = item.get("published", {}).get("date-parts", [[]])[0]
        published = "-".join(
            str(part) if position == 0 else str(part).zfill(2)
            for position, part in enumerate(date_parts)
        )
        authors = [
            " ".join(filter(None, [author.get("given"), author.get("family")]))
            for author in item.get("author", [])
        ]
        papers.append({
            "source": "Crossref",
            "title": clean((item.get("title") or ["Untitled"])[0]),
            "authors": ", ".join(authors) or "Authors unavailable",
            "published": published or "Date unavailable",
            "url": "https://doi.org/" + item["DOI"] if item.get("DOI") else "",
            "abstract": clean(re.sub(r"<[^>]+>", " ", item.get("abstract", ""))),
            "venue": clean((item.get("container-title") or [""])[0]),
        })
    return papers


def fetch(config: dict) -> Path:
    """Stage 1: retrieve source records and save the raw normalized data locally."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    limit = config["papers_per_source"]
    sources = config["sources"]
    if sources["arxiv"]["enabled"]:
        records.extend(fetch_arxiv(sources["arxiv"]["query"], limit))
    if sources["crossref"]["enabled"]:
        records.extend(fetch_crossref(sources["crossref"]["query"], limit))

    raw_path = RAW_DIR / f"papers-{dt.date.today().isoformat()}.json"
    raw_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    return raw_path


def paper_block(paper: dict) -> str:
    title = paper["title"]
    if paper["url"]:
        title = f"[{title}]({paper['url']})"
    abstract = paper["abstract"] or "_No abstract supplied by this source._"
    if len(abstract) > 700:
        abstract = abstract[:700].rstrip() + "…"
    venue = f" · {paper['venue']}" if paper.get("venue") else ""
    return f"""### {title}

- **Published:** {paper["published"]}
- **Authors:** {paper["authors"]}
- **Source:** {paper["source"]}{venue}

{abstract}
"""


def generate(config: dict, raw_path: Path) -> Path:
    """Stage 2: turn a saved raw-data snapshot into a human-readable digest."""
    papers = json.loads(raw_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = {}
    for paper in papers:
        grouped.setdefault(paper["source"], []).append(paper)
    sections = []
    for source, source_papers in grouped.items():
        sections.append(f"## {source}\n\n" + "\n".join(paper_block(paper) for paper in source_papers))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = dt.date.today().isoformat()
    output_path = OUTPUT_DIR / f"digest-{date}.md"
    output_path.write_text(
        f"""# Research Digest: {config["digest_title"]}

**Generated:** {date}  
**Scope:** {config["description"]}

This digest was produced locally from the raw snapshot
data/raw/{raw_path.name}. Review source links and the original papers before
relying on a paper's claims.

{chr(10).join(sections)}
## Review prompts

1. What is the threat model and trust boundary?
2. Does it fit edge constraints: latency, energy, memory, privacy, and connectivity?
3. Is it tested with realistic data and adaptive adversaries?
""",
        encoding="utf-8",
    )
    return output_path


def latest_snapshot() -> Path:
    snapshots = sorted(RAW_DIR.glob("papers-*.json"))
    if not snapshots:
        raise FileNotFoundError("No raw snapshot exists. Run fetch first.")
    return snapshots[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("fetch", help="Fetch papers and save a local JSON snapshot.")
    build_parser = subcommands.add_parser("build", help="Build Markdown from a saved JSON snapshot.")
    build_parser.add_argument("--input", type=Path, help="Snapshot to use; defaults to the latest.")
    subcommands.add_parser("run", help="Fetch a new snapshot, then build its Markdown digest.")
    args = parser.parse_args()
    config = load_config()

    if args.command == "fetch":
        print(fetch(config))
    elif args.command == "build":
        print(generate(config, args.input or latest_snapshot()))
    else:
        print(generate(config, fetch(config)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
