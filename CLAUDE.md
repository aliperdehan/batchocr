# batchocr

Batch document extraction and OCR — see the module docstring
(`batchocr.py`'s opening comment) for what it actually handles (PDF hybrid
text extraction, lower-quality-score fallback to OCR, and whatever else
the docstring currently lists — check there, not here, for the current
feature set).

This repository is public. Don't commit personal details (absolute
`/Users/...` home paths, names, anything local-only) — use `~/` paths.

## Before touching batchocr.py

**Commit first.** Git replaces manual backup copies: before any edit,
`git status` must be clean (commit or stash anything pending), so the
last commit is the exact pre-edit state. Don't create `.bak` copies.
Older backups live in `~/dev/python-projects/backups/`.

**Versioning:** the version lives in the `BATCHOCR_VERSION` constant right
after the docstring (shown by `--version`), and `CHANGELOG.md` is
newest-first. Any substantive change bumps the constant and adds a changelog
entry in the same commit, following the pattern pdfmd uses. History before
1.1.0 is not tracked and should not be backfilled: reconstructing intent from
old backup diffs alone is unreliable.

**Verify through the real command**, on real input files, not only
synthetic snippets.

## Tests, vendored code, optional dependencies

- `python3 -m unittest discover tests` (fixtures are built at test time; tests
  needing PyMuPDF or Tesseract skip without them). Never commit real documents.
- `m1ck4_pdfmd/` is generated (pinned copy of M1ck4/pdfmd, MIT) by
  `scripts/vendor_m1ck4.py` from pristine upstream plus `scripts/m1ck4.patch`;
  see `VENDORED.md`. Don't hand-edit it without regenerating the patch
  (`--update-patch`); `--check` verifies it. Keep its MIT notice.
- PyMuPDF is AGPL-3.0: an optional, separately installed dependency, only
  needed for `--to md`. Never bundle it or make plain-text mode require it.

## Known gaps (PDF → Markdown, as of 1.2.4)

Open by design or not yet done; check here before "fixing" any of them.

- A paragraph that continues across a page or column break stays two
  paragraphs, with the page marker between them.
- Side-by-side columns on OCR pages are read one after the other (a two-column
  dictionary page comes out as two runs, not a table).
- Tables come only from M1ck4's text-based detector: no ruled (geometric)
  detection. Index pages and forms can come out as 2–3 column tables or
  reordered (a form table is rendered row-major). Headings are H1/H2 only; a
  heading wrapped across blocks becomes two headings; footnotes are plain
  paragraphs or lists.
- Math: M1ck4's equation stage rarely fires, and fragmented equations come out
  as scattered fragments.
- Running-header removal is off below 4 pages and cannot tell a repeated form
  label at the top of a page from a header (`--keep-headers` disables it). It
  is also outside the per-page text-loss check, deliberately.
- `--layout` applies to the text path only; Markdown ignores it.
- Plain-text output differs with and without PyMuPDF installed (PyMuPDF stream
  order vs `pdftotext`, which can misorder e.g. a reference list). Don't assume
  byte-stable `.txt` across machines. Markdown always needs PyMuPDF.
- Typed-page column order assumes the PDF stores columns in reading order (true
  for every tested file); there is no geometric column detection to rescue a
  scrambled stream. 3-column/newspaper layouts are untested. Scans rely on
  Tesseract's layout analysis.
- The OCR cross-check costs about 1 s per PDF in batch runs (`--no-ocr-check`).
  Its 0.30 overlap threshold came from 15 genuine typed samples (lowest 0.52)
  plus one synthetic garbage layer; a larger corpus could move it.

Not verified: Linux/Windows, Python 3.10/3.11 (tested on 3.12 and 3.14), the
apt package names, password-protected PDFs (not prompted for; they fail with a
message), `--ocr ocrmypdf` beyond one sample, a 100+ page *scanned* file in md
mode (only a 447-page native book with 4 OCR pages), `--export-images` on CMYK
images, and any hand-transcribed ground truth for scans.

## Benchmark harness (intentionally outside the repo)

The harness used to choose and tune the Markdown design lives in
`~/Downloads/batchocr-md-bench` (scripts `corpus.py`, `runbench.py`,
`score.py`, `run_new.py`, plus `scores.json` and the raw outputs). It is not in
the repo on purpose: its corpus is ~30 MB of real documents (never committed),
the scripts hardcode absolute paths, and they need a separate venv and a clone
of M1ck4/pdfmd. Its README has the setup. If you rebuild it, keep it outside
the repo, or make it path-independent with a synthetic corpus before adding it.

What to remember when reading or reproducing its numbers:

- Ground truth is PyMuPDF stream order, so batchocr's native-text path scores
  0.0 WER / 1.0 F1 *by construction*. That is not evidence; order is judged on
  the image-of-typed slices (Tesseract layout vs stream order) and by eye.
- M1ck4's `score.py` stripped `<[^>]+>` and matched from "p < 0.10" to a later
  `<http…>` across lines, deleting pages of output before scoring. The bench
  scorer is fixed (real tags only); `scores_v0_buggy_scorer.json` holds the
  old numbers. Treat "stock M1ck4 lost content" claims from the old scorer as
  wrong; its real losses were body text merged with footnotes into a table,
  multi-block tables printed twice, and OCR lines keyed by (block, line).
- Md scores are against truth with detected header/footer lines removed
  (`BENCH_ADJUST=1`). A bigram-F1 metric was added (a moved block costs 2
  bigrams, interleaved columns cost most of them).
- A PDF whose text layer is mojibake scores meaninglessly against its own
  truth; judge it by eye.
- Tesseract output can vary run to run under load (a 334 vs 350 word
  difference on one scan with identical code).

## Location

The real file is `~/dev/py/batchocr/batchocr.py`.
`~/dev/python-projects/batchocr.py` is a symlink to it, kept because a
shell alias invokes that path; don't remove it.
