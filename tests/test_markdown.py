"""Markdown-mode tests. Fixtures are synthetic and built on the fly; tests needing
PyMuPDF or Tesseract skip when those are absent."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import batchocr as B

try:
    import pymupdf
except ImportError:
    pymupdf = None

TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"


def tsv(lines, page_h=1000):
    """lines: (block, par, line, top, height, conf, text)"""
    rows = [TSV_HEADER, f"1\t1\t0\t0\t0\t0\t0\t0\t800\t{page_h}\t-1\t"]
    for blk, par, ln, top, h, conf, text in lines:
        for wi, word in enumerate(text.split(), start=1):
            rows.append(f"5\t1\t{blk}\t{par}\t{ln}\t{wi}\t{wi * 50}\t{top}\t40\t{h}\t{conf}\t{word}")
    return "\n".join(rows)


@unittest.skipUnless(pymupdf, "needs PyMuPDF")
class TsvTests(unittest.TestCase):
    def test_paragraphs_with_the_same_line_number_stay_separate_and_in_order(self):
        # Tesseract restarts line numbers in every paragraph; keying on (block, line) alone
        # merges paragraphs 1 and 2 and interleaves their lines.
        data = tsv([
            (1, 1, 1, 200, 20, 90, "first paragraph line one"),
            (1, 1, 2, 230, 20, 90, "first paragraph line two"),
            (1, 2, 1, 300, 20, 90, "second paragraph line one"),
            (1, 2, 2, 330, 20, 90, "second paragraph line two"),
        ])
        page = B.tsv_to_pagetext(data)
        self.assertEqual(len(page.blocks), 2)
        self.assertEqual([l.text() for l in page.blocks[0].lines],
                         ["first paragraph line one", "first paragraph line two"])
        self.assertEqual(page.blocks[1].lines[0].text(), "second paragraph line one")

    def test_tall_confident_capitalised_line_is_a_heading_candidate(self):
        data = tsv([
            (1, 1, 1, 100, 40, 95, "Chapter One"),
            (2, 1, 1, 300, 20, 92, "body text of the first paragraph"),
            (2, 1, 2, 330, 20, 92, "continues over here nicely"),
            (3, 1, 1, 400, 20, 92, "more body text in a later block"),
        ])
        page = B.tsv_to_pagetext(data)
        sizes = {l.text(): l.spans[0].size for b in page.blocks for l in b.lines}
        self.assertGreater(sizes["Chapter One"], 11 * 1.3)
        self.assertEqual(sizes["body text of the first paragraph"], 11.0)

    def test_noise_and_lowercase_lines_never_become_headings(self):
        data = tsv([
            (1, 1, 1, 100, 40, 30, "Xq Zz Pp"),
            (2, 1, 1, 200, 40, 95, "surprising that every party"),
            (3, 1, 1, 300, 20, 92, "body text of the first paragraph"),
            (3, 1, 2, 330, 20, 92, "continues over here nicely"),
        ])
        page = B.tsv_to_pagetext(data)
        lines = {l.text(): l.spans[0] for b in page.blocks for l in b.lines}
        self.assertEqual(lines["Xq Zz Pp"].size, 11.0)
        self.assertTrue(getattr(lines["Xq Zz Pp"], "low_conf", False))
        self.assertEqual(lines["surprising that every party"].size, 11.0)


@unittest.skipUnless(pymupdf, "needs PyMuPDF")
class CleanupTests(unittest.TestCase):
    def pages(self, *texts_per_page, ymid=None):
        from m1ck4_pdfmd.models import Block, Line, PageText, Span
        out = []
        for texts in texts_per_page:
            blocks = []
            for i, t in enumerate(texts):
                ln = Line(spans=[Span(text=t, size=11.0)])
                if ymid:
                    ln.ymid = ymid[i]
                blocks.append(Block(lines=[ln]))
            out.append(PageText(blocks=blocks))
        return out

    def test_dehyphenate_joins_and_keeps_known_compounds(self):
        from m1ck4_pdfmd.models import Block, Line, PageText, Span
        def block(*lines):
            return Block(lines=[Line(spans=[Span(text=t, size=11.0)]) for t in lines])
        page = PageText(blocks=[
            block("study actual linguistic per-", "formance is mentalistic"),
            block("the twentieth-century view", "of a twentieth-", "century idea"),
        ])
        joins = B.dehyphenate([page])
        self.assertEqual(joins, 2)
        self.assertEqual(page.blocks[0].lines[0].text(), "study actual linguistic performance is mentalistic")
        self.assertIn("twentieth-century idea", page.blocks[1].lines[-1].text())

    def test_running_header_and_page_numbers_go_but_repeated_body_lines_stay(self):
        header = "Journal of Tests"
        body = [f"{header}", "unique body line {}", "Not relevant", "{}"]
        pages = [[header, f"unique body line {i}", "Not relevant", str(i + 10)] for i in range(4)]
        ymid = [0.04, 0.4, 0.5, 0.96]
        out, removed = B.strip_running_edges(self.pages(*pages, ymid=ymid))
        kept = [ln.text() for p in out for b in p.blocks for ln in b.lines]
        self.assertNotIn(header, kept)
        self.assertFalse(any(t.isdigit() for t in kept))
        self.assertEqual(kept.count("Not relevant"), 4)          # mid-page repeat is content
        self.assertEqual(len(removed), 8)

    def test_short_documents_keep_their_headers(self):
        pages = [["Running head", "text"], ["Running head", "text"], ["Running head", "text"]]
        self.assertEqual(B.MIN_PAGES_HEADER_FOOTER, 4)  # pages_to_markdown skips edge removal below this


def build(path: Path, draw):
    doc = pymupdf.open()
    draw(doc)
    doc.save(path)


def table_page(doc):
    pg = doc.new_page()
    pg.insert_text((72, 80), "Results of the experiment", fontsize=16)
    pg.insert_textbox(pymupdf.Rect(72, 100, 520, 160),
                      "The following table lists the measured values for each sample.", fontsize=11)
    rows = [("Sample", "Mass (g)", "Volume (mL)", "Density"), ("Alpha", "12.40", "5.1", "2.43"),
            ("Beta", "8.75", "3.9", "2.24"), ("Gamma", "15.02", "6.4", "2.35"),
            ("Delta", "9.88", "4.0", "2.47"), ("Epsilon", "11.31", "5.2", "2.17")]
    for r, row in enumerate(rows):
        for x, cell in zip((72, 200, 300, 420), row):
            pg.insert_text((x, 200 + r * 20), cell, fontsize=11)
    pg.insert_textbox(pymupdf.Rect(72, 340, 520, 420), "As the table shows, density varies little.", fontsize=11)


def columns_page(doc):
    pg = doc.new_page()
    pg.insert_textbox(pymupdf.Rect(50, 60, 280, 400), "\n".join(f"left column line {i}" for i in range(1, 9)), fontsize=11)
    pg.insert_textbox(pymupdf.Rect(320, 60, 550, 400), "\n".join(f"right column line {i}" for i in range(1, 9)), fontsize=11)


def multipage(doc):
    for i in range(5):
        pg = doc.new_page()
        pg.insert_text((72, 40), "Journal of Tests", fontsize=9)
        pg.insert_text((72, 100), f"Section {i + 1}", fontsize=18)
        pg.insert_textbox(pymupdf.Rect(72, 130, 520, 300),
                          f"Body paragraph on page {i + 1} with enough words to be a paragraph of its own, "
                          "and a hyphen-\nated word that wraps. " * 2, fontsize=11)
        pg.insert_text((290, 800), str(i + 1), fontsize=9)


def run_cli(*args, **kw):
    return subprocess.run([sys.executable, str(ROOT / "batchocr.py"), *args], capture_output=True, text=True, **kw)


@unittest.skipUnless(pymupdf and shutil.which("pdftotext") and shutil.which("pdfinfo"),
                     "needs PyMuPDF and poppler")
class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def convert(self, draw, *extra):
        pdf = self.dir / "doc.pdf"
        build(pdf, draw)
        out = self.dir / "doc.md"
        r = run_cli(str(pdf), "--to", "md", "-o", str(out), "--force", "--no-ocr-check", *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return out.read_text()

    def test_real_table_becomes_a_markdown_table(self):
        md = self.convert(table_page)
        self.assertIn("| Sample | Mass (g) | Volume (mL) | Density |", md)
        self.assertIn("| Epsilon | 11.31 | 5.2 | 2.17 |", md)
        self.assertEqual(md.count("Epsilon"), 1)           # not printed again below the table
        self.assertIn("## Results of the experiment", md)

    def test_columns_read_whole(self):
        md = self.convert(columns_page)
        self.assertLess(md.index("left column line 8"), md.index("right column line 1"))

    def test_headers_removed_markers_and_page_breaks(self):
        md = self.convert(multipage, "--page-breaks")
        self.assertNotIn("Journal of Tests", md)
        self.assertEqual(md.count("<!-- Page "), 5)
        self.assertEqual(md.count("\n---\n"), 4)
        self.assertIn("hyphenated word", md)
        self.assertIn("\n# Section 3\n", md)
        self.assertNotIn("<!-- Page", self.convert(multipage, "--no-page-markers"))
        self.assertIn("Journal of Tests", self.convert(multipage, "--keep-headers"))

    def test_rerun_is_byte_identical(self):
        self.assertEqual(self.convert(multipage), self.convert(multipage))

    def test_unknown_flag_fails_with_one_line_not_a_traceback(self):
        r = run_cli("x.pdf", "--frobnicate")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)

    def test_stdout_carries_only_the_document(self):
        pdf = self.dir / "doc.pdf"
        build(pdf, columns_page)
        r = run_cli(str(pdf), "--to", "md", "--stdout", "--no-ocr-check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("<!-- Page 1 -->"), r.stdout[:80])
        self.assertNotIn("[hybrid]", r.stdout)

    def test_missing_pymupdf_is_one_clear_line(self):
        pdf = self.dir / "doc.pdf"
        build(pdf, columns_page)
        code = ("import sys; sys.modules['pymupdf']=None; sys.path.insert(0, %r); import batchocr; "
                "sys.argv=['batchocr', %r, '--to', 'md', '--stdout']; batchocr.main()" % (str(ROOT), str(pdf)))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("PyMuPDF", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_failed_file_gives_nonzero_exit(self):
        bad = self.dir / "broken.pdf"
        bad.write_bytes(b"%PDF-1.4 not really a pdf")
        r = run_cli(str(bad), "--to", "md", "-o", str(self.dir / "out.md"), "--force")
        self.assertNotEqual(r.returncode, 0)

    def test_version_needs_no_optional_dependencies(self):
        r = run_cli("--version")
        self.assertEqual(r.returncode, 0)
        self.assertRegex(r.stdout, r"^batchocr \d+\.\d+\.\d+")


@unittest.skipUnless(pymupdf and shutil.which("tesseract") and shutil.which("pdftoppm"),
                     "needs PyMuPDF, tesseract and poppler")
class ScanTests(unittest.TestCase):
    def test_image_only_pdf_goes_through_ocr_into_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = pymupdf.open()
            sp = src.new_page()
            sp.insert_text((72, 100), "Introduction", fontsize=26)
            sp.insert_textbox(pymupdf.Rect(72, 140, 520, 400),
                              "This paragraph was rendered as a picture and must be recognised by "
                              "Tesseract before it can become Markdown text.", fontsize=14)
            pix = sp.get_pixmap(dpi=200)
            doc = pymupdf.open()
            doc.new_page().insert_image(doc[0].rect if len(doc) else pymupdf.paper_rect("a4"), pixmap=pix)
            pdf = td / "scan.pdf"
            doc.save(pdf)
            out = td / "scan.md"
            r = run_cli(str(pdf), "--to", "md", "-o", str(out), "--force")
            self.assertEqual(r.returncode, 0, r.stderr)
            md = out.read_text()
            self.assertIn("recognised", md)
            self.assertIn("# Introduction", md)


if __name__ == "__main__":
    unittest.main()
