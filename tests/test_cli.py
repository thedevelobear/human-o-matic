"""`human-o-matic analyze`, run through typer's runner on MIDI files built in code, and the plain
functions under it: the answers file, the kit lookup and the summary."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from typer.testing import CliRunner, Result

from human_o_matic.cli import EXIT_OPEN, MAX_BPM, MIN_BPM, app, find_kit, read_answers, summarize
from human_o_matic.decisions import DecisionRequest
from human_o_matic.maps.loader import built_in_maps
from human_o_matic.midi.io import read_midi
from human_o_matic.normalize.hit_types import HitTypeBounds
from human_o_matic.normalize.pipeline import normalize
from midi_files import MidoMessage, end, name, off, on, save, signature, tempo, track

PPQ = 960
KICK, SNARE, HAT, UNMAPPED = 36, 38, 42, 99
GROOVE = [
    *[(beat * PPQ, KICK if beat % 2 == 0 else SNARE, 110) for beat in range(8)],
    *[(eighth * PPQ // 2, HAT, 90) for eighth in range(16)],
]
"""Two bars of kick, snare and 8th hats, all on the 16th grid."""
UNCLEAR = [(0, UNMAPPED, 100), (0, KICK, 100), (PPQ + 340, SNARE, 100), (2 * PPQ, KICK, 100)]
"""An unmapped note, a beat that could be 16ths or 8th triplets, and one velocity."""
ALL_NORMAL = {"hit_types": {"kick": {}, "snare": {}, "hat": {}}}

type Json = dict[str, Any]
"""Parsed JSON, which the assertions index freely. A precise JSON type would need narrowing at
every step, so its values are `Any`."""

runner = CliRunner()


def drums(
    path: Path,
    notes: list[tuple[int, int, int]],
    *,
    bpm: float | None = 120,
    meta: tuple[tuple[int, MidoMessage], ...] = (),
) -> Path:
    """A one-track file of (tick, pitch, velocity) notes on channel 10, at 960 PPQ."""
    items: list[tuple[int, int, MidoMessage]] = [(0, 0, name("Drums"))]
    if bpm is not None:
        items.append((0, 0, tempo(bpm)))
    items.extend((tick, 0, message) for tick, message in meta)
    for tick, pitch, velocity in notes:
        items.extend([(tick, 2, on(pitch, velocity)), (tick + 10, 1, off(pitch))])
    items.sort(key=lambda item: (item[0], item[1]))
    messages = [(tick, message) for tick, _, message in items]
    return save(path / "drums.mid", track(*messages, (messages[-1][0], end())), ppq=PPQ)


def answers_file(path: Path, answers: object) -> Path:
    file = path / "answers.json"
    file.write_text(answers if isinstance(answers, str) else json.dumps(answers))
    return file


def analyze(*args: str | Path) -> Result:
    return runner.invoke(app, ["analyze", *(str(arg) for arg in args)])


def output(result: Result) -> Json:
    out = json.loads(result.stdout)
    assert isinstance(out, dict)
    return out


def kinds(result: Result) -> list[str]:
    return [request["kind"] for request in output(result)["decisions"]]


def usage_error(result: Result) -> str:
    """The message of a usage error, which is printed on stderr with nothing on stdout."""
    assert result.exit_code == 2, result.output
    assert isinstance(result.exception, SystemExit)
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    return result.stderr


def test_a_clean_run_prints_the_summary_and_no_requests(tmp_path: Path) -> None:
    song = drums(tmp_path, GROOVE)

    result = analyze(song, "--from-map", "gm", "--answers", answers_file(tmp_path, ALL_NORMAL))

    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    out = output(result)
    assert list(out) == ["summary", "decisions"]
    assert out["decisions"] == []
    summary = out["summary"]
    assert summary["file"] == str(song)
    assert summary["kit"] == "gm/default"
    assert summary["track"] == {"index": 0, "name": "Drums", "reason": "only_track"}
    assert summary["notes"] == {"read": 24, "score": 24, "pending": 0, "dropped": 0}
    assert summary["bars"] == 2
    assert summary["families"] == {"hat": 16, "kick": 4, "snare": 4}


def test_the_output_is_one_line_of_compact_json(tmp_path: Path) -> None:
    result = analyze(drums(tmp_path, GROOVE), "--from-map", "gm")

    assert result.stdout.count("\n") == 1
    assert result.stdout == json.dumps(output(result), separators=(",", ":")) + "\n"


def test_an_open_request_is_printed_with_the_summary_and_exits_3(tmp_path: Path) -> None:
    result = analyze(drums(tmp_path, UNCLEAR), "--from-map", "gm")

    assert result.exit_code == EXIT_OPEN == 3
    out = output(result)
    assert out["summary"]["notes"] == {"read": 4, "score": 3, "pending": 1, "dropped": 0}
    assert kinds(result) == ["unmapped_notes", "ambiguous_bars", "hit_types"]
    for request in out["decisions"]:
        DecisionRequest.model_validate(request)


def test_a_missing_tempo_prints_only_its_request(tmp_path: Path) -> None:
    song = drums(tmp_path, GROOVE, bpm=None)

    asked = analyze(song, "--from-map", "gm")
    answered = analyze(song, "--from-map", "gm", "--bpm", "100")

    assert asked.exit_code == EXIT_OPEN
    assert list(output(asked)) == ["decisions"]
    assert kinds(asked) == ["tempo"]
    assert output(asked)["decisions"][0]["answer_with"] == ["bpm"]
    assert output(answered)["summary"]["tempo"] == {
        "given": True,
        "replaced": False,
        "bpm": 100.0,
        "changes": 0,
        "min_bpm": 100.0,
        "max_bpm": 100.0,
    }


def test_an_unclear_drum_track_prints_only_its_request(tmp_path: Path) -> None:
    # Two tracks with notes, neither named like drums nor on channel 10.
    first = track((0, tempo(120)), (0, on(40, channel=0)), (100, off(40, channel=0)), (100, end()))
    second = track((0, on(KICK, channel=1)), (100, off(KICK, channel=1)), (100, end()))
    song = save(tmp_path / "two.mid", first, second, ppq=PPQ)

    asked = analyze(song, "--from-map", "gm")
    request = output(asked)["decisions"][0]
    answered = analyze(song, "--from-map", "gm", "--track", str(request["options"][1]["value"]))

    assert asked.exit_code == EXIT_OPEN
    assert list(output(asked)) == ["decisions"]
    assert request["kind"] == "drum_track"
    assert request["answer_with"] == ["track"]
    assert [option["value"] for option in request["options"]] == [0, 1]
    assert output(answered)["summary"]["track"] == {"index": 1, "name": "", "reason": "argument"}


def answer(request: Json) -> Json:
    """The answers file entry that settles a request, built from what the request lists."""
    details = request["details"]
    match request["kind"]:
        case "unmapped_notes":
            return {"unmapped": {str(group["pitch"]): "drop" for group in details["notes"]}}
        case "ambiguous_bars":
            return {
                "grids": {
                    f"{bar['bar']},{beat['beat']}": beat["alternatives"][0]
                    for bar in details["bars"]
                    for beat in bar["beats"]
                }
            }
        case "hit_types":
            return {"hit_types": {family["family"]: {} for family in details["families"]}}
        case kind:
            raise AssertionError(f"no answer in the file for {kind}")


@pytest.mark.parametrize("kind", ["unmapped_notes", "ambiguous_bars", "hit_types"])
def test_an_answer_built_from_its_request_settles_it(tmp_path: Path, kind: str) -> None:
    song = drums(tmp_path, UNCLEAR)
    asked = output(analyze(song, "--from-map", "gm"))
    (request,) = [request for request in asked["decisions"] if request["kind"] == kind]

    result = analyze(song, "--from-map", "gm", "--answers", answers_file(tmp_path, answer(request)))

    assert result.exit_code == EXIT_OPEN
    assert kinds(result) == [other["kind"] for other in asked["decisions"] if other != request]


def test_answers_to_every_request_close_them_all(tmp_path: Path) -> None:
    song = drums(tmp_path, UNCLEAR)
    asked = output(analyze(song, "--from-map", "gm"))
    answers: Json = {}
    for request in asked["decisions"]:
        answers |= answer(request)

    result = analyze(song, "--from-map", "gm", "--answers", answers_file(tmp_path, answers))

    assert result.exit_code == 0, result.output
    summary = output(result)["summary"]
    assert summary["notes"] == {"read": 4, "score": 3, "pending": 0, "dropped": 1}
    assert summary["beats"]["ambiguous"] == 0
    assert summary["beats"]["grids"] == {"16th": 2, "8th_triplet": 0, "16th_triplet": 0, "32nd": 1}
    assert summary["hit_types"]["low_confidence"] == 0


def test_an_unmapped_pitch_can_be_given_an_articulation(tmp_path: Path) -> None:
    answers = {"unmapped": {str(UNMAPPED): "tom.1.hit"}}

    result = analyze(
        drums(tmp_path, UNCLEAR), "--from-map", "gm", "--answers", answers_file(tmp_path, answers)
    )

    summary = output(result)["summary"]
    assert summary["notes"] == {"read": 4, "score": 4, "pending": 0, "dropped": 0}
    assert summary["families"] == {"kick": 2, "snare": 1, "tom": 1}


@pytest.mark.parametrize(
    ("answers", "message"),
    [
        ("{", "Invalid JSON"),
        ("[]", "Input should be an object"),
        ({"tempo": 120}, "tempo: Extra inputs are not permitted"),
        ({"bpm": 120}, "bpm: given as --bpm, not in the answers file"),
        ({"from_map": "gm"}, "from_map: given as --from-map"),
        ({"unmapped": {"x": "drop"}}, "unmapped.x: 'x' is not a pitch, 0 to 127"),
        ({"unmapped": {"128": "drop"}}, "unmapped.128: Input should be less than or equal to 127"),
        ({"unmapped": {"99": 5}}, "unmapped.99: Input should be a valid string"),
        ({"grids": {"1:1": "16th"}}, """grids.1:1: '1:1' is not a beat as "bar,beat\""""),
        ({"grids": {"0,1": "8th"}}, "grids.0,1: Input should be '16th', '8th_triplet'"),
        ({"hit_types": {"snare": {"soft": 40}}}, "hit_types.snare.soft: Extra inputs"),
        (
            {"hit_types": {"snare": {"soft_below": 90, "accent_from": 60}}},
            "hit_types.snare: soft_below is above accent_from",
        ),
        (
            {"unmapped": {"99": "snare.nope"}},
            "unmapped.99: note 99: General MIDI (Percussion key map) has no snare.nope",
        ),
        (
            {"unmapped": {"50": "drop"}},
            "unmapped.50: note 50: the drum track has no note of this pitch",
        ),
        (
            {"grids": {"5,0": "16th"}},
            "grids.5,0: bar 6, beat 1 is after the last bar with drums, bar 1",
        ),
        (
            {"hit_types": {"tom": {}}},
            "hit_types.tom: the drums have no tom notes, only kick and snare",
        ),
    ],
    ids=lambda value: None if isinstance(value, str) else json.dumps(value),
)
def test_a_bad_answers_file_is_a_usage_error(tmp_path: Path, answers: object, message: str) -> None:
    file = answers_file(tmp_path, answers)

    result = analyze(drums(tmp_path, UNCLEAR), "--from-map", "gm", "--answers", file)

    stderr = usage_error(result)
    assert "Invalid value for '--answers'" in stderr
    assert message in stderr


def test_a_grid_a_beat_cant_have_is_a_usage_error(tmp_path: Path) -> None:
    # A beat of 7/8 is an eighth, which an 8th triplet doesn't divide.
    song = drums(tmp_path, [(0, KICK, 100)], meta=((0, signature(7, 8)),))
    answers = {"grids": {"0,0": "8th_triplet"}}

    result = analyze(song, "--from-map", "gm", "--answers", answers_file(tmp_path, answers))

    stderr = usage_error(result)
    assert "grids.0,0: bar 1, beat 1: a 8th_triplet grid doesn't fit a beat of 1/8" in stderr


@pytest.mark.parametrize(
    ("from_map", "message"),
    [
        ("nope", "no library 'nope'; there are addictive-drums-2, ezdrummer-3"),
        ("iof-drummer", "iof-drummer has the kits default, old; name one"),
        ("gm/nope", "gm has no kit 'nope'; it has default"),
        ("iof-drummer/", "iof-drummer has no kit ''; it has default, old"),
    ],
)
def test_a_map_that_isnt_built_in_is_a_usage_error(
    tmp_path: Path, from_map: str, message: str
) -> None:
    result = analyze(drums(tmp_path, GROOVE), "--from-map", from_map)

    stderr = usage_error(result)
    assert "Invalid value for '--from-map'" in stderr
    assert message in stderr


@pytest.mark.parametrize(
    "args",
    [
        ["missing.mid", "--from-map", "gm"],
        ["--from-map", "gm"],
        ["DRUMS", "--from-map", "gm", "--track", "-1"],
        ["DRUMS"],
    ],
)
def test_bad_flags_are_usage_errors(tmp_path: Path, args: list[str]) -> None:
    song = drums(tmp_path, GROOVE)

    usage_error(analyze(*(str(song) if arg == "DRUMS" else arg for arg in args)))


@pytest.mark.parametrize("bpm", ["0", "-120", "1e-320", "3.576", "60000001", "inf", "nan"])
def test_a_tempo_a_midi_file_cant_hold_is_a_usage_error(tmp_path: Path, bpm: str) -> None:
    result = analyze(drums(tmp_path, GROOVE), "--from-map", "gm", "--bpm", bpm)

    stderr = usage_error(result)
    assert "Invalid value for '--bpm'" in stderr
    assert "is not a tempo a MIDI file can hold, from 3.577 to 60000000 BPM" in stderr


@pytest.mark.parametrize("bpm", ["3.577", "60000000"])
def test_the_slowest_and_fastest_tempos_are_taken(tmp_path: Path, bpm: str) -> None:
    result = analyze(drums(tmp_path, GROOVE), "--from-map", "gm", "--bpm", bpm)

    assert result.exit_code == EXIT_OPEN, result.output
    assert output(result)["summary"]["tempo"]["bpm"] == float(bpm)


def test_the_slowest_and_fastest_tempos_fit_a_midi_tempo_event() -> None:
    # A tempo event holds 1 to 16,777,215 microseconds per quarter note, which mido checks as it
    # builds one, and the tempo written is the nearest whole microsecond.
    assert tempo(MAX_BPM).bytes()[3:] == [0, 0, 1]
    assert tempo(MIN_BPM).bytes()[3:] == list((16_773_833).to_bytes(3))
    with pytest.raises(ValueError, match="16777215"):
        tempo(MIN_BPM - 0.001)


def test_a_file_that_isnt_midi_is_a_usage_error(tmp_path: Path) -> None:
    file = tmp_path / "notes.mid"
    file.write_text("not MIDI")

    assert "not a readable MIDI file" in usage_error(analyze(file, "--from-map", "gm"))


def test_an_empty_file_is_a_usage_error(tmp_path: Path) -> None:
    file = tmp_path / "empty.mid"
    file.write_bytes(b"")

    stderr = usage_error(analyze(file, "--from-map", "gm"))

    assert "Invalid value for 'MIDI_FILE': not a readable MIDI file: EOFError" in stderr


def test_a_file_with_no_notes_is_a_usage_error(tmp_path: Path) -> None:
    file = save(tmp_path / "silent.mid", track((0, tempo(120)), (0, name("Drums")), (960, end())))

    stderr = usage_error(analyze(file, "--from-map", "gm"))

    assert "Invalid value for 'MIDI_FILE': the file has no notes" in stderr


def test_another_error_is_a_crash_not_a_bad_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fails(*args: object, **kwargs: object) -> None:
        raise ValueError("not about an answer")

    monkeypatch.setattr("human_o_matic.cli.normalize", fails)
    file = answers_file(tmp_path, ALL_NORMAL)

    result = analyze(drums(tmp_path, GROOVE), "--from-map", "gm", "--answers", file)

    assert result.exit_code == 1
    assert isinstance(result.exception, ValueError)
    assert "--answers" not in result.output


def test_the_kit_is_named_by_library_and_kit(tmp_path: Path) -> None:
    result = analyze(drums(tmp_path, GROOVE), "--from-map", "iof-drummer/old")

    assert output(result)["summary"]["kit"] == "iof-drummer/old"
    assert find_kit("gm").ref == find_kit("gm/default").ref == "gm/default"


def test_analyze_is_deterministic(tmp_path: Path) -> None:
    rng = np.random.default_rng(np.random.SeedSequence(5))
    notes = [
        (int(tick), int(rng.choice([KICK, SNARE, HAT, UNMAPPED, 50])), int(rng.integers(20, 128)))
        for tick in rng.integers(0, 32 * PPQ, 400)
    ]
    song = drums(tmp_path, notes)

    first, second = analyze(song, "--from-map", "gm"), analyze(song, "--from-map", "gm")

    assert first.exit_code == second.exit_code == EXIT_OPEN
    assert first.stdout_bytes == second.stdout_bytes


def test_analyze_writes_no_file(tmp_path: Path) -> None:
    song = drums(tmp_path, UNCLEAR)
    file = answers_file(tmp_path, {"unmapped": {"99": "drop"}})
    before = sorted(tmp_path.iterdir())
    data = song.read_bytes()

    analyze(song, "--from-map", "gm", "--answers", file)

    assert sorted(tmp_path.iterdir()) == before
    assert song.read_bytes() == data


def test_the_printed_summary_is_the_summary_function(tmp_path: Path) -> None:
    path = drums(tmp_path, UNCLEAR)
    song = read_midi(path)

    result = analyze(path, "--from-map", "gm", "--bpm", "90")

    expected = summarize(str(path), song, normalize(song, find_kit("gm"), bpm=90), bpm=90)
    assert output(result)["summary"] == expected.model_dump(mode="json")


# The plain functions under the command.


def test_the_answers_file_reads_into_the_arguments_normalize_takes() -> None:
    text = json.dumps(
        {
            "unmapped": {"99": "drop", "100": "tom.1.hit"},
            "grids": {"32,1": "8th_triplet", "0,3": "32nd"},
            "hit_types": {"snare": {"soft_below": 64}, "kick": {}},
        }
    )

    answers = read_answers(text)

    assert answers.unmapped == {99: "drop", 100: "tom.1.hit"}
    assert answers.grids == {(32, 1): "8th_triplet", (0, 3): "32nd"}
    assert answers.hit_types == {"snare": HitTypeBounds(soft_below=64), "kick": HitTypeBounds()}
    assert read_answers("{}") == read_answers('{"unmapped": {}, "grids": {}, "hit_types": {}}')


def test_every_problem_in_an_answers_file_is_listed() -> None:
    with pytest.raises(ValueError, match="; ") as raised:
        read_answers('{"unmapped": {"x": "drop"}, "grids": {"1": "16th"}}')

    assert str(raised.value) == (
        "unmapped.x: 'x' is not a pitch, 0 to 127; "
        """grids.1: '1' is not a beat as "bar,beat", both counted from 0"""
    )


def test_the_summary_counts_the_score(tmp_path: Path) -> None:
    # Two unmapped pitches, one left out by the answer and one still pending, and two clear
    # groups of snare velocities beside a flat kick.
    notes = [
        *UNCLEAR,
        (2 * PPQ + PPQ // 2, SNARE, 105),
        (3 * PPQ, 98, 100),
        (3 * PPQ, SNARE, 40),
        (3 * PPQ + PPQ // 2, SNARE, 41),
    ]
    song = read_midi(drums(tmp_path, notes))
    normalized = normalize(song, find_kit("gm"), unmapped={UNMAPPED: "drop"})

    summary = summarize("song.mid", song, normalized)

    assert summary.notes.model_dump() == {"read": 8, "score": 6, "pending": 1, "dropped": 1}
    assert summary.beats.model_dump() == {
        "count": 4,
        "ambiguous": 1,
        "grids": {"16th": 3, "8th_triplet": 1, "16th_triplet": 0, "32nd": 0},
    }
    assert summary.families == {"kick": 2, "snare": 4}
    assert summary.hit_types.model_dump() == {
        "soft": 2,
        "normal": 4,
        "accent": 0,
        "low_confidence": 2,
    }
    assert summary.low_confidence == {}
    assert summary.bars == 1


def test_the_summary_counts_notes_read_through_low_confidence_names(tmp_path: Path) -> None:
    kit = built_in_maps().kit("ezdrummer-3")
    song = read_midi(drums(tmp_path, GROOVE))
    normalized = normalize(song, kit)

    summary = summarize("song.mid", song, normalized)

    assert summary.low_confidence == {e.articulation: e.count for e in normalized.low_confidence}
    assert sum(summary.low_confidence.values()) == sum(
        kit.articulation(note.articulation).confidence == "low" for note in normalized.score.notes
    )
    assert summary.low_confidence


def test_the_summary_tells_the_tempo_and_time_signatures(tmp_path: Path) -> None:
    meta = (
        (0, signature(4, 4)),
        (2 * 4 * PPQ, tempo(140)),
        (2 * 4 * PPQ, signature(3, 4)),
        (2 * 4 * PPQ + 3 * PPQ, tempo(100)),
    )
    notes = [(beat * PPQ, KICK, 100) for beat in range(8 + 3 * 3)]
    song = read_midi(drums(tmp_path, notes, meta=meta))

    from_file = summarize("song.mid", song, normalize(song, find_kit("gm")))
    replaced = summarize("song.mid", song, normalize(song, find_kit("gm"), bpm=90.5), bpm=90.5)

    assert from_file.tempo.model_dump() == {
        "given": False,
        "replaced": False,
        "bpm": 120.0,
        "changes": 2,
        "min_bpm": 100.0,
        "max_bpm": 140.0,
    }
    tempo_given = replaced.tempo
    assert (tempo_given.given, tempo_given.replaced, tempo_given.changes) == (True, True, 0)
    assert tempo_given.bpm == 90.5
    assert from_file.time_signatures.model_dump() == {
        "assumed": False,
        "changes": ((0, "4/4"), (2, "3/4")),
    }
    assert from_file.bars == 5
    assert (from_file.ppq, from_file.source_ppq) == (PPQ, PPQ)
