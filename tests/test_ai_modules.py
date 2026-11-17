"""Unit tests for the knowledge base, life stages, retriever, guardrails, agent, compliance,
verifier and storage. No network and no API key are used."""

import json
from datetime import date

import pytest

import compliance as cmp
from agent import AgentOutputError, Proposal, parse_proposals
from guardrails import mentions_medication, validate_pet_input
from knowledge_base import KnowledgeBaseError, load_document, load_knowledge_base, KnowledgeBase
from life_stage import age_in_months, life_stage, stage_changes
from pawpal_system import Frequency, Owner, Pet, Plan, PlannedTask, Priority, Scheduler, SkippedTask, Task
from pipeline import OVERRIDE_SUFFIX, ReviewItem, accept_item
from retriever import CONFIDENCE_THRESHOLD, retrieve, retrieve_topics
import storage
from verifier import verify_plan

TODAY = date(2026, 11, 16)


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


# ---- knowledge base ----

def test_every_claim_quote_is_in_its_passage(kb):
    assert len(kb.claims) >= 10  # loading would have raised if a quote were missing


def test_claim_with_missing_quote_is_rejected(tmp_path):
    doc = tmp_path / "bad.md"
    doc.write_text(
        "# Bad\n\nSpecies: cat\nStages: all\n\n## Source\n\n- Title: x\n- Author: y\n\n"
        "## Section\n\nSome text here.\n\n```claim\nid: c1\ntask: t\ncadence: daily\ncadence_text: daily\n"
        "cadence_quote: not in the text\nimportance: essential\nimportance_quote: Some text\nmedication: no\n```\n"
    )
    with pytest.raises(KnowledgeBaseError, match="cadence_quote"):
        load_document(doc, KnowledgeBase())


def test_drafts_folder_is_not_loaded(kb):
    assert not any("drafts" in pid for pid in kb.passages)


# ---- life stage ----

@pytest.mark.parametrize(
    "birth,expected",
    [
        (date(2026, 8, 1), "kitten"),
        (date(2026, 4, 16), "junior"),  # 7 months
        (date(2024, 12, 1), "junior"),  # 1 y 11 m
        (date(2024, 5, 16), "junior"),  # 2 y 6 m: the gap the source leaves
        (date(2023, 11, 16), "adult"),  # exactly 3 y
        (date(2019, 11, 17), "adult"),  # 6 y 11 m
        (date(2019, 11, 16), "mature"),  # exactly 7 y
        (date(2015, 11, 16), "senior"),  # exactly 11 y
        (date(2011, 11, 16), "geriatric"),  # exactly 15 y
    ],
)
def test_cat_stage_boundaries(birth, expected):
    assert life_stage("cat", birth, TODAY) == expected


def test_stage_is_none_for_species_without_a_source():
    assert life_stage("other", date(2020, 1, 1), TODAY) is None
    assert life_stage("cat", None, TODAY) is None


@pytest.mark.parametrize(
    "birth,expected",
    [(date(2026, 6, 1), "puppy"), (date(2025, 11, 17), "puppy"), (date(2025, 11, 16), "adult"), (date(2015, 1, 1), "adult")],
)
def test_dog_stages(birth, expected):
    assert life_stage("dog", birth, TODAY) == expected


def test_future_birth_date_raises():
    with pytest.raises(ValueError):
        age_in_months(date(2027, 1, 1), TODAY)


def test_stage_change_is_reported_only_when_it_differs():
    pet = Pet("Mochi", "cat", birth_date=date(2015, 11, 16))  # senior today
    assert stage_changes([pet], {"Mochi (cat)": "mature"}, TODAY)[0].current == "senior"
    assert stage_changes([pet], {"Mochi (cat)": "senior"}, TODAY) == []
    assert stage_changes([pet], {}, TODAY) == []  # new pet: not a change


# ---- retriever ----

def test_retriever_filters_by_species_and_stage(kb):
    kitten = retrieve(kb, "cat", "kitten", "feeding meals per day")
    adult = retrieve(kb, "cat", "adult", "feeding meals per day")
    assert "Feeding kittens" in [h.passage.heading for h in kitten.hits]
    assert "Feeding kittens" not in [h.passage.heading for h in adult.hits]
    assert retrieve(kb, "horse", "adult", "feeding").hits == []


def test_unrelated_query_is_not_confident(kb):
    assert not retrieve(kb, "cat", "adult", "training a parrot to talk").confident


def test_topic_retrieval_is_confident_for_cats_and_dogs(kb):
    assert retrieve_topics(kb, "cat", "adult", top_k=20).confident
    assert retrieve_topics(kb, "dog", "puppy", top_k=20).confident
    assert retrieve_topics(kb, "dog", "adult", top_k=20).confident
    assert CONFIDENCE_THRESHOLD == 0.225


def test_dog_puppy_passages_are_not_given_to_adult_dogs(kb):
    headings = [h.passage.heading for h in retrieve_topics(kb, "dog", "adult", top_k=20).hits]
    assert "Feeding puppies" not in headings and "Daily walks" in headings


# ---- guardrails ----

@pytest.mark.parametrize("text", ["give 5 mg twice a day", "flea treatment", "a vaccine", "worming tablets", "what dose?"])
def test_medication_is_detected(text):
    assert mentions_medication(text)


@pytest.mark.parametrize("text", ["Clean the litter box", "Refresh drinking water", "Veterinary wellness exam", "Feed meals"])
def test_ordinary_tasks_are_not_medication(text):
    assert not mentions_medication(text)


def test_input_validation():
    assert validate_pet_input("Mochi", "cat", date(2020, 1, 1), TODAY) == []
    assert len(validate_pet_input("", "lizard", None, TODAY)) == 3
    assert validate_pet_input("Mochi", "cat", date(2030, 1, 1), TODAY)


# ---- agent output parsing ----

GOOD = {"claim_id": "c", "title": "t", "frequency": "Daily", "priority": "high", "duration_minutes": 5, "quote": "q"}


def test_parse_accepts_plain_and_fenced_json():
    assert parse_proposals(json.dumps([GOOD]))[0].priority == "HIGH"
    assert parse_proposals("```json\n" + json.dumps([GOOD]) + "\n```")[0].frequency == "daily"
    assert parse_proposals("[]") == []


@pytest.mark.parametrize("bad", ["nope", "{}", "[1]", json.dumps([{"claim_id": "c"}])])
def test_parse_rejects_bad_replies(bad):
    with pytest.raises(AgentOutputError):
        parse_proposals(bad)


# ---- compliance ----

def _check(kb, claim_id, **changes):
    claim = kb.claims[claim_id]
    passage = kb.passages[claim.passage_id]
    base = dict(claim_id=claim_id, title=claim.task, frequency=claim.cadence, priority=claim.priority,
                duration_minutes=10, quote=claim.cadence_quote or claim.importance_quote)
    base.update(changes)
    return cmp.check_proposal(Proposal(**base), kb.claims, kb.passages, passage.species, "adult", 90)


def test_matching_proposal_passes(kb):
    assert _check(kb, "cat-litter-daily").status == cmp.PASS


def test_each_failure_has_the_expected_severity(kb):
    assert _check(kb, "cat-litter-daily", frequency="weekly").status == cmp.DECLINE
    assert _check(kb, "cat-litter-daily", priority="LOW").status == cmp.DECLINE
    assert _check(kb, "cat-litter-daily", quote="made up").status == cmp.ESCALATE
    assert _check(kb, "cat-litter-daily", duration_minutes=500).status == cmp.ESCALATE
    assert _check(kb, "cat-litter-daily", duration_minutes=True).status == cmp.ESCALATE
    assert _check(kb, "cat-parasite-control").status == cmp.MEDICATION


def test_medication_outranks_a_decline(kb):
    r = _check(kb, "cat-litter-daily", title="Give dose", frequency="weekly")
    assert r.status == cmp.MEDICATION and len(r.reasons) >= 2


# ---- accepting items ----

def _item(**kw):
    base = dict(claim_id="c", title="Clean the litter box", priority="HIGH", cadence="daily",
                cadence_text="at least once a day", duration_minutes=10, status=cmp.PASS)
    base.update(kw)
    return ReviewItem(**base)


def test_accept_maps_cadence_priority_and_override():
    pet = Pet("Mochi", "cat")
    t = accept_item(pet, _item())
    assert (t.frequency, t.priority, t.duration_minutes) == (Frequency.DAILY, Priority.HIGH, 10)
    t2 = accept_item(pet, _item(title="Vet exam", cadence="other", cadence_text="once a year", status=cmp.ESCALATE))
    assert t2.frequency == Frequency.ONCE
    assert t2.title == "Vet exam (once a year)" + OVERRIDE_SUFFIX


def test_declined_and_durationless_items_cannot_be_added():
    pet = Pet("Mochi", "cat")
    with pytest.raises(ValueError):
        accept_item(pet, _item(status=cmp.DECLINE))
    with pytest.raises(ValueError):
        accept_item(pet, _item(duration_minutes=None, status=cmp.MEDICATION))
    assert accept_item(pet, _item(duration_minutes=None, status=cmp.MEDICATION), duration_minutes=15).duration_minutes == 15


# ---- verifier ----

def test_verifier_flags_over_budget_and_skipped_high():
    owner = Owner("O", 30)
    high = Task("Feed", 20, Priority.HIGH)
    plan = Plan(scheduled=[PlannedTask(high, "08:00", "")], skipped=[SkippedTask(Task("Vet", 60, Priority.HIGH), "no time")], total_minutes=20)
    problems = verify_plan(plan, owner)
    assert len(problems) == 1 and "HIGH priority task skipped" in problems[0]
    plan.total_minutes = 50
    assert any("over the owner's" in p for p in verify_plan(plan, owner))


def test_verifier_passes_a_real_plan():
    owner = Owner("O", 60)
    pet = Pet("Mochi", "cat")
    pet.add_task(Task("Feed", 20, Priority.HIGH, Frequency.DAILY))
    owner.add_pet(pet)
    assert verify_plan(Scheduler(owner).generate_plan(), owner) == []


# ---- storage ----

def test_save_and_load_round_trip(tmp_path):
    owner = Owner("Jordan", 75, {"a": 1})
    pet = Pet("Mochi", "cat", birth_date=date(2020, 1, 15))
    pet.add_task(Task("Feed", 20, Priority.HIGH, Frequency.DAILY, scheduled_time="8:30", due_date=date(2026, 11, 20)))
    owner.add_pet(pet)
    path = tmp_path / "d" / "pawpal.json"
    storage.save(owner, {"Mochi": "adult"}, path)
    loaded, seen = storage.load(path)
    assert loaded.name == "Jordan" and loaded.available_minutes_per_day == 75
    p = loaded.get_pet("Mochi")
    assert p.birth_date == date(2020, 1, 15) and seen == {"Mochi": "adult"}
    t = p.tasks[0]
    assert (t.title, t.priority, t.frequency, t.scheduled_time, t.due_date) == ("Feed", Priority.HIGH, Frequency.DAILY, "08:30", date(2026, 11, 20))


def test_load_returns_none_for_missing_or_corrupt_file(tmp_path):
    assert storage.load(tmp_path / "nope.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert storage.load(bad) is None


def test_source_duration_is_validated_and_loaded(kb, tmp_path):
    assert kb.claims["dog-walk-adult"].duration_minutes == 30
    doc = tmp_path / "bad.md"
    doc.write_text(
        "# Bad\n\nSpecies: dog\nStages: all\n\n## Source\n\n- Title: x\n- Author: y\n\n"
        "## Section\n\nWalk every day for good health.\n\n```claim\nid: c1\ntask: t\ncadence: daily\ncadence_text: daily\n"
        "cadence_quote: Walk every day\nimportance: essential\nimportance_quote: good health\nmedication: no\n"
        "duration_minutes: 20\nduration_quote: twenty minutes\n```\n"
    )
    with pytest.raises(KnowledgeBaseError, match="duration_quote"):
        load_document(doc, KnowledgeBase())


# ---- same name, different species ----

def test_a_cat_and_a_dog_can_share_a_name():
    owner = Owner("O", 90)
    owner.add_pet(Pet("Mochi", "cat"))
    owner.add_pet(Pet("Mochi", "dog"))
    with pytest.raises(ValueError, match="already exists"):
        owner.add_pet(Pet("Mochi", "cat"))
    assert owner.get_pet("Mochi", "dog").species == "dog"
    assert owner.get_pet_by_label("Mochi (cat)").species == "cat"
    with pytest.raises(ValueError, match="Several pets"):
        owner.get_pet("Mochi")


def test_same_named_pets_keep_separate_tasks_and_labels():
    owner = Owner("O", 120)
    cat, dog = Pet("Mochi", "cat"), Pet("Mochi", "dog")
    owner.add_pet(cat)
    owner.add_pet(dog)
    cat.add_task(Task("Feed", 10, Priority.HIGH, scheduled_time="08:00"))
    dog.add_task(Task("Feed", 10, Priority.HIGH, scheduled_time="08:00"))  # same title is fine: different pet
    assert [t.pet_label for t in owner.filter_tasks(pet_label="Mochi (dog)")] == ["Mochi (dog)"]
    plan = Scheduler(owner).generate_plan()
    assert {i.pet_label for i in plan.scheduled} == {"Mochi (cat)", "Mochi (dog)"}
    assert any("Mochi (cat)" in w and "Mochi (dog)" in w for w in plan.warnings)


def test_already_on_pet_detects_a_pending_duplicate():
    from pipeline import already_on_pet, task_title

    pet = Pet("Mochi", "cat")
    item = _item()
    assert not already_on_pet(pet, item)
    accept_item(pet, item)
    assert already_on_pet(pet, item)
    assert task_title(_item(cadence="other", cadence_text="once a year")) == "Clean the litter box (once a year)"
    pet.tasks[0].completed = True
    assert not already_on_pet(pet, item)  # a finished task can be suggested again


# ---- the live evaluation's scoring rules (no model involved) ----

def test_evaluation_counts_only_daily_tasks_against_the_daily_budget():
    import evaluate
    from knowledge_base import load_knowledge_base
    from pipeline import SuggestionResult

    kb = load_knowledge_base()

    def item(claim_id, cadence, minutes):
        return ReviewItem(claim_id=claim_id, title=claim_id, priority="HIGH", cadence=cadence,
                          cadence_text="", duration_minutes=minutes, status=cmp.PASS)

    ok = SuggestionResult(pet_name="P", stage="adult")
    ok.items = [item("cat-litter-daily", "daily", 40), item("cat-wellness-annual", "other", 45), item("cat-litter-weekly-wash", "weekly", 30)]
    assert evaluate.invariants(ok, "adult", kb) == []  # 115 min in total, but only 40 are daily

    over = SuggestionResult(pet_name="P", stage="adult")
    over.items = [item("cat-litter-daily", "daily", 60), item("cat-water-daily", "daily", 40)]
    assert any("over" in b for b in evaluate.invariants(over, "adult", kb))
    assert any("expected" in b for b in evaluate.invariants(ok, "kitten", kb))


def test_no_ordinary_claim_trips_the_medication_filter(kb):
    """The filter must not remove a normal task because of the claim's own wording.

    Found by the live evaluation: the puppy walk's title mentioned vaccination, so the filter
    removed a core daily task. Every non-medication claim's title and quotes must pass the filter.
    """
    from guardrails import mentions_medication

    for claim in kb.claims.values():
        if claim.medication:
            continue
        for label, text in (("task", claim.task), ("cadence_quote", claim.cadence_quote), ("importance_quote", claim.importance_quote)):
            assert not mentions_medication(text), f"{claim.id} {label}: {text!r}"
