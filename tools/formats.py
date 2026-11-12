"""Knowledge of Fukufuku no Shima's text containers.

Every container is described by a "handler" that can:
  * extract(data) -> list of Entry(key, capacity, jp)
  * build(data, {key: encoded_bytes}) -> new data

Keys are hex offsets (fixed-size fields patched in place) or record indices
(size-prefixed record files that are rebuilt).
"""
import re
import struct

SJIS_DBL = re.compile(rb'[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]')


class Entry:
    __slots__ = ('key', 'cap', 'jp', 'width')

    def __init__(self, key, cap, jp, width=0):
        self.key, self.cap, self.jp, self.width = key, cap, jp, width


def decode(b):
    return b.decode('cp932')


def is_japanese(b, min_chars=1):
    if not b:
        return False
    try:
        b.decode('cp932')
    except UnicodeDecodeError:
        return False
    return len(SJIS_DBL.findall(b)) >= min_chars


# ---------------------------------------------------------------- fixed fields

def _nz_after(d, i, hi):
    while i < hi and d[i] == 0:
        i += 1
    return i


def find_strings(d, lo, hi, min_chars=1):
    """Zero-delimited Japanese strings in d[lo:hi] -> list of (start, end)."""
    out = []
    for m in re.finditer(rb'[^\x00]+', d[lo:hi]):
        s = m.group()
        a = lo + m.start()
        if is_japanese(s, min_chars):
            out.append((a, a + len(s)))
    return out


def column_capacities(d, strings, lo, hi, max_hits=24):
    """For each string, the number of bytes (excl. NUL) that can safely be written.

    Strings that sit in a table of fixed-size records (same field repeated
    every S bytes) are limited to the tightest gap seen in any record, so we
    never overwrite a numeric field that happens to be zero in one record.
    """
    starts = {a: b for a, b in strings}
    order = sorted(starts)
    prev_gap, next_gap = {}, {}
    for i, a in enumerate(order):
        prev_gap[a] = a - order[i - 1] if i else None
        next_gap[a] = order[i + 1] - a if i + 1 < len(order) else None

    def same_shape(x, y):
        return prev_gap[x] == prev_gap[y] or next_gap[x] == next_gap[y]
    caps = {}
    for a, b in strings:
        q = _nz_after(d, b, hi)
        best = None
        cands = set()
        for a2, _ in strings:
            if a2 != a and abs(a2 - a) <= 0x4000:
                cands.add(abs(a2 - a))
        for S in sorted(cands):
            if S % 4:
                continue
            ks = [0]
            for sgn in (1, -1):
                k = 1
                # a record only counts if it has the same shape (the previous
                # string sits at the same distance), so the chain never runs on
                # into a neighbouring table that happens to share the stride
                while k <= max_hits and (a + sgn * k * S) in starts \
                        and prev_gap[a + sgn * k * S] == prev_gap[a]:
                    ks.append(sgn * k)
                    k += 1
            if len(ks) >= 3 and (best is None or len(ks) > len(best[1])):
                best = (S, ks)
        cap = q - a - 1
        if best:
            S, ks = best
            for k in ks:
                pa = a + k * S
                pb = starts[pa]
                qq = _nz_after(d, pb, hi)
                cap = min(cap, qq - pa - 1)
            cap = min(cap, S - 1)
        caps[a] = (max(cap, b - a), best is not None)
    return caps


# ---------------------------------------------------------------- .scb scripts

SCB_MSG_BASE = 0x5144
SCB_MSG_SLOT = 0x280
SCB_MSG_COUNT = 101
SCB_EXT_BASE = SCB_MSG_BASE + SCB_MSG_COUNT * SCB_MSG_SLOT + 0xA0   # 0x14E64


class ScbHandler:
    """Script files: 520 opcodes, 101 message slots of 640 bytes, optional data tables."""
    kind = 'scb'

    def extract(self, d):
        out = []
        for k in range(SCB_MSG_COUNT):
            a = SCB_MSG_BASE + k * SCB_MSG_SLOT
            z = d.find(b'\0', a, a + SCB_MSG_SLOT)
            s = d[a:z]
            if is_japanese(s):
                out.append(Entry('%X' % a, SCB_MSG_SLOT - 1, decode(s)))
        if len(d) > SCB_EXT_BASE:
            strs = find_strings(d, SCB_EXT_BASE, len(d))
            caps = column_capacities(d, strs, SCB_EXT_BASE, len(d))
            for a, b in strs:
                out.append(Entry('%X' % a, caps[a][0], decode(d[a:b])))
        return out

    def build(self, d, repl, caps):
        return patch_fixed(d, repl, caps)


def patch_fixed(d, repl, caps):
    d = bytearray(d)
    for key, enc in repl.items():
        a = int(key, 16)
        cap = caps[key]
        if len(enc) > cap:
            raise ValueError('%s: %d bytes > capacity %d' % (key, len(enc), cap))
        # clear old string (up to its NUL) then write new one + NUL
        z = d.find(b'\0', a)
        d[a:z] = bytes(z - a)
        d[a:a + len(enc)] = enc
        d[a + len(enc)] = 0
    return bytes(d)


# ---------------------------------------------------------------- record files

class RecordHandler:
    """[u32 size][text][00 00 00 00] repeated (kakugen, unchiku, newspaper, bottle mail).

    With extra=N, N extra u32 fields sit between size and text (uso_data)."""
    kind = 'rec'

    def __init__(self, extra=0):
        self.extra = extra

    def _parse(self, d):
        recs = []
        p = 0
        while p + 4 <= len(d):
            size, = struct.unpack_from('<I', d, p)
            if size < 8 + 4 * self.extra or p + size > len(d):
                raise ValueError('bad record at %X' % p)
            hdr = d[p + 4:p + 4 + 4 * self.extra]
            body = d[p + 4 + 4 * self.extra:p + size]
            z = body.find(b'\0')
            recs.append((hdr, body[:z], body[z:]))
            p += size
        if p != len(d):
            raise ValueError('trailing data')
        return recs

    def extract(self, d):
        out = []
        for i, (hdr, text, tail) in enumerate(self._parse(d)):
            if is_japanese(text):
                out.append(Entry('#%d' % i, 0, decode(text)))
        return out

    def build(self, d, repl, caps):
        out = bytearray()
        for i, (hdr, text, tail) in enumerate(self._parse(d)):
            t = repl.get('#%d' % i, text)
            body = hdr + t + tail
            out += struct.pack('<I', 4 + len(body)) + body
        return bytes(out)


def handler_for(path):
    p = path.replace('\\', '/').lower()
    if p.endswith('.scb'):
        return ScbHandler()
    if p.endswith('uso_data.bin'):
        return RecordHandler(extra=2)
    if any(k in p for k in ('misctext/', 'unchiku/', 'newsppr/', 'bottmail/')):
        return RecordHandler()
    if p.endswith('boot.bin') or p.endswith('.prx'):
        from elf import ElfHandler
        return ElfHandler()
    return None
