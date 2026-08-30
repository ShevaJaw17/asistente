# recolorear_robin.py - Deriva un modelo Live2D "Robin" a partir del modelo
# base (Akari): copia assets/akari -> assets/robin_l2d, renombra a robin_*
# y recoloriza su atlas de texturas hacia la paleta de Nico Robin
# (pelo negro, piel canela, vestuario verde/marron, ocres) preservando las
# luces/sombras de cada zona (recolor por familia + valor).
import copy
import json
import os
import shutil

import numpy as np
from PIL import Image

ORIGEN = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "akari"
)
DESTINO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "robin_l2d"
)

# --- familias: (nombre, lista de centroides RGB, target RGB, luma media) ---
FAMILIAS = [
    ("pelo", [(64, 0, 0), (88, 8, 48), (72, 0, 56), (80, 24, 64),
              (120, 48, 104), (150, 20, 60)],
     (22, 18, 34), 30.0),
    ("piel", [(240, 160, 136), (248, 200, 184), (248, 216, 200),
              (248, 208, 192), (224, 144, 128), (240, 168, 152),
              (216, 120, 104), (240, 208, 192), (248, 208, 176)],
     (224, 166, 112), 182.0),
    ("morado", [(120, 56, 88), (128, 80, 120), (104, 56, 104),
                (140, 90, 130), (160, 110, 140)],
     (166, 110, 200), 128.0),
    ("marron", [(200, 48, 24), (176, 48, 40), (216, 88, 64)],
     (150, 52, 44), 84.0),
    ("lavanda", [(232, 208, 216), (248, 184, 208), (240, 224, 232),
                 (232, 216, 224), (248, 224, 208), (240, 216, 224)],
     (206, 182, 236), 191.0),
    ("blanco", [(248, 248, 248), (248, 240, 240), (248, 240, 224),
                (240, 240, 240)],
     (246, 244, 238), 244.0),
]


def _clasificar(arr, tolerancia=52):
    """Devuelve mascara de familias (np.bool_) por pixel-opaco-no-clasificado."""
    rgb = arr[..., :3].astype(np.float32)
    n = arr.shape[0]
    mascara_total = np.zeros(n, dtype=bool)
    resultado = np.zeros((len(FAMILIAS), n), dtype=bool)
    for f, (nombre, centros, _, _) in enumerate(FAMILIAS):
        centros_np = np.asarray(centros, dtype=np.float32)
        # distancia por canal ponderada (la luminancia manda)
        dist = np.abs(rgb[:, None, :] - centros_np[None, :, :]) * np.array(
            (1.0, 1.0, 1.0), dtype=np.float32
        )
        dmin = dist.sum(2).min(1)
        ok = (dmin <= tolerancia) & ~mascara_total
        resultado[f] = ok
        mascara_total |= ok
    return resultado, mascara_total


def recolorear(arr):
    n = arr.shape[0]
    rgb = arr[..., :3].astype(np.float32)
    luma = (
        0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    )
    out_rgb = rgb.copy()
    mascaras, masc_total = _clasificar(arr)
    for f, (nombre, _, target, luma_media) in enumerate(FAMILIAS):
        m = mascaras[f]
        if not m.any():
            continue
        t = np.asarray(target, dtype=np.float32)
        escala = np.clip((luma[m] / luma_media), 0.28, 1.65)
        nuevo = t[None, :] * escala[:, None]
        nuevo = np.clip(nuevo, 0, 255)
        out_rgb[m] = nuevo
    return out_rgb


def main():
    if os.path.exists(DESTINO):
        shutil.rmtree(DESTINO)
    shutil.copytree(ORIGEN, DESTINO)

    for viejo, nuevo in [
        ("akari.moc3", "robin.moc3"),
        ("akari.model3.json", "robin.model3.json"),
        ("akari.physics3.json", "robin.physics3.json"),
        ("akari.userdata3.json", "robin.userdata3.json"),
        ("akari.cdi3.json", "robin.cdi3.json"),
        ("akari.vtube.json", "robin.vtube.json"),
        ("icon.jpg", "icon.jpg"),
    ]:
        p = os.path.join(DESTINO, viejo)
        if os.path.exists(p):
            os.rename(p, os.path.join(DESTINO, nuevo))

    tex_dir = os.path.join(DESTINO, "akari.4096")
    if os.path.exists(tex_dir):
        os.rename(tex_dir, os.path.join(DESTINO, "robin.4096"))
    ruta_tex = os.path.join(DESTINO, "robin.4096", "texture_00.png")

    img = Image.open(ruta_tex).convert("RGBA")
    arr = np.frombuffer(img.tobytes(), dtype=np.uint8).reshape(
        img.height, img.width, 4
    ).copy()
    nuevo = recolorear(arr.reshape(-1, 4)).astype(np.uint8)
    arr[..., :3] = nuevo.reshape(img.height, img.width, -1)
    img2 = Image.fromarray(arr, "RGBA")
    img2.save(ruta_tex)

    ruta_json = os.path.join(DESTINO, "robin.model3.json")
    datos = json.load(open(ruta_json, encoding="utf-8"))
    refs = datos["FileReferences"]
    refs["Moc"] = "robin.moc3"
    refs["Physics"] = "robin.physics3.json"
    refs["UserData"] = "robin.userdata3.json"
    refs["DisplayInfo"] = "robin.cdi3.json"
    refs["Textures"] = ["robin.4096/texture_00.png"]
    datos["Name"] = "Robin"
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent="\t")

    m_total = arr[..., 3] > 10
    print(f"TEXTURA={img2.size} px_opacos={int(m_total.sum())}")
    for f, (nombre, _, target, _) in enumerate(FAMILIAS):
        print(f"  {nombre}: target #{target[0]:02X}{target[1]:02X}{target[2]:02X}")
    print("MODELO_GENERADO=" + DESTINO)


if __name__ == "__main__":
    main()