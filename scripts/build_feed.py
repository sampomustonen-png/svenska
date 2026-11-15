#!/usr/bin/env python3
"""Hakee sources.json-tiedoston RSS-syötteet ja kirjoittaa sivun tiedostot:

    feed.json    jutut, lähteiden tila ja Reddit-pikalinkit
    ordbok.json  ruotsi–suomi-sanakirja selaimelle (data/-kansiosta + omat korjaukset)

Käyttö:
    python scripts/build_feed.py --sources sources.json --data data --out _site --cache .cache
"""
from __future__ import annotations

import argparse
import calendar
import collections
import concurrent.futures as cf
import hashlib
import html
import json
import re
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import feedparser

sys.path.insert(0, str(Path(__file__).parent))
import ordbok_data  # noqa: E402

USER_AGENT = "Mozilla/5.0 (compatible; svensk-lasning/3.0; personal RSS reader)"
CATEGORIES = {"varlden", "aktuellt", "kultur", "latt"}
DEFAULT_MAX_AGE_DAYS = 4
MAX_ITEMS_PER_SOURCE = 25
MAX_ITEMS_TOTAL = 400
SUMMARY_CHARS = 360
IMAGE_FETCH_LIMIT = 120  # kuinka monen uuden jutun kuva haetaan yhdellä ajolla

# Sama sanojen pilkkominen kuin selaimessa.
WORD_RE = re.compile(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*")

BOOK_RE = re.compile(
    r"\b("
    r"\w*bok|\w*boken|\w*bokens|\w*böcker|\w*böckerna|"
    r"roman|romanen|romaner|romanens|\w+roman|"
    r"\w*författar\w*|poet|poeten|poeter|poesi\w*|lyrik\w*|"
    r"dikt|dikten|dikter|diktsamling\w*|novell\w*|essä\w*|"
    r"\w*litteratur\w*|skönlitter\w*|deckare|deckaren|deckarförfattar\w*|"
    r"biografi\w*|memoar\w*|bokförlag\w*|förlaget|bokmäss\w*|"
    r"augustpris\w*|nobelpris\w* i litteratur"
    r")\b",
    re.IGNORECASE,
)
# Sanontoja, joissa "bok" ei tarkoita kirjaa.
NOT_BOOK_RE = re.compile(r"\b(för[ad]? bok|förde bok|bokför\w*|bokslut\w*|bokning\w*)\b", re.IGNORECASE)

FILM_RE = re.compile(
    r"\b("
    r"film|filmen|filmer|filmerna|filmens|\w+film|\w+filmen|\w+filmer|filmar\w*|filmade|"
    r"biograf\w*|bion|biopremiär\w*|regissör\w*|regisserat|skådespelar\w*|"
    r"tv-serie\w*|tv-serien|dramaserie\w*|thrillerserie\w*|serieskapar\w*|tv-program\w*|"
    r"netflix|hbo|viaplay|svt play|disney\+|streaming\w*|"
    r"oscar\w*|guldbagge\w*|filmfestival\w*|dokumentär\w*"
    r")\b",
    re.IGNORECASE,
)

# Länsimaiden politiikka: jutussa mainitaan länsimainen maa tai toimija JA politiikkaan liittyvä sana.
WEST_RE = re.compile(
    r"\b("
    r"usa|usa:s|amerikansk\w*|trump\w*|vita huset|washington|kongress\w*|senat\w*|representanthus\w*|"
    r"demokrater\w*|republikan\w*|eu|eu:s|eu-\w+|europa\w*|europeisk\w*|bryssel|nato\w*|"
    r"tyskland\w*|tysk\w*|berlin|merz|frankrike\w*|fransk\w*|macron|paris|storbritannien\w*|britt\w*|"
    r"london|starmer|italien\w*|meloni|spanien\w*|spansk\w*|polen\w*|polsk\w*|nederländ\w*|belgien\w*|"
    r"österrike\w*|ungern\w*|kanada\w*|danmark\w*|dansk\w*|norge\w*|norsk\w*|baltikum|estland\w*|"
    r"lettland\w*|litauen\w*|grekland\w*|portugal\w*|irland\w*|schweiz\w*|ukrain\w*|zelenskyj\w*|"
    r"von der leyen|kaja kallas|europaparlament\w*|eu-kommission\w*|ministerråd\w*"
    r")\b",
    re.IGNORECASE,
)
POLITICS_RE = re.compile(
    r"\b("
    r"val|valet|valen|valrörelse\w*|valseger\w*|president\w*|premiärminister\w*|statsminister\w*|"
    r"regering\w*|parlament\w*|parti|partiet|partier\w*|\w+partiet|minister\w*|\w+minister\w*|"
    r"förhandl\w*|avtal\w*|sanktion\w*|tull\w*|toppmöte\w*|politi\w*|opposition\w*|koalition\w*|"
    r"omröstning\w*|förbundskansler\w*|kansler\w*|lagförslag\w*|budget\w*|säkerhetspolitik\w*|"
    r"försvar\w*|diplomat\w*|fredssamtal\w*|fredsavtal\w*|vapenvila\w*|kommission\w*|ledamot\w*|"
    r"demokrati\w*|populis\w*|högerextrem\w*|ytterhöger\w*|migrationspolitik\w*|asylpolitik\w*|"
    r"\w*medlemskap\w*|\w+valet|\w+valen|\w*toppmöte\w*|\w*samtal|\w*förhandling\w*|\w*minister\w*|\w*ministr\w*"
    r")\b",
    re.IGNORECASE,
)

# Länsimaiset johtajat: pelkkä nimi riittää politiikkamerkintään.
LEADER_RE = re.compile(
    r"\b(trump\w*|vance|macron\w*|merz|starmer\w*|meloni\w*|von der leyen|kaja kallas|zelenskyj\w*|"
    r"tusk\w*|orbán\w*|orban\w*|sánchez|rutte\w*|frederiksen\w*|støre\w*|stubb\w*|orpo\w*|rubio\w*)\b",
    re.IGNORECASE,
)

# Opulensin ingressit alkavat lajityypillä, esim. "LYRIK. " tai "TONSATT POESI. ".
GENRE_RE = re.compile(r"^([A-ZÅÄÖÉ][A-ZÅÄÖÉ0-9 \-&]{4,40})\.\s+")
# WordPress-syötteiden loppurivi, esim. "Inlägget X dök först upp på MovieZine.se."
WP_FOOTER_RE = re.compile(r"\s*(?:Inlägget|The post)\s.+?\s(?:dök först upp på|appeared first on)\s.+$", re.S)


# --------------------------------------------------------------------------- apufunktiot

def fetch(url: str, timeout: int = 25, limit: int | None = None) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.5",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(limit) if limit else response.read()


def clean_text(raw: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw or "", flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, limit: int = SUMMARY_CHARS) -> str:
    """Lyhentää tekstin virkkeen rajalta. Jos ensimmäinenkin virke on liian pitkä, katkaistaan sanan rajalta."""
    if len(text) <= limit:
        return text
    sentences = re.findall(r".+?(?:[.!?…]+[”\"’)]*(?=\s|$)|$)", text)
    out = ""
    for sentence in sentences:
        candidate = (out + " " + sentence.strip()).strip()
        if len(candidate) > limit:
            break
        out = candidate
    if len(out) >= 80:
        return out
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:–-— ")
    return cut + "…"


def entry_time(entry) -> float | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            return float(calendar.timegm(value))
    return None


def feed_image(entry) -> str | None:
    candidates: list[str] = []
    for media in entry.get("media_content") or []:
        kind = str(media.get("type", "")) + str(media.get("medium", ""))
        if "image" in kind or not kind:
            candidates.append(media.get("url", ""))
    for link in entry.get("links") or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image"):
            candidates.append(link.get("href", ""))
    for media in entry.get("media_thumbnail") or []:
        candidates.append(media.get("url", ""))
    raw = (entry["content"][0].get("value", "") if entry.get("content") else "") + entry.get("summary", "")
    match = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", raw)
    if match:
        candidates.append(html.unescape(match.group(1)))
    return next((u for u in candidates if u and u.startswith("https://")), None)


def og_image(page: str) -> str | None:
    """Etsii jutun sivulta isoimman jakokuvan (og:image)."""
    for pattern in (
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
    ):
        match = re.search(pattern, page, re.I)
        if match:
            url = html.unescape(match.group(1)).strip()
            if url.startswith("//"):
                url = "https:" + url
            if url.startswith("https://"):
                return url
    return None


def normalise_link(link: str) -> str:
    link = link.split("#", 1)[0]
    link = re.sub(r"[?&](utm_[^&]+|origin=rss)", "", link)
    return link.rstrip("/")


def tags_for(title: str, summary: str) -> list[str]:
    text = f"{title} {summary}"
    tags = []
    if LEADER_RE.search(text) or (WEST_RE.search(text) and POLITICS_RE.search(text)):
        tags.append("politik")
    if BOOK_RE.search(text) and not NOT_BOOK_RE.search(text):
        tags.append("bok")
    if FILM_RE.search(text):
        tags.append("film")
    return tags


def difficulty(text: str, zipf: dict[str, float]) -> int:
    """1 = lätt, 2 = medel, 3 = svår. Perustuu harvinaisten sanojen osuuteen ja virkkeiden pituuteen."""
    words = [w.lower() for w in WORD_RE.findall(text)]
    if len(words) < 4:
        return 0
    rare = sum(1 for w in words if zipf.get(w, 0) < 3.6) / len(words)
    long_words = sum(1 for w in words if len(w) > 9) / len(words)
    sentences = max(1, len(re.findall(r"[.!?…]+", text)))
    per_sentence = len(words) / sentences
    score = rare * 100 + long_words * 60 + per_sentence * 0.8
    if score < 26:
        return 1
    if score < 40:
        return 2
    return 3


# --------------------------------------------------------------------------- syötteet

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
    exclude = [p.lower() for p in source.get("exclude_url", [])]
    include = [p.lower() for p in source.get("include_url", [])]
    required = source.get("require_tag")
    items = []
    for entry in parsed.entries:
        link = entry.get("link", "")
        title = clean_text(entry.get("title", ""))
        if not title or not link.startswith(("http://", "https://")):
            continue
        if any(p in link.lower() for p in exclude):
            continue
        if include and not any(p in link.lower() for p in include):
            continue
        published = entry_time(entry) or now
        if published > now + 3600:
            published = now
        if now - published > max_age:
            continue
        summary_raw = "" if source.get("no_summary") else entry.get("summary", "")
        if not summary_raw and entry.get("content"):
            summary_raw = entry["content"][0].get("value", "")
        summary = WP_FOOTER_RE.sub("", clean_text(summary_raw))
        genre = None
        match = GENRE_RE.match(summary)
        if match:
            genre = match.group(1).strip().capitalize()
            summary = summary[match.end():]
        summary = truncate(summary)
        if summary.lower() == title.lower():
            summary = ""
        tags = sorted(set(tags_for(title, summary)) | set(source.get("tags", [])))
        if required and required not in tags:
            continue
        items.append(
            {
                "id": hashlib.sha1(normalise_link(link).encode()).hexdigest()[:12],
                "title": title,
                "link": link,
                "summary": summary,
                "genre": genre,
                "published": datetime.fromtimestamp(published, timezone.utc).isoformat(timespec="seconds"),
                "ts": int(published),
                "source": source["id"],
                "category": source["category"],
                "tags": tags,
                "image": feed_image(entry),
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


def add_images(items: list[dict], cache_dir: Path | None) -> None:
    """Hakee jokaiselle jutulle jakokuvan (og:image). Tulokset säilyvät välimuistissa ajojen välillä."""
    cache: dict[str, str | None] = {}
    cache_file = cache_dir / "kuvat.json" if cache_dir else None
    if cache_file and cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}

    todo = [it for it in items if it["link"] not in cache][:IMAGE_FETCH_LIMIT]

    def find(item: dict) -> tuple[str, str | None]:
        try:
            page = fetch(item["link"], timeout=12, limit=200_000).decode("utf-8", "ignore")
            return item["link"], og_image(page)
        except Exception:
            return item["link"], None

    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for link, image in pool.map(find, todo):
            cache[link] = image
    found = 0
    for item in items:
        better = cache.get(item["link"])
        if better:
            item["image"] = better
            found += 1
    print(f"Kuvat: {found}/{len(items)} jutulla jakokuva ({len(todo)} haettu nyt).")

    if cache_file:
        live = {it["link"] for it in items}
        cache = {k: v for k, v in cache.items() if k in live}
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def norm_title(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[”“„\"«»’'`´]", "", text)
    return re.sub(r"\s+", " ", text).strip(" .:–-")


def site_links(site_url: str) -> dict[str, str]:
    """Ohjelman verkkosivun juttulinkit: normalisoitu linkkiteksti -> osoite. Ensin sivun HTML suoraan,
    jos siitä ei löydy linkkejä, sama sivu lukupalvelun kautta (tekstimuoto)."""
    links: dict[str, str] = {}
    try:
        page = fetch(site_url, timeout=15, limit=2_000_000).decode("utf-8", "ignore")
        for m in re.finditer(r'<a\b[^>]*?href="((?:https://www\.sverigesradio\.se)?/artikel/[^"#?]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
            text = norm_title(clean_text(m.group(2)))
            if text:
                links.setdefault(text, urllib.parse.urljoin("https://www.sverigesradio.se/", m.group(1)))
    except Exception:
        pass
    if not links:
        try:
            md = fetch("https://r.jina.ai/" + site_url, timeout=45).decode("utf-8", "ignore")
            for m in re.finditer(r"\[([^\]\n]{6,240})\]\((https://www\.sverigesradio\.se/artikel/[^)\s#?]+)\)", md):
                links.setdefault(norm_title(m.group(1)), m.group(2))
        except Exception:
            pass
    return links


def find_on_site(title: str, links: dict[str, str]) -> str | None:
    want = norm_title(title)
    if want in links:
        return links[want]
    # Linkki voi kattaa koko kortin (otsikko + ingressi): riittää, että se alkaa otsikolla.
    for text, url in links.items():
        if len(want) >= 12 and text.startswith(want):
            return url
    return None


def check_links(items: list[dict], sources: list[dict], cache_dir: Path | None, sites: dict[str, str] | None = None) -> list[dict]:
    """Tarkistaa Sveriges Radion juttujen linkit. Syötteen numerolinkki (sverigesradio.se/artikel/123) ei
    toimi kaikilla jutuilla (esim. Kulturnytt), vaikka juttu on verkossa toisella osoitteella. Silloin juttu
    etsitään ohjelman verkkosivulta otsikon perusteella. Jos sitä ei löydy, juttu jätetään pois.
    Toimiva linkki korvataan osoitteella, johon sivu ohjaa. Juttujen tunnisteet eivät muutu."""
    wanted = {s["id"] for s in sources if s.get("check_links")}
    links = sorted({it["link"] for it in items if it["source"] in wanted})
    if not links:
        return items
    cache: dict[str, str] = {}
    cache_file = cache_dir / "linkit.json" if cache_dir else None
    if cache_file and cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}

    def probe(url: str) -> tuple[str, str | None, bool]:
        """(linkki, lopullinen osoite tai None jos sivua ei ole, voiko tuloksen tallentaa)"""
        if url in cache:
            return url, cache[url], False
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                final = response.geturl()
            return url, final if final.startswith("https://") else url, True
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 410):
                return url, None, False  # tarkistetaan uudelleen seuraavalla ajolla
            return url, url, False
        except Exception:
            return url, url, False  # verkko-ongelma: juttu pidetään

    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe, links))
    final = {url: dest for url, dest, _ in results}
    for url, dest, cacheable in results:
        if cacheable and dest:
            cache[url] = dest
    dead = {url for url, dest in final.items() if dest is None}

    # Toimimattomat linkit: haetaan oikea osoite ohjelman verkkosivulta (yksi haku ohjelmaa kohden).
    found = 0
    by_site: dict[str, list[dict]] = collections.defaultdict(list)
    for item in items:
        if item["link"] in dead and (sites or {}).get(item["source"]):
            by_site[sites[item["source"]]].append(item)
    for site, site_items in by_site.items():
        on_site = site_links(site)
        for item in site_items:
            url = find_on_site(item["title"], on_site)
            if url:
                final[item["link"]] = url
                cache[item["link"]] = url
                dead.discard(item["link"])
                found += 1
    kept = []
    for item in items:
        if item["link"] in dead:
            continue
        if item["link"] in final:
            item["link"] = final[item["link"]]
        kept.append(item)
    print(f"Linkit: {len(links)} tarkistettu, {found} korjattu ohjelman sivulta, {len(dead)} jätetty pois (sivua ei ole).")
    if cache_file:
        cache = {k: v for k, v in cache.items() if k in final}
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return kept


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="sources.json", type=Path)
    parser.add_argument("--data", default="data", type=Path)
    parser.add_argument("--out", default="_site", type=Path)
    parser.add_argument("--cache", default=None, type=Path)
    parser.add_argument("--no-images", action="store_true")
    args = parser.parse_args()

    sources, reddit = load_config(args.sources)
    now = time.time()

    statuses: dict[str, dict] = {}
    all_items: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        for status, items in pool.map(lambda s: read_source(s, now), sources):
            statuses[status["id"]] = status
            all_items.extend(items)

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

    sites = {sid: st.get("site") for sid, st in statuses.items() if st.get("site")}
    items = check_links(items, sources, args.cache, sites)

    if not args.no_images:
        add_images(items, args.cache)

    zipf = ordbok_data.zipf_table(args.data)
    for item in items:
        item["level"] = difficulty(f"{item['title']}. {item['summary']}", zipf)

    args.out.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"),
        "sources": ordered_statuses,
        "reddit": reddit,
        "items": items,
    }
    (args.out / "feed.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"feed.json: {len(items)} juttua {sum(s['ok'] for s in ordered_statuses)}/{len(sources)} lähteestä.")

    dictionary = ordbok_data.load(args.data)
    (args.out / "ordbok.json").write_text(json.dumps(dictionary, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"ordbok.json: {len(dictionary['d'])} hakusanaa, {len(dictionary['f'])} taivutusmuotoa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
