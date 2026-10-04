import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert.py"
spec = importlib.util.spec_from_file_location("ydk_convert", SCRIPT)
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)


class ConverterTests(unittest.TestCase):
    def test_order_gameplay_fields_and_deck_identity_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deck.ydk"
            raw = b"#created by Author - https://example.com/deck/abc\r\n#main\r\n001\r\n2\r\n1\r\n#extra\r\n2\r\n!side\r\n1\r\n"
            path.write_bytes(raw)
            path.with_suffix(".json").write_text(json.dumps({"id": "stable-v1", "source": {"provided_by": "user"}}))
            records = {i: {"id": i, "name": f"Card {i}", "desc": "Text", "type": "Spell Card", "race": "Normal",
                           "misc_info": [{"future_field": [1, 2]}], "card_prices": [{"price": "1.00"}]}
                       for i in (1, 2)}
            with patch.object(converter, "fetch_all", return_value=records):
                converter.convert([path])
            deck = json.loads(path.with_suffix(".json").read_text())
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(deck["main"], [1, 2, 1])
            self.assertEqual(deck["counts"], {"main": 3, "extra": 1, "side": 1})
            self.assertEqual(deck["cards"]["1"], converter.gameplay_card(records[1]))
            self.assertNotIn("misc_info", deck["cards"]["1"])
            self.assertNotIn("card_prices", deck["cards"]["1"])
            self.assertNotIn("source", deck)
            self.assertNotIn("card_data_source", deck)
            self.assertEqual(deck["id"], "stable-v1")
            self.assertEqual(deck["schema_version"], "2.0")

    def test_folder_name_and_generic_output_without_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "my-deck"
            folder.mkdir()
            path = folder / "deck.ydk"
            path.write_text("#main\n1\n")
            record = {"id": 1, "name": "Spell", "type": "Spell Card", "race": "Normal", "desc": "Text"}
            with patch.object(converter, "fetch_all", return_value={1: record}):
                converter.convert([path])
            deck = json.loads((folder / "deck.json").read_text())
            self.assertEqual(deck["id"], "my-deck")
            self.assertEqual(deck["name"], "My Deck")
            self.assertEqual({f.name for f in folder.iterdir()}, {"deck.ydk", "deck.json"})

    def test_alternate_art_id_keeps_original_api_object(self):
        card = {"id": 1, "name": "Name", "type": "Effect Monster", "desc": "Text",
                "card_images": [{"id": 99, "image_url": "https://example.test/99.jpg"}]}
        self.assertEqual(converter.match_records([99], [card]), {99: card})

    def test_missing_card_does_not_overwrite_any_deck(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / f"deck-{i}" / "deck.ydk" for i in (1, 2)]
            for path in paths:
                path.parent.mkdir()
            for i, path in enumerate(paths, 1):
                path.write_text(f"#main\n{i}\n")
                path.with_suffix(".json").write_text('{"keep": true}')
            with patch.object(converter, "fetch_all", return_value={1: {"id": 1, "name": "Card 1", "type": "Spell Card", "race": "Normal", "desc": "Text"}}):
                with self.assertRaisesRegex(ValueError, "incomplete card coverage"):
                    converter.convert(paths)
            for path in paths:
                self.assertEqual(path.with_suffix(".json").read_text(), '{"keep": true}')

    def test_monster_stats_pendulum_and_link_details_survive(self):
        monster = {"id": 1, "name": "Monster", "type": "Pendulum Effect Monster",
                   "race": "Dragon", "desc": "Full text", "atk": 2500, "def": 2000,
                   "level": 7, "attribute": "LIGHT", "scale": 8,
                   "pend_desc": "Pendulum effect", "monster_desc": "Monster effect",
                   "card_sets": [], "ygoprodeck_url": "https://example.test"}
        projected = converter.gameplay_card(monster)
        for field in ("atk", "def", "level", "attribute", "scale", "pend_desc", "monster_desc"):
            self.assertEqual(projected[field], monster[field])
        self.assertNotIn("card_sets", projected)
        self.assertNotIn("ygoprodeck_url", projected)
        link = {"id": 2, "name": "Link", "type": "Link Monster", "race": "Dragon",
                "desc": "Materials and effect", "atk": 2000, "attribute": "DARK",
                "linkval": 2, "linkmarkers": ["Bottom-Left", "Bottom-Right"]}
        self.assertEqual(converter.gameplay_card(link), link)
        with self.assertRaisesRegex(ValueError, "Missing gameplay stats"):
            converter.gameplay_card({key: value for key, value in monster.items() if key != "atk"})

    def test_invalid_ydk_fails_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.ydk"
            path.write_text("#main\n123\nnot-a-card\n")
            with patch.object(converter, "fetch_all") as fetch:
                with self.assertRaisesRegex(ValueError, "invalid card ID"):
                    converter.convert([path])
                fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
