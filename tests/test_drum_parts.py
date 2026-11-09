"""Each drum note's role, from families, names, ticks and hit types (ADR 0047)."""

from grooves import (
    BAR,
    CHINA,
    CRASH,
    HAT,
    KICK,
    PEDAL,
    PPQ,
    RIDE,
    SIXTEENTH,
    SNARE,
    SOFT,
    TOM_1,
    TOM_2,
    TOM_3,
    Hit,
    normalized,
    rock,
    song,
)
from human_o_matic.instruments.drums import drum_parts
from human_o_matic.normalize.score import Score
from human_o_matic.render.parts import Part, Role


def parts_of(hits: list[Hit]) -> tuple[Score, tuple[Part, ...]]:
    score = normalized(song(hits)).score
    return score, drum_parts(score)


def roles_at(hits: list[Hit], pitch: int) -> list[tuple[int, Role]]:
    """`(tick, role)` of each note of the pitch, in order."""
    score, parts = parts_of(hits)
    return [
        (note.tick, part.role)
        for note, part in zip(score.notes, parts, strict=True)
        if note.source.pitch == pitch
    ]


def test_a_rock_groove_has_kick_backbeats_and_riders() -> None:
    score, parts = parts_of(rock(2))

    roles = {(note.family, part.role) for note, part in zip(score.notes, parts, strict=True)}

    assert roles == {("kick", "kick"), ("snare", "backbeat"), ("hat", "rider")}
    assert {
        part.limb for note, part in zip(score.notes, parts, strict=True) if note.family == "snare"
    } == {"snare"}


def test_a_snare_on_the_bar_s_first_beat_or_off_the_beat_or_soft_is_no_backbeat() -> None:
    hits: list[Hit] = [
        (0, SNARE),
        (PPQ, SNARE),
        (PPQ + PPQ // 2, SNARE),
        (2 * PPQ, SNARE, SOFT),
        (3 * PPQ, SNARE),
    ]

    assert roles_at(hits, SNARE) == [
        (0, "snare"),
        (PPQ, "backbeat"),
        (PPQ + PPQ // 2, "snare"),
        (2 * PPQ, "snare"),
        (3 * PPQ, "backbeat"),
    ]


def test_quarter_note_hat_hits_alternate_with_the_strong_ones_on_the_snare() -> None:
    score, parts = parts_of(rock(1))

    hats = [
        (note.tick, part.rider, part.strong)
        for note, part in zip(score.notes, parts, strict=True)
        if note.family == "hat"
    ]

    assert hats == [
        (0, "alternate", False),
        (PPQ // 2, "weak", False),
        (PPQ, "alternate", True),
        (3 * PPQ // 2, "weak", False),
        (2 * PPQ, "alternate", False),
        (5 * PPQ // 2, "weak", False),
        (3 * PPQ, "alternate", True),
        (7 * PPQ // 2, "weak", False),
    ]


def test_a_rider_hit_alone_is_at_its_center_and_the_hat_pedal_is_no_rider() -> None:
    score, parts = parts_of([(0, RIDE), (3 * PPQ, RIDE), (PPQ, PEDAL)])

    found = [
        (note.family, part.role, part.rider) for note, part in zip(score.notes, parts, strict=True)
    ]

    assert found == [
        ("ride", "rider", "center"),
        ("hat", "other", "center"),
        ("ride", "rider", "center"),
    ]


def test_a_crash_alone_or_starting_a_run_on_a_beat_is_an_accent_and_the_rest_ride() -> None:
    crashes: list[Hit] = [(0, CRASH), *((BAR + eighth * PPQ // 2, CRASH) for eighth in range(4))]
    off_beat: list[Hit] = [(3 * BAR + PPQ // 2, CHINA), (3 * BAR + PPQ, CHINA)]
    lone: list[Hit] = [(5 * BAR + PPQ // 2, CHINA)]

    assert roles_at(crashes, CRASH) == [
        (0, "accent_cymbal"),
        (BAR, "accent_cymbal"),
        *((BAR + eighth * PPQ // 2, "rider") for eighth in range(1, 4)),
    ]
    assert [role for _, role in roles_at(off_beat + lone, CHINA)] == [
        "rider",
        "rider",
        "accent_cymbal",
    ]


def test_a_run_of_snare_and_toms_is_a_fill_with_a_crescendo_at_its_end() -> None:
    fill: list[Hit] = [
        (BAR - 4 * SIXTEENTH, SNARE),
        (BAR - 3 * SIXTEENTH, SNARE),
        (BAR - 2 * SIXTEENTH, TOM_1),
        (BAR - SIXTEENTH, TOM_2),
    ]
    score, parts = parts_of([(0, KICK), *fill, (BAR, CRASH)])

    filled = [
        (part.role, part.metric, part.hand)
        for note, part in zip(score.notes, parts, strict=True)
        if note.family in ("snare", "tom")
    ]

    assert filled == [("fill", 0, 1), ("fill", 2, -1), ("fill", 1, 1), ("fill", 2, -1)]
    rises = [part.crescendo for part in parts if part.role == "fill"]
    assert rises == [0.0, 1 / 3, 2 / 3, 1.0]


def test_snare_quarters_or_8ths_without_a_tom_are_no_fill() -> None:
    quarters: list[Hit] = [(beat * PPQ, SNARE) for beat in range(4)]
    eighths: list[Hit] = [(eighth * PPQ // 2, SNARE) for eighth in range(8)]

    assert {role for _, role in roles_at(quarters, SNARE)} == {"snare", "backbeat"}
    assert {role for _, role in roles_at(eighths, SNARE)} == {"snare", "backbeat"}


def test_a_run_that_goes_on_past_two_bars_is_no_fill() -> None:
    toms: list[Hit] = [(eighth * PPQ // 2, TOM_3) for eighth in range(17)]
    two_bars = toms[:16]

    assert {role for _, role in roles_at(toms, TOM_3)} == {"other"}
    assert {role for _, role in roles_at(two_bars, TOM_3)} == {"fill"}


def test_four_kicks_at_16ths_are_double_kick_with_the_feet_by_turns() -> None:
    hits: list[Hit] = [(step * SIXTEENTH, KICK) for step in range(4)]
    three: list[Hit] = [(BAR + step * SIXTEENTH, KICK) for step in range(3)]
    score, parts = parts_of(hits + three)

    kicks = [(part.role, part.foot) for part in parts]

    assert kicks == [
        *(("double_kick", foot) for foot in (1, -1, 1, -1)),
        *(("kick", 0) for _ in range(3)),
    ]
    assert len(score.notes) == 7


def test_a_grace_takes_its_main_note_s_part() -> None:
    grace = round(PPQ * 30 / 500)
    score, parts = parts_of([(PPQ - grace, SNARE, SOFT), (PPQ, SNARE), (0, HAT)])

    (main,) = [
        p
        for note, p in zip(score.notes, parts, strict=True)
        if note.family == "snare" and note.grace_of is None
    ]
    (graced,) = [p for note, p in zip(score.notes, parts, strict=True) if note.grace_of is not None]

    assert graced == main
    assert main.role == "backbeat"
