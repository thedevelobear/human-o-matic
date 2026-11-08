# 0020. A map file is one library in TOML, and an ambiguous map fails to load

- **Status:** Proposed
- **Date:** 2026-11-08

- Each built-in library is one TOML file in `data/maps/`, with `schema = 1`, a kebab-case `id`, a `name`, its `[sources.<id>]` and its `[[kits]]`. A source has a `kind` (`standard`, `vendor-file`, `manual` or `owner-check`), a `title` and, for a vendor file, the `path` it is read from in place. A kit has an `id`, a `name` and an optional output `channel`.
- An articulation has a vocabulary `name`, unique in its kit, and a list of `bindings`: a note, with an optional velocity range (1 to 127), channel and controller condition. `notes`, with `velocity`, `channel` and `cc` beside it, is shorthand for one binding per note. The first binding is the one written, and the others are only read. Channels are 1 to 16, as instruments and drum maps show them.
- A controller condition is `select`, where the controller's value at the note-on picks the articulation when it is within `values`, or `shape`, where the controller shapes it. `select` names its controller, and `shape` may leave it out when the source doesn't say.
- An articulation also stores its `source`, an optional `ref`, a `label` of at most 40 characters with the source's own name for it, and a `confidence`: `high` when the source names it or the owner has confirmed it, `medium` when the source names it but the canonical name is an interpretation, and `low` when it is inferred.
- Loading checks that names are in the vocabulary, that variants' parents and pieces' defaults are present, that a family's pieces run from 1 with no gaps, that values are in range and that every source exists. It also checks that no two bindings overlap, that is, that no note on one channel at one velocity can match both. The only bindings that may share a note and velocities are ones told apart by `select` ranges of one controller that don't overlap either, and a binding with no channel overlaps every channel. Any of these is a load error that names what is wrong, and for an overlap, both articulations, the note and the ranges.
- Reading takes a note, its velocity and channel to the articulations it matches. None is an unmapped note, one with no controller condition is the articulation, and anything else depends on a controller value. Writing takes an articulation to its first binding's note, that binding's channel or else the kit's, and that binding's velocity range.

**Why:** Checking at load time means a built-in map can never be ambiguous at run time. A label lets the owner check a map against its source and the agent explain a conversion, and a few words per note stay the project's own format rather than a copy of the vendor's file ([ADR 0007](0007-library-data-stays-out-of-the-repo.md)).

**Consequences:** A note the source kit doesn't map, or one only a controller value can settle, is a question for the user ([ADR 0021](0021-conversion-falls-back-within-a-family.md)).
