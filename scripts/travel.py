"""
PASSO 3 - Calcolare quanto dista ogni scuola da casa.

Per ogni indirizzo di scuola chiediamo a Google due cose:
  1. le coordinate (Geocoding API);
  2. il percorso coi mezzi pubblici per ARRIVARE alle 8:00 (Routes API),
     piu' il percorso in auto (che ci da' i chilometri "veri" di strada).

Tutto viene salvato in data/cache_viaggi.json: la volta dopo, per le scuole
gia' calcolate, non chiediamo piu' niente a Google. Cosi' anche facendo girare
il controllo ogni 30 minuti il costo resta zero.

Serve la chiave API in una variabile d'ambiente chiamata GOOGLE_MAPS_API_KEY.
Prova cosi' (dopo aver messo la chiave):
    python scripts/travel.py "Via Ponchielli 56, 10154 Torino, Italia"
"""

import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

import config

URL_GEOCODING = "https://maps.googleapis.com/maps/api/geocode/json"
URL_ROTTE = "https://routes.googleapis.com/directions/v2:computeRoutes"
# Servizio gratuito di OpenStreetMap: lo usiamo solo per trovare le coordinate
# quando la chiave Google non c'e' ancora, cosi' la mappa funziona lo stesso.
URL_NOMINATIM = "https://nominatim.openstreetmap.org/search"

# Quali informazioni chiedere a Google sul percorso. Chiedere solo il minimo
# necessario tiene le chiamate nella fascia gratuita.
CAMPI_TRANSIT = (
    "routes.duration,routes.distanceMeters,"
    "routes.legs.steps.travelMode,"
    "routes.legs.steps.transitDetails.transitLine.nameShort,"
    "routes.legs.steps.transitDetails.transitLine.vehicle.type"
)
CAMPI_MINIMI = "routes.duration,routes.distanceMeters"


def chiave_api():
    """Legge la chiave di Google dall'ambiente (None se non c'e')."""
    return os.environ.get("GOOGLE_MAPS_API_KEY", "").strip() or None


# --------------------------------------------------------------------------
# Cache su file
# --------------------------------------------------------------------------
def carica_cache():
    """Cache dei percorsi verso le scuole. Questo file PUO' stare su GitHub."""
    if config.FILE_CACHE_VIAGGI.exists():
        cache = json.loads(config.FILE_CACHE_VIAGGI.read_text(encoding="utf-8"))
        # Nelle prime versioni le coordinate di casa stavano qui dentro:
        # se le troviamo le spostiamo nel file privato e le togliamo da qui.
        if cache.pop("casa", None) and not config.FILE_CASA_PRIVATA.exists():
            print("   (sposto le coordinate di casa nel file privato)")
        cache.setdefault("destinazioni", {})
        return cache
    return {"destinazioni": {}}


def salva_cache(cache):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache.pop("casa", None)          # per sicurezza: casa non deve finire qui
    config.FILE_CACHE_VIAGGI.write_text(
        json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8"
    )


def carica_casa():
    """
    Coordinate di casa, tenute in un file separato ed escluso da GitHub.

    Sul computer di GitHub il file non c'e': viene ricreato a ogni giro
    partendo dal segreto CASA_INDIRIZZO, e non viene mai salvato nel progetto.
    """
    if config.FILE_CASA_PRIVATA.exists():
        casa = json.loads(config.FILE_CASA_PRIVATA.read_text(encoding="utf-8"))
        if casa.get("indirizzo") == config.CASA_INDIRIZZO:
            return casa
    return None


def salva_casa(casa):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.FILE_CASA_PRIVATA.write_text(
        json.dumps(casa, indent=1, ensure_ascii=False), encoding="utf-8"
    )


def _cache_ancora_valida(voce):
    """Un tempo di viaggio calcolato piu' di 30 giorni fa va rifatto."""
    if not voce or not voce.get("aggiornato"):
        return False
    try:
        quando = date.fromisoformat(voce["aggiornato"])
    except ValueError:
        return False
    if voce.get("mezzi") is None and voce.get("errore"):
        # Se l'ultima volta e' andata male riproviamo dopo 3 giorni, non dopo 30.
        return (date.today() - quando).days < 3
    return (date.today() - quando).days < config.GIORNI_VALIDITA_CACHE_VIAGGI


# --------------------------------------------------------------------------
# Orario di arrivo
# --------------------------------------------------------------------------
def prossimo_arrivo_scolastico():
    """
    Restituisce il momento in cui vuoi essere a scuola: le 8:00 del prossimo
    giorno feriale (se oggi e' venerdi' pomeriggio, sara' lunedi').

    Lo diamo a Google in formato UTC, come vuole lui.
    """
    fuso = ZoneInfo(config.FUSO_ORARIO)
    momento = datetime.now(fuso) + timedelta(days=1)
    while momento.weekday() >= 5:          # 5 = sabato, 6 = domenica
        momento += timedelta(days=1)
    momento = momento.replace(hour=config.ORA_ARRIVO, minute=0, second=0, microsecond=0)
    return momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Chiamate a Google
# --------------------------------------------------------------------------
def _chiamata_con_ritenti(funzione, tentativi=3):
    """Riprova qualche volta se Google e' momentaneamente occupato."""
    for numero in range(tentativi):
        try:
            risposta = funzione()
        except requests.RequestException as errore:
            if numero == tentativi - 1:
                raise
            time.sleep(2 ** numero)
            continue
        if risposta.status_code in (429, 500, 502, 503, 504) and numero < tentativi - 1:
            time.sleep(2 ** numero)
            continue
        return risposta
    raise RuntimeError("Google non risponde")


def geocodifica(indirizzo, chiave):
    """Indirizzo scritto -> coordinate (latitudine, longitudine)."""
    risposta = _chiamata_con_ritenti(lambda: requests.get(
        URL_GEOCODING,
        params={"address": indirizzo, "key": chiave, "region": "it", "language": "it"},
        timeout=30,
    ))
    dati = risposta.json()
    if dati.get("status") != "OK" or not dati.get("results"):
        raise RuntimeError(f"indirizzo non trovato ({dati.get('status')}): {indirizzo}")
    primo = dati["results"][0]
    posizione = primo["geometry"]["location"]
    return {
        "lat": posizione["lat"],
        "lng": posizione["lng"],
        "indirizzo_google": primo.get("formatted_address", indirizzo),
        "precisione": primo["geometry"].get("location_type", ""),
    }


def geocodifica_openstreetmap(indirizzo):
    """
    Trova le coordinate senza bisogno di nessuna chiave (servizio di OpenStreetMap).

    E' meno preciso di Google e ha una regola precisa: massimo una richiesta al
    secondo. Lo usiamo solo per far comparire i segnaposto sulla mappa finche'
    non configuri la chiave Google.
    """
    risposta = _chiamata_con_ritenti(lambda: requests.get(
        URL_NOMINATIM,
        params={"q": indirizzo, "format": "json", "limit": 1, "countrycodes": "it"},
        headers={"User-Agent": config.USER_AGENT},
        timeout=30,
    ))
    dati = risposta.json() if risposta.ok else []
    if not dati:
        raise RuntimeError(f"indirizzo non trovato su OpenStreetMap: {indirizzo}")
    return {
        "lat": float(dati[0]["lat"]),
        "lng": float(dati[0]["lon"]),
        "indirizzo_google": dati[0].get("display_name", indirizzo),
        "precisione": "OSM_" + str(dati[0].get("type", "")),
    }


def _comune_da_indirizzo(indirizzo):
    """
    Da "Via Roma 3, 10015 Ivrea, Italia" ricava "Ivrea, Italia".

    Serve come ripiego: se non troviamo il civico esatto, mettiamo almeno il
    segnaposto al centro del paese invece di far sparire la scuola dalla mappa.
    """
    pezzi = [p.strip() for p in indirizzo.split(",")]
    if len(pezzi) < 2:
        return None
    comune = re.sub(r"^\d{5}\s*", "", pezzi[-2]).strip()
    return f"{comune}, Italia" if comune else None


def _geocodifica_con_ripiego(indirizzo, funzione):
    """
    Prova a geocodificare l'indirizzo preciso; se fallisce, ripiega sul comune.

    Restituisce anche "approssimativo": la app lo usa per avvisare che quel
    segnaposto e' il centro del paese, non la scuola esatta.
    """
    try:
        risultato = funzione(indirizzo)
        risultato["approssimativo"] = False
        return risultato
    except Exception:
        comune = _comune_da_indirizzo(indirizzo)
        if not comune:
            raise
        time.sleep(1.0)
        risultato = funzione(comune)
        risultato["approssimativo"] = True
        return risultato


def solo_coordinate(indirizzi):
    """
    Riempie le coordinate mancanti usando OpenStreetMap (senza chiave Google).

    Serve per avere subito la mappa funzionante: i tempi di viaggio restano
    vuoti e verranno calcolati appena imposti GOOGLE_MAPS_API_KEY.
    """
    cache = carica_cache()
    da_fare = [i for i in sorted(set(indirizzi))
               if not (cache["destinazioni"].get(i) or {}).get("lat")]

    if config.CASA_INDIRIZZO and not carica_casa():
        casa = geocodifica_openstreetmap(config.CASA_INDIRIZZO)
        casa["indirizzo"] = config.CASA_INDIRIZZO
        salva_casa(casa)
        time.sleep(1.1)

    if not da_fare:
        print("   coordinate: gia' tutte presenti")
        return cache["destinazioni"]

    print(f"   cerco le coordinate di {len(da_fare)} sedi su OpenStreetMap "
          f"(circa {round(len(da_fare) * 1.2 / 60) + 1} minuti)")
    for numero, indirizzo in enumerate(da_fare, start=1):
        voce = dict(cache["destinazioni"].get(indirizzo) or {})
        try:
            voce.update(_geocodifica_con_ripiego(indirizzo, geocodifica_openstreetmap))
            voce.setdefault("mezzi", None)
            voce.setdefault("auto", None)
            # Non segniamo la data: cosi' quando arrivera' la chiave Google
            # questi indirizzi verranno comunque ricalcolati per intero.
            print(f"   [{numero}/{len(da_fare)}] ok   {indirizzo[:60]}")
        except Exception as errore:
            voce["errore"] = str(errore)[:200]
            print(f"   [{numero}/{len(da_fare)}] no   {indirizzo[:50]} -> {errore}")
        cache["destinazioni"][indirizzo] = voce
        salva_cache(cache)
        time.sleep(1.1)          # regola d'uso di OpenStreetMap: 1 richiesta al secondo

    return cache["destinazioni"]


def _punto(coordinate):
    return {"location": {"latLng": {"latitude": coordinate["lat"], "longitude": coordinate["lng"]}}}


def percorso_mezzi(casa, scuola, chiave, arrivo):
    """Percorso coi mezzi pubblici, calcolato per arrivare entro le 8:00."""
    corpo = {
        "origin": _punto(casa),
        "destination": _punto(scuola),
        "travelMode": "TRANSIT",
        "arrivalTime": arrivo,
        "computeAlternativeRoutes": False,
        "languageCode": "it-IT",
        "units": "METRIC",
    }

    def invia(campi):
        return requests.post(
            URL_ROTTE,
            json=corpo,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": chiave,
                "X-Goog-FieldMask": campi,
            },
            timeout=40,
        )

    risposta = _chiamata_con_ritenti(lambda: invia(CAMPI_TRANSIT))
    if risposta.status_code == 400:
        # Alcune chiavi/progetti non danno i dettagli delle linee: ripieghiamo
        # sulla richiesta minima (durata e distanza), che basta per il ranking.
        risposta = _chiamata_con_ritenti(lambda: invia(CAMPI_MINIMI))
    if not risposta.ok:
        raise RuntimeError(f"Routes API {risposta.status_code}: {risposta.text[:200]}")

    rotte = risposta.json().get("routes") or []
    if not rotte:
        return None  # nessun collegamento coi mezzi a quell'ora
    rotta = rotte[0]

    # Le linee usate (bus 4, metro, treno...) e quanti cambi servono.
    linee, mezzi_usati = [], 0
    for tappa in rotta.get("legs", []):
        for passo in tappa.get("steps", []):
            if passo.get("travelMode") != "TRANSIT":
                continue
            mezzi_usati += 1
            dettagli = passo.get("transitDetails", {}).get("transitLine", {})
            nome = dettagli.get("nameShort")
            tipo = (dettagli.get("vehicle") or {}).get("type", "")
            if nome:
                linee.append({"nome": nome, "tipo": tipo})

    return {
        "minuti": round(int(str(rotta["duration"]).rstrip("s")) / 60),
        "km": round(rotta.get("distanceMeters", 0) / 1000, 1),
        "cambi": max(mezzi_usati - 1, 0),
        "linee": linee,
    }


def percorso_auto(casa, scuola, chiave):
    """Percorso in auto: serve soprattutto per i chilometri di strada."""
    corpo = {
        "origin": _punto(casa),
        "destination": _punto(scuola),
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_UNAWARE",
        "computeAlternativeRoutes": False,
        "languageCode": "it-IT",
        "units": "METRIC",
    }
    risposta = _chiamata_con_ritenti(lambda: requests.post(
        URL_ROTTE,
        json=corpo,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": chiave,
            "X-Goog-FieldMask": CAMPI_MINIMI,
        },
        timeout=40,
    ))
    if not risposta.ok:
        raise RuntimeError(f"Routes API {risposta.status_code}: {risposta.text[:200]}")
    rotte = risposta.json().get("routes") or []
    if not rotte:
        return None
    rotta = rotte[0]
    return {
        "minuti": round(int(str(rotta["duration"]).rstrip("s")) / 60),
        "km": round(rotta.get("distanceMeters", 0) / 1000, 1),
    }


# --------------------------------------------------------------------------
# Funzione principale
# --------------------------------------------------------------------------
def aggiorna_viaggi(indirizzi):
    """
    Dati tutti gli indirizzi che servono, restituisce il dizionario
    indirizzo -> {minuti coi mezzi, km, cambi, ...}.

    Calcola SOLO quelli non ancora in cache (o scaduti). Se la chiave di Google
    non c'e', restituisce quello che ha in cache senza bloccare nulla.
    """
    cache = carica_cache()
    chiave = chiave_api()
    indirizzi = sorted(set(indirizzi))

    if not config.CASA_INDIRIZZO:
        print("   ATTENZIONE: non so dove sia casa, quindi niente tempi di viaggio.")
        print("   Crea un file casa.txt con dentro l'indirizzo (vedi il README),")
        print("   oppure imposta il segreto CASA_INDIRIZZO su GitHub.")
        return solo_coordinate(indirizzi)

    da_calcolare = [i for i in indirizzi if not _cache_ancora_valida(cache["destinazioni"].get(i))]

    if not chiave:
        if da_calcolare:
            print(f"   manca GOOGLE_MAPS_API_KEY: niente tempi di viaggio per {len(da_calcolare)} sedi.")
            print("   ripiego su OpenStreetMap per avere almeno i segnaposto sulla mappa.")
            return solo_coordinate(indirizzi)
        return cache["destinazioni"]

    # Casa la geocodifichiamo una volta sola e non cambia mai.
    casa = carica_casa()
    if not casa:
        print("   trovo la posizione di casa")
        casa = geocodifica(config.CASA_INDIRIZZO, chiave)
        casa["indirizzo"] = config.CASA_INDIRIZZO
        salva_casa(casa)

    if not da_calcolare:
        print(f"   tempi di viaggio: tutti gia' in cache ({len(indirizzi)} sedi)")
        return cache["destinazioni"]

    arrivo = prossimo_arrivo_scolastico()
    print(f"   calcolo {len(da_calcolare)} percorsi (arrivo entro {arrivo} UTC)")

    for numero, indirizzo in enumerate(da_calcolare, start=1):
        voce = dict(cache["destinazioni"].get(indirizzo) or {})
        try:
            if "lat" not in voce:
                voce.update(_geocodifica_con_ripiego(
                    indirizzo, lambda posto: geocodifica(posto, chiave)))
            voce["mezzi"] = percorso_mezzi(casa, voce, chiave, arrivo)
            voce["auto"] = percorso_auto(casa, voce, chiave)
            voce["errore"] = None
            minuti = voce["mezzi"]["minuti"] if voce["mezzi"] else "-"
            print(f"   [{numero}/{len(da_calcolare)}] {minuti} min  {indirizzo[:60]}")
        except Exception as errore:      # non deve mai fermare tutto il programma
            voce.setdefault("mezzi", None)
            voce.setdefault("auto", None)
            voce["errore"] = str(errore)[:200]
            print(f"   [{numero}/{len(da_calcolare)}] ERRORE  {indirizzo[:50]} -> {errore}")

        voce["aggiornato"] = date.today().isoformat()
        cache["destinazioni"][indirizzo] = voce
        salva_cache(cache)               # salviamo mano a mano: se si interrompe non perdiamo nulla
        time.sleep(0.12)                 # un attimo di respiro tra una chiamata e l'altra

    return cache["destinazioni"]


if __name__ == "__main__":
    if not chiave_api():
        print("Manca la chiave. Nel terminale, prima di lanciare:")
        print('   $env:GOOGLE_MAPS_API_KEY = "la-tua-chiave"   (PowerShell)')
        sys.exit(1)
    prova = sys.argv[1] if len(sys.argv) > 1 else "Via Ponchielli 56, 10154 Torino, Italia"
    risultato = aggiorna_viaggi([prova])
    print(json.dumps(risultato.get(prova), indent=2, ensure_ascii=False))
