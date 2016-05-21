"""
Test module.
"""

from pprint import pprint

import pytest

import haags


def read_sample_file(fp):
    lines = (line.strip() for line in fp)
    lines = (line for line in lines if line and not line.startswith('#'))
    pairs = []
    for line in lines:
        a, b = line.split('/')
        pairs.append((a.strip(), b.strip()))
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
        Ken ik jou?
        Ik dacht het niet.
        WAT MAAKT MIJ HET UIT?
        van jou
    """
    expected = """
        Kennik jâh?
        Ik dachutnie.
        WAT MAAK MÈNNUT ÙIT?
        vajjâh
    """
    print(input)
    translated = haags.translate(input)
    print(translated)
    assert translated == expected


with open('samples.txt') as fp:
    pairs = read_sample_file(fp)


@pytest.mark.parametrize('dutch,expected', pairs)
def test_translation(dutch, expected):
    actual = haags.translate(dutch)
    print()
    print(dutch)
    print(expected)
    print(actual)
    print()
    assert actual == expected
