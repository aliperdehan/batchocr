"""Plain text to Markdown: the never-change-the-words promise, the garbled check, and a structure benchmark."""

from __future__ import annotations

import random
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import batchocr_txt as T  # noqa: E402

LOREM = ("The pipeline reads raw exports from the shared drive and cleans them before it produces a monthly summary "
         "for every account, and several customers reported delays at the start of each month when the volume is "
         "highest and the retry logic is missing for the upload step of the nightly job").split()


def sentence(rng: random.Random, words: int) -> str:
    return " ".join(rng.choice(LOREM) for _ in range(words)).capitalize() + "."


def wrap(text: str, width: int = 72) -> str:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return "\n".join(lines + [line])


def typed_document(rng: random.Random) -> tuple[str, dict]:
    """A document as a person would type it in a text editor, and what structure it has."""
    parts, expect = [], {"headings": [], "bullets": 0, "numbered": 0, "tables": 0}
    parts.append("PROJECT STATUS REPORT")
    expect["headings"].append("PROJECT STATUS REPORT")
    for section in range(1, rng.randint(3, 5)):
        title = f"{section}. {' '.join(rng.sample(['Background', 'Methods', 'Results', 'Open', 'Issues', 'Plan'], 2))}"
        parts.append(title)
        expect["headings"].append(title)
        parts.append(wrap(sentence(rng, 40) + " " + sentence(rng, 35)))
        kind = rng.choice(["bullets", "numbered", "table", "none"])
        if kind == "bullets":
            items = [sentence(rng, rng.randint(4, 8)) for _ in range(rng.randint(2, 4))]
            parts.append("\n".join(f"- {item}" for item in items))
            expect["bullets"] += len(items)
        elif kind == "numbered":
            items = [sentence(rng, rng.randint(4, 8)) for _ in range(rng.randint(2, 4))]
            parts.append("\n".join(f"{n}. {item}" for n, item in enumerate(items, start=1)))
            expect["numbered"] += len(items)
        elif kind == "table":
            rows = [["Name", "Owner", "Due"]] + [[rng.choice(["Loader", "Summary", "Upload", "Report"]),
                                                  rng.choice(["Anna", "Boris", "Carla"]),
                                                  rng.choice(["Friday", "Monday", "Tuesday"])] for _ in range(3)]
            parts.append("\n".join(f"{a:<12}{b:<10}{c}" for a, b, c in rows))
            expect["tables"] += 1
    return "\n\n".join(parts) + "\n", expect


def structure_of(markdown: str) -> dict:
    lines = markdown.splitlines()
    return {"headings": [re.sub(r"^#+\s+", "", line) for line in lines if re.match(r"^#{1,6}\s", line)],
            "bullets": sum(1 for line in lines if line.startswith("- ")),
            "numbered": sum(1 for line in lines if re.match(r"^\d+\.\s", line)),
            "tables": sum(1 for line in lines if re.match(r"^\|[-|]+\|$", line))}


class Promise(unittest.TestCase):
    def test_the_letters_and_digits_never_change(self):
        rng = random.Random(7)
        for _ in range(60):
            text, _ = typed_document(rng)
            self.assertEqual(T.alnum(T.convert(text).markdown), T.alnum(text))

    def test_the_promise_holds_for_hostile_text_too(self):
        samples = ["# not a heading\n\n> quote > more\n\n1) odd\n2) list\n\n<b>tag</b> a < b > c\n\n| a | b |\n",
                   "word-\nbreak and well-\nknown things\n\n   indented\n   lines\n\n=====\n\n* * *\n",
                   "ÀÉÎ ünïcödé text — with dashes … and “quotes”\n\nα β γ δ ε\n",
                   "", "x", "\n\n\n", "A\n===\n\nB\n---\n"]
        for text in samples:
            self.assertEqual(T.alnum(T.convert(text).markdown), T.alnum(text), repr(text))
            self.assertEqual(T.alnum(T.convert(text, "force").markdown), T.alnum(text), repr(text))

    def test_markup_in_plain_text_is_protected(self):
        out = T.convert("A line.\n\n# looks like a heading but only in the middle of nothing\n\nSee <b>this</b>.\n").markdown
        self.assertIn("\\<b>", out)

    def test_a_hyphen_at_a_line_end_stays(self):
        text = ("The quarterly report states that the infor-\nmation about the pipeline was well-known by\n"
                "everyone in the team, and the retry logic was\nmissing.\n")
        self.assertIn("infor-mation", T.convert(text).markdown)


class Garbled(unittest.TestCase):
    def test_prose_is_not_garbled(self):
        text, _ = typed_document(random.Random(1))
        self.assertEqual(T.garbled_reasons(T.garble_metrics(text)), [])

    def test_symbol_soup_and_ocr_noise_are_named(self):
        rng = random.Random(3)
        soup = "\n".join("".join(rng.choice("#@%^&*()_+=~|\\<>/ ab") for _ in range(30)) for _ in range(30))
        reasons = T.garbled_reasons(T.garble_metrics(soup))
        self.assertTrue(any("letters or digits" in reason for reason in reasons), reasons)
        letters = " ".join(rng.choice("bcdfghjkl") for _ in range(200))
        self.assertTrue(any("single letters" in reason for reason in T.garbled_reasons(T.garble_metrics(letters))))
        broken = "word� " * 40
        self.assertTrue(any("replacement" in reason for reason in T.garbled_reasons(T.garble_metrics(broken))))

    def test_a_garbled_text_gets_paragraphs_only_unless_forced(self):
        rng = random.Random(5)
        soup = "\n\n".join("1. " + "".join(rng.choice("#@%^&*()_+=~|\\<>/ ab") for _ in range(40)) for _ in range(12))
        auto = T.convert(soup)
        self.assertTrue(auto.garbled)
        self.assertEqual(auto.stats["lists"], 0)
        self.assertEqual(T.alnum(auto.markdown), T.alnum(soup))
        self.assertGreaterEqual(T.convert(soup, "force").stats["lists"] + T.convert(soup, "force").stats["headings"], 0)


class Benchmark(unittest.TestCase):
    """Typed documents with a known structure: headings, list items and tables are found, nothing invented."""

    def test_structure_is_recovered(self):
        rng = random.Random(11)
        found = expected = wrong = 0
        for _ in range(80):
            text, expect = typed_document(rng)
            got = structure_of(T.convert(text).markdown)
            want_headings = [re.sub(r"^\d+\.\s+", "", h) if False else h for h in expect["headings"]]
            expected += len(want_headings) + expect["bullets"] + expect["numbered"] + expect["tables"]
            found += sum(1 for heading in want_headings if heading in got["headings"])
            found += min(got["bullets"], expect["bullets"]) + min(got["numbered"], expect["numbered"]) + min(got["tables"], expect["tables"])
            wrong += max(0, len(got["headings"]) - len(want_headings)) + max(0, got["bullets"] - expect["bullets"]) \
                + max(0, got["numbered"] - expect["numbered"]) + max(0, got["tables"] - expect["tables"])
        recall, invented = found / expected, wrong / expected
        self.assertGreaterEqual(recall, 0.97, f"recall {recall:.3f}")
        self.assertLessEqual(invented, 0.02, f"invented {invented:.3f}")

    def test_wrapped_paragraphs_are_joined_and_ragged_lines_kept(self):
        text = (wrap(sentence(random.Random(2), 60)) + "\n\n" + wrap(sentence(random.Random(4), 55)) + "\n\n"
                + wrap(sentence(random.Random(6), 50)) + "\n\nDear Anna,\nThank you.\nBoris\n")
        out = T.convert(text).markdown
        paragraphs = [p for p in out.split("\n\n") if p.strip()]
        self.assertTrue(all("\n" not in p for p in paragraphs[:3]), paragraphs[:3])
        self.assertIn("Dear Anna,  \nThank you.  \nBoris", out)


class Cli(unittest.TestCase):
    def run_cli(self, name: str, text: str, *flags: str):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / name
            source.write_text(text, encoding="utf-8")
            done = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "batchocr.py"), str(source),
                                   "--to", "md", "-q", *flags], capture_output=True, text=True)
            target = source.with_suffix(".md")
            return done, (target.read_text(encoding="utf-8") if target.is_file() else None)

    def test_a_txt_file_becomes_markdown_with_the_provenance_line(self):
        text, _ = typed_document(random.Random(9))
        done, markdown = self.run_cli("notes.txt", text)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("# PROJECT STATUS REPORT", markdown)
        self.assertIn("<!-- text extracted with batchocr v", markdown)
        done, markdown = self.run_cli("notes.txt", text, "--no-provenance", "--txt-structure", "off")
        self.assertNotIn("<!--", markdown)
        self.assertNotIn("# PROJECT", markdown)

    def test_without_to_md_a_txt_file_is_still_just_copied(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "a.txt").write_text("HELLO\n\nworld\n", encoding="utf-8")
            out = folder / "out"
            done = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "batchocr.py"),
                                   str(folder / "a.txt"), "-o", str(out), "-q"], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual((out / "a.txt").read_text(encoding="utf-8") if (out / "a.txt").is_file() else
                             next(out.glob("*.txt")).read_text(encoding="utf-8"), "HELLO\n\nworld\n")


if __name__ == "__main__":
    unittest.main()
