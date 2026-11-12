"""Fortune result window buttons (tex2.gma 'ftwin.gim', image at 0x42680)."""
from texlib import load_from_iso, save, relabel_flat

PATH, OFF = 'USRDIR/data/start/tex2.gma', 0x42680
GRAY = (60, 60, 60, 255)
FONTS = ('arialbd.ttf', 'ARIALNB.TTF')

# stacked buttons on the right, 16-pixel grid: (y of the text, English)
RIGHT = [(183, 'Close'), (200, 'Next'), (216, 'Prev'),          # 次の占い 前の占い
         (232, 'Next'), (248, 'Prev')]                                # 次の分析 前の分析


def main():
    img = load_from_iso(PATH, OFF)
    for y, text in RIGHT:
        band = (y // 16 * 16 + 1, y // 16 * 16 + 14)
        relabel_flat(img, 123, 168, y, text, GRAY, ref_x=122, fonts=FONTS, max_size=11, rows=band)
    relabel_flat(img, 18, 92, 192, 'See Other Results', GRAY, ref_x=17, fonts=FONTS, max_size=11)   # 他の結果を見る
    relabel_flat(img, 20, 88, 225, 'Close', GRAY, ref_x=19, fonts=FONTS, max_size=11)               # 閉じる
    save(img, PATH, OFF)
    return img


if __name__ == '__main__':
    main()
