"""Fitting the styles `tight`, `medium` and `loose` from the measured grooves, and writing them to
`data/styles/` (ADRs 0067 to 0070).

The grooves are `calibrate.py`'s, and every statistic here is one the engine draws or measures
(`render/measure.py`, `render/parts.py`), so a fitted number means what the render means by it.

- **Velocities** are fitted once, on every groove whose velocities aren't flat, and the three
  styles share them (ADR 0065). A groove's energy is its rank in velocity level among them, from
  0 to 1, so a role's center at energy 0.2, 0.5 and 1.0 is the median of its mean velocity over
  the grooves ranked within `WINDOW` of it, and what each metric level adds is the median of how
  far that level's notes sit from the role's mean. The spreads, the soft notes and the fills'
  accents are medians or percentiles over the grooves.
- **Timing** is fitted per band of timing spread, on the performed grooves the grid fits (ADRs
  0060, 0064), by tempo band. A groove's offsets are taken apart as the engine draws them: each
  limb's mean less the `other` limb's, the spread an onset's hits share and each hit's own. The
  song's slow drift stays modelled, so the spread it adds within a groove is taken out of the
  shared part. A style draws its band's medians at the default tightness, and the control's
  shape about them stays the placeholder's.
- What a performance can't give keeps the placeholder's value, and so do three values whose fit
  runs against Appendix A or ADR 0052's tests, and the riders' noise, which would blur their
  alternation (`KEPT`).

The fitted numbers are rounded to hundredths, and the kept ones are the placeholder's exactly, so
running the fit again on the same grooves gives the same files byte for byte.
"""

import fnmatch
import json
import math
import textwrap
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import cast

import numpy as np

from calibrate import FileResult, Groove, timed, velocity_grooves
from human_o_matic.controls import StyleName
from human_o_matic.render.engine import drift
from human_o_matic.render.parts import METRIC_LEVELS, ROLES, Limb, Role
from human_o_matic.render.style import PLACEHOLDER, Style, Timing

CUTS = (3.0, 6.0)
"""Timing spread under the first is `tight`, under the second `medium`, and the rest `loose`, in
ms (ADR 0067)."""
STYLE_NAMES: tuple[StyleName, ...] = ("tight", "medium", "loose")
TEMPO_CUTS = (150.0,)
"""The tempo bands' cut, in BPM."""
WINDOW = 0.1
"""How far a groove's energy rank may be from an anchor's energy and count for it."""
ANCHORS = {"full": 1.0, "half": 0.5, "low": 0.2}
MIN_GROOVES = 10
"""The fewest grooves a velocity statistic is a median of; with fewer it keeps a fallback."""
MIN_TEMPO_GROOVES = 20
MIN_TEMPO_PACKS = 2
"""A tempo band of a style is fitted on its own grooves with at least these; otherwise it takes
the style's timing over every tempo."""
LOUD = 118
"""The plan's floor for kick and backbeats at high energy."""
QUARTERS = 64
"""A 16-bar groove in 4/4, over which the drift the engine adds is measured."""
DRIFT_SEEDS = 64
FLAT_STEPS = 4
"""A role's metric offset is a median of the grooves with at least this many of its notes."""
KEPT = (
    "defaults",
    "velocity.*.band",
    "feet",
    "rider_groove",
    "rider_flip",
    "soft_mix",
    "fill_hand",
    "fill_shift",
    "snare_loudness",
    "arc_span",
    "energy_drift_sd",
    "energy_drift_quarters",
    "drift_sd",
    "drift_quarters",
    "rider_gap",
    "accent",
    "fill_crescendo",
    "rider_noise_sd",
)
"""What keeps the placeholder's value: the controls' defaults and the shapes of their effects,
which a performance plays at one setting only; which foot is which, and which hand, which MIDI
doesn't say; the rider's flip rate, which needs labels a performance doesn't have; the loudness
laid-back playing adds, which needs the control; and the song's drifts, which loops are too
short to show. A velocity band is a floor the plan sets for loud kicks and backbeats.

Three the grooves do give run against Appendix A or ADR 0052's tests, so they keep it too:
- the rider gap, under half a step in the grooves, too small for `dynamic_range` and `groove`
  to move by 2 steps;
- the accent, whose line in energy pushes accents past 127, so their contrast falls as `groove`
  rises;
- a fill's crescendo, which the grooves' fills fit at none, where Appendix A's rise.

The riders' noise keeps Appendix A's too: the grooves' riders spread about twice as far, with
their strong, weak and metric means taken out, which would blur the alternation of their strong
and weak hits (ADR 0076)."""


@dataclass(frozen=True, slots=True)
class Fit:
    """The fitted styles, and what each part of the fit drew on."""

    styles: dict[StyleName, Style]
    velocity_grooves: int
    velocity_folders: int
    velocity_packs: int
    timing: dict[StyleName, tuple[int, int, int]]
    """Each style's timing grooves, folders and packs."""
    tempo: dict[StyleName, tuple[int, ...]]
    """Each style's grooves per tempo band, 0 where the band took the style's pooled timing."""
    fallbacks: list[str] = field(default_factory=list[str])
    """The statistics that had too few grooves and took a fallback."""


def drift_variance(sd: float, constants: Sequence[float]) -> float:
    """The variance a drift of the engine's adds within a 16-bar groove, on average over seeds."""
    times = np.arange(0.0, QUARTERS, 0.25)
    values = [
        float(np.var(drift(times, sd, constants, np.random.default_rng(np.random.SeedSequence(k)))))
        for k in range(DRIFT_SEEDS)
    ]
    return float(np.mean(values))


def ranks(values: Sequence[float]) -> list[float]:
    """Each value's rank among them from 0 to 1, ties sharing the middle of theirs."""
    ordered = np.sort(np.array(values, dtype=np.float64))
    last = max(len(values) - 1, 1)
    return [
        (
            int(np.searchsorted(ordered, value, "left"))
            + int(np.searchsorted(ordered, value, "right"))
            - 1
        )
        / 2
        / last
        for value in values
    ]


def _median(values: Iterable[float]) -> float | None:
    found = list(values)
    return float(np.median(found)) if len(found) >= MIN_GROOVES else None


def fit(results: Sequence[FileResult]) -> Fit:
    """The three styles from the measured files of the assigned folders."""
    grooves = [groove for result in results for groove in result.grooves]
    fallbacks: list[str] = []
    velocity = _velocity(velocity_grooves(grooves), fallbacks)
    styles: dict[StyleName, Style] = {}
    counts: dict[StyleName, tuple[int, int, int]] = {}
    tempo: dict[StyleName, tuple[int, ...]] = {}
    drift_var = drift_variance(PLACEHOLDER.drift_sd, PLACEHOLDER.drift_quarters)
    lows = (None, *CUTS)
    highs = (*CUTS, None)
    for name, low, high in zip(STYLE_NAMES, lows, highs, strict=True):
        mine = [g for g in timed(grooves) if _within(g, low, high)]
        counts[name] = (len(mine), len({g.folder for g in mine}), len({g.pack for g in mine}))
        timing, per_tempo = _timings(mine, drift_var, name, fallbacks)
        tempo[name] = per_tempo
        fitted = _rounded(
            velocity | {"tempo_cuts": list(TEMPO_CUTS), "timing": timing, "feel_ms": _feel(mine)}
        )
        data = PLACEHOLDER.model_dump(mode="json") | fitted | {"name": name, "placeholder": False}
        styles[name] = Style.model_validate_json(json.dumps(data))
    chosen = velocity_grooves(grooves)
    return Fit(
        styles=styles,
        velocity_grooves=len(chosen),
        velocity_folders=len({g.folder for g in chosen}),
        velocity_packs=len({g.pack for g in chosen}),
        timing=counts,
        tempo=tempo,
        fallbacks=fallbacks,
    )


def _within(groove: Groove, low: float | None, high: float | None) -> bool:
    spread = groove.spread_ms
    assert spread is not None
    return (low is None or spread >= low) and (high is None or spread < high)


def _velocity(grooves: Sequence[Groove], fallbacks: list[str]) -> dict[str, object]:
    """The velocity fields every style shares."""
    energies = [g.energy if g.energy is not None else 0.0 for g in grooves]
    rank = dict(zip(map(id, grooves), ranks(energies), strict=True))

    def role_mean(groove: Groove, role: Role) -> float | None:
        found = groove.detail.roles.get(role)
        return found[0] if found else None

    kick: dict[str, float] = {}
    velocity: dict[str, dict[str, float | None]] = {}
    for role in ROLES:  # the kick first, which the other roles fall back on
        row: dict[str, float | None] = {}
        placeholder = PLACEHOLDER.velocity[role]
        for anchor, energy in ANCHORS.items():
            values = [
                value
                for g in grooves
                if abs(rank[id(g)] - energy) <= WINDOW and (value := role_mean(g, role)) is not None
            ]
            found = _median(values)
            if found is None and role != "kick":
                offset = _median(
                    a - b
                    for g in grooves
                    if (a := role_mean(g, role)) is not None
                    and (b := role_mean(g, "kick")) is not None
                )
                if offset is not None:
                    found = kick[anchor] + offset
                    fallbacks.append(f"velocity.{role}.{anchor}: the kick's, less its usual offset")
            if found is None:
                found = float(getattr(placeholder, anchor))
                fallbacks.append(f"velocity.{role}.{anchor}: kept")
            row[anchor] = found
            if role == "kick":
                kick[anchor] = found
        row["band"] = placeholder.band
        velocity[role] = row

    metric: dict[str, list[float]] = {}
    for role in ROLES:
        levels = [0.0] * METRIC_LEVELS
        if role not in ("fill", "rider"):
            for level in range(METRIC_LEVELS):
                found = _median(
                    g.detail.metric[(role, level)][0] - g.detail.roles[role][0]
                    for g in grooves
                    if (role, level) in g.detail.metric
                    and g.detail.metric[(role, level)][1] >= 2
                    and g.detail.roles[role][1] >= FLAT_STEPS
                )
                levels[level] = found if found is not None else 0.0
        metric[role] = levels

    energy_drift = drift_variance(PLACEHOLDER.energy_drift_sd, (PLACEHOLDER.energy_drift_quarters,))
    noise = _median(g.detail.noise for g in grooves if g.detail.noise is not None)
    softs = [g.detail.soft for g in grooves if g.detail.soft is not None]
    soft_sd = _median(g.detail.soft_sd for g in grooves if g.detail.soft_sd is not None)
    fill_metric = [
        _median(g.detail.fill_metric[level] for g in grooves if level in g.detail.fill_metric)
        for level in range(METRIC_LEVELS)
    ]
    fields: dict[str, object] = {"velocity": velocity, "metric_velocity": metric}
    fields["noise_sd"] = (
        math.sqrt(max(noise**2 - energy_drift, 0.0)) if noise is not None else PLACEHOLDER.noise_sd
    )
    if len(softs) >= MIN_GROOVES:
        low, high = np.percentile(softs, [10, 90]).tolist()
        fields["soft"] = [low, high - low]
    else:
        fields["soft"] = list(PLACEHOLDER.soft)
    fields["soft_sd"] = soft_sd if soft_sd is not None else PLACEHOLDER.soft_sd
    if all(value is not None for value in fill_metric):
        fields["fill_metric"] = [float(value or 0.0) for value in fill_metric]
    else:
        fields["fill_metric"] = list(PLACEHOLDER.fill_metric)
        fallbacks.append("fill_metric: kept")
    for name, value in (("noise_sd", noise), ("soft_sd", soft_sd)):
        if value is None:
            fallbacks.append(f"{name}: kept")
    return fields


def _timings(
    grooves: Sequence[Groove], drift_var: float, name: str, fallbacks: list[str]
) -> tuple[list[dict[str, object]], tuple[int, ...]]:
    pooled = _timing(grooves, drift_var)
    found: list[dict[str, object]] = []
    used: list[int] = []
    edges = (0.0, *TEMPO_CUTS, math.inf)
    for low, high in pairwise(edges):
        mine = [g for g in grooves if low <= g.detail.bpm < high]
        if len(mine) >= MIN_TEMPO_GROOVES and len({g.pack for g in mine}) >= MIN_TEMPO_PACKS:
            found.append(_timing(mine, drift_var))
            used.append(len(mine))
        else:
            found.append(pooled)
            used.append(0)
            fallbacks.append(
                f"{name}: tempo band {low:g} to {high:g} BPM takes the style's pooled timing"
            )
    return found, tuple(used)


def _timing(grooves: Sequence[Groove], drift_var: float) -> dict[str, object]:
    """One tempo band's timing, so that at the default tightness it draws the grooves' medians."""
    tightness = PLACEHOLDER.defaults.tightness
    reference = PLACEHOLDER.timing_at(120.0)
    loose, tight = reference.jitter_sd
    shape = tight / loose
    at_default = 1 + (shape - 1) * tightness
    clip_ratio = reference.jitter_clip / (loose * at_default)
    shared = float(
        np.median(
            [
                math.sqrt(max(g.detail.shared_var - drift_var, 0.0))
                for g in grooves
                if g.detail.shared_var is not None
            ]
        )
    )
    jitter = float(
        np.median(
            [math.sqrt(g.detail.jitter_var) for g in grooves if g.detail.jitter_var is not None]
        )
    )
    limbs: dict[Limb, float] = {"other": 0.0}
    for limb in ("snare", "rider"):
        values = [g.detail.limbs[limb] for g in grooves if limb in g.detail.limbs]
        limbs[limb] = float(np.median(values)) if values else reference.limb_ms[limb]
    timing = Timing(
        shared_sd=shared / (1.5 - tightness),
        jitter_sd=(jitter / at_default, jitter * shape / at_default),
        jitter_clip=jitter * clip_ratio,
        limb_ms=limbs,
    )
    return timing.model_dump(mode="json")


def _feel(grooves: Sequence[Groove]) -> list[float]:
    """How far `feel` +1 moves the snare and riders late, and -1 early: from the band's median
    feel to its 90th percentile, and to its 10th."""
    feels = [g.feel_ms for g in grooves if g.feel_ms is not None]
    low, middle, high = np.percentile(feels, [10, 50, 90]).tolist()
    return [high - middle, middle - low]


type Json = bool | int | float | str | list[Json] | dict[str, Json] | None


def _hundredths(text: str) -> float:
    return round(float(text), 2) + 0.0  # + 0.0 turns -0.0 into 0.0


def _rounded(data: object) -> dict[str, Json]:
    """The data with every float rounded to hundredths."""
    return cast(dict[str, Json], json.loads(json.dumps(data), parse_float=_hundredths))


def style_toml(style: Style) -> str:
    """A style as its file in `data/styles/` (ADR 0069)."""
    header = (
        f"The `{style.name}` style, written by `tools/calibrate.py fit` from performed MIDI: "
        "aggregate statistics only (ADRs 0007, 0044). The velocities are fitted once and shared "
        "by the three styles (ADR 0065), and the timing is this style's band's, by tempo band. "
        "Values a performance can't give keep the placeholder's, and so do the rider gap, accent "
        "and fill crescendo, whose fits run against Appendix A or ADR 0052's tests (ADR 0068), "
        "and the riders' noise, whose fit would blur their alternation (ADR 0076). Don't edit "
        "it: change the fit and run it again."
    )
    lines = textwrap.wrap(header, width=98, initial_indent="# ", subsequent_indent="# ")
    _table(lines, [], cast(dict[str, Json], style.model_dump(mode="json")))
    return "\n".join(lines) + "\n"


def _table(lines: list[str], path: list[str], table: dict[str, Json]) -> None:
    for key, value in table.items():
        if value is not None and not isinstance(value, dict) and not _tables(value):
            lines.append(f"{key} = {_value(value)}")
    for key, value in table.items():
        if isinstance(value, dict):
            lines += ["", f"[{'.'.join([*path, key])}]"]
            _table(lines, [*path, key], value)
        elif _tables(value):
            assert isinstance(value, list)
            for item in value:
                assert isinstance(item, dict)
                lines += ["", f"[[{'.'.join([*path, key])}]]"]
                _table(lines, [*path, key], item)


def _tables(value: Json) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, dict) for v in value)


def _value(value: Json) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_value(item) for item in value) + "]"
    if value is None:
        return "-"
    if isinstance(value, dict):
        raise ValueError("a table is written as a table")
    return repr(value)


def flat(data: Json, prefix: str = "") -> dict[str, Json]:
    """Every value of a style's data by its dotted path; a list of tables by index."""
    if isinstance(data, dict):
        found: dict[str, Json] = {}
        for key, value in data.items():
            found |= flat(value, f"{prefix}{key}.")
        return found
    if _tables(data):
        assert isinstance(data, list)
        found = {}
        for index, value in enumerate(data):
            found |= flat(value, f"{prefix}{index}.")
        return found
    return {prefix.rstrip("."): data}


def kept(path: str) -> bool:
    return any(
        fnmatch.fnmatchcase(path, pattern) or path.startswith(f"{pattern}.") for pattern in KEPT
    )


def table(found: Fit) -> str:
    """Every value of the placeholder beside each style's, as Markdown, `kept` where it stays
    the placeholder's. A style's timing has a row per tempo band; the placeholder has one band."""
    placeholder = flat(cast(Json, PLACEHOLDER.model_dump(mode="json")))
    styles = {
        name: flat(cast(Json, each.model_dump(mode="json"))) for name, each in found.styles.items()
    }
    rows = ["| Value | Placeholder | tight | medium | loose |", "|---|---|---|---|---|"]
    paths = [p for p in styles["tight"] if p not in ("name", "placeholder")]
    for path in paths:
        if path.startswith("defaults.") or path == "tempo_cuts":
            continue
        source = "timing.0." + path.split(".", 2)[2] if path.startswith("timing.") else path
        before = placeholder.get(source, "-")
        cells = ["kept" if kept(path) else _value(styles[name][path]) for name in STYLE_NAMES]
        rows.append(f"| {path} | {_value(before)} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def contradictions(found: Fit) -> list[str]:
    """What in the fit runs against Appendix A's directions or the plan's limits."""
    style = found.styles["tight"]
    problems = [
        f"{role}'s velocity falls as energy rises: {anchors}"
        for role, anchors in style.velocity.items()
        if not anchors.low <= anchors.half <= anchors.full
    ]
    problems += [
        f"{role} at energy 1.0 is {style.velocity[role].full}, under 118"
        for role in ("kick", "backbeat")
        if style.velocity[role].full < LOUD
    ]
    if style.rider_gap[0] <= 0:
        problems.append(
            f"the rider's strong hits aren't louder than its weak ones: {style.rider_gap}"
        )
    quarter, eighth, sixteenth, _ = style.fill_metric
    if not quarter >= eighth >= sixteenth:
        problems.append(f"fill accents don't fall from quarter to 16th: {style.fill_metric}")
    if style.fill_crescendo <= 0:
        problems.append(f"a fill's crescendo doesn't rise: {style.fill_crescendo}")
    for name, each in found.styles.items():
        late, early = each.feel_ms
        if early >= late:
            problems.append(
                f"{name}: feel's pushed side, {early}, isn't under its laid-back {late}"
            )
        problems += [
            f"{name}, tempo band {band}: the {limb} plays early, {timing.limb_ms[limb]} ms"
            for band, timing in enumerate(each.timing)
            for limb in ("snare", "rider")
            if timing.limb_ms[limb] < 0
        ]
    return problems
