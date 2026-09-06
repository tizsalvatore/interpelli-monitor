"""
L'ARCHIVIO STORICO - la memoria lunga del progetto.

Il sito dell'Ufficio Scolastico tiene gli interpelli di un anno scolastico e
poi azzera tutto: il 28 agosto 2026 la tabella e' passata da 4000 righe a zero,
portandosi via anche lo storico delle tue classi.

Questo file evita che succeda di nuovo: ogni volta che il robot legge il sito,
gli interpelli trovati vengono aggiunti a data/archivio_interpelli.json e non
vengono piu' tolti. La app mostra quindi sempre l'unione fra:

    quello che c'e' sul sito adesso  +  tutto quello che abbiamo gia' visto

Gli interpelli che non sono piu' sul sito restano, marcati "archiviato": cosi'
si sa che quel dato viene dalla nostra memoria e non dalla pagina ufficiale.
"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import config

# Campi calcolati a ogni giro (tempi di viaggio): non vanno salvati
# nell'archivio, altrimenti ci restano dentro dei valori vecchi.
CAMPI_DA_NON_SALVARE = ("minuti", "km", "archiviato")


def carica():
    """Legge l'archivio: dizionario id -> interpello."""
    if not config.FILE_ARCHIVIO.exists():
        return {}
    try:
        dati = json.loads(config.FILE_ARCHIVIO.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("   ATTENZIONE: archivio illeggibile, riparto da quello che c'e' sul sito")
        return {}
    return {i["id"]: i for i in dati.get("interpelli", [])}


def salva(per_id):
    """Riscrive l'archivio, ordinato dal piu' recente."""
    interpelli = sorted(
        per_id.values(),
        key=lambda i: (i.get("data_interpello") or "", i.get("scuola") or ""),
        reverse=True,
    )
    for interpello in interpelli:
        for campo in CAMPI_DA_NON_SALVARE:
            interpello.pop(campo, None)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.FILE_ARCHIVIO.write_text(json.dumps({
        "_cos_e": ("Tutti gli interpelli che questo progetto ha visto sul sito, anche "
                   "quelli che il sito ha poi cancellato. Lo aggiorna il robot da solo."),
        "aggiornato": datetime.now(ZoneInfo(config.FUSO_ORARIO)).isoformat(timespec="seconds"),
        "quanti": len(interpelli),
        "interpelli": interpelli,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def unisci(dal_sito):
    """
    Mette insieme gli interpelli letti adesso e quelli gia' in archivio.

    Vince sempre il sito: se un interpello e' ancora pubblicato, prendiamo la
    sua versione aggiornata (lo stato puo' essere passato da aperto a chiuso).
    Quelli spariti dal sito restano, con "archiviato": true.
    """
    archivio = carica()
    quanti_prima = len(archivio)
    id_sul_sito = set()

    for interpello in dal_sito:
        voce = dict(interpello)
        voce["archiviato"] = False
        archivio[voce["id"]] = voce
        id_sul_sito.add(voce["id"])

    for identificativo, voce in archivio.items():
        voce["archiviato"] = identificativo not in id_sul_sito

    salva({k: dict(v) for k, v in archivio.items()})

    nuovi = len(archivio) - quanti_prima
    solo_archivio = sum(1 for v in archivio.values() if v["archiviato"])
    print(f"   archivio: {len(archivio)} interpelli"
          f" ({nuovi} nuovi, {solo_archivio} non piu' sul sito)")

    return list(archivio.values())
