"""
RECUPERO DI EMERGENZA - ripescare interpelli spariti dal sito.

Il sito dell'Ufficio Scolastico azzera l'elenco a ogni anno scolastico. Se in
quel momento noi non avevamo ancora in archivio una certa classe di concorso
(e' successo con primaria e infanzia, aggiunte a settembre 2026), quello
storico sembrerebbe perso per sempre.

Non del tutto: l'Archivio di Internet (web.archive.org) ogni tanto fotografa
le pagine pubbliche. Questo script cerca quelle fotografie, le legge con lo
stesso lettore di sempre e aggiunge all'archivio solo gli interpelli che non
abbiamo gia'.

Si lancia a mano, quando serve:
    python scripts/recupera_da_archivio_internet.py
    python scripts/recupera_da_archivio_internet.py --da 20250901 --a 20260906
"""

import argparse
import collections

import requests

import archivio
import config
import scrape

CDX = "http://web.archive.org/cdx/search/cdx"
ISTANTANEA = "https://web.archive.org/web/{timestamp}id_/{url}"


def istantanee(url, da, a):
    """Elenca le fotografie disponibili di una pagina, dalla piu' recente."""
    risposta = requests.get(CDX, params={
        "url": url, "output": "json", "from": da, "to": a,
        "fl": "timestamp,statuscode", "filter": "statuscode:200",
    }, headers={"User-Agent": config.USER_AGENT}, timeout=120)
    risposta.raise_for_status()
    righe = risposta.json()
    return sorted((r[0] for r in righe[1:]), reverse=True)


def scarica_istantanea(url, timestamp):
    indirizzo = ISTANTANEA.format(timestamp=timestamp, url=url)
    print(f"   scarico la fotografia del {timestamp[:8]}")
    risposta = requests.get(indirizzo, headers={"User-Agent": config.USER_AGENT}, timeout=300)
    risposta.raise_for_status()
    try:
        return risposta.content.decode("utf-8")
    except UnicodeDecodeError:
        return risposta.content.decode("iso-8859-1")


def main(da="20250901", a=None):
    from datetime import date
    a = a or date.today().strftime("%Y%m%d")

    gia_in_archivio = archivio.carica()
    print(f"archivio attuale: {len(gia_in_archivio)} interpelli")

    aggiunti = []
    for anno in (2025, 2026):
        url = config.INTERPELLI_URL_MODELLO.format(anno=anno)
        try:
            elenco = istantanee(url, da, a)
        except requests.RequestException as errore:
            print(f"   {url}: archivio non raggiungibile ({errore})")
            continue
        print(f"{url}\n   fotografie disponibili: {len(elenco)}")

        for timestamp in elenco:
            html = scarica_istantanea(url, timestamp)
            trovati = scrape.analizza(html)

            nuovi = 0
            for interpello in trovati:
                if interpello["id"] in gia_in_archivio:
                    continue
                # Erano "aperti" il giorno della fotografia, mesi fa: oggi
                # sicuramente non lo sono piu'. Segnarli aperti farebbe
                # contare male la app e, peggio, farebbe partire le notifiche.
                if interpello["stato"] == "aperto":
                    interpello["stato"] = "chiuso"
                interpello["scaduto"] = False
                interpello["archiviato"] = True
                gia_in_archivio[interpello["id"]] = interpello
                aggiunti.append(interpello)
                nuovi += 1
            print(f"   {timestamp[:8]}: {len(trovati)} letti, {nuovi} nuovi")

    if not aggiunti:
        print("\nNiente da aggiungere: l'archivio era gia' completo.")
        return

    archivio.salva(gia_in_archivio)
    per_classe = collections.Counter(i["classe"] for i in aggiunti)
    print(f"\nAggiunti {len(aggiunti)} interpelli. Per classe:")
    for classe, quanti in per_classe.most_common():
        print(f"   {classe}  {quanti}")
    print(f"archivio ora: {len(gia_in_archivio)} interpelli")


if __name__ == "__main__":
    lettore = argparse.ArgumentParser(description=__doc__)
    lettore.add_argument("--da", default="20250901", help="data di inizio, formato AAAAMMGG")
    lettore.add_argument("--a", default=None, help="data di fine, formato AAAAMMGG")
    argomenti = lettore.parse_args()
    main(argomenti.da, argomenti.a)
