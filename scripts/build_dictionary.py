#!/usr/bin/env python3
"""Rakentaa sanakirjan aineistot kansioon data/. Ajetaan vain kerran (tiedostot ovat jo repossa).

Lähteet:
  - FreeDict/WikDict swe-fin ja fin-swe (TEI), perustuu Wikisanakirjaan, CC BY-SA 3.0
  - michmech/lemmatization-lists, lemmatization-sv.txt (ODbL)
  - spaCy lookups data, sv_lemma_lookup.json.gz (MIT)
  - wordfreq (sanataajuudet, Apache 2.0 / CC BY-SA 4.0)

Tulosteet:
  data/sv-fi.json.gz      perusmuoto -> {"p": sanaluokka, "s": [[[suomennokset], "ruotsinkielinen selitys"], ...]}
  data/sv-former.tsv.gz   taivutusmuoto <TAB> perusmuoto|perusmuoto
  data/sv-frekvens.tsv.gz sana <TAB> yleisyys (zipf * 10)

Käyttö:
  python scripts/build_dictionary.py TEI_KANSIO lemmatization-sv.txt sv_lemma_lookup.json.gz data/
"""
import collections
import gzip
import json
import re
import sys
import xml.etree.ElementTree as ET

from wordfreq import top_n_list, zipf_frequency

tei_dir, lemma_list, spacy_lookup, outdir = sys.argv[1:5]
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

POS_MAP = {
    "n": "subst.", "noun": "subst.", "v": "verb", "verb": "verb", "adj": "adj.", "adv": "adv.",
    "prep": "prep.", "preposition": "prep.", "postposition": "postp.", "pron": "pron.", "pronoun": "pron.",
    "conjunction": "konj.", "conj": "konj.", "num": "räkn.", "interj": "interj.", "interjection": "interj.",
    "proverb": "ordspråk",
}
# Kielioppitermit, joita WikDict joskus antaa käännöksinä.
NOISE = {"allativ", "illativ", "inessiv", "elativ", "adessiv", "ablativ", "genitiv", "partitiv", "essiv",
         "translativ", "abessiv", "komitativ", "instruktiv", "nominativ", "ackusativ"}


def tag(el):
    return el.tag.split("}")[-1]


def entries(path):
    for _, el in ET.iterparse(path, events=("end",)):
        if tag(el) == "entry":
            yield el
            el.clear()


def read(path, want_lang):
    """Palauttaa {hakusana: {"pos": .., "senses": [(käännökset, selitys)]}}."""
    out = collections.OrderedDict()
    for e in entries(path):
        orth, pos, senses = None, None, []
        for child in e:
            t = tag(child)
            if t == "form" and orth is None:
                for o in child.iter():
                    if tag(o) == "orth" and o.text:
                        orth = o.text.strip()
                        break
            elif t == "gramGrp":
                for p in child.iter():
                    if tag(p) == "pos" and p.text:
                        pos = p.text.strip()
            elif t == "sense":
                trans, defs = [], []
                for c in child.iter():
                    if tag(c) == "cit" and c.get("type") == "trans" and c.get(XML_LANG, want_lang) == want_lang:
                        for q in c:
                            text = (q.text or "").strip()
                            if tag(q) == "quote" and text and text.lower() not in NOISE:
                                trans.append(text)
                    elif tag(c) == "def" and c.text and c.text.strip():
                        defs.append(c.text.strip())
                if trans:
                    senses.append((trans, "; ".join(defs[:2])[:90]))
        if orth and senses and not orth.startswith("-") and not orth.endswith("-"):
            out.setdefault(orth, {"pos": pos, "senses": []})["senses"].extend(senses)
    return out


def zfi(word):
    # Monisanaisissa ilmauksissa käytetään harvinaisinta sanaa.
    parts = [p for p in re.split(r"[\s/]+", word.strip("-")) if p]
    if not parts:
        return 0.0
    return min(zipf_frequency(p, "fi") for p in parts)


def rank(senses):
    """Järjestää käännökset yleisyyden mukaan ja nostaa selvästi yleisimmän merkityksen ensimmäiseksi."""
    cleaned = []
    for trans, definition in senses:
        uniq = list(dict.fromkeys(trans))
        uniq.sort(key=lambda w: -zfi(w))
        item = (uniq[:4], definition)
        if all(item[0] != s[0] for s in cleaned):
            cleaned.append(item)
    if len(cleaned) > 1:
        scores = [max(zfi(w) for w in s[0]) for s in cleaned]
        best = max(range(len(cleaned)), key=lambda i: scores[i])
        if best != 0 and scores[best] >= scores[0] + 1.0:
            cleaned.insert(0, cleaned.pop(best))
    return cleaned[:4]


swe = read(f"{tei_dir}/swe-fin/swe-fin.tei", "fi")
fin = read(f"{tei_dir}/fin-swe/fin-swe.tei", "sv")
print("swe-fin", len(swe), "fin-swe", len(fin))

d = {}
for word, info in swe.items():
    d[word] = {"p": POS_MAP.get(info["pos"] or "", info["pos"] or ""), "s": list(info["senses"])}

# Käänteinen suomi-ruotsi: suomen hakusana on ruotsin sanan käännös.
inverse = collections.defaultdict(list)
for fword, info in fin.items():
    if re.fullmatch(r"-?\w{1,3}-?", fword) and zfi(fword) < 4.0:
        continue  # päätteitä ja muuta kohinaa
    for trans, _ in info["senses"]:
        for sword in trans:
            if fword not in inverse[sword]:
                inverse[sword].append(fword)
added = extended = 0
for sword, fwords in inverse.items():
    # Olemassa olevia hakusanoja ei täydennetä: käänteiset käännökset toivat niihin lähinnä kohinaa
    # (esim. också -> voi, tid -> aikana).
    if sword not in d:
        d[sword] = {"p": "", "s": [(fwords[:5], "")]}
        added += 1

for word in d:
    d[word]["s"] = rank(d[word]["s"])
print("hakusanoja", len(d), "lisätty fin-swe:stä", added)

lower = {}
for word in d:
    lower.setdefault(word.lower(), word)

forms = collections.defaultdict(list)


def add_form(form, lemma):
    form = form.strip().lower()
    key = lower.get(lemma.strip().lower())
    if not key or not form or ":" in form or form == key.lower():
        return
    if key not in forms[form]:
        forms[form].append(key)


with open(lemma_list, encoding="utf-8-sig") as fh:
    for line in fh:
        parts = line.rstrip("\r\n").split("\t")
        if len(parts) == 2:
            add_form(parts[1], parts[0])
with gzip.open(spacy_lookup, "rt", encoding="utf-8") as fh:
    for form, lemma in json.load(fh).items():
        add_form(form, lemma)
print("taivutusmuotoja", len(forms))

freq = {}
for word in top_n_list("sv", 80000, wordlist="large"):
    z = zipf_frequency(word, "sv")
    if z < 1.8:
        break
    freq[word] = int(round(z * 10))
print("taajuuksia", len(freq))

with gzip.open(f"{outdir}/sv-fi.json.gz", "wt", encoding="utf-8", compresslevel=9) as fh:
    json.dump({w: {"p": e["p"], "s": [[t, dfn] for t, dfn in e["s"]]} for w, e in d.items()},
              fh, ensure_ascii=False, separators=(",", ":"))
with gzip.open(f"{outdir}/sv-former.tsv.gz", "wt", encoding="utf-8", compresslevel=9) as fh:
    for form in sorted(forms):
        fh.write(form + "\t" + "|".join(forms[form][:3]) + "\n")
with gzip.open(f"{outdir}/sv-frekvens.tsv.gz", "wt", encoding="utf-8", compresslevel=9) as fh:
    for word, z in freq.items():
        fh.write(f"{word}\t{z}\n")
print("valmis")
