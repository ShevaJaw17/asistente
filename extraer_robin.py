# extraer_robin.py - Convierte el render de Robin (fondo verde de croma) en PNG
# transparente (assets/robin/robin.png) + versión de avatar (robin_avatar.png).
import os
from PIL import Image

RUTA_RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "robin", "raw_Nico_Robin_Anime_Post_Timeskip_Outfit.png")
RUTA_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "robin", "robin.png")
RUTA_AVATAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "robin", "robin_avatar.png")
ALTURA_AVATAR = 520


def sintetizar_alpha(img_rgb):
    """Marca fondo verde (g - max(r,b) > umbral) y conserva solo la región
    conectada a los bordes (evita agujeros de verde dentro del personaje)."""
    w, h = img_rgb.size
    px = img_rgb.load()
    es_bg = bytearray(w * h)
    umbral = 26
    for y in range(h):
        fila = y * w
        for x in range(w):
            r, g, b = px[x, y]
            if g - max(r, b) >= umbral:
                es_bg[fila + x] = 1
    # BFS desde el borde sobre píxeles bg
    visitado = bytearray(w * h)
    pila = []
    for x in range(w):
        for yy in (0, h - 1):
            i = yy * w + x
            if es_bg[i] and not visitado[i]:
                visitado[i] = 1
                pila.append(i)
    for y in range(h):
        for xx in (0, w - 1):
            i = y * w + xx
            if es_bg[i] and not visitado[i]:
                visitado[i] = 1
                pila.append(i)
    while pila:
        i = pila.pop()
        x = i % w
        y = i // w
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                j = ny * w + nx
                if es_bg[j] and not visitado[j]:
                    visitado[j] = 1
                    pila.append(j)
    # Alpha: 0 en bg conectado al borde, 255 en el resto
    alpha = Image.new("L", (w, h), 255)
    pa = alpha.load()
    for y in range(h):
        fila = y * w
        for x in range(w):
            if visitado[fila + x]:
                pa[x, y] = 0
    return alpha


def main():
    img = Image.open(RUTA_RAW).convert("RGB")
    alpha = sintetizar_alpha(img)
    img = img.convert("RGBA")
    img.putalpha(alpha)
    # Recorte al contenido visible
    img = img.crop(alpha.getbbox())
    img.save(RUTA_OUT)
    # Versión del avatar (más liviana para la GUI)
    av = img.copy()
    nueva_h = ALTURA_AVATAR
    nueva_w = max(1, round(av.width * nueva_h / av.height))
    av = av.resize((nueva_w, nueva_h), Image.LANCZOS)
    av.save(RUTA_AVATAR)
    print("OK", RUTA_OUT, img.size)
    print("OK", RUTA_AVATAR, av.size)


if __name__ == "__main__":
    main()