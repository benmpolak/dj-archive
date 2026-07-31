#!/usr/bin/env python3
"""Refresh The DJ Archive from a Spotify Extended Streaming History export.

Usage:
    python3 refresh-spotify-data.py /path/to/my_spotify_data.zip --dry-run
    python3 refresh-spotify-data.py /path/to/my_spotify_data.zip

The raw export is read directly from the zip and is never copied into the repo.
Only archive-matched play counts and aggregate listening statistics are baked
into index.html. IP addresses and individual location records are not retained.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "index.html"
WINDOWS = (1, 2, 3, 5, 7, 10)
MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CRATE_BUCKETS = {
    "Jazz", "Funk", "Soul & R&B", "Disco & Boogie", "House", "Electronic",
    "Downtempo", "Hip Hop", "Brazilian", "Afro & World", "Reggae & Dub",
    "Indie & Rock",
}

# Family listening is present in the account export but is not Ben's taste.
KIDS_ARTISTS = {
    "duggee & the squirrels", "bluey", "mojo swoptops", "super simple songs",
    "toddler fun learning", "dream supplier", "hey duggee", "cocomelon",
    "pinkfong", "rené aubry", "the wiggles", "kidz bop kids",
    "kpop demon hunters cast", "huddle", "gracie's corner", "ms rachel",
    "sesame street", "baby shark", "lullaby baby trio", "disney junior",
    "frozen", "various artists", "peppa pig", "julia donaldson",
    "idina menzel", "kristen bell", "danny go!", "caitie's classroom",
    "kids imagine nation", "josh gad", "jonathan groff",
    "the learning station", "blippi", "raffi", "justine clarke",
    "songs for littles", "encanto cast",
    "the little sunshine kids",
}

# A football-song spike is real listening, but it makes a poor annual/seasonal
# recommendation. It remains counted everywhere else.
EDITORIAL_WINNER_EXCLUDES = {"6Agz3UKEtgz0GsOkwBtwoM"}
ACCOUNT_TASTE_EXCLUDE_SIDS = {
    "6Agz3UKEtgz0GsOkwBtwoM",  # Everton F.C. — Spirit Of The Blues
    "7IeuN8aA1Sq5aL2Ensvepy",  # Gary Barlow — Paddington Bear
}

COUNTRY_NAMES = {
    "ES": "Spain", "GR": "Greece", "US": "USA", "IT": "Italy",
    "IL": "Israel", "CY": "Cyprus", "MX": "Mexico", "ZA": "South Africa",
    "MU": "Mauritius", "DE": "Germany", "FR": "France", "PT": "Portugal",
    "NL": "Netherlands", "IE": "Ireland", "BE": "Belgium", "AT": "Austria",
    "CH": "Switzerland", "BR": "Brazil", "DK": "Denmark", "SE": "Sweden",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    return parser.parse_args()


def find_balanced_value(text: str, start: int) -> int:
    opening = text[start]
    pairs = {"[": "]", "{": "}", "(": ")"}
    if opening not in pairs:
        raise ValueError(f"Expected a JS container at index {start}")
    stack = [pairs[opening]]
    in_string = False
    quote = ""
    escaped = False
    i = start + 1
    while i < len(text):
        c = text[i]
        if escaped:
            escaped = False
        elif in_string and c == "\\":
            escaped = True
        elif in_string and c == quote:
            in_string = False
        elif not in_string and c in "\"'`":
            in_string = True
            quote = c
        elif not in_string and c in pairs:
            stack.append(pairs[c])
        elif not in_string and c == stack[-1]:
            stack.pop()
            if not stack:
                return i + 1
        i += 1
    raise ValueError("Unterminated JS value")


def read_js_value(text: str, declaration: str, name: str):
    marker = f"{declaration} {name}="
    start = text.index(marker) + len(marker)
    end = find_balanced_value(text, start)
    return json.loads(text[start:end]), start, end


def replace_js_value(text: str, declaration: str, name: str, value) -> str:
    marker = f"{declaration} {name}="
    if marker not in text:
        raise ValueError(f"Could not find {marker!r}")
    start = text.index(marker) + len(marker)
    end = find_balanced_value(text, start)
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text[:start] + encoded + text[end:]


def replace_var_scalar(text: str, name: str, value) -> str:
    pattern = rf"\bvar {re.escape(name)}=[^;]+;"
    replacement = f"var {name}={json.dumps(value, ensure_ascii=False)};"
    text, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise ValueError(f"Could not replace scalar var {name}")
    return text


def load_genre_mapper():
    spec = importlib.util.spec_from_file_location("genre_map", HERE / "genre-map.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.map_genre


def track_buckets(track: dict, map_genre) -> dict[str, float]:
    weights = defaultdict(float)
    for raw in (track.get("g") or "").split(","):
        bucket = map_genre(raw)
        if not bucket:
            continue
        parts = bucket.split("|")
        for part in parts:
            weights[part] += 1 / len(parts)
    if not weights:
        crates = [c for c in track.get("c", []) if c in CRATE_BUCKETS]
        for crate in crates:
            weights[crate] += 1
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()} if total else {}


def primary_artist(track: dict) -> str:
    return (track.get("a") or "").split(";")[0].strip()


def track_label(track: dict) -> str:
    return f"{primary_artist(track)} — {track.get('t', '')}"


def season_key(date: dt.date) -> tuple[int, int, str]:
    if date.month in (12, 1, 2):
        label_year = date.year + 1 if date.month == 12 else date.year
        return label_year, 0, f"Winter {label_year}"
    if date.month <= 5:
        return date.year, 1, f"Spring {date.year}"
    if date.month <= 8:
        return date.year, 2, f"Summer {date.year}"
    return date.year, 3, f"Autumn {date.year}"


def normalised_artist_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).casefold()


def top_artist_rows(counter: Counter, displays: dict[str, Counter], limit: int) -> list:
    rows = []
    for key, count in counter.most_common(limit):
        display = displays[key].most_common(1)[0][0]
        rows.append((display, count))
    return rows


def round_percentages(values: list[float]) -> list[int]:
    if not values or sum(values) == 0:
        return [0] * len(values)
    total = sum(values)
    raw = [100 * v / total for v in values]
    rounded = [int(x) for x in raw]
    remainder = 100 - sum(rounded)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - rounded[i], reverse=True)
    for i in order[:remainder]:
        rounded[i] += 1
    return rounded


def main() -> int:
    args = parse_args()
    if not args.zip_path.is_file():
        raise SystemExit(f"Spotify export not found: {args.zip_path}")

    html = ARCHIVE.read_text()
    data, _, _ = read_js_value(html, "const", "DATA")
    existing_hunt, _, _ = read_js_value(html, "var", "HUNT")

    tracks_by_sid = defaultdict(list)
    for track in data:
        sid = track.get("sid")
        if isinstance(sid, str) and len(sid) == 22:
            tracks_by_sid[sid].append(track)
    sids = set(tracks_by_sid)
    old_sid_counts = {
        sid: max((track.get("pc") or 0) for track in tracks)
        for sid, tracks in tracks_by_sid.items()
    }
    meta = {sid: tracks[0] for sid, tracks in tracks_by_sid.items()}
    sid_added = {
        sid: min((t.get("da") for t in tracks if t.get("da")), default=0)
        for sid, tracks in tracks_by_sid.items()
    }
    sid_crates = {}
    for sid, tracks in tracks_by_sid.items():
        crates = []
        for track in tracks:
            for crate in track.get("c", []):
                if crate in CRATE_BUCKETS and crate not in crates:
                    crates.append(crate)
        sid_crates[sid] = crates

    map_genre = load_genre_mapper()
    sid_buckets = {sid: track_buckets(track, map_genre) for sid, track in meta.items()}

    # Archive-matched listening aggregates.
    sid_count = Counter()
    sid_dates = defaultdict(list)
    sid_month = defaultdict(Counter)
    year_sid = defaultdict(Counter)
    month_sid = defaultdict(Counter)
    season_sid = defaultdict(Counter)
    hour_counts = [0] * 24
    dow_counts = [0] * 7
    shuffle_counts = Counter()
    year_ms = Counter()
    year_energy_sum = Counter()
    year_energy_n = Counter()
    skip_counts = Counter()
    day_album = Counter()
    day_album_track = defaultdict(Counter)
    year_bucket_plays = defaultdict(Counter)
    play_crates = Counter()
    age_bins = [0, 0, 0, 0]

    # Full-account aggregates, with family listening removed.
    artist_year = defaultdict(Counter)
    artist_displays = defaultdict(lambda: defaultdict(Counter))
    distinct_tracks_year = defaultdict(set)
    distinct_artists_year = defaultdict(set)
    all_distinct_tracks = set()
    all_distinct_artists = set()
    month_all = Counter()
    country_counts = Counter()
    total_track_events = 0
    total_listening_ms = 0
    all_day_counts = Counter()
    all_skip_count = 0
    first_track_play = None

    # Trips use every press of play, matching the original feature.
    trip_events = defaultdict(Counter)
    trip_tracks = defaultdict(lambda: defaultdict(set))

    # Existing Hunt entries can gain plays from the new history.
    hunt_by_sid = {item["sid"]: dict(item) for item in existing_hunt.get("items", [])}
    hunt_playafter = Counter()

    latest_ts = ""
    total_events = 0
    qualifying_tracks = 0

    with zipfile.ZipFile(args.zip_path) as zf:
        names = sorted(
            name for name in zf.namelist()
            if re.search(r"Streaming_History_Audio_.*\.json$", name)
        )
        if not names:
            raise SystemExit("No Extended Streaming History audio JSON files found")
        for name in names:
            with zf.open(name) as fh:
                rows = json.load(fh)
            total_events += len(rows)
            for row in rows:
                total_listening_ms += row.get("ms_played") or 0
                uri = row.get("spotify_track_uri") or ""
                if not uri.startswith("spotify:track:"):
                    continue
                total_track_events += 1
                ts = row.get("ts") or ""
                if ts > latest_ts:
                    latest_ts = ts
                try:
                    date = dt.date.fromisoformat(ts[:10])
                except ValueError:
                    continue
                sid = uri.rsplit(":", 1)[-1]
                all_day_counts[ts[:10]] += 1
                if row.get("skipped") is True:
                    all_skip_count += 1
                if first_track_play is None or ts < first_track_play[0]:
                    first_track_play = (
                        ts,
                        row.get("master_metadata_album_artist_name") or "",
                        row.get("master_metadata_track_name") or "",
                    )
                raw_artist = row.get("master_metadata_album_artist_name") or ""
                artist_key = normalised_artist_key(raw_artist)
                is_family = artist_key in KIDS_ARTISTS
                taste_excluded = is_family or sid in ACCOUNT_TASTE_EXCLUDE_SIDS

                if raw_artist and not is_family:
                    trip_events[raw_artist][ts[:10]] += 1
                    trip_tracks[raw_artist][ts[:10]].add(
                        row.get("master_metadata_track_name") or ""
                    )

                if sid in sids and not taste_excluded and row.get("skipped") is True:
                    skip_counts[sid] += 1

                if (row.get("ms_played") or 0) < 30000:
                    continue
                qualifying_tracks += 1

                if not is_family:
                    year = date.year
                    artist_year[year][artist_key] += 1
                    artist_displays[year][artist_key][raw_artist] += 1
                    distinct_tracks_year[year].add(uri)
                    distinct_artists_year[year].add(artist_key)
                    all_distinct_tracks.add(uri)
                    all_distinct_artists.add(artist_key)
                    month_all[date.month] += 1
                    country = row.get("conn_country") or ""
                    if country:
                        country_counts[country] += 1

                hunt = hunt_by_sid.get(sid)
                if hunt and not taste_excluded and ts[:10] >= hunt.get("d", ""):
                    hunt_playafter[sid] += 1

                if sid not in sids or taste_excluded:
                    continue

                track = meta[sid]
                year = date.year
                ym = date.year * 100 + date.month
                sid_count[sid] += 1
                sid_dates[sid].append(date)
                sid_month[sid][ym] += 1
                year_sid[year][sid] += 1
                month_sid[date.month][sid] += 1
                season_sid[season_key(date)][sid] += 1
                hour_counts[int(ts[11:13])] += 1
                dow_counts[date.weekday()] += 1
                shuffle_counts[bool(row.get("shuffle"))] += 1
                year_ms[year] += row.get("ms_played") or 0

                energy = float(track.get("e") or 0)
                if energy:
                    year_energy_sum[year] += energy
                    year_energy_n[year] += 1

                crates = sid_crates.get(sid) or []
                if crates:
                    for crate in crates:
                        play_crates[crate] += 1 / len(crates)

                added = sid_added.get(sid) or 0
                if added:
                    delta_months = (
                        (date.year - added // 100) * 12
                        + date.month - added % 100
                    )
                    if delta_months <= 3:
                        age_bins[0] += 1
                    elif delta_months <= 12:
                        age_bins[1] += 1
                    elif delta_months <= 36:
                        age_bins[2] += 1
                    else:
                        age_bins[3] += 1

                for bucket, weight in sid_buckets.get(sid, {}).items():
                    year_bucket_plays[year][bucket] += weight

                album = track.get("al") or ""
                if album:
                    artist = primary_artist(track)
                    key = (ts[:10], artist, album)
                    day_album[key] += 1
                    day_album_track[key][sid] += 1

    if not latest_ts:
        raise SystemExit("Spotify export contained no timestamped audio plays")
    ref_date = dt.date.fromisoformat(latest_ts[:10])
    cuts = {years: ref_date - dt.timedelta(days=365 * years) for years in WINDOWS}
    cut_30 = ref_date - dt.timedelta(days=30)
    cut_7 = ref_date - dt.timedelta(days=7)

    # Refresh every play field, clearing stale values first.
    play_fields = {"pc", "fp", "lp", "py", "pm", "pw"}
    play_fields.update(f"p{years}" for years in WINDOWS)
    for track in data:
        for field in play_fields:
            track.pop(field, None)
        sid = track.get("sid")
        dates = sid_dates.get(sid)
        if not dates:
            continue
        track["pc"] = sid_count[sid]
        track["fp"] = min(dates).year * 100 + min(dates).month
        track["lp"] = max(dates).year * 100 + max(dates).month
        for years in WINDOWS:
            count = sum(date >= cuts[years] for date in dates)
            if count:
                track[f"p{years}"] = count
        py = sum(date >= cuts[1] for date in dates)
        pm = sum(date >= cut_30 for date in dates)
        pw = sum(date >= cut_7 for date in dates)
        if py:
            track["py"] = py
        if pm:
            track["pm"] = pm
        if pw:
            track["pw"] = pw

    years = list(range(min(year_sid), ref_date.year + 1))
    current_year = ref_date.year

    # Listening clock and straightforward snapshots.
    lc_dow = [[DAY_NAMES[i], dow_counts[i]] for i in range(7)]
    deliberate_total = sum(shuffle_counts.values())
    deliberate = round(
        100 * shuffle_counts[False] / deliberate_total
    ) if deliberate_total else 0
    hours_year = [[str(year), round(year_ms[year] / 3_600_000)] for year in years]

    track_year = []
    for year in years:
        candidates = [
            (count, sid) for sid, count in year_sid[year].items()
            if sid not in EDITORIAL_WINNER_EXCLUDES
        ]
        if not candidates:
            continue
        count, sid = max(candidates)
        suffix = " so far" if year == current_year else ""
        track_year.append(
            [str(year), f"{track_label(meta[sid])} · {count}x{suffix}"]
        )

    monthly_peaks = []
    for sid, months in sid_month.items():
        for ym, count in months.items():
            monthly_peaks.append((count, ym, sid))
    monthly_peaks.sort(reverse=True)
    obsess = []
    for count, ym, sid in monthly_peaks[:10]:
        year, month = divmod(ym, 100)
        label = f"{MONTHS_SHORT[month - 1]} '{str(year)[2:]}"
        obsess.append([label, f"{track_label(meta[sid])} · {count}x"])

    # Artist/year, range and calendar-month totals use the full account minus
    # identified family listening, rather than only tracks already in the archive.
    aoty = []
    for year in years:
        top = top_artist_rows(artist_year[year], artist_displays[year], 3)
        if not top:
            continue
        label = " · ".join(f"{artist} ({count})" for artist, count in top)
        if year == current_year:
            label += " · so far"
        aoty.append([str(year), label])
    artist_first_year = {}
    for year, counts in artist_year.items():
        for artist in counts:
            artist_first_year[artist] = min(artist_first_year.get(artist, year), year)
    new_disc = [
        [str(year), sum(1 for debut in artist_first_year.values() if debut == year)]
        for year in years
    ]
    range_year = [
        [str(year), len(distinct_tracks_year[year]), len(distinct_artists_year[year])]
        for year in years
    ]
    season_month = [
        [MONTHS_SHORT[month - 1], month_all[month]] for month in range(1, 13)
    ]

    # How long each track had been in the archive when it was played.
    age_bias = [
        ["within 3 months", 0], ["3–12 months", 0],
        ["1–3 years", 0], ["3+ years", 0],
    ]
    for row, pct in zip(age_bias, round_percentages(age_bins)):
        row[1] = pct

    # Listen vs own: split multi-crate tracks fractionally.
    own_crates = Counter()
    for track in data:
        crates = [c for c in track.get("c", []) if c in CRATE_BUCKETS]
        if not crates:
            continue
        for crate in dict.fromkeys(crates):
            own_crates[crate] += 1 / len(set(crates))
    crate_order = [
        crate for crate, _ in
        (play_crates + own_crates).most_common()
        if play_crates[crate] or own_crates[crate]
    ]
    play_pct = {
        crate: round(100 * play_crates[crate] / sum(play_crates.values()))
        for crate in crate_order
    }
    own_pct = {
        crate: round(100 * own_crates[crate] / sum(own_crates.values()))
        for crate in crate_order
    }
    crate_lo = [[crate, play_pct[crate], own_pct[crate]] for crate in crate_order]

    # Listening abroad and energy by year.
    abroad = []
    for code, count in country_counts.most_common():
        if code in {"GB", "ZZ"}:
            continue
        abroad.append([COUNTRY_NAMES.get(code, code), count])
        if len(abroad) == 8:
            break
    uk_pct = round(100 * country_counts["GB"] / sum(country_counts.values()))
    energy_year = [
        [str(year), round(100 * year_energy_sum[year] / year_energy_n[year])]
        for year in years if year_energy_n[year]
    ]

    # Seasonal winners, newest first.
    seasons = []
    for key in sorted(season_sid, reverse=True):
        candidates = [
            (count, sid) for sid, count in season_sid[key].items()
            if sid not in EDITORIAL_WINNER_EXCLUDES
        ]
        if not candidates:
            continue
        count, sid = max(candidates)
        seasons.append([key[2], f"{track_label(meta[sid])} · {count}x"])

    # Soundtrack by calendar month.
    monthly = {}
    for month in range(1, 13):
        rows = []
        for sid, count in month_sid[month].most_common(15):
            rows.append([track_label(meta[sid]), count, sid])
        monthly[str(month)] = rows

    # Obsession arcs for the current top 100 archive tracks.
    top_sids = [sid for sid, _ in sid_count.most_common(100)]
    obsession_arcs = []
    for sid in top_sids:
        counts = sid_month[sid]
        if not counts:
            continue
        indexes = sorted((ym // 100) * 12 + (ym % 100 - 1) for ym in counts)
        lo, hi = indexes[0], indexes[-1]
        series = [0] * (hi - lo + 1)
        for ym, count in counts.items():
            idx = (ym // 100) * 12 + (ym % 100 - 1)
            series[idx - lo] = count
        obsession_arcs.append({
            "l": track_label(meta[sid]),
            "pc": sid_count[sid],
            "start": f"{lo // 12}-{lo % 12 + 1:02d}",
            "c": series,
        })

    # Biggest one-day album binges.
    binge_rows = []
    for (day, artist, album), count in day_album.items():
        sid = day_album_track[(day, artist, album)].most_common(1)[0][0]
        binge_rows.append((count, day, artist, album, sid))
    binge_rows.sort(reverse=True)
    binges = []
    seen_albums = set()
    for count, day, artist, album, sid in binge_rows:
        if count < 8:
            continue
        key = (artist.casefold(), album.casefold())
        if key in seen_albums:
            continue
        seen_albums.add(key)
        date = dt.date.fromisoformat(day)
        binges.append({
            "a": artist, "al": album, "n": count,
            "dl": f"{date.day} {MONTHS_SHORT[date.month - 1]} {date.year}",
            "sid": sid,
        })
        if len(binges) == 150:
            break

    # Multi-day rabbit holes.
    clusters = []
    for artist, days_counter in trip_events.items():
        days = sorted(days_counter)
        if not days:
            continue
        run = [days[0]]
        for day in days[1:]:
            if (dt.date.fromisoformat(day) - dt.date.fromisoformat(run[-1])).days <= 2:
                run.append(day)
            else:
                clusters.append((artist, run))
                run = [day]
        clusters.append((artist, run))
    candidate_clusters = []
    for artist, run in clusters:
        count = sum(trip_events[artist][day] for day in run)
        tracks = set().union(*(trip_tracks[artist][day] for day in run))
        if count >= 8 and len(tracks) >= 3 and len(run) <= 14:
            candidate_clusters.append({
                "a": artist, "start": run[0], "end": run[-1], "n": count
            })
    candidate_clusters.sort(key=lambda row: row["start"])
    trips = []
    for cluster in candidate_clusters:
        placed = False
        for trip in trips:
            if cluster["start"] <= trip["end"] and cluster["end"] >= trip["start"]:
                start = min(trip["start"], cluster["start"])
                end = max(trip["end"], cluster["end"])
                if (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days <= 10:
                    trip["start"], trip["end"] = start, end
                    trip["arts"][cluster["a"]] += cluster["n"]
                    trip["n"] += cluster["n"]
                    placed = True
                    break
        if not placed:
            trips.append({
                "start": cluster["start"], "end": cluster["end"],
                "arts": Counter({cluster["a"]: cluster["n"]}), "n": cluster["n"],
            })
    trips.sort(key=lambda row: -row["n"])
    trip_items = []
    for trip in trips[:100]:
        artists = [name for name, _ in trip["arts"].most_common()]
        trip_items.append({
            "s": trip["start"], "e": trip["end"], "n": trip["n"],
            "arts": artists[:4], "more": max(0, len(artists) - 4),
        })
    trip_items.sort(key=lambda row: row["s"], reverse=True)
    trips_data = {"items": trip_items}

    # Eras: genre shares of archive additions and matched plays.
    adds_by_year = defaultdict(Counter)
    for track in data:
        added = track.get("da") or 0
        year = added // 100
        if years[0] <= year <= current_year:
            for bucket, weight in track_buckets(track, map_genre).items():
                adds_by_year[year][bucket] += weight

    def yearly_rows(source):
        rows = []
        for year in sorted(source, reverse=True):
            total = sum(source[year].values())
            if total < 20:
                continue
            top = source[year].most_common(4)
            rows.append({
                "y": year, "n": round(total),
                "top": [[bucket, round(100 * count / total)] for bucket, count in top],
            })
        return rows

    eras = {
        "adds": yearly_rows(adds_by_year),
        "plays": yearly_rows(year_bucket_plays),
    }

    debut = {}
    artists_added_year = defaultdict(Counter)
    for track in data:
        added = track.get("da") or 0
        year = added // 100
        if not (years[0] <= year <= current_year):
            continue
        artist = primary_artist(track)
        if not artist:
            continue
        artists_added_year[year][artist] += 1
        debut[artist] = min(debut.get(artist, year), year)
    eras_detail = {}
    for year in years:
        top_tracks = [
            {
                "a": meta[sid].get("a", ""), "t": meta[sid].get("t", ""),
                "n": count, "sid": sid,
            }
            for sid, count in year_sid[year].most_common(10)
        ]
        new_artists = [
            artist for artist, count in artists_added_year[year].most_common(40)
            if debut.get(artist) == year and count >= 3
        ][:6]
        if top_tracks or new_artists:
            eras_detail[str(year)] = {"tracks": top_tracks, "newa": new_artists}

    # Re-count the existing Hunt entries. The extended export has no search
    # queries, so it cannot discover new hunts; a future Account Data export can.
    hunt_items = []
    for sid, item in hunt_by_sid.items():
        if sid in ACCOUNT_TASTE_EXCLUDE_SIDS:
            continue
        item["n"] = hunt_playafter[sid]
        hunt_items.append(item)
    hunt_items.sort(key=lambda row: -row["n"])
    hunt_data = dict(existing_hunt)
    hunt_data["items"] = hunt_items[:100]

    # Most skipped is based on actual skip actions, not the 30-second threshold.
    skip_list = []
    for sid, count in skip_counts.most_common(10):
        track = meta[sid]
        skip_list.append([primary_artist(track), track.get("t", ""), count])

    busiest_day, busiest_count = all_day_counts.most_common(1)[0]
    busy_date = dt.date.fromisoformat(busiest_day)
    first_date = dt.date.fromisoformat(first_track_play[0][:10])
    total_hours = round(total_listening_ms / 3_600_000)
    by_numbers = {
        "streams": total_track_events,
        "hours": total_hours,
        "days": round(total_hours / 24),
        "first": f"{first_track_play[1]} — {first_track_play[2]}",
        "firstDate": f"{first_date.day} {calendar.month_name[first_date.month]} {first_date.year}",
        "busyDate": f"{busy_date.day} {calendar.month_name[busy_date.month]} {busy_date.year}",
        "busyN": busiest_count,
        "skipEvery": round(total_track_events / all_skip_count) if all_skip_count else 0,
    }

    # Apply data and aggregate variables to the single-file app.
    html = replace_js_value(html, "const", "DATA", data)
    replacements = {
        "lcHours": hour_counts,
        "lcDOW": lc_dow,
        "hoursYr": hours_year,
        "trackYr": track_year,
        "obsess": obsess,
        "aoty": aoty,
        "rangeY": range_year,
        "seasonM": season_month,
        "ageBias": age_bias,
        "newDisc": new_disc,
        "crateLO": crate_lo,
        "abroad": abroad,
        "ergYr": energy_year,
        "seasons": seasons,
        "OBSESS": obsession_arcs,
        "BINGES": binges,
        "HUNT": hunt_data,
        "TRIPS": trips_data,
        "ERAS": eras,
        "ERASD": eras_detail,
        "MONTHLY": monthly,
    }
    for name, value in replacements.items():
        html = replace_js_value(html, "var", name, value)
    if "var skipList=" in html:
        html = replace_js_value(html, "var", "skipList", skip_list)
    if "var byNumbers=" in html:
        html = replace_js_value(html, "var", "byNumbers", by_numbers)
    else:
        marker = "var newDisc="
        html = html.replace(
            marker,
            "var byNumbers="
            + json.dumps(by_numbers, ensure_ascii=False, separators=(",", ":"))
            + ";\n  "
            + marker,
            1,
        )
    html = replace_var_scalar(html, "lcDeliberate", deliberate)

    through = f"{ref_date.day} {MONTHS_SHORT[ref_date.month - 1]} {ref_date.year}"
    if "var spotifyThrough=" in html:
        html = replace_var_scalar(html, "spotifyThrough", through)
    else:
        html = html.replace(
            "var lcHours=", f"var spotifyThrough={json.dumps(through)};\n  var lcHours=", 1
        )

    # Roll the factual descriptions with the data.
    cutoff = ref_date - dt.timedelta(days=365)
    cutoff_ym = cutoff.year * 100 + cutoff.month
    html, count = re.subn(r"t\.lp<\d{6}", f"t.lp<{cutoff_ym}", html, count=1)
    if count != 1:
        raise ValueError("Could not update Forgotten Loves cutoff")
    html = re.sub(
        r"Different tracks you played each year &middot; [\d,]+ distinct tracks / [\d,]+ artists all-time",
        "Different tracks you played each year &middot; "
        f"{len(all_distinct_tracks):,} distinct tracks / "
        f"{len(all_distinct_artists):,} artists all-time",
        html,
        count=1,
    )
    html = re.sub(
        r"<b style=\"color:var\(--accent\)\">\d+%</b> of your plays are on tracks you added in the last three months.*?How old a track is when you play it:",
        f"<b style=\"color:var(--accent)\">{age_bias[0][1]}%</b> of matched plays are on tracks added to the archive within the previous three months. How long a track had been on the shelves when you played it:",
        html,
        count=1,
    )
    html = re.sub(
        r"\d+% of your listening is in the UK",
        f"{uk_pct}% of your listening is in the UK",
        html,
        count=1,
    )
    html = html.replace("<h3>You Mellowed</h3>", "<h3>Listening Energy</h3>", 1)
    html = re.sub(
        r"Average energy of what you play, by year\..*?not slower\.",
        "Average energy of archive tracks played each year, weighted by qualified plays.",
        html,
        count=1,
    )
    html = html.replace(
        "&middot; from your Spotify listening history</div>'",
        "&middot; Spotify history through '+spotifyThrough+'</div>'",
        1,
    )
    html = html.replace(
        "&middot; from your Spotify history &middot; '+lcDeliberate",
        "&middot; through '+spotifyThrough+' &middot; '+lcDeliberate",
        1,
    )
    html = re.sub(
        r"h\+='<p><b style=\"color:var\(--accent\)\">[\d,]+</b> streams logged since 2012\.</p>';\s*"
        r"h\+='<p><b style=\"color:var\(--accent\)\">[\d,]+ hours</b> of listening — \d+ days solid\.</p>';\s*"
        r"h\+='<p>Your first ever Spotify play: <b style=\"color:var\(--accent2\)\">.*?</b>, .*?</p>';\s*"
        r"h\+='<p>Busiest single day: <b style=\"color:var\(--accent2\)\">.*?</b> — \d+ tracks in one day\.</p>';\s*"
        r"h\+='<p>You skip roughly <b style=\"color:var\(--accent\)\">1 in \d+</b> of what comes on\. Ruthless\.</p>';",
        """h+='<p><b style="color:var(--accent)">'+byNumbers.streams.toLocaleString()+'</b> streams logged since 2012.</p>';
  h+='<p><b style="color:var(--accent)">'+byNumbers.hours.toLocaleString()+' hours</b> of listening — '+byNumbers.days+' days solid.</p>';
  h+='<p>Your first ever Spotify play: <b style="color:var(--accent2)">'+byNumbers.first+'</b>, '+byNumbers.firstDate+'.</p>';
  h+='<p>Busiest single day: <b style="color:var(--accent2)">'+byNumbers.busyDate+'</b> — '+byNumbers.busyN+' tracks in one day.</p>';
  h+='<p>You skip roughly <b style="color:var(--accent)">1 in '+byNumbers.skipEvery+'</b> of what comes on. Ruthless.</p>';""",
        html,
        count=1,
        flags=re.S,
    )

    # Validate the regenerated file before touching disk.
    check_data, _, _ = read_js_value(html, "const", "DATA")
    if len(check_data) != len(data):
        raise ValueError("Track count changed during refresh")
    for declaration, name in (
        ("var", "MONTHLY"), ("var", "BINGES"), ("var", "OBSESS"),
        ("var", "TRIPS"), ("var", "ERAS"), ("var", "ERASD"),
    ):
        read_js_value(html, declaration, name)

    old_unique_total = sum(old_sid_counts.values())
    summary = {
        "history_files": len(names),
        "history_events": total_events,
        "latest_play": latest_ts,
        "archive_tracks": len(data),
        "matched_spotify_ids": len(sid_count),
        "matched_plays": sum(sid_count.values()),
        "qualified_spotify_plays": qualifying_tracks,
        "plays_after_refresh": sum(sid_count.values()),
        "previous_unique_play_total": old_unique_total,
        "new_or_changed_tracks": sum(
            1 for sid in sids
            if sid_count[sid] != old_sid_counts[sid]
        ),
        "through": through,
        "summer_2026_winner": next(
            (row[1] for row in seasons if row[0] == "Summer 2026"), None
        ),
    }

    if args.dry_run:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print("Dry run: index.html not changed")
        return 0

    if not args.no_backup:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = HERE / f"_backup-pre-spotify-refresh-{stamp}.html"
        shutil.copy2(ARCHIVE, backup)
        summary["backup"] = backup.name
    ARCHIVE.write_text(html)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("Updated index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
