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
    --senza-viaggi non chiama Google: usa solo i tempi gia' calcolati
"""

import json
import os
import re
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

import archivio
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


# Campi che nel file pubblicato non servono, o che la app ricava da sola.
# Con quasi 3000 interpelli ogni campo inutile pesa: "classe_nome" ripetuto
# 3000 volte sono un centinaio di KB che il telefono scarica per niente, visto
# che i nomi delle classi stanno gia' nel dizionario "classi".
def _alleggerisci(interpello):
    magro = {k: v for k, v in interpello.items()
             if k != "classe_nome" and v is not None and v != ""}
    # questi due devono esserci sempre, anche vuoti: la app ci conta sopra
    for campo in ("minuti", "km"):
        magro[campo] = interpello.get(campo)
    return magro


def _date_italiane(testo):
    """Riscrive "fino al 2027-06-30" come "fino al 30/06/2027"."""
    return re.sub(r"(\d{4})-(\d{2})-(\d{2})",
                  lambda t: f"{t.group(3)}/{t.group(2)}/{t.group(1)}", testo)


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

    # Se hai indicato un indirizzo apposta per la mappa, il segnaposto va li',
    # preciso. L'indirizzo vero non entra comunque mai in questo file.
    visibile = travel.posizione_visibile()
    if visibile:
        pubblico["lat"] = visibile["lat"]
        pubblico["lng"] = visibile["lng"]
        pubblico["indirizzo"] = visibile["indirizzo"]
        return pubblico

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


def main(usa_cache=False, notifica=True, senza_viaggi=False):
    print("\n1) Leggo la pagina degli interpelli")
    html = scrape.scarica_pagina(usa_cache=usa_cache)
    interpelli_sito = scrape.analizza(html)
    data_sito = scrape.data_aggiornamento_sito(html)

    # Il sito cancella tutto a inizio anno scolastico: uniamo quello che c'e'
    # adesso con tutto quello che abbiamo gia' visto (vedi archivio.py).
    interpelli = archivio.unisci(interpelli_sito)

    # "Aperto" ma col termine gia' passato non e' ne' aperto ne' chiuso:
    # lo mettiamo in una categoria sua, cosi' non sporca i risultati e non
    # fa scattare le notifiche.
    oggi = date.today().isoformat()
    for interpello in interpelli:
        scadenza = interpello.get("data_scadenza")
        if interpello.get("stato") == "aperto" and scadenza and scadenza < oggi:
            interpello["stato"] = "scaduto"
        # il vecchio campo non serve piu': ora lo dice lo stato
        interpello.pop("scaduto", None)
        # il sito scrive certe date all'americana dentro il testo della durata
        if interpello.get("durata"):
            interpello["durata"] = _date_italiane(interpello["durata"])

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
    if senza_viaggi:
        print("   saltato (--senza-viaggi): uso solo quello che c'e' gia' in cache")
        viaggi = travel.carica_cache()["destinazioni"]
    else:
        viaggi = travel.aggiorna_viaggi(indirizzi)
        travel.dimentica_indirizzi_non_piu_usati(indirizzi)

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
        # Il nome scritto sul sito lo mettono le scuole a mano, e a volte e'
        # il codice meccanografico in minuscolo ("tovc01000q") o una sigla
        # diversa ogni volta. Quello dell'anagrafica e' sempre lo stesso.
        if scuola and scuola.get("denominazione"):
            interpello["scuola"] = scuola["denominazione"]
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
        # Da quale indirizzo abbiamo letto: cambia a ogni anno scolastico,
        # e la app lo usa per il collegamento "pagina ufficiale".
        "fonte_url": scrape.URL_USATO,
        "casa": _casa_da_pubblicare(),
        # Quando gira su GitHub sappiamo il nome del progetto: serve alla app
        # per offrirti il collegamento diretto al file delle ricerche.
        "github": {"repo": os.environ.get("GITHUB_REPOSITORY")},
        "classi": config.CLASSI_DI_CONCORSO,
        "durate": config.DURATE_SUPPLENZA,
        "settori": config.SETTORI,
        "stati": config.STATI,
        "settore_per_classe": {
            classe: config.SETTORE_PER_CLASSE.get(
                classe, config.SETTORE_PER_CLASSE["_default"])
            for classe in config.CLASSI_DI_CONCORSO
        },
        "grado_per_classe": config.GRADO_PER_CLASSE,
        "conteggi": {
            "totale": len(interpelli),
            "sul_sito": len(interpelli_sito),
            "archiviati": sum(1 for i in interpelli if i.get("archiviato")),
            "aperti": sum(1 for i in interpelli if i["stato"] == "aperto"),
            "scaduti": sum(1 for i in interpelli if i["stato"] == "scaduto"),
            "per_settore": {
                settore: sum(1 for i in interpelli if i.get("settore") == settore)
                for settore in config.SETTORI
            },
            "senza_tempo_di_viaggio": senza_tempo,
        },
        # Serve alla app per spiegarti PERCHE' mancano i tempi di viaggio,
        # invece di mostrare "n.d." e basta. Non contiene nessun dato sensibile:
        # dice solo se le due impostazioni ci sono, non quali sono.
        "diagnostica": {
            "casa_impostata": bool(config.CASA_INDIRIZZO),
            "chiave_google": bool(travel.chiave_api()),
        },
        "scuole": scuole_json,
        "interpelli": [_alleggerisci(i) for i in interpelli],
    }

    config.DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.FILE_APP_DATI.write_text(
        json.dumps(dati_app, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
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
    main(usa_cache="--cache" in sys.argv,
         notifica="--no-notifica" not in sys.argv,
         senza_viaggi="--senza-viaggi" in sys.argv)
