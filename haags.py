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
    """
    Container for a single syllable and its context.

    See:
    - https://nl.wikipedia.org/wiki/Lettergreep
    - https://en.wikipedia.org/wiki/Syllable
    """

    value = attr.ib()

    # Subdivision of the syllable, and derived properties.
    onset = attr.ib()
    rime = attr.ib()
    nucleus = attr.ib()
    coda = attr.ib()
    open = attr.ib()

    # Context: all letters before and after this syllable, and the
    # syllables preceding and following this one.
    head = attr.ib()
    tail = attr.ib()
    previous = attr.ib(default=None, repr=False)
    next = attr.ib(default=None, repr=False)

    def __init__(self, value, *, head, tail):
        self.value = value
        self.head = head
        self.tail = tail
        self.previous = None
        self.next = None

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

    #
    # vowels (klinkers)
    #

    # ei en ij worden è, behalve in -lijk/-lijkheid
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

    # lange o wordt au
    if syl.nucleus == 'oo' and syl.rime != 'oor':
        new.nucleus = 'au'
    elif syl.nucleus == 'o' and syl.open:
        new.nucleus = 'au'
    elif syl.nucleus in ('ooi', 'ooie'):  # pyphen oddity
        new.nucleus = 'au' + syl.nucleus[2:]

    # au/ou wordt âh
    if syl.nucleus in ('au', 'auw', 'ou', 'ouw'):
        # -ouw/-auw verliezen de -w,
        # e.g. saus, rauw, nou, jouw
        new.nucleus = 'âh'
        if syl.value == 'houd':
            # -houd verliest soms de -d
            if syl.previous and syl.previous.value in (
                    'be', 'der', 'huis', 'in', 'ont'):
                # e.g. behoud (behâhd), inhoud (inhâhd).
                pass
            else:
                # e.g. houd (hâh), aanhoud (anhâh)
                new.coda = ''
    elif syl.previous and syl.previous.rime == 'ou':
        # -oude- wordt meestal -âhwe-
        if syl.value == 'de':
            # e.g. oude (âhwe), oudere (âhwere)
            new.onset = 'w'
        elif syl.value == 'der':
            # e.g. pashouder (pashâhwâh)
            new.onset = 'w'
            new.nucleus = 'âh'
            new.coda = ''
        elif syl.value == 'den':
            new.onset = 'w'
            new.nucleus = 'e'
            new.coda = ''

    # - ui wordt ùi
    if syl.nucleus == 'ui':
        # e.g. rui (rùik)
        new.nucleus = 'ùi'

    # eu wordt ui, behalve als een r volgt
    if syl.nucleus == 'eu' and not syl.coda.startswith('r'):
        new.nucleus = 'ui'

    # - lange e wordt ei
    #   TODO: er zijn nog meer lange e, maar om dat vast te stellen heb
    #   je de volgende lettergreep nodig
    if syl.nucleus in ('ee', 'é', 'éé', 'ée') and syl.rime != 'eer':
        new.nucleus = 'ei'
    # TODO: ua wordt uwa (crosses syllables)

    # lange a blijft meestal een lange a
    if syl.value == 'aan':
        # e.g. aan (an)
        new.nucleus = 'a'

    #
    # consonants / medeklinkers
    #

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

    # Lettergrepen eindigend op een vloeiklank (l of r) gevolgd
    # door een medeklinker krijgen soms een extra lettergreep:
    # medeklinkerverdubbeling en een tussen-a, tussen-e, of-u.
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

    # Suffixes
    if syl.head and not syl.tail:

        # Uitgang -ens wordt meestal -es.
        if syl.rime == 'ens':
            if syl.onset in ('g', 'k', 't', 'v'):
                # e.g. volgens (volges), tekens (teikes), gewetens
                # (geweites), havens (haves)
                # TODO: uitzonderingen? intens
                new.coda = 's'
            elif syl.onset == 'd' and not syl.head.endswith(('ca', 'ten')):
                # e.g. heidens (hèdes), niet cadens, tendens
                new.coda = 's'
            elif syl.onset == 'r' and not syl.head.endswith('fo'):
                # e.g. varens (vares), niet cadens, forens
                # TODO: meer uitzonderingen
                new.coda = 's'
            # TODO: -lens  molens cameralens
            # TODO: -mens  examens aapmens
            # TODO: -pens  wapens
            # TODO: -sens kunssens
            # TODO: meer -ens
    # The new instance itself is useless since only a few attributes
    # make sense at this point, so simply return a string.
    return new.onset + new.nucleus + new.coda


def pairwise(iterable):  # from itertools recipes
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


hyphenation_dictionary = pyphen.Pyphen(lang='nl', left=1, right=1)


def translate_using_syllables(word):
    # The (naive) assumption here is that hyphenation is the same as
    # syllable splitting. First obtain the split points.
    positions = [0]
    positions.extend(hyphenation_dictionary.positions(word))
    positions.append(len(word))
    assert len(positions) == len(set(positions))  # all unique

    # Build syllable instances containing all data and context around them.
    syllables = [
        Syllable(word[start:stop], head=word[:start], tail=word[stop:])
        for start, stop in pairwise(positions)]
    for i in range(len(syllables)):
        if i > 0:
            syllables[i].previous = syllables[i-1]
        if i < len(syllables) - 1:
            syllables[i].next = syllables[i+1]

    # Process each syllable and format the result.
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
