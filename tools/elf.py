"""Text in the game executable (BOOT.BIN, a relocatable PSP PRX/ELF).

Strings are patched in place. Strings that are reached through pointer
tables (PRX R_MIPS_32 relocations into segment 0) may be longer than their
slot: they are moved into space freed from debug-only printf messages and
the table pointers are updated.
"""
import re
import struct

from formats import Entry, SJIS_DBL, find_strings, column_capacities, is_japanese, decode, patch_fixed

PRX_RELOC = 0x700000A0
R_MIPS_32 = 2


class ElfHandler:
    kind = 'elf'
    RELOC_MAX = 63                                   # max bytes for a relocatable string
    DATE_MARKERS = (0x2299C8, 0x2299CC, 0x2299D0)    # 年 月 日 of the birthday entry
    # Field sizes checked by hand where the automatic table detection cannot
    # prove them (string offset: bytes available excluding the NUL).
    CAP_OVERRIDES = {
        0x2421B4: 79,     # 福福先生: character record, name field ends at the int at +0x50
        0x1F1FE4: 19,     # 賢者の像: item category record, name ends at the id at +0x14
        0x1F2024: 19,     # 髪型: same table
        0x2A74C4: 31,     # 起動回数: stats list, 0x20-byte entries
    }

    # ------------------------------------------------------------ ELF layout
    def _shdrs(self, d):
        shoff, = struct.unpack_from('<I', d, 0x20)
        shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x2E)
        return [struct.unpack_from('<IIIIII', d, shoff + i * shentsize) for i in range(shnum)], shstrndx

    def sections(self, d):
        shdrs, shstrndx = self._shdrs(d)
        stro = shdrs[shstrndx][4]
        res = {}
        for nm, typ, flags, addr, off, size in shdrs:
            name = d[stro + nm:d.index(b'\0', stro + nm)].decode()
            res[name] = (off, off + size)
        return res

    def segments(self, d):
        phoff, = struct.unpack_from('<I', d, 0x1C)
        phnum, = struct.unpack_from('<H', d, 0x2C)
        segs = []
        for i in range(phnum):
            typ, off, vaddr, paddr, filesz, memsz, flags, align = struct.unpack_from('<8I', d, phoff + i * 32)
            segs.append((off, vaddr, filesz))
        return segs

    def pointer_slots(self, d):
        """{string file offset: [file offsets of the 32-bit words pointing at it]}"""
        segs = self.segments(d)
        seg0_off, seg0_va, _ = segs[0]
        shdrs, _ = self._shdrs(d)
        refs = {}
        for nm, typ, flags, addr, off, size in shdrs:
            if typ != PRX_RELOC:
                continue
            for k in range(0, size, 8):
                r_off, info = struct.unpack_from('<II', d, off + k)
                if info & 0xFF != R_MIPS_32 or (info >> 16) & 0xFF != 0:
                    continue
                ofsbase = (info >> 8) & 0xFF
                if ofsbase >= len(segs):
                    continue
                word = segs[ofsbase][0] + r_off
                if word + 4 > len(d):
                    continue
                target_va, = struct.unpack_from('<I', d, word)
                refs.setdefault(target_va - seg0_va + seg0_off, []).append(word)
        return refs

    def code_targets(self, d):
        """File offsets that the code loads as addresses (lui/addiu pairs
        described by R_MIPS_HI16 / R_MIPS_LO16 relocations)."""
        segs = self.segments(d)
        seg0_off, seg0_va, _ = segs[0]
        shdrs, _ = self._shdrs(d)
        targets = set()
        for nm, typ, flags, addr, off, size in shdrs:
            if typ != PRX_RELOC:
                continue
            hi = None
            for k in range(0, size, 8):
                r_off, info = struct.unpack_from('<II', d, off + k)
                t = info & 0xFF
                ofsbase = (info >> 8) & 0xFF
                if ofsbase >= len(segs) or (info >> 16) & 0xFF != 0:
                    continue
                word = segs[ofsbase][0] + r_off
                if word + 4 > len(d):
                    continue
                ins, = struct.unpack_from('<I', d, word)
                if t == 5:                                   # R_MIPS_HI16
                    hi = ins & 0xFFFF
                elif t == 6 and hi is not None:              # R_MIPS_LO16
                    lo = ins & 0xFFFF
                    va = ((hi << 16) + (lo - 0x10000 if lo & 0x8000 else lo)) & 0xFFFFFFFF
                    targets.add(va - seg0_va + seg0_off)
        return targets

    # ------------------------------------------------------------- strings
    def _strings(self, d):
        secs = self.sections(d)
        known = set(self.pointer_slots(d)) | self.code_targets(d)
        found = []
        for name in ('.rodata', '.data'):
            lo, hi = secs[name]
            strs = []
            for a, b in find_strings(d, lo, hi, 1):
                if d[a - 1] != 0:
                    continue
                # bytes that can never start real text (0xFF.. of an int -1,
                # float tails, control codes) belong to the previous field
                while a < b and (d[a] in (0x80, 0xA0, 0xFD, 0xFE, 0xFF) or d[a] < 0x20):
                    a += 1
                if b - a < 2:
                    continue
                # A lone single-byte char glued in front of the Japanese is the
                # tail of the previous field (e.g. the 0x41 of float 16.0), not
                # part of the string: "Aはい" is really "はい". Strings here are
                # 4-byte aligned, so an unaligned run whose Japanese starts at
                # the next boundary carries such junk.
                if a % 4:
                    na = (a + 3) & ~3
                    junk = d[a:na]
                    if a in known:
                        pass                                 # the program really uses this start
                    elif na in known and na + 1 < b:
                        a = na                               # the program loads the aligned start
                    elif na + 1 < b and 0x81 <= d[na] <= 0xEF and is_japanese(d[na:b]) \
                            and not any(0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF for c in junk):
                        a = na
                strs.append((a, b))
            found.append((lo, hi, strs))
        return found

    def extract(self, d, with_inplace=False):
        out = []
        refs = self.pointer_slots(d)
        seg1_off = self.segments(d)[1][0]
        for lo, hi, strs in self._strings(d):
            multi = [(a, b) for a, b in strs if len(SJIS_DBL.findall(d[a:b])) >= 2]
            caps = column_capacities(d, multi, lo, hi)
            for a, b in strs:
                s = d[a:b]
                if len(SJIS_DBL.findall(s)) < 2:
                    try:
                        t = decode(s)
                    except UnicodeDecodeError:
                        continue
                    # single characters: only a kanji (or ？) reached through a
                    # pointer table, plus the birthday date markers. Never kana
                    # or letters - those are the name-entry keyboard tables.
                    table_char = len(t) == 1 and a in refs and ('一' <= t <= '鿿' or t == '？')
                    if not table_char and a not in self.DATE_MARKERS:
                        continue
                    cap = ((b + 1 + 3) & ~3) - a - 1
                else:
                    cap, in_table = caps[a]
                    # stand-alone C strings: only use the alignment padding, never
                    # spill into what could be a zeroed variable.
                    if not in_table:
                        cap = min(cap, ((b + 1 + 3) & ~3) - a - 1)
                cap = self.CAP_OVERRIDES.get(a, cap)
                inplace = cap
                if a in refs and a < seg1_off:
                    cap = max(cap, self.RELOC_MAX)
                e = Entry('%X' % a, cap, decode(s))
                if with_inplace:
                    e.width = inplace
                out.append(e)
        return out

    def free_pool(self, d):
        """Aligned slots of debug-only printf messages that can be reused."""
        lo, hi = self.sections(d)['.rodata']
        pool = []
        for m in re.finditer(rb'(?<=\x00)[\x20-\x7e\x0a\x09]{12,}\x00', d[lo:hi]):
            s = m.group()[:-1]
            # Only text that is plainly a log message: real words, ends in a
            # newline or mentions an error. Never pure format strings (e.g. the
            # %02x... hex formatter), file name patterns or paths.
            letters = len(re.findall(rb'[A-Za-z]{3,}', s))
            log_like = s.endswith(b'\n') or any(k in s for k in (b'rror', b'ERROR', b'ailed', b'Faild', b'!!'))
            filey = re.search(rb'\.(gim|gma|cts|bin|scb|at3|prx|vag|cto|ini|htm|dat|txt)', s, re.I) or b'/' in s or b'\\' in s
            if log_like and letters >= 2 and not filey and not s.startswith(b'%') and b':' not in s[:6] \
                    and len(re.findall(rb'%', s)) * 4 < len(s):
                a = lo + m.start()
                z = d.find(b'\0', a)
                pool.append([a, (z + 1 + 3) & ~3])
        return pool

    def build(self, d, repl, caps, short=None):
        """short: {key: bytes} text to leave in the original slot when a
        string is relocated (for code that copies a fixed number of bytes)."""
        short = short or {}
        inplace_cap = {e.key: e.width for e in self.extract(d, with_inplace=True)}
        refs = self.pointer_slots(d)
        inplace, moved = {}, {}
        for key, enc in repl.items():
            (inplace if len(enc) <= inplace_cap[key] else moved)[key] = enc
        d = bytearray(patch_fixed(d, inplace, inplace_cap))
        if moved:
            pool = self.free_pool(bytes(d))
            seg0_off, seg0_va, _ = self.segments(bytes(d))[0]
            for key, enc in sorted(moved.items(), key=lambda kv: -len(kv[1])):
                need = len(enc) + 1
                slot = next((p for p in pool if p[1] - p[0] >= need), None)
                if slot is None:
                    raise ValueError('out of relocation space for %s' % key)
                a = slot[0]
                d[a:slot[1]] = bytes(slot[1] - a)
                d[a:a + len(enc)] = enc
                slot[0] = (a + need + 3) & ~3
                old = int(key, 16)
                for word in refs[old]:
                    struct.pack_into('<I', d, word, a - seg0_off + seg0_va)
                # keep a shortened copy in the old slot for any direct code use
                z = d.find(b'\0', old)
                d[old:z] = bytes(z - old)
                cut = short.get(key, enc)[:inplace_cap[key]]
                while cut:
                    try:
                        cut.decode('cp932')
                        break
                    except UnicodeDecodeError:
                        cut = cut[:-1]
                d[old:old + len(cut)] = cut
        return bytes(d)
