import json
import tempfile
import unittest
from pathlib import Path

from upload import CAPTION, USER_TAG, load_games, selected_games


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

    def test_exact_five_games_and_groups(self):
        games = load_games()
        self.assertEqual(
            [(g.name, g.version) for g in games],
            [
                ("Solateria", "1.0.5"),
                ("Ready or Nowhere", "1.0.0-1"),
                ("Mario vs. Donkey Kong", "1.0.1"),
                ("Cult of the Lamb", "1.5.27"),
                ("Super Mario 3D World + Bowser's Fury", "1.2.2"),
            ],
        )
        self.assertEqual(
            [g.name for g in selected_games(games, "first_two")],
            ["Solateria", "Ready or Nowhere"],
        )
        self.assertEqual(
            [g.name for g in selected_games(games, "last_three")],
            ["Mario vs. Donkey Kong", "Cult of the Lamb",
             "Super Mario 3D World + Bowser's Fury"],
        )
        self.assertEqual(
            sorted(g.name for group in ("first_two", "last_three")
                   for g in selected_games(games, group)),
            sorted(g.name for g in games),
        )
        self.assertTrue(all(g.icon.startswith("https://") for g in games))
        self.assertTrue(all(g.filename.endswith(" [ @iKiraPlus ].ipa") for g in games))

    def test_reject_unsupported_batch(self):
        with self.assertRaises(RuntimeError):
            selected_games(load_games(), "all")
        with self.assertRaises(RuntimeError):
            selected_games(load_games()[:2], "first_two")

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
