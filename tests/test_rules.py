from feibi_singer.feibi_rules import *

FEI = chr(0x83F2)
BI = chr(0x6BD4)
JIU = chr(0x557E)
BA = chr(0x516B)
FEN = chr(0x5206)
QIAN = chr(0x94B1)
JAPANESE = ''.join(chr(cp) for cp in [0x3053, 0x3093, 0x306B, 0x3061, 0x306F])


def test_counts_multilingual():
    assert syllable_count(chr(0x4F60) + chr(0x597D)) == 2
    assert syllable_count("hello") == 2
    assert syllable_count(JAPANESE) == 5


def test_rewrite_preserves_count_and_matches_pattern():
    out, checks = rewrite_lyrics([
        chr(0x6625) + chr(0x98CE) + chr(0x5439) + chr(0x8FC7),
        "hello world",
        chr(0x4F60),
    ])
    assert out[0] == FEI + BI + JIU + BI
    assert checks[0].pattern == "????"
    assert checks[0].accepted
    assert checks[1].pattern == "??"
    assert checks[1].accepted
    assert checks[2].pattern == "?"
    assert checks[2].rewritten_syllables == 1


def test_patterns():
    assert detect_pattern(FEI + BI) == "??"
    assert detect_pattern(FEI + BI + JIU + BI) == "????"
    assert detect_pattern(FEI + BA + FEN + QIAN) == "????"
