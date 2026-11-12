"""Constellation panel labels (tex2.gma 'sp_elmnt.gim', image at 0x8a980):
black text on a transparent background."""
from texlib import load_from_iso, save, erase, draw_text

PATH, OFF = 'USRDIR/data/start/tex2.gma', 0x8a980
INK = (10, 10, 10, 255)


def main():
    img = load_from_iso(PATH, OFF)
    for (x0, y0, x1, y1), text in (((0, 32, 78, 46), 'Stars needed'),     # 必要な星
                                    ((0, 47, 78, 62), 'Stars owned')):     # 持っている星
        erase(img, (x0, y0, x1, y1), (0, 0, 0, 0))
        draw_text(img, (x0 + 2, y0 + 1, x1, y1 - 1), text, INK, fonts=('arialbd.ttf', 'ARIALNB.TTF'),
                  max_size=11, align='left')
    save(img, PATH, OFF)


if __name__ == '__main__':
    main()
