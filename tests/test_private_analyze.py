"""`human-o-matic analyze` on a sample of the performed MIDI in `private/midi/`, checking only the
shape of what it prints. The folder is never committed (ADR 0007), and the test skips when it is
missing or empty."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from human_o_matic.cli import EXIT_OPEN, Summary, app
from human_o_matic.decisions import DecisionRequest
from test_private_midi import private_sample

SAMPLE_SIZE = 14
FALLBACK_BPM = "120"


def analyze(path: Path, *flags: str) -> tuple[int, dict[str, object], list[DecisionRequest]]:
    """The exit code, the printed JSON and its requests."""
    result = CliRunner().invoke(app, ["analyze", str(path), "--from-map", "gm", *flags])
    assert result.exit_code in (0, EXIT_OPEN), result.output
    out = json.loads(result.stdout)
    assert isinstance(out, dict)
    decisions = out["decisions"]
    assert isinstance(decisions, list)
    return result.exit_code, out, [DecisionRequest.model_validate(item) for item in decisions]


@pytest.mark.private
def test_analyze_prints_a_summary_and_requests_for_performed_midi() -> None:
    sample = private_sample(SAMPLE_SIZE)
    if not sample:
        pytest.skip("no MIDI in private/midi/")
    for path in sample:
        flags: list[str] = []
        code, out, requests = analyze(path)
        # A file without a tempo, or with an unclear drum track, asks first, with no summary.
        for _ in range(2):
            if "summary" in out:
                break
            assert list(out) == ["decisions"]
            assert code == EXIT_OPEN
            (request,) = requests
            if request.kind == "tempo":
                flags += ["--bpm", FALLBACK_BPM]
            else:
                assert request.kind == "drum_track"
                flags += ["--track", str(request.options[0].value)]
            code, out, requests = analyze(path, *flags)

        assert list(out) == ["summary", "decisions"]
        summary = Summary.model_validate(out["summary"])
        assert (code == EXIT_OPEN) == bool(requests)
        assert {request.kind for request in requests} <= {
            "unmapped_notes",
            "ambiguous_bars",
            "hit_types",
        }
        counts = summary.notes
        assert counts.read == counts.score + counts.pending + counts.dropped
        assert sum(summary.families.values()) == counts.score
        assert sum(summary.beats.grids.values()) == summary.beats.count
