"""
Crea le icone della app (quelle che vedi sulla schermata home del telefono).

Si lancia una volta sola:
    python scripts/make_icons.py

Disegna un segnaposto da mappa bianco su sfondo blu: e' il simbolo del
progetto, "dove sono le scuole rispetto a casa".
Serve la libreria Pillow:  pip install pillow
"""

from PIL import Image, ImageDraw

import config

SFONDO_ALTO = (43, 86, 212)      # blu della app
SFONDO_BASSO = (26, 55, 150)     # blu piu' scuro, per la sfumatura
BIANCO = (255, 255, 255)


def disegna(lato, margine_percentuale=0.18, angoli_tondi=True):
    """Disegna l'icona a una certa dimensione e la restituisce."""
    # Lavoriamo 4 volte piu' grandi e poi rimpiccioliamo: cosi' i bordi
    # vengono lisci invece che seghettati.
    grande = lato * 4
    immagine = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))
    disegno = ImageDraw.Draw(immagine)

    # Sfondo con sfumatura verticale
    for y in range(grande):
        parte = y / grande
        colore = tuple(
            round(SFONDO_ALTO[i] + (SFONDO_BASSO[i] - SFONDO_ALTO[i]) * parte)
            for i in range(3)
        )
        disegno.line([(0, y), (grande, y)], fill=colore)

    if angoli_tondi:
        # Ritagliamo gli angoli arrotondati (stile iOS)
        maschera = Image.new("L", (grande, grande), 0)
        ImageDraw.Draw(maschera).rounded_rectangle(
            [0, 0, grande - 1, grande - 1], radius=int(grande * 0.22), fill=255
        )
        immagine.putalpha(maschera)

    # Il segnaposto: un cerchio con sotto una punta triangolare
    centro_x = grande / 2
    raggio = grande * (0.5 - margine_percentuale) * 0.62
    centro_y = grande * 0.42
    disegno.ellipse(
        [centro_x - raggio, centro_y - raggio, centro_x + raggio, centro_y + raggio],
        fill=BIANCO,
    )
    disegno.polygon(
        [(centro_x - raggio * 0.72, centro_y + raggio * 0.72),
         (centro_x + raggio * 0.72, centro_y + raggio * 0.72),
         (centro_x, centro_y + raggio * 2.05)],
        fill=BIANCO,
    )
    # Il "buco" del segnaposto, colorato come lo sfondo
    buco = raggio * 0.38
    disegno.ellipse(
        [centro_x - buco, centro_y - buco, centro_x + buco, centro_y + buco],
        fill=SFONDO_ALTO,
    )

    return immagine.resize((lato, lato), Image.LANCZOS)


def main():
    cartella = config.DOCS_DIR / "icons"
    cartella.mkdir(parents=True, exist_ok=True)

    disegna(192).save(cartella / "icon-192.png")
    disegna(512).save(cartella / "icon-512.png")
    disegna(180).save(cartella / "apple-touch-icon.png")
    # L'icona "maskable" di Android viene ritagliata a cerchio dal telefono:
    # va disegnata piu' piccola e senza angoli arrotondati.
    disegna(512, margine_percentuale=0.30, angoli_tondi=False).save(cartella / "icon-maskable.png")

    print(f"Icone create in {cartella}")


if __name__ == "__main__":
    main()
