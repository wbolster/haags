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


def test_haags():
    with open('samples.txt') as fp:
        pairs = read_sample_file(fp)
    for dutch, translation in pairs:
        print(dutch)
        print(translation)
        translated = haags.translate(dutch)
        print(translated)
        print()
