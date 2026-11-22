"""Offline tests for JSON metadata extraction and caption safety."""
import unittest

from metadata import extract_item, caption_segments


class MetadataTests(unittest.TestCase):
    def test_single_app(self):
        obj = {"name": "Great Game", "version": "1.2", "ipaUrl": "https://example.org/abc?token=x",
               "description": "Line one\nLine two", "iconURL": "https://example.org/icon.png"}
        item = extract_item(obj)
        self.assertEqual(item.file_name, "Great Game - v1.2.ipa")
        self.assertEqual(item.description, "Line one\nLine two")
        self.assertEqual(item.icon_url, "https://example.org/icon.png")
        self.assertEqual(item.version, "1.2")

    def test_pubg_targets_only_main_url_note_icon(self):
        import json
        from pathlib import Path
        fixture = json.loads((Path(__file__).parent / "pubg_targets.json").read_text(encoding="utf-8"))
        self.assertEqual(len(fixture["apps"]), 1)
        expected = {
            "APP-5874636765": ("Pubg GL Hack", "http://file-to-link-stevebotz-01.koyeb.app/9715/EL+CHAPO+PRO+V2+4.7.ipa?hash=AgADQS"),
        }
        for app_id, (name, url) in expected.items():
            item = extract_item(fixture, app_id)
            raw = next(app for app in fixture["apps"] if app["id"] == app_id)
            self.assertEqual(item.url, url)
            self.assertEqual(item.name, name)
            self.assertEqual(item.version, "4.7.0")
            self.assertEqual(item.description, raw["note"])
            self.assertEqual(item.icon_url, raw["icon"])
            self.assertEqual(f"{item.name} - {item.version} [ @iKiraPlus ].ipa",
                             f"{name} - 4.7.0 [ @iKiraPlus ].ipa")

    def test_catalog_selector(self):
        data = {"apps": [
            {"id": "a", "name": "Game A", "downloadURL": "https://example.org/a.ipa"},
            {"id": "b", "name": "Game B", "downloadURL": "https://example.org/b.ipa"}]}
        with self.assertRaises(RuntimeError):
            extract_item(data)
        self.assertEqual(extract_item(data, "Game B").file_name, "Game B.ipa")
        self.assertEqual(extract_item(data, "2").url, "https://example.org/b.ipa")

    def test_nested_versions(self):
        data = {"apps": [{"name": "App", "version": "2.0", "versions": [
            {"version": "1.0", "downloadURL": "https://example.org/1.ipa"},
            {"version": "2.0", "downloadURL": "https://example.org/2.ipa"}]}]}
        self.assertEqual(extract_item(data).url, "https://example.org/2.ipa")

    def test_long_caption_roundtrip(self):
        text = "Hello 🕹️ مرحبا\n" * 1000
        chunks = caption_segments(text)
        self.assertEqual("".join(chunks), text)
        self.assertLessEqual(len(chunks[0].encode("utf-16-le")) // 2, 1024)
        self.assertTrue(all(len(x.encode("utf-16-le")) // 2 <= 4096 for x in chunks[1:]))


if __name__ == "__main__":
    unittest.main()
