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
      draftDescription: "",
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
      if (clean.draft && typeof saved.draftDescription === "string")
        clean.draftDescription = saved.draftDescription.slice(0, 10000);
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
  // A generated set description is a paragraph, while selection names are
  // limited to 120 characters. Keep the paragraph separately in the draft.
  function setSelectionName(description, fallback) {
    const text = String(description || fallback).trim();
    if (text.length <= 120) return text;
    const sentence = text.match(/^.*?[.!?](?:\s|$)/)?.[0].trim();
    if (sentence && sentence.length <= 120) return sentence;
    return text.slice(0, 117).replace(/\s+\S*$/, "").trimEnd() + "…";
  }
  const originalRender = window.renderSet;
  window.renderSet = function () {
    try {
      state.draft = djSet.length
        ? C.selection(setSelectionName(setDesc, "Current set"), djSet, "set-builder")
        : null;
      state.draftDescription = djSet.length ? setDesc : "";
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
    state.draftDescription = "";
    persist();
  };
  if (state.draft) {
    try {
      const draft = C.resolve(state.draft, DATA);
      djSet = draft.tracks;
      setDesc = state.draftDescription || draft.selection.name;
    } catch (e) {
      state.draft = null;
    }
  }
  // Keep the existing filtering, sorting and tool handlers; give them one home.
  function mountArchive() {
    const main = document.querySelector('.main-area');
    const table = document.getElementById('table-wrap');
    const search = document.getElementById('search');
    if (!main || !table || !search) return;
    document.body.classList.add('archive-ready');
    const toolbar = document.createElement('section');
    toolbar.className = 'archive-toolbar';
    toolbar.setAttribute('aria-label', 'Find tracks');
    toolbar.innerHTML = '<div class="archive-search"><label for="search">Full archive</label></div><div class="archive-controls"><label class="archive-sort-label" for="archive-sort">Sort</label><select id="archive-sort" aria-label="Sort tracks"></select><button type="button" id="archive-direction" aria-label="Reverse sort order">↓</button><button type="button" id="archive-filter-button">Filters</button><details id="archive-tools"><summary>Tools</summary><div class="archive-tools-panel"><div class="archive-tool-actions"></div><div class="archive-dates"><span>Added in the last</span></div></div></details></div>';
    toolbar.querySelector('.archive-search').append(search);
    search.setAttribute('aria-label', 'Search artist, track or album');
    search.placeholder = 'Search artist, track or album';
    main.prepend(toolbar);
    const tools = toolbar.querySelector('#archive-tools');
    const actions = toolbar.querySelector('.archive-tool-actions');
    const panel = toolbar.querySelector('.archive-tools-panel');
    const quick = document.querySelector('.cc-quick-actions');
    quick?.querySelectorAll('button').forEach(b => actions.append(b));
    const dig = button('Dig deeper', () => {
      tools.open = false;
      const artist = search.value.trim();
      if (artist) digDeeper(artist);
      else {
        search.focus();
        showToast('Search for an artist, then choose Dig deeper in Tools');
      }
    });
    dig.id = 'archive-dig';
    dig.title = 'Find related music for the artist in your search';
    actions.append(dig);
    const dates = document.getElementById('cc-time-chips');
    if (dates) {
      toolbar.querySelector('.archive-dates').append(dates);
      dates.querySelectorAll('.time-chip').forEach(chip => {
        chip.setAttribute('role', 'button');
        chip.tabIndex = 0;
        chip.addEventListener('keydown', e => {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chip.click(); }
        });
      });
    }
    const spotify = document.getElementById('cc-spotify-connect');
    if (spotify) panel.append(spotify);
    const playlists = document.getElementById('playlist-actions');
    if (playlists) panel.append(playlists);
    actions.addEventListener('click', e => { if (e.target.closest('button')) tools.open = false; });
    document.addEventListener('click', e => {
      if (tools.open && !tools.contains(e.target)) tools.open = false;
    });
    tools.addEventListener('keydown', e => {
      if (e.key === 'Escape') { tools.open = false; tools.querySelector('summary').focus(); }
    });

    const sort = toolbar.querySelector('#archive-sort');
    const labels = {recent:'Recently added', artist:'Artist A–Z', tempo:'BPM', year:'Release year', album:'Album', plays:'All-time plays', playsY:'Plays this year', playsM:'Plays in 30 days', playsW:'Plays in 7 days'};
    const oldSort = document.querySelector('.sort-controls');
    Object.entries(labels).forEach(([value, label]) => sort.add(new Option(label, value)));
    const direction = toolbar.querySelector('#archive-direction');
    const syncSort = () => {
      sort.value = sorted_key;
      direction.textContent = sdir === 1 ? '↑' : '↓';
      direction.setAttribute('aria-label', 'Reverse sort order: currently ' + (sdir === 1 ? 'ascending' : 'descending'));
      dates?.querySelectorAll('.time-chip').forEach(chip => chip.setAttribute('aria-pressed', String(chip.classList.contains('active'))));
    };
    sort.onchange = () => { oldSort.querySelector('[data-s="' + sort.value + '"]').click(); syncSort(); };
    direction.onclick = () => { oldSort.querySelector('[data-s="' + sorted_key + '"]').click(); syncSort(); };
    new MutationObserver(syncSort).observe(oldSort, {subtree:true, attributes:true, attributeFilter:['class']});
    if (dates) new MutationObserver(syncSort).observe(dates, {subtree:true, attributes:true, attributeFilter:['class']});
    syncSort();

    const filters = document.createElement('dialog');
    filters.id = 'archive-filters';
    filters.className = 'music-dialog archive-filters';
    filters.setAttribute('aria-labelledby', 'archive-filters-title');
    filters.innerHTML = '<div class="archive-filter-head"><h2 id="archive-filters-title">Filter the archive</h2><button type="button" aria-label="Close filters">×</button></div>';
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) filters.append(sidebar);
    document.body.append(filters);
    const filterButton = toolbar.querySelector('#archive-filter-button');
    filterButton.onclick = () => filters.showModal();
    filters.querySelector('.archive-filter-head button').onclick = () => filters.close();
    filters.addEventListener('close', () => filterButton.focus());
    const about = filters.querySelector('.about-link');
    if (about) about.addEventListener('click', () => filters.close(), {capture:true});
    filters.querySelectorAll('.chip, .mood-group-label, .folder-label, .bpm-zone, .about-link').forEach(chip => {
      if (chip.tagName === 'A') return;
      chip.setAttribute('role', 'button');
      chip.tabIndex = 0;
      chip.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chip.click(); }
      });
    });

    // The old nodes retain their IDs because the existing core updates them.
    // Their duplicate mobile controls and introductory panel stay out of the list.
    const stats = document.querySelector('.stats-bar');
    const tryToday = stats?.nextElementSibling;
    if (tryToday?.textContent.startsWith('Try today:')) tryToday.classList.add('archive-try-today');
    const cleanLabels = root => {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const node = walker.currentNode;
        const clean = node.data.replace(/[\p{Extended_Pictographic}\p{Regional_Indicator}\uFE0F\u200D]/gu, '').replace(/^\s+/, '');
        if (node.data !== clean) node.data = clean;
      }
    };
    cleanLabels(panel);
    cleanLabels(filters);
    new MutationObserver(() => cleanLabels(panel)).observe(panel, {subtree:true, childList:true, characterData:true});

    table.tabIndex = 0;
    table.setAttribute('role', 'region');
    table.setAttribute('aria-label', 'Full archive tracks');
    const tbody = document.getElementById('tbody');
    const details = (track, row) => {
      const host = open(track.t);
      dialog.querySelector('.mh-close').setAttribute('aria-label', 'Close track details');
      const artist = document.createElement('p');
      artist.className = 'archive-detail-artist';
      artist.textContent = track.a.replace(/;/g, '; ');
      const list = document.createElement('dl');
      list.className = 'archive-track-metadata';
      const metadata = [
        ['Album', track.al], ['Released', track.r], ['Added', daFmt(track.da)],
        ['BPM', track.tp > 0 ? Math.round(track.tp) : ''], ['Plays', track.pc || 0],
        ['Plays this year', track.py || 0], ['Plays in 30 days', track.pm || 0], ['Plays in 7 days', track.pw || 0],
        ['Vibe', track.vb], ['Crates', (track.c || []).join(', ')],
        ['Genre', track.g], ['Subgenre', (track.sg || []).join(', ')], ['Vinyl', track.vy ? 'In the collection' : '']
      ];
      metadata.forEach(([label, value]) => {
        if (value === '' || value === undefined || value === null) return;
        const dt = document.createElement('dt'), dd = document.createElement('dd');
        dt.textContent = label; dd.textContent = value;
        list.append(dt, dd);
      });
      const extra = document.createElement('div');
      extra.className = 'mh-actions';
      extra.append(button('Similar tracks', e => { e.stopPropagation(); close(); showTrackPop(track, e); }));
      extra.append(button('Artist map', e => { e.stopPropagation(); close(); openArtistMap(track.a); }));
      if (document.body.classList.contains('owner')) extra.append(button('Edit tags', e => { e.stopPropagation(); close(); openQuickTag(e, Number(row.dataset.i)); }));
      if (track.vy && track.did) {
        const link = document.createElement('a');
        link.href = 'https://www.discogs.com/release/' + track.did;
        link.textContent = 'View vinyl on Discogs'; link.target = '_blank'; link.rel = 'noopener';
        extra.append(link);
      }
      host.append(artist, list, extra);
    };
    const decorateRows = () => {
      tbody.querySelectorAll('tr:not([data-archive-row])').forEach(row => {
        row.dataset.archiveRow = 'true';
        const artistName = row.querySelector('.artist-link');
        if (artistName) artistName.textContent = artistName.textContent.replace(/;/g, '; ');
        const cell = document.createElement('td');
        cell.className = 'col-details';
        const b = button('•••', e => {
          e.stopPropagation();
          const track = filtered[Number(row.dataset.i)];
          if (track) details(track, row);
        }, 'archive-track-details');
        const track = filtered[Number(row.dataset.i)];
        b.setAttribute('aria-label', 'Details for ' + (track?.t || 'track'));
        cell.append(b); row.append(cell);
        const play = row.querySelector('.play-btn');
        if (play && play.tagName !== 'A') {
          play.setAttribute('role', 'button'); play.tabIndex = 0;
          play.setAttribute('aria-label', 'Play ' + (track?.t || 'track'));
          play.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); play.click(); }
          });
        }
        const map = row.querySelector('.qt-edit[title="Artist map"]');
        if (map) map.textContent = 'Map';
      });
    };
    new MutationObserver(decorateRows).observe(tbody, {childList:true});
    decorateRows();
  }

  // Navigation and deep links are shared by guest and owner views.
  function mount() {
    const nav = document.createElement("nav");
    nav.className = "music-nav";
    nav.setAttribute("aria-label", "Music");
    nav.innerHTML =
      '<a class="music-brand" href="index.html">DJ Archive</a><a href="index.html" aria-current="page">Discover</a><a href="?view=records">Full archive</a><a href="gigs.html">Gigs</a><a href="?view=saved">Saved</a><a href="https://the-dial-listen.benmpolak.workers.dev/">The Dial</a>';
    document.body.prepend(nav);
    mountArchive();
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
              MusicHome.keep(setSelectionName(setDesc, "My set"), djSet, "set-builder");
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
