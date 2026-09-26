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

**Versioning:** as of 2026-09-25 there is no version marker and no
`CHANGELOG.md` yet. Add both the next time the script is substantively
modified, following the pattern pdfmd uses (a `*_VERSION` constant right
after the docstring, a `--version` flag, and a newest-first `CHANGELOG.md`
updated in the same edit). Don't backfill a history: reconstructing intent
from old backup diffs alone is unreliable.

**Verify through the real command**, on real input files, not only
synthetic snippets.

## Location

The real file is `~/dev/py/batchocr/batchocr.py`.
`~/dev/python-projects/batchocr.py` is a symlink to it, kept because a
shell alias invokes that path; don't remove it.
