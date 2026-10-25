# Digital Asset Library

A searchable media library: ingest files, attach structured metadata and
taxonomy, find assets by full-text search and filters, and publish and reuse
them at scale. Pure Python, standard library only — no dependencies to install.

## What it does

- **Asset ingestion** — add files of any type. Metadata is extracted from
  the file itself: filename, size, broad type (by extension), modification
  date, and a SHA-256 checksum. Identical content is deduplicated on
  checksum, so the same file added twice is stored once.
- **Metadata & taxonomy** — every asset carries a title, description, tags,
  taxonomy category and licence/status, all editable after ingest.
- **Search & discovery** — full-text search over title, description and
  tags, plus tag and category filters. Results are ranked: title hits
  outrank tag hits, which outrank description hits.
- **Reuse & publish** — assets move through `draft → published → archived`
  (with `archived → draft` for rework). Every reuse is counted, and stats
  summarise the library by status, category and total reuses.

## How to run

```bash
# Demo (builds a sample library in a temp dir, searches, publishes, stats)
python3 demo.py

# CLI — add, search, list, publish, reuse, stats
python3 -m damlib.cli --db library.db add photo.jpg --title "Brand Hero" \
    --tags brand,hero --category marketing --description "Homepage hero"
python3 -m damlib.cli --db library.db search --query brand
python3 -m damlib.cli --db library.db search --query brand --tag hero
python3 -m damlib.cli --db library.db search --query brand --category marketing
python3 -m damlib.cli --db library.db list
python3 -m damlib.cli --db library.db list --status published
python3 -m damlib.cli --db library.db publish 1
python3 -m damlib.cli --db library.db reuse 1
python3 -m damlib.cli --db library.db stats

# Tests
python3 -m unittest discover -s tests -v
```

## Architecture

```
demo.py                  End-to-end demo with a sample dataset
damlib/
  library.py             Library class: SQLite store, ingestion, metadata,
                         search ranking, status transitions, reuse, stats
  cli.py                 argparse CLI (add / search / list / publish / reuse / stats)
tests/
  test_library.py        unittest suite
```

Assets live in one SQLite table (`assets`). Tags are stored as JSON, the
checksum column is unique (that is what enforces dedup), and search scoring
is a small deterministic function over metadata — no external search engine.

## Honest mapping to the portfolio description

This project implements, as a standalone Python program, the concepts in the
portfolio description "A searchable media library on AEM DAM — structured
assets and metadata so teams can find, reuse and publish the right media
without digging through folders" (features: AEM DAM structure, metadata &
taxonomy, search & discovery, asset reuse at scale).

It does **not** run inside Adobe AEM DAM, it is not an AEM package, and it
is not claimed as a client production system. No client usage figures are
stated anywhere in this repo, because none exist for this implementation.
Binary files (for example images) are handled by file metadata only: this
code does not parse image pixels or extract embedded image metadata.
