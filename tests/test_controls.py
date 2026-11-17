"""Known-answer and adversarial tests of the system's own controls.

No model and no fake model are involved. Each test builds the proposals by hand and passes them
straight to the checking code (`prepare` and `review` in pipeline.py), so it shows what the checks
do with a good proposal and with a bad one. How well the real model behaves is measured only by
`evaluate.py`, which calls the real model.
"""

from datetime import date

import pytest

import compliance as cmp
from agent import Proposal
from pawpal_system import Owner, Pet
from pipeline import prepare, review

TODAY = date(2026, 11, 16)
ADULT_CAT, KITTEN, SENIOR_CAT = date(2021, 1, 1), date(2026, 8, 1), date(2014, 1, 1)
PUPPY, ADULT_DOG = date(2026, 6, 1), date(2020, 1, 1)

LITTER_Q = "Litterboxes should be cleaned at least once a day"
WATER_Q = "put down fresh water at least once a day"
WEIGHT_Q = "Regular assessment of weight and body condition score is important in cats of all ages"
KITTEN_FEED_Q = "Four or more meals a day for the kittens is normal"
SENIOR_VET_Q = "they should visit the veterinarian twice yearly"
PUPPY_WALK_Q = "Short, gentle walks taken daily"
ADULT_WALK_Q = "walks per day can make a huge difference"
TRAINING_Q = "Training your dog at home for five minutes per day"
WASH_Q = "Once a week, empty litter completely"
BOWLS_Q = "Clean these bowls daily with water"
KITTEN_TRAIN_Q = "Repeat training sessions every day"


def P(claim_id, title, freq, prio, minutes, quote):
    return Proposal(claim_id, title, freq, prio, minutes, quote)


def run(species, born, proposals, minutes=90, name="Mochi"):
    prep = prepare(Owner("Test", minutes), Pet(name, species, birth_date=born), today=TODAY)
    return review(prep, proposals) if prep.ready else prep.result


def statuses(r):
    return {i.claim_id: i.status for i in r.items}


def declined(r):
    return {i.claim_id for i in r.declined}


# ---- input and coverage: stopped before any model would be called ----

@pytest.mark.parametrize(
    "species,born,name,expected_text",
    [
        ("other", date(2020, 1, 1), "Mochi", "no care guidance"),
        ("cat", date(2027, 1, 1), "Mochi", "future"),
        ("cat", None, "Mochi", "Birth date"),
        ("cat", ADULT_CAT, "  ", "name"),
    ],
    ids=["species with no documents", "future birth date", "missing birth date", "blank pet name"],
)
def test_bad_input_is_declined_before_the_model(species, born, name, expected_text):
    prep = prepare(Owner("T", 90), Pet(name, species, birth_date=born), today=TODAY)
    assert not prep.ready and not prep.result.items
    assert expected_text in " ".join(prep.result.messages)


def test_medication_claims_are_never_offered_to_the_model_or_the_owner():
    for species, born in (("cat", ADULT_CAT), ("dog", PUPPY), ("dog", ADULT_DOG)):
        prep = prepare(Owner("T", 90), Pet("M", species, birth_date=born), today=TODAY)
        assert prep.ready and prep.result.notes
        assert not any(c.medication for c, _ in prep.candidates)
        assert not prep.result.items


def test_stage_decides_which_claims_the_model_may_use():
    kitten = {c.id for c, _ in prepare(Owner("T", 90), Pet("M", "cat", birth_date=KITTEN), today=TODAY).candidates}
    adult = {c.id for c, _ in prepare(Owner("T", 90), Pet("M", "cat", birth_date=ADULT_CAT), today=TODAY).candidates}
    assert "cat-feed-kitten" in kitten and "cat-feed-kitten" not in adult
    assert "cat-feed-adult" in adult and "cat-feed-adult" not in kitten
    puppy = {c.id for c, _ in prepare(Owner("T", 90), Pet("M", "dog", birth_date=PUPPY), today=TODAY).candidates}
    adult_dog = {c.id for c, _ in prepare(Owner("T", 90), Pet("M", "dog", birth_date=ADULT_DOG), today=TODAY).candidates}
    assert "dog-walk-puppy" in puppy and "dog-walk-puppy" not in adult_dog
    assert "dog-walk-adult" in adult_dog and "dog-walk-adult" not in puppy


# ---- good proposals pass ----

@pytest.mark.parametrize(
    "species,born,proposal",
    [
        ("cat", ADULT_CAT, P("cat-litter-daily", "Clean the litter box", "daily", "HIGH", 10, LITTER_Q)),
        ("cat", ADULT_CAT, P("cat-water-daily", "Refresh drinking water", "daily", "HIGH", 5, WATER_Q)),
        ("cat", ADULT_CAT, P("cat-litter-weekly-wash", "Wash the litter tray", "weekly", "MEDIUM", 15, WASH_Q)),
        ("cat", KITTEN, P("cat-feed-kitten", "Feed kitten meals", "daily", "HIGH", 20, KITTEN_FEED_Q)),
        ("cat", SENIOR_CAT, P("cat-vet-senior-twice-yearly", "Senior vet visit", "other", "HIGH", 30, SENIOR_VET_Q)),
        ("dog", PUPPY, P("dog-walk-puppy", "Short daily walk", "daily", "HIGH", 15, PUPPY_WALK_Q)),
        ("dog", ADULT_DOG, P("dog-walk-adult", "Daily walks", "daily", "MEDIUM", 30, ADULT_WALK_Q)),
    ],
    ids=lambda v: v.claim_id if isinstance(v, Proposal) else None,
)
def test_matching_proposal_passes(species, born, proposal):
    assert statuses(run(species, born, [proposal])).get(proposal.claim_id) == cmp.PASS


def test_weekly_cadence_is_kept():
    r = run("cat", ADULT_CAT, [P("cat-litter-weekly-wash", "Wash", "weekly", "MEDIUM", 15, WASH_Q)])
    assert r.items[0].cadence == "weekly"


# ---- bad proposals are caught ----

def test_wrong_frequency_is_declined():
    r = run("cat", ADULT_CAT, [P("cat-litter-daily", "Clean", "weekly", "HIGH", 10, LITTER_Q)])
    assert declined(r) == {"cat-litter-daily"} and not r.items


def test_wrong_priority_is_declined():
    r = run("cat", ADULT_CAT, [P("cat-litter-daily", "Clean", "daily", "LOW", 10, LITTER_Q)])
    assert declined(r) == {"cat-litter-daily"}


def test_source_with_no_frequency_is_declined():
    r = run("cat", ADULT_CAT, [P("cat-weight-check", "Check weight", "daily", "MEDIUM", 5, WEIGHT_Q)])
    assert declined(r) == {"cat-weight-check"}


def test_bowl_washing_with_wrong_frequency_is_declined():
    r = run("cat", ADULT_CAT, [P("cat-bowls-daily", "Wash bowls", "weekly", "MEDIUM", 5, BOWLS_Q)])
    assert declined(r) == {"cat-bowls-daily"}


def test_invented_claim_id_is_escalated():
    r = run("cat", ADULT_CAT, [P("cat-made-up", "Walk the cat", "daily", "HIGH", 30, "walk")])
    assert statuses(r) == {"cat-made-up": cmp.ESCALATE}


def test_claim_for_another_life_stage_is_escalated():
    r = run("cat", ADULT_CAT, [P("cat-feed-kitten", "Feed kitten", "daily", "HIGH", 20, KITTEN_FEED_Q)])
    assert statuses(r) == {"cat-feed-kitten": cmp.ESCALATE}
    r = run("cat", ADULT_CAT, [P("cat-kitten-training", "Train", "daily", "MEDIUM", 5, KITTEN_TRAIN_Q)])
    assert statuses(r) == {"cat-kitten-training": cmp.ESCALATE}
    r = run("dog", ADULT_DOG, [P("dog-feed-puppy", "Feed puppy", "daily", "HIGH", 20, "3-4 small meals per day")])
    assert statuses(r) == {"dog-feed-puppy": cmp.ESCALATE}


def test_fabricated_quote_is_escalated():
    r = run("cat", ADULT_CAT, [P("cat-litter-daily", "Clean", "daily", "HIGH", 10, "Clean the litter box every hour")])
    assert statuses(r) == {"cat-litter-daily": cmp.ESCALATE}


def test_duration_over_the_owners_time_is_escalated():
    r = run("cat", ADULT_CAT, [P("cat-litter-daily", "Clean", "daily", "HIGH", 120, LITTER_Q)], minutes=60)
    assert statuses(r) == {"cat-litter-daily": cmp.ESCALATE}


def test_non_numeric_duration_is_escalated():
    r = run("cat", ADULT_CAT, [P("cat-litter-daily", "Clean", "daily", "HIGH", "a while", LITTER_Q)])
    assert statuses(r) == {"cat-litter-daily": cmp.ESCALATE}


def test_medication_wording_is_removed_not_shown():
    r = run("cat", ADULT_CAT, [P("cat-litter-daily", "Give flea treatment 5 mg", "daily", "HIGH", 5, LITTER_Q)])
    assert not r.items and not r.declined
    assert [i.claim_id for i in r.redirected] == ["cat-litter-daily"] and r.notes


def test_duplicate_proposals_are_ignored():
    r = run("cat", ADULT_CAT, [
        P("cat-litter-daily", "Clean the litter box", "daily", "HIGH", 10, LITTER_Q),
        P("cat-litter-daily", "Clean litter again", "daily", "HIGH", 10, LITTER_Q),
    ])
    assert [i.claim_id for i in r.items] == ["cat-litter-daily"]


# ---- durations stated by a source ----

def test_a_source_duration_replaces_the_models_estimate():
    r = run("dog", ADULT_DOG, [P("dog-walk-adult", "Daily walks", "daily", "MEDIUM", 10, ADULT_WALK_Q)])
    item = r.items[0]
    assert item.duration_minutes == 30 and item.duration_from_source


def test_a_source_duration_longer_than_the_owners_time_is_escalated():
    r = run("dog", ADULT_DOG, [P("dog-walk-adult", "Daily walks", "daily", "MEDIUM", 10, ADULT_WALK_Q)], minutes=20)
    assert statuses(r) == {"dog-walk-adult": cmp.ESCALATE}


def test_training_uses_the_sources_five_minutes():
    r = run("dog", ADULT_DOG, [P("dog-training-daily", "Training", "daily", "MEDIUM", 20, TRAINING_Q)])
    assert r.items[0].duration_minutes == 5


def test_kitten_training_uses_the_sources_fifteen_minutes():
    r = run("cat", KITTEN, [P("cat-kitten-training", "Train", "daily", "MEDIUM", 5, KITTEN_TRAIN_Q)])
    assert r.items[0].duration_minutes == 15 and r.items[0].duration_from_source


# ---- tasks the model proposes from its own knowledge (no source) ----

def G(title, freq="daily", prio="MEDIUM", minutes=10):
    return Proposal("general", title, freq, prio, minutes, "")


def test_a_general_task_is_shown_apart_and_can_never_pass():
    r = run("cat", ADULT_CAT, [G("Rotate toys for variety")])
    assert [i.status for i in r.unsourced] == [cmp.UNSOURCED]
    assert r.items == [] and r.declined == []
    assert "not from your documents" in " ".join(r.unsourced[0].reasons)


def test_a_general_task_about_medication_is_removed():
    r = run("cat", ADULT_CAT, [G("Give a flea treatment monthly", "weekly")])
    assert r.unsourced == [] and len(r.redirected) == 1


def test_a_general_task_cannot_be_high_priority():
    r = run("cat", ADULT_CAT, [G("Check the heart rate", prio="HIGH")])
    assert r.unsourced == [] and len(r.declined) == 1


def test_a_general_task_must_be_daily_or_weekly():
    r = run("cat", ADULT_CAT, [G("Deep clean the cat tree", freq="other")])
    assert r.unsourced == [] and len(r.declined) == 1


def test_a_general_task_longer_than_the_owners_time_is_declined():
    r = run("cat", ADULT_CAT, [G("Long grooming session", minutes=120)], minutes=60)
    assert r.unsourced == [] and len(r.declined) == 1


def test_no_more_than_three_general_tasks_and_no_repeats():
    r = run("cat", ADULT_CAT, [G("Toy rotation"), G("toy rotation"), G("Window perch time"),
                                G("Scratching post check"), G("Gentle brushing")])
    assert [i.title for i in r.unsourced] == ["Toy rotation", "Window perch time", "Scratching post check"]


def test_general_tasks_have_unique_ids_and_a_label_on_the_pet():
    from pipeline import accept_item, task_title
    r = run("cat", ADULT_CAT, [G("Toy rotation"), G("Window perch time")])
    assert len({i.claim_id for i in r.unsourced}) == 2
    pet = Pet("Mochi", "cat", birth_date=ADULT_CAT)
    task = accept_item(pet, r.unsourced[0])
    assert task.title.endswith("[AI suggestion, no source]") and task.title == task_title(r.unsourced[0])


def test_sourced_and_general_tasks_are_kept_separate():
    r = run("cat", ADULT_CAT, [P("cat-litter-daily", "Clean the litter box", "daily", "HIGH", 10, LITTER_Q), G("Toy rotation")])
    assert statuses(r) == {"cat-litter-daily": cmp.PASS}
    assert len(r.unsourced) == 1
