# 0082. A section's facts are counted from the score, its pattern is its most typical bar, and its guess says only what the score shows

- **Status:** Proposed
- **Date:** 2026-11-12

- `analyze/facts.py` gives each section, from the score and the parts the drums give its notes ([ADR 0047](0047-roles-come-from-canonical-families-and-the-score.md)):
  - its `label`, with bars counted from 1, its `meter` and its lowest and highest `bpm`;
  - its notes, and per bar, each family's notes, per bar, soft and accents, and the hit types, with the notes whose type is a guess;
  - `riding`, the cymbal family with the most rider hits, when they number at least half the section's beats;
  - `half_time`, when at least three quarters of its 4/4 bars with a snare not typed soft on a beat have it on beat 3 and not on 2 or 4, and none when no bar has;
  - `double_kick`, its double kick notes, and `fill_bars`, `empty_bars` and `ambiguous_bars`;
  - `plays`, the most telling of these in words, such as "crash riding, half-time, 34 soft snare notes".
- A note counts in the bar it is heard in: its tick's, or for a grace, its main's.
- `pattern` is the section's most typical bar, the one with hits most alike the section's others ([ADR 0036](0036-a-bar-is-its-onset-pattern-in-each-family.md)), and `ends` its last bar with hits when that is less than 0.8 alike it, as a fill is. A bar is a row per family, from the cymbals down to the kick, with the hat pedal a row of its own, and a column per step of the simplest grid that puts every hit on one: 16ths, 8th triplets, 16th triplets, 32nds, or 12 or 24 to a quarter. Beats are a space apart, and `X` is an accent, `x` a normal hit, `o` a soft one and `.` none. Graces are left out.
- `guess` is a `kind`, a `confidence` and what it `says`:
  - `silent`, at high confidence, for a section with no hits;
  - `repeat`, for a section after the first of its repeat group, at high confidence when its bars are at least 0.95 alike the first's and medium otherwise, saying it can take the first's controls;
  - `fill`, at medium confidence, for a section of 2 bars or fewer at least half of whose hits are fills;
  - otherwise `groove`, at low confidence, saying how hard it plays isn't readable from its notes.
- `questions` follow the plan's question policy: for a groove, its energy, and whether its soft notes should be more present when it has any, or else whether it should be steadier or groovier when a cymbal rides; for a fill, how hard it should hit; for the last repeat of a group, whether it plays the same or bigger. A silent section and any other repeat ask nothing.

**Why:** Energy isn't readable from note density, so no fact or guess says how hard a section plays, and each guess is one the score shows. Counting by the bar a note is heard in matches the bar patterns the sections were found from. The facts and the guess only help the agent ask, and no render reads them, so their thresholds decide nothing about how the output sounds.

**Consequences:** The thresholds are set by reading, not measured, and the skill's check of about 30 answers can revise them.
