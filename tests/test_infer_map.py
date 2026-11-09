"""`tools/infer_map.py` and `tools/midi_folders.py`, on folders of MIDI built in `tmp_path`."""

from pathlib import Path

import pytest

from human_o_matic.maps.kit import DrumKit
from human_o_matic.midi.io import Note
from infer_map import format_report, main, reading, reports, scan
from map_files import articulation, load_kit
from midi_files import end, off, on, save, signature, track
from midi_folders import AssignmentError, Assignments, Entry, folders, midi_files

PPQ = 480
KICK, SNARE, OPEN, CLOSED, ODD = 36, 38, 46, 42, 99


def groove(path: Path, *hits: tuple[int, int, int], bar: tuple[int, int] = (4, 4)) -> Path:
    """A one-track file of (tick, pitch, velocity) hits, each a 16th long."""
    items = [(0, signature(*bar))]
    for tick, pitch, velocity in sorted(hits):
        items += [(tick, on(pitch, velocity)), (tick + PPQ // 4, off(pitch))]
    items.sort(key=lambda item: item[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    return save(path, track(*items, (items[-1][0], end())), ppq=PPQ)


def ref(kit: DrumKit | None) -> str | None:
    return kit.ref if kit else None


@pytest.fixture
def kit(tmp_path: Path) -> DrumKit:
    maps = tmp_path / "maps"
    maps.mkdir()
    return load_kit(
        maps,
        articulation("kick.hit", KICK),
        articulation("snare.center", SNARE),
        articulation("hat.closed", CLOSED),
        articulation("hat.variable", OPEN, cc={"mode": "shape"}),
    )


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """Folder `a` with a groove on top and one in `a/sub`."""
    root = tmp_path / "midi"
    beat = PPQ
    groove(
        root / "a" / "one.mid",
        *((step * beat, KICK, velocity) for step, velocity in enumerate((100, 110, 120, 127))),
        (1 * beat, SNARE, 90),
        (3 * beat, SNARE, 95),
        (0, OPEN, 80),
    )
    groove(root / "a" / "sub" / "two.mid", (0, KICK, 60), (PPQ // 2, ODD, 70))
    return root


def test_a_folder_s_pitches_are_counted_and_read_through_the_kit(root: Path, kit: DrumKit) -> None:
    (report,) = reports(root, ["a"], Assignments({}), kit)

    assert (report.files, report.notes, dict(report.channels)) == (2, 9, {10: 9})
    kick, snare = report.pitches[KICK], report.pitches[SNARE]
    velocities = (min(kick.velocities), max(kick.velocities))
    assert (kick.notes, len(kick.files), velocities) == (5, 2, (60, 127))
    assert dict(kick.reads) == {"kick.hit": 5}
    # Two kicks on the bar's first beat, all four on a beat, and two on beats 2 and 4.
    assert (kick.on_beat, kick.downbeat, kick.backbeat) == (5, 2, 2)
    assert (snare.on_beat, snare.backbeat, snare.downbeat) == (2, 2, 0)
    # The kicks of one file are a quarter, 4 16ths, apart.
    assert kick.gaps == [4.0, 4.0, 4.0]
    assert dict(report.pitches[OPEN].reads) == {"hat.variable (controller)": 1}
    assert report.unmapped() == {ODD: 1}
    counts = [report.count(kind) for kind in ("mapped", "controller", "unmapped")]
    assert counts == [7, 1, 1]


def test_a_beat_is_the_signature_s_and_only_4_4_has_backbeats(tmp_path: Path, kit: DrumKit) -> None:
    eighth = PPQ // 2
    groove(tmp_path / "f" / "six.mid", *((i * eighth, KICK, 100) for i in range(6)), bar=(6, 8))

    (report,) = reports(tmp_path, ["f"], Assignments({}), kit)

    kick = report.pitches[KICK]
    assert (kick.on_beat, kick.downbeat, kick.backbeat) == (6, 1, 0)


def test_the_report_prints_counts_shares_velocities_and_readings(root: Path, kit: DrumKit) -> None:
    (report,) = reports(root, ["a"], Assignments({}), kit)

    text = format_report(report)

    assert text.splitlines()[0] == "== a"
    assert "2 files read; 9 notes; channels 10 (9)" in text
    assert "7 read (77.78%), 1 by a controller value (11.11%), 1 unmapped (11.11%): 99 (1)" in text
    row = next(line for line in text.splitlines() if line.split()[0] == str(KICK))
    assert row.split()[:9] == ["36", "5", "55.56%", "2", "60", "100", "110", "120", "127"]
    assert row.endswith("kick.hit")


def test_folders_are_found_by_listing_and_links_are_followed(tmp_path: Path, kit: DrumKit) -> None:
    root = tmp_path / "midi"
    elsewhere = tmp_path / "installed"
    groove(elsewhere / "inside" / "x.mid", (0, KICK, 100))
    root.mkdir()
    (root / "b").symlink_to(elsewhere, target_is_directory=True)
    groove(root / "a" / "y.mid", (0, SNARE, 100))
    (root / "a" / "loop").symlink_to(root / "a", target_is_directory=True)
    (root / "notes.txt").write_text("not a folder")

    assert [folder.name for folder in folders(root)] == ["a", "b"]
    assert [path.name for path in midi_files(root / "b")] == ["x.mid"]
    # A link back up the tree is followed once, so its files are listed once.
    assert [path.name for path in midi_files(root / "a")] == ["y.mid"]
    found = reports(root, [], Assignments({}), kit)
    assert [(report.name, report.files) for report in found] == [("a", 1), ("b", 1)]


def test_the_assignments_choose_the_kit_and_leave_out_other_entries(root: Path) -> None:
    assignments = Assignments(
        {"a": Entry(map="gm"), "a/sub": Entry(exclude="copies of another folder")}
    )

    (report,) = reports(root, ["a"], assignments, None)

    assert ref(report.kit) == "gm/default"
    assert (report.files, dict(report.elsewhere), report.excluded) == (1, {"a/sub": 1}, None)
    (sub,) = reports(root, ["a/sub"], assignments, None)
    assert (sub.kit, sub.excluded, sub.files) == (None, "copies of another folder", 1)


def test_a_kit_given_reads_every_file_whatever_the_assignments(root: Path, kit: DrumKit) -> None:
    assignments = Assignments({"a/sub": Entry(exclude="copies")})

    (report,) = reports(root, ["a"], assignments, kit)

    assert (report.files, dict(report.elsewhere)) == (2, {})


def test_split_gives_a_report_per_subfolder_after_the_top(root: Path, kit: DrumKit) -> None:
    found = reports(root, ["a"], Assignments({}), kit, split=True)

    assert [(report.name, report.files, report.notes) for report in found] == [
        ("a", 1, 7),
        ("a/sub", 1, 2),
    ]


def test_a_file_that_cannot_be_read_is_counted_and_skipped(tmp_path: Path, kit: DrumKit) -> None:
    (tmp_path / "f").mkdir()
    (tmp_path / "f" / "broken.mid").write_bytes(b"not midi")
    groove(tmp_path / "f" / "fine.mid", (0, KICK, 100))

    report = scan("f", [(path, None) for path in midi_files(tmp_path / "f")], kit, None)

    assert report.files == 1
    assert sum(report.skipped.values()) == 1


def test_an_assignments_file_is_checked_when_it_is_read(tmp_path: Path) -> None:
    path = tmp_path / "folders.toml"
    assert len(Assignments.read(path)) == 0

    path.write_text('schema = 1\n[folders.a]\nmap = "gm"\n[folders."a/b"]\nexclude = "why"\n')
    assignments = Assignments.read(path)
    found = assignments.find("a/b/c/song.mid")
    assert found is not None
    assert (found.key, found.exclude) == ("a/b", "why")
    found = assignments.find("a/c.mid")
    assert found is not None
    assert ref(found.kit) == "gm/default"
    assert assignments.find("z/song.mid") is None

    for text, problem in (
        ('schema = 1\n[folders.a]\nmap = "no-such-library"\n', "no library"),
        ('schema = 1\n[folders.a]\nmap = "gm"\nexclude = "why"\n', "either"),
        ("schema = 1\n[folders.a]\n", "either"),
        ('schema = 2\n[folders.a]\nmap = "gm"\n', "schema"),
        ('schema = 1\n[folders."/a"]\nmap = "gm"\n', "not a path"),
    ):
        path.write_text(text)
        with pytest.raises(AssignmentError, match=problem):
            Assignments.read(path)


def test_reading_names_the_articulation_or_says_unmapped(kit: DrumKit) -> None:
    def note(pitch: int) -> Note:
        return Note(track=0, channel=9, pitch=pitch, start=0, end=1, velocity=100)

    assert reading(kit, note(KICK)) == "kick.hit"
    assert reading(kit, note(OPEN)) == "hat.variable (controller)"
    assert reading(kit, note(ODD)) == "unmapped"


def test_main_prints_the_reports_and_exits_2_on_a_usage_error(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    options = ["--root", str(root), "--assignments", str(tmp_path / "none.toml")]

    assert main(["a", "--map", "gm", *options]) == 0
    printed = capsys.readouterr()
    assert printed.out.startswith("== a\n")
    assert "through gm/default" in printed.out
    assert "1 folders, 2 files, 9 notes" in printed.err

    assert main(["a", *options]) == 0
    assert "no map: give --map, or assign the folder" in capsys.readouterr().out

    assert main(["missing", *options]) == 2
    assert "is not a folder" in capsys.readouterr().err
    assert main(["../a", *options]) == 2
    assert main(["a", "--map", "no-such-library", *options]) == 2
    assert "no library" in capsys.readouterr().err
