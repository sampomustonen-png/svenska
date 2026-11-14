#!/usr/bin/env python3
"""Hakee sources.json-tiedoston RSS-syötteet ja kirjoittaa sivun tiedostot:

    feed.json     jutut, lähteiden tila ja Reddit-pikalinkit
    ordlista.json sanasto: jokaiselle juttujen sanalle suomennos (jos sanakirjasta löytyy)

Käyttö:
    python scripts/build_feed.py --sources sources.json --data data --out _site
"""
from __future__ import annotations

import argparse
import calendar
import concurrent.futures as cf
import gzip
import hashlib
import html
import json
import re
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import feedparser

USER_AGENT = "Mozilla/5.0 (compatible; svensk-lasning/2.0; personal RSS reader)"
CATEGORIES = {"varlden", "aktuellt", "kultur", "latt"}
DEFAULT_MAX_AGE_DAYS = 4
MAX_ITEMS_PER_SOURCE = 25
MAX_ITEMS_TOTAL = 400
SUMMARY_CHARS = 340

# Sama sanojen pilkkominen kuin sivun JavaScriptissä: kirjaimia, väliviiva tai heittomerkki sanan sisällä.
WORD_RE = re.compile(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*")

# Kirjallisuuteen liittyvät sanat: näistä jutuista tulee "Böcker"-tunniste.
BOOK_RE = re.compile(
    r"\b("
    r"\w*bok|\w*boken|\w*bokens|\w*böcker|\w*böckerna|"
    r"roman|romanen|romaner|romanens|\w*roman|"
    r"\w*författar\w*|poet|poeten|poeter|poesi\w*|lyrik\w*|"
    r"dikt|dikten|dikter|diktsamling\w*|novell\w*|essä\w*|"
    r"\w*litteratur\w*|skönlitter\w*|deckare|deckaren|deckarförfattar\w*|"
    r"biografi\w*|memoar\w*|bokförlag\w*|förlaget|bokmäss\w*|"
    r"augustpris\w*|nobelpris\w* i litteratur"
    r")\b",
    re.IGNORECASE,
)

# Yleisiä ruotsin päätteitä, joita kokeillaan, jos taivutusmuotoa ei löydy listasta.
SUFFIXES = (
    "arnas", "ernas", "ornas", "arna", "erna", "orna", "andet", "andes", "ande", "ende",
    "ades", "ade", "ats", "at", "ars", "ers", "ors", "ar", "er", "or", "ens", "ets",
    "en", "et", "na", "ns", "ts", "es", "as", "s", "n", "t", "a", "e",
)


# --------------------------------------------------------------------------- sanakirja

class Ordbok:
    def __init__(self, data_dir: Path):
        with gzip.open(data_dir / "sv-fi.json.gz", "rt", encoding="utf-8") as fh:
            self.entries: dict = json.load(fh)
        self.lower: dict[str, str] = {}
        for key in self.entries:
            self.lower.setdefault(key.lower(), key)
        self.forms: dict[str, list[str]] = {}
        with gzip.open(data_dir / "sv-former.tsv.gz", "rt", encoding="utf-8") as fh:
            for line in fh:
                form, _, lemmas = line.rstrip("\n").partition("\t")
                self.forms[form] = lemmas.split("|")

    def _entry(self, key: str) -> dict:
        e = self.entries[key]
        return {"l": key, "p": e.get("p", ""), "s": [s[:4] for s in e["s"][:3]]}

    def lemmas(self, w: str, guess: bool = True) -> list[str]:
        found: list[str] = []
        if w in self.lower:
            found.append(self.lower[w])
        for lemma in self.forms.get(w, []):
            if lemma not in found:
                found.append(lemma)
        if found or not guess:
            return found
        for suffix in SUFFIXES:
            if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                base = w[: -len(suffix)]
                for cand in (base, base + "a", base + "e"):
                    hits = self.lemmas(cand, guess=False)
                    if hits:
                        return hits[:1]
        return []

    def split(self, w: str) -> list[str] | None:
        """Yhdyssana kahteen osaan: alkuosa (mahdollinen s-liitos) + loppuosan perusmuoto."""
        best = None
        for i in range(3, len(w) - 2):
            left, right = w[:i], w[i:]
            left_keys = self.lemmas(left, guess=False)
            if not left_keys and left.endswith("s") and len(left) > 3:
                left_keys = self.lemmas(left[:-1], guess=False)
            if not left_keys:
                continue
            right_keys = self.lemmas(right)
            if not right_keys:
                continue
            score = min(len(left), len(right))
            if best is None or score > best[0]:
                best = (score, [left_keys[0], right_keys[0]])
        return best[1] if best else None

    def lookup(self, word: str) -> dict | None:
        w = word.lower()
        keys = self.lemmas(w)
        if keys:
            return {"m": [self._entry(k) for k in keys[:2]]}
        if "-" in w:
            tail = self.lookup(w.rsplit("-", 1)[1])
            if tail:
                return tail
        parts = self.split(w)
        if parts:
            return {"c": [self._entry(k) for k in parts]}
        return None


# --------------------------------------------------------------------------- syötteet

def fetch(url: str, timeout: int = 25) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def clean_text(raw: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw or "", flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, limit: int = SUMMARY_CHARS) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:–-— ")
    return cut + "…"


def entry_time(entry) -> float | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            return float(calendar.timegm(value))
    return None


def find_image(entry) -> str | None:
    candidates: list[str] = []
    for media in entry.get("media_thumbnail") or []:
        candidates.append(media.get("url", ""))
    for media in entry.get("media_content") or []:
        kind = str(media.get("type", "")) + str(media.get("medium", ""))
        if "image" in kind or not kind:
            candidates.append(media.get("url", ""))
    for link in entry.get("links") or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image"):
            candidates.append(link.get("href", ""))
    raw = ""
    if entry.get("content"):
        raw = entry["content"][0].get("value", "")
    raw += entry.get("summary", "")
    match = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", raw)
    if match:
        candidates.append(html.unescape(match.group(1)))
    for url in candidates:
        if url and url.startswith("https://"):
            return url
    return None


def normalise_link(link: str) -> str:
    link = link.split("#", 1)[0]
    link = re.sub(r"[?&]utm_[^&]+", "", link)
    return link.rstrip("/")


def read_source(source: dict, now: float) -> tuple[dict, list[dict]]:
    status = {
        "id": source["id"],
        "name": source["name"],
        "category": source["category"],
        "url": source["url"],
        "ok": False,
        "count": 0,
        "error": None,
    }
    # Virheviestit ovat ruotsiksi, koska ne näkyvät sivulla.
    try:
        data = fetch(source["url"])
    except urllib.error.HTTPError as exc:
        status["error"] = f"HTTP {exc.code}"
        return status, []
    except (TimeoutError, socket.timeout):
        status["error"] = "svarade inte i tid"
        return status, []
    except urllib.error.URLError:
        status["error"] = "ingen kontakt"
        return status, []
    except Exception as exc:
        status["error"] = type(exc).__name__
        return status, []

    parsed = feedparser.parse(data)
    if not parsed.entries:
        status["error"] = "tomt eller trasigt flöde"
        return status, []

    status["site"] = parsed.feed.get("link")
    max_age = float(source.get("max_age_days", DEFAULT_MAX_AGE_DAYS)) * 86400
    items = []
    for entry in parsed.entries:
        link = entry.get("link", "")
        title = clean_text(entry.get("title", ""))
        if not title or not link.startswith(("http://", "https://")):
            continue
        published = entry_time(entry) or now
        if published > now + 3600:
            published = now
        if now - published > max_age:
            continue
        summary_raw = entry.get("summary", "")
        if not summary_raw and entry.get("content"):
            summary_raw = entry["content"][0].get("value", "")
        summary = truncate(clean_text(summary_raw))
        if summary.lower() == title.lower():
            summary = ""
        tags = ["bok"] if BOOK_RE.search(f"{title} {summary}") else []
        items.append(
            {
                "id": hashlib.sha1(normalise_link(link).encode()).hexdigest()[:12],
                "title": title,
                "link": link,
                "summary": summary,
                "published": datetime.fromtimestamp(published, timezone.utc).isoformat(timespec="seconds"),
                "ts": int(published),
                "source": source["id"],
                "category": source["category"],
                "tags": tags,
                "image": find_image(entry),
            }
        )
        if len(items) >= MAX_ITEMS_PER_SOURCE:
            break

    status["ok"] = True
    status["count"] = len(items)
    return status, items


def load_config(path: Path) -> tuple[list[dict], list[dict]]:
    config = json.loads(path.read_text(encoding="utf-8"))
    sources = []
    seen = set()
    for source in config["sources"]:
        if source.get("enabled", True) is False:
            continue
        missing = {"id", "name", "url", "category"} - source.keys()
        if missing:
            sys.exit(f"Lähteestä puuttuu kenttiä {sorted(missing)}: {source}")
        if source["category"] not in CATEGORIES:
            sys.exit(f"Tuntematon kategoria '{source['category']}' lähteessä {source['id']}")
        if source["id"] in seen:
            sys.exit(f"Sama id kahdesti: {source['id']}")
        seen.add(source["id"])
        sources.append(source)
    reddit = [
        {"name": r["name"], "url": r["url"], "about": r.get("about", "")}
        for r in config.get("reddit", [])
        if str(r.get("url", "")).startswith("https://")
    ]
    return sources, reddit


def build_glossary(items: list[dict], ordbok: Ordbok) -> tuple[dict, int, int]:
    words: set[str] = set()
    for item in items:
        for text in (item["title"], item["summary"]):
            words.update(m.group(0).lower() for m in WORD_RE.finditer(text))
    glossary = {}
    for w in sorted(words):
        hit = ordbok.lookup(w)
        if hit:
            glossary[w] = hit
    return glossary, len(glossary), len(words)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="sources.json", type=Path)
    parser.add_argument("--data", default="data", type=Path)
    parser.add_argument("--out", default="_site", type=Path)
    args = parser.parse_args()

    sources, reddit = load_config(args.sources)
    now = time.time()

    statuses: dict[str, dict] = {}
    all_items: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(read_source, s, now): s for s in sources}
        for future in cf.as_completed(futures):
            status, items = future.result()
            statuses[status["id"]] = status
            all_items.extend(items)

    # Sama juttu useasta syötteestä näytetään vain kerran (ensimmäinen lähde voittaa).
    order = {s["id"]: i for i, s in enumerate(sources)}
    all_items.sort(key=lambda it: (order[it["source"]], -it["ts"]))
    unique: dict[str, dict] = {}
    for item in all_items:
        unique.setdefault(item["id"], item)
    items = sorted(unique.values(), key=lambda it: it["ts"], reverse=True)[:MAX_ITEMS_TOTAL]

    ordered_statuses = [statuses[s["id"]] for s in sources]
    for status in ordered_statuses:
        mark = "ok " if status["ok"] else "VIRHE"
        detail = f"{status['count']} juttua" if status["ok"] else status["error"]
        print(f"  [{mark}] {status['name']}: {detail}")

    if not any(s["ok"] for s in ordered_statuses):
        print("Yksikään syöte ei toiminut, tiedostoja ei kirjoiteta.", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"),
        "sources": ordered_statuses,
        "reddit": reddit,
        "items": items,
    }
    (args.out / "feed.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"feed.json: {len(items)} juttua {sum(s['ok'] for s in ordered_statuses)}/{len(sources)} lähteestä.")

    ordbok = Ordbok(args.data)
    glossary, found, total = build_glossary(items, ordbok)
    (args.out / "ordlista.json").write_text(
        json.dumps(glossary, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    share = 100 * found / total if total else 0
    print(f"ordlista.json: suomennos {found}/{total} sanalle ({share:.0f} %).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
