# Läsning på svenska

Oma ruotsinkielinen lukusivu: maailman uutiset, ajankohtaiset aiheet, kulttuuri, kirjallisuus, elokuvat ja tv sekä helppo ruotsi. Jokaisen sanan saa suomennettua napauttamalla. Ulkoasu mukailee iOS 26:n Liquid Glass -tyyliä.

## Mitä sivulla on

- **I dag:** *Dagens läsning* poimii joka päivä kahdeksan juttua eri aiheista, helpoimmat ensin. Rengas näyttää, montako olet lukenut, ja peräkkäisten lukupäivien määrä näkyy sen vieressä. Alla ovat kaikki muut jutut.
- **Nyheter:** maailman uutiset, länsimaiden politiikka sekä Ruotsin ja Suomen ajankohtaiset asiat (Alla, Världen, Politik, Aktuellt). *Politik* kokoaa jutut, joissa on kyse Euroopan, EU:n, USA:n tai muiden länsimaiden politiikasta; niissä on merkintä *Världspolitik*. SVT:n urheilu- ja paikallisuutiset on suodatettu pois.
- **Kultur:** kulttuuri, *Böcker* (kirjallisuus) ja *Film & tv*.
- **Lätt:** helppoa ruotsia (8 Sidor, Klartext).
- **Mina ord:** tallentamasi sanat ja niiden kertaus.
- **Vaikeustaso:** jokaisessa jutussa on merkintä *Lätt*, *Medel* tai *Svår*. Järjestyksen voi vaihtaa kohdasta *Sortera* (Nyast först tai Lättast först).

### Sanakirja

Napauta mitä tahansa sanaa otsikossa tai tekstissä. Kupla näyttää:

- **sanaliiton tai partikkeliverbin**, jos sana kuuluu sellaiseen (esim. *tog inte upp* → *ta upp* = ottaa esille, *på grund av* = takia). Ilmauksen sanat korostetaan tekstissä.
- sanan perusmuodon ja sanaluokan (esim. *snöat → snöa, verb*)
- kuinka yleinen sana on (*vanligt*, *ganska vanligt*, *ovanligt*)
- enintään neljä merkitystä, yleisin ensin, ja esimerkin tai lyhyen selityksen
- **virkkeeseen sopivan merkityksen**: jos virkkeen käännös on tiedossa, siihen sopiva merkitys nostetaan ensimmäiseksi ja merkitään *i den här meningen*
- yhdyssanan osat (esim. *cykel + banor*)
- **Spara** tallentaa sanan ja virkkeen, jossa se esiintyi, Mina ord -välilehdelle
- **Översätt meningen** kääntää koko virkkeen
- **Google** avaa virkkeen Google Kääntäjässä

Usean sanan voi maalata pitkällä painalluksella, jolloin koko valinta käännetään.

### Mina ord ja kertaus

Tallennetut sanat näkyvät tekstissä katkoviivalla alleviivattuina. *Repetera* näyttää sanan ja esimerkkivirkkeen. Kun muistat sanan, se tulee uudelleen yhä harvemmin (1, 2, 4, 8 … päivän päästä). Jos et muista, se kysytään heti uudelleen. Suomennosta voi muokata, ja sanalistan voi kopioida varmuuskopioksi ja palauttaa.

### Koko juttu sanakirjan kanssa

*Läs artikeln* (tai jutun kuva) avaa jutun sovelluksen omaan lukunäkymään. Ensin näkyy tiivistelmä, ja hetken päästä koko jutun teksti, jonka jokaista sanaa voi napauttaa. *Original ↗* avaa jutun uutissivustolla.

- Jutun tekstin hakee ilmainen lukupalvelu [Jina Reader](https://jina.ai/reader) vasta, kun avaat jutun. Teksti näytetään vain sinulle, eikä sitä tallenneta julkiselle sivulle. Palvelulle välittyy vain jutun osoite.
- Viimeksi avatut 40 juttua säilyvät puhelimessa, joten ne aukeavat uudelleen heti ja myös ilman verkkoa.
- Jos haku epäonnistuu (esim. sivusto estää palvelun hetkellisesti), lukunäkymässä on tiivistelmä ja painike, joka avaa jutun alkuperäisellä sivulla.
- Maksumuurin takana olevista jutuista saadaan vain näkyvä osa.

Valikon (•••) kohdassa *Läs egen text med ordbok* voit lisäksi liittää minkä tahansa tekstin ja lukea sen sanakirjan kanssa.

### Muuta

- **Valikko (•••):** luettujen piilotus, teema (Auto, Ljust, Mörkt), tekstikoko, lähteiden päälle- ja poiskytkentä, lähteiden tila ja Reddit-linkit.
- **Offline-tila:** viimeksi ladatut jutut, sanakirja ja jo avatut kokonaiset jutut toimivat ilman verkkoa, esimerkiksi lentokoneessa. Kuvat ja uusien juttujen avaaminen tarvitsevat verkon.
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
| `data/grundord.txt` | noin 900 yleisimmän sanan tarkistetut suomennokset |
| `data/uttryck.txt` | sanaliitot ja partikkeliverbit (noin 300 omaa ja sanakirjan omat) |
| `data/egna-ord.json` | yksittäiset korjaukset ja taivutusmuotojen ohjaukset |
| `data/*.gz` | valmis sanakirja, taivutusmuodot ja sanojen yleisyys |

## Lähteiden muokkaus

Lähteet ovat tiedostossa `sources.json`:

| Kenttä | Merkitys |
|---|---|
| `id` | lyhyt tunniste, ei välilyöntejä |
| `name` | sivulla näkyvä nimi |
| `url` | RSS-syötteen osoite |
| `category` | `varlden`, `aktuellt`, `kultur` tai `latt` |
| `tags` | merkinnät kaikille lähteen jutuille: `bok`, `film` tai `politik` |
| `exclude_url` | osoitteen osat, joita sisältävät jutut jätetään pois, esim. `"/sport/"` |
| `include_url` | vain osoitteet, joissa on jokin näistä osista, otetaan mukaan |
| `require_tag` | vain jutut, jotka saavat tämän merkinnän, esim. `"politik"` (Expressen ja Aftonbladet: vain maailmanpolitiikka) |
| `no_summary` | `true` ohittaa syötteen tiivistelmän (jos se on pelkkää roskaa) |
| `check_links` | `true` korjaa Sveriges Radion linkit. Syötteen numerolinkki ei toimi kaikilla jutuilla (esim. Kulturnytt), vaikka juttu on verkossa. Siksi jokainen juttu etsitään ensin otsikon perusteella ohjelman verkkosivulta (esim. sverigesradio.se/kultur), ja sieltä löytyvä osoite otetaan käyttöön. Muut linkit kokeillaan, ja jos sivua ei ole, juttu jätetään pois. Tulos näkyy Actions-ajon yhteenvedossa (Annotations) ja feed.jsonin kohdassa `linkcheck`. |
| `enabled` | `false` poistaa lähteen käytöstä |
| `max_age_days` | kuinka monen päivän vanhoja juttuja näytetään (oletus 4) |

Lähteen voi myös piilottaa vain itseltään valikon kytkimellä muuttamatta tiedostoa.

Maailmanpolitiikan lähteet ovat SVT Utrikes, Svenska Yle utrikes, Europaportalen (EU ja Euroopan politiikka), Sveriges Radion *Konflikt* (viikoittainen ulkomaanmakasiini) sekä Expressenin ja Aftonbladetin uutisista ne, jotka koskevat länsimaiden politiikkaa. Jos jokin näistä näyttää valikossa tekstiä *fungerar inte*, sen syöteosoite on muuttunut.

Dagens Nyheter, Svenska Dagbladet ja Hufvudstadsbladet ovat mukana, mutta pois päältä, koska suuri osa niiden jutuista on maksumuurin takana.

## Sanakirjan korjaaminen

Sanakirja koostuu kerroksista. Ylempi voittaa alemman:

1. `data/egna-ord.json`: yksittäiset korjaukset
2. `data/grundord.txt`: yleisimpien sanojen tarkistetut merkitykset
3. FreeDict/WikDict-sanakirja (`data/sv-fi.json.gz`)

Helpoin tapa korjata sana on lisätä tai muuttaa rivi tiedostossa `data/grundord.txt`:

```
driva|verb|pyörittää, johtaa = driva företag; ajaa (asiaa) = driva frågan; ajelehtia
```

- Muoto on `sana|sanaluokka|merkitykset`. Merkitykset erotetaan puolipisteellä (enintään neljä, yleisin ensin).
- Yhden merkityksen sisällä suomennokset erotetaan pilkulla, ja `=`-merkin jälkeen voi kirjoittaa esimerkin.

Sanaliiton tai partikkeliverbin lisäät tiedostoon `data/uttryck.txt` samalla tavalla ilman sanaluokkaa:

```
ta upp|ottaa esille, ottaa puheeksi = ta upp frågan; nostaa ylös
```

Kirjoita verbi perusmuodossa. Sovellus tunnistaa myös taivutetut muodot (*tog upp*, *tar upp*) ja lyhyet välisanat (*tog inte upp*).

Jos taivutusmuoto ohjautuu väärään perusmuotoon, lisää se tiedoston `data/egna-ord.json` kohtaan `former`, esim. `"lever": "leva|lever"`.

Korjaukset tulevat voimaan seuraavassa ajossa. Actions-ajon välimuistissa on myös lista sanoista, joita sanakirjasta ei löytynyt.

## Hyvä tietää

- **Tallennukset ovat selaimessa.** Luetut jutut, asetukset ja Mina ord tallentuvat vain siihen selaimeen, jossa niitä käytät. Koti-valikon sovelluksella ja Safarilla on iPhonessa erilliset tallennukset. Safari voi myös poistaa tallennukset, jos et avaa sivua Safarissa seitsemään päivään (Koti-valikon sovellusta tämä ei koske). Ota siksi välillä varmuuskopio Mina ord -välilehdeltä.
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
