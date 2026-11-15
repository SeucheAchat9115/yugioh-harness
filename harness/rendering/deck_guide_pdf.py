"""Export the deck bundle's existing playbook as a compact, printable A4 PDF."""

from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
from os import environ
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

from PIL import Image as PILImage
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


INK = colors.HexColor('#221C32')
MUTED = colors.HexColor('#514A60')
ACCENT = colors.HexColor('#503475')
LINE = colors.HexColor('#DAD3E5')
PAPER = colors.HexColor('#F3EFF8')
GOLD = colors.HexColor('#966329')
WATCH = colors.HexColor('#FBF3E7')
ART_URL = 'https://images.ygoprodeck.com/images/cards/{card_id}.jpg'
MAX_IMAGE_BYTES = 2_000_000
SECTION_NAMES = ('main', 'extra', 'side')
FONT_DIR = Path(reportlab.__file__).with_name('fonts')
pdfmetrics.registerFont(TTFont('GuideRegular', str(FONT_DIR / 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('GuideBold', str(FONT_DIR / 'VeraBd.ttf')))

STYLES = {
    'title': ParagraphStyle('title', fontName='GuideBold', fontSize=36, leading=38, textColor=INK),
    'heading': ParagraphStyle('heading', fontName='GuideBold', fontSize=23, leading=25, textColor=INK),
    'label': ParagraphStyle('label', fontName='GuideBold', fontSize=8.5, leading=11, textColor=ACCENT),
    'watch': ParagraphStyle('watch', fontName='GuideBold', fontSize=8.5, leading=11, textColor=GOLD),
    'number': ParagraphStyle('number', fontName='GuideBold', fontSize=18, leading=21, textColor=ACCENT),
    'strong': ParagraphStyle('strong', fontName='GuideBold', fontSize=10.5, leading=13, textColor=INK),
    'body': ParagraphStyle('body', fontName='GuideRegular', fontSize=10, leading=14, textColor=INK),
    'small': ParagraphStyle('small', fontName='GuideRegular', fontSize=9, leading=11.5, textColor=MUTED),
    'deck': ParagraphStyle('deck', fontName='GuideRegular', fontSize=9.2, leading=12, textColor=INK),
    'count': ParagraphStyle('count', fontName='GuideBold', fontSize=9.2, leading=12, textColor=ACCENT),
}

COPY = {
    'en': {
        'title': 'Deck Guide', 'key_cards': 'Key cards', 'opening': 'Opening line',
        'unopposed': 'Uninterrupted', 'continued': 'Continued',
        'inputs': 'Starting position', 'result': 'End board', 'watch': 'Watch for',
        'notes': 'Play notes', 'inventory': 'Card inventory', 'deck_list': 'Complete deck list',
        'main': 'Main Deck', 'extra': 'Extra Deck', 'side': 'Side Deck', 'empty': 'Empty',
        'credits': 'Card images: YGOPRODeck  /  Cards © KONAMI',
        'overview': 'Overview', 'roles': 'Card roles and usage', 'combos': 'Combo lines',
        'turn_plan': 'Going first and going second', 'interaction': 'Opponent-turn interaction',
        'side_plan': 'Sideboarding and matchup notes',
    },
    'de': {
        'title': 'Deckguide', 'key_cards': 'Schlüsselkarten', 'opening': 'Eröffnung',
        'unopposed': 'Ohne Unterbrechung', 'continued': 'Fortsetzung',
        'inputs': 'Ausgangslage', 'result': 'Endfeld', 'watch': 'Unterbrechungspunkte',
        'notes': 'Spielhinweise', 'inventory': 'Kartenübersicht', 'deck_list': 'Vollständige Deckliste',
        'main': 'Main Deck', 'extra': 'Extra Deck', 'side': 'Side Deck', 'empty': 'Leer',
        'credits': 'Kartenbilder: YGOPRODeck  /  Karten © KONAMI',
        'overview': 'Überblick', 'roles': 'Kartenrollen', 'combos': 'Eröffnungen',
        'turn_plan': 'Als Erster und als Zweiter', 'interaction': 'Interaktion im gegnerischen Zug',
        'side_plan': 'Side-Deck-Plan',
    },
}


@dataclass
class Combo:
    title: str
    inputs: str
    steps: list[str]
    notes: list[str]
    end_board: list[tuple[str, str]] = field(default_factory=list)


def default_art_cache():
    base = Path(environ.get('XDG_CACHE_HOME') or Path.home() / '.cache')
    return base / 'yugioh-harness' / 'card-images'


def read_guide(folder, language):
    filename = 'guide.md' if language == 'en' else f'guide.{language}.md'
    path = folder / filename
    if not path.is_file():
        raise ValueError(f'{folder.name} has no {language} playbook ({filename})')
    guide = path.read_text(encoding='utf-8')
    digest = sha256((folder / 'deck.json').read_bytes()).hexdigest()
    if f'deck_json_sha256: {digest}' not in guide.splitlines():
        raise ValueError(f'{filename} needs review against the current deck list')
    return guide


def plain(markdown):
    text = re.sub(r'!?\[([^\]]+)\]\([^)]+\)', r'\1', markdown)
    text = text.replace('**', '').replace('`', '')
    text = re.sub(r'[\u2011\u2013\u2014]', '-', text)
    text = text.replace('→', 'to').replace('’', "'").replace('“', '"').replace('”', '"')
    return ' '.join(text.split())


def section(guide, heading):
    match = re.search(rf'^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)', guide, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ''


def combo_lines(guide, heading='Combo lines'):
    text = section(guide, heading)
    # The shared playbook format uses headings. Tournament guides also use bold titles.
    titles = list(re.finditer(r'^(?:### +(.+)|\*\*([^\n]+?)\*\*(?= +Start\b|\s*$))',
                              text, re.MULTILINE))
    for index, title in enumerate(titles):
        end = titles[index + 1].start() if index + 1 < len(titles) else len(text)
        body = text[title.end():end].strip()
        steps = []
        inputs = []
        notes = []
        end_board = []
        for block in re.split(r'\n\s*\n', body):
            numbered = re.split(r'^\s*\d+\. +', block, flags=re.MULTILINE)
            if len(numbered) > 1:
                if numbered[0].strip():
                    inputs.append(plain(numbered[0]))
                steps.extend(plain(step) for step in numbered[1:] if step.strip())
            elif steps:
                lines = block.splitlines()
                if lines[0].startswith(('| Zone or resource |', '| Zone oder Ressource |')):
                    for line in lines[2:]:
                        cells = line.strip('|').split('|')
                        if len(cells) == 2:
                            end_board.append((plain(cells[0]), plain(cells[1])))
                else:
                    notes.append(plain(block))
            elif block:
                inputs.append(plain(block))
        if steps:
            yield Combo(plain(title[1] or title[2]).rstrip('.'), ' '.join(inputs), steps, notes, end_board)


def role_rows(guide, heading):
    roles = {}
    for line in section(guide, heading).splitlines():
        fields = [cell.strip() for cell in line.strip('|').split('|')]
        if len(fields) == 5 and fields[0].isascii() and fields[0].isdigit():
            roles[int(fields[0])] = (plain(fields[3]), plain(fields[4]))
    return roles


class Artwork:
    def __init__(self, directory):
        self.directory = directory
        self.images = {}

    @staticmethod
    def printable_jpeg(data):
        if len(data) > MAX_IMAGE_BYTES:
            return None
        try:
            with PILImage.open(BytesIO(data)) as image:
                if image.format != 'JPEG' or max(image.size) > 2500:
                    return None
                # The largest illustration is 110 points tall. This retains >320 dpi
                # from a full-size image without embedding the entire source JPEG.
                image.thumbnail((500, 500), PILImage.Resampling.LANCZOS)
                optimized = BytesIO()
                image.convert('RGB').save(optimized, format='JPEG', quality=86, optimize=True)
                return optimized.getvalue()
        except (OSError, ValueError, SyntaxError, PILImage.DecompressionBombError):
            return None

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
            if image := self.printable_jpeg(data):
                return image
        except OSError:
            pass
        try:
            request = Request(ART_URL.format(card_id=card_id), headers={'User-Agent': 'yugioh-harness/pdf'})
            with urlopen(request, timeout=4) as response:
                data = response.read(MAX_IMAGE_BYTES + 1)
        except (URLError, OSError):
            return None
        image = self.printable_jpeg(data)
        if image is None:
            return None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            write_atomic(path, data)
        except OSError:
            pass
        return image


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


def cover(deck, overview, key_ids, art, width, copy):
    info = '  /  '.join(str(value) for value in (
        (deck.get('format') or '').upper(), deck.get('banlist'), deck['id']) if value)
    intro = [paragraph(f'YU-GI-OH!  /  {copy["title"].upper()}', 'label'), Spacer(1, 5),
             paragraph(deck['name'], 'title'), Spacer(1, 9), paragraph(info, 'small')]
    if overview:
        intro.extend([Spacer(1, 10), paragraph(overview)])

    count_width = width / 3
    counts = table([[[paragraph(str(len(deck[name])), 'number'), paragraph(copy[name].upper(), 'label')]
                     for name in SECTION_NAMES]], [count_width] * 3)
    counts.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PAPER),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 11), ('LINEAFTER', (0, 0), (-2, 0), 0.6, LINE),
    ]))
    images = [image for card_id in key_ids[:2] if (image := card_picture(art.get(card_id), 75))]
    artwork_width = len(images) * 82
    header = table([[intro, '', table([images], [82] * len(images)) if images else '']],
                   [width - 12 - artwork_width, 12, artwork_width])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PAPER),
        ('BOX', (0, 0), (-1, -1), 0.55, LINE), ('LINEBEFORE', (0, 0), (0, 0), 2, ACCENT),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14), ('LEFTPADDING', (0, 0), (0, 0), 16),
    ]))
    # Keep the summary visible beside the card images, then give the counts their own row.
    return [header, Spacer(1, 7), counts, Spacer(1, 17)]


def key_cards(keys, deck, roles, art, width):
    cards = []
    column = (width - 16) / 2
    for card_id in keys:
        card = deck['cards'][str(card_id)]
        role, use = roles.get(card_id, ('', ''))
        details = [paragraph(card['name'], 'strong')]
        if role:
            details.extend([Spacer(1, 3), paragraph(role, 'label'), Spacer(1, 4), paragraph(use, 'small')])
        image = card_picture(art.get(card_id), 48)
        item = table([[image or '', '', details]], [48, 10, column - 58])
        item.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 8),
                                  ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                                  ('LINEABOVE', (0, 0), (-1, 0), 0.5, LINE)]))
        cards.append(item)
    return table([[cards[i], '', cards[i+1] if i+1 < len(cards) else '']
                  for i in range(0, len(cards), 2)], [column, 16, column])


def callout(label, text, width, background=PAPER):
    warning = background == WATCH
    box = table([[[paragraph(label, 'watch' if warning else 'label'), Spacer(1, 3), paragraph(text)]]], [width])
    box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), background),
        ('LEFTPADDING', (0, 0), (-1, -1), 12), ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LINEBEFORE', (0, 0), (0, 0), 1.6, GOLD if warning else ACCENT),
    ]))
    return box


def combo_page(combo, number, locate, art, width, copy):
    label = f'{copy["opening"].upper()}  /  {number:02d}'
    if combo.end_board:
        label += f'  /  {copy["unopposed"].upper()}'
    story = [paragraph(label, 'label'), Spacer(1, 5),
             paragraph(combo.title, 'heading'), Spacer(1, 16)]
    if combo.inputs:
        story.extend([callout(copy['inputs'].upper(), combo.inputs, width), Spacer(1, 12)])
    image_width = 31 if combo.end_board else 60
    padding = 3 if combo.end_board else 10
    for index, text in enumerate(combo.steps, 1):
        if index == 7 and len(combo.steps) > 7 and combo.end_board:
            story.extend([PageBreak(), paragraph(f'{label}  /  {copy["continued"].upper()}', 'label'),
                          Spacer(1, 5), paragraph(combo.title, 'heading'), Spacer(1, 16)])
        ids = locate(text)[:2 if combo.end_board else 3]
        pictures = [card_picture(art.get(card_id), image_width) for card_id in ids]
        pictures = [image for image in pictures if image is not None]
        strip = table([pictures], [image_width + 5] * len(pictures)) if pictures else ''
        art_width = (image_width + 5) * len(pictures)
        row = table([[paragraph(str(index), 'number'), paragraph(text, 'deck' if combo.end_board else 'body'), '', strip]],
                    [35, width - 47 - art_width, 12, art_width])
        row.setStyle(TableStyle([
            ('TOPPADDING', (0, 0), (-1, -1), padding), ('BOTTOMPADDING', (0, 0), (-1, -1), padding),
            ('BACKGROUND', (0, 0), (0, 0), PAPER),
            ('LEFTPADDING', (0, 0), (0, 0), 10), ('LEFTPADDING', (1, 0), (1, 0), 12),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
            ('VALIGN', (1, 0), (1, 0), 'MIDDLE'),
        ]))
        story.append(row)
    if combo.end_board:
        rows = [[paragraph(copy['result'].upper(), 'label'), '']]
        rows.extend([paragraph(zone, 'label'), paragraph(state, 'small')] for zone, state in combo.end_board)
        board = table(rows, [140, width - 140], repeatRows=1)
        board.setStyle(TableStyle([
            ('SPAN', (0, 0), (-1, 0)), ('BACKGROUND', (0, 0), (-1, 0), PAPER),
            ('LINEBEFORE', (0, 0), (0, -1), 1.5, ACCENT),
            ('LINEBELOW', (0, 0), (-1, -1), 0.35, LINE),
            ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.extend([Spacer(1, 12), board])
    notes = {'result': 'result', 'output': 'result', 'endfeld': 'result',
             'watch for': 'watch', 'failure/fallback': 'watch', 'unterbrechungspunkte': 'watch'}
    for note in combo.notes:
        prefix, _, remainder = note.partition(': ')
        key = notes.get(prefix.lower(), 'notes')
        background = WATCH if key == 'watch' else PAPER
        story.extend([Spacer(1, 10), callout(copy[key].upper(), note if key == 'notes' else remainder, width, background)])
    return story


def deck_rows(deck, name, width, copy):
    title = f'{copy[name].upper()}  /  {len(deck[name])}'
    rows = [[paragraph(title, 'label'), '']]
    for card_id, count in Counter(deck[name]).items():
        rows.append([paragraph(str(count), 'count'), paragraph(deck['cards'][str(card_id)]['name'], 'deck')])
    if len(rows) == 1:
        rows.append(['', paragraph(copy['empty'], 'small')])
    sheet = table(rows, [23, width - 23], repeatRows=1)
    sheet.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)), ('BACKGROUND', (0, 0), (-1, 0), PAPER),
        ('LEFTPADDING', (0, 0), (0, -1), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 6), ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 3), ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ('LINEBELOW', (0, 1), (-1, -1), 0.35, LINE),
    ]))
    return sheet


def export(deck, guide, output, art_cache, *, language='en'):
    """Build the PDF atomically and return the IDs of requested artwork that was unavailable."""
    copy = COPY[language]
    combos = [combo for _, combo in zip(range(2), combo_lines(guide, copy['combos']))]
    roles = role_rows(guide, copy['roles'])
    ids = list(dict.fromkeys(card_id for name in SECTION_NAMES for card_id in deck[name]))
    locate = card_references(deck, ids)
    art = Artwork(art_cache)
    combo_texts = [combo.title for combo in combos] + [
        target for combo in combos for target in (combo.inputs, *combo.steps)
    ]
    key_ids = list(dict.fromkeys(card_id for target in combo_texts for card_id in locate(target)))
    key_ids = list(dict.fromkeys(key_ids + [card_id for card_id in roles if card_id in ids] + ids))[:6]
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=38, rightMargin=38, topMargin=49, bottomMargin=49,
                            title=f'{deck["name"]} | {copy["title"]}', author='Yu-Gi-Oh! Harness')
    width = doc.width - 12
    overview = plain(section(guide, copy['overview']))
    overview = re.sub(r'^\d+ Main / \d+ Extra / \d+ Side\.\s*(?:YDK\s*[·|]?\s*Gameplay data\s*[·|]?\s*(?:Event list\.?)?\s*)?', '', overview)
    story = cover(deck, overview, key_ids, art, width, copy)
    if key_ids:
        story.extend([paragraph(copy['key_cards'], 'heading'), Spacer(1, 6),
                      key_cards(key_ids, deck, roles, art, width), Spacer(1, 12)])
    turn_plan = plain(section(guide, copy['turn_plan']))
    if turn_plan and not combos:
        story.append(callout(copy['turn_plan'].upper(), turn_plan, width))
    turn_plan_after = len(combos) if any(combo.end_board for combo in combos) else 1
    for number, combo in enumerate(combos, 1):
        story.extend([PageBreak(), *combo_page(combo, number, locate, art, width, copy)])
        if number == turn_plan_after and turn_plan:
            story.extend([Spacer(1, 13), paragraph(copy['turn_plan'].upper(), 'label'),
                          Spacer(1, 4), paragraph(turn_plan, 'small')])

    story.extend([PageBreak(), paragraph(copy['inventory'].upper(), 'label'), Spacer(1, 5),
                  paragraph(copy['deck_list'], 'heading'), Spacer(1, 16)])
    # Main can span a page independently for larger format-specific lists.
    main_width = width * 0.53
    other_width = width - main_width - 15
    main = deck_rows(deck, 'main', main_width, copy)
    supplemental = [deck_rows(deck, 'extra', other_width, copy), Spacer(1, 15), deck_rows(deck, 'side', other_width, copy)]
    columns = table([[main, '', supplemental]], [main_width, 15, other_width])
    if columns.wrap(width, doc.height)[1] < doc.height - 75:
        story.append(columns)
    else:
        story.extend([main, Spacer(1, 15), *supplemental])
    for heading in (copy['interaction'], copy['side_plan']):
        text = plain(section(guide, heading))
        if text:
            story.extend([Spacer(1, 12), callout(heading.upper(), text, width)])
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
        canvas.setFont('GuideRegular', 8)
        canvas.drawString(left, 24, f'{deck["name"]}  /  {copy["title"]}')
        canvas.setFont('GuideRegular', 7)
        canvas.drawCentredString(A4[0] / 2, 24, copy['credits'])
        canvas.setFont('GuideBold', 8)
        canvas.setFillColor(ACCENT)
        canvas.drawRightString(right, 24, f'{document.page:02d}')

    doc.build(story, onFirstPage=page_decorations, onLaterPages=page_decorations)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(output, buffer.getvalue())
    return [card_id for card_id, data in art.images.items() if data is None]
