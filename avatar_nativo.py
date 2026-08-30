# avatar_nativo.py - Render del modelo Live2D (akari) directo en la GUI,
# sin necesidad de VTube Studio. Usa pyopengltk + live2d-py (Cubism Core).
import glob
import os
import time

try:
    import tkinter as tk
except Exception:
    tk = None

DIRECTORIO_PROYECTO = os.path.dirname(os.path.abspath(__file__))
RUTA_MODELO = os.environ.get(
    "AVATAR_L2D_MODEL",
    os.path.join(
        DIRECTORIO_PROYECTO, "assets", "akari", "akari.model3.json"
    ),
)

EXPRESIONES = {
    "pensando": "SignShock.exp3",
    "error": "EyesCry.exp3",
    "respuesta": "EyesLove.exp3",
}

COLOR_FONDO = (0.114, 0.114, 0.114, 1.0)

ENCUADRE_MARGEN_SUP = 0.11
ENCUADRE_FONDO_PX = 8
ENCUADRE_CINTURA_FRACC = 0.35

try:
    from pyopengltk import OpenGLFrame
    import live2d.v3 as live2d
except Exception:
    OpenGLFrame = None

try:
    from OpenGL import GL
except Exception:
    GL = None


class AvatarL2D(OpenGLFrame):
    def __init__(self, master=None, on_estado=None, **kw):
        self.on_estado = on_estado
        self.model = None
        self._fallo = None
        self._hablando_hasta = 0.0
        self._expresion_actual = ""
        self._encuadrando = True
        self._encuadre_base = None
        self._encuadre_zoom = 1.0
        self._encuadre_pendiente_zoom = False
        self._encuadre_objetivo = 0.0
        self._offset_y = 0.0
        self._encuadre_pasos = 0
        self.color_fondo = COLOR_FONDO
        self._gl_global = True
        super().__init__(master=master, **kw)
        self.animate = 16

    # ----- utilidades -----
    def _estado(self, texto):
        if self.on_estado:
            try:
                self.on_estado(texto)
            except Exception:
                pass

    def _cargar(self):
        if OpenGLFrame is None:
            raise RuntimeError("pyopengltk/live2d no disponible")
        if not os.path.exists(RUTA_MODELO):
            raise RuntimeError(f"No se encuentra el modelo: {RUTA_MODELO}")
        live2d.init()
        live2d.glInit()
        model = live2d.LAppModel()
        model.LoadModelJson(RUTA_MODELO)
        model.Resize(max(1, self.winfo_width()), max(1, self.winfo_height()))
        model.SetAutoBreathEnable(True)
        model.SetAutoBlinkEnable(True)

        ids = model.GetParamIds()
        self._param_boca = "ParamMouthOpen" if "ParamMouthOpen" in ids else "ParamMouthOpenY"

        base = os.path.dirname(RUTA_MODELO)
        for f in sorted(glob.glob(os.path.join(base, "expressions", "*.exp3.json"))):
            try:
                model.LoadExtraExpression(
                    os.path.splitext(os.path.basename(f))[0], f
                )
            except Exception:
                pass
        for f in sorted(glob.glob(os.path.join(base, "animations", "*.motion3.json"))):
            try:
                model.LoadExtraMotion("Idle", f)
            except Exception:
                pass

        self.model = model
        grupos = model.GetMotionGroups()
        if grupos.get("Idle"):
            model.StartRandomMotion("Idle", priority=1)
        self._estado("Avatar 2D: render listo")
        return model

    # ----- ciclo OpenGL -----
    def initgl(self):
        try:
            if self.model is None:
                self._cargar()
            else:
                self.model.Resize(
                    max(1, self.winfo_width()), max(1, self.winfo_height())
                )
        except Exception as e:
            self._fallo = str(e)
            self._estado(f"Avatar 2D: error {e}")

    def redraw(self):
        if self._fallo or self.model is None:
            return
        live2d.clearBuffer(*self.color_fondo)
        now = time.time()
        if self._hablando_hasta > now:
            abierta = int(now * 4) % 2 == 0
            valor = 1.0 if abierta else 0.35
        else:
            valor = 0.0
        self.model.SetParameterValue(self._param_boca, valor)
        self._aplicar_encuadre()
        self.model.Update()
        self.model.Draw()
        if self._encuadrando:
            self._converger_encuadre()

    def destroy(self):
        try:
            if self.model is not None and self.winfo_ismapped():
                self.model.DestroyRenderer()
                if self._gl_global:
                    live2d.glRelease()
        except Exception:
            pass
        try:
            super().destroy()
        except Exception:
            pass

    # ----- control desde el asistente (siempre en el hilo principal) -----
    def hablar_texto(self, texto):
        duracion = max(0.8, min(4.0, len(texto) / 16))
        self._hablando_hasta = time.time() + duracion

    def boca(self, abierta):
        if abierta:
            self._hablando_hasta = time.time() + 1.0
        else:
            self._hablando_hasta = 0

    def expresion(self, nombre, activa=True):
        if self.model is None or self._fallo:
            return
        try:
            if activa and nombre:
                candidato = str(nombre)
                if not candidato.endswith(".exp3"):
                    candidato += ".exp3"
                self._expresion_actual = candidato
                self.model.SetExpression(candidato)
            else:
                self._expresion_actual = ""
                self.model.ResetExpression()
        except Exception:
            pass

    def expresion_estado(self, estado):
        expresion_actual = EXPRESIONES.get(estado, "")
        if not expresion_actual:
            self.expresion("", activa=False)
            return
        self.expresion(expresion_actual, activa=True)

    # ----- encuadre cenital (cintura para arriba) -----
    def _bbox_modelo(self):
        if GL is None:
            return (0, 0, max(1, self.winfo_width()), max(1, self.winfo_height()))
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        try:
            buf = GL.glReadPixels(0, 0, w, h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        except Exception:
            return (0, 0, w, h)
        br = int(self.color_fondo[0] * 255)
        bg = int(self.color_fondo[1] * 255)
        bb = int(self.color_fondo[2] * 255)
        minx = miny = 10 ** 9
        maxx = maxy = -1
        for y in range(h):
            base = y * w * 4
            for x in range(w):
                o = base + x * 4
                r, g, b = buf[o], buf[o + 1], buf[o + 2]
                if abs(r - br) > 12 or abs(g - bg) > 12 or abs(b - bb) > 12:
                    if x < minx:
                        minx = x
                    if x > maxx:
                        maxx = x
                    if y < miny:
                        miny = y
                    if y > maxy:
                        maxy = y
        if maxy < 0:
            return (0, 0, w, h)
        return (minx, miny, maxx, maxy)

    def _aplicar_encuadre(self):
        if not self._encuadre_pendiente_zoom and self._offset_y == 0.0:
            return
        try:
            if self._encuadre_pendiente_zoom:
                self.model.SetScale(self._encuadre_zoom)
                self._encuadre_pendiente_zoom = False
            self.model.SetOffsetY(self._offset_y)
        except Exception:
            pass

    def _converger_encuadre(self):
        try:
            if self._encuadre_base is None:
                bb = self._bbox_modelo()
                if bb[3] <= bb[1]:
                    return
                self._encuadre_base = bb
                _, y0, _, y1 = bb
                h = self.winfo_height()
                cintura = y0 + ENCUADRE_CINTURA_FRACC * (y1 - y0)
                if y1 - cintura < 20:
                    self._encuadrando = False
                    return
                self._encuadre_objetivo = (1.0 - ENCUADRE_MARGEN_SUP) * h
                self._encuadre_zoom = (
                    self._encuadre_objetivo + ENCUADRE_FONDO_PX
                ) / (y1 - cintura)
                self._encuadre_pendiente_zoom = True
                return
            bb = self._bbox_modelo()
            cabeza = bb[3]
            delta = (self._encuadre_objetivo - cabeza) / 250.0
            self._offset_y += delta
            self._encuadre_pasos += 1
            if (
                abs(self._encuadre_objetivo - cabeza) < 3
                or self._encuadre_pasos > 60
            ):
                self._encuadrando = False
        except Exception:
            self._encuadrando = False


def ruta_robin_l2d():
    return os.path.join(
        DIRECTORIO_PROYECTO, "assets", "robin_l2d", "robin.model3.json"
    )


def robin_l2d_disponible():
    return OpenGLFrame is not None and os.path.exists(ruta_robin_l2d())


def _color_gl(color):
    if color is None:
        return COLOR_FONDO
    if isinstance(color, str):
        s = color.lstrip("#")
        if len(s) == 6:
            return tuple(int(s[i : i + 2], 16) / 255 for i in (0, 2, 4)) + (1.0,)
        return COLOR_FONDO
    return tuple(color)


class RobinL2D:
    """Adaptador que expone el mismo contrato que AvatarRobin (malla) hacia
    la interfaz, pero renderizando el modelo Live2D de Robin (derivado de
    Akari). Puede ir incrustado en un marco de la GUI o flotante."""

    def __init__(
        self,
        master,
        on_estado=None,
        escala=1.0,
        incrustado=False,
        color_fondo=None,
    ):
        self._on_estado = on_estado
        self._incrustado = bool(incrustado)
        self._activo = True
        if color_fondo is None:
            color_fondo = COLOR_FONDO
        if self._incrustado:
            self._l2d = AvatarL2D(
                master, on_estado=on_estado, width=262, height=420
            )
            self._l2d.color_fondo = _color_gl(color_fondo)
            self._l2d._gl_global = False
        else:
            from avatar_flotante import AvatarFlotante

            self._l2d = AvatarFlotante(
                master, on_estado=on_estado, ancho=240, alto=400
            )

    @property
    def model(self):
        return self._l2d.model

    @property
    def _fallo(self):
        return self._l2d._fallo

    def _estado(self, texto):
        if self._on_estado:
            try:
                self._on_estado(texto)
            except Exception:
                pass

    def iniciar(self):
        m = self._l2d
        try:
            if self._incrustado:
                m.pack(fill=tk.BOTH, expand=True)
            else:
                m.iniciar()
            m.update_idletasks()
        except Exception:
            pass
        self._estado("Robin Live2D lista")

    def expresion(self, nombre, activa=True):
        m = self._l2d
        if m is None or m._fallo or m.model is None:
            return
        try:
            if activa and nombre:
                candidato = str(nombre)
                if not candidato.endswith(".exp3"):
                    candidato += ".exp3"
                m.model.SetExpression(candidato)
            else:
                m.model.ResetExpression()
        except Exception:
            pass

    def expresion_estado(self, estado):
        expr = EXPRESIONES.get(estado, "")
        if expr:
            self.expresion(expr, activa=True)
        else:
            self.expresion("", activa=False)

    def hablar_texto(self, texto):
        try:
            self._l2d.hablar_texto(texto)
        except Exception:
            pass

    def actividad(self, texto, duracion=3.5):
        self._estado(f"Robin: {texto}")

    def gesto(self, nombre):
        if nombre == "saludo":
            self.expresion_estado("respuesta")
            self.hablar_texto("¡Hola!")

    def detener(self):
        self._activo = False
        m = self._l2d
        try:
            if hasattr(m, "detener"):
                m.detener()
            else:
                m.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    import tkinter as tk

    root = tk.Tk()
    root.title("Prueba avatar 2D")
    frame = AvatarL2D(root, on_estado=print, width=300, height=450)
    frame.pack(fill=tk.BOTH, expand=True)
    root.after(3000, lambda: print("EXPRESIONES:", frame.model.GetExpressionIds() if frame.model else None))
    root.after(3500, lambda: frame.expresion("EyesLove.exp3", activa=True))
    root.after(6000, lambda: frame.expresion("EyesLove.exp3", activa=False))
    root.after(6500, lambda: frame.hablar_texto(
        "Hola, soy akari, tu asistente ahora puede animarme en la propia ventana."
    ))
    root.after(12000, root.destroy)
    root.mainloop()