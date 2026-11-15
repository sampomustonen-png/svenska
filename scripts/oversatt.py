#!/usr/bin/env python3
"""Konekääntää juttujen virkkeet ja sanakirjasta puuttuvat sanat ruotsista suomeksi.

Käyttää Helsingin yliopiston avointa OPUS-MT-mallia (Helsinki-NLP/opus-mt-sv-fi, Apache 2.0).
Käännökset tallennetaan välimuistiin (.cache/mt.json), joten kukin virke käännetään vain kerran.
Jos malli ei jostain syystä toimi, sivu käyttää aiempia käännöksiä ja tarvittaessa MyMemory-palvelua.

Käyttö:
    python scripts/oversatt.py --site _site --cache .cache [--missing .cache/saknade.txt]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

MODEL = "Helsinki-NLP/opus-mt-sv-fi"
SENTENCE_RE = re.compile(r"[^.!?…]+(?:[.!?…]+|$)")  # sama kuin selaimessa
MAX_PER_RUN = 1500
TIME_BUDGET = 15 * 60  # sekuntia


def sentences(text: str) -> list[str]:
    out = []
    for match in SENTENCE_RE.finditer(text or ""):
        s = match.group(0).strip()
        if len(re.findall(r"\w+", s)) >= 2:
            out.append(s)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="_site", type=Path)
    parser.add_argument("--cache", default=".cache", type=Path)
    parser.add_argument("--missing", default=None, type=Path)
    parser.add_argument("--mock", action="store_true", help="testikäyttö ilman mallia")
    args = parser.parse_args()

    feed = json.loads((args.site / "feed.json").read_text(encoding="utf-8"))
    wanted_s: list[str] = []
    for item in feed["items"]:
        for text in (item["title"], item.get("summary") or ""):
            for s in sentences(text):
                if s not in wanted_s:
                    wanted_s.append(s)
    wanted_w: list[str] = []
    if args.missing and args.missing.exists():
        wanted_w = [w.strip() for w in args.missing.read_text(encoding="utf-8").splitlines() if w.strip()]

    cache_file = args.cache / "mt.json"
    cache = {"s": {}, "w": {}}
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except ValueError:
            pass

    todo_s = [s for s in wanted_s if s not in cache["s"]][:MAX_PER_RUN]
    todo_w = [w for w in wanted_w if w not in cache["w"]][:MAX_PER_RUN]
    print(f"Käännettävää: {len(todo_s)} virkettä, {len(todo_w)} sanaa (välimuistissa {len(cache['s'])} + {len(cache['w'])}).")

    if todo_s or todo_w:
        try:
            translate = load_model(args.mock)
            start = time.time()
            for kind, todo in (("w", todo_w), ("s", todo_s)):
                for i in range(0, len(todo), 16):
                    if time.time() - start > TIME_BUDGET:
                        print("Aikaraja täyttyi, loput käännetään seuraavalla ajolla.")
                        break
                    batch = todo[i:i + 16]
                    for src, out in zip(batch, translate(batch)):
                        cache[kind][src] = out
        except Exception as exc:  # malli puuttuu, verkkovirhe tms.
            print(f"Konekäännös ei onnistunut ({type(exc).__name__}: {exc}). Käytetään aiempia käännöksiä.")

    # Välimuistiin jää vain nykyisten juttujen tarvitsema (sanat säilyvät, niitä on vähän).
    keep_s = set(wanted_s)
    cache["s"] = {k: v for k, v in cache["s"].items() if k in keep_s}
    args.cache.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    output = {
        "model": MODEL,
        "s": cache["s"],
        "w": {w: cache["w"][w] for w in wanted_w if w in cache["w"]},
    }
    (args.site / "oversattning.json").write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"oversattning.json: {len(output['s'])} virkettä, {len(output['w'])} sanaa.")
    return 0


def load_model(mock: bool):
    if mock:
        return lambda batch: [f"[fi] {x}" for x in batch]
    from transformers import MarianMTModel, MarianTokenizer  # noqa: WPS433 (raskas tuonti vain tarvittaessa)

    tokenizer = MarianTokenizer.from_pretrained(MODEL)
    model = MarianMTModel.from_pretrained(MODEL)
    model.eval()

    def translate(batch: list[str]) -> list[str]:
        import torch

        with torch.no_grad():
            encoded = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=256)
            generated = model.generate(**encoded, num_beams=3, max_new_tokens=256)
        return [t.strip() for t in tokenizer.batch_decode(generated, skip_special_tokens=True)]

    return translate


if __name__ == "__main__":
    sys.exit(main())
