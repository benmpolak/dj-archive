const { test } = require("node:test");
const assert = require("node:assert/strict");
const C = require("../music-core.js");
const a = {
  sid: "0123456789012345678901",
  a: "Curió Curió",
  t: "Água",
  al: "First",
};
const b = {
  sid: "spotify:local:Seu:Jorge",
  a: "Seu Jorge",
  t: "São Paulo",
  al: "Live",
};
test("portable selection keeps exact order and Unicode", () => {
  const s = C.selection("Domingo — São Paulo", [b, a], "selector:Brazilian");
  assert.deepEqual(C.decode(C.encode(s)), s);
  assert.deepEqual(C.resolve(s, [a, b]).tracks, [b, a]);
});
test("ids survive catalogue reordering and a missing track is explicit", () => {
  const s = C.selection("Test", [a, b]);
  const r = C.resolve(s, [b]);
  assert.deepEqual(r.tracks, [b]);
  assert.deepEqual(r.missing, [C.trackId(a)]);
  assert.equal(r.selection.tracks.length, 2);
});
test("malformed and oversized selection links are rejected", () => {
  for (const input of ["", "!!!", "a".repeat(50001)])
    assert.throws(() => C.decode(input));
  assert.throws(() => C.validate({ version: 99, name: "X", tracks: [] }));
  assert.throws(() => C.selection("x", Array(251).fill(a)));
});
test("artist bridge matches complete credited artists, never title substrings", () => {
  assert.deepEqual(C.artistTracks("Curio Curio", [a, b]), [a]);
  assert.deepEqual(C.artistTracks("Jorge", [a, b]), []);
  assert.deepEqual(C.artistTracks("Seu Jorge", [a, b]), [b]);
});
