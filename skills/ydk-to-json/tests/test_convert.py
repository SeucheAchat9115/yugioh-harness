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
    def test_order_full_records_and_existing_metadata_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deck.ydk"
            raw = b"#created by Author - https://cardcluster.com/deck/abc\r\n#main\r\n001\r\n2\r\n1\r\n#extra\r\n2\r\n!side\r\n1\r\n"
            path.write_bytes(raw)
            path.with_suffix(".json").write_text(json.dumps({"id": "stable-v1", "source": {"provided_by": "user"}}))
            records = {i: {"id": i, "name": f"Card {i}", "desc": "Text", "type": "Spell Card",
                           "misc_info": [{"future_field": [1, 2]}], "card_prices": [{"price": "1.00"}]}
                       for i in (1, 2)}
            with patch.object(converter, "fetch_all", return_value=records):
                converter.convert([path])
            deck = json.loads(path.with_suffix(".json").read_text())
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(deck["main"], [1, 2, 1])
            self.assertEqual(deck["counts"], {"main": 3, "extra": 1, "side": 1})
            self.assertEqual(deck["cards"]["1"], records[1])
            self.assertEqual(deck["id"], "stable-v1")
            self.assertEqual(deck["source"]["url"], "https://cardcluster.com/deck/abc")

    def test_alternate_art_id_keeps_original_api_object(self):
        card = {"id": 1, "name": "Name", "type": "Effect Monster", "desc": "Text",
                "card_images": [{"id": 99, "image_url": "https://example.test/99.jpg"}]}
        self.assertEqual(converter.match_records([99], [card]), {99: card})

    def test_missing_card_does_not_overwrite_any_deck(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / f"{i}.ydk" for i in (1, 2)]
            for i, path in enumerate(paths, 1):
                path.write_text(f"#main\n{i}\n")
                path.with_suffix(".json").write_text('{"keep": true}')
            with patch.object(converter, "fetch_all", return_value={1: {"id": 1}}):
                with self.assertRaisesRegex(ValueError, "incomplete card coverage"):
                    converter.convert(paths)
            for path in paths:
                self.assertEqual(path.with_suffix(".json").read_text(), '{"keep": true}')

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
