"""Cover the optional print command without live network access."""
from contextlib import redirect_stdout, redirect_stderr
import importlib.util
from io import BytesIO, StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
HAS_PDF = importlib.util.find_spec('reportlab') is not None


@unittest.skipUnless(HAS_PDF, 'PDF support is optional')
class DeckGuidePdfTests(unittest.TestCase):
    def test_german_source_has_translated_roles_and_matching_deck_hash(self):
        from harness.rendering.deck_guide_pdf import COPY, combo_lines, read_guide, role_rows

        folder = ROOT / 'decks/tcg/angelechy'
        guide = read_guide(folder, 'de')
        german = COPY['de']
        first, second = combo_lines(guide, german['combos'])
        self.assertEqual([len(first.steps), len(second.steps)], [6, 9])
        self.assertEqual(dict(first.end_board)['Spielfeldzone'], 'Angelechy Endgame Problem')
        self.assertIn('Castellan', dict(second.end_board)['Zauber- und Fallenzonen'])
        self.assertEqual(role_rows(guide, german['roles'])[17782288][0], 'Einstieg und Wiederaufbau')
        with tempfile.TemporaryDirectory() as directory:
            translated = Path(directory)
            (translated / 'guide.de.md').write_text(guide, encoding='utf-8')
            (translated / 'deck.json').write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'needs review'):
                read_guide(translated, 'de')

    def test_combo_parser_accepts_headings_and_bold_playbook_titles(self):
        from harness.rendering.deck_guide_pdf import combo_lines
        guide = """# Example

## Combo lines

**Modern line.** Start with two cards.
1. Activate the first card.
   Keep timing in this step.
2. Resolve the effect.

**Watch for:** Negation.

### Historical line

Inputs: one card.

1. Normal Summon.

## Going first and going second
"""
        modern, historical = list(combo_lines(guide))
        self.assertEqual(modern.title, 'Modern line')
        self.assertEqual(modern.inputs, 'Start with two cards.')
        self.assertEqual(modern.steps, ['Activate the first card. Keep timing in this step.', 'Resolve the effect.'])
        self.assertEqual(modern.notes, ['Watch for: Negation.'])
        self.assertEqual(historical.steps, ['Normal Summon.'])

    def test_cli_embeds_cached_art_and_reports_missing_images(self):
        from PIL import Image
        from harness.cli import main
        from harness.engine.session import load_bundle

        name = 'decks/tcg/angelechy'
        _, deck = load_bundle(ROOT, name)
        jpeg = BytesIO()
        Image.new('RGB', (40, 58), 'purple').save(jpeg, format='JPEG')
        missing_art = 48340269
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            for card_id in deck['cards']:
                if int(card_id) != missing_art:
                    (cache / f'{card_id}.jpg').write_bytes(jpeg.getvalue())
            output = cache / 'test.pdf'
            args = ['yugioh-harness', 'deck-guide-pdf', name, '--repo', str(ROOT),
                    '--art-cache', str(cache), '--output', str(output)]
            errors = StringIO()
            with patch('sys.argv', args), redirect_stdout(StringIO()), redirect_stderr(errors):
                with patch('harness.rendering.deck_guide_pdf.urlopen', side_effect=URLError('offline')) as fetch:
                    main()
            fetch.assert_called_once()
            self.assertTrue(fetch.call_args.args[0].full_url.endswith(f'/{missing_art}.jpg'))
            self.assertIn('YGOPRODeck image unavailable for Angelechy Verdict', errors.getvalue())
            rendered = output.read_bytes()
            self.assertTrue(rendered.startswith(b'%PDF-'))
            self.assertIn(b'/Subtype /Image', rendered)
