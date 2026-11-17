"""Saves and loads the owner, pets and tasks as JSON, so a pet's age can be tracked across visits.

Also stores the life stage each pet was last seen in, which is how a stage change is noticed.
The file holds personal data and is ignored by git (see .gitignore).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pawpal_system import Frequency, Owner, Pet, Priority, Task

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "pawpal.json"


def _task_to_dict(t: Task) -> dict:
    return {
        "title": t.title,
        "duration_minutes": t.duration_minutes,
        "priority": t.priority.name,
        "frequency": t.frequency.value,
        "completed": t.completed,
        "scheduled_time": t.scheduled_time,
        "due_date": t.due_date.isoformat() if t.due_date else None,
    }


def _task_from_dict(d: dict) -> Task:
    task = Task(
        d["title"],
        d["duration_minutes"],
        Priority[d["priority"]],
        Frequency(d["frequency"]),
        completed=d.get("completed", False),
        scheduled_time=d.get("scheduled_time"),
        due_date=date.fromisoformat(d["due_date"]) if d.get("due_date") else None,
    )
    return task


def save(owner: Owner, last_seen_stages: dict, path: Path = DEFAULT_PATH) -> None:
    data = {
        "owner": {
            "name": owner.name,
            "available_minutes_per_day": owner.available_minutes_per_day,
            "preferences": owner.preferences,
        },
        "pets": [
            {
                "name": p.name,
                "species": p.species,
                "birth_date": p.birth_date.isoformat() if p.birth_date else None,
                "tasks": [_task_to_dict(t) for t in p.tasks],
            }
            for p in owner.pets
        ],
        "last_seen_stages": last_seen_stages,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)  # write then rename, so a crash cannot leave half a file


def load(path: Path = DEFAULT_PATH) -> tuple[Owner, dict] | None:
    """Return (owner, last_seen_stages), or None if there is no saved file or it is unreadable."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        o = data["owner"]
        owner = Owner(o["name"], o["available_minutes_per_day"], o.get("preferences", {}))
        for p in data["pets"]:
            pet = Pet(
                p["name"],
                p["species"],
                birth_date=date.fromisoformat(p["birth_date"]) if p.get("birth_date") else None,
            )
            for t in p["tasks"]:
                pet.add_task(_task_from_dict(t))
            owner.add_pet(pet)
        return owner, data.get("last_seen_stages", {})
    except (KeyError, ValueError, json.JSONDecodeError):
        return None
