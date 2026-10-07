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

`batchocr` is a single Python file.

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

Native text comes out in reading order: whole columns, tables row by row as
the PDF stores them. With PyMuPDF installed (`pip install pymupdf`, optional)
batchocr uses its content-stream order; without it, plain `pdftotext`. Pass
`--layout` to get the pre-1.2.0 `pdftotext -layout` output, which keeps
visual rows (useful for a fixed-width table) but interleaves columns line by
line.

OCR is not perfect. In the example above, Tesseract read `ΔS` as `AS`.
Where a PDF has a good text layer, `batchocr` uses it instead, and that
text is exact.

## What happens to each format

| Input | Default handling | Output |
|---|---|---|
| `.pdf` | text layer if its quality score is high enough, otherwise page-by-page Tesseract OCR | `.txt` |
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

## License

[MIT](LICENSE)
