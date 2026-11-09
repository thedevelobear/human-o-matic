"""The M2 exit (ADR 0034): the sections found in the songs of the hand labels in
`private/labels/`, with markers left out, scored against the labels. The folder is never
committed (ADR 0007), and the test skips when it is missing or holds no label file.

With fewer than `EXIT_TRACKS` labelled tracks it skips with the scores in its reason, which
`pytest -m private -rs` shows, so a pass always means the exit holds. The scores name each track
by its number in the label files' name order, never by its file, since the report may be passed
on. A label file that is wrong is still named, so it can be fixed.
"""

from pathlib import Path

import pytest

from human_o_matic.analyze.labels import Measured, measure, read_labels
from human_o_matic.analyze.scoring import EXIT_F1, EXIT_TRACKS, Totals, totals

PRIVATE = Path(__file__).resolve().parents[1] / "private"
LABELS = PRIVATE / "labels"


def describe(results: list[Measured], total: Totals) -> str:
    """Each track's scores, by its number from 1, then the means and the pooled F1, on one line
    each."""
    lines = [
        f"track {number}{' (tuned)' if result.label.tuned else ''}: "
        f"precision {result.score.precision:.3f}, recall {result.score.recall:.3f}, "
        f"F1 {result.score.f1:.3f}"
        for number, result in enumerate(results, start=1)
    ]
    untuned = (
        f"{total.untuned_mean_f1:.3f} over {total.untuned} untuned"
        if total.untuned_mean_f1 is not None
        else "none, as every track is tuned"
    )
    lines.append(
        f"mean F1 {total.mean_f1:.3f} over {total.tracks}, pooled F1 {total.pooled_f1:.3f}, "
        f"untuned mean F1 {untuned}"
    )
    return "\n".join(lines)


@pytest.mark.private
def test_the_sections_match_the_hand_labels() -> None:
    labels = read_labels(LABELS) if LABELS.is_dir() else ()
    if not labels:
        pytest.skip("no label files in private/labels/")
    results = [measure(path, label, PRIVATE) for path, label in labels]
    total = totals([result.score for result in results], [result.label.tuned for result in results])
    report = describe(results, total)

    if total.tracks < EXIT_TRACKS:
        pytest.skip(
            f"{total.tracks} labelled tracks of the {EXIT_TRACKS} the exit needs, so it isn't "
            f"measured yet:\n{report}"
        )
    assert total.mean_f1 >= EXIT_F1, report
