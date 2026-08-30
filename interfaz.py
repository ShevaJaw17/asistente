# Interfaz grafica del asistente virtual
import json
import os
import queue
import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import asistente
import avatar

try:
    import voz
except Exception:
    voz = None

try:
    import recordatorios
except Exception:
    recordatorios = None

try:
    import avatar_robin
except Exception:
    avatar_robin = None

try:
    import avatar_nativo as avatar_l2d
    if avatar_l2d.robin_l2d_disponible():
        avatar_l2d.RUTA_MODELO = avatar_l2d.ruta_robin_l2d()
except Exception:
    avatar_l2d = None


def _crear_robin(master, on_estado=None, escala=1.0, incrustado=False, color_fondo=None):
    """Prioriza el modelo Live2D de Robin; respalda con el motor de malla."""
    if avatar_l2d is not None and avatar_l2d.robin_l2d_disponible():
        return avatar_l2d.RobinL2D(
            master,
            on_estado=on_estado,
            escala=escala,
            incrustado=incrustado,
            color_fondo=color_fondo,
        )
    if avatar_robin is not None:
        return avatar_robin.AvatarRobin(
            master,
            on_estado=on_estado,
            escala=escala,
            incrustado=incrustado,
            color_fondo=color_fondo,
        )
    return None

try:
    import proactividad
except Exception:
    proactividad = None


class AsistenteApp:
    def __init__(self, root):
        self.root = root
        root.title("Asistente Virtual Local")
        root.geometry("720x640")
        root.minsize(560, 480)

        self.mensajes = [
            {
                "role": "system",
                "content": asistente.sistema_con_contexto(),
            }
        ]

        self.ocupado = False
        self.voz_activa = True
        self._escuchando = False
        asistente.confirmar_accion = self._confirmar_en_gui

        self.avatar = avatar.AvatarVTubeStudio(on_estado=self._actualizar_estado_avatar)
        self.avatar_robin = None
        self._ultima_actividad = time.time()
        self._proactivo = True
        self._proactivo_generando = False
        self._cola_tk = queue.Queue()
        self.root.after(60, self._drenar_cola_tk)

        self._construir_ui()
        self._agregar_mensaje("sistema", "Asistente iniciado. Escribe para comenzar.")
        if self.avatar.cfg.get("activar_al_iniciar", True):
            self.avatar.conectar()
        if avatar_l2d is None:
            self._iniciar_robin_flotante()
        self.root.after(5000, self._revisar_recordatorios)
        self.root.after(12000, self._bucle_proactividad)

    def _al_tk(self, fn, *args):
        """Programa una llamada a Tk desde el hilo principal (seguro desde
        cualquier hilo). Todo acceso a la interfaz debe pasar por aqui."""
        try:
            if threading.current_thread() is threading.main_thread():
                try:
                    fn(*args)
                    return
                except Exception:
                    pass
            self._cola_tk.put((fn, args))
        except Exception:
            pass

    def _drenar_cola_tk(self):
        try:
            while True:
                try:
                    fn, args = self._cola_tk.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn(*args)
                except Exception:
                    pass
        finally:
            try:
                self.root.after(60, self._drenar_cola_tk)
            except Exception:
                pass

    def _construir_ui(self):
        marco_barra = tk.Frame(self.root, bg="#2b2b2b")
        marco_barra.pack(side=tk.TOP, fill=tk.X)
        tk.Label(
            marco_barra,
            text=" Asistente Virtual (qwen2.5-7b / GPU-Vulkan)",
            bg="#2b2b2b",
            fg="#ffffff",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(side=tk.LEFT, padx=8, pady=6)

        self.btn_avatar = tk.Button(
            marco_barra,
            text="Avatar",
            command=self.toggle_avatar,
            bg="#3a3a3a",
            fg="#e0e0e0",
            activebackground="#555555",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=10,
            pady=4,
        )
        self.btn_avatar.pack(side=tk.RIGHT, padx=(6, 4), pady=4)

        self.btn_robin = tk.Button(
            marco_barra,
            text="Robin",
            command=self.toggle_robin,
            bg="#3a3a3a",
            fg="#e0e0e0",
            activebackground="#555555",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=10,
            pady=4,
        )
        self.btn_robin.pack(side=tk.RIGHT, padx=(0, 4), pady=4)

        self.btn_proactivo = tk.Button(
            marco_barra,
            text="Proactivo ON",
            command=self.toggle_proactivo,
            bg="#3a3a3a",
            fg="#e0e0e0",
            activebackground="#555555",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
        )
        self.btn_proactivo.pack(side=tk.RIGHT, padx=(0, 4), pady=4)

        self.lbl_avatar = tk.Label(
            marco_barra,
            text="â€”",
            bg="#2b2b2b",
            fg="#9e9e9e",
            font=("Segoe UI", 9),
        )
        self.lbl_avatar.pack(side=tk.RIGHT, pady=6)

        self.lbl_estado = tk.Label(
            marco_barra,
            text="Listo",
            bg="#2b2b2b",
            fg="#9ef01a",
            font=("Segoe UI", 9),
        )
        self.lbl_estado.pack(side=tk.RIGHT, padx=10, pady=6)

        self.btn_voz = tk.Button(
            marco_barra,
            text="ðŸ”Š",
            command=self.toggle_voz,
            bg="#3a3a3a",
            fg="#e0e0e0",
            activebackground="#555555",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
        )
        self.btn_voz.pack(side=tk.RIGHT, padx=(6, 2), pady=4)

        self.btn_mic = tk.Button(
            marco_barra,
            text="ðŸŽ¤",
            command=self.toggle_mic,
            bg="#3a3a3a",
            fg="#e0e0e0",
            activebackground="#555555",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
        )
        self.btn_mic.pack(side=tk.RIGHT, padx=(6, 2), pady=4)

        marco_cuerpo = tk.Frame(self.root, bg="#1e1e1e")
        marco_cuerpo.pack(fill=tk.BOTH, expand=True)
        marco_cuerpo.columnconfigure(0, weight=1)
        marco_cuerpo.rowconfigure(0, weight=1)

        self.chat = scrolledtext.ScrolledText(
            marco_cuerpo,
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg="#1e1e1e",
            fg="#e0e0e0",
            font=("Consolas", 10),
        )
        self.chat.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=(8, 4))

        self.avatar_robin_incrustado = None
        self.lbl_avatar2d = None
        marco_avatar = tk.Frame(marco_cuerpo, bg="#1e1e1e")
        marco_avatar.grid(
            row=0,
            column=1,
            sticky="ns",
            padx=(4, 0),
            pady=(8, 4),
        )
        try:
            robin = _crear_robin(
                marco_avatar,
                on_estado=self._actualizar_estado_robin,
                escala=0.72,
                incrustado=True,
                color_fondo="#1e1e1e",
            )
            if robin is not None:
                robin.iniciar()
                self.avatar_robin_incrustado = robin
        except Exception:
            self.avatar_robin_incrustado = None

        self.chat.tag_config("usuario", foreground="#4fc3f7")
        self.chat.tag_config("asistente", foreground="#81c784")
        self.chat.tag_config("sistema", foreground="#9e9e9e")
        self.chat.tag_config("tool", foreground="#ffb74d")

        marco_entrada = tk.Frame(self.root)
        marco_entrada.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=8)

        self.entrada = tk.Entry(marco_entrada, font=("Segoe UI", 11))
        self.entrada.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=6)
        self.entrada.bind("<Return>", lambda e: self.enviar())

        self.btn_enviar = tk.Button(
            marco_entrada,
            text="Enviar",
            command=self.enviar,
            bg="#2b6cb0",
            fg="#ffffff",
            activebackground="#2c5282",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 10, "bold"),
            padx=16,
            pady=4,
        )
        self.btn_enviar.pack(side=tk.RIGHT)

    def _estado(self, texto, color="#9ef01a"):
        self.lbl_estado.config(text=texto, fg=color)
        if texto.startswith("Pensando"):
            self.avatar.expresion_estado("pensando")
            if self.avatar_robin_incrustado is not None:
                self.avatar_robin_incrustado.expresion_estado("pensando")
            if self.avatar_robin is not None:
                self.avatar_robin.expresion_estado("pensando")
        elif texto == "Error":
            self.avatar.expresion_estado("error")
            if self.avatar_robin_incrustado is not None:
                self.avatar_robin_incrustado.expresion_estado("error")
            if self.avatar_robin is not None:
                self.avatar_robin.expresion_estado("error")

    def _actualizar_estado_robin(self, texto):
        if self.lbl_avatar2d is None:
            return
        etiqueta = texto.replace("Avatar: ", "")
        try:
            self._al_tk(lambda: self.lbl_avatar2d.config(text=etiqueta))
        except Exception:
            pass

    def toggle_avatar(self):
        if self.avatar.conectado:
            self.avatar.desconectar()
        else:
            self.avatar.conectar(reintentos=1)

    def _iniciar_robin_flotante(self):
        if self.avatar_robin is not None:
            return
        robin = _crear_robin(self.root, on_estado=self._actualizar_estado_robin)
        if robin is None:
            return
        try:
            robin.iniciar()
            self.avatar_robin = robin
        except Exception:
            self.avatar_robin = None

    def _robin_actividad(self, texto, duracion=3.5):
        for avatar_act in (self.avatar_robin, self.avatar_robin_incrustado):
            if avatar_act is not None:
                try:
                    avatar_act.actividad(texto, duracion)
                except Exception:
                    pass

    def _robin_gesto(self, nombre):
        for avatar_act in (self.avatar_robin, self.avatar_robin_incrustado):
            if avatar_act is not None:
                try:
                    avatar_act.gesto(nombre)
                except Exception:
                    pass

    def toggle_robin(self):
        if self.avatar_robin is not None:
            self.avatar_robin.detener()
            self.avatar_robin = None
            self._estado("Listo")
            return
        robin = _crear_robin(self.root, on_estado=self._actualizar_estado_robin)
        if robin is None:
            self._estado("Robin no disponible", "#ef5350")
            return
        try:
            robin.iniciar()
            self.avatar_robin = robin
            self._estado("Robin: activa")
        except Exception as e:
            self.avatar_robin = None
            self._estado(f"Robin: error {e}", "#ef5350")

    def toggle_voz(self):
        self.voz_activa = not self.voz_activa
        self.btn_voz.config(text="ðŸ”Š" if self.voz_activa else "ðŸ”‡")

    def toggle_mic(self):
        if voz is None or self._escuchando or self.ocupado:
            return
        self._escuchando = True
        self.btn_mic.config(text="Escuchando...", state=tk.DISABLED)
        self._estado("Escuchando...", "#4fc3f7")
        threading.Thread(target=self._escuchar_y_enviar, daemon=True).start()

    def _escuchar_y_enviar(self):
        try:
            texto, error = voz.escuchar()
        except Exception as e:
            texto, error = "", f"{e}"

        def final():
            self._escuchando = False
            self.btn_mic.config(text="ðŸŽ¤", state=tk.NORMAL)
            self.entrada.focus_set()
            if error == "silencioso":
                self._estado("Listo")
                return
            if error:
                self._estado(f"Mic: {error}", "#ef5350")
                return
            self._estado("Listo")
            self.entrada.delete(0, tk.END)
            self.entrada.insert(0, texto)
            self.enviar()

        try:
            self._al_tk(final)
        except Exception:
            pass

    def _actualizar_estado_avatar(self, texto):
        etiqueta = texto.replace("Avatar: ", "")
        if "conectado" in texto and "desconectado" not in texto:
            color = "#9ef01a"
        elif "sin websocket" in texto or "no disponible" in texto or "desconectado" in texto:
            color = "#ef5350"
        else:
            color = "#ffb74d"
        self._al_tk(lambda: self.lbl_avatar.config(text=etiqueta, fg=color))

    def _agregar_mensaje(self, quien, texto):
        self.chat.config(state=tk.NORMAL)
        etiqueta = {"usuario": "Tu", "asistente": "Asistente",
                    "sistema": "Sistema", "tool": "Herramienta"}[quien]
        self.chat.insert(tk.END, f"{etiqueta}: ", quien)
        self.chat.insert(tk.END, f"{texto}\n\n", "normal")
        self.chat.config(state=tk.DISABLED)
        self.chat.see(tk.END)

    def _confirmar_en_gui(self, mensaje):
        respuesta = queue.Queue()
        self._al_tk(
            lambda: respuesta.put(
                messagebox.askyesno(
                    "Confirmar comando",
                    f"Â¿Ejecutar este comando?\n\n{mensaje}",
                )
            )
        )
        return respuesta.get()

    def enviar(self):
        if self.ocupado:
            return
        entrada = self.entrada.get().strip()
        if not entrada:
            return
        self._ultima_actividad = time.time()
        if entrada.lower() in ("salir", "exit", "quit"):
            self.root.after(300, self.root.destroy)
            return
        self.entrada.delete(0, tk.END)
        self._agregar_mensaje("usuario", entrada)
        self.mensajes.append({"role": "user", "content": entrada})
        self.ocupado = True
        self._estado("Pensando...", "#ffb74d")
        self.btn_enviar.config(state=tk.DISABLED)
        threading.Thread(target=self._procesar, daemon=True).start()

    def _procesar(self):
        try:
            resultado = self._procesar_mensajes()
            self._al_tk(self._finalizar, resultado)
        except Exception as e:
            self._al_tk(self._finalizar, f"[Error: {e}]")

    def _procesar_mensajes(self):
        while True:
            mensaje = asistente.responder_asistente(self.mensajes)
            self.mensajes.append(
                {
                    "role": "assistant",
                    "content": mensaje.get("content", ""),
                    "tool_calls": mensaje.get("tool_calls"),
                }
            )
            tool_calls = mensaje.get("tool_calls")
            if not tool_calls:
                texto = mensaje.get("content", "")
                try:
                    asistente.guardar_intercambio(self.mensajes)
                except Exception:
                    pass
                return texto
            for llamada in tool_calls:
                nombre = llamada["function"]["name"]
                args = llamada["function"].get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                self._al_tk(self._robin_actividad, f"Ejecutando: {nombre}â€¦", 2.2)
                resultado = asistente.ejecutar_herramienta(nombre, args)
                self._al_tk(self._robin_actividad, "Hecho âœ“", 1.2)
                self.mensajes.append(
                    {
                        "role": "tool",
                        "tool_call_id": llamada.get("id", ""),
                        "content": str(resultado),
                    }
                )

    def _finalizar(self, texto):
        self.ocupado = False
        self.btn_enviar.config(state=tk.NORMAL)
        if texto and texto.startswith("[Error"):
            self._estado("Error", "#ef5350")
            self._agregar_mensaje("sistema", texto)
        else:
            self._estado("Listo")
            self._agregar_mensaje("asistente", texto)
            self.avatar.expresion_estado("respuesta")
            self.avatar.hablar_texto(texto)
            if self.avatar_robin_incrustado is not None:
                self.avatar_robin_incrustado.expresion_estado("respuesta")
                self.avatar_robin_incrustado.hablar_texto(texto)
            if self.avatar_robin is not None:
                self.avatar_robin.expresion_estado("respuesta")
                self.avatar_robin.hablar_texto(texto)
            if self.voz_activa and voz is not None:
                voz.hablar(texto)
        self.entrada.focus_set()

    def _revisar_recordatorios(self):
        try:
            disparados = recordatorios.vencidos()
        except Exception:
            disparados = []
        for r in disparados:
            texto = r.get("texto") or "Tienes un recordatorio."
            self._agregar_mensaje("sistema", f"[Recordatorio] {texto}")
            self._notificar_recordatorio(texto)
            self._robin_actividad(f"Recordatorio: {texto}", 4.0)
            if self.voz_activa and voz is not None:
                try:
                    voz.hablar(f"Recordatorio: {texto}")
                except Exception:
                    pass
        self.root.after(10000, self._revisar_recordatorios)

    def _notificar_recordatorio(self, texto):
        try:
            ventana = tk.Toplevel(self.root)
            ventana.title("Recordatorio")
            ventana.attributes("-topmost", True)
            ventana.configure(bg="#2b2b2b")
            x = self.root.winfo_rootx() + max(0, self.root.winfo_width() - 360)
            y = self.root.winfo_rooty() + 30
            ventana.geometry(f"+{x}+{y}")
            marco = tk.Frame(ventana, bg="#2b2b2b", padx=14, pady=12)
            marco.pack(fill=tk.BOTH, expand=True)
            tk.Label(
                marco,
                text="[Recordatorio]",
                bg="#2b2b2b",
                fg="#ffb74d",
                font=("Segoe UI", 11, "bold"),
            ).pack(anchor="w")
            tk.Label(
                marco,
                text=texto,
                bg="#2b2b2b",
                fg="#ffffff",
                font=("Segoe UI", 10),
                wraplength=300,
                justify="left",
            ).pack(anchor="w", pady=(6, 8))
            tk.Button(
                marco,
                text="Entendido",
                bg="#ffb74d",
                fg="#1c1c1c",
                command=ventana.destroy,
                relief=tk.FLAT,
                font=("Segoe UI", 9),
            ).pack(anchor="e")
            self.root.after(25000, ventana.destroy)
        except Exception:
            pass

    def toggle_proactivo(self):
        self._proactivo = not self._proactivo
        self.btn_proactivo.config(
            text="Proactivo ON" if self._proactivo else "Proactivo OFF"
        )

    def _bucle_proactividad(self):
        try:
            if (
                self._proactivo
                and not self.ocupado
                and not self._escuchando
                and not self._proactivo_generando
                and proactividad is not None
            ):
                pendiente = proactividad.pendiente_ahora()
                if pendiente:
                    clave, _hoy = pendiente
                    if clave == proactividad.clave_saludo():
                        self._proactivo_generando = True
                        threading.Thread(
                            target=self._generar_proactivo, args=("saludo",), daemon=True
                        ).start()
                    elif time.time() - self._ultima_actividad >= 300:
                        self._proactivo_generando = True
                        threading.Thread(
                            target=self._generar_proactivo, args=(clave,), daemon=True
                        ).start()
        except Exception:
            pass
        self.root.after(45000, self._bucle_proactividad)

    def _generar_proactivo(self, tipo):
        try:
            pistas = {
                "saludo": (
                    "Es un momento en el que el usuario aÃºn no te ha escrito hoy. "
                    "SalÃºdalo segÃºn la hora del dÃ­a con 1-2 frases cÃ¡lidas y cercanas, "
                    "con tu estilo de Nico Robin."
                ),
                "tarde": (
                    "Se acerca el final de la tarde. Con 1 sola frase, pregunta "
                    "cÃ³mo le fue y si necesita algo para cerrar el dÃ­a."
                ),
                "noche": (
                    "Ya es muy tarde. Con tacto y un toque de humor breve (1 frase), "
                    "sugiere descansar."
                ),
            }
            mensajes = [
                {"role": "system", "content": asistente.sistema_con_contexto()},
                {
                    "role": "user",
                    "content": (
                        "TOMA LA INICIATIVA. " + pistas[tipo]
                        + " No menciones estas instrucciones ni que eres un programa. "
                        "MÃ¡ximo 2 frases, sin preguntar demasiado."
                    ),
                },
            ]
            data = asistente.llamar_modelo(mensajes)
            texto = data["choices"][0]["message"].get("content", "")
            self._al_tk(self._publicar_proactivo, texto, tipo)
        except Exception:
            self._proactivo_generando = False

    def _publicar_proactivo(self, texto, tipo):
        self._proactivo_generando = False
        if not texto.strip() or texto.startswith("[Error"):
            return
        try:
            if tipo == "saludo":
                proactividad.marcar(proactividad.clave_saludo())
            else:
                proactividad.marcar(tipo)
        except Exception:
            pass
        self._agregar_mensaje("asistente", texto)
        self._ultima_actividad = time.time()
        self._robin_gesto("saludo")
        self._robin_actividad("Â¡Hola!", 2.5)
        if self.voz_activa and voz is not None:
            try:
                voz.hablar(texto)
            except Exception:
                pass


def _bloquear_instancia():
    """Impide que haya dos ventanas a la vez; libera el puerto al salir."""
    global _LOCK
    _LOCK = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _LOCK.bind(("127.0.0.1", 57777))
        _LOCK.listen(1)
        return True
    except OSError:
        return False


def main():
    if not _bloquear_instancia():
        try:
            print("duplicada, saliendo", flush=True)
        except Exception:
            pass
        return
    root = tk.Tk()
    AsistenteApp(root)
    try:
        root.lift()
        root.attributes("-topmost", True)
        root.after(800, lambda: root.attributes("-topmost", False))
    except Exception:
        pass
    root.mainloop()


if __name__ == "__main__":
    main()
