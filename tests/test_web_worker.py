"""The page's worker API, run natively on songs built in code: its allowlist, its compact JSON,
no note list and no path of its own in a reply or an error, the browser's limits, `reset`, and a
download equal to `export`'s and `human-o-matic render`'s (ADRs 0084, 0098, 0100)."""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from grooves import KICK, PPQ, midi_file, rock
from human_o_matic.cli import app
from human_o_matic.midi.io import parse_midi, read_midi
from human_o_matic.web.worker import CALLS, FAILED, MAX_BYTES, Worker
from midi_files import build, end, name, on, tempo, track
from test_service import HIT_TYPES, Json, notes_in, song_file

SONG = "My Song (v2).mid"
"""The display name the page gives the file."""


@pytest.fixture
def worker(tmp_path: Path) -> Worker:
    return Worker(tmp_path / "worker")


def ask(worker: Worker, call: str, data: bytes | None = None, **args: Any) -> Json:
    """A call's reply, which is compact JSON."""
    text = worker.handle(json.dumps({"call": call, "args": args}), data)
    assert isinstance(text, str)
    assert text == json.dumps(json.loads(text), separators=(",", ":"))
    reply: Json = json.loads(text)
    return reply


def opened(worker: Worker, file: Path, **args: Any) -> str:
    """A session of `file`, opened through the worker with every request answered."""
    reply = ask(worker, "open_session", file.read_bytes(), name=SONG, from_map="gm", **args)
    session_id: str = reply["session_id"]
    ask(worker, "set_hit_types", session_id=session_id, hit_types=HIT_TYPES)
    return session_id


def download(worker: Worker, session_id: str) -> bytes:
    data = worker.handle(json.dumps({"call": "download", "args": {"session_id": session_id}}))
    assert isinstance(data, bytes)
    return data


def files_in(worker: Worker) -> list[Path]:
    return sorted(path for path in worker.songs.parent.rglob("*") if path.is_file())


def test_every_call_of_the_allowlist_answers_and_no_reply_holds_a_note_list(
    worker: Worker, tmp_path: Path
) -> None:
    file = song_file(tmp_path, repeats=8)
    notes = len(read_midi(file).notes)
    replies: dict[str, Json] = {"list_maps": ask(worker, "list_maps")}
    replies["open_session"] = ask(worker, "open_session", file.read_bytes(), from_map="gm")
    session_id = replies["open_session"]["session_id"]
    replies["set_hit_types"] = ask(
        worker, "set_hit_types", session_id=session_id, hit_types=HIT_TYPES
    )
    replies["get_sections"] = ask(worker, "get_sections", session_id=session_id)
    replies["update_sections"] = ask(
        worker, "update_sections", session_id=session_id, ops=[{"op": "split", "at": 2}]
    )
    replies["set_style"] = ask(worker, "set_style", session_id=session_id, style="medium", seed=7)
    replies["set_section_controls"] = ask(
        worker, "set_section_controls", session_id=session_id, controls={"energy": 0.9}
    )
    replies["render"] = ask(worker, "render", session_id=session_id, take=1)
    replies["kit_articulations"] = ask(worker, "kit_articulations", map="gm")
    replies["presets"] = ask(worker, "presets")
    midi = download(worker, session_id)
    replies["reset"] = ask(worker, "reset")

    assert set(replies) | {"download"} == set(CALLS)
    assert len(parse_midi(midi).notes) == notes
    for call, reply in replies.items():
        assert "error" not in reply, call
        assert notes_in(reply, notes) == [], call
    assert replies["update_sections"]["sections"][1]["start"] == 2
    assert "kick.hit" in replies["kit_articulations"]["articulations"]
    assert replies["presets"]["answers"][0]["answer"] == "breakdown, full power"


@pytest.mark.parametrize(
    ("request_text", "message"),
    [
        ('{"call": "export", "args": {}}', "the request: call: Input should be"),
        ('{"call": "eval", "args": {}}', "the request: call: Input should be"),
        ('{"call": "list_maps", "args": {}, "more": 1}', "the request: more: Extra inputs"),
        ("not json", "the request: Invalid JSON"),
        ('{"call": "list_maps", "args": {"all": true}}', "all: Unexpected keyword argument"),
        ('{"call": "render", "args": {"session_id": "x", "take": -1}}', "take: Input should be"),
        ('{"call": "get_sections", "args": {"session_id": "0123456789ab"}}', "there is no session"),
        ('{"call": "kit_articulations", "args": {"map": "nope"}}', "map: no library 'nope'"),
        ('{"call": "open_session", "args": {"from_map": "gm"}}', "choose a MIDI file to open"),
    ],
)
def test_a_call_it_can_t_take_is_an_error_in_plain_words(
    worker: Worker, request_text: str, message: str
) -> None:
    text = worker.handle(request_text)

    assert isinstance(text, str)
    reply = json.loads(text)
    assert list(reply) == ["error"]
    assert message in reply["error"]


def test_open_session_takes_no_path_and_names_the_file_by_its_display_name(
    worker: Worker, tmp_path: Path
) -> None:
    file = song_file(tmp_path)

    refused = ask(worker, "open_session", file.read_bytes(), from_map="gm", midi_path=str(file))
    reply = ask(worker, "open_session", file.read_bytes(), name=SONG, from_map="gm")

    assert refused == {"error": "midi_path: the page sends the file itself, never a path"}
    assert reply["summary"]["file"] == SONG
    (written,) = worker.songs.iterdir()
    assert written.read_bytes() == file.read_bytes()


def test_no_reply_or_error_holds_a_path_of_the_worker(worker: Worker, tmp_path: Path) -> None:
    session_id = opened(worker, song_file(tmp_path))
    texts = [
        worker.handle(json.dumps({"call": call, "args": {"session_id": session_id}}))
        for call in ("get_sections", "render")
    ]
    (song,) = worker.songs.iterdir()
    song.write_bytes(midi_file(rock(4)))

    changed = ask(worker, "get_sections", session_id=session_id)

    assert SONG in changed["error"]
    assert "has changed since session" in changed["error"]
    for text in [*texts, json.dumps(changed)]:
        assert isinstance(text, str)
        assert str(worker.songs) not in text
        assert str(worker.state) not in text
    unreadable = "0123456789ab"
    (worker.state / "sessions" / f"{unreadable}.json").mkdir()
    assert ask(worker, "get_sections", session_id=unreadable) == {"error": FAILED}


def test_a_tempo_request_keeps_no_session_and_no_file(worker: Worker) -> None:
    data = build(track((0, name("Drums")), (0, on(KICK)), (10, end())), ppq=960)

    asked = ask(worker, "open_session", data, from_map="gm")
    answered = ask(worker, "open_session", data, from_map="gm", bpm=128.0)

    assert [request["kind"] for request in asked["decisions"]] == ["tempo"]
    assert "session_id" in answered
    assert len(list(worker.songs.iterdir())) == 1


def many_tracks(count: int) -> bytes:
    return build(*(track((0, tempo(120)), (0, end())) for _ in range(count)), ppq=PPQ)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"MThd" + bytes(MAX_BYTES), "is 512 KB; the page reads MIDI files up to 512 KB"),
        (b"not midi", "isn't a MIDI file: it doesn't start as one does"),
        (b"MThd\x00\x00", "not a readable MIDI file"),
        (many_tracks(65), "has 65 tracks; the page reads up to 64"),
        (midi_file((tick * 8, KICK) for tick in range(50_001)), "has 100,004 events; the page"),
        (midi_file([(0, KICK), (600 * 4 * PPQ, KICK)]), "has 601 bars; the page reads up to 600"),
        (
            midi_file([(0, KICK)], tempos=[(tick, 120) for tick in range(1, 10_001)]),
            "has 10,001 tempo changes; the page reads up to 10,000",
        ),
    ],
    ids=["size", "not midi", "broken", "tracks", "events", "bars", "tempos"],
)
def test_a_file_past_a_limit_is_refused_in_plain_words_and_nothing_is_kept(
    worker: Worker, data: bytes, message: str
) -> None:
    reply = ask(worker, "open_session", data, name=SONG, from_map="gm")

    assert reply["error"].startswith(SONG)
    assert message in reply["error"]
    assert files_in(worker) == []


def test_reset_leaves_the_worker_s_files_empty(worker: Worker, tmp_path: Path) -> None:
    session_id = opened(worker, song_file(tmp_path))
    assert files_in(worker)

    assert ask(worker, "reset") == {"reset": True}
    assert files_in(worker) == []
    assert list(worker.songs.parent.iterdir()) == []
    assert "there is no session" in ask(worker, "get_sections", session_id=session_id)["error"]


def test_download_waits_for_the_requests(worker: Worker, tmp_path: Path) -> None:
    file = song_file(tmp_path)
    session_id = ask(worker, "open_session", file.read_bytes(), from_map="gm")["session_id"]

    waiting = worker.handle(json.dumps({"call": "download", "args": {"session_id": session_id}}))

    assert isinstance(waiting, str)
    assert [request["kind"] for request in json.loads(waiting)["decisions"]] == ["hit_types"]


def test_the_download_equals_export_and_at_take_0_human_o_matic_render(
    worker: Worker, tmp_path: Path
) -> None:
    file = song_file(tmp_path)
    session_id = opened(worker, file, to_map="sleep-token-ii/default")
    ask(worker, "set_style", session_id=session_id, style="medium", seed=5)
    ask(worker, "set_section_controls", session_id=session_id, controls={"feel": 0.2})
    ask(
        worker,
        "set_section_controls",
        session_id=session_id,
        controls={"energy": 0.8},
        section_ids=[4],
    )
    first = download(worker, session_id)
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"hit_types": HIT_TYPES}))
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"controls": {"feel": 0.2}, "sections": {"4": {"energy": 0.8}}}))
    rendered = tmp_path / "cli.mid"
    result = CliRunner().invoke(
        app,
        [
            "render",
            str(file),
            "--from-map=gm",
            "--to-map=sleep-token-ii/default",
            f"--output={rendered}",
            "--seed=5",
            "--style=medium",
            f"--answers={answers}",
            f"--plan={plan}",
        ],
    )
    worker.tools.export(session_id, str(tmp_path / "first.mid"))
    ask(worker, "render", session_id=session_id, section_ids=[4], take=2)
    second = download(worker, session_id)
    worker.tools.export(session_id, str(tmp_path / "second.mid"))

    assert result.exit_code == 0, result.output
    assert first == rendered.read_bytes()
    assert first == (tmp_path / "first.mid").read_bytes()
    assert second == (tmp_path / "second.mid").read_bytes()
    assert second != first
