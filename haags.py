#!/usr/bin/env python

import collections
import itertools
import re
import typing
from typing import Dict, Iterable, Iterator, List, Sequence, Tuple, TypeVar

import attr
import pyphen

T = TypeVar("T")


#
# Letter case
#


def apply_case_hack(s: str) -> str:
    # Hacky unicode 'ij' ligature
    return s.replace("ij", "ĳ").replace("IJ", "Ĳ")


def undo_case_hack(s: str) -> str:
    return s.replace("ĳ", "ij").replace("Ĳ", "IJ")


def detect_case(s: str) -> str:
    s = apply_case_hack(s)
    if not s:
        case = "other"
    elif s == s.upper():
        case = "upper"
    elif s == s.lower():
        case = "lower"
    elif s[0].isupper() and s[1:] == s[1:].lower():
        case = "sentence"
    elif s == s.title():
        case = "title"
    else:
        case = "other"
    return case


def recase(s: str, case: str) -> str:
    """Change letter case of a string."""
    s = apply_case_hack(s)
    if case == "lower":
        s = s.lower()
    elif case == "upper":
        s = s.upper()
    elif case == "sentence":
        s = s[0].upper() + s[1:].lower()
    elif case == "title":
        s = s.title()
    s = undo_case_hack(s)
    return s


#
# Tokenisation
#

# Matches runs of whitespace.
WHITESPACE_RE = re.compile(r"(\s+)")

# Matches numbers, optionally with separator dots and commas. May not
# have a word character directly after it (e.g. does not match "123abc").
NUMBER_RE = re.compile(r"(\d+(?:[,.]\d+)*)(?!\w\s)")

# Matches "words", including the shorthands "'n", "'r" , and "'t".
# Matches may include digits and underscores.
WORD_RE = re.compile(r"([\w-]+|'[nrt])\b")

# Matches punctuation characters that may occur in normal text.
PUNCTUATION_CHARS = "".join(
    [
        ".?!",  # terminators
        ",:;-",  # separators
        "\"'“”‘’„‚",  # quotation marks
        "&/",  # misc
    ]
)
PUNCTUATION_RE = re.compile(r"([{}]+)".format(re.escape(PUNCTUATION_CHARS)))


def is_regular_word(s: str) -> bool:
    if s in {"'t", "'n"}:
        return True
    return s.isalpha()


@attr.s(init=False, slots=True)
class Token:
    TYPES = {
        "word",
        "whitespace",
        "punctuation",
        "number",
        "other",
        "translated",
    }

    value = attr.ib()
    type = attr.ib()
    case = attr.ib(repr=False)
    value_lower = attr.ib(repr=False)

    def __init__(self, value: str, type: str) -> None:
        self.value = value
        self.value_lower = value.lower()
        assert type in self.TYPES
        self.type = type
        self.case = detect_case(value) if self.type == "word" else None


WHITESPACE_TOKEN = Token(" ", "whitespace")


def tokenize(s: str) -> Iterator[Token]:
    regexes_with_token_types = [  # This is an ordered list.
        (WHITESPACE_RE, "whitespace"),
        (NUMBER_RE, "number"),
        (WORD_RE, "word"),
        (PUNCTUATION_RE, "punctuation"),
    ]

    junk = ""  # Accumulates unknown input.
    pos = 0
    while pos < len(s):
        for regex, token_type in regexes_with_token_types:
            m = regex.match(s, pos)
            if m is None:
                continue
            if junk:  # Emit pending junk, if any.
                yield Token(junk, type="other")
                junk = ""
            value = m.group()
            assert value
            if token_type == "word" and not is_regular_word(value):
                token_type = "other"
            yield Token(value, type=token_type)
            pos = m.end()
            break
        else:
            junk += s[pos]
            pos += 1  # FIXME


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
    "het wordt": "twogt",
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
    "of er": "oftâh",
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
ALL_CONTRACTIONS_BY_SIZE: typing.DefaultDict[
    int, Dict[str, str]
] = collections.defaultdict(dict)
for dutch, haags in ALL_CONTRACTIONS.items():
    key = len(dutch.split())
    ALL_CONTRACTIONS_BY_SIZE[key][dutch] = haags


def words_from_tokens(tokens: Sequence[Token], offset: int, n: int) -> str:
    """
    Obtain `n` words from `tokens` as a single string, starting at `offset`.
    """
    g = (t.value_lower for t in tokens[offset:] if t.type == "word")
    return " ".join(itertools.islice(g, n))


def make_token_type_string(
    tokens: Sequence[Token], pad_with_spaces: bool = True
) -> str:
    # Make a string with one character per token, which indicates the
    # token type. "Hallo, wereld!" becomes "w, w," (word, punctuation,
    # space, ...).
    mapping = {
        "word": "w",
        "whitespace": " ",
        "punctuation": ",",
        "number": "1",
        "other": "_",
        "translated": "t",
    }
    s = "".join(mapping[t.type] for t in tokens)
    return s


def apply_contractions(tokens: Sequence[Token]) -> List[Token]:
    # Contractions are found by looking for patterns in the list of
    # tokens, and comparing these against lookup tables. For example,
    # "word space word space word" is a candidate a 3 word contraction.
    # To make this easier, transform the list of token into a simple
    # string containing the token types, so that regular expressions can
    # be used for matching.

    tokens = list(tokens)

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
        base_pattern = " ".join(["w"] * size)
        pattern = re.compile(r"{}(?= |, )".format(base_pattern))
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
            tokens[m.start() : m.end()] = [Token(replacement, "translated")]
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
GEDEKTE_KLINKERS = ["a", "e", "i", "o", "u"]
VRIJE_KLINKERS = ["aa", "ee", "ie", "oo", "uu", "eu", "oe"]
ZUIVERE_TWEEKLANKEN = ["ei", "ij", "ui", "ou", "au"]
ONECHTE_TWEEKLANKEN = ["ai", "oi", "aai", "ooi", "oe", "eeuw", "ieuw"]

# Alternate spellings, mostly in loan words and for
# disambiguating clashing vowels (klinkerbotsing).
GEDEKTE_KLINKERS += [
    "ah",  # e.g. ayatollah, bah
    "è",  # e.g. scène, barrière
    "ë",  # e.g. België, patiënt, skiën
    "ï",  # e.g. beïnvloeden
]
ZUIVERE_TWEEKLANKEN += [
    "auw",  # e.g. rauw
    "ouw",  # e.g. rouw
]
VRIJE_KLINKERS += [
    "é",  # e.g. coupé
    "éé",  # e.g. één
    "ée",  # e.g. brûlée
    "ü",  # e.g. bühne, continuüm, reünie
]
# TODO: ä, e.g. hutenkäse, knäckebröd, salonfähig
# TODO: ö, e.g. coördinator, röntgen, zoölogie
# TODO: y, ey, e.g. baby, cowboy, hockey, systeem, but not mayonaise
# TODO: sjwa 'e', e.g. de, lade

VOWELS = sorted(
    ONECHTE_TWEEKLANKEN + ZUIVERE_TWEEKLANKEN + VRIJE_KLINKERS + GEDEKTE_KLINKERS,
    key=len,
    reverse=True,
)
CONSONANTS = "bcçdfghjklmnpqrstvwxz"


@attr.s(init=False, slots=True)
class Syllable:
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
    previous = attr.ib(default=None, repr=False, hash=False)
    next = attr.ib(default=None, repr=False, hash=False)

    def __init__(self, value: str, *, head: str, tail: str) -> None:
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
            self.onset, self.nucleus, self.coda = "", value, ""

        self.rime = self.nucleus + self.coda
        self.open = False if self.coda else True


SYLLABLES = {
    "aan": "an",
    "flat": "flet",
    "wrap": "wrep",
}


def translate_syllable(syl: Syllable) -> Tuple[str, int]:
    translated = SYLLABLES.get(syl.value)
    if translated is not None:
        return translated, 1

    # defaults serving as the starting point
    onset = syl.onset
    nucleus = syl.nucleus
    coda = syl.coda

    #
    # special cases
    #

    # jus
    if syl.value == "jus":
        if syl.tail.startswith("t"):
            # e.g. justitie (justisie)
            return "jus", 1
        else:
            # e.g. juskom (zjukom)
            return "zju", 1

    #
    # vowels (klinkers)
    #

    # ei en ij worden è, behalve in -lijk/-lijkheid
    if syl.nucleus in ("ei", "ij"):
        if syl.value in ("lijk", "lijks") or (
            syl.value == "lij" and syl.tail.startswith("k")
        ):
            if not syl.head:
                # e.g. lijk (lèk), lijkwit (lèkwit)
                nucleus = "è"
            elif syl.head == "ge":
                # e.g. gelijk (gelèk), gelijkheid (gelèkhèd)
                nucleus = "è"
            elif syl.head.endswith(
                ("insge", "isge", "onge", "rechts", "tege", "verge")
            ):
                # e.g. ongelijk (ongelèk), tegelijk (tegelèk)
                nucleus = "è"
            else:
                # e.g. bangelijk (bangelijk), eigenlijk (ègelijk),
                # mogelijk (maugelijk),
                # TODO: aanzienlijk (anzienlek) ?
                pass
        else:
            # e.g. kijk (kèk), krijg (krèg)
            nucleus = "è"

    # lange o wordt au, maar niet voor een -r.
    if syl.nucleus == "oo" and not syl.coda.startswith("r"):
        nucleus = "au"
    elif syl.nucleus == "o" and syl.open:
        nucleus = "au"
    elif syl.nucleus in ("ooi", "ooie"):  # pyphen oddity
        nucleus = "au" + syl.nucleus[2:]

    # au/ou wordt âh
    if syl.nucleus in ("au", "auw", "ou", "ouw"):
        # -ouw/-auw verliezen de -w,
        # e.g. saus, rauw, nou, jouw
        nucleus = "âh"
        if syl.value == "houd":
            # -houd verliest soms de -d
            if syl.previous and syl.previous.value in (
                "be",
                "der",
                "huis",
                "in",
                "ont",
            ):
                # e.g. behoud (behâhd), inhoud (inhâhd).
                pass
            else:
                # e.g. houd (hâh), aanhoud (anhâh)
                coda = ""
    elif syl.previous and syl.previous.rime == "ou":
        # -oude- wordt meestal -âhwe-
        if syl.value == "de":
            # e.g. oude (âhwe), oudere (âhwere)
            onset = "w"
        elif syl.value == "der":
            # e.g. pashouder (pashâhwâh)
            onset = "w"
            nucleus = "âh"
            coda = ""
        elif syl.value == "den":
            onset = "w"
            nucleus = "e"
            coda = ""

    # - ui wordt ùi
    if syl.nucleus == "ui":
        # e.g. rui (rùik)
        nucleus = "ùi"

    # eu wordt ui, behalve als een r volgt
    if syl.nucleus == "eu" and not syl.coda.startswith("r"):
        nucleus = "ui"

    # - lange e wordt ei
    #   TODO: er zijn nog meer lange e, maar om dat vast te stellen heb
    #   je de volgende lettergreep nodig
    if syl.nucleus in ("ee", "é", "éé", "ée") and syl.rime != "eer":
        nucleus = "ei"

    # -ua- wordt -uwa-
    if syl.value == "a" and syl.previous and syl.previous.rime == "u":
        # e.g. situatie (situwasie)
        onset = "w"

    #
    # consonants / medeklinkers
    #

    # -isch wordt -ies, -ische wordt -iese
    if syl.rime == "isch":
        # e.g. basisch (basies)
        return syl.onset + "ies", 1
    elif syl.rime == "i" and syl.next and syl.next.value in {"sche", "schen"}:
        # e.g. basische (basiese), harmonische (harmauniese)
        return syl.onset + "iese", 2

    # -cie wordt -sie, -cieel wordt -sjeil
    if syl.value.startswith("cie"):
        return "s" + syl.value[1:], 1
    elif syl.value == "ci" and syl.next:
        if syl.next.value == "ë":
            # e.g. officiële (offesjeile)
            return "sjei", 2
        elif not syl.next.onset:
            # e.g. officieel (offesjeil)
            onset = "sj"
            nucleus = ""

    # offi- wordt offe-
    if syl.value == "of" and syl.next and syl.next.value == "fi":
        # e.g. officieel (offesjeil)
        return "offe", 2

    # uitgang -t na een andere medeklinker vervalt in de meeste gevallen
    if len(syl.coda) >= 2 and syl.coda.endswith("t"):
        # -kt/-ct wordt -k
        if syl.coda == "ct":
            # e.g. respect (respek)
            coda = "k"
        elif syl.coda.startswith("r"):
            # e.g. kort (kogt), wordt (wogt), harst (hags)
            pass  # handled elsewhere
        elif syl.coda in {"lt", "nt"}:
            # e.g. valt (valt), vent (vent)
            pass
        elif syl.rime == "angt":
            # e.g. hangt (hank)
            coda = "nk"
        else:
            # e.g. bakt (bak), nacht (nach), zwart (zwagt)
            coda = syl.coda[:-1]

    # qua- wordt kwa-, -quent- wordt -kwent-
    if syl.onset == "qu":
        # e.g. adequaat (adekwaat)
        onset = "kw"

    # va- wordt soms ve-
    if syl.value == "va" and syl.tail.startswith(("kant", "cant")):
        # e.g. vakantie (vekansie), vacant (vecant)
        return "ve", 1

    # c wordt vaak een k
    if syl.onset == "c" and not syl.nucleus.startswith(("i", "e")):
        onset = "k"
    if syl.coda == "c":
        coda = "k"

    # -ti- en -tie worden -si- en -sie na een open lettergreep.
    if syl.previous and not syl.previous.coda:
        if syl.value == "ti":
            # e.g. justitioneel (justisiauneil)
            onset = "s"
            nucleus = "i"
        elif syl.value == "tie":
            # e.g. politie (poliesie)
            onset = "s"
            nucleus = "ie"

    # - TODO de r na een korte klank wordt een g
    # - de r na een lange a wordt een h
    # - na overige klanken wordt de r een âh
    # - uitgang -eer wordt -eâh
    # TODO: coda.startswith('r'), e.g. barst (bagst)
    # TODO: drop -t?
    if syl.coda.startswith("r"):
        r_codas = ("r", "rs", "rst", "rt", "rts")
        # todo: -rd? gehoord?
        vowel_map = {
            "e": "âh",
            "ee": "eâh",
            "eu": "euâh",
            "ie": "ieâh",
            "oo": "oâh",
            "uu": "uâh",
        }
        if syl.rime == "ar":
            # e.g. bar (bâh)
            nucleus = "âh"
            coda = ""
        elif syl.rime == "aar":
            # e.g. naar (naah)
            coda = "h"
        elif syl.nucleus in vowel_map and syl.coda in r_codas:
            # e.g. lekker (lekkâh), weigert (wègâht), lekkerst (lekkâhst),
            # duurt (duâht), voorts (voâhts)
            nucleus = vowel_map[syl.nucleus]
            coda = syl.coda.lstrip("r")

    # Lettergrepen eindigend op een vloeiklank (l of r) gevolgd
    # door een medeklinker krijgen soms een extra lettergreep:
    # medeklinkerverdubbeling en een tussen-a, tussen-e, of-u.
    if syl.rime == "urg":
        # e.g. voorburg (voâhburrag)
        coda = "rrag" + syl.coda[3:]
    elif syl.coda.startswith(("l", "r")) and len(syl.coda) > 1:
        # FIXME: do not clash with r- coda handling above
        if syl.coda.startswith(
            ("lf", "lg", "lk", "lm", "lp", "rf", "rg", "rm", "rn", "rp")
        ):
            # e.g. volk (volluk), zorg (zorrug)
            coda = syl.coda[0] + syl.coda[0] + "u" + syl.coda[1:]
        elif syl.coda.startswith("rk"):
            # e.g. sterkte (sterrekte)
            coda = syl.coda[0] + syl.coda[0] + "e" + syl.coda[1:]

    # -md wordt -mp
    if syl.coda == "md":
        # e.g. geruimd (gerùimp)
        coda = "mp"

    # Suffixes (uitgangen)
    if syl.head:

        # -ens wordt meestal -es.
        if syl.rime == "ens":
            if syl.onset in ("g", "k", "t", "v"):
                # e.g. volgens (volges), tekens (teikes), gewetens
                # (geweites), havens (haves)
                # TODO: uitzonderingen? intens
                coda = "s"
            elif syl.onset == "d" and not syl.head.endswith(("ca", "ten")):
                # e.g. heidens (hèdes), niet cadens, tendens
                coda = "s"
            elif syl.onset == "r" and not syl.head.endswith("fo"):
                # e.g. varens (vares)
                # TODO: meer uitzonderingen
                coda = "s"
            # TODO: -lens  molens cameralens
            # TODO: -mens  examens aapmens
            # TODO: -pens  wapens
            # TODO: -sens kussens
            # TODO: meer -ens

        # -en wordt -e of -ûh (aan einde zin).
        # TODO
        elif syl.rime == "en":
            coda = ""

    return onset + nucleus + coda, 1


def pairwise(iterable: Iterable[T]) -> Iterator[Tuple[T, T]]:  # from itertools recipes
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


hyphenation_dictionary = pyphen.Pyphen(lang="nl", left=1, right=1)


def split_into_syllables(word: str) -> List[Syllable]:
    # The (naive) assumption here is that hyphenation is the same as
    # syllable splitting. First obtain the split points.
    positions = [0]
    positions.extend(hyphenation_dictionary.positions(word))
    positions.append(len(word))
    assert len(positions) == len(set(positions))  # all unique

    # Build syllable instances containing all data and context around them.
    syllables = [
        Syllable(word[start:stop], head=word[:start], tail=word[stop:])
        for start, stop in pairwise(positions)
    ]
    for i in range(len(syllables)):
        if i > 0:
            syllables[i].previous = syllables[i - 1]
        if i < len(syllables) - 1:
            syllables[i].next = syllables[i + 1]

    return syllables


def translate_using_syllables(word: str) -> str:
    syllables = split_into_syllables(word)
    out = []
    while syllables:
        translated, n = translate_syllable(syllables[0])
        out.append(translated)
        syllables = syllables[n:]
    return "".join(out)


#
# Single word translation
#

WORDS = {
    "aan": "an",
    "als": "as",
    "baby": "beibie",
    "een": "'n",
    "er": "'r",
    "even": "effe",
    "heeft": "heb",
    "het": "'t",
}


def translate_single_word_token(token: Token) -> Token:
    translated = WORDS.get(token.value_lower)
    if translated is None:
        translated = translate_using_syllables(token.value_lower)
    return Token(recase(translated, token.case), "word")


def apply_single_words(tokens: Sequence[Token]) -> List[Token]:
    return [
        translate_single_word_token(token) if token.type == "word" else token
        for token in tokens
    ]


#
# Main API
#


def translate(s: str) -> str:
    tokens = list(tokenize(s))
    tokens = apply_contractions(tokens)
    tokens = apply_single_words(tokens)
    return "".join(t.value for t in tokens)
