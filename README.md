# PawPal+ Care Advisor

PawPal+ Care Advisor adds an AI care planner to an existing pet-care scheduler. You add a pet with its species and birth date. The system works out the pet's life stage, finds care guidance for that species and stage in a set of cited documents, and has an AI propose daily care tasks. Every proposal is checked against the passages that were retrieved, and nothing is added until you approve it. The AI may also add up to three extra ideas from its own general knowledge. These are labeled as having no source, shown apart, never ticked for you, and never allowed to be high priority or about medication. The approved tasks go to the original scheduler, which builds the day's plan.

**Why it matters.** Pet owners are often unsure what a new puppy, an adult cat or a senior dog needs. AI answers can sound confident and still be wrong. This project makes the AI show its source for each task, checks that the source really says what the AI claims, and keeps medication decisions with a veterinarian. It is general guidance, not veterinary advice.

## Original project

The original project is **PawPal+ (Module 2 project)**, a Streamlit pet-care scheduler. An owner enters a daily time budget and their pets, adds care tasks with a duration, priority and repeat frequency, and the scheduler builds a prioritized daily plan with a reason for every choice. It also warns about overlapping tasks, recurs daily and weekly tasks. That code (`pawpal_system.py`) still does all the scheduling. Two small things were added to it: pets now have an optional birth date, and a cat and a dog may share a name. 
## Architecture overview

The data flow is: input, process, output, with checks along the way.

1. **Input.** The owner adds a pet (name, species, birth date). Pets are saved to disk (`data/pawpal.json`, not committed) so a pet's age can be tracked across visits. A life-stage tracker raises a banner when a saved pet reaches a new stage.
2. **Guardrails** validate the input and detect medication and dosage content.
3. **Retriever** picks the care passages for the pet's species and life stage. Passages are keyword-matched (TF-IDF) against a fixed list of care topics.
4. **LLM agent** (Claude, called with an API key) proposes tasks from the retrieved claims. Each carries a frequency, priority, duration and a quote from its source. It may also add up to three tasks from its own general knowledge, with no source.
5. **Compliance check** compares each proposal with its claim: the frequency and priority must match what the source supports, the quote must appear in the passage, the passage must apply to this species and life stage, and the duration must fit the owner's time. Failures are declined or shown to the owner with the reason. A task from the model's own knowledge can never pass: it gets the status UNSOURCED, is shown in its own section, and must not be HIGH priority, about medication, or anything other than daily or weekly.
6. **Human review.** The owner ticks the tasks to add and can edit the minutes. Nothing is added automatically.
7. **Scheduler and plan verifier.** The original scheduler builds the plan. The verifier checks the time budget and flags skipped high-priority tasks.
8. **Output.** The plan, each task's source, and a trace of what every step did.

Where humans and tests check the AI: the compliance check (every proposal, before a person sees it), human approval (every task), a standing rule that medication is never suggested, and direct tests of every check (no model involved), and a live evaluation against the real model.


Main files:

| File | Role |
|---|---|
| `app.py` | Streamlit guided flow: your day, your pets, care suggestions, tasks, today's schedule |
| `pipeline.py` | Runs the whole flow for one pet and returns the items to review |
| `llm_client.py` | The only code that calls the model. Reads the key from `.env`. |
| `agent.py` | Builds the prompt and parses the model's JSON reply |
| `compliance.py` | The compliance check |
| `knowledge_base.py`, `knowledge_base/*.md` | The cited care documents and their structured claims |
| `retriever.py`, `life_stage.py`, `guardrails.py` | Retrieval, life-stage rules, input and medication checks |
| `verifier.py`, `storage.py` | Plan verifier, saving pets to disk |
| `evaluate.py`, `tests/test_controls.py` | The live-model evaluation, and the direct tests of the checks |
| `pawpal_system.py` | The original scheduler (Module 2) |


## Setup instructions

1. Clone the repository and open its folder (the one that contains `app.py`).
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```
3. Install the requirements:
   ```bash
   pip install -r requirements.txt
   ```
4. Add your Anthropic API key. Copy `.env.example` to `.env` and put the key after the equals sign, with no quotes:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
   `.env` is ignored by git. The tests run without a key. The "Suggest care tasks" button and `evaluate.py` need one.
5. Start the app:
   ```bash
   streamlit run app.py
   ```
   If you change the code while the server is running, stop it with Ctrl+C and start it again. A browser refresh keeps old imported modules.
6. Optional checks, all from the project folder:
   ```bash
   python -m pytest            # all tests; no model is called, so no key or network is needed
   python evaluate.py          # live evaluation against the real model (paid; see the file for options)
   python evaluate.py --show   # same, and also print every proposal
   python demo.py              # one pet end to end, step by step (one paid request)
   python eval_retrieval.py    # measures retriever scores
   python verify_quotes.py     # checks knowledge-base quotes against the source PDFs
   ```
   `verify_quotes.py` needs the source PDFs in `assets/`, which are not committed because several are copyrighted.

## Sample interactions


**1. Adult cat, live model.** Run on 2026-11-16 with an earlier version of the live script (now `evaluate.py`), using the app's default model setting (`claude-opus-5-5`) and the real compliance check. Mochi is an adult cat, and the owner has 90 minutes a day. This is the output as printed:

```text
Mochi (cat, adult): {'PASS': 9, 'DECLINE': 1}
  [PASS] Feed Mochi's meals | HIGH | once or twice a day | 5 min
  [PASS] Refresh Mochi's drinking water | HIGH | at least once a day | 2 min
  [PASS] Clean the litter box | HIGH | at least once a day | 5 min
  [PASS] Veterinary wellness exam | HIGH | at least once a year | 30 min
  [PASS] Wash food and water bowls | MEDIUM | daily | 5 min
  [PASS] Play with Mochi (morning and evening) | MEDIUM | briefly, morning and evening | 10 min
  [PASS] Empty and wash the litter tray | MEDIUM | once a week | 10 min
  [PASS] Clean Mochi's teeth | MEDIUM | once or twice a week | 5 min
  [PASS] Veterinary fecal exam | MEDIUM | 1-2 times a year, depending on health and lifestyle | 10 min
  [DECLINE] Check weight and body condition | MEDIUM | no frequency | 5 min
      - The source gives no frequency for this task.
```


**2. A species with no documents (no model call).** Thumper, a rabbit. The system stops before the model is called, so there is nothing to guess.

```text
There is no care guidance for 'other' in the knowledge base, so no tasks are suggested.
```

**3. Kitten, live model.** Pip, a cat about 3 months old, 90 minutes a day, run on 2026-11-16 with `python evaluate.py --show`. Ten of eleven proposals passed.

```text
Pip (cat, kitten)            run 2: proposals=11  PASS=10 ESCALATE=0 DECLINE=1 REMOVED=0
    [PASS] Veterinary wellness exam | HIGH | at least once a year | 15 min
    [PASS] Veterinary fecal exam for Pip | MEDIUM | 2-4 times in the first year | 10 min
    [PASS] Empty and wash the litter tray | MEDIUM | once a week | 10 min
    [PASS] Wash food and water bowls | MEDIUM | daily | 5 min
    [PASS] Brief play sessions morning and evening | MEDIUM | briefly, morning and evening | 10 min
    [PASS] Short training session | MEDIUM | every day | 15 min (from source)
    [PASS] Clean the litter box | HIGH | at least once a day | 5 min
    [PASS] Feed Pip small kitten meals | HIGH | four or more small meals a day, falling to three by 3-4 months and two by 6 months | 10 min
    [PASS] Refresh drinking water | HIGH | at least once a day | 2 min
    [PASS] Clean Pip's teeth | MEDIUM | once or twice a week | 5 min
    [DECLINE] Check weight and body condition | MEDIUM | no frequency | 3 min
        - The source gives no frequency for this task.
```


**4. Adult dog and puppy, live model.** Rex, a dog about 6 years old, 90 minutes a day, run with `python evaluate.py --only Rex --repeats 1 --show`. Output as printed:

```text
Rex (dog, adult)             run 1: proposals=5   PASS=5 ESCALATE=0 DECLINE=0 REMOVED=0
    [PASS] Two daily walks with time to sniff | MEDIUM | two walks a day | 30 min (from source)
    [PASS] Short home training session | MEDIUM | five minutes a day | 5 min (from source)
    [PASS] Play fetch or with toys | MEDIUM | a few times a day | 15 min
    [PASS] Toilet breaks at set times | MEDIUM | at the same times every day | 10 min
    [PASS] Yearly vet check-up | HIGH | at least once a year | 30 min
```


```text
Biscuit (dog, puppy)         run 1: proposals=7   PASS=7 ESCALATE=0 DECLINE=0 REMOVED=0
    [PASS] Feed Biscuit small puppy meals | HIGH | 3-4 small meals a day, slowly decreasing to twice a day | 10 min
    [PASS] Short, gentle daily walk (check with your veterinarian first) | HIGH | short walks, daily | 15 min
    [PASS] Yearly veterinary check-up | HIGH | at least once a year | 30 min
    [PASS] Short training session | MEDIUM | five minutes a day | 5 min (from source)
    [PASS] Play fetch or with toys | MEDIUM | a few times a day | 15 min
    [PASS] Toilet breaks at the same times each day | MEDIUM | at the same times every day | 10 min
    [PASS] Brush Biscuit's teeth | MEDIUM | ideally daily | 5 min
```


**5. End-to-end run, live model.** Mochi, an adult cat born 2021-11-01, owner with 90 minutes a day, run on 2026-11-17 with `python demo.py`. It shows each stage in order: guardrails and life stage, retrieval (passages with scores), the live model's proposals checked against the sources, approval, the scheduler's plan, the plan verifier, and the trace log. Approval is automatic in this demo (only tasks that passed are added) so the output is repeatable. In the app, the owner ticks each task. Cases 2 and 3 involve no model call.

```text
=== CASE 1: end-to-end run for Mochi (cat, born 2021-11-01), owner has 90 min/day ===
Guardrails passed. Life stage: adult

=== RETRIEVAL (species and life-stage filter, then TF-IDF per care topic) ===
11 passages cleared the cut-off; best score 0.71
  0.71  AAFP-AAHA Feline Life Stage Guidelines (...), section 'Weight and body condition'
  0.68  Understanding, Caring for & Training Your Cat (...), section 'Weekly litter tray wash'
  0.57  The Ultimate Encyclopedia of Cats, Cat Breeds & Cat Care (...), section 'Fresh water'
  0.53  Understanding, Caring for & Training Your Cat (...), section 'Washing food and water bowls'
  0.53  Understanding, Caring for & Training Your Cat (...), section 'Play sessions'
  0.45  The Ultimate Encyclopedia of Cats, Cat Breeds & Cat Care (...), section 'Teeth cleaning'
  ... and 5 more

=== AGENT (live model) AND COMPLIANCE CHECK ===
[PASS] Feed Mochi's meals | HIGH | once or twice a day | 5 min (estimate)
    source: The Ultimate Encyclopedia of Cats (...), section 'Feeding adult cats'
[PASS] Refresh Mochi's drinking water | HIGH | at least once a day | 3 min (estimate)
    source: The Ultimate Encyclopedia of Cats (...), section 'Fresh water'
[PASS] Clean the litter box | HIGH | at least once a day | 5 min (estimate)
    source: What to Expect When Adopting a Feline Friend (Cornell Feline Health Center), section 'Litter box cleaning'
[PASS] Wash food and water bowls | MEDIUM | daily | 5 min (estimate)
    source: Understanding, Caring for & Training Your Cat (...), section 'Washing food and water bowls'
[PASS] Short play sessions, morning and evening | MEDIUM | briefly, morning and evening | 10 min (estimate)
    source: Understanding, Caring for & Training Your Cat (...), section 'Play sessions'
[PASS] Empty and wash the litter tray | MEDIUM | once a week | 10 min (estimate)
    source: Understanding, Caring for & Training Your Cat (...), section 'Weekly litter tray wash'
[PASS] Clean Mochi's teeth | MEDIUM | once or twice a week | 5 min (estimate)
    source: The Ultimate Encyclopedia of Cats (...), section 'Teeth cleaning'
[PASS] Veterinary fecal exam | MEDIUM | 1-2 times a year, depending on health and lifestyle | 10 min (estimate)
    source: AAFP-AAHA Feline Life Stage Guidelines (...), section 'Fecal examination, adult and older'
[PASS] Veterinary wellness exam | HIGH | at least once a year | 30 min (estimate)
    source: AAFP-AAHA Feline Life Stage Guidelines (...), section 'Wellness examinations'
[DECLINE] Check weight and body condition | MEDIUM | no frequency | 2 min (estimate)
    source: AAFP-AAHA Feline Life Stage Guidelines (...), section 'Weight and body condition'
    check: The source gives no frequency for this task.
NOTE: Vaccinations, worming, heartworm prevention and other medication are decided with your veterinarian. They are not part of these suggestions, and no product or dose is given.

=== HUMAN APPROVAL (PASS items approved automatically in this demo) ===
9 of 10 proposals added to Mochi's task list

=== SCHEDULER AND PLAN VERIFIER ===
  08:00  Refresh Mochi's drinking water (3 min)
  08:03  Feed Mochi's meals (5 min)
  08:08  Clean the litter box (5 min)
  08:13  Veterinary wellness exam (at least once a year) (30 min)
  08:43  Wash food and water bowls (5 min)
  08:48  Clean Mochi's teeth (5 min)
  08:53  Short play sessions, morning and evening (10 min)
  09:03  Empty and wash the litter tray (10 min)
  09:13  Veterinary fecal exam (1-2 times a year, depending on health and lifestyle) (10 min)
Total 83 of 90 minutes
Verifier: plan checks out

=== TRACE LOG ===
  guardrails  input valid
  life_stage  adult
  retrieval   11 passages, best score 0.71, confident=True
  medication  cat-parasite-control not suggested: medication is decided with a veterinarian
  medication  cat-vaccination not suggested: medication is decided with a veterinarian
  agent       model=claude-opus-5-5 proposals=10 in=1739 out=1574 request_id=req_011Ch85oG4ThWBck4arvNeuw
  compliance  cat-feed-adult: PASS []
  compliance  cat-water-daily: PASS []
  compliance  cat-litter-daily: PASS []
  compliance  cat-bowls-daily: PASS []
  compliance  cat-play-daily: PASS []
  compliance  cat-litter-weekly-wash: PASS []
  compliance  cat-teeth-brushing: PASS []
  compliance  cat-weight-check: DECLINE ['The source gives no frequency for this task.']
  compliance  cat-fecal-adult: PASS []
  compliance  cat-wellness-annual: PASS []

=== CASE 2: guardrail, a medication request (no model call) ===
Request: "What dose of flea treatment should I give Mochi?"
Detected as medication: True
Result: not suggested. Ask your veterinarian.

=== CASE 3: compliance check on a fabricated quote (hand-written proposal, no model call) ===
[ESCALATE] Clean the litter box
    check: The quote is not found in the cited passage.
Result: shown to the owner with the reason; the owner decides.
```

Long source citations are shortened to `(...)` in this README. The full citation, with authors and year, is printed by `demo.py`.

**6 to 9. The same end-to-end run at other ages and species** (live model, 2026-11-17, `python demo.py --pet <name>`, 90 minutes a day). Each block is condensed from the printed output: source names are shortened to the document and section, the retrieval list shows the top three passages, the medication-claim lines are merged, and cases 2 and 3 (identical to sample 5) are left out. The full output is printed by `demo.py`. Samples 1 to 9 were recorded before the own-knowledge tier was added, so they show sourced tasks only. Sample 10 shows the new tier.

*6. Biscuit, puppy (dog, about 5 months)*

```text
Life stage: puppy | 9 passages cleared the cut-off; best score 0.61
  0.61  Puppy Care Guide, 'Brushing a puppy's teeth'
  0.58  Dog Owner's Guide (Humane Fort Wayne), 'Training and play'
  0.55  Dog Owner's Guide (Humane Fort Wayne), 'Toilet routine'
Model proposals: 7 | PASS 7, DECLINE 0, ESCALATE 0
[PASS] Feed Biscuit small puppy meals | HIGH | 3-4 small meals a day, slowly decreasing to twice a day | 10 min (estimate) | Puppy Care Guide, 'Feeding puppies'
[PASS] Short, gentle walk (check with your veterinarian first about when to start) | HIGH | short walks, daily | 15 min (estimate) | Puppy Care Guide, 'Daily walks for puppies'
[PASS] Yearly veterinary check-up | HIGH | at least once a year | 30 min (estimate) | Dog Owner's Guide, 'Yearly veterinary visit'
[PASS] Toilet breaks at the same times each day | MEDIUM | 10 min (estimate) | Dog Owner's Guide, 'Toilet routine'
[PASS] Short training session | MEDIUM | five minutes a day | 5 min (from source) | Dog Owner's Guide, 'Training and play'
[PASS] Play fetch or with toys | MEDIUM | a few times a day | 10 min (estimate) | Dog Owner's Guide, 'Training and play'
[PASS] Brush Biscuit's teeth | MEDIUM | ideally daily | 5 min (estimate) | Puppy Care Guide, 'Brushing a puppy's teeth'
Not suggested (medication): dog-vaccination-puppy, dog-worming-puppy, dog-heartworm
Plan: 08:00 Feed (10) | 08:10 Walk (15) | 08:25 Yearly check-up (30) | 08:55 Training (5) | 09:00 Teeth (5) | 09:05 Toilet (10) | 09:15 Play (10)
Total 85 of 90 minutes | Verifier: plan checks out
```

*7. Rex, adult dog (about 6 years)*

```text
Life stage: adult | 8 passages cleared the cut-off; best score 0.59
  0.59  Dog Owner's Guide (Humane Fort Wayne), 'Training and play'
  0.57  Puppy Care Guide, 'Heartworm prevention'
  0.54  Dog Owner's Guide (Humane Fort Wayne), 'Toilet routine'
Model proposals: 5 | PASS 5, DECLINE 0, ESCALATE 0
[PASS] Two 15-minute walks with time to sniff | MEDIUM | two walks a day | 30 min (from source) | Dog Owner's Guide, 'Daily walks'
[PASS] Short home training session | MEDIUM | five minutes a day | 5 min (from source) | Dog Owner's Guide, 'Training and play'
[PASS] Play fetch or play with toys | MEDIUM | a few times a day | 10 min (estimate) | Dog Owner's Guide, 'Training and play'
[PASS] Toilet breaks at the same times each day | MEDIUM | 10 min (estimate) | Dog Owner's Guide, 'Toilet routine'
[PASS] Yearly veterinary check-up | HIGH | at least once a year | 30 min (estimate) | Dog Owner's Guide, 'Yearly veterinary visit'
Not suggested (medication): dog-vaccination-adult, dog-heartworm
Plan: 08:00 Yearly check-up (30) | 08:30 Training (5) | 08:35 Play (10) | 08:45 Toilet (10) | 08:55 Walks (30)
Total 85 of 90 minutes | Verifier: plan checks out
```

*8. Pip, kitten (cat, about 3 months)*

```text
Life stage: kitten | 13 passages cleared the cut-off; best score 0.71
Model proposals: 11 | PASS 10, DECLINE 1, ESCALATE 0
[PASS] Feed Pip small kitten meals | HIGH | four or more small meals a day, falling to three by 3-4 months and two by 6 months | 8 min (estimate) | Encyclopedia of Cats, 'Feeding kittens'
[PASS] Short training session | MEDIUM | every day | 15 min (from source) | Understanding, Caring for & Training Your Cat, 'Kitten training sessions'
[PASS] Veterinary fecal exam for Pip | MEDIUM | 2-4 times in the first year | 10 min (estimate) | AAFP-AAHA Guidelines, 'Fecal examination, kitten'
[PASS] Veterinary wellness exam | HIGH | at least once a year | 20 min (estimate) | AAFP-AAHA Guidelines, 'Wellness examinations'
(six more PASS: litter box, drinking water, bowls, play, litter tray wash, teeth)
[DECLINE] Check weight and body condition | MEDIUM | no frequency | 2 min (estimate) | The source gives no frequency for this task.
Not suggested (medication): cat-parasite-control, cat-vaccination, cat-kitten-vet-visits
Plan: 10 tasks, 88 of 90 minutes | Verifier: plan checks out
```

*9. Old Tom, senior cat (about 12 years)*

```text
Life stage: senior | 12 passages cleared the cut-off; best score 0.72
Model proposals: 10 | PASS 9, DECLINE 1, ESCALATE 0
[PASS] Senior veterinary wellness visit | HIGH | twice a year | 60 min (estimate) | Cornell, 'Senior cat veterinary visits'
[PASS] Veterinary fecal exam | MEDIUM | 1-2 times a year, depending on health and lifestyle | 15 min (estimate) | AAFP-AAHA Guidelines, 'Fecal examination, adult and older'
(seven more PASS: litter box, meals, drinking water, bowls, play, litter tray wash, teeth)
[DECLINE] Check weight and body condition | MEDIUM | no frequency | 5 min (estimate) | The source gives no frequency for this task.
Not suggested (medication): cat-parasite-control, cat-vaccination
Plan: 08:00 water (2) | 08:02 litter box (5) | 08:07 meals (5) | 08:12 senior wellness visit (60) | 09:12 bowls (5) | 09:17 teeth (5)
Skipped: play sessions, litter tray wash, fecal exam ("medium priority, but not enough time left after higher-priority tasks")
Total 82 of 90 minutes | Verifier: plan checks out
```

What these four runs show, compared with sample 5 (adult cat): the retrieved passages and the proposals change with species and life stage. Dogs get dog sources and no cat tasks. The kitten gets four-plus meals a day and a 15-minute training session taken from a source. The puppy walk now passes, with a note to check with a veterinarian first. In every run the medication claims were withheld and the vet note was shown, and the only decline was the weight check. For Old Tom, the 60-minute senior visit used most of the day's time, so the scheduler skipped three medium-priority tasks and explained why. The verifier reported "plan checks out" because it flags only skipped HIGH-priority tasks. Yearly and twice-yearly vet visits are placed in today's plan as one-off tasks, because the scheduler knows only once, daily and weekly.

**10. Tasks from the model's own knowledge, live model.** Mochi, an adult cat, run 2, from `python evaluate.py --show` on 2026-11-17. Two of the twelve proposals came from the model's own knowledge (UNSOURCED). They carry no source, are shown in their own section in the app, and are never ticked or added without the owner. The sourced tasks and the declined weight check behave as before.

```text
Mochi (cat, adult)           run 2: proposals=12  PASS=9 ESCALATE=0 UNSOURCED=2 DECLINE=1 REMOVED=0
    [PASS] Veterinary wellness exam | HIGH | at least once a year | 45 min
    [PASS] Veterinary fecal exam | MEDIUM | 1-2 times a year, depending on health and lifestyle | 15 min
    (seven more PASS: litter tray, bowls, play, litter box, meals, water, teeth)
    [UNSOURCED] Brush Mochi's coat | LOW | weekly | 10 min
        - From the AI's general knowledge, not from your documents. Nothing here was checked against a source.
    [UNSOURCED] Offer enrichment (puzzle feeder or new scratching/climbing spot) | LOW | daily | 10 min
        - From the AI's general knowledge, not from your documents. Nothing here was checked against a source.
    [DECLINE] Check weight and body condition | MEDIUM | no frequency | 5 min
        - The source gives no frequency for this task.
```

## Design decisions

- **Retrieval plus a compliance check, not a free-form AI answer.** The model may only choose from claims taken from the documents, and each claim holds the source's own quotes. This makes errors detectable. The trade-off is that the system can only suggest what the documents support, so coverage is limited.
- **Frequency and priority must match the source; duration may be an estimate.** Sources rarely give minutes. Where one does ("two 15-minute walks", "five minutes of training"), that figure is used. Otherwise the model estimates within the owner's daily time and the owner can edit it. The trade-off is that an estimated duration is not backed by a source.
- **Priority comes from the source's wording.** Wording that says a task is needed for health maps to HIGH, recommended to MEDIUM, optional to LOW. This mapping is the project's own rule, not the sources', and it is listed as an assumption.
- **Medication is never suggested.** Vaccination, worming and treatments are vet decisions. They are kept out of the suggestions entirely, and the owner sees a standing note to ask their veterinarian.
- **A failed check goes to the owner, not an automatic retry.** The owner sees the reason and decides. A retry could push the model to bend its answer until it passes. The trade-off is more review work for the owner.
- **Human approval for every task.** Nothing is added to a pet without a tick.
- **Two tiers of suggestion.** Sourced tasks are verified against the documents and can pass. The model may also propose up to three tasks from its own general knowledge (for example enrichment or grooming). These get the status UNSOURCED, which can never pass: they are shown in their own section, labeled "AI general knowledge, no source", unticked by default, and carry the suffix "[AI suggestion, no source]" once added. The checks that need no source still apply: no medication, never HIGH priority, daily or weekly only, and minutes within the owner's time. This relaxes the earlier rule that every suggestion must cite a document, so the evidence that the system follows its sources applies to the first tier only.
- **Birth date, not age.** Age is computed, so life-stage changes are noticed automatically. This needs pets saved to disk.
- **Pets are identified by name and species.** A cat and a dog can both be called Mochi.
- **No fake model anywhere.** The checks are tested by handing them hand-written inputs and proposals, and the model is evaluated only by running the real pipeline against the real model. The trade-off is that evaluating the model costs money and its results vary from run to run, and the paths for a model refusal or outage are not covered by automated tests.

Known limits: cats are covered by four sources and dogs by two weaker ones (a retailer brochure and a shelter handout), none from a veterinary body for dogs. Dogs have only puppy and adult stages (12 months), with no size or breed. Other species are declined. A life-stage change shows only when the app is opened. The medication filter is a keyword list.

## Testing summary

**What worked**
- **163 tests pass** in the project's `.venv`, and none of them calls a model or uses a fake one. They are: the 54 original scheduler tests; 37 direct tests of the system's controls in `tests/test_controls.py` (bad input, species with no documents, wrong frequency, wrong priority, invented claim, claim for the wrong life stage, fabricated quote, duration longer than the owner's time, medication wording, duplicates, durations stated by a source, and the rules for tasks from the model's own knowledge); 11 UI-flow tests using Streamlit's test runner; and 61 unit tests for the knowledge base, retriever, life stages, guardrails, response parsing, key loading, storage and the plan verifier.
- **The tests can fail.** Replacing the compliance check with one that approves everything made 11 of the 29 control tests fail. Breaking the step-gating in the app made 2 UI tests fail. The post-add UI test fails on the earlier buggy code.
- **Every knowledge-base quote is checked** against the source PDFs: 59 of 59 found.
- Building the knowledge base caught real mistakes: the loader refuses a claim whose quote is not in its own passage, and it rejected several first drafts of the documents.
- **Live model, recorded runs (2026-11-16, real model, `evaluate.py`).** Across 8 cat runs (kitten, junior, adult and senior, two runs each) the model made 82 proposals: 74 passed (90%), 8 were declined, none were escalated or removed. All 8 declines were the same task, "Check weight and body condition", which no source gives a frequency for. After the puppy-walk fix, the two dog runs (a puppy and an adult) made 12 proposals and all 12 passed. No model errors and no broken system rules were recorded. That is 10 runs on 6 pet profiles on one day, which is a small sample. The model's own minute estimates varied between runs (for example the yearly wellness exam ranged from 15 to 45 minutes).

### Results table

Every row can be read without running the app. Part A is reproducible with `python -m pytest` (no model, no cost). Part B comes from `python evaluate.py` against the real model and varies from run to run. The latest single run is saved to `eval_results/latest.json`.

**A. Direct tests of the system's controls** (`tests/test_controls.py`, 37 tests, 29 run on 2026-11-17 before the unsourced tier was added; all 37 pass now)

| Test input | Evaluation criteria | Result |
|---|---|---|
| Species with no documents (rabbit) | Declined before the model is called, with a "no care guidance" message | Pass |
| Birth date in the future | Declined before the model, message mentions "future" | Pass |
| Missing birth date | Declined before the model, message asks for the birth date | Pass |
| Blank pet name | Declined before the model, message asks for a name | Pass |
| Medication claims (vaccination, worming, heartworm) | Never offered to the model or to the owner | Pass |
| Pet of each life stage | Only claims for that species and stage are offered to the model | Pass |
| Correct proposal for each of 7 claims (litter, water, litter-tray wash, kitten feeding, senior vet visit, puppy walk, adult walk) | Status PASS | Pass (7 of 7) |
| Weekly task proposed as weekly | Cadence kept | Pass |
| Frequency that disagrees with the source | DECLINE | Pass |
| Priority that disagrees with the source | DECLINE | Pass |
| Claim whose source states no frequency | DECLINE | Pass |
| Bowl washing proposed with the wrong frequency | DECLINE | Pass |
| Invented claim id | ESCALATE to the owner | Pass |
| Claim written for another life stage | ESCALATE to the owner | Pass |
| Quote that is not in the source | ESCALATE to the owner | Pass |
| Duration longer than the owner's available time | ESCALATE to the owner | Pass |
| Non-numeric duration | ESCALATE to the owner | Pass |
| Proposal with medication wording | Removed from suggestions, not shown | Pass |
| Same claim proposed twice | Second one ignored | Pass |
| Model's minutes differ from a source's stated minutes | Source minutes used | Pass |
| Source duration longer than the owner's time | ESCALATE to the owner | Pass |
| Dog training / kitten training | Source minutes used (5 / 15) | Pass |
| Task from the model's own knowledge | Shown apart with status UNSOURCED, never PASS | Pass |
| Own-knowledge task about medication | Removed, not shown | Pass |
| Own-knowledge task with HIGH priority, `other` frequency, or minutes over the owner's time | Declined | Pass |
| Four or more own-knowledge tasks, or a repeated title | Only the first three distinct ones kept | Pass |
| Own-knowledge task added to a pet | Title carries "[AI suggestion, no source]" | Pass |

**B. Live model runs** (`evaluate.py`, real model `claude-opus-5-5`, 2026-11-16)

| Pet profile | Runs | Proposals | PASS | DECLINE | ESCALATE | REMOVED | Rule broken | Result |
|---|---|---|---|---|---|---|---|---|
| Cats: kitten, junior, adult, senior (two runs each) | 8 | 82 | 74 (90%) | 8 | 0 | 0 | 0 | Pass: every decline was the weight-check task, which no source gives a frequency for |
| Biscuit, puppy (after the walk fix) | 1 | 7 | 7 | 0 | 0 | 0 | 0 | Pass |
| Rex, adult dog | 1 | 5 | 5 | 0 | 0 | 0 | 0 | Pass |
| Biscuit, puppy (before the fix) | 1 | not recorded | not recorded | 0 | 0 | 1 | 0 | **Fail**: the puppy walk was removed as medication because its title contained "vaccination". Fixed, with a regression test |
| End-to-end `demo.py`, 2026-11-17: Mochi (adult cat), Biscuit (puppy), Rex (adult dog), Pip (kitten), Old Tom (senior cat) | 5 | 10 + 7 + 5 + 11 + 10 = 43 | 9 + 7 + 5 + 10 + 9 = 40 | 3 | 0 | 0 | 0 | Pass: each plan passed the verifier; every decline was the weight check |
| **Full `evaluate.py --show` after the unsourced tier was added** (6 pet profiles, 2 runs each, 2026-11-17) | 12 | 119 | 98 (82%) | 8 | 0 | 0 (0 REMOVED) | 0 | Pass: 0 model errors, 0 broken rules. 13 UNSOURCED (11%), all LOW priority, none about medication. All 8 declines were the weight check |
| Model errors, all runs | 27 | | | | | | | 0 errors |

Rows under B count only runs whose output was seen. The per-profile cat figures are not split out because only the aggregate was kept.

**Unsourced tier, from that run.** The model proposed 13 tasks from its own knowledge across 12 runs (1 in 9 runs, 2 in 2 runs, none in 1 run; the limit is 3). Every one was LOW priority, weekly or daily, and none involved medication, so none was declined or removed. They were almost all grooming or handling: gentle coat brushing (cats, senior cats), "gentle handling practice (paws, ears, coat)" for the kitten and the puppy, "brush coat and check paws" for the adult dog, and, in the two runs with two extras, an enrichment idea (a puzzle feeder or a new scratching or climbing spot) for Mochi and a check that Old Tom's resting spots are warm, soft and easy to reach. None was added to a pet without a tick. This is 12 runs on one day, so the pattern may not hold. Of the 106 sourced proposals, 98 passed and the 8 that did not were the weight check.

**C. App flow** (`tests/test_app_flow.py`, 11 tests with Streamlit's test runner: 11 pass). Checked: the app opens on step 1 and cannot continue without a pet, adding a pet shows its life stage and unlocks the next step, a cat and a dog both named Mochi can be added, Back and Next move between steps, suggest then tick then add then schedule works end to end, a missing API key shows a message instead of a crash, Select all and Clear work, a pet can be removed, Refresh returns to the start and keeps the saved data, and tasks from the model's own knowledge are shown unticked and are added only when ticked.

**What did not work**
- **The retrieval confidence cut-off.** The first value (0.30) was a guess and would have rejected a valid vet-visit question. It was changed to 0.225 using 16 measured queries, which separated cleanly while only cat documents existed. After the dog documents were added, answerable and unanswerable questions overlapped (lowest answerable 0.180, highest unanswerable 0.410). A keyword score cannot reliably tell covered questions from uncovered ones. In this app the species and life-stage filters do the real work, because the owner never types free text. A better gate (embeddings, or requiring a claim match) would be needed for free-text questions.




## Reflection

I used AI in this project as a design partner, not as the builder. It suggested extending PawPal+ with a retrieval-augmented care advisor, an agent loop, and a reliability test harness. I chose that direction because it builds on the scheduler I already wrote. When the AI started setting up code before we had agreed on a design, I stopped it and asked to work through the project together. That decision shaped the rest of the work: we moved one step at a time, and I made each design choice myself.

I accepted the AI’s human-in-the-loop design. The system proposes care tasks from retrieved guidelines, each with a source, and nothing is added to a pet until I approve it. This matches a rule from my Module 2 project, where the scheduler warns about conflicts but never moves a task on its own. In both projects the AI can suggest, and the owner decides. 
The system has real limitations. It only knows what is in its knowledge base, so its advice is only as good as the content I review, and it is not a substitute for a veterinarian. Retrieval can miss relevant guidance or return the wrong passage, so the system is designed to decline instead of guessing, and I have to test whether it does. It refuses medication and dosage questions, and it covers only the species I include. My tests cover only the cases I thought of, so a passing score shows that those cases work, not that the system is always right. 

The main lesson is that AI can produce plans and code quickly, but it does not know what is correct for my project. My job is to decide the design, check the output against the requirements, and test where it fails.

