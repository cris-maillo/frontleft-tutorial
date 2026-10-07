#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>

#include "secrets.h"  // WIFI_SSID, WIFI_PASS, EVENTS_URL, GH_TOKEN — copy secrets.example.h

TFT_eSPI tft = TFT_eSPI();

const char* TITLE         = "front left";  // header text at the top of the screen
const unsigned long REFRESH_MS = 3600000UL;  // re-fetch every hour

const int MAX_EVENTS      = 20;  // how many we parse; the screen decides how many we show
const int WHO_MAX_LINES   = 2;
const int WHAT_MAX_LINES  = 3;
const int WHERE_MAX_LINES = 1;
const int WRAP_BUF        = 4;   // >= the largest of the above

struct Event {
  String when;   // "24.10" or "20.09 - 15.11"
  String who;    // headline (artist)
  String what;   // description
  String where_; // venue
  String src;    // "RA" / "poster" (parsed, not displayed yet)
};

Event events[MAX_EVENTS];
int eventCount = 0;
String updatedAt = "";

// --- "2026-10-24" or "2026-09-01T13:53:48..." -> "24.10" ---
String formatDate(const String& iso) {
  if (iso.length() < 10) return iso;
  return iso.substring(8, 10) + "." + iso.substring(5, 7);
}

// "20.09" or "20.09 - 15.11" if there's an end date
String formatRange(const String& from, const String& until) {
  String s = formatDate(from);
  if (until.length() && until != from) s += " - " + formatDate(until);
  return s;
}

bool fetchEvents() {
  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  if (!http.begin(client, EVENTS_URL)) {
    Serial.println("http.begin() failed");
    return false;
  }
  if (strlen(GH_TOKEN)) http.addHeader("Authorization", String("Bearer ") + GH_TOKEN);

  int code = http.GET();
  Serial.printf("HTTP code: %d\n", code);
  if (code != 200) {
    Serial.println(http.getString());
    http.end();
    return false;
  }

  String payload = http.getString();
  http.end();

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload);
  if (err) {
    Serial.print("JSON parse failed: ");
    Serial.println(err.c_str());
    return false;
  }

  updatedAt = formatDate(String(doc["updated"] | ""));

  eventCount = 0;
  for (JsonObject e : doc["events"].as<JsonArray>()) {
    if (eventCount >= MAX_EVENTS) break;
    Event& ev = events[eventCount];
    ev.when   = formatRange(String(e["when"] | ""), String(e["until"] | ""));
    ev.who    = String(e["who"]   | "");
    ev.what   = String(e["what"]  | "");
    ev.where_ = String(e["where"] | "");
    ev.src    = String(e["src"]   | "");
    eventCount++;
  }
  return true;
}

// --- word-wrap: fills out[], returns line count. Adds "..." if text is cut off. ---
int wrapLines(const String& text, int maxWidth, String out[], int maxLines) {
  int lines = 0, start = 0, n = text.length();

  while (start < n && lines < maxLines) {
    int end = start, lastSpace = -1;
    while (end < n) {
      if (text[end] == ' ') lastSpace = end;
      if (tft.textWidth(text.substring(start, end + 1)) > maxWidth) break;
      end++;
    }

    int cut;
    if (end >= n)               cut = n;
    else if (lastSpace > start) cut = lastSpace;
    else                        cut = end;  // no space — hard break

    String line = text.substring(start, cut);
    line.trim();
    out[lines++] = line;

    start = cut;
    while (start < n && text[start] == ' ') start++;
  }

  // text didn't fit in maxLines — ellipsise the last line
  if (start < n && lines > 0) {
    String& last = out[lines - 1];
    while (last.length() && tft.textWidth(last + "...") > maxWidth) {
      last.remove(last.length() - 1);
    }
    last.trim();
    last += "...";
  }
  return lines;
}

void drawLines(String lines[], int count, int x, int y, int lineH, bool bold) {
  for (int i = 0; i < count; i++) {
    tft.setCursor(x, y + i * lineH);
    tft.print(lines[i]);
    if (bold) {                       // fake bold: redraw 1px right
      tft.setCursor(x + 1, y + i * lineH);
      tft.print(lines[i]);
    }
  }
}

void drawEvents() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextSize(1);

  int screenW = tft.width();
  int screenH = tft.height();
  int margin  = 12;
  int maxW    = screenW - margin * 2;
  int lineH   = 14;
  int gap     = 16;
  int bottom  = screenH - lineH - 4;  // keep one line free for "+N more"

  // header
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  String header = TITLE;
  tft.setCursor((screenW - tft.textWidth(header)) / 2, 10);
  tft.print(header);

  if (updatedAt.length()) {
    tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
    tft.setCursor((screenW - tft.textWidth(updatedAt)) / 2, 22);
    tft.print(updatedAt);
  }

  int y = 46;
  int shown = 0;

  for (int i = 0; i < eventCount; i++) {
    Event& ev = events[i];

    // wrap everything first so we know the block height
    String whoL[WRAP_BUF], whatL[WRAP_BUF], whereL[WRAP_BUF];
    int nWho   = wrapLines(ev.who,    maxW - 1, whoL,   WHO_MAX_LINES);  // -1 for bold offset
    int nWhat  = wrapLines(ev.what,   maxW,     whatL,  WHAT_MAX_LINES);
    int nWhere = wrapLines(ev.where_, maxW,     whereL, WHERE_MAX_LINES);

    int blockH = lineH * (1 + nWho + nWhat + nWhere);
    if (y + blockH > bottom) break;   // doesn't fit — stop here

    // date / range
    tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
    tft.setCursor(margin, y);
    tft.print(ev.when);
    y += lineH;

    // who
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    drawLines(whoL, nWho, margin, y, lineH, true);
    y += lineH * nWho;

    // what
    drawLines(whatL, nWhat, margin, y, lineH, false);
    y += lineH * nWhat;

    // where
    tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
    drawLines(whereL, nWhere, margin, y, lineH, false);
    y += lineH * nWhere;

    y += gap;
    shown++;
  }

  // footer if some didn't fit
  if (shown < eventCount) {
    String more = "+" + String(eventCount - shown) + " more";
    tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
    tft.setCursor((screenW - tft.textWidth(more)) / 2, screenH - lineH);
    tft.print(more);
  }
}

void setup() {
  Serial.begin(115200);

  tft.init();
  tft.setRotation(0);
  tft.fillScreen(TFT_BLACK);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) delay(300);

  if (fetchEvents()) drawEvents();
  else {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setCursor(10, 10);
    tft.print("Fetch failed");
  }
}

void loop() {
  delay(REFRESH_MS);
  if (fetchEvents()) drawEvents();
}
