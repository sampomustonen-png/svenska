#!/usr/bin/env node
/* Listaa juttujen sanat, joita sanakirja ei tunne. Tulos menee konekäännökselle (scripts/oversatt.py).
 * Käyttö: node scripts/saknade_ord.js _site > .cache/saknade.txt
 */
"use strict";
const fs = require("fs");
const path = require("path");
const { Ordbok, WORD_RE } = require(path.join(__dirname, "..", "ordbok.js"));

const site = process.argv[2] || "_site";
const feed = JSON.parse(fs.readFileSync(path.join(site, "feed.json"), "utf8"));
const ordbok = new Ordbok(JSON.parse(fs.readFileSync(path.join(site, "ordbok.json"), "utf8")));

const seen = new Map(); // pienellä kirjoitettu sana -> esiintyikö koskaan pienellä alkukirjaimella
for (const item of feed.items) {
  for (const text of [item.title, item.summary || ""]) {
    for (const m of text.normalize("NFC").matchAll(WORD_RE)) {
      const word = m[0];
      const low = word.toLowerCase();
      const lowerSeen = word === low;
      seen.set(low, (seen.get(low) || false) || lowerSeen);
    }
  }
}

const missing = [];
for (const [word, lowerSeen] of seen) {
  if (word.length < 3 || !lowerSeen) continue; // erisnimet (vain isolla) jätetään pois
  if (!ordbok.lookup(word)) missing.push(word);
}
process.stdout.write(missing.sort().join("\n") + "\n");
console.error(`Puuttuvia sanoja: ${missing.length} / ${seen.size}`);
