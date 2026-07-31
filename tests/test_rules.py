from feibi_singer.feibi_rules import *

def test_counts_multilingual():
    assert syllable_count(chr(0x4f60)+chr(0x597d)) == 2
    assert syllable_count("hello") == 2

def test_rewrite_preserves_count_and_ends_bi():
    out, checks = rewrite_lyrics([chr(0x6625)+chr(0x98ce)+chr(0x5439)+chr(0x8fc7), "hello world", chr(0x4f60)])
    assert out[0] == chr(0x83f2)+chr(0x556e)+chr(0x556e)+chr(0x6bd4)
    assert all(c.accepted for c in checks[:2])
    assert checks[2].rewritten_syllables == 2

def test_patterns():
    assert detect_pattern(chr(0x83f2)+chr(0x6bd4)) == "?+?+"
    assert detect_pattern(chr(0x83f2)+chr(0x6bd4)+chr(0x556e)+chr(0x6bd4)) == "?+?+?+?"
    assert detect_pattern(chr(0x83f2)+chr(0x516b)+chr(0x5206)+chr(0x94b1)) == "????"
