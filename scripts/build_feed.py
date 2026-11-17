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
import difflib
import hashlib
import html
import json
import os
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
MAX_ITEMS_TOTAL = 500
SUMMARY_CHARS = 360
PAGE_FETCH_LIMIT = 200  # kuinka monen uuden jutun sivu (kuva ja maksumuuri) haetaan yhdellä ajolla

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

def fetch(url: str, timeout: int = 25, limit: int | None = None, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.5",
            **(headers or {}),
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


# Maksumuuri: uutissivut kertovat hakukoneille sivun rakenteisessa datassa (schema.org, JSON-LD),
# onko juttu kaikkien luettavissa ("isAccessibleForFree": false). Tieto luetaan samasta sivusta kuin
# jakokuva. Vain sivun omat JSON-LD-lohkot tutkitaan, ettei muiden juttujen esittelyt sekoita tulosta.
LDJSON_RE = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)
NOT_FREE_RE = re.compile(r'"isAccessibleForFree"\s*:\s*"?(?:false|no)\b', re.I)
LOCKED_META_RE = re.compile(
    r"<meta[^>]+(?:property|name)=[\"']article:content_tier[\"'][^>]+content=[\"']locked"
    r"|<meta[^>]+content=[\"']locked[\"'][^>]+(?:property|name)=[\"']article:content_tier",
    re.I,
)


def is_paywalled(page: str) -> bool:
    if any(NOT_FREE_RE.search(block) for block in LDJSON_RE.findall(page)):
        return True
    return bool(LOCKED_META_RE.search(page))


def add_page_info(items: list[dict], cache_dir: Path | None) -> None:
    """Hakee jokaisen jutun sivulta jakokuvan (og:image) ja tiedon, onko juttu maksumuurin takana.
    Tulokset säilyvät välimuistissa ajojen välillä. Maksulliset jutut saavat merkinnän "paywall": true,
    jolloin sovellus näyttää niistä otsikon ja ingressin eikä yritä hakea koko tekstiä."""
    cache: dict[str, dict] = {}
    cache_file = cache_dir / "sivut.json" if cache_dir else None
    if cache_file and cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}

    todo = [it for it in items if it["link"] not in cache][:PAGE_FETCH_LIMIT]

    def find(item: dict) -> tuple[str, dict]:
        try:
            page = fetch(item["link"], timeout=12, limit=800_000).decode("utf-8", "ignore")
            return item["link"], {"i": og_image(page), "p": 1 if is_paywalled(page) else 0}
        except Exception:
            return item["link"], {"i": None, "p": 0}

    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for link, info in pool.map(find, todo):
            cache[link] = info
    found = locked = 0
    for item in items:
        info = cache.get(item["link"]) or {}
        if info.get("i"):
            item["image"] = info["i"]
            found += 1
        if info.get("p"):
            item["paywall"] = True
            locked += 1
    print(f"Sivut: {found}/{len(items)} jutulla jakokuva, {locked} maksumuurin takana ({len(todo)} haettu nyt).")

    if cache_file:
        live = {it["link"] for it in items}
        cache = {k: v for k, v in cache.items() if k in live}
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def norm_title(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[”“„\"«»’'`´]", "", text)
    text = re.sub(r"[–—‒−]", "-", text)
    return re.sub(r"\s+", " ", text).strip(" .:-")


SR_BASE = "https://www.sverigesradio.se/"
SR_ARTICLE_RE = r"(?:https?://(?:www\.)?sverigesradio\.se)?/artikel/[^\"'#?\s<>)\\]+"
# Sveriges Radion "sivua ei löydy" -sivu. Se voi tulla myös tilakoodilla 200.
SR_NOT_FOUND_RE = re.compile(r"<title[^>]*>[^<]*kunde inte hittas|<h1[^>]*>[^<]*kunde inte hittas", re.I)
JINA = "https://r.jina.ai/"


def _sr_url(path: str) -> str:
    return urllib.parse.urljoin(SR_BASE, path.replace("\\/", "/"))


def _html_links(page: str) -> dict[str, str]:
    """Juttulinkit HTML:stä: <a href="/artikel/...">otsikko</a>, ja sivun upotetusta datasta
    ("title":"...", "url":"/artikel/..."), jos linkit piirretään vasta selaimessa."""
    links: dict[str, str] = {}
    anchor = re.compile(r"<a\b([^>]*?)href=[\"'](" + SR_ARTICLE_RE + r")[\"']([^>]*)>(.*?)</a>", re.S | re.I)
    for m in anchor.finditer(page):
        text = norm_title(clean_text(m.group(4)))
        if not text:
            label = re.search(r"aria-label=[\"']([^\"']+)", m.group(1) + m.group(3))
            text = norm_title(html.unescape(label.group(1))) if label else ""
        if text:
            links.setdefault(text, _sr_url(m.group(2)))
    flat = page.replace('\\"', '"')
    pair = re.compile(
        r'"(?:title|headline|heading|name)"\s*:\s*"((?:[^"\\]|\\.){6,300})"[^{}\[\]]{0,600}?"(?:url|href|link|path|canonicalUrl)"\s*:\s*"(' + SR_ARTICLE_RE + r')"'
        r'|"(?:url|href|link|path|canonicalUrl)"\s*:\s*"(' + SR_ARTICLE_RE + r')"[^{}\[\]]{0,600}?"(?:title|headline|heading|name)"\s*:\s*"((?:[^"\\]|\\.){6,300})"'
    )
    for m in pair.finditer(flat):
        raw, path = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        try:
            title = json.loads('"' + raw + '"')
        except ValueError:
            title = raw
        text = norm_title(clean_text(title))
        if text:
            links.setdefault(text, _sr_url(path))
    return links


def _markdown_links(md: str) -> dict[str, str]:
    """Juttulinkit lukupalvelun tekstimuodosta: [otsikko](https://www.sverigesradio.se/artikel/...),
    myös kun linkin sisällä on kuva tai väliotsikko."""
    links: dict[str, str] = {}
    pattern = re.compile(r"\[((?:!\[[^\]]*\]\([^)]*\)|[^\[\]])*)\]\((" + SR_ARTICLE_RE + r")\)")
    for m in pattern.finditer(md):
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", m.group(1))
        text = re.sub(r"(^|\s)#{1,6}\s", " ", text)
        text = norm_title(re.sub(r"[*_]{1,3}", "", text))
        if len(text) >= 6:
            links.setdefault(text, _sr_url(m.group(2)))
    return links


def site_links(site_url: str) -> tuple[dict[str, str], str]:
    """Ohjelman verkkosivun juttulinkit: normalisoitu linkkiteksti -> osoite, ja millä tavalla ne saatiin.
    Ensin sivu suoraan, sitten lukupalvelun kautta HTML:nä (selaimessa piirretty sivu), lopuksi tekstinä."""
    attempts = [
        ("suora", lambda: _html_links(fetch(site_url, timeout=15, limit=3_000_000).decode("utf-8", "ignore"))),
        ("lukupalvelu-html", lambda: _html_links(fetch(JINA + site_url, timeout=45, headers={"X-Return-Format": "html"}).decode("utf-8", "ignore"))),
        ("lukupalvelu-teksti", lambda: _markdown_links(fetch(JINA + site_url, timeout=45, headers={"X-With-Links-Summary": "true"}).decode("utf-8", "ignore"))),
    ]
    tried = []
    for name, attempt in attempts:
        try:
            links = attempt()
        except urllib.error.HTTPError as exc:
            tried.append(f"{name}:{exc.code}")
            continue
        except Exception as exc:  # noqa: BLE001 - verkko-ongelma, kokeillaan seuraavaa
            tried.append(f"{name}:{type(exc).__name__}")
            continue
        if links:
            return links, name
        tried.append(f"{name}:0")
    return {}, ", ".join(tried)


def find_on_site(title: str, links: dict[str, str]) -> str | None:
    want = norm_title(title)
    if not want:
        return None
    if want in links:
        return links[want]
    # Linkki voi kattaa koko kortin (otsikko + ingressi): riittää, että se alkaa otsikolla.
    if len(want) >= 12:
        for text, url in links.items():
            if text.startswith(want):
                return url
    # Pienet erot (välimerkit, lyhenteet): lähes sama otsikko kelpaa.
    best, best_ratio = None, 0.0
    for text, url in links.items():
        ratio = difflib.SequenceMatcher(None, want, text[: len(want) + 8]).ratio()
        if ratio > best_ratio:
            best, best_ratio = url, ratio
    return best if best_ratio >= 0.9 and len(want) >= 12 else None


def check_links(items: list[dict], sources: list[dict], cache_dir: Path | None, sites: dict[str, str] | None = None) -> tuple[list[dict], dict]:
    """Korjaa Sveriges Radion juttujen linkit. Syötteen numerolinkki (sverigesradio.se/artikel/123) ei toimi
    kaikilla jutuilla (esim. Kulturnytt), vaikka juttu on verkossa toisella osoitteella. Siksi jokainen juttu
    etsitään ensin ohjelman verkkosivulta otsikon perusteella, ja sieltä löytyvä osoite on aina oikea.
    Muut linkit kokeillaan: jos sivua ei ole, juttu jätetään pois. Juttujen tunnisteet eivät muutu.
    Palauttaa jutut ja tilaston, joka tallennetaan feed.jsoniin (näkyy ilman kirjautumista)."""
    wanted = {s["id"] for s in sources if s.get("check_links")}
    sr_items = [it for it in items if it["source"] in wanted]
    stats: dict = {"tarkistettu": len(sr_items), "valimuistista": 0, "ohjelman_sivulta": 0, "poistettu": 0, "sivut": {}, "kokeilu": {}}
    if not sr_items:
        return items, stats
    cache: dict[str, str] = {}
    cache_file = cache_dir / "linkit2.json" if cache_dir else None
    if cache_file and cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}

    resolved: dict[str, str] = {}  # juttu-id -> oikea osoite
    for item in sr_items:
        if cache.get(item["link"], item["link"]) != item["link"]:
            resolved[item["id"]] = cache[item["link"]]
            stats["valimuistista"] += 1

    # 1) Ohjelman verkkosivu, yksi haku ohjelmaa kohden.
    by_source: dict[str, list[dict]] = collections.defaultdict(list)
    for item in sr_items:
        if item["id"] not in resolved and (sites or {}).get(item["source"]):
            by_source[item["source"]].append(item)
    def load_site(source_id: str) -> tuple[str, dict[str, str], str]:
        links, how = site_links(sites[source_id])
        return source_id, links, how
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        site_results = list(pool.map(load_site, by_source))
    for source_id, links, how in site_results:
        matched, unmatched = 0, []
        for item in by_source[source_id]:
            url = find_on_site(item["title"], links)
            if url:
                resolved[item["id"]] = url
                cache[item["link"]] = url
                matched += 1
            else:
                unmatched.append(item["title"])
        stats["ohjelman_sivulta"] += matched
        stats["sivut"][source_id] = {"linkkeja": len(links), "tapa": how, "loytyi": matched, "ei_loytynyt": unmatched[:4]}

    # 2) Loput kokeillaan suoraan.
    def probe(item: dict) -> tuple[dict, str, str | None]:
        """(juttu, tulos, lopullinen osoite tai None jos sivua ei ole)"""
        url = item["link"]
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                final = response.geturl()
                body = response.read(400_000).decode("utf-8", "ignore")
            if SR_NOT_FOUND_RE.search(body):
                return item, "ei-sivua-200", None
            if final.startswith("https://") and final != url:
                return item, "ohjaus", final
            return item, "ok", url
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 410):
                return item, str(exc.code), None
            return item, f"http-{exc.code}", url
        except Exception as exc:  # noqa: BLE001 - verkko-ongelma: juttu pidetään
            return item, type(exc).__name__, url

    rest = [it for it in sr_items if it["id"] not in resolved]
    dead: set[str] = set()
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        for item, outcome, dest in pool.map(probe, rest):
            per_source = stats["kokeilu"].setdefault(item["source"], {})
            per_source[outcome] = per_source.get(outcome, 0) + 1
            if dest is None:
                dead.add(item["id"])
            else:
                resolved[item["id"]] = dest
                if outcome == "ohjaus":
                    cache[item["link"]] = dest

    kept = []
    current = set()
    for item in items:
        if item["id"] in dead:
            continue
        if item["source"] in wanted:
            current.add(item["link"])
            item["link"] = resolved.get(item["id"], item["link"])
        kept.append(item)
    stats["poistettu"] = len(dead)
    summary = (f"Linkit: {len(sr_items)} tarkistettu, {stats['valimuistista']} välimuistista, "
               f"{stats['ohjelman_sivulta']} ohjelman sivulta, {len(dead)} jätetty pois (sivua ei ole).")
    print(summary)
    for source_id, info in stats["sivut"].items():
        print(f"  {source_id}: sivulla {info['linkkeja']} linkkiä ({info['tapa']}), löytyi {info['loytyi']}")
    print(f"  kokeilu: {json.dumps(stats['kokeilu'], ensure_ascii=False)}")
    if os.environ.get("GITHUB_ACTIONS"):
        # Huomautus näkyy Actions-ajon yhteenvedossa ilman kirjautumista.
        print(f"::notice title=Sveriges Radion linkit::{summary} Sivut: "
              + "; ".join(f"{k} {v['linkkeja']} ({v['tapa']})" for k, v in stats["sivut"].items()))
    if cache_file:
        cache = {k: v for k, v in cache.items() if k in current}
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return kept, stats


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
    items, link_stats = check_links(items, sources, args.cache, sites)

    if not args.no_images:
        add_page_info(items, args.cache)
        for status in ordered_statuses:
            status["paywalled"] = sum(1 for it in items if it["source"] == status["id"] and it.get("paywall"))

    zipf = ordbok_data.zipf_table(args.data)
    for item in items:
        item["level"] = difficulty(f"{item['title']}. {item['summary']}", zipf)

    args.out.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"),
        "sources": ordered_statuses,
        "reddit": reddit,
        "items": items,
        "linkcheck": link_stats,
    }
    (args.out / "feed.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"feed.json: {len(items)} juttua {sum(s['ok'] for s in ordered_statuses)}/{len(sources)} lähteestä.")

    dictionary = ordbok_data.load(args.data)
    (args.out / "ordbok.json").write_text(json.dumps(dictionary, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"ordbok.json: {len(dictionary['d'])} hakusanaa, {len(dictionary['f'])} taivutusmuotoa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
