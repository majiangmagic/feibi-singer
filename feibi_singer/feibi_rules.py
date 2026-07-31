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
    ("菲+比+啾+比", rf"^{FEI}+{BI}+{JIU}+{BI}+$"),
    ("菲+比+啾+", rf"^{FEI}+{BI}+{JIU}+$"),
    ("菲+比+", rf"^{FEI}+{BI}+$"),
    ("菲+八啾+比", rf"^{FEI}+{BA}+{JIU}+{BI}+$"),
    ("菲+八+", rf"^{FEI}+{BA}+$"),
    ("菲八分钱", rf"^{FEI}{BA}{FEN}{QIAN}$"),
    ("菲", rf"^{FEI}$"),
)


@dataclass(frozen=True)
class LineCheck:
    source_syllables: int
    rewritten_syllables: int
    accepted: bool
    pattern: str
    reasons: tuple[str, ...] = ()


def syllable_count(text: str) -> int:
    count = 0
    for word in re.findall(r"[A-Za-z]+|[぀-ヿ]|[一-鿿]|\d+", text):
        if re.fullmatch(r"[぀-ヿ]|[一-鿿]", word):
            count += len(word)
        elif word.isdigit():
            count += len(word)
        else:
            count += max(1, len(re.findall(r"[aeiouy]+", word.lower())))
    return count


def _compact(text: str) -> str:
    return "".join(ch for ch in text if ch in TOKENS)


def detect_pattern(text: str) -> str | None:
    compact = _compact(text)
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
    if syllables <= 0:
        return ""
    if syllables == 1:
        return FEI
    if syllables == 2:
        return FEI + BI
    if syllables == 3:
        return FEI + BI + JIU
    if syllables == 4:
        return (FEI + BI + JIU + BI) if index % 2 == 0 else (FEI + BA + FEN + QIAN)
    if index % 2 == 0:
        return FEI + BI + (JIU * (syllables - 3)) + BI
    return FEI + BA + (JIU * (syllables - 3)) + BI


def rewrite_lyrics(lines: list[str]) -> tuple[list[str], list[LineCheck]]:
    rewritten_lines: list[str] = []
    checks: list[LineCheck] = []
    for index, line in enumerate(lines):
        rewritten = make_feibi_line(line, index)
        rewritten_lines.append(rewritten)
        checks.append(validate_line(line, rewritten))
    return rewritten_lines, checks
