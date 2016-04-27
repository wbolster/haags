#!/usr/bin/env python

import collections
import itertools
import re

import attr


#
# Letter case
#

def apply_case_hack(s):
    # Hacky unicode 'ij' ligature
    return s.replace('ij', 'ĳ').replace('IJ', 'Ĳ')


def undo_case_hack(s):
    return s.replace('ĳ', 'ij').replace('Ĳ', 'IJ')


def detect_case(s):
    s = apply_case_hack(s)
    if not s:
        case = 'other'
    elif s == s.upper():
        case = 'upper'
    elif s == s.lower():
        case = 'lower'
    elif s[0].isupper() and s[1:] == s[1:].lower():
        case = 'sentence'
    elif s == s.title():
        case = 'title'
    else:
        case = 'other'
    return case


def recase(s, case):
    """Change letter case of a string."""
    s = apply_case_hack(s)
    if case == 'lower':
        s = s.lower()
    elif case == 'upper':
        s = s.upper()
    elif case == 'sentence':
        s = s[0].upper() + s[1:].lower()
    elif case == 'title':
        s = s.title()
    s = undo_case_hack(s)
    return s


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


def is_regular_word(s):
    if s in {"'t", "'n"}:
        return True
    return s.isalpha()


@attr.s(init=False)
class Token():
    TYPES = {'word', 'whitespace', 'punctuation', 'number', 'other', 'translated'}

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


WHITESPACE_TOKEN = Token(' ', 'whitespace')


def tokenize(s):
    regexes_with_token_types = [  # This is an ordered list.
        (WHITESPACE_RE, 'whitespace'),
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


#
# Contractions
#

CONTRACTIONS = {
    "aan het": "annut",
    "al een": "alle",
    "als een": "assun",
    "dacht ik": "dachik",
    "dacht het niet": "dachutnie",
    "dat ik": "dattik",
    "heb ik": "heppik",
    "ik dacht het niet": "ik dachutnie",
    "ik dacht het": "dachut",
    "ken ik": "kennik",
    "kijk dan": "kèktan",
    "mag het": "maggut",
    "mij het": "mènnut",
    "met een": "mettun",
    "op een": "oppun",
    "niet dan": "niettan",
    "van het": "vannut",
    "van hetzelfde": "vannutzelfde",
    "van jou": "vajjâh",
}
CONTRACTIONS_BY_LENGTH = collections.defaultdict(dict)
for dutch, haags in CONTRACTIONS.items():
    key = len(dutch.split())
    CONTRACTIONS_BY_LENGTH[key][dutch] = haags


def words_from_tokens(tokens, offset, n):
    """
    Obtain `n` words from `tokens` as a single string, starting at `offset`.
    """
    g = (t.value_lower for t in tokens[offset:] if t.type == 'word')
    return ' '.join(itertools.islice(g, n))


def make_token_type_string(tokens, pad_with_spaces=True):
    # Make a string with one character per token, which indicates the
    # token type. "Hallo, wereld!" becomes "w, w," (word, punctuation,
    # space, ...).
    mapping = {
        'word': 'w',
        'whitespace': ' ',
        'punctuation': ',',
        'number': '1',
        'other': '_',
        'translated': 't',
    }
    s = ''.join(mapping[t.type] for t in tokens)
    return s


def apply_contractions(tokens):
    # Contractions are found by looking for patterns in the list of
    # tokens, and comparing these against lookup tables. For example,
    # "word space word space word" is a candidate a 3 word contraction.
    # To make this easier, transform the list of token into a simple
    # string containing the token types, so that regular expressions can
    # be used for matching.

    tokens = tokens.copy()

    # Add whitespace tokens at the beginning and end for easier
    # matching. This means there is no special casing for matching at
    # the start of the end of the token stream.
    tokens = [WHITESPACE_TOKEN] + tokens + [WHITESPACE_TOKEN]

    # Search for long matches first, e.g. 4 words, then 3 words, and so on.
    items = sorted(CONTRACTIONS_BY_LENGTH.items(), reverse=True)

    for size, contractions in items:
        # Look for space separated words (e.g. "w w w)", followed by
        # either whitespace or punctuation+whitespace.
        types_str = make_token_type_string(tokens)
        base_pattern = ' '.join(['w'] * size)
        pattern = re.compile(r'{}(?= |, )'.format(base_pattern))
        pos = 0
        while True:
            m = pattern.search(types_str, pos)
            if m is None:
                break
            pos = m.start() + 1
            lookup = words_from_tokens(tokens, m.start(), size)
            replacement = CONTRACTIONS_BY_LENGTH[size].get(lookup)
            if not replacement:
                continue
            replacement = recase(replacement, tokens[m.start()].case)
            tokens[m.start():m.end()] = [Token(replacement, 'translated')]
            types_str = make_token_type_string(tokens)  # refresh

    # Remove whitespace wrapping.
    assert tokens[0] == WHITESPACE_TOKEN
    assert tokens[-1] == WHITESPACE_TOKEN
    tokens = tokens[1:-1]

    return tokens


#
# Translation
#

def translate(s):
    tokens = list(tokenize(s))
    tokens = apply_contractions(tokens)
    return ''.join(t.value for t in tokens)
