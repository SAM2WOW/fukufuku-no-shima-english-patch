<h1 align="center">Fukufuku no Shima – English Translation</h1>

<h4 align="center">A fan-made English translation patch for <b>Fukufuku no Shima</b> (福福の島, "Fukufuku Island") on the PlayStation Portable.</h4>

<p align="center">
  <a href="#installation">Installation</a> -
  <a href="#whats-translated">What's translated</a> -
  <a href="#building">Building</a> -
  <a href="#contributing">Contributing</a> -
  <a href="#credits">Credits</a> -
  <a href="#license">License</a>
</p>

Fukufuku no Shima (Sony Computer Entertainment, 2005) is a laid-back life game set on an island full of
fortune-tellers, quiz-loving princes, skeleton henchmen and very opinionated mushrooms. This project
translates the game's dialogue, menus, items, trivia, newspapers and UI graphics into English while
keeping everything else (including the Japanese name-entry keyboard) untouched.

> [!NOTE]
> The first pass of the translation was produced with AI assistance and is being proofread by humans.
> If you spot a mistranslation, odd phrasing or text that runs off the screen, please
> [open an issue](../../issues) with a screenshot, or fix it directly (see [Contributing](#contributing)).

## Installation

You need your own dump of the original Japanese UMD as an `.iso` file. The patch was made against:

| Game title | Fukufuku no Shima (Japan) |
|---|---|
| Platform | PlayStation Portable (UMD) |
| File size | 719,323,136 bytes |
| MD5 | `f4ade11283409fe9c524d10db1c1cee4` |

### Applying the xdelta patch

1. Download the latest `.xdelta` file from the [Releases page](../../releases).
2. Use any xdelta patcher, for example:
   - [Online xdelta patcher](https://kotcrab.github.io/xdelta-wasm/) (in your web browser)
   - [Delta Patcher](https://github.com/marco-calautti/DeltaPatcher) (Windows, macOS, Linux)
   - [xdelta UI](https://www.romhacking.net/utilities/598/) (Windows)
3. Choose your original `Fukufuku no Shima (Japan).iso` as the source file and the `.xdelta` as the patch,
   then save the result as a new `.iso`.

Keep a copy of the original ISO: you will need it again for future patch versions.

### Playing

* **PPSSPP** (Windows, macOS, Linux, Android, iOS): open the patched `.iso` from the Games tab.
* **Real PSP / PS Vita**: copy the patched `.iso` to `ISO/` on your memory card and run it with custom
  firmware (see the [ConsoleMods PSP wiki](https://consolemods.org/wiki/PSP:PSP_Mods_Wiki)).

Name entry still uses the original Japanese on-screen keyboard. You can type your name in kana or with
the full-width Latin letters on the keyboard's alphabet page.

## What's translated

| Part of the game | Status |
|---|---|
| Character dialogue (all NPC scripts) | Translated |
| Opening quiz, trivia (うんちく), maxims, fortunes | Translated |
| Daily newspapers and bottle mail | Translated |
| Item, clothing and furniture names and descriptions | Translated |
| Menus, system messages, place names | Translated |
| Button labels, result banners (Pass!/Fail, Hit!/Miss, Start!/Finish!), title menu | Redrawn in English |
| Name entry keyboard | Left in Japanese (on purpose) |
| Crossword puzzles | Left in Japanese – the puzzles are built on Japanese kana grids |
| Kanji / English-test questions that depend on Japanese writing | Translated where possible, otherwise left as-is |
| Loading-screen character bios, calligraphy rank certificates, network terms of service | Still Japanese (images) |
| Signs/text painted on 3D models | Not checked yet |

Known limitations:

* The profile page has room for only two letters of your Chinese zodiac sign, so it shows a short
  form (e.g. `Ho` for Horse). Everywhere else the full name is used.
* Birthdays are entered as Year／Month／Day, as in the original game (the prompt says so).

Tested in PPSSPP 1.20.4: title screen, opening, name/birthday/gender/blood-type entry, the main
menu, the item and fortune menus and the profile page. Please report anything that overflows a
window or looks wrong elsewhere.

## Building

The build reads your original ISO, inserts the English text and images, and writes a new ISO. It only
needs **Python 3.8+**; no other tools are required.

```
git clone https://github.com/<your-name>/fukufuku-no-shima-english.git
cd fukufuku-no-shima-english
```

Put `Fukufuku no Shima (Japan).iso` in the project folder, then run:

* Windows: `build.cmd` (double-click, or run it in Command Prompt / PowerShell)
* Linux/macOS: `./build.sh`

The patched game is written to `build/Fukufuku no Shima (English).iso`. Add `--xdelta` to also create a
distributable patch in the same folder, and `--strict` to stop on any text problem:

```
build.cmd --xdelta
./build.sh "/path/to/Fukufuku no Shima (Japan).iso" --xdelta
```

If some lines could not be inserted (too long for their slot, broken tags...) they stay in Japanese and
are listed in `build/text_problems.txt`.

## Contributing

### Project layout

| Path | Contents |
|---|---|
| `text/` | One translation file per game file (UTF-8). Mirrors the game's folder layout. |
| `textures/` | Edited images, as PNG. `file.gma@1940.png` means "the image at offset 0x1940 inside file.gma". |
| `glossary.md` | Character names, places and recurring terms. Please keep translations consistent with it. |
| `tools/` | Build scripts (pure Python): ISO patching, script/record/EXE text insertion, GIM image encoding, xdelta. |
| `tools/dev/` | Developer scripts used to redraw the UI textures (need Pillow). |
| `tools/extract.py` | Re-creates `text/` from an original ISO, keeping existing English lines. |
| `tools/codex_translate.py` | The machine-assisted first-pass translator (fills empty `EN:` lines). |

### Editing text

Each entry in a `text/**/*.txt` file looks like this:

```
@5144 max=639
JP: よーう。あんた、<PN>やろ？<n>ハハ、ワイは何でも知っとるでー。
EN: Hey there! You're <PN>, right?<n>Ha ha! Nothing gets past me!
```

* `@5144` is where the text lives in the game file, `max=` the number of bytes available. Don't change these.
* Only edit the `EN:` line. Leave it empty to keep the Japanese.
* `<n>` is a line break, `<p>` a new page (button press). Long lines are wrapped automatically at
  build time (44 characters, 2 lines per dialogue box).
* Keep all other tags exactly: `<PN>` = player name, `<UN>` = nickname, `<GN>` = skeleton number,
  `<NUM>`, `<ITEM>`, `<MONEY>` and similar insert values; `<col.RED>`…`</col>` changes colour.
* Use plain ASCII punctuation (`'` `"` `...`). ♪ and ★ are fine.
* `<SKIP>` means "never translate" (used for the name-entry keyboard's character tables).
* Some executable strings are shown by code that copies a fixed number of bytes. For those
  (marked with a `//` note) write `Full text||Short`: the full text is used where the game
  reads the string through a pointer, the short form where it copies it directly.
* Lines starting with `//` are notes for translators and are kept when the files are re-extracted.

Run the build afterwards. Any line that is too long or has broken tags is reported in
`build/text_problems.txt`.

### Technical notes

* Script files (`data/script/*.scb`) hold 520 opcodes of 40 bytes followed by 101 message slots of
  640 bytes at 0x5144, plus optional fixed-size data tables (quizzes, personality tests, fortunes).
  Text is Shift-JIS; the game renders ASCII with its half-width font (`start/fontA.gim`), so English
  needs no font hacking.
* Trivia, maxims, newspapers and bottle mail are `[u32 size][text][00 00 00 00]` records and are rebuilt.
* `BOOT.BIN` is patched in place (item/menu strings) and copied over the encrypted `EBOOT.BIN`, which
  PPSSPP and custom firmware run directly. String starts are taken from the program's own
  relocations (`lui`/`addiu` pairs and pointer tables), so text is never written a byte early.
  Strings reached through pointer tables can be longer than their slot: they are moved into space
  freed from debug-only log messages and the pointers are updated.
* Files that grow are relocated to the end of the ISO; everything else is patched in place, which keeps
  the xdelta small.

## Credits

* Translation project: _your name here_
* Toolchain and pipeline: built with Claude Code.
* First-pass translation: OpenAI Codex, guided by the project glossary.
* Proofreading: _contributors welcome!_
* Project structure inspired by the
  [Doko Demo Issyo PSP English translation](https://github.com/pumpkinhasapatch/dokodemo-psp-english).

## License

The code, text and images in this repository are available under the
[GNU General Public License](./LICENSE-GPL.txt) version 3 or later.

### Disclaimer

This is an unofficial fan translation. It is not affiliated with, approved or endorsed by Sony
Interactive Entertainment. No game data is distributed in this repository: you need your own legally
obtained copy of the game. Please support the original creators.
