"""
PASSO 5 - Avvisarti quando esce un interpello nuovo.

Confronta gli interpelli aperti di adesso con quelli gia' visti l'ultima volta
(data/gia_notificati.json) e ti manda un messaggio solo per le NOVITA'.

Quali novita'? Quelle che corrispondono alle tue RICERCHE SALVATE, che leggiamo
da docs/data/ricerche.json (lo stesso file che la app ti fa copiare dalla
schermata "Ricerche"). Se quel file non c'e', usiamo i criteri scritti in
config.py.

Funziona con Telegram (consigliato) e/o via email. Se non configuri niente,
questo file non fa nulla e la app continua a funzionare normalmente.

Variabili da impostare (vedi il README):
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_UTENTE, EMAIL_PASSWORD, EMAIL_DESTINATARIO
"""

import json
import os
import smtplib
from datetime import date
from email.message import EmailMessage

import requests

import config

URL_APP = os.environ.get("URL_APP", "").strip()   # link alla app, incluso nel messaggio
FILE_RICERCHE = config.DOCS_DATA_DIR / "ricerche.json"


# --------------------------------------------------------------------------
# Le tue ricerche salvate
# --------------------------------------------------------------------------
def carica_ricerche():
    """
    Legge le ricerche salvate dalla app.

    Ogni ricerca ha questa forma:
        {"nome": "A027 vicino a casa", "notifiche": true,
         "filtri": {"stato": ["aperto"], "classi": ["A027"], "corso": ["Diurno"],
                    "tipo": [], "maxMinuti": 30}}
    """
    if FILE_RICERCHE.exists():
        try:
            dati = json.loads(FILE_RICERCHE.read_text(encoding="utf-8"))
            ricerche = [r for r in dati.get("ricerche", []) if r.get("notifiche")]
            if ricerche:
                return ricerche
        except json.JSONDecodeError:
            print("   ricerche.json non e' scritto bene: uso i criteri di config.py")

    # Ripiego: i criteri generici scritti in config.py
    return [{
        "nome": "Predefinita",
        "notifiche": True,
        "filtri": {
            "stato": ["aperto"],
            "classi": config.NOTIFICA_CLASSI,
            "corso": config.NOTIFICA_CORSI,
            "tipo": [],
            "maxMinuti": config.NOTIFICA_MAX_MINUTI,
        },
    }]


def _corrisponde(interpello, filtri):
    """Dice se un interpello rientra in una ricerca salvata."""
    if interpello["stato"] != "aperto" or interpello.get("scaduto"):
        return False
    if filtri.get("classi") and interpello["classe"] not in filtri["classi"]:
        return False
    if filtri.get("corso") and interpello["corso"] not in filtri["corso"]:
        return False
    if filtri.get("tipo") and interpello["tipo_cattedra"] not in filtri["tipo"]:
        return False
    if filtri.get("durata") and interpello.get("durata_tipo") not in filtri["durata"]:
        return False
    limite = filtri.get("maxMinuti")
    minuti = interpello.get("minuti")
    # Se non sappiamo quanto dista, meglio avvisare comunque che perderlo.
    if limite is not None and minuti is not None and minuti > limite:
        return False
    return True


def interpelli_da_notificare(dati_app, ricerche):
    """
    Restituisce {nome ricerca: [interpelli]} per tutti gli aperti che
    corrispondono ad almeno una ricerca.
    """
    risultato = {}
    for ricerca in ricerche:
        trovati = [i for i in dati_app["interpelli"]
                   if _corrisponde(i, ricerca.get("filtri", {}))]
        if trovati:
            risultato[ricerca.get("nome", "Ricerca")] = trovati
    return risultato


# --------------------------------------------------------------------------
# Memoria di cosa e' gia' stato notificato
# --------------------------------------------------------------------------
def _carica_gia_notificati():
    if config.FILE_GIA_NOTIFICATI.exists():
        try:
            return json.loads(config.FILE_GIA_NOTIFICATI.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return None       # None = e' la primissima volta che gira


def _salva_gia_notificati(memoria):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.FILE_GIA_NOTIFICATI.write_text(
        json.dumps(memoria, indent=1, ensure_ascii=False), encoding="utf-8"
    )


# --------------------------------------------------------------------------
# Come si presenta il messaggio
# --------------------------------------------------------------------------
def _riga_messaggio(interpello):
    pezzi = [f"<b>{interpello['classe']} - {interpello['classe_nome']}</b>",
             interpello["scuola"]]
    if interpello.get("minuti") is not None:
        # In italiano i decimali si scrivono con la virgola: 8,1 km
        km = f" · {str(interpello['km']).replace('.', ',')} km" if interpello.get("km") else ""
        pezzi.append(f"🚌 {interpello['minuti']} min da casa{km}")
    else:
        pezzi.append("🚌 distanza non disponibile")
    pezzi.append(f"📅 dal {interpello['data_interpello_testo']}"
                 f" · scade il {interpello['data_scadenza_testo'] or 'n.d.'}")
    dettagli = [interpello["durata"], interpello["corso"], interpello["tipo_cattedra"]]
    if interpello.get("ore_spezzone"):
        dettagli.append(f"{interpello['ore_spezzone']} ore")
    pezzi.append("📄 " + " · ".join(d for d in dettagli if d))
    return "\n".join(pezzi)


def _componi_messaggio(per_ricerca, quanti_totali):
    titolo = ("🔔 1 nuovo interpello" if quanti_totali == 1
              else f"🔔 {quanti_totali} nuovi interpelli")
    righe = [titolo, ""]
    for nome_ricerca, interpelli in per_ricerca.items():
        righe.append(f"— <i>{nome_ricerca}</i> —")
        righe.append("")
        for interpello in interpelli[:8]:
            righe.append(_riga_messaggio(interpello))
            righe.append("")
        if len(interpelli) > 8:
            righe.append(f"…e altri {len(interpelli) - 8}.")
            righe.append("")
    if URL_APP:
        righe.append(f'👉 <a href="{URL_APP}">Apri Interpelli Monitor</a>')
    return "\n".join(righe)


# --------------------------------------------------------------------------
# Invio
# --------------------------------------------------------------------------
def _manda_telegram(testo):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return False
    risposta = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": testo, "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=30,
    )
    if not risposta.ok:
        print(f"   Telegram ha risposto {risposta.status_code}: {risposta.text[:150]}")
        return False
    print("   notifica Telegram inviata")
    return True


def _manda_email(oggetto, testo_html):
    host = os.environ.get("EMAIL_SMTP_HOST", "").strip()
    utente = os.environ.get("EMAIL_UTENTE", "").strip()
    password = os.environ.get("EMAIL_PASSWORD", "").strip()
    destinatario = os.environ.get("EMAIL_DESTINATARIO", "").strip() or utente
    if not (host and utente and password and destinatario):
        return False

    porta = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    messaggio = EmailMessage()
    messaggio["Subject"] = oggetto
    messaggio["From"] = utente
    messaggio["To"] = destinatario
    messaggio.set_content("Apri questa email in HTML per leggere gli interpelli.")
    messaggio.add_alternative(testo_html.replace("\n", "<br>"), subtype="html")

    with smtplib.SMTP(host, porta, timeout=30) as server:
        server.starttls()
        server.login(utente, password)
        server.send_message(messaggio)
    print("   notifica email inviata")
    return True


# --------------------------------------------------------------------------
# Funzione principale (la chiama build.py)
# --------------------------------------------------------------------------
def avvisa_se_ci_sono_novita(dati_app):
    ricerche = carica_ricerche()
    print(f"   ricerche attive per le notifiche: {[r['nome'] for r in ricerche]}")

    per_ricerca = interpelli_da_notificare(dati_app, ricerche)
    tutti_interessanti = {i["id"]: i for gruppo in per_ricerca.values() for i in gruppo}
    memoria = _carica_gia_notificati()

    if memoria is None:
        # Prima esecuzione: registriamo la situazione attuale SENZA mandare
        # niente, altrimenti riceveresti un messaggio con tutto l'arretrato.
        _salva_gia_notificati({identificativo: date.today().isoformat()
                               for identificativo in tutti_interessanti})
        print(f"   prima esecuzione: memorizzati {len(tutti_interessanti)} interpelli aperti, "
              "nessuna notifica inviata")
        return []

    # Teniamo solo le novita', ricerca per ricerca.
    nuovi_per_ricerca = {}
    for nome, interpelli in per_ricerca.items():
        nuovi = [i for i in interpelli if i["id"] not in memoria]
        if nuovi:
            nuovi_per_ricerca[nome] = nuovi

    identificativi_nuovi = {i["id"] for gruppo in nuovi_per_ricerca.values() for i in gruppo}
    if not identificativi_nuovi:
        print("   nessun interpello nuovo")
        return []

    testo = _componi_messaggio(nuovi_per_ricerca, len(identificativi_nuovi))
    titolo = f"{len(identificativi_nuovi)} nuovi interpelli"

    inviato = _manda_telegram(testo)
    inviato = _manda_email(f"🔔 {titolo}", testo) or inviato

    if not inviato:
        print("   nessun canale di notifica configurato (Telegram/email): salto")
        return list(identificativi_nuovi)

    for identificativo in identificativi_nuovi:
        memoria[identificativo] = date.today().isoformat()
    _salva_gia_notificati(memoria)
    print(f"   notificati {len(identificativi_nuovi)} nuovi interpelli")
    return list(identificativi_nuovi)


if __name__ == "__main__":
    dati = json.loads(config.FILE_APP_DATI.read_text(encoding="utf-8"))
    avvisa_se_ci_sono_novita(dati)
