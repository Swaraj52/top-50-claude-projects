"""Topic clusters built from the words you chose, with no model and no hidden state.

Candidates come from titles and tags, not from the whole body: a cluster is a subject you
named, not a word that happened to repeat. Clusters are recomputed from the current library
each time they are shown, so editing an item moves it between clusters on the next request.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from ..models import Item
from .search import label, split_tags, stem, tokenize

# Words that name no subject. They are excluded from cluster candidates because a
# cluster called "First" or "Keep" tells the reader nothing.
GENERIC = {
    "add", "also", "another", "any", "back", "become", "best", "better", "call", "can",
    "change", "could", "day", "days", "did", "different", "does", "done", "each", "even",
    "every", "first", "get", "give", "go", "good", "great", "had", "has", "have", "here",
    "how", "into", "just", "keep", "know", "last", "less", "like", "little", "long", "look",
    "made", "make", "many", "may", "more", "most", "move", "much", "must", "need", "new",
    "next", "not", "now", "note", "notes", "one", "only", "other", "out", "over", "own", "part", "put",
    "read", "really", "return", "run", "same", "say", "see", "set", "should", "show",
    "small", "some", "still", "take", "tell", "than", "that", "then", "there", "these",
    "thing", "things", "think", "this", "time", "times", "today", "too", "try", "turn",
    "two", "use", "used", "very", "want", "way", "week", "weeks", "well", "what", "when",
    "where", "which", "while", "who", "why", "will", "with", "work", "would", "year",
    "years", "your",
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:60] or "cluster"


@dataclass
class Cluster:
    slug: str
    name: str
    terms: list[str]
    items: list[Item] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.items)


def _title_case(word: str) -> str:
    return word[:1].upper() + word[1:] if word else word


def _terms(item: Item) -> tuple[set[str], set[str]]:
    """Return (tag terms, title terms). Tags are curated, so they lead the candidates."""
    tags = {stem(tag.lower()) for tag in split_tags(item.tags)}
    title = set(tokenize(item.title))
    return tags, title


def build_clusters(items: list[Item], limit: int = 6, min_shared: int = 2) -> list[Cluster]:
    """Greedy grouping on the most widely shared tag or title term.

    Deterministic: tag terms are considered before title terms, then document frequency,
    then weighted frequency, then alphabetically. Clusters may overlap: they are lenses
    on the library, not a partition of it. A cluster must hold at least ``min_shared``
    items, and identical member sets are never repeated.
    """
    if len(items) < min_shared:
        return []
    total = len(items)
    tag_df: dict[str, int] = {}
    title_df: dict[str, int] = {}
    doc_freq: dict[str, int] = {}
    term_freq: dict[str, int] = {}
    by_item: dict[int, set[str]] = {}
    for item in items:
        tags, title = _terms(item)
        by_item[item.id] = tags | title
        for term in tags:
            tag_df[term] = tag_df.get(term, 0) + 1
        for term in title:
            title_df[term] = title_df.get(term, 0) + 1
        for term in by_item[item.id]:
            doc_freq[term] = doc_freq.get(term, 0) + 1
            term_freq[term] = term_freq.get(term, 0) + (2 if term in tags else 0) + (3 if term in title else 0)

    ceiling = total if total < 5 else max(min_shared, int(math.ceil(total * 0.6)))
    candidates = [
        term
        for term, df in doc_freq.items()
        if min_shared <= df <= ceiling
        and len(term) > 2
        and not term.isdigit()
        and term not in GENERIC
    ]
    candidates.sort(
        key=lambda term: (
            0 if tag_df.get(term, 0) >= min_shared else 1,
            -doc_freq[term],
            -term_freq.get(term, 0),
            term,
        )
    )

    seen: set[frozenset[int]] = set()
    clusters: list[Cluster] = []
    for term in candidates:
        members = [item for item in items if term in by_item[item.id]]
        if len(members) < min_shared:
            continue
        signature = frozenset(item.id for item in members)
        if signature in seen:
            continue
        shared: dict[str, int] = {}
        for item in members:
            for word in by_item[item.id]:
                shared[word] = shared.get(word, 0) + 1
        companions = sorted(
            (
                word for word, count in shared.items()
                if count == len(members) and word != term and word not in GENERIC
            ),
            key=lambda word: (-doc_freq.get(word, 0), word),
        )[:2]
        display = [_title_case(label(word).replace("-", " ")) for word in [term, *companions]]
        clusters.append(
            Cluster(
                slug=slugify("-".join(display)),
                name=" · ".join(display),
                terms=display,
                items=sorted(members, key=lambda item: item.updated_at, reverse=True),
            )
        )
        seen.add(signature)
        if len(clusters) >= limit:
            break
    return clusters
