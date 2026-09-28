# Changelog

Newest first. History before 1.1.0 was not tracked.

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
