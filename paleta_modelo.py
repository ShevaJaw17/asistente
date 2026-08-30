# paleta_modelo.py - Extrae los colores dominantes (con luma y cobertura) de
# una textura, para planear recolores semánticos. Uso interno.
import sys
from PIL import Image

RUTA = sys.argv[1] if len(sys.argv) > 1 else "assets/akari/akari.4096/texture_00.png"
BITS = int(sys.argv[2]) if len(sys.argv) > 2 else 5


def main():
    img = Image.open(RUTA).convert("RGBA").resize((1024, 1024))
    pix = img.load()
    w, h = img.size
    cuenta = {}
    for y in range(h):
        for x in range(w):
            r, g, b, a = pix[x, y]
            if a < 10:
                continue
            q = tuple(((c >> (8 - BITS)) << (8 - BITS)) for c in (r, g, b))
            cuenta[q] = cuenta.get(q, 0) + 1
    total = sum(cuenta.values())
    top = sorted(cuenta.items(), key=lambda kv: -kv[1])[:24]
    for (r, g, b), n in top:
        luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
        hue = None
        import math
        mx, mn = max(r, g, b), min(r, g, b)
        d = mx - mn
        if d:
            if mx == r:
                hue = ((g - b) / d) % 6
            elif mx == g:
                hue = (b - r) / d + 2
            else:
                hue = (r - g) / d + 4
            hue = round(hue * 60)
        saturacion = 255 * (d / 255) if mx else 0
        print(
            f"#{r:02X}{g:02X}{b:02X} luma={luma:4.0f} hue={hue} sat={saturacion:4.0f} "
            f"cob={100.0*n/total:5.2f}%"
        )


if __name__ == "__main__":
    main()