# Historial de conversación persistente por sesiones.
# Guarda conversaciones agrupadas por sesión (client_id) en historial_sesiones.json,
# lo que permite retomar conversaciones entre sesiones y desde el móvil/web.
import os
import json
import threading
from datetime import datetime

import tools.registro as reg

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

ARCHIVO = os.path.join(_DIR, "historial_sesiones.json")

_LOCK = threading.Lock()


def _cargar():
    if os.path.exists(ARCHIVO):
        try:
            with open(ARCHIVO, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, dict):
                return datos
        except Exception:
            pass
    return {"sesiones": {}, "actual": "default"}


def _guardar(datos):
    os.makedirs(_DIR, exist_ok=True)
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _sesion_id(client_id="default"):
    datos = _cargar()
    return datos.get("actual", "default") if client_id == "default" else client_id


def guardar_turno(contenido_usuario, respuesta, client_id="default"):
    """Guarda un turno usuario->asistente en la sesión activa persistente."""
    if not contenido_usuario and not respuesta:
        return
    with _LOCK:
        datos = _cargar()
        sid = _sesion_id(client_id)
        sesiones = datos.setdefault("sesiones", {})
        sesion = sesiones.setdefault(
            sid,
            {
                "id": sid,
                "nombre": "Conversación por defecto" if sid == "default" else sid,
                "creada": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "mensajes": [],
            },
        )
        if not contenido_usuario and len(sesion["mensajes"]) > 0 and sesion["mensajes"][-1]["role"] == "assistant":
            sesion["mensajes"][-1]["content"] = respuesta
        else:
            if contenido_usuario:
                sesion["mensajes"].append(
                    {"role": "user", "content": contenido_usuario, "ts": datetime.now().strftime("%H:%M")}
                )
            sesion["mensajes"].append(
                {"role": "assistant", "content": respuesta, "ts": datetime.now().strftime("%H:%M")}
            )
        # Límite de mensajes por sesión para no inflar el archivo.
        sesion["mensajes"] = sesion["mensajes"][-200:]
        _guardar(datos)


@reg.registrar(
    "nueva_sesion",
    descripcion="Inicia una nueva conversación limpia con un nombre de tema. Devuelve el código de la sesión.",
    parametros={"nombre": {"type": "string", "description": "Nombre o tema de la nueva sesión.", "requerido": True}},
)
def nueva_sesion(nombre):
    with _LOCK:
        datos = _cargar()
        sid = "s" + datetime.now().strftime("%Y%m%d%H%M%S")
        datos["sesiones"][sid] = {
            "id": sid,
            "nombre": nombre,
            "creada": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "mensajes": [],
        }
        datos["actual"] = sid
        _guardar(datos)
    return f"Sesión nueva creada: '{nombre}' (código {sid}). A partir de ahora escribo aquí."


@reg.registrar(
    "listar_sesiones",
    descripcion="Muestra todas las sesiones de conversación guardadas con su código y fecha.",
)
def listar_sesiones():
    datos = _cargar()
    sesiones = datos.get("sesiones", {})
    if not sesiones:
        return "Todavía no hay sesiones guardadas."
    actual = datos.get("actual", "")
    lineas = []
    for sid, s in sorted(sesiones.items(), key=lambda kv: kv[1].get("creada", ""), reverse=True):
        marco = " [ACTIVA]" if sid == actual else ""
        n = len(s.get("mensajes", [])) // 2
        lineas.append(f"{sid}: '{s.get('nombre')}' ({s.get('creada')}{marco}, {n} turnos)")
    return "\n".join(lineas) if lineas else "No hay sesiones."


@reg.registrar(
    "cambiar_sesion",
    descripcion="Cambia a una sesión de conversación existente usando su código (de listar_sesiones). Las futuras respuestas se guardarán ahí.",
    parametros={"codigo": {"type": "string", "description": "Código de la sesión a la que cambiar.", "requerido": True}},
)
def cambiar_sesion(codigo):
    with _LOCK:
        datos = _cargar()
        sesiones = datos.get("sesiones", {})
        if codigo not in sesiones:
            return f"Error: no existe la sesión '{codigo}'. Usa listar_sesiones para ver los códigos."
        datos["actual"] = codigo
        _guardar(datos)
    return f"Sesión cambiada a '{sesiones[codigo].get('nombre')}' ({codigo})."


@reg.registrar(
    "ver_historial",
    descripcion="Muestra un resumen de la conversación actual (últimos intercambios) de la sesión activa.",
    parametros={"cuantos": {"type": "integer", "description": "Número de turnos a mostrar (por defecto 5)."}},
)
def ver_historial(cuantos=None):
    datos = _cargar()
    sid = datos.get("actual", "default")
    sesion = datos.get("sesiones", {}).get(sid)
    if not sesion:
        return "No hay historial en la sesión actual."
    mensajes = sesion.get("mensajes", [])
    n = cuantos or 5
    ultimos = mensajes[-n * 2 :]
    lineas = []
    for m in ultimos:
        papel = "Tú" if m["role"] == "user" else "Robin"
        texto = m.get("content", "")
        texto = texto if len(texto) <= 120 else texto[:120] + "..."
        lineas.append(f"{m.get('ts','')} {papel}: {texto}")
    return "\n".join(lineas) if lineas else "Aún no hay mensajes en esta sesión."
