"""Extract Japanese text from the original ISO into text/*.txt.

Existing translations (EN lines) are kept when the file is re-extracted.
Usage: python tools/extract.py "Fukufuku no Shima (Japan).iso"
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formats
import iso9660
import textfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = os.path.join(ROOT, 'text')

# Script files that are debug/test menus and never seen by players.
SKIP = re.compile(r'/(debug\d*|sample)\.scb$', re.I)
DIALOGUE_WIDTH = 44


def line_width(s):
    s = re.sub(r'<[^>]*>', '', s)
    return sum(1 if ord(c) < 0x80 or 0xFF61 <= ord(c) <= 0xFF9F else 2 for c in s)


def wanted(path):
    p = path.upper()
    if p == 'PSP_GAME/SYSDIR/BOOT.BIN':
        return True
    if not p.startswith('PSP_GAME/USRDIR/DATA/'):
        return False
    return formats.handler_for(path) is not None and not SKIP.search(path)


def main(iso_path):
    with open(iso_path, 'rb') as f:
        files = iso9660.list_files(f)
        total = 0
        for key in sorted(files):
            e = files[key]
            if not wanted(e.path):
                continue
            h = formats.handler_for(e.path)
            data = iso9660.read_file(f, e)
            ents = h.extract(data)
            if not ents:
                continue
            out = os.path.join(TEXT, *e.path.split('/')[1:])
            out = os.path.splitext(out)[0] + '.txt'
            os.makedirs(os.path.dirname(out), exist_ok=True)
            old = {}
            if os.path.exists(out):
                _, olds = textfile.load(out)
                old = {o.key: o for o in olds}
            width = DIALOGUE_WIDTH if h.kind == 'scb' else max(
                (line_width(l) for x in ents for l in re.split(r'<n>|<p>', x.jp)), default=40)
            meta = {'source': e.path, 'format': h.kind, 'width': str(width)}
            tents = []
            for x in ents:
                t = textfile.TEntry(x.key, x.cap, x.jp)
                o = old.get(x.key)
                if o and o.jp == x.jp:
                    t.en, t.note = o.en, o.note
                tents.append(t)
            textfile.save(out, meta, tents)
            total += len(tents)
            print('%-60s %5d' % (e.path, len(tents)))
        print('total entries', total)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'Fukufuku no Shima (Japan).iso'))
