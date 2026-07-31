"""Local hard validation for Feibi lyrics."""
import re
from dataclasses import dataclass

FEI, BI, JIU, BA, FEN, QIAN = map(chr, (0x83f2, 0x6bd4, 0x556e, 0x516b, 0x5206, 0x94b1))
TOKENS = (FEI, BI, JIU, BA, FEN, QIAN)

@dataclass(frozen=True)
class LineCheck:
    source_syllables: int
    rewritten_syllables: int
    accepted: bool
    pattern: str
    reasons: tuple[str, ...] = ()

def syllable_count(text: str) -> int:
    count = 0
    for word in re.findall(r"[A-Za-z]+|[\u4e00-\u9fff]|\d+", text):
        if re.fullmatch(r"[\u4e00-\u9fff]", word): count += 1
        elif word.isdigit(): count += len(word)
        else: count += max(1, len(re.findall(r"[aeiouy]+", word.lower())))
    return count

def _compact(text: str) -> str:
    return "".join(ch for ch in text if ch in TOKENS)

def detect_pattern(text: str) -> str | None:
    s = _compact(text)
    if s == FEI + BA + FEN + QIAN: return "????"
    if s == FEI + BI: return "?+?+"
    if s.startswith(FEI + BA) and JIU in s and s.endswith(BI): return "???+?"
    if s.startswith(FEI) and BI in s and JIU in s and s.endswith(BI): return "?+?+?+?"
    if s.startswith(FEI) and BI in s and JIU in s: return "?+?+?+"
    if s.startswith(FEI) and BI in s: return "?+?+"
    if s.startswith(FEI + BA): return "?+?"
    return None

def validate_line(source: str, rewritten: str) -> LineCheck:
    reasons=[]; pattern=detect_pattern(rewritten)
    src=syllable_count(source); dst=syllable_count(rewritten)
    if src != dst: reasons.append(f"syllable mismatch: source={src}, rewritten={dst}")
    if pattern is None: reasons.append("invalid Feibi pattern")
    if pattern in ("?+?+?+?", "?+?+?+", "???+?") and not _compact(rewritten).endswith(BI):
        reasons.append("pattern must end with Bi")
    return LineCheck(src,dst,not reasons,pattern or "unknown",tuple(reasons))

def make_feibi_line(source: str, index: int = 0) -> str:
    n=max(2, syllable_count(source))
    if n == 2: return FEI + BI
    middle=(JIU if index % 2 == 0 else BI) * max(0, n-2)
    return FEI + middle + BI

def rewrite_lyrics(lines: list[str]) -> tuple[list[str], list[LineCheck]]:
    out=[]; checks=[]
    for i,line in enumerate(lines):
        rewritten=make_feibi_line(line,i)
        out.append(rewritten); checks.append(validate_line(line,rewritten))
    return out,checks
