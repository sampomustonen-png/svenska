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

    return {"d": entries, "f": forms, "p": prefer, "z": freq}


def zipf_table(data_dir: Path) -> dict[str, float]:
    table: dict[str, float] = {}
    with gzip.open(data_dir / "sv-frekvens.tsv.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            word, _, z = line.rstrip("\n").partition("\t")
            table[word] = int(z) / 10
    return table
