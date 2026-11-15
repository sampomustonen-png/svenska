/* Ruotsi–suomi-sanahaku. Toimii selaimessa (window.Ordbok) ja Nodessa (testit).
 *
 * Aineisto (ordbok.json) syntyy GitHub Actionsissa tiedostoista data/*.gz:
 *   d: perusmuoto -> { p: sanaluokka, s: [[[suomennokset], "ruotsinkielinen selitys"], ...] }
 *   f: taivutusmuoto -> "perusmuoto|perusmuoto"
 *   p: omat korjaukset: taivutusmuoto -> ensisijaiset perusmuodot
 *   z: sana -> yleisyys (zipf * 10)
 *   u: sanaliitot [teksti, merkitykset, alkaako verbillä 0/1]
 */
(function (root) {
  "use strict";

  const WORD_RE = /\p{L}+(?:[-’']\p{L}+)*/gu;

  // Yleisiä päätteitä, joita kokeillaan, jos taivutusmuotoa ei löydy listasta.
  const SUFFIXES = [
    "arnas", "ernas", "ornas", "arna", "erna", "orna", "andet", "andes", "ande", "ende",
    "ades", "ade", "ats", "at", "ars", "ers", "ors", "ar", "er", "or", "ens", "ets",
    "en", "et", "na", "ns", "ts", "es", "as", "s", "n", "t", "a", "e",
  ];

  // Refleksiivipronominit: ilmauksen "sig" vastaa myös näitä.
  const REFLEXIVE = new Set(["sig", "mig", "dig", "oss", "er"]);
  // Lyhyet sanat, jotka saavat jäädä verbin ja partikkelin väliin (tog inte upp, tar han över).
  const GAP = new Set([
    "inte", "aldrig", "också", "även", "ju", "nog", "redan", "då", "nu", "sedan", "han", "hon", "de", "dom",
    "vi", "jag", "du", "ni", "man", "den", "det", "alltså", "dock", "snart", "ofta", "gärna", "helt", "själv",
    "heller", "bara", "just", "ändå", "fortfarande", "ännu", "inte", "kanske", "verkligen", "faktiskt",
  ]);

  class Ordbok {
    constructor(data) {
      this.d = data.d || {};
      this.f = data.f || {};
      this.p = data.p || {};
      this.z = data.z || {};
      this.phrases = [];
      this.byToken = new Map();
      for (const [text, s, verb] of data.u || []) {
        const toks = text.toLowerCase().split(" ");
        if (toks.length < 2) continue;
        const phrase = { text, toks, s, verb: !!verb };
        this.phrases.push(phrase);
        for (const t of new Set(toks)) {
          if (!this.byToken.has(t)) this.byToken.set(t, []);
          this.byToken.get(t).push(phrase);
        }
      }
      this.lower = new Map();
      for (const key of Object.keys(this.d)) {
        const low = key.toLowerCase();
        // Pienikirjaiminen hakusana voittaa erisnimen (per vs. Per).
        if (!this.lower.has(low) || key === low) this.lower.set(low, key);
      }
    }

    entry(key) {
      const e = this.d[key];
      return { l: key, p: e.p || "", s: e.s || [] };
    }

    zipf(word) {
      const z = this.z[word.toLowerCase()];
      return typeof z === "number" ? z / 10 : null;
    }

    /** Sanan mahdolliset perusmuodot sanakirjassa. */
    lemmas(w, guess = true) {
      const found = [];
      const preferred = this.p[w];
      if (preferred) {
        for (const l of preferred.split("|")) {
          const key = this.d[l] ? l : this.lower.get(l);
          if (key && !found.includes(key)) found.push(key);
        }
        if (found.length) return found;
      }
      const direct = this.lower.get(w);
      if (direct) found.push(direct);
      const forms = this.f[w];
      if (forms) {
        for (const l of forms.split("|")) if (this.d[l] && !found.includes(l)) found.push(l);
      }
      if (found.length || !guess) return found;
      for (const suffix of SUFFIXES) {
        if (w.endsWith(suffix) && w.length - suffix.length >= 3) {
          const base = w.slice(0, -suffix.length);
          for (const cand of [base, base + "a", base + "e"]) {
            const hits = this.lemmas(cand, false);
            if (hits.length) return hits.slice(0, 1);
          }
        }
      }
      return [];
    }

    /** Yhdyssanan alkuosa voi olla taivutettu (kvinno-, gatu-) tai siinä voi olla s-liitos. */
    leftLemmas(left) {
      const tries = [left];
      if (left.endsWith("s") && left.length > 3) tries.push(left.slice(0, -1));
      if (/[ou]$/.test(left)) tries.push(left.slice(0, -1) + "a");
      if (left.endsWith("e") && left.length > 3) tries.push(left.slice(0, -1), left.slice(0, -1) + "a");
      for (const t of tries) {
        const hits = this.lemmas(t, false);
        if (hits.length) return hits;
      }
      return [];
    }

    /** Jakaa yhdyssanan osiin (enintään kolme osaa). */
    split(w, depth = 0) {
      let best = null;
      for (let i = 3; i <= w.length - 3; i++) {
        const left = w.slice(0, i);
        const right = w.slice(i);
        const leftKeys = this.leftLemmas(left);
        if (!leftKeys.length) continue;
        let rightParts = null;
        const rightKeys = this.lemmas(right);
        if (rightKeys.length) rightParts = [rightKeys[0]];
        else if (depth === 0) rightParts = this.split(right, 1);
        if (!rightParts) continue;
        // Suositaan tasaisia jakoja ja vähiä osia.
        const score = Math.min(left.length, right.length) - (rightParts.length - 1) * 3;
        if (!best || score > best.score) best = { score, parts: [leftKeys[0], ...rightParts] };
      }
      return best ? best.parts : null;
    }

    /** Vastaako tekstin sana ilmauksen sanaa (perusmuodon kautta)? */
    tokenMatches(word, tok) {
      if (word === tok) return true;
      if (tok === "sig") return REFLEXIVE.has(word);
      return this.lemmas(word, false).some((l) => l.toLowerCase() === tok);
    }

    /**
     * Sanaliitot, joihin kohdan i sana kuuluu. words: virkkeen sanat pienillä kirjaimilla.
     * Palauttaa [{ text, s, from, to }], pisin ensin.
     */
    phrasesAt(words, i) {
      const word = words[i];
      if (!word) return [];
      const cands = new Set();
      for (const key of [word, ...this.lemmas(word, false).map((l) => l.toLowerCase())]) {
        for (const p of this.byToken.get(key) || []) cands.add(p);
      }
      if (REFLEXIVE.has(word)) for (const p of this.byToken.get("sig") || []) cands.add(p);
      const out = [];
      for (const p of cands) {
        const n = p.toks.length;
        for (let start = Math.max(0, i - n - 2); start <= i; start++) {
          const hit = this.align(p, words, start);
          if (hit && hit.includes(i)) {
            out.push({ text: p.text, s: p.s, from: hit[0], to: hit[hit.length - 1] });
            break;
          }
        }
      }
      out.sort((a, b) => b.text.split(" ").length - a.text.split(" ").length || a.from - b.from);
      // Lyhyempi ilmaus, joka sisältyy pidempään (ta upp ⊂ ta upp frågan), jätetään pois.
      return out.filter((x, k) => !out.slice(0, k).some((y) => y.from <= x.from && y.to >= x.to)).slice(0, 2);
    }

    align(p, words, start) {
      if (!this.tokenMatches(words[start] || "", p.toks[0])) return null;
      const covered = [start];
      let j = start + 1;
      for (let k = 1; k < p.toks.length; k++) {
        if (k === 1 && p.verb) {
          let skipped = 0;
          while (skipped < 2 && words[j] && GAP.has(words[j]) && !this.tokenMatches(words[j], p.toks[1])) {
            j++;
            skipped++;
          }
        }
        if (!words[j] || !this.tokenMatches(words[j], p.toks[k])) return null;
        covered.push(j);
        j++;
      }
      return covered;
    }

    /**
     * Hakee sanan. Palauttaa
     *   { type: "word", entries: [...] }       sana tai sen taivutusmuoto löytyi
     *   { type: "compound", parts: [...] }     yhdyssana, osat löytyivät
     *   null                                   ei löytynyt
     */
    lookup(word) {
      const w = word.toLowerCase().replace(/’/g, "'");
      const keys = this.lemmas(w);
      if (keys.length) return { type: "word", entries: keys.slice(0, 2).map((k) => this.entry(k)) };
      if (w.includes("-")) {
        const tail = this.lookup(w.split("-").pop());
        if (tail) return tail;
      }
      const parts = this.split(w);
      if (parts) return { type: "compound", parts: parts.map((k) => this.entry(k)) };
      return null;
    }
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { Ordbok, WORD_RE };
  else root.Ordbok = Ordbok;
})(typeof self !== "undefined" ? self : this);
