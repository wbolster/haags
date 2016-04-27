#!/usr/bin/env python

import re

import attr


#
# Tokenisation
#

# Matches runs of whitespace.
WHITESPACE_RE = re.compile(r'(\s+)')

# Matches numbers, optionally with separator dots and commas. May not
# have a word character directly after it (e.g. does not match "123abc").
NUMBER_RE = re.compile(r'(\d+(?:[,.]\d+)*)(?!\w\s)')

# Matches "words", including the shorthands "'n", "'r" , and "'t".
# Matches may include digits and underscores.
WORD_RE = re.compile(r"([\w-]+|'[nrt])\b")

# Matches punctuation characters that may occur in normal text.
PUNCTUATION_CHARS = (
    ".?!"  # terminators
    ",:;-"  # separators
    "\"'“”‘’„‚"  # quotation marks
    "&/")  # misc
PUNCTUATION_RE = re.compile(r'([{}]+)'.format(re.escape(PUNCTUATION_CHARS)))


def detect_case(s):
    if s == s.upper():
        return 'upper'
    elif s == s.lower():
        return 'lower'
    elif s == s.title():
        return 'title'
    elif s.startswith('IJ') and s[2:] == s[2:].lower():
        # e.g. IJsland
        return 'title'
    return 'other'


def is_regular_word(s):
    if s in {"'t", "'n"}:
        return True
    return s.isalpha()


@attr.s(init=False)
class Token():
    TYPES = {'word', 'space', 'punctuation', 'number', 'other'}

    value = attr.ib()
    type = attr.ib()
    case = attr.ib(repr=False)
    value_lower = attr.ib(repr=False)

    def __init__(self, value, type):
        self.value = value
        self.value_lower = value.lower()
        assert type in self.TYPES
        self.type = type
        self.case = detect_case(value) if self.type == 'word' else None


def tokenize(s):
    regexes_with_token_types = [  # This is an ordered list.
        (WHITESPACE_RE, 'space'),
        (NUMBER_RE, 'number'),
        (WORD_RE, 'word'),
        (PUNCTUATION_RE, 'punctuation')]

    junk = ''  # Accumulates unknown input.
    pos = 0
    while pos < len(s):
        for regex, token_type in regexes_with_token_types:
            m = regex.match(s, pos)
            if m is None:
                continue
            if junk:  # Emit pending junk, if any.
                yield Token(junk, type='other')
                junk = ''
            value = m.group()
            assert value
            if token_type == 'word' and not is_regular_word(value):
                token_type = 'other'
            yield Token(value, type=token_type)
            pos = m.end()
            break
        else:
            junk += s[pos]
            pos += 1   # FIXME


def translate(s):
    tokens = list(tokenize(s))
    print(tokens)
