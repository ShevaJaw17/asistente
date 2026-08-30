# avatar_flotante.py - Akari como overlay transparente sobre el escritorio.
# Ventana sin bordes, siempre arriba, click-through, que sigue al cursor.
# Vive como Toplevel de la GUI (misma hebra Tk), igual que el avatar embebido.
import ctypes
import ctypes.wintypes
import tkinter as tk

from avatar_nativo import AvatarL2D

COLOR_TK_CLAVE = "magenta"
CLAVE_VIDA = (1.0, 0.0, 1.0, 1.0)


class AvatarFlotante(AvatarL2D):
    color_fondo = CLAVE_VIDA

    def __init__(
        self,
        root_padre,
        on_estado=None,
        ancho=210,
        alto=360,
        separacion=24,
        elevacion=0.30,
        click_through=True,
    ):
        self._separacion = int(separacion)
        self._elevacion = float(elevacion)
        self._activado = False
        self._ventana = tk.Toplevel(root_padre)
        self._ventana.overrideredirect(True)
        self._ventana.attributes("-topmost", True)
        self._ventana.configure(bg=COLOR_TK_CLAVE)
        try:
            self._ventana.attributes("-transparentcolor", COLOR_TK_CLAVE)
        except Exception:
            pass
        super().__init__(master=self._ventana, on_estado=on_estado, width=ancho, height=alto)
        self._gl_global = False
        self.pack(fill=tk.BOTH, expand=True)
        self._click_through = click_through
        if click_through:
            self._aplicar_click_through()
        self._ventana.withdraw()

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

    def iniciar(self):
        if self._activado:
            return
        self._activado = True
        self._ventana.deiconify()
        self._mover_a_cursor()
        self._ventana.update_idletasks()
        self._ventana.after(33, self._bucle_seguimiento)

    def _mover_a_cursor(self):
        try:
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            x = pt.x - self.winfo_width() - self._separacion
            y = pt.y - int(self.winfo_height() * self._elevacion)
            self._ventana.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _bucle_seguimiento(self):
        self._mover_a_cursor()
        if self._activado:
            try:
                self._ventana.after(33, self._bucle_seguimiento)
            except Exception:
                pass

    def detener(self):
        self._activado = False
        try:
            self.destroy()
        except Exception:
            pass
        try:
            self._ventana.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    import time

    import pyopengltk  # noqa: F401  (asegura registro del frame OpenGL)

    from avatar_nativo import AvatarL2D

    root = tk.Tk()
    emb = AvatarL2D(root, width=220, height=340)
    emb.pack()
    flot = AvatarFlotante(root, ancho=200, alto=340, on_estado=lambda t: print("FLOT:", t))
    flot.iniciar()
    root.after(3000, lambda: flot.expresion("EyesHappy.exp3", activa=True))
    root.after(6000, lambda: flot.hablar_texto("Hola, soy akari, y floto sobre tu escritorio."))
    root.after(9000, lambda: print("ANTES DE DETENER, EMB_OK:", emb.model is not None, emb._fallo))
    root.after(9500, flot.detener)
    root.after(12000, root.destroy)
    root.mainloop()
    time.sleep(0.5)
    print("FIN emb model:", emb.model is not None, "fallo:", emb._fallo)

