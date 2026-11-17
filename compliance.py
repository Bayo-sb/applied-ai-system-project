"""The compliance check: is each proposed task supported by what was retrieved?

Statuses, most severe first:
  MEDICATION  mentions medication or dosage. Always goes to a human. Never decided here.
  DECLINE     its frequency or priority is not supported by the cited claim. Not shown for approval.
  ESCALATE    some other check failed. Shown to the owner with the reasons; the owner decides.
  UNSOURCED   the model proposed it from its own knowledge. It can never PASS: it is shown in its own
              section, labelled, unticked, and the owner decides. See check_general.
  PASS        every check passed.

The duration is the agent's estimate unless the source states one. When the claim has a source
duration it is used instead (the pipeline overrides the agent's number), and only its fit within
the owner's daily time is checked. An estimate must be a positive whole number of minutes that fits.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent import MAX_TASK_MINUTES, Proposal
from guardrails import mentions_medication
from knowledge_base import normalize

PASS, ESCALATE, DECLINE, MEDICATION = "PASS", "ESCALATE", "DECLINE", "MEDICATION"
UNSOURCED = "UNSOURCED"
_SEVERITY = {PASS: 0, UNSOURCED: 1, ESCALATE: 2, DECLINE: 3, MEDICATION: 4}
GENERAL_PRIORITIES = ("MEDIUM", "LOW")  # the model's own knowledge may never claim HIGH (health) priority
GENERAL_FREQUENCIES = ("daily", "weekly")
GENERAL_REASON = "From the AI's general knowledge, not from your documents. Nothing here was checked against a source."


@dataclass
class ComplianceResult:
    status: str = PASS
    reasons: list[str] = field(default_factory=list)

    def add(self, status: str, reason: str) -> None:
        self.reasons.append(reason)
        if _SEVERITY[status] > _SEVERITY[self.status]:
            self.status = status


def check_proposal(
    proposal: Proposal, claims: dict, passages: dict, species: str, stage: str, owner_minutes: int
) -> ComplianceResult:
    """claims and passages are dicts keyed by id, containing only what was retrieved."""
    result = ComplianceResult()
    claim = claims.get(proposal.claim_id)
    if claim is None:
        result.add(ESCALATE, f"It cites '{proposal.claim_id}', which was not among the retrieved passages.")
        if mentions_medication(f"{proposal.title} {proposal.quote}"):
            result.add(MEDICATION, "It mentions medication or dosage.")
        return result
    passage = passages[claim.passage_id]

    if claim.medication or mentions_medication(f"{proposal.title} {proposal.quote}"):
        result.add(MEDICATION, "It involves medication, vaccination or treatment. Ask your veterinarian.")

    if not passage.applies_to(species, stage):
        result.add(ESCALATE, f"The cited passage does not apply to a {stage} {species}.")

    if not proposal.quote or normalize(proposal.quote) not in normalize(passage.text):
        result.add(ESCALATE, "The quote is not found in the cited passage.")

    # Frequency: must match what the source states.
    if claim.cadence == "none":
        result.add(DECLINE, "The source gives no frequency for this task.")
    elif proposal.frequency != claim.cadence:
        result.add(DECLINE, f"The frequency '{proposal.frequency}' does not match the source ('{claim.cadence_text}').")

    # Priority: must match what the source's importance wording gives.
    if proposal.priority != claim.priority:
        result.add(DECLINE, f"The priority {proposal.priority} does not match the source's wording ({claim.importance}, which gives {claim.priority}).")

    # Duration: the source's value if it states one, otherwise the agent's estimate.
    d = claim.duration_minutes if claim.duration_minutes is not None else proposal.duration_minutes
    if isinstance(d, bool) or not isinstance(d, int) or d < 1 or d > MAX_TASK_MINUTES:
        result.add(ESCALATE, f"The duration {d!r} is not a whole number of minutes between 1 and {MAX_TASK_MINUTES}.")
    elif d > owner_minutes:
        result.add(ESCALATE, f"The duration ({d} min) is more than the owner's {owner_minutes} minutes per day.")
    return result


def check_general(proposal: Proposal, owner_minutes: int) -> ComplianceResult:
    """Check a task the model proposed from its own knowledge.

    It has no source, so the frequency, priority and duration cannot be verified and it can never
    PASS. The best it can get is UNSOURCED: shown to the owner, clearly labelled, who decides. The
    rules that still apply are the ones that need no source: no medication, never HIGH priority,
    only daily or weekly, and a sensible duration that fits the owner's time.
    """
    result = ComplianceResult(UNSOURCED, [GENERAL_REASON])
    if mentions_medication(f"{proposal.title} {proposal.quote}"):
        result.add(MEDICATION, "It involves medication, vaccination or treatment. Ask your veterinarian.")
    if proposal.priority not in GENERAL_PRIORITIES:
        result.add(DECLINE, f"A task without a source cannot be {proposal.priority} priority.")
    if proposal.frequency not in GENERAL_FREQUENCIES:
        result.add(DECLINE, f"A task without a source must be daily or weekly, not '{proposal.frequency}'.")
    d = proposal.duration_minutes
    if isinstance(d, bool) or not isinstance(d, int) or d < 1 or d > MAX_TASK_MINUTES:
        result.add(DECLINE, f"The duration {d!r} is not a whole number of minutes between 1 and {MAX_TASK_MINUTES}.")
    elif d > owner_minutes:
        result.add(DECLINE, f"The duration ({d} min) is more than the owner's {owner_minutes} minutes per day.")
    return result
