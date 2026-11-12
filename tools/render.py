"""Decide how an English string is laid out for a given container/entry."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout
import formats

ID_PREFIX = re.compile(r'^([a-z]\d{3})(?=[^\x00-\x7f])')
PRINTF = re.compile(r'%[-+ 0#]*\d*(?:\.\d+)?[diouxXcsfeEgG%]')


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
    if fmt == 'scb' and not key.startswith('#') and int(key, 16) < formats.SCB_EXT_BASE:
        return layout.wrap(en, jp, layout.DIALOGUE_WIDTH, layout.DIALOGUE_LINES, True)
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
    if cap and len(b) > cap:
        return None, 'too long: %d bytes after layout, limit %d - shorten' % (len(b), cap)
    return b, None
