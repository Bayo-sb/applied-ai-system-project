"""Keyword (TF-IDF) retriever over the care passages.

Passages are first filtered by the pet's species and life stage, then ranked against a query by
cosine similarity. Scores are between 0 and 1. The retriever only reports the best score and
whether it clears the confidence cut-off. What to do about low confidence is the pipeline's job.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from knowledge_base import KnowledgeBase, Passage

# Provisional. Set from 16 measured queries (see eval_retrieval.py): the lowest answerable query
# scored 0.251 and the highest unanswerable one 0.201, so this sits between them. That is a small
# sample with a narrow gap. Rerun eval_retrieval.py whenever the documents change.
CONFIDENCE_THRESHOLD = 0.225
DEFAULT_TOP_K = 8

# What the system looks up for a newly added pet: one short query per care topic. Fixed, so
# results are repeatable. A single long query scored poorly against every passage.
TOPIC_QUERIES = [
    "feeding meals per day",
    "fresh water each day",
    "clean the litter box",
    "veterinary wellness exam visit",
    "senior cat veterinary visits twice a year",
    "kitten veterinary visits first vaccine series",
    "teeth cleaning dental",
    "weight and body condition",
    "fecal exam parasite testing",
    "parasite control vaccination veterinarian",
    "wash the litter tray once a week",
    "wash food and water bowls daily",
    "play with the cat morning and evening",
    "kitten training session minutes",
    "daily walk exercise",
    "dog training minutes per day play",
    "toilet breaks routine take the dog out",
    "yearly veterinary check-up visit dog",
    "brushing teeth daily dental disease",
    "puppy vaccination schedule veterinarian",
    "worming heartworm prevention",
    "puppy worming schedule",
    "annual vaccination booster adult dog",
]
CARE_QUERY = TOPIC_QUERIES[0]

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "its",
    "of", "on", "or", "that", "the", "to", "with", "this", "can", "may", "so", "than",
    "how", "i", "my", "should", "do", "does", "what", "when", "your", "you",
}


def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS]


@dataclass(frozen=True)
class Hit:
    passage: Passage
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    hits: list
    best_score: float
    confident: bool


def _vectors(docs: list[list[str]], query: list[str]):
    n = len(docs)
    df = Counter(term for d in docs for term in set(d))
    idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}

    def vec(tokens):
        counts = Counter(tokens)
        return {t: (1 + math.log(c)) * idf.get(t, 0.0) for t, c in counts.items() if t in idf}

    return [vec(d) for d in docs], vec(query)


def _cosine(a: dict, b: dict) -> float:
    dot = sum(v * b.get(t, 0.0) for t, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


def retrieve(
    kb: KnowledgeBase,
    species: str,
    stage: str | None,
    query: str = CARE_QUERY,
    top_k: int = DEFAULT_TOP_K,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> RetrievalResult:
    """Return the best passages for this species and stage, with scores."""
    candidates = [p for p in kb.passages.values() if p.applies_to(species, stage)]
    if not candidates:
        return RetrievalResult([], 0.0, False)
    docs = [tokenize(p.heading + " " + p.text) for p in candidates]
    doc_vecs, q_vec = _vectors(docs, tokenize(query))
    hits = sorted(
        (Hit(p, _cosine(v, q_vec)) for p, v in zip(candidates, doc_vecs)),
        key=lambda h: (-h.score, h.passage.id),
    )
    hits = [h for h in hits if h.score > 0][:top_k]
    best = hits[0].score if hits else 0.0
    return RetrievalResult(hits, best, best >= threshold)


def retrieve_topics(
    kb: KnowledgeBase,
    species: str,
    stage: str | None,
    queries: list[str] = TOPIC_QUERIES,
    top_k: int = DEFAULT_TOP_K,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> RetrievalResult:
    """Run one query per care topic and merge the passages that clear the cut-off.

    Each passage keeps its best score over the topics. `confident` is True if any passage clears
    the cut-off. Passages below it are dropped, so the agent never sees weak matches.
    """
    best: dict[str, Hit] = {}
    for q in queries:
        for hit in retrieve(kb, species, stage, q, top_k=top_k, threshold=threshold).hits:
            if hit.score >= threshold and (hit.passage.id not in best or hit.score > best[hit.passage.id].score):
                best[hit.passage.id] = hit
    hits = sorted(best.values(), key=lambda h: (-h.score, h.passage.id))
    overall = max((retrieve(kb, species, stage, q, threshold=threshold).best_score for q in queries), default=0.0)
    return RetrievalResult(hits, overall, bool(hits))
