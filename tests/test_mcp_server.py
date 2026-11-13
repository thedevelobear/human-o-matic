"""The MCP tools, called as plain methods on songs built in code, then through the SDK's client
in memory and over stdio. Sessions are kept in `tmp_path`, never in the user's state directory."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp import Client, StdioServerParameters
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import TextContent

from grooves import BAR, CRASH, KICK, PPQ, SIXTEENTH, SNARE, SOFT, Hit, midi_file, rock
from human_o_matic import files, mcp_server
from human_o_matic.controls import ControlInput
from human_o_matic.mcp_server import Tools, build_server
from human_o_matic.midi.io import midi_bytes, read_midi
from human_o_matic.session import (
    STATE_ENV,
    Merge,
    Rename,
    SessionStore,
    Split,
    load_song,
    render_session,
)
from midi_files import build, end, name, off, on, track

type Json = dict[str, Any]
"""Parsed JSON, which the assertions index freely."""

TYPED = {"soft_below": 50, "accent_from": 110}
HIT_TYPES: dict[str, dict[str, int] | None] = dict.fromkeys(
    ("kick", "snare", "hat", "crash"), TYPED
)
"""The answer that types every family of `song_file` by the same bounds."""
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
UNMAPPED = 99
"""A pitch the General MIDI map doesn't map."""


@pytest.fixture(autouse=True)
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Any session kept by default goes to `tmp_path`, never to the user's state."""
    held = tmp_path / "state"
    monkeypatch.setenv(STATE_ENV, str(held))
    return held


def verse(start: int) -> list[Hit]:
    """Four bars of rock with a soft snare in each."""
    hits = rock(4, start=start)
    hits.extend((bar * BAR + PPQ + 3 * SIXTEENTH, SNARE, SOFT) for bar in range(start, start + 4))
    return hits


def chorus(start: int) -> list[Hit]:
    """Four bars of a crash on every beat, kick and backbeats."""
    hits: list[Hit] = []
    for bar in range(start, start + 4):
        at = bar * BAR
        hits.extend((at + beat * PPQ, CRASH) for beat in range(4))
        hits.extend([(at, KICK), (at + 2 * PPQ, KICK), (at + PPQ, SNARE), (at + 3 * PPQ, SNARE)])
    return hits


def song_file(path: Path, extra: list[Hit] | None = None, repeats: int = 1) -> Path:
    """Verse, chorus and verse, `repeats` times over."""
    hits: list[Hit] = []
    for number in range(repeats):
        at = 12 * number
        hits.extend([*verse(at), *chorus(at + 4), *verse(at + 8)])
    file = path / "song.mid"
    file.write_bytes(midi_file([*hits, *(extra or [])]))
    return file


@pytest.fixture
def tools(tmp_path: Path) -> Tools:
    return Tools(SessionStore(tmp_path / "sessions"))


def opened(tools: Tools, file: Path, **arguments: Any) -> Json:
    reply: Json = tools.open_session(str(file), "gm", **arguments)
    return reply


def ready(tools: Tools, tmp_path: Path, **arguments: Any) -> str:
    """A session with every request answered."""
    session_id: str = opened(tools, song_file(tmp_path), **arguments)["session_id"]
    tools.set_hit_types(session_id, hit_types=HIT_TYPES)
    return session_id


def kinds(reply: Json) -> list[str]:
    return [request["kind"] for request in reply["decisions"]]


def test_list_maps_names_every_built_in_kit_as_open_session_takes_it(tools: Tools) -> None:
    reply: Json = tools.list_maps()

    libraries = {library["id"]: library for library in reply["libraries"]}
    assert {kit["map"] for kit in libraries["iof-drummer"]["kits"]} == {
        "iof-drummer/default",
        "iof-drummer/old",
    }
    assert libraries["gm"]["kits"][0]["articulations"] > 40
    assert all(kit["low_confidence"] >= 0 for kit in libraries["gm"]["kits"])


def test_open_session_keeps_a_session_and_returns_its_summary_sections_and_requests(
    tools: Tools, tmp_path: Path
) -> None:
    reply = opened(tools, song_file(tmp_path), to_map="sleep-token-ii/default")

    assert list(reply) == ["session_id", "summary", "to_kit", "instrument", "sections", "decisions"]
    assert (tmp_path / "sessions" / f"{reply['session_id']}.json").is_file()
    assert reply["summary"]["kit"] == "gm/default"
    assert reply["to_kit"] == "sleep-token-ii/default"
    assert reply["summary"]["bars"] == 12
    assert [section["start"] for section in reply["sections"]] == [0, 4, 8]
    assert [section["group"] for section in reply["sections"]] == ["A", "B", "A"]
    assert reply["sections"][1]["label"] == "bars 5 to 8"
    assert kinds(reply) == ["hit_types"]


def test_a_missing_tempo_asks_for_bpm_and_keeps_no_session(tools: Tools, tmp_path: Path) -> None:
    file = tmp_path / "no-tempo.mid"
    file.write_bytes(
        build(track((0, name("Drums")), (0, on(KICK)), (10, off(KICK)), (10, end())), ppq=960)
    )

    asked = opened(tools, file)
    answered = opened(tools, file, bpm=128.0)

    assert asked == {"decisions": [asked["decisions"][0]]}
    assert kinds(asked) == ["tempo"]
    assert asked["decisions"][0]["answer_with"] == ["bpm"]
    assert answered["summary"]["tempo"]["given"]
    assert len(list((tmp_path / "sessions").iterdir())) == 1


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"midi_path": "song.mid"}, "is not an absolute path"),
        ({"midi_path": "/nowhere/song.mid"}, "can't be read"),
        ({"from_map": "nope"}, "from_map: no library 'nope'"),
        ({"to_map": "iof-drummer"}, "to_map: iof-drummer has the kits default, old; name one"),
        ({"bpm": 1.0}, "bpm 1.0 is outside"),
    ],
)
def test_open_session_refuses_what_it_can_t_use(
    tools: Tools, tmp_path: Path, arguments: Json, message: str
) -> None:
    given: Json = {"midi_path": str(song_file(tmp_path)), "from_map": "gm", **arguments}

    with pytest.raises(ToolError, match=message):
        tools.open_session(**given)


def test_a_file_that_isn_t_midi_is_a_tool_error(tools: Tools, tmp_path: Path) -> None:
    file = tmp_path / "notes.mid"
    file.write_text("not midi")

    with pytest.raises(ToolError, match="not a readable MIDI file"):
        opened(tools, file)


def test_get_sections_gives_each_section_s_facts_pattern_guess_and_controls(
    tools: Tools, tmp_path: Path
) -> None:
    session_id = ready(tools, tmp_path)
    tools.set_section_controls(session_id, ControlInput(energy=0.9), [4], "big chorus")

    reply: Json = tools.get_sections(session_id)

    first, middle, last = reply["sections"]
    assert (reply["bars"], reply["source"], reply["style"], reply["seed"]) == (
        12,
        "drums",
        "tight",
        0,
    )
    assert first["plays"] == "hats, 4 soft snare notes"
    assert middle["riding"] == "crash"
    assert middle["pattern"]["lines"][0] == "crash x... x... x... x..."
    assert (middle["controls"], middle["note"], middle["take"]) == (
        {"energy": 0.9},
        "big chorus",
        0,
    )
    assert last["guess"] == {
        "kind": "repeat",
        "confidence": "high",
        "says": "Plays like bars 1 to 4, so it can take the same controls. Ask only if it should "
        "differ, as a bigger last chorus does.",
        "like": 0,
    }
    assert first["questions"][0].startswith("What's the energy in bars 1 to 4")
    assert reply["decisions"] == []


def test_an_unknown_session_is_a_tool_error(tools: Tools) -> None:
    with pytest.raises(ToolError, match="there is no session 0123456789ab"):
        tools.get_sections("0123456789ab")
    with pytest.raises(ToolError, match="is not a session ID"):
        tools.get_sections("../../etc")


def test_update_sections_applies_its_ops_in_turn_and_keeps_them(
    tools: Tools, tmp_path: Path
) -> None:
    session_id = ready(tools, tmp_path)
    tools.set_section_controls(session_id, ControlInput(energy=0.9), [4])

    reply: Json = tools.update_sections(
        session_id,
        [
            Split(op="split", at=6),
            Rename(op="rename", start=6, name="chorus end", group="C"),
            Merge(op="merge", start=8),
        ],
    )
    sections: Json = tools.get_sections(session_id)

    assert [
        (row["start"], row["bars"], row["group"], row["name"]) for row in reply["sections"]
    ] == [
        (0, 4, "A", ""),
        (4, 2, "B", ""),
        (6, 6, "C", "chorus end"),
    ]
    assert sections["source"] == "edited"
    assert [row["controls"] for row in sections["sections"]] == [
        {},
        {"energy": 0.9},
        {"energy": 0.9},
    ]


def test_an_op_that_can_t_be_applied_changes_nothing(tools: Tools, tmp_path: Path) -> None:
    session_id = ready(tools, tmp_path)

    with pytest.raises(ToolError, match=r"ops\[1\] \(merge\): no section starts at bar 5"):
        tools.update_sections(session_id, [Split(op="split", at=2), Merge(op="merge", start=5)])
    sections: Json = tools.get_sections(session_id)
    assert [row["start"] for row in sections["sections"]] == [0, 4, 8]


def test_set_hit_types_answers_the_requests_and_null_takes_an_answer_back(
    tools: Tools, tmp_path: Path
) -> None:
    session_id: str = opened(tools, song_file(tmp_path))["session_id"]

    answered: Json = tools.set_hit_types(session_id, hit_types=HIT_TYPES)
    again: Json = tools.set_hit_types(session_id, hit_types={"crash": None})

    assert answered["decisions"] == []
    assert answered["hit_types"]["soft"] == 8
    assert answered["answers"]["hit_types"]["snare"] == TYPED
    assert kinds(again) == ["hit_types"]
    assert "crash" not in again["answers"]["hit_types"]


def test_set_hit_types_places_unmapped_notes_and_refuses_an_answer_the_song_lacks(
    tools: Tools, tmp_path: Path
) -> None:
    file = song_file(tmp_path, extra=[(0, UNMAPPED)])
    session_id: str = opened(tools, file)["session_id"]

    with pytest.raises(ToolError, match=r"hit_types\.tom: the drums have no tom notes"):
        tools.set_hit_types(session_id, hit_types={"tom": TYPED})
    with pytest.raises(ToolError, match=r"unmapped\.12"):
        tools.set_hit_types(session_id, unmapped={"12": "drop"})
    unanswered: Json = tools.get_sections(session_id)
    reply: Json = tools.set_hit_types(
        session_id, hit_types=HIT_TYPES, unmapped={str(UNMAPPED): "drop"}
    )

    assert "unmapped_notes" in kinds(unanswered)
    assert reply["decisions"] == []
    assert reply["answers"]["unmapped"] == {str(UNMAPPED): "drop"}


def test_set_style_sets_the_style_seed_and_song_tightness_clamped(
    tools: Tools, tmp_path: Path
) -> None:
    session_id = ready(tools, tmp_path)

    reply: Json = tools.set_style(session_id, "loose", 77, 1.4)

    assert (reply["style"], reply["seed"], reply["controls"]) == ("loose", 77, {"tightness": 1.0})
    assert reply["clamped"] == [{"control": "tightness", "given": 1.4, "used": 1.0}]
    assert reply["defaults"]["energy"] == 0.5


def test_set_section_controls_stores_them_and_says_what_they_give(
    tools: Tools, tmp_path: Path
) -> None:
    session_id = ready(tools, tmp_path)

    song: Json = tools.set_section_controls(session_id, ControlInput(groove=0.8), note="groovy")
    chorus: Json = tools.set_section_controls(
        session_id, ControlInput.model_validate({"energy": 1.2, "dynamic_range": 0.2}), [4], "full"
    )

    assert song["song"] == {"controls": {"groove": 0.8}, "note": "groovy"}
    assert [section["start"] for section in song["sections"]] == [0, 4, 8]
    (section,) = chorus["sections"]
    assert section["controls"] == {"energy": 1.0, "dynamic_range": 0.2}
    assert (section["resolved"]["energy"], section["resolved"]["groove"]) == (1.0, 0.8)
    assert section["expected"].startswith("kick about ")
    assert "backbeats about" in section["expected"]
    assert "timing spread about" in section["expected"]
    assert chorus["clamped"] == [{"control": "energy", "given": 1.2, "used": 1.0}]
    assert "song" not in chorus
    with pytest.raises(ToolError, match="no section starts at bar 5; they start at 0, 4, 8"):
        tools.set_section_controls(session_id, ControlInput(energy=0.1), [5])


def test_a_creative_section_says_what_it_adds_and_counts_it_leaving_the_others_alone(
    tools: Tools, tmp_path: Path
) -> None:
    session_id = ready(tools, tmp_path)
    before: Json = tools.render(session_id)

    reply: Json = tools.set_section_controls(session_id, ControlInput(creative=True), [0])
    after: Json = tools.render(session_id)

    (section,) = reply["sections"]
    assert section["controls"] == {"creative": True}
    assert "creative adds " in section["expected"]
    assert (
        "skips 1 backbeat as a rimshot: the kit has no articulation for them"
        in (section["expected"])
    )
    verse = after["sections"][0]
    added = sum(verse["creative"]["added"].values())
    assert verse["stats"]["notes"] == before["sections"][0]["stats"]["notes"] + added
    assert after["summary"]["creative"] == verse["creative"]
    assert after["summary"]["notes"]["added"] == added
    assert after["sections"][1:] == before["sections"][1:]
    assert all(row["creative"] is None for row in after["sections"][1:])


def test_a_render_that_fails_stores_neither_controls_nor_a_take(
    tools: Tools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = ready(tools, tmp_path)
    store = SessionStore(tmp_path / "sessions")
    before = store.load(session_id)

    def broken(*_: object) -> None:
        raise RuntimeError("the engine failed")

    monkeypatch.setattr(mcp_server, "render_session", broken)

    with pytest.raises(RuntimeError, match="the engine failed"):
        tools.set_section_controls(session_id, ControlInput(energy=0.9), [4])
    with pytest.raises(RuntimeError, match="the engine failed"):
        tools.render(session_id, [4], 3)
    assert store.load(session_id) == before


def test_set_section_controls_says_nothing_expected_while_notes_wait(
    tools: Tools, tmp_path: Path
) -> None:
    session_id: str = opened(tools, song_file(tmp_path, extra=[(0, UNMAPPED)]))["session_id"]

    reply: Json = tools.set_section_controls(session_id, ControlInput(energy=0.7))

    assert all("expected" not in section for section in reply["sections"])
    assert "unmapped_notes" in kinds(reply)


def test_render_waits_for_the_requests_then_measures_each_section(
    tools: Tools, tmp_path: Path
) -> None:
    session_id: str = opened(tools, song_file(tmp_path))["session_id"]

    waiting: Json = tools.render(session_id)
    tools.set_hit_types(session_id, hit_types=HIT_TYPES)
    reply: Json = tools.render(session_id)
    chorus: Json = tools.render(session_id, [4])

    assert list(waiting) == ["sections", "decisions"]
    assert kinds(waiting) == ["hit_types"]
    assert reply["summary"]["notes"] == {"written": 136, "kept": 0, "dropped": 0, "added": 0}
    assert reply["summary"]["creative"] is None
    assert [section["start"] for section in reply["sections"]] == [0, 4, 8]
    assert reply["sections"][1]["stats"] == chorus["sections"][0]["stats"]
    assert reply["sections"][1]["says"] == chorus["sections"][0]["says"]
    assert reply["sections"][0]["stats"]["soft"] is not None


def test_another_take_of_a_section_changes_it_alone_and_is_kept(
    tools: Tools, tmp_path: Path
) -> None:
    session_id = ready(tools, tmp_path)

    before: Json = tools.render(session_id)
    after: Json = tools.render(session_id, [4], 2)
    sections: Json = tools.get_sections(session_id)

    assert [section["take"] for section in after["sections"]] == [2]
    assert [section["take"] for section in sections["sections"]] == [0, 2, 0]
    assert after["sections"][0]["stats"] != before["sections"][1]["stats"]


def test_export_writes_the_render_and_its_report_and_records_them(
    tools: Tools, tmp_path: Path
) -> None:
    session_id = ready(tools, tmp_path, to_map="sleep-token-ii/default")
    output = tmp_path / "out" / "song-2.mid"
    output.parent.mkdir()

    reply: Json = tools.export(session_id, str(output))

    report = json.loads((tmp_path / "out" / "song-2.report.json").read_text())
    session = SessionStore(tmp_path / "sessions").load(session_id)
    assert reply["output"] == str(output)
    assert reply["summary"]["to_kit"] == "sleep-token-ii/default"
    assert len(read_midi(output).notes) == 136
    assert output.read_bytes() == midi_bytes(render_session(session, load_song(session)).song)
    assert report["summary"] == reply["summary"]
    assert report["sections"] == reply["sections"]
    assert report["session"]["id"] == session_id
    assert [entry["output"] for entry in report["session"]["exports"]] == [str(output)]
    assert session.exports[0].output == str(output)


def test_the_same_session_and_seed_export_the_same_bytes(tools: Tools, tmp_path: Path) -> None:
    session_id = ready(tools, tmp_path)
    tools.set_style(session_id, "medium", 5)
    tools.set_section_controls(session_id, ControlInput(energy=0.8, feel=0.3), [4])

    tools.export(session_id, str(tmp_path / "a.mid"))
    tools.export(session_id, str(tmp_path / "b.mid"))
    tools.set_style(session_id, seed=6)
    tools.export(session_id, str(tmp_path / "c.mid"))

    assert (tmp_path / "a.mid").read_bytes() == (tmp_path / "b.mid").read_bytes()
    assert (tmp_path / "a.mid").read_bytes() != (tmp_path / "c.mid").read_bytes()


def test_export_never_writes_over_the_input_and_refuses_files_that_exist(
    tools: Tools, tmp_path: Path
) -> None:
    session_id = ready(tools, tmp_path)
    source = tmp_path / "song.mid"
    original = source.read_bytes()
    output = tmp_path / "out.mid"
    tools.export(session_id, str(output))
    first = output.read_bytes()

    with pytest.raises(ToolError, match="is the session's input file"):
        tools.export(session_id, str(source), overwrite=True)
    with pytest.raises(ToolError, match="exists; give overwrite"):
        tools.export(session_id, str(output))
    (tmp_path / "other.report.json").write_text("{}")
    with pytest.raises(ToolError, match=r"other\.report\.json exists"):
        tools.export(session_id, str(tmp_path / "other.mid"))
    tools.set_style(session_id, seed=3)
    tools.export(session_id, str(output), overwrite=True)

    assert source.read_bytes() == original
    assert output.read_bytes() != first
    assert not (tmp_path / "other.mid").exists()


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("out.mid", "is not an absolute path"),
        ("/tmp/out.wav", "doesn't end in .mid or .midi"),
        ("/nowhere/at/all/out.mid", "isn't a folder that exists"),
    ],
)
def test_export_refuses_a_path_it_can_t_use(
    tools: Tools, tmp_path: Path, name: str, message: str
) -> None:
    session_id = ready(tools, tmp_path)

    with pytest.raises(ToolError, match=message):
        tools.export(session_id, name)


@pytest.mark.parametrize(
    ("failing", "named"), [(b"{", "song-2.report.json"), (b"MThd", "song-2.mid")]
)
def test_a_failed_write_leaves_neither_file_nor_an_export(
    tools: Tools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: bytes, named: str
) -> None:
    session_id = ready(tools, tmp_path)
    folder = tmp_path / "out"
    folder.mkdir()
    real = files.write_aside

    def full(where: Path, data: bytes) -> Path:
        if data.startswith(failing):
            raise OSError(28, "No space left on device")
        return real(where, data)

    monkeypatch.setattr(mcp_server, "write_aside", full)

    with pytest.raises(ToolError, match=rf"can't write .*{re.escape(named)}: .*No space left"):
        tools.export(session_id, str(folder / "song-2.mid"))
    assert list(folder.iterdir()) == []
    assert SessionStore(tmp_path / "sessions").load(session_id).exports == ()


def test_a_file_that_appears_while_exporting_is_kept_and_the_report_taken_back(
    tools: Tools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = ready(tools, tmp_path)
    folder = tmp_path / "out"
    folder.mkdir()
    real = files.write_aside

    def racing(where: Path, data: bytes) -> Path:
        written = real(where, data)
        if data.startswith(b"MThd"):
            (folder / "song-2.mid").write_bytes(b"theirs")
        return written

    monkeypatch.setattr(mcp_server, "write_aside", racing)

    with pytest.raises(ToolError, match=r"song-2\.mid exists; give overwrite"):
        tools.export(session_id, str(folder / "song-2.mid"))
    assert [path.name for path in folder.iterdir()] == ["song-2.mid"]
    assert (folder / "song-2.mid").read_bytes() == b"theirs"
    assert SessionStore(tmp_path / "sessions").load(session_id).exports == ()


def test_export_writes_where_files_can_t_be_linked_and_still_refuses_a_taken_name(
    tools: Tools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = ready(tools, tmp_path)
    output = tmp_path / "out.mid"

    def refuse(*_: object) -> None:
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(os, "link", refuse)
    tools.export(session_id, str(output))
    real = files.write_aside

    def racing(where: Path, data: bytes) -> Path:
        written = real(where, data)
        if data.startswith(b"MThd"):
            (tmp_path / "other.mid").write_bytes(b"theirs")
        return written

    monkeypatch.setattr(mcp_server, "write_aside", racing)

    with pytest.raises(ToolError, match=r"other\.mid exists; give overwrite"):
        tools.export(session_id, str(tmp_path / "other.mid"))
    assert len(read_midi(output).notes) == 136
    assert json.loads((tmp_path / "out.report.json").read_text())["session"]["id"] == session_id
    assert (tmp_path / "other.mid").read_bytes() == b"theirs"
    assert not (tmp_path / "other.report.json").exists()
    assert [path.name for path in tmp_path.iterdir() if path.name.startswith(".")] == []


def test_a_changed_input_file_is_refused(tools: Tools, tmp_path: Path) -> None:
    session_id = ready(tools, tmp_path)
    (tmp_path / "song.mid").write_bytes(midi_file(rock(4)))

    with pytest.raises(ToolError, match="has changed since session"):
        tools.render(session_id)


def _notes_in(value: object, notes: int) -> list[str]:
    """Where a reply holds something like a note list: an object with a pitch or tick and a
    velocity, or a list as long as the song's notes."""
    found: list[str] = []
    if isinstance(value, dict):
        keys = set(value)  # pyright: ignore[reportUnknownArgumentType]
        if "velocity" in keys and keys & {"pitch", "tick", "start_tick"}:
            found.append(f"a note-like object {sorted(keys)}")
        for item in value.values():  # pyright: ignore[reportUnknownVariableType]
            found.extend(_notes_in(item, notes))
    elif isinstance(value, list):
        if len(value) >= notes // 4:  # pyright: ignore[reportUnknownArgumentType]
            found.append(f"a list of {len(value)}")  # pyright: ignore[reportUnknownArgumentType]
        for item in value:  # pyright: ignore[reportUnknownVariableType]
            found.extend(_notes_in(item, notes))
    return found


def test_no_reply_holds_a_note_list(tools: Tools, tmp_path: Path) -> None:
    file = song_file(tmp_path, repeats=8)
    notes = len(read_midi(file).notes)
    replies: list[Json] = [tools.list_maps(), opened(tools, file)]
    session_id: str = replies[1]["session_id"]
    replies.extend(
        [
            tools.get_sections(session_id),
            tools.set_hit_types(session_id, hit_types=HIT_TYPES),
            tools.set_style(session_id, "tight", 1, 0.8),
            tools.set_section_controls(session_id, ControlInput(energy=0.9)),
            tools.render(session_id, take=1),
            tools.export(session_id, str(tmp_path / "out.mid")),
            tools.get_sections(session_id),
        ]
    )

    assert notes > 1000
    for reply in replies:
        assert _notes_in(reply, notes) == []
        assert len(json.dumps(reply)) < 40_000


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
