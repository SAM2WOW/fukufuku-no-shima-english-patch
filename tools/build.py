"""Build the English version of Fukufuku no Shima.

    python tools/build.py [original.iso] [--xdelta] [--strict]

* copies the original ISO to build/
* inserts the English text from text/**/*.txt
* inserts the edited textures from textures/**.png
* writes the patched BOOT.BIN over EBOOT.BIN and USRDIR/aki.psp.prx
* optionally writes an .xdelta patch for distribution
"""
import argparse
import glob
import hashlib
import os
import re
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formats
import gim
import iso9660
import layout
import pngio
import render
import textfile
import vcdiff

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED_MD5 = 'f4ade11283409fe9c524d10db1c1cee4'
OUT_NAME = 'Fukufuku no Shima (English).iso'


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def find_iso(arg):
    if arg:
        return arg
    isos = [p for p in glob.glob(os.path.join(ROOT, '*.iso')) if 'English' not in p]
    if not isos:
        sys.exit('Put your original "Fukufuku no Shima (Japan).iso" in %s' % ROOT)
    return isos[0]


def text_patches(original, report, strict, only=None):
    """Returns {iso_path_upper: new_bytes} for every text container."""
    out = {}
    nent = ntr = 0
    for fn in sorted(glob.glob(os.path.join(ROOT, 'text', '**', '*.txt'), recursive=True)):
        if only and not re.search(only, fn.replace(os.sep, '/')):
            continue
        meta, ents = textfile.load(fn)
        path = meta['source']
        h = formats.handler_for(path)
        data = original(path)
        caps = {x.key: x.cap for x in h.extract(data)}
        repl, short = {}, {}
        for e in ents:
            nent += 1
            if not e.en or e.en == '<SKIP>':
                continue
            en = e.en
            if '||' in en and meta['format'] == 'elf':
                # "Full name||Short": full text for pointer users, short form
                # left in the original slot for code that copies fixed bytes
                en, sh = en.split('||', 1)
                short[e.key] = layout.encode(sh)
            if e.key not in caps:
                report.append('%s @%s: entry no longer exists in the game file' % (path, e.key))
                continue
            b, err = render.check(en, e.jp, meta['format'], e.key, meta, caps[e.key])
            if err:
                report.append('%s @%s: %s' % (os.path.relpath(fn, ROOT), e.key, err))
                continue
            repl[e.key] = b
            ntr += 1
        if repl:
            out[path.upper()] = h.build(data, repl, caps, short) if short else h.build(data, repl, caps)
    print('text: %d/%d entries translated' % (ntr, nent))
    if strict and report:
        sys.exit('\n'.join(report))
    return out


def texture_patches(original, patched):
    """textures/<path under PSP_GAME>/<file>.png  or  <file>@<hexoffset>.png
    (for images inside .gma/.cts archives)."""
    n = 0
    for png in sorted(glob.glob(os.path.join(ROOT, 'textures', '**', '*.png'), recursive=True)):
        rel = os.path.relpath(png, os.path.join(ROOT, 'textures')).replace('\\', '/')
        m = re.match(r'(.+?)(?:@([0-9a-fA-F]+))?\.png$', rel)
        name, off = m.group(1), m.group(2)
        path = ('PSP_GAME/' + name).upper()
        data = bytearray(patched.get(path) or original(path))
        w, h, rgba = pngio.read_png(png)
        if off is None:
            data = bytearray(gim.encode_into(bytes(data), rgba, keep_palette=True))
        else:
            o = int(off, 16)
            size = int.from_bytes(data[o + 0x14:o + 0x18], 'little') + 0x10
            data[o:o + size] = gim.encode_into(bytes(data[o:o + size]), rgba, keep_palette=True)
        patched[path] = bytes(data)
        n += 1
    print('textures: %d images' % n)


GAME_TITLE = 'Fukufuku no Shima (English)'


def update_file_table(exe, moves):
    """Rewrite the executable's own file table. Each entry holds the file's
    start sector and byte size right after each other; replace every aligned
    (old sector, old size) pair by the new values. Every changed file must be
    found exactly once, otherwise the game would still read the old copy."""
    exe = bytearray(exe)
    for (olba, osz), (nlba, nsz) in moves.items():
        pat = struct.pack('<II', olba, osz)
        hits = []
        i = exe.find(pat)
        while i >= 0:
            if i % 4 == 0:
                hits.append(i)
            i = exe.find(pat, i + 1)
        if len(hits) != 1:
            raise SystemExit('file table: expected one entry for sector %d size %d, found %d' % (olba, osz, len(hits)))
        struct.pack_into('<II', exe, hits[0], nlba, nsz)
    return bytes(exe)


def patch_sfo_title(d, title):
    """Set the TITLE shown in the PSP menu / PPSSPP game list."""
    d = bytearray(d)
    _, _, kt, dt, n = struct.unpack_from('<4sIIII', d, 0)
    for i in range(n):
        ko, fmt, ln, mx, do = struct.unpack_from('<HHIII', d, 20 + i * 16)
        key = d[kt + ko:d.index(b'\0', kt + ko)]
        if key == b'TITLE':
            v = title.encode('utf-8') + b'\0'
            v = v[:mx]
            d[dt + do:dt + do + mx] = v + bytes(mx - len(v))
            struct.pack_into('<I', d, 20 + i * 16 + 4, len(v))
    return bytes(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('iso', nargs='?')
    ap.add_argument('--xdelta', action='store_true', help='also write build/*.xdelta')
    ap.add_argument('--strict', action='store_true', help='fail on any text problem')
    ap.add_argument('--only', help='(testing) only insert text files whose path matches this regex')
    ap.add_argument('--no-textures', action='store_true', help='(testing) skip texture replacement')
    ap.add_argument('--out', default=os.path.join(ROOT, 'build', OUT_NAME))
    a = ap.parse_args()

    src = find_iso(a.iso)
    print('original:', src)
    h = md5(src)
    if EXPECTED_MD5 != 'REPLACE_ME' and h != EXPECTED_MD5:
        print('WARNING: MD5 %s does not match the expected %s (bad dump or already patched?)' % (h, EXPECTED_MD5))

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    fsrc = open(src, 'rb')
    files = iso9660.list_files(fsrc)
    cache = {}

    def original(path):
        k = path.upper()
        if k not in cache:
            cache[k] = iso9660.read_file(fsrc, files[k])
        return cache[k]

    report = []
    patched = text_patches(original, report, a.strict, a.only)
    if not a.no_textures:
        texture_patches(original, patched)

    patched['PSP_GAME/PARAM.SFO'] = patch_sfo_title(original('PSP_GAME/PARAM.SFO'), GAME_TITLE)

    EXE = 'PSP_GAME/SYSDIR/BOOT.BIN'
    EXE_COPIES = ['PSP_GAME/SYSDIR/EBOOT.BIN', 'PSP_GAME/USRDIR/AKI.PSP.PRX']
    boot = patched.pop(EXE, None) or original(EXE)

    print('copying ISO...')
    shutil.copyfile(src, a.out)
    with open(a.out, 'r+b') as f:
        files = iso9660.list_files(f)
        nxt = [iso9660.volume_sectors(f)]
        # 1. data files first: they may grow and move to the end of the disc
        moves = {}
        for path, data in sorted(patched.items()):
            e = files[path]
            old = (e.lba, e.size)
            iso9660.write_file(f, e, data, nxt)
            if (e.lba, e.size) != old:
                moves[old] = (e.lba, e.size)
                print('  moved/resized:', path)
        # 2. the game does not use the ISO directory: the executable keeps its
        #    own table of {name pointer, start sector, size} per file. Point it
        #    at the new location/size of every file that changed.
        boot = update_file_table(boot, moves)
        # 3. then the executable itself (same size, in place)
        for path in [EXE] + EXE_COPIES:
            iso9660.write_file(f, files[path], boot, nxt)
        iso9660.set_volume_sectors(f, nxt[0])
    print('wrote', a.out, '(%d files changed, %d file-table entries updated)' % (len(patched) + 3, len(moves)))

    if report:
        rp = os.path.join(os.path.dirname(a.out), 'text_problems.txt')
        with open(rp, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report) + '\n')
        print('%d text entries were skipped (kept Japanese), see %s' % (len(report), rp))

    if a.xdelta:
        # same name as the GitHub release asset, so the README's
        # releases/latest/download/... link keeps working for new versions
        xd = os.path.join(os.path.dirname(a.out), 'Fukufuku.no.Shima.English.xdelta')
        print('creating', xd)
        vcdiff.encode(open(src, 'rb').read(), open(a.out, 'rb').read(), xd)
        print('xdelta size: %d bytes' % os.path.getsize(xd))


if __name__ == '__main__':
    main()
