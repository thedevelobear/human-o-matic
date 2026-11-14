# 0106. `make_ab.py score` counts each variant's mean and the gate's three pairs, per trial and overall

- **Status:** Accepted
- **Date:** 2026-11-13

- `uv run python tools/make_ab.py score KEY SHEET [SHEET ...]` reads the key and one or more filled sheets, one per listener, and prints JSON:
  - `sheets`, how many, and `questions`, the count the key holds, or null;
  - `variants`: each variant's number, name, how many ratings it has and their mean;
  - `comparisons`, for 4 against 2, 4 against 3 and 5 against 4: for each trial, each variant's mean over the sheets that rate both, and which is higher, null for a tie; and over the trials, how many each is higher in, how many tie, and the mean of the trials' differences.
- Means are rounded to 3 places. A blank rating is a file not rated. A sheet without the columns `file` and `rating`, naming a file the key doesn't, naming one twice, or with a rating that isn't a whole number from 1 to 5, is refused, and it exits 2.
- It judges nothing: whether 4 beats 2 and 3, and whether 5 matches 4, is the owner's to read from it and record in the plan, with the count of questions and whether they felt worth it.

**Why:** The gate asks three comparisons and a count, and a trial's own result shows where a variant wins. A song's sections and a few listeners are too few for a significance test to say much, so it counts.
