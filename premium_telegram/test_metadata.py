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
