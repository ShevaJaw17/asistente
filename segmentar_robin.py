# segmentar_robin.py - Divide robin_avatar.png en capas (cabeza/torso/cuerpo)
# usando el perfil de anchura alfa para encontrar cuello y cintura.
# Salida: assets/robin/layer_{cabeza,torso,cuerpo}.png (canvas completo translucido)
#         y layer.json con (cuello, cintura, alto) en pixeles del sprite base.
import json
import os

from PIL import Image

RUTA_BASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "robin", "robin_avatar.png"
)
CARPETA = os.path.dirname(RUTA_BASE)


def perfil_ancho(img):
    w, h = img.size
    px = img.load()
    return [
        sum(1 for x in range(w) if px[x, y][3] > 128)
        for y in range(h)
    ]


def suavizar(serie, k=5):
    out = list(serie)
    n = len(serie)
    for i in range(n):
        ini = max(0, i - k)
        fin = min(n, i + k + 1)
        out[i] = sum(serie[ini:fin]) / (fin - ini)
    return out


def minimo_local(serie, ini, fin, margen=0.9):
    """Devuelve la fila del minimo en (ini, fin) o None si no hay valle claro."""
    ventana = serie[ini:fin]
    if not ventana:
        return None
    base = max(ventana)
    fila = ini + ventana.index(min(ventana))
    m = serie[fila]
    if base > 0 and m < base * margen and m < 30:
        return fila
    return None


def main():
    img = Image.open(RUTA_BASE).convert("RGBA")
    w, h = img.size
    ancho = perfil_ancho(img)
    alisado = suavizar(ancho)

    cuello = minimo_local(alisado, int(h * 0.12), int(h * 0.40))
    if cuello is None:
        cuello = 140
    if cuello < 120 or cuello > 175:
        cuello = 140
    cintura = minimo_local(alisado, int(h * 0.40), int(h * 0.70))
    if cintura is None:
        cintura = int(h * 0.50)

    bandas = {
        "cabeza": (0, cuello),
        "torso": (cuello, cintura),
        "cuerpo": (cintura, h),
    }
    for nombre, (y0, y1) in bandas.items():
        capa = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        px = img.load()
        cp = capa.load()
        for y in range(y0, y1):
            for x in range(w):
                cp[x, y] = px[x, y]
        capa.save(os.path.join(CARPETA, f"layer_{nombre}.png"))

    with open(os.path.join(CARPETA, "layer.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "ancho": w,
                "alto": h,
                "cuello": cuello,
                "cintura": cintura,
                "anchos": alisado,
            },
            f,
        )
    print(f"BASE={w}x{h}")
    print(f"CUELLO=y{cuello} CINTURA=y{cintura}")
    print("ANCHURA_ALISADA_COLS0_20:", [
        int(alisado[y] or 0) for y in range(0, min(h, 21), 5)
    ])
    print("GENERADAS 3 CAPAS + layer.json")


if __name__ == "__main__":
    main()