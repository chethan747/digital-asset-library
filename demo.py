"""End-to-end demo: builds a small library from sample files and exercises
ingest, dedup, search, publish, reuse and stats.

Run:  python3 demo.py
The demo uses a temporary directory and leaves no files behind. Sample
image files are metadata-only placeholders (a PNG header, not a real
picture); the library records their metadata and never parses their pixels.
"""

import tempfile
from pathlib import Path

from damlib.library import Library

SAMPLES = [
    ("brand-hero.jpg", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64,
     "Brand Hero Banner", "Homepage hero image for the spring brand campaign",
     ["brand", "hero", "campaign"], "marketing", "internal"),
    ("brand-logo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32,
     "Brand Logo", "Primary brand logo, light background variant",
     ["brand", "logo"], "marketing", "internal"),
    ("product-guide.md", b"# Product Guide\nHow to use the new product line.\n",
     "Product Guide", "Guide to the product line for support teams",
     ["product", "guide"], "documentation", "internal"),
    ("team-photo.jpg", b"\x89PNG\r\n\x1a\n" + b"\x00" * 48,
     "Team Photo", "Team photo from the company offsite",
     ["team", "people"], "internal-comms", "internal"),
]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        lib = Library(root / "demo.db")
        print("== ingest ==")
        for name, data, title, desc, tags, category, licence in SAMPLES:
            path = root / name
            path.write_bytes(data)
            asset, is_new = lib.add_asset(path, title=title, description=desc,
                                          tags=tags, category=category,
                                          licence=licence)
            print(f"  {'added' if is_new else 'dedup'}: {asset.title} "
                  f"(id={asset.id}, {asset.filetype}, {asset.size_bytes} bytes)")

        print("== dedup check: re-add the hero image ==")
        _, is_new = lib.add_asset(root / "brand-hero.jpg")
        print(f"  is_new={is_new} (expected False)")

        print("== search: 'brand' ==")
        for asset, score in lib.search("brand"):
            print(f"  (score {score}) {asset.title} [{asset.category}]")

        print("== search: 'brand' filtered to category=marketing ==")
        for asset, score in lib.search("brand", category="marketing"):
            print(f"  (score {score}) {asset.title}")

        print("== publish + reuse ==")
        hero = lib.search("brand hero")[0][0]
        lib.publish(hero.id)
        lib.record_reuse(hero.id)
        lib.record_reuse(hero.id)
        print(f"  {hero.title}: status=published, reuses=2")

        print("== stats ==")
        stats = lib.stats()
        print(f"  total={stats['total']}, by_status={stats['by_status']}, "
              f"total_reuses={stats['total_reuses']}")
        lib.close()
    print("demo complete")


if __name__ == "__main__":
    main()
