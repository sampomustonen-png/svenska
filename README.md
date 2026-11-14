# Läsning på svenska

Oma ruotsinkielinen lukusivu: maailman uutiset, ajankohtaiset aiheet, kulttuuri ja kirjallisuus sekä helppo ruotsi samassa näkymässä. Ulkoasu mukailee iOS 26:n Liquid Glass -tyyliä.

- **Välilehdet:** Allt, Världen, Aktuellt, Kultur, Böcker (kirjallisuusaiheiset jutut kaikista lähteistä), Lätt (helppo ruotsi) ja Reddit.
- **Sanakirja:** napauta mitä tahansa sanaa jutun ingressissä, niin näet suomennoksen, sanan perusmuodon (esim. *regeringen → regering*) ja yhdyssanan osat (esim. *klimat + mål*). *Översätt meningen* kääntää koko virkkeen. Usean sanan voi myös maalata pitkällä painalluksella.
- **Luetut:** avaamasi jutut himmenevät, ja ne voi piilottaa valikosta (•••). Samassa valikossa ovat tekstikoko ja lähteiden tila.
- **Kotivalikkoon:** Safarissa *Jaa → Lisää Koti-valikkoon*, niin sivu aukeaa kuin oma sovellus.

## Käyttöönotto

1. Luo GitHubissa uusi **julkinen** repo, esimerkiksi nimellä `svensk-lasning`. GitHub Pages toimii ilmaiseksi julkisissa repoissa.
2. Lisää kaikki tämän kansion tiedostot repoon kansioineen, myös `.github/workflows/uppdatera.yml`.
   - Selaimessa: *Add file → Upload files* ja raahaa kansion sisältö. Macin Finder piilottaa `.github`-kansion, mutta sen saa näkyviin näppäimillä Cmd + Shift + piste.
3. Avaa repon **Settings → Pages** ja valitse kohtaan *Source* vaihtoehto **GitHub Actions**.
4. Avaa **Actions**-välilehti, valitse **Uppdatera flödet** ja paina **Run workflow**.
5. Parin minuutin kuluttua sivu toimii osoitteessa `https://KÄYTTÄJÄTUNNUS.github.io/svensk-lasning/`.

Tämän jälkeen GitHub hakee uudet jutut noin kolmen tunnin välein ja rakentaa samalla sanaston juttujen sanoista. Sivu päivittyy myös aina, kun muutat repon tiedostoja.

## Lähteiden muokkaus

Lähteet ovat tiedostossa `sources.json`. Jokaisella lähteellä on:

| Kenttä | Merkitys |
|---|---|
| `id` | lyhyt tunniste, ei välilyöntejä |
| `name` | sivulla näkyvä nimi |
| `url` | RSS-syötteen osoite |
| `category` | `varlden`, `aktuellt`, `kultur` tai `latt` |
| `enabled` | `false` piilottaa lähteen |
| `max_age_days` | kuinka monen päivän vanhoja juttuja näytetään (oletus 4) |

Dagens Nyheter, Svenska Dagbladet ja Hufvudstadsbladet ovat mukana, mutta pois päältä, koska suuri osa niiden jutuista on maksumuurin takana. Jos tilaat jonkin niistä, vaihda sen kohdalle `"enabled": true`.

Valikon (•••) **Källor**-kohdasta näet, mitkä lähteet toimivat. Jos lähde näyttää tekstiä *fungerar inte*, sen syötteen osoite on luultavasti muuttunut. Korjaa osoite tai poista lähde.

## Reddit

Reddit lopetti RSS-syötteet 13.11.2026, eikä sen rajapintaan saa enää uusia käyttöoikeuksia. Siksi Reddit-välilehti näyttää vain pikalinkit (oma etusivu, r/sweden, r/svenskpolitik ja r/Svenska), jotka avautuvat Reddit-sovellukseen. Linkkejä voi muokata `sources.json`-tiedoston kohdassa `reddit`.

## Sanakirja

- Suomennokset tulevat FreeDict-/WikDict-sanakirjoista (ruotsi–suomi ja käännetty suomi–ruotsi), jotka perustuvat Wikisanakirjaan. Lisenssi CC BY-SA 3.0.
- Taivutusmuodot tunnistetaan michmech/lemmatization-lists-aineistolla (ODbL).
- Valmiit tiedostot ovat kansiossa `data/`. Ne on tehty skriptillä `scripts/build_dictionary.py`, eikä niitä tarvitse rakentaa uudelleen.
- Jos sanaa ei löydy sanakirjasta tai painat *Översätt meningen*, sana tai virke lähetetään MyMemory-konekäännöspalveluun. Ilmaisen käytön raja on noin 5 000 merkkiä päivässä, mikä riittää hyvin henkilökohtaiseen käyttöön.

## Hyvä tietää

- GitHub pysäyttää ajastetut ajot, jos julkisessa repossa ei ole tapahtunut mitään 60 päivään. Saat siitä sähköpostin, ja ajon saa takaisin päälle Actions-välilehdeltä (*Enable workflow*).
- Jos sivun yläosassa lukee punaisella, ettei syötettä ole päivitetty vähään aikaan, katso Actions-välilehdeltä, mikä ajo epäonnistui.
- Luettu-merkinnät ja asetukset tallentuvat vain omaan selaimeesi.

## Testaus omalla koneella

```sh
pip install feedparser
python scripts/build_feed.py --sources sources.json --data data --out _site
cp -r index.html manifest.webmanifest fonts assets _site/
python -m http.server -d _site
```

Avaa sitten selaimessa `http://localhost:8000`.

## Fontit

Applen laitteilla sivu käyttää järjestelmän fontteja (SF Pro ja New York). Muilla laitteilla tekstit näkyvät Literata-fontilla, joka on SIL Open Font License 1.1 -lisenssin alainen. Lisenssi on kansiossa `fonts/`.
