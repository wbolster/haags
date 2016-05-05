#!/usr/bin/env python

import collections
import itertools
import re

import attr
import pyphen


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
    TYPES = {
        'word',
        'whitespace',
        'punctuation',
        'number',
        'other',
        'translated',
    }

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

ALL_CONTRACTIONS = {
    "aan het": "annut",
    "al een": "alle",
    "als een": "assun",
    "dacht het niet": "dachutnie",
    "dacht ik": "dachik",
    "dat ik": "dattik",
    "heb ik": "heppik",
    "ik dacht het niet": "ik dachutnie",
    "ik dacht het": "dachut",
    "in je": "ijje",
    "ken ik": "kennik",
    "kijk dan": "kèktan",
    "mag het": "maggut",
    "met een": "mettun",
    "mij het": "mènnut",
    "niet dan": "niettan",
    "op een": "oppun",
    "van het": "vannut",
    "van hetzelfde": "vannutzelfde",
    "van jou": "vajjâh",
    "van mijn": "vamme",
    "zal ik eens": "sallekes",
}
ALL_CONTRACTIONS_BY_SIZE = collections.defaultdict(dict)
for dutch, haags in ALL_CONTRACTIONS.items():
    key = len(dutch.split())
    ALL_CONTRACTIONS_BY_SIZE[key][dutch] = haags


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
    items = sorted(ALL_CONTRACTIONS_BY_SIZE.items(), reverse=True)

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
            replacement = contractions.get(lookup)
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
# Single word translation
#

hyphenation_dictionary = pyphen.Pyphen(lang='nl', left=1, right=1)


def apply_single_words(tokens):
    return [
        translate_single_word_token(token) if token.type == 'word' else token
        for token in tokens]


def pairwise(iterable):  # from itertools recipes
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)

VOWELS = 'aeoui'


def starts_with_vowel(s):
    return s[0] in VOWELS


def ends_with_vowel(s):
    return s[-1] in VOWELS or s.endswith('ey')


SYLLABLES = {
    "flat": "flet",
}


def translate_syllable(s):
    translated = SYLLABLES.get(s)
    if translated is not None:
        return translated

    # Vowels / klinkers.
    # - ei en ij worden è
    if 'ei' in s and 'oei' not in s:
        s = s.replace('ei', 'è')
    elif 'ij' in s:
        # FIXME: niet voor -lijk en -lijkheid enz
        s = s.replace('ij', 'è')
    # - lange o wordt au
    # - TODO er zijn er meer lang
    elif 'oo' in s and not s.endswith('oor'):
        s = s.replace('oo', 'au')
    elif s.endswith('o'):
        s = s.replace('o', 'au')
    # - au en ou worden âh
    # - -ouw/-auw verliezen de -w
    elif 'au' in s:
        s = s.replace('auw', 'âh')
        s = s.replace('au', 'âh')
    elif 'ou' in s:
        s = s.replace('oud', 'âh')
        s = s.replace('ouw', 'âh')
        s = s.replace('ou', 'âh')
    # ui wordt ùi
    elif 'ui' in s:
        s = s.replace('ui', 'ùi')
    # eu wordt ui, behalve als een r volgt
    elif 'eu' in s and 'eur' not in s:
        s = s.replace('eu', 'ui')
    # - lange e wordt ei
    #   TODO: er zijn nog meer lange e, maar om dat vast te stellen heb
    #   je de volgende lettergreep nodig
    elif 'ee' in s and not s.endswith('eer'):
        s = s.replace('ee', 'ei')
    elif 'é' in s:
        s = s.replace('é', 'ei')
    # TODO: ua wordt uwa (crosses syllables)

    # Consonants / medeklinkers.
    # - TODO de r na een korte klank wordt een g
    # - de r na een lange a wordt een h
    # - na overige klanken wordt de r een âh
    # - uitgang -eer wordt -eâh
    if s.endswith('aar'):
        s = s.replace('aar', 'aah')
    elif s.endswith('ar'):
        s = s.replace('ar', 'âh')
    elif s.endswith('oor'):
        s = s.replace('oor', 'oâh')
    elif s.endswith('eer'):
        s = s.replace('eer', 'eâh')
    elif s.endswith('ier'):
        s = s.replace('ier', 'ieâh')
    elif s.endswith('er'):
        pass
    elif s.endswith('r'):
        s = s[:-1] + 'âh'

    # FIXME: alleen aan einde woord?
    # -ft wordt -f
    # -kt wordt -k
    if s.endswith('ft'):
        s = s[:-1]
    elif s.endswith('kt'):
        s = s[:-1]

    return s


WORDS = {
    "aan": "an",
    "een": "'n",
    "even": "effe",
    "het": "'t",
}


def translate_single_word_token(token):
    translated = WORDS.get(token.value_lower)
    if translated is None:
        # Naive assumption: hyphenation is the same as syllable splitting.
        positions = [0]
        positions.extend(hyphenation_dictionary.positions(token.value_lower))
        positions.append(None)
        assert len(positions) == len(set(positions))  # all unique
        syllables = [
            token.value_lower[start:stop]
            for start, stop in pairwise(positions)]
        translated = ''.join(translate_syllable(s) for s in syllables)
    return Token(recase(translated, token.case), 'word')


#
# Main API
#

def translate(s):
    tokens = list(tokenize(s))
    tokens = apply_contractions(tokens)
    tokens = apply_single_words(tokens)
    return ''.join(t.value for t in tokens)
