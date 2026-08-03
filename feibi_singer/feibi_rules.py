"""Local hard validation for Feibi lyrics."""
from __future__ import annotations

import re
from dataclasses import dataclass

FEI = chr(0x83F2)
BI = chr(0x6BD4)
JIU = chr(0x557E)
BA = chr(0x516B)
FEN = chr(0x5206)
QIAN = chr(0x94B1)
TOKENS = (FEI, BI, JIU, BA, FEN, QIAN)

PATTERN_LABELS: tuple[tuple[str, str], ...] = (
    ("\u83f2+\u6bd4+", rf"^{FEI}+{BI}+$"),
    ("\u83f2+\u6bd4+\u557e+", rf"^{FEI}+{BI}+{JIU}+$"),
    ("\u83f2+\u6bd4+\u557e+\u6bd4", rf"^{FEI}+{BI}+{JIU}+{BI}$"),
    ("\u83f2+\u516b", rf"^{FEI}+{BA}$"),
    ("\u83f2\u516b\u557e+\u6bd4", rf"^{FEI}{BA}{JIU}+{BI}$"),
    ("\u83f2\u516b\u5206\u94b1", rf"^{FEI}{BA}{FEN}{QIAN}$"),
)


@dataclass(frozen=True)
class LineCheck:
    source_syllables: int
    rewritten_syllables: int
    accepted: bool
    pattern: str
    reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "source_syllables": self.source_syllables,
            "rewritten_syllables": self.rewritten_syllables,
            "accepted": self.accepted,
            "pattern": self.pattern,
            "reasons": list(self.reasons),
        }


def _is_cjk_like(ch: str) -> bool:
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x3040 <= code <= 0x30FF
        or 0x31F0 <= code <= 0x31FF
        or 0xAC00 <= code <= 0xD7AF
    )


def syllable_count(text: str) -> int:
    count = 0
    latin_chunks = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+", text)
    for ch in text:
        if _is_cjk_like(ch):
            count += 1
    for chunk in latin_chunks:
        if chunk.isdigit():
            count += len(chunk)
            continue
        groups = re.findall(r"[aeiouy]+", chunk.lower())
        count += max(1, len(groups))
    return count


def _compact(text: str) -> str | None:
    """Return a whitespace-normalized line, or ``None`` for foreign symbols.

    The six user-defined forms are exact token grammars.  In particular, do
    not silently drop arbitrary characters: doing so could turn an invalid
    line such as ``?x?`` into a valid ``??`` line.
    """
    compact = "".join(ch for ch in text if not ch.isspace())
    if any(ch not in TOKENS for ch in compact):
        return None
    return compact


def detect_pattern(text: str) -> str | None:
    compact = _compact(text)
    if compact is None:
        return None
    for label, pattern in PATTERN_LABELS:
        if re.fullmatch(pattern, compact):
            return label
    return None


def validate_line(source: str, rewritten: str) -> LineCheck:
    reasons: list[str] = []
    pattern = detect_pattern(rewritten)
    source_syllables = syllable_count(source)
    rewritten_syllables = syllable_count(rewritten)
    if source_syllables != rewritten_syllables:
        reasons.append(
            f"syllable mismatch: source={source_syllables}, rewritten={rewritten_syllables}"
        )
    if pattern is None:
        reasons.append("invalid Feibi pattern")
    return LineCheck(
        source_syllables=source_syllables,
        rewritten_syllables=rewritten_syllables,
        accepted=not reasons,
        pattern=pattern or "unknown",
        reasons=tuple(reasons),
    )


def make_feibi_line(source: str, index: int = 0) -> str:
    syllables = syllable_count(source)
    if syllables < 2:
        return ""
    # Alternate only between the user-approved families. Every '+' means one
    # or more repetitions; a suffix without '+' is exactly one character.
    if syllables == 2:
        return FEI + (BI if index % 2 == 0 else BA)
    if syllables == 3:
        return FEI + BI + (JIU if index % 2 == 0 else BI)
    if syllables == 4:
        return (FEI + BI + JIU + BI) if index % 2 == 0 else FEI + BA + FEN + QIAN
    if index % 2 == 0:
        # ?+?+?+?: final ? is exactly one.
        return FEI + BI + (JIU * (syllables - 3)) + BI
    # ???+?: ????? are fixed, ? repeats as needed.
    return FEI + BA + (JIU * (syllables - 3)) + BI


def rewrite_lyrics(lines: list[str]) -> tuple[list[str], list[LineCheck]]:
    rewritten_lines: list[str] = []
    checks: list[LineCheck] = []
    for index, line in enumerate(lines):
        rewritten = make_feibi_line(line, index)
        rewritten_lines.append(rewritten)
        checks.append(validate_line(line, rewritten))
    return rewritten_lines, checks
