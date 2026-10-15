"""Trigram helpers for sqlmind's pure-SQL similarity.

Similarity is trigram Jaccard, computed set-wise inside SQLite. The Python
side only extracts trigram *sets* at insert time; every score, ranking, and
merge decision is a SQL statement (see consolidate.py).
"""

import re

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _WS.sub(" ", text.lower().strip())


def trigrams(text: str):
    """Character trigrams of the normalized text, as a set."""
    t = normalize(text)
    if len(t) < 3:
        return {t} if t else set()
    return {t[i : i + 3] for i in range(len(t) - 2)}
