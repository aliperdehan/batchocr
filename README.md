# batchocr

**Turn a folder of mixed documents into plain text in one command.** PDFs,
scans, photos, Word and PowerPoint files, and ebooks all become `.txt`/`.md`
files. For each file, `batchocr` decides whether it needs OCR or already has
real text.

```console
$ batchocr inbox/ -o text/
[done, OCR] photo-of-board.png -> photo-of-board.txt (200 chars) | time 00:00:00
[hybrid] scanned-handout.pdf: native quality 0.00 -> forcing OCR
[hybrid] typed-notes.pdf: native quality 1.00 -> using native text layer
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
  garbage. `batchocr` samples each PDF's text layer and gives it a quality
  score. Files that score well are extracted with `pdftotext`; the rest are
  OCRed page by page.
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
batchocr old-scan.pdf --full-ocr           # always OCR, ignoring any text layer
batchocr inbox/ --dpi 400                  # sharper rendering for small print (default 300)
batchocr inbox/ --lang eng+rus             # several Tesseract languages
batchocr inbox/ -j 4                       # number of parallel OCR workers (default: all cores)
```

`--full-ocr` is the right choice for a PDF whose text layer exists but is
garbled, as in some old scans that were OCRed badly.

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
