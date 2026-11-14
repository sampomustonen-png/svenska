"""Rakentaa sanakirjatiedostot data/sv-fi.json.gz (perusmuoto -> suomennokset) ja data/sv-former.tsv.gz
(taivutusmuoto -> perusmuoto). Lähteet: FreeDict/WikDict swe-fin ja fin-swe (TEI) sekä michmech/lemmatization-lists."""
import gzip, json, re, sys, collections
import xml.etree.ElementTree as ET
src, lemfile, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
NS = {"t": "http://www.tei-c.org/ns/1.0"}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

def entries(path):
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag.endswith("}entry") or el.tag == "entry":
            yield el
            el.clear()

def tag(el): return el.tag.split("}")[-1]

POS_MAP = {"n": "subst.", "noun": "subst.", "v": "verb", "verb": "verb", "adj": "adj.", "adv": "adv.",
           "prep": "prep.", "preposition": "prep.", "postposition": "postp.", "pron": "pron.", "pronoun": "pron.",
           "conjunction": "konj.", "conj": "konj.", "num": "räkn.", "interj": "interj.", "interjection": "interj.",
           "proverb": "ordspråk"}
# Kielioppitermit, joita WikDict joskus antaa käännöksinä.
NOISE = {"allativ", "illativ", "inessiv", "elativ", "adessiv", "ablativ", "genitiv", "partitiv", "essiv",
         "translativ", "abessiv", "komitativ", "instruktiv", "nominativ", "ackusativ"}

def read(path, want_lang):
    out = collections.OrderedDict()
    for e in entries(path):
        orth = None; pos = None; senses = []
        for child in e:
            t = tag(child)
            if t == "form" and orth is None:
                for o in child.iter():
                    if tag(o) == "orth" and o.text: orth = o.text.strip(); break
            elif t == "gramGrp":
                for p in child.iter():
                    if tag(p) == "pos" and p.text: pos = p.text.strip()
            elif t == "sense":
                trans = []
                for c in child.iter():
                    if tag(c) == "cit" and c.get("type") == "trans" and c.get(XML_LANG, want_lang) == want_lang:
                        for q in c:
                            if tag(q) == "quote" and q.text and q.text.strip() and q.text.strip().lower() not in NOISE:
                                trans.append(q.text.strip())
                if trans: senses.append(trans)
        if orth and senses and not orth.startswith("-") and not orth.endswith("-"):
            out.setdefault(orth, {"pos": pos, "senses": []})["senses"].extend(senses)
    return out

swe = read(f"{src}/swe-fin/swe-fin.tei", "fi")
fin = read(f"{src}/fin-swe/fin-swe.tei", "sv")
print("swe-fin", len(swe), "fin-swe", len(fin))

d = {}
for w, info in swe.items():
    senses = []
    for s in info["senses"]:
        s = list(dict.fromkeys(s))[:4]
        if s not in senses: senses.append(s)
    d[w] = {"p": POS_MAP.get(info["pos"] or "", info["pos"] or ""), "s": senses[:4]}
# Invert fin-swe: Finnish headword becomes a translation of each Swedish quote.
inv = collections.defaultdict(list)
for fw, info in fin.items():
    for s in info["senses"]:
        for sw in s:
            if fw not in inv[sw]: inv[sw].append(fw)
added = extended = 0
for sw, fws in inv.items():
    if sw in d:
        have = {x for s in d[sw]["s"] for x in s}
        extra = [f for f in fws if f not in have][:3]
        if extra and len(d[sw]["s"]) < 4:
            d[sw]["s"].append(extra); extended += 1
    else:
        d[sw] = {"p": "", "s": [fws[:5]]}; added += 1
print("dict entries", len(d), "added from fin-swe", added, "extended", extended)

# lowercase index (keep original casing for display)
lower = {}
for w in d:
    lower.setdefault(w.lower(), w)

forms = collections.defaultdict(list)
with open(lemfile, encoding="utf-8-sig") as fh:
    for line in fh:
        parts = line.rstrip("\r\n").split("\t")
        if len(parts) != 2: continue
        lemma, form = parts[0].strip(), parts[1].strip().lower()
        if ":" in form or not form: continue
        key = lower.get(lemma.lower())
        if key and form != key.lower() and key not in forms[form]:
            forms[form].append(key)
print("forms mapped", len(forms))

with gzip.open(f"{outdir}/sv-fi.json.gz", "wt", encoding="utf-8", compresslevel=9) as fh:
    json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
with gzip.open(f"{outdir}/sv-former.tsv.gz", "wt", encoding="utf-8", compresslevel=9) as fh:
    for form in sorted(forms):
        fh.write(form + "\t" + "|".join(forms[form][:3]) + "\n")
