# Control de aplicaciones (punto 10) con lista blanca de seguridad.
# Permite abrir/cerrar apps (con confirmación si no está en la lista blanca),
# encender/apagar procesos, y gestionar la lista blanca en data/apps.json.
import os
import json
import subprocess
import threading

import tools.registro as reg
import tools.asistente_util as util

_LOCK = threading.Lock()

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ARCHIVO = os.path.join(_DIR, "apps.json")

# Apps conocidas por defecto: nombre -> comando de apertura.
# Se pueden añadir más con agregar_app_whitelist.
APPS_DEFECTO = {
    "navegador": "start msedge",
    "edge": "start msedge",
    "chrome": "start chrome",
    "bloc de notas": "notepad",
    "notepad": "notepad",
    "calculadora": "calc",
    "explorador": "explorer",
    "explorador de archivos": "explorer",
}


def _cargar():
    if os.path.exists(ARCHIVO):
        try:
            with open(ARCHIVO, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, dict):
                return datos
        except Exception:
            pass
    return {"whitelist": [], "apps": dict(APPS_DEFECTO)}


def _guardar(datos):
    os.makedirs(_DIR, exist_ok=True)
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _normalizar(nombre):
    return (nombre or "").strip().lower()


def _esta_en_whitelist(nombre, datos):
    return _normalizar(nombre) in {_normalizar(a) for a in datos.get("whitelist", [])}


@reg.registrar(
    "listar_apps",
    descripcion="Muestra las aplicaciones conocidas por Robin y cuáles están en la lista blanca (permitidas para abrir sin confirmación).",
)
def listar_apps():
    datos = _cargar()
    apps = datos.get("apps", {})
    wl = {_normalizar(a) for a in datos.get("whitelist", [])}
    if not apps:
        return "No hay aplicaciones configuradas."
    lineas = ["Aplicaciones conocidas:"]
    for nombre, comando in apps.items():
        permitida = _normalizar(nombre) in wl or not comando.startswith("start")
        etiqueta = " [permitida]" if permitida else " [necesita confirmación]"
        lineas.append(f"- {nombre}{etiqueta}: {comando}")
    return "\n".join(lineas)


@reg.registrar(
    "abrir_app",
    descripcion="Abre una aplicación. Si no está en la lista blanca, pedirá confirmación. Ejemplos: 'navegador', 'calculadora', 'bloc de notas'.",
    parametros={"nombre": {"type": "string", "description": "Nombre de la aplicación a abrir.", "requerido": True}},
)
def abrir_app(nombre):
    datos = _cargar()
    clave = _normalizar(nombre)
    apps = datos.get("apps", {})
    # Buscar por nombre exacto o contiene.
    comando = None
    for n, c in apps.items():
        if clave in _normalizar(n) or _normalizar(n) in clave:
            comando = c
            break
    if not comando:
        return f"No conozco la aplicación '{nombre}'. Usa listar_apps o agrégala con agregar_app_whitelist."
    if not _esta_en_whitelist(nombre, datos) and comando.startswith("start"):
        if not util.pedir_confirmacion(f"¿Permites abrir {nombre}?"):
            return f"Cancelado: {nombre} no está en la lista blanca y no se confirmó. Usa agregar_app_whitelist para permitirla."
    try:
        if comando.startswith("start"):
            subprocess.Popen(["cmd", "/c", comando], shell=True)
        else:
            subprocess.Popen(comando, shell=True)
        return f"Abriendo {nombre}."
    except Exception as e:
        return f"Error al abrir {nombre}: {e}"


@reg.registrar(
    "cerrar_app",
    descripcion="Cierra una aplicación por su nombre de proceso (ej. 'msedge', 'notepad', 'chrome'). Pide confirmación.",
    parametros={"proceso": {"type": "string", "description": "Nombre del proceso a cerrar (sin .exe).", "requerido": True}},
)
def cerrar_app(proceso):
    datos = _cargar()
    if not _esta_en_whitelist(proceso, datos):
        if not util.pedir_confirmacion(f"¿Cierro el proceso {proceso}?"):
            return f"Cancelado: cierre de {proceso} no confirmado."
    try:
        p = (proceso or "").strip().rstrip(".exe")
        r = subprocess.run(["taskkill", "/IM", f"{p}.exe", "/F"], capture_output=True, text=True)
        if r.returncode == 0:
            return f"Proceso {proceso} cerrado."
        return f"No se pudo cerrar {proceso} (¿está en ejecución?): {r.stderr.strip()[:200]}"
    except Exception as e:
        return f"Error al cerrar {proceso}: {e}"


@reg.registrar(
    "agregar_app_whitelist",
    descripcion="Añade una aplicación a la lista blanca para que Robin pueda abrirla sin confirmación. Puedes dar un comando de apertura opcional.",
    parametros={
        "nombre": {"type": "string", "description": "Nombre de la aplicación (ej. 'Canva', 'Spotify').", "requerido": True},
        "comando": {"type": "string", "description": "Comando o ruta para abrirla (opcional). Ej: 'start spotify' o 'C:/ruta/app.exe'."},
    },
)
def agregar_app_whitelist(nombre, comando=None):
    nombre = (nombre or "").strip()
    if not nombre:
        return "Error: dime el nombre de la aplicación."
    with _LOCK:
        datos = _cargar()
        datos["apps"][nombre] = comando or f"start {nombre}"
        if _normalizar(nombre) not in {_normalizar(a) for a in datos["whitelist"]}:
            datos["whitelist"].append(nombre)
        _guardar(datos)
    return f"{nombre} añadida a la lista blanca: {datos['apps'][nombre]}"


@reg.registrar(
    "quitar_app_whitelist",
    descripcion="Quita una aplicación de la lista blanca (dejará de poderse abrir sin confirmación).",
    parametros={"nombre": {"type": "string", "description": "Nombre de la aplicación a quitar de la lista blanca.", "requerido": True}},
)
def quitar_app_whitelist(nombre):
    nombre = (nombre or "").strip()
    datos = _cargar()
    clave = _normalizar(nombre)
    nueva = [a for a in datos["whitelist"] if _normalizar(a) != clave]
    datos["whitelist"] = nueva
    _guardar(datos)
    return f"{nombre} quitada de la lista blanca."
