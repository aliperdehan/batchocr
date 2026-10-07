"""Text-layer gate and reading-order tests. Fixtures are built on the fly (PyMuPDF
and Tesseract are optional: tests needing them skip when absent)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import batchocr as B

try:
    import pymupdf
except ImportError:
    pymupdf = None

PROSE = ("The quick brown fox jumps over the lazy dog while the committee reviews "
         "the findings of the previous year and considers whether further funding "
         "is warranted for the continuation of the programme. ") * 3
CYRILLIC = "Науковий вісник міжнародного гуманітарного університету містить статті про термінологію. " * 3
MOJIBAKE = "èéɋ;Ȳ<õˈ !ʐx ɭÞˀˈz.Ɍˈ58ˈ ǷɁʉɀʇˈǶʘ ɮɨɔƘ ʆʂʈˈ ɤɩʃɥ " * 4
IPA_DICTIONARY = "jeshoy: [dZeSoj] DP adj. freezing ʃ ŋ ɡ ɪ jeshven: [dZeSven] DP adj. icy " * 4


class QualityTests(unittest.TestCase):
    def test_prose_and_cyrillic_pass(self):
        self.assertGreater(B.page_quality(PROSE), 0.95)
        self.assertGreater(B.page_quality(CYRILLIC), 0.95)

    def test_broken_font_encoding_fails(self):
        self.assertLess(B.page_quality(MOJIBAKE), 0.75)
        self.assertLess(B.char_quality(MOJIBAKE), 0.5)

    def test_phonetic_dictionary_still_passes(self):
        self.assertGreater(B.page_quality(IPA_DICTIONARY), 0.85)

    def test_numeric_table_passes(self):
        table = "\n".join(f"{i}  {i * 1.5:.2f}  {i ** 2}  (p < 0.05)" for i in range(60))
        self.assertGreater(B.page_quality(table), 0.95)

    def test_empty_page_goes_to_ocr(self):
        self.assertEqual(B.page_quality(""), 0.0)
        self.assertEqual(B.page_quality("  3  \n"), 0.0)

    def test_replacement_and_private_use_characters_count_against(self):
        self.assertLess(B.char_quality("� ab"), 0.5)

    def test_word_overlap(self):
        self.assertGreater(B.word_overlap(PROSE, PROSE), 0.99)
        self.assertLess(B.word_overlap("qzxv wkrt bnmp hjkl", PROSE), 0.1)
        self.assertEqual(B.word_overlap("anything", ""), 1.0)


def two_column_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    left = [f"left column line {i}" for i in range(1, 9)]
    right = [f"right column line {i}" for i in range(1, 9)]
    page.insert_textbox(pymupdf.Rect(50, 60, 280, 400), "\n".join(left), fontsize=11)
    page.insert_textbox(pymupdf.Rect(320, 60, 550, 400), "\n".join(right), fontsize=11)
    doc.save(path)


def image_page_pdf(path: Path, visible: str, layer: str) -> None:
    """One page whose picture shows `visible` and whose invisible text layer says `layer`."""
    src = pymupdf.open()
    sp = src.new_page()
    sp.insert_textbox(pymupdf.Rect(40, 60, 560, 700), visible, fontsize=14)
    pix = sp.get_pixmap(dpi=200)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, pixmap=pix)
    page.insert_textbox(pymupdf.Rect(40, 60, 560, 700), layer, fontsize=14, render_mode=3)
    doc.save(path)


@unittest.skipUnless(pymupdf and shutil.which("pdftotext"), "needs PyMuPDF and pdftotext")
class ReadingOrderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = Path(self.tmp.name) / "two.pdf"
        two_column_pdf(self.pdf)

    def tearDown(self):
        self.tmp.cleanup()

    def assert_columns_whole(self, text):
        self.assertLess(text.index("left column line 8"), text.index("right column line 1"))

    def test_pymupdf_stream_order(self):
        self.assert_columns_whole(B.native_pages(self.pdf)[0])

    def test_pdftotext_fallback_order(self):
        saved = sys.modules.get("pymupdf")
        sys.modules["pymupdf"] = None  # makes `import pymupdf` raise ImportError
        try:
            self.assert_columns_whole(B.native_pages(self.pdf)[0])
        finally:
            sys.modules["pymupdf"] = saved

    def test_layout_flag_keeps_visual_rows(self):
        text = B.native_pages(self.pdf, layout=True)[0]
        self.assertLess(text.index("right column line 1"), text.index("left column line 8"))


@unittest.skipUnless(pymupdf and shutil.which("tesseract") and shutil.which("pdftoppm"),
                     "needs PyMuPDF, tesseract and pdftoppm")
class CrossCheckTests(unittest.TestCase):
    TEXT = ("Reading order matters when a document has several columns and the "
            "committee decided that every paragraph should keep its place on the page. ") * 4

    def plan(self, layer):
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / "p.pdf"
            image_page_pdf(pdf, self.TEXT, layer)
            pages = B.native_pages(pdf)
            return B.plan_native_pages(pdf, pages, 0.75, "eng", Path(td))

    def test_matching_layer_is_kept(self):
        keep, note = self.plan(self.TEXT)
        self.assertEqual(list(keep), [1], note)

    def test_plausible_looking_garbage_layer_is_rejected(self):
        garbage = ("qeva lori usnat dimero kalu senta mirov falu tepos anuki "
                   "rovel binat sutek morfa lenid gatu pomer ") * 4
        keep, note = self.plan(garbage)
        self.assertEqual(keep, {}, note)
        self.assertIn("corrupt", note)


if __name__ == "__main__":
    unittest.main()
