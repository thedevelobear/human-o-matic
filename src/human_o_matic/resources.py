"""Where the app's built-in data is.

The data, such as the vocabulary and the maps, is in `data/` at the repository root, beside
`src/`, as the plan lays it out. Everything that reads it finds it through `data_dir`, so a
change to how the app is packaged changes this one function.
"""

from pathlib import Path


def data_dir() -> Path:
    """The directory of the built-in data.

    It is found from this file's place in the repository, `src/human_o_matic/`, which holds when
    the app runs from the repository, as `uv run` does. A built wheel doesn't contain it.
    """
    return Path(__file__).resolve().parents[2] / "data"
