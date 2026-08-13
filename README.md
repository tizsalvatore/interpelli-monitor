# Interpelli Monitor — Torino

App per telefono (Android e iPhone) che mostra gli **interpelli della provincia di Torino**
su **elenco e mappa**, ordinati per **quanto sono vicini a casa** con i mezzi pubblici.

- Classi seguite: **A027, A020, A026, A040, A041, A047, A060**
- I minuti sono calcolati da casa, per arrivare a scuola **entro le 8:00** di un giorno feriale
  (l'indirizzo di casa resta privato: vedi §6)
- Ricerche salvabili con nome, preferiti a stellina, notifiche Telegram per i nuovi interpelli
- Si aggiorna da sola ogni 30 minuti, anche a PC spento

---

## 1. Provarla subito sul computer

Prima di tutto crea nella cartella del progetto un file chiamato **`casa.txt`**
con dentro una riga sola, l'indirizzo di partenza:

```
Via Roma 1, 10100 Torino TO, Italia
```

Questo file **non finisce mai su GitHub** (vedi §6). Poi apri il terminale nella
cartella del progetto e lancia, una riga alla volta:

```bash
python -m venv .venv
```

```bash
.venv\Scripts\pip install -r requirements.txt
```

```bash
.venv\Scripts\python scripts\build.py
```

Poi accendi un piccolo server per vedere la app:

```bash
.venv\Scripts\python -m http.server 8765 --directory docs
```

e apri il browser su **http://localhost:8765**.

> Senza la chiave di Google (passo 3) i tempi di viaggio appaiono come "n.d.",
> ma la mappa e tutto il resto funzionano già.

---

## 2. Metterla online (e sul telefono)

Serve un account GitHub gratuito.

1. Crea un progetto nuovo su <https://github.com/new>, chiamalo `interpelli-monitor`.
   Scegli **Public** (con l'account gratuito le pagine si pubblicano solo dai progetti pubblici)
   e **non** spuntare "Add a README file": la cartella ha già tutto.
2. Nella cartella del progetto, un comando alla volta:

```bash
git init
```

```bash
git add .
```

```bash
git commit -m "Prima versione"
```

```bash
git branch -M main
```

```bash
git remote add origin https://github.com/TUO-NOME/interpelli-monitor.git
```

```bash
git push -u origin main
```

> **Se incollando nel terminale compaiono caratteri strani** come `^[[200~` o un `~` in fondo
> al comando, è un difetto noto di Git Bash. Si spegne una volta per sempre così:
>
> ```bash
> echo "set enable-bracketed-paste off" >> ~/.inputrc
> ```
>
> poi chiudi e riapri il terminale.

3. Su GitHub: **Settings → Pages**. In *Source* scegli **Deploy from a branch**,
   ramo **main**, cartella **/docs**. Salva.
4. Dopo un paio di minuti la app è online su
   `https://TUO-NOME.github.io/interpelli-monitor/`

**Installarla sul telefono:**

- **iPhone**: apri il link con Safari → tasto *Condividi* → *Aggiungi a Home*
- **Android**: apri il link con Chrome → menu ⋮ → *Installa app*

Da quel momento ha la sua icona e si apre a schermo intero, come un'app normale.

---

## 3. Attivare i tempi di viaggio (chiave Google)

Servono due API di Google: **Geocoding** (indirizzo → posizione) e **Routes** (percorsi coi mezzi).
Il progetto fa poche centinaia di chiamate in tutto, poi tiene i risultati in memoria:
si resta ampiamente nel credito gratuito mensile.

1. Vai su <https://console.cloud.google.com/> e crea un progetto.
2. Attiva la fatturazione (serve la carta, ma non verrà addebitato nulla se resti nei limiti gratuiti).
3. In **API e servizi → Libreria** attiva: **Geocoding API** e **Routes API**.
4. In **Credenziali → Crea credenziali → Chiave API**, copia la chiave.
5. Consigliato: limita la chiave alle sole due API sopra.

**Per usarla sul tuo computer** (PowerShell, vale solo per quella finestra):

```bash
$env:GOOGLE_MAPS_API_KEY = "la-tua-chiave"
```

**Per usarla online**: su GitHub, **Settings → Secrets and variables → Actions → New repository secret**,
nome `GOOGLE_MAPS_API_KEY`, valore la chiave.

Al giro successivo i tempi compaiono ovunque (e restano salvati: non si ricalcolano ogni volta).

---

## 4. Attivare le notifiche Telegram

1. Su Telegram cerca **@BotFather**, scrivi `/newbot` e segui le istruzioni: ti darà un **token**.
2. Scrivi un messaggio qualsiasi al tuo bot appena creato.
3. Apri nel browser `https://api.telegram.org/botIL-TUO-TOKEN/getUpdates` e cerca `"chat":{"id":123456789`:
   quel numero è il tuo **chat id**.
4. Su GitHub aggiungi due secret (come sopra):
   - `TELEGRAM_BOT_TOKEN` = il token
   - `TELEGRAM_CHAT_ID` = il numero
5. Facoltativo: **Settings → Secrets and variables → Actions → Variables** → `URL_APP`
   con l'indirizzo della tua app, così il messaggio contiene il link.

Alla prima esecuzione il robot **non manda niente**: si limita a prendere nota della situazione,
per non sommergerti con tutto l'arretrato. Dalla volta dopo ti avvisa solo delle novità.

### Le ricerche salvate e le notifiche

Le ricerche che salvi nella app vivono **sul telefono**. Il robot delle notifiche invece gira su GitHub
e non può leggerle da solo. Per collegarli:

1. nella app apri **Ricerche** e scendi fino a *Sincronizza le notifiche*;
2. tocca **Copia**;
3. tocca **Apri il file su GitHub**, incolla al posto di quello che c'è, e conferma (*Commit changes*).

Va fatto solo quando cambi le ricerche che devono avvisarti.
Se non lo fai mai, valgono i criteri scritti in `scripts/config.py`.

---

## 5. Cambiare le impostazioni

Quasi tutto sta in **`scripts/config.py`**, con i commenti che spiegano cosa fa cosa:

| Cosa vuoi cambiare | Dove |
|---|---|
| L'indirizzo di casa | il file `casa.txt` (e il segreto `CASA_INDIRIZZO` su GitHub) |
| Quanto della posizione di casa si vede online | `PRECISIONE_CASA_PUBBLICA` in `config.py` |
| L'ora di arrivo a scuola | `ORA_ARRIVO` |
| Le classi di concorso seguite | `CLASSI_DI_CONCORSO` |
| Quando avvisarti (se non usi le ricerche) | `NOTIFICA_*` |

Se cambi casa, cancella anche `data/cache_viaggi.json`: così tutti i tempi vengono ricalcolati.

---

## 6. La privacy del tuo indirizzo

Il progetto su GitHub è pubblico (serve per pubblicare le pagine con l'account gratuito),
quindi **l'indirizzo di casa non è scritto da nessuna parte nel codice**. Funziona così:

| Dove gira | Da dove legge l'indirizzo |
|---|---|
| Sul tuo computer | il file `casa.txt`, escluso da GitHub tramite `.gitignore` |
| Su GitHub | il segreto `CASA_INDIRIZZO` (Settings → Secrets and variables → Actions), che nessuno può leggere, nemmeno chi guarda il progetto |

Le coordinate finiscono in `data/casa_privata.json`, anch'esso escluso da GitHub.

**Il segnaposto 🏠 sulla mappa** non arriva dal server: al primo avvio l'app ti chiede dove abiti
(scrivendo l'indirizzo, usando la posizione del dispositivo, o toccando il punto sulla mappa) e lo
salva **solo su quel telefono**. Lo cambi quando vuoi da *Info → Il tuo segnaposto*.
Va impostato su ogni dispositivo dove installi l'app.

**Cosa si vede online**: solo quello che decidi con `PRECISIONE_CASA_PUBBLICA` in `config.py`:

- `"nascosta"` *(predefinito)* — niente del tutto: nel file pubblicato non c'è nessuna coordinata
- `"approssimata"` — coordinate arrotondate a circa un chilometro: il segnaposto indica la zona,
  utile se vuoi che l'app parta già con un riferimento su qualsiasi dispositivo
- `"esatta"` — indirizzo e posizione precisi (usalo solo se rendi il progetto privato)

**I minuti e i km restano sempre esatti**: vengono calcolati sul computer di GitHub partendo
dall'indirizzo vero, e nel file pubblicato finiscono solo i risultati (i numeri), non il punto di partenza.

> ⚠️ Se in passato hai già pubblicato l'indirizzo, toglierlo dai file **non basta**: resta
> nella cronologia dei commit. In quel caso la via più sicura è cancellare il repository su
> GitHub e ricrearlo da zero (§2), così la cronologia riparte pulita.

---

## 7. Com'è fatto

```
Interpelli Monitor/
├── scripts/            il "motore" in Python
│   ├── config.py       tutte le impostazioni
│   ├── scrape.py       legge la tabella dal sito dell'Ufficio Scolastico
│   ├── schools.py      trova gli indirizzi delle scuole (anagrafica del Ministero)
│   ├── travel.py       chiede a Google km e minuti, e li tiene in cache
│   ├── notify.py       manda Telegram/email per i nuovi interpelli
│   ├── build.py        mette insieme tutto  ← è questo che si lancia
│   └── make_icons.py   ridisegna le icone della app
├── docs/               la app (è la cartella che GitHub pubblica)
│   ├── index.html · styles.css · app.js
│   ├── sw.js           permette di installarla e di aprirla offline
│   └── data/
│       ├── interpelli.json   i dati che la app legge
│       └── ricerche.json     le ricerche che fanno scattare le notifiche
├── data/               file di lavoro e memoria (cache dei tempi, già notificati)
└── .github/workflows/  il robot che aggiorna tutto ogni 30 minuti
```

**Da dove arrivano i dati**

- Interpelli: [Ufficio Scolastico Piemonte – ambito di Torino](https://servizi.istruzionepiemonte.it/interpello2025/ric_interpello_ambito_to.php)
- Indirizzi delle scuole: anagrafica scuole statali del Ministero (dati.istruzione.it), uniti su due anni
  perché il file dell'anno in corso a volte è incompleto
- Mappa: OpenStreetMap con sfondo CARTO — km e minuti: Google Maps

---

## 8. Se qualcosa non va

| Problema | Cosa fare |
|---|---|
| I tempi restano "n.d." | Manca `GOOGLE_MAPS_API_KEY`, o le API Geocoding/Routes non sono attive |
| La mappa è grigia | Sei offline: le mappe non si salvano per l'uso offline |
| Non arrivano notifiche | Controlla i secret; ricorda che la prima esecuzione non manda mai nulla |
| Il robot non parte più | GitHub sospende i lavori automatici nei progetti fermi da 60 giorni: apri Actions e premi *Run workflow* |
| La app mostra dati vecchi | Tocca l'icona ↻ in alto a destra |
| Ho cambiato la app ma il telefono mostra la vecchia | In `docs/sw.js` alza il numero di `VERSIONE` |

**Nota**: app non ufficiale, a uso personale. I dati possono contenere errori o non essere aggiornati:
prima di candidarti verifica sempre l'avviso pubblicato dalla scuola.
