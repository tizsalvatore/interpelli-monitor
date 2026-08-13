"""
IL PROGRAMMA PRINCIPALE - mette insieme tutti i pezzi.

    1. legge la pagina degli interpelli          (scrape.py)
    2. trova gli indirizzi delle scuole          (schools.py)
    3. calcola km e minuti da casa               (travel.py)
    4. scrive docs/data/interpelli.json          <- il file che legge la app
    5. manda le notifiche per i nuovi interpelli (notify.py)

Si lancia cosi':
    python scripts/build.py

Opzioni utili per fare prove:
    --cache        non riscarica la pagina del sito (usa l'ultima copia)
    --no-notifica  non manda notifiche
"""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import schools
import scrape
import travel


def _viaggio_da_cache(indirizzo, viaggi):
    """Prende il tempo di viaggio calcolato per un indirizzo (None se non c'e')."""
    voce = viaggi.get(indirizzo)
    if not voce:
        return None
    mezzi = voce.get("mezzi")
    auto = voce.get("auto")
    if not mezzi and not auto:
        # Niente percorso, ma se abbiamo le coordinate servono comunque:
        # sono quelle che mettono il segnaposto sulla mappa.
        if voce.get("lat") is None:
            return None
        return {"minuti": None, "km": None, "km_strada": None, "cambi": None,
                "linee": [], "auto_minuti": None,
                "lat": voce.get("lat"), "lng": voce.get("lng"),
                "approssimativo": bool(voce.get("approssimativo"))}
    return {
        "minuti": mezzi["minuti"] if mezzi else None,
        "km": (mezzi or auto).get("km"),
        "km_strada": auto["km"] if auto else None,
        "cambi": mezzi.get("cambi") if mezzi else None,
        "linee": mezzi.get("linee") if mezzi else [],
        "auto_minuti": auto["minuti"] if auto else None,
        "lat": voce.get("lat"),
        "lng": voce.get("lng"),
        # vero = non abbiamo trovato il civico esatto e stiamo usando il
        # centro del comune: il tempo di viaggio e' indicativo.
        "approssimativo": bool(voce.get("approssimativo")),
    }


def _casa_da_pubblicare():
    """
    Decide quanto della posizione di casa finisce nel file pubblicato.

    Il file docs/data/interpelli.json e' visibile a chiunque apra la app, quindi
    qui applichiamo la scelta fatta in config.PRECISIONE_CASA_PUBBLICA.
    I minuti e i km NON passano da qui: sono gia' calcolati e restano precisi.
    """
    pubblico = {
        "etichetta": config.CASA_ETICHETTA,
        "ora_arrivo": f"{config.ORA_ARRIVO:02d}:00",
    }
    modo = config.PRECISIONE_CASA_PUBBLICA
    casa = travel.carica_casa() or {}

    if modo == "esatta":
        pubblico["indirizzo"] = config.CASA_INDIRIZZO
        pubblico["lat"] = casa.get("lat")
        pubblico["lng"] = casa.get("lng")
    elif modo == "approssimata" and casa.get("lat") is not None:
        # Due decimali = circa un chilometro: si vede il quartiere, non la casa.
        pubblico["lat"] = round(casa["lat"], 2)
        pubblico["lng"] = round(casa["lng"], 2)
        pubblico["approssimata"] = True

    return pubblico


def main(usa_cache=False, notifica=True):
    print("\n1) Leggo la pagina degli interpelli")
    html = scrape.scarica_pagina(usa_cache=usa_cache)
    interpelli = scrape.analizza(html)
    data_sito = scrape.data_aggiornamento_sito(html)

    print("\n2) Carico l'anagrafica delle scuole")
    anagrafica = schools.carica_scuole()

    print("\n3) Preparo la lista degli indirizzi da calcolare")
    # Per ogni scuola raccogliamo: la sede centrale + i plessi utili alle classi
    # di concorso che compaiono davvero negli interpelli di quella scuola.
    sedi_per_scuola = {}
    senza_anagrafica = set()

    for interpello in interpelli:
        codice = interpello["codice_scuola"]
        istituto = anagrafica.get(codice)
        if not istituto:
            senza_anagrafica.add(codice)
            continue

        voce = sedi_per_scuola.setdefault(codice, {
            "denominazione": istituto["denominazione"] or interpello["scuola"],
            "sede_centrale": istituto["sede_centrale"],
            "plessi": {},
        })
        for plesso in schools.plessi_per_classe(istituto, interpello["classe"]):
            voce["plessi"][plesso["indirizzo"]] = plesso

    indirizzi = set()
    for voce in sedi_per_scuola.values():
        if voce["sede_centrale"]:
            indirizzi.add(voce["sede_centrale"]["indirizzo"])
        indirizzi.update(voce["plessi"].keys())
    print(f"   scuole coinvolte: {len(sedi_per_scuola)} | indirizzi diversi: {len(indirizzi)}")
    if senza_anagrafica:
        print(f"   {len(senza_anagrafica)} scuole non trovate in anagrafica: {sorted(senza_anagrafica)}")

    print("\n4) Calcolo i tempi di viaggio da casa")
    viaggi = travel.aggiorna_viaggi(indirizzi)

    print("\n5) Scrivo il file per la app")
    scuole_json = {}
    for codice, voce in sedi_per_scuola.items():
        sede = voce["sede_centrale"]
        scuole_json[codice] = {
            "denominazione": voce["denominazione"],
            "sede": {
                "indirizzo": sede["indirizzo"] if sede else None,
                "comune": sede["comune"] if sede else None,
                "sito": sede.get("sito") if sede else None,
                "viaggio": _viaggio_da_cache(sede["indirizzo"], viaggi) if sede else None,
            },
            "plessi": [
                {
                    "nomi": plesso["nomi"],
                    "indirizzo": plesso["indirizzo"],
                    "comune": plesso["comune"],
                    "gradi": plesso["gradi"],
                    "viaggio": _viaggio_da_cache(indirizzo, viaggi),
                }
                for indirizzo, plesso in sorted(
                    voce["plessi"].items(),
                    key=lambda coppia: (_viaggio_da_cache(coppia[0], viaggi) or {}).get("minuti") or 9999,
                )
            ],
        }

    # A ogni interpello attacchiamo i minuti della sede centrale: e' il numero
    # con cui la app ordina la lista (dal piu' vicino al piu' lontano).
    senza_tempo = 0
    for interpello in interpelli:
        scuola = scuole_json.get(interpello["codice_scuola"])
        viaggio = (scuola or {}).get("sede", {}).get("viaggio")
        interpello["minuti"] = (viaggio or {}).get("minuti")
        interpello["km"] = (viaggio or {}).get("km_strada") or (viaggio or {}).get("km")
        if interpello["minuti"] is None:
            senza_tempo += 1

    # Ordine: prima i piu' vicini; quelli senza tempo finiscono in fondo.
    interpelli.sort(key=lambda i: (
        i["minuti"] if i["minuti"] is not None else 10_000,
        i["data_interpello"] or "",
    ))

    adesso = datetime.now(ZoneInfo(config.FUSO_ORARIO))
    dati_app = {
        "aggiornato": adesso.isoformat(timespec="seconds"),
        "aggiornato_sito": data_sito,
        "casa": _casa_da_pubblicare(),
        # Quando gira su GitHub sappiamo il nome del progetto: serve alla app
        # per offrirti il collegamento diretto al file delle ricerche.
        "github": {"repo": os.environ.get("GITHUB_REPOSITORY")},
        "classi": config.CLASSI_DI_CONCORSO,
        "grado_per_classe": config.GRADO_PER_CLASSE,
        "conteggi": {
            "totale": len(interpelli),
            "aperti": sum(1 for i in interpelli if i["stato"] == "aperto"),
            "senza_tempo_di_viaggio": senza_tempo,
        },
        "scuole": scuole_json,
        "interpelli": interpelli,
    }

    config.DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.FILE_APP_DATI.write_text(
        json.dumps(dati_app, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    peso_kb = config.FILE_APP_DATI.stat().st_size / 1024
    print(f"   scritto {config.FILE_APP_DATI} ({peso_kb:.0f} KB)")
    print(f"   interpelli: {dati_app['conteggi']['totale']} "
          f"| aperti: {dati_app['conteggi']['aperti']} "
          f"| senza tempo di viaggio: {senza_tempo}")

    if notifica:
        print("\n6) Controllo se ci sono novita' da notificare")
        try:
            import notify
            notify.avvisa_se_ci_sono_novita(dati_app)
        except Exception as errore:       # una notifica fallita non deve rompere tutto
            print(f"   notifiche non inviate: {errore}")

    print("\nFatto.\n")
    return dati_app


if __name__ == "__main__":
    main(usa_cache="--cache" in sys.argv, notifica="--no-notifica" not in sys.argv)
