"""English text layout: normalisation, word wrap and encoding for the game.

The game draws ASCII with its half-width font (fontA, 8 px per character) and
Japanese with the full-width font (16 px). Dialogue boxes hold two lines of
about 24 full-width characters, i.e. ~48 half-width columns. All limits live
here so they can be tuned after testing on hardware/emulator.
"""
import re
import unicodedata

DIALOGUE_WIDTH = 44      # half-width columns per dialogue line
DIALOGUE_LINES = 2       # lines per dialogue page

TAG = re.compile(r'<[^<>]*>')
# Tags that print something (variable text). Their printed width is unknown, so
# we budget a typical width for each.
TAG_WIDTH = {'<PN>': 10, '<UN>': 14, '<UC>': 10, '<GN>': 2, '<NUM>': 4, '<MONEY>': 6,
             '<ITEM>': 14, '<HNUM>': 4, '<HNUM2>': 4, '<HORO>': 12, '<HEXP>': 4}

_REPL = {
    '‘': "'", '’': "'", '“': '"', '”': '"', '—': '-', '–': '-',
    '…': '...', ' ': ' ', '　': ' ', '‐': '-', '‑': '-', '×': 'x',
}
# Full-width symbols the game font has and that read well next to ASCII.
_KEEP = set('♪★☆○●◎◇◆□■△▲▽▼※→←↑↓♂♀〜「」『』【】・')


def normalise(s):
    if s == '　':
        return s                      # deliberate full-width blank (2-byte fields)
    out = []
    for ch in s:
        if ch in _REPL:
            out.append(_REPL[ch])
        elif ord(ch) < 0x80 or ch in _KEEP:
            out.append(ch)
        else:
            try:
                ch.encode('cp932')
                out.append(ch)       # Japanese left on purpose (rare)
            except UnicodeEncodeError:
                d = unicodedata.normalize('NFKD', ch).encode('ascii', 'ignore').decode()
                out.append(d)
    return ''.join(out)


def width(s):
    w = 0
    for part in re.split(r'(<[^<>]*>)', s):
        if TAG.fullmatch(part or 'x'):
            w += TAG_WIDTH.get(part, 0)
        else:
            w += sum(1 if ord(c) < 0x80 or 0xFF61 <= ord(c) <= 0xFF9F else 2 for c in part)
    return w


def _wrap_words(text, w):
    words = text.split(' ')
    lines, cur = [], ''
    for word in words:
        if not word:
            continue
        cand = word if not cur else cur + ' ' + word
        if width(cand) <= w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or ['']


def is_menu(jp):
    """Choice lists such as '話す<n>やめる' keep their line structure."""
    if '<p>' in jp or '<n>' not in jp:
        return False
    lines = jp.split('<n>')
    return all(width(l) <= 24 and not re.search('[。、？！…]', l) for l in lines)


def wrap(en, jp, max_width=DIALOGUE_WIDTH, max_lines=DIALOGUE_LINES, split_pages=True):
    """Re-flow English so no line exceeds max_width and no page exceeds max_lines.

    Pages (<p>) the translator wrote are kept; long pages are split into more
    pages when split_pages is true, otherwise lines are just re-flowed."""
    if is_menu(jp):
        return en
    jp_pages = jp.split('<p>')
    pages_out = []
    for i, page in enumerate(en.split('<p>')):
        lines = page.split('<n>')
        jp_lines = jp_pages[i].count('<n>') + 1 if i < len(jp_pages) else 1
        limit = max(max_lines, jp_lines) if max_lines else 999
        if all(width(l) <= max_width for l in lines) and len(lines) <= limit:
            pages_out.append(page)
            continue
        flat = ' '.join(l.strip() for l in lines)
        wl = _wrap_words(flat, max_width)
        if split_pages and len(wl) > limit:
            for k in range(0, len(wl), limit):
                pages_out.append('<n>'.join(wl[k:k + limit]))
        else:
            pages_out.append('<n>'.join(wl))
    return '<p>'.join(pages_out)


def encode(s):
    return normalise(s).encode('cp932')


def tags_of(s):
    return sorted(t for t in TAG.findall(s) if t not in ('<n>', '<p>'))
