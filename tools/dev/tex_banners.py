"""Big stylised result banners (Pass!/Fail, Hit!/Miss, Correct!/Wrong, Start!/Finish!)."""
from PIL import Image, ImageDraw, ImageFilter
from texlib import load_from_iso, save, font

RED = ((205, 40, 35), (112, 16, 16))
BLUE = ((20, 100, 200), (0, 32, 112))
ORANGE = ((240, 70, 0), (150, 30, 0))
YELLOW = (245, 195, 10)


def banner(img, box, text, colors, clear=True, font_name='ARLRDBD.TTF'):
    x0, y0, x1, y1 = box
    fill, dark = colors
    if clear:
        px = img.load()
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px[x, y] = (0, 0, 0, 0)
    W, H = x1 - x0 + 1, y1 - y0 + 1
    pad = max(2, H // 14)             # room for outlines
    d = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    size = H
    while size > 6:
        f = font(font_name, size)
        l, t, r, b = d.textbbox((0, 0), text, font=f, stroke_width=pad)
        if r - l <= W and b - t <= H:
            break
        size -= 1
    sw = pad
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    l, t, r, b = dl.textbbox((0, 0), text, font=f, stroke_width=sw)
    x = x0 + (W - (r - l)) // 2 - l
    y = y0 + (H - (b - t)) // 2 - t
    dl.text((x, y), text, font=f, fill=dark + (255,), stroke_width=sw, stroke_fill=dark + (255,))
    dl.text((x, y), text, font=f, fill=YELLOW + (255,), stroke_width=max(1, sw - 1), stroke_fill=YELLOW + (255,))
    dl.text((x, y), text, font=f, fill=fill + (255,))
    # soft highlight on the top half of the letters, like the original art
    hl = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(hl).text((x, y), text, font=f, fill=(255, 255, 255, 70))
    mask = Image.new('L', img.size, 0)
    ImageDraw.Draw(mask).rectangle((x0, y0, x1, y0 + H * 0.45), fill=255)
    layer.alpha_composite(Image.composite(hl, Image.new('RGBA', img.size, (0, 0, 0, 0)), mask))
    img.alpha_composite(layer)


JOBS = [
    ('USRDIR/data/start/tex2.gma', 0xac8c0, [
        ((13, 4, 81, 37), 'Done!', ORANGE),
        ((3, 68, 211, 147), 'PASS!', RED),
        ((2, 156, 239, 235), 'FAILED', BLUE)]),
    ('USRDIR/data/window/2d/rsltlogo.gim', None, [
        ((13, 4, 81, 37), 'Done!', ORANGE),
        ((3, 68, 211, 147), 'PASS!', RED),
        ((2, 156, 239, 235), 'FAILED', BLUE)]),
    ('USRDIR/data/window/2d/hitmiss.gim', None, [
        ((5, 4, 225, 82), 'HIT!', RED),
        ((4, 92, 227, 172), 'MISS', BLUE)]),
    ('USRDIR/data/window/2d/window46.gim', None, [
        ((5, 4, 225, 82), 'HIT!', RED),
        ((4, 92, 227, 172), 'MISS', BLUE)]),
    ('USRDIR/data/window/2d/window48.gim', None, [
        ((4, 0, 238, 78), 'RIGHT!', RED),
        ((4, 79, 238, 160), 'WRONG', BLUE)]),
    ('USRDIR/data/window/2d/window49.gim', None, [
        ((1, 0, 255, 78), 'START!', RED),
        ((1, 79, 255, 158), 'FINISH!', BLUE)]),
]


def main():
    sheet = Image.new('RGBA', (1024, 512), (60, 60, 90, 255))
    for i, (path, off, items) in enumerate(JOBS):
        img = load_from_iso(path, off)
        for box, text, colors in items:
            banner(img, box, text, colors)
        save(img, path, off)
        sheet.alpha_composite(img.crop((0, 0, 256, 256)), ((i % 4) * 256, (i // 4) * 256))
    sheet.convert('RGB').save(__file__ + '.preview.png')


if __name__ == '__main__':
    main()
