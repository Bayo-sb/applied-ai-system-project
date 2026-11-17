"""Live evaluation: runs the whole pipeline against the REAL model and scores what comes back.

Run:   python evaluate.py                  (2 runs per pet profile)
       python evaluate.py --repeats 3      (more runs, more cost)
       python evaluate.py --show           (also print every proposal, for the README)
       python evaluate.py --only Rex --repeats 1 --show   (one pet profile, one run: cheapest)

This calls the paid API: one request per pet profile per run. Needs ANTHROPIC_API_KEY (see
.env.example). Results vary a little from run to run, which is why each profile is repeated.

What is scored, per proposal the model makes:
  PASS      passed every check in the compliance check
  ESCALATE  failed a check that the owner would decide on (e.g. a quote not found in the source)
  UNSOURCED the model proposed it from its own knowledge (no source); shown apart, owner decides
  DECLINE   frequency or priority not supported by the source
  REMOVED   the model proposed something about medication, so it was removed
and per run, whether the system's own rules held (see INVARIANTS). The checks themselves are
tested without any model in tests/test_controls.py.

Results are also written to eval_results/latest.json.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from knowledge_base import load_knowledge_base
from llm_client import AnthropicLLM, LLMError
from pawpal_system import Owner, Pet
from pipeline import suggest_tasks

TODAY = date.today()
MINUTES_PER_DAY = 90

def months_ago(months: int) -> date:
    """The first day of the month, `months` months before today."""
    total = TODAY.year * 12 + (TODAY.month - 1) - months
    return date(total // 12, total % 12 + 1, 1)


# (name, species, birth date, expected life stage)
PROFILES = [
    ("Pip", "cat", months_ago(3), "kitten"),
    ("Junior", "cat", months_ago(14), "junior"),
    ("Mochi", "cat", months_ago(60), "adult"),
    ("Old Tom", "cat", months_ago(144), "senior"),
    ("Biscuit", "dog", months_ago(5), "puppy"),
    ("Rex", "dog", months_ago(72), "adult"),
]


def invariants(result, expected_stage: str, kb) -> list[str]:
    """Rules the system must always keep, whatever the model says. Returns the ones that broke."""
    broken = []
    if result.stage != expected_stage:
        broken.append(f"stage was {result.stage}, expected {expected_stage}")
    shown = result.items
    for i in result.unsourced:
        if i.priority == "HIGH":
            broken.append(f"an unsourced task has HIGH priority: {i.title}")
        if i.status != "UNSOURCED":
            broken.append(f"an unsourced task has status {i.status}")
    if any(i.status == "MEDICATION" for i in shown + result.unsourced):
        broken.append("a medication item was shown to the owner")
    ids = [i.claim_id for i in shown + result.declined]
    if len(ids) != len(set(ids)):
        broken.append("the same claim appeared twice")
    for i in shown:
        if i.status == "PASS" and i.claim_id not in kb.claims:
            broken.append(f"a passing task cites unknown claim {i.claim_id}")
        if i.status == "PASS" and kb.claims[i.claim_id].medication:
            broken.append(f"a passing task is a medication claim: {i.claim_id}")
    # Only daily tasks use up the daily budget. Weekly, yearly and other tasks happen on other days.
    daily = sum(i.duration_minutes or 0 for i in shown if i.status == "PASS" and i.cadence == "daily")
    if daily > MINUTES_PER_DAY:
        broken.append(f"passing daily tasks add up to {daily} min, over {MINUTES_PER_DAY}")
    return broken


def run_profile(llm, kb, name, species, born, expected):
    owner = Owner("Evaluation", MINUTES_PER_DAY)
    pet = Pet(name, species, birth_date=born)
    result = suggest_tasks(owner, pet, llm, today=TODAY, kb=kb)
    counts = {"PASS": 0, "ESCALATE": 0, "UNSOURCED": len(result.unsourced),
              "DECLINE": len(result.declined), "REMOVED": len(result.redirected)}
    for item in result.items:
        counts[item.status] = counts.get(item.status, 0) + 1
    errored = any(t["step"] == "agent_error" for t in result.trace)
    tokens = [t["detail"] for t in result.trace if t["step"] == "agent"]
    return {
        "pet": f"{name} ({species}, {expected})",
        "counts": counts,
        "proposals": sum(counts.values()),
        "model_error": errored,
        "broken_rules": invariants(result, expected, kb),
        "trace_agent": tokens[0] if tokens else None,
        "items": [
            {"status": i.status, "title": i.title, "priority": i.priority, "frequency": i.cadence_text or "no frequency",
             "minutes": i.duration_minutes, "from_source": i.duration_from_source, "reasons": i.reasons}
            for i in result.items + result.unsourced + result.declined
        ],
        "removed": [i.title for i in result.redirected],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeats", type=int, default=2, help="runs per pet profile (default 2)")
    parser.add_argument("--show", action="store_true", help="print every proposal")
    parser.add_argument("--only", help="run only the pet profile with this name, e.g. Rex or Pip")
    args = parser.parse_args()
    profiles = [p for p in PROFILES if args.only is None or p[0].lower() == args.only.lower()]
    if not profiles:
        parser.error(f"no profile named {args.only!r}. Choose from: " + ", ".join(p[0] for p in PROFILES))

    kb = load_knowledge_base()
    llm = AnthropicLLM()
    runs = []
    for name, species, born, expected in profiles:
        for n in range(1, args.repeats + 1):
            try:
                run = run_profile(llm, kb, name, species, born, expected)
            except LLMError as exc:
                run = {"pet": f"{name} ({species}, {expected})", "counts": {}, "proposals": 0, "model_error": True,
                       "broken_rules": [], "items": [], "removed": [], "trace_agent": None, "error": str(exc)}
            run["run"] = n
            runs.append(run)
            c = run["counts"]
            print(f"{run['pet']:<28} run {n}: proposals={run['proposals']:<3} PASS={c.get('PASS', 0)} "
                  f"ESCALATE={c.get('ESCALATE', 0)} UNSOURCED={c.get('UNSOURCED', 0)} DECLINE={c.get('DECLINE', 0)} REMOVED={c.get('REMOVED', 0)}"
                  + ("  MODEL ERROR" if run["model_error"] else "")
                  + (f"  BROKEN RULES: {run['broken_rules']}" if run["broken_rules"] else ""))
            if args.show:
                for it in run["items"]:
                    print(f"    [{it['status']}] {it['title']} | {it['priority']} | {it['frequency']} | "
                          f"{it['minutes']} min{' (from source)' if it['from_source'] else ''}")
                    for r in it["reasons"]:
                        print(f"        - {r}")
                for title in run["removed"]:
                    print(f"    [REMOVED, medication] {title}")

    total = {k: sum(r["counts"].get(k, 0) for r in runs) for k in ("PASS", "ESCALATE", "UNSOURCED", "DECLINE", "REMOVED")}
    proposals = sum(total.values())
    ok_runs = [r for r in runs if not r["model_error"]]
    broken = [r for r in runs if r["broken_rules"]]
    print("\nSUMMARY (real model, "
          f"{len(runs)} runs over {len(profiles)} pet profile(s), {datetime.now():%Y-%m-%d})")
    print(f"  runs with a model error:      {len(runs) - len(ok_runs)} of {len(runs)}")
    print(f"  runs where a system rule broke: {len(broken)} of {len(runs)}")
    if proposals:
        for key in ("PASS", "ESCALATE", "UNSOURCED", "DECLINE", "REMOVED"):
            print(f"  {key:<9} {total[key]:>3} of {proposals} proposals ({100 * total[key] / proposals:.0f}%)")
    Path("eval_results").mkdir(exist_ok=True)
    Path("eval_results/latest.json").write_text(
        json.dumps({"date": TODAY.isoformat(), "model": llm.model, "repeats": args.repeats, "runs": runs}, indent=2),
        encoding="utf-8",
    )
    print("  saved to eval_results/latest.json")
    return 0 if not broken and len(ok_runs) == len(runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
