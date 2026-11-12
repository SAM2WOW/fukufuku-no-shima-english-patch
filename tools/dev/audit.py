"""Before/after comparison sheets for every edited texture (developer aid).

python audit.py [name-filter]  ->  tools/dev/audit/<name>.png  (original | edited, zoomed)
"""
import glob
import os
import re
import sys

from PIL import Image
from texlib import load_from_iso, ROOT

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audit')
os.makedirs(OUT, exist_ok=True)
flt = sys.argv[1] if len(sys.argv) > 1 else ''
for png in sorted(glob.glob(os.path.join(ROOT, 'textures', '**', '*.png'), recursive=True)):
    rel = os.path.relpath(png, os.path.join(ROOT, 'textures')).replace('\\', '/')
    if flt not in rel:
        continue
    m = re.match(r'(.+?)(?:@([0-9a-fA-F]+))?\.png$', rel)
    orig = load_from_iso(m.group(1), int(m.group(2), 16) if m.group(2) else None)
    new = Image.open(png).convert('RGBA')
    # only the rows/cols that changed
    a, b = orig.load(), new.load()
    xs = [x for x in range(new.width) for y in range(0, new.height, 1) if a[x, y] != b[x, y]]
    if not xs:
        continue
    ys = [y for y in range(new.height) for x in range(new.width) if a[x, y] != b[x, y]]
    box = (max(0, min(xs) - 4), max(0, min(ys) - 4), min(new.width, max(xs) + 5), min(new.height, max(ys) + 5))
    z = 3 if box[2] - box[0] < 300 else 2
    o, n = orig.crop(box), new.crop(box)
    w, h = o.width * z, o.height * z
    sheet = Image.new('RGBA', (w * 2 + 8, h), (255, 0, 255, 255))
    for i, im in enumerate((o, n)):
        bg = Image.new('RGBA', im.size, (40, 40, 70, 255))
        bg.alpha_composite(im)
        sheet.paste(bg.resize((w, h), Image.NEAREST), (i * (w + 8), 0))
    name = rel.replace('/', '__').replace('.png', '')
    sheet.convert('RGB').save(os.path.join(OUT, name + '.png'))
    print(name, box)
