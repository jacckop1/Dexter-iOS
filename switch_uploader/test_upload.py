import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from upload import CAPTION, USER_TAG, load_games, selected_games, send_game_document


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

    def test_exact_five_pending_games_and_groups(self):
        games = load_games()
        self.assertEqual(
            [(g.name, g.version) for g in games],
            [
                ("Ready or Nowhere", "1.0.0"),
                ("Air Strike Command Tactical Assault Operation", "1.0.0"),
                ("Mario vs. Donkey Kong", "1.0.1"),
                ("Cult of the Lamb", "1.5.27"),
                ("Super Mario 3D World + Bowser's Fury", "1.2.2"),
            ],
        )
        self.assertEqual(
            [g.name for g in selected_games(games, "first_two")],
            ["Ready or Nowhere", "Air Strike Command Tactical Assault Operation"],
        )
        self.assertEqual(
            [g.name for g in selected_games(games, "last_three")],
            ["Mario vs. Donkey Kong", "Cult of the Lamb",
             "Super Mario 3D World + Bowser's Fury"],
        )
        self.assertEqual(
            [g.name for batch in ("first_two", "last_three")
             for g in selected_games(games, batch)],
            [g.name for g in games],
        )
        self.assertEqual(
            [g.url.split("/")[2] for g in games],
            ["noord-store.com", "noord-store.com",
             "ipasoon.icu", "ipasoon.icu", "ipasoon.icu"],
        )
        self.assertTrue(all(g.filename.endswith(" [ @iKiraPlus ].ipa") for g in games))
        self.assertTrue(all(g.icon.startswith("https://") for g in games if g.icon))
        self.assertEqual(games[1].icon, "")

    def test_reject_unsupported_batch(self):
        games = load_games()
        for name in ("all", "remaining_four", "solateria", "ready_or_nowhere"):
            with self.subTest(name=name):
                with self.assertRaises(RuntimeError):
                    selected_games(games, name)
        with self.assertRaises(RuntimeError):
            selected_games(games[:4], "first_two")

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


class NoThumbnailTests(unittest.IsolatedAsyncioTestCase):
    async def test_deliver_ipa_without_custom_thumb_or_icon_request(self):
        client = MagicMock()
        client.send_file = AsyncMock(return_value=object())
        file = object()
        name = "Air Strike Command Tactical Assault Operation - 1.0.0 [ @iKiraPlus ].ipa"
        result = await send_game_document(client, file, name)
        self.assertIsNotNone(result)
        args, kwargs = client.send_file.await_args
        self.assertEqual(args, ("me", file))
        self.assertNotIn("thumb", kwargs)
        self.assertTrue(kwargs["force_document"])
        self.assertEqual(kwargs["caption"], CAPTION)
        self.assertEqual(kwargs["attributes"][0].file_name, name)


if __name__ == "__main__":
    unittest.main()
