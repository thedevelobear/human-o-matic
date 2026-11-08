import math
import time

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from human_o_matic.decisions import DecisionRequired
from human_o_matic.midi.io import parse_midi
from human_o_matic.midi.tempo import (
    BarBeat,
    TempoMap,
    TimeSignature,
    TimeSignatureMap,
    tempo_map,
    time_signature_map,
)
from midi_files import MidoMessage, build, end, off, on, signature, tempo, track


def reference_ms(ppq: int, changes: list[tuple[int, float]], tick: float) -> float:
    """Milliseconds at `tick`, walking the changes one by one."""
    segments: list[tuple[int, float]] = []
    for at, microseconds in sorted(changes, key=lambda change: change[0]):
        if segments and segments[-1][0] == at:
            segments[-1] = (at, microseconds)
        else:
            segments.append((at, microseconds))
    segments[0] = (0, segments[0][1])
    ms = 0.0
    for index, (start, microseconds) in enumerate(segments):
        last = index + 1 == len(segments)
        if last or tick < segments[index + 1][0]:
            return ms + (tick - start) * microseconds / (1000 * ppq)
        ms += (segments[index + 1][0] - start) * microseconds / (1000 * ppq)
    raise AssertionError("unreachable")


def test_one_tick_at_96_ppq_and_129_bpm_is_4_8_ms() -> None:
    data = build(track((0, tempo(129)), (0, on(36)), (1, off(36))), ppq=96)

    song = parse_midi(data)
    tempos = tempo_map(song)
    per_source_tick = tempos.tick_to_ms(10) - tempos.tick_to_ms(0)

    assert song.ppq == 960
    assert per_source_tick == pytest.approx(60_000 / 129 / 96, rel=1e-6)
    assert round(per_source_tick, 1) == 4.8
    assert tempos.bpm(0) == pytest.approx(129, rel=1e-6)


@given(st.integers(0, 10_000_000))
def test_tick_to_ms_to_tick_is_within_one_output_tick(tick: int) -> None:
    tempos = TempoMap(960, [0, 96_000, 500_000], [465_116, 300_000, 1_000_000])

    back = tempos.ms_to_tick(tempos.tick_to_ms(tick))

    assert abs(back - tick) < 1
    assert round(back) == tick


def test_a_file_with_no_tempo_is_a_decision_request() -> None:
    song = parse_midi(build(track((0, signature(4, 4)), (0, on(36)), (1, off(36))), ppq=96))

    with pytest.raises(DecisionRequired) as raised:
        tempo_map(song)

    request = raised.value.request
    assert request.kind == "tempo"
    assert request.answer_with == ("bpm",)
    assert "BPM" in request.message
    assert request.model_dump(mode="json")["kind"] == "tempo"


def test_a_given_bpm_supplies_the_tempo() -> None:
    song = parse_midi(build(track((0, on(36)), (96, off(36))), ppq=96))

    tempos = tempo_map(song, bpm=129)

    assert len(tempos) == 1
    assert tempos.tick_to_ms(960) == pytest.approx(60_000 / 129)


def test_a_given_bpm_replaces_the_file_tempo() -> None:
    song = parse_midi(build(track((0, tempo(90)), (0, on(36)), (96, off(36))), ppq=96))

    assert tempo_map(song, bpm=120).tick_to_ms(960) == pytest.approx(500)
    assert tempo_map(song).tick_to_ms(960) == pytest.approx(60_000 / 90, rel=1e-6)


@pytest.mark.parametrize("bpm", [0, -10, math.inf, math.nan])
def test_a_bpm_must_be_positive_and_finite(bpm: float) -> None:
    song = parse_midi(build(track((0, on(36)), (96, off(36))), ppq=96))

    with pytest.raises(ValueError, match="BPM"):
        tempo_map(song, bpm=bpm)


def test_tempo_on_another_track_than_the_notes() -> None:
    data = build(
        track((0, signature(4, 4))),
        track((0, on(36)), (480, off(36)), (960, end())),
        track((0, tempo(100)), (480, tempo(200))),
        ppq=480,
    )

    tempos = tempo_map(parse_midi(data))

    # 960 ticks is a beat at 100 BPM, then one at 200 BPM.
    assert tempos.tick_to_ms(1920) == pytest.approx(600 + 300, rel=1e-6)


def test_tempo_changes_in_a_format_0_file() -> None:
    data = build(
        track((0, tempo(120)), (0, on(36)), (480, tempo(60)), (480, off(36)), (960, end())),
        midi_format=0,
        ppq=480,
    )

    tempos = tempo_map(parse_midi(data))

    assert tempos.tick_to_ms(960) == pytest.approx(500)
    assert tempos.tick_to_ms(1920) == pytest.approx(500 + 1000)


def test_the_last_tempo_at_a_tick_wins_and_the_first_holds_before_it() -> None:
    data = build(
        track((0, on(36)), (240, tempo(60)), (240, tempo(120)), (480, off(36))),
        track((240, tempo(240))),
        ppq=480,
    )

    tempos = tempo_map(parse_midi(data))

    # At tick 480 of the song (240 in the file) the later track's 240 BPM wins, and before it
    # the first tempo there, also 240 BPM, holds from the start.
    assert list(tempos.starts) == [0]
    assert tempos.bpm(0) == pytest.approx(240, rel=1e-6)


def test_a_dense_tempo_map_is_fast_and_matches_the_reference() -> None:
    rng = np.random.default_rng(np.random.SeedSequence(2026))
    count = 5000
    ticks = np.cumsum(rng.integers(0, 200, size=count))
    microseconds = rng.integers(150_000, 1_500_000, size=count)
    conductor: list[tuple[int, MidoMessage]] = [
        (int(tick), tempo(60_000_000 / float(value)))
        for tick, value in zip(ticks, microseconds, strict=True)
    ]
    data = build(track(*conductor), track((0, on(36)), (int(ticks[-1]), off(36))), ppq=480)
    song = parse_midi(data)
    queries = rng.uniform(-100, float(ticks[-1]) * 2 + 1000, size=100_000)

    started = time.perf_counter()
    tempos = tempo_map(song)
    ms = tempos.ticks_to_ms(queries)
    back = tempos.ms_to_ticks(ms)
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0
    assert np.allclose(back, queries, rtol=0, atol=1e-6)
    # The song is at 960 PPQ, twice the file's 480.
    changes = [
        (int(tick) * 2, float(value)) for tick, value in zip(ticks, microseconds, strict=True)
    ]
    for query in queries[:100]:
        expected = reference_ms(960, changes, float(query))
        assert tempos.tick_to_ms(float(query)) == pytest.approx(expected, rel=1e-9, abs=1e-6)


_changes = st.lists(
    st.tuples(st.integers(0, 100_000), st.integers(100_000, 3_000_000)), min_size=1, max_size=60
)


@given(changes=_changes, ppq=st.integers(1, 2000), ticks=st.lists(st.floats(-1000, 300_000)))
def test_tempo_map_matches_the_reference(
    changes: list[tuple[int, int]], ppq: int, ticks: list[float]
) -> None:
    tempos = TempoMap(ppq, [t for t, _ in changes], [u for _, u in changes])
    as_float = [(t, float(u)) for t, u in changes]

    for tick in ticks:
        expected = reference_ms(ppq, as_float, tick)
        assert tempos.tick_to_ms(tick) == pytest.approx(expected, rel=1e-9, abs=1e-6)
        assert tempos.ms_to_tick(tempos.tick_to_ms(tick)) == pytest.approx(tick, abs=1e-6)


def test_bars_and_beats_across_time_signature_changes() -> None:
    # Two bars of 4/4, two of 7/8, then 3/4, at 480 PPQ.
    meter = TimeSignatureMap(
        480, [(0, TimeSignature(4, 4)), (3840, TimeSignature(7, 8)), (7200, TimeSignature(3, 4))]
    )

    assert not meter.assumed
    assert [(tick, bar, str(sig)) for tick, bar, sig in meter.changes] == [
        (0, 0, "4/4"),
        (3840, 2, "7/8"),
        (7200, 4, "3/4"),
    ]
    assert list(meter.bar_starts(10_000)) == [0, 1920, 3840, 5520, 7200, 8640]
    assert meter.position(0) == BarBeat(0, 0.0)
    assert meter.position(2400) == BarBeat(1, 1.0)
    assert meter.position(5520 + 240 * 6) == BarBeat(3, 6.0)  # the last eighth of 7/8
    assert meter.position(8640 + 720) == BarBeat(5, 1.5)
    assert meter.tick_at(3, 6.0) == 5520 + 1440
    assert meter.bar_at(7199) == 3
    assert meter.bar_at(7200) == 4
    assert meter.signature_at(7199) == TimeSignature(7, 8)


def test_duplicate_time_signatures_change_nothing() -> None:
    # As in some exports: 4/4 twice at tick 0, then 4/4 again in the middle of bar 1. The song
    # is at 960 PPQ, so a bar of 4/4 is 3840 ticks.
    data = build(
        track(
            (0, signature(4, 4)),
            (0, signature(4, 4)),
            (0, on(36)),
            (2880, signature(4, 4)),
            (2880, off(36)),
        ),
        midi_format=0,
        ppq=480,
    )

    meter = time_signature_map(parse_midi(data))

    assert meter.ppq == 960
    assert [(tick, bar) for tick, bar, _ in meter.changes] == [(0, 0)]
    assert list(meter.bar_starts(3 * 3840 + 1)) == [0, 3840, 7680, 11520]


def test_the_last_time_signature_at_a_tick_wins_across_tracks() -> None:
    data = build(
        track((0, signature(4, 4)), (1920, signature(3, 4))),
        track((0, on(36)), (1920, signature(5, 4)), (1920, off(36))),
        ppq=480,
    )

    meter = time_signature_map(parse_midi(data))

    assert [(tick, bar, str(sig)) for tick, bar, sig in meter.changes] == [
        (0, 0, "4/4"),
        (3840, 1, "5/4"),
    ]


def test_a_change_back_at_the_same_tick_leaves_one_signature() -> None:
    meter = TimeSignatureMap(
        480, [(0, TimeSignature(4, 4)), (1920, TimeSignature(3, 4)), (1920, TimeSignature(4, 4))]
    )

    assert len(meter.changes) == 1


def test_a_change_in_the_middle_of_a_bar_starts_a_bar() -> None:
    meter = TimeSignatureMap(480, [(0, TimeSignature(4, 4)), (2880, TimeSignature(3, 4))])

    # Bar 1 ends early, after two beats, and bar 2 starts at the change.
    assert list(meter.bar_starts(5760)) == [0, 1920, 2880, 4320]
    assert meter.position(2879) == BarBeat(1, 959 / 480)


def test_no_time_signature_assumes_4_4() -> None:
    meter = time_signature_map(parse_midi(build(track((0, on(36)), (1, off(36))), ppq=480)))

    assert meter.assumed
    assert meter.signature_at(0) == TimeSignature(4, 4)
    assert meter.bar_start(2) == 2 * 3840


def test_a_first_time_signature_after_tick_0_follows_assumed_4_4() -> None:
    meter = TimeSignatureMap(480, [(1920, TimeSignature(6, 8))])

    assert meter.assumed
    assert [(tick, bar, str(sig)) for tick, bar, sig in meter.changes] == [
        (0, 0, "4/4"),
        (1920, 1, "6/8"),
    ]


def test_malformed_time_signatures_are_left_out() -> None:
    data = bytearray(build(track((0, signature(3, 4)), (0, on(36)), (1, off(36))), ppq=480))
    position = data.index(bytes((0xFF, 0x58, 0x04)))
    data[position + 3] = 0  # numerator 0

    song = parse_midi(bytes(data))
    meter = time_signature_map(song)

    assert meter.assumed
    assert meter.signature_at(0) == TimeSignature(4, 4)
    assert [e.data[0] for e in song.events if e.meta_type == 0x58] == [0]


_signatures = st.builds(TimeSignature, st.integers(1, 15), st.sampled_from([1, 2, 4, 8, 16, 32]))


@given(
    ppq=st.sampled_from([96, 384, 960, 1000, 1152]),
    changes=st.lists(st.tuples(st.integers(0, 50_000), _signatures), max_size=8),
    ticks=st.lists(st.integers(0, 100_000), min_size=1),
)
def test_bar_positions_are_consistent(
    ppq: int, changes: list[tuple[int, TimeSignature]], ticks: list[int]
) -> None:
    meter = TimeSignatureMap(ppq, changes)
    lines = meter.bar_starts(100_001)

    assert lines[0] == 0
    assert np.all(np.diff(lines) > 0)
    for tick in ticks:
        bar = meter.bar_at(tick)
        assert meter.bar_start(bar) <= tick < meter.bar_start(bar + 1)
        assert lines[bar] == meter.bar_start(bar)
        position = meter.position(tick)
        assert position.bar == bar
        assert meter.tick_at(position.bar, position.beat) == tick
