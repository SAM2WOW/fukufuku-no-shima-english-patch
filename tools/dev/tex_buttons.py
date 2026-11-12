"""Main UI button atlas (start/tex1.gma 'windows.gim', image at 0x1940)."""
from texlib import load_from_iso, save, draw_text, erase, erase_clone, relabel_flat

PATH, OFF = 'USRDIR/data/start/tex1.gma', 0x1940
GRAY = (70, 70, 70, 255)
FONTS = ('arialbd.ttf', 'ARIALNB.TTF')

# (x where the Japanese starts (right of the icon), x where the straight part
#  of the button ends, first/last row around the text, English)
LABELS = [
    (70, 93, 1, 15, 'Qty'),       # 個数
    (70, 93, 17, 31, 'Pick'),      # 選択
    (20, 61, 35, 48, 'Prev'),      # 前ページ
    (20, 61, 49, 63, 'Next'),      # 次ページ
    (20, 44, 65, 78, 'Info'),      # 詳細
    (69, 92, 65, 78, 'Info'),      # 詳細
    (165, 188, 49, 62, 'Buy'),       # 買う
    (165, 188, 65, 78, 'Sell'),      # 売る
    (68, 92, 81, 95, 'Back'),      # 戻る
    (117, 140, 81, 94, 'Edit'),      # 修正
    (165, 188, 81, 94, 'Use'),       # 使う
    (117, 140, 97, 110, 'Read'),      # 読む
    (160, 188, 97, 110, 'Toss'),      # 捨てる
    (144, 173, 113, 126, 'Close'),     # 閉じる
    (198, 220, 112, 127, 'Give'),      # 渡す
    (185, 217, 129, 142, 'Close'),     # 閉じる
    (31, 57, 161, 175, 'Move'),      # 移動
    (31, 57, 177, 191, 'Swap'),      # 変更
    (94, 118, 161, 174, 'OK'),        # 決定
    (88, 124, 176, 192, 'Match'),     # 相性度
]
TABS = ['General', 'Owned', 'Luck', 'Traits', 'Results']   # 一般 所有 運勢 性格 成果
TAB_X = [(2, 46), (50, 94), (97, 142), (145, 190), (193, 238)]


def main():
    img = load_from_iso(PATH, OFF)
    for x0, x1, top, bot, text in LABELS:
        print(text, relabel_flat(img, x0, x1, (top + bot) // 2, text, GRAY))
    # tabs: gray row 192-207 sits directly on the yellow row 208-223; face is a
    # vertical gradient, so copy a clean column (just left of the text)
    for top, bot in ((192, 207), (208, 223)):
        for (x0, x1), text in zip(TAB_X, TABS):
            erase_clone(img, (x0 + 6, top, x1 - 6, bot), x0 + 3)
            draw_text(img, (x0 + 1, top + 1, x1 - 1, bot - 1), text, (40, 40, 40, 255), fonts=FONTS, max_size=11)
    # 公開 / 非公開 toggles (face rows 226-237)
    for x0, x1, ref, text, size in ((174, 201, 172, 'Public', 10), (217, 247, 212, 'Private', 10)):
        erase_clone(img, (x0, 226, x1, 237), ref)
        draw_text(img, (ref - 6, 226, x1 + 3, 237), text, (40, 40, 40, 255), fonts=FONTS, max_size=size)
    # dark labels on transparent background
    erase(img, (160, 162, 240, 176), (0, 0, 0, 0))     # ラッキーカラー
    draw_text(img, (160, 163, 240, 175), 'Lucky Color', (25, 25, 25, 255), fonts=FONTS, max_size=12, align='left')
    erase(img, (160, 178, 191, 191), (0, 0, 0, 0))      # 定価
    draw_text(img, (160, 179, 191, 190), 'Price', (25, 25, 25, 255), fonts=FONTS, max_size=12, align='left')
    # ゴッド・オブ・探し道 rank title (white text on transparent)
    erase(img, (0, 135, 112, 153), (0, 0, 0, 0))
    draw_text(img, (1, 137, 112, 152), 'God of Searching', (255, 255, 255, 255),
              fonts=('arialbd.ttf',), max_size=12, align='left')
    save(img, PATH, OFF)
    return img


if __name__ == '__main__':
    main()
