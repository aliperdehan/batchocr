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

## Location

The real file is `~/dev/py/batchocr/batchocr.py`.
`~/dev/python-projects/batchocr.py` is a symlink to it, kept because a
shell alias invokes that path; don't remove it.
