# batchocr

**Turn a folder of mixed documents into plain text in one command.** PDFs,
scans, photos, Word and PowerPoint files, and ebooks all become `.txt`/`.md`
files. For each file, `batchocr` decides whether it needs OCR or already has
real text.

```console
$ batchocr inbox/ -o text/
[done, OCR] photo-of-board.png -> photo-of-board.txt (200 chars) | time 00:00:00
[hybrid] scanned-handout.pdf: 0/1 pages pass the text-layer check; OCR for page 1
[hybrid] typed-notes.pdf: 1/1 pages pass the text-layer check, OCR check on page 1: 100% word overlap
[done, native] typed-notes.pdf -> typed-notes.txt (392 chars, 1 pages) | time 00:00:00
[info] OCR queue: 1 pages across 1 file(s), auto workers, 300 dpi, lang=eng
[progress] 1/1 pages OCR'd | elapsed 00:00:02 | last 1 pages in 00:00:01
[done, OCR] scanned-handout.pdf -> scanned-handout.txt (218 chars, 1 pages) | time 00:00:01
```

In that run, the typed PDF already had a clean text layer, so it was
extracted instantly and exactly. The scanned PDF had no usable text, so its
pages were OCRed. The photo was OCRed directly.

## Why

- **OCR is slow and lossy, but sometimes necessary.** Running Tesseract on
  a PDF that already contains real text wastes minutes and swaps exact text
  for recognition errors. Skipping OCR on a scan gives you nothing, or
  garbage. `batchocr` scores every page's text layer (are the characters
  plausible text?) and OCRs one sampled page to check that the layer says
  what the page shows. Pages that pass keep their exact text; the rest are
  OCRed, so a PDF that mixes typed and scanned pages is handled page by page.
- **Real folders are mixed.** One tool needs to handle the PDF, the
  PowerPoint, the phone photo and the `.epub` alike, and pick the right
  backend for each.
- **It's built for reruns.** Finished outputs are skipped, and `-a` moves
  each processed source out of the input folder. You can keep dropping
  files into an inbox folder and rerun the same command.

## Install

`batchocr` is a single Python file for plain-text extraction. PDF to Markdown
(`--to md`) also uses the bundled `m1ck4_pdfmd/` folder next to it (see
[Credits](#credits)).

**Requirements:**
- Python 3.10+
- On macOS:
  ```sh
  brew install poppler tesseract pandoc          # PDFs, images, Office files
  brew install tesseract-lang                    # more OCR languages
  brew install --cask calibre libreoffice        # ebooks, legacy Office formats
  ```
  On Linux, install the equivalents of `pdftotext`/`pdftoppm` (poppler),
  `tesseract` and `pandoc` from your package manager.

Calibre and LibreOffice are only needed for the formats that use them
(see below).

```sh
git clone https://github.com/aliperdehan/batchocr.git ~/batchocr
echo 'alias batchocr="python3 ~/batchocr/batchocr.py"' >> ~/.zshrc   # or ~/.bashrc
```

Or install the command with pip, straight from a release tag (not on PyPI):

```sh
pip install "git+https://github.com/aliperdehan/batchocr.git@v1.2.1"
pip install "batchocr[md] @ git+https://github.com/aliperdehan/batchocr.git@v1.2.1"   # with PDF -> Markdown
```

PDF to Markdown needs **PyMuPDF** (`pip install pymupdf`, which is what the
`md` extra installs). PyMuPDF is AGPL-3.0 licensed, so batchocr does not bundle
it: it is a separate, optional install, and everything else, including plain
text from PDFs, works without it.

## Usage

### One file

```sh
batchocr handout.pdf                  # -> handout.txt beside it
batchocr handout.pdf -o out/          # -> out/handout.txt
batchocr handout.pdf -o notes.txt     # -> exactly notes.txt
batchocr scan.png                     # an image is OCRed directly
batchocr handout.pdf --stdout | grep -i entropy   # print the text instead of saving it
```

With `--stdout`, only the extracted text goes to standard output. Progress
messages go to standard error, so the output is safe to pipe.

### A folder

```sh
batchocr inbox/                       # everything merged into inbox.txt
batchocr inbox/ -o text/              # one output per source, in text/
batchocr inbox/ -o text/ -a inbox/done   # ...and move each source into inbox/done when finished
batchocr pages/                       # page1.png, page2.png, ... page10.png -> pages.txt, in page order
```

A folder with no `-o` is merged into one file. Each source gets its own
heading:

```text
=== photo-of-board.png ===
...
=== scanned-handout.pdf ===
...
```

Running the command again skips any file whose output already exists.
Use `--force` to redo them.

### Several files, one result

```sh
batchocr a.pdf b.pdf c.pdf -o out/            # out/a.txt, out/b.txt, out/c.txt
batchocr a.pdf b.pdf -o all.txt --concat      # one file, one "=== a.pdf ===" section each
```

With several inputs, `-o` is always treated as a folder unless you add
`--concat`, so an existing file can never be overwritten by mistake.

### Tuning OCR

```sh
batchocr inbox/ --quality-threshold 0.85   # OCR more readily (default 0.75)
batchocr inbox/ --no-ocr-check             # skip the sampled-page OCR cross-check (faster)
batchocr paper.pdf --layout                # old `pdftotext -layout` rows instead of reading order
batchocr old-scan.pdf --full-ocr           # always OCR, ignoring any text layer
batchocr inbox/ --dpi 400                  # sharper rendering for small print (default 300)
batchocr inbox/ --lang eng+rus             # several Tesseract languages
batchocr inbox/ -j 4                       # number of parallel OCR workers (default: all cores)
```

`--full-ocr` forces OCR on every page. It is rarely needed now: a text layer
with a broken font encoding (symbols and accented junk where the words should
be) fails the character check, and a layer that looks like words but does not
match the page fails the OCR cross-check, so those PDFs fall back to OCR
automatically.

Native text comes out in reading order (the exact text can differ a little
with and without PyMuPDF installed, because the two readers format and order
blocks differently): whole columns, tables row by row as
the PDF stores them. With PyMuPDF installed (`pip install pymupdf`, optional)
batchocr uses its content-stream order; without it, plain `pdftotext`. Pass
`--layout` to get the pre-1.2.0 `pdftotext -layout` output, which keeps
visual rows (useful for a fixed-width table) but interleaves columns line by
line.

OCR quality depends first on the language pack. A Kazakh page read with
`--lang rus` scores a word F1 of about 0.40 against its true text, with
`--lang kaz+rus` about 0.80, and page segmentation mode or DPI changes
barely matter; Ukrainian needs `ukr`, Portuguese `por`, and so on
(`tesseract --list-langs` shows what is installed; a missing pack is an error).

OCR is not perfect. In the example above, Tesseract read `ΔS` as `AS`.
Where a PDF has a good text layer, `batchocr` uses it instead, and that
text is exact.

### PDF to Markdown

```sh
batchocr paper.pdf --to md                 # -> paper.md
batchocr paper.pdf -t md -o notes/paper.md --lang eng+rus
batchocr scans/ --to md -o md/             # one .md per PDF
batchocr paper.pdf --to md --stdout | less
```

Markdown mode produces headings (from font size, or from line height in OCR),
bold and italic, lists, tables, and `$$ ... $$` math where it recognises it,
with paragraphs re-flowed and line-end hyphens repaired. It reads text per
page, so a PDF that mixes typed and scanned pages is handled page by page:

| Page type | What happens |
|---|---|
| Typed (text layer passes the check) | PyMuPDF reads the text blocks in stream order (columns come out whole) with font size, bold and italic |
| Scanned, or a broken text layer | Tesseract at `--dpi`; paragraphs and reading order come from Tesseract's layout analysis, heading candidates from line height (never from low-confidence lines) |

- **Page markers.** Each page starts with an HTML comment `<!-- Page 12 -->`
  (with the printed label if it differs, `<!-- Page 150 (3-12) -->`), which is
  invisible when rendered. `--no-page-markers` drops them; `--page-breaks`
  adds a `---` rule between pages.
- **Running headers, footers and page numbers** are removed when the PDF has 4
  or more pages: only lines in the top or bottom 12% of the page that repeat
  on at least 40% of the pages (and at least 3), or bare page numbers there.
  The run prints what it removed; a repeated line that is really content (a
  form field label at the top of every page, say) can be mistaken for a
  header, so `--keep-headers` turns the removal off.
- **Nothing is dropped silently.** Every page is rendered, then checked: if the
  Markdown no longer holds the page's letters and digits (for example a table
  or math detector swallowed text), that page is re-rendered without table and
  math detection, and the run says so. A "table" whose cells are sentences is
  rendered as the paragraph it is.
- **Provenance.** The file ends with `<!-- text extracted with batchocr v1.2.4 -->`
  (version only, so reruns stay byte-identical); `--no-provenance` leaves it out.
- **Reruns** give byte-identical output.
- Without PyMuPDF the run stops with a one-line message and a non-zero exit
  status; plain-text mode is unaffected.

Flags borrowed from [M1ck4's `pdfmd`](https://github.com/M1ck4/pdfmd) work the
same here: `--output`, `--ocr {off,auto,tesseract,ocrmypdf}`, `--lang`,
`--export-images` (images to `<name>_assets/`, links appended),
`--page-breaks`, `--preview-only` (first 3 pages), `--no-progress`, `-q`,
`-v`, `--stats`, `--no-color`, `--version`. Differences: `--ocr` defaults to
`auto` (the per-page hybrid) rather than `off`; `-s` is still `--stdout`,
`-c` `--concat` and `-j` `--jobs`; `--ocr` and the other options also work in
plain-text mode. Exit status is 0 on success and non-zero if any file failed.

### Plain text to Markdown

```sh
batchocr notes.txt --to md                 # -> notes.md
batchocr notes.txt --to md --txt-structure off      # paragraphs only
```

A `.txt` file has no fonts, so structure is guessed from how people type: a short line in capitals, `1.2 Title`, an
underline of `====`, bullets and numbered runs, columns separated by runs of spaces (a table), indented blocks (code),
lines wrapped at one column (joined into paragraphs; ragged lines such as an address keep their breaks). It is off unless
you ask for it with `--to md`, and it needs nothing installed.

Two promises. **The words never change**: the letters and digits of the result, in order, are the input's (a hyphen at a
line end stays; headings get `#`, lists `-`, tables `|`); the check runs on every file and falls back to plain
paragraphs if it ever fails. **A garbled text is not given structure**: the share of letters and digits, replacement and
control characters, very short lines, one-letter "words" and the average word length are measured, and past a limit
(`GARBLE_LIMITS` in `batchocr_txt.py`) the file gets paragraphs only and the rule that fired is printed
(`--txt-structure force` skips the check). Guessing is still guessing: read the result before relying on it.

## What happens to each format

| Input | Default handling | Output |
|---|---|---|
| `.pdf` | per page: the text layer if it passes the quality check, otherwise Tesseract OCR | `.txt`, or `.md` with `--to md` |
| `.png` `.jpg` `.tif` `.bmp` ... | Tesseract OCR | `.txt` |
| `.docx` `.pptx` | Pandoc to Markdown; every embedded image is OCRed, with its text placed right below the image | `.md` |
| `.epub` `.mobi` `.azw3` `.cbz` ... | Calibre `ebook-convert`, falling back to Pandoc | `.txt` |
| `.doc` `.xls` `.ppt` `.ods` `.odp` ... | headless LibreOffice | `.txt` |
| `.odt` `.rtf` `.html` `.tex` `.rst` `.ipynb` `.org` ... | Pandoc | `.txt` |
| `.txt` `.md` | copied as-is | same |
| anything else | reported as skipped, never guessed at | none |

PDF output always marks page boundaries with `--- Page N ---`, whether the
text came from the text layer or from OCR. If the PDF has printed page
labels that differ from the physical page number, the marker shows both,
for example `--- Page 150 (3-12) ---`. That lets you search a big handbook
by the page numbers printed in it. Reading labels needs PyMuPDF or pypdf
(`pip install pymupdf`), and both are optional. `--no-page-markers` turns
the markers off for text-layer PDFs.

When a format has more than one backend, `--engine` chooses:

```sh
batchocr report.docx --engine docx=libreoffice   # plain text, no image OCR (.txt)
batchocr book.epub --engine epub=pandoc          # skip Calibre
batchocr library/ --engine ebook=pandoc          # Pandoc for every ebook format
```

For Word and PowerPoint files, `--save-images` keeps the extracted images,
`--no-office-ocr` skips OCR of those images, and `--ocr-report` writes the
image OCR to a separate file.

## Logs and summaries

```sh
batchocr inbox/ -o text/ -m                    # also write manifest.tsv
batchocr inbox/ -o text/ --log                 # also save terminal output to batchocr.log
batchocr inbox/ -o text/ -m --meta-dir text/_meta   # put both in their own folder
```

`manifest.tsv` has one row per source: file name, type, page count, word
count, a short snippet, the output file, and the line range of that source
inside a merged output. Press Ctrl+C to cancel queued OCR pages cleanly.

## Reference

`batchocr --help` lists every flag. The docstring at the top of
[`batchocr.py`](batchocr.py) documents every output rule in detail.

## Credits

`m1ck4_pdfmd/` is a pinned, lightly patched copy of
[**pdfmd** by Michael Neivandt (M1ck4)](https://github.com/M1ck4/pdfmd)
(MIT licence, copyright kept in `m1ck4_pdfmd/LICENSE`; the repository is
archived). It supplies the PDF to Markdown structure stages: heading, list,
table and math detection and Markdown rendering. It was written by M1ck4, not
by batchocr's author. It is not the unrelated PyPI package called `pdfmd`.
`VENDORED.md` records the upstream commit, checksums and the patch;
`scripts/vendor_m1ck4.py` regenerates the folder, so it is never edited by hand.

## License

[MIT](LICENSE). The vendored `m1ck4_pdfmd/` is MIT as well (its own notice
applies to it). PyMuPDF, needed only for `--to md` and installed separately, is
AGPL-3.0.
