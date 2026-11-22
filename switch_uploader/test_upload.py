import json
import tempfile
import unittest
from pathlib import Path

from upload import CAPTION, USER_TAG, load_games


class SwitchManifestTests(unittest.TestCase):
    def test_fixed_caption(self):
        self.assertEqual(CAPTION, (
            "لعبة نينتندو سويتش حصرية.\n\n"
            "- تتطلب آيفون 16 فما فوق.\n"
            "- تتطلب إصدار ios26 فما فوق.\n"
            "- قد تحتوي تحميل داخلي."
        ))
        self.assertEqual(USER_TAG, "@iKiraPlus")

    def test_exact_filename(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "games.json"
            file.write_text(json.dumps({"games": [
                {"name": "My Game", "version": "1.4.2", "url": "https://example.com/example.ipa"}
            ]}), encoding="utf-8")
            game = load_games(file)[0]
            self.assertEqual(game.filename, "My Game - 1.4.2 [ @iKiraPlus ].ipa")
            self.assertEqual(game.icon, "")

    def test_duplicate_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "games.json"
            item = {"name": "Same", "version": "1", "url": "https://example.com/file.ipa"}
            file.write_text(json.dumps({"games": [item, item]}), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                load_games(file)

    def test_empty_manifest_requires_links(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "games.json"
            file.write_text('{"games": []}', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                load_games(file)


if __name__ == "__main__":
    unittest.main()
