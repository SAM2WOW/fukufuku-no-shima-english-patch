"""Machine-assisted first-pass translation using the Codex CLI (`codex exec`).

Fills empty EN lines in text/**/*.txt. Results are cached in work/codex so the
script can be stopped and resumed at any time. Every answer is validated
(tags, byte limits, menu shape); failures are retried with the error message.

Usage:
    python tools/codex_translate.py [--jobs 6] [--batch 40] [--only PATTERN] [--limit N]
"""
import argparse
import concurrent.futures as cf
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textfile
import render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'work', 'codex')
EMPTY = os.path.join(ROOT, 'work', 'codex_cwd')

SCHEMA = {
    "type": "object",
    "properties": {"t": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "en": {"type": "string"}},
        "required": ["id", "en"], "additionalProperties": False}}},
    "required": ["t"], "additionalProperties": False}

PROMPT = """You are localizing the Japanese PSP game "Fukufuku no Shima" (Fukufuku Island, Sony 2005), a gentle life-sim about a fortune-telling island full of quirky characters, into natural, fun, idiomatic English for a fan translation patch.

Translate every item below. Rules:
1. Output JSON only, matching the schema: {{"t":[{{"id":..., "en":...}}, ...]}} with one object per input id.
2. Keep every control tag exactly as written, same count: <PN> (player name), <UN>, <UC>, <GN>, <NUM>, <ITEM>, <MONEY>, <HNUM>, <col.RED>, </col> etc. Never translate or invent tags.
3. <p> = new text page, <n> = line break. Keep the same pages (<p>) as the Japanese. Inside a page you may put <n> where natural; the patch re-wraps long lines automatically, so do not worry about line length.
4. Items marked "menu" are choice lists: keep exactly the same number of <n>-separated options, each short (ideally <= 20 characters).
5. Respect "max_bytes": the English (ASCII, 1 byte per char, each <n>/<p> counts 3) must not exceed it. Very small limits mean a short label - abbreviate if needed.
6. ASCII only: straight quotes, "..." for ellipses, no em dashes or accented letters. You may keep ♪ and ★ symbols.
7. Keep printf codes like %d %s exactly.
8. Preserve each character's personality and speech quirks (see glossary). The "file" field tells you which character/script the line comes from (e.g. hiyopi = Hiyopi, gk01 = a Skull Number, load2 = Nox's opening quiz, stony = the Stony Brothers, BOOT = system/menu/item text).
9. Japanese-specific wordplay or kanji/kana trivia: translate the meaning and adapt naturally; if the joke depends on Japanese script, keep it understandable (romanize briefly if needed).
10. If an item is clearly binary garbage or a programmer debug label that is not real text, return "<SKIP>".
11. Fortune-telling, trivia and quiz answers must stay factually consistent with the Japanese (a true/false quiz must stay true/false).
12. Items with a "window" field are shown in a small fixed text window ("7 lines x 40 chars" etc.). The patch word-wraps the English to that width; the wrapped text MUST fit in that many lines, so the English must be clearly shorter than lines x chars (aim for about 85% of it, counting spaces). Condense and paraphrase as needed, keep the key advice/meaning and the speaker's tone, drop filler. Do not use <n> in these.
13. Items with "previous_attempt" failed validation for the reason in "problem": fix exactly that problem.

GLOSSARY (follow strictly):
{glossary}

ITEMS (JSON lines):
{items}
"""

lock = threading.Lock()


def load_all(only=None):
    files = []
    for fn in sorted(glob.glob(os.path.join(ROOT, 'text', '**', '*.txt'), recursive=True)):
        if only and not re.search(only, fn.replace('\\', '/')):
            continue
        meta, ents = textfile.load(fn)
        files.append((fn, meta, ents))
    return files


def unit_info(meta, e):
    fmt = meta['format']
    kind = 'text'
    if fmt == 'scb' and int(e.key, 16) < 0x14E64:
        kind = 'dialogue'
    from layout import is_menu
    if is_menu(e.jp):
        kind = 'menu'
    return fmt, kind


def skip_jp(jp):
    return '<<' in jp or re.search(r'[\x00-\x08\x0b-\x1f]', jp) or re.search('[｡-ﾟ]', jp)


def build_units(files):
    """Unique JP strings needing translation, grouped by file in order."""
    seen = {}
    order = []
    for fn, meta, ents in files:
        src = os.path.splitext(os.path.basename(fn))[0]
        for e in ents:
            if e.en or skip_jp(e.jp):
                continue
            fmt, kind = unit_info(meta, e)
            u = seen.get(e.jp)
            if u is None:
                u = {'jp': e.jp, 'cap': e.cap, 'fmt': fmt, 'kind': kind, 'key': e.key,
                     'meta': meta, 'file': src}
                seen[e.jp] = u
                order.append(u)
            else:
                if e.cap and (not u['cap'] or e.cap < u['cap']):
                    u.update(cap=e.cap, fmt=fmt, key=e.key, meta=meta)
    return order


def batches(units, size, maxchars):
    cur, n, curfile = [], 0, None
    for u in units:
        if cur and (len(cur) >= size or n + len(u['jp']) > maxchars or u['file'] != curfile):
            yield cur
            cur, n = [], 0
        cur.append(u)
        n += len(u['jp'])
        curfile = u['file']
    if cur:
        yield cur


def run_codex(prompt, tag):
    os.makedirs(EMPTY, exist_ok=True)
    schema = os.path.join(WORK, 'schema.json')
    out = os.path.join(WORK, tag + '.out.json')
    cmd = ['codex', 'exec', '--skip-git-repo-check', '--ephemeral', '-s', 'read-only',
           '-C', EMPTY, '--output-schema', schema, '-o', out, '-']
    for attempt in range(3):
        try:
            p = subprocess.run(cmd, input=prompt.encode('utf-8'), stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=1800, shell=(os.name == 'nt'))
            if p.returncode == 0 and os.path.exists(out):
                with open(out, encoding='utf-8') as f:
                    return json.load(f)
            log = p.stdout.decode('utf-8', 'replace')[-2000:]
        except Exception as ex:      # timeout, bad JSON...
            log = repr(ex)
        with lock:
            print('  codex failed (%s, attempt %d): %s' % (tag, attempt + 1, log[-300:].replace('\n', ' ')))
        time.sleep(20 * (attempt + 1))
    return None


def translate_batch(batch, glossary, errors=None):
    items = []
    for i, u in enumerate(batch):
        d = {'id': str(i), 'file': u['file'], 'type': u['kind'], 'jp': u['jp']}
        if u['cap']:
            d['max_bytes'] = u['cap']
        box = render.window(u['fmt'], u['meta'], u['key'], u['jp'])
        if box:
            d['window'] = '%d lines x %d chars' % (box[1], box[0])
            if u['fmt'] == 'rec' and render.rec_box(u['meta'])[2]:
                d['window'] += ' (each item starts on a new line with "- ")' 
        if errors and u['jp'] in errors:
            d['previous_attempt'] = errors[u['jp']][0]
            d['problem'] = errors[u['jp']][1]
        items.append(json.dumps(d, ensure_ascii=False))
    prompt = PROMPT.format(glossary=glossary, items='\n'.join(items))
    tag = hashlib.sha1(prompt.encode('utf-8')).hexdigest()[:16]
    cache = os.path.join(WORK, tag + '.json')
    if os.path.exists(cache):
        with open(cache, encoding='utf-8') as f:
            res = json.load(f)
    else:
        res = run_codex(prompt, tag)
        if res is None:
            return {}, {u['jp']: ('', 'codex failed') for u in batch}
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=0)
    got = {r['id']: r['en'] for r in res.get('t', [])}
    ok, bad = {}, {}
    for i, u in enumerate(batch):
        en = got.get(str(i), '')
        if en.strip() == '<SKIP>':
            ok[u['jp']] = '<SKIP>'
            continue
        b, err = render.check(en, u['jp'], u['fmt'], u['key'], u['meta'], u['cap'])
        if err:
            bad[u['jp']] = (en, err)
        else:
            ok[u['jp']] = en
    return ok, bad


def failing_units(files):
    """Already translated entries that fail validation (too long for their
    field/window...), with the current English as the previous attempt."""
    units, errors, seen = [], {}, set()
    for fn, meta, ents in files:
        src = os.path.splitext(os.path.basename(fn))[0]
        for e in ents:
            if not e.en or e.en == '<SKIP>' or e.jp in seen:
                continue
            en = e.en.split('||')[0]
            b, err = render.check(en, e.jp, meta['format'], e.key, meta, e.cap)
            if err:
                seen.add(e.jp)
                fmt, kind = unit_info(meta, e)
                units.append({'jp': e.jp, 'cap': e.cap, 'fmt': fmt, 'kind': kind, 'key': e.key,
                              'meta': meta, 'file': src})
                errors[e.jp] = (e.en, err)
    return units, errors


def write_back(results, only=None, overwrite=()):
    n = 0
    for fn, meta, ents in load_all(only):
        changed = False
        for e in ents:
            if (not e.en or e.jp in overwrite) and e.jp in results and e.en != results[e.jp]:
                r = results[e.jp]
                if r == '<SKIP>':
                    continue
                b, err = render.check(r, e.jp, meta['format'], e.key, meta, e.cap)
                if err:          # same JP but a tighter field elsewhere
                    continue
                e.en = r
                changed = True
                n += 1
        if changed:
            textfile.save(fn, meta, ents)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--batch', type=int, default=40)
    ap.add_argument('--chars', type=int, default=3500)
    ap.add_argument('--only', default=None, help='regex on text file path')
    ap.add_argument('--limit', type=int, default=0, help='max batches (testing)')
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--refit', action='store_true',
                    help='re-translate existing entries that fail validation (too long etc.)')
    a = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    with open(os.path.join(WORK, 'schema.json'), 'w') as f:
        json.dump(SCHEMA, f)
    glossary = open(os.path.join(ROOT, 'glossary.md'), encoding='utf-8').read()

    overwrite = ()
    if a.refit:
        units, errors = failing_units(load_all(a.only))
        overwrite = set(errors)
    else:
        units, errors = build_units(load_all(a.only)), {}
    print('units to translate:', len(units), 'chars:', sum(len(u['jp']) for u in units))
    results = {}
    todo = units
    for rnd in range(a.rounds):
        bl = list(batches(todo, a.batch if rnd == 0 and not a.refit else 10, a.chars))
        if a.limit:
            bl = bl[:a.limit]
        print('round %d: %d batches' % (rnd + 1, len(bl)))
        done = 0
        t0 = time.time()
        with cf.ThreadPoolExecutor(a.jobs) as ex:
            futs = [ex.submit(translate_batch, b, glossary, errors if (rnd or a.refit) else None) for b in bl]
            for fu in cf.as_completed(futs):
                ok, bad = fu.result()
                with lock:
                    results.update(ok)
                    for k in ok:
                        errors.pop(k, None)
                    errors.update(bad)
                    done += 1
                    if done % 5 == 0 or done == len(bl):
                        el = time.time() - t0
                        print('  %d/%d batches, %d ok, %d failing, %.0fs elapsed, ~%.0fs left'
                              % (done, len(bl), len(results), len(errors), el,
                                 el / done * (len(bl) - done)), flush=True)
                    if done % 20 == 0:
                        write_back(dict(results), a.only, overwrite)
        n = write_back(results, a.only, overwrite)
        print('written %d entries' % n)
        todo = [u for u in units if u['jp'] in errors]
        if not todo:
            break
    with open(os.path.join(ROOT, 'work', 'codex_failures.json'), 'w', encoding='utf-8') as f:
        json.dump(errors, f, ensure_ascii=False, indent=1)
    print('remaining failures:', len(errors))


if __name__ == '__main__':
    main()
