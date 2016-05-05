"""
Test module.
"""

from pprint import pprint

import haags


def read_sample_file(fp):
    lines = (line.strip() for line in fp)
    lines = (line for line in lines if line and not line.startswith('#'))
    pairs = []
    while lines:
        a, b, *lines = lines
        pairs.append((a, b))
    return pairs


def test_letter_case():
    assert haags.detect_case('lekker') == 'lower'
    assert haags.detect_case('LEKKER') == 'upper'
    assert haags.detect_case('Haags') == 'sentence'
    assert haags.detect_case('IJsland is mooi') == 'sentence'
    assert haags.detect_case('Dit Is Niet Gangbaar.') == 'title'
    assert haags.detect_case('IJsland Title Case IJsland.') == 'title'
    assert haags.detect_case('BrEeZâH') == 'other'

    assert haags.recase('lekker', 'upper') == 'LEKKER'
    assert haags.recase('lekKER', 'lower') == 'lekker'
    assert haags.recase('ijsland', 'title') == 'IJsland'


def test_tokenize():
    input = "'t duurde 3,14 lange,    bange dagen."
    tokens = list(haags.tokenize(input))
    pprint(tokens)
    assert ''.join(t.value for t in tokens) == input
    assert len(tokens) == 13
    assert tokens[0].value == "'t"
    assert tokens[1].type == "whitespace"
    assert tokens[2].value == "duurde"
    assert tokens[4].type == "number"
    assert tokens[4].value == "3,14"
    assert tokens[7].value == ","
    assert tokens[7].type == "punctuation"

    input = (
        "De informatie is te vinden op "
        "http://example.org/een/of/andere/pagina.html.")
    pprint(list(haags.tokenize(input)))


def test_contraction():
    input = """
        Hallo, ken ik jou? Ik dacht het niet.
        WAT KAN MIJ HET ROTTEN? Ik houd van jou.
    """
    expected = """
        Hallo, kennik jou? Ik dachutnie.
        WAT KAN MÈNNUT ROTTEN? Ik houd vajjâh.
    """
    print(input)
    translated = haags.translate(input)
    print(translated)
    assert translated == expected


def test_haags():
    with open('samples.txt') as fp:
        pairs = read_sample_file(fp)
    for dutch, translation in pairs:
        translated = haags.translate(dutch)
        print(dutch)
        print(translation)
        print(translated)
        print()
