"""What the page's Web Worker calls: one entry, a JSON request in, compact JSON or a file out.

The page sends `{"call": name, "args": {...}}` to `handle`, with the chosen file's bytes beside
an `open_session`, and gets compact JSON back, or the MIDI file's bytes for a `download`. The
calls are an allowlist, `CALLS`: the tools of `service.Tools` but `export`, each taking the
arguments the MCP server's tool takes and checked the same way, plus `download`,
`kit_articulations`, `presets` and `reset`. Like the tools, no call takes or gives a note.

The worker keeps one `Tools` over a `SessionStore` in `state/` under its root, in Pyodide's
in-memory file system, and writes each chosen file to `song/<random hex>.mid` there, a name it
draws, so nothing the user gives names a path. Every path in a reply or an error is replaced by
the file's display name, which the page passes as `name`. The browser's limits are checked
before the song is normalized (ADR 0098): the size and the `MThd` header before parsing, and the
tracks, events, bars and tempo events after. `reset` removes everything under `state/` and
`song/`. The page queues its calls, so they run one at a time, as the MCP server's lock does.
"""

import json
import secrets
import shutil
from collections.abc import Buffer, Callable
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, validate_call

from human_o_matic.maps.loader import find_kit
from human_o_matic.midi.io import MidiFileError, MidiSong, midi_bytes, parse_midi
from human_o_matic.midi.tempo import META_TEMPO, time_signature_map
from human_o_matic.presets import read_vocabulary, starting_points
from human_o_matic.service import Reply, ToolError, Tools
from human_o_matic.session import (
    STATE_ENV,
    SessionError,
    SessionStore,
    load_song,
    render_session,
    sessions_dir,
)

type Call = Literal[
    "list_maps",
    "open_session",
    "get_sections",
    "update_sections",
    "set_hit_types",
    "set_style",
    "set_section_controls",
    "render",
    "download",
    "kit_articulations",
    "presets",
    "reset",
]
CALLS: tuple[Call, ...] = (
    "list_maps",
    "open_session",
    "get_sections",
    "update_sections",
    "set_hit_types",
    "set_style",
    "set_section_controls",
    "render",
    "download",
    "kit_articulations",
    "presets",
    "reset",
)
"""The calls the page may make: the tools but `export`, which writes files the page can't reach,
and the page's own four."""
TOOLS: tuple[Call, ...] = (
    "list_maps",
    "get_sections",
    "update_sections",
    "set_hit_types",
    "set_style",
    "set_section_controls",
    "render",
)
"""The calls that are tools as they are, with the MCP server's arguments."""

MAX_BYTES = 512 * 1024
MAX_TRACKS = 64
MAX_EVENTS = 100_000
"""MIDI messages: two for each note, its note-on and note-off, and one for each other event."""
MAX_BARS = 600
MAX_TEMPOS = 10_000
"""The browser's limits on a file, which protect the user's tab (ADR 0098), to confirm."""
DEFAULT_NAME = "song.mid"
"""The display name of a file the page gives none for."""
FAILED = "the engine couldn't read its own files; start over"
"""An error that would otherwise have named a file in the worker."""


class Request(BaseModel):
    """One call from the page."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    call: Call
    args: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue])


def compact(reply: Reply) -> str:
    return json.dumps(reply, separators=(",", ":"))


class Worker:
    """The engine as the page's worker runs it, over files under `root`."""

    def __init__(self, root: Path) -> None:
        root = root.resolve()
        self.state = root / "state"
        self.songs = root / "song"
        self.tools = Tools(SessionStore(sessions_dir({STATE_ENV: str(self.state)})))
        self.names: dict[str, str] = {}
        """Each song file written, by its path, and the name the page shows for it."""

    def handle(self, request: str, data: Buffer | None = None) -> str | bytes:
        """The reply to a call as compact JSON, or for a `download`, the MIDI file's bytes. An
        argument or a file that can't be used gives `{"error": why}`, in plain words."""
        try:
            asked = Request.model_validate_json(request)
        except ValidationError as error:
            return compact({"error": f"the request: {_problems(error)}"})
        try:
            out = self._call(asked.call, dict(asked.args), data)
        except ToolError as error:
            return compact({"error": self._error(str(error))})
        except ValidationError as error:
            return compact({"error": self._error(_problems(error))})
        return out if isinstance(out, bytes) else self._scrub(compact(out))

    def _call(self, call: Call, args: dict[str, JsonValue], data: Buffer | None) -> Reply | bytes:
        if call in TOOLS:
            return _checked(getattr(self.tools, call))(**args)
        match call:
            case "open_session":
                return self._open(args, data)
            case "download":
                return _checked(self._download)(**args)
            case "kit_articulations":
                return _checked(_articulations)(**args)
            case "presets":
                return _checked(_presets)(**args)
            case _:
                return _checked(self._reset)(**args)

    def _open(self, args: dict[str, JsonValue], data: Buffer | None) -> Reply:
        """`open_session` of the file the page sends, written where the worker chooses."""
        name = args.pop("name", DEFAULT_NAME)
        if not isinstance(name, str) or not name:
            raise ToolError("name: give the file's name as text")
        if "midi_path" in args:
            raise ToolError("midi_path: the page sends the file itself, never a path")
        if data is None:
            raise ToolError("choose a MIDI file to open")
        content = bytes(data)
        _check(name, content)
        self.songs.mkdir(parents=True, exist_ok=True)
        path = self.songs / f"{secrets.token_hex(8)}.mid"
        path.write_bytes(content)
        self.names[str(path)] = name
        try:
            reply = _checked(self.tools.open_session)(midi_path=str(path), **args)
        except BaseException:
            self._forget(path)
            raise
        if "session_id" not in reply:
            # A tempo or drum track request keeps no session, so nothing reads the file again.
            self._forget(path)
        return reply

    def _download(self, session_id: str) -> Reply | bytes:
        """The session rendered as a MIDI file, from the same functions `export` writes from,
        writing nothing. While a decision request is open it renders nothing and returns them."""
        try:
            session = self.tools.store.load(session_id)
            loaded = load_song(session)
        except SessionError as error:
            raise ToolError(str(error)) from error
        if loaded.decisions:
            return {"decisions": [request.model_dump(mode="json") for request in loaded.decisions]}
        return midi_bytes(render_session(session, loaded).song)

    def _reset(self) -> Reply:
        """Remove every session and song file, leaving nothing of the user's in the worker."""
        shutil.rmtree(self.state, ignore_errors=True)
        shutil.rmtree(self.songs, ignore_errors=True)
        self.names.clear()
        return {"reset": True}

    def _forget(self, path: Path) -> None:
        path.unlink(missing_ok=True)
        self.names.pop(str(path), None)

    def _scrub(self, text: str) -> str:
        """`text` with each song file's path replaced by its display name."""
        for path, name in self.names.items():
            text = text.replace(path, json.dumps(name)[1:-1])
        return text

    def _error(self, message: str) -> str:
        """An error's message with no path of the worker's in it."""
        for path, name in self.names.items():
            message = message.replace(path, name)
        if str(self.state) in message or str(self.songs) in message:
            return FAILED
        return message


def _checked[T](method: Callable[..., T]) -> Callable[..., T]:
    """`method` with its arguments checked against its signature, as the MCP SDK checks a tool's.
    Raises `ValidationError` for one it can't take."""
    return validate_call(method)


def _check(name: str, data: bytes) -> None:
    """Refuse a file past the browser's limits, in plain words: its size and header before it is
    parsed, and its tracks, events, bars and tempo events after. Raises `ToolError`."""
    if len(data) > MAX_BYTES:
        raise ToolError(f"{name} is {len(data) // 1024} KB; the page reads MIDI files up to 512 KB")
    if not data.startswith(b"MThd"):
        raise ToolError(f"{name} isn't a MIDI file: it doesn't start as one does")
    try:
        song = parse_midi(data)
    except MidiFileError as error:
        raise ToolError(f"{name}: {error}") from error
    found = {
        "tracks": (song.track_count, MAX_TRACKS),
        "events": (2 * len(song.notes) + len(song.events), MAX_EVENTS),
        "bars": (_bars(song), MAX_BARS),
        "tempo changes": (sum(event.meta_type == META_TEMPO for event in song.events), MAX_TEMPOS),
    }
    for what, (count, most) in found.items():
        if count > most:
            raise ToolError(f"{name} has {count:,} {what}; the page reads up to {most:,}")


def _bars(song: MidiSong) -> int:
    """How many bars the song spans, to the end of its longest track."""
    end = max(song.track_ends, default=0)
    return time_signature_map(song).bar_at(max(end - 1, 0)) + 1


def _articulations(map: str) -> Reply:
    """A built-in kit's articulations by name, for the page's `unmapped_notes` form."""
    try:
        kit = find_kit(map)
    except KeyError as error:
        raise ToolError(f"map: {error.args[0]}") from error
    return {
        "map": kit.ref,
        "articulations": [articulation.name for articulation in kit.articulations],
    }


def _presets() -> Reply:
    """The vocabulary's rows, each answer with its controls at their starting points."""
    return starting_points(read_vocabulary())


def _problems(error: ValidationError) -> str:
    """Each problem as `where: what`."""
    found: list[str] = []
    for problem in error.errors(include_url=False):
        where = ".".join(str(part) for part in problem["loc"] if part != "[key]")
        message = problem["msg"].removeprefix("Value error, ")
        found.append(f"{where}: {message}" if where else message)
    return "; ".join(found)


@cache
def _worker() -> Worker:
    return Worker(Path("/"))


def handle(request: str, data: Buffer | None = None) -> str | bytes:
    """`Worker.handle` over the worker's in-memory file system, from its root: what the page's
    worker calls under Pyodide."""
    return _worker().handle(request, data)
