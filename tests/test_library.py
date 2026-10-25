"""Unit tests for the Digital Asset Library (stdlib unittest only)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from damlib.library import Library


def _write(root, name, data):
    path = Path(root) / name
    path.write_bytes(data)
    return path


class TestIngestion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lib = Library(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.lib.close()
        self.tmp.cleanup()

    def test_ingest_extracts_metadata(self):
        path = _write(self.tmp.name, "hero.jpg", b"\x89PNG" + b"\x00" * 100)
        asset, is_new = self.lib.add_asset(path, title="Hero",
                                           tags=["brand"], category="marketing")
        self.assertTrue(is_new)
        self.assertEqual(asset.filename, "hero.jpg")
        self.assertEqual(asset.filetype, "image")
        self.assertEqual(asset.size_bytes, 104)
        self.assertEqual(asset.title, "Hero")
        self.assertEqual(asset.tags, ["brand"])
        self.assertEqual(asset.status, "draft")
        self.assertEqual(len(asset.checksum), 64)

    def test_dedup_same_content(self):
        p1 = _write(self.tmp.name, "a.txt", b"same content")
        p2 = _write(self.tmp.name, "b.txt", b"same content")
        a1, new1 = self.lib.add_asset(p1)
        a2, new2 = self.lib.add_asset(p2)
        self.assertTrue(new1)
        self.assertFalse(new2)
        self.assertEqual(a1.id, a2.id)
        self.assertEqual(len(self.lib.list_assets()), 1)

    def test_different_content_not_deduped(self):
        _write(self.tmp.name, "a.txt", b"one")
        _write(self.tmp.name, "b.txt", b"two")
        self.lib.add_asset(Path(self.tmp.name) / "a.txt")
        self.lib.add_asset(Path(self.tmp.name) / "b.txt")
        self.assertEqual(len(self.lib.list_assets()), 2)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.lib.add_asset(Path(self.tmp.name) / "nope.txt")


class TestMetadata(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lib = Library(Path(self.tmp.name) / "test.db")
        path = _write(self.tmp.name, "doc.md", b"# doc")
        self.asset, _ = self.lib.add_asset(path, title="Old",
                                           category="docs")

    def tearDown(self):
        self.lib.close()
        self.tmp.cleanup()

    def test_update_metadata(self):
        updated = self.lib.update_asset(self.asset.id, title="New",
                                        tags=["guide", "v2"],
                                        category="support")
        self.assertEqual(updated.title, "New")
        self.assertEqual(updated.tags, ["guide", "v2"])
        self.assertEqual(updated.category, "support")
        # Unchanged fields survive.
        self.assertEqual(updated.filename, "doc.md")

    def test_update_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            self.lib.update_asset(9999, title="x")


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lib = Library(Path(self.tmp.name) / "test.db")
        root = Path(self.tmp.name)
        self.lib.add_asset(_write(root, "a.txt", b"1"), title="Brand Hero",
                           description="something else",
                           tags=["campaign"], category="marketing")
        self.lib.add_asset(_write(root, "b.txt", b"2"), title="Unrelated",
                           description="brand guidelines document",
                           tags=[], category="docs")
        self.lib.add_asset(_write(root, "c.txt", b"3"), title="Brand Logo",
                           description="logo file",
                           tags=["brand"], category="marketing")

    def tearDown(self):
        self.lib.close()
        self.tmp.cleanup()

    def test_title_match_ranks_above_description_match(self):
        results = self.lib.search("brand")
        titles = [a.title for a, _ in results]
        # Title hits (+10) outrank the description-only hit (+3).
        self.assertEqual(titles[-1], "Unrelated")
        self.assertIn("Brand Hero", titles[:2])
        self.assertIn("Brand Logo", titles[:2])

    def test_tag_filter(self):
        results = self.lib.search("", tag="brand")
        self.assertEqual([a.title for a, _ in results], ["Brand Logo"])

    def test_category_filter(self):
        results = self.lib.search("brand", category="marketing")
        self.assertEqual({a.title for a, _ in results},
                         {"Brand Hero", "Brand Logo"})

    def test_no_match_returns_empty(self):
        self.assertEqual(self.lib.search("zzzzzz"), [])


class TestPublishAndReuse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lib = Library(Path(self.tmp.name) / "test.db")
        path = _write(self.tmp.name, "x.txt", b"x")
        self.asset, _ = self.lib.add_asset(path)

    def tearDown(self):
        self.lib.close()
        self.tmp.cleanup()

    def test_publish_and_archive_flow(self):
        self.assertEqual(self.lib.publish(self.asset.id).status, "published")
        self.assertEqual(
            self.lib.set_status(self.asset.id, "archived").status, "archived")
        self.assertEqual(
            self.lib.set_status(self.asset.id, "draft").status, "draft")

    def test_invalid_transition_raises(self):
        # draft -> published is fine, but published -> draft is not allowed.
        self.lib.publish(self.asset.id)
        with self.assertRaises(ValueError):
            self.lib.set_status(self.asset.id, "draft")
        # published -> published is not a transition.
        with self.assertRaises(ValueError):
            self.lib.publish(self.asset.id)

    def test_reuse_counting_and_stats(self):
        self.lib.record_reuse(self.asset.id)
        self.lib.record_reuse(self.asset.id)
        self.assertEqual(self.lib.get(self.asset.id).reuse_count, 2)
        stats = self.lib.stats()
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["total_reuses"], 2)
        self.assertEqual(stats["by_status"], {"draft": 1})


if __name__ == "__main__":
    unittest.main()
