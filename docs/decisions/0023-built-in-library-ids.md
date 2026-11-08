# 0023. Built-in libraries have short kebab-case ids

- **Status:** Proposed
- **Date:** 2026-11-08

- A library's `id` and its kit's `id` are what `list_maps` shows and what `from_map` and `to_map` take. The ids are `gm`, `iof-drummer`, `ezdrummer-3`, `superior-drummer-3`, `addictive-drums-2`, `ssd5`, `ggd-modern-and-massive`, `ni-abbey-road` and `sleep-token-ii`, plus `logic-pro-drums` and `garageband-drums` if those maps ship. A library's kit is `default` unless it has several.
- Two map files can't share a library id, and a kit id is unique in its library. A library with one kit can be chosen without naming its kit.

**Why:** An id names the library a user knows, stays the same when the map's data changes, and is short enough to type in an answer.
