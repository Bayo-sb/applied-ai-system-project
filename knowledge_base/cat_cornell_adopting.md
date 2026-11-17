# Cat care: Cornell Feline Health Center handout

General guidance, not veterinary advice.

Species: cat
Stages: all

## Source

- Title: "What to Expect When Adopting a Feline Friend" (2-page handout)
- Author: Cornell Feline Health Center, Cornell University College of Veterinary Medicine
- Local copy: `assets/cornell-adopting-a-feline-friend.pdf` (not committed to the repository)
- Quotes are short exact phrases. The rest is written in my own words.

## Litter box cleaning

The handout says litter boxes are important to cat health and behaviour and that the quantity and cleanliness of litter boxes matters: "Another important thing to keep in mind is the quantity and cleanliness of litterboxes". It states a minimum cleaning frequency: "Litterboxes should be cleaned at least once a day". It also advises one litter box per cat plus one extra.

```claim
id: cat-litter-daily
task: Clean the litter box
cadence: daily
cadence_text: at least once a day
cadence_quote: Litterboxes should be cleaned at least once a day
importance: essential
importance_quote: Another important thing to keep in mind is the quantity and cleanliness of litterboxes
medication: no
```

## Senior cat veterinary visits

Stages: senior, geriatric

The handout says cats face a higher risk of several health problems as they age: "they face an increased risk of several health problems". For seniors it advises more frequent vet visits: "they should visit the veterinarian twice yearly". The handout counts a cat as a senior from age 10. The AAFP-AAHA stages used by this system start Senior at 11 years, so this passage is applied from 11 years only.

```claim
id: cat-vet-senior-twice-yearly
task: Veterinary wellness visit (senior cat)
cadence: other
cadence_text: twice a year
cadence_quote: they should visit the veterinarian twice yearly
importance: essential
importance_quote: they face an increased risk of several health problems
medication: no
```

## Kitten veterinary visits

Stages: kitten

Kittens should have a first vet visit at about six weeks, then return for examinations and vaccinations at short intervals until the first vaccine series is complete at about 16 weeks: "approximately two to three-week intervals". The handout calls vaccination "this crucial aspect of your cat's health care plan". This task involves vaccination, so it always goes to a human and the system states no product or dose.

```claim
id: cat-kitten-vet-visits
task: Kitten veterinary visits (ask your veterinarian about vaccinations)
cadence: other
cadence_text: every two to three weeks until about 16 weeks of age
cadence_quote: approximately two to three-week intervals
importance: essential
importance_quote: crucial aspect of your cat
medication: yes
```
