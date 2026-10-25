"""Command-line interface for the Digital Asset Library.

Usage:
    python3 -m damlib.cli --db library.db add photo.jpg --title "Hero" --tags brand,hero --category marketing
    python3 -m damlib.cli --db library.db search --query brand
    python3 -m damlib.cli --db library.db search --query brand --tag hero
    python3 -m damlib.cli --db library.db list
    python3 -m damlib.cli --db library.db list --status published
    python3 -m damlib.cli --db library.db publish 1
    python3 -m damlib.cli --db library.db reuse 1
    python3 -m damlib.cli --db library.db stats
"""

import argparse
import json
import sys

from .library import Library


def _split_tags(value):
    return [t.strip() for t in value.split(",") if t.strip()] if value else []


def _fmt(asset):
    return (f"[{asset.id}] {asset.title} ({asset.filename}, {asset.filetype}, "
            f"{asset.size_bytes} bytes, {asset.status}, "
            f"category={asset.category or '-'}, "
            f"tags={','.join(asset.tags) or '-'}, reuses={asset.reuse_count})")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="damlib")
    parser.add_argument("--db", default="library.db", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="ingest a file into the library")
    p_add.add_argument("file")
    p_add.add_argument("--title")
    p_add.add_argument("--description", default="")
    p_add.add_argument("--tags", default="")
    p_add.add_argument("--category", default="")
    p_add.add_argument("--licence", default="")

    p_search = sub.add_parser("search", help="search title/description/tags")
    p_search.add_argument("--query", default="")
    p_search.add_argument("--tag")
    p_search.add_argument("--category")

    p_list = sub.add_parser("list", help="list assets, optionally filtered")
    p_list.add_argument("--status")
    p_list.add_argument("--category")
    p_list.add_argument("--tag")

    p_pub = sub.add_parser("publish", help="move a draft asset to published")
    p_pub.add_argument("id", type=int)
    p_reuse = sub.add_parser("reuse", help="record one reuse of an asset")
    p_reuse.add_argument("id", type=int)
    sub.add_parser("stats", help="show library statistics")

    args = parser.parse_args(argv)
    lib = Library(args.db)
    try:
        if args.command == "add":
            asset, is_new = lib.add_asset(
                args.file, title=args.title, description=args.description,
                tags=_split_tags(args.tags), category=args.category,
                licence=args.licence)
            print(("added " if is_new else "already in library (dedup, same content): ")
                  + _fmt(asset))
        elif args.command == "search":
            results = lib.search(args.query, tag=args.tag, category=args.category)
            if not results:
                print("no results")
            for asset, score in results:
                print(f"(score {score}) " + _fmt(asset))
        elif args.command == "list":
            assets = lib.list_assets(status=args.status, category=args.category,
                                     tag=args.tag)
            if not assets:
                print("no assets")
            for asset in assets:
                print(_fmt(asset))
        elif args.command == "publish":
            print("published " + _fmt(lib.publish(args.id)))
        elif args.command == "reuse":
            print("reuse recorded " + _fmt(lib.record_reuse(args.id)))
        elif args.command == "stats":
            print(json.dumps(lib.stats(), indent=2, sort_keys=True))
    finally:
        lib.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
