"""Export the deck bundle's existing playbook as a compact, printable A4 PDF."""

from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from os import environ
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


INK = colors.HexColor('#22242B')
MUTED = colors.HexColor('#50545F')
ACCENT = colors.HexColor('#4D3466')
LINE = colors.HexColor('#D7D3DC')
PAPER = colors.HexColor('#F5F3F7')
WATCH = colors.HexColor('#F6F1E9')
ART_URL = 'https://images.ygoprodeck.com/images/cards/{card_id}.jpg'
MAX_IMAGE_BYTES = 2_000_000
SECTION_NAMES = ('main', 'extra', 'side')

STYLES = {
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=32, leading=35, textColor=INK),
    'heading': ParagraphStyle('heading', fontName='Helvetica-Bold', fontSize=21, leading=24, textColor=INK),
    'label': ParagraphStyle('label', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=ACCENT),
    'strong': ParagraphStyle('strong', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=INK),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10, leading=14, textColor=INK),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=9, leading=12, textColor=MUTED),
    'deck': ParagraphStyle('deck', fontName='Helvetica', fontSize=8.8, leading=11, textColor=INK),
}


@dataclass
class Combo:
    title: str
    inputs: str
    steps: list[str]
    notes: list[str]


def default_art_cache():
    base = Path(environ.get('XDG_CACHE_HOME') or Path.home() / '.cache')
    return base / 'yugioh-harness' / 'card-images'


def plain(markdown):
    text = re.sub(r'!?\[([^\]]+)\]\([^)]+\)', r'\1', markdown)
    text = text.replace('**', '').replace('`', '')
    text = re.sub(r'[\u2011\u2013\u2014]', '-', text)
    text = text.replace('→', 'to').replace('’', "'").replace('“', '"').replace('”', '"')
    return ' '.join(text.split())


def section(guide, heading):
    match = re.search(rf'^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)', guide, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ''


def combo_lines(guide):
    text = section(guide, 'Combo lines')
    # The shared playbook format uses headings. Tournament guides also use bold titles.
    titles = list(re.finditer(r'^(?:### +(.+)|\*\*([^\n]+?)\*\*(?= +Start\b|\s*$))',
                              text, re.MULTILINE))
    for index, title in enumerate(titles):
        end = titles[index + 1].start() if index + 1 < len(titles) else len(text)
        body = text[title.end():end].strip()
        steps = []
        inputs = []
        notes = []
        for block in re.split(r'\n\s*\n', body):
            numbered = re.split(r'^\s*\d+\. +', block, flags=re.MULTILINE)
            if len(numbered) > 1:
                if numbered[0].strip():
                    inputs.append(plain(numbered[0]))
                steps.extend(plain(step) for step in numbered[1:] if step.strip())
            elif steps:
                notes.append(plain(block))
            elif block:
                inputs.append(plain(block))
        if steps:
            yield Combo(plain(title[1] or title[2]).rstrip('.'), ' '.join(inputs), steps, notes)


def role_rows(guide):
    roles = {}
    for line in section(guide, 'Card roles and usage').splitlines():
        fields = [cell.strip() for cell in line.strip('|').split('|')]
        if len(fields) == 5 and fields[0].isascii() and fields[0].isdigit():
            roles[int(fields[0])] = (plain(fields[3]), plain(fields[4]))
    return roles


class Artwork:
    def __init__(self, directory):
        self.directory = directory
        self.images = {}

    @staticmethod
    def valid_jpeg(data):
        if len(data) > MAX_IMAGE_BYTES:
            return False
        try:
            with PILImage.open(BytesIO(data)) as image:
                if image.format != 'JPEG' or max(image.size) > 2500:
                    return False
                image.verify()
                return True
        except (OSError, ValueError, SyntaxError, PILImage.DecompressionBombError):
            return False

    def get(self, card_id):
        if type(card_id) is not int or not 0 < card_id <= 999999999:
            return None
        if card_id not in self.images:
            self.images[card_id] = self.load(card_id)
        return self.images[card_id]

    def load(self, card_id):
        path = self.directory / f'{card_id}.jpg'
        try:
            with path.open('rb') as source:
                data = source.read(MAX_IMAGE_BYTES + 1)
            if self.valid_jpeg(data):
                return data
        except OSError:
            pass
        try:
            request = Request(ART_URL.format(card_id=card_id), headers={'User-Agent': 'yugioh-harness/pdf'})
            with urlopen(request, timeout=4) as response:
                data = response.read(MAX_IMAGE_BYTES + 1)
        except (URLError, OSError):
            return None
        if not self.valid_jpeg(data):
            return None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            write_atomic(path, data)
        except OSError:
            pass
        return data


def write_atomic(path, data):
    with NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        temporary = Path(temp.name)
        try:
            temp.write(data)
            temp.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def paragraph(text, style='body'):
    return Paragraph(escape(text), STYLES[style])


def table(rows, widths, **kwargs):
    result = Table(rows, colWidths=widths, hAlign='LEFT', **kwargs)
    result.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return result


def card_references(deck, card_ids):
    names = {plain(deck['cards'][str(card_id)]['name']): card_id for card_id in card_ids}
    prefixes = Counter(name.split()[0] for name in names)
    aliases = {}
    for name, card_id in names.items():
        prefix, _, suffix = name.partition(' ')
        if suffix and prefixes[prefix] > 1:
            aliases.setdefault(suffix, set()).add(card_id)
    names.update({alias: next(iter(ids)) for alias, ids in aliases.items()
                  if len(ids) == 1 and alias not in names})
    if not names:
        return lambda _text: []
    pattern = re.compile(r'(?<!\w)(?:' + '|'.join(map(re.escape, sorted(names, key=len, reverse=True))) + r')(?!\w)')
    return lambda text: list(dict.fromkeys(names[match[0]] for match in pattern.finditer(text)))


def card_picture(data, width):
    if data is None:
        return None
    return Image(BytesIO(data), width=width, height=width * 1.46, kind='proportional')


def key_cards(keys, deck, roles, art, width):
    cards = []
    column = (width - 16) / 2
    for card_id in keys:
        card = deck['cards'][str(card_id)]
        role, use = roles.get(card_id, ('', ''))
        details = [paragraph(card['name'], 'strong')]
        if role:
            details.extend([Spacer(1, 3), paragraph(role, 'label'), Spacer(1, 4), paragraph(use, 'small')])
        image = card_picture(art.get(card_id), 50)
        item = table([[image or '', '', details]], [50, 9, column - 59])
        item.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 8),
                                  ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                                  ('LINEABOVE', (0, 0), (-1, 0), 0.5, LINE)]))
        cards.append(item)
    return table([[cards[i], '', cards[i+1] if i+1 < len(cards) else '']
                  for i in range(0, len(cards), 2)], [column, 16, column])


def callout(label, text, width, background=PAPER):
    box = table([[[paragraph(label, 'label'), paragraph(text)]]], [width])
    box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), background),
        ('LEFTPADDING', (0, 0), (-1, -1), 12), ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    return box


def combo_page(combo, number, locate, art, width):
    story = [paragraph(f'OPENING LINE {number}', 'label'), Spacer(1, 4),
             paragraph(combo.title, 'heading'), Spacer(1, 14)]
    if combo.inputs:
        story.extend([callout('STARTING POSITION', combo.inputs, width), Spacer(1, 10)])
    for index, text in enumerate(combo.steps, 1):
        ids = locate(text)[:3]
        pictures = [card_picture(art.get(card_id), 52) for card_id in ids]
        pictures = [image for image in pictures if image is not None]
        strip = table([pictures], [56] * len(pictures)) if pictures else ''
        art_width = 56 * len(pictures)
        row = table([[paragraph(f'{index:02d}', 'label'), paragraph(text), '', strip]],
                    [27, width - 39 - art_width, 12, art_width])
        row.setStyle(TableStyle([
            ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
        ]))
        story.append(row)
    labels = {'result': 'RESULT', 'output': 'RESULT', 'watch for': 'WATCH FOR', 'failure/fallback': 'WATCH FOR'}
    for note in combo.notes:
        prefix, _, remainder = note.partition(': ')
        label = labels.get(prefix.lower())
        background = WATCH if label == 'WATCH FOR' else PAPER
        story.extend([Spacer(1, 9), callout(label or 'PLAY NOTES', remainder if label else note, width, background)])
    return story


def deck_rows(deck, name, width):
    title = f'{name.upper()} DECK  /  {len(deck[name])}'
    rows = [[paragraph(title, 'label'), '']]
    for card_id, count in Counter(deck[name]).items():
        rows.append([paragraph(str(count), 'deck'), paragraph(deck['cards'][str(card_id)]['name'], 'deck')])
    if len(rows) == 1:
        rows.append(['', paragraph('Empty', 'small')])
    sheet = table(rows, [23, width - 23], repeatRows=1)
    sheet.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)), ('BACKGROUND', (0, 0), (-1, 0), PAPER),
        ('LEFTPADDING', (0, 0), (0, -1), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 6), ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 3), ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ('LINEBELOW', (0, 1), (-1, -1), 0.35, LINE),
    ]))
    return sheet


def export(deck, guide, output, art_cache):
    """Build the PDF atomically and return the IDs of requested artwork that was unavailable."""
    combos = [combo for _, combo in zip(range(2), combo_lines(guide))]
    roles = role_rows(guide)
    ids = list(dict.fromkeys(card_id for name in SECTION_NAMES for card_id in deck[name]))
    locate = card_references(deck, ids)
    art = Artwork(art_cache)
    key_ids = list(dict.fromkeys(card_id for combo in combos for target in
                                 [combo.title, combo.inputs, *combo.steps] for card_id in locate(target)))
    key_ids = list(dict.fromkeys(key_ids + [card_id for card_id in roles if card_id in ids] + ids))[:6]
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=38, rightMargin=38, topMargin=49, bottomMargin=49,
                            title=f'{deck["name"]} | Deck Guide', author='Yu-Gi-Oh! Harness')
    width = doc.width - 12
    header = '  /  '.join(str(value) for value in (deck.get('format', '').upper() if deck.get('format') else None,
                                                   deck.get('banlist'), deck['id']) if value)
    overview = plain(section(guide, 'Overview'))
    overview = re.sub(r'^\d+ Main / \d+ Extra / \d+ Side\.\s*(?:YDK\s*[·|]?\s*Gameplay data\s*[·|]?\s*(?:Event list\.?)?\s*)?', '', overview)
    story = [paragraph('YU-GI-OH!  /  DECK GUIDE', 'label'), Spacer(1, 5), paragraph(deck['name'], 'title'),
             Spacer(1, 6), paragraph(header, 'small'), Spacer(1, 14)]
    if overview:
        story.extend([paragraph(overview), Spacer(1, 14)])
    if key_ids:
        story.extend([paragraph('KEY CARDS', 'label'), Spacer(1, 3), key_cards(key_ids, deck, roles, art, width), Spacer(1, 12)])
    for heading in ('Going first and going second', 'Opponent-turn interaction'):
        text = plain(section(guide, heading))
        if text:
            story.extend([callout(heading.upper(), text, width), Spacer(1, 9)])
    for number, combo in enumerate(combos, 1):
        story.extend([PageBreak(), *combo_page(combo, number, locate, art, width)])

    story.extend([PageBreak(), paragraph('CARD INVENTORY', 'label'), Spacer(1, 4),
                  paragraph('Complete deck list', 'heading'), Spacer(1, 14)])
    # Main can span a page independently for larger format-specific lists.
    main_width = width * 0.53
    other_width = width - main_width - 15
    main = deck_rows(deck, 'main', main_width)
    supplemental = [deck_rows(deck, 'extra', other_width), Spacer(1, 15), deck_rows(deck, 'side', other_width)]
    columns = table([[main, '', supplemental]], [main_width, 15, other_width])
    if columns.wrap(width, doc.height)[1] < doc.height - 75:
        story.append(columns)
    else:
        story.extend([main, Spacer(1, 15), *supplemental])
    sideboard = plain(section(guide, 'Sideboarding and matchup notes'))
    if sideboard:
        story.extend([Spacer(1, 13), callout('SIDE DECK NOTES', sideboard, width)])
    story.extend([Spacer(1, 10), paragraph('Source: the bundled guide.md and deck.json. Card images: YGOPRODeck. Cards © KONAMI.', 'small')])

    def page_decorations(canvas, document):
        left = document.leftMargin + 6
        right = A4[0] - left
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1.25)
        canvas.line(left, A4[1] - 38, right, A4[1] - 38)
        canvas.setLineWidth(0.45)
        canvas.setStrokeColor(LINE)
        canvas.line(left, 37, right, 37)
        canvas.setFillColor(MUTED)
        canvas.setFont('Helvetica', 8)
        canvas.drawString(left, 24, f'{deck["name"]}  /  Deck guide')
        canvas.drawRightString(right, 24, str(document.page))

    doc.build(story, onFirstPage=page_decorations, onLaterPages=page_decorations)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(output, buffer.getvalue())
    return [card_id for card_id, data in art.images.items() if data is None]
