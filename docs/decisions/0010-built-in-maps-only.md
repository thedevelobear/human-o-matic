# 0010. Maps are built in, and this version loads no user-supplied map file

- **Status:** Proposed
- **Date:** 2026-11-08

- The maps ship in `data/maps/`, and this version loads no map file from the user.
- `list_maps` lists the built-in libraries and their kits, and `open_session`'s `from_map` and `to_map` take built-in library and kit names.
- A note that the source kit's map doesn't cover is a decision request listing its pitch, count and position.

**Why:** Every built-in map is validated and tested before it ships, so a conversion can't go wrong because of a malformed or partial map from outside, and the scope stays small.

**Consequences:** Supporting another library means adding its map to the repo. User-supplied maps need a new decision, and can build on the schema's validation.
