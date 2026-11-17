"""The LLM agent: turns retrieved care claims into proposed tasks for one pet.

The agent only chooses from the claims it is given. It sets the task title, the duration
(within the owner's time) and repeats the frequency, priority and a quote from the source. It does
not decide whether its proposal is allowed. The compliance check does that.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from llm_client import LLM, LLMError, LLMResponse

MAX_TASK_MINUTES = 240  # the same upper limit the app's duration field uses
GENERAL_ID = "general"  # reserved claim_id: a task the model proposes from its own knowledge, with no source
MAX_GENERAL_TASKS = 3

SYSTEM_PROMPT = """You help plan routine care for a pet. You are given a pet and a list of CANDIDATE
CARE ITEMS taken from veterinary and care documents. Propose tasks for this pet using ONLY those items.

Rules:
- Every task must use one candidate item. Put its id in "claim_id".
- "frequency" must be the candidate's own cadence: daily, weekly, other or none. Never invent one.
- "priority" must be HIGH, MEDIUM or LOW, following the candidate's importance
  (essential = HIGH, recommended = MEDIUM, optional = LOW).
- "duration_minutes": if a candidate states "duration", use exactly that number. Otherwise give your
  own estimate of how long one session takes (it is not from the documents). Keep estimates
  realistic and keep the total of all tasks within the owner's minutes per day.
- "quote" must be a short exact phrase copied from the candidate's source text.
- Never name a medicine, product or dose.
- Reply with ONLY a JSON array, no other text. Each element:
  {"claim_id": str, "title": str, "frequency": str, "priority": str,
   "duration_minutes": int, "quote": str}
- If no candidate fits, reply with [].

You may ALSO add up to 3 extra tasks from your own general knowledge of caring for this kind of
pet at this life stage, for routine care the candidates do not cover (for example enrichment,
grooming or training that suits the breed type or age). These are NOT from the documents and the
owner will see them labelled as such. For each one:
- use "claim_id": "general" and "quote": ""
- "frequency" must be daily or weekly
- "priority" must be MEDIUM or LOW (never HIGH)
- never include anything about medicine, vaccination, parasites, treatment, diagnosis or a dose
- do not repeat a task that a candidate item already covers"""


class AgentOutputError(LLMError):
    """The model's reply was not the JSON the pipeline expects."""


@dataclass(frozen=True)
class Proposal:
    claim_id: str
    title: str
    frequency: str
    priority: str
    duration_minutes: object  # int if the model followed the rules; checked by the compliance step
    quote: str

    @property
    def is_general(self) -> bool:
        """True for a task the model proposed from its own knowledge, with no source."""
        return self.claim_id == GENERAL_ID


def build_user_prompt(pet_name: str, species: str, stage: str, owner_minutes: int, candidates) -> str:
    """candidates: list of (Claim, Passage) pairs."""
    lines = [
        f"Pet: {pet_name}, a {species}, life stage: {stage}.",
        f"The owner has {owner_minutes} minutes per day for all care.",
        "",
        "CANDIDATE CARE ITEMS:",
    ]
    for claim, passage in candidates:
        lines += [
            f"- id: {claim.id}",
            f"  item: {claim.task}",
            f"  cadence: {claim.cadence}" + (f" ({claim.cadence_text})" if claim.cadence_text else ""),
            f"  importance: {claim.importance}",
            *([f"  duration: {claim.duration_minutes} minutes ({claim.duration_text})"] if claim.duration_minutes else []),
            f"  source text: {passage.text}",
        ]
    return "\n".join(lines)


def parse_proposals(text: str) -> list[Proposal]:
    """Parse the model's reply. Raises AgentOutputError if it is not the expected JSON array."""
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AgentOutputError(f"The reply was not valid JSON ({exc.msg}).") from None
    if not isinstance(data, list):
        raise AgentOutputError("The reply was JSON but not a list of tasks.")
    proposals = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise AgentOutputError(f"Item {i} is not an object.")
        try:
            proposals.append(
                Proposal(
                    claim_id=str(item["claim_id"]),
                    title=str(item["title"]),
                    frequency=str(item["frequency"]).lower(),
                    priority=str(item["priority"]).upper(),
                    duration_minutes=item["duration_minutes"],
                    quote=str(item.get("quote", "")),
                )
            )
        except KeyError as missing:
            raise AgentOutputError(f"Item {i} is missing {missing}.") from None
    return proposals


def propose_tasks(
    llm: LLM, pet_name: str, species: str, stage: str, owner_minutes: int, candidates
) -> tuple[list[Proposal], LLMResponse]:
    """Ask the model for proposals. Raises LLMError or AgentOutputError on failure."""
    response = llm.complete(
        SYSTEM_PROMPT, build_user_prompt(pet_name, species, stage, owner_minutes, candidates)
    )
    return parse_proposals(response.text), response
