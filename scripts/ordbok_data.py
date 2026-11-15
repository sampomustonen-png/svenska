"""Kokoaa selaimen sanakirjatiedoston (ordbok.json) kansion data/ tiedostoista.

data/egna-ord.json sisältää omat korjaukset. Muoto:
    {
      "ord":    {"bana": {"p": "subst.", "s": [[["rata", "reitti"], "väg, spår"]], "ersätt": false}},
      "former": {"bor": "bo", "satt": "sitta|sätta"}
    }
"ord": omat merkitykset lisätään ensimmäisiksi; jos "ersätt" on true, sanakirjan merkitykset jätetään pois.
"former": taivutusmuoto -> perusmuodot, joita käytetään ensisijaisesti.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

FREQ_LIMIT = 50000  # selaimeen riittää näin monen yleisimmän sanan yleisyys


def load(data_dir: Path) -> dict:
    with gzip.open(data_dir / "sv-fi.json.gz", "rt", encoding="utf-8") as fh:
        entries: dict = json.load(fh)

    # Perussanasto (grundord.txt): käsin tarkistetut merkitykset yleisimmille sanoille.
    for word, entry in load_grundord(data_dir / "grundord.txt").items():
        entries[word] = entry

    prefer: dict[str, str] = {}
    own_path = data_dir / "egna-ord.json"
    if own_path.exists():
        own = json.loads(own_path.read_text(encoding="utf-8"))
        for word, fix in own.get("ord", {}).items():
            if not isinstance(fix, dict):
                continue
            senses = [[list(s[0]), s[1] if len(s) > 1 else ""] for s in fix.get("s", []) if s and s[0]]
            base = entries.get(word, {"p": "", "s": []})
            kept = [] if fix.get("ersätt") else [s for s in base["s"] if s[0] not in [x[0] for x in senses]]
            entries[word] = {"p": fix.get("p", base.get("p", "")), "s": (senses + kept)[:4]}
        prefer = {form.lower(): lemmas for form, lemmas in own.get("former", {}).items()}

    forms: dict[str, str] = {}
    with gzip.open(data_dir / "sv-former.tsv.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            form, _, lemmas = line.rstrip("\n").partition("\t")
            forms[form] = lemmas

    freq: dict[str, int] = {}
    with gzip.open(data_dir / "sv-frekvens.tsv.gz", "rt", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i >= FREQ_LIMIT:
                break
            word, _, z = line.rstrip("\n").partition("\t")
            freq[word] = int(z)

    return {"d": entries, "f": forms, "p": prefer, "z": freq, "u": phrases(entries, data_dir / "uttryck.txt")}


# Sanakirjan monisanaisista hakusanoista otetaan mukaan vain ne, joissa on jokin näistä sanoista
# (partikkeliverbit ja vakiintuneet ilmaukset, ei esim. lintulajeja).
FUNCTION_WORDS = {
    "upp", "ut", "in", "ner", "ned", "av", "på", "till", "om", "med", "för", "i", "över", "under", "bort",
    "fram", "tillbaka", "ihop", "igen", "efter", "åt", "mot", "emot", "vid", "från", "sig", "som", "och",
    "när", "att", "så", "än", "inte", "helst", "kvar", "undan", "igenom", "förbi", "runt", "omkring",
}


def phrases(entries: dict, path: Path) -> list:
    found: dict[str, list] = {}
    for key, e in entries.items():
        toks = key.split(" ")
        if (2 <= len(toks) <= 4 and key == key.lower() and not key.endswith((".", "!", "?"))
                and any(t in FUNCTION_WORDS for t in toks) and e.get("s")):
            found[key] = e["s"][:2]
    for key, senses in load_lines(path, with_pos=False).items():
        found[key.lower()] = senses
    out = []
    for key, senses in found.items():
        first = entries.get(key.split(" ")[0], {})
        out.append([key, senses, 1 if "verb" in first.get("p", "") else 0])
    return out


def load_grundord(path: Path) -> dict:
    return {w: {"p": pos, "s": s} for w, (pos, s) in load_lines(path, with_pos=True).items()}


def load_lines(path: Path, with_pos: bool) -> dict:
    """Lukee rivit muotoa  sana|sanaluokka|suomennos, suomennos = esimerkki; seuraava merkitys
    (tai ilman sanaluokkaa: ilmaus|merkitykset)."""
    out: dict = {}
    if not path.exists():
        return out
    want = 3 if with_pos else 2
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != want or not parts[0]:
            raise ValueError(f"{path.name} rivi {n}: väärä muoto ({want} osaa |-merkeillä erotettuna)")
        senses = []
        for chunk in parts[-1].split(";"):
            fi, _, note = chunk.partition(" = ")
            words = [w.strip() for w in fi.split(",") if w.strip()]
            if words:
                senses.append([words, note.strip()])
        if not senses:
            raise ValueError(f"{path.name} rivi {n}: ei suomennoksia")
        out[parts[0]] = (parts[1], senses[:4]) if with_pos else senses[:4]
    return out


def zipf_table(data_dir: Path) -> dict[str, float]:
    table: dict[str, float] = {}
    with gzip.open(data_dir / "sv-frekvens.tsv.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            word, _, z = line.rstrip("\n").partition("\t")
            table[word] = int(z) / 10
    return table
