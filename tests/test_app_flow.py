"""Drives the guided Streamlit flow with Streamlit's own test runner.

There is no fake model. Where a test needs suggestion cards on screen, it puts a suggestion result
(built by the real `prepare` and `review` from a hand-written proposal) into the session, which is
what the "Suggest care tasks" button would have stored. Storage is replaced so no disk is used.
Skipped automatically if Streamlit cannot be imported in this environment.
"""

from datetime import date

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

import llm_client
import storage
from agent import Proposal
from pawpal_system import Owner, Pet
from pipeline import prepare, review

LITTER = Proposal(
    "cat-litter-daily", "Clean the litter box", "daily", "HIGH", 10,
    "Litterboxes should be cleaned at least once a day",
)


def suggestion_for(owner, proposals):
    """What the Suggest button would store, built by the real pipeline from hand-written proposals."""
    pet = owner.pets[0]
    return review(prepare(owner, pet, today=date.today()), proposals)


@pytest.fixture(autouse=True)
def no_disk(monkeypatch):
    monkeypatch.setattr(storage, "load", lambda: None)
    monkeypatch.setattr(storage, "save", lambda *a, **k: None)


def start(owner=None, step=0):
    at = AppTest.from_file("app.py", default_timeout=30)
    if owner is not None:
        at.session_state["owner"] = owner
        at.session_state["last_seen_stages"] = {}
    at.session_state["step"] = step
    return at.run()


def click(at, label):
    next(b for b in at.button if b.label == label).click()
    return at.run()


def cat_owner():
    owner = Owner("Jordan", 90)
    owner.add_pet(Pet("Mochi", "cat", birth_date=date(2021, 1, 1)))
    return owner


def test_opens_on_step_one_and_later_steps_need_a_pet():
    at = start()
    assert not at.exception
    assert any("Step 1 of 5" in str(p.proto) for p in at.get("progress"))
    assert at.button(key="nav_2").disabled and at.button(key="nav_4").disabled
    assert not at.button(key="next").disabled


def test_cannot_continue_from_pets_step_without_a_pet():
    at = start(step=1)
    assert at.button(key="next").disabled


def test_adding_a_pet_shows_live_stage_and_unlocks_next():
    at = start(step=1)
    at.selectbox(key="new_pet_species").select("cat")
    at.date_input(key="new_pet_birth").set_value(date(2021, 1, 1))
    at.run()
    assert any("adult" in c.value for c in at.caption)  # live preview before clicking Add
    at = click(at, "Add pet")
    assert not at.exception
    assert [p.label for p in at.session_state["owner"].pets] == ["Mochi (cat)"]
    assert not at.button(key="next").disabled


def test_a_cat_and_a_dog_named_mochi_can_both_be_added():
    at = start(step=1)
    at.selectbox(key="new_pet_species").select("cat")
    at.run()
    at = click(at, "Add pet")
    at.selectbox(key="new_pet_species").select("dog")
    at.run()
    at = click(at, "Add pet")
    assert not at.exception
    assert sorted(p.label for p in at.session_state["owner"].pets) == ["Mochi (cat)", "Mochi (dog)"]


def test_back_and_next_move_between_steps():
    at = start(cat_owner(), step=0)
    at = at.button(key="next").click().run()
    assert at.session_state["step"] == 1
    at = at.button(key="back").click().run()
    assert at.session_state["step"] == 0


def test_suggest_tick_add_then_schedule():
    owner = cat_owner()
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["owner"], at.session_state["last_seen_stages"] = owner, {}
    at.session_state["step"] = 2
    at.session_state["suggestion"] = suggestion_for(owner, [LITTER])
    at.run()
    assert not at.exception
    assert any("standing" in n.value or "veterinarian" in n.value for n in at.info)  # medication note
    box = at.checkbox(key="add_cat-litter-daily")
    box.check()
    at.run()
    at = click(at, "Add selected tasks")
    assert not at.exception
    pet = at.session_state["owner"].get_pet_by_label("Mochi (cat)")
    assert [t.title for t in pet.tasks] == ["Clean the litter box"]
    assert any("Added 1 task" in s.value for s in at.success)
    # the tick box is reset and the item is now marked as already added, so it cannot be added twice
    assert at.checkbox(key="add_cat-litter-daily").value is False
    assert at.checkbox(key="add_cat-litter-daily").disabled
    assert any("Already added" in c.value for c in at.caption)
    assert len(pet.tasks) == 1
    at.session_state["step"] = 4
    at.run()
    assert not at.exception
    assert any(str(m.value) == "1" for m in at.metric)  # one task scheduled


def test_missing_key_is_a_message_not_a_crash(monkeypatch):
    def boom():
        raise llm_client.MissingAPIKeyError("ANTHROPIC_API_KEY is not set.")

    monkeypatch.setattr(llm_client, "AnthropicLLM", boom)
    at = click(start(cat_owner(), step=2), "Suggest care tasks")
    assert not at.exception
    assert any("ANTHROPIC_API_KEY" in e.value for e in at.error)


def at_with_suggestion(step=2):
    owner = cat_owner()
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["owner"], at.session_state["last_seen_stages"] = owner, {}
    at.session_state["step"] = step
    at.session_state["suggestion"] = suggestion_for(owner, [LITTER])
    return at.run()


def test_select_all_and_clear_buttons():
    at = click(at_with_suggestion(), "Select all")
    assert at.checkbox(key="add_cat-litter-daily").value is True
    at = click(at, "Clear")
    assert at.checkbox(key="add_cat-litter-daily").value is False


def test_remove_pet_button():
    at = start(cat_owner(), step=1)
    at.button(key="rm_Mochi (cat)").click()
    at.run()
    assert at.session_state["owner"].pets == []


def test_refresh_returns_to_the_start_and_keeps_data():
    at = at_with_suggestion()
    at.checkbox(key="add_cat-litter-daily").check()
    at.run()
    at.session_state["step"] = 3
    at.run()
    at.button(key="refresh").click()
    at.run()
    assert not at.exception
    assert at.session_state["step"] == 0
    assert "suggestion" not in at.session_state
    assert not any(str(k).startswith("add_") for k in at.session_state.filtered_state)
    assert [p.label for p in at.session_state["owner"].pets] == ["Mochi (cat)"]  # data is kept


def test_general_knowledge_tasks_are_shown_unticked_and_added_only_when_ticked():
    owner = cat_owner()
    general = Proposal("general", "Rotate the toys", "weekly", "LOW", 10, "")
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["owner"], at.session_state["last_seen_stages"] = owner, {}
    at.session_state["step"] = 2
    at.session_state["suggestion"] = suggestion_for(owner, [LITTER, general])
    at.run()
    assert not at.exception
    assert any("general knowledge" in m.value for m in at.markdown)
    box = at.checkbox(key="add_general-1")
    assert box.value is False
    box.check()
    at.run()
    at = click(at, "Add selected tasks")
    assert not at.exception
    pet = at.session_state["owner"].get_pet_by_label("Mochi (cat)")
    assert [t.title for t in pet.tasks] == ["Rotate the toys [AI suggestion, no source]"]
