"""Runs the whole care-suggestion flow for one pet and returns what the owner should review.

guardrails -> life stage -> retriever -> LLM agent -> compliance check -> (human review in the app)
The scheduler and plan verifier run afterwards, on the tasks the owner accepts.

Every step is recorded in `trace`. Nothing here adds a task to a pet. That happens only in
`accept_item`, called after the owner approves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import compliance as cmp
from agent import MAX_GENERAL_TASKS, propose_tasks
from guardrails import SUPPORTED_SPECIES, validate_pet_input
from knowledge_base import KnowledgeBase, load_knowledge_base
from life_stage import life_stage
from llm_client import LLM, LLMError
from pawpal_system import Frequency, Owner, Pet, Priority, Task
from retriever import retrieve_topics

OVERRIDE_SUFFIX = " [failed check, owner override]"
UNSOURCED_SUFFIX = " [AI suggestion, no source]"
UNSOURCED_CITATION = "none (AI general knowledge)"
MEDICATION_NOTE = (
    "Vaccinations, worming, heartworm prevention and other medication are decided with your "
    "veterinarian. They are not part of these suggestions, and no product or dose is given."
)


@dataclass
class ReviewItem:
    claim_id: str
    title: str
    priority: str
    cadence: str  # daily, weekly, other or none
    cadence_text: str
    duration_minutes: int | None  # None for medication items: the owner enters it
    status: str  # PASS, ESCALATE, DECLINE or MEDICATION
    reasons: list = field(default_factory=list)
    citation: str = ""
    duration_from_source: bool = False
    duration_text: str = ""

    @property
    def duration_is_estimate(self) -> bool:
        return self.duration_minutes is not None and not self.duration_from_source

    @property
    def can_accept(self) -> bool:
        return self.status != cmp.DECLINE


@dataclass
class SuggestionResult:
    pet_name: str
    pet_label: str = ""
    stage: str | None = None
    items: list = field(default_factory=list)  # ReviewItems the owner may accept
    unsourced: list = field(default_factory=list)  # tasks from the model's own knowledge: shown apart, owner decides
    declined: list = field(default_factory=list)  # ReviewItems or reasons that cannot be accepted
    messages: list = field(default_factory=list)  # warnings for the owner
    notes: list = field(default_factory=list)  # standing information, e.g. ask your vet
    redirected: list = field(default_factory=list)  # AI proposals removed because they involve medication
    trace: list = field(default_factory=list)  # [{"step": ..., "detail": ...}]

    def log(self, step: str, detail: str) -> None:
        self.trace.append({"step": step, "detail": detail})

    def decline_all(self, reason: str) -> "SuggestionResult":
        self.messages.append(reason)
        self.log("decline", reason)
        return self


@dataclass
class Preparation:
    """Everything decided before the model is called. `ready` is False if the pipeline already stopped."""

    result: SuggestionResult
    species: str = ""
    stage: str | None = None
    owner_minutes: int = 0
    claims: dict = field(default_factory=dict)
    passages: dict = field(default_factory=dict)
    candidates: list = field(default_factory=list)  # (claim, passage) pairs the model may use
    ready: bool = False


def prepare(owner: Owner, pet: Pet, today: date | None = None, kb: KnowledgeBase | None = None) -> Preparation:
    """Run the steps before the model: guardrails, life stage, retrieval, medication filter."""
    today = today or date.today()
    kb = kb or load_knowledge_base()
    result = SuggestionResult(pet_name=pet.name, pet_label=pet.label)
    prep = Preparation(result=result, species=pet.species, owner_minutes=owner.available_minutes_per_day)

    # 1. Guardrails
    problems = validate_pet_input(pet.name, pet.species, pet.birth_date, today)
    result.log("guardrails", "; ".join(problems) if problems else "input valid")
    if problems:
        result.decline_all("Cannot suggest tasks: " + " ".join(problems))
        return prep
    if pet.species not in kb.species():
        result.decline_all(
            f"There is no care guidance for '{pet.species}' in the knowledge base, so no tasks are suggested."
        )
        return prep

    # 2. Life stage
    stage = life_stage(pet.species, pet.birth_date, today)
    prep.stage = result.stage = stage
    result.log("life_stage", f"{stage}" if stage else "no stage definition for this species")
    if stage is None:
        result.decline_all(
            f"No source in the knowledge base defines life stages for a {pet.species}, so no tasks are suggested."
        )
        return prep

    # 3. Retrieval
    found = retrieve_topics(kb, pet.species, stage, top_k=20)
    result.log("retrieval", f"{len(found.hits)} passages, best score {found.best_score:.2f}, confident={found.confident}")
    if not found.confident:
        result.decline_all(
            f"The knowledge base has no confident match for a {stage} {pet.species}, so no tasks are suggested."
        )
        return prep
    prep.passages = {h.passage.id: h.passage for h in found.hits}
    prep.claims = {c.id: c for c in kb.claims_for(prep.passages)}

    # 4. Medication claims are never suggested and never sent to the model.
    medication_claims = [c for c in prep.claims.values() if c.medication]
    for claim in medication_claims:
        result.log("medication", f"{claim.id} not suggested: medication is decided with a veterinarian")
    if medication_claims:
        result.notes.append(MEDICATION_NOTE)

    prep.candidates = [(c, prep.passages[c.passage_id]) for c in prep.claims.values() if not c.medication]
    prep.ready = True
    return prep


def review(prep: Preparation, proposals: list, response=None) -> SuggestionResult:
    """Run the compliance check on proposals and sort them into items, declined and redirected."""
    result = prep.result
    if response is not None:
        result.log(
            "agent",
            f"model={response.model} proposals={len(proposals)} in={response.input_tokens} "
            f"out={response.output_tokens} request_id={response.request_id}",
        )
    seen = set()
    general_titles = set()
    for p in proposals:
        if p.is_general:
            _review_general(result, p, prep, general_titles)
            continue
        if p.claim_id in seen:
            result.log("compliance", f"duplicate proposal for {p.claim_id} ignored")
            continue
        seen.add(p.claim_id)
        check = cmp.check_proposal(p, prep.claims, prep.passages, prep.species, prep.stage, prep.owner_minutes)
        claim = prep.claims.get(p.claim_id)
        item = ReviewItem(
            claim_id=p.claim_id,
            title=p.title,
            priority=p.priority,
            cadence=claim.cadence if claim else "none",
            cadence_text=claim.cadence_text if claim else "",
            duration_minutes=(
                claim.duration_minutes
                if claim and claim.duration_minutes is not None
                else p.duration_minutes if isinstance(p.duration_minutes, int) and not isinstance(p.duration_minutes, bool) else None
            ),
            status=check.status,
            reasons=check.reasons,
            citation=prep.passages[claim.passage_id].citation if claim else "",
            duration_from_source=bool(claim and claim.duration_minutes is not None),
            duration_text=claim.duration_text if claim else "",
        )
        result.log("compliance", f"{p.claim_id}: {check.status} {check.reasons}")
        if check.status == cmp.MEDICATION:
            result.redirected.append(item)
            if MEDICATION_NOTE not in result.notes:
                result.notes.append(MEDICATION_NOTE)
        elif check.status == cmp.DECLINE:
            result.declined.append(item)
        else:
            result.items.append(item)
    return result


def _review_general(result: SuggestionResult, p, prep: Preparation, titles: set) -> None:
    """Check a task the model proposed from its own knowledge (no source) and file it."""
    title_key = p.title.strip().lower()
    if title_key in titles:
        result.log("compliance", f"duplicate general proposal '{p.title}' ignored")
        return
    if len(titles) >= MAX_GENERAL_TASKS:
        result.log("compliance", f"general proposal '{p.title}' ignored: more than {MAX_GENERAL_TASKS} allowed")
        return
    titles.add(title_key)
    check = cmp.check_general(p, prep.owner_minutes)
    duration = p.duration_minutes if isinstance(p.duration_minutes, int) and not isinstance(p.duration_minutes, bool) else None
    item = ReviewItem(
        claim_id=f"general-{len(titles)}",
        title=p.title,
        priority=p.priority if p.priority in cmp.GENERAL_PRIORITIES else "MEDIUM",
        cadence=p.frequency if p.frequency in cmp.GENERAL_FREQUENCIES else "none",
        cadence_text=p.frequency,
        duration_minutes=duration,
        status=check.status,
        reasons=check.reasons,
        citation=UNSOURCED_CITATION,
    )
    result.log("compliance", f"general '{p.title}': {check.status} {check.reasons}")
    if check.status == cmp.MEDICATION:
        result.redirected.append(item)
        if MEDICATION_NOTE not in result.notes:
            result.notes.append(MEDICATION_NOTE)
    elif check.status == cmp.DECLINE:
        result.declined.append(item)
    else:
        result.unsourced.append(item)


def suggest_tasks(
    owner: Owner, pet: Pet, llm: LLM, today: date | None = None, kb: KnowledgeBase | None = None
) -> SuggestionResult:
    """The whole flow: prepare, ask the model, then check what it proposed."""
    prep = prepare(owner, pet, today, kb)
    if not prep.ready or not prep.candidates:
        return prep.result
    try:
        proposals, response = propose_tasks(
            llm, pet.name, pet.species, prep.stage, prep.owner_minutes, prep.candidates
        )
    except LLMError as exc:
        prep.result.messages.append(f"The AI step failed ({type(exc).__name__}): {exc} No tasks were suggested.")
        prep.result.log("agent_error", f"{type(exc).__name__}: {exc}")
        return prep.result
    return review(prep, proposals, response)


def task_title(item: ReviewItem) -> str:
    """The title the task gets on the pet's list."""
    title = item.title
    if item.cadence not in ("daily", "weekly") and item.cadence_text:
        title = f"{title} ({item.cadence_text})"
    if item.status == cmp.ESCALATE:
        title += OVERRIDE_SUFFIX
    if item.status == cmp.UNSOURCED:
        title += UNSOURCED_SUFFIX
    return title


def already_on_pet(pet: Pet, item: ReviewItem) -> bool:
    """True if this item's task is already pending on the pet's list."""
    title = task_title(item)
    return any(t.title == title and not t.completed for t in pet.tasks)


def accept_item(pet: Pet, item: ReviewItem, duration_minutes: int | None = None) -> Task:
    """Add an item the owner approved to the pet. Raises ValueError if it cannot be added."""
    if not item.can_accept:
        raise ValueError(f"'{item.title}' was declined and cannot be added.")
    minutes = duration_minutes if duration_minutes is not None else item.duration_minutes
    if minutes is None:
        raise ValueError(f"Enter how many minutes '{item.title}' takes.")
    frequency = Frequency.ONCE
    if item.cadence == "daily":
        frequency = Frequency.DAILY
    elif item.cadence == "weekly":
        frequency = Frequency.WEEKLY
    title = task_title(item)
    task = Task(title, int(minutes), Priority[item.priority], frequency)
    pet.add_task(task)
    return task
