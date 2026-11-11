# 0023. Built-in libraries have short kebab-case ids

- **Status:** Accepted. Its list of ids is amended by [ADR 0055](0055-m3-adds-maps-for-four-drum-libraries.md), and its library with several kits by [ADR 0066](0066-sleep-token-ii-gets-an-inferred-groove-pack-kit.md)
- **Date:** 2026-11-08

- A library's `id` and its kit's `id` are what `list_maps` shows and what `from_map` and `to_map` take. The ids are `gm`, `iof-drummer`, `ezdrummer-3`, `superior-drummer-3`, `addictive-drums-2`, `ssd5`, `ggd-modern-and-massive`, `ni-abbey-road`, `logic-pro-drums`, `garageband-drums` and `sleep-token-ii`. A library's kit is `default` unless it has several, as `iof-drummer` has `default` and `old`.
- Two map files can't share a library id, and a kit id is unique in its library. A library with one kit can be chosen without naming its kit.

**Why:** An id names the library a user knows, stays the same when the map's data changes, and is short enough to type in an answer.
