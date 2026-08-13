"""
PASSO 2 - Trovare gli indirizzi delle scuole.

Il sito degli interpelli dice solo "TOIS016005 - IIS Amaldi Sraffa": nessun
indirizzo. Per calcolare km e minuti ci serve sapere DOVE si trova la scuola.

La soluzione: l'anagrafica ufficiale delle scuole statali pubblicata dal
Ministero, che per ogni codice meccanografico elenca la sede centrale e tutti
i plessi (succursali) con il loro indirizzo.

Puoi lanciarlo da solo per provare:
    python scripts/schools.py TOIS016005
"""

import csv
import re
import sys
from datetime import date, datetime, timedelta

import requests

import config

# Come classificare un plesso in base a come lo chiama il Ministero.
# Serve per mostrare, nel dettaglio di un interpello, solo le sedi sensate.
_PAROLE_II_GRADO = (
    "ISTITUTO SUPERIORE", "LICEO", "ISTITUTO TECNICO", "IST TEC", "IST PROF",
    "ISTITUTO MAGISTRALE", "ISTITUTO D'ARTE", "CONVITTO", "IST PROF",
)


def _classifica_grado(descrizione):
    """Dice se un plesso e' medie (I grado), superiori (II grado) o altro."""
    testo = (descrizione or "").upper()
    if "PRIMO GRADO" in testo:
        return "I_GRADO"
    if any(parola in testo for parola in _PAROLE_II_GRADO):
        return "II_GRADO"
    if "CENTRO TERRITORIALE" in testo:
        return "CPIA"          # scuole per adulti (corsi serali)
    if "PRIMARIA" in testo:
        return "PRIMARIA"
    if "INFANZIA" in testo:
        return "INFANZIA"
    return "ALTRO"


def _codici_anagrafica_da_provare():
    """
    Costruisce i possibili nomi del file del Ministero, dal piu' recente.

    Il file si chiama tipo SCUANAGRAFESTAT20262720260901.csv, dove 202627 e'
    l'anno scolastico e 20260901 la data di riferimento (1 settembre).
    """
    oggi = date.today()
    anno_corrente = oggi.year if oggi.month >= 9 else oggi.year - 1

    anni = [anno_corrente, anno_corrente - 1, anno_corrente - 2]
    # Da giugno in poi il Ministero pubblica in anticipo il file dell'anno
    # scolastico che sta per cominciare: se c'e', quello e' il piu' aggiornato.
    if oggi.month >= 6:
        anni.insert(0, anno_corrente + 1)

    return [f"{anno}{(anno + 1) % 100:02d}{anno}0901" for anno in anni]


def scarica_anagrafiche(forza=False):
    """
    Scarica gli ultimi anni di anagrafica e restituisce i file, dal piu' recente.

    Perche' piu' di uno? Perche' il file dell'anno in corso a volte esce
    incompleto (a agosto 2026 mancavano 6 istituti superiori di Torino che
    esistono davvero). Quelli che mancano li recuperiamo dall'anno prima.
    """
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_trovati = []

    for codice in _codici_anagrafica_da_provare():
        if len(file_trovati) >= config.ANNI_ANAGRAFICA:
            break
        file_csv = config.DATA_DIR / config.FILE_ANAGRAFICA_MODELLO.format(codice=codice)

        # Gia' scaricato di recente? Non lo riscarichiamo.
        if file_csv.exists() and not forza:
            eta_giorni = (datetime.now() - datetime.fromtimestamp(file_csv.stat().st_mtime)).days
            if eta_giorni < 30:
                file_trovati.append(file_csv)
                continue

        url = config.ANAGRAFICA_URL_BASE.format(codice=codice)
        try:
            risposta = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=120)
        except requests.RequestException as errore:
            print(f"   anagrafica {codice}: scaricamento fallito ({errore})")
            if file_csv.exists():
                file_trovati.append(file_csv)
            continue

        # Se il file non esiste il sito risponde con una pagina HTML di errore:
        # il file vero comincia sempre con l'intestazione delle colonne.
        if risposta.ok and risposta.text.lstrip().upper().startswith("ANNOSCOLASTICO"):
            file_csv.write_text(risposta.text, encoding="utf-8")
            print(f"   anagrafica {codice}: scaricata ({len(risposta.text):,} caratteri)")
            file_trovati.append(file_csv)
        elif file_csv.exists():
            file_trovati.append(file_csv)
        else:
            print(f"   anagrafica {codice}: non ancora pubblicata")

    if not file_trovati:
        raise RuntimeError("Non sono riuscito a scaricare l'anagrafica delle scuole dal Ministero")
    return file_trovati


# Abbreviazioni che le scuole usano nell'anagrafica e che i servizi di mappe
# faticano a interpretare.
_ABBREVIAZIONI = {
    "c.so": "Corso", "cso": "Corso", "c/so": "Corso",
    "v.le": "Viale", "vle": "Viale", "v.lo": "Vicolo",
    "p.za": "Piazza", "p.zza": "Piazza", "pza": "Piazza", "p.tta": "Piazzetta",
    "f.lli": "Fratelli", "fll": "Fratelli",
    "l.go": "Largo", "str.": "Strada", "c.ne": "Circonvallazione",
    "va": "Via", "v.": "Via", "vi.": "Via",
    "s.": "San", "ss.": "Santi", "cav.": "Cavaliere",
}
_NUMERI_ROMANI = re.compile(r"^[IVXLC]+$", re.IGNORECASE)


def _indirizzo_pulito(riga):
    """Compone un indirizzo completo e leggibile, adatto ai servizi di mappe."""
    via = _sistema_via(riga["INDIRIZZOSCUOLA"])
    comune = _sistema_comune(riga["DESCRIZIONECOMUNE"])
    cap = (riga["CAPSCUOLA"] or "").strip()
    # Ogni tanto il CAP e' la scritta "Non Disponibile": meglio non metterlo,
    # altrimenti confonde chi cerca l'indirizzo.
    if not re.fullmatch(r"\d{5}", cap):
        cap = ""
    inizio = f"{via}, {cap} {comune}".replace("  ", " ").strip()
    return f"{inizio}, Italia"


def _sistema_via(via):
    """
    Ripulisce gli indirizzi scritti a mano dalle scuole.

    Casi reali trovati nell'anagrafica:
        "VIA PONCHIELLI56"        -> manca lo spazio prima del numero
        "VIA MARINUZZI 1 - TORINO"-> il comune ripetuto dentro la via
        "C.SO MONTEVECCHIO 67"    -> abbreviazione di "Corso"
        "VIA XXV APRILE 139"      -> il numero romano non va scritto "Xxv"
    """
    via = (via or "").strip()
    if via.upper() == via:                                  # tutto maiuscolo
        via = re.sub(r"\s*-\s*[A-Z' ]+$", "", via)          # toglie "- TORINO" finale
    via = re.sub(r"([A-Za-z])(\d)", r"\1 \2", via)          # "PONCHIELLI56" -> "PONCHIELLI 56"

    parole = []
    for parola in via.split():
        minuscola = parola.lower()
        if minuscola in _ABBREVIAZIONI:
            parole.append(_ABBREVIAZIONI[minuscola])
        elif _NUMERI_ROMANI.fullmatch(parola) and len(parola) > 1:
            parole.append(parola.upper())                   # "Xxv" -> "XXV"
        else:
            parole.append(parola.title() if parola.upper() == parola else parola)
    return " ".join(parole)


def _sistema_comune(comune):
    """
    Sistema i nomi dei comuni: "CIRIE'" -> "Ciriè", "SAN MAURO" -> "San Mauro".

    Nell'anagrafica gli accenti finali sono scritti con l'apostrofo, e i servizi
    di mappe non li riconoscono.
    """
    comune = (comune or "").strip().title()
    accenti = {"a'": "à", "e'": "è", "i'": "ì", "o'": "ò", "u'": "ù"}
    for sbagliato, giusto in accenti.items():
        if comune.lower().endswith(sbagliato):
            comune = comune[:-2] + giusto
    return comune


def carica_scuole():
    """
    Restituisce un dizionario: codice istituto -> informazioni sulle sedi.

    Struttura:
        "TOIS016005": {
            "denominazione": "...",
            "sede_centrale": {...},      # la sede legale: usata per l'ordinamento
            "plessi": [ {...}, {...} ],  # tutte le sedi dove si fa lezione
        }

    Unisce piu' anni di anagrafica: vince sempre il dato piu' recente, gli anni
    precedenti servono solo a tappare i buchi.
    """
    istituti = {}
    for numero, file_csv in enumerate(scarica_anagrafiche()):
        parziale = _leggi_un_file(file_csv)
        nuovi = 0
        for codice, dati in parziale.items():
            if codice not in istituti:      # il primo file letto e' il piu' recente
                istituti[codice] = dati
                nuovi += 1
        if numero > 0 and nuovi:
            print(f"   recuperati {nuovi} istituti da un'anagrafica piu' vecchia")

    # Se per qualche istituto manca la sede legale, usiamo il primo plesso.
    for istituto in istituti.values():
        if istituto["sede_centrale"] is None and istituto["plessi"]:
            istituto["sede_centrale"] = istituto["plessi"][0]
        istituto["plessi"] = _unisci_plessi_stesso_indirizzo(istituto["plessi"])

    print(f"   anagrafica: {len(istituti)} istituti in provincia di {config.PROVINCIA.title()}")
    return istituti


def _leggi_un_file(file_csv):
    """Legge un singolo CSV del Ministero e ne estrae le scuole della provincia."""
    istituti = {}

    with open(file_csv, encoding="utf-8", newline="") as f:
        for riga in csv.DictReader(f):
            if riga.get("PROVINCIA") != config.PROVINCIA:
                continue

            codice_istituto = (riga["CODICEISTITUTORIFERIMENTO"] or "").strip().upper()
            codice_plesso = (riga["CODICESCUOLA"] or "").strip().upper()
            if not codice_istituto:
                continue

            istituto = istituti.setdefault(codice_istituto, {
                "denominazione": (riga["DENOMINAZIONEISTITUTORIFERIMENTO"] or "").strip(),
                "sede_centrale": None,
                "plessi": [],
            })

            sede = {
                "codice": codice_plesso,
                "nome": (riga["DENOMINAZIONESCUOLA"] or "").strip(),
                "tipo": (riga["DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA"] or "").strip(),
                "grado": _classifica_grado(riga["DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA"]),
                "indirizzo": _indirizzo_pulito(riga),
                "comune": (riga["DESCRIZIONECOMUNE"] or "").title(),
                "sito": (riga.get("SITOWEBSCUOLA") or "").strip(),
                "email": (riga.get("INDIRIZZOEMAILSCUOLA") or "").strip(),
            }

            # La riga con lo stesso codice dell'istituto e' l'entita' amministrativa:
            # il suo indirizzo e' la sede legale (la "centrale").
            if codice_plesso == codice_istituto:
                istituto["sede_centrale"] = sede

            # SEDESCOLASTICA = SI significa "qui si fa davvero lezione".
            if (riga.get("SEDESCOLASTICA") or "").upper() == "SI":
                istituto["plessi"].append(sede)

    return istituti


def _unisci_plessi_stesso_indirizzo(plessi):
    """
    Accorpa i plessi che stanno allo stesso indirizzo.

    Un istituto superiore ha spesso 3-4 codici meccanografici diversi (tecnico,
    professionale, liceo...) tutti nello stesso edificio: mostrarli separati
    sarebbe solo rumore, e ci farebbe sprecare chiamate a Google.
    """
    per_indirizzo = {}
    for plesso in plessi:
        chiave = plesso["indirizzo"].lower()
        if chiave in per_indirizzo:
            esistente = per_indirizzo[chiave]
            if plesso["grado"] not in esistente["gradi"]:
                esistente["gradi"].append(plesso["grado"])
            if plesso["nome"] not in esistente["nomi"]:
                esistente["nomi"].append(plesso["nome"])
        else:
            nuovo = dict(plesso)
            nuovo["gradi"] = [plesso["grado"]]
            nuovo["nomi"] = [plesso["nome"]]
            per_indirizzo[chiave] = nuovo
    return list(per_indirizzo.values())


def plessi_per_classe(istituto, classe):
    """
    Dati un istituto e una classe di concorso, restituisce le sedi sensate.

    Per A060 (tecnologia alle medie) mostriamo solo i plessi di primo grado;
    per tutte le altre solo le superiori. Se non troviamo nulla di adatto
    (capita con istituti dall'anagrafica incompleta) restituiamo tutto.
    """
    grado_voluto = config.GRADO_PER_CLASSE.get(classe, config.GRADO_PER_CLASSE["_default"])
    adatti = [p for p in istituto["plessi"] if grado_voluto in p["gradi"]]
    if not adatti and grado_voluto == "II_GRADO":
        adatti = [p for p in istituto["plessi"] if "CPIA" in p["gradi"]]
    return adatti or istituto["plessi"]


if __name__ == "__main__":
    scuole = carica_scuole()
    codice = (sys.argv[1] if len(sys.argv) > 1 else "TOIS016005").upper()
    dati = scuole.get(codice)
    if not dati:
        print(f"{codice} non trovato in anagrafica")
    else:
        print(f"\n{codice} - {dati['denominazione']}")
        print(f"  sede centrale: {dati['sede_centrale']['indirizzo']}")
        for plesso in dati["plessi"]:
            print(f"  plesso: {plesso['indirizzo']}  [{', '.join(plesso['gradi'])}]")
