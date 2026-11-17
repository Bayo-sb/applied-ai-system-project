"""Loads the care documents in knowledge_base/ into passages and claims.

A document is a markdown file. Its header gives `Species:` and `Stages:`. Every `## ` section is a
passage (the "Source" section is metadata, not a passage). A section may carry one or more
```claim blocks: the structured facts the compliance check verifies a proposal against.

Loading fails loudly if a claim's quotes are not found in its own passage, so a claim cannot
point at wording the passage does not contain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent / "knowledge_base"

CADENCES = {"daily", "weekly", "other", "none"}
# How a source's importance wording maps to a priority. This mapping is the system's own rule,
# not the sources': essential = needed for health in general, recommended = depends on the
# animal or situation, optional = comfort or enrichment.
IMPORTANCE_TO_PRIORITY = {"essential": "HIGH", "recommended": "MEDIUM", "optional": "LOW"}


class KnowledgeBaseError(Exception):
    """A care document is malformed or a claim does not match its passage."""


def normalize(text: str) -> str:
    """Lowercase and collapse whitespace and curly quotes, for quote matching."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


@dataclass(frozen=True)
class Passage:
    id: str
    source_title: str
    source_author: str
    heading: str
    species: str
    stages: frozenset  # empty means all life stages
    text: str

    def applies_to(self, species: str, stage: str | None) -> bool:
        if self.species != species:
            return False
        return not self.stages or (stage is not None and stage in self.stages)

    @property
    def citation(self) -> str:
        return f"{self.source_title} ({self.source_author}), section '{self.heading}'"


@dataclass(frozen=True)
class Claim:
    id: str
    passage_id: str
    task: str
    cadence: str  # daily, weekly, other or none
    cadence_text: str
    cadence_quote: str
    importance: str  # essential, recommended or optional
    importance_quote: str
    medication: bool
    duration_minutes: int | None = None  # set only when the source states a duration
    duration_text: str = ""
    duration_quote: str = ""

    @property
    def priority(self) -> str:
        return IMPORTANCE_TO_PRIORITY[self.importance]


@dataclass
class KnowledgeBase:
    passages: dict = field(default_factory=dict)  # id -> Passage
    claims: dict = field(default_factory=dict)  # id -> Claim

    def claims_for(self, passage_ids) -> list[Claim]:
        wanted = set(passage_ids)
        return [c for c in self.claims.values() if c.passage_id in wanted]

    def species(self) -> set[str]:
        return {p.species for p in self.passages.values()}


_CLAIM_RE = re.compile(r"```claim\n(.*?)```", re.DOTALL)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _parse_stages(value: str) -> frozenset:
    value = value.strip().lower()
    if value in ("", "all"):
        return frozenset()
    return frozenset(s.strip() for s in value.split(",") if s.strip())


def _parse_claim(block: str, passage: Passage) -> Claim:
    fields = {}
    for line in block.strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    where = f"claim in {passage.id}"
    for required in ("id", "task", "cadence", "importance", "importance_quote", "medication"):
        if required not in fields:
            raise KnowledgeBaseError(f"{where} is missing '{required}'.")
    if fields["cadence"] not in CADENCES:
        raise KnowledgeBaseError(f"{where}: cadence must be one of {sorted(CADENCES)}.")
    if fields["importance"] not in IMPORTANCE_TO_PRIORITY:
        raise KnowledgeBaseError(f"{where}: importance must be one of {sorted(IMPORTANCE_TO_PRIORITY)}.")
    text = normalize(passage.text)
    if fields["cadence"] != "none":
        for key in ("cadence_text", "cadence_quote"):
            if not fields.get(key):
                raise KnowledgeBaseError(f"{where} needs '{key}' when cadence is not 'none'.")
        if normalize(fields["cadence_quote"]) not in text:
            raise KnowledgeBaseError(f"{where}: cadence_quote is not in the passage text.")
    if normalize(fields["importance_quote"]) not in text:
        raise KnowledgeBaseError(f"{where}: importance_quote is not in the passage text.")
    duration = None
    if "duration_minutes" in fields:
        try:
            duration = int(fields["duration_minutes"])
        except ValueError:
            raise KnowledgeBaseError(f"{where}: duration_minutes must be a whole number.") from None
        if duration < 1:
            raise KnowledgeBaseError(f"{where}: duration_minutes must be at least 1.")
        if not fields.get("duration_quote") or normalize(fields["duration_quote"]) not in text:
            raise KnowledgeBaseError(f"{where}: duration_quote is missing or not in the passage text.")
    return Claim(
        id=fields["id"],
        passage_id=passage.id,
        task=fields["task"],
        cadence=fields["cadence"],
        cadence_text=fields.get("cadence_text", ""),
        cadence_quote=fields.get("cadence_quote", ""),
        importance=fields["importance"],
        importance_quote=fields["importance_quote"],
        medication=fields["medication"].lower() in ("yes", "true"),
        duration_minutes=duration,
        duration_text=fields.get("duration_text", ""),
        duration_quote=fields.get("duration_quote", ""),
    )


def load_document(path: Path, kb: KnowledgeBase) -> None:
    raw = path.read_text(encoding="utf-8")
    header, *sections = re.split(r"^## ", raw, flags=re.MULTILINE)
    species_match = re.search(r"^Species:\s*(\S+)", header, re.MULTILINE)
    if not species_match:
        raise KnowledgeBaseError(f"{path.name} has no 'Species:' line in its header.")
    species = species_match.group(1).lower()
    stages_match = re.search(r"^Stages:\s*(.*)$", header, re.MULTILINE)
    doc_stages = _parse_stages(stages_match.group(1) if stages_match else "all")

    title = author = ""
    for section in sections:
        heading, _, body = section.partition("\n")
        heading = heading.strip()
        if heading.lower() == "source":
            t = re.search(r'Title:\s*"([^"]+)"', body) or re.search(r"Title:\s*(.+)", body)
            a = re.search(r"Authors?:\s*(.+)", body)
            title = t.group(1).strip() if t else path.stem
            author = a.group(1).strip() if a else ""
            continue
        stages = doc_stages
        m = re.search(r"^Stages:\s*(.*)$", body, re.MULTILINE)
        if m:
            stages = _parse_stages(m.group(1))
            body = body.replace(m.group(0), "")
        claim_blocks = _CLAIM_RE.findall(body)
        text = _CLAIM_RE.sub("", body).strip()
        passage = Passage(
            id=f"{path.stem}#{_slug(heading)}",
            source_title=title or path.stem,
            source_author=author,
            heading=heading,
            species=species,
            stages=stages,
            text=text,
        )
        if passage.id in kb.passages:
            raise KnowledgeBaseError(f"Duplicate passage id {passage.id}.")
        kb.passages[passage.id] = passage
        for block in claim_blocks:
            claim = _parse_claim(block, passage)
            if claim.id in kb.claims:
                raise KnowledgeBaseError(f"Duplicate claim id {claim.id}.")
            kb.claims[claim.id] = claim


def load_knowledge_base(directory: Path = KB_DIR) -> KnowledgeBase:
    """Load every top-level .md file in `directory`. Subfolders (such as drafts/) are ignored."""
    kb = KnowledgeBase()
    for path in sorted(directory.glob("*.md")):
        load_document(path, kb)
    return kb
