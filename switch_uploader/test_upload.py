import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from upload import CAPTION, USER_TAG, load_games, selected_games, thumbnail_safely


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
                ("Ready or Nowhere", "1.0.0"),
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
        self.assertEqual(
            [g.url.split("/")[2] for g in games],
            ["noord-store.com", "noord-store.com", "ipasoon.icu", "ipasoon.icu", "ipasoon.icu"]
        )
        self.assertTrue(all(g.filename.endswith(" [ @iKiraPlus ].ipa") for g in games))

    def test_single_game_retries_do_not_reupload_other_games(self):
        games = load_games()
        expected = {
            "solateria": "Solateria",
            "ready_or_nowhere": "Ready or Nowhere",
            "mario_vs_donkey_kong": "Mario vs. Donkey Kong",
            "cult_of_the_lamb": "Cult of the Lamb",
            "super_mario_3d_world": "Super Mario 3D World + Bowser's Fury",
        }
        for selection, name in expected.items():
            with self.subTest(selection=selection):
                chosen = selected_games(games, selection)
                self.assertEqual(len(chosen), 1)
                self.assertEqual(chosen[0].name, name)

    def test_icon_429_retry_then_skip_without_failing_game(self):
        response = requests.Response()
        response.status_code = 429
        error = requests.HTTPError("HTTP 429")
        error.response = response
        with patch("upload.thumbnail", side_effect=error) as icon:
            with patch("upload.time.sleep") as wait:
                fallback = thumbnail_safely(
                    requests.Session(), "https://example.org/icon.png",
                    Path("/tmp/not-used-thumbnail.jpg"), "test-icon"
                )
        self.assertIsNone(fallback)
        self.assertEqual(icon.call_count, 3)
        self.assertEqual(wait.call_count, 2)

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
