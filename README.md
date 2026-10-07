# front left

> front left is the dancefloor's universal meeting spot. if you know you know.

Front left is a little physical screen showing upcoming events you are interested in!

It fetches events from any artist on [Resident Advisor](https://ra.co) and from photos of posters, which are parsed by Claude to extract key information. Posters can either be uploaded manually or sent via an Apple Shortcuts flow.

A [Cheap Yellow Display](https://github.com/witnessmenow/ESP32-Cheap-Yellow-Display) (CYD) is used to display upcoming events and I've also included a 3d-printable case (see [Print a case](#7-print-a-case-optional)).

*Photo coming soon.*

No server needed: a GitHub Action re-runs the scripts every day and commits events.json to the repo, and the CYD reads it from raw.githubusercontent.com.

```
 RA (artists you choose) ─┐
                          ├─► events.json ─► GitHub ─► raw.githubusercontent.com ─► CYD
 poster photos (inbox/) ──┘        ▲
                                   └── manual_events.json
```

## What's in the repo

| File | What it does |
|---|---|
| `fetch_ra.py` | Gets upcoming events for your artists from RA, keeps the ones in your city, merges in manual events and writes `events.json`. **Your artist list and city go at the top of this file.** |
| `parse_inbox.py` | Sends each image in `inbox/` to Claude, pulls out the event details and adds them to `manual_events.json`. Optional. |
| `lookup_ra.py` | Finds the RA IDs for artists and cities. |
| `front left.shortcut` | iPhone shortcut to send a poster to `inbox/` from the share sheet. |
| `manual_events.json` | Events you add yourself, or that came from posters. |
| `events.json` | The generated file the display reads. Don't edit it by hand, it gets overwritten. |
| `.github/workflows/update-events.yml` | Runs the scripts daily (and whenever you push to `inbox/`), then commits `events.json`. |
| `display/display.ino` | Arduino sketch for the CYD. |
| `display/secrets.example.h` | Template for your Wi-Fi details and the `events.json` URL. |
| `case/front.stl`, `case/back.stl` | 3D-printable case for the CYD. |

---

## 1. Get your own copy

Click **Use this template** (or fork) on GitHub, then clone your copy:

```bash
git clone https://github.com/<you>/<your-repo>.git
cd <your-repo>
```

If you forked, open the **Actions** tab and click **I understand my workflows, go ahead and enable them**. GitHub turns off scheduled workflows in forks until you do.

The repo can be public or private. A private repo means the display needs a token (step 5).

The repo ships with sample data so the display has something to draw straight away. Every entry in `manual_events.json` starting with `TEST` is fake. Delete those once you've seen the display working.

## 2. Choose your artists and city

Set up Python (3.10 or newer):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Find an artist's RA ID from the last part of their RA URL. For `ra.co/dj/fumi-de` that's `fumi-de`:

```bash
python lookup_ra.py artist fumi-de
# "131776"  fumi (DE)
```

Find your city's area ID:

```bash
python lookup_ra.py area london
# "13"  London (United Kingdom)
```

Put the IDs at the top of `fetch_ra.py`:

```python
ARTISTS = {
    "Fumi": "131776",   # the name on the left is what the display shows
    "VTSS": "60607",
}

AREA_ID = "13"  # London
```

Run it:

```bash
python fetch_ra.py
```

You should see a list of events and `Wrote N events`. If none of your artists have upcoming dates in your city, the script prints an error and leaves `events.json` unchanged. That stops a temporary RA outage from wiping your screen. Add an artist who's playing soon to test it.

> RA has no public API. `fetch_ra.py` uses the same GraphQL endpoint as the ra.co website. Keep requests light (once a day is plenty), and expect to fix things if RA changes their site.

## 3. Add events by hand (optional)

Add an entry to `manual_events.json` for anything that isn't on RA:

```json
{
  "when": "2026-11-14",
  "what": "Night name or description",
  "who": "Artist",
  "where": "Venue",
  "src": "manual"
}
```

For something that runs over several days (an exhibition, a festival), add `"until": "YYYY-MM-DD"`. The display shows it as a date range. Manual events disappear from `events.json` once their last day has passed.

## 4. Add events from posters (optional)

Drop a photo of a poster or a screenshot of an Instagram post (`.jpg`, `.jpeg` or `.png`) into `inbox/`. `parse_inbox.py` asks Claude to read it, adds whatever events it finds to `manual_events.json` and deletes the image. If it can't find an event in an image, the image is moved to `inbox/failed/` so you can check it.

You need an [Anthropic API key](https://console.anthropic.com/). Each image costs a few cents at most.

To run it locally:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python parse_inbox.py
```

The Claude prompt says which city the events are in. Change `CITY` at the top of `parse_inbox.py` to match yours.

### From your iPhone

`front left.shortcut` adds a **front left** option to the share sheet. Share a photo or screenshot to it, and it uploads the image to `inbox/` in your repo. The GitHub Action (step 5) then reads the image and updates the display, usually within a minute or two.

The shortcut needs a GitHub token that can write to your repo:

1. Create a [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new).
   - **Repository access**: Only select repositories → your repo.
   - **Permissions → Contents**: **Read and write**.
   - Copy the token (`github_pat_...`).
2. On your iPhone, open [`front left.shortcut`](front%20left.shortcut) on github.com, tap **Download**, and open it with Shortcuts.
3. Shortcuts asks two questions:
   - **What is your github repository?** Enter the full upload URL, including the trailing slash:
     ```
     https://api.github.com/repos/<you>/<your-repo>/contents/inbox/
     ```
     The shortcut adds the file name (e.g. `20261007-224600.jpg`) straight onto the end, so `<you>/<your-repo>` on its own won't work.
   - **Add your github personal token**: paste the token from step 1.

The token is stored inside the shortcut on your phone, so don't share your installed copy. The shortcut resizes the image to 1568px on its longest side before uploading, which is the size Claude reads best. Share one image at a time.

You don't need an iPhone for this. Anything that can upload a file to `inbox/` works, including the **Add file → Upload files** button on github.com.

## 5. Let GitHub keep it updated

Push your changes:

```bash
git add -A
git commit -m "My artists"
git push
```

Then on GitHub:

1. **Settings → Actions → General → Workflow permissions**: choose **Read and write permissions**, so the workflow can commit `events.json`.
2. To use posters, add a secret under **Settings → Secrets and variables → Actions → New repository secret**, named `ANTHROPIC_API_KEY`. Without it, the poster step is skipped.
3. **Actions → Update events → Run workflow** to check it works.

From then on the workflow runs:

- every day at 06:00 UTC (change the `cron` line in the workflow to adjust),
- whenever an image lands in `inbox/` (from the iPhone shortcut, a `git push`, or an upload on github.com) or `manual_events.json` changes.

Your display URL is:

```
https://raw.githubusercontent.com/<you>/<your-repo>/main/events.json
```

Open it in a browser to check it. GitHub caches raw files for a few minutes, so a new commit can take up to ~5 minutes to show up.

## 6. Set up the display

### Hardware

An **ESP32-2432S028R**, usually sold as the "Cheap Yellow Display": a 2.8" 240×320 screen with a built-in ESP32. You'll also need a USB cable that carries data. Some cheap cables only carry power, and with those the board lights up but your computer never sees it.

#### You may need a dongle

Look at which USB port your board has:

- **Micro-USB only** (the original CYD): use a USB-A to micro-USB cable. If your laptop only has USB-C ports, use a USB-C to micro-USB cable, or a USB-C to USB-A adapter with a normal micro-USB cable.
- **USB-C** (newer boards, often with a micro-USB port as well): a USB-C to USB-C cable often **won't work**. The board gets no power and no port shows up. Use a **USB-A to USB-C** cable instead. If your laptop only has USB-C ports, plug that cable into a **USB-C to USB-A adapter (dongle)**.

Why a USB-C cable doesn't work: a USB-C port doesn't send power down the cable straight away. It waits until it sees a small resistor (5.1kΩ) on the device's "CC" pins, which is how a USB-C device says "something is connected, power me". Many CYDs leave those two resistors off to save a few cents. A USB-C laptop or charger then thinks nothing is plugged in and never turns the power on.

USB-A works differently. A USB-A port always puts out 5V, with no handshake. A USB-A to USB-C cable also has the right resistor built in at its own end. Going through a USB-A port, or a dongle that provides one, skips the check the board can't pass.

### Software

1. Install the [Arduino IDE](https://www.arduino.cc/en/software).
2. Add ESP32 support: in **Boards Manager**, install **esp32 by Espressif Systems**.
3. In **Library Manager**, install:
   - **TFT_eSPI** by Bodmer
   - **ArduinoJson** by Benoit Blanchon (version 7 or newer)

### Configure TFT_eSPI for the CYD

TFT_eSPI gets its pin setup from a file inside the library folder, not from the sketch. Open `Arduino/libraries/TFT_eSPI/User_Setup.h` and replace everything in it with:

```cpp
#define ILI9341_2_DRIVER

#define TFT_WIDTH  240
#define TFT_HEIGHT 320

#define TFT_BL   21
#define TFT_BACKLIGHT_ON HIGH

#define TFT_MISO 12
#define TFT_MOSI 13
#define TFT_SCLK 14
#define TFT_CS   15
#define TFT_DC    2
#define TFT_RST  -1

#define USE_HSPI_PORT

#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define SMOOTH_FONT

#define SPI_FREQUENCY      55000000
#define SPI_READ_FREQUENCY 20000000
```

Some CYDs have two USB ports (USB-C and micro-USB) and use a different driver chip. If your screen is blank or the colours look inverted, swap `ILI9341_2_DRIVER` for `ST7789_DRIVER` and add `#define TFT_INVERSION_ON`. See the [CYD repo](https://github.com/witnessmenow/ESP32-Cheap-Yellow-Display) for more.

Updating the library overwrites `User_Setup.h`, so keep a copy somewhere.

### Secrets

```bash
cp display/secrets.example.h display/secrets.h
```

Fill in `display/secrets.h`:

- `WIFI_SSID` / `WIFI_PASS`: your Wi-Fi. The ESP32 only connects to **2.4 GHz** networks.
- `EVENTS_URL`: the raw URL from step 5.
- `GH_TOKEN`: leave as `""` for a public repo. For a private repo, create a [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new) that can only access this repo, with **Contents: Read-only** permission.

`secrets.h` is in `.gitignore`. Don't commit it.

### Flash it

1. Open `display/display.ino` in the Arduino IDE.
2. **Tools → Board → esp32 → ESP32 Dev Module**.
3. Select the port and click **Upload**. If the upload hangs on `Connecting...`, hold the **BOOT** button on the board until it starts.
4. Open **Serial Monitor** at 115200 baud and look for `HTTP code: 200`.

The display fetches on boot and then every hour. To change the title or refresh rate, edit `TITLE` and `REFRESH_MS` at the top of the sketch. `WHO_MAX_LINES`, `WHAT_MAX_LINES` and `WHERE_MAX_LINES` set how many lines each field can use before it's cut off with `...`. Events that don't fit on screen are counted in a `+N more` footer.

## 7. Print a case (optional)

The `case/` folder has a two-part case for the CYD, ready to print:

| File | Part | Size (W × H × D) |
|---|---|---|
| `case/front.stl` | Front shell. Holds the board, with a window for the screen. | 104.7 × 58.6 × 13.8 mm |
| `case/back.stl` | Flat back panel. | 104.7 × 58.6 × 4.0 mm |

The board sits in the front shell, and the back panel screws onto it.

You'll need:

- **M2 heat-set threaded inserts**, one for each screw hole in the front shell. I used [these](https://www.amazon.co.uk/dp/B0FLJVYGHS).
- **M2 × 12 mm screws**, one for each insert. I used [these](https://www.amazon.co.uk/dp/B0F38BHHJN).

Heat-set inserts are small brass sleeves with a screw thread inside. You put one on the tip of a soldering iron and gently press it into a screw hole in the print. The plastic melts around it and sets as it cools, leaving a solid metal thread. Press slowly and keep the insert straight.

---

## The `events.json` format

This is the only thing the display depends on. You can swap out the Python side entirely, as long as you publish JSON in this shape:

```json
{
  "updated": "2026-10-07T21:04:55+00:00",
  "events": [
    {
      "when": "2026-10-24",
      "until": "2026-10-26",
      "what": "Event title",
      "who": "Artist",
      "where": "Venue",
      "src": "RA"
    }
  ]
}
```

- `when` / `until`: `YYYY-MM-DD`. `until` is optional.
- Events should be sorted by `when`. The display draws them in the order they arrive.
- `src` is `RA`, `poster` or anything you like. The display ignores it for now.

## Troubleshooting

| Problem | Try |
|---|---|
| Screen says **Fetch failed** | Check the Serial Monitor. `404` means the URL is wrong, or the repo is private and has no token. `401` means the token is wrong. |
| Board doesn't power on, or no port shows up in the Arduino IDE | If it's a USB-C board on a USB-C to USB-C cable, switch to a USB-A to USB-C cable, with a dongle if needed (see [You may need a dongle](#you-may-need-a-dongle)). Otherwise, try a different cable: it may be power-only. |
| Screen stays black | Check `User_Setup.h`: the backlight (`TFT_BL 21`) or the wrong driver for your board. |
| Board never connects | Wi-Fi details are wrong, or the network is 5 GHz only. |
| Workflow fails at **Commit changes** with a 403 | Turn on **Read and write permissions** (step 5). |
| `fetch_ra.py` prints `no events fetched` | None of your artists have upcoming events in `AREA_ID`, or RA is blocking or has changed its API. |
| The shortcut says "Added" but nothing shows up in `inbox/` | The shortcut shows that message even if the upload failed. Check the repository URL (full `api.github.com/.../contents/inbox/` path, with trailing slash) and that the token has **Contents: Read and write** on this repo. |
| A poster ends up in `inbox/failed/` | The image had no readable date. Crop it closer, or add the event to `manual_events.json` by hand. |
