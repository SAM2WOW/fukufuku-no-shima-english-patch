"""Title menu, fortune-ranking header and qualification certificate."""
from PIL import Image, ImageDraw, ImageFilter
from texlib import load_from_iso, save, relabel, draw_text, erase, erase_clone

DARK = (45, 40, 40, 255)


def title_menu():
    path, off = 'USRDIR/data/title/title.cts', 0x61140
    img = load_from_iso(path, off)
    labels = ['New Game', 'Continue', 'Credits', 'Homepage']   # はじめから つづきから スタッフロール ホームページ
    px = img.load()
    for top, bot in ((272, 287), (288, 303)):        # normal / highlighted rows
        face = [px[9, y] for y in range(top, bot + 1)]   # column 9 of the first button is clean
        for i, text in enumerate(labels):
            x = i * 80
            for cx in range(x + 4, x + 75):
                for k, y in enumerate(range(top, bot + 1)):
                    px[cx, y] = face[k]
            draw_text(img, (x + 6, top + 3, x + 74, bot - 3), text, DARK,
                      fonts=('arialbd.ttf', 'ARIALNB.TTF'), max_size=11)
    save(img, path, off)
    return img


def ranking_header():
    path = 'USRDIR/data/window/2d/window72.gim'
    img = load_from_iso(path)
    box = (16, 1, 271, 30)
    region = img.crop(box)
    # remove the bright lettering (min filter), then smooth what is left so it
    # reads as a soft dark band, feathered into the untouched starfield
    soft = region.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.GaussianBlur(4))
    mask = Image.new('L', region.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((3, 2, region.width - 4, region.height - 3), 6, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(2))
    region.paste(soft, (0, 0), mask)
    img.paste(region, box[:2])
    draw_text(img, (18, 2, 269, 29), "Today's Luck Ranking", (232, 222, 140, 255),
              fonts=('georgiab.ttf', 'timesbd.ttf'), max_size=19, outline=(35, 28, 8, 255))
    save(img, path)
    return img


def certificate():
    path = 'USRDIR/data/window/2d/qual.gim'
    img = load_from_iso(path)
    clear = (0, 0, 0, 0)
    erase(img, (176, 62, 240, 96), clear)      # 表彰状 / 殿
    erase(img, (0, 190, 240, 242), clear)     # body text
    ink = (25, 25, 25, 255)
    draw_text(img, (176, 62, 240, 80), 'Certificate', ink, fonts=('georgiab.ttf', 'timesbd.ttf'), max_size=13)
    lines = ['In recognition of your daily diligence,',
             'we hereby certify that you have earned',
             'the qualification stated above.']
    for k, line in enumerate(lines):
        y = 192 + k * 16
        draw_text(img, (18, y, 236, y + 12), line, ink, fonts=('georgia.ttf', 'times.ttf'), max_size=11)
    save(img, path)
    return img


if __name__ == '__main__':
    from PIL import Image
    a, b, c = title_menu(), ranking_header(), certificate()
    out = Image.new('RGBA', (560, 420), (90, 90, 120, 255))
    out.alpha_composite(a.crop((0, 262, 330, 304)).resize((660, 84), 0), (0, 0))
    out.alpha_composite(b, (0, 90))
    out.alpha_composite(c, (290, 150))
    out.convert('RGB').save(__file__ + '.preview.png')
