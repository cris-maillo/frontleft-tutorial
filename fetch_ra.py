import sys
import requests
from datetime import datetime, timezone
import json

# --- Configure me -----------------------------------------------------------
# RA artist IDs to follow. Find an ID with: python lookup_ra.py artist <slug>
# (the slug is the last part of the artist's RA URL, e.g. ra.co/dj/fumi-de)
ARTISTS = {
    "Fumi": "131776",
    "VTSS": "60607",
    "MZA": "123832",
    "Alycia Bezgo": "150403",
}

# Only keep events in this RA area. Find an ID with: python lookup_ra.py area <city>
AREA_ID = "13"  # London
# ---------------------------------------------------------------------------

RA = "https://ra.co/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://ra.co/events",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Origin": "https://ra.co",
}

QUERY = """query GET_DEFAULT_EVENTS_LISTING($indices: [IndexType!], $filters: [FilterInput], $pageSize: Int, $page: Int, $sortField: FilterSortFieldType, $sortOrder: FilterSortOrderType) {
  listing(indices: $indices, aggregations: [], filters: $filters, pageSize: $pageSize, page: $page, sortField: $sortField, sortOrder: $sortOrder) {
    data { ...eventFragment __typename }
    totalResults
    __typename
  }
}

fragment eventFragment on Event {
  id
  title
  date
  startTime
  contentUrl
  venue { id name area { id name country { name } } }
  artists { id name }
  __typename
}"""

def fetch_artist_events(artist_id: str):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    variables = {
        "indices": ["EVENT"],
        "pageSize": 20,
        "page": 1,
        "aggregations": [],
        "filters": [
            {"type": "ARTIST", "value": artist_id},
            {"type": "DATERANGE", "value": f'{{"gte":"{now}"}}'},
        ],
        "sortOrder": "ASCENDING",
        "sortField": "EVENTDATE",
        "baseFilters": [
            {"type": "ARTIST", "value": artist_id},
            {"type": "DATERANGE", "value": f'{{"gte":"{now}"}}'},
        ],
    }
    r = requests.post(RA, headers=HEADERS,
                       json={"operationName": "GET_DEFAULT_EVENTS_LISTING",
                             "variables": variables, "query": QUERY},
                       timeout=15)
    r.raise_for_status()
    return r.json()["data"]["listing"]["data"]

def format_date(value):
    return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%a %d %b %Y")

def event_area_id(event):
    venue = event.get("venue") or {}
    area = venue.get("area") or {}
    return area.get("id") or ""

def to_contract(matches):
    seen = {}
    for artist_name, e in matches:
        key = e["contentUrl"]  # stable unique id per event
        if key in seen:
            continue
        seen[key] = {
            "when": e["date"][:10],          # trim to YYYY-MM-DD
            "what": e["title"],
            "who": artist_name,
            "where": (e.get("venue") or {}).get("name", ""),
            "src": "RA",
        }
    return sorted(seen.values(), key=lambda x: x["when"])

MANUAL_EVENTS = "manual_events.json"

def load_manual_events():
    try:
        with open(MANUAL_EVENTS) as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def write_events(ra_events):
    """Merge RA events with upcoming manual ones and write events.json."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seen = {}
    for e in ra_events + [m for m in load_manual_events() if m.get("until", m["when"]) >= today]:
        seen.setdefault((e["when"], e["what"].lower()), e)
    events = sorted(seen.values(), key=lambda x: x["when"])
    out = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "events": events,
    }
    with open("events.json", "w") as f:
        json.dump(out, f, indent=2)
    return events

if __name__ == "__main__":
    matches = []
    for name, artist_id in ARTISTS.items():
        try:
            for e in fetch_artist_events(artist_id):
                if event_area_id(e) != AREA_ID:
                    continue
                matches.append((name, e))
                print(format_date(e["date"]), "|", name, "|", e["title"], "@", (e.get("venue") or {}).get("name", ""))
        except Exception as exc:
            print(f"WARN: {name} ({artist_id}) failed: {exc}", file=sys.stderr)

    contract_events = to_contract(matches)
    if not contract_events:
        print("ERROR: no events fetched from any artist, aborting", file=sys.stderr)
        sys.exit(1)

    events = write_events(contract_events)
    print(f"Wrote {len(events)} events")
