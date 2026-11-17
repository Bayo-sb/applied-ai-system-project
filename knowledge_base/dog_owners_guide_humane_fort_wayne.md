# Dog care: Dog Owner's Guide (Humane Fort Wayne)

General guidance, not veterinary advice.

Species: dog
Stages: all

## Source

- Title: "Dog Owner's Guide"
- Author: Humane Fort Wayne (animal shelter and clinic, Indiana, USA), 28-page adoption handout, 2021
- Local copy: `assets/Dog-Book.pdf` (not committed to the repository)
- A shelter's guide for new adopters, mostly about settling in and behaviour. Not written by a veterinary body, and some rules are specific to Indiana. Quotes are short exact phrases (one has a typo in the source, kept as printed). The rest is written in my own words.

## Daily walks

Stages: adult

The guide's enrichment section says dogs that get enough exercise are healthier: "Dogs that get enough mental and physical exercise are happier and healthier". It suggests walking, and gives a figure: "Two 15 mintue walks per day can make a huge difference" (spelled so in the source). Together that is 30 minutes a day. Walks should let the dog stop to sniff.

```claim
id: dog-walk-adult
task: Daily walks (two 15-minute walks)
cadence: daily
cadence_text: two walks a day
cadence_quote: walks per day can make a huge difference
importance: recommended
importance_quote: happier and healthier
medication: no
duration_minutes: 30
duration_text: two 15-minute walks
duration_quote: Two 15 mintue walks per day
```

## Training and play

Stages: all

The same section lists training and play as enrichment, for dogs that are "happier and healthier". Training at home is short: "Training your dog at home for five minutes per day". It also suggests "Playing fetch or playing with toys for just a few times per day". It recommends short "(5 minute)" training sessions spread through the day.

```claim
id: dog-training-daily
task: Short training session
cadence: daily
cadence_text: five minutes a day
cadence_quote: Training your dog at home for five minutes per day
importance: recommended
importance_quote: happier and healthier
medication: no
duration_minutes: 5
duration_text: five minutes
duration_quote: five minutes per day
```

```claim
id: dog-play-daily
task: Play with toys or fetch
cadence: daily
cadence_text: a few times a day
cadence_quote: just a few times per day
importance: recommended
importance_quote: happier and healthier
medication: no
```

## Toilet routine

Stages: all

The guide says routine matters for a new dog: "Dogs crave predictability". For toilet breaks it says to "Take your dog out at the same times every day", for example on waking, when you get home and before bed. Puppies need to go out more often, such as after napping, playing and eating.

```claim
id: dog-toilet-routine
task: Take the dog out for toilet breaks
cadence: daily
cadence_text: at the same times every day
cadence_quote: Take your dog out at the same times every day
importance: recommended
importance_quote: Dogs crave predictability
medication: no
```

## Yearly veterinary visit

Stages: all

The guide says a regular vet is important: "Establising a vet for your new dog is essential to keeping your pet happy and healthy" (spelled so in the source). Its adoption contract requires "at least one yearly visit to the vet". The vet checks the dog's overall health and decides on vaccinations and other treatment. This system does not suggest those.

```claim
id: dog-vet-yearly
task: Yearly veterinary check-up
cadence: other
cadence_text: at least once a year
cadence_quote: at least one yearly visit to the vet
importance: essential
importance_quote: essential to keeping your pet happy and healthy
medication: no
```
