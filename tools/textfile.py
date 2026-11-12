"""Read/write the human-editable translation files in text/.

Format (UTF-8):

    # source: PSP_GAME/USRDIR/data/script/hiyopi.scb
    # width: 44

    @5144 max=639
    JP: よーう。あんた、<PN>やろ？<n>ハハ、ワイは何でも知っとるでー。
    EN: Heyyy. You're <PN>, right?<n>Haha, I know everything!

An empty EN line keeps the original Japanese. Tags such as <n> (new line),
<p> (new page) and <PN> (player name) must be kept. Control characters are
written as \\n, \\t, \\r and a literal backslash as \\\\.
"""
import re

BS = chr(92)
_ESC = {BS: BS + BS, '\n': BS + 'n', '\r': BS + 'r', '\t': BS + 't'}
_UNESC = {'n': '\n', 'r': '\r', 't': '\t', BS: BS}
_UNESC_RE = re.compile(re.escape(BS) + '(.)')


def esc(s):
    return ''.join(_ESC.get(c, c) for c in s)


def unesc(s):
    return _UNESC_RE.sub(lambda m: _UNESC.get(m.group(1), BS + m.group(1)), s)


class TEntry:
    __slots__ = ('key', 'cap', 'jp', 'en', 'note')

    def __init__(self, key, cap, jp, en='', note=''):
        self.key, self.cap, self.jp, self.en, self.note = key, cap, jp, en, note


def load(path):
    meta = {}
    entries = []
    cur = None
    with open(path, encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\r\n')
            if line.startswith('# ') and ':' in line and not entries:
                k, v = line[2:].split(':', 1)
                meta[k.strip()] = v.strip()
            elif line.startswith('@'):
                m = re.match(r'@(\S+)(?:\s+max=(\d+))?', line)
                cur = TEntry(m.group(1), int(m.group(2) or 0), '')
                entries.append(cur)
            elif line.startswith('JP: ') or line == 'JP:':
                cur.jp = unesc(line[4:])
            elif line.startswith('EN: ') or line == 'EN:':
                cur.en = unesc(line[4:])
            elif line.startswith('// ') and cur is not None:
                cur.note = line[3:]
    return meta, entries


def save(path, meta, entries):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        for k, v in meta.items():
            f.write('# %s: %s\n' % (k, v))
        for e in entries:
            f.write('\n@%s%s\n' % (e.key, ' max=%d' % e.cap if e.cap else ''))
            if e.note:
                f.write('// %s\n' % e.note)
            f.write('JP: %s\n' % esc(e.jp))
            f.write('EN: %s\n' % esc(e.en))
