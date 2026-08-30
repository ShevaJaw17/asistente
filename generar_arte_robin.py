# generar_arte_robin.py - Produce el "arte fuente" por capas de Robin
# (lista para riggear en Umamo/Krita/PSD): cuerpo, torso, cabeza, ojos y boca.
# Salidas:
#   assets/robin/arte_capas/robina_layered.psd   (capas con transparencia)
#   assets/robin/arte_capas/*.png                (cada capa como PNG alineado)
import os
from PIL import Image

from psd_tools import PSDImage

BASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "robin", "robin_avatar.png"
)
SALIDA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "robin", "arte_capas"
)

ANCHO, ALTO = 258, 520
Y_CUELLO, Y_CINTURA = 140, 260
OJO_I = (103.2, 55.1)
OJO_D = (142.5, 60.1)
BOCA = (106.07, 126.72)


def _banda(orig, y0, y1):
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    capa.paste(orig.crop((0, y0, ANCHO, y1)), (0, y0))
    return capa


def _parche(orig, cx, cy, dx, dy):
    x0, y0 = max(0, int(cx) - dx), max(0, int(cy) - dy)
    x1, y1 = min(ANCHO, int(cx) + dx), min(ALTO, int(cy) + dy)
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    capa.paste(orig.crop((x0, y0, x1, y1)), (x0, y0))
    return capa


def main():
    os.makedirs(SALIDA, exist_ok=True)
    orig = Image.open(BASE).convert("RGBA")

    capas = [
        ("Boca", _parche(orig, BOCA[0], BOCA[1], 11, 7), 0),
        ("Ojo_Der", _parche(orig, OJO_D[0], OJO_D[1], 18, 12), 0),
        ("Ojo_Izq", _parche(orig, OJO_I[0], OJO_I[1], 18, 12), 0),
        ("Cabeza", _banda(orig, 0, Y_CUELLO), 0),
        ("Torso", _banda(orig, Y_CUELLO, Y_CINTURA), 0),
        ("Cuerpo", _banda(orig, Y_CINTURA, ALTO), 0),
    ]

    psd = PSDImage.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    for nombre, pil, _ in capas:
        psd.create_pixel_layer(pil, name=nombre, top=0, left=0)
        pil.save(os.path.join(SALIDA, f"{nombre}.png"))

    ruta_psd = os.path.join(SALIDA, "robina_layered.psd")
    psd.save(ruta_psd)

    re = PSDImage.open(ruta_psd).composite()
    dif = sum(
        1
        for a, b in zip(
            re.tobytes(), orig.tobytes()
        )
        if a != b
    )
    total = ALTO * ANCHO * 4
    print(f"PSD_GENERADO={ruta_psd}")
    print(f"COMPOSITE_IDENTICO_AL_RENDER dif={dif}/{total} ({100.0*dif/max(1,total):.4f}%)")
    print(f"CAPAS_PNG_OK n={len(capas)}")


if __name__ == "__main__":
    main()