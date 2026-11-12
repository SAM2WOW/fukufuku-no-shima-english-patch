"""Diary/calendar sheet (tex2.gma 'notebook.gim') and the reading/trivia menu
sheet (tex2.gma 'unchiku.gim')."""
from texlib import load_from_iso, save, draw_text, erase, relabel_flat, clean_region

PATH = 'USRDIR/data/start/tex2.gma'
FONTS = ('arialbd.ttf', 'ARIALNB.TTF')
INK = (10, 10, 10, 255)
GRAY = (60, 60, 60, 255)
CLEAR = (0, 0, 0, 0)


def notebook():
    img = load_from_iso(PATH, 0x69f40)
    # top strip: black glyphs on a transparent background, icons in between
    erase(img, (166, 0, 236, 15), CLEAR)                     # ノックスの日記
    draw_text(img, (166, 0, 255, 15), "Nox's Diary", (58, 58, 58, 255), fonts=FONTS, max_size=12, align='left')
    for x0, x1, text in ((19, 52, 'Prev Mo.'), (71, 107, 'Prev Day'), (124, 150, 'News'),
                         (169, 205, 'Next Day'), (225, 255, 'Next Mo.')):
        erase(img, (x0, 16, x1, 32), CLEAR)
        draw_text(img, (x0, 17, x1, 31), text, INK, fonts=FONTS, max_size=11, align='left')
    # bottom buttons: gray capsules
    for x0, x1, ref, text in ((25, 59, 60, 'Prev Mo.'), (89, 123, 124, 'Prev Day'),
                              (152, 187, 188, 'Next Day'), (218, 251, 252, 'Next Mo.')):
        relabel_flat(img, x0, x1, 247, text, GRAY, ref_x=ref, fonts=FONTS, max_size=11, rows=(240, 255))
    relabel_flat(img, 146, 168, 231, 'News', GRAY, ref_x=169, fonts=FONTS, max_size=11, rows=(224, 238))   # △新聞
    save(img, PATH, 0x69f40)
    return img


def unchiku():
    img = load_from_iso(PATH, 0x9ae80)
    # (x0, x1, a y inside the button, clean column near, English)
    for x0, x1, y, ref, text in (
            (26, 55, 8, 56, 'Read'), (93, 118, 8, 119, 'Last'), (157, 200, 8, 201, 'History'),
            (24, 55, 24, 56, 'Close'), (97, 118, 24, 119, 'Next'), (155, 200, 24, 201, 'Close'),
            (30, 55, 40, 56, 'First'), (97, 118, 40, 119, 'Prev'), (157, 200, 40, 201, 'Back'),
            (157, 200, 56, 201, 'Use'), (58, 104, 72, 105, 'Delete'), (155, 200, 72, 201, 'Edit')):
        band = (y // 16 * 16 + 1, y // 16 * 16 + 14)
        relabel_flat(img, x0, x1, y, text, GRAY, ref_x=ref, fonts=FONTS, max_size=11, rows=band)
    # brown tag buttons 相性度 / 添付
    for x0, x1, y, ref, text in ((212, 250, 8, 210, 'Match'), (212, 250, 24, 210, 'Attach')):
        relabel_flat(img, x0, x1, y, text, (40, 36, 30, 255), ref_x=ref, fonts=FONTS, max_size=11,
                     rows=(y // 16 * 16 + 1, y // 16 * 16 + 14))
    # うんちく大全 title: black lettering on a flat beige band
    erase(img, (0, 48, 92, 63), (0xa3, 0xa0, 0x91, 255))
    draw_text(img, (2, 48, 92, 63), 'Trivia Book', INK, fonts=('arialbd.ttf',), max_size=13, align='left')
    save(img, PATH, 0x9ae80)
    return img


if __name__ == '__main__':
    notebook()
    unchiku()
