"""The local search engine: query parsing, ranking, snippets and related items.

Everything here is deterministic and offline. The UI shows exactly how a query was
understood, so a surprising result can be traced to a term, a synonym or a filter.
"""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from ..models import KINDS, Item

STOPWORDS = {
    "a", "about", "after", "again", "against", "all", "also", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once",
    "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "would", "you", "your", "yours", "yourself",
    "about", "find", "show", "tell", "give", "want", "need", "look", "search", "anything",
    "something", "everything",
}

# Function words that survive the stopword list but say nothing about a shared subject.
RELATED_NOISE = {
    "get", "got", "give", "gave", "make", "made", "take", "took", "come", "came", "say",
    "said", "see", "seen", "go", "went", "use", "used", "want", "need", "know", "think",
    "thing", "things", "way", "time", "day", "week", "year", "also", "just", "like", "one",
    "two", "first", "last", "next", "new", "old", "good", "bad", "big", "small", "many",
    "much", "more", "most", "some", "any", "all", "each", "every", "other", "same", "own",
}

# Canonical term -> related surface forms. expand() makes this symmetric.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "price": ("pricing", "cost", "costs", "fee", "fees", "budget", "rate", "ratecard"),
    "salary": ("pay", "compensation", "package", "ctc"),
    "meeting": ("sync", "standup", "call", "catchup"),
    "plan": ("roadmap", "strategy", "schedule", "timeline"),
    "ai": ("llm", "model", "claude", "gpt", "agent", "agents"),
    "tax": ("gst", "vat", "deduction"),
    "contract": ("agreement", "msa", "sow", "terms"),
    "customer": ("client", "account", "buyer"),
    "hiring": ("recruit", "interview", "candidate", "role"),
    "travel": ("trip", "flight", "hotel", "itinerary"),
    "health": ("sleep", "exercise", "workout", "diet"),
    "code": ("software", "programming", "repo", "script", "python"),
    "design": ("ui", "ux", "layout", "wireframe", "typography"),
    "marketing": ("brand", "campaign", "launch", "content"),
    "finance": ("money", "revenue", "invoice", "cash"),
    "database": ("sql", "postgres", "sqlite", "schema"),
    "book": ("reading", "read", "author", "chapter"),
    "research": ("paper", "study", "source", "evidence"),
    "security": ("privacy", "auth", "password", "encryption"),
    "writing": ("draft", "essay", "prose", "edit"),
}

_CANON: dict[str, set[str]] = {}
for _canonical, _related in SYNONYMS.items():
    group = {_canonical, *_related}
    for _word in group:
        _CANON.setdefault(_word, set()).update(group)

FILTER_RE = re.compile(r"(?:(?<=^)|(?<=\s))(kind|tag|in|collection|is):(\S+)", re.IGNORECASE)
PHRASE_RE = re.compile(r'"([^"]{2,80})"')
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.'’-]*")


def normalize(text: str) -> str:
    return (
        (text or "")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )


def stem(word: str) -> str:
    """A small suffix stripper, not a linguist. It only has to be stable."""
    word = word.lower().strip(".'’")
    if len(word) <= 3 or word.isdigit():
        return word
    if word.endswith("'s"):
        word = word[:-2]
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("sses", "shes", "ches", "xes", "zes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")) and len(word) > 3:
        word = word[:-1]
    if word.endswith("ing") and len(word) > 5:
        word = word[:-3]
    elif word.endswith("ed") and len(word) > 4:
        word = word[:-2]
    if len(word) > 4 and word[-1] == word[-2] and word[-1] not in "aeiouls":
        word = word[:-1]
    return word


DISPLAY: dict[str, str] = {}
for _canonical, _related in SYNONYMS.items():
    for _word in {_canonical, *_related}:
        _stemmed = stem(_word)
        if _stemmed == _word:
            DISPLAY[_stemmed] = _word
for _canonical, _related in SYNONYMS.items():
    for _word in {_canonical, *_related}:
        DISPLAY.setdefault(stem(_word), _word)


def label(term: str) -> str:
    """A presentable surface form for an indexed term."""
    return DISPLAY.get(term, term)


_CANON_STEMS: dict[str, set[str]] = {}
for _group in _CANON.values():
    _stems = {stem(word) for word in _group}
    for _stemmed in _stems:
        _CANON_STEMS.setdefault(_stemmed, set()).update(_stems)


def tokenize(text: str) -> list[str]:
    words: list[str] = []
    for match in TOKEN_RE.findall(normalize(text)):
        lowered = match.lower().strip(".'’-")
        if len(lowered) < 2 and not lowered.isdigit():
            continue
        if lowered in STOPWORDS:
            continue
        words.append(stem(lowered))
    return words


def expand(term: str) -> list[str]:
    """The term itself plus its known relatives, in a stable order."""
    group = _CANON_STEMS.get(term, {term})
    return sorted(group)


def split_tags(raw: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for piece in re.split(r"[,;]", raw or ""):
        tag = re.sub(r"\s+", " ", piece.strip())
        if not tag or len(tag) > 32:
            continue
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            out.append(tag)
    return out[:10]


def tag_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-") or "tag"


def url_host(url: str) -> str:
    try:
        parsed = urlparse(url or "")
    except ValueError:
        return ""
    return (parsed.netloc or "").removeprefix("www.")[:80]


@dataclass
class Query:
    raw: str
    text: str
    terms: list[str] = field(default_factory=list)
    expansions: list[str] = field(default_factory=list)
    phrases: list[str] = field(default_factory=list)
    kind: str = ""
    tag: str = ""
    collection: str = ""
    starred: bool = False
    ignored: list[str] = field(default_factory=list)
    surface: dict[str, str] = field(default_factory=dict)

    @property
    def all_terms(self) -> list[str]:
        return list(dict.fromkeys([*self.terms, *self.expansions]))

    @property
    def terms_display(self) -> list[str]:
        return _unique(self.surface.get(term, label(term)) for term in self.terms)

    @property
    def expansions_display(self) -> list[str]:
        return _unique(self.surface.get(term, label(term)) for term in self.expansions)

    @property
    def display_terms(self) -> list[str]:
        return _unique([*self.terms_display, *self.expansions_display])

    @property
    def active(self) -> bool:
        return bool(self.terms or self.phrases or self.kind or self.tag or self.collection or self.starred)

    def summary(self) -> list[str]:
        bits: list[str] = []
        if self.terms_display:
            bits.append("terms: " + ", ".join(self.terms_display))
        if self.expansions_display:
            bits.append("also matching: " + ", ".join(self.expansions_display))
        if self.phrases:
            bits.append("exact phrase: " + ", ".join(f'"{p}"' for p in self.phrases))
        if self.kind:
            bits.append(f"kind: {self.kind}")
        if self.tag:
            bits.append(f"tag: {self.tag}")
        if self.collection:
            bits.append(f"collection: {self.collection}")
        if self.starred:
            bits.append("starred only")
        if self.ignored:
            bits.append("ignored: " + ", ".join(self.ignored))
        return bits


def _unique(values) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def parse_query(raw: str) -> Query:
    original = normalize(raw or "").strip()
    query = Query(raw=original, text=original)

    cleaned = original
    for match in FILTER_RE.finditer(original):
        name, value = match.group(1).lower(), match.group(2).strip().strip('"')
        cleaned = cleaned.replace(match.group(0), " ")
        if name == "kind":
            if value.lower() in KINDS:
                query.kind = value.lower()
            else:
                query.ignored.append(f"kind:{value}")
        elif name == "tag":
            query.tag = value.lower()
        elif name in ("in", "collection"):
            query.collection = value.lower()
        elif name == "is":
            if value.lower() in ("starred", "favourite", "favorite"):
                query.starred = True
            else:
                query.ignored.append(f"is:{value}")

    for match in PHRASE_RE.finditer(cleaned):
        phrase = re.sub(r"\s+", " ", match.group(1)).strip().lower()
        if phrase:
            query.phrases.append(phrase)
        cleaned = cleaned.replace(match.group(0), " ")

    surfaces: dict[str, str] = {}
    ordered: list[str] = []
    for match in TOKEN_RE.finditer(cleaned):
        word = match.group(0).lower().strip(".'’-")
        if len(word) < 2 and not word.isdigit():
            continue
        if word in STOPWORDS:
            continue
        term = stem(word)
        if term not in surfaces:
            surfaces[term] = word
        if term not in ordered:
            ordered.append(term)
    query.terms = ordered[:12]
    expanded: list[str] = []
    for term in query.terms:
        for cousin in expand(term):
            if cousin not in query.terms and cousin not in expanded:
                expanded.append(cousin)
                surfaces.setdefault(cousin, DISPLAY.get(cousin, cousin))
    query.expansions = expanded[:16]
    query.surface = {term: surfaces[term] for term in [*query.terms, *query.expansions] if term in surfaces}
    return query


def _field_tokens(item: Item) -> dict[str, list[str]]:
    return {
        "title": tokenize(item.title),
        "tags": tokenize(item.tags),
        "author": tokenize(item.author),
        "source": tokenize(url_host(item.source_url)),
        "body": tokenize(item.body),
    }


def _slug(value: str) -> str:
    """Compare collection names the way a person types them: 'Client work' == 'client-work'."""
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


def _matches_filters(item: Item, query: Query) -> bool:
    if query.kind and item.kind != query.kind:
        return False
    if query.starred and not item.starred:
        return False
    if query.tag and _slug(query.tag) not in {_slug(t) for t in split_tags(item.tags)}:
        return False
    if query.collection:
        name = _slug(item.collection.name) if item.collection else ""
        if _slug(query.collection) not in name:
            return False
    return True


def _phrase_hits(haystack: str, phrase: str) -> int:
    if not phrase:
        return 0
    return normalize(haystack).lower().count(phrase)


@dataclass
class Hit:
    item: Item
    score: float
    matched: list[str]
    snippet: str
    phrase_hits: int = 0

    @property
    def percent(self) -> int:
        """A bounded, presentational read of the raw score."""
        return max(1, min(100, round(100 * self.score / (self.score + 6))))


def _idf(total: int, df: int) -> float:
    return math.log(1 + (total - df + 0.5) / (df + 0.5))


def search(
    items: list[Item],
    query: Query,
    *,
    limit: int = 40,
    now=None,
) -> list[Hit]:
    pool = [item for item in items if _matches_filters(item, query)]
    if not query.active:
        pool.sort(key=lambda item: item.updated_at, reverse=True)
        return [Hit(item, 0.0, [], snippet(item.body, [], 220)) for item in pool[:limit]]

    prepared = [(item, _field_tokens(item)) for item in pool]
    total = max(1, len(prepared))
    df: dict[str, int] = {}
    for _, fields in prepared:
        present = {stem(word) for words in fields.values() for word in words}
        for term in query.all_terms:
            if term in present:
                df[term] = df.get(term, 0) + 1

    weights = {"title": 3.0, "tags": 2.2, "author": 1.4, "source": 1.2, "body": 1.0}
    hits: list[Hit] = []
    for item, fields in prepared:
        score = 0.0
        matched: list[str] = []
        for term in query.all_terms:
            tf_weighted = sum(
                weights[name] * fields[name].count(term) for name in weights if fields[name]
            )
            if tf_weighted:
                boost = 1.0 if term in query.terms else 0.55
                score += boost * _idf(total, df.get(term, 0)) * (tf_weighted / (tf_weighted + 1.2))
                matched.append(term)
        title_hits = sum(_phrase_hits(item.title, phrase) for phrase in query.phrases)
        body_hits = sum(_phrase_hits(item.body, phrase) for phrase in query.phrases)
        occurrences = title_hits + body_hits
        if occurrences:
            score += 6.0 * (2 * title_hits + body_hits)
        if query.terms and all(term in matched for term in query.terms):
            score += 3.0
        if query.starred:
            score += 1.0
        if score <= 0 and (query.terms or query.phrases):
            continue
        matched_display = _unique(query.surface.get(term, label(term)) for term in sorted(set(matched)))
        highlight = _unique(
            [*matched_display, *(word for phrase in query.phrases for word in phrase.split())]
        )
        hits.append(
            Hit(
                item=item,
                score=round(score, 4),
                matched=matched_display,
                snippet=snippet(item.body, highlight, 240),
                phrase_hits=occurrences,
            )
        )

    hits.sort(key=lambda hit: (-hit.score, -hit.item.updated_at.timestamp(), hit.item.id))
    return hits[:limit]


def search_count(items: list[Item], query: Query) -> int:
    return len(search(items, query, limit=10_000))


def _highlight_pattern(terms: list[str]):
    """A boundary-aware pattern so 'rate' does not mark the middle of 'separate'."""
    parts: list[str] = []
    for term in sorted(set(terms), key=len, reverse=True):
        if len(term) < 2:
            continue
        piece = re.escape(term)
        if term[0].isalnum():
            piece = r"(?<![A-Za-z0-9])" + piece
        if term[-1].isalnum():
            piece += r"(?:s|es|ed|d|ing|ly)?(?![A-Za-z0-9])"
        parts.append(piece)
    if not parts:
        return None
    return re.compile("(" + "|".join(parts) + ")", re.IGNORECASE)


def snippet(body: str, terms: list[str], width: int = 240) -> str:
    """Escape a body, then mark the first matching window. The result is safe HTML."""
    text = re.sub(r"\s+", " ", normalize(body or "")).strip()
    if not text:
        return ""
    pattern = _highlight_pattern(terms)
    first = pattern.search(text) if pattern else None
    if first is None:
        piece = text[:width]
        return html.escape(piece) + ("…" if len(text) > width else "")

    start = max(0, first.start() - width // 3)
    end = min(len(text), start + width)
    if start:
        while start < first.start() and text[start - 1] not in " ":
            start += 1
    if end < len(text):
        while end > first.start() and text[end - 1] not in " ":
            end -= 1
    window = text[start:end]

    out: list[str] = []
    cursor = 0
    for match in pattern.finditer(window):
        out.append(html.escape(window[cursor:match.start()]))
        out.append("<mark>" + html.escape(match.group(1)) + "</mark>")
        cursor = match.end()
    out.append(html.escape(window[cursor:]))
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return prefix + "".join(out) + suffix


def related(items: list[Item], target: Item, limit: int = 4) -> list[Hit]:
    """Other items sharing rare terms with this one, using the same scoring idea."""
    others = [item for item in items if item.id != target.id and item.user_id == target.user_id]
    if not others:
        return []
    target_terms = set(tokenize(f"{target.title} {target.tags} {target.body}"))
    if not target_terms:
        return []
    total = len(others)
    df: dict[str, int] = {}
    prepared = []
    for item in others:
        terms = set(tokenize(f"{item.title} {item.tags} {item.body}"))
        prepared.append((item, terms))
        for term in target_terms:
            if term in terms:
                df[term] = df.get(term, 0) + 1
    hits: list[Hit] = []
    for item, terms in prepared:
        shared = sorted(
            term
            for term in target_terms & terms
            if not term.isdigit() and term not in RELATED_NOISE
        )
        if not shared:
            continue
        score = sum(_idf(total, df.get(term, 0)) for term in shared)
        display = _unique(label(term) for term in sorted(shared, key=lambda word: (-_idf(total, df.get(word, 0)), word)))[:5]
        hits.append(Hit(item, round(score, 4), display, snippet(item.body, display, 160)))
    hits.sort(key=lambda hit: (-hit.score, -hit.item.updated_at.timestamp()))
    return hits[:limit]
