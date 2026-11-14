"""Where the app's built-in data and the skill are.

The data, such as the vocabulary and the maps, is in `data/` at the repository root, beside
`src/`, as the plan lays it out, and the skill in `skills/human-o-matic/`. Everything that reads
them finds them through `data_dir` and `skill_dir`, so a change to how the app is packaged
changes these two functions. The site's bundle keeps the three at their repository paths.
"""

from pathlib import Path


def data_dir() -> Path:
    """The directory of the built-in data.

    It is found from this file's place in the repository, `src/human_o_matic/`, which holds when
    the app runs from the repository, as `uv run` does. A built wheel doesn't contain it.
    """
    return Path(__file__).resolve().parents[2] / "data"


def skill_dir() -> Path:
    """The skill's directory, `skills/human-o-matic/`, whose `references/vocabulary.md` holds the
    presets. It is found as `data_dir` is, and a built wheel doesn't contain it either."""
    return Path(__file__).resolve().parents[2] / "skills" / "human-o-matic"
