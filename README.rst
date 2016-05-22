=====
Haags
=====

A Python library to programmatically "translate" Dutch text into the
"Haags" dialect, as spoken in the city of The Hague, the Netherlands.
It aims to transform well-written Dutch text into the dialectal
spelling, as popularized by the Haagse Harry comics written by Marnix
Rueb.

**DO NOT USE**: This code is pre-alpha quality, and should not be used
by anyone but the author.

TODO
====

incomplete list of things to think about at some point (and not
mentioned in fixme/todo comments in the code itself)

* normaliseren van z'n -> zijn alvorens te vertalen
* 'r 's 'n 't zijn woorden
* speciaal token type voor quote chars?
* contractions: require whitespace/punctuation before occurence in
  addition to after occurence
* recognize 's suffix as part of word, e.g. auto's
* lots of other things


References
==========

* https://nl.wikipedia.org/wiki/Haags
* https://en.wikipedia.org/wiki/The_Hague_dialect
* http://www.mijnwoordenboek.nl/dialect/Haags
