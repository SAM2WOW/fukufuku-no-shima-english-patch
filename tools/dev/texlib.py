"""Helpers for redrawing Japanese text in UI textures (developer tool).

Needs Pillow (`pip install pillow`). Only used to (re)generate the PNGs in
textures/; the normal build does not need it.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import gim
import iso9660

ROOT = os.path.dirname(os.path.dirname(HERE))
FONTS = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
_iso = None


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def load_from_iso(path, offset=None):
    """path relative to PSP_GAME, e.g. 'USRDIR/data/start/tex1.gma'."""
    global _iso
    if _iso is None:
        import glob
        iso = [p for p in glob.glob(os.path.join(ROOT, '*.iso')) if 'English' not in p][0]
        f = open(iso, 'rb')
        _iso = (f, iso9660.list_files(f))
    f, files = _iso
    data = iso9660.read_file(f, files[('PSP_GAME/' + path).upper()])
    if offset is not None:
        size = int.from_bytes(data[offset + 0x14:offset + 0x18], 'little') + 0x10
        data = data[offset:offset + size]
    w, h, rgba, info, cols = gim.decode(data)
    return Image.frombytes('RGBA', (w, h), bytes(rgba))


def save(img, path, offset=None):
    name = path + ('@%x' % offset if offset is not None else '') + '.png'
    out = os.path.join(ROOT, 'textures', *name.split('/'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print('saved', os.path.relpath(out, ROOT))


def erase(img, box, mode='hinterp'):
    """Remove text inside box (x0,y0,x1,y1 inclusive) by interpolating the
    background from the pixels just outside the box."""
    x0, y0, x1, y1 = box
    px = img.load()
    W, H = img.size
    for y in range(y0, y1 + 1):
        if mode == 'hinterp':
            L = px[max(0, x0 - 1), y]
            R = px[min(W - 1, x1 + 1), y]
            n = x1 - x0 + 2
            for x in range(x0, x1 + 1):
                t = (x - x0 + 1) / n
                px[x, y] = tuple(round(L[c] * (1 - t) + R[c] * t) for c in range(4))
        elif mode == 'right':
            R = px[min(W - 1, x1 + 1), y]
            for x in range(x0, x1 + 1):
                px[x, y] = R
        elif mode == 'vinterp':
            pass
    if mode == 'vinterp':
        for x in range(x0, x1 + 1):
            T = px[x, max(0, y0 - 1)]
            B = px[x, min(H - 1, y1 + 1)]
            n = y1 - y0 + 2
            for y in range(y0, y1 + 1):
                t = (y - y0 + 1) / n
                px[x, y] = tuple(round(T[c] * (1 - t) + B[c] * t) for c in range(4))
    elif isinstance(mode, tuple):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px[x, y] = mode


def fit_font(text, fonts, max_w, max_h, sizes=range(14, 5, -1)):
    """Pick the biggest font/size where text fits."""
    d = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    for s in sizes:
        for fn in fonts:
            f = font(fn, s)
            l, t, r, b = d.textbbox((0, 0), text, font=f)
            if r - l <= max_w and b - t <= max_h:
                return f
    return font(fonts[-1], sizes[-1])


def draw_text(img, region, text, color, fonts=('arialbd.ttf', 'ARIALNB.TTF'), align='center',
              max_size=11, outline=None, outline_w=1, shadow=None, sizes=None):
    x0, y0, x1, y1 = region
    w, h = x1 - x0 + 1, y1 - y0 + 1
    f = fit_font(text, fonts, w, h + 3, sizes or range(max_size, 5, -1))
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    tw, th = r - l, b - t
    if align == 'center':
        x = x0 + (w - tw) / 2 - l
    elif align == 'left':
        x = x0 - l
    else:
        x = x1 - tw - l
    y = y0 + (h - th) / 2 - t
    x, y = round(x), round(y)
    if shadow:
        d.text((x + 1, y + 1), text, font=f, fill=shadow)
    if outline:
        d.text((x, y), text, font=f, fill=color, stroke_width=outline_w, stroke_fill=outline)
    else:
        d.text((x, y), text, font=f, fill=color)
    img.alpha_composite(layer)
    return f.size


def erase_auto(img, box, thresh=60):
    """Replace every pixel in box that differs from the box's dominant colour
    with that colour. Returns the most contrasting (original text) colour."""
    x0, y0, x1, y1 = box
    px = img.load()
    hist = {}
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            c = px[x, y]
            c = (0, 0, 0, 0) if c[3] == 0 else c
            hist[c] = hist.get(c, 0) + 1
    dom = max(hist, key=hist.get)

    def dist(c):
        return abs(c[0] - dom[0]) + abs(c[1] - dom[1]) + abs(c[2] - dom[2]) + 2 * abs(c[3] - dom[3])
    text = max(hist, key=dist)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if dist(px[x, y]) > thresh:
                px[x, y] = dom
    return text


def relabel(img, items, fonts=('arialbd.ttf', 'ARIALNB.TTF'), max_size=11):
    """items: (erase_box, text_region or None, english[, options dict])."""
    for it in items:
        box, region, text = it[:3]
        opt = it[3] if len(it) > 3 else {}
        mode = opt.get('erase', 'auto')
        if mode == 'auto':
            col = erase_auto(img, box, opt.get('thresh', 60))
        else:
            col = None
            erase(img, box, mode)
        col = opt.get('color', col if col and col[3] > 0 else (70, 70, 70, 255))
        if col[3] < 255:
            col = col[:3] + (255,)
        draw_text(img, region or box, text, col, fonts=opt.get('fonts', fonts),
                  max_size=opt.get('size', max_size), align=opt.get('align', 'center'),
                  outline=opt.get('outline'))


def erase_clone(img, box, ref_x):
    """Rebuild box row by row by copying the pixel at column ref_x (a clean
    column of the same button face). Exact for flat or vertically-shaded
    buttons, leaves no anti-aliasing fringe."""
    x0, y0, x1, y1 = box
    px = img.load()
    for y in range(y0, y1 + 1):
        c = px[ref_x, y]
        for x in range(x0, x1 + 1):
            px[x, y] = c


def key_cells(img, y_probe, x_from=0, x_to=None, border=((0x53, 0x53, 0x53), (0x89, 0x89, 0x89))):
    """Find key faces along a row: runs of non-border, non-transparent pixels."""
    px = img.load()
    x_to = img.width if x_to is None else x_to
    runs, start = [], None
    for x in range(x_from, x_to):
        c = px[x, y_probe]
        face = c[3] > 0 and c[:3] not in border
        if face and start is None:
            start = x
        elif not face and start is not None:
            runs.append((start, x - 1))
            start = None
    if start is not None:
        runs.append((start, x_to - 1))
    return runs


def relabel_keys(img, y0, y1, labels, color=(20, 20, 20, 255), fonts=('arial.ttf', 'ARIALN.TTF'),
                 max_size=12, x_from=0, x_to=None, inset=2):
    """Relabel a row of keys whose faces span y0..y1 (inclusive, face only).
    labels: list of English strings or None (leave key untouched), in order."""
    cells = key_cells(img, y0 + 1, x_from, x_to)
    if len(cells) < len([l for l in labels if l is not None]):
        raise ValueError('found %d keys %s for %d labels' % (len(cells), cells, len(labels)))
    px = img.load()
    rows = list(range(y0 - 1, y1 + 2))

    def column(x):
        return tuple(px[x, y] for y in rows)
    pool = {}
    for cx0, cx1 in cells:
        seen = set(column(x) for x in range(cx0 + 2, cx1 - 1))
        for f in seen:
            k, n = pool.get(f, (0, 0))
            pool[f] = (k + 1, n + sum(1 for x in range(cx0 + 2, cx1 - 1) if column(x) == f))
    # the face shared by the most keys (ties: most columns)
    row_face = max(pool, key=lambda f: pool[f])

    def same_style(cx0, cx1):
        # the border row above and the shade row below never contain glyphs
        c = column((cx0 + cx1) // 2)
        return c[0] == row_face[0] and c[-1] == row_face[-1]
    styled = [(a, b) for a, b in cells if same_style(a, b)]
    edges = {}
    for off in (0, 1, -1, -2):
        cnt = {}
        for cx0, cx1 in styled:
            c = column(cx0 + off if off >= 0 else cx1 + off + 1)
            cnt[c] = cnt.get(c, 0) + 1
        edges[off] = max(cnt, key=cnt.get) if cnt else None
    for (cx0, cx1), text in zip(cells, labels):
        if text is None:
            continue
        if same_style(cx0, cx1):
            for x in range(cx0 + 2, cx1 - 1):
                for k, y in enumerate(rows):
                    px[x, y] = row_face[k]
            for off in (0, 1, -1, -2):
                x = cx0 + off if off >= 0 else cx1 + off + 1
                for k, y in enumerate(rows):
                    px[x, y] = edges[off][k]
        else:
            erase_face(img, cx0 + 2, cx1 - 2, y0 - 1, y1 + 1)
        draw_text(img, (cx0 + 1, y0, cx1 - 1, y1), text, color, fonts=fonts, max_size=max_size)
    return cells


def clean_column(img, candidates, y0, y1, dark=0x80):
    """First candidate column with no text-dark pixel between y0 and y1."""
    px = img.load()
    def col(x):
        return [px[x, y] for y in range(y0 - 1, y1 + 2)]
    for x in candidates:
        if col(x) == col(x + 1) == col(x - 1):
            return x
    raise ValueError('no clean reference column among %s' % candidates)


def face_profile(img, x0, x1, y0, y1):
    px = img.load()
    counts = {}
    for x in range(x0, x1 + 1):
        c = tuple(px[x, y] for y in range(y0, y1 + 1))
        counts[c] = counts.get(c, 0) + 1
    face = max(counts, key=counts.get)
    return face, counts[face]


def erase_face(img, x0, x1, y0, y1, fallback=None, prefer=None):
    """Replace every column x0..x1 (rows y0..y1) with the most common column
    profile in that range - i.e. the clean button face."""
    px = img.load()
    face, n = face_profile(img, x0, x1, y0, y1)
    if prefer is not None and any(tuple(px[x, y] for y in range(y0, y1 + 1)) == prefer for x in range(x0, x1 + 1)):
        face, n = prefer, 99
    if n < 3:
        if fallback is None:
            raise ValueError('no clean face found in %s' % ((x0, y0, x1, y1),))
        face = fallback
    for x in range(x0, x1 + 1):
        for k, y in enumerate(range(y0, y1 + 1)):
            px[x, y] = face[k]


def button_rows(img, x, y):
    """Vertical extent (top, bottom) of the opaque button containing (x, y)."""
    px = img.load()
    t = y
    while t > 0 and px[x, t - 1][3] == 255:
        t -= 1
    b = y
    while b < img.height - 1 and px[x, b + 1][3] == 255:
        b += 1
    return t, b


def clean_region(img, box, min_clean=2, guard=True):
    """Remove text inside box (x0,y0,x1,y1) on a button/strip whose background
    is the same in every column (flat, vertical gradient or horizontal
    stripes). The most common column profile in the box is the clean
    background; every column that differs from it is replaced by it.
    The box must not contain icons or rounded caps."""
    x0, y0, x1, y1 = box
    px = img.load()
    cols = {x: tuple(px[x, y] for y in range(y0, y1 + 1)) for x in range(x0, x1 + 1)}
    cnt = {}
    for c in cols.values():
        cnt[c] = cnt.get(c, 0) + 1
    face = max(cnt, key=cnt.get)
    if cnt[face] < min_clean:
        raise ValueError('clean_region: no clean column in %s' % (box,))
    n = 0
    for x, c in cols.items():
        # guard: never touch columns whose outer rows differ (rounded caps, icons edges)
        if c != face and (not guard or (c[0] == face[0] and c[-1] == face[-1])):
            n += 1
            for k, y in enumerate(range(y0, y1 + 1)):
                px[x, y] = face[k]
    return face


def text_color_of(img, box):
    """Darkest/most contrasting colour in the box (the original glyph colour)."""
    px = img.load()
    x0, y0, x1, y1 = box
    best = None
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            c = px[x, y]
            if c[3] < 200:
                continue
            l = sum(c[:3])
            if best is None or l < best[0]:
                best = (l, c)
    return best[1] if best else (40, 40, 40, 255)


def button_box(img, x0, x1, y0, y1):
    """Grow the text rows y0..y1 to the full button (stop at a fully
    transparent separator row) and trim x0..x1 to the straight middle part
    (columns opaque on both the top and bottom row)."""
    px = img.load()

    def clear_row(y):
        return all(px[x, y][3] == 0 for x in range(x0, x1 + 1))
    top, bot = y0, y1
    while top > 0 and not clear_row(top - 1) and y0 - top < 5:
        top -= 1
    while bot < img.height - 1 and not clear_row(bot + 1) and bot - y1 < 5:
        bot += 1
    xs = [x for x in range(x0, x1 + 1) if px[x, top][3] == 255 and px[x, bot][3] == 255]
    return (min(xs), top, max(xs), bot)


def relabel_button(img, x0, x1, y0, y1, text, color, fonts=('arialbd.ttf', 'ARIALNB.TTF'), max_size=11):
    box = button_box(img, x0, x1, y0, y1)
    clean_region(img, box, guard=False)
    draw_text(img, (box[0], box[1] + 1, box[2], box[3] - 1), text, color, fonts=fonts, max_size=max_size)
    return box


def clean_column_near(img, x, y, search=6, dark=150):
    """A column near x whose opaque run through row y has no glyph pixels.
    Returns (x, top, bottom) of that run."""
    px = img.load()
    for dx in [0] + [d for k in range(1, search + 1) for d in (-k, k)]:
        cx = x + dx
        if not (0 <= cx < img.width) or px[cx, y][3] < 255:
            continue
        t = y
        while t > 0 and px[cx, t - 1][3] == 255:
            t -= 1
        b = y
        while b < img.height - 1 and px[cx, b + 1][3] == 255:
            b += 1
        if all(sum(px[cx, yy][:3]) / 3 >= dark for yy in range(t + 1, b)):
            return cx, t, b
    raise ValueError('no clean column near %d,%d' % (x, y))


def relabel_flat(img, x0, x1, y, text, color, ref_x=None, fonts=('arialbd.ttf', 'ARIALNB.TTF'), max_size=11,
                 rows=None):
    """Button with a uniform face: copy a clean column over x0..x1 for the
    button's full height (or the given rows), then draw the English label."""
    if rows:
        t, b = rows
        px = img.load()
        start = ref_x if ref_x is not None else x1
        for cx in [start] + [start + d for k in range(1, 7) for d in (k, -k)]:
            if all(px[cx, yy][3] == 255 and sum(px[cx, yy][:3]) / 3 >= 150 for yy in range(t + 1, b)):
                break
        else:
            raise ValueError('no clean column near %d in rows %s' % (start, rows))
    else:
        cx, t, b = clean_column_near(img, ref_x if ref_x is not None else x1, y)
    erase_clone(img, (x0, t, x1, b), cx)
    draw_text(img, (x0, t, x1, b), text, color, fonts=fonts, max_size=max_size)
    return (x0, t, x1, b, cx)


def erase_row_median(img, box, is_text):
    """For horizontally striped/noisy backgrounds: fill each row with the
    median of its non-text pixels."""
    x0, y0, x1, y1 = box
    px = img.load()
    for y in range(y0, y1 + 1):
        bg = [px[x, y] for x in range(x0, x1 + 1) if not is_text(px[x, y])]
        if not bg:
            continue
        med = tuple(sorted(c[i] for c in bg)[len(bg) // 2] for i in range(4))
        for x in range(x0, x1 + 1):
            px[x, y] = med
