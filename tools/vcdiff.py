"""Minimal VCDIFF (RFC 3284) encoder/decoder, compatible with xdelta3 patchers.

The encoder assumes target and source are mostly aligned (true for an
in-place patched ISO): each target window is compared with the same range of
the source and encoded as COPY/ADD instructions.

    python tools/vcdiff.py encode original.iso patched.iso out.xdelta
    python tools/vcdiff.py decode original.iso patch.xdelta out.iso
"""
import sys

MAGIC = b'\xd6\xc3\xc4\x00'
WIN = 1 << 22           # 4 MiB target windows
BLOCK = 1 << 16
MIN_COPY = 24


def varint(n):
    out = [n & 0x7f]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7f))
        n >>= 7
    return bytes(reversed(out))


def read_varint(b, p):
    n = 0
    while True:
        c = b[p]
        p += 1
        n = (n << 7) | (c & 0x7f)
        if not c & 0x80:
            return n, p


def _diff_ranges(s, t):
    """Yield ('copy', off, n) / ('add', off, n) covering t, comparing with s."""
    n = len(t)
    i = 0
    ops = []
    while i < n:
        j = min(n, i + BLOCK)
        if j <= len(s) and s[i:j] == t[i:j]:
            ops.append(['copy', i, j - i])
        else:
            # fine-grained inside the block
            k = i
            while k < j:
                if k < len(s) and s[k] == t[k]:
                    e = k
                    while e < j and e < len(s) and s[e] == t[e]:
                        e += 1
                    ops.append(['copy', k, e - k])
                    k = e
                else:
                    e = k
                    while e < j and (e >= len(s) or s[e] != t[e]):
                        e += 1
                    ops.append(['add', k, e - k])
                    k = e
        i = j
    # merge neighbours, turn short copies into adds
    merged = []
    for op in ops:
        if op[0] == 'copy' and op[2] < MIN_COPY:
            op[0] = 'add'
        if merged and merged[-1][0] == op[0] and merged[-1][1] + merged[-1][2] == op[1]:
            merged[-1][2] += op[2]
        else:
            merged.append(op)
    return merged


def encode(src, tgt, out):
    with open(out, 'wb') as f:
        f.write(MAGIC + b'\x00')
        for t0 in range(0, len(tgt), WIN):
            t = tgt[t0:t0 + WIN]
            s = src[t0:t0 + WIN] if t0 < len(src) else b''
            data, inst, addr = bytearray(), bytearray(), bytearray()
            for kind, off, n in _diff_ranges(s, t):
                if kind == 'copy':
                    inst += b'\x13' + varint(n)          # COPY, size follows, mode 0 (SELF)
                    addr += varint(off)
                else:
                    inst += b'\x01' + varint(n)          # ADD, size follows
                    data += t[off:off + n]
            body = varint(len(t)) + b'\x00' + varint(len(data)) + varint(len(inst)) + varint(len(addr))
            body += data + inst + addr
            if s:
                f.write(b'\x01' + varint(len(s)) + varint(t0) + varint(len(body)) + body)
            else:
                f.write(b'\x00' + varint(len(body)) + body)


def decode(src, patch):
    """Decoder supporting the default code table (enough to verify our patches
    and most xdelta3 output that does not use secondary compression)."""
    # build default code table
    table = [((0, 0, 0), (0, 0, 0))] * 256
    table = []
    table.append(((2, 0, 0), (0, 0, 0)))              # RUN
    for s in range(0, 18):
        table.append(((1, s, 0), (0, 0, 0)))          # ADD
    for m in range(9):
        table.append(((3, 0, m), (0, 0, 0)))
        for s in range(4, 19):
            table.append(((3, s, m), (0, 0, 0)))
    for m in range(6):
        for s in range(1, 5):
            for c in range(4, 7):
                table.append(((1, s, 0), (3, c, m)))
    for m in range(6, 9):
        for s in range(1, 5):
            table.append(((1, s, 0), (3, 4, m)))
    for m in range(9):
        table.append(((3, 4, m), (1, 1, 0)))
    assert len(table) == 256
    p = patch
    assert p[:4] == MAGIC
    hi = p[4]
    q = 5
    assert hi == 0, 'secondary compression / custom tables not supported'
    out = bytearray()
    while q < len(p):
        wi = p[q]
        q += 1
        seg = b''
        if wi & 3:
            ssz, q = read_varint(p, q)
            spos, q = read_varint(p, q)
            seg = src[spos:spos + ssz] if wi & 1 else bytes(out[spos:spos + ssz])
        dlen, q = read_varint(p, q)
        tlen, q2 = read_varint(p, q)
        di = p[q2]
        q2 += 1
        ld, q2 = read_varint(p, q2)
        li, q2 = read_varint(p, q2)
        la, q2 = read_varint(p, q2)
        if wi & 4:
            q2 += 4
        data = p[q2:q2 + ld]
        inst = p[q2 + ld:q2 + ld + li]
        adrs = p[q2 + ld + li:q2 + ld + li + la]
        q = q + dlen
        t = bytearray()
        dp = ip = ap = 0
        near = [0] * 4
        nidx = 0
        same = [0] * (3 * 256)
        while ip < len(inst):
            code = inst[ip]
            ip += 1
            for typ, size, mode in table[code]:
                if typ == 0:
                    continue
                if size == 0:
                    size, ip = read_varint(inst, ip)
                if typ == 1:
                    t += data[dp:dp + size]
                    dp += size
                elif typ == 2:
                    t += data[dp:dp + 1] * size
                    dp += 1
                else:
                    here = len(seg) + len(t)
                    if mode == 0:
                        a, ap = read_varint(adrs, ap)
                    elif mode == 1:
                        v, ap = read_varint(adrs, ap)
                        a = here - v
                    elif mode < 6:
                        v, ap = read_varint(adrs, ap)
                        a = near[mode - 2] + v
                    else:
                        a = same[(mode - 6) * 256 + adrs[ap]]
                        ap += 1
                    near[nidx] = a
                    nidx = (nidx + 1) % 4
                    same[a % (3 * 256)] = a
                    for k in range(size):
                        x = a + k
                        t.append(seg[x] if x < len(seg) else t[x - len(seg)])
        assert len(t) == tlen
        out += t
    return bytes(out)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'encode':
        encode(open(sys.argv[2], 'rb').read(), open(sys.argv[3], 'rb').read(), sys.argv[4])
    elif cmd == 'decode':
        res = decode(open(sys.argv[2], 'rb').read(), open(sys.argv[3], 'rb').read())
        open(sys.argv[4], 'wb').write(res)
