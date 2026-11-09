import tomllib
from importlib.metadata import entry_points
from pathlib import Path

import human_o_matic
from human_o_matic import cli

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_package_imports() -> None:
    assert human_o_matic.__doc__


def test_the_cli_is_a_console_script() -> None:
    with PYPROJECT.open("rb") as file:
        scripts = tomllib.load(file)["project"]["scripts"]

    (installed,) = entry_points(group="console_scripts", name="human-o-matic")

    assert scripts == {"human-o-matic": "human_o_matic.cli:app"}
    assert installed.load() is cli.app
