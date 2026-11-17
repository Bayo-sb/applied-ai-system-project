"""Input checks and the medication detector.

Medication content is never decided by the system: anything that mentions it goes to a human.
The detector is a keyword list, so it misses synonyms and unusual wording. That limit is
deliberate to state: it is a first filter, and the knowledge base also marks medication claims by hand.
"""

from __future__ import annotations

import re
from datetime import date

SUPPORTED_SPECIES = ("dog", "cat", "other")
MAX_NAME_LENGTH = 40

_MEDICATION_PATTERN = re.compile(
    r"\b(medic\w*|drug\w*|dos(?:e|es|age|ing)|prescri\w*|tablets?|pills?|capsules?|injections?|"
    r"antibiotic\w*|steroid\w*|painkiller\w*|vaccin\w*|deworm\w*|worm(?:ing|s|ers?)?|"
    r"flea (?:treatment|control|collar)s?|insecticide\w*|prophylaxis|heartworm|"
    r"\d+\s?(?:mg|ml|mcg|iu)|treatment)\b",
    re.IGNORECASE,
)


def mentions_medication(text: str) -> bool:
    """True if the text appears to be about medication, dosage or a treatment."""
    return bool(_MEDICATION_PATTERN.search(text or ""))


def validate_pet_input(name: str, species: str, birth_date: date | None, today: date) -> list[str]:
    """Return a list of problems with a new pet's details (empty if all is well)."""
    problems = []
    if not name or not name.strip():
        problems.append("Pet name is required.")
    elif len(name.strip()) > MAX_NAME_LENGTH:
        problems.append(f"Pet name must be at most {MAX_NAME_LENGTH} characters.")
    if species not in SUPPORTED_SPECIES:
        problems.append(f"Species must be one of {', '.join(SUPPORTED_SPECIES)}.")
    if birth_date is None:
        problems.append("Birth date is required (an approximate date is fine).")
    elif birth_date > today:
        problems.append("Birth date cannot be in the future.")
    return problems
