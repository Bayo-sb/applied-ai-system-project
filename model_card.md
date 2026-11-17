# PawPal+ Care Advisor: Model Card and Reflection

PawPal+ suggests daily care tasks for a cat or dog. It looks up care documents, asks a language model (Claude, `claude-opus-5-5`) to propose tasks from them, checks every proposal against the documents, and adds nothing to a pet until I approve it. The model may also add up to three ideas from its own knowledge, which are labeled as having no source and are never ticked for me. It gives general care guidance, not veterinary advice.

## 1. Limitations and biases

**The advice is only as good as my documents, and the extra ideas have no source at all.** Sourced tasks come only from the knowledge base, and I chose and reviewed those documents. The up-to-three extra tasks come from the model's own knowledge. Nothing verifies their content, so they carry the model's own biases, for example toward common breeds and typical households. I limit them to daily or weekly, MEDIUM or LOW priority, and no medication, and I label them, but I cannot check that the advice is right. Cats are covered by four sources, two of them from veterinary bodies (the AAFP-AAHA life stage guidelines and Cornell). Dogs are covered by two weaker sources: a retailer's puppy guide from Australia and a shelter's adoption handout from the USA. No dog source comes from a veterinary body. So the dog advice is less trustworthy than the cat advice, and the system does not show that difference to the owner. Both sets of sources also come from specific countries and are written for typical pets, so they carry that bias with them.

**Only cats and dogs, and dogs are simplified.** Any other species is declined. Dogs have two life stages, puppy and adult at 12 months, with no size or breed. A Chihuahua and a Great Dane are treated the same, even though they age differently. Cat stages come from a source table, but they depend on a birth date, and an approximate birth date shifts the stage.

**The retrieval check is weak.** I set the confidence cut-off at 0.225 after measuring 16 queries, and it separated them cleanly. After I added the dog documents it stopped working: the lowest answerable question scored 0.180 and the highest unanswerable one scored 0.410. A keyword score cannot reliably tell a covered question from an uncovered one. In this app the species and life-stage filters do the real work, because the owner never types free text. If I added free-text questions, I would need a better check.

**The minutes are mostly the model's guess.** Only a few tasks have a duration stated in a source (dog walks, dog training, kitten training). For the rest, the model estimates, and the estimates change from run to run. The yearly wellness exam came back as anything from 15 to 45 minutes. The priorities (HIGH, MEDIUM, LOW) are my own mapping of the sources' words "essential", "recommended" and "optional", so they are my judgment, not the sources'.

**The scheduler cannot do yearly tasks.** It only knows once, daily and weekly. A yearly vet visit becomes a one-off task and lands on whatever day I plan. In Old Tom's run, the 60-minute senior visit used most of the day and three medium-priority tasks were skipped. The verifier said the plan was fine, because it only flags skipped HIGH tasks.

**The medication filter is a keyword list.** It catches the words I thought of. A task described in unusual words could get past it.

**My testing is small.** The live evaluation is 27 recorded runs on 6 pet profiles, over two days, and the newest 12 are the only ones that include the extra own-knowledge tasks. The 163 tests cover the cases I thought of. The paths where the model refuses or the service is down are not covered by automated tests. A passing score shows that those cases work, not that the system is always right.

## 2. Could the AI be misused, and how do I prevent it?

**The main risk is someone treating it as a veterinarian.** An owner could use a clean daily plan as a reason to skip a vet visit, or ask the system for a dose. I handled the medication part directly. Vaccination, worming, heartworm and other medication are never suggested and are never sent to the model. The owner always sees a note to ask their veterinarian. If the model proposes something that mentions medication anyway, it is removed and not shown. Medication stays out because it is a one-time decision for a vet, not a daily care task.

**A made-up source.** A language model can invent a citation or a quote. Every sourced proposal has to name a claim from the documents and quote it, and the check refuses a quote that is not in that passage. A task from the model's own knowledge makes no such claim, so it is never marked as passed and always shows that it has no source. Every quote in the knowledge base was also checked against the source PDFs (59 of 59 found). In the demo, a fabricated quote is escalated to the owner with the reason, not accepted quietly.

**The extra ideas.** The model's own-knowledge tasks are the part with the least protection, so they have the strictest limits. They can never pass the check, cannot be HIGH priority, cannot be about medication, and must be daily or weekly. They are shown in their own section, unticked, and carry "[AI suggestion, no source]" if I add one. In the 12-run live test, all 13 of them were LOW priority and none touched medication, so the limits were never needed. That does not show that they could not be, so the rules are also tested directly with hand-written proposals. A wrong but harmless idea (for example a grooming tip that does not suit a breed) can still get through, because nothing checks it. The label and the owner's tick are the protection, not a check of the content.

**The AI acting on its own.** Nothing is added to a pet without a tick from the owner. A task that failed a check can still be added by the owner, but it is labeled "[failed check, owner override]" so it is not mistaken for a checked one. A task whose frequency or priority is not supported by its source is declined, and the owner cannot add it.

**Secrets and private data.** The API key lives only in an ignored `.env` file and is never printed or saved in a result. The saved pet data is also ignored by git. The source PDFs are copyrighted, so they are not committed.

**What I have not covered.** The pet's name is passed to the model, and I only check its length. I have not tested whether a name written as an instruction could change the model's behavior. The checks after the model would still catch a bad proposal, but I have not proven that. I would also want a clearer warning in the app that this is general guidance, because a person who is worried about a sick animal may over-trust a confident-looking plan.

## 3. What surprised me while testing reliability

**A real bug showed up only on the live model.** In one live run, the puppy walk was removed as "medication". The cause was that the task's title contained the word "vaccination" ("check with your veterinarian about vaccination first"), and my keyword filter removed it. No test I had written would have found this, because I had not written a test with that title. I reworded the task, added a regression test, and checked that the test fails on the old title. The next puppy run passed all 7 proposals.

**My own scoring was wrong, not the system.** The evaluation script first reported "BROKEN RULES: passing tasks add up to 137 min, over 90". I was adding yearly and weekly tasks to the daily budget. Only daily tasks use up a day's time. I fixed the script and added a test. It was a reminder that the thing measuring the system can be wrong too.

**One task was declined every time.** "Check weight and body condition" was declined in every cat run, because no source gives it a frequency. I first read this as a flaw. It is the compliance check doing its job: the model proposed a task, and the documents did not support how often to do it. I decided to keep it visible because it is honest evidence.

**The retrieval check stopped separating after I added documents.** It worked on cats alone and broke once dogs were added. That was a good lesson: a threshold measured on a small set can fail when the data changes, and I should say so instead of quietly keeping a number that looked fine.

**Writing the knowledge base caught my own mistakes.** My loader refuses a claim whose quote is not in its own passage, and it rejected several of my first drafts. I had paraphrased from memory instead of copying the words.

**The model's results were more consistent than I expected.** Across the live runs, 40 of 43 proposals in the end-to-end demos and 74 of 82 in the earlier cat runs passed, and every decline was the weight check. In the full 12-run test after I added the extra tier, 98 of 119 proposals passed and the 8 declines were again only the weight check. That is a small sample, so I do not treat it as proof.

**The model used the extra tier lightly.** I allowed up to three own-knowledge tasks and expected it to use most of them. It added 13 in 12 runs (never more than 2 in a run, and none in one run), and they were mostly gentle brushing or handling practice, with an enrichment idea and a check on a senior cat's resting spots in the runs that had two. They were reasonable, but I cannot say they are right for any particular pet. The strongest sign that the design held was that they were the same kind of low-risk tip every time, not that a rule caught anything.

## 4. Collaboration with AI

I used the AI as a design partner and a fast builder, and I kept the design decisions myself. I asked it to work one step at a time, and I changed direction when its plan did not fit.

**A suggestion I accepted: escalate failed checks to the owner.** When I asked what should happen after a failed compliance check, the AI gave two options: retry or drop, or escalate. I chose escalate: the task is shown with its failure reason and the owner decides. I accepted it because it matches the rule I already used in Module 2, where the scheduler warns about conflicts but never moves a task on its own. The AI suggests and the owner decides. It added review work for the owner, and I accepted that cost on purpose.

**A suggestion I did not accept as written: the fake model.** The first plan was an offline, deterministic fake model, so the tests could run without an API key. It sounded sensible, and I built on it for a while. Then I told the AI to remove it, because I was only interested in the live model. My reasoning was that a test that passes against a fake model only shows that my code works with my fake. It says nothing about how the real model behaves. The puppy-walk bug is the proof: only a live run could find it. So I changed the testing in two parts. The checks (guardrails, compliance, medication removal, durations) are tested directly with hand-written inputs, with no model involved. The model itself is measured only by running it live and scoring what comes back. The cost is that evaluating the model costs money and varies from run to run.

**Another change I made: medication.** The AI first treated medication as tasks to be sent to a human, with the owner entering the minutes. I corrected it: vaccination and medication are one-time decisions, and should not be part of a daily plan from the AI at all. The final rule is that they are never suggested, and a standing note tells the owner to ask their vet.

**A suggestion I accepted again: two tiers for the model's own knowledge.** I wanted the model to add its own knowledge, not only what is in my documents, while keeping the compliance check and the guardrails. The AI recommended keeping the check as it was and adding a separate tier: up to three tasks labeled "no source", never passed by the check, never ticked for me, never HIGH priority or about medication. I accepted it because it gave me the model's knowledge without removing the evidence that the system follows its sources. It also meant I had to change what the README and this card claim, because "every task is cited" was no longer true.

**What I learned.** AI can write code and plans quickly, but it does not know what is correct for my project. It often built what I asked for, not what the requirements needed, and I had to read its output, run it, and check it against the rules. The best results came when I gave it something specific to check against. The design decisions stayed mine: what the system may suggest, what it must never suggest, and when a person decides.
