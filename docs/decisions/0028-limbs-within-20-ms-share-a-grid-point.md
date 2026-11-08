# 0028. Hits on different drums within 20 ms, or half a 32nd at a fast tempo, share one grid point

- **Status:** Proposed
- **Date:** 2026-11-08

- Before grids are chosen, the hits that aren't graces are gathered into onsets in time order. A hit joins the current onset when it is within the limb window of the onset's first hit and on a drum the onset doesn't have yet, or under 5 ms after that drum's hit in it ([ADR 0027](0027-hits-on-one-drum-under-45-ms-apart-are-a-grace-and-its-main.md)). Otherwise it starts a new onset.
- The window is 20 ms, or half a 32nd at the local tempo when that is shorter: 18.75 ms at 200 BPM and 15 ms at 250 BPM.
- An onset's time is the mean of its hits'. Grids are scored on onsets, each onset goes to one grid point, and every hit of it takes that tick, keeping its own offset in the score.

**Why:** Limbs played together spread over several milliseconds, so snapping each hit on its own can split a unison across two grid points when it sits near the middle between them. 20 ms is about twice the spread of a tight unison, which the plan keeps at or below about 10 ms in what it renders, and half a 32nd keeps two drums a 32nd apart from merging at fast tempos. Scoring onsets counts a unison of several limbs once, so it doesn't outweigh a single note when grids are compared.

**Consequences:** Two drums played on purpose under 20 ms apart, as in a flam across two drums, go to one grid point and keep their gap only in their offsets.
