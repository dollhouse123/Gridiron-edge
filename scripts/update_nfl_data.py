from __future__ import annotations
import csv
import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("data/nfl_weekly.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

PLAYERS = {
    "gibbs": {"name": "Jahmyr Gibbs", "stat": "rushing_yards"},
    "goff": {"name": "Jared Goff", "stat": "passing_yards"},
    "amon": {"name": "Amon-Ra St. Brown", "stat": "receiving_yards"},
    "allen": {"name": "Josh Allen", "stat": "passing_yards"},
}

SEASONS = [2024, 2025, 2026]

def clean(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())

def fetch_csv(year: int):
    url = f"https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{year}.csv"
    req = urllib.request.Request(url, headers={"User-Agent": "GridironEdge/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))

payload = {
    "source": "nflverse",
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "seasons_loaded": [],
    "players": {k: [] for k in PLAYERS},
}

errors = []

for year in SEASONS:
    try:
        rows = fetch_csv(year)
        payload["seasons_loaded"].append(year)
    except Exception as exc:
        errors.append(f"{year}: {exc}")
        continue

    for pid, meta in PLAYERS.items():
        target = clean(meta["name"])
        for row in rows:
            season_type = str(row.get("season_type") or "").upper()
            if season_type and season_type != "REG":
                continue
            row_name = row.get("player_display_name") or row.get("player_name") or row.get("player") or row.get("name") or ""
            if clean(row_name) != target:
                continue

            try:
                week = int(float(row.get("week") or 0))
                season = int(float(row.get("season") or year))
                value = float(row.get(meta["stat"]) or 0)
            except Exception:
                continue

            if week <= 0:
                continue

            opp = row.get("opponent_team") or row.get("opponent") or "—"
            payload["players"][pid].append({
                "season": season,
                "week": week,
                "opp": opp,
                "v": value,
            })

for games in payload["players"].values():
    games.sort(key=lambda g: (g["season"], g["week"]))

payload["errors"] = errors
OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"Wrote {OUT} with seasons {payload['seasons_loaded']}")
