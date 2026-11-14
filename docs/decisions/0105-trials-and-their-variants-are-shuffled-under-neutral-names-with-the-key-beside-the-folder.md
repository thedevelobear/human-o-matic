# 0105. Trials and their variants are shuffled under neutral names, with the key beside the folder and a sheet to rate each file from 1 to 5

- **Status:** Proposed
- **Date:** 2026-11-13

- `--seed` builds a numpy `Generator` from `SeedSequence(seed, spawn_key=(0,))`, which draws the order of the trials, then for each trial in turn the order of its five variants. Trial `NN`'s files are `trial-NN-a.mid` to `trial-NN-e.mid`, the letters taking the variants in its order, `NN` two digits or as many as the count needs. The same session, kit, seed and velocity give the same bytes in every file, the key and the sheet.
- The files are written in name order, so not even their times say which is which, and `make` prints counts and paths only.
- The key, `FOLDER.key.json` beside the folder unless `--key` names another file, never one inside it, holds each file's trial, variant and hash, each trial's section, the session, the kit, the style and both seeds, the flat velocity, the sections left out and those creative mode was turned off in, and `--questions`, the count of questions the agent gave at the end of the session ([ADR 0090](0090-the-skill-counts-its-questions-the-confirmation-batch-as-one.md)), when given.
- The folder holds the files and `ratings.csv`, with the columns `file`, `rating` and `comment` and a row per file in name order. Each listener fills a copy, rating each file a whole number from 1, the worst, to 5, the best, and may leave one blank.
- It never writes over the session's file or its input, even with `--overwrite`: the folder may hold neither, and the key may be neither, by its path or as the same file. A folder or key that exists is refused unless `--overwrite` is given, which removes from the folder only the files `make` names, the trials' and the sheet, keeps any other, and replaces the key. A new folder is written whole beside itself, then takes its name, and a new key takes its name by a link that fails when it is taken, so a failure leaves neither ([ADR 0080](0080-a-session-holds-what-a-render-needs-and-reads-its-file-again-by-its-hash.md)).

**Why:** Shuffling the trials and each trial's letters keeps any order effect off one variant. A key outside the folder lets the folder go to other producers whole. A rating per file, on a scale of five, is quick, needs no pairing, and gives every comparison the gate asks for from the same sheet.

**Consequences:** A filled sheet kept in the folder is replaced by `--overwrite`, so listeners fill copies.
