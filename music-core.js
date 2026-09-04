/* Shared archive / Wax On FM selection contract. No UI, accounts or playback. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.MusicCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const VERSION = 1,
    MAX_TRACKS = 250;
  function trackId(t) {
    return /^[A-Za-z0-9]{22}$/.test(t.sid || "")
      ? "sp:" + t.sid
      : "local:" + JSON.stringify([t.a || "", t.t || "", t.al || ""]);
  }
  function normaliseArtist(s) {
    return String(s || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/&|\+/g, " and ")
      .replace(/[^a-z0-9]+/g, " ")
      .trim()
      .replace(/^the /, "");
  }
  function selection(name, tracks, source) {
    return validate({
      version: VERSION,
      name: String(name || "Untitled selection").trim(),
      source: source || "archive",
      tracks: tracks.map(trackId),
    });
  }
  function validate(value) {
    if (
      !value ||
      value.version !== VERSION ||
      typeof value.name !== "string" ||
      !value.name.trim() ||
      value.name.length > 120 ||
      !Array.isArray(value.tracks) ||
      !value.tracks.length ||
      value.tracks.length > MAX_TRACKS ||
      value.tracks.some(
        (id) =>
          typeof id !== "string" ||
          id.length > 2000 ||
          (!id.startsWith("sp:") && !id.startsWith("local:")),
      )
    )
      throw Error("This selection cannot be opened.");
    return {
      version: VERSION,
      name: value.name.trim(),
      source:
        typeof value.source === "string"
          ? value.source.slice(0, 80)
          : "archive",
      tracks: value.tracks.slice(),
    };
  }
  function resolve(value, catalogue) {
    const s = validate(value),
      index = new Map(catalogue.map((t) => [trackId(t), t]));
    return {
      selection: s,
      tracks: s.tracks.map((id) => index.get(id)).filter(Boolean),
      missing: s.tracks.filter((id) => !index.has(id)),
    };
  }
  function encode(value) {
    const s = JSON.stringify(validate(value));
    if (typeof Buffer !== "undefined")
      return Buffer.from(s).toString("base64url");
    const bytes = new TextEncoder().encode(s);
    let raw = "";
    bytes.forEach((b) => (raw += String.fromCharCode(b)));
    return btoa(raw).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  function decode(raw) {
    if (
      typeof raw !== "string" ||
      raw.length > 50000 ||
      !/^[A-Za-z0-9_-]+$/.test(raw)
    )
      throw Error("This selection link is invalid.");
    let str;
    if (typeof Buffer !== "undefined")
      str = Buffer.from(raw, "base64url").toString();
    else {
      const bytes = Uint8Array.from(
        atob(raw.replace(/-/g, "+").replace(/_/g, "/")),
        (c) => c.charCodeAt(0),
      );
      str = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    }
    return validate(JSON.parse(str));
  }
  function artistTracks(artist, catalogue, count = 5) {
    const key = normaliseArtist(artist);
    return catalogue
      .filter((t) =>
        (t.a || "").split(";").some((a) => normaliseArtist(a) === key),
      )
      .sort((a, b) => (b.pc || 0) - (a.pc || 0) || (b.n || 0) - (a.n || 0))
      .slice(0, count);
  }
  return {
    VERSION,
    MAX_TRACKS,
    trackId,
    normaliseArtist,
    selection,
    validate,
    resolve,
    encode,
    decode,
    artistTracks,
  };
});
