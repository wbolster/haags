#!/usr/bin/env python

import collections
import itertools
import re

#
# Tokenisation
#

RE_SPLIT_WORDS = re.compile(r'(\W+)', re.MULTILINE)

Token = collections.namedtuple('Token', ['value', 'tail', 'is_translated'])


def tokenize(s, *, is_translated):
    chunks = RE_SPLIT_WORDS.split(s)
    print(chunks)
    it = iter(chunks)
    for value, tail in zip(it, it):
        yield Token(value=value, tail=tail, is_translated=is_translated)


def ngrams(iterable, size):
    iterators = itertools.tee(iterable, size)
    for i in range(size):
        for _ in range(i):
            next(iterators[i])
    yield from zip(*iterators)


#
# Translation
#

SIMPLE_REPLACEMENTS = {
    "het haags": "'t haags",
    "is het": "isset",
    "euro": "pleuro",
}


SIMPLE_REPLACEMENTS_BY_NUMBER_OF_WORDS = collections.defaultdict(dict)
for k, v in SIMPLE_REPLACEMENTS.items():
    SIMPLE_REPLACEMENTS_BY_NUMBER_OF_WORDS[len(k.split())][k] = v


def join_tokens(tokens):
    chunks = []
    for token in tokens:
        chunks.append(token.value)
        chunks.append(token.tail)
    return ''.join(chunks)


def translate(s):
    tokens = list(tokenize(s, is_translated=False))

    # Pass 1: simple replacements
    for size in sorted(SIMPLE_REPLACEMENTS_BY_NUMBER_OF_WORDS, reverse=True):
        pending = list(tokens)
        new = []
        while len(pending) >= size:
            run = pending[:size]
            if any(t.is_translated for t in run):
                new.append(pending.pop(0))
                continue
            key = ' '.join(t.value for t in run).lower()
            try:
                replacement = SIMPLE_REPLACEMENTS[key]
            except KeyError:
                new.append(pending.pop(0))
            else:
                new.append(replacement)
                # new.extend(tokenize(replacement, is_translated=True))
                pending = pending[size:]
        tokens = new

    return join_tokens(tokens)


#
# Main program
#

def main():
    sample = 'kijk nou'
    translated = translate(sample)
    print(translated)


if __name__ == '__main__':
    main()
