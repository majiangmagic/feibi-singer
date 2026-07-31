from feibi_singer.feibi_rules import *


def test_counts_multilingual():
    assert syllable_count(chr(0x4F60) + chr(0x597D)) == 2
    assert syllable_count("hello") == 2
    assert syllable_count("こんにちは") == 5


def test_rewrite_preserves_count_and_matches_pattern():
    out, checks = rewrite_lyrics([
        chr(0x6625) + chr(0x98CE) + chr(0x5439) + chr(0x8FC7),
        "hello world",
        chr(0x4F60),
    ])
    assert out[0] == chr(0x83F2) + chr(0x6BD4) + chr(0x557E) + chr(0x6BD4)
    assert checks[0].pattern == "菲+比+啾+比"
    assert checks[0].accepted
    assert checks[1].pattern == "菲+比+啾+"
    assert checks[1].accepted
    assert checks[2].pattern == "菲"
    assert checks[2].rewritten_syllables == 1


def test_patterns():
    assert detect_pattern(chr(0x83F2) + chr(0x6BD4)) == "菲+比+"
    assert detect_pattern(chr(0x83F2) + chr(0x6BD4) + chr(0x557E) + chr(0x6BD4)) == "菲+比+啾+比"
    assert detect_pattern(chr(0x83F2) + chr(0x516B) + chr(0x5206) + chr(0x94B1)) == "菲八分钱"
