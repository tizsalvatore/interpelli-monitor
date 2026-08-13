"""
PASSO 1 - Leggere la pagina degli interpelli e trasformarla in dati ordinati.

Il sito dell'Ufficio Scolastico pubblica UNA sola pagina HTML con dentro una
tabellona (circa 4000 righe) che contiene tutti gli interpelli della provincia
di Torino, sia aperti che chiusi. Qui la scarichiamo, la leggiamo riga per riga
e teniamo solo le classi di concorso che interessano a te.

Puoi lanciarlo da solo per provare:
    python scripts/scrape.py
"""

import hashlib
import json
import re
import sys
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

import config

# Le colonne della tabella, nell'ordine in cui compaiono sul sito.
COL_CODICE = 0
COL_SCUOLA = 1
COL_CLASSE = 2
COL_TIPO_CATTEDRA = 3
COL_CORSO = 4
COL_DURATA = 5
COL_DATA_INTERPELLO = 6
COL_ALLEGATO = 7
COL_STATO = 8
COL_SCADENZA = 9
COL_NOTE_CANCELLAZIONE = 10
COL_DATA_CANCELLAZIONE = 11
NUM_COLONNE = 12


def scarica_pagina(usa_cache=False):
    """Scarica la pagina degli interpelli e restituisce il testo HTML."""
    if usa_cache and config.FILE_INTERPELLI_HTML.exists():
        print("   (uso la copia locale gia' scaricata)")
        return config.FILE_INTERPELLI_HTML.read_text(encoding="utf-8", errors="replace")

    print(f"   scarico {config.INTERPELLI_URL}")
    risposta = requests.get(
        config.INTERPELLI_URL,
        headers={"User-Agent": config.USER_AGENT},
        timeout=90,
    )
    risposta.raise_for_status()

    # Il sito dichiara una codifica ma ne usa un'altra: proviamo prima UTF-8,
    # e se fallisce ripieghiamo sulla vecchia ISO-8859-1 (che non fallisce mai).
    try:
        testo = risposta.content.decode("utf-8")
    except UnicodeDecodeError:
        testo = risposta.content.decode("iso-8859-1")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.FILE_INTERPELLI_HTML.write_text(testo, encoding="utf-8")
    print(f"   scaricati {len(testo):,} caratteri")
    return testo


def data_aggiornamento_sito(html):
    """
    Legge la data che il sito scrive in cima alla pagina
    ("SITUAZIONE INTERPELLI AGGIORNATA AL 13-08-2026").
    """
    trovato = re.search(r"AGGIORNATA AL\s*(\d{1,2})[-/](\d{1,2})[-/](\d{4})", html, re.IGNORECASE)
    if not trovato:
        return None
    giorno, mese, anno = (int(x) for x in trovato.groups())
    try:
        return date(anno, mese, giorno).isoformat()
    except ValueError:
        return None


def _pulisci(testo):
    """Toglie spazi doppi, a capo e caratteri strani da una cella."""
    if testo is None:
        return ""
    testo = testo.replace("\xa0", " ")          # spazio "unificatore" dell'HTML
    testo = re.sub(r"\s+", " ", testo)          # spazi multipli -> uno solo
    testo = testo.strip()
    return "" if testo == "-" else testo        # il sito usa "-" per "vuoto"


def _leggi_data(testo):
    """
    Trasforma una data scritta all'italiana in formato ordinabile (2026-05-13).

    Il sito e' compilato a mano dalle scuole, quindi troviamo di tutto:
    "13/05/2026", "09/09/25", "20/05/2026 ore 08:30", "25/05/2026 ENTRO LE 7.30".
    Cerchiamo il primo pezzo che assomiglia a una data e ignoriamo il resto.
    """
    if not testo:
        return None
    # Accettiamo 13/05/2026, 13-05-2026 e anche 19.09.2025 (usato da qualche scuola).
    trovato = re.search(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})", testo)
    if not trovato:
        return None
    giorno, mese, anno = (int(x) for x in trovato.groups())
    if anno < 100:                 # "25" vuol dire 2025
        anno += 2000
    try:
        return date(anno, mese, giorno).isoformat()
    except ValueError:             # date impossibili tipo 31/02
        return None


def _leggi_tipo_cattedra(testo):
    """
    Separa il tipo di cattedra dalle ore.

    Sul sito trovi "Interna", "Esterna" oppure "Spezzone per numero ore: 12"
    (con mille varianti scritte a mano: "12h", "11+1", "12,5"...).
    """
    if not testo:
        return "Non indicato", None
    if testo.lower().startswith("spezzone"):
        ore = testo.split(":", 1)[1].strip() if ":" in testo else None
        return "Spezzone", (ore or None)
    return testo, None


def _leggi_classe(testo):
    """Da 'A027 - Matematica e Fisica' ricava il codice 'A027'."""
    if not testo:
        return None
    return testo.split("-", 1)[0].strip().upper()


def analizza(html):
    """Legge l'HTML e restituisce la lista degli interpelli che ti interessano."""
    # lxml e' piu' veloce, ma se non e' installato usiamo il lettore di Python.
    try:
        zuppa = BeautifulSoup(html, "lxml")
    except Exception:
        zuppa = BeautifulSoup(html, "html.parser")

    oggi = date.today().isoformat()
    interpelli = []
    id_usati = set()
    righe_totali = 0

    for riga in zuppa.find_all("tr"):
        celle = riga.find_all(["td", "th"])
        if len(celle) < NUM_COLONNE:
            continue

        valori = [_pulisci(c.get_text()) for c in celle]

        # La prima riga e' l'intestazione: si riconosce perche' contiene "*"
        if valori[COL_CODICE].lower().startswith("codice meccanografico"):
            continue

        righe_totali += 1

        classe = _leggi_classe(valori[COL_CLASSE])
        if classe not in config.CLASSI_DI_CONCORSO:
            continue  # non e' una delle tue 7 classi: la saltiamo

        tipo_cattedra, ore = _leggi_tipo_cattedra(valori[COL_TIPO_CATTEDRA])
        data_interpello = _leggi_data(valori[COL_DATA_INTERPELLO])
        data_scadenza = _leggi_data(valori[COL_SCADENZA])
        stato = (valori[COL_STATO] or "sconosciuto").lower()

        # Un "codice identificativo" stabile: serve per capire quali interpelli
        # sono NUOVI rispetto all'ultimo controllo (e quindi da notificare).
        # Non includiamo lo stato: cosi' quando un interpello passa da aperto a
        # chiuso resta lo stesso interpello e non ti arriva una seconda notifica.
        impronta = "|".join([
            valori[COL_CODICE], classe, valori[COL_DATA_INTERPELLO],
            valori[COL_DURATA], valori[COL_TIPO_CATTEDRA], valori[COL_CORSO],
            valori[COL_SCADENZA],
        ])
        identificativo = hashlib.sha1(impronta.encode("utf-8")).hexdigest()[:12]
        # Capita che la stessa riga sia inserita due volte (una poi cancellata):
        # in quel caso aggiungiamo un suffisso per non confonderle.
        suffisso = 2
        base = identificativo
        while identificativo in id_usati:
            identificativo = f"{base}-{suffisso}"
            suffisso += 1
        id_usati.add(identificativo)

        interpelli.append({
            "id": identificativo,
            "codice_scuola": valori[COL_CODICE].upper(),
            "scuola": valori[COL_SCUOLA],
            "classe": classe,
            "classe_nome": config.CLASSI_DI_CONCORSO[classe],
            "tipo_cattedra": tipo_cattedra,
            "ore_spezzone": ore,
            "corso": valori[COL_CORSO] or "Non indicato",
            "durata": valori[COL_DURATA],
            "data_interpello": data_interpello,
            "data_interpello_testo": valori[COL_DATA_INTERPELLO],
            "stato": stato,
            "data_scadenza": data_scadenza,
            "data_scadenza_testo": valori[COL_SCADENZA],
            "note_cancellazione": valori[COL_NOTE_CANCELLAZIONE],
            "data_cancellazione": _leggi_data(valori[COL_DATA_CANCELLAZIONE]),
            # "scaduto": e' ancora marcato aperto sul sito ma la scadenza e' passata.
            # Succede spesso: le scuole si dimenticano di chiuderli.
            "scaduto": bool(stato == "aperto" and data_scadenza and data_scadenza < oggi),
        })

    print(f"   righe lette: {righe_totali:,} | interpelli nelle tue classi: {len(interpelli)}")
    return interpelli


def main(usa_cache=False):
    html = scarica_pagina(usa_cache=usa_cache)
    interpelli = analizza(html)

    aperti = [i for i in interpelli if i["stato"] == "aperto"]
    print(f"   di cui APERTI adesso: {len(aperti)}")
    return interpelli


if __name__ == "__main__":
    # Se lo lanci con --cache non riscarica la pagina (utile per fare prove).
    risultato = main(usa_cache="--cache" in sys.argv)
    print(json.dumps(risultato[:3], indent=2, ensure_ascii=False))
