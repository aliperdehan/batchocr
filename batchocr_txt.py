"""Plain text to Markdown, for `batchocr notes.txt --to md`.

A plain-text file has no fonts, so structure can only be guessed from how people type: a short line in capitals,
`1.2 Title`, an underline of `====`, bullets, runs of numbered lines, columns separated by runs of spaces,
indented blocks, lines wrapped at one column. This reads those cues and writes Markdown. Two promises:

1. **The words never change.** The letters and digits of the output, in order, are the input's (headings get `#`,
   lists `-`, tables `|`, a wrapped line is joined to the next with a space; a hyphen at a line end stays). The
   check runs on every conversion; if it ever fails, the text comes out as plain paragraphs instead.
2. **A text that is already garbled is not given structure.** Measured, not felt: the share of letters and digits
   among the characters, replacement characters, very short lines, one-letter "words", the average word length.
   Past a threshold the conversion keeps paragraphs only and says which rule fired (`structure="force"` skips this).

No dependencies. `convert(text)` returns a `Result`; `garble_metrics(text)` is the measurement alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# thresholds of the garbled check (see garble_metrics): a text past any of them gets paragraphs only
GARBLE_LIMITS = {
    "alnum_ratio_min": 0.60,        # letters and digits among the non-space characters
    "replacement_ratio_max": 0.002,  # U+FFFD and control characters per character
    "short_line_ratio_max": 0.60,    # share of lines of 12 characters or fewer (checked from 20 lines on)
    "single_letter_ratio_max": 0.30,  # one-letter words among the words, a, I and the like excluded
    "word_length_min": 2.0, "word_length_max": 14.0,   # average word length
}

BULLET = re.compile(r"^(\s*)([-*+•·▪●◦⁃‣o])\s+(\S.*)$")
NUMBERED = re.compile(r"^(\s*)(\d{1,3})([.)])\s+(\S.*)$")
LETTERED = re.compile(r"^(\s*)\(?([a-zA-Z])[.)]\s+(\S.*)$")
SETEXT = re.compile(r"^\s*([=\-~*#_+])\1{2,}\s*$")
RULE = re.compile(r"^\s*(?:[-=_*]\s?){3,}\s*$")
NUMBERED_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+(\S.*)$")
WORD_HEADING = re.compile(r"^(chapter|part|section|appendix|book|article)\s+([0-9ivxlcdm]+|[a-z])\b[.:]?(?:\s+\S.*)?$", re.I)
ROMAN_HEADING = re.compile(r"^([IVXLCDM]{1,6})[.)]\s+(\S.*)$")
CELL_SPLIT = re.compile(r"\t+|\s{2,}")
LINE_START_HAZARD = re.compile(r"^(#{1,6}(\s|$)|>|[-+*]\s|\d+[.)]\s|=+\s*$|-{3,}\s*$|\||```|~~~|\[\d+\]:)")


@dataclass
class Result:
    markdown: str
    garbled: bool = False
    reasons: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def alnum(text: str) -> str:
    """The letters and digits of `text`, nothing else: what must survive a conversion."""
    return "".join(char for char in text if char.isalnum())


def garble_metrics(text: str) -> dict:
    """The measurements the garbled check rests on, for any text."""
    characters = len(text)
    visible = [char for char in text if not char.isspace()]
    lines = [line for line in text.splitlines() if line.strip()]
    words = re.findall(r"[^\W_]+", text)
    short = sum(1 for line in lines if len(line.strip()) <= 12)
    singles = sum(1 for word in words if len(word) == 1 and word.lower() not in ("a", "i", "o") and not word.isdigit())
    bad = sum(1 for char in text if char == "�" or (ord(char) < 32 and char not in "\n\r\t\f"))
    return {
        "characters": characters,
        "lines": len(lines),
        "words": len(words),
        "alnum_ratio": (sum(1 for char in visible if char.isalnum()) / len(visible)) if visible else 1.0,
        "replacement_ratio": bad / characters if characters else 0.0,
        "short_line_ratio": short / len(lines) if lines else 0.0,
        "single_letter_ratio": singles / len(words) if words else 0.0,
        "word_length": (sum(len(word) for word in words) / len(words)) if words else 0.0,
    }


def garbled_reasons(metrics: dict) -> list[str]:
    """Which rules of GARBLE_LIMITS the measurements break (empty: the text is fine)."""
    limits, reasons = GARBLE_LIMITS, []
    if metrics["words"] < 5:
        return reasons                                    # too little to judge
    if metrics["alnum_ratio"] < limits["alnum_ratio_min"]:
        reasons.append(f"only {metrics['alnum_ratio']:.0%} of the characters are letters or digits")
    if metrics["replacement_ratio"] > limits["replacement_ratio_max"]:
        reasons.append(f"{metrics['replacement_ratio']:.1%} of the characters are replacement or control characters")
    if metrics["lines"] >= 20 and metrics["short_line_ratio"] > limits["short_line_ratio_max"]:
        reasons.append(f"{metrics['short_line_ratio']:.0%} of the lines are 12 characters or fewer")
    if metrics["single_letter_ratio"] > limits["single_letter_ratio_max"]:
        reasons.append(f"{metrics['single_letter_ratio']:.0%} of the words are single letters")
    if not limits["word_length_min"] <= metrics["word_length"] <= limits["word_length_max"]:
        reasons.append(f"the average word is {metrics['word_length']:.1f} letters long")
    return reasons


# ---------------------------------------------------------------------------
# reading the text

def normalise(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n\n").replace(" ", " ")
    return [line.rstrip() for line in text.split("\n")]


def blocks_of(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    fence = None
    for line in lines:
        stripped = line.strip()
        if fence is None and re.match(r"^(```|~~~)", stripped):
            fence = stripped[:3]
            if current:
                blocks.append(current)
                current = []
            current.append(line)
            continue
        if fence is not None:
            current.append(line)
            if stripped.startswith(fence) and len(current) > 1:
                blocks.append(current)
                current, fence = [], None
            continue
        if stripped == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def dedent(lines: list[str]) -> list[str]:
    margin = min((indent_of(line) for line in lines if line.strip()), default=0)
    return [line[margin:] for line in lines]


def wrap_column(blocks: list[list[str]]) -> int:
    """The column text was wrapped at: the 90th percentile of the line lengths of multi-line blocks (not the
    last line of each). 0 when nothing in the text is wrapped."""
    lengths = sorted(len(line.strip()) for block in blocks if len(block) >= 3 for line in block[:-1])
    if len(lengths) < 6:
        lengths = sorted(len(line.strip()) for block in blocks if len(block) >= 2 for line in block[:-1])
    if not lengths:
        return 0
    if len(lengths) < 3:
        return lengths[-1]                       # too little to take a percentile of: the longest line
    return lengths[int(0.9 * (len(lengths) - 1))]


def is_wrapped(block: list[str], column: int) -> bool:
    if len(block) < 2 or column < 30:
        return False
    body = block[:-1]
    long = sum(1 for line in body if len(line.strip()) >= 0.72 * column)
    return long >= 0.6 * len(body)


def is_caps_heading(line: str) -> bool:
    text = line.strip()
    letters = [char for char in text if char.isalpha()]
    return (2 <= len(letters) and len(text) <= 70 and not text.endswith((".", ",", ";", ":", "!", "?"))
            and all(char.isupper() for char in letters) and len(text.split()) <= 10
            and not NUMBERED.match(text) and not BULLET.match(text))


def looks_like_title(line: str) -> bool:
    text = line.strip()
    words = text.split()
    return (0 < len(words) <= 9 and len(text) <= 70 and not text.endswith((".", ",", ";", "!", "?", ":"))
            and not BULLET.match(text) and not NUMBERED.match(text)
            and (text[0].isupper() or text[0].isdigit()) and sum(1 for char in text if char.isalpha()) >= 3)


def heading_of(line: str, first: bool, neighbours_numbered: bool) -> tuple[int, str] | None:
    """(level, text) when a lone line reads as a heading."""
    text = line.strip()
    if not text or len(text) > 90:
        return None
    match = re.match(r"^(#{1,6})\s+(\S.*)$", text)
    if match:
        return len(match.group(1)), match.group(2)
    if WORD_HEADING.match(text) and len(text.split()) <= 12 and not text.endswith((",", ";")):
        return 1, text
    if not neighbours_numbered:
        match = NUMBERED_HEADING.match(text)
        if (match and match.group(2)[0].isupper() and not text.endswith((".", ",", ";", ":", "?", "!"))
                and len(match.group(2).split()) <= 12):
            return min(match.group(1).count(".") + 1, 4), text
        match = ROMAN_HEADING.match(text)
        if match and match.group(2)[0].isupper() and not text.endswith((".", ",", ";")) and len(match.group(2).split()) <= 10:
            return 1, text
    if is_caps_heading(text):
        return (1 if first else 2), text
    return None


# ---------------------------------------------------------------------------
# writing Markdown

def protect(text: str) -> str:
    """Keep a line's start and any `<tag>` from being read as Markdown or HTML; no letter or digit changes."""
    if LINE_START_HAZARD.match(text):
        text = "\\" + text
    return re.sub(r"<(?=[A-Za-z/!])", r"\\<", text)


def join_wrapped(lines: list[str]) -> str:
    out = lines[0].strip()
    for line in lines[1:]:
        piece = line.strip()
        if re.search(r"[A-Za-z]-$", out) and piece[:1].isalpha():
            out += piece                       # a hyphen at a line end stays; the two halves meet
        else:
            out += " " + piece
    return out


def paragraph(lines: list[str], wrapped: bool, keep_breaks: bool) -> str:
    if wrapped or not keep_breaks or len(lines) == 1:
        return protect(join_wrapped(lines))
    return "  \n".join(protect(line.strip()) for line in lines)


def pipe_cells(row: list[str]) -> str:
    return "| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |"


def as_table(block: list[str]) -> str | None:
    rows = []
    for line in block:
        if RULE.match(line) and rows:
            continue
        cells = [cell.strip() for cell in CELL_SPLIT.split(line.strip()) if cell.strip()]
        rows.append(cells)
    if len(rows) < 2:
        return None
    counts = [len(row) for row in rows]
    common = max(set(counts), key=counts.count)
    if common < 2 or counts.count(common) < 0.8 * len(rows) or any(len(cell) > 48 for row in rows for cell in row):
        return None
    rows = [row for row in rows if len(row) == common]
    if len(rows) < 2:
        return None
    lines = [pipe_cells(rows[0]), "|" + "|".join("---" for _ in range(common)) + "|"]
    return "\n".join(lines + [pipe_cells(row) for row in rows[1:]])


def as_bullets(block: list[str]) -> str | None:
    items: list[list[str]] = []
    for line in block:
        match = BULLET.match(line)
        if match and (indent_of(line) <= 6):
            items.append([match.group(3)])
        elif items and line.strip():
            items[-1].append(line.strip())
        else:
            return None
    if not items:
        return None
    return "\n".join("- " + protect(join_wrapped(item)) for item in items)


def as_numbered(block: list[str]) -> str | None:
    items: list[tuple[str, list[str]]] = []
    for line in block:
        match = NUMBERED.match(line)
        if match:
            items.append((match.group(2), [match.group(4)]))
        elif items and line.strip():
            items[-1][1].append(line.strip())
        else:
            return None
    if len(items) < 2 and not (items and block[0].lstrip()[0].isdigit() and len(block) == 1):
        return None
    numbers = [int(number) for number, _ in items]
    if len(items) >= 2 and numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        return None
    return "\n".join(f"{number}. {protect(join_wrapped(item))}" for number, item in items)


def as_lettered(block: list[str]) -> str | None:
    items: list[list[str]] = []
    letters: list[str] = []
    for line in block:
        match = LETTERED.match(line)
        if match:
            items.append([match.group(3)])
            letters.append(match.group(2))
        elif items and line.strip():
            items[-1].append(line.strip())
        else:
            return None
    if len(items) < 2 or [ord(letter.lower()) for letter in letters] != list(range(ord(letters[0].lower()), ord(letters[0].lower()) + len(letters))):
        return None
    # a bullet that keeps its letter: lettered lists are not Markdown everywhere (GitHub-flavoured has none)
    return "\n".join(f"- {letter}) {protect(join_wrapped(item))}" for letter, item in zip(letters, items))


CODE_HINT = re.compile(r"[{};]\s*$|\(\)|=>|==|\b(def|return|function|import|class|if|for|while|print)\b|^\s*(#include|//|/\*|\$ )")


def looks_like_code(raw: list[str]) -> bool:
    """An indented block whose layout is its content: every line indented four columns, or indentation that
    varies together with code-like lines."""
    lines = [line for line in raw if line.strip()]
    if len(lines) < 2:
        return False
    indents = [indent_of(line) for line in lines]
    if min(indents) >= 4:
        return True
    return (min(indents) >= 2 and max(indents) - min(indents) >= 2
            and sum(1 for line in lines if CODE_HINT.search(line)) >= max(1, len(lines) // 3))


def convert_blocks(blocks: list[list[str]], structure: bool) -> tuple[str, dict]:
    stats = {"headings": 0, "lists": 0, "tables": 0, "code": 0, "paragraphs": 0}
    column = wrap_column(blocks)
    out: list[str] = []
    heading_at: dict[int, tuple[int, str]] = {}      # output position -> (level, text)
    seen_heading = False
    for index, raw in enumerate(blocks):
        block = [line for line in raw]
        if re.match(r"^(```|~~~)", block[0].strip()):
            out.append("\n".join(block))
            stats["code"] += 1
            continue
        if not structure:
            out.append(paragraph(dedent(block), True, False))
            stats["paragraphs"] += 1
            continue
        block = dedent(block)
        # already Markdown: ATX headings and pipe tables stay as they are
        if all(line.lstrip().startswith("|") for line in block) and len(block) >= 2:
            out.append("\n".join(line.strip() for line in block))
            stats["tables"] += 1
            continue
        # a setext heading with its text lines
        if len(block) >= 2 and SETEXT.match(block[1]) and not BULLET.match(block[0]):
            level = 1 if block[1].strip()[0] in "=#" else 2
            heading_at[len(out)] = (level, block[0].strip())
            out.append("")
            stats["headings"] += 1
            seen_heading = True
            rest = block[2:]
            if rest:
                blocks_after = rest
                out.append(paragraph(blocks_after, is_wrapped(blocks_after, column), True))
                stats["paragraphs"] += 1
            continue
        next_block = blocks[index + 1] if index + 1 < len(blocks) else None
        previous_block = blocks[index - 1] if index else None
        # "1. Title" alone between two other lone numbered lines is an item of a list spread over paragraphs
        lone_numbered = lambda other: other is not None and len(other) == 1 and NUMBERED.match(other[0]) is not None
        if len(block) == 1:
            found = heading_of(block[0], not seen_heading and index == 0, lone_numbered(next_block) or lone_numbered(previous_block))
            if found:
                level, text = found
                text = re.sub(r"^#{1,6}\s+", "", text)
                heading_at[len(out)] = (level, text)
                out.append("")
                stats["headings"] += 1
                seen_heading = True
                continue
            if index == 0 and looks_like_title(block[0]) and next_block is not None:
                heading_at[len(out)] = (1, block[0].strip())
                out.append("")
                stats["headings"] += 1
                seen_heading = True
                continue
        # a heading line running straight into its text (what a PDF's text layer gives): "I. INTRODUCTION" then lines
        if (len(block) >= 2 and not any(pattern.match(block[1]) for pattern in (BULLET, NUMBERED, LETTERED))
                and (is_caps_heading(block[0]) or ROMAN_HEADING.match(block[0].strip()) or
                     NUMBERED_HEADING.match(block[0].strip()))):
            found = heading_of(block[0], False, False)
            if found and (found[1] == block[0].strip()):
                heading_at[len(out)] = found
                out.append("")
                stats["headings"] += 1
                seen_heading = True
                block = block[1:]
                raw = raw[len(raw) - len(block):]
        for converter in (as_bullets, as_numbered, as_lettered):
            made = converter(block)
            if made:
                out.append(made)
                stats["lists"] += 1
                break
            # "Next steps:" and then the items, in one block
            if len(block) >= 3 and block[0].rstrip().endswith(":") and not BULLET.match(block[0]) and not NUMBERED.match(block[0]):
                made = converter(block[1:])
                if made:
                    out.append(protect(block[0].strip()))
                    out.append(made)
                    stats["lists"] += 1
                    stats["paragraphs"] += 1
                    break
        else:
            table = as_table(block) if len(block) >= 2 and not is_wrapped(block, column) else None
            if table:
                out.append(table)
                stats["tables"] += 1
            elif looks_like_code(raw):
                out.append("```\n" + "\n".join(line.rstrip() for line in raw) + "\n```")    # layout is the content
                stats["code"] += 1
            else:
                out.append(paragraph(block, is_wrapped(block, column), True))
                stats["paragraphs"] += 1
    shift = 0
    if heading_at:
        first = min(heading_at)
        others = [level for position, (level, _) in heading_at.items() if position != first]
        if first == 0 and heading_at[first][0] == 1 and 1 in others:
            shift = 1                                 # one title above, so "1. Background" is a section of it
    for position, (level, text) in heading_at.items():
        mark = 1 if position == min(heading_at) and shift else min(level + shift, 6)
        out[position] = "#" * mark + " " + protect(text).lstrip("\\")
    return "\n\n".join(out), stats


def convert(text: str, structure: str = "auto") -> Result:
    """`text` as Markdown. `structure`: `auto` (guess structure unless the text measures as garbled), `force`
    (always), `off` (paragraphs only)."""
    if structure not in ("auto", "force", "off"):
        raise ValueError("structure must be auto, force or off")
    metrics = garble_metrics(text)
    reasons = garbled_reasons(metrics)
    garbled = bool(reasons) and structure == "auto"
    blocks = blocks_of(normalise(text))
    use_structure = structure == "force" or (structure == "auto" and not reasons)
    markdown, stats = convert_blocks(blocks, use_structure)
    if alnum(markdown) != alnum(text):
        # the promise: never a changed word. Fall back to plain paragraphs; if even that differs, the text as is.
        markdown, stats = convert_blocks(blocks, False)
        reasons = reasons + ["the structured conversion would have changed the text; paragraphs only"]
        if alnum(markdown) != alnum(text):
            markdown = "\n".join(normalise(text))
            reasons.append("paragraph conversion changed the text too; kept as typed")
        garbled = True
    stats = {**stats, **{key: round(value, 3) if isinstance(value, float) else value for key, value in metrics.items()}}
    return Result(markdown.strip() + "\n", garbled, reasons, stats)
