import sys
import json
import base64
import shutil
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from fetch_ra import MANUAL_EVENTS, load_manual_events, write_events

CITY = "London"  # used in the prompt so the model knows where the events are

INBOX = Path("inbox")
FAILED = INBOX / "failed"
MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

PROMPT = """This is a photo of an event poster or a screenshot of a social media post about an event in {city}.
Today is {today}. Extract every event it advertises:
- when: the event date as YYYY-MM-DD. If the year isn't shown, use the next upcoming occurrence after today.
- until: for something that runs continuously over several days or weeks (an exhibition, festival, residency or season), the last day as YYYY-MM-DD, with when as the first day; otherwise an empty string. If it is already running, keep its real start date.
- what: the event or night name, as written (include headliners if there's no separate title).
- who: the main artist(s), comma-separated.
- where: the venue name.
Separate dates that aren't one continuous run (e.g. a tour, or a night repeated on several dates) are separate events.
If the image doesn't advertise an event with a readable date, return an empty list."""

SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "when": {"type": "string"},
                    "what": {"type": "string"},
                    "who": {"type": "string"},
                    "where": {"type": "string"},
                    "until": {"type": "string"},
                },
                "required": ["when", "what", "who", "where", "until"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["events"],
    "additionalProperties": False,
}

def parse_image(client, path, today):
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    response = client.beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=4096,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": MEDIA_TYPES[path.suffix.lower()],
                                             "data": data}},
                {"type": "text", "text": PROMPT.format(city=CITY, today=today)},
            ],
        }],
    )
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"stop_reason={response.stop_reason}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["events"]

def clean(event):
    """Return the event in contract shape, or None if it's unusable."""
    try:
        datetime.strptime(event["when"], "%Y-%m-%d")
        if event["until"]:
            datetime.strptime(event["until"], "%Y-%m-%d")
    except ValueError:
        return None
    if not event["what"].strip():
        return None
    until = event.pop("until")
    if until > event["when"]:
        event["until"] = until
    return event

if __name__ == "__main__":
    images = sorted(p for p in INBOX.glob("*") if p.suffix.lower() in MEDIA_TYPES)
    if not images:
        print("inbox empty")
        sys.exit(0)

    client = anthropic.Anthropic()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    manual = load_manual_events()

    for path in images:
        try:
            events = [e for e in map(clean, parse_image(client, path, today)) if e]
            if not events:
                raise RuntimeError("no events found")
        except Exception as exc:
            print(f"WARN: {path.name} failed: {exc}", file=sys.stderr)
            FAILED.mkdir(exist_ok=True)
            shutil.move(path, FAILED / path.name)
            continue
        for e in events:
            manual.append({**e, "src": "poster"})
            dates = e["when"] + (f" → {e['until']}" if "until" in e else "")
            print(dates, "|", e["who"], "|", e["what"], "@", e["where"])
        path.unlink()

    with open(MANUAL_EVENTS, "w") as f:
        json.dump(manual, f, indent=2)

    try:
        with open("events.json") as f:
            ra_events = [e for e in json.load(f)["events"] if e["src"] == "RA"]
    except FileNotFoundError:
        ra_events = []
    print(f"Wrote {len(write_events(ra_events))} events")
