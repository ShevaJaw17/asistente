import os
import shutil

import numpy as np
from PIL import Image

ORIGEN = r"C:\Users\Usuario\asistente\assets\akari\akari.4096\texture_00.png"
DESTINO_PNG = r"C:\Users\Usuario\asistente\assets\robin_l2d\robin.4096\texture_00.png"

OLDPNG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "robin_l2d", "robin.4096"
)


def main():
    shutil.copy2(DESTINO_PNG, OLDPNG + r"\texture_00.robinv1.png")
    img = Image.open(ORIGEN).convert("RGBA")
    arr = np.frombuffer(img.tobytes(), dtype=np.uint8).reshape(
        img.height, img.width, 4
    ).copy()
    n = arr.reshape(-1, 4)
    rgb = n[..., :3].astype(np.float32)
    luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    mx = rgb.max(1)
    mn = rgb.min(1)
    sat = mx - mn
    out = rgb.copy()
    hecho = np.zeros(n.shape[0], dtype=bool)
    alfa = n[..., 3] > 10

    def aplicar(m, target, luma_media, lim_inf=0.22, lim_sup=1.75):
        m = m & ~hecho
        if not m.any():
            return
        t = np.asarray(target, dtype=np.float32)
        e = np.clip(luma[m] / luma_media, lim_inf, lim_sup)
        out[m] = t[None, :] * e[:, None]
        out[m] = np.clip(out[m], 0, 255)
        hecho[m] = True

    # 1) piel canela (solo tonos naranja-warm: excluye blancos rosados de la ropa)
    centros_piel = np.asarray(
        [[248, 200, 184], [248, 216, 200], [248, 208, 192], [240, 168, 152],
         [248, 208, 176], [240, 208, 192]], dtype=np.float32
    )
    dmin_piel = np.abs(rgb[:, None, :] - centros_piel[None, :, :]).sum(2).min(1)
    m_piel = (
        (dmin_piel <= 60)
        & (rgb[..., 0] - rgb[..., 2] > 22)
        & (rgb[..., 0] - rgb[..., 1] > 10)
        & (rgb[..., 1] >= rgb[..., 2])
        & (luma <= 246)
        & ~hecho
    )
    aplicar(m_piel, (224, 166, 112), 190.0)

    # 2) pelo (negro azulado)
    centros_pelo = np.asarray(
        [[64, 0, 0], [88, 8, 48], [72, 0, 56], [120, 48, 104], [150, 20, 60]],
        dtype=np.float32,
    )
    dmin_pelo = np.abs(rgb[:, None, :] - centros_pelo[None, :, :]).sum(2).min(1)
    m_pelo = (dmin_pelo <= 52) & ~hecho
    aplicar(m_pelo, (22, 18, 34), 30.0)

    # 3) vestido lavanda: blancos suaves/neutros y rosados-palidos de la ropa
    m_vestido = (
        (luma >= 150)
        & (sat <= 90)
        & ~hecho
    )
    m_vestido |= (dmin_piel <= 90) & (luma >= 150) & ~hecho
    aplicar(m_vestido, (196, 168, 236), 195.0, 0.25, 1.8)

    # 4) morado sombra (resto oscuro no clasificado)
    m_morado = (luma < 150) & ~hecho & alfa
    aplicar(m_morado, (150, 94, 200), 100.0)

    # 5) especular puro se queda blanco (ojos, brillos)
    m_espec = (sat < 6) & (luma > 248) & ~hecho
    out[m_espec] = np.asarray((250, 248, 246), dtype=np.float32)

    n[..., :3] = np.clip(np.round(out), 0, 255)
    img2 = Image.fromarray(arr, "RGBA")
    img2.save(DESTINO_PNG)

    op = alfa
    for nombre, m in [("sin_mapa", ~hecho & op), ("piel", m_piel), ("pelo", m_pelo),
                      ("vestido", hecho & ~m_piel & ~m_pelo & ~m_morado),
                      ("morado", m_morado)]:
        print(f"{nombre}: {round(100 * m.sum() / op.sum(), 2)}%")
    print("OK", DESTINO_PNG)


if __name__ == "__main__":
    main()