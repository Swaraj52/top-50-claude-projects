"""Plain-text utilities: tokenising, chunking, FTS query building, extractive summaries."""

from __future__ import annotations

import math
import re
from collections import Counter

STOPWORDS = frozenset(
    """a about above after again against all also am an and any are as at be because been before
    being below between both but by can could did do does doing down during each few for from
    further had has have having he her here hers herself him himself his how i if in into is it
    its itself just me more most my myself no nor not now of off on once only or other our ours
    ourselves out over own same she should so some such than that the their theirs them
    themselves then there these they this those through to too under until up very was we were
    what when where which while who whom why will with would you your yours yourself yourselves
    one two get got make made many much may might must shall us like even also however really
    within without via per s t don isn aren wasn weren hasn haven didn doesn won wouldn couldn
    shouldn what's it's i'm you're we're they're let's tell say said says ask asked know find
    saved save library""".split()
)

_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[\"'“‘(A-Z0-9])")
HIGHLIGHT_START = ""
HIGHLIGHT_END = ""


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def word_count(text: str) -> int:
    return len(_WORD.findall(text))


def reading_minutes(count: int) -> int:
    return max(1, round(count / 230)) if count else 0


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]


def sentences(text: str) -> list[str]:
    out = []
    for para in paragraphs(text):
        out.extend(s.strip() for s in _SENTENCE.split(para) if s.strip())
    return out


def chunk_text(text: str, size: int = 1200) -> list[str]:
    """Pack paragraphs into passages of about `size` characters (long paragraphs are split)."""
    pieces: list[str] = []
    for para in paragraphs(text):
        if len(para) <= size:
            pieces.append(para)
            continue
        buf = ""
        for sent in _SENTENCE.split(para):
            if buf and len(buf) + len(sent) + 1 > size:
                pieces.append(buf)
                buf = ""
            while len(sent) > size:  # a single enormous "sentence"
                pieces.append(sent[:size])
                sent = sent[size:]
            buf = f"{buf} {sent}".strip()
        if buf:
            pieces.append(buf)

    chunks, current = [], ""
    for piece in pieces:
        if current and len(current) + len(piece) + 2 > size:
            chunks.append(current)
            current = piece
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def query_terms(text: str, limit: int = 12) -> list[str]:
    seen: dict[str, None] = {}
    for w in words(text):
        w = w.replace("’", "'").split("'")[0]
        if len(w) >= 2 and w not in STOPWORDS:
            seen.setdefault(w, None)
    return list(seen)[:limit]


def fts_query(text: str, mode: str = "and") -> str | None:
    """Turn free text into a safe FTS5 query: each term quoted and prefix-matched."""
    terms = query_terms(text)
    if not terms:
        return None
    joiner = " AND " if mode == "and" else " OR "
    return joiner.join(f'"{t}"*' for t in terms)


def normalize_tag(name: str) -> str:
    """'Machine Learning ' -> 'machine-learning'; returns '' for unusable names."""
    name = re.sub(r"[\s_]+", "-", name.strip().lower().lstrip("#"))
    name = re.sub(r"[^\w-]", "", name, flags=re.UNICODE).strip("-")
    return name[:40]


def keywords(text: str, k: int = 5) -> list[str]:
    counts = Counter(w for w in words(text) if len(w) > 3 and w not in STOPWORDS and not w.isdigit())
    return [w for w, _ in counts.most_common(k)]


def extractive_summary(text: str, n_points: int = 4) -> tuple[str, list[str]]:
    """Pick the most representative sentences (term frequency, with a lead bias).

    Returns (tldr, key_points). A classic, transparent non-AI baseline.
    """
    sents = [s for s in sentences(text) if 30 <= len(s) <= 400]
    if not sents:
        return (text.strip()[:280], [])
    freq = Counter(w for w in words(text) if w not in STOPWORDS and len(w) > 2)
    if not freq:
        return (sents[0], sents[1 : n_points + 1])
    top = freq.most_common(1)[0][1]

    def score(i: int, s: str) -> float:
        toks = [w for w in words(s) if w in freq]
        if not toks:
            return 0.0
        base = sum(freq[w] / top for w in toks) / math.sqrt(len(words(s)))
        return base * (1.25 if i < 3 else 1.0)

    ranked = sorted(range(len(sents)), key=lambda i: score(i, sents[i]), reverse=True)
    tldr = sents[ranked[0]]
    picked = sorted(ranked[1 : n_points + 1])
    return (tldr, [sents[i] for i in picked])
