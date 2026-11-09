"""`human-o-matic render`, run through typer's runner on MIDI files built in code (ADR 0054)."""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from grooves import BAR, COWBELL, KICK, PPQ, RIDE, SNARE, Hit, midi_file, rock
from human_o_matic.cli import app, read_plan
from human_o_matic.controls import MAX_SEED, ControlVector
from human_o_matic.midi.io import read_midi

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
    assert (summary["style"], summary["placeholder"], summary["seed"]) == ("tight", True, 7)
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


def test_the_same_file_answers_plan_and_seed_write_the_same_bytes(tmp_path: Path) -> None:
    first = render(*clean_args(tmp_path))
    again = render(*clean_args(tmp_path), "--overwrite")
    other = tmp_path / "other.mid"

    assert first.exit_code == again.exit_code == 0
    render(*clean_args(tmp_path)[:-2], "-o", other)
    assert (tmp_path / "out.mid").read_bytes() == other.read_bytes()


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
    args = [song, "--from-map", "gm", "--to-map", "sleep-token-ii", "--seed", "1"]

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
        ["--style", "loose"],
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
