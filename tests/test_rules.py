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
    assert out[0] == FEI * 2 + BI * 2
    assert checks[0].pattern == "\u83f2+\u6bd4+"
    assert checks[0].accepted
    assert checks[1].pattern == "\u83f2+\u6bd4+\u557e+"
    assert checks[1].accepted
    assert checks[2].pattern == "unknown"
    assert checks[2].rewritten_syllables == 0
    assert not checks[2].accepted


def test_patterns():
    assert detect_pattern(FEI + BI) == "\u83f2+\u6bd4+"
    assert detect_pattern(FEI + BI + JIU) == "\u83f2+\u6bd4+\u557e+"
    assert detect_pattern(FEI + BI + JIU + BI) == "\u83f2+\u6bd4+\u557e+\u6bd4"
    assert detect_pattern(FEI + BA) == "\u83f2+\u516b"
    assert detect_pattern(FEI + BA + JIU + BI) == "\u83f2+\u516b\u557e+\u6bd4"
    assert detect_pattern(FEI + BA + FEN + QIAN) == "\u83f2\u516b\u5206\u94b1"


def test_user_approved_patterns_reject_old_unlisted_forms():
    assert detect_pattern(FEI + BI + JIU + BI) == "\u83f2+\u6bd4+\u557e+\u6bd4"
    assert detect_pattern(FEI + BA + JIU + BI) == "\u83f2+\u516b\u557e+\u6bd4"
    assert detect_pattern(FEI + BI + JIU + BI + JIU) is None


def test_plus_means_one_or_more_and_final_bi_is_exact_suffix():
    assert detect_pattern(FEI * 3 + BI * 2) == "\u83f2+\u6bd4+"
    assert detect_pattern(FEI * 2 + BI * 3 + JIU * 4) == "\u83f2+\u6bd4+\u557e+"
    assert detect_pattern(FEI * 2 + BI * 2 + JIU * 3 + BI) == "\u83f2+\u6bd4+\u557e+\u6bd4"
    assert detect_pattern(FEI * 2 + BI * 2 + JIU * 3 + BI * 2) is None
    assert detect_pattern(FEI + BA) == "\u83f2+\u516b"
    assert detect_pattern(FEI * 2 + BA) == "\u83f2+\u516b"
    assert detect_pattern(FEI + BA + JIU * 3 + BI) == "\u83f2+\u516b\u557e+\u6bd4"
    assert detect_pattern(FEI * 3 + BA + JIU * 2 + BI) == "\u83f2+\u516b\u557e+\u6bd4"


def test_invalid_or_old_forms_are_rejected_strictly():
    assert detect_pattern("") is None
    assert detect_pattern(FEI) is None
    assert detect_pattern(FEI + BI + JIU + BI + JIU) is None
    assert detect_pattern(FEI + BA + JIU) is None
    assert detect_pattern(FEI + BA + FEN) is None
    assert detect_pattern(FEI + "x" + BI) is None
    assert detect_pattern(FEI + BI + ",") is None
    assert detect_pattern(" " + FEI + BI + " \n") == "\u83f2+\u6bd4+"


def test_generator_cycles_through_every_feasible_long_line_family():
    source = chr(0x4E00) * 8
    generated = [make_feibi_line(source, index) for index in range(5)]

    assert [detect_pattern(line) for line in generated] == [
        "\u83f2+\u6bd4+",
        "\u83f2+\u6bd4+\u557e+",
        "\u83f2+\u6bd4+\u557e+\u6bd4",
        "\u83f2+\u516b",
        "\u83f2+\u516b\u557e+\u6bd4",
    ]
    assert all(syllable_count(line) == 8 for line in generated)
    assert len(set(generated)) == 5


def test_generator_uses_all_six_families_for_four_syllable_lines():
    source = chr(0x4E00) * 4
    generated = [make_feibi_line(source, index) for index in range(6)]

    assert [detect_pattern(line) for line in generated] == [label for label, _pattern in PATTERN_LABELS]
    assert generated[-1] == FEI + BA + FEN + QIAN
    assert all(syllable_count(line) == 4 for line in generated)


def test_plus_groups_receive_repetitions_instead_of_padding_only_with_jiu():
    source = chr(0x4E00) * 10

    fei_bi = make_feibi_line(source, 0)
    fei_bi_jiu = make_feibi_line(source, 1)
    fei_bi_jiu_bi = make_feibi_line(source, 2)

    assert fei_bi.count(FEI) > 1 and fei_bi.count(BI) > 1
    assert fei_bi_jiu.count(FEI) > 1 and fei_bi_jiu.count(BI) > 1 and fei_bi_jiu.count(JIU) > 1
    assert fei_bi_jiu_bi.endswith(BI)
    assert fei_bi_jiu_bi.count(FEI) > 1 and fei_bi_jiu_bi.count(JIU) > 1

    fei_ba_jiu_bi = make_feibi_line(source, 4)
    assert fei_ba_jiu_bi.count(FEI) > 1 and fei_ba_jiu_bi.count(JIU) > 1


def test_rewrite_does_not_collapse_long_song_lines_to_two_templates():
    source_char = chr(0x4E00)
    lines = [source_char * length for length in (10, 12, 9, 7, 6, 6, 10, 6)]

    generated, checks = rewrite_lyrics(lines)

    assert [check.pattern for check in checks] == [
        "\u83f2+\u6bd4+",
        "\u83f2+\u6bd4+\u557e+",
        "\u83f2+\u6bd4+\u557e+\u6bd4",
        "\u83f2+\u516b",
        "\u83f2+\u516b\u557e+\u6bd4",
        "\u83f2+\u6bd4+",
        "\u83f2+\u6bd4+\u557e+",
        "\u83f2+\u6bd4+\u557e+\u6bd4",
    ]
    assert all(check.accepted for check in checks)
    assert [syllable_count(line) for line in generated] == [10, 12, 9, 7, 6, 6, 10, 6]
