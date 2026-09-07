from __future__ import annotations
import json
import os
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("data/sportsbook_props.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

PLAYERS = {
    "gibbs": {"name": "Jahmyr Gibbs", "stat": "rushing_yards"},
    "goff": {"name": "Jared Goff", "stat": "passing_yards"},
    "amon": {"name": "Amon-Ra St. Brown", "stat": "receiving_yards"},
    "allen": {"name": "Josh Allen", "stat": "passing_yards"},
}

def clean(s):
    return "".join(ch.lower() for ch in str(s or "") if ch.isalnum())

def as_float(v):
    try:
        return float(v)
    except Exception:
        return None

api_key = os.environ.get("SPORTSGAMEODDS_API_KEY", "").strip()
if not api_key:
    raise SystemExit("SPORTSGAMEODDS_API_KEY secret is missing")

params = urllib.parse.urlencode({
    "apiKey": api_key,
    "leagueID": "NFL",
    "oddsAvailable": "true",
    "includeAltLines": "false",
    "limit": "25",
})
url = "https://api.sportsgameodds.com/v2/events?" + params
req = urllib.request.Request(url, headers={"User-Agent": "GridironEdge/1.0"})

with urllib.request.urlopen(req, timeout=60) as r:
    payload = json.loads(r.read().decode("utf-8"))

events = payload.get("data") or payload.get("events") or []
if isinstance(events, dict):
    events = list(events.values())

result = {
    "source": "SportsGameOdds",
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "status": "ok",
    "players": {},
}

for pid, meta in PLAYERS.items():
    target = clean(meta["name"])
    candidates = []

    for event in events:
        odds = event.get("odds") or {}
        if isinstance(odds, list):
            odds = {str(i): v for i, v in enumerate(odds)}
        for odd in odds.values():
            if not isinstance(odd, dict):
                continue
            if odd.get("statID") != meta["stat"]:
                continue
            if str(odd.get("betTypeID") or "").lower() != "ou":
                continue
            if str(odd.get("sideID") or "").lower() != "over":
                continue

            market_name = clean(odd.get("marketName"))
            player_id = clean(odd.get("playerID") or odd.get("statEntityID"))
            if target not in market_name and target not in player_id:
                continue

            books = []
            lines = []
            by_book = odd.get("byBookmaker") or {}
            for book, q in by_book.items():
                if not isinstance(q, dict) or q.get("available") is False:
                    continue
                line = as_float(q.get("overUnder"))
                if line is None:
                    continue
                lines.append(line)
                books.append({
                    "book": book,
                    "line": line,
                    "odds": q.get("odds"),
                    "updated_at": q.get("lastUpdatedAt"),
                })

            fair_line = as_float(odd.get("fairOverUnder"))
            book_line = as_float(odd.get("bookOverUnder"))
            consensus = fair_line
            if consensus is None and lines:
                consensus = statistics.median(lines)
            if consensus is None:
                consensus = book_line
            if consensus is None:
                continue

            candidates.append({
                "market_name": odd.get("marketName"),
                "stat": meta["stat"],
                "consensus_line": consensus,
                "fair_line": fair_line,
                "book_consensus_line": book_line,
                "fair_odds": odd.get("fairOdds"),
                "book_odds": odd.get("bookOdds"),
                "books": sorted(books, key=lambda x: x["book"]),
                "event_id": event.get("eventID"),
                "start_time": event.get("startsAt") or event.get("startTime") or event.get("startDate"),
            })

    if candidates:
        # Prefer the candidate with the most bookmaker quotes.
        candidates.sort(key=lambda x: len(x["books"]), reverse=True)
        result["players"][pid] = candidates[0]

OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(f"Wrote {OUT} with {len(result['players'])} current player props")
