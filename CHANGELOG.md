# Changelog

Newest first. History before 1.1.0 was not tracked.

## 1.2.0 — 2026-10-07

- Native PDF text now comes out in reading order. `pdftotext -layout` kept
  visual rows, so left and right columns were interleaved line by line on
  multi-column pages, tables and figure-adjacent text. Extraction now uses
  PyMuPDF's content-stream order when PyMuPDF is installed (optional) and
  plain `pdftotext` otherwise. New `--layout` flag restores the old output.
- Repaired the native-vs-OCR quality gate. It scored only letter-only tokens
  from the middle page, so a text layer made of symbols (broken font
  encoding) scored 0.99 and was shipped as garbage. It now scores every page
  by characters (private-use, IPA/modifier and replacement glyphs count
  against it) and words, and decides per page, so PDFs mixing typed and
  scanned pages are handled page by page.
- The gate also OCRs one sampled page at 150 dpi and compares its words with
  the text layer; a layer whose words are not on the page is rejected as a
  whole. `--no-ocr-check` skips it. Log lines change accordingly
  (`[hybrid] file.pdf: 3/4 pages pass the text-layer check, ...`).
- Added `tests/` (`python3 -m unittest discover tests`). Fixtures are built
  at test time; tests needing PyMuPDF or Tesseract skip without them.

## 1.1.1 — 2026-09-29

- Fixed `--save-images` on PPTX/DOCX: images were extracted into a `media/`
  folder shared by every document in the output directory, so decks
  overwrote each other's `image1.png` etc., and image OCR also scanned other
  documents' images. Each document now gets its own `<stem>_media/` folder,
  cleared before extraction.

## 1.1.0 — 2026-09-27

- Native-text PDFs (the `pdftotext` path) now get the same `--- Page N ---`
  markers as OCRed PDFs, instead of one unmarked block of text.
- Page markers on both paths include the PDF's printed page label when it
  differs from the physical page number, e.g. `--- Page 150 (3-12) ---`.
  Labels come from PyMuPDF or pypdf, whichever is installed. Both are
  optional: without either, markers show only the physical page number.
- New `--no-page-markers` flag restores the old unmarked native output.
- Added a `--version` flag and this changelog.
