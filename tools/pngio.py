"""Minimal dependency-free PNG reader/writer (8-bit, non-interlaced)."""
import zlib, struct


def write_png(path, w, h, rgba):
    """rgba: bytes/bytearray of length w*h*4"""
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)


def read_png(path):
    """Returns (w, h, rgba bytearray). Supports 8-bit gray, RGB, palette, gray+alpha, RGBA."""
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', 'not a PNG'
    pos = 8
    idat = b''
    plte = None
    trns = None
    while pos < len(d):
        ln, = struct.unpack('>I', d[pos:pos + 4])
        t = d[pos + 4:pos + 8]
        body = d[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if t == b'IHDR':
            w, h, bd, ct, _, _, il = struct.unpack('>IIBBBBB', body)
            if bd != 8 or il != 0:
                raise ValueError('%s: only 8-bit non-interlaced PNG supported' % path)
        elif t == b'PLTE':
            plte = body
        elif t == b'tRNS':
            trns = body
        elif t == b'IDAT':
            idat += body
        elif t == b'IEND':
            break
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    raw = zlib.decompress(idat)
    stride = w * ch
    out = bytearray(w * h * ch)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pa = abs(b - c)
                pb = abs(a - c)
                pc = abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line
    if ct == 6:
        return w, h, out
    rgba = bytearray(w * h * 4)
    for i in range(w * h):
        if ct == 2:
            rgba[i * 4:i * 4 + 4] = out[i * 3:i * 3 + 3] + b'\xff'
        elif ct == 0:
            g = out[i]
            rgba[i * 4:i * 4 + 4] = bytes((g, g, g, 255))
        elif ct == 4:
            g = out[i * 2]
            rgba[i * 4:i * 4 + 4] = bytes((g, g, g, out[i * 2 + 1]))
        elif ct == 3:
            k = out[i]
            a = trns[k] if trns and k < len(trns) else 255
            rgba[i * 4:i * 4 + 4] = plte[k * 3:k * 3 + 3] + bytes((a,))
    return w, h, rgba
