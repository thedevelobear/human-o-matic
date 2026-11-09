import tempfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from human_o_matic.maps.kit import Output
from human_o_matic.maps.loader import built_in_vocabulary, load_library, load_maps
from human_o_matic.maps.vocabulary import MapError
from map_files import Table, articulation, kit, library, load_kit, write_library

KICK = articulation("kick.hit", 36, 35, label="Kick", source="standard")
SNARE = articulation("snare.center", 38)


def test_a_map_file_loads_its_kits(tmp_path: Path) -> None:
    path = write_library(
        tmp_path,
        library(kit(KICK, SNARE, id="studio", channel=10), kit(KICK, id="vintage")),
    )

    studio, vintage = load_library(path, built_in_vocabulary())

    assert (studio.ref, vintage.ref) == ("test-drums/studio", "test-drums/vintage")
    assert studio.label == "Library test-drums (Kit studio)"
    assert "snare.center" in studio
    assert "snare.center" not in vintage
    assert studio.articulation("kick.hit").label == "Kick"
    assert studio.pieces("kick") == 1
    assert studio.pieces("tom") == 0


def test_reading_takes_a_note_to_its_articulation(tmp_path: Path) -> None:
    drums = load_kit(tmp_path, KICK, SNARE)

    assert [match.articulation.name for match in drums.read(35, 100, 9)] == ["kick.hit"]
    kick = drums.resolve(36, 1, 0)
    assert kick is not None
    assert kick.name == "kick.hit"
    assert drums.resolve(37, 100, 9) is None
    assert drums.read(37, 100, 9) == ()


def test_writing_takes_the_first_binding(tmp_path: Path) -> None:
    drums = load_kit(tmp_path, KICK, SNARE, channel=10)

    assert drums.write("kick.hit") == Output(pitch=36, channel=9, velocity=(1, 127), cc=None)


def test_without_a_kit_channel_a_note_keeps_its_own(tmp_path: Path) -> None:
    drums = load_kit(tmp_path, KICK)

    assert drums.write("kick.hit").channel is None


def test_velocity_ranges_and_channels_select_the_articulation(tmp_path: Path) -> None:
    drums = load_kit(
        tmp_path,
        articulation("snare.center", 38, velocity=[1, 119]),
        articulation(
            "snare.rimshot",
            bindings=[{"note": 40}, {"note": 38, "channel": 10, "velocity": [120, 127]}],
        ),
        articulation("snare.2.center", 38, channel=2, velocity=[120, 127]),
    )

    def name(pitch: int, velocity: int, channel: int) -> str | None:
        found = drums.resolve(pitch, velocity, channel)
        return found.name if found else None

    assert name(38, 119, 9) == "snare.center"
    assert name(38, 120, 9) == "snare.rimshot"
    assert name(38, 120, 1) == "snare.2.center"
    assert name(38, 120, 4) is None
    assert name(40, 64, 4) == "snare.rimshot"
    assert drums.write("snare.rimshot").pitch == 40
    assert drums.write("snare.2.center") == Output(38, channel=1, velocity=(120, 127), cc=None)


def test_controller_conditions_are_kept_and_not_resolved(tmp_path: Path) -> None:
    drums = load_kit(
        tmp_path,
        articulation("hat.closed", 26, cc={"mode": "select", "controller": 4, "values": [0, 40]}),
        articulation(
            "hat.open.half", 26, cc={"mode": "select", "controller": 4, "values": [41, 100]}
        ),
        articulation(
            "hat.open",
            bindings=[
                {"note": 46},
                {"note": 26, "cc": {"mode": "select", "controller": 4, "values": [101, 127]}},
            ],
        ),
        articulation("hat.variable", 30, cc={"mode": "shape"}),
    )

    names = [match.articulation.name for match in drums.read(26, 100, 9)]
    assert names == ["hat.closed", "hat.open.half", "hat.open"]
    assert drums.resolve(26, 100, 9) is None
    assert drums.resolve(30, 100, 9) is None
    assert [match.articulation.name for match in drums.read(30, 100, 9)] == ["hat.variable"]
    hat = drums.resolve(46, 100, 9)
    assert hat is not None
    assert hat.name == "hat.open"
    closed = drums.write("hat.closed").cc
    assert closed is not None
    assert (closed.controller, closed.values) == (4, (0, 40))


def test_every_articulation_reads_back_from_what_is_written(tmp_path: Path) -> None:
    drums = load_kit(
        tmp_path,
        KICK,
        articulation("snare.center", 38, velocity=[1, 99]),
        articulation("snare.rimshot", 38, velocity=[100, 127]),
        articulation("tom.1.hit", 48, channel=3),
        articulation("tom.2.hit", 48, channel=4),
        channel=10,
    )

    for entry in drums.articulations:
        output = drums.write(entry.name)
        channel = output.channel if output.channel is not None else 0
        for velocity in output.velocity:
            assert drums.resolve(output.pitch, velocity, channel) == entry


def overlapping(first: Table, second: Table) -> bool:
    """Whether some note could match both bindings, found by trying every value that matters:
    two ranges that meet share one of their ends."""
    if first["note"] != second["note"]:
        return False
    channels = {first.get("channel"), second.get("channel"), 1} - {None}
    velocities = {*_range(first, "velocity", 1, 127), *_range(second, "velocity", 1, 127)}
    values = {*_cc_values(first), *_cc_values(second), 0}
    return any(
        _matches(first, channel, velocity, controllers)
        and _matches(second, channel, velocity, controllers)
        for channel in channels
        for velocity in velocities
        for controllers in ({4: four, 11: eleven} for four in values for eleven in values)
    )


def _range(binding: Table, key: str, low: int, high: int) -> tuple[int, int]:
    found = binding.get(key, [low, high])
    assert isinstance(found, list)
    return found[0], found[1]


def _cc_values(binding: Table) -> tuple[int, ...]:
    cc = binding.get("cc")
    return _range(cc, "values", 0, 127) if isinstance(cc, dict) else ()


def _matches(binding: Table, channel: int, velocity: int, controllers: dict[int, int]) -> bool:
    """Whether a note matches the binding, with each controller at its value in `controllers`."""
    low, high = _range(binding, "velocity", 1, 127)
    if binding.get("channel", channel) != channel or not low <= velocity <= high:
        return False
    cc = binding.get("cc")
    if not isinstance(cc, dict):
        return True
    low, high = _range(cc, "values", 0, 127)
    return low <= controllers[cc["controller"]] <= high


@st.composite
def bindings(draw: st.DrawFn) -> Table:
    binding: Table = {"note": draw(st.sampled_from([38, 40]))}
    if draw(st.booleans()):
        binding["channel"] = draw(st.sampled_from([1, 2]))
    if draw(st.booleans()):
        low = draw(st.sampled_from([1, 40, 41, 100, 127]))
        binding["velocity"] = [
            low,
            draw(st.sampled_from([v for v in (40, 41, 100, 127) if v >= low])),
        ]
    if draw(st.booleans()):
        low = draw(st.sampled_from([0, 50, 51, 127]))
        high = draw(st.sampled_from([v for v in (50, 51, 127) if v >= low]))
        controller = draw(st.sampled_from([4, 11]))
        binding["cc"] = {"mode": "select", "controller": controller, "values": [low, high]}
    return binding


@given(bindings(), bindings())
def test_a_map_loads_only_when_no_two_articulations_overlap(first: Table, second: Table) -> None:
    # A temporary directory per example, since hypothesis runs many examples per test.
    with tempfile.TemporaryDirectory() as directory:
        path = write_library(
            Path(directory),
            library(
                kit(
                    articulation("snare.center", bindings=[first]),
                    articulation("snare.rimshot", bindings=[second]),
                )
            ),
        )
        if overlapping(first, second):
            with pytest.raises(MapError, match=r"snare\.center and snare\.rimshot overlap"):
                load_library(path, built_in_vocabulary())
        else:
            load_library(path, built_in_vocabulary())


def test_an_overlap_names_both_articulations_the_note_and_the_ranges(tmp_path: Path) -> None:
    path = write_library(
        tmp_path,
        library(
            kit(
                articulation("snare.center", 38, velocity=[1, 100]),
                articulation("snare.rimshot", 38, velocity=[100, 127], channel=10),
            )
        ),
    )

    with pytest.raises(MapError) as raised:
        load_library(path, built_in_vocabulary())

    message = str(raised.value)
    assert "test-drums/kit: snare.center and snare.rimshot overlap on note 38" in message
    assert "any channel, velocity 1 to 100 and channel 10, velocity 100 to 127" in message


def test_one_articulation_cannot_list_a_note_twice(tmp_path: Path) -> None:
    path = write_library(tmp_path, library(kit(articulation("kick.hit", 36, 36))))

    with pytest.raises(MapError, match=r"kick\.hit and kick\.hit overlap on note 36"):
        load_library(path, built_in_vocabulary())


@pytest.mark.parametrize(
    ("articulations", "message"),
    [
        ([articulation("snare.centre", 38)], "not an articulation of snare"),
        ([articulation("snare.1.center", 38)], "first snare has no piece number"),
        ([SNARE, articulation("snare.center", 40)], "snare.center is listed twice"),
        ([articulation("hat.closed", 42), articulation("hat.open.quarter", 46)], "needs hat.open"),
        ([articulation("hat.open", 46)], "needs its piece's default, hat.closed"),
        ([articulation("crash.1.hit", 49), articulation("crash.2.choke", 50)], "crash.2.hit"),
        ([articulation("tom.1.hit", 48), articulation("tom.3.hit", 45)], "tom pieces 1, 3"),
        ([articulation("snare.2.center", 40)], "snare pieces 2 are not numbered from 1"),
        ([articulation("kick.hit", 36, source="manual")], "source"),
        ([articulation("kick.hit", 36, label="Kick")], "only a `standard` articulation"),
        ([articulation("kick.hit", 128)], "less than or equal to 127"),
        ([articulation("kick.hit", 36, velocity=[0, 127])], "within 1 to 127"),
        ([articulation("kick.hit", 36, velocity=[100, 99])], "within 1 to 127"),
        ([articulation("kick.hit", 36, channel=0)], "greater than or equal to 1"),
        ([articulation("kick.hit", 36, channel=17)], "less than or equal to 16"),
        ([articulation("kick.hit", 36, confidence="certain")], "confidence"),
        ([articulation("kick.hit", 36, label="x" * 41, source="standard")], "at most 40"),
        ([articulation("kick.hit")], "bindings"),
        ([articulation("kick.hit", notes=[])], "at least 1"),
        ([articulation("kick.hit", 36, bindings=[{"note": 36}])], "not both"),
        ([articulation("kick.hit", bindings=[{"note": 36}], velocity=[1, 127])], "velocity"),
        ([articulation("kick.hit", 36, cc={"mode": "select", "controller": 4})], "values"),
        ([articulation("kick.hit", 36, cc={"mode": "select", "values": [0, 9]})], "controller"),
        ([articulation("kick.hit", 36, cc={"mode": "shape", "values": [0, 9]})], "no `values`"),
        ([articulation("kick.hit", 36, cc={"mode": "pedal"})], "mode"),
        ([articulation("kick.hit", 36, sample="kick.wav")], "sample"),
    ],
)
def test_an_invalid_map_is_refused_when_it_loads(
    tmp_path: Path, articulations: list[Table], message: str
) -> None:
    path = write_library(tmp_path, library(kit(*articulations)))

    with pytest.raises(MapError, match=message):
        load_library(path, built_in_vocabulary())


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"schema": 2}, "schema"),
        ({"id": "Test Drums"}, "pattern"),
        ({"sources": {"test": {"title": "?"}}}, "sources"),
        ({"kits": []}, "kits"),
        ({"kits": [kit(KICK, id="a"), kit(KICK, id="a")]}, "kit ids repeat"),
    ],
)
def test_an_invalid_library_is_refused(tmp_path: Path, fields: Table, message: str) -> None:
    path = write_library(tmp_path, library(kit(KICK)) | fields, name="drums")

    with pytest.raises(MapError, match=message):
        load_library(path, built_in_vocabulary())


def test_a_directory_of_maps_loads_by_library_and_kit(tmp_path: Path) -> None:
    write_library(tmp_path, library(kit(KICK, id="one"), kit(SNARE, id="two"), id="first"))
    write_library(tmp_path, library(kit(KICK), id="second"))
    (tmp_path / "notes.txt").write_text("not a map")

    maps = load_maps(tmp_path, built_in_vocabulary())

    assert [entry.id for entry in maps.libraries] == ["first", "second"]
    assert [drums.ref for drums in maps] == ["first/one", "first/two", "second/kit"]
    assert maps.kit("first", "two").ref == "first/two"
    assert maps.kit("second").ref == "second/kit"
    with pytest.raises(KeyError, match="first has the kits one, two; name one"):
        maps.kit("first")
    with pytest.raises(KeyError, match="first has no kit 'three'; it has one, two"):
        maps.kit("first", "three")
    with pytest.raises(KeyError, match="second has no kit 'one'; it has kit"):
        maps.kit("second", "one")
    with pytest.raises(KeyError, match="no library 'third'"):
        maps.kit("third")


def test_two_files_cannot_share_a_library_id(tmp_path: Path) -> None:
    write_library(tmp_path, library(kit(KICK)), name="a")
    write_library(tmp_path, library(kit(SNARE)), name="b")

    with pytest.raises(MapError, match="library id test-drums"):
        load_maps(tmp_path, built_in_vocabulary())
