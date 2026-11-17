import streamlit as st

from datetime import date, time

import storage
from life_stage import age_in_months, life_stage, stage_changes
from llm_client import AnthropicLLM, LLMError
from pipeline import accept_item, already_on_pet, suggest_tasks
from verifier import verify_plan
from pawpal_system import (
    Frequency,
    Owner,
    Pet,
    Priority,
    Scheduler,
    Task,
    format_clock,
    parse_clock,
)

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

STEPS = ["Your day", "Your pets", "Care suggestions", "Tasks", "Today's schedule"]
PRIORITY_DOT = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟢"}
STATUS_TEXT = {
    "PASS": "✅ Passed all checks",
    "ESCALATE": "⚠️ Failed a check: you decide",
    "UNSOURCED": "🧠 AI general knowledge, no source: you decide",
}

# ---------------------------------------------------------------- state

if "owner" not in st.session_state:
    saved = storage.load()
    if saved is not None:
        st.session_state.owner, st.session_state.last_seen_stages = saved
    else:
        st.session_state.owner = Owner(name="Jordan", available_minutes_per_day=90)
        st.session_state.last_seen_stages = {}
owner = st.session_state.owner
last_seen = st.session_state.setdefault("last_seen_stages", {})
st.session_state.setdefault("step", 0)


def save_all() -> None:
    """Write pets, tasks and the last-seen life stages to disk."""
    storage.save(owner, last_seen)


def go(step: int) -> None:
    st.session_state.step = max(0, min(step, len(STEPS) - 1))


def review_pet(label: str) -> None:
    """Jump to the suggestions step with this pet already chosen."""
    st.session_state.suggest_for = label
    go(2)


def remove_pet(label: str) -> None:
    pet = owner.get_pet_by_label(label)
    if pet is not None:
        owner.remove_pet(pet.name, pet.species)
        last_seen.pop(label, None)
        suggestion = st.session_state.get("suggestion")
        if suggestion is not None and suggestion.pet_label == label:
            st.session_state.pop("suggestion", None)
        save_all()
        st.toast(f"Removed {label}.")


def refresh() -> None:
    """Back to the default screen: step 1, no suggestions, form fields reset.

    Saved pets, tasks and your time budget are kept. Nothing on disk is touched.
    """
    transient = ("add_", "min_", "new_pet_", "suggest_for", "manual_pet", "task_pick")
    for key in [k for k in st.session_state if str(k).startswith(transient)]:
        del st.session_state[key]
    for key in ("suggestion", "add_report"):
        st.session_state.pop(key, None)
    st.session_state.step = 0
    st.toast("Back to the start. Your pets and tasks are kept.", icon="🔄")


def select_all(ids: list) -> None:
    for claim_id in ids:
        st.session_state[f"add_{claim_id}"] = True


def clear_all(ids: list) -> None:
    for claim_id in ids:
        st.session_state[f"add_{claim_id}"] = False


def add_selected() -> None:
    """Add the ticked suggestions to the pet. Runs before the page redraws, so the tick boxes can be reset."""
    result = st.session_state.get("suggestion")
    pet = owner.get_pet_by_label(result.pet_label) if result is not None else None
    if pet is None:
        return
    added, problems = 0, []
    for item in result.items + result.unsourced:
        key = f"add_{item.claim_id}"
        if st.session_state.get(key):
            try:
                accept_item(pet, item, int(st.session_state[f"min_{item.claim_id}"]))
                added += 1
            except ValueError as e:
                problems.append(f"{item.title}: {e}")
            st.session_state[key] = False
    if added:
        save_all()
        st.toast(f"Added {added} task(s) to {pet.label}.", icon="✅")
    st.session_state.add_report = (added, problems, pet.label)


# ---------------------------------------------------------------- header

title_col, refresh_col = st.columns([5, 1], vertical_alignment="center")
title_col.title("🐾 PawPal+")
refresh_col.button("🔄 Refresh", key="refresh", on_click=refresh, help="Go back to the start. Your pets and tasks are kept.")
st.caption("A daily care planner for your pets: add them, review AI care suggestions, and build a schedule.")

step = st.session_state.step
st.progress((step + 1) / len(STEPS), text=f"Step {step + 1} of {len(STEPS)}: {STEPS[step]}")
nav_cols = st.columns(len(STEPS))
for i, name in enumerate(STEPS):
    nav_cols[i].button(
        f"{i + 1}. {name}",
        key=f"nav_{i}",
        type="primary" if i == step else "secondary",
        use_container_width=True,
        disabled=(i >= 2 and not owner.pets),
        on_click=go,
        args=(i,),
    )

# Life-stage changes since the last visit. A banner can only appear when the app is opened.
for change in stage_changes(owner.pets, last_seen, date.today()):
    with st.container(border=True):
        st.info(f"🎂 {change.pet_name} has moved from {change.previous} to {change.current}.")
        st.button(
            f"Review care tasks for {change.pet_name}",
            key=f"review_{change.pet_name}",
            on_click=review_pet,
            args=(change.pet_name,),
        )

st.divider()

# ---------------------------------------------------------------- step 1: your day

if step == 0:
    st.subheader("Your day")
    st.caption("How much time can you spend on pet care each day? Plans and AI suggestions stay within this.")
    owner.name = st.text_input("Your name", value=owner.name)
    owner.available_minutes_per_day = st.slider(
        "Minutes available per day", min_value=0, max_value=480, step=5, value=min(owner.available_minutes_per_day, 480)
    )
    hours, minutes = divmod(owner.available_minutes_per_day, 60)
    st.metric("Time for pet care", f"{hours} h {minutes} min" if hours else f"{minutes} min")

# ---------------------------------------------------------------- step 2: your pets

elif step == 1:
    st.subheader("Your pets")
    for pet in owner.pets:
        stage = life_stage(pet.species, pet.birth_date, date.today())
        with st.container(border=True):
            info_col, remove_col = st.columns([5, 1], vertical_alignment="center")
            info_col.markdown(
                f"**{pet.label}**"
                + (f", {stage}" if stage else "")
                + (f", {age_in_months(pet.birth_date, date.today()) // 12} y {age_in_months(pet.birth_date, date.today()) % 12} m" if pet.birth_date else "")
                + f", {len(pet.tasks)} task(s)"
            )
            remove_col.button("Remove", key=f"rm_{pet.label}", on_click=remove_pet, args=(pet.label,))

    st.markdown("**Add a pet**")
    name_col, species_col, birth_col = st.columns(3)
    pet_name = name_col.text_input("Pet name", value="Mochi", key="new_pet_name")
    species = species_col.selectbox("Species", ["dog", "cat", "other"], key="new_pet_species")
    birth_date = birth_col.date_input(
        "Birth date (approximate is fine)",
        value=date(date.today().year - 2, 1, 1),
        min_value=date(1990, 1, 1),
        max_value=date.today(),
        key="new_pet_birth",
    )
    preview = life_stage(species, birth_date, date.today())
    if preview:
        months = age_in_months(birth_date, date.today())
        st.caption(f"{pet_name or 'This pet'} would be a **{preview}** ({months // 12} y {months % 12} m).")
    else:
        st.caption(f"No care documents or life-stage source for '{species}' yet, so no AI suggestions. You can still add tasks yourself.")

    if st.button("Add pet", type="primary"):
        try:
            owner.add_pet(Pet(name=pet_name.strip(), species=species, birth_date=birth_date))
        except ValueError as e:
            st.error(str(e))
        else:
            if preview:
                last_seen[f"{pet_name.strip()} ({species})"] = preview
            save_all()
            st.toast(f"Added {pet_name.strip()} the {species}.", icon="🐾")
            st.rerun()
    if not owner.pets:
        st.info("Add at least one pet to continue.")

# ---------------------------------------------------------------- step 3: care suggestions

elif step == 2:
    st.subheader("Care suggestions")
    st.caption(
        "The AI suggests routine care tasks from the care documents, with the source for each. "
        "General guidance, not veterinary advice. Nothing is added until you tick it and click Add."
    )
    labels = [p.label for p in owner.pets]
    suggest_for = st.selectbox("Suggest tasks for", labels, key="suggest_for")
    if st.button("Suggest care tasks", type="primary"):
        pet_obj = owner.get_pet_by_label(suggest_for)
        try:
            llm = AnthropicLLM()
        except LLMError as e:
            st.error(str(e))
        else:
            with st.spinner("Asking the AI and checking its answer..."):
                st.session_state.suggestion = suggest_tasks(owner, pet_obj, llm)
            for key in [k for k in st.session_state if str(k).startswith(("add_", "min_"))]:
                del st.session_state[key]
            current = st.session_state.suggestion.stage
            if current:  # the owner has now seen this stage, so the stage-change banner can clear
                last_seen[pet_obj.label] = current
                save_all()

    result = st.session_state.get("suggestion")
    if result is not None and owner.get_pet_by_label(result.pet_label) is not None:
        pet_obj = owner.get_pet_by_label(result.pet_label)
        st.markdown(f"**{result.pet_label}**" + (f", life stage: **{result.stage}**" if result.stage else ""))
        for message in result.messages:
            st.warning(message)
        for note in result.notes:
            st.info(note)

        report = st.session_state.pop("add_report", None)
        if report is not None:
            added, problems, label = report
            if added:
                st.success(f"Added {added} task(s) to {label}. Continue to Tasks or Today's schedule.")
            for problem in problems:
                st.error(problem)

        everything = result.items + result.unsourced
        already = {item.claim_id for item in everything if already_on_pet(pet_obj, item)}
        ids = [item.claim_id for item in result.items if item.claim_id not in already]
        if already:
            st.caption(f"{len(already)} suggestion(s) are already on {pet_obj.label}'s task list.")
        if ids:
            ticked = sum(1 for cid in ids if st.session_state.get(f"add_{cid}"))
            select_col, clear_col, count_col = st.columns([1, 1, 2], vertical_alignment="center")
            select_col.button("Select all", on_click=select_all, args=(ids,))
            clear_col.button("Clear", on_click=clear_all, args=(ids,))
            count_col.caption(f"{ticked} of {len(ids)} selected")

        selected_minutes = 0
        for item in everything:
            if result.unsourced and item is result.unsourced[0]:
                st.markdown("**From the AI's general knowledge**")
                st.caption(
                    "These were not found in your documents and nothing checked them against a source. "
                    "They are never selected for you."
                )
            with st.container(border=True):
                add_col, minutes_col = st.columns([4, 1], vertical_alignment="center")
                checked = add_col.checkbox(
                    f"{PRIORITY_DOT.get(item.priority, '')} {item.title}  ({item.priority.title()} priority, "
                    f"{item.cadence_text or 'frequency not given'})",
                    key=f"add_{item.claim_id}",
                    disabled=item.claim_id in already,
                )
                minutes = minutes_col.number_input(
                    "Minutes",
                    min_value=1,
                    max_value=240,
                    value=item.duration_minutes or 15,
                    key=f"min_{item.claim_id}",
                    label_visibility="collapsed",
                )
                if checked and item.claim_id not in already and item.cadence == "daily":
                    selected_minutes += int(minutes)  # only daily tasks use the daily budget
                st.caption(
                    ("✔ Already added. " if item.claim_id in already else "")
                    + f"{STATUS_TEXT.get(item.status, item.status)}. Source: {item.citation}"
                )
                if item.duration_from_source:
                    st.caption(f"Minutes are from the source ({item.duration_text}). You can still change them.")
                for reason in item.reasons:
                    st.caption(f"- {reason}")

        if everything:
            budget = owner.available_minutes_per_day
            st.progress(min(selected_minutes / budget, 1.0) if budget else 0.0, text=f"Selected daily tasks: {selected_minutes} of {budget} min per day")
            if selected_minutes > budget:
                st.warning("The selected daily tasks add up to more than your daily time. The scheduler will skip the lowest priority ones.")
            any_ticked = any(
                st.session_state.get(f"add_{i.claim_id}") for i in everything if i.claim_id not in already
            )
            st.button("Add selected tasks", type="primary", disabled=not any_ticked, on_click=add_selected)
        if result.declined:
            with st.expander(f"Declined by the check ({len(result.declined)})"):
                for item in result.declined:
                    st.write(f"**{item.title}**: " + " ".join(item.reasons))
        with st.expander("What the system did (trace)"):
            st.dataframe(result.trace, hide_index=True)

# ---------------------------------------------------------------- step 4: tasks

elif step == 3:
    st.subheader("Tasks")
    scheduler = Scheduler(owner)

    with st.expander("Add a task yourself"):
        target = st.selectbox("Pet", [p.label for p in owner.pets], key="manual_pet")
        col1, col2, col3, col4 = st.columns(4)
        task_title = col1.text_input("Task title", value="Morning walk")
        duration = col2.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
        priority = col3.selectbox("Priority", [p.name for p in Priority], index=2)
        frequency = col4.selectbox("Repeats", [f.value for f in Frequency])
        start_time = None
        if st.checkbox("Fixed start time"):
            start_time = st.time_input("Start time", value=time(8, 30), step=300).strftime("%H:%M")
        if st.button("Add task"):
            try:
                owner.get_pet_by_label(target).add_task(
                    Task(task_title, int(duration), Priority[priority], Frequency(frequency), scheduled_time=start_time)
                )
            except ValueError as e:
                st.error(str(e))
            else:
                save_all()
                st.toast(f"Added '{task_title}' for {target}.", icon="✅")
                st.rerun()

    all_tasks = owner.get_all_tasks()
    if all_tasks:
        total_col, pending_col, done_col = st.columns(3)
        total_col.metric("Total tasks", len(all_tasks))
        pending_col.metric("Pending", len(owner.filter_tasks(completed=False)))
        done_col.metric("Completed", len(owner.filter_tasks(completed=True)))

        filter_col1, filter_col2 = st.columns(2)
        pet_filter = filter_col1.selectbox("Show pet", ["All"] + [p.label for p in owner.pets])
        status_filter = filter_col2.selectbox("Show status", ["All", "Pending", "Completed"])
        shown = scheduler.sort_by_time(
            owner.filter_tasks(
                pet_label=None if pet_filter == "All" else pet_filter,
                completed={"All": None, "Pending": False, "Completed": True}[status_filter],
            )
        )
        if shown:
            st.dataframe(
                [
                    {
                        "Time": t.scheduled_time or "any time",
                        "Pet": t.pet_label,
                        "Task": t.title,
                        "Minutes": t.duration_minutes,
                        "Priority": f"{PRIORITY_DOT[t.priority.name]} {t.priority.name.title()}",
                        "Repeats": t.frequency.value,
                        "Done": t.completed,
                    }
                    for t in shown
                ],
                hide_index=True,
                column_config={"Done": st.column_config.CheckboxColumn("Done", disabled=True)},
            )
            st.caption(f"Showing {len(shown)} of {len(all_tasks)} tasks, sorted by time.")
        else:
            st.info("No tasks match these filters.")

        pending = [t for t in all_tasks if not t.completed]
        pick_col, done_btn_col, rm_btn_col = st.columns([3, 1, 1], vertical_alignment="bottom")
        chosen = pick_col.selectbox("Pick a task", [f"{t.pet_label}: {t.title}" for t in all_tasks], key="task_pick")
        if done_btn_col.button("Mark done", disabled=not pending):
            pet_label, title = chosen.split(": ", 1)
            try:
                owner.get_pet_by_label(pet_label).complete_task(title)
            except (KeyError, ValueError) as e:
                st.error(str(e))
            else:
                save_all()
                st.toast(f"Done: {title}", icon="🎉")
                st.rerun()
        if rm_btn_col.button("Remove"):
            pet_label, title = chosen.split(": ", 1)
            try:
                owner.get_pet_by_label(pet_label).remove_task(title)
            except KeyError as e:
                st.error(str(e))
            else:
                save_all()
                st.toast(f"Removed: {title}")
                st.rerun()
    else:
        st.info("No tasks yet. Get suggestions in the previous step, or add one above.")

# ---------------------------------------------------------------- step 5: schedule

elif step == 4:
    st.subheader("Today's schedule")
    day_start = st.time_input("Day starts at", value=time(8, 0), step=900).strftime("%H:%M")
    plan = Scheduler(owner, day_start=day_start).generate_plan()
    budget = owner.available_minutes_per_day
    free = budget - plan.total_minutes

    scheduled_col, planned_col, free_col, conflict_col = st.columns(4)
    scheduled_col.metric("Tasks scheduled", len(plan.scheduled))
    planned_col.metric("Minutes planned", plan.total_minutes)
    free_col.metric("Minutes free", free)
    conflict_col.metric("Conflicts", len(plan.warnings))
    st.progress(min(plan.total_minutes / budget, 1.0) if budget else 0.0, text=f"{plan.total_minutes} of {budget} min used")

    for warning in plan.warnings:
        st.warning(warning)
    if plan.scheduled and not plan.warnings:
        st.success("No scheduling conflicts.")
    for problem in verify_plan(plan, owner):
        st.error(f"Plan check: {problem}")

    if plan.scheduled:
        st.dataframe(
            [
                {
                    "Time": f"{item.start_time} - {format_clock(parse_clock(item.start_time) + item.task.duration_minutes)}",
                    "Pet": item.pet_label,
                    "Task": item.task.title,
                    "Minutes": item.task.duration_minutes,
                    "Why": item.reason,
                }
                for item in plan.scheduled
            ],
            hide_index=True,
        )
    else:
        st.info("Nothing to schedule yet. Add some tasks first.")

    if plan.skipped:
        st.warning(f"{len(plan.skipped)} task(s) did not fit in the available time.")
        st.dataframe(
            [
                {
                    "Task": item.task.title,
                    "Pet": item.pet_label,
                    "Minutes": item.task.duration_minutes,
                    "Priority": item.task.priority.name.title(),
                    "Reason": item.reason.removeprefix("Skipped: "),
                }
                for item in plan.skipped
            ],
            hide_index=True,
        )

# ---------------------------------------------------------------- back / next

st.divider()
back_col, next_col = st.columns(2)
back_col.button("← Back", key="back", disabled=step == 0, on_click=go, args=(step - 1,), use_container_width=True)
next_col.button(
    "Next →",
    key="next",
    type="primary",
    disabled=step == len(STEPS) - 1 or (step == 1 and not owner.pets),
    help="Add at least one pet first." if step == 1 and not owner.pets else None,
    on_click=go,
    args=(step + 1,),
    use_container_width=True,
)
