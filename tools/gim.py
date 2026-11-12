"""PSP GIM image reader/writer (subset used by Fukufuku no Shima). Pure Python."""
import struct, sys, os

FMT_BPP = {0: 16, 1: 16, 2: 16, 3: 32, 4: 4, 5: 8, 6: 16, 7: 32}


def _blocks(d, off, end, out):
    while off + 16 <= end:
        bid, unk, size, nxt, doff = struct.unpack_from('<HHIII', d, off)
        out.append((bid, off, size, nxt, doff))
        if bid in (2, 3):
            _blocks(d, off + doff, off + size, out)
        if size == 0:
            break
        off += size


def parse(d):
    if d[:4] != b'MIG.':
        raise ValueError('not a GIM')
    out = []
    _blocks(d, 0x10, len(d), out)
    imgs = []
    pals = []
    for bid, off, size, nxt, doff in out:
        if bid in (4, 5):
            b = off + doff
            hdr = struct.unpack_from('<HHHHHHHHHHIIIIHHHH', d, b)
            info = dict(block=off, base=b, hdrsize=hdr[0], fmt=hdr[2], order=hdr[3], w=hdr[4], h=hdr[5],
                        bpp_align=hdr[6], pitch_align=hdr[7], h_align=hdr[8],
                        pix_start=b + hdr[12], pix_end=b + hdr[13])
            (imgs if bid == 4 else pals).append(info)
    return imgs, pals


def _rowbytes(info):
    bpp = FMT_BPP[info['fmt']]
    pa = info['pitch_align'] or 16
    rb = (info['w'] * bpp + 7) // 8
    return (rb + pa - 1) // pa * pa, bpp


def _unswizzle(src, rowbytes, h):
    hh = (h + 7) // 8 * 8
    out = bytearray(rowbytes * hh)
    bw = rowbytes // 16
    i = 0
    for by in range(hh // 8):
        for bx in range(bw):
            for r in range(8):
                dst = (by * 8 + r) * rowbytes + bx * 16
                out[dst:dst + 16] = src[i:i + 16]
                i += 16
    return out


def _swizzle(lin, rowbytes, h):
    hh = (h + 7) // 8 * 8
    lin = bytes(lin) + bytes(max(0, rowbytes * hh - len(lin)))
    out = bytearray(rowbytes * hh)
    bw = rowbytes // 16
    i = 0
    for by in range(hh // 8):
        for bx in range(bw):
            for r in range(8):
                src = (by * 8 + r) * rowbytes + bx * 16
                out[i:i + 16] = lin[src:src + 16]
                i += 16
    return out


def _color(fmt, v):
    if fmt == 0:
        return ((v & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, ((v >> 11) & 31) * 255 // 31, 255)
    if fmt == 1:
        return ((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31, 255 if v >> 15 else 0)
    if fmt == 2:
        return ((v & 15) * 17, ((v >> 4) & 15) * 17, ((v >> 8) & 15) * 17, ((v >> 12) & 15) * 17)
    return (v & 255, (v >> 8) & 255, (v >> 16) & 255, v >> 24)


def _pack(fmt, c):
    r, g, b, a = c
    if fmt == 0:
        return (r * 31 + 127) // 255 | ((g * 63 + 127) // 255) << 5 | ((b * 31 + 127) // 255) << 11
    if fmt == 1:
        return (r * 31 + 127) // 255 | ((g * 31 + 127) // 255) << 5 | ((b * 31 + 127) // 255) << 10 | (0x8000 if a >= 128 else 0)
    if fmt == 2:
        return (r * 15 + 127) // 255 | ((g * 15 + 127) // 255) << 4 | ((b * 15 + 127) // 255) << 8 | ((a * 15 + 127) // 255) << 12
    return r | g << 8 | b << 16 | a << 24


def read_palette(d, pal):
    bpp = FMT_BPP[pal['fmt']]
    n = (pal['pix_end'] - pal['pix_start']) // (bpp // 8)
    cols = []
    for i in range(n):
        if bpp == 32:
            v, = struct.unpack_from('<I', d, pal['pix_start'] + i * 4)
        else:
            v, = struct.unpack_from('<H', d, pal['pix_start'] + i * 2)
        cols.append(_color(pal['fmt'], v))
    return cols


def decode(d, idx=0):
    imgs, pals = parse(d)
    info = imgs[idx]
    rowbytes, bpp = _rowbytes(info)
    w, h = info['w'], info['h']
    src = d[info['pix_start']:info['pix_end']]
    lin = _unswizzle(src, rowbytes, h) if info['order'] == 1 else bytearray(src)
    cols = read_palette(d, pals[min(idx, len(pals) - 1)]) if pals else None
    rgba = bytearray(w * h * 4)
    fmt = info['fmt']
    for y in range(h):
        row = y * rowbytes
        for x in range(w):
            if bpp == 4:
                b = lin[row + x // 2]
                c = cols[(b >> 4) if x & 1 else (b & 15)]
            elif bpp == 8:
                c = cols[lin[row + x]]
            elif bpp == 16:
                v, = struct.unpack_from('<H', lin, row + x * 2)
                c = cols[v] if fmt == 6 else _color(fmt, v)
            else:
                v, = struct.unpack_from('<I', lin, row + x * 4)
                c = cols[v] if fmt == 7 else _color(fmt, v)
            o = (y * w + x) * 4
            rgba[o:o + 4] = bytes(c)
    return w, h, rgba, info, cols


def quantize(items, n):
    """Median cut over [(rgba tuple, count)] -> list of <= n colours."""
    if len(items) <= n:
        return [tuple(c) for c, _ in items]
    boxes = [list(items)]

    def spread(b):
        return max(max(c[k] for c, _ in b) - min(c[k] for c, _ in b) for k in range(4))
    while len(boxes) < n:
        boxes.sort(key=lambda b: -spread(b) if len(b) > 1 else 1)
        b = boxes.pop(0)
        if len(b) < 2:
            boxes.append(b)
            break
        k = max(range(4), key=lambda k: max(c[k] for c, _ in b) - min(c[k] for c, _ in b))
        b.sort(key=lambda it: it[0][k])
        tot = sum(cnt for _, cnt in b)
        acc = 0
        cut = len(b) // 2
        for i, (_, cnt) in enumerate(b):
            acc += cnt
            if acc >= tot / 2:
                cut = max(1, min(len(b) - 1, i + 1))
                break
        boxes += [b[:cut], b[cut:]]
    pal = []
    for b in boxes:
        tot = sum(cnt for _, cnt in b)
        pal.append(tuple(round(sum(c[k] * cnt for c, cnt in b) / tot) for k in range(4)))
    return pal


def encode_into(d, rgba, idx=0, keep_palette=False):
    """Re-encode RGBA pixels into an existing GIM (same size/format). Returns new bytes."""
    d = bytearray(d)
    imgs, pals = parse(d)
    info = imgs[idx]
    rowbytes, bpp = _rowbytes(info)
    w, h = info['w'], info['h']
    fmt = info['fmt']
    lin = bytearray(rowbytes * ((h + 7) // 8 * 8) if info['order'] == 1 else info['pix_end'] - info['pix_start'])
    if fmt in (4, 5):
        pal = pals[min(idx, len(pals) - 1)]
        cols = read_palette(d, pal)
        maxc = min(1 << bpp, len(cols))
        hist = {}
        for i in range(w * h):
            c = tuple(rgba[i * 4:i * 4 + 4])
            if c[3] == 0:
                c = (0, 0, 0, 0)
            hist[c] = hist.get(c, 0) + 1
        cset = set(tuple(c) for c in cols)
        if keep_palette or all(c in cset for c in hist):
            palette = [tuple(c) for c in cols]
        else:
            palette = quantize(list(hist.items()), maxc)
            palette += [(0, 0, 0, 0)] * (len(cols) - len(palette))
            pbpp = FMT_BPP[pal['fmt']]
            for i, c in enumerate(palette):
                v = _pack(pal['fmt'], c)
                if pbpp == 32:
                    struct.pack_into('<I', d, pal['pix_start'] + i * 4, v)
                else:
                    struct.pack_into('<H', d, pal['pix_start'] + i * 2, v)
            palette = [_color(pal['fmt'], _pack(pal['fmt'], c)) for c in palette]
        cache = {}

        def nearest(c):
            r = cache.get(c)
            if r is None:
                r = min(range(maxc), key=lambda k: (c[0] - palette[k][0]) ** 2 + (c[1] - palette[k][1]) ** 2 +
                        (c[2] - palette[k][2]) ** 2 + 3 * (c[3] - palette[k][3]) ** 2)
                cache[c] = r
            return r
        for y in range(h):
            for x in range(w):
                o = (y * w + x) * 4
                c = tuple(rgba[o:o + 4])
                if c[3] == 0:
                    c = (0, 0, 0, 0)
                k = nearest(c)
                if bpp == 4:
                    p = y * rowbytes + x // 2
                    lin[p] = (lin[p] & 0x0f) | (k << 4) if x & 1 else (lin[p] & 0xf0) | k
                else:
                    lin[y * rowbytes + x] = k
    elif fmt in (0, 1, 2, 3):
        for y in range(h):
            for x in range(w):
                o = (y * w + x) * 4
                v = _pack(fmt, tuple(rgba[o:o + 4]))
                if bpp == 32:
                    struct.pack_into('<I', lin, y * rowbytes + x * 4, v)
                else:
                    struct.pack_into('<H', lin, y * rowbytes + x * 2, v)
    else:
        raise ValueError('unsupported GIM format %d' % fmt)
    if info['order'] == 1:
        lin = _swizzle(lin, rowbytes, h)
    n = info['pix_end'] - info['pix_start']
    d[info['pix_start']:info['pix_end']] = bytes(lin[:n]) + bytes(max(0, n - len(lin)))
    return bytes(d)


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pngio import write_png
    outdir = sys.argv[1]
    for p in sys.argv[2:]:
        d = open(p, 'rb').read()
        try:
            imgs, pals = parse(d)
            for i in range(len(imgs)):
                w, h, rgba, info, cols = decode(d, i)
                o = os.path.join(outdir, os.path.basename(p) + ('' if i == 0 else '_%d' % i) + '.png')
                write_png(o, w, h, rgba)
                print(o, w, h, 'fmt', info['fmt'], 'order', info['order'], 'imgs', len(imgs))
        except Exception as e:
            print('ERR', p, repr(e))
