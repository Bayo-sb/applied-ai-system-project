"""The plan verifier: checks the finished plan after the scheduler has run."""

from __future__ import annotations

from pawpal_system import Owner, Plan, Priority


def verify_plan(plan: Plan, owner: Owner) -> list[str]:
    """Return problems found in the plan (empty list means it checks out)."""
    problems = []
    if plan.total_minutes > owner.available_minutes_per_day:
        problems.append(
            f"The plan uses {plan.total_minutes} minutes, over the owner's {owner.available_minutes_per_day}."
        )
    for item in plan.skipped:
        if item.task.priority == Priority.HIGH:
            problems.append(f"HIGH priority task skipped: '{item.task.title}' for {item.pet_name}. {item.reason}")
    summed = sum(p.task.duration_minutes for p in plan.scheduled)
    if summed != plan.total_minutes:
        problems.append(f"Scheduled tasks add up to {summed} minutes but the plan reports {plan.total_minutes}.")
    return problems
