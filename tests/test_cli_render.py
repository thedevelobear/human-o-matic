"""`human-o-matic render`, run through typer's runner on MIDI files built in code (ADR 0054)."""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from grooves import (
    BAR,
    COWBELL,
    HAT,
    KICK,
    PPQ,
    RIDE,
    SNARE,
    TOM_1,
    TOM_2,
    TOM_3,
    Hit,
    midi_file,
    rock,
)
from human_o_matic.cli import app, read_plan
from human_o_matic.controls import MAX_SEED, ControlVector
from human_o_matic.maps.loader import find_kit
from human_o_matic.midi.io import read_midi
from midi_files import MidoMessage, build, end, name, off, on, tempo, track

type Json = dict[str, Any]
"""Parsed JSON, which the assertions index freely."""

TYPED = {"soft_below": 50, "accent_from": 110}
ANSWERS = {"hit_types": {"kick": TYPED, "snare": TYPED, "hat": TYPED}}

runner = CliRunner()


def write(path: Path, hits: list[Hit], name: str = "in.mid") -> Path:
    file = path / name
    file.write_bytes(midi_file(hits))
    return file


def json_file(path: Path, name: str, content: object) -> Path:
    file = path / name
    file.write_text(content if isinstance(content, str) else json.dumps(content))
    return file


def render(*args: str | Path) -> Result:
    return runner.invoke(app, ["render", *(str(arg) for arg in args)])


def output(result: Result) -> Json:
    out = json.loads(result.stdout)
    assert isinstance(out, dict)
    return out


def usage_error(result: Result) -> str:
    assert result.exit_code == 2, result.output
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    return result.stderr


def clean_args(path: Path, *extra: str | Path) -> list[str | Path]:
    """A song with every request answered, rendered to `out.mid` with seed 7."""
    song = write(path, rock(8))
    answers = json_file(path, "answers.json", ANSWERS)
    return [
        song,
        "--from-map",
        "gm",
        "--answers",
        answers,
        "--seed",
        "7",
        "-o",
        path / "out.mid",
        *extra,
    ]


def test_a_clean_render_writes_the_file_and_prints_its_summary(tmp_path: Path) -> None:
    result = render(*clean_args(tmp_path))

    assert result.exit_code == 0, result.output
    out = output(result)
    assert list(out) == ["summary", "sections", "decisions"]
    assert out["decisions"] == []
    summary = out["summary"]
    assert summary["kit"] == summary["to_kit"] == "gm/default"
    assert (summary["style"], summary["placeholder"], summary["seed"]) == ("tight", False, 7)
    assert summary["notes"] == {"written": 96, "kept": 0, "dropped": 0}
    assert set(summary["guards"]) >= {"capped", "tick_zero", "gap", "nudged", "unmet"}
    (section,) = out["sections"]
    assert (section["start"], section["bars"], section["group"], section["skip"]) == (
        0,
        8,
        "A",
        False,
    )
    assert section["stats"]["notes"] == 96
    written = read_midi(tmp_path / "out.mid")
    assert len(written.notes) == 96
    assert "\n" not in result.stdout.strip()
    assert summary["conversion"] == {
        "changed": [],
        "collisions": [],
        "low_confidence": {"read": {}, "written": {}},
    }


def test_the_same_file_answers_plan_and_seed_write_the_same_bytes(tmp_path: Path) -> None:
    out_file = tmp_path / "out.mid"

    first = render(*clean_args(tmp_path))
    written = out_file.read_bytes()
    again = render(*clean_args(tmp_path), "--overwrite")
    other = render(*clean_args(tmp_path)[:-2], "--seed", "8", "-o", tmp_path / "other.mid")

    assert first.exit_code == again.exit_code == other.exit_code == 0
    assert out_file.read_bytes() == written
    assert first.stdout == again.stdout
    assert (tmp_path / "other.mid").read_bytes() != written


def test_an_open_request_prints_the_sections_and_requests_writes_nothing_and_exits_3(
    tmp_path: Path,
) -> None:
    song = write(tmp_path, rock(4))
    out_file = tmp_path / "out.mid"

    result = render(song, "--from-map", "gm", "--seed", "1", "-o", out_file)

    assert result.exit_code == 3, result.output
    out = output(result)
    assert list(out) == ["sections", "decisions"]
    assert [request["kind"] for request in out["decisions"]] == ["hit_types"]
    assert out["sections"] == [{"start": 0, "bars": 4, "group": "A"}]
    assert not out_file.exists()


def test_a_conversion_request_is_open_until_a_substitution_answers_it(tmp_path: Path) -> None:
    song = write(tmp_path, [*rock(2), (0, COWBELL)])
    typed = {"hit_types": {**ANSWERS["hit_types"], "cowbell": TYPED}}
    dropped = {**typed, "substitutions": {"cowbell.hit": "drop"}}
    args = [song, "--from-map", "gm", "--to-map", "sleep-token-ii/default", "--seed", "1"]

    asked = render(*args, "--answers", json_file(tmp_path, "a.json", typed), "-o", tmp_path / "a")
    settled = render(
        *args, "--answers", json_file(tmp_path, "b.json", dropped), "-o", tmp_path / "b.mid"
    )

    assert asked.exit_code == 3, asked.output
    assert "conversion" in [request["kind"] for request in output(asked)["decisions"]]
    assert not (tmp_path / "a").exists()
    assert settled.exit_code == 0, settled.output
    assert output(settled)["summary"]["notes"]["dropped"] == 1
    assert output(settled)["summary"]["to_kit"].startswith("sleep-token-ii/")
    assert output(settled)["summary"]["conversion"]["changed"] == [
        {
            "source": "cowbell.hit",
            "target": "drop",
            "notes": 1,
            "steps": [{"kind": "picked", "asked": "cowbell.hit", "used": "drop"}],
        }
    ]


TOMS = {"hit_types": {**ANSWERS["hit_types"], "tom": TYPED}}


def test_the_summary_counts_the_notes_written_as_another_articulation(tmp_path: Path) -> None:
    song = write(tmp_path, [*rock(2), (BAR - PPQ, TOM_3), (2 * BAR - PPQ, TOM_3)])
    answers = json_file(tmp_path, "answers.json", TOMS)
    args = [song, "--from-map", "gm", "--answers", answers, "--seed", "1"]

    result = render(*args, "--to-map", "sleep-token-ii/default", "-o", tmp_path / "out.mid")

    assert result.exit_code == 0, result.output
    conversion = output(result)["summary"]["conversion"]
    # GM's six toms re-spread onto the target's three, so its third becomes the second.
    assert conversion["changed"] == [
        {
            "source": "tom.3.hit",
            "target": "tom.2.hit",
            "notes": 2,
            "steps": [{"kind": "piece", "asked": "tom.3.hit", "used": "tom.2.hit"}],
        }
    ]
    assert conversion["collisions"] == []


def test_toms_that_land_on_one_pitch_at_one_tick_are_a_collision_and_two_hits(
    tmp_path: Path,
) -> None:
    song = write(tmp_path, [*rock(2), (BAR + 3 * PPQ, TOM_1), (BAR + 3 * PPQ, TOM_2)])
    answers = json_file(tmp_path, "answers.json", TOMS)
    target = find_kit("sleep-token-ii/default")
    out_file = tmp_path / "out.mid"

    result = render(
        song,
        "--from-map",
        "gm",
        "--answers",
        answers,
        "--seed",
        "1",
        "--to-map",
        target.ref,
        "-o",
        out_file,
    )

    assert result.exit_code == 0, result.output
    pitch = target.write("tom.1.hit").pitch
    channel = target.write("tom.1.hit").channel
    assert output(result)["summary"]["conversion"]["collisions"] == [
        {
            "pitch": pitch,
            "channel": channel,
            "count": 1,
            "notes": 2,
            "sources": ["tom.1.hit", "tom.2.hit"],
            "positions": [[1, 3.0]],
        }
    ]
    first, second = sorted(note.start for note in read_midi(out_file).notes if note.pitch == pitch)
    assert second > first


def test_the_summary_counts_the_notes_read_and_written_through_low_confidence_names(
    tmp_path: Path,
) -> None:
    song = write(tmp_path, rock(2))
    answers = json_file(tmp_path, "answers.json", ANSWERS)
    inferred = "sleep-token-ii/groove-pack"
    to_inferred = render(
        song,
        "--from-map",
        "gm",
        "--answers",
        answers,
        "--seed",
        "1",
        "--to-map",
        inferred,
        "-o",
        tmp_path / "inferred.mid",
    )
    from_inferred = render(
        tmp_path / "inferred.mid",
        "--from-map",
        inferred,
        "--answers",
        answers,
        "--seed",
        "1",
        "--to-map",
        "gm",
        "-o",
        tmp_path / "back.mid",
    )

    assert to_inferred.exit_code == from_inferred.exit_code == 0, from_inferred.output
    counts = {"kick.hit": 4, "snare.center": 4, "hat.closed": 16}
    assert output(to_inferred)["summary"]["conversion"]["low_confidence"] == {
        "read": {},
        "written": counts,
    }
    assert output(from_inferred)["summary"]["conversion"]["low_confidence"] == {
        "read": counts,
        "written": {},
    }


def test_a_plan_sets_the_song_s_controls_and_a_section_s_by_its_first_bar(tmp_path: Path) -> None:
    ride: list[Hit] = [
        (bar * BAR + beat * PPQ, pitch)
        for bar in range(8, 16)
        for beat in range(4)
        for pitch in (RIDE, KICK if beat % 2 == 0 else SNARE)
    ]
    song = write(tmp_path, [*rock(8), *ride])
    ridden = {"hit_types": {**ANSWERS["hit_types"], "ride": TYPED}}
    answers = json_file(tmp_path, "answers.json", ridden)
    controls = {"controls": {"energy": 0.9}, "sections": {"0": {"skip": True}}}
    plan = json_file(tmp_path, "plan.json", controls)

    result = render(
        song,
        "--from-map",
        "gm",
        "--answers",
        answers,
        "--plan",
        plan,
        "--seed",
        "3",
        "-o",
        tmp_path / "out.mid",
    )

    assert result.exit_code == 0, result.output
    out = output(result)
    assert [section["skip"] for section in out["sections"]] == [True, False]
    assert out["summary"]["notes"]["kept"] == out["sections"][0]["stats"]["notes"]


@pytest.mark.parametrize(
    ("plan", "message"),
    [
        ({"sections": {"3": {"energy": 0.5}}}, "sections.3: no section starts at bar 3"),
        ({"sections": {"x": {}}}, "sections.x"),
        ({"controls": {"energy": "high"}}, "controls.energy"),
        ({"controls": {"energy": 2}}, "controls.energy"),
        ({"tempo": 120}, "tempo"),
        ("not json", "Invalid JSON"),
    ],
)
def test_a_bad_plan_is_a_usage_error(tmp_path: Path, plan: object, message: str) -> None:
    result = render(*clean_args(tmp_path, "--plan", json_file(tmp_path, "plan.json", plan)))

    assert message in usage_error(result)
    assert not (tmp_path / "out.mid").exists()


def test_an_existing_output_is_refused_unless_overwrite_is_given(tmp_path: Path) -> None:
    (tmp_path / "out.mid").write_bytes(b"keep")

    refused = render(*clean_args(tmp_path))

    assert "exists; give --overwrite to replace it" in usage_error(refused)
    assert (tmp_path / "out.mid").read_bytes() == b"keep"
    assert render(*clean_args(tmp_path), "--overwrite").exit_code == 0
    assert (tmp_path / "out.mid").read_bytes() != b"keep"


def test_the_input_is_never_overwritten(tmp_path: Path) -> None:
    args = clean_args(tmp_path)
    song = Path(args[0])
    before = song.read_bytes()

    result = render(*args[:-1], song, "--overwrite")

    assert "it is the input file" in usage_error(result)
    assert song.read_bytes() == before


@pytest.mark.parametrize(
    "extra",
    [
        ["--seed", "-1"],
        ["--seed", str(MAX_SEED + 1)],
        ["--style", "sloppy"],
        ["--to-map", "nope"],
        ["--bpm", "2"],
    ],
)
def test_bad_flags_are_usage_errors(tmp_path: Path, extra: list[str]) -> None:
    usage_error(render(*clean_args(tmp_path, *extra)))


def test_the_seed_and_the_output_are_required(tmp_path: Path) -> None:
    args = clean_args(tmp_path)

    usage_error(render(*args[:5], "-o", tmp_path / "out.mid"))
    usage_error(render(*args[:7]))


def test_a_substitution_the_target_can_t_play_is_a_usage_error(tmp_path: Path) -> None:
    answers = {**ANSWERS, "substitutions": {"kick.hit": "kick.nope"}}
    args = clean_args(tmp_path)
    args[4] = json_file(tmp_path, "answers.json", answers)

    assert "substitutions." in usage_error(render(*args))


def test_the_help_names_every_control_a_plan_takes() -> None:
    result = runner.invoke(app, ["render", "--help"])

    assert result.exit_code == 0, result.output
    text = " ".join(result.stdout.split())
    assert all(control in text for control in ControlVector.model_fields)
    assert '{"controls": {"energy": 0.8}, "sections": {"8": {"skip": true}}}' in text


def test_a_plan_file_reads_into_controls_by_bar() -> None:
    plan = read_plan('{"controls": {"feel": 0.2}, "sections": {"8": {"arc": "build"}}}')

    assert plan.controls == ControlVector(feel=0.2)
    assert plan.sections == {8: ControlVector(arc="build")}


def test_an_error_in_the_render_is_a_crash_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fails(*args: object, **kwargs: object) -> None:
        raise ValueError("not about an answer")

    monkeypatch.setattr("human_o_matic.cli.render", fails)

    result = render(*clean_args(tmp_path))

    assert result.exit_code == 1
    assert isinstance(result.exception, ValueError)
    assert not (tmp_path / "out.mid").exists()


def test_track_settles_which_track_holds_the_drums(tmp_path: Path) -> None:
    def part(pitches: tuple[int, int]) -> list[MidoMessage]:
        items: list[tuple[int, MidoMessage]] = [(0, tempo(120))]
        for beat in range(8):
            pitch = pitches[beat % 2]
            items.extend([(beat * PPQ, on(pitch, channel=0)), (beat * PPQ + 10, off(pitch, 0))])
        return track(*items, (8 * PPQ, end()))

    song = tmp_path / "two.mid"
    song.write_bytes(build(part((60, 64)), part((KICK, SNARE)), ppq=PPQ))
    answers = json_file(tmp_path, "answers.json", {"hit_types": {"kick": TYPED, "snare": TYPED}})
    args = [song, "--from-map", "gm", "--answers", answers, "--seed", "1"]

    asked = render(*args, "-o", tmp_path / "a.mid")
    chosen = render(*args, "--track", "1", "-o", tmp_path / "b.mid")

    assert asked.exit_code == 3, asked.output
    assert output(asked) == {"sections": [], "decisions": output(asked)["decisions"]}
    assert [request["kind"] for request in output(asked)["decisions"]] == ["drum_track"]
    assert not (tmp_path / "a.mid").exists()
    assert chosen.exit_code == 0, chosen.output
    written = read_midi(tmp_path / "b.mid")
    assert [note.pitch for note in written.notes if note.track == 0] == [60, 64] * 4


def test_bpm_gives_a_file_with_no_tempo_its_tempo(tmp_path: Path) -> None:
    items: list[tuple[int, MidoMessage]] = [(0, name("Drums"))]
    for hit in sorted(rock(2)):
        items.extend([(hit[0], on(hit[1])), (hit[0] + 10, off(hit[1]))])
    items.sort(key=lambda item: item[0])
    song = tmp_path / "untimed.mid"
    song.write_bytes(build(track(*items, (2 * BAR, end())), ppq=PPQ))
    answers = json_file(tmp_path, "answers.json", ANSWERS)
    args = [song, "--from-map", "gm", "--answers", answers, "--seed", "1"]

    asked = render(*args, "-o", tmp_path / "a.mid")
    given = render(*args, "--bpm", "100", "-o", tmp_path / "b.mid")

    assert asked.exit_code == 3, asked.output
    assert [request["kind"] for request in output(asked)["decisions"]] == ["tempo"]
    assert given.exit_code == 0, given.output


def test_bpm_replaces_the_file_s_tempo_for_the_timing_and_the_file_keeps_its_own(
    tmp_path: Path,
) -> None:
    hats: list[Hit] = [(eighth * PPQ // 2, HAT) for eighth in range(64)]
    song = tmp_path / "slow.mid"
    song.write_bytes(midi_file(hats, bpm=60))
    answers = json_file(tmp_path, "answers.json", {"hit_types": {"hat": TYPED}})
    loose = json_file(tmp_path, "plan.json", {"controls": {"tightness": 0, "feel": 1}})
    args = [song, "--from-map", "gm", "--answers", answers, "--plan", loose, "--seed", "5"]

    as_written = render(*args, "-o", tmp_path / "file.mid")
    replaced = render(*args, "--bpm", "240", "-o", tmp_path / "given.mid")

    def furthest(name: str) -> int:
        written = sorted(note.start for note in read_midi(tmp_path / name).notes)
        return max(abs(start - hit[0]) for start, hit in zip(written, hats, strict=True))

    assert as_written.exit_code == replaced.exit_code == 0
    # 12 ms is 12 ticks at 60 BPM and 46 at 240, so only the given tempo reaches past 13.
    assert furthest("file.mid") <= 13 < furthest("given.mid") <= 47
    assert read_midi(tmp_path / "given.mid").events == read_midi(song).events
