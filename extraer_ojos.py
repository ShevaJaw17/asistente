# extraer_ojos.py - Detecta los ojos en el sprite de Robin y genera:
#  - vision.json: coordenadas de los ojos (escala del sprite original robin_avatar.png 258x520)
#  - robin_ojos.png: sprite recortado por ojo con colores de piel muestreados del rostro
import json
import os
from collections import deque

from PIL import Image

RUTA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets",
    "robin",
    "robin_avatar.png",
)
SALIDA_JSON = os.path.join(os.path.dirname(RUTA), "ojos.json")
SALIDA_PNG = os.path.join(os.path.dirname(RUTA), "robin_ojos.png")


def buscar_ojos(img):
    w, h = img.size
    px = img.load()

    def luminancia(c):
        return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

    def es_piel(c):
        r, g, b, a = c
        if a < 128:
            return False
        m = max(r, g, b)
        return r > 140 and m - min(r, g, b) < 90

    # Región de la cabeza: franja superior. Los ojos quedan dentro.
    y_min = int(h * 0.04)
    y_max = int(h * 0.24)
    x_min = int(w * 0.10)
    x_max = int(w * 0.90)

    candidatos = []
    for y in range(y_min, y_max):
        for x in range(x_min, x_max):
            c = px[x, y]
            if c[3] < 128:
                continue
            lum = luminancia(c)
            if 25 <= lum <= 105:
                # evita cabello: el cabello suele ser más oscuro que el ojo
                candidatos.append((x, y))

    if len(candidatos) < 20:
        return None

    # agrupar por conectividad para separar ojo izquierdo/derecho
    vistos = set()
    grumos = []
    for p in candidatos:
        if p in vistos:
            continue
        cola = deque([p])
        vistos.add(p)
        zona = []
        while cola:
            x, y = cola.popleft()
            zona.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q not in vistos and q in set(candidatos):
                        vistos.add(q)
                        cola.append(q)
        if len(zona) >= 8:
            grumos.append(zona)

    if len(grumos) < 2:
        return None

    grumos.sort(key=len, reverse=True)
    mejores = grumos[:2]
    # Comprobar simetria (alturas parecidas y separacion horizontal)
    centros = []
    for zona in mejores:
        xs = [p[0] for p in zona]
        ys = [p[1] for p in zona]
        centros.append((sum(xs) / len(xs), sum(ys) / len(ys)))
    c0, c1 = centros
    if abs(c0[1] - c1[1]) > h * 0.06:
        return None
    if abs(c0[0] - c1[0]) < w * 0.05:
        return None
    return sorted(centros, key=lambda c: c[0])


def muestrear_piel(img, x, y, radio=7):
    px = img.load()
    w, h = img.size
    pieles = []
    for dy in range(-radio, radio + 1):
        for dx in range(-radio, radio + 1):
            xx, yy = int(x + dx), int(y + dy)
            if 0 <= xx < w and 0 <= yy < h:
                c = px[xx, yy]
                if c[3] > 128 and c[0] > 140 and max(c[0], c[1], c[2]) - min(c[0], c[1], c[2]) < 90:
                    pieles.append(c[:3])
    if not pieles:
        return None
    prom = tuple(sum(v[i] for v in pieles) // len(pieles) for i in range(3))
    return prom


def generar_parpadeo(img, ojos, radio=6):
    w, h = img.size
    salida = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out = salida.load()
    for (cx, cy) in ojos:
        piel = muestrear_piel(img, int(cx), int(cy + radio))
        for dy in range(-radio, radio + 1):
            for dx in range(int(radio * 1.7), -int(radio * 1.7) - 1, -1):
                if (dx * dx) / (radio * 1.7) ** 2 + (dy * dy) / radio ** 2 <= 1.0:
                    x = int(cx + dx)
                    y = int(cy + dy)
                    if 0 <= x < w and 0 <= y < h:
                        if out[x, y][3] == 0:
                            out[x, y] = (*piel, 255)
        # linea del parpado
        for dx in range(-int(radio * 1.4), int(radio * 1.4) + 1):
            x = int(cx + dx)
            y = int(cy) - 1
            if 0 <= x < w and 0 <= y < h:
                out[x, y] = tuple(max(0, v - 60) for v in piel) + (255,)
    return salida


def buscar_boca(img, ojos):
    w, h = img.size
    px = img.load()
    if not ojos:
        return None
    x0 = int(min(ojos[0][0], ojos[1][0]))
    x1 = int(max(ojos[0][0], ojos[1][0]))
    cx = (x0 + x1) / 2
    cy_ojos = (ojos[0][1] + ojos[1][1]) / 2
    y_mn = int(cy_ojos + (x1 - x0) * 0.6)
    y_mx = int(cy_ojos + (x1 - x0) * 2.0)
    candidatos = []
    for y in range(y_mn, y_mx):
        for x in range(int(cx - (x1 - x0) * 1.6), int(cx + (x1 - x0) * 1.6)):
            if 0 <= x < w and 0 <= y < h:
                c = px[x, y]
                if c[3] < 128:
                    continue
                r, g, b = c[0], c[1], c[2]
                if r > 130 and r - g > 30 and r - b > 25:
                    candidatos.append((x, y))
    if len(candidatos) < 10:
        return None
    xs = [p[0] for p in candidatos]
    ys = [p[1] for p in candidatos]
    return [sum(xs) / len(xs), sum(ys) / len(ys)]


def main():
    img = Image.open(RUTA).convert("RGBA")
    ojos = buscar_ojos(img)
    if not ojos:
        print("NO_SE_ENCONTRARON_OJOS")
        return
    boca = buscar_boca(img, ojos)
    parpadeo = generar_parpadeo(img, ojos)
    parpadeo.save(SALIDA_PNG)
    with open(SALIDA_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {"ancho": img.width, "alto": img.height, "ojos": ojos, "boca": boca},
            f,
        )
    print("OJOS:", json.dumps(ojos))
    print("BOCA:", json.dumps(boca))
    print("GENERADOS:", SALIDA_JSON, SALIDA_PNG)


if __name__ == "__main__":
    main()