"""Tiny ISO9660 reader/patcher for PSP UMD images (2048-byte sectors)."""
import struct

SECTOR = 2048


class IsoFile:
    __slots__ = ('path', 'lba', 'size', 'rec_off')

    def __init__(self, path, lba, size, rec_off):
        self.path, self.lba, self.size, self.rec_off = path, lba, size, rec_off


def list_files(f):
    """f: binary file object. Returns {UPPER/PATH: IsoFile}."""
    f.seek(16 * SECTOR)
    pvd = f.read(SECTOR)
    if pvd[1:6] != b'CD001':
        raise ValueError('not an ISO9660 image')
    root = pvd[156:156 + 34]
    files = {}

    def walk(lba, size, prefix):
        f.seek(lba * SECTOR)
        data = f.read(size)
        pos = 0
        while pos < len(data):
            ln = data[pos]
            if ln == 0:
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            ext, = struct.unpack_from('<I', data, pos + 2)
            sz, = struct.unpack_from('<I', data, pos + 10)
            flags = data[pos + 25]
            nlen = data[pos + 32]
            name = data[pos + 33:pos + 33 + nlen]
            if name not in (b'\0', b'\1'):
                n = name.decode('ascii').split(';')[0]
                p = prefix + n
                if flags & 2:
                    walk(ext, sz, p + '/')
                else:
                    files[p.upper()] = IsoFile(p, ext, sz, lba * SECTOR + pos)
            pos += ln

    walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')
    return files


def read_file(f, e):
    f.seek(e.lba * SECTOR)
    return f.read(e.size)


def volume_sectors(f):
    f.seek(16 * SECTOR + 80)
    return struct.unpack('<I', f.read(4))[0]


def write_file(f, e, data, append_lba_holder):
    """Write data for entry e into the image opened r+b.

    If it fits in the sectors the file already owns it is written in place,
    otherwise it is appended at the end of the image (append_lba_holder is a
    one-element list holding the next free LBA, updated in place).
    Directory record (extent + size) is updated accordingly."""
    owned = (e.size + SECTOR - 1) // SECTOR
    need = (len(data) + SECTOR - 1) // SECTOR
    lba = e.lba
    if need > owned:
        lba = append_lba_holder[0]
        append_lba_holder[0] += need
    f.seek(lba * SECTOR)
    f.write(data)
    pad = need * SECTOR - len(data)
    if pad:
        f.write(bytes(pad))
    # update directory record: extent (LE+BE) at +2, size (LE+BE) at +10
    f.seek(e.rec_off + 2)
    f.write(struct.pack('<I', lba) + struct.pack('>I', lba) + struct.pack('<I', len(data)) + struct.pack('>I', len(data)))
    e.lba, e.size = lba, len(data)


def set_volume_sectors(f, n):
    f.seek(16 * SECTOR + 80)
    f.write(struct.pack('<I', n) + struct.pack('>I', n))
