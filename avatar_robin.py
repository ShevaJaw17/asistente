# avatar_robin.py - Nico Robin como "cuerpo virtual" del asistente.
# Motor de deformacion por malla (mini-Live2D con PIL):
#  - Rejilla de vertices sobre el dibujo; cada frame se dobla (cabeza gira,
#    labios/boca se agitan, pecho respira) re-malleando con Image.MESH.
#  - Parpadeo y boca abierta compuestos ANTES del warp (se doblan con la cara).
#  - Burbuja de estado, gestos y patrulla hacia el cursor.
# API: iniciar/detener/expresion_estado/hablar_texto/actividad/gesto.
import ctypes
import ctypes.wintypes
import json
import math
import os
import random
import time
import tkinter as tk

import numpy as np
from PIL import Image, ImageTk

COLOR_TK_CLAVE = "magenta"

EXPRESIONES = {
    "pensando": "pensando",
    "respuesta": "respuesta",
    "error": "error",
    "hablar": "hablar",
}

ANCHO_ORIG = 258
ALTO_ORIG = 520
PAD = 10

COLUMNAS = (0, 20, 44, 72, 104, 140, 178, 210, 236, 258)
FILAS = (0, 18, 36, 54, 72, 90, 106, 118, 128, 138, 152,
         170, 192, 220, 256, 300, 352, 412, 472, 520)


def _ruta_assets(nombre):
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "assets", "robin", nombre
    )


def _cargar_parpadeo():
    try:
        with open(_ruta_assets("ojos.json"), encoding="utf-8") as f:
            datos = json.load(f)
        ojos = datos.get("ojos") or []
        png = Image.open(_ruta_assets("robin_ojos.png")).convert("RGBA")
        patches = []
        for cx, cy in ojos:
            x0 = max(0, int(cx) - 18)
            y0 = max(0, int(cy) - 12)
            x1 = min(png.width, int(cx) + 18)
            y1 = min(png.height, int(cy) + 12)
            recorte = png.crop((x0, y0, x1, y1))
            patches.append((recorte, x0, y0))
        return patches
    except Exception:
        return None


def _cargar_boca():
    try:
        with open(_ruta_assets("ojos.json"), encoding="utf-8") as f:
            datos = json.load(f)
        return datos.get("boca")
    except Exception:
        return None


def _componer_boca(base, boca, escala_x, escala_y):
    from PIL import ImageDraw

    cx = int(boca[0] * escala_x)
    cy = int(boca[1] * escala_y)
    rx = max(3, int(9 * escala_x))
    ry = max(2, int(5 * escala_y))
    resultado = base.copy()
    dr = ImageDraw.Draw(resultado, "RGBA")
    dr.ellipse(
        (cx - rx, cy - ry, cx + rx, cy + ry),
        fill=(95, 45, 60, 255),
        outline=(150, 90, 95, 255),
        width=1,
    )
    return resultado


def _variante_cerrado(base, patches, escala_x, escala_y):
    if not patches:
        return None
    resultado = base.copy()
    for patch, ox, oy in patches:
        pw = max(1, int(patch.width * escala_x))
        ph = max(1, int(patch.height * escala_y))
        if pw >= base.width or ph >= base.height:
            continue
        redim = patch.resize((pw, ph), Image.LANCZOS)
        px = max(0, min(int(ox * escala_x), base.width - pw))
        py = max(0, min(int(oy * escala_y), base.height - ph))
        resultado.alpha_composite(redim, (px, py))
    return resultado


def _gauss(filas, mu, sigma):
    return np.exp(-0.5 * ((filas - mu) / max(1.0, sigma)) ** 2)


class AvatarRobin:
    def __init__(
        self,
        root_padre,
        on_estado=None,
        separacion=24,
        elevacion=0.35,
        click_through=True,
        escala=0.9,
        incrustado=False,
        color_fondo=None,
    ):
        self._on_estado = on_estado
        self._separacion = int(separacion)
        self._elevacion = float(elevacion)
        self._escala = float(escala)
        self._incrustado = bool(incrustado)
        self._activado = False
        self._hablando_hasta = 0.0
        self._error_hasta = 0.0
        self._t0 = time.time()
        self._estado = "respuesta"

        self._parpadeando_hasta = 0.0
        self._proximo_parpadeo = self._tiempo_parpadeo()
        self._texto_habla = ""
        self._duracion_habla = 0.8

        self._burbuja_visible = False
        self._burbuja_hasta = 0.0
        self._burbuja_items = None
        self._burbuja_puntos = None

        self._gesto = None
        self._gesto_hasta = 0.0

        self._ultima_repos = 0.0
        self._pos_ventana = None

        self._configurar_malla()

        margen = 40
        self._ancho = int(self._W)
        self._alto = int(self._H)
        aw = self._ancho + 2 * margen
        ah = self._alto + 2 * margen

        fondo = color_fondo or ("#1e1e1e" if self._incrustado else COLOR_TK_CLAVE)

        if self._incrustado:
            self._marco = tk.Frame(root_padre, bg=fondo)
            self._marco.pack(fill=tk.BOTH, expand=True)
            contenedor = self._marco
        else:
            self._ventana = tk.Toplevel(root_padre)
            self._ventana.overrideredirect(True)
            self._ventana.attributes("-topmost", True)
            self._ventana.configure(bg=COLOR_TK_CLAVE)
            try:
                self._ventana.attributes("-transparentcolor", COLOR_TK_CLAVE)
            except Exception:
                pass
            contenedor = self._ventana

        self._canvas = tk.Canvas(
            contenedor,
            width=aw,
            height=ah,
            bg=fondo,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack()
        self._x_base = int(aw / 2)
        self._y_base = int(ah / 2)
        self._item = self._canvas.create_image(
            self._x_base, self._y_base, image=self._foto
        )
        self._y_burbuja = int(self._y_base - self._alto * 0.5 - 16)

        if not self._incrustado:
            if click_through:
                self._aplicar_click_through()
            self._ventana.withdraw()

    # ----- malla -----
    def _tiempo_parpadeo(self):
        return time.time() + random.uniform(2.2, 5.0)

    def _configurar_malla(self):
        escala = self._escala
        W = int(ANCHO_ORIG * escala)
        H = int(ALTO_ORIG * escala)
        base = Image.open(_ruta_assets("robin_avatar.png")).convert("RGBA")
        base = base.resize((W, H), Image.LANCZOS)
        esx = W / ANCHO_ORIG
        esy = H / ALTO_ORIG
        patches = _cargar_parpadeo()
        boca = _cargar_boca()
        cerrado = _variante_cerrado(base, patches, esx, esy)
        abierta = _componer_boca(base, boca, esx, esy) if boca else None
        self._base_pil = base
        self._cerrado_pil = cerrado
        self._boca_pil = abierta
        self._W = W
        self._H = H
        self._foto = ImageTk.PhotoImage(base)
        self._foto_actual = None

        self._X = np.clip([int(c * escala) for c in COLUMNAS], 0, W)
        self._R = np.clip([int(f * escala) for f in FILAS], 0, H)
        self._Yfilas = np.arange(H, dtype=float)
        self._cabeza = _gauss(self._Yfilas, 92.0 * escala, 34.0 * escala)
        self._boca_g = _gauss(self._Yfilas, 126.0 * escala, 17.0 * escala)
        self._pecho = (
            _gauss(self._Yfilas, 190.0 * escala, 62.0 * escala)
            + 0.32 * _gauss(self._Yfilas, 90.0 * escala, 50.0 * escala)
        )
        self._Yf = np.asarray(self._R, dtype=float)
        self._Xf = np.asarray(self._X, dtype=float)

    def _warp(self, pil, s, v):
        W, H, pad = self._W, self._H, PAD
        Wp = W + 2 * pad
        Hp = H + 2 * pad
        src = Image.new("RGBA", (Wp, Hp), (0, 0, 0, 0))
        src.paste(pil, (pad, pad))
        X = self._Xf + pad
        R = self._Yf + pad
        fi = np.clip(self._R, 0, H - 1)
        s_row = s[fi]
        v_row = v[fi]
        nx = len(X)
        ny = len(R)
        cells = []
        for j in range(nx - 1):
            x0, x1 = X[j], X[j + 1]
            for i in range(ny - 1):
                y0, y1 = R[i], R[i + 1]
                s0, s1 = s_row[i], s_row[i + 1]
                v0, v1 = v_row[i], v_row[i + 1]
                cells.append((
                    (int(x0 - pad), int(y0 - pad), int(x1 - pad), int(y1 - pad)),
                    (
                        int(x0 - pad + s0), int(y0 - pad + v0),
                        int(x1 - pad + s0), int(y0 - pad + v0),
                        int(x1 - pad + s1), int(y1 - pad + v1),
                        int(x0 - pad + s1), int(y1 - pad + v1),
                    ),
                ))
        return src.transform(
            (W, H), Image.MESH, cells, resample=Image.BILINEAR
        )

    def _aplicar_click_through(self):
        try:
            hwnd = self._ventana.winfo_id()
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000
            WS_EX_TOOLWINDOW = 0x00000080
            estilo = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            estilo |= WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, estilo)
        except Exception:
            pass

    # ----- API publica -----
    def iniciar(self):
        if self._activado:
            return
        self._activado = True
        if self._incrustado:
            self._ventana = self._marco
        else:
            self._ventana.deiconify()
            self._mover_a_cursor(0.0, 0.0)
        self._ventana.update_idletasks()
        self._ventana.after(33, self._bucle_animacion)

    def detener(self):
        self._activado = False
        try:
            if self._incrustado:
                self._marco.destroy()
            else:
                self._ventana.destroy()
        except Exception:
            pass

    def expresion(self, nombre, activa=True):
        self._estado = str(nombre) if nombre and activa else "respuesta"

    def expresion_estado(self, estado):
        self._estado = EXPRESIONES.get(estado, "respuesta")
        if self._estado == "error":
            self._error_hasta = time.time() + 1.2
            self.actividad("¡Ups! Algo no salió bien", 2.5)
            self.gesto("sorpresa")
        elif self._estado == "pensando":
            self.actividad("Pensando…", 2.5)
        else:
            self.actividad("", 0)
        if self._on_estado:
            try:
                self._on_estado(self._estado)
            except Exception:
                pass

    def hablar_texto(self, texto):
        duracion = max(0.8, min(4.0, len(texto) / 14))
        self._hablando_hasta = time.time() + duracion
        self._duracion_habla = duracion
        self._texto_habla = (texto or "")[:400]
        self._estado = "hablar"
        self.actividad("", 0)

    def _boca_abierta(self, t):
        if not self._texto_habla or not self._duracion_habla:
            return False
        fraccion = t / self._duracion_habla
        si = int(fraccion * len(self._texto_habla))
        si = max(0, min(len(self._texto_habla) - 1, si))
        vocales = set("aeiouáéíóúäëïöüAEIOU")
        texto = self._texto_habla
        actual = si < len(texto) and texto[si] in vocales
        siguiente = (
            si + 1 < len(texto) and fraccion - si / len(texto) > 0.5
            and texto[si + 1] in vocales
        )
        return actual or siguiente

    def actividad(self, texto, duracion=3.5):
        self._texto_burbuja = texto
        self._burbuja_hasta = time.time() + max(0, duracion) if texto else 0.0
        if not texto:
            self._ocultar_burbuja()

    def gesto(self, nombre):
        self._gesto = nombre
        self._gesto_hasta = time.time() + (1.6 if nombre == "saludo" else 1.1)

    # ----- burbuja -----
    def _forma_rr(self, cx, cy, w, h, r):
        x0, y0 = cx - w / 2 + r, cy - h / 2 + r
        x1, y1 = cx + w / 2 - r, cy + h / 2 - r
        pts = []
        for a in range(270, 360, 30):
            rad = a * math.pi / 180
            pts.append((x1 + r * math.cos(rad), y0 + r * math.sin(rad)))
        for a in range(0, 90, 30):
            rad = a * math.pi / 180
            pts.append((x1 + r * math.cos(rad), y1 + r * math.sin(rad)))
        for a in range(90, 180, 30):
            rad = a * math.pi / 180
            pts.append((x0 + r * math.cos(rad), y1 + r * math.sin(rad)))
        for a in range(180, 270, 30):
            rad = a * math.pi / 180
            pts.append((x0 + r * math.cos(rad), y0 + r * math.sin(rad)))
        return pts

    def _crear_burbuja(self, texto):
        alto = 26
        ancho = max(70, min(200, len(texto) * 7 + 24))
        cx = self._x_base
        cy = self._y_burbuja
        cuerpo = self._forma_rr(cx, cy, ancho, alto, 10)
        cola = [
            (cx - 7, cy + alto / 2),
            (cx + 7, cy + alto / 2),
            (cx, cy + alto / 2 + 9),
        ]
        self._burbuja_puntos = (cuerpo, cola)
        item_fondo = self._canvas.create_polygon(
            list(cuerpo) + list(cola),
            fill="#ffffff",
            outline="",
            smooth=True,
        )
        item_texto = self._canvas.create_text(
            cx,
            cy - 2,
            text=texto,
            fill="#1e1e1e",
            font=("Segoe UI", 9, "bold"),
        )
        self._burbuja_items = (item_fondo, item_texto)

    def _mostrar_burbuja(self, texto):
        if self._burbuja_items is None:
            self._crear_burbuja(texto)
        elif self._texto_burbuja != texto:
            self._canvas.itemconfig(self._burbuja_items[1], text=texto)
        self._canvas.itemconfigure(self._burbuja_items[0], state="normal")
        self._canvas.itemconfigure(self._burbuja_items[1], state="normal")
        self._burbuja_visible = True

    def _ocultar_burbuja(self):
        if self._burbuja_items is None:
            return
        try:
            self._canvas.itemconfigure(self._burbuja_items[0], state="hidden")
            self._canvas.itemconfigure(self._burbuja_items[1], state="hidden")
        except Exception:
            pass
        self._burbuja_visible = False

    # ----- movimiento -----
    def _mover_a_cursor(self, off_x, off_y):
        ahora = time.time()
        if ahora - self._ultima_repos < 0.9:
            return
        self._ultima_repos = ahora
        try:
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            w = self._ventana.winfo_width()
            h = self._ventana.winfo_height()
            objetivo_x = pt.x - w - self._separacion
            objetivo_y = pt.y - int(h * self._elevacion)
            if self._pos_ventana is None:
                x, y = objetivo_x, objetivo_y
            else:
                px, py = self._pos_ventana
                x = px + (objetivo_x - px) * 0.35
                y = py + (objetivo_y - py) * 0.35
            self._pos_ventana = (int(x), int(y))
            self._ventana.geometry(
                f"+{max(0, int(x)) + int(off_x)}+{max(0, int(y)) + int(off_y)}"
            )
        except Exception:
            pass

    def _bucle_animacion(self):
        if not self._activado:
            return
        ahora = time.time()
        t = ahora - self._t0
        hablando = ahora < self._hablando_hasta
        en_error = ahora < self._error_hasta
        gesto_saludo = self._gesto == "saludo" and ahora < self._gesto_hasta
        gesto_sorpresa = self._gesto == "sorpresa" and ahora < self._gesto_hasta

        if hablando:
            amp_x, freq_x, amp_y, freq_y, resp = 6.0, 1.7, 10.0, 3.3, 5.0
            ha, hf, ma, mf, vb, bf = 2.6, 1.7, 2.2, 4.4, 1.7, 3.3
        elif en_error or gesto_sorpresa:
            amp_x, freq_x, amp_y, freq_y, resp = 12.0, 5.0, 3.0, 1.4, 2.0
            ha, hf, ma, mf, vb, bf = 4.0, 5.0, 1.4, 4.0, 1.0, 2.2
        elif self._estado == "pensando":
            amp_x, freq_x, amp_y, freq_y, resp = 8.0, 0.5, 3.0, 0.7, 1.1
            ha, hf, ma, mf, vb, bf = 1.9, 0.5, 0.0, 0.0, 0.8, 1.1
        else:
            amp_x, freq_x, amp_y, freq_y, resp = 5.0, 0.3, 6.0, 0.7, 1.5
            ha, hf, ma, mf, vb, bf = 1.1, 0.3, 0.0, 0.0, 0.7, 1.5

        off_x = amp_x * math.sin(2 * math.pi * freq_x * t)
        off_y = amp_y * math.sin(2 * math.pi * freq_y * t + 0.8)
        if gesto_saludo:
            off_y += 16.0 * abs(math.sin(2 * math.pi * 3.0 * t))

        if not self._incrustado:
            self._mover_a_cursor(off_x, off_y)

        parpadeando = ahora < self._parpadeando_hasta
        if not parpadeando and ahora >= self._proximo_parpadeo:
            self._parpadeando_hasta = ahora + 0.13
            self._proximo_parpadeo = self._tiempo_parpadeo()
        boca_abierta = hablando and self._boca_abierta(t)

        try:
            e = escala = self._escala
            s_fila = (
                ha * e * math.sin(2 * math.pi * hf * t) * self._cabeza
                + ma * e * math.sin(2 * math.pi * mf * t) * self._boca_g
            )
            v_fila = vb * e * math.sin(2 * math.pi * bf * t) * self._pecho
            base = self._base_pil
            if boca_abierta and self._boca_pil is not None:
                base = self._boca_pil
            elif parpadeando and not hablando and self._cerrado_pil is not None:
                base = self._cerrado_pil
            warp = self._warp(base, s_fila, v_fila)
            foto = ImageTk.PhotoImage(warp)
            if foto != self._foto_actual:
                self._foto_actual = foto
                self._canvas.itemconfigure(self._item, image=foto)

            self._canvas.coords(
                self._item, self._x_base + off_x, self._y_base + off_y
            )

            con_burbuja = bool(self._texto_burbuja and ahora < self._burbuja_hasta)
            if con_burbuja:
                self._mostrar_burbuja(self._texto_burbuja)
                cx = self._x_base + off_x
                cy = self._y_burbuja + off_y
                cuerpo, cola = self._burbuja_puntos
                self._canvas.coords(
                    self._burbuja_items[0],
                    [(p[0] + (cx - self._x_base), p[1] + (cy - self._y_burbuja)) for p in cuerpo]
                    + [
                        (p[0] + (cx - self._x_base), p[1] + (cy - self._y_burbuja))
                        for p in cola
                    ],
                )
                self._canvas.coords(
                    self._burbuja_items[1],
                    cx,
                    cy - 2,
                )
            elif self._burbuja_visible:
                self._ocultar_burbuja()
        except Exception:
            pass
        try:
            self._ventana.after(33, self._bucle_animacion)
        except Exception:
            pass


if __name__ == "__main__":
    import time as _t

    _tiempos = []
    _base = _t.time()

    def _medir(pb, cnt):
        if cnt <= 0:
            if _tiempos:
                print("WARP_MS_AVG", round(sum(_tiempos) / len(_tiempos), 2))
            return
        pb._ventana.update_idletasks()
        t0 = _t.time()
        pb._bucle_animacion()
        _tiempos.append((_t.time() - t0) * 1000)
        pb._ventana.after(33, lambda: _medir(pb, cnt - 1))

    root = tk.Tk()
    pb = AvatarRobin(root, on_estado=lambda t: print("ROBIN:", t))
    pb.iniciar()
    root.after(600, lambda: pb.actividad("Hola, soy tu asistente Robin"))
    root.after(1200, lambda: pb.hablar_texto("Estoy al pendiente de todo."))
    root.after(6000, _medir, pb, 60)
    root.after(13000, pb.detener)
    root.after(14000, root.destroy)
    root.mainloop()
    print("FIN robin OK")