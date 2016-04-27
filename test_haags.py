"""
Test module.
"""

import haags


def read_sample_file(fp):
    lines = (line.strip() for line in fp)
    lines = (line for line in lines if line and not line.startswith('#'))
    pairs = []
    while lines:
        a, b, *lines = lines
        pairs.append((a, b))
    return pairs


def test_haags():
    from pprint import pprint
    with open('samples.txt') as fp:
        pairs = read_sample_file(fp)
    for dutch, translation in pairs:
        tokens = list(haags.tokenize(dutch))
        print(dutch)
        pprint(tokens)
        print()
        assert ''.join(t.value for t in tokens) == dutch
