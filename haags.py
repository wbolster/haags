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
    "als er": "alstâh",
    "als u": "assu",
    "dacht het niet": "dachutnie",
    "dacht ik": "dachik",
    "dat ik": "dattik",
    "dat voor": "daffoâh",
    "doe je het": "doejenet",
    "en ik": "ennik",
    "had er": "hattâh",
    "heb ik": "heppik",
    "ik dacht het niet": "ik dachutnie",
    "ik dacht het": "dachut",
    "in een": "innun",
    "in je": "ijje",
    "in me": "imme",
    "kan er": "kandâh",
    "ken ik": "kennik",
    "ken je hem": "kejjenem",
    "ken je": "kejje",
    "ken jij": "kejjè",
    "ken u": "kennu",
    "kijk dan": "kèktan",
    "laat hem": "latem",
    "mag het": "maggut",
    "mag ik": "maggik",
    "met een": "mettun",
    "met je": "mejje",
    "met me": "memme",
    "mij het": "mènnut",
    "niet dan": "niettan",
    "omdat ik": "omdattik",
    "op een": "oppun",
    "val ik": "vallik",
    "van het": "vannut",
    "van hetzelfde": "vannutzelfde",
    "van je": "vajje",
    "van jou": "vajjâh",
    "van mijn": "vamme",
    "vind je": "vijje",
    "voordat ik": "voordattik",
    "wat ben je": "wabbejje",
    "zal ik eens": "sallekes",
    "zal ik": "zallik",
    "zeg het": "zeggut",
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
# Syllables
#

# Vowels can be written in various ways. See
# https://nl.wikipedia.org/wiki/Klinker_(klank)
GEDEKTE_KLINKERS = ['a', 'e', 'i', 'o', 'u']
VRIJE_KLINKERS = ['aa', 'ee', 'ie', 'oo', 'uu', 'eu', 'oe']
ZUIVERE_TWEEKLANKEN = ['ei', 'ij', 'ui', 'ou', 'au']
ONECHTE_TWEEKLANKEN = ['ai', 'oi', 'aai', 'ooi', 'oe', 'eeuw', 'ieuw']

# Alternate spellings, mostly in loan words and for
# disambiguating clashing vowels (klinkerbotsing).
GEDEKTE_KLINKERS += [
    'ah',  # e.g. ayatollah, bah,
    'è',  # e.g. scène, barrière
    'ë',  # e.g. België, patiënt, skiën
    'ï',  # e.g. beïnvloeden
]
ZUIVERE_TWEEKLANKEN += [
    'auw',  # e.g. rauw
    'ouw',  # e.g. rouw
]
VRIJE_KLINKERS += [
    'é',  # e.g. coupé
    'éé',  # e.g. één
    'ée',  # e.g. brûlée
    'ü',  # e.g. bühne, continuüm, reünie
]
# TODO: ä, e.g. hutenkäse, knäckebröd, salonfähig
# TODO: ö, e.g. coördinator, röntgen, zoölogie
# TODO: y, ey, e.g. baby, cowboy, hockey, systeem, but not mayonaise
# TODO: sjwa 'e', e.g. de, lade

VOWELS = sorted(
    ONECHTE_TWEEKLANKEN + ZUIVERE_TWEEKLANKEN +
    VRIJE_KLINKERS + GEDEKTE_KLINKERS,
    key=len, reverse=True)
CONSONANTS = 'bcçdfghjklmnpqrstvwxz'


@attr.s(init=False)
class Syllable():
    # See:
    # - https://nl.wikipedia.org/wiki/Lettergreep
    # - https://en.wikipedia.org/wiki/Syllable
    value = attr.ib()
    head = attr.ib()
    tail = attr.ib()
    onset = attr.ib()
    nucleus = attr.ib()
    coda = attr.ib()
    rime = attr.ib()
    open = attr.ib()

    def __init__(self, value, head='', tail=''):
        self.value = value
        self.head = head
        self.tail = tail

        # Split the syllable into its onset, nucleus, and coda. Each
        # syllable is supposed to contain a vowel which forms the
        # nucleus, optionally preceded by an onset, and optionally
        # followed by a coda.
        # https://en.wikipedia.org/wiki/Syllable#Components
        for vowel in VOWELS:
            if vowel not in value:
                continue
            self.onset, self.nucleus, self.coda = value.partition(vowel)
            break
        else:
            # This is not a normal syllable. TODO: do something more
            # sensible than this for cases that occur in normal text.
            self.onset, self.nucleus, self.coda = '', value, ''

        self.rime = self.nucleus + self.coda
        self.open = False if self.coda else True


SYLLABLES = {
    "flat": "flet",
    "wrap": "wrep",
}


def translate_syllable(syl):
    translated = SYLLABLES.get(syl.value)
    if translated is not None:
        return translated

    new = attr.assoc(syl)

    # Vowels / klinkers.
    # - ei en ij worden è, behalve in -lijk/-lijkheid
    if syl.nucleus in ('ei', 'ij'):
        if syl.value in ('lijk', 'lijks') or (
                syl.value == 'lij' and syl.tail.startswith('k')):
            if not syl.head:
                # e.g. lijk (lèk), lijkwit (lèkwit)
                new.nucleus = 'è'
            elif syl.head == 'ge':
                # e.g. gelijk (gelèk), gelijkheid (gelèkhèd)
                new.nucleus = 'è'
            elif syl.head.endswith((
                    'insge', 'isge', 'onge', 'rechts', 'tege', 'verge')):
                # e.g. ongelijk (ongelèk), tegelijk (tegelèk)
                new.nucleus = 'è'
            else:
                # e.g. bangelijk (bangelijk), eigenlijk (ègelijk),
                # mogelijk (maugelijk),
                pass
        else:
            # e.g. kijk (kèk), krijg (krèg)
            new.nucleus = 'è'
    # - lange o wordt au
    elif syl.nucleus == 'oo' and syl.rime is not 'oor':
        new.nucleus = 'au'
    elif syl.nucleus == 'o' and syl.open:
        new.nucleus = 'au'
    # - au en ou worden âh
    # - -ouw/-auw verliezen de -w
    # - -oud verliest de -d
    elif syl.rime == 'oud':
        # e.g. goud
        new.nucleus = 'âh'
        new.coda = ''
    elif syl.nucleus in ('au', 'auw', 'ou', 'ouw'):
        # e.g. saus, rauw, nou, jouw
        new.nucleus = 'âh'
    # - ui wordt ùi
    elif syl.nucleus == 'ui':
        # e.g. rui (rùik)
        new.nucleus = 'ùi'
    # eu wordt ui, behalve als een r volgt
    elif syl.nucleus == 'eu' and not syl.coda.startswith('r'):
        new.nucleus = 'ui'
    # - lange e wordt ei
    #   TODO: er zijn nog meer lange e, maar om dat vast te stellen heb
    #   je de volgende lettergreep nodig
    elif syl.nucleus in ('ee', 'é', 'éé', 'ée') and syl.rime != 'eer':
        new.nucleus = 'ei'
    # TODO: ua wordt uwa (crosses syllables)

    # Consonants / medeklinkers.
    # - TODO de r na een korte klank wordt een g
    # - de r na een lange a wordt een h
    # - na overige klanken wordt de r een âh
    # - uitgang -eer wordt -eâh
    # TODO: coda.startswith('r'), e.g. barst (bagst)
    if syl.rime == 'aar':
        # e.g. naar (naah)
        new.coda = 'h'
    elif syl.rime == 'ar':
        # e.g. bar (bâh)
        new.nucleus = 'âh'
        new.coda = ''
    elif syl.nucleus == 'oo' and syl.coda.startswith('r'):
        # e.g. door (doâh)
        new.nucleus = 'o'
        new.coda = 'âh' + syl.coda[1:]
    elif syl.rime == 'eer':
        new.nucleus = 'e'
        new.coda = 'âh'
    elif syl.rime == 'ier':
        new.nucleus = 'ie'
        new.coda = 'âh'
    elif syl.rime == 'er':
        pass  # TODO
    elif new.coda == 'r':
        new.coda = 'âh'

    # FIXME: alleen aan einde woord?
    # -ft wordt -f
    # -kt wordt -k
    if syl.coda == 'ft':
        new.coda = 'f'
    elif syl.coda in ('kt', 'ct'):
        # e.g. bakt (bak), respect (respek)
        new.coda = 'k'

    # Woorden eindigend op -l + medeklinker of -r + medeklinker krijgen
    # soms een extra lettergreep: medeklinkerverdubbeling en een
    # tussen-a, tussen-e, of-u.
    elif syl.rime == 'urg':
        # e.g. voorburg (voâhburrag)
        new.coda = 'rrag' + syl.coda[3:]
    elif syl.coda.startswith(('l', 'r')) and len(syl.coda) > 1:
        if syl.coda.startswith((
                'lf', 'lg', 'lk', 'lm', 'lp',
                'rf', 'rg', 'rm', 'rn', 'rp')):
            # e.g. volk (volluk), zorg (zorrug)
            new.coda = syl.coda[0] + syl.coda[0] + 'u' + syl.coda[1:]
        elif syl.coda.startswith('rk'):
            # e.g. sterkte (sterrekte)
            new.coda = syl.coda[0] + syl.coda[0] + 'e' + syl.coda[1:]

    # The new instance itself is useless since only a few attributes
    # make sense at this point, so simply return a string.
    return new.onset + new.nucleus + new.coda


def pairwise(iterable):  # from itertools recipes
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


hyphenation_dictionary = pyphen.Pyphen(lang='nl', left=1, right=1)


def translate_using_syllables(word):
    # Naive assumption: hyphenation is the same as syllable splitting.
    positions = [0]
    positions.extend(hyphenation_dictionary.positions(word))
    positions.append(None)
    assert len(positions) == len(set(positions))  # all unique
    syllables = [
        Syllable(word[start:stop], head=word[:start], tail=word[stop:])
        for start, stop in pairwise(positions)]
    return ''.join(translate_syllable(syl) for syl in syllables)


#
# Single word translation
#

WORDS = {
    "aan": "an",
    "een": "'n",
    "even": "effe",
    "heeft": "heb",
    "het": "'t",
}


def translate_single_word_token(token):
    translated = WORDS.get(token.value_lower)
    if translated is None:
        translated = translate_using_syllables(token.value_lower)
    return Token(recase(translated, token.case), 'word')


def apply_single_words(tokens):
    return [
        translate_single_word_token(token) if token.type == 'word' else token
        for token in tokens]


#
# Main API
#

def translate(s):
    tokens = list(tokenize(s))
    tokens = apply_contractions(tokens)
    tokens = apply_single_words(tokens)
    return ''.join(t.value for t in tokens)
