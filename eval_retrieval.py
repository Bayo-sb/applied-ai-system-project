"""Measures retriever scores on questions the documents answer and ones they do not.

Run: python eval_retrieval.py
Use the output to set CONFIDENCE_THRESHOLD in retriever.py. Scores depend on the documents,
so rerun this whenever the knowledge base changes.
"""

from knowledge_base import load_knowledge_base
from retriever import CONFIDENCE_THRESHOLD, retrieve

ANSWERABLE = [
    "how often to feed an adult cat meals",
    "how often should I clean the litter box",
    "fresh water for my cat each day",
    "how often should a cat visit the veterinarian for a wellness exam",
    "brushing my cat's teeth",
    "kitten feeding meals per day",
    "fecal exam parasite testing frequency",
    "checking my cat's weight and body condition",
    "how long should a puppy walk each day",
    "brushing my puppy's teeth daily",
    "how many meals a day for a puppy",
    "when does a puppy become an adult dog",
]
NOT_ANSWERABLE = [
    "how to trim a horse's hooves",
    "aquarium filter cleaning schedule",
    "training a parrot to talk",
    "best hamster wheel size",
    "how to groom a poodle's coat",
    "rabbit hutch bedding",
    "teaching a dog to sit and stay",
    "snake terrarium temperature",
]


def best(query: str) -> float:
    kb = load_knowledge_base()
    cats = (("cat", s) for s in ("kitten", "adult", "senior"))
    dogs = (("dog", s) for s in ("puppy", "adult"))
    return max(retrieve(kb, sp, stage, query).best_score for sp, stage in (*cats, *dogs))


if __name__ == "__main__":
    ans = [(q, best(q)) for q in ANSWERABLE]
    non = [(q, best(q)) for q in NOT_ANSWERABLE]
    print(f"Current cut-off: {CONFIDENCE_THRESHOLD}\n\nANSWERABLE (cat and dog)")
    for q, s in ans:
        print(f"  {s:.3f}  {q}")
    print("\nNOT ANSWERABLE")
    for q, s in non:
        print(f"  {s:.3f}  {q}")
    lo, hi = min(s for _, s in ans), max(s for _, s in non)
    print(f"\nlowest answerable = {lo:.3f}, highest unanswerable = {hi:.3f}")
    print("A cut-off between these separates the two sets." if lo > hi else "The sets overlap: no cut-off separates them.")
