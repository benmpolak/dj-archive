/* Music home: local saves, exact selection links and the archive/gig bridge. */
(function () {
  "use strict";
  const C = MusicCore,
    STORAGE = "dj_music_home_v1";
  const incoming = new URLSearchParams(
    window._musicIncoming || location.search,
  );
  function readSaved(raw) {
    const clean = {
      selections: [],
      draft: null,
      lastSelection: null,
      meta: {},
    };
    try {
      const saved = JSON.parse(raw || "null");
      if (!saved || typeof saved !== "object") return clean;
      if (Array.isArray(saved.selections))
        saved.selections.forEach((s) => {
          try {
            clean.selections.push({
              ...C.validate(s),
              id: typeof s.id === "string" ? s.id : C.encode(s).slice(0, 80),
            });
          } catch (e) {}
        });
      ["draft", "lastSelection"].forEach((k) => {
        try {
          if (saved[k]) clean[k] = C.validate(saved[k]);
        } catch (e) {}
      });
      if (
        saved.meta &&
        typeof saved.meta === "object" &&
        !Array.isArray(saved.meta)
      )
        clean.meta = saved.meta;
    } catch (e) {}
    return clean;
  }
  let state = readSaved(null),
    current = null,
    focusBefore = null;
  try {
    state = readSaved(localStorage.getItem(STORAGE));
  } catch (e) {}
  window.addEventListener("storage", (e) => {
    if (e.key === STORAGE) state = readSaved(e.newValue);
  });

  function persist() {
    try {
      localStorage.setItem(STORAGE, JSON.stringify(state));
      return true;
    } catch (e) {
      showToast(
        "Could not save on this device. Export the selection to keep a copy.",
      );
      return false;
    }
  }
  function notice(text) {
    document.getElementById("mh-message").textContent = text;
  }
  function button(label, handler, cls) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.className = cls || "";
    b.onclick = handler;
    return b;
  }
  function close() {
    dialog.close();
    if (focusBefore) focusBefore.focus();
  }
  const dialog = document.createElement("dialog");
  dialog.id = "music-dialog";
  dialog.className = "music-dialog";
  dialog.setAttribute("aria-labelledby", "mh-title");
  dialog.innerHTML =
    '<div class="mh-dialog-head"><span class="mh-kicker">DJ ARCHIVE</span><button type="button" class="mh-close" aria-label="Close saved selection">×</button></div><h2 id="mh-title">Saved</h2><p id="mh-message" role="status"></p><div id="mh-content"></div>';
  document.body.appendChild(dialog);
  dialog.querySelector(".mh-close").onclick = close;
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) {
      const r = dialog.getBoundingClientRect();
      if (
        e.clientX < r.left ||
        e.clientX > r.right ||
        e.clientY < r.top ||
        e.clientY > r.bottom
      )
        close();
    }
  });
  function open(title) {
    focusBefore = document.activeElement;
    document.getElementById("mh-title").textContent = title;
    notice("");
    const host = document.getElementById("mh-content");
    host.replaceChildren();
    if (!dialog.open) dialog.showModal();
    return host;
  }
  function download(selection) {
    const blob = new Blob([JSON.stringify(C.validate(selection), null, 2)], {
        type: "application/json",
      }),
      url = URL.createObjectURL(blob),
      a = document.createElement("a");
    a.href = url;
    a.download =
      selection.name.replace(/[^a-z0-9]+/gi, "-").toLowerCase() + ".json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function share(selection) {
    try {
      const url = new URL("index.html", location.href);
      url.searchParams.set("selection", C.encode(selection));
      await navigator.clipboard.writeText(url.href);
      notice("Link copied. It opens these exact tracks, in this order.");
    } catch (e) {
      notice("Could not copy a link. Export the selection instead.");
    }
  }
  function view(value, savedId) {
    let result;
    try {
      result = C.resolve(value, DATA);
    } catch (e) {
      open("Selection unavailable");
      notice(e.message);
      return;
    }
    current = { ...result.selection };
    const host = open(current.name);
    const name = document.createElement("input");
    name.id = "mh-name";
    name.maxLength = 120;
    name.value = current.name;
    const label = document.createElement("label");
    label.htmlFor = name.id;
    label.textContent = "Selection name";
    host.append(label, name);
    const actions = document.createElement("div");
    actions.className = "mh-actions";
    function named() {
      return C.validate({
        ...current,
        name: name.value.trim() || current.name,
      });
    }
    actions.append(
      button(
        savedId ? "Save changes" : "Keep selection",
        () => {
          let item;
          try {
            item = { ...named(), id: savedId || crypto.randomUUID() };
          } catch (e) {
            notice(e.message);
            return;
          }
          const old = state.selections.slice();
          state.selections = state.selections.filter((s) => s.id !== item.id);
          state.selections.unshift(item);
          if (persist()) {
            savedId = item.id;
            view(item, item.id);
            notice(
              "Kept on this device. Use a link or export to take it elsewhere.",
            );
          } else state.selections = old;
        },
        "primary",
      ),
    );
    actions.append(
      button("Open in set builder", () => {
        djSet = result.tracks.slice();
        setDesc = named().name;
        if (window.closeDealer) closeDealer();
        if (window._ghExplore) window._ghExplore();
        renderSet();
        close();
        document
          .getElementById("set-builder")
          .scrollIntoView({ behavior: "smooth", block: "nearest" });
      }),
    );
    actions.append(
      button("Copy selection link", () => share(named())),
      button("Export selection", () => download(named())),
    );
    if (document.body.classList.contains("owner"))
      actions.append(
        button("Save to Spotify", () =>
          _doSpotifySave(result.tracks, named().name, null),
        ),
      );
    host.append(actions);
    const meta = document.createElement("p");
    meta.className = "mh-muted";
    meta.textContent = result.tracks.length + " tracks · your order is kept";
    host.append(meta);
    if (result.missing.length)
      notice(
        result.missing.length +
          " tracks are no longer in this archive. Their places remain in the saved selection; available tracks are shown below.",
      );
    const list = document.createElement("ol");
    list.className = "mh-tracklist";
    result.tracks.forEach((t) => {
      const li = document.createElement("li");
      const wrap = document.createElement("div"),
        a = document.createElement("strong"),
        title = document.createElement("span");
      a.textContent = t.a.split(";")[0];
      title.textContent = t.t;
      wrap.append(a, title);
      li.append(wrap);
      const link = document.createElement("a");
      link.textContent = "Listen";
      link.target = "_blank";
      link.rel = "noopener";
      link.href = /^[A-Za-z0-9]{22}$/.test(t.sid || "")
        ? "https://open.spotify.com/track/" + t.sid
        : "https://www.youtube.com/results?search_query=" +
          encodeURIComponent(t.a + " " + t.t);
      li.append(link);
      li.append(
        button(
          "Swap",
          () => {
            const pool = current.source.startsWith("selector:")
              ? _dlrCore.pool(_dlrCore.parse(current.source.slice(9)))
              : findSimilarTracks(t, 80);
            const options = pool.filter(
              (x) => !current.tracks.includes(C.trackId(x)),
            );
            if (!options.length) {
              notice("No other matching tracks in this slice.");
              return;
            }
            const pick = options[Math.floor(Math.random() * options.length)],
              next = named();
            next.tracks[next.tracks.indexOf(C.trackId(t))] = C.trackId(pick);
            view(next, savedId);
            notice("Track swapped. Keep the selection to save this version.");
          },
          "mh-swap",
        ),
      );
      list.append(li);
    });
    host.append(list);
  }
  function saved() {
    const host = open("Saved selections");
    const note = document.createElement("p");
    note.className = "mh-muted";
    note.textContent =
      "Kept on this device. Selection links and exports work across devices.";
    host.append(note);
    const links = document.createElement("div");
    links.className = "mh-actions";
    const gl = document.createElement("a");
    gl.href = "gigs.html?saved=1";
    gl.textContent = "Saved gigs";
    links.append(gl);
    const file = document.createElement("input");
    file.type = "file";
    file.accept = "application/json,.json";
    file.hidden = true;
    file.onchange = async () => {
      if (!file.files[0]) return;
      try {
        if (file.files[0].size > 100000)
          throw Error("Selection file is too large.");
        view(C.validate(JSON.parse(await file.files[0].text())));
      } catch (e) {
        notice("Could not open that selection file.");
      }
    };
    links.append(
      button("Import a selection", () => file.click()),
      file,
    );
    host.append(links);
    if (state.lastSelection)
      host.append(
        button(
          "Last Selector session",
          () => view(state.lastSelection),
          "mh-saved-item",
        ),
      );
    if (state.draft)
      host.append(
        button(
          "Continue current set",
          () => view(state.draft),
          "mh-saved-item",
        ),
      );
    if (!state.selections.length) {
      const empty = document.createElement("p");
      empty.textContent =
        "Make a selection in the Selector, then choose Keep selection.";
      host.append(empty);
    }
    state.selections.forEach((s) => {
      const row = document.createElement("div");
      row.className = "mh-saved-row";
      row.append(
        button(
          s.name + " · " + s.tracks.length + " tracks",
          () => view(s, s.id),
          "mh-saved-item",
        ),
      );
      row.append(
        button("Remove", () => {
          const old = state.selections;
          state.selections = old.filter((x) => x.id !== s.id);
          if (persist()) {
            saved();
            notice("Selection removed.");
          } else state.selections = old;
        }),
      );
      host.append(row);
    });
  }
  window.MusicHome = {
    remember: (name, tracks, source) => {
      state.lastSelection = C.selection(name, tracks, source);
      persist();
    },
    keep: (name, tracks, source) => view(C.selection(name, tracks, source)),
    saved,
  };
  // Metadata overrides are kept separately from the imported catalogue.
  const byId = new Map(DATA.map((t) => [C.trackId(t), t]));
  Object.entries(state.meta || {}).forEach(([id, m]) => {
    const t = byId.get(id);
    if (t && m) {
      if (typeof m.g === "string") t.g = m.g;
      if (typeof m.vb === "string") t.vb = m.vb;
    }
  });
  const originalTag = window.qtApply;
  window.qtApply = function () {
    const t = filtered[_qtTrackIdx];
    const all = document.getElementById("qt-all-artist").checked;
    const targets = t
      ? DATA.filter((d) =>
          all ? d.a.split(";")[0] === t.a.split(";")[0] : d === t,
        )
      : [];
    originalTag();
    targets.forEach((d) => (state.meta[C.trackId(d)] = { g: d.g, vb: d.vb }));
    persist();
  };
  const originalRender = window.renderSet;
  window.renderSet = function () {
    try {
      state.draft = djSet.length
        ? C.selection(setDesc || "Current set", djSet, "set-builder")
        : null;
      persist();
    } catch (e) {
      showToast(
        "This set is too large to save locally. Copy the tracklist to keep it.",
      );
    }
    originalRender();
  };
  const originalClear = window.clearSet;
  window.clearSet = function () {
    originalClear();
    state.draft = null;
    persist();
  };
  if (state.draft) {
    try {
      const draft = C.resolve(state.draft, DATA);
      djSet = draft.tracks;
      setDesc = draft.selection.name;
    } catch (e) {
      state.draft = null;
    }
  }
  // Navigation and deep links are shared by guest and owner views.
  function mount() {
    const nav = document.createElement("nav");
    nav.className = "music-nav";
    nav.setAttribute("aria-label", "Music");
    nav.innerHTML =
      '<a class="music-brand" href="index.html">DJ Archive</a><a href="index.html" aria-current="page">Discover</a><a href="?view=records">Full archive</a><a href="gigs.html">Gigs</a><a href="?view=saved">Saved</a>';
    document.body.prepend(nav);
    const table = document.getElementById("table-wrap");
    if (table) {
      table.tabIndex = 0;
      table.setAttribute("role", "region");
      table.setAttribute("aria-label", "Full archive tracks. Scroll sideways for more columns.");
      const controls = document.createElement("div");
      controls.className = "archive-scroll-tools";
      controls.innerHTML = '<span>Scroll across for all columns</span><button type="button" aria-label="Scroll archive left">←</button><button type="button" aria-label="Scroll archive right">→</button>';
      table.before(controls);
      const [left, right] = controls.querySelectorAll("button");
      left.onclick = () => table.scrollBy({left: -Math.max(260, table.clientWidth * .7), behavior: "smooth"});
      right.onclick = () => table.scrollBy({left: Math.max(260, table.clientWidth * .7), behavior: "smooth"});
      const updateScroll = () => {
        left.disabled = table.scrollLeft < 2;
        right.disabled = table.scrollLeft + table.clientWidth >= table.scrollWidth - 2;
      };
      table.addEventListener("scroll", updateScroll, {passive: true});
      new ResizeObserver(updateScroll).observe(table);
      updateScroll();
    }
    const updateNav = () => {
      const inArchive = !document.body.classList.contains("guest-focus");
      nav.querySelectorAll("[aria-current]").forEach(a => a.removeAttribute("aria-current"));
      nav.querySelector(inArchive ? '[href="?view=records"]' : '[href="index.html"]:not(.music-brand)')?.setAttribute("aria-current", "page");
    };
    new MutationObserver(updateNav).observe(document.body, {attributes: true, attributeFilter: ["class"]});
    updateNav();

    nav.querySelector('[href="?view=saved"]').onclick = (e) => {
      e.preventDefault();
      saved();
    };
    const records = () => {
      nav
        .querySelectorAll("[aria-current]")
        .forEach((a) => a.removeAttribute("aria-current"));
      nav
        .querySelector('[href="?view=records"]')
        .setAttribute("aria-current", "page");
      if (window._ghExplore) window._ghExplore();
      document
        .querySelector(".main-area")
        .scrollIntoView({ behavior: "smooth" });
    };
    nav.querySelector('[href="?view=records"]').onclick = (e) => {
      e.preventDefault();
      records();
    };
    const sb =
      document.querySelector("#set-builder .set-actions") ||
      document.querySelector("#set-builder");
    if (sb)
      sb.append(
        button(
          "Keep this set",
          () => {
            if (djSet.length)
              MusicHome.keep(setDesc || "My set", djSet, "set-builder");
            else showToast("Add some tracks first");
          },
          "mh-keep-set",
        ),
      );
    if (Object.keys(state.meta || {}).length) applyFilters();
    if (incoming.has("selection")) {
      try {
        view(C.decode(incoming.get("selection")));
      } catch (e) {
        open("Selection unavailable");
        notice(e.message);
      }
    } else if (incoming.has("hear")) {
      const a = incoming.get("hear"),
        tracks = C.artistTracks(a, DATA);
      if (tracks.length)
        MusicHome.keep(a + " — five from the archive", tracks, "gig-radar");
      else {
        open("No tracks found");
        notice("This artist is not in this copy of the archive.");
      }
    } else if (incoming.get("view") === "saved") saved();
    else if (incoming.get("view") === "records") records();
    // Avoid re-opening a shared selection after an ordinary reload/navigation.
    if (
      incoming.has("selection") ||
      incoming.has("hear") ||
      incoming.has("view")
    )
      history.replaceState(null, "", location.pathname + location.hash);
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", mount);
  else mount();
  let gigsPromise;
  function gigs() {
    if (!gigsPromise)
      gigsPromise = fetch("gigs-data.json").then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      });
    return gigsPromise;
  }
  window.MusicHome.artistGigs = async function (artist, host) {
    host.replaceChildren();
    host.hidden = true;
    host.dataset.artist = artist;
    const name = C.normaliseArtist(artist);
    try {
      const data = await gigs();
      const now = new Date(),
        today =
          now.getFullYear() +
          "-" +
          String(now.getMonth() + 1).padStart(2, "0") +
          "-" +
          String(now.getDate()).padStart(2, "0");
      const matches = data.matches
        .filter(
          (g) =>
            g.date >= today &&
            (g.performers || []).some((a) => C.normaliseArtist(a) === name),
        )
        .slice(0, 3);
      if (!matches.length) return;
      if (host.dataset.artist !== artist) return;
      const heading = document.createElement("strong");
      heading.textContent = "Playing London";
      host.append(heading);
      matches.forEach((g) => {
        const link = document.createElement("a");
        link.href = "gigs.html?q=" + encodeURIComponent(artist);
        link.textContent =
          new Date(g.date + "T12:00:00").toLocaleDateString("en-GB", {
            day: "numeric",
            month: "short",
          }) +
          " · " +
          g.venue;
        host.append(link);
      });
      host.hidden = false;
    } catch (e) {
      /* No guessed gigs when listings are unavailable. */
    }
  };
})();
