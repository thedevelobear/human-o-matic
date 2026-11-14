"""The MCP server: the plan's tools, `service.Tools`, served over stdio (ADRs 0084, 0085).

`build_server` registers each tool with the official MCP SDK, which runs them one at a time and
replies with compact JSON, turning a `service.ToolError` into the SDK's own, and `main`, the
`human-o-matic-mcp` console script, serves them over stdio.
"""

import functools
import json
import threading
from collections.abc import Callable

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from human_o_matic import service
from human_o_matic.service import Reply, Tools
from human_o_matic.session import SessionStore

INSTRUCTIONS = """\
human-o-matic re-performs a drum MIDI file section by section, steered by the user's answers.
1. list_maps gives the built-in kits. open_session reads a file through the kit it was made
   for (from_map) and writes through the kit that will play it (to_map).
2. Answer the decision requests: bpm and track by calling open_session again, and soft notes,
   unclear grids, unmapped notes and conversions with set_hit_types. Confirm the kit maps, the
   section table (get_sections, update_sections), the soft notes and the unclear bars with the
   user in one batch.
3. Ask about the song's style and tightness once (set_style), then, per repeat group in song
   order, about its energy and feel, and set the controls the answers give with
   set_section_controls, which says what they give, to echo in plain words. Repeats can take
   their group's controls. When a section leads into a clearly louder one, get_sections suggests
   asking over how many bars it builds into it, set as ramp, 0 for none. Only when the user asks
   for notes the song lacks, set creative, which lets a section add ghost notes, cymbals, a fill,
   flams, rimshots and chokes.
4. export writes a new MIDI file, never the input, which the user drags into the DAW onto the
   to_map kit's track to listen. render gives the statistics without writing.
Bars are counted from 0 in arguments and replies, and from 1 in labels and messages. A section
is named by its first bar."""


def _compact(method: Callable[..., Reply], lock: threading.Lock) -> Callable[..., str]:
    """A tool that returns its reply as compact JSON, one call at a time. It keeps the method's
    name, description and signature, which the SDK reads the tool's schema from."""

    @functools.wraps(method)
    def tool(*args: object, **kwargs: object) -> str:
        with lock:
            try:
                reply = method(*args, **kwargs)
            except service.ToolError as error:
                raise ToolError(str(error)) from error
            return json.dumps(reply, separators=(",", ":"))

    return tool


READ_ONLY = ToolAnnotations(read_only_hint=True)


def build_server(store: SessionStore | None = None) -> MCPServer:
    """The MCP server, its tools over `store`, the user's sessions by default."""
    tools = Tools(store if store is not None else SessionStore())
    server = MCPServer(name="human-o-matic", instructions=INSTRUCTIONS, log_level="WARNING")
    lock = threading.Lock()
    methods: list[tuple[Callable[..., Reply], bool]] = [
        (tools.list_maps, True),
        (tools.open_session, False),
        (tools.get_sections, True),
        (tools.update_sections, False),
        (tools.set_hit_types, False),
        (tools.set_style, False),
        (tools.set_section_controls, False),
        (tools.render, False),
        (tools.export, False),
    ]
    for method, read_only in methods:
        server.add_tool(
            _compact(method, lock),
            name=method.__name__,
            annotations=READ_ONLY if read_only else None,
            structured_output=False,
        )
    return server


def main() -> None:
    """Serve the tools over stdio: the `human-o-matic-mcp` console script."""
    build_server().run("stdio")
