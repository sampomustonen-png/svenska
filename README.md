# Läsning på svenska

Oma ruotsinkielinen lukusivu: maailman uutiset, ajankohtaiset aiheet, kulttuuri, kirjallisuus, elokuvat ja tv sekä helppo ruotsi. Jokaisen sanan saa suomennettua napauttamalla. Ulkoasu mukailee iOS 26:n Liquid Glass -tyyliä.

## Mitä sivulla on

- **I dag:** *Dagens läsning* poimii joka päivä kahdeksan juttua eri aiheista, helpoimmat ensin. Rengas näyttää, montako olet lukenut, ja peräkkäisten lukupäivien määrä näkyy sen vieressä. Alla ovat kaikki muut jutut.
- **Nyheter:** maailman uutiset ja Ruotsin ja Suomen ajankohtaiset asiat (Alla, Världen, Aktuellt). SVT:n urheilu- ja paikallisuutiset on suodatettu pois.
- **Kultur:** kulttuuri, *Böcker* (kirjallisuus) ja *Film & tv*.
- **Lätt:** helppoa ruotsia (8 Sidor, Klartext).
- **Mina ord:** tallentamasi sanat ja niiden kertaus.
- **Vaikeustaso:** jokaisessa jutussa on merkintä *Lätt*, *Medel* tai *Svår*. Järjestyksen voi vaihtaa kohdasta *Sortera* (Nyast först tai Lättast först).

### Sanakirja

Napauta mitä tahansa sanaa otsikossa tai tekstissä. Kupla näyttää:

- sanan perusmuodon ja sanaluokan (esim. *snöat → snöa, verb*)
- kuinka yleinen sana on (*vanligt*, *ganska vanligt*, *ovanligt*)
- suomennokset merkityksittäin, yleisin ensin, ja lyhyen ruotsinkielisen selityksen
- yhdyssanan osat (esim. *cykel + banor*)
- **Spara** tallentaa sanan ja virkkeen, jossa se esiintyi, Mina ord -välilehdelle
- **Översätt meningen** kääntää koko virkkeen
- **Google** avaa virkkeen Google Kääntäjässä

Usean sanan voi maalata pitkällä painalluksella, jolloin koko valinta käännetään.

### Mina ord ja kertaus

Tallennetut sanat näkyvät tekstissä katkoviivalla alleviivattuina. *Repetera* näyttää sanan ja esimerkkivirkkeen. Kun muistat sanan, se tulee uudelleen yhä harvemmin (1, 2, 4, 8 … päivän päästä). Jos et muista, se kysytään heti uudelleen. Suomennosta voi muokata, ja sanalistan voi kopioida varmuuskopioksi ja palauttaa.

### Sanakirja uutissivuilla

Valikosta (•••) löytyy kaksi tapaa lukea mitä tahansa tekstiä sanakirjan kanssa:

- **Läs egen text med ordbok:** liitä teksti, niin sen jokaisen sanan voi napauttaa.
- **Ordbok på nyhetssidor:** Safarin kirjanmerkki, joka avaa auki olevan uutisjutun tämän sivun lukunäkymään. Ohjeet ovat valikossa. Kirjanmerkki toimii useimmilla uutissivuilla (SVT, Yle, SR), mutta maksumuurin takana olevista jutuista se saa vain näkyvän osan.

### Muuta

- **Valikko (•••):** luettujen piilotus, teema (Auto, Ljust, Mörkt), tekstikoko, lähteiden päälle- ja poiskytkentä, lähteiden tila ja Reddit-linkit.
- **Offline-tila:** viimeksi ladatut jutut ja sanakirja toimivat ilman verkkoa, esimerkiksi lentokoneessa. Kuvat ja artikkelien avaaminen tarvitsevat verkon.
- **Kotivalikkoon:** Safarissa *Jaa → Lisää Koti-valikkoon*, niin sivu aukeaa kuin oma sovellus.

## Käyttöönotto ja päivitys

Repo: `sampomustonen-png/svenska`. Sivu: <https://sampomustonen-png.github.io/svenska/>

1. Lisää tai päivitä repoon kaikki tämän kansion tiedostot kansioineen: `.github/workflows/`, `assets/`, `data/`, `scripts/` sekä juuren tiedostot.
2. **Settings → Pages → Source** pitää olla **GitHub Actions**.
3. Ajo käynnistyy itsestään, kun tiedostot muuttuvat. Käsin: **Actions → Uppdatera flödet → Run workflow**.

GitHub hakee uudet jutut kolmen tunnin välein. Ensimmäinen ajo kestää noin 10–15 minuuttia, koska se lataa käännösmallin. Sen jälkeen ajot kestävät muutaman minuutin.

### Mitä ajo tekee

| Vaihe | Tiedosto |
|---|---|
| Hakee syötteet, juttujen kuvat ja vaikeustasot, kirjoittaa `feed.json` ja `ordbok.json` | `scripts/build_feed.py` |
| Listaa sanat, joita sanakirjassa ei ole | `scripts/saknade_ord.js` |
| Kääntää virkkeet ja puuttuvat sanat valmiiksi OPUS-MT-mallilla (Helsingin yliopisto) | `scripts/oversatt.py` |
| Kopioi sivun tiedostot ja julkaisee sivun | `.github/workflows/uppdatera.yml` |
| Pitää ajastuksen päällä, ettei GitHub sammuta sitä 60 päivän jälkeen | sama tiedosto, työ `hall-vid-liv` |

Jos käännösvaihe epäonnistuu, sivu julkaistaan silti. Silloin virkkeet käännetään napautettaessa MyMemory-palvelulla (ilmaisraja noin 5 000 merkkiä päivässä).

## Tiedostot

| Tiedosto | Sisältö |
|---|---|
| `index.html` | sivun rakenne |
| `styles.css` | ulkoasu |
| `app.js` | sivun toiminta |
| `ordbok.js` | sanahaku: taivutusmuodot, yhdyssanat |
| `sw.js` | offline-tila |
| `sources.json` | lähteet ja Reddit-linkit |
| `data/egna-ord.json` | omat korjaukset sanakirjaan |
| `data/*.gz` | valmis sanakirja, taivutusmuodot ja sanojen yleisyys |

## Lähteiden muokkaus

Lähteet ovat tiedostossa `sources.json`:

| Kenttä | Merkitys |
|---|---|
| `id` | lyhyt tunniste, ei välilyöntejä |
| `name` | sivulla näkyvä nimi |
| `url` | RSS-syötteen osoite |
| `category` | `varlden`, `aktuellt`, `kultur` tai `latt` |
| `tags` | merkinnät kaikille lähteen jutuille, esim. `["film"]` tai `["bok"]` |
| `exclude_url` | osoitteen osat, joita sisältävät jutut jätetään pois, esim. `"/sport/"` |
| `enabled` | `false` poistaa lähteen käytöstä |
| `max_age_days` | kuinka monen päivän vanhoja juttuja näytetään (oletus 4) |

Lähteen voi myös piilottaa vain itseltään valikon kytkimellä muuttamatta tiedostoa.

Dagens Nyheter, Svenska Dagbladet ja Hufvudstadsbladet ovat mukana, mutta pois päältä, koska suuri osa niiden jutuista on maksumuurin takana.

## Sanakirjan korjaaminen

Jos jokin suomennos on väärin, lisää rivi tiedoston `data/egna-ord.json` kohtaan `ord`:

```json
"cykel": {"p": "subst.", "s": [[["polkupyörä", "pyörä"], "fordon med pedaler"]], "ersätt": true},
```

- `s` on lista merkityksiä: `[[suomennokset], "ruotsinkielinen selitys"]`.
- `"ersätt": true` korvaa sanakirjan merkitykset. Ilman sitä omat merkitykset lisätään ensimmäisiksi.
- Kohdassa `former` taivutusmuoto ohjataan oikeaan perusmuotoon, esim. `"är": "vara"`.

Korjaus tulee voimaan seuraavassa ajossa. Actions-ajon välimuistissa on myös lista sanoista, joita sanakirjasta ei löytynyt.

## Hyvä tietää

- **Tallennukset ovat selaimessa.** Luetut jutut, asetukset ja Mina ord tallentuvat vain siihen selaimeen, jossa niitä käytät. Koti-valikon sovelluksella ja Safarilla on iPhonessa erilliset tallennukset. Safari voi myös poistaa tallennukset, jos et avaa sivua Safarissa seitsemään päivään (Koti-valikon sovellusta tämä ei koske). Ota siksi välillä varmuuskopio Mina ord -välilehdeltä.
- Kirjanmerkki avaa jutun Safarissa, joten siellä tallennetut sanat menevät Safarin listaan. Ne saa siirrettyä varmuuskopiolla.
- Jos sivun yläosassa lukee punaisella, ettei syötettä ole päivitetty, katso Actions-välilehdeltä, mikä ajo epäonnistui.

## Lisenssit

- Sanakirja: FreeDict / WikDict (Wiktionary), CC BY-SA 3.0, sekä omat korjaukset.
- Taivutusmuodot: michmech/lemmatization-lists, ODbL.
- Sanojen yleisyys: wordfreq.
- Konekäännös: OPUS-MT (Helsinki-NLP); varalla MyMemory.

## Testaus omalla koneella

```sh
pip install "feedparser>=6,<7"
python scripts/build_feed.py --sources sources.json --data data --out _site
cp index.html styles.css app.js ordbok.js sw.js manifest.webmanifest _site/
cp -r assets _site/
python -m http.server -d _site
```

Avaa sitten selaimessa `http://localhost:8000`.
