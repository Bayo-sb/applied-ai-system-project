"""End-to-end demonstration of PawPal+ with the REAL model, printed step by step.

Run:   python demo.py              (one paid request: Mochi, an adult cat)
       python demo.py --pet Biscuit   (Biscuit, a puppy; or Pip, Junior, Old Tom, Rex)

Shows, in order: guardrails, life stage, retrieval (passages and scores), the model's
proposals checked by the compliance check, owner approval, the scheduler's plan, the plan verifier,
and the trace log. Then two guardrail cases that need no model call.

Approval: a person normally ticks each task in the app. Here every task that PASSED is approved
automatically and anything that failed a check is left out, so the output is repeatable.
"""

from __future__ import annotations

import argparse
from datetime import date

import compliance as cmp
from agent import Proposal
from evaluate import PROFILES, TODAY
from guardrails import mentions_medication
from knowledge_base import load_knowledge_base
from llm_client import AnthropicLLM
from pawpal_system import Owner, Pet, Scheduler
from pipeline import accept_item, prepare, review, suggest_tasks
from retriever import retrieve_topics
from verifier import verify_plan

MINUTES = 90


def heading(text: str) -> None:
    print(f"\n=== {text} ===")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pet", default="Mochi", help="Mochi, Pip, Junior, Old Tom, Biscuit or Rex")
    args = parser.parse_args()
    profile = next((p for p in PROFILES if p[0].lower() == args.pet.lower()), None)
    if profile is None:
        parser.error("choose one of: " + ", ".join(p[0] for p in PROFILES))
    name, species, born, _ = profile

    kb = load_knowledge_base()
    owner = Owner("Demo owner", MINUTES)
    pet = Pet(name, species, birth_date=born)
    owner.add_pet(pet)

    heading(f"CASE 1: end-to-end run for {name} ({species}, born {born}), owner has {MINUTES} min/day")

    # Steps before the model
    prep = prepare(owner, pet, today=TODAY, kb=kb)
    print(f"Guardrails passed. Life stage: {prep.stage}")
    heading("RETRIEVAL (species and life-stage filter, then TF-IDF per care topic)")
    found = retrieve_topics(kb, species, prep.stage, top_k=20)
    print(f"{len(found.hits)} passages cleared the cut-off; best score {found.best_score:.2f}")
    for hit in found.hits[:6]:
        print(f"  {hit.score:.2f}  {hit.passage.citation}")
    if len(found.hits) > 6:
        print(f"  ... and {len(found.hits) - 6} more")

    # The model and the compliance check
    heading("AGENT (live model) AND COMPLIANCE CHECK")
    llm = AnthropicLLM()
    result = suggest_tasks(owner, pet, llm, today=TODAY, kb=kb)
    for item in result.items + result.unsourced + result.declined:
        minutes = f"{item.duration_minutes} min" + (" (from source)" if item.duration_from_source else " (estimate)")
        print(f"[{item.status}] {item.title} | {item.priority} | {item.cadence_text or 'no frequency'} | {minutes}")
        print(f"    source: {item.citation}")
        for reason in item.reasons:
            print(f"    check: {reason}")
    for item in result.redirected:
        print(f"[REMOVED, medication] {item.title}")
    for note in result.notes:
        print(f"NOTE: {note}")

    # Human approval (automatic here: PASS only), then the existing scheduler
    heading("HUMAN APPROVAL (PASS items approved automatically in this demo)")
    approved = [i for i in result.items if i.status == cmp.PASS]
    for item in approved:
        accept_item(pet, item)
    print(f"{len(approved)} of {len(result.items) + len(result.unsourced) + len(result.declined)} proposals added to {name}'s task list")
    if result.unsourced:
        print(f"{len(result.unsourced)} UNSOURCED task(s) from the model's own knowledge were NOT added: they are never approved automatically")

    heading("SCHEDULER AND PLAN VERIFIER")
    plan = Scheduler(owner, day_start="08:00", plan_date=TODAY).generate_plan()
    for planned in plan.scheduled:
        print(f"  {planned.start_time}  {planned.task.title} ({planned.task.duration_minutes} min)")
    for skipped in plan.skipped:
        print(f"  skipped: {skipped.task.title} - {skipped.reason}")
    print(f"Total {plan.total_minutes} of {MINUTES} minutes")
    problems = verify_plan(plan, owner)
    print("Verifier: " + ("plan checks out" if not problems else "; ".join(problems)))

    heading("TRACE LOG")
    for step in result.trace:
        print(f"  {step['step']:<11} {step['detail']}")

    # Guardrail cases that do not call the model
    heading("CASE 2: guardrail, a medication request (no model call)")
    request = "What dose of flea treatment should I give Mochi?"
    print(f'Request: "{request}"')
    print("Detected as medication:", mentions_medication(request))
    print("Result: not suggested. Ask your veterinarian.")

    heading("CASE 3: compliance check on a fabricated quote (hand-written proposal, no model call)")
    cat = Pet("Mochi", "cat", birth_date=date(TODAY.year - 5, 1, 1))
    prep2 = prepare(Owner("Demo owner", MINUTES), cat, today=TODAY, kb=kb)
    fake = Proposal("cat-litter-daily", "Clean the litter box", "daily", "HIGH", 10, "Clean the litter box every hour")
    for item in review(prep2, [fake]).items:
        print(f"[{item.status}] {item.title}")
        for reason in item.reasons:
            print(f"    check: {reason}")
    print("Result: shown to the owner with the reason; the owner decides.")


if __name__ == "__main__":
    main()
