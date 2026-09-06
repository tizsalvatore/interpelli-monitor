"""
Crea le icone della app (quelle che vedi sulla schermata home del telefono).

Si lancia una volta sola, o quando vuoi cambiare il disegno:
    python scripts/make_icons.py

Disegna un libro aperto bianco su sfondo blu.
Il disegno e' volutamente essenziale: sulla home di un telefono l'icona e'
grande poco piu' di un'unghia, e i dettagli fini diventano poltiglia.

Serve la libreria Pillow:  pip install pillow
"""

from PIL import Image, ImageDraw

import config

SFONDO_ALTO = (43, 86, 212)      # blu della app
SFONDO_BASSO = (26, 55, 150)     # blu piu' scuro, per la sfumatura
BIANCO = (255, 255, 255)
ARDESIA = (20, 42, 110)          # il "verde lavagna", qui in blu scuro per
                                 # restare in tinta con lo sfondo
RIPIANO = (188, 203, 240)        # il portagessi: azzurrino, cosi' il gesso
                                 # bianco appoggiato sopra si vede


def disegna(lato, margine=0.10, angoli_tondi=True):
    """
    Disegna l'icona a una certa dimensione e la restituisce.

    "margine" e' lo spazio vuoto lasciato attorno al disegno: serve per le
    icone che Android ritaglia a cerchio, dove i bordi vengono mangiati.
    """
    # Lavoriamo 4 volte piu' grandi e poi rimpiccioliamo: cosi' i bordi
    # vengono lisci invece che seghettati.
    grande = lato * 4
    immagine = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))
    disegno = ImageDraw.Draw(immagine)

    # --- sfondo con sfumatura verticale
    for y in range(grande):
        parte = y / grande
        colore = tuple(
            round(SFONDO_ALTO[i] + (SFONDO_BASSO[i] - SFONDO_ALTO[i]) * parte)
            for i in range(3)
        )
        disegno.line([(0, y), (grande, y)], fill=colore)

    if angoli_tondi:
        maschera = Image.new("L", (grande, grande), 0)
        ImageDraw.Draw(maschera).rounded_rectangle(
            [0, 0, grande - 1, grande - 1], radius=int(grande * 0.22), fill=255
        )
        immagine.putalpha(maschera)

    # --- l'area dentro cui sta il disegno vero e proprio
    utile = grande * (1 - 2 * margine)
    origine = (grande - utile) / 2

    def area(x1, y1, x2, y2):
        """Da coordinate 0..1 dentro l'area utile a pixel veri."""
        return [origine + x1 * utile, origine + y1 * utile,
                origine + x2 * utile, origine + y2 * utile]

    # --- un libro aperto, visto di tre quarti: due pagine che si alzano
    #     verso il centro. La sagoma "a farfalla" e' inconfondibile, mentre
    #     una lavagna a questa dimensione somiglia troppo a uno schermo.
    def punti(coppie):
        return [(origine + x * utile, origine + y * utile) for x, y in coppie]

    # pagina sinistra e destra (il centro resta vuoto: e' la costa del libro)
    disegno.polygon(punti([(0.02, 0.26), (0.46, 0.13), (0.46, 0.87), (0.02, 0.74)]),
                    fill=BIANCO)
    disegno.polygon(punti([(0.98, 0.26), (0.54, 0.13), (0.54, 0.87), (0.98, 0.74)]),
                    fill=BIANCO)

    # --- righe di testo sulle pagine, per non lasciarle due macchie bianche
    for riga in (0.34, 0.47, 0.60):
        disegno.line(punti([(0.10, riga + 0.02), (0.39, riga - 0.055)]),
                     fill=ARDESIA, width=max(2, int(utile * 0.028)))
        disegno.line(punti([(0.61, riga - 0.055), (0.90, riga + 0.02)]),
                     fill=ARDESIA, width=max(2, int(utile * 0.028)))

    return immagine.resize((lato, lato), Image.LANCZOS)


def main():
    cartella = config.DOCS_DIR / "icons"
    cartella.mkdir(parents=True, exist_ok=True)

    disegna(192).save(cartella / "icon-192.png")
    disegna(512).save(cartella / "icon-512.png")
    disegna(180).save(cartella / "apple-touch-icon.png")
    # L'icona "maskable" di Android viene ritagliata a cerchio dal telefono:
    # va disegnata piu' piccola e senza angoli arrotondati.
    disegna(512, margine=0.26, angoli_tondi=False).save(cartella / "icon-maskable.png")

    print(f"Icone create in {cartella}")


if __name__ == "__main__":
    main()
