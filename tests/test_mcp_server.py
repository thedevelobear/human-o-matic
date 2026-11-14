"""The MCP server: the tools through the SDK's client in memory and over stdio. Sessions are kept
in `tmp_path`, never in the user's state directory."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp import Client, StdioServerParameters
from mcp_types import TextContent

from human_o_matic.mcp_server import build_server
from human_o_matic.session import STATE_ENV
from test_service import HIT_TYPES, Json, song_file

PLAN_TOOLS = {
    "list_maps",
    "open_session",
    "get_sections",
    "update_sections",
    "set_hit_types",
    "set_style",
    "set_section_controls",
    "render",
    "export",
}


@pytest.fixture(autouse=True)
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Any session kept by default goes to `tmp_path`, never to the user's state."""
    held = tmp_path / "state"
    monkeypatch.setenv(STATE_ENV, str(held))
    return held


def _text(result: Any) -> str:
    (content,) = result.content
    assert isinstance(content, TextContent)
    text: str = content.text
    return text


def test_the_server_serves_the_plan_s_tools_as_compact_json_through_the_sdk(
    tmp_path: Path, state: Path
) -> None:
    file = song_file(tmp_path)

    async def session() -> tuple[set[str], str, Json, str, bool]:
        async with Client(build_server(), mode="legacy") as client:
            listed = {tool.name for tool in (await client.list_tools()).tools}
            opened = await client.call_tool(
                "open_session", {"midi_path": str(file), "from_map": "gm"}
            )
            reply = json.loads(_text(opened))
            await client.call_tool(
                "set_hit_types", {"session_id": reply["session_id"], "hit_types": HIT_TYPES}
            )
            controls = await client.call_tool(
                "set_section_controls",
                {"session_id": reply["session_id"], "controls": {"energy": 2}, "section_ids": [4]},
            )
            missing = await client.call_tool("get_sections", {"session_id": "0123456789ab"})
            return (
                listed,
                _text(opened),
                json.loads(_text(controls)),
                _text(missing),
                missing.is_error,
            )

    listed, text, controls, missing, is_error = anyio.run(session)

    assert listed == PLAN_TOOLS
    assert "\n" not in text
    assert text == json.dumps(json.loads(text), separators=(",", ":"))
    assert controls["clamped"] == [{"control": "energy", "given": 2.0, "used": 1.0}]
    assert is_error
    assert "there is no session 0123456789ab" in missing
    assert len(list((state / "sessions").iterdir())) == 1


def test_the_console_script_serves_the_tools_over_stdio(tmp_path: Path) -> None:
    script = Path(sys.executable).parent / "human-o-matic-mcp"
    file = song_file(tmp_path)
    server = StdioServerParameters(
        command=str(script),
        env={**os.environ, STATE_ENV: str(tmp_path / "stdio")},
    )

    async def session() -> tuple[set[str], Json]:
        async with Client(server) as client:
            listed = {tool.name for tool in (await client.list_tools()).tools}
            opened = await client.call_tool(
                "open_session", {"midi_path": str(file), "from_map": "gm"}
            )
            return listed, json.loads(_text(opened))

    listed, reply = anyio.run(session)

    assert listed == PLAN_TOOLS
    assert (tmp_path / "stdio" / "sessions" / f"{reply['session_id']}.json").is_file()


def test_the_tools_import_no_mcp_sdk() -> None:
    """The site's engine runs `service` where the SDK doesn't exist (ADR 0100)."""
    code = "import sys, human_o_matic.service\nprint(sorted(sys.modules))"

    loaded = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout

    assert "'mcp'" not in loaded
    assert "'mcp_types'" not in loaded
