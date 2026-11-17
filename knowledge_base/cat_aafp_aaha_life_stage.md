# Cat care: AAFP-AAHA Feline Life Stage Guidelines

General guidance, not veterinary advice.

Species: cat
Stages: all

## Source

- Title: "AAFP-AAHA Feline Life Stage Guidelines"
- Authors: Hoyumpa Vogt A, Rodan I, Brown M, et al. J Am Anim Hosp Assoc 2010; 46:70-85
- Local copy: `assets/aaha-aafp-feline-life-stage-guidelines.pdf` (not committed to the repository)
- Written for veterinarians. Quotes are short exact phrases. The rest is written in my own words.

## Life stage definitions

The guideline defines six feline life stages: kitten (0-6 months), junior (7 months to 2 years), adult (3-6 years), mature (7-10 years), senior (11-14 years) and geriatric (15 years and over). It warns that these are "arbitrary demarcations along a spectrum, and not absolutes".

## Wellness examinations

The guideline supports "a minimum of annual wellness examinations" for all cats, notes that veterinarians often recommend semi-annual exams, and that more frequent exams may be recommended for seniors and geriatrics. It concludes that "preventive veterinary care can improve quality of life" and finds illness earlier.

```claim
id: cat-wellness-annual
task: Veterinary wellness exam
cadence: other
cadence_text: at least once a year
cadence_quote: a minimum of annual wellness examinations
importance: essential
importance_quote: preventive veterinary care can improve quality of life
medication: no
```

## Fecal examination, kitten

Stages: kitten

Kittens should have faecal exams several times in the first year: "Fecal exams 2-4 times during the first year of life". The guideline states: "Parasite control is important in cats of all ages".

```claim
id: cat-fecal-kitten
task: Veterinary fecal exam (kitten)
cadence: other
cadence_text: 2-4 times in the first year
cadence_quote: Fecal exams 2-4 times during the first year of life
importance: recommended
importance_quote: Parasite control is important in cats of all ages
medication: no
```

## Fecal examination, junior

Stages: junior

"Continue fecal exams 1-4 times/year depending on health and lifestyle factors". The guideline states: "Parasite control is important in cats of all ages".

```claim
id: cat-fecal-junior
task: Veterinary fecal exam (junior cat)
cadence: other
cadence_text: 1-4 times a year, depending on health and lifestyle
cadence_quote: Continue fecal exams 1-4 times/year
importance: recommended
importance_quote: Parasite control is important in cats of all ages
medication: no
```

## Fecal examination, adult and older

Stages: adult, mature, senior, geriatric

"Conduct fecal exams 1-2 times/year, depending on health and lifestyle factors". The guideline states: "Parasite control is important in cats of all ages".

```claim
id: cat-fecal-adult
task: Veterinary fecal exam
cadence: other
cadence_text: 1-2 times a year, depending on health and lifestyle
cadence_quote: Conduct fecal exams 1-2 times/year
importance: recommended
importance_quote: Parasite control is important in cats of all ages
medication: no
```

## Parasite control and vaccination

Parasite prevention and vaccination are veterinary treatments. The guideline says "Parasite control is important in cats of all ages" and lists core vaccines, with the schedule to follow current vaccination guidelines. It also gives a kitten deworming schedule: "Deworming every 2 weeks from 3-9 weeks of age". These are medication, so this system always sends them to a human, with the note to ask the veterinarian. It states no product and no dose.

```claim
id: cat-parasite-control
task: Parasite control (ask your veterinarian)
cadence: none
importance: essential
importance_quote: Parasite control is important in cats of all ages
medication: yes
```

```claim
id: cat-vaccination
task: Vaccinations (ask your veterinarian)
cadence: none
importance: recommended
importance_quote: Core vaccines
medication: yes
```

## Weight and body condition

Stages: all

The guideline says regular weight and body condition checks matter at every age: "Regular assessment of weight and body condition score is important in cats of all ages". It gives no frequency.

```claim
id: cat-weight-check
task: Check weight and body condition
cadence: none
importance: recommended
importance_quote: Regular assessment of weight and body condition score is important in cats of all ages
medication: no
```
