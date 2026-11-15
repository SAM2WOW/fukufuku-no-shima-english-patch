"""Qualification icons (window/2d/icon050.gim, 8x4 cells of 32x32) and the
place viewer's buttons (window/2d/sight.gim: L Prev / R Next / Close).

Each icon cell is rebuilt from an empty cell of the same sheet (row 4 has
seven blank ones), then labelled in the same dark ink.
"""
from PIL import ImageDraw
from texlib import load_from_iso, save, fit_font, relabel_flat

INK = (40, 32, 28, 255)
CELL = 32
# row-major, as on the sheet
QUALS = ['Eng\nLv5', 'Eng\nLv3', 'Kanji\nLv3', 'Kanji\nLv1', 'Tour\nGuide', 'Weath-\ner', 'Haz\nMat', 'Elec-\ntric',
         'Archi-\ntect', 'Con-\ncrete', 'Fire-\nman', 'Explo-\nsives', 'Child\nCare', 'FP', 'Beau-\ntician', 'Chef',
         'Real\nEstate', 'Boat', 'IT', 'Pollu-\ntion', 'Driver', 'Secre-\ntary', 'Color', 'Aroma',
         'Inter-\nior']
BLANK = (1, 3)          # (col, row) of a clean empty cell


def quals():
    path = 'USRDIR/data/window/2d/icon050.gim'
    img = load_from_iso(path)
    bx, by = BLANK[0] * CELL, BLANK[1] * CELL
    blank = img.crop((bx, by, bx + CELL, by + CELL))
    d = ImageDraw.Draw(img)
    for i, label in enumerate(QUALS):
        x, y = (i % 8) * CELL, (i // 8) * CELL
        img.paste(blank, (x, y))
        # inner area inside the brown frame
        x0, y0, x1, y1 = x + 3, y + 3, x + CELL - 4, y + CELL - 4
        f = fit_font(label, ('arialbd.ttf', 'ARIALNB.TTF'), x1 - x0 + 1, y1 - y0 + 1, range(10, 6, -1))
        l, t, r, b = d.multiline_textbbox((0, 0), label, font=f, spacing=0, align='center')
        tx = x0 + (x1 - x0 + 1 - (r - l)) / 2 - l
        ty = y0 + (y1 - y0 + 1 - (b - t)) / 2 - t
        d.multiline_text((round(tx), round(ty)), label, font=f, fill=INK, spacing=0, align='center')
    save(img, path)
    return img


def sight():
    path = 'USRDIR/data/window/2d/sight.gim'
    img = load_from_iso(path)
    gray = (60, 60, 60, 255)
    for (t, b), text in (((281, 294), 'Prev Spot'), ((297, 310), 'Next Spot'), ((313, 326), 'Close')):
        relabel_flat(img, 25, 71, (t + b) // 2, text, gray, ref_x=24, rows=(t, b), max_size=11)
    save(img, path)
    return img


if __name__ == '__main__':
    quals()
    sight()
