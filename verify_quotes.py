"""Checks that the short quotes in the knowledge base really appear in the source PDFs.

Run: python verify_quotes.py   (needs `pdftotext` and the PDFs in assets/, which are not committed)
Quotes are matched after lowercasing and collapsing whitespace. Two-column layouts can break a
quote across columns in the extracted text, so a miss means "check this by eye", not "wrong".
"""

import re
import subprocess
from pathlib import Path

from knowledge_base import load_knowledge_base, normalize

ROOT = Path(__file__).resolve().parent
PDFS = {
    "cat_cornell_adopting": "cornell-adopting-a-feline-friend.pdf",
    "cat_aafp_aaha_life_stage": "aaha-aafp-feline-life-stage-guidelines.pdf",
    "dog_puppy_care_guide": "498223126-Puppy-Care-Guide.pdf",
    "dog_owners_guide_humane_fort_wayne": "Dog-Book.pdf",
    "cat_brough_understanding_caring": "Understanding-Caring-for-and-Training-Your-Cat.pdf",
    "cat_edwards_encyclopedia": "909417662-The-Ultimate-Encyclopedia-of-Cats-Cat-Breeds-Cat-Care-a-Alan-Edwards.pdf",
}


def pdf_text(name: str) -> str:
    out = subprocess.run(["pdftotext", str(ROOT / "assets" / name), "-"], capture_output=True, text=True, check=True)
    return normalize(re.sub(r"/\s+", "/", re.sub(r"-\n", "-", out.stdout)))


if __name__ == "__main__":
    kb = load_knowledge_base()
    cache, missing, total = {}, 0, 0
    for claim in kb.claims.values():
        stem = claim.passage_id.split("#")[0]
        if stem not in PDFS:
            continue
        cache.setdefault(stem, pdf_text(PDFS[stem]))
        for label, quote in (("cadence", claim.cadence_quote), ("importance", claim.importance_quote), ("duration", claim.duration_quote)):
            if not quote:
                continue
            total += 1
            if normalize(quote) not in cache[stem]:
                missing += 1
                print(f"NOT FOUND  {claim.id} {label}: {quote}")
    print(f"\n{total - missing}/{total} quotes found in the source PDFs.")
