"""A session: one song being re-performed, kept as a JSON file between tool calls.

A session holds what a render needs besides the song's own file (ADR 0080): where the file is and
a hash of its bytes, the kit it is read with and the kit it is written to, the instrument, the
`track` and `bpm` given, the answers to its decision requests, the style and seed, the song's
controls, and the sections, each with its controls, the user's words and its take. It also
records the files it was exported to. It holds no note: `load_song` reads the song from its file
again each time, and a file whose bytes no longer match the hash is an error, never another
render. So the same session JSON and seed always give the same file (ADR 0049).

Sessions are kept one JSON file per session ID in the user's state directory (ADR 0079), by a
`SessionStore`, which writes each file whole through a temporary file, so a crash never leaves
half a session.

The sections are found once, when the session is opened, and change only by `edit_sections`:
split, merge, move a boundary, or rename (ADR 0081). A section is named by its first bar, from 0,
as `analyze` prints `start` and the engine keys its stream. Controls are set by merge patch
(`ControlVector.patched`), and answers likewise by key, null removing one.
"""

import hashlib
import os
import re
import secrets
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from human_o_matic.analyze.sections import Sections
from human_o_matic.cli import BeatKey, Pitch, RenderAnswers
from human_o_matic.controls import (
    ControlVector,
    SectionPlan,
    Seed,
    SessionPlan,
    StyleName,
)
from human_o_matic.decisions import DecisionRequest
from human_o_matic.instruments.base import Instrument
from human_o_matic.instruments.drums import DRUMS
from human_o_matic.instruments.generic import GENERIC
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import find_kit
from human_o_matic.midi.io import MidiSong, parse_midi
from human_o_matic.normalize.grid import Grid
from human_o_matic.normalize.hit_types import HitTypeBounds
from human_o_matic.normalize.pipeline import normalize
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.engine import Rendered, render
from human_o_matic.render.target import Placement, place_score

SESSION_VERSION = 1
"""The version of the session file's format."""
APP = "human-o-matic"
STATE_ENV = "HUMAN_O_MATIC_STATE_DIR"
"""The environment variable that names the app's state directory in place of the default."""
ID_PATTERN = re.compile(r"[0-9a-f]{12}")
"""A session ID: 12 lowercase hex digits."""
DEFAULT_SEED = 0
"""The seed a new session renders with until `set_style` gives another."""

type InstrumentName = Literal["drums", "generic"]
type SectionsSource = Literal["markers", "drums", "edited"]
"""Where the sections came from: the file's markers, the drums, or edits since."""

INSTRUMENTS: Mapping[InstrumentName, Instrument] = {"drums": DRUMS, "generic": GENERIC}

_FROZEN = ConfigDict(frozen=True, extra="forbid")


def state_dir(environ: Mapping[str, str] | None = None) -> Path:
    """The app's state directory: `HUMAN_O_MATIC_STATE_DIR` when set, else `human-o-matic` in
    `XDG_STATE_HOME` when that is an absolute path, else in `~/.local/state` (ADR 0079)."""
    env = os.environ if environ is None else environ
    own = env.get(STATE_ENV, "")
    if own:
        return Path(own).expanduser()
    xdg = env.get("XDG_STATE_HOME", "")
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".local" / "state"
    return base / APP


def sessions_dir(environ: Mapping[str, str] | None = None) -> Path:
    """Where the sessions are kept: `sessions` in the app's state directory."""
    return state_dir(environ) / "sessions"


class SessionError(ValueError):
    """A session that can't be found or read, or can't be changed as asked. The message says why
    in plain language."""


class SessionSection(BaseModel):
    """One section of a session: a run of whole bars, with what the user set for it."""

    model_config = _FROZEN

    start: int = Field(ge=0)
    """Its first bar, counting from 0, which names it."""
    bars: int = Field(ge=1)
    group: str = Field(min_length=1)
    """Its repeat group."""
    name: str = ""
    """What the user calls it, such as `chorus`, or empty."""
    controls: ControlVector = ControlVector()
    note: str = ""
    """The user's words its controls were read from."""
    take: int = Field(default=0, ge=0)

    @property
    def end(self) -> int:
        """The bar after its last."""
        return self.start + self.bars


class Export(BaseModel):
    """A file the session was exported to."""

    model_config = _FROZEN

    output: str
    report: str
    sha256: str
    """The hash of the MIDI file's bytes as written."""


class Session(BaseModel):
    """What a session holds (ADR 0080). Its JSON is `dump`, which `Session.model_validate_json`
    reads back to an equal session."""

    model_config = _FROZEN

    version: Literal[1] = SESSION_VERSION
    id: str = Field(pattern=f"^{ID_PATTERN.pattern}$")
    midi_path: str
    """The input file, as an absolute path."""
    midi_sha256: str
    """The hash of its bytes when the session was opened."""
    from_map: str
    """The kit it is read with, as `library/kit`."""
    to_map: str
    """The kit it is written to."""
    instrument: InstrumentName = "drums"
    track: int | None = None
    bpm: float | None = None
    answers: RenderAnswers = RenderAnswers()
    """The answers to its decision requests, as `render --answers` takes them."""
    style: StyleName = "tight"
    seed: Seed = DEFAULT_SEED
    controls: ControlVector = ControlVector()
    """The song's controls, under each section's."""
    note: str = ""
    """The user's words the song's controls were read from."""
    sections: tuple[SessionSection, ...] = Field(min_length=1)
    """In order, from bar 0, each starting where the one before ends."""
    sections_source: SectionsSource
    exports: tuple[Export, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> Self:
        expected = 0
        for section in self.sections:
            if section.start != expected:
                raise ValueError(
                    f"the section at bar {section.start} should start at bar {expected}, where "
                    "the one before it ends"
                )
            expected = section.end
        return self

    @property
    def bars(self) -> int:
        """How many bars the sections cover: the drums' bars."""
        return self.sections[-1].end

    @property
    def starts(self) -> tuple[int, ...]:
        return tuple(section.start for section in self.sections)

    def section(self, start: int) -> SessionSection:
        """The section that starts at `start`. Raises `SessionError` naming those that exist."""
        return self.sections[_index(self.starts, start)]

    def dump(self) -> str:
        """The session's JSON, as its file holds it."""
        return self.model_dump_json(indent=2, exclude_none=True)


def _bars(starts: Sequence[int]) -> str:
    return ", ".join(str(start) for start in starts)


class SessionStore:
    """The sessions in one directory, a JSON file each, named by its ID."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else sessions_dir()

    def path(self, session_id: str) -> Path:
        """The file of a session. Raises `SessionError` for an ID of the wrong form, so no ID can
        name a file elsewhere."""
        if ID_PATTERN.fullmatch(session_id) is None:
            raise SessionError(f"{session_id!r} is not a session ID, 12 hex digits")
        return self.directory / f"{session_id}.json"

    def create(self, make: Callable[[str], Session]) -> Session:
        """A new session, made by `make` from a new ID, and saved."""
        self.directory.mkdir(parents=True, exist_ok=True)
        # The ID only names the file. It is random so two sessions never share one, and no
        # render draws from it: a render's randomness is the session's seed (ADR 0049).
        while True:
            session = make(secrets.token_hex(6))
            try:
                with self.path(session.id).open("x", encoding="utf-8") as file:
                    file.write(session.dump())
            except FileExistsError:
                continue
            return session

    def save(self, session: Session) -> None:
        """Write the session's file whole, replacing what it held."""
        path = self.path(session.id)
        self.directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.directory, prefix=f".{session.id}.", delete=False
        ) as file:
            file.write(session.dump())
        os.replace(file.name, path)

    def load(self, session_id: str) -> Session:
        """A saved session. Raises `SessionError` when there is none or it can't be read."""
        path = self.path(session_id)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise SessionError(f"there is no session {session_id}") from error
        except OSError as error:
            raise SessionError(f"session {session_id} can't be read: {error}") from error
        try:
            return Session.model_validate_json(text)
        except ValidationError as error:
            raise SessionError(f"session {session_id} isn't a valid session: {error}") from error


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class Loaded:
    """A session's song, read from its file, normalized and placed in the target kit."""

    song: MidiSong
    source: DrumKit
    target: DrumKit
    normalized: Normalized
    placement: Placement

    @property
    def decisions(self) -> tuple[DecisionRequest, ...]:
        """The requests still open: normalizing's, then placing's."""
        return (*self.normalized.decisions, *self.placement.decisions)

    @property
    def complete(self) -> bool:
        """Whether no note waits for an answer, so the song can be rendered."""
        return self.normalized.complete and self.placement.complete


def read_song(
    data: bytes,
    source: DrumKit,
    target: DrumKit,
    *,
    track: int | None = None,
    bpm: float | None = None,
    answers: RenderAnswers | None = None,
) -> Loaded:
    """A song from a file's bytes, normalized with `source` and placed in `target`.

    Raises what `normalize` and `place_score` raise: `MidiFileError`, `DecisionRequired` for the
    tempo or the drum track, `AnswerError` for an answer that doesn't fit the song, and
    `ValueError` for a substitution the target can't play.
    """
    given = answers or RenderAnswers()
    song = parse_midi(data)
    normalized = normalize(
        song,
        source,
        track=track,
        bpm=bpm,
        unmapped=given.unmapped,
        grids=given.grids,
        hit_types=given.hit_types,
    )
    placement = place_score(normalized.score, source, target, given.substitutions)
    return Loaded(
        song=song, source=source, target=target, normalized=normalized, placement=placement
    )


def opened(
    session_id: str,
    path: Path,
    data: bytes,
    loaded: Loaded,
    found: Sections,
    *,
    instrument: InstrumentName = "drums",
    track: int | None = None,
    bpm: float | None = None,
) -> Session:
    """A new session of the file at `path`, whose bytes are `data`, read as `loaded` with
    `track` and `bpm`, with the sections `found` in it."""
    return Session(
        id=session_id,
        midi_path=str(path.resolve()),
        midi_sha256=file_hash(data),
        from_map=loaded.source.ref,
        to_map=loaded.target.ref,
        instrument=instrument,
        track=track,
        bpm=bpm,
        sections=tuple(
            SessionSection(start=section.start, bars=section.bars, group=section.group)
            for section in found.sections
        ),
        sections_source=found.source,
    )


def load_song(session: Session, answers: RenderAnswers | None = None) -> Loaded:
    """The session's song, read from its file again, with its answers or `answers`.

    Raises `SessionError` when the file can't be read or has changed since the session was
    opened, and what `read_song` raises for `answers` that don't fit the song.
    """
    path = Path(session.midi_path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise SessionError(f"the session's file {path} can't be read: {error}") from error
    if file_hash(data) != session.midi_sha256:
        raise SessionError(
            f"{path} has changed since session {session.id} was opened, so it would render "
            "differently; open it in a new session"
        )
    return read_song(
        data,
        find_kit(session.from_map),
        find_kit(session.to_map),
        track=session.track,
        bpm=session.bpm,
        answers=session.answers if answers is None else answers,
    )


def plan_of(session: Session) -> SessionPlan:
    """What the engine renders the session by."""
    return SessionPlan(
        style=session.style,
        seed=session.seed,
        controls=session.controls,
        sections=tuple(
            SectionPlan(
                start=section.start,
                bars=section.bars,
                group=section.group,
                controls=section.controls,
                take=section.take,
                note=section.note,
            )
            for section in session.sections
        ),
    )


def render_session(session: Session, loaded: Loaded) -> Rendered:
    """The session rendered: the same session and song always give the same notes."""
    return render(
        loaded.song,
        loaded.normalized,
        loaded.placement,
        plan_of(session),
        instrument=INSTRUMENTS[session.instrument],
    )


class AnswersPatch(BaseModel):
    """Answers to merge into a session's, by key: an answer replaces the one held for its key,
    and null removes it."""

    model_config = _FROZEN

    unmapped: dict[Pitch, str | None] = Field(default_factory=dict[Pitch, str | None])
    grids: dict[BeatKey, Grid | None] = Field(default_factory=dict[BeatKey, Grid | None])
    hit_types: dict[str, HitTypeBounds | None] = Field(
        default_factory=dict[str, HitTypeBounds | None]
    )
    substitutions: dict[str, str | None] = Field(default_factory=dict[str, str | None])


def _merged[K, V](held: Mapping[K, V], patch: Mapping[K, V | None]) -> dict[K, V]:
    out = dict(held)
    for key, value in patch.items():
        if value is None:
            out.pop(key, None)
        else:
            out[key] = value
    return out


def merge_answers(held: RenderAnswers, patch: AnswersPatch) -> RenderAnswers:
    """The answers held with the patch's merged in."""
    return RenderAnswers(
        unmapped=_merged(held.unmapped, patch.unmapped),
        grids=_merged(held.grids, patch.grids),
        hit_types=_merged(held.hit_types, patch.hit_types),
        substitutions=_merged(held.substitutions, patch.substitutions),
    )


def with_controls(
    session: Session,
    starts: Sequence[int] | None,
    patch: ControlVector,
    note: str | None = None,
) -> Session:
    """The session with `patch` applied to the song's controls when `starts` is None, and
    otherwise to those of each section that starts at one of them, and `note` replacing their
    words when given. Raises `SessionError` for a start no section has."""
    if starts is None:
        return session.model_copy(
            update={
                "controls": session.controls.patched(patch),
                "note": session.note if note is None else note,
            }
        )
    chosen = set(starts)
    for start in sorted(chosen):
        session.section(start)
    sections = tuple(
        section.model_copy(
            update={
                "controls": section.controls.patched(patch),
                "note": section.note if note is None else note,
            }
        )
        if section.start in chosen
        else section
        for section in session.sections
    )
    return session.model_copy(update={"sections": sections})


def with_takes(session: Session, starts: Sequence[int] | None, take: int) -> Session:
    """The session with each section that starts at one of `starts`, or every section when it
    is None, rendered as `take`. Raises `SessionError` for a start no section has."""
    chosen = set(session.starts if starts is None else starts)
    for start in sorted(chosen):
        session.section(start)
    sections = tuple(
        section.model_copy(update={"take": take}) if section.start in chosen else section
        for section in session.sections
    )
    return session.model_copy(update={"sections": sections})


class Split(BaseModel):
    """Start a new section at bar `at`, inside a section: both halves keep what it had."""

    model_config = _FROZEN

    op: Literal["split"]
    at: int = Field(ge=0)


class Merge(BaseModel):
    """Join the section that starts at `start` to the one before it, which keeps its own
    controls, words, take, name and group."""

    model_config = _FROZEN

    op: Literal["merge"]
    start: int = Field(ge=0)


class Move(BaseModel):
    """Move the boundary at `start`, where a section starts, to bar `to`, between the start of
    the section before it and the end of its own. Each section keeps what it had."""

    model_config = _FROZEN

    op: Literal["move"]
    start: int = Field(ge=0)
    to: int = Field(ge=0)


class Rename(BaseModel):
    """Give the section that starts at `start` a name, a repeat group, or both."""

    model_config = _FROZEN

    op: Literal["rename"]
    start: int = Field(ge=0)
    name: str | None = None
    group: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.name is None and self.group is None:
            raise ValueError("rename gives a name, a group or both")
        return self


type SectionOp = Annotated[Split | Merge | Move | Rename, Field(discriminator="op")]


def edit_sections(
    sections: Sequence[SessionSection], ops: Sequence[SectionOp]
) -> tuple[SessionSection, ...]:
    """The sections with the ops applied in turn, all or none. Raises `SessionError` naming the
    first op that can't be applied and why, with bars counted from 0 as the ops count them."""
    held = list(sections)
    for number, op in enumerate(ops):
        try:
            held = _apply(held, op)
        except SessionError as error:
            raise SessionError(f"ops[{number}] ({op.op}): {error}") from None
    return tuple(held)


def _apply(sections: list[SessionSection], op: SectionOp) -> list[SessionSection]:
    starts = [section.start for section in sections]
    bars = sections[-1].end
    match op:
        case Split(at=at):
            if at in starts:
                raise SessionError(f"bar {at} already starts a section")
            if at >= bars:
                raise SessionError(f"the drums have {bars} bars, 0 to {bars - 1}")
            index = max(number for number, start in enumerate(starts) if start < at)
            section = sections[index]
            first = section.model_copy(update={"bars": at - section.start})
            second = section.model_copy(update={"start": at, "bars": section.end - at})
            return [*sections[:index], first, second, *sections[index + 1 :]]
        case Merge(start=start):
            index = _boundary(starts, start)
            before, section = sections[index - 1], sections[index]
            joined = before.model_copy(update={"bars": before.bars + section.bars})
            return [*sections[: index - 1], joined, *sections[index + 1 :]]
        case Move(start=start, to=to):
            index = _boundary(starts, start)
            before, section = sections[index - 1], sections[index]
            if not before.start < to < section.end:
                raise SessionError(
                    f"the boundary at bar {start} can move to bars {before.start + 1} to "
                    f"{section.end - 1}, inside the sections either side of it"
                )
            moved_before = before.model_copy(update={"bars": to - before.start})
            moved = section.model_copy(update={"start": to, "bars": section.end - to})
            return [*sections[: index - 1], moved_before, moved, *sections[index + 1 :]]
        case Rename(start=start, name=name, group=group):
            index = _index(starts, start)
            section = sections[index]
            renamed = section.model_copy(
                update={
                    "name": section.name if name is None else name,
                    "group": section.group if group is None else group,
                }
            )
            return [*sections[:index], renamed, *sections[index + 1 :]]


def _index(starts: Sequence[int], start: int) -> int:
    """The index of the section that starts at `start`."""
    if start not in starts:
        raise SessionError(f"no section starts at bar {start}; they start at {_bars(starts)}")
    return list(starts).index(start)


def _boundary(starts: Sequence[int], start: int) -> int:
    """The index of the section that starts at `start`, after the first."""
    if start == 0:
        raise SessionError("bar 0 starts the song, so it is no boundary")
    return _index(starts, start)
