"""Look up the RA IDs that fetch_ra.py needs.

    python lookup_ra.py artist fumi-de   # slug from ra.co/dj/fumi-de
    python lookup_ra.py area berlin      # search areas by name
"""
import sys
import requests

from fetch_ra import RA, HEADERS

QUERIES = {
    "artist": ("query($q: String) { artist(slug: $q) { id name } }", "artist"),
    "area": ("query($q: String) { areas(searchTerm: $q, limit: 10) { id name country { name } } }", "areas"),
}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in QUERIES:
        sys.exit(__doc__)
    kind, term = sys.argv[1], sys.argv[2]
    query, field = QUERIES[kind]
    r = requests.post(RA, headers=HEADERS, json={"query": query, "variables": {"q": term}}, timeout=15)
    r.raise_for_status()
    result = r.json()["data"][field]
    if not result:
        sys.exit(f"No {kind} found for {term!r}")
    for item in result if isinstance(result, list) else [result]:
        country = f" ({item['country']['name']})" if "country" in item else ""
        print(f'"{item["id"]}"  {item["name"]}{country}')
