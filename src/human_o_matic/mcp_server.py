"""The MCP server: the plan's tools over sessions, each returning compact JSON (ADRs 0084, 0085).

The tools take session IDs, section IDs and file paths, never notes, and return compact JSON
of counts, bars, facts, controls and statistics, never a note list. A section's ID is its first
bar, counted from 0, as every bar in the arguments and replies is, while labels and messages
count bars from 1, as a DAW shows them. Unclear input is a decision request in the reply, as the
CLI prints them (ADR 0015): `bpm` and `track` are answered by opening the session again, and the
others with `set_hit_types`. An argument that can't be used, such as a session that doesn't
exist, a map that isn't built in, an answer that names something the song lacks, or an output
file that exists, is a tool error whose message says why.

`Tools` holds the tools as plain methods over a `SessionStore`, which the tests call directly.
`build_server` registers each one with the official MCP SDK, which runs them one at a time, and
`main`, the `human-o-matic-mcp` console script, serves them over stdio.
"""

import functools
import json
import os
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field, JsonValue, ValidationError

from human_o_matic.analyze.facts import label, song_facts
from human_o_matic.analyze.sections import Section, find_sections
from human_o_matic.cli import (
    HitTypeCounts,
    RenderedNotes,
    RenderSummary,
    SectionEntry,
    answer_problem,
    rendered_notes,
    summarize,
)
from human_o_matic.controls import MAX_SEED, ControlInput, ControlVector, StyleName, clamp
from human_o_matic.decisions import DecisionRequest, DecisionRequired
from human_o_matic.files import name_new, write_aside
from human_o_matic.instruments.drums import DRUMS
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import built_in_maps, find_kit
from human_o_matic.midi.io import MidiFileError, midi_bytes
from human_o_matic.midi.tempo import MAX_BPM, MIN_BPM
from human_o_matic.normalize.answers import AnswerError
from human_o_matic.render.creative import CreativeReport
from human_o_matic.render.describe import sound
from human_o_matic.render.engine import Rendered, RenderedNote
from human_o_matic.render.measure import section_stats
from human_o_matic.render.style import built_in_styles
from human_o_matic.session import (
    AnswersPatch,
    Export,
    InstrumentName,
    Loaded,
    SectionOp,
    Session,
    SessionError,
    SessionStore,
    edit_sections,
    file_hash,
    load_song,
    merge_answers,
    opened,
    read_song,
    render_session,
    with_controls,
    with_takes,
)

type Reply = dict[str, JsonValue]

MIDI_SUFFIXES = (".mid", ".midi")
REPORT_SUFFIX = ".report.json"
"""The report is written beside the MIDI file, as `<name>.report.json`."""

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
   their group's controls. Only when the user asks for notes the song lacks, set creative, which
   lets a section add ghost notes, cymbals, a fill, flams, rimshots and chokes.
4. export writes a new MIDI file, never the input, which the user drags into the DAW onto the
   to_map kit's track to listen. render gives the statistics without writing.
Bars are counted from 0 in arguments and replies, and from 1 in labels and messages. A section
is named by its first bar."""

type SessionId = Annotated[str, Field(description="The session ID open_session returned.")]
type SectionIds = Annotated[
    list[int] | None,
    Field(description="The sections, each by its first bar from 0, as get_sections gives them."),
]


def _given_path(text: str, what: str) -> Path:
    """A path as given, with `~` expanded. Raises `ToolError` unless it is absolute."""
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise ToolError(f"{what} {text!r} is not an absolute path; give the whole path")
    return path


def _kit(name: str, what: str) -> DrumKit:
    try:
        return find_kit(name)
    except KeyError as error:
        raise ToolError(f"{what}: {error.args[0]}") from error


def _decisions(requests: Sequence[DecisionRequest]) -> list[JsonValue]:
    return [request.model_dump(mode="json") for request in requests]


def _vector(controls: ControlVector) -> JsonValue:
    return controls.model_dump(mode="json", exclude_none=True)


def _table(session: Session) -> list[JsonValue]:
    """The sections as a table: their bars, label, group and name."""
    return [
        {
            "start": section.start,
            "bars": section.bars,
            "label": label(section.start, section.bars),
            "group": section.group,
            "name": section.name,
        }
        for section in session.sections
    ]


def _sections(session: Session) -> tuple[Section, ...]:
    return tuple(
        Section(start=section.start, bars=section.bars, group=section.group)
        for section in session.sections
    )


class Tools:
    """The MCP tools as plain methods over a store of sessions. Each returns the reply as JSON
    data, and raises `ToolError` for an argument it can't use."""

    def __init__(self, store: SessionStore) -> None:
        self.store = store

    def _session(self, session_id: str) -> Session:
        try:
            return self.store.load(session_id)
        except SessionError as error:
            raise ToolError(str(error)) from error

    def _loaded(self, session: Session) -> Loaded:
        try:
            return load_song(session)
        except SessionError as error:
            raise ToolError(str(error)) from error

    def list_maps(self) -> Reply:
        """The built-in drum maps: each library and its kits. A kit is named as `library/kit`,
        and a library with one kit by its id alone, in open_session's from_map and to_map."""
        libraries: list[JsonValue] = []
        maps = built_in_maps()
        for library in maps.libraries:
            kits: list[JsonValue] = []
            for kit in maps:
                if kit.library is not library:
                    continue
                kits.append(
                    {
                        "id": kit.spec.id,
                        "map": kit.ref,
                        "name": kit.spec.name,
                        "articulations": len(kit.articulations),
                        "low_confidence": sum(
                            articulation.confidence == "low" for articulation in kit.articulations
                        ),
                    }
                )
            libraries.append({"id": library.id, "name": library.name, "kits": kits})
        return {"libraries": libraries}

    def open_session(
        self,
        midi_path: Annotated[str, Field(description="The drum MIDI file, as an absolute path.")],
        from_map: Annotated[
            str,
            Field(description="The built-in kit the file was made for: library/kit, or library."),
        ],
        to_map: Annotated[
            str | None,
            Field(
                description="The built-in kit that will play the result: the drum instrument in "
                "the DAW. Left out, from_map's."
            ),
        ] = None,
        instrument: Annotated[
            InstrumentName,
            Field(description="drums, or generic: dynamics and timing without drum roles."),
        ] = "drums",
        bpm: Annotated[
            float | None,
            Field(description="A constant tempo that replaces the file's, when it has none."),
        ] = None,
        track: Annotated[
            int | None, Field(description="The track that holds the drums, from 0.")
        ] = None,
    ) -> Reply:
        """Open a drum MIDI file in a new session: normalize its drums through from_map, find
        its sections, and place its notes in to_map. Returns the session ID, a summary of
        counts, the section table, and the decision requests to answer. A request for the tempo
        or the drum track makes no session: open it again with bpm or track."""
        path = _given_path(midi_path, "midi_path")
        source = _kit(from_map, "from_map")
        target = _kit(to_map, "to_map") if to_map is not None else source
        if bpm is not None and not MIN_BPM <= bpm <= MAX_BPM:
            raise ToolError(
                f"bpm {bpm} is outside {MIN_BPM:g} to {MAX_BPM:.0f}, the tempos a MIDI file can "
                "hold"
            )
        try:
            data = path.read_bytes()
        except OSError as error:
            raise ToolError(f"{path} can't be read: {error}") from error
        try:
            loaded = read_song(data, source, target, track=track, bpm=bpm)
        except DecisionRequired as asked:
            return {"decisions": _decisions([asked.request])}
        except MidiFileError as error:
            raise ToolError(f"{path}: {error}") from error
        found = find_sections(loaded.song, loaded.normalized.score)
        session = self.store.create(
            lambda session_id: opened(
                session_id, path, data, loaded, found, instrument=instrument, track=track, bpm=bpm
            )
        )
        summary = summarize(str(path), loaded.song, loaded.normalized, found, track=track, bpm=bpm)
        return {
            "session_id": session.id,
            "summary": summary.model_dump(mode="json"),
            "to_kit": target.ref,
            "instrument": instrument,
            "sections": _table(session),
            "decisions": _decisions(loaded.decisions),
        }

    def get_sections(self, session_id: SessionId) -> Reply:
        """Each section's bars, repeat group, facts and one typical bar as an ASCII pattern,
        with a modest guess of what it is and suggested questions, and the controls, words and
        take set for it so far. Energy isn't readable from the notes, so it is never guessed."""
        session = self._session(session_id)
        loaded = self._loaded(session)
        score = loaded.normalized.score
        facts = song_facts(score, DRUMS.parts(score), _sections(session), session.bars)
        sections: list[JsonValue] = []
        for section, found in zip(session.sections, facts, strict=True):
            entry = found.model_dump(mode="json")
            entry.update(
                {
                    "name": section.name,
                    "controls": _vector(section.controls),
                    "note": section.note,
                    "take": section.take,
                }
            )
            sections.append(entry)
        return {
            "session_id": session.id,
            "bars": session.bars,
            "source": session.sections_source,
            "style": session.style,
            "seed": session.seed,
            "controls": _vector(session.controls),
            "note": session.note,
            "sections": sections,
            "decisions": _decisions(loaded.decisions),
        }

    def update_sections(
        self,
        session_id: SessionId,
        ops: Annotated[
            list[SectionOp],
            Field(
                description='Applied in turn, all or none: {"op": "split", "at": bar} starts a '
                'section at a bar inside one; {"op": "merge", "start": bar} joins the section '
                'starting there to the one before; {"op": "move", "start": bar, "to": bar} '
                'moves the boundary at start; {"op": "rename", "start": bar, "name": "chorus", '
                '"group": "B"} sets a name, a repeat group or both. Bars count from 0.'
            ),
        ],
    ) -> Reply:
        """Split, merge, move the boundaries of, or rename sections. A section split keeps its
        controls in both halves, a merged one takes the first's, and a moved boundary keeps each
        side's. Returns the new section table."""
        session = self._session(session_id)
        try:
            sections = edit_sections(session.sections, ops)
        except SessionError as error:
            raise ToolError(str(error)) from error
        session = session.model_copy(update={"sections": sections, "sections_source": "edited"})
        self.store.save(session)
        return {"session_id": session.id, "source": "edited", "sections": _table(session)}

    def set_hit_types(
        self,
        session_id: SessionId,
        hit_types: Annotated[
            dict[str, dict[str, int] | None] | None,
            Field(
                description='For a hit_types request: from a family to {"soft_below": v, '
                '"accent_from": v}, velocities 1 to 128, either left out; {} makes every note '
                "of the family normal."
            ),
        ] = None,
        grids: Annotated[
            dict[str, str | None] | None,
            Field(
                description='For an ambiguous_bars request: from a beat, "bar,beat" both from '
                '0, to "16th", "8th_triplet", "16th_triplet" or "32nd".'
            ),
        ] = None,
        unmapped: Annotated[
            dict[str, str | None] | None,
            Field(
                description='For an unmapped_notes request: from a pitch, such as "99", to an '
                'articulation of from_map or "drop".'
            ),
        ] = None,
        substitutions: Annotated[
            dict[str, str | None] | None,
            Field(
                description="For a conversion request: from a source articulation to an "
                'articulation of to_map or "drop".'
            ),
        ] = None,
    ) -> Reply:
        """Answer the decision requests about the notes: confirm the soft notes and accents
        (hit_types), settle unclear grids (grids), and place unmapped notes (unmapped) and notes
        to_map lacks (substitutions). Each answer replaces the one held for its key, and null
        removes it. Returns the hit types and the requests still open."""
        session = self._session(session_id)
        try:
            patch = AnswersPatch.model_validate(
                {
                    "hit_types": hit_types or {},
                    "grids": grids or {},
                    "unmapped": unmapped or {},
                    "substitutions": substitutions or {},
                }
            )
        except ValidationError as error:
            raise ToolError(_problems(error)) from error
        answers = merge_answers(session.answers, patch)
        try:
            loaded = load_song(session, answers)
        except SessionError as error:
            raise ToolError(str(error)) from error
        except AnswerError as error:
            raise ToolError(answer_problem(error)) from error
        except ValueError as error:
            raise ToolError(f"substitutions.{error}") from error
        session = session.model_copy(update={"answers": answers})
        self.store.save(session)
        score = loaded.normalized.score
        return {
            "session_id": session.id,
            "hit_types": HitTypeCounts(
                soft=sum(note.hit_type == "soft" for note in score.notes),
                normal=sum(note.hit_type == "normal" for note in score.notes),
                accent=sum(note.hit_type == "accent" for note in score.notes),
                low_confidence=sum(note.hit_type_confidence == "low" for note in score.notes),
            ).model_dump(mode="json"),
            "answers": answers.model_dump(mode="json", exclude_none=True),
            "decisions": _decisions(loaded.decisions),
        }

    def set_style(
        self,
        session_id: SessionId,
        style: Annotated[
            StyleName | None,
            Field(description="tight, the default, medium or loose: how tight the drummer is."),
        ] = None,
        seed: Annotated[
            int | None,
            Field(ge=0, le=MAX_SEED, description="Another seed plays another take of the song."),
        ] = None,
        tightness: Annotated[
            float | None,
            Field(
                allow_inf_nan=False,
                description="The song's tightness, 0 to 1, 1 the tightest, under each section's.",
            ),
        ] = None,
    ) -> Reply:
        """Set the song-wide style, the seed, and the song's tightness. Returns them with the
        style's defaults, which every control left unset takes."""
        session = self._session(session_id)
        update: dict[str, object] = {}
        if style is not None:
            update["style"] = style
        if seed is not None:
            update["seed"] = seed
        clamped: list[JsonValue] = []
        if tightness is not None:
            patch, moved = clamp(ControlInput(tightness=tightness))
            update["controls"] = session.controls.patched(patch)
            clamped = [entry.model_dump(mode="json") for entry in moved]
        session = session.model_copy(update=update)
        self.store.save(session)
        return {
            "session_id": session.id,
            "style": session.style,
            "seed": session.seed,
            "defaults": built_in_styles()[session.style].defaults.model_dump(mode="json"),
            "controls": _vector(session.controls),
            "clamped": clamped,
        }

    def set_section_controls(
        self,
        session_id: SessionId,
        controls: Annotated[
            ControlInput,
            Field(
                description="energy, groove, dynamic_range, tightness, fill_intensity and "
                "ghost_level from 0 to 1, feel from -1 pushed to +1 laid back, arc steady, build "
                "or drop, skip to leave a section as it came in, and creative to let it add "
                "notes, only when the user asks: ghost notes, cymbals where it has few, a fill "
                "into the next section where it has none, flams, rimshots and chokes. skip wins "
                "over creative. A control given replaces the one held, null unsets it, and one "
                "left out stays. A number outside its range is clamped to it, and the reply says "
                "so."
            ),
        ],
        section_ids: SectionIds = None,
        note: Annotated[
            str | None, Field(description="The user's words the controls were read from.")
        ] = None,
    ) -> Reply:
        """Set controls for some sections, or for the whole song, under each section's own,
        when section_ids is left out. Returns, per section, its own controls, every control as
        it will render, and what they give in plain words, such as "backbeats about 118 to 127;
        timing spread about 2.0 ms", to echo to the user, with any clamping."""
        session = self._session(session_id)
        patch, moved = clamp(controls)
        try:
            session = with_controls(session, section_ids, patch, note)
        except SessionError as error:
            raise ToolError(str(error)) from error
        loaded = self._loaded(session)
        rendered = render_session(session, loaded) if loaded.complete else None
        self.store.save(session)
        defaults = built_in_styles()[session.style].defaults
        chosen = set(section_ids if section_ids is not None else session.starts)
        sections: list[JsonValue] = []
        for number, section in enumerate(session.sections):
            if section.start not in chosen:
                continue
            resolved = section.controls.over(session.controls).resolve(defaults)
            entry: Reply = {
                "start": section.start,
                "label": label(section.start, section.bars),
                "controls": _vector(section.controls),
                "resolved": resolved.model_dump(mode="json"),
            }
            if rendered is not None:
                entry["expected"] = sound(_of(rendered, number), rendered.creative[number]).says
            sections.append(entry)
        out: Reply = {"session_id": session.id}
        if section_ids is None:
            out["song"] = {"controls": _vector(session.controls), "note": session.note}
        out["sections"] = sections
        out["clamped"] = [entry.model_dump(mode="json") for entry in moved]
        out["decisions"] = _decisions(loaded.decisions)
        return out

    def render(
        self,
        session_id: SessionId,
        section_ids: SectionIds = None,
        take: Annotated[
            int | None,
            Field(
                ge=0,
                description="Render these sections, or every section, as this take: another "
                "take draws them again. Left out, each keeps its own.",
            ),
        ] = None,
    ) -> Reply:
        """Render the session, without writing a file, and return each section's measured
        statistics, of the sections given or of all, with what they give in plain words. While
        a decision request is open it renders nothing and returns the requests."""
        session = self._session(session_id)
        if section_ids is not None:
            try:
                for start in section_ids:
                    session.section(start)
            except SessionError as error:
                raise ToolError(str(error)) from error
        loaded = self._loaded(session)
        if loaded.decisions:
            return {"sections": _table(session), "decisions": _decisions(loaded.decisions)}
        if take is not None:
            session = with_takes(session, section_ids, take)
        rendered = render_session(session, loaded)
        if take is not None:
            self.store.save(session)
        chosen = set(section_ids if section_ids is not None else session.starts)
        return {
            "session_id": session.id,
            "summary": {
                "style": session.style,
                "seed": session.seed,
                "instrument": session.instrument,
                "notes": _notes(loaded, rendered).model_dump(mode="json"),
                "guards": rendered.guards.model_dump(mode="json"),
                "conversion": loaded.placement.report.model_dump(mode="json"),
                "creative": _creative(CreativeReport.summed(rendered.creative)),
            },
            "sections": _measured(session, rendered, chosen),
            "decisions": [],
        }

    def export(
        self,
        session_id: SessionId,
        output_path: Annotated[
            str,
            Field(
                description="The MIDI file to write, as an absolute path ending .mid or .midi: "
                "never the input. A report is written beside it, as <name>.report.json."
            ),
        ],
        overwrite: Annotated[
            bool, Field(description="Replace the output file and its report if they exist.")
        ] = False,
    ) -> Reply:
        """Render the session and write it to a new MIDI file through to_map, with a JSON
        report beside it of the session and each section's statistics. It never writes over the
        input, and refuses a file that exists unless overwrite is set. It writes both new files or
        neither, and with overwrite replaces the report, then the MIDI file. While a decision
        request is open it writes nothing and returns the requests."""
        session = self._session(session_id)
        output = _given_path(output_path, "output_path")
        if output.suffix.lower() not in MIDI_SUFFIXES:
            raise ToolError(f"{output} doesn't end in .mid or .midi")
        report = output.with_name(output.stem + REPORT_SUFFIX)
        source = Path(session.midi_path)
        for path in (output, report):
            if path.resolve() == source.resolve() or (
                path.exists() and source.exists() and path.samefile(source)
            ):
                raise ToolError(f"{path} is the session's input file, which is never overwritten")
            if path.exists() and not overwrite:
                raise ToolError(f"{path} exists; give overwrite to replace it")
        if not output.parent.is_dir():
            raise ToolError(f"{output.parent} isn't a folder that exists")
        loaded = self._loaded(session)
        if loaded.decisions:
            return {"sections": _table(session), "decisions": _decisions(loaded.decisions)}
        rendered = render_session(session, loaded)
        data = midi_bytes(rendered.song)
        summary = RenderSummary(
            file=session.midi_path,
            output=str(output),
            kit=loaded.source.ref,
            to_kit=loaded.target.ref,
            style=session.style,
            placeholder=built_in_styles()[session.style].placeholder,
            seed=session.seed,
            notes=_notes(loaded, rendered),
            guards=rendered.guards,
            conversion=loaded.placement.report,
            creative=CreativeReport.summed(rendered.creative),
        ).model_dump(mode="json")
        measured = _measured(session, rendered, set(session.starts))
        written = Export(output=str(output), report=str(report), sha256=file_hash(data))
        session = session.model_copy(update={"exports": (*session.exports, written)})
        record: Reply = {
            "summary": summary,
            "session": json.loads(session.model_dump_json(exclude_none=True)),
            "sections": measured,
        }
        _write_together(
            [(report, json.dumps(record, indent=2).encode("utf-8")), (output, data)], overwrite
        )
        self.store.save(session)
        return {
            "session_id": session.id,
            "output": str(output),
            "report": str(report),
            "summary": summary,
            "sections": measured,
            "decisions": [],
        }


def _write_together(files: Sequence[tuple[Path, bytes]], overwrite: bool) -> None:
    """Write each file: each is written aside first, and only then takes its name, in order.
    New files are all or none: each takes its name by `files.name_new`, which fails when the name
    is taken, and a failure removes those this call named. With `overwrite` each replaces the
    file of its name, one after the other, which can't be undone: a failure between two
    replacements leaves the first new file beside the second old one. Raises `ToolError` saying
    what failed."""
    aside: list[Path] = []
    named: list[Path] = []
    current = files[0][0]
    try:
        for current, data in files:
            aside.append(write_aside(current.parent, data))
        for (current, _), written in zip(files, aside, strict=True):
            if overwrite:
                os.replace(written, current)
            else:
                name_new(written, current)
                named.append(current)
    except FileExistsError as error:
        _remove(named)
        raise ToolError(f"{current} exists; give overwrite to replace it") from error
    except OSError as error:
        _remove(named)
        raise ToolError(f"can't write {current}: {error}") from error
    finally:
        _remove(aside)


def _remove(paths: Sequence[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def _of(rendered: Rendered, number: int) -> list[RenderedNote]:
    """The notes of the section at `number` in the session's order."""
    return [note for note in rendered.notes if note.section == number]


def _notes(loaded: Loaded, rendered: Rendered) -> RenderedNotes:
    return rendered_notes(rendered, loaded.normalized, loaded.placement)


def _creative(report: CreativeReport | None) -> JsonValue:
    return report.model_dump(mode="json") if report is not None else None


def _measured(session: Session, rendered: Rendered, chosen: set[int]) -> list[JsonValue]:
    """Each chosen section's statistics and what they give in words."""
    defaults = built_in_styles()[session.style].defaults
    out: list[JsonValue] = []
    for number, section in enumerate(session.sections):
        if section.start not in chosen:
            continue
        notes = _of(rendered, number)
        creative = rendered.creative[number]
        entry = SectionEntry(start=section.start, bars=section.bars, group=section.group)
        row: Reply = entry.model_dump(mode="json")
        row.update(
            {
                "take": section.take,
                "skip": section.controls.over(session.controls).resolve(defaults).skip,
                "stats": section_stats(notes).model_dump(mode="json"),
                "creative": _creative(creative),
                "says": sound(notes, creative).says,
            }
        )
        out.append(row)
    return out


def _problems(error: ValidationError) -> str:
    """Each problem as `where: what`."""
    found: list[str] = []
    for problem in error.errors(include_url=False):
        where = ".".join(str(part) for part in problem["loc"] if part != "[key]")
        found.append(f"{where}: {problem['msg'].removeprefix('Value error, ')}")
    return "; ".join(found)


def _compact(method: Callable[..., Reply], lock: threading.Lock) -> Callable[..., str]:
    """A tool that returns its reply as compact JSON, one call at a time. It keeps the method's
    name, description and signature, which the SDK reads the tool's schema from."""

    @functools.wraps(method)
    def tool(*args: object, **kwargs: object) -> str:
        with lock:
            return json.dumps(method(*args, **kwargs), separators=(",", ":"))

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
