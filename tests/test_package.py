import tomllib
from importlib.metadata import entry_points
from pathlib import Path

import human_o_matic
from human_o_matic import cli, mcp_server

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_package_imports() -> None:
    assert human_o_matic.__doc__


def test_the_cli_and_the_mcp_server_are_console_scripts() -> None:
    with PYPROJECT.open("rb") as file:
        scripts = tomllib.load(file)["project"]["scripts"]

    (installed,) = entry_points(group="console_scripts", name="human-o-matic")
    (server,) = entry_points(group="console_scripts", name="human-o-matic-mcp")

    assert scripts == {
        "human-o-matic": "human_o_matic.cli:app",
        "human-o-matic-mcp": "human_o_matic.mcp_server:main",
    }
    assert installed.load() is cli.app
    assert server.load() is mcp_server.main
