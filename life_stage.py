"""Works out a pet's life stage from its birth date, using a source's definitions.

Cats use the AAFP-AAHA Feline Life Stage Guidelines (Table 1). Dogs use the Puppy Care Guide, which
only separates puppy from adult. For any other
species `life_stage` returns None, and the pipeline declines with a reason instead of guessing.

The source prints ranges such as "7 m-2 y" and "3-6 y" and leaves gaps between them. This module
counts completed months and treats each printed range as including the whole of its last month or
year (so "2 y" runs to just before the third birthday). That reading is an assumption of this
system, not the source's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# (stage, first month inclusive, last month exclusive). None = no upper limit.
CAT_STAGES = [
    ("kitten", 0, 7),  # 0-6 m
    ("junior", 7, 36),  # 7 m-2 y
    ("adult", 36, 84),  # 3-6 y
    ("mature", 84, 132),  # 7-10 y
    ("senior", 132, 180),  # 11-14 y
    ("geriatric", 180, None),  # 15+ y
]
# Puppy Care Guide (Greencross Vets / Petbarn): dogs are "classified as adults" from about 12
# months. The guide says giant breeds can take up to 24 months. This system has no size field.
DOG_STAGES = [
    ("puppy", 0, 12),
    ("adult", 12, None),
]
STAGE_SOURCES = {"cat": CAT_STAGES, "dog": DOG_STAGES}


def age_in_months(birth_date: date, today: date) -> int:
    """Completed months between birth_date and today. Raises ValueError for a future date."""
    if birth_date > today:
        raise ValueError("Birth date is in the future.")
    months = (today.year - birth_date.year) * 12 + (today.month - birth_date.month)
    if today.day < birth_date.day:
        months -= 1
    return months


def life_stage(species: str, birth_date: date | None, today: date) -> str | None:
    """Return the stage name, or None if the species has no stage source or no birth date."""
    stages = STAGE_SOURCES.get(species)
    if stages is None or birth_date is None:
        return None
    months = age_in_months(birth_date, today)
    for name, start, end in stages:
        if months >= start and (end is None or months < end):
            return name
    return None


@dataclass(frozen=True)
class StageChange:
    pet_name: str
    previous: str | None
    current: str


def stage_changes(pets, last_seen: dict, today: date) -> list[StageChange]:
    """Pets whose current stage differs from the stage recorded at the last visit.

    A pet with no recorded stage is new, not changed, so it is not reported.
    """
    changes = []
    for pet in pets:
        current = life_stage(pet.species, getattr(pet, "birth_date", None), today)
        previous = last_seen.get(pet.label)
        if current is not None and previous is not None and previous != current:
            changes.append(StageChange(pet.label, previous, current))
    return changes
