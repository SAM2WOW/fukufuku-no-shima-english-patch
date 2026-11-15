"""Read and translate the loading-screen character bios (title/l01-l56.gim).

The bios are drawn into the images, so the Japanese is read from the pictures
by the Codex CLI (image input) and translated in the same step. Results go to
tools/dev/loading_bios.json (edit the English there; tex_loading.py draws it).

    python tools/dev/loading_ocr.py [--jobs 4]
"""
import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from texlib import load_from_iso      # noqa: E402

WORK = os.path.join(ROOT, 'work', 'loading')
OUT = os.path.join(HERE, 'loading_bios.json')
SCHEMA = {
    "type": "object",
    "properties": {"bios": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "jp": {"type": "string"},
                       "name": {"type": "string"}, "en": {"type": "string"}},
        "required": ["id", "jp", "name", "en"], "additionalProperties": False}}},
    "required": ["bios"], "additionalProperties": False}

PROMPT = """These images are loading screens of the Japanese PSP game "Fukufuku no Shima" (Fukufuku Island), a gentle life-sim about a fortune-telling island. Each image shows one character and a short Japanese profile: a title line starting with ■ (the character's name) and a few lines of description.

For each image (ids in order: {ids}):
1. "jp": transcribe the Japanese exactly (title line first, lines joined with \\n).
2. "name": the English name for the title line, without the ■ (follow the glossary).
3. "en": a natural, fun English translation of the description (not the title), as one paragraph. It must fit in a small area, so keep it about the same length as a literal translation or shorter (aim for at most 260 characters). ASCII only, straight quotes.
Output JSON only, matching the schema.

GLOSSARY (follow strictly):
{glossary}
"""


def crops():
    os.makedirs(WORK, exist_ok=True)
    files = []
    for n in range(1, 57):
        p = os.path.join(WORK, 'l%02d.png' % n)
        if not os.path.exists(p):
            img = load_from_iso('USRDIR/data/title/l%02d.gim' % n)
            img.resize((img.width * 2, img.height * 2)).save(p)
        files.append(p)
    return files


def run(batch, glossary):
    ids = [os.path.splitext(os.path.basename(p))[0] for p in batch]
    out = os.path.join(WORK, '_'.join(ids) + '.json')
    if os.path.exists(out):
        return json.load(open(out, encoding='utf-8'))
    schema = os.path.join(WORK, 'schema.json')
    cmd = ['codex', 'exec', '--skip-git-repo-check', '--ephemeral', '-s', 'read-only', '-C', WORK,
           '--output-schema', schema, '-o', out]
    for p in batch:
        cmd += ['-i', p]
    cmd += ['-']
    prompt = PROMPT.format(ids=', '.join(ids), glossary=glossary)
    for attempt in range(3):
        r = subprocess.run(cmd, input=prompt.encode('utf-8'), stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=1800, shell=(os.name == 'nt'))
        if r.returncode == 0 and os.path.exists(out):
            return json.load(open(out, encoding='utf-8'))
        print('codex failed', ids, r.stdout.decode('utf-8', 'replace')[-400:])
    return {'bios': []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--batch', type=int, default=4)
    a = ap.parse_args()
    files = crops()
    json.dump(SCHEMA, open(os.path.join(WORK, 'schema.json'), 'w'))
    glossary = open(os.path.join(ROOT, 'glossary.md'), encoding='utf-8').read()
    old = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
    todo = [p for p in files if os.path.splitext(os.path.basename(p))[0] not in old]
    batches = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for res in ex.map(lambda b: run(b, glossary), batches):
            for b in res['bios']:
                old[b['id']] = {'jp': b['jp'], 'name': b['name'], 'en': b['en']}
            print(len(old), 'bios', flush=True)
    json.dump(dict(sorted(old.items())), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('missing:', [n for n in ('l%02d' % i for i in range(1, 57)) if n not in old])


if __name__ == '__main__':
    main()
