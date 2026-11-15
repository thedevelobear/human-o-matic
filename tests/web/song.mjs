// A four-group song built in code for the question flow's test (the website plan's PR 4): a
// type 0 MIDI file in General MIDI, 4/4 at 120 BPM and 480 PPQ, with a marker at each section's
// first bar so the sections are exactly these. Groups come out in song order: A, a verse with
// soft snare notes; B, a chorus riding the ride; C, a two-bar tom fill; and D, a half-time groove.
// A and B repeat, so each asks about its last repeat.

const PPQ = 480;
const BAR = 4 * PPQ;
const KICK = 36;
const SNARE = 38;
const HAT = 42;
const RIDE = 51;
const TOMS = [50, 48, 47];

const BARS = {
  A: (hits) => {
    for (let n = 0; n < 8; n += 1) hits.push([(n * PPQ) / 2, HAT, n % 2 ? 80 : 96]);
    hits.push([0, KICK, 96], [2 * PPQ, KICK, 96], [PPQ, SNARE, 96], [3 * PPQ, SNARE, 96]);
    hits.push([PPQ + (3 * PPQ) / 4, SNARE, 30]);
  },
  B: (hits) => {
    for (let n = 0; n < 4; n += 1) hits.push([n * PPQ, RIDE, 100]);
    for (let n = 0; n < 8; n += 1) hits.push([(n * PPQ) / 2, KICK, 100]);
    hits.push([PPQ, SNARE, 120], [3 * PPQ, SNARE, 120]);
  },
  C: (hits) => {
    for (let n = 0; n < 16; n += 1) hits.push([(n * PPQ) / 4, TOMS[Math.floor(n / 4) % 3], 100]);
  },
  D: (hits) => {
    for (let n = 0; n < 8; n += 1) hits.push([(n * PPQ) / 2, RIDE, 100]);
    hits.push([0, KICK, 100], [2 * PPQ, SNARE, 110]);
  },
};
export const FORM = [
  ["A", 4],
  ["B", 4],
  ["A", 4],
  ["C", 2],
  ["D", 4],
  ["B", 4],
];

function variable(value) {
  const bytes = [value & 0x7f];
  for (let rest = value >> 7; rest; rest >>= 7) bytes.unshift((rest & 0x7f) | 0x80);
  return bytes;
}

/** The song's bytes. */
export function fourGroups() {
  const events = [
    [0, [0xff, 0x51, 3, 0x07, 0xa1, 0x20]],
    [0, [0xff, 0x58, 4, 4, 2, 24, 8]],
  ];
  let bar = 0;
  for (const [group, bars] of FORM) {
    if (bar) events.push([bar * BAR, [0xff, 0x06, 1, group.charCodeAt(0)]]);
    for (let number = 0; number < bars; number += 1) {
      const hits = [];
      BARS[group](hits);
      for (const [tick, pitch, velocity] of hits) {
        events.push([(bar + number) * BAR + tick, [0x99, pitch, velocity]]);
        events.push([(bar + number) * BAR + tick + 30, [0x89, pitch, 0]]);
      }
    }
    bar += bars;
  }
  events.sort((a, b) => a[0] - b[0]);
  const track = [];
  let now = 0;
  for (const [tick, message] of events) {
    track.push(...variable(tick - now), ...message);
    now = tick;
  }
  track.push(0, 0xff, 0x2f, 0);
  const length = [24, 16, 8, 0].map((shift) => (track.length >> shift) & 0xff);
  return new Uint8Array([
    ...[0x4d, 0x54, 0x68, 0x64, 0, 0, 0, 6, 0, 0, 0, 1, PPQ >> 8, PPQ & 0xff],
    ...[0x4d, 0x54, 0x72, 0x6b, ...length],
    ...track,
  ]);
}
