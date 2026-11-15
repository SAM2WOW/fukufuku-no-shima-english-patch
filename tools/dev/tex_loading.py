"""Loading-screen character bios (title/l01-l56.gim, 480x272, text on black).

English comes from tools/dev/loading_bios.json (made by loading_ocr.py).
The Japanese block starts with a white ■ (name line); everything from there
to the right/bottom edge of the text is plain black, so it is cleared and the
English is drawn in the same place, same white.

    python tools/dev/tex_loading.py [l01 l02 ...]
"""
import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from texlib import load_from_iso, save, font      # noqa: E402

BIOS = os.path.join(HERE, 'loading_bios.json')
WHITE = (255, 255, 255, 255)


def is_gray(p, lo=24):
    r, g, b, a = p
    return max(r, g, b) >= lo and max(r, g, b) - min(r, g, b) <= 24


def find_square(px, w, h):
    """Top-left of the white ■ that starts the name line."""
    for y in range(h - 10):
        for x in range(60, w - 10):
            if min(px[x, y][:3]) >= 200 and all(min(px[x + i, y + j][:3]) >= 200
                                                for i in range(0, 9, 2) for j in range(0, 9, 2)):
                # first row/col of the solid square
                return x, y
    raise ValueError('no ■ found')


def text_box(img):
    px = img.load()
    w, h = img.size
    x0, y0 = find_square(px, w, h)
    x0 -= 1
    y0 -= 2
    # extend down while text rows (gray pixels right of x0) continue, allowing
    # the line gaps of the Japanese (up to ~14 px)
    y1, gap, y = y0, 0, y0
    x1 = x0
    while y < h and gap < 16:
        row = [x for x in range(x0, w) if is_gray(px[x, y])]
        # the text is pure gray/white; coloured pixels right of x0 mean the
        # character art reaches into the block: the text ended above it
        if any(not is_gray(px[x, y], 0) and max(px[x, y][:3]) > 40 for x in range(x0, w)):
            break
        if row:
            y1, gap = y, 0
            x1 = max(x1, row[-1])
        else:
            gap += 1
        y += 1
    return x0, y0, min(w - 1, x1 + 2), min(h - 1, y1 + 2)


def wrap(draw, text, f, width):
    lines, cur = [], ''
    for word in text.split():
        cand = (cur + ' ' + word).strip()
        if draw.textlength(cand, font=f) <= width or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def free_rows(img, x0, x1, y0, y1):
    """Rows above/below the text block that are completely black from x0
    to the right edge (room for longer English)."""
    px = img.load()
    def empty(y):
        return all(max(px[x, y][:3]) < 24 for x in range(max(0, x0 - 4), img.width))
    top = y0
    while top > 4 and empty(top - 1):
        top -= 1
    bot = y1
    while bot < img.height - 5 and empty(bot + 1):
        bot += 1
    return top, bot


def render(img, name, en, report=None):
    x0, y0, x1, y1 = text_box(img)
    px = img.load()
    colored = sum(1 for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
                  if not is_gray(px[x, y], 0) and max(px[x, y][:3]) > 40)
    if report is not None and colored:
        report.append('%d coloured pixels inside the text box' % colored)
    ImageDraw.Draw(img).rectangle((x0, y0, x1, y1), fill=(0, 0, 0, 255))
    # some glyphs start a few pixels left of the ■: clear gray pixels there
    # too (never coloured character art)
    for y in range(y0, y1 + 1):
        for x in range(max(0, x0 - 6), x0):
            if is_gray(px[x, y], 1):
                px[x, y] = (0, 0, 0, 255)
    lo, hi = free_rows(img, x0, x1, y0, y1)
    d = ImageDraw.Draw(img)
    right = img.width - 10
    for size, pitch in ((12, 17), (12, 16), (11, 15), (11, 14), (10, 13), (10, 12)):
        fb, fr = font('arialbd.ttf', size), font('arial.ttf', size)
        lines = wrap(d, en, fr, right - (x0 + 1))
        need = pitch * (len(lines) + 1) + 4
        # keep the original top if possible, otherwise centre on the old block
        top = y0 + 1
        if top + need > hi:
            top = max(lo, min(top, hi - need))
        if top + need <= hi:
            break
    else:
        if report is not None:
            report.append('TEXT DOES NOT FIT')
    # name line: keep the original ■ look
    d.rectangle((x0 + 1, top + 2, x0 + 9, top + 10), fill=WHITE)
    d.text((x0 + 14, top), name, font=fb, fill=WHITE)
    y = top + pitch + 4
    for ln in lines:
        d.text((x0 + 1, y), ln, font=fr, fill=WHITE)
        y += pitch
    return img


def main(ids):
    bios = json.load(open(BIOS, encoding='utf-8'))
    for k in ids or sorted(bios):
        b = bios[k]
        path = 'USRDIR/data/title/%s.gim' % k
        img = load_from_iso(path)
        rep = []
        name = b['name'][4:] if b['name'].lower().startswith('the ') else b['name']
        render(img, name[0].upper() + name[1:], b['en'], rep)
        save(img, path)
        print(k, b['name'], *rep)


if __name__ == '__main__':
    main(sys.argv[1:])
