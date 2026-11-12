"""Function keys of the name/profile keyboard (tex2.gma kb_elmnt) and the
bottle-mail keyboard (window/2d/bm_kb.gim). Kana/letter keys stay as they are."""
from texlib import load_from_iso, save, relabel_keys

# (face y0, face y1, labels left->right; None = keep)
KB_ELMNT = [
    (1, 14, [None, None, None, 'Convert', 'Convert']),        # orange bars, blank, 変換 x2
    (17, 29, ['OK', 'Back', 'Cancel', 'Katakana', 'Hiragana']),
    (241, 253, ['Space', 'Clear', 'Male', 'Female']),
    (257, 269, ['Type A', 'Type B', 'Type O']),
    (273, 285, ['Type AB', 'Type ?']),
]
BM_KB = [
    (1, 13, ['Back', 'Space', 'Confirm', 'Cancel']),
    (17, 29, ['Cancel', 'Convert', 'New Line', 'Input', 'Symbols']),
    (33, 45, ['OK', 'Katakana', 'Hiragana', 'Done']),
]


def build(path, off, rows):
    img = load_from_iso(path, off)
    for y0, y1, labels in rows:
        cells = relabel_keys(img, y0, y1, labels)
        print(path, y0, cells)
    save(img, path, off)
    return img


if __name__ == '__main__':
    a = build('USRDIR/data/start/tex2.gma', 0x55600, KB_ELMNT)
    b = build('USRDIR/data/window/2d/bm_kb.gim', None, BM_KB)
    from PIL import Image
    out = Image.new('RGBA', (288 * 3, 160), (60, 60, 90, 255))
    out.alpha_composite(a.crop((0, 0, 288, 32)).resize((864, 96), 0), (0, 0))
    out.alpha_composite(b.crop((0, 0, 256, 48)).resize((512, 96), 0).crop((0, 0, 512, 64)), (0, 96))
    out.convert('RGB').save(__file__ + '.preview.png')
    out2 = Image.new('RGBA', (288 * 3, 144), (60, 60, 90, 255))
    out2.alpha_composite(a.crop((0, 240, 288, 288)).resize((864, 144), 0))
    out2.convert('RGB').save(__file__ + '.preview2.png')
