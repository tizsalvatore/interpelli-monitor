"""
Impostazioni centrali del progetto.

Se un giorno vuoi cambiare casa, aggiungere una classe di concorso o spostare
l'orario di arrivo a scuola, questo e' l'UNICO file che devi toccare.

NOTA SULLA PRIVACY: l'indirizzo di casa NON si scrive qui dentro, perche'
questo file finisce su GitHub e sarebbe leggibile da chiunque. Vedi piu' sotto.
"""

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Cartelle del progetto
# --------------------------------------------------------------------------
# ROOT = la cartella "Interpelli Monitor" (questo file sta in ROOT/scripts/)
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"          # file di lavoro (cache): non li guarda nessuno
DOCS_DIR = ROOT / "docs"          # la app vera e propria (quella pubblicata online)
DOCS_DATA_DIR = DOCS_DIR / "data"  # i dati che la app legge

# File usati dagli script
FILE_INTERPELLI_HTML = DATA_DIR / "ultima_pagina.html"      # copia grezza del sito
FILE_ANAGRAFICA_MODELLO = "anagrafica_scuole_{codice}.csv"  # elenco scuole del Ministero
FILE_CACHE_VIAGGI = DATA_DIR / "cache_viaggi.json"          # tempi gia' calcolati (per non ricalcolarli)
FILE_CASA_PRIVATA = DATA_DIR / "casa_privata.json"          # coordinate di casa: NON va su GitHub
FILE_CASA_VISIBILE = DATA_DIR / "casa_visibile.json"        # posizione del segnaposto sulla mappa (pubblica)
FILE_GIA_NOTIFICATI = DATA_DIR / "gia_notificati.json"      # id degli interpelli gia' segnalati
FILE_APP_DATI = DOCS_DATA_DIR / "interpelli.json"           # <-- il file che legge la app

# --------------------------------------------------------------------------
# Sorgenti dei dati
# --------------------------------------------------------------------------
INTERPELLI_URL = "https://servizi.istruzionepiemonte.it/interpello2025/ric_interpello_ambito_to.php"

# Anagrafica scuole statali del Ministero (serve per avere gli INDIRIZZI, che il
# sito degli interpelli non fornisce). Il nome del file cambia ogni anno
# scolastico, quindi ne proviamo diversi partendo dal piu' recente.
ANAGRAFICA_URL_BASE = "https://dati.istruzione.it/opendata/opendata/catalogo/elements1/SCUANAGRAFESTAT{codice}.csv"
PROVINCIA = "TORINO"

# Quanti anni scolastici di anagrafica unire, partendo dal piu' recente.
# Serve perche' il file dell'anno in corso a volte e' incompleto: le scuole che
# mancano le recuperiamo da quello dell'anno prima.
ANNI_ANAGRAFICA = 2

# --------------------------------------------------------------------------
# Casa: il punto da cui si calcolano distanze e tempi
# --------------------------------------------------------------------------
# L'indirizzo non sta scritto qui: viene letto da fuori, cosi' resta privato
# anche se il progetto e' pubblico su GitHub. Due modi, si prova il primo:
#
#   1. sul tuo computer -> file "casa.txt" nella cartella del progetto,
#      con dentro solo l'indirizzo (il file e' escluso da GitHub)
#   2. su GitHub -> Settings > Secrets and variables > Actions > New secret
#      con nome CASA_INDIRIZZO
#
def _leggi_indirizzo_casa():
    dalla_variabile = os.environ.get("CASA_INDIRIZZO", "").strip()
    if dalla_variabile:
        return dalla_variabile

    file_casa = ROOT / "casa.txt"
    if file_casa.exists():
        for riga in file_casa.read_text(encoding="utf-8").splitlines():
            riga = riga.strip()
            if riga and not riga.startswith("#"):
                return riga
    return ""      # vuoto = i tempi di viaggio non si possono calcolare


CASA_INDIRIZZO = _leggi_indirizzo_casa()
CASA_ETICHETTA = "Casa"     # come viene chiamata dentro la app

# Dove mettere il segnaposto "Casa" sulla mappa.
# ATTENZIONE: questo indirizzo e' PUBBLICO (finisce nel file che legge la app),
# quindi di solito ci si mette un civico vicino, non il proprio. I calcoli di
# km e minuti non lo usano: quelli partono sempre da CASA_INDIRIZZO.
# Lascia "" per non avere il segnaposto e usare invece la regola qui sotto.
CASA_INDIRIZZO_VISIBILE = "Via Genova 213, 10127 Torino TO, Italia"

# Quanto della posizione di casa finisce nel file pubblicato online:
#   "nascosta"    -> niente: nessun segnaposto di casa sulla mappa
#   "approssimata"-> coordinate arrotondate (circa 1 km): il segnaposto c'e',
#                    ma l'indirizzo esatto non e' ricavabile   <- consigliato
#   "esatta"      -> indirizzo e coordinate precise (solo se il progetto e' privato)
#
# In tutti i casi i minuti e i km restano precisi: sono calcolati dal computer
# di GitHub partendo dall'indirizzo vero, che non viene mai pubblicato.
PRECISIONE_CASA_PUBBLICA = "approssimata"

# A che ora vuoi ESSERE a scuola. Il tempo di viaggio viene calcolato
# "a ritroso": Google cerca la corsa che ti fa arrivare entro quest'ora.
ORA_ARRIVO = 8   # 8:00 del mattino
FUSO_ORARIO = "Europe/Rome"

# --------------------------------------------------------------------------
# Classi di concorso che ti interessano
# --------------------------------------------------------------------------
# chiave = codice usato dal sito, valore = nome esteso mostrato nella app
CLASSI_DI_CONCORSO = {
    "A027": "Matematica e Fisica",
    "A020": "Fisica",
    "A026": "Matematica",
    "A040": "Scienze e tecnologie elettriche ed elettroniche",
    "A041": "Scienze e tecnologie informatiche",
    "A047": "Scienze matematiche applicate",
    "A060": "Tecnologia nella scuola secondaria di I grado",
}

# In quale tipo di scuola si insegna ogni classe di concorso.
# Serve per mostrare, nel dettaglio, solo i plessi sensati: per A060 (tecnologia
# alle medie) non ha senso elencare il liceo, e viceversa.
GRADO_PER_CLASSE = {
    "A060": "I_GRADO",     # scuola secondaria di primo grado (medie)
    "_default": "II_GRADO",  # tutte le altre: superiori
}

# --------------------------------------------------------------------------
# Impostazioni delle notifiche (Telegram / email)
# --------------------------------------------------------------------------
# Vieni avvisato solo per gli interpelli che rispettano QUESTI criteri.
# Sono volutamente piu' larghi dei filtri della app: meglio una notifica in piu'
# che perdere un'occasione.
NOTIFICA_CLASSI = list(CLASSI_DI_CONCORSO.keys())  # tutte e 7
NOTIFICA_CORSI = ["Diurno", "Serale"]              # metti [] per accettare qualsiasi corso
NOTIFICA_MAX_MINUTI = 60                           # None = nessun limite di distanza

# --------------------------------------------------------------------------
# Varie
# --------------------------------------------------------------------------
# Ogni quanti giorni ricalcolare un tempo di viaggio gia' in cache.
# I tempi cambiano poco (cambio orario GTT), 30 giorni e' un buon compromesso.
GIORNI_VALIDITA_CACHE_VIAGGI = 30

# User-Agent "gentile": ci presentiamo al sito invece di sembrare un bot anonimo.
USER_AGENT = "InterpelliMonitor/1.0 (progetto personale di monitoraggio interpelli)"
