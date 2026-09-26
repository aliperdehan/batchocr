#!/usr/bin/env python3
"""
batchocr -- batch document extraction and OCR.

What it handles:
  - PDF: hybrid text extraction by default -- samples the native text layer,
    and files scoring at least the quality threshold use pdftotext; lower-
    scoring (garbled/scanned) files receive full-page Tesseract OCR
    automatically. Use --full-ocr to always force full OCR on every page
    regardless of native text quality (the old default; still the better
    choice for garbled/scanned sources). -H/--hybrid is kept as a harmless
    no-op for backward compatibility.
  - Images (.png/.jpg/.jpeg/.tif/.tiff/.bmp/.pnm): OCRed directly with
    Tesseract, no rasterisation needed. A single image is treated like a
    single-page document. A directory of page images (page1.png, page2.png,
    ...) is treated like one document's pages: sorted in natural numeric
    order and, since directory input with no -o merges by default (see
    "Directory runs" below), combined into one output automatically -- the
    same way --concat combines multiple files.
  - PPTX/DOCX: converts to Markdown with Pandoc by default, OCRs extracted
    images, and places each image's OCR below its image reference. Images are
    temporary unless --save-images is used. --engine docx=libreoffice switches
    .docx to LibreOffice instead: plain text only, output is .txt, no
    embedded-image OCR -- useful when you just want the text and don't care
    about images. .pptx has no LibreOffice alternative (soffice has no plain-
    text export filter for Impress/presentation files) and always uses Pandoc.
  - Ebook/comic formats: uses Calibre's ebook-convert by default, with Pandoc
    as a fallback when Calibre is unavailable or fails. Image-only comics may
    produce little or no text because this path is extraction, not image OCR.
    --engine epub=pandoc (or mobi=..., cbz=..., or ebook=... for every
    Calibre-supported extension at once) forces Pandoc instead, skipping
    Calibre entirely.
  - Legacy Office/OpenDocument formats (.doc, .xls, .ppt, .pps, .sx*, .od*)
    use LibreOffice headlessly to produce plain text.
  - TXT/MD are copied directly. Pandoc-supported text/document formats are
    passed to Pandoc with an explicit input format where one is known.
  - --engine FORMAT=ENGINE (repeatable) is the general switch above, for any
    format with more than one viable backend. See "Choosing an engine" below.

Important behavior:
  - This is extension-based, not a universal wrapper around every format a
    third-party program might accept. Unknown extensions are explicitly
    reported as skipped. Add a handler before relying on a new format.
  - Single-file and directory runs both accept an optional output; if omitted,
    output is written beside the input (a directory merges into "<dirname>.txt"
    beside it, same as --concat -- see "Directory runs" below).
  - Existing output is skipped on normal reruns. Use --force to redo it.
    Single-file mode always processes the selected file.
  - Completed files are written as soon as ready. With --archive-dir, each
    completed source is moved there immediately; unfinished sources remain.
  - manifest.tsv is a tab-separated summary of outputs, not an OCR transcript;
    off by default in every mode, use -m/--manifest to write it. Columns:
    filename, type, pages, word_count, snippet, output_file, line_range.
    output_file/line_range point into the merged file or stdout stream when
    --concat/--stdout applies to that source; otherwise line_range is '-'.
    With --stdout, -m prints the manifest to stderr instead of a file (real
    stdout stays text-only). --meta-dir collects the manifest, default log,
    and default Office OCR report in a separate directory.
    --log optionally mirrors terminal messages to a log file.
  - Ctrl-C cancels queued PDF pages and terminates OCR workers.

Dependencies:
  macOS: brew install poppler tesseract pandoc calibre libreoffice
  Extra Tesseract languages: brew install tesseract-lang
  Linux package names vary; install pdfinfo/pdftoppm, tesseract, Pandoc,
  and optionally Calibre. If Calibre is absent, supported ebook formats try
  Pandoc and print a warning.

Common commands:
  batchocr sources/ -o out/ --dpi 300 -a sources/parsed
  batchocr inbox/ -o text/ --quality-threshold 0.85 -a inbox/done
  batchocr sources/ -o out/ --quality-threshold 0.85
  batchocr input.pdf
  batchocr input.pdf -o out/ --force --log
  batchocr input.pdf -o output.txt --full-ocr
  batchocr presentation.pptx -o out/ --save-images --ocr-report
  batchocr a.pdf b.pdf c.pdf -o out/
  batchocr a.pdf b.pdf -m
  batchocr a.pdf b.pdf c.pdf -o notes.txt --concat
  batchocr a.pdf b.pdf --stdout | some-other-tool
  batchocr pages/ -o book.txt --concat
  batchocr scan.png
  batchocr contract.docx --engine docx=libreoffice
  batchocr library/ -o out/ --engine ebook=pandoc

Choosing an engine (--engine FORMAT=ENGINE, repeatable):
  batchocr file.docx --engine docx=libreoffice   -> plain text via LibreOffice,
                                                     output file.txt, no image OCR
  batchocr book.epub --engine epub=pandoc        -> force Pandoc, skip Calibre
  batchocr library/ --engine ebook=pandoc        -> Pandoc for every Calibre-supported
                                                     extension (epub, mobi, cbz, ...)
  Default engines (no --engine needed): .docx -> pandoc; .pptx -> pandoc always
  (no LibreOffice alternative exists); ebook formats -> calibre, falling back
  to Pandoc only if Calibre is missing or fails. --engine office=... and
  --engine pptx=libreoffice are rejected since LibreOffice can't do it.

Input files:
  Give one directory (batch mode), one file (single-file mode), or several
  files (multi-file mode). A directory can't be mixed with other inputs in
  the same run. -a is a short alias for --archive-dir; -H is a legacy short
  alias for --hybrid, now a no-op since hybrid extraction is the default
  (-h is taken by --help).

Single-file output rule (exactly one input file):
  batchocr input.pdf                -> beside input.pdf: input.txt
  batchocr input.pdf -o .           -> ./input.txt
  batchocr input.pdf -o out/        -> out/input.txt
  batchocr input.pdf -o output.txt  -> exactly output.txt (not a directory)
  batchocr input.pdf --stdout       -> extracted text printed to the terminal

Multi-file output rule (more than one input file):
  batchocr a.pdf b.pdf -o out/      -> out/a.txt, out/b.txt
  batchocr a.pdf b.pdf              -> each output written beside its own source
  -o must be a directory (or omitted) when more than one input file is given --
  it is never taken as an exact output filename, so an existing file can't
  accidentally be used as an output target and overwritten.

Merging multiple files into one stream (-c/--concat and -s/--stdout):
  batchocr a.pdf b.pdf -o notes.txt --concat  -> notes.txt, sections headed
                                                  "=== a.pdf ===" / "=== b.pdf ==="
  batchocr sources/ -o notes.txt --concat     -> same, for every file in a directory
  batchocr a.pdf b.pdf --stdout               -> same merge, printed to stdout
  batchocr sources/ --stdout                  -> whole directory batch, to stdout
  batchocr input.pdf --stdout                 -> single file, printed raw (no header)
  --stdout is mutually exclusive with -o/--output. All progress/status/manifest
  messages move to stderr in --stdout mode, so stdout carries only the
  extracted text -- safe to pipe into another command or script.

Directory runs:
  batchocr sources/                      -> merged into sources.txt beside sources/
  batchocr sources/ -o out/               -> one output file per source, in out/
  batchocr sources/ -o notes.txt --concat -> merged into notes.txt (explicit name)
  batchocr sources/ --stdout              -> merged, printed to stdout
  batchocr pages/                         -> folder of page1.png, page2.png, ... merged
                                              into pages.txt in natural page order

Supplementary outputs:
  batchocr sources/ -o out/ --meta-dir out/_meta
  batchocr input.pdf -m
"""

import argparse
import concurrent.futures as cf
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import glob
from pathlib import Path

PDF_EXT = {".pdf"}
DIRECT_EXT = {".txt", ".md"}
CALIBRE_EXT = {
    ".epub", ".mobi", ".azw", ".azw3", ".kfx", ".fb2", ".fbz",
    ".lit", ".lrf", ".pdb", ".prc", ".rb", ".snb", ".tcr",
    ".htmlz", ".cbz", ".cbr", ".cb7", ".cbt",
}
LIBREOFFICE_EXT = {
    ".doc", ".docm", ".xls", ".xlsm", ".ppt", ".pptm", ".pps", ".pot",
    ".potx", ".potm", ".xlt", ".xltx", ".xltm", ".sdd", ".sxc", ".sxi", ".sxw",
    ".ods", ".odp", ".odg", ".fodt", ".fods", ".fodp",
}
PANDOC_EXT = {
    ".asciidoc", ".adoc", ".bib", ".biblatex", ".bits", ".commonmark",
    ".creole", ".csv", ".djot", ".docbook", ".dokuwiki", ".epub",
    ".endnotexml", ".fb2", ".html", ".htm", ".ipynb", ".jats", ".jira",
    ".json", ".latex", ".tex", ".man", ".mediawiki", ".muse", ".opml",
    ".org", ".pod", ".ris", ".rst", ".rtf", ".t2t", ".textile", ".tikiwiki",
    ".tsv", ".typst", ".vimwiki", ".xml", ".odt",
}
OFFICE_EXT = {".pptx", ".docx"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".pnm"}

# Formats where more than one extraction backend is viable; --engine picks between them.
# LibreOffice has no plain-text export filter for Impress (.pptx) documents --
# "soffice --convert-to txt" fails with "no export filter found" for pptx even
# though it works fine for Writer formats -- so pptx only ever gets pandoc.
EBOOK_ENGINES = {"calibre", "pandoc"}
ENGINE_CHOICES = {ext: EBOOK_ENGINES for ext in CALIBRE_EXT}
ENGINE_CHOICES[".docx"] = {"pandoc", "libreoffice"}
ENGINE_CHOICES[".pptx"] = {"pandoc"}


def find_tool(name: str) -> str | None:
    """Find a command, including standard macOS application-bundle paths."""
    found = shutil.which(name)
    if found:
        return found
    candidates = []
    configured = os.environ.get("BATCHOCR_SOFFICE") if name == "soffice" else None
    if configured:
        candidates.append(Path(configured).expanduser())
    if name == "soffice":
        candidates.extend([
            Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
            Path.home() / "Applications/LibreOffice.app/Contents/MacOS/soffice",
        ])
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


class Tee:
    """Write output to the terminal and, optionally, a log file."""

    def __init__(self, terminal, logfile):
        self.terminal = terminal
        self.logfile = logfile

    def write(self, text):
        self.terminal.write(text)
        self.logfile.write(text)

    def flush(self):
        self.terminal.flush()
        self.logfile.flush()

    def isatty(self):
        return self.terminal.isatty()


def check_pdf_tools():
    """Hard requirement, checked only once we know the run actually has PDFs."""
    needed = ["pdfinfo", "pdftoppm", "tesseract"]
    missing = [t for t in needed if shutil.which(t) is None]
    if missing:
        sys.exit(
            f"Missing required tools: {', '.join(missing)}.\n"
            "See the install instructions in this script's header."
        )


def check_image_tools():
    """Hard requirement, checked only once we know the run actually has images."""
    if shutil.which("tesseract") is None:
        sys.exit(
            "Missing required tool: tesseract.\n"
            "See the install instructions in this script's header."
        )


def natural_sort_key(path: Path):
    """Numeric-aware sort key so page2.png sorts before page10.png."""
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", path.name)]


def check_tools():
    if shutil.which("pandoc") is None:
        print(
            "[warn] pandoc not found -- HTML/RTF/ODT files and Calibre fallback "
            "will be unavailable.",
            file=sys.stderr,
        )
    if shutil.which("ebook-convert") is None:
        print(
            "[warn] ebook-convert not found -- supported ebook/comic files "
            "will fall back to Pandoc when possible.",
            file=sys.stderr,
        )
    if find_tool("soffice") is None and shutil.which("libreoffice") is None:
        print(
            "[warn] LibreOffice not found -- legacy Office formats will be skipped.",
            file=sys.stderr,
        )


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def enable_logging(log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logfile = log_path.open("a", encoding="utf-8", buffering=1)
    logfile.write(f"\n--- batchocr started {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    sys.stdout = Tee(sys.__stdout__, logfile)
    sys.stderr = Tee(sys.__stderr__, logfile)


def archive_source(src: Path, archive_dir: Path | None) -> bool:
    """Archive one completed source immediately, if requested."""
    if archive_dir is None or not src.exists():
        return False
    dest = archive_dir / src.name
    if dest.exists():
        print(f"[warn] {dest} already exists in archive dir, leaving {src.name} in place")
        return False
    shutil.move(str(src), str(dest))
    print(f"[archive] {src.name} -> {archive_dir}")
    return True


MANIFEST_HEADER = ["filename", "type", "pages", "word_count", "snippet", "output_file", "line_range"]


def write_manifest_file(meta_dir: Path, manifest_rows: list, manifest_flag: bool, to_stderr: bool = False) -> None:
    if not manifest_flag:
        print("\n[manifest] not written (use -m/--manifest to enable)")
        return
    if to_stderr:
        # --stdout keeps real stdout text-only, so the manifest goes to the
        # terminal via stderr instead of a manifest.tsv file on disk.
        w = csv.writer(sys.stderr, delimiter="\t")
        w.writerow(MANIFEST_HEADER)
        w.writerows(manifest_rows)
        return
    manifest_path = meta_dir / "manifest.tsv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(MANIFEST_HEADER)
        w.writerows(manifest_rows)
    print(f"\n[manifest] {manifest_path}")


def build_merge(concat_entries: dict, ordered_files: list) -> tuple[str, dict]:
    """Build the '=== filename ===' merged text and, for each source that made
    it in, the 1-indexed inclusive (start_line, end_line) it occupies there --
    header line through its last line of content, so a manifest row can point
    straight at the right slice of the merged output."""
    chunks = []
    line_ranges = {}
    line_no = 1
    first = True
    for f in ordered_files:
        if f not in concat_entries:
            continue
        if not first:
            chunks.append("")  # blank separator line between sections
            line_no += 1
        first = False
        section_lines = [f"=== {f.name} ===", ""] + concat_entries[f].strip().split("\n")
        start = line_no
        chunks.extend(section_lines)
        line_no += len(section_lines)
        line_ranges[f] = (start, line_no - 1)
    merged = "\n".join(chunks) + ("\n" if chunks else "")
    return merged, line_ranges


def write_merged_output(concat_target: Path | None, dump_stdout: bool,
                         concat_entries: dict, ordered_files: list) -> dict:
    """Merge whatever's in concat_entries, in original input order, either into
    concat_target or (dump_stdout) straight to the real terminal stdout -- which
    stays the true stdout even after main() redirects sys.stdout to sys.stderr.
    Returns the source -> (start_line, end_line) map for the manifest."""
    if concat_target is None and not dump_stdout:
        return {}
    merged, line_ranges = build_merge(concat_entries, ordered_files)
    if dump_stdout:
        sys.__stdout__.write(merged)
        print(f"[stdout] dumped {len(line_ranges)}/{len(ordered_files)} file(s)", file=sys.stderr)
    else:
        concat_target.write_text(merged, encoding="utf-8")
        print(f"\n[concat] merged {len(line_ranges)}/{len(ordered_files)} file(s) -> {concat_target}")
    return line_ranges


def assemble_manifest_rows(all_files: list, manifest_entries: dict, line_ranges: dict,
                            concat_target: Path | None) -> list:
    """Turn the per-source bookkeeping into manifest.tsv rows, in original input
    order. output_file/line_range point into the merged file/stream when one of
    --concat/--stdout applies to this source, otherwise line_range is '-'."""
    merged_label = concat_target.name if concat_target is not None else "(stdout)"
    rows = []
    for f in all_files:
        if f not in manifest_entries:
            continue
        ext, pages, word_count, snippet, label = manifest_entries[f]
        if f in line_ranges:
            start, end = line_ranges[f]
            rows.append([f.name, ext, pages, word_count, snippet, merged_label, f"{start}-{end}"])
        else:
            rows.append([f.name, ext, pages, word_count, snippet, label, "-"])
    return rows


def stop_executor(executor, futures):
    """Cancel queued pages and terminate workers after Ctrl-C."""
    for future in futures:
        future.cancel()

    terminate_workers = getattr(executor, "terminate_workers", None)
    if terminate_workers is not None:
        terminate_workers()
        return

    # Compatibility fallback for Python versions before 3.14.
    for process in getattr(executor, "_processes", {}).values():
        process.terminate()
    executor.shutdown(wait=False, cancel_futures=True)


def pdf_page_count(pdf_path: Path) -> int:
    out = subprocess.run(
        ["pdfinfo", str(pdf_path)], capture_output=True, text=True
    ).stdout
    m = re.search(r"Pages:\s*(\d+)", out)
    return int(m.group(1)) if m else 0


def word_quality(text: str) -> float:
    """Cheap heuristic: fraction of tokens that look like real words,
    not font-encoding garbage. Used only for the hybrid native-vs-OCR check
    (skipped entirely when --full-ocr is given)."""
    tokens = re.findall(r"[A-Za-zÀ-ÿЀ-ӿ][A-Za-zÀ-ÿЀ-ӿ'\-]*", text)
    if not tokens:
        return 0.0
    good = sum(
        1
        for t in tokens
        if 1 <= len(t) <= 25
        and not re.search(r"[bcdfghjklmnpqrstvwxzBCDFGHJKLMNPQRSTVWXZ]{5,}", t)
    )
    return good / len(tokens)


def native_quality_for_file(pdf_path: Path, pages: int) -> float:
    if pages == 0:
        return 0.0
    mid = max(1, pages // 2)
    out = subprocess.run(
        ["pdftotext", "-f", str(mid), "-l", str(mid), str(pdf_path), "-"],
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout
    return word_quality(out)


def ocr_one_page(pdf_path: Path, page_num: int, dpi: int, lang: str, tmp_root: Path) -> str:
    # tmp_root is a run-wide scratch directory owned by the parent process, so
    # that a forcibly-terminated worker (Ctrl-C) still gets its leftovers
    # swept up by the parent's cleanup instead of orphaning files in /tmp.
    td = Path(tempfile.mkdtemp(prefix=f"p{page_num}-", dir=tmp_root))
    try:
        prefix = td / "p"
        subprocess.run(
            [
                "pdftoppm", "-png", "-r", str(dpi),
                "-f", str(page_num), "-l", str(page_num),
                str(pdf_path), str(prefix),
            ],
            check=True,
            capture_output=True,
        )
        imgs = sorted(td.glob("p*.png"))
        if not imgs:
            return ""
        result = subprocess.run(
            ["tesseract", str(imgs[0]), "stdout", "-l", lang],
            capture_output=True,
            text=True,
        )
        return result.stdout
    finally:
        shutil.rmtree(td, ignore_errors=True)


def native_extract_pdf(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return result.stdout


def ocr_image(image_path: Path, lang: str) -> str:
    """OCR a single standalone image file directly (no rasterisation needed)."""
    result = subprocess.run(
        ["tesseract", str(image_path), "stdout", "-l", lang],
        capture_output=True,
        text=True,
    )
    return result.stdout


PANDOC_FORMAT_BY_EXT = {
    ".asciidoc": "asciidoc", ".adoc": "asciidoc", ".bib": "bibtex",
    ".biblatex": "biblatex", ".commonmark": "commonmark", ".creole": "creole",
    ".djot": "djot", ".docbook": "docbook", ".dokuwiki": "dokuwiki",
    ".endnotexml": "endnotexml", ".epub": "epub", ".fb2": "fb2",
    ".html": "html", ".htm": "html", ".ipynb": "ipynb", ".jats": "jats",
    ".jira": "jira", ".json": "json", ".latex": "latex", ".tex": "latex",
    ".man": "man", ".mediawiki": "mediawiki", ".muse": "muse", ".opml": "opml",
    ".org": "org", ".pod": "pod", ".ris": "ris", ".rst": "rst",
    ".rtf": "rtf", ".t2t": "t2t", ".textile": "textile", ".tikiwiki": "tikiwiki",
    ".tsv": "tsv", ".typst": "typst", ".vimwiki": "vimwiki", ".xml": "xml",
    ".odt": "odt",
}


def pandoc_extract(src_path: Path) -> str:
    input_format = PANDOC_FORMAT_BY_EXT.get(src_path.suffix.lower())
    try:
        command = ["pandoc", str(src_path)]
        if input_format:
            command.extend(["-f", input_format])
        command.extend(["-t", "plain"])
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except FileNotFoundError:
        pass
    if src_path.suffix.lower() == ".rtf":
        raw = src_path.read_text(errors="replace")
        text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
        text = re.sub(r"\\[a-zA-Z]+\d* ?", "", text)
        text = re.sub(r"[{}]", "", text)
        return text
    return ""


def calibre_extract(src_path: Path) -> str:
    """Extract readable text through Calibre's ebook-convert command."""
    with tempfile.TemporaryDirectory(prefix="batchocr-calibre-") as td:
        converted = Path(td) / "converted.txt"
        result = subprocess.run(
            ["ebook-convert", str(src_path), str(converted)],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if result.returncode != 0 or not converted.exists():
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(detail or "ebook-convert produced no output")
        return converted.read_text(errors="replace")


def book_extract(src_path: Path, force_engine: str | None = None) -> tuple[str, str]:
    """Use Calibre first, falling back to Pandoc when Calibre is unavailable.
    force_engine (from --engine) pins the choice instead: 'calibre' or 'pandoc',
    no fallback."""
    calibre = shutil.which("ebook-convert")
    pandoc = shutil.which("pandoc")

    if force_engine == "pandoc":
        if not pandoc:
            raise RuntimeError("pandoc is not installed")
        return pandoc_extract(src_path), "pandoc (--engine)"

    if force_engine == "calibre":
        if not calibre:
            raise RuntimeError("ebook-convert is not installed")
        return calibre_extract(src_path), "calibre (--engine)"

    if calibre:
        try:
            return calibre_extract(src_path), "calibre"
        except Exception as exc:
            if pandoc:
                print(f"[warn] Calibre failed for {src_path.name}: {exc}; falling back to Pandoc",
                      file=sys.stderr)
            else:
                raise
    else:
        print(f"[warn] ebook-convert not found; falling back to Pandoc for {src_path.name}",
              file=sys.stderr)

    if not pandoc:
        raise RuntimeError("Neither ebook-convert nor pandoc is installed")
    return pandoc_extract(src_path), "pandoc fallback"


def libreoffice_extract(src_path: Path) -> str:
    """Extract plain text from legacy Office/OpenDocument files."""
    soffice = find_tool("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("soffice/libreoffice is not installed")
    with tempfile.TemporaryDirectory(prefix="batchocr-libreoffice-") as td:
        out_dir = Path(td) / "out"
        profile_dir = Path(td) / "profile"
        out_dir.mkdir()
        profile_dir.mkdir()
        profile_uri = profile_dir.as_uri()
        result = subprocess.run(
            [
                soffice,
                f"-env:UserInstallation={profile_uri}",
                "--headless", "--convert-to", "txt:Text",
                "--outdir", str(out_dir), str(src_path),
            ],
            capture_output=True,
            text=True,
            errors="replace",
        )
        converted = out_dir / f"{src_path.stem}.txt"
        if result.returncode != 0 or not converted.exists():
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(detail or "soffice produced no text output")
        return converted.read_text(errors="replace")


def office_convert(source_path: Path, md_file: Path, pandoc_target: str,
                   save_images: bool) -> tuple[Path, Path]:
    """Convert a PPTX/DOCX to Markdown at exactly md_file; return its Markdown/media paths."""
    md_file.parent.mkdir(parents=True, exist_ok=True)
    media_root = (
        md_file.parent if save_images else md_file.parent / f".{md_file.stem}_media_tmp"
    )
    media_root.mkdir(parents=True, exist_ok=True)
    source_format = source_path.suffix.lower().lstrip(".")
    targets = [
        pandoc_target,
        "markdown+tex_math_dollars+tex_math_single_backslash",
        "markdown",
        "gfm+tex_math_dollars",
        "gfm",
        "commonmark",
    ]
    last_err = ""
    for target in targets:
        result = subprocess.run(
            [
                "pandoc", str(source_path), "-f", source_format, "-t", target,
                f"--extract-media={media_root}", "-o", str(md_file), "--wrap=none",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return md_file, media_root
        if "not supported" in result.stderr or "Unknown extension" in result.stderr:
            last_err = result.stderr.strip()
            continue
        raise RuntimeError(f"Pandoc failed for {source_path.name}: {result.stderr.strip()}")
    raise RuntimeError(f"All Pandoc targets failed for {source_path.name}: {last_err}")


def office_inline_ocr(md_file: Path, media_root: Path, out_dir: Path,
                      source_name: str, langs: str, report_path: Path | None) -> int:
    """OCR extracted Office images and place each result below its image."""
    if shutil.which("tesseract") is None:
        print("[warn] tesseract not found; Office image OCR skipped", file=sys.stderr)
        return 0

    images = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.tiff", "*.bmp", "*.emf", "*.wmf"):
        images.extend(media_root.rglob(ext))
    ocr_results = []
    for image in sorted(set(images)):
        try:
            if image.stat().st_size < 1024:
                continue
            result = subprocess.run(
                ["tesseract", str(image), "stdout", "-l", langs, "--psm", "6"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            text = result.stdout.strip()
            if text and len(text) > 2:
                ocr_results.append((image.relative_to(out_dir), text))
        except Exception as exc:
            print(f"[warn] OCR failed for {image.name}: {exc}", file=sys.stderr)

    if not ocr_results:
        return 0

    markdown = md_file.read_text(encoding="utf-8")
    for relative, text in ocr_results:
        relative_text = str(relative).replace("\\", "/")
        marker = (
            f"\n\n<!-- BEGIN IMAGE OCR: {relative_text} -->\n"
            f"{text}\n"
            f"<!-- END IMAGE OCR: {relative_text} -->"
        )
        pattern = re.compile(
            r"(?m)^(?P<line>.*!\[[^\]]*\]\([^\n)]*"
            + re.escape(relative_text)
            + r"[^\n)]*\)[^\n]*)$"
        )
        markdown, count = pattern.subn(
            lambda match: match.group("line") + marker, markdown, count=1
        )
        if count == 0:
            markdown += f"\n\n![{relative.name}]({relative_text}){marker}\n"
    md_file.write_text(markdown, encoding="utf-8")

    if report_path:
        with report_path.open("w", encoding="utf-8") as report:
            report.write(f"# OCR from {source_name}\n\n")
            for relative, text in ocr_results:
                report.write(
                    f"### {relative}\n\n![{relative.name}]({relative})\n\n"
                    f"```\n{text}\n```\n\n---\n\n"
                )
    return len(ocr_results)


def process_office(source_path: Path, md_file_target: Path, pandoc_target: str,
                   save_images: bool, do_ocr: bool, langs: str,
                   report_path: Path | None) -> tuple[Path, int]:
    md_file, media_root = office_convert(source_path, md_file_target, pandoc_target, save_images)
    try:
        image_count = office_inline_ocr(
            md_file, media_root, md_file.parent, source_path.name, langs, report_path
        ) if do_ocr else 0
        return md_file, image_count
    finally:
        if not save_images:
            shutil.rmtree(media_root, ignore_errors=True)


def parse_engine_overrides(specs: list, ap: argparse.ArgumentParser) -> dict:
    """Turn --engine FORMAT=ENGINE specs into an {extension: engine} map.
    FORMAT is a bare extension (docx, epub, cbz, ...) or a group alias:
    'office' means docx+pptx, 'ebook' means every Calibre-supported extension."""
    groups = {"office": OFFICE_EXT, "ebook": CALIBRE_EXT}
    overrides = {}
    for spec in specs:
        if "=" not in spec:
            ap.error(f"--engine expects FORMAT=ENGINE, got: {spec!r}")
        fmt, engine = spec.split("=", 1)
        fmt = fmt.strip().lower().lstrip(".")
        engine = engine.strip().lower()
        exts = groups.get(fmt, {f".{fmt}"})
        for ext in exts:
            valid = ENGINE_CHOICES.get(ext)
            if valid is None:
                ap.error(
                    f"--engine: unknown format {fmt!r} -- supported: docx, pptx, "
                    f"office (both), ebook (all Calibre formats), or any Calibre "
                    f"extension such as epub, mobi, cbz"
                )
            if engine not in valid:
                ap.error(f"--engine {fmt}={engine!r}: engine must be one of {sorted(valid)}")
            overrides[ext] = engine
    return overrides


def main():
    run_started = time.monotonic()
    ap = argparse.ArgumentParser(
        description="Batch force-OCR / extract text from a mixed folder of source documents."
    )
    ap.add_argument("inputs", type=Path, nargs="+",
                     help="one or more source files, or a single source directory")
    ap.add_argument("-o", "--output", type=Path, default=None,
                     help="output directory (batch/multi-file mode), or -- with a single "
                          "input file, or with --concat -- an exact output file; "
                          "omit to write beside each input")
    ap.add_argument("-c", "--concat", action="store_true",
                     help="with multiple input files, merge all extracted text into the "
                          "single -o/--output file (each section headed by '=== filename ==='), "
                          "instead of -o needing to be a directory")
    ap.add_argument("-s", "--stdout", action="store_true",
                     help="print extracted text to the terminal instead of writing files "
                          "(single file: raw; directory/multi-file: merged with '=== filename ===' "
                          "headers, like --concat). Mutually exclusive with -o/--output; all "
                          "progress/status/manifest messages move to stderr so stdout stays clean "
                          "for piping into another command or script")
    ap.add_argument("-j", "--jobs", type=int, default=None,
                     help="parallel workers (default: CPU count)")
    ap.add_argument("--dpi", type=int, default=300,
                     help="OCR rasterisation DPI (default 300)")
    ap.add_argument("--lang", default="eng",
                     help="tesseract language(s), e.g. eng+rus for a mixed English/Russian document")
    ap.add_argument("-H", "--hybrid", action="store_true",
                     help="hybrid PDF text extraction is on by default; this flag is kept only "
                          "for backward compatibility and does nothing extra (-H since -h is "
                          "taken by --help). Use --full-ocr to turn hybrid off instead")
    ap.add_argument("--full-ocr", action="store_true",
                     help="always force full-page Tesseract OCR on every PDF page, bypassing "
                          "native-text-layer detection -- this was the old default, still the "
                          "better choice for garbled/scanned sources")
    ap.add_argument("--quality-threshold", type=float, default=0.75,
                     help="native-quality cutoff for hybrid mode (default 0.75)")
    ap.add_argument("--engine", action="append", default=[], metavar="FORMAT=ENGINE",
                     help="pick the extraction backend for a format that has more than one; "
                          "repeatable. docx defaults to pandoc (Markdown + embedded-image OCR), "
                          "alt libreoffice (plain text only, no image OCR, output is .txt instead "
                          "of .md); pptx has no LibreOffice alternative and always uses pandoc. "
                          "ebook, or any Calibre extension such as epub/mobi/cbz, defaults to "
                          "calibre with a Pandoc fallback, alt pandoc (forces Pandoc, no Calibre "
                          "attempt). Example: --engine docx=libreoffice --engine epub=pandoc")
    ap.add_argument("--force", action="store_true",
                     help="reprocess files even if output already exists")
    ap.add_argument("-a", "--archive-dir", type=Path, default=None,
                     help="after processing, move each source file here once its output "
                          "exists -- keeps the input folder clean so future runs only see new files")
    ap.add_argument("-m", "--manifest", action="store_true",
                     help="write manifest.tsv (off by default in every mode); with --stdout, "
                          "the manifest is printed to stderr instead of written to disk")
    ap.add_argument("--meta-dir", type=Path, default=None,
                     help="directory for manifest, default log, and default Office OCR reports")
    ap.add_argument("--log", nargs="?", const="", metavar="FILE",
                     help="also write terminal progress to FILE; without a path, use meta_dir/batchocr.log")
    ap.add_argument("--save-images", action="store_true",
                     help="retain extracted Office images (default: temporary only)")
    ap.add_argument("--no-office-ocr", action="store_true",
                     help="skip OCR of images extracted from PPTX/DOCX")
    ap.add_argument("--ocr-report", nargs="?", const="", metavar="FILE",
                     help="also write a separate Office OCR report; without a path, use meta_dir/<stem>_images_ocr.md")
    ap.add_argument("--pandoc-to", default="markdown+tex_math_dollars",
                     help="preferred Pandoc target for PPTX/DOCX")
    args = ap.parse_args()
    if args.stdout and args.output is not None:
        sys.exit("--stdout/-s and -o/--output are mutually exclusive")
    engine_for = parse_engine_overrides(args.engine, ap)

    check_tools()

    # --- resolve inputs: expand any shell-quoted glob patterns, keep literal
    # files/dirs as given. Every item here is checked to actually exist. ---
    resolved_inputs = []
    for raw in args.inputs:
        raw_str = str(raw.expanduser())
        if any(ch in raw_str for ch in "*?[") and not Path(raw_str).exists():
            matches = sorted(Path(p).resolve() for p in glob.glob(raw_str) if Path(p).is_file())
            if not matches:
                sys.exit(f"No files matched pattern: {raw_str}")
            resolved_inputs.extend(matches)
        else:
            resolved_inputs.append(Path(raw_str).resolve())
    for p in resolved_inputs:
        if not p.exists():
            sys.exit(f"Input path not found: {p}")

    # A single directory is batch mode. Anything else (one file, or several
    # files) never gets to silently swallow a positional "output" argument --
    # output is only ever taken from the explicit -o/--output flag, which is
    # what stops a second *input* file from being mistaken for an output
    # target and overwritten.
    is_dir_mode = len(resolved_inputs) == 1 and resolved_inputs[0].is_dir()
    if is_dir_mode:
        input_path = resolved_inputs[0]
        single_file = False
        selected_file = None
        explicit_files = None
    else:
        for p in resolved_inputs:
            if p.is_dir():
                sys.exit(
                    f"{p} is a directory; pass a single directory on its own, "
                    "not mixed with other inputs"
                )
        single_file = len(resolved_inputs) == 1
        input_path = resolved_inputs[0]
        selected_file = input_path if single_file else None
        explicit_files = None if single_file else resolved_inputs
        if single_file and input_path.suffix.lower() not in (
            PDF_EXT | OFFICE_EXT | CALIBRE_EXT | LIBREOFFICE_EXT | PANDOC_EXT | DIRECT_EXT | IMAGE_EXT
        ):
            sys.exit("No handler is registered for this single-file extension")

    if args.concat and single_file:
        print("[warn] --concat/-c only applies with a directory or multiple input files; ignoring",
              file=sys.stderr)
        args.concat = False

    def resolve_concat_target(requested: Path | None) -> Path:
        """Validate -o for --concat (dir batch or multi-file) and return the merge target."""
        if requested is None or not requested.expanduser().suffix:
            sys.exit(
                "--concat/-c requires -o/--output to be an exact output filename "
                "(e.g. -o notes.txt), not a directory"
            )
        target = requested.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        if args.save_images:
            print(
                "[warn] --save-images has no effect on Office files in --concat mode "
                "(each conversion uses a throwaway scratch directory)",
                file=sys.stderr,
            )
        return target

    single_output_path = None
    concat_target = None
    requested_output = args.output
    if args.stdout:
        # Real output goes to the terminal; this is just a harmless default
        # location for manifest.tsv (no per-file writes happen in this mode).
        args.output_dir = input_path if is_dir_mode else input_path.parent
        if args.save_images:
            print("[warn] --save-images has no effect on Office files with --stdout "
                  "(each conversion uses a throwaway scratch directory)", file=sys.stderr)
    elif is_dir_mode:
        if args.concat:
            concat_target = resolve_concat_target(requested_output)
            args.output_dir = None
        elif requested_output is not None:
            args.output_dir = requested_output.expanduser()
        else:
            # No -o and no --concat: merge the whole directory into
            # "<dirname>.txt" beside it -- the same "write beside the input,
            # named after it" convention single-file mode already uses.
            concat_target = input_path.parent / f"{input_path.name}.txt"
            args.output_dir = None
            args.concat = True
    elif single_file:
        if requested_output is None:
            args.output_dir = input_path.parent
        else:
            requested_output = requested_output.expanduser()
            # In single-file mode, a filename (e.g. output.txt) means exactly
            # that file; a directory (or '.') keeps the normal stem-based name.
            if requested_output.exists() and requested_output.is_dir():
                args.output_dir = requested_output
            elif requested_output.suffix:
                single_output_path = requested_output.resolve()
                args.output_dir = single_output_path.parent
            elif requested_output.exists():
                sys.exit(
                    f"{requested_output} already exists and has no file extension; point "
                    "-o/--output at a directory, or an exact filename with an extension"
                )
            else:
                args.output_dir = requested_output
    else:
        # Several explicit input files, no single shared input directory.
        if args.concat:
            concat_target = resolve_concat_target(requested_output)
            args.output_dir = None
        elif requested_output is None:
            args.output_dir = None  # each file's output is written beside itself
        else:
            requested_output = requested_output.expanduser()
            if requested_output.suffix and not (requested_output.exists() and requested_output.is_dir()):
                sys.exit(
                    "-o/--output must be a directory when multiple input files are given "
                    f"(got what looks like a single filename: {requested_output}). "
                    "Pass --concat/-c to merge them into that one file, or --stdout to "
                    "print them to the terminal instead."
                )
            args.output_dir = requested_output

    if args.output_dir is not None:
        args.output_dir = args.output_dir.expanduser().resolve()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        default_meta_dir = args.output_dir
    elif concat_target is not None:
        default_meta_dir = concat_target.parent
    else:
        default_meta_dir = input_path.parent
    args.meta_dir = (args.meta_dir or default_meta_dir).expanduser().resolve()
    args.meta_dir.mkdir(parents=True, exist_ok=True)

    def output_for(source: Path, extension: str) -> Path:
        if single_output_path is not None:
            return single_output_path
        base_dir = args.output_dir if args.output_dir is not None else source.parent
        return base_dir / f"{source.stem}{extension}"

    def should_skip(out_path: Path) -> bool:
        # No sensible "existing output" to compare against once several
        # sources are being merged into one stream (file or stdout).
        return (
            out_path.exists() and not args.force and not single_file
            and not args.concat and not args.stdout
        )

    def route_output(source: Path, extension: str, text: str) -> str:
        """Send extracted text to wherever it belongs; return a label for the log line."""
        if args.stdout:
            if single_file:
                sys.__stdout__.write(text if text.endswith("\n") else text + "\n")
                return "(stdout)"
            concat_entries[source] = text
            return "(stdout, pending merge)"
        if args.concat:
            concat_entries[source] = text
            return concat_target.name
        out_path = output_for(source, extension)
        out_path.write_text(text, encoding="utf-8")
        return out_path.name
    if args.log is not None:
        log_path = args.meta_dir / "batchocr.log" if args.log == "" else Path(args.log).expanduser().resolve()
        enable_logging(log_path)
    if args.archive_dir:
        args.archive_dir.mkdir(parents=True, exist_ok=True)
    if args.stdout:
        # Every plain print() from here on lands on stderr (still captured by
        # --log's Tee, if that's active) so real stdout carries only the text
        # written explicitly via sys.__stdout__ -- safe to pipe.
        sys.stdout = sys.stderr

    if is_dir_mode:
        # Natural (numeric-aware) sort so a folder of page images -- page2.png,
        # page10.png, ... -- merges back together in the right page order.
        all_files = sorted((p for p in input_path.iterdir() if p.is_file()), key=natural_sort_key)
    elif single_file:
        all_files = [selected_file]
    else:
        all_files = explicit_files
    pdf_files, direct_files, calibre_files, libreoffice_files, pandoc_files, office_files, image_files, other_files = [], [], [], [], [], [], [], []
    for f in all_files:
        ext = f.suffix.lower()
        if ext in PDF_EXT:
            pdf_files.append(f)
        elif ext in DIRECT_EXT:
            direct_files.append(f)
        elif ext in CALIBRE_EXT:
            calibre_files.append(f)
        elif ext in LIBREOFFICE_EXT:
            libreoffice_files.append(f)
        elif ext in PANDOC_EXT:
            pandoc_files.append(f)
        elif ext in OFFICE_EXT:
            office_files.append(f)
        elif ext in IMAGE_EXT:
            image_files.append(f)
        else:
            other_files.append(f)

    if pdf_files:
        check_pdf_tools()
    if image_files:
        check_image_tools()

    if other_files:
        print(f"[warn] {len(other_files)} file(s) have no registered handler and will be skipped:",
              file=sys.stderr)
        for f in other_files:
            print(f"       [skipped] {f.name} ({f.suffix or 'no extension'})",
                  file=sys.stderr)

    manifest_entries = {}  # source Path -> (type, pages, word_count, snippet, output_label)
    completed_sources = []  # source Paths whose output is confirmed present
    concat_entries = {}  # source Path -> extracted text, only populated in --concat/--stdout merges

    # --- ebook/comic formats: Calibre first, Pandoc fallback ---
    for f in calibre_files:
        file_started = time.monotonic()
        out_path = output_for(f, ".txt")
        if should_skip(out_path):
            print(f"[skip] {f.name} already has output")
            text = out_path.read_text(errors="replace")
            method = "existing output"
            label = out_path.name
        else:
            try:
                text, method = book_extract(f, engine_for.get(f.suffix.lower()))
            except Exception as exc:
                print(f"[warn] {f.name}: could not extract text; skipped ({exc})",
                      file=sys.stderr)
                continue
            label = route_output(f, ".txt", text)
            if not text.strip():
                print(f"[warn] {f.name}: extracted output is empty; check whether it is image-only",
                      file=sys.stderr)
            print(f"[done, {method}] {f.name} -> {label} ({len(text)} chars)"
                  f" | time {format_duration(time.monotonic() - file_started)}")
        manifest_entries[f] = (f.suffix.lower(), "-", len(text.split()), text[:300].replace("\n", " "), label)
        completed_sources.append(f)
        archive_source(f, args.archive_dir)

    # --- legacy Office/OpenDocument formats: LibreOffice -> plain text ---
    for f in libreoffice_files:
        file_started = time.monotonic()
        out_path = output_for(f, ".txt")
        if should_skip(out_path):
            print(f"[skip] {f.name} already has output")
            text = out_path.read_text(errors="replace")
            method = "existing output"
            label = out_path.name
        else:
            try:
                text = libreoffice_extract(f)
                method = "LibreOffice"
            except Exception as exc:
                print(f"[warn] {f.name}: could not extract text; skipped ({exc})",
                      file=sys.stderr)
                continue
            label = route_output(f, ".txt", text)
            print(f"[done, {method}] {f.name} -> {label} ({len(text)} chars)"
                  f" | time {format_duration(time.monotonic() - file_started)}")
        manifest_entries[f] = (f.suffix.lower(), "-", len(text.split()), text[:300].replace("\n", " "), label)
        completed_sources.append(f)
        archive_source(f, args.archive_dir)

    # --- Office formats (.docx/.pptx): Pandoc by default, LibreOffice via --engine ---
    for f in office_files:
        file_started = time.monotonic()

        if engine_for.get(f.suffix.lower()) == "libreoffice":
            out_path = output_for(f, ".txt")
            if should_skip(out_path):
                print(f"[skip] {f.name} already has output")
                text = out_path.read_text(errors="replace")
                label = out_path.name
            else:
                try:
                    text = libreoffice_extract(f)
                except Exception as exc:
                    print(f"[warn] {f.name}: could not extract text; skipped ({exc})",
                          file=sys.stderr)
                    continue
                label = route_output(f, ".txt", text)
                print(f"[done, LibreOffice] {f.name} -> {label} ({len(text)} chars)"
                      f" | time {format_duration(time.monotonic() - file_started)}")
            manifest_entries[f] = (f.suffix.lower(), "-", len(text.split()), text[:300].replace("\n", " "), label)
            completed_sources.append(f)
            archive_source(f, args.archive_dir)
            continue

        out_path = output_for(f, ".md")
        if should_skip(out_path):
            print(f"[skip] {f.name} already has output")
            text = out_path.read_text(errors="replace")
            image_count = 0
            label = out_path.name
        else:
            report_path = None
            if args.ocr_report is not None:
                report_path = (
                    args.meta_dir / f"{f.stem}_images_ocr.md"
                    if args.ocr_report == "" else Path(args.ocr_report)
                )
            print(f"[convert] {f.name}")
            if args.concat or args.stdout:
                # Pandoc needs a real file to convert into; use a throwaway
                # scratch dir and just keep the resulting text.
                with tempfile.TemporaryDirectory(prefix="batchocr-office-") as td:
                    scratch_md, image_count = process_office(
                        f, Path(td) / f"{f.stem}.md", args.pandoc_to, False,
                        not args.no_office_ocr, args.lang, report_path,
                    )
                    text = scratch_md.read_text(errors="replace")
                label = route_output(f, ".md", text)
            else:
                out_path, image_count = process_office(
                    f, out_path, args.pandoc_to, args.save_images,
                    not args.no_office_ocr, args.lang, report_path,
                )
                text = out_path.read_text(errors="replace")
                label = out_path.name
            print(f"[done, Office] {f.name} -> {label}"
                  f" ({len(text)} chars, {image_count} images OCR'd)"
                  f" | time {format_duration(time.monotonic() - file_started)}")
        manifest_entries[f] = (f.suffix.lower(), "-", len(text.split()), text[:300].replace("\n", " "), label)
        completed_sources.append(f)
        archive_source(f, args.archive_dir)

    # --- fast, non-OCR formats first ---
    for f in direct_files + pandoc_files:
        file_started = time.monotonic()
        out_path = output_for(f, ".txt")
        if should_skip(out_path):
            print(f"[skip] {f.name} already has output")
            text = out_path.read_text(errors="replace")
            label = out_path.name
        else:
            text = f.read_text(errors="replace") if f.suffix.lower() in DIRECT_EXT else pandoc_extract(f)
            label = route_output(f, ".txt", text)
            print(f"[done] {f.name} -> {label} ({len(text)} chars)"
                  f" | time {format_duration(time.monotonic() - file_started)}")
        manifest_entries[f] = (f.suffix.lower(), "-", len(text.split()), text[:300].replace("\n", " "), label)
        completed_sources.append(f)
        archive_source(f, args.archive_dir)

    # --- standalone images: direct Tesseract OCR, no rasterisation needed ---
    for f in image_files:
        file_started = time.monotonic()
        out_path = output_for(f, ".txt")
        if should_skip(out_path):
            print(f"[skip] {f.name} already has output")
            text = out_path.read_text(errors="replace")
            label = out_path.name
        else:
            text = ocr_image(f, args.lang)
            label = route_output(f, ".txt", text)
            print(f"[done, OCR] {f.name} -> {label} ({len(text)} chars)"
                  f" | time {format_duration(time.monotonic() - file_started)}")
        manifest_entries[f] = (f.suffix.lower(), "-", len(text.split()), text[:300].replace("\n", " "), label)
        completed_sources.append(f)
        archive_source(f, args.archive_dir)

    # --- PDFs ---
    pending_pdfs = []
    for pdf in pdf_files:
        out_path = output_for(pdf, ".txt")
        if should_skip(out_path):
            print(f"[skip] {pdf.name} already has output (use --force to redo)")
            completed_sources.append(pdf)
            archive_source(pdf, args.archive_dir)
            continue
        pending_pdfs.append(pdf)

    tasks = []
    for pdf in pending_pdfs:
        pages = pdf_page_count(pdf)
        if pages == 0:
            print(f"[warn] {pdf.name}: pdfinfo reported 0 pages, skipping", file=sys.stderr)
            continue

        use_native = False
        if not args.full_ocr:
            q = native_quality_for_file(pdf, pages)
            use_native = q >= args.quality_threshold
            print(f"[hybrid] {pdf.name}: native quality {q:.2f} -> "
                  f"{'using native text layer' if use_native else 'forcing OCR'}")

        if use_native:
            file_started = time.monotonic()
            text = native_extract_pdf(pdf)
            label = route_output(pdf, ".txt", text)
            manifest_entries[pdf] = (".pdf", pages, len(text.split()), text[:300].replace("\n", " "), label)
            print(f"[done, native] {pdf.name} -> {label} ({len(text)} chars, {pages} pages)"
                  f" | time {format_duration(time.monotonic() - file_started)}")
            completed_sources.append(pdf)
            archive_source(pdf, args.archive_dir)
        else:
            for p in range(1, pages + 1):
                tasks.append((pdf, p, pages))

    if tasks:
        n_files = len({t[0] for t in tasks})
        print(f"[info] OCR queue: {len(tasks)} pages across {n_files} file(s), "
              f"{args.jobs or 'auto'} workers, {args.dpi} dpi, lang={args.lang}")

        pending_counts = {}
        for pdf, p, pages in tasks:
            pending_counts[pdf] = pending_counts.get(pdf, 0) + 1
        page_results = {pdf: {} for pdf in pending_counts}

        total = len(tasks)
        done = 0
        batch_started = time.monotonic()
        last_progress_done = 0
        last_progress_time = batch_started
        file_started = {pdf: batch_started for pdf in pending_counts}
        run_tmp_root = Path(tempfile.mkdtemp(prefix="batchocr-run-"))
        ex = cf.ProcessPoolExecutor(max_workers=args.jobs)
        future_map = {
            ex.submit(ocr_one_page, pdf, p, args.dpi, args.lang, run_tmp_root): (pdf, p)
            for pdf, p, _ in tasks
        }
        try:
            for fut in cf.as_completed(future_map):
                pdf, p = future_map[fut]
                try:
                    text = fut.result()
                except Exception as e:
                    text = f"[OCR ERROR on page {p}: {e}]"
                page_results[pdf][p] = text
                pending_counts[pdf] -= 1
                done += 1
                if done % 20 == 0 or done == total:
                    progress_batch_size = done - last_progress_done
                    progress_batch_time = time.monotonic() - last_progress_time
                    print(
                        f"[progress] {done}/{total} pages OCR'd"
                        f" | elapsed {format_duration(time.monotonic() - run_started)}"
                        f" | last {progress_batch_size} pages in {format_duration(progress_batch_time)}"
                    )
                    last_progress_done = done
                    last_progress_time = time.monotonic()

                if pending_counts[pdf] == 0:
                    full_text = ""
                    for pn in sorted(page_results[pdf]):
                        full_text += f"\n\n--- Page {pn} ---\n\n{page_results[pdf][pn].strip()}\n"
                    label = route_output(pdf, ".txt", full_text)
                    pages_total = pdf_page_count(pdf)
                    manifest_entries[pdf] = (
                        ".pdf", pages_total, len(full_text.split()),
                        full_text[:300].replace("\n", " "), label,
                    )
                    print(f"[done, OCR] {pdf.name} -> {label} ({len(full_text)} chars, {pages_total} pages)"
                          f" | time {format_duration(time.monotonic() - file_started[pdf])}")
                    completed_sources.append(pdf)
                    archive_source(pdf, args.archive_dir)
                    del page_results[pdf]
        except KeyboardInterrupt:
            print(
                f"\n[interrupt] stopping after {done}/{total} pages;"
                f" elapsed {format_duration(time.monotonic() - run_started)}",
                file=sys.stderr,
            )
            stop_executor(ex, future_map)
            # Everything finished before the interrupt already has its output
            # recorded -- make sure the merge/manifest reflect that too instead
            # of being silently skipped by the early exit below.
            line_ranges = write_merged_output(concat_target, args.stdout and not single_file, concat_entries, all_files)
            manifest_rows = assemble_manifest_rows(all_files, manifest_entries, line_ranges, concat_target)
            write_manifest_file(args.meta_dir, manifest_rows, args.manifest, to_stderr=args.stdout)
            raise SystemExit(130)
        else:
            ex.shutdown(wait=True)
        finally:
            # Sweeps any page temp-dirs a forcibly-terminated worker didn't
            # get to clean up itself.
            shutil.rmtree(run_tmp_root, ignore_errors=True)

    line_ranges = write_merged_output(concat_target, args.stdout and not single_file, concat_entries, all_files)
    manifest_rows = assemble_manifest_rows(all_files, manifest_entries, line_ranges, concat_target)
    write_manifest_file(args.meta_dir, manifest_rows, args.manifest, to_stderr=args.stdout)


if __name__ == "__main__":
    main()
