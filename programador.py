# Motor de tareas programadas (cron local).
#
# Permite programar acciones automáticas a ciertas horas (diarias o en días
# concretos de la semana): avisos, comandos y acciones del sistema que ya
# existen en sistema.py. Un hilo demonio revisa periódicamente qué tareas tocan
# y las ejecuta.
import json
import os
import subprocess
import threading
import time
from datetime import datetime

import sistema

ARCHIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tareas_programadas.json")

# Callback opcional para notificar al usuario (la GUI lo conecta para mostrar
# avisos en pantalla). Por defecto imprime.
on_aviso = None

_lock = threading.Lock()


def cargar():
    try:
        if os.path.exists(ARCHIVO):
            with open(ARCHIVO, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, list):
                return datos
    except Exception:
        pass
    return []


def guardar(lista):
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


def _proximo_id(lista):
    ids = [int(t.get("id", 0)) for t in lista if str(t.get("id", "0")).isdigit()]
    return (max(ids) + 1) if ids else 1


def agregar(nombre, hora, dias="*", accion="aviso", parametros=None):
    """Programa una tarea.
    - hora: 'HH:MM' (reloj de 24h)
    - dias: '*' (todos) o lista de ints 0-6 (0=Lunes ... 6=Domingo)
    - accion: 'aviso' | 'comando' | 'abrir' | 'sistema:<nombre>'
    - parametros: según acción (ver _ejecutar)
    Devuelve un texto con el resultado o un error."""
    nombre = (nombre or "").strip()
    parametros = parametros or {}
    hora = (hora or "").strip()
    try:
        hh, mm = hora.split(":")
        hh, mm = int(hh), int(mm)
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return "Error: hora inválida. Usa formato HH:MM (ej. '09:30')."
    except ValueError:
        return "Error: hora inválida. Usa formato HH:MM (ej. '09:30')."

    if isinstance(dias, str):
        dias = dias.strip()
        if dias == "*":
            dias_ok = "*"
        else:
            try:
                dias_ok = [int(d) % 7 for d in dias.replace(" ", "").split(",")]
            except ValueError:
                return "Error: 'dias' debe ser '*' o una lista de días (0=Lunes..6=Domingo)."
    elif isinstance(dias, (list, tuple)):
        dias_ok = [int(d) % 7 for d in dias]
    else:
        return "Error: 'dias' inválido."

    accion = (accion or "aviso").strip()
    tarea = {
        "id": None,
        "nombre": nombre or f"Tarea {datetime.now():%H:%M}",
        "hora": f"{hh:02d}:{mm:02d}",
        "dias": dias_ok,
        "accion": accion,
        "parametros": parametros if isinstance(parametros, dict) else {},
        "activa": True,
        "ultimo_disparo": None,
        "creada": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    lista = cargar()
    tarea["id"] = _proximo_id(lista)
    lista.append(tarea)
    guardar(lista)
    desc_dias = "todos los días" if dias_ok == "*" else ", ".join(
        ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"][d] for d in dias_ok
    )
    return f"Tarea #{tarea['id']} programada: '{tarea['nombre']}' a las {tarea['hora']} ({desc_dias})."


def listar():
    lista = cargar()
    if not lista:
        return "No tienes tareas programadas."
    lineas = []
    dias_n = ["L", "M", "X", "J", "V", "S", "D"]
    for t in lista:
        estado = "✅" if t.get("activa", True) else "⏸️"
        dias = "todos" if t.get("dias") == "*" else "-".join(
            dias_n[d] for d in (t.get("dias") or [])
        )
        accion = t.get("accion", "aviso")
        lineas.append(
            f"#{t['id']} {estado} '{t.get('nombre')}' "
            f"a las {t.get('hora')} ({dias}) [{accion}]"
        )
    return "\n".join(lineas)


def borrar(indice):
    try:
        idx = int(indice)
    except (TypeError, ValueError):
        return "Error: índice inválido."
    lista = cargar()
    for i, t in enumerate(lista):
        if t.get("id") == idx:
            texto = t.get("nombre", "?")
            lista.pop(i)
            guardar(lista)
            return f"Tarea programada #{idx} eliminada: {texto}"
    return f"Error: no existe la tarea #{idx}."


def activar_desactivar(indice, activa):
    try:
        idx = int(indice)
    except (TypeError, ValueError):
        return "Error: índice inválido."
    lista = cargar()
    for t in lista:
        if t.get("id") == idx:
            t["activa"] = bool(activa)
            guardar(lista)
            estado = "activada" if activa else "pausada"
            return f"Tarea #{idx} {estado}: {t.get('nombre')}"
    return f"Error: no existe la tarea #{idx}."


# --------------------------- ejecución ---------------------------

def _toca(tarea, ahora):
    if not tarea.get("activa", True):
        return False
    try:
        hh, mm = map(int, tarea["hora"].split(":"))
    except (KeyError, ValueError):
        return False
    minuto = ahora.hour * 60 + ahora.minute
    if minuto != hh * 60 + mm:
        return False
    dias = tarea.get("dias")
    if dias != "*" and ahora.weekday() not in (dias or []):
        return False
    # Evitar doble disparo en el mismo minuto del mismo día.
    marca = ahora.strftime("%Y-%m-%d %H:%M")
    if tarea.get("ultimo_disparo") == marca:
        return False
    return True


def _notificar(texto):
    if callable(on_aviso):
        try:
            on_aviso(texto)
            return
        except Exception:
            pass
    try:
        print(f"\n[Programada] {texto}")
    except Exception:
        pass


def _respaldar_desde_param(valor, nombre):
    """Acepta 'parametros' como dict o como string con 'clave=valor'."""
    v = valor or {}
    if isinstance(v, str):
        d = {}
        for par in v.split(","):
            if "=" in par:
                k, val = par.split("=", 1)
                d[k.strip()] = val.strip()
        return d.get(nombre)
    return v.get(nombre)


def _ejecutar(tarea):
    accion = tarea.get("accion", "aviso")
    p = tarea.get("parametros") or {}
    nombre = tarea.get("nombre", "")
    if accion == "aviso":
        texto = p.get("texto") if isinstance(p, dict) else p
        _notificar(f"📣 {nombre}: {texto or ''}".rstrip())
        return
    if accion == "comando":
        comando = p.get("comando") if isinstance(p, dict) else None
        if comando:
            try:
                r = subprocess.run(comando, shell=True, capture_output=True,
                                   text=True, errors="replace", timeout=60)
                _notificar(f"⚙️ Comando '{comando}' -> código {r.returncode}")
            except Exception as e:
                _notificar(f"⚙️ Error en comando: {e}")
        return
    if accion == "abrir":
        ruta = p.get("ruta") if isinstance(p, dict) else None
        if ruta:
            try:
                import webbrowser
                if str(ruta).startswith(("http://", "https://")):
                    webbrowser.open(ruta)
                else:
                    os.startfile(ruta)
                _notificar(f"🚀 Abierto: {ruta}")
            except Exception as e:
                _notificar(f"🚀 Error al abrir: {e}")
        return
    if accion == "sistema:limpiar_temporales":
        dias = int(_respaldar_desde_param(p, "dias") or 7)
        r = sistema.limpiar_temporales(dias)
        _notificar(f"🧹 {r}")
        return
    if accion == "sistema:vaciar_papelera":
        _notificar(f"🗑️ {sistema.vaciar_papelera()}")
        return
    if accion == "sistema:capturar_pantalla":
        r = sistema.capturar_pantalla()
        _notificar(f"📸 {r}")
        return
    if accion == "sistema:ajustar_volumen":
        nivel = _respaldar_desde_param(p, "nivel")
        if nivel is not None:
            _notificar(f"🔊 {sistema.ajustar_volumen(int(nivel))}")
        return
    if accion == "sistema:abrir_url":
        url = _respaldar_desde_param(p, "url")
        if url:
            import webbrowser
            webbrowser.open(url)
            _notificar(f"🌐 Abriendo: {url}")
        return
    _notificar(f"⚠️ Acción programada no reconocida: {accion}")


def _tick(ahora=None):
    """Ejecuta las tareas que tocan en este minuto. Devuelve cantidad disparada."""
    ahora = ahora or datetime.now()
    lista = cargar()
    disparadas = []
    nuevas = []
    for t in lista:
        if _toca(t, ahora):
            t["ultimo_disparo"] = ahora.strftime("%Y-%m-%d %H:%M")
            disparadas.append(t)
        nuevas.append(t)
    if disparadas:
        guardar(nuevas)
        for t in disparadas:
            try:
                _ejecutar(t)
            except Exception as e:
                _notificar(f"⚠️ Falló la tarea #{t.get('id')}: {e}")
    return len(disparadas)


# --------------------------- hilo ---------------------------

def iniciar_hilo(intervalo_segundos=20):
    """Arranca el hilo demonio que revisa las tareas cada N segundos."""
    def bucle():
        while True:
            try:
                _tick()
            except Exception:
                pass
            time.sleep(intervalo_segundos)

    hilo = threading.Thread(target=bucle, daemon=True, name="programador")
    hilo.start()
    return hilo


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("listar", "-l"):
        print(listar())
    elif len(sys.argv) > 1 and sys.argv[1] in ("test",):
        print("Tareas:", cargar())
        print("Ahora toca(prueba con hora exacta). Ejecuta un tick manual :", _tick())
    else:
        print("programador.py: ejecuta las tareas programadas en segundo plano.")
        iniciar_hilo()
        print("Revisando cada 20s. Ctrl+C para salir.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nDetenido.")
