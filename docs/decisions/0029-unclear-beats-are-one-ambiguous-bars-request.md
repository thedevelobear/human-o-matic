# 0029. A beat whose grid is unclear keeps its best guess, and all of them are one `ambiguous_bars` request

- **Status:** Proposed
- **Date:** 2026-11-08

- A beat is ambiguous when another grid that applies scores within 6 ms of the chosen one and would put one of its onsets on a different tick, or when an onset is more than 20 ms from its point on the chosen grid ([ADR 0026](0026-a-grid-per-beat-by-timing-error-and-complexity.md)). A grid that scores as well but moves no note is no alternative.
- The chosen grid is still used, so the pipeline goes on, and the beat says it is a guess.
- The ambiguous beats are one `ambiguous_bars` decision request, returned with the score ([ADR 0015](0015-unclear-input-is-a-decision-request.md)). Its details list, per bar, each ambiguous beat's place in the bar, its chosen grid, the alternatives, and the furthest any onset is from its point in milliseconds. Bars and beats count from 0 in the details and from 1 in the message, which names at most 8 beats beside the count.
- The answer is `grids`, a grid for a beat by its bar and place in the bar. An answered beat takes that grid and is not ambiguous, and a grid the beat can't have is an error.

**Why:** A wrong grid moves notes by a step or more, which can be heard, while one request costs the user a single round of questions for every unclear bar. 6 ms is the smallest penalty, so a choice decided by less is the penalty's call rather than the timing's. A note 20 ms from its point is beyond the plan's 12 ms timing cap, so it is either loose playing or a misread grid, and the user can tell which.

**Consequences:** The looser the playing, the more beats are ambiguous, since a note 20 ms off is reported whichever grid it is on. The skill (M4) has to batch these questions, and may describe beats that are only loose rather than ask about each one.
