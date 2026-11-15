"""Decide how an English string is laid out for a given container/entry."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout
import formats

ID_PREFIX = re.compile(r'^([a-z]\d{3})(?=[^\x00-\x7f])')
PRINTF = re.compile(r'%[-+ 0#]*\d*(?:\.\d+)?[diouxXcsfeEgG%]')

# Text windows that are smaller than the dialogue box (script data tables).
# (script name regex, half-width columns, lines). Measured from the Japanese
# (full lines of 20/15/14 full-width characters) and the daily-luck window.
# The engine wraps over-long lines itself, by bytes, cutting words in half,
# so English must be broken by the patch to these widths.
EXT_BOXES = [
    (r'(fukufuku|chiyo|copitan[234]|marian|matsu)$', 40, 7),   # daily-luck readings
    (r'amesyo$', 40, 8),                                        # personality type readings
    (r'gk\d\d$', 30, 7),                                        # Skull Number readings
    (r'jill$', 28, 8),                                          # Jill's advice
]


def ext_box(meta, jp):
    """(width, lines) of the window an scb data-table text is shown in, or None."""
    name = os.path.splitext(os.path.basename(meta.get('source', '')))[0].lower()
    if '<p>' in jp:
        return None                    # paged text is dialogue, not a reading
    long_text = jp.count('<n>') >= 4 or ('<n>' not in jp.rstrip('<n>') and layout.width(jp) > 60)
    for rx, w, n in EXT_BOXES:
        if re.match(rx, name) and long_text:
            return w, max(n, len(jp.rstrip('<n>').split('<n>')) if '<n>' in jp.rstrip('<n>') else n)
    return None


def table_lines(key, jp):
    """Line limit of an unpaged multi-line text in a script data table: the
    window was sized for the Japanese, so no more lines than it had (min 2)."""
    if key.startswith('#') or int(key, 16) < formats.SCB_EXT_BASE or '<p>' in jp or '<n>' not in jp:
        return None
    return max(2, len(jp.split('<n>')))


# Record files (size-prefixed texts): (path regex, columns, lines, bullets).
# Lines = the most the Japanese ever uses (engine wrapping included); the
# newspaper's items each start on a new line with a ■.
REC_BOXES = [
    (r'newsppr/', 42, 8, True),
    (r'bottmail/teikei', 38, 5, False),
    (r'misctext/kakugen', 42, 6, False),
    (r'misctext/uso_data', 40, 2, False),
    (r'unchiku/unchiku', 50, 7, False),
]
BULLET = re.compile(r'^\s*[-*■・]\s*')


def rec_box(meta):
    src = meta.get('source', '').replace(os.sep, '/').lower()
    for rx, w, n, bullets in REC_BOXES:
        if re.search(rx, src):
            return w, n, bullets
    return None


def window(fmt, meta, key, jp):
    """(columns, lines) of the window a text must fit, or None if unknown."""
    if fmt == 'rec':
        box = rec_box(meta)
        return box[:2] if box else None
    if fmt == 'scb' and not key.startswith('#') and int(key, 16) >= formats.SCB_EXT_BASE:
        box = ext_box(meta, jp)
        if box:
            return box
        if table_lines(key, jp):
            return layout.DIALOGUE_WIDTH, table_lines(key, jp)
    return None


def wrap_box(en, w, n, bullets):
    out = []
    for page in en.split('<p>'):
        lines = [l.strip() for l in page.split('<n>')]
        if bullets:
            items = []
            for l in lines:
                if BULLET.match(l) or not items:
                    items.append(BULLET.sub('', l))
                elif l:
                    items[-1] += ' ' + l
            res = []
            for it in items:
                res += layout._wrap_words('■' + it, w)
        else:
            res = [x for l in lines for x in layout._wrap_words(l, w)]
            if len(res) > n:                       # translator's breaks cost lines
                res = layout._wrap_words(' '.join(l for l in lines if l), w)
        out.append('<n>'.join(res))
    return '<p>'.join(out)


# Executable labels that the game measures to place something after them
# (location name + area number in the top bar). The game counts a space as
# half a character but draws it full width, so the number overlaps the name;
# one trailing space per inner space restores the measured width.
SPACE_PAD = [(0x21C000, 0x21F800)]


def page_lines(s):
    return [len(pg.split('<n>')) for pg in s.split('<p>')]


def render(en, jp, fmt, key, meta):
    """Return the final string (still text) that will be written to the game."""
    en = layout.normalise(en)
    if en.strip():
        en = en.strip()              # (a lone space is a deliberate translation)
    # Item/object records start with an internal id ("i001", "o312", "b005")
    # that the game strips before display; make sure it is always kept.
    m = ID_PREFIX.match(jp)
    if m and not en.startswith(m.group(1)):
        en = m.group(1) + en
    if fmt == 'elf' and any(a <= int(key, 16) < b for a, b in SPACE_PAD) and '<n>' not in en:
        return en + ' ' * en.count(' ')
    if fmt == 'scb' and not key.startswith('#') and int(key, 16) < formats.SCB_EXT_BASE:
        return layout.wrap(en, jp, layout.DIALOGUE_WIDTH, layout.DIALOGUE_LINES, True)
    if fmt == 'scb' and not key.startswith('#'):
        box = ext_box(meta, jp)
        if box:
            # flatten and re-break at word boundaries (trailing <n> padding of
            # the Japanese is dropped: it would only push text out of the box)
            flat = ' '.join(l.strip() for l in re.split('<n>', en) if l.strip())
            return '<p>'.join('<n>'.join(layout._wrap_words(pg.strip(), box[0])) for pg in flat.split('<p>'))
        if '<p>' in jp:
            # paged text in a data table is dialogue: same 2-line box as the
            # message slots, so split long pages the same way
            return layout.wrap(en, jp, layout.DIALOGUE_WIDTH, layout.DIALOGUE_LINES, True)
    if fmt == 'rec' and rec_box(meta):
        return wrap_box(en, *rec_box(meta))
    if '<n>' not in jp and '<p>' not in jp:
        return en                      # the engine wraps (or it is a label)
    w = int(meta.get('width', 40)) if fmt == 'rec' else layout.DIALOGUE_WIDTH
    if fmt == 'elf':
        w = max(20, max(layout.width(l) for l in re.split('<n>|<p>', jp)))
        w = max(w, 36)
    return layout.wrap(en, jp, w, 0, False)


def check(en, jp, fmt, key, meta, cap):
    """Validate a translation. Returns (rendered_bytes, error or None)."""
    if not en:
        return None, 'empty'
    out = render(en, jp, fmt, key, meta)
    try:
        b = out.encode('cp932')
    except UnicodeEncodeError as e:
        return None, 'unencodable character %r' % out[e.start]
    if layout.tags_of(en) != layout.tags_of(jp):
        return None, 'tags must be exactly %s (got %s)' % (layout.tags_of(jp), layout.tags_of(en))
    if sorted(PRINTF.findall(en)) != sorted(PRINTF.findall(jp)):
        return None, 'printf codes must be exactly %s' % sorted(PRINTF.findall(jp))
    if layout.is_menu(jp) and en.count('<n>') != jp.count('<n>'):
        return None, 'menu must have exactly %d items separated by <n>' % (jp.count('<n>') + 1)
    win = window(fmt, meta, key, jp)
    if win and max(page_lines(out)) > win[1]:
        return None, 'too long for its window: %d lines of %d characters, the window holds %d - shorten' % (
            max(page_lines(out)), win[0], win[1])
    if cap and len(b) > cap:
        return None, 'too long: %d bytes after layout, limit %d - shorten' % (len(b), cap)
    return b, None
