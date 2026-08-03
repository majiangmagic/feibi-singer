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
    assert checks[0].pattern == "\u83f2+\u6bd4+\u557e+\u6bd4"
    assert checks[0].accepted
    assert checks[1].pattern == "\u83f2+\u6bd4+"
    assert checks[1].accepted
    assert checks[2].pattern == "unknown"
    assert checks[2].rewritten_syllables == 0
    assert not checks[2].accepted


def test_patterns():
    assert detect_pattern(FEI + BI) == "\u83f2+\u6bd4+"
    assert detect_pattern(FEI + BI + JIU) == "\u83f2+\u6bd4+\u557e+"
    assert detect_pattern(FEI + BI + JIU + BI) == "\u83f2+\u6bd4+\u557e+\u6bd4"
    assert detect_pattern(FEI + BA) == "\u83f2+\u516b"
    assert detect_pattern(FEI + BA + JIU + BI) == "\u83f2\u516b\u557e+\u6bd4"
    assert detect_pattern(FEI + BA + FEN + QIAN) == "\u83f2\u516b\u5206\u94b1"


def test_user_approved_patterns_reject_old_unlisted_forms():
    assert detect_pattern(FEI + BI + JIU + BI) == "\u83f2+\u6bd4+\u557e+\u6bd4"
    assert detect_pattern(FEI + BA + JIU + BI) == "\u83f2\u516b\u557e+\u6bd4"
    assert detect_pattern(FEI + BI + JIU + BI + JIU) is None


def test_plus_means_one_or_more_and_final_bi_is_exact_suffix():
    assert detect_pattern(FEI * 3 + BI * 2) == "\u83f2+\u6bd4+"
    assert detect_pattern(FEI * 2 + BI * 3 + JIU * 4) == "\u83f2+\u6bd4+\u557e+"
    assert detect_pattern(FEI * 2 + BI * 2 + JIU * 3 + BI) == "\u83f2+\u6bd4+\u557e+\u6bd4"
    assert detect_pattern(FEI * 2 + BI * 2 + JIU * 3 + BI * 2) is None
    assert detect_pattern(FEI + BA) == "\u83f2+\u516b"
    assert detect_pattern(FEI * 2 + BA) == "\u83f2+\u516b"
    assert detect_pattern(FEI + BA + JIU * 3 + BI) == "\u83f2\u516b\u557e+\u6bd4"


def test_invalid_or_old_forms_are_rejected_strictly():
    assert detect_pattern("") is None
    assert detect_pattern(FEI) is None
    assert detect_pattern(FEI + BI + JIU + BI + JIU) is None
    assert detect_pattern(FEI + BA + JIU) is None
    assert detect_pattern(FEI + BA + FEN) is None
    assert detect_pattern(FEI + "x" + BI) is None
    assert detect_pattern(FEI + BI + ",") is None
    assert detect_pattern(" " + FEI + BI + " \n") == "\u83f2+\u6bd4+"
